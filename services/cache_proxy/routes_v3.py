"""
Cache Proxy API — V3 Enhanced Endpoints
=========================================
Endpointهای جدید V2 که بر روی providers و core ساخته شده‌اند.

New Endpoints:
POST  /api/v2/explorer/tx-history     — تاریخچه تراکنش (EVM, Tron, Solana, BTC, Polkadot)
POST  /api/v2/explorer/internal-tx    — Internal transactions (EVM only)
POST  /api/v2/explorer/token-tx       — Token transfer history (ERC20/TRC20)
POST  /api/v2/balance/native          — Balance native coin (EVM, Tron, Solana, BTC, Polkadot)
POST  /api/v2/balance/token           — Balance توکن (ERC20/TRC20)
POST  /api/v2/rpc/<chain>             — Generic RPC call (read-only, EVM only)
POST  /api/v2/broadcast               — Broadcast signed tx (EVM + Tron)
GET   /api/v2/token-metadata          — Metadata توکن (EVM, Tron)
GET   /api/v2/proxy-health            — Health check کامل همه providers
GET   /api/v2/metrics                 — Prometheus metrics / JSON counters
"""

import os
from datetime import datetime, timezone
from typing import Dict, Optional

from flask import Blueprint, jsonify, request, Response

from utils.logging_config import get_logger
from .core.rate_limiter import get_rate_limiter, rate_limit_ip
from .core.cache import get_cache_layer
from .core.key_pool import get_key_pool_manager
from .core.errors import ProxyError, RateLimitError

from .core.metrics import get_metrics
from .providers.evm_explorer import get_evm_explorer
from .providers.evm_rpc import get_evm_rpc_pool
from .providers.trongrid import get_trongrid_proxy
from .providers.tron_broadcast import get_tron_broadcast_provider
from .providers.solana import get_solana_proxy
from .providers.blockcypher import get_blockcypher_proxy
from .providers.blockstream import get_blockstream_proxy
from .providers.subscan import get_subscan_proxy

logger = get_logger(__file__)

# Blueprint جدید — با url_prefix یکسان (برای merge شدن با routes_v2)
cache_proxy_v3_bp = Blueprint("cache_proxy_v3", __name__, url_prefix="/api/v2")


# ============================================================
# Helperها
# ============================================================

# نگاشت chain به نوع blockchain برای routing
CHAIN_TYPE_MAP: Dict[str, str] = {
    "ethereum": "evm", "eth": "evm",
    "bsc": "evm", "bnb": "evm",
    "polygon": "evm", "matic": "evm",
    "avalanche": "evm", "avax": "evm",
    "arbitrum": "evm", "arb": "evm",
    "optimism": "evm", "op": "evm",
    "tron": "tron", "trx": "tron",
    "solana": "solana", "sol": "solana",
    "bitcoin": "utxo", "btc": "utxo",
    "dogecoin": "utxo", "doge": "utxo",
    "dash": "utxo",
    "litecoin": "utxo", "ltc": "utxo",
    "polkadot": "substrate", "dot": "substrate",
    "kusama": "substrate", "ksm": "substrate",
}


def _get_chain_type(chain: str) -> Optional[str]:
    """تشخیص نوع blockchain."""
    return CHAIN_TYPE_MAP.get(chain.lower().replace("-", "").replace(" ", ""))


def _error_response(message: str, status_code: int = 400, details: dict = None):
    return jsonify({
        "success": False,
        "error": message,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


def _decode_hex_bytes(hex_str: Optional[str]) -> str:
    """Decode a hex-encoded ABI result (bytes32 or string) to a readable string.
    
    Handles both:
    - Static bytes32: 0x555344540000... (padded with zeros)
    - Dynamic string with offset+length ABI encoding
    """
    if not hex_str or hex_str == "0x" or hex_str == "0x0":
        return ""
    clean = hex_str.removeprefix("0x")
    if not clean:
        return ""
    try:
        raw = bytes.fromhex(clean)
        # Try to detect dynamic string encoding (starts with 32-byte offset)
        if len(raw) > 64:
            offset = int.from_bytes(raw[0:32], "big")
            if 32 <= offset < len(raw):
                length_pos = offset
                str_len = int.from_bytes(raw[length_pos:length_pos + 32], "big")
                str_start = length_pos + 32
                str_end = str_start + str_len
                if str_end <= len(raw):
                    return raw[str_start:str_end].decode("utf-8", errors="replace")
        # Fallback: strip null bytes from bytes32
        return raw.rstrip(b"\x00").decode("utf-8", errors="replace").strip()
    except Exception:
        return hex_str


def _success_response(data, source: str = "proxy", extra: dict = None):
    response = {
        "success": True,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(data, dict):
        response.update(data)
    else:
        response["data"] = data
    if extra:
        response.update(extra)
    return jsonify(response), 200


# ============================================================
# تاریخچه تراکنش
# ============================================================


@cache_proxy_v3_bp.route("/explorer/tx-history", methods=["POST"])
def explorer_tx_history():
    """
    تاریخچه تراکنش‌های یک address.
    
    Body:
        chain (str): نام بلاکچین (الزامی)
        address (str): آدرس کیف پول (الزامی)
        page (int, optional): شماره صفحه (پیش‌فرض: 1)
        limit (int, optional): تعداد در هر صفحه (پیش‌فرض: 25)
    
    Returns:
        200: لیست تراکنش‌ها
        400: خطای اعتبارسنجی
        502: خطای provider
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        address = data.get("address", "").strip()
        page = int(data.get("page", 1))
        limit = min(int(data.get("limit", 25)), 100)

        if not chain or not address:
            return _error_response("chain and address are required")

        chain_type = _get_chain_type(chain)
        if not chain_type:
            return _error_response(f"Unsupported chain: {chain}")

        txs = None

        if chain_type == "evm":
            explorer = get_evm_explorer()
            txs = explorer.get_transactions(chain, address, page, limit)
        elif chain_type == "tron":
            proxy = get_trongrid_proxy()
            txs = proxy.get_transactions(address, limit)
        elif chain_type == "solana":
            proxy = get_solana_proxy()
            sigs = proxy.get_transactions(address, limit)
            if sigs:
                txs = []
                for sig in sigs:
                    detail = proxy.get_transaction_detail(sig.get("signature", ""))
                    if detail:
                        txs.append(detail)
            else:
                txs = None
        elif chain_type == "utxo":
            proxy = get_blockcypher_proxy()
            txs = proxy.get_transactions(chain, address, limit)
            # Fallback: اگر BlockCypher جواب نداد، Blockstream را امتحان کن
            if txs is None and chain in ("bitcoin", "btc"):
                bs_proxy = get_blockstream_proxy()
                bs_txs = bs_proxy.get_transactions(address, limit)
                if bs_txs:
                    txs = bs_txs
        elif chain_type == "substrate":
            proxy = get_subscan_proxy()
            txs = proxy.get_transactions(chain, address, max(0, page - 1), limit)

        if txs is None:
            return _error_response(f"No transaction data available for {chain}:{address}", 502)

        return _success_response({
            "transactions": txs,
            "count": len(txs),
            "chain": chain,
            "address": address,
        }, source="proxy")

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/explorer/tx-history error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Internal Transactions
# ============================================================


@cache_proxy_v3_bp.route("/explorer/internal-tx", methods=["POST"])
def explorer_internal_tx():
    """
    Internal transactions (فقط EVM).
    
    Body:
        chain (str): نام بلاکچین
        address (str): آدرس کیف پول
        page (int, optional): شماره صفحه
        limit (int, optional): تعداد در هر صفحه
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        address = data.get("address", "").strip()
        page = int(data.get("page", 1))
        limit = min(int(data.get("limit", 25)), 100)

        if not chain or not address:
            return _error_response("chain and address are required")

        chain_type = _get_chain_type(chain)
        if chain_type != "evm":
            return _error_response(f"Internal transactions not supported for {chain}")

        explorer = get_evm_explorer()
        txs = explorer.get_internal_transactions(chain, address, page, limit)

        if txs is None:
            return _error_response(f"No internal transactions for {chain}:{address}", 502)

        return _success_response({
            "transactions": txs,
            "count": len(txs),
            "chain": chain,
            "address": address,
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/explorer/internal-tx error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Token Transfer History
# ============================================================


@cache_proxy_v3_bp.route("/explorer/token-tx", methods=["POST"])
def explorer_token_tx():
    """
    Token transfer history.
    
    Body:
        chain (str): نام بلاکچین
        address (str): آدرس کیف پول
        page (int, optional): شماره صفحه
        limit (int, optional): تعداد
        contract_address (str, optional): فیلتر آدرس توکن
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        address = data.get("address", "").strip()
        page = int(data.get("page", 1))
        limit = min(int(data.get("limit", 25)), 100)
        contract_address = data.get("contract_address", "").strip() or None

        if not chain or not address:
            return _error_response("chain and address are required")

        chain_type = _get_chain_type(chain)
        txs = None

        if chain_type == "evm":
            explorer = get_evm_explorer()
            txs = explorer.get_token_transactions(chain, address, page, limit, contract_address)
        elif chain_type == "tron":
            proxy = get_trongrid_proxy()
            txs = proxy.get_trc20_transactions(address, limit, contract_address)
        else:
            return _error_response(f"Token transactions not supported for {chain}")

        if txs is None:
            return _error_response(f"No token transactions for {chain}:{address}", 502)

        return _success_response({
            "transactions": txs,
            "count": len(txs),
            "chain": chain,
            "address": address,
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/explorer/token-tx error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Native Balance
# ============================================================


@cache_proxy_v3_bp.route("/balance/native", methods=["POST"])
def balance_native():
    """
    دریافت balance native coin.
    
    Body:
        chain (str): نام بلاکچین (الزامی)
        address (str): آدرس کیف پول (الزامی)
    
    Returns:
        200: balance
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        address = data.get("address", "").strip()

        if not chain or not address:
            return _error_response("chain and address are required")

        chain_type = _get_chain_type(chain)
        balance = None

        if chain_type == "evm":
            # اول از RPC سریع، بعد explorer
            rpc = get_evm_rpc_pool()
            balance = rpc.get_balance(chain, address)
            if balance is not None:
                balance = str(balance)
            else:
                explorer = get_evm_explorer()
                balance = explorer.get_native_balance(chain, address)
        elif chain_type == "tron":
            proxy = get_trongrid_proxy()
            trx_balance = proxy.get_balance(address)
            if trx_balance is not None:
                balance = str(int(trx_balance * 1e6))  # TRX → SUN
        elif chain_type == "solana":
            proxy = get_solana_proxy()
            lamports = proxy.get_balance(address)
            if lamports is not None:
                balance = str(lamports)  # lamports
        elif chain_type == "utxo":
            proxy = get_blockcypher_proxy()
            btc_balance = proxy.get_balance(chain, address)
            if btc_balance is not None:
                balance = str(int(btc_balance * 1e8))  # BTC → satoshi
            else:
                # Fallback: Blockstream
                bs_proxy = get_blockstream_proxy()
                sat = bs_proxy.get_balance(address)
                if sat is not None:
                    balance = str(sat)
        elif chain_type == "substrate":
            proxy = get_subscan_proxy()
            dot_balance = proxy.get_balance(chain, address)
            if dot_balance is not None:
                balance = str(int(dot_balance * 1e10))  # DOT → Planck
        else:
            return _error_response(f"Unsupported chain: {chain}")

        if balance is None:
            return _error_response(f"Could not fetch balance for {chain}:{address}", 502)

        return _success_response({
            "chain": chain,
            "address": address,
            "balance": balance,
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/balance/native error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Token Balance
# ============================================================


@cache_proxy_v3_bp.route("/balance/token", methods=["POST"])
def balance_token():
    """
    دریافت balance یک توکن (ERC20/TRC20).
    
    Body:
        chain (str): نام بلاکچین (الزامی)
        address (str): آدرس کیف پول (الزامی)
        contract_address (str): آدرس قرارداد توکن (الزامی)
    
    Returns:
        200: balance
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        address = data.get("address", "").strip()
        contract_address = data.get("contract_address", "").strip()

        if not chain or not address or not contract_address:
            return _error_response("chain, address, and contract_address are required")

        chain_type = _get_chain_type(chain)
        balance_raw = None

        if chain_type == "evm":
            # EVM: ابتدا از RPC (eth_call)، سپس explorer
            rpc = get_evm_rpc_pool()
            # ABI: balanceOf(address) → 0x70a08231
            data_hex = "0x70a08231" + address[2:].zfill(64).lower()
            result = rpc.call_contract(chain, contract_address, data_hex)
            if result:
                balance_raw = str(int(result, 16))
            else:
                # Fallback explorer
                explorer = get_evm_explorer()
                balance_raw = explorer.get_token_balance(chain, address, contract_address)
        elif chain_type == "tron":
            proxy = get_trongrid_proxy()
            balance_raw = proxy.get_trc20_balance(address, contract_address)
        else:
            return _error_response(f"Token balance not supported for {chain}")

        if balance_raw is None:
            return _error_response(f"Could not fetch token balance for {chain}:{address}", 502)

        return _success_response({
            "chain": chain,
            "address": address,
            "contract_address": contract_address,
            "balance": balance_raw,
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/balance/token error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Generic RPC Call
# ============================================================


@cache_proxy_v3_bp.route("/rpc/<chain>", methods=["POST"])
def rpc_call(chain: str):
    """
    Generic RPC call (فقط read-only).
    
    Args:
        chain: نام بلاکچین (در URL)
    
    Body:
        method (str): متد JSON-RPC (الزامی)
        params (list, optional): پارامترها
    
    Returns:
        200: result
    """
    try:
        data = request.get_json(silent=True) or {}
        method = data.get("method", "").strip()
        params = data.get("params", [])

        if not method:
            return _error_response("method is required")

        chain_lower = chain.strip().lower()
        chain_type = _get_chain_type(chain_lower)

        if chain_type != "evm":
            return _error_response(f"RPC calls not supported for {chain_lower}")

        rpc = get_evm_rpc_pool()
        result = rpc.call(chain_lower, method, params)

        if result is None:
            return _error_response(f"RPC call failed: {method}", 502)

        return _success_response({
            "chain": chain_lower,
            "method": method,
            "result": result,
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/rpc/%s error: %s", chain, e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Broadcast Signed Transaction
# ============================================================


@cache_proxy_v3_bp.route("/broadcast", methods=["POST"])
def broadcast_transaction():
    """
    Broadcast یک تراکنش امضا شده.
    
    ⚠️ مهم: بک‌اند هرگز signedTx را ذخیره/لاگ نمی‌کند.
    فقط به RPC فوروارد می‌کند. Non-custodial preserved.
    
    Body:
        chain (str): نام بلاکچین (الزامی)
        signed_tx (str): signed raw transaction hex (الزامی)
        simulate (bool, optional): فقط شبیه‌سازی (پیش‌فرض: false)
    
    Returns:
        200: txHash
    """
    try:
        data = request.get_json(silent=True) or {}
        chain = data.get("chain", "").strip().lower()
        signed_tx = data.get("signed_tx", "").strip()
        simulate = bool(data.get("simulate", False))

        if not chain or not signed_tx:
            return _error_response("chain and signed_tx are required")

        chain_type = _get_chain_type(chain)
        if chain_type not in ("evm", "tron"):
            return _error_response(f"Broadcast not supported for {chain}")

        # Rate limit stricter for broadcast
        get_rate_limiter().check_broadcast(request.remote_addr or "unknown")

        # نباید signedTx را در لاگ بنویسیم
        tx_preview = signed_tx[:16] + "..." if len(signed_tx) > 16 else signed_tx[:8]
        logger.info("Broadcast request: chain=%s, tx=%s, chain_type=%s, simulate=%s",
                     chain, tx_preview, chain_type, simulate)

        if simulate:
            return _handle_broadcast_simulate(chain, chain_type, signed_tx)

        # Broadcast واقعی
        tx_hash = None
        provider = None

        if chain_type == "evm":
            rpc = get_evm_rpc_pool()
            tx_hash = rpc.broadcast_transaction(chain, signed_tx)
            provider = "evm_rpc_pool"
        elif chain_type == "tron":
            tron_broadcast = get_tron_broadcast_provider()
            tx_hash = tron_broadcast.broadcast(signed_tx)
            provider = "trongrid_broadcasthex"

        if not tx_hash:
            provider_name = provider or "unknown"
            return _error_response(
                f"Broadcast failed via {provider_name}. "
                "The transaction could not be submitted to the network.",
                502,
            )

        return _success_response({
            "chain": chain,
            "tx_hash": tx_hash,
            "provider": provider,
            "note": "Non-custodial: signedTx was not stored or logged",
        })

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/broadcast error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


def _handle_broadcast_simulate(chain: str, chain_type: str, signed_tx: str):
    """شبیه‌سازی broadcast بدون ارسال واقعی (فقط EVM)."""
    if chain_type == "evm":
        rpc = get_evm_rpc_pool()
        result = rpc.call(chain, "eth_estimateGas", [{"data": signed_tx}])
        if result:
            return _success_response({
                "chain": chain,
                "simulate": True,
                "estimated_gas": str(result),
            })
        return _error_response("Gas estimation failed", 502)
    # Tron: تخمین پیش‌فرض (بدون شبیه‌سازی اختصاصی)
    return _success_response({
        "chain": chain,
        "simulate": True,
        "estimated_fee": "0.1",
        "note": "Tron fee is fixed (~0.1 TRX for simple transfer)",
    })


# ============================================================
# Token Metadata
# ============================================================


@cache_proxy_v3_bp.route("/token-metadata", methods=["GET"])
def token_metadata():
    """
    دریافت metadata یک توکن (decimals, symbol, name).
    
    Query Parameters:
        chain (str): نام بلاکچین (الزامی)
        contract_address (str): آدرس قرارداد توکن (الزامی)
    
    Returns:
        200: metadata
    """
    try:
        chain = request.args.get("chain", "").strip().lower()
        contract_address = request.args.get("contract_address", "").strip()

        if not chain or not contract_address:
            return _error_response("chain and contract_address are required")

        chain_type = _get_chain_type(chain)
        metadata = None

        if chain_type == "evm":
            explorer = get_evm_explorer()
            # دریافت از explorer
            info = explorer.get_token_metadata(chain, contract_address)
            if info:
                metadata = {
                    "contract_address": contract_address,
                    "symbol": info.get("symbol", ""),
                    "name": info.get("name", ""),
                    "decimals": int(info.get("divisor", info.get("decimals", 18))),
                }
            else:
                # Fallback: از RPC بخوان
                rpc = get_evm_rpc_pool()
                # symbol(): 0x95d89b41
                symbol_hex = "0x95d89b41"
                symbol_result = rpc.call_contract(chain, contract_address, symbol_hex)
                # decimals(): 0x313ce567
                dec_hex = "0x313ce567"
                dec_result = rpc.call_contract(chain, contract_address, dec_hex)
                # name(): 0x06fdde03
                name_hex = "0x06fdde03"
                name_result = rpc.call_contract(chain, contract_address, name_hex)

                if symbol_result or dec_result:
                    metadata = {
                        "contract_address": contract_address,
                        "symbol": _decode_hex_bytes(symbol_result),
                        "name": _decode_hex_bytes(name_result),
                        "decimals": int(dec_result, 16) if dec_result else 18,
                        "source": "rpc_fallback",
                    }

        elif chain_type == "tron":
            proxy = get_trongrid_proxy()
            info = proxy.get_token_info(contract_address)
            if info:
                metadata = {
                    "contract_address": contract_address,
                    "symbol": info.get("symbol", info.get("abbr", "")),
                    "name": info.get("name", ""),
                    "decimals": int(info.get("decimals", 18)),
                    "source": "trongrid",
                }

        if not metadata:
            return _error_response(
                f"Token metadata not found for {chain}:{contract_address}", 404
            )

        return _success_response({"token": metadata})

    except RateLimitError as e:
        return _error_response(str(e), 429)
    except ProxyError as e:
        return _error_response(str(e), e.status_code)
    except Exception as e:
        logger.error("v2/token-metadata error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Proxy Health Check (Full)
# ============================================================


@cache_proxy_v3_bp.route("/proxy-health", methods=["GET"])
def proxy_health():
    """
    Health check کامل همه providers + core modules.
    
    Returns:
        200: وضعیت کامل proxy
    """
    try:
        cache_layer = get_cache_layer()
        rate_limiter = get_rate_limiter()
        pool_manager = get_key_pool_manager()

        health = {
            "success": True,
            "service": "Cache Proxy V3 — Hybrid Backend",
            "version": "3.0.0",
            "status": "healthy",
            "modules": {
                "cache": cache_layer.get_stats(),
                "rate_limiter": rate_limiter.get_status(),
                "key_pools": pool_manager.get_status_all(),
                "metrics": get_metrics().export_json(),
            },
            "providers": {
                "evm_explorer": {"chains": get_evm_explorer().get_supported_chains()},
                "evm_rpc": {"providers": len(get_evm_rpc_pool()._providers) if hasattr(get_evm_rpc_pool(), '_providers') else 0},
                "trongrid": {"status": "active"},
                "tron_broadcast": get_tron_broadcast_provider().check_health(),
                "solana": {"chains": get_solana_proxy().get_supported_chains()},
                "blockcypher": {"chains": ["btc", "doge", "dash", "ltc"]},
                "blockstream": {"chains": ["bitcoin"], "note": "Public API, no key required"},
                "subscan": {"chains": ["polkadot", "kusama"]},
            },
            "note": "All endpoints are public — Non-Custodial architecture",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return jsonify(health), 200

    except Exception as e:
        logger.error("v2/proxy-health error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "error": str(e),
        }), 500


# ============================================================
# Admin: Reload API Keys (بدون ری‌استارت)
# ============================================================


@cache_proxy_v3_bp.route("/admin/reload-keys", methods=["POST"])
def admin_reload_keys():
    """
    بارگذاری مجدد همه API Keyها از فایل env.
    بدون نیاز به ری‌استارت سرویس.

    Body (optional):
        secret (str): رمز تأیید (پیش‌فرض: از env به نام ADMIN_SECRET)

    Returns:
        200: گزارش تعداد کلیدهای جدید بارگذاری شده
        403: رمز اشتباه
    """
    try:
        data = request.get_json(silent=True) or {}
        provided = data.get("secret", "")
        expected = os.environ.get("ADMIN_SECRET", "")

        if expected and provided != expected:
            return _error_response("Forbidden: invalid secret", 403)

        mgr = get_key_pool_manager()
        report = mgr.reload()

        logger.info("Admin: keys reloaded — %s", report)

        return _success_response({
            "message": "All API key pools reloaded successfully",
            "pools": report,
            "total_pools": len(report),
        })

    except Exception as e:
        logger.error("admin/reload-keys error: %s", e, exc_info=True)
        return _error_response(str(e), 500)


# ============================================================
# Prometheus Metrics Export
# ============================================================


@cache_proxy_v3_bp.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """
    خروجی metrics برای Prometheus scraping.

    Returns:
        200: metrics در فرمت Prometheus
        200: JSON metrics اگر prometheus_client نصب نباشد
    """
    try:
        metrics = get_metrics()

        if metrics.is_prometheus_enabled:
            output = metrics.export_prometheus()
            if output:
                return Response(output, mimetype="text/plain; version=0.0.4")

        return jsonify({
            "success": True,
            "metrics": metrics.export_json(),
            "note": "Install prometheus_client for native Prometheus format",
        }), 200

    except Exception as e:
        logger.error("v2/metrics error: %s", e, exc_info=True)
        return _error_response(str(e), 500)
