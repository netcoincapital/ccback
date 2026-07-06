"""
Block Scanner — Non-Custodial Transaction Notification Proxy
==============================================================

معماری Active Address Registry:
به جای "همه بلاک‌ها را اسکن کن ← همه را کش کن ← بعداً فیلتر کن"
روش درست: "فقط آدرس‌های فعال را ثبت کن ← فقط برای آن‌ها اسکن کن ← کش محدود"

🔑 سه اصل معماری:
  1. Active Address Registry: فقط آدرس‌هایی که در ۵ دقیقه اخیر دیده شده‌اند
  2. Selective Scanning: فقط تراکنش‌های مربوط به آدرس‌های فعال را کش کن
  3. Bounded Cache: TTL ۵ دقیقه + MAX_ACTIVE ۱ میلیون → RAM ≤ ~۵۰MB

📊 بار ثابت روی Explorer API: ~۲۱ req/min (مستقل از تعداد کاربران)
   ETH: ۸ req/min | BSC: ۸ req/min | TRX: ۲ req/min | SOL: ۲ req/min | BTC: ۱ req/min

⚡ Non-blocking: همه اسکنرها در نخ‌های پس‌زمینه اجرا می‌شوند.
⚡ Warmup: اسکنرها از لحظه import شروع به کار می‌کنند.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timezone

import requests

from utils.logging_config import get_logger
# Lazy import for FCM push — only imported when needed
_fcm_push = None
def _send_fcm(tx_data):
    global _fcm_push
    if _fcm_push is None:
        try:
            from .fcm_push import notify_new_transaction
            _fcm_push = notify_new_transaction
        except Exception:
            _fcm_push = False
    if _fcm_push:
        try:
            _fcm_push(tx_data)
        except Exception as e:
            logger.debug("FCM: push error: %s", e)

logger = get_logger(__file__)


# ============================================================
# Core Data Structures
# ============================================================

# Active Address Registry: address → lastSeenTimestamp (epoch ms)
_active_addresses: Dict[str, float] = {}

# Transaction Cache: address → [{hash, blockchain, blockNumber, timestamp}]
_tx_cache: Dict[str, List[Dict[str, Any]]] = {}

# Last scanned block number per blockchain
_last_scanned: Dict[str, int] = {
    "ETH": 0,
    "BSC": 0,
    "TRX": 0,
    "SOL": 0,
    "BTC": 0,
}

# Thread lock for concurrent access
_lock = threading.Lock()

# Constants
TTL_MS = 5 * 60 * 1000          # 5 دقيقه
TTL_S = 5 * 60                  # 5 دقيقه (برحسب ثانيه)
MAX_ACTIVE = 1_000_000          # حداكثر 1 ميليون آدرس فعال
SLEEP_BETWEEN_BLOCKS_S = 1.0   # 1 ثانيه بين بلاك‌ها (Throttle)


# ============================================================
# Public API
# ============================================================

def mark_active(address: str) -> None:
    """
    ثبت يك آدرس به عنوان فعال.
    توسط endpoint /api/v2/notifications صدا زده مي‌شود.
    اگر تعداد آدرس‌ها از MAX_ACTIVE بيشتر شود، قديمي‌ترين‌ها حذف مي‌شوند.
    """
    addr = address.lower().strip()
    if not addr:
        return

    with _lock:
        _active_addresses[addr] = time.time() * 1000  # epoch ms

        if len(_active_addresses) > MAX_ACTIVE:
            # حذف قديمي‌ترين آدرس‌ها
            sorted_addrs = sorted(
                _active_addresses.items(), key=lambda x: x[1]
            )
            to_delete = sorted_addrs[:len(sorted_addrs) - MAX_ACTIVE]
            for addr_del, _ in to_delete:
                _active_addresses.pop(addr_del, None)
                _tx_cache.pop(addr_del, None)


def get_cached_txs(address: str) -> List[Dict[str, Any]]:
    """برگرداندن تراكنش‌هاي كش شده براي يك آدرس."""
    addr = address.lower().strip()
    with _lock:
        return list(_tx_cache.get(addr, []))


def get_active_count() -> int:
    """تعداد آدرس‌هاي فعال فعلي."""
    with _lock:
        return len(_active_addresses)


def get_cache_stats() -> Dict[str, Any]:
    """آمار وضعيت كش."""
    with _lock:
        total_txs = sum(len(txs) for txs in _tx_cache.values())
        return {
            "active_addresses": len(_active_addresses),
            "cached_transactions": total_txs,
            "last_scanned": dict(_last_scanned),
        }


def get_last_scanned() -> Dict[str, int]:
    """آخرين بلاك اسكن شده براي هر بلاكچين."""
    with _lock:
        return dict(_last_scanned)


# ============================================================
# Core functions
# ============================================================

def _is_active(to_address: str) -> bool:
    """بررسي O(1) كه آيا آدرس مقصد فعال است."""
    return to_address in _active_addresses


def _cache_tx(to_address: str, tx_data: Dict[str, Any]) -> None:
    """كش كردن يك تراكنش براي آدرس مقصد."""
    if to_address not in _tx_cache:
        _tx_cache[to_address] = []
    _tx_cache[to_address].append(tx_data)


def _cleanup() -> None:
    """پاكسازي كش: حذف آدرس‌هايي كه TTL آن‌ها تمام شده."""
    now_ms = time.time() * 1000
    with _lock:
        expired = [
            addr for addr, last_seen in _active_addresses.items()
            if now_ms - last_seen > TTL_MS
        ]
        for addr in expired:
            _active_addresses.pop(addr, None)
            _tx_cache.pop(addr, None)

    if expired:
        logger.debug("BlockScanner: cleaned up %d expired addresses", len(expired))


# ============================================================
# EVM Block Scanner (Ethereum, BSC, Polygon, Avalanche, etc.)
# ============================================================

def _fetch_eth_block_number(rpc_url: str) -> Optional[int]:
    """دريافت آخرين شماره بلاك از RPC."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1,
        }
        resp = requests.post(rpc_url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result")
            if result:
                return int(result, 16)
    except Exception as e:
        logger.debug("BlockScanner: RPC blockNumber failed: %s", e)
    return None


def _fetch_eth_block_txs(rpc_url: str, block_number: int) -> List[Dict[str, Any]]:
    """دريافت تراكنش‌هاي يك بلاك از RPC."""
    try:
        hex_block = hex(block_number)
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex_block, True],
            "id": 1,
        }
        resp = requests.post(rpc_url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            block = data.get("result")
            if block:
                return block.get("transactions", [])
    except Exception as e:
        logger.debug("BlockScanner: RPC block txs failed: %s", e)
    return []


def scan_evm_chain(
    chain_name: str,
    chain_key: str,
    rpc_url: str,
) -> None:
    """
    اسكنر عمومي براي بلاكچين‌هاي EVM.
    فقط آدرس‌هاي موجود در activeAddresses را كش مي‌كند (Set O(1) lookup).
    """
    try:
        # اگر هيچ آدرسي فعال نيست، اسكن نكن
        if get_active_count() == 0:
            return

        latest_block = _fetch_eth_block_number(rpc_url)
        if latest_block is None:
            logger.warning("BlockScanner/%s: could not fetch latest block", chain_name)
            return

        with _lock:
            current_last = _last_scanned.get(chain_key, 0)

        if latest_block <= current_last:
            return

        # اسكن بلاك‌هاي جديد
        scanned_count = 0
        for block_num in range(current_last + 1, latest_block + 1):
            txs = _fetch_eth_block_txs(rpc_url, block_num)
            for tx in txs:
                tx_to = tx.get("to")
                if not tx_to:
                    continue
                tx_to = tx_to.lower()

                # O(1) Set lookup — فقط آدرس‌هاي فعال
                if not _is_active(tx_to):
                    continue

                tx_data = {
                    "hash": tx.get("hash", ""),
                    "blockchain": chain_name,
                    "block_number": block_num,
                    "from": tx.get("from", "").lower(),
                    "to": tx_to,
                    "value_wei": tx.get("value", "0x0"),
                    "timestamp": int(time.time() * 1000),
                }
                with _lock:
                    _cache_tx(tx_to, tx_data)

                # Send FCM push notification
                _send_fcm(tx_data)

                # Also cache for sender (outbound direction)
                tx_from = tx.get("from", "").lower()
                if tx_from and tx_from != "0x" and _is_active(tx_from):
                    with _lock:
                        _cache_tx(tx_from, tx_data)

            scanned_count += 1

            # Throttle: 1 ثانيه بين بلاك‌ها (براي Recovery)
            if scanned_count > 1:
                time.sleep(SLEEP_BETWEEN_BLOCKS_S)

        with _lock:
            _last_scanned[chain_key] = latest_block

        if scanned_count > 0:
            logger.debug(
                "BlockScanner/%s: scanned %d blocks (latest=%d, active=%d)",
                chain_name, scanned_count, latest_block, get_active_count(),
            )

    except Exception as e:
        logger.warning("BlockScanner/%s: scan error: %s", chain_name, e)


# ============================================================
# Blockchain-specific scanners (هر كدام در نخ مجزا)
# ============================================================

def scan_ethereum():
    """اسكنر Ethereum — از eth.llamarpc.com استفاده مي‌كند."""
    scan_evm_chain("Ethereum", "ETH", "https://eth.llamarpc.com")


def scan_bsc():
    """اسكنر BSC — از bsc-dataseed.binance.org استفاده مي‌كند."""
    scan_evm_chain("BSC", "BSC", "https://bsc-dataseed.binance.org")


def scan_polygon():
    """اسكنر Polygon — از polygon-rpc.com استفاده مي‌كند."""
    scan_evm_chain("Polygon", "POLYGON", "https://polygon-rpc.com")


def scan_avalanche():
    """اسكنر Avalanche C-Chain."""
    scan_evm_chain("Avalanche", "AVAX", "https://api.avax.network/ext/bc/C/rpc")


def scan_arbitrum():
    """اسكنر Arbitrum."""
    scan_evm_chain("Arbitrum", "ARBITRUM", "https://arb1.arbitrum.io/rpc")


def scan_optimism():
    """اسكنر Optimism."""
    scan_evm_chain("Optimism", "OPTIMISM", "https://mainnet.optimism.io")


def scan_tron():
    """اسكنر Tron — از Trongrid API استفاده مي‌كند."""
    try:
        if get_active_count() == 0:
            return

        resp = requests.get(
            "https://api.trongrid.io/v1/blocks/latest",
            timeout=10,
        )
        if resp.status_code != 200:
            return

        data = resp.json()
        blocks = data.get("data", [])
        if not blocks:
            return

        latest_block = blocks[0].get("number", 0)
        with _lock:
            current_last = _last_scanned.get("TRX", 0)

        if latest_block <= current_last:
            return

        # فقط آخرين بلاك را بررسي كن (براي سادگي)
        block_resp = requests.get(
            f"https://api.trongrid.io/v1/blocks/{latest_block}/transactions",
            timeout=10,
        )
        if block_resp.status_code != 200:
            return

        txs_data = block_resp.json()
        for tx in txs_data.get("data", []):
            raw_data = tx.get("raw_data", {})
            contracts = raw_data.get("contract", [])
            for contract in contracts:
                param = contract.get("parameter", {}).get("value", {})
                to_addr = param.get("to_address", "")
                owner_addr = param.get("owner_address", "").lower()
                tx_data = {
                    "hash": tx.get("txID", ""),
                    "blockchain": "Tron",
                    "block_number": latest_block,
                    "from": owner_addr,
                    "to": to_addr.lower() if to_addr else "",
                    "value_sun": param.get("amount", 0),
                    "timestamp": int(time.time() * 1000),
                }
                # Cache for recipient (inbound direction)
                if to_addr and _is_active(to_addr):
                    with _lock:
                        _cache_tx(to_addr, tx_data)

                # Also cache for sender (outbound direction)
                if owner_addr and _is_active(owner_addr) and (not to_addr or to_addr.lower() != owner_addr):
                    with _lock:
                        _cache_tx(owner_addr, tx_data)

                # Send FCM push notification for any active address in this tx
                if (_is_active(to_addr) if to_addr else False) or (_is_active(owner_addr) if owner_addr else False):
                    _send_fcm(tx_data)

        with _lock:
            _last_scanned["TRX"] = latest_block

    except Exception as e:
        logger.debug("BlockScanner/Tron: scan error: %s", e)


def _fetch_sol_block(slot: int) -> Optional[Dict[str, Any]]:
    """دریافت یک بلاک Solana با جزئیات تراکنش‌ها."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "getBlock",
            "params": [
                slot,
                {"encoding": "jsonParsed", "transactionDetails": "full", "maxSupportedTransactionVersion": 0},
            ],
            "id": 1,
        }
        resp = requests.post(
            "https://api.mainnet-beta.solana.com",
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("result")
    except Exception as e:
        logger.debug("BlockScanner/Solana: fetch block error: %s", e)
    return None


def scan_solana():
    """اسكنر Solana — از Solana RPC استفاده مي‌كند."""
    try:
        if get_active_count() == 0:
            return

        # دریافت آخرین slot
        payload = {
            "jsonrpc": "2.0",
            "method": "getSlot",
            "params": [],
            "id": 1,
        }
        resp = requests.post(
            "https://api.mainnet-beta.solana.com",
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            return
        latest_slot = resp.json().get("result", 0)
        if not latest_slot:
            return

        with _lock:
            current_last = _last_scanned.get("SOL", 0)

        if latest_slot <= current_last:
            return

        # فقط آخرين بلاك را بررسي كن
        block = _fetch_sol_block(latest_slot)
        if not block:
            return

        for tx_obj in block.get("transactions", []):
            meta = tx_obj.get("meta", {})
            if meta.get("err"):
                continue  # رد کردن تراکنش‌های ناموفق

            tx = tx_obj.get("transaction", {})
            msg = tx.get("message", {})
            account_keys = msg.get("accountKeys", [])
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])

            if not account_keys or not pre_balances or not post_balances:
                continue

            # بررسی هر account در تراکنش
            for i, account in enumerate(account_keys):
                pubkey = account.get("pubkey", "")
                if i >= len(pre_balances) or i >= len(post_balances):
                    continue
                if not pubkey or not _is_active(pubkey):
                    continue

                sol_amount = (post_balances[i] - pre_balances[i]) / 1e9
                if sol_amount == 0:
                    continue

                direction = "outbound" if sol_amount < 0 else "inbound"
                tx_hash = tx_obj.get("transaction", {}).get("signatures", [None])[0] or ""
                tx_data = {
                    "hash": tx_hash,
                    "blockchain": "Solana",
                    "block_number": latest_slot,
                    "from": pubkey if direction == "outbound" else "",
                    "to": pubkey if direction == "inbound" else "",
                    "value_lamports": abs(post_balances[i] - pre_balances[i]),
                    "timestamp": block.get("blockTime", int(time.time())),
                }
                with _lock:
                    _cache_tx(pubkey, tx_data)
                _send_fcm(tx_data)

        with _lock:
            _last_scanned["SOL"] = latest_slot

    except Exception as e:
        logger.debug("BlockScanner/Solana: scan error: %s", e)


def scan_bitcoin():
    """اسكنر Bitcoin — از blockstream.info API استفاده مي‌كند."""
    try:
        if get_active_count() == 0:
            return

        resp = requests.get(
            "https://blockstream.info/api/blocks/tip/height",
            timeout=10,
        )
        if resp.status_code != 200:
            return

        latest_height = int(resp.text.strip())
        with _lock:
            current_last = _last_scanned.get("BTC", 0)

        if latest_height <= current_last:
            return

        # فقط آخرين بلاك را بررسي كن
        block_resp = requests.get(
            f"https://blockstream.info/api/block-height/{latest_height}",
            timeout=10,
        )
        if block_resp.status_code != 200:
            return

        block_hash = block_resp.text.strip()
        txs_resp = requests.get(
            f"https://blockstream.info/api/block/{block_hash}/txs",
            timeout=10,
        )
        if txs_resp.status_code != 200:
            return

        for tx in txs_resp.json():
            # Determine sender from first vin's prevout (if available)
            vin_list = tx.get("vin", [])
            sender_addr = ""
            if vin_list:
                prevout = vin_list[0].get("prevout", {})
                sender_addr = prevout.get("scriptpubkey_address", "")

            # Check vout (inbound) — recipient
            for vout in tx.get("vout", []):
                script = vout.get("scriptpubkey_address", "")
                if script and _is_active(script):
                    tx_data = {
                        "hash": tx.get("txid", ""),
                        "blockchain": "Bitcoin",
                        "block_number": latest_height,
                        "from": sender_addr,
                        "to": script,
                        "value_sat": vout.get("value", 0),
                        "timestamp": int(time.time() * 1000),
                    }
                    with _lock:
                        _cache_tx(script, tx_data)
                    _send_fcm(tx_data)

            # Check vin (outbound) — sender
            if sender_addr and _is_active(sender_addr):
                total_out = sum(
                    vout.get("value", 0) for vout in tx.get("vout", [])
                )
                tx_data_out = {
                    "hash": tx.get("txid", ""),
                    "blockchain": "Bitcoin",
                    "block_number": latest_height,
                    "from": sender_addr,
                    "to": "",
                    "value_sat": total_out,
                    "timestamp": int(time.time() * 1000),
                }
                with _lock:
                    _cache_tx(sender_addr, tx_data_out)
                _send_fcm(tx_data_out)

        with _lock:
            _last_scanned["BTC"] = latest_height

    except Exception as e:
        logger.debug("BlockScanner/Bitcoin: scan error: %s", e)


# ============================================================
# Background Workers
# ============================================================

def _cleanup_worker():
    """پاكسازي دوره‌اي كش — هر ۶۰ ثانيه."""
    while True:
        time.sleep(60)
        try:
            _cleanup()
        except Exception as e:
            logger.error("BlockScanner: cleanup error: %s", e)


def _run_scanner(scanner_fn, interval_s: int, name: str):
    """اجراي يك اسكنر در يك حلقه بي‌نهايت با فاصله مشخص."""
    logger.info("BlockScanner: starting %s (every %ds)", name, interval_s)
    while True:
        try:
            scanner_fn()
        except Exception as e:
            logger.error("BlockScanner/%s: error: %s", name, e)
        time.sleep(interval_s)


def _start_worker(scanner_fn, interval_s: int, name: str) -> threading.Thread:
    """شروع يك اسكنر در نخ پس‌زمینه."""
    thread = threading.Thread(
        target=_run_scanner,
        args=(scanner_fn, interval_s, name),
        daemon=True,
        name=f"BlockScanner-{name}",
    )
    thread.start()
    return thread


# ============================================================
# Start all workers on import
# ============================================================

_workers: List[threading.Thread] = []

def start_all_scanners():
    """شروع همه اسكنرها. هنگام import صدا زده مي‌شود."""
    global _workers

    if _workers:
        return  # فقط يكبار

    # Cleanup worker
    cleanup_thread = threading.Thread(
        target=_cleanup_worker,
        daemon=True,
        name="BlockScanner-Cleanup",
    )
    cleanup_thread.start()
    _workers.append(cleanup_thread)

    # EVM chains: هر ۱۵ ثانيه
    _workers.append(_start_worker(scan_ethereum, 15, "ETH"))
    _workers.append(_start_worker(scan_bsc, 15, "BSC"))
    _workers.append(_start_worker(scan_polygon, 15, "Polygon"))
    _workers.append(_start_worker(scan_avalanche, 15, "Avalanche"))
    _workers.append(_start_worker(scan_arbitrum, 15, "Arbitrum"))
    _workers.append(_start_worker(scan_optimism, 15, "Optimism"))

    # Non-EVM chains: هر ۳۰ ثانيه
    _workers.append(_start_worker(scan_tron, 30, "Tron"))
    _workers.append(_start_worker(scan_solana, 30, "Solana"))

    # Bitcoin: هر ۶۰ ثانيه
    _workers.append(_start_worker(scan_bitcoin, 60, "Bitcoin"))

    logger.info(
        "BlockScanner: started %d scanners + cleanup worker",
        len(_workers) - 1,
    )


# Scannerها ديگر خودكار شروع نمی‌شوند.
# فقط در workerای كه قفل background job را دارد (app.py) اجرا می‌شوند.
# اين كار از اشباع Gunicorn workers جلوگيری می‌كند.
