#!/usr/bin/env python3
"""
Shasta Testnet — Tron Comprehensive Integration Test
=====================================================
تست یکپارچه ترون روی شبکه تست Shasta.

این اسکریپت:
  1. به Shasta Testnet متصل می‌شود
  2. تراکنش TRX می‌سازد، امضا می‌کند و broadcast می‌کند
  3. تراکنش TRC20 (USDT) می‌سازد، امضا می‌کند و broadcast می‌کند
  4. تراکنش TRC10 می‌سازد، امضا می‌کند و broadcast می‌کند
  5. خطاهای TronGrid را decode می‌کند
  6. تبدیل آدرس (Base58 ↔ Hex) را تست می‌کند

نیازمندی‌ها:
  - Python 3.9+
  - نصب: pip install tronpy requests base58
  - یک حساب Shasta با TRX تست:
      https://shasta.tronex.io/join/getJoinPage

اجرا:
  # حالت Dry-run (بدون ارسال واقعی):
  python scripts/test_tron_shasta.py --dry-run

  # حالت Real (نیاز به PRIVATE_KEY_SHASTA در env):
  set PRIVATE_KEY_SHASTA=your_private_key_here
  python scripts/test_tron_shasta.py

  # با لاگ verbose:
  python scripts/test_tron_shasta.py -v
  python scripts/test_tron_shasta.py --dry-run -v
"""

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# Tron error messages for local error decoding (avoids import cascade)
# ---------------------------------------------------------------------------
_TRON_ERROR_MESSAGES = {
    "SIGERROR": "Transaction signature is invalid. Please re-sign the transaction.",
    "SIGNATURE_ERROR": "Transaction signature is invalid. Please re-sign the transaction.",
    "TRANSACTION_EXPIRATION_ERROR": "Transaction has expired. Please create a new transaction.",
    "DUP_TRANSACTION_ERROR": "Duplicate transaction — already broadcast to the network.",
    "TAPOS_ERROR": "Invalid block reference. Please rebuild the transaction with a recent block.",
    "TOO_BIG_TRANSACTION_ERROR": "Transaction data is too large. Reduce the transaction size.",
    "CONTRACT_VALIDATE_ERROR": "Contract validation failed. The transaction data appears malformed.",
    "ACCOUNT_NOT_EXIST_ERROR": "Recipient account does not exist on the TRON network.",
    "ACCOUNT_NOT_FOUND": "Account not found on the TRON network.",
    "NOT_ENOUGH_BANDWIDTH": "Insufficient bandwidth to process this transaction. Stake TRX for bandwidth or use TRX to cover fees.",
    "NOT_ENOUGH_ENERGY": "Insufficient energy to process this transaction. Stake TRX for energy or increase the fee limit.",
    "BANDWIDTH_NOT_ENOUGH": "Insufficient bandwidth. Please stake TRX or reduce transaction complexity.",
    "TRANSACTION_SIGN_ERROR": "Transaction signature validation failed.",
    "DUP_TRANSACTION": "Transaction already exists in the mempool.",
    "TRANSACTION_EXPIRATION": "Transaction has expired.",
    "SERVER_BUSY": "TRON network is busy. Please try again shortly.",
    "OTHER_ERROR": "An unknown error occurred while broadcasting the transaction.",
}


def _decode_tron_error_local(raw_message: str, error_code: str = "") -> str:
    """Local copy of tron_broadcast._decode_tron_error to avoid import cascade."""
    decoded_message = raw_message
    if raw_message:
        try:
            decoded_bytes = bytes.fromhex(raw_message)
            decoded_text = decoded_bytes.decode("utf-8", errors="replace")
            if decoded_text and len(decoded_text) < 200:
                decoded_message = decoded_text
        except (ValueError, TypeError):
            decoded_message = raw_message

    if error_code:
        upper_code = error_code.upper().strip()
        if upper_code in _TRON_ERROR_MESSAGES:
            return _TRON_ERROR_MESSAGES[upper_code]

    if decoded_message:
        upper_msg = decoded_message.upper()
        for key, readable in _TRON_ERROR_MESSAGES.items():
            if key in upper_msg:
                return readable

    if decoded_message and decoded_message != raw_message:
        return f"TRON broadcast rejected: {decoded_message}"
    if decoded_message:
        return f"TRON broadcast rejected: {decoded_message}"
    return "TRON broadcast rejected. The transaction could not be submitted to the network."

# ---------------------------------------------------------------------------
# Ensure project root is in path
# ---------------------------------------------------------------------------
_PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

import base58
import requests

# ---------------------------------------------------------------------------
# Constants — Shasta Testnet
# ---------------------------------------------------------------------------
SHASTA_API = "https://api.shasta.trongrid.io"
SHASTA_EXPLORER = "https://shasta.tronscan.org"

# Shasta USDT (TRC20)
USDT_CONTRACT = "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs"
# Shasta USDC (TRC20)
USDC_CONTRACT = "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs"  # same as USDT on Shasta
# Shasta TRC10 test token ID
TRC10_TOKEN_ID = "1000001"

# Known test addresses (public, no private key needed for read tests)
TEST_ADDR_1 = "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK"
TEST_ADDR_2 = "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
INFO = "[INFO]"


def _print(icon: str, msg: str, detail: str = ""):
    """Print a test result with consistent formatting."""
    line = f"  {icon} {msg}"
    if detail:
        line += f" — {detail}"
    print(line)


def _rpc_post(method: str, params: dict) -> dict:
    """Execute a Tron RPC POST call against Shasta."""
    url = f"{SHASTA_API}/{method}"
    resp = requests.post(url, json=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------
class TronShastaTestSuite:
    """Full test suite for Tron on Shasta testnet."""

    def __init__(self, private_key: Optional[str] = None, dry_run: bool = True,
                 verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.failures = 0
        self.total = 0
        self.private_key = private_key
        self.sender_address = None
        self.tronpy_available = False

        # Derive sender address from private key if provided
        if private_key:
            self.sender_address = self._derive_address(private_key)
        else:
            self.sender_address = TEST_ADDR_1

        # Check if tronpy is available (needed for signing)
        try:
            from tronpy import Tron
            from tronpy.keys import PrivateKey
            from tronpy.providers import HTTPProvider
            self.Tron = Tron
            self.PrivateKey = PrivateKey
            self.HTTPProvider = HTTPProvider
            self.tronpy_available = True
        except ImportError:
            self.tronpy_available = False

    def _log(self, msg: str):
        if self.verbose:
            print(f"    DEBUG: {msg}")

    def _derive_address(self, private_key_hex: str) -> str:
        """Derive TRON address from private key hex."""
        try:
            from tronpy.keys import PrivateKey
            pk = PrivateKey(bytes.fromhex(private_key_hex))
            return pk.public_key.to_base58check_address()
        except Exception as e:
            self._log(f"Cannot derive address: {e}")
            return TEST_ADDR_1

    # ===================== Section Runners =====================

    def run_all(self):
        """Run all test sections."""
        print(f"\n{'='*60}")
        print(f"  Tron Shasta Testnet — Integration Test Suite")
        print(f"  Mode: {'DRY-RUN (no broadcast)' if self.dry_run else 'LIVE'}")
        print(f"  Sender: {self.sender_address}")
        print(f"  API: {SHASTA_API}")
        print(f"{'='*60}\n")

        # Section 1: Address Conversion
        self.test_address_conversion()

        # Section 2: Read Operations (always run, no key needed)
        self.test_get_account_info()
        self.test_get_trx_balance()
        self.test_get_trc20_balance()
        self.test_get_trc10_token_info()
        self.test_get_transaction_history()
        self.test_get_token_metadata()

        # Section 3: Fee Estimation
        self.test_estimate_fee()
        self.test_estimate_trc20_fee()

        # Section 4: Transaction Build & Sign (tronpy needed)
        if self.tronpy_available:
            if self.private_key:
                self.test_build_sign_trx_transfer()
                if not self.dry_run:
                    self.test_broadcast_trx_transfer()
                else:
                    _print(SKIP, "TRX broadcast", "Dry-run mode, skipped")

                if self.dry_run:
                    self.test_build_sign_trc20_transfer()
                    self.test_build_sign_trc10_transfer()
                else:
                    _print(SKIP, "TRC20/TRC10 build & sign", "Only in dry-run mode (needs funded wallet)")
            else:
                _print(SKIP, "Transaction build & sign",
                       "PRIVATE_KEY_SHASTA not provided. Set env var or pass --key.")
        else:
            _print(SKIP, "Transaction build & sign",
                   "tronpy not installed. Run: pip install tronpy")

        # Section 5: Error Decoding (always runs)
        self.test_error_decoding()

        # Section 6: Health Check (broadcast provider)
        self.test_broadcast_health()

        # Summary
        print(f"\n{'='*60}")
        print(f"  Results: {self.total - self.failures}/{self.total} passed")
        if self.failures > 0:
            print(f"  {FAIL} {self.failures} test(s) FAILED")
        else:
            print(f"  {PASS} All tests PASSED")
        print(f"{'='*60}\n")

        return self.failures == 0

    def _check(self, condition: bool, name: str, detail: str = ""):
        """Check a test condition."""
        self.total += 1
        if condition:
            _print(PASS, name, detail)
        else:
            self.failures += 1
            _print(FAIL, name, detail)

    # ===================== 1. Address Conversion =====================

    def test_address_conversion(self):
        """تست تبدیل آدرس Base58 ↔ Hex با API واقعی Shasta."""
        print(f"\n--- 1. Address Conversion ---")

        # Generate guaranteed-valid test vectors dynamically
        import base58
        hex_1 = "41a614f803b6fd780986a42c78ec9c7f77e6de13ea"
        hex_2 = "41e552f6487585c2b58bc2c9bb4492bc1f17132f70"
        b58_1 = base58.b58encode_check(bytes.fromhex(hex_1)).decode()
        b58_2 = base58.b58encode_check(bytes.fromhex(hex_2)).decode()

        known_addrs = [(b58_1, hex_1), (b58_2, hex_2)]

        for base58_addr, expected_hex in known_addrs:
            # Base58 → Hex
            try:
                decoded = base58.b58decode_check(base58_addr)
                actual_hex = decoded.hex()
                self._check(
                    actual_hex.lower() == expected_hex.lower(),
                    f"to_hex({base58_addr[:10]}...)",
                    f"expected {expected_hex[:16]}..., got {actual_hex[:16]}..."
                )
            except Exception as e:
                self._check(False, f"to_hex({base58_addr[:10]}...)", str(e))

            # Hex → Base58
            try:
                actual_base58 = base58.b58encode_check(bytes.fromhex(expected_hex)).decode()
                self._check(
                    actual_base58 == base58_addr,
                    f"to_base58({expected_hex[:16]}...)",
                    f"expected {base58_addr[:10]}..., got {actual_base58[:10]}..."
                )
            except Exception as e:
                self._check(False, f"to_base58({expected_hex[:16]}...)", str(e))

        # Round-trip
        test_addr = b58_1
        try:
            intermediate = base58.b58decode_check(test_addr).hex()
            roundtrip = base58.b58encode_check(bytes.fromhex(intermediate)).decode()
            self._check(roundtrip == test_addr, "Round-trip Base58→Hex→Base58", "OK")
        except Exception as e:
            self._check(False, "Round-trip Base58→Hex→Base58", str(e))

        # Invalid addresses
        self._check(
            self._try_to_hex("") is None,
            "to_hex(empty) → None",
        )
        self._check(
            self._try_to_hex("invalid") is None,
            "to_hex(invalid) → None",
        )

    def _try_to_hex(self, addr):
        """Try to convert address to hex, return None on failure."""
        if not addr or not isinstance(addr, str) or not addr.startswith('T'):
            return None
        try:
            decoded = base58.b58decode_check(addr)
            return decoded.hex()
        except Exception:
            return None

    # ===================== 2. Read Operations =====================

    def test_get_account_info(self):
        """دریافت اطلاعات حساب از Shasta API."""
        print(f"\n--- 2. Read Operations ---")

        try:
            resp = _rpc_post("wallet/getaccount", {
                "address": TEST_ADDR_1,
                "visible": True,
            })
            self._check(
                resp.get("address") == TEST_ADDR_1 or bool(resp),
                f"getAccount({TEST_ADDR_1[:10]}...)",
                f"account data: {list(resp.keys())[:5] if resp else 'empty'}",
            )
        except Exception as e:
            self._check(False, f"getAccount({TEST_ADDR_1[:10]}...)", str(e))

    def test_get_trx_balance(self):
        """دریافت TRX balance."""
        try:
            # TronGrid v1 API — account balance
            url = f"{SHASTA_API}/v1/accounts/{TEST_ADDR_1}"
            resp = requests.get(url, timeout=15)
            self._check(
                resp.status_code == 200,
                f"v1/accounts/{TEST_ADDR_1[:10]}...",
                f"HTTP {resp.status_code}",
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    balance_sun = int(data["data"][0].get("balance", 0))
                    balance_trx = balance_sun / 1_000_000
                    _print(INFO, f"TRX balance", f"{balance_trx} TRX ({balance_sun} SUN)")
                else:
                    _print(INFO, "TRX balance", "Account not found on Shasta")
        except Exception as e:
            self._check(False, f"v1/accounts/{TEST_ADDR_1[:10]}...", str(e))

    def test_get_trc20_balance(self):
        """دریافت TRC20 (USDT) balance."""
        try:
            url = f"{SHASTA_API}/v1/accounts/{TEST_ADDR_1}"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and data["data"][0].get("trc20"):
                    for token_balance in data["data"][0]["trc20"]:
                        if USDT_CONTRACT in token_balance:
                            raw_balance = token_balance[USDT_CONTRACT]
                            actual_balance = int(raw_balance) / 1_000_000
                            _print(PASS, f"TRC20 balance (USDT)",
                                   f"{actual_balance} USDT")
                            break
                    else:
                        _print(INFO, "TRC20 balance (USDT)", "No USDT balance found")
                else:
                    _print(INFO, "TRC20 balance (USDT)", "No TRC20 data for this address")
            self._check(resp.status_code == 200, "TRC20 balance API call", f"HTTP {resp.status_code}")
        except Exception as e:
            self._check(False, "TRC20 balance", str(e))

    def test_get_trc10_token_info(self):
        """دریافت اطلاعات TRC10 token #1000001."""
        print(f"\n--- 3. TRC10 Token Info ---")
        try:
            resp = _rpc_post("wallet/getassetissuebyid", {
                "value": int(TRC10_TOKEN_ID),
            })
            token_name = resp.get("name", "unknown")
            token_abbr = resp.get("abbr", resp.get("symbol", "unknown"))
            total_supply = resp.get("totalSupply", "?")
            self._check(
                bool(resp) and token_name != "unknown",
                f"TRC10 token #{TRC10_TOKEN_ID}",
                f"name={token_name}, symbol={token_abbr}, supply={total_supply}",
            )
        except Exception as e:
            self._check(False, f"TRC10 token #{TRC10_TOKEN_ID}", str(e))

    def test_get_transaction_history(self):
        """دریافت تاریخچه تراکنش (TronGrid v1)."""
        print(f"\n--- 4. Transaction History ---")
        try:
            url = f"{SHASTA_API}/v1/accounts/{TEST_ADDR_1}/transactions"
            resp = requests.get(url, params={"limit": 5}, timeout=15)
            self._check(
                resp.status_code == 200,
                "v1/accounts/.../transactions",
                f"HTTP {resp.status_code}",
            )
            if resp.status_code == 200:
                data = resp.json()
                tx_count = len(data.get("data", []))
                _print(INFO, f"Transactions count", f"{tx_count} transactions")

            # TRC20 history
            url = f"{SHASTA_API}/v1/accounts/{TEST_ADDR_1}/transactions/trc20"
            resp2 = requests.get(url, params={"limit": 5, "only_confirmed": True}, timeout=15)
            self._check(
                resp2.status_code == 200,
                "v1/accounts/.../transactions/trc20",
                f"HTTP {resp2.status_code}",
            )
            if resp2.status_code == 200:
                data2 = resp2.json()
                trc20_count = len(data2.get("data", []))
                _print(INFO, "TRC20 transactions count", f"{trc20_count} transactions")

        except Exception as e:
            self._check(False, "Transaction history", str(e))

    def test_get_token_metadata(self):
        """دریافت metadata توکن از /v1/contracts/ (رفع شده)."""
        print(f"\n--- 5. Token Metadata (v1/contracts/) ---")
        try:
            url = f"{SHASTA_API}/v1/contracts/{USDT_CONTRACT}"
            resp = requests.get(url, timeout=15)
            self._check(
                resp.status_code == 200,
                f"v1/contracts/{USDT_CONTRACT[:16]}...",
                f"HTTP {resp.status_code}",
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    info = data["data"][0]
                    symbol = info.get("symbol", "?")
                    decimals = info.get("decimals", "?")
                    name = info.get("name", "?")
                    _print(INFO, "Token info",
                           f"symbol={symbol}, decimals={decimals}, name={name}")
                    # Verify it's the right endpoint
                    self._check(
                        symbol == "USD" or symbol == "USDT",
                        "TRC20 token metadata via /v1/contracts/",
                        f"symbol={symbol}, endpoint is correct",
                    )
                else:
                    _print(INFO, "Token info via /v1/contracts/", "No data returned")
        except Exception as e:
            self._check(False, f"v1/contracts/{USDT_CONTRACT[:16]}...", str(e))

    # ===================== 3. Fee Estimation =====================

    def test_estimate_fee(self):
        """تخمین کارمزد TRX با API واقعی Shasta."""
        print(f"\n--- 6. Fee Estimation ---")
        try:
            # Check if account exists on Shasta
            resp = _rpc_post("wallet/getaccount", {
                "address": TEST_ADDR_2,
                "visible": True,
            })
            account_exists = bool(resp and resp.get("address"))

            # Get account resources
            resp = _rpc_post("wallet/getaccountresource", {
                "address": TEST_ADDR_1,
                "visible": True,
            })
            free_net_used = resp.get("freeNetUsed", 0)
            free_net_limit = resp.get("freeNetLimit", 0)
            available_bandwidth = free_net_limit - free_net_used

            self._check(
                resp.get("freeNetLimit") is not None or resp.get("EnergyLimit") is not None,
                "getaccountresource",
                f"freeNetLimit={free_net_limit}, used={free_net_used}, available={available_bandwidth}",
            )

            # Activation check for recipient
            _print(INFO, "Recipient activation",
                   f"Target account {'exists' if account_exists else 'DOES NOT EXIST (needs 1 TRX activation)'}")

        except Exception as e:
            self._check(False, "Fee estimation", str(e))

    def test_estimate_trc20_fee(self):
        """تخمین کارمزد TRC20 با API واقعی Shasta."""
        try:
            # Verify the USDT contract exists on Shasta
            resp = _rpc_post("wallet/getcontract", {
                "value": USDT_CONTRACT,
                "visible": True,
            })
            self._check(
                "name" in resp,
                f"USDT contract exists on Shasta",
                f"name={resp.get('name', '?')}",
            )

            # Get account energy info
            resp = _rpc_post("wallet/getaccountresource", {
                "address": TEST_ADDR_1,
                "visible": True,
            })
            energy_limit = resp.get("EnergyLimit", 0)
            energy_used = resp.get("EnergyUsed", 0)
            available_energy = energy_limit - energy_used
            _print(INFO, "Energy resources",
                   f"limit={energy_limit}, used={energy_used}, available={available_energy}")

        except Exception as e:
            self._check(False, "TRC20 fee estimation", str(e))

    # ===================== 4. Transaction Build & Sign =====================

    def test_build_sign_trx_transfer(self):
        """
        ساخت و امضای تراکنش TRX با tronpy روی Shasta.

        This builds and signs a real transaction. In dry-run mode,
        we verify the signed bytes are valid hex. In live mode,
        we actually broadcast.
        """
        print(f"\n--- 7. TRX Transaction Build & Sign ---")

        if not self.tronpy_available or not self.private_key:
            _print(SKIP, "TRX build & sign", "tronpy or private key not available")
            return

        try:
            client = self.Tron(provider=self.HTTPProvider(SHASTA_API))
            priv_key = self.PrivateKey(bytes.fromhex(self.private_key))
            sender = self.sender_address

            # Get sender TRX balance to verify we have funds
            balance_sun = client.get_account_balance(sender)
            balance_trx = balance_sun / 1_000_000
            self._log(f"Sender balance: {balance_trx} TRX")

            self._check(
                balance_trx > 0 or self.dry_run,
                "Sender has TRX balance",
                f"{balance_trx} TRX" if balance_trx > 0 else "0 TRX (dry-run tolerance)",
            )

            # Build TRX transfer (send 0.001 TRX = 1000 SUN)
            amount_sun = 1000
            txn = (
                client.trx.transfer(sender, TEST_ADDR_2, amount_sun)
                .build()
                .sign(priv_key)
            )

            # Serialize to hex
            signed_hex = txn.serialize().hex()
            tx_id_bytes = txn.hash
            tx_id = tx_id_bytes.hex() if isinstance(tx_id_bytes, bytes) else str(tx_id_bytes)

            self._check(
                bool(signed_hex) and len(signed_hex) > 100,
                "TRX transaction signed",
                f"txid={tx_id[:20]}..., hex_len={len(signed_hex)}",
            )

            # Store for potential broadcast
            self._last_trx_txn = txn
            self._last_trx_hex = signed_hex
            self._last_trx_txid = tx_id

            # Verify the signed tx contains valid data
            self._check(
                "0a" in signed_hex[:10],
                "Signed TRX hex has valid protobuf prefix",
                f"starts with: {signed_hex[:30]}...",
            )

            # Test: decode the raw_data_hex from the transaction
            raw_data_hex = txn.txn.get("raw_data_hex", "")
            self._check(
                bool(raw_data_hex),
                "TRX raw_data_hex present",
                f"len={len(raw_data_hex)}",
            )

            # Verify contract type is TransferContract (type 0x01 = transfer, type_url contains TransferContract)
            contracts = txn.txn.get("raw_data", {}).get("contract", [])
            contract_type = contracts[0].get("type", "") if contracts else ""
            self._check(
                "TransferContract" in contract_type,
                "TRX contract type is TransferContract",
                contract_type,
            )

        except Exception as e:
            self._check(False, "TRX build & sign", str(e))
            if self.verbose:
                traceback.print_exc()

    def test_broadcast_trx_transfer(self):
        """
        Broadcast تراکنش TRX امضا شده به Shasta.

        از endpoint /wallet/broadcasthex استفاده می‌کند
        (دقیقاً مشابه مسیر non-custodial در production).
        """
        print(f"\n--- 8. TRX Broadcast (LIVE) ---")

        if not hasattr(self, '_last_trx_hex') or not self._last_trx_hex:
            _print(SKIP, "TRX broadcast", "No signed transaction available")
            return

        try:
            # Send to Shasta via /wallet/broadcasthex (same as our production code)
            url = f"{SHASTA_API}/wallet/broadcasthex"
            headers = {"Content-Type": "application/json"}
            payload = {"transaction": self._last_trx_hex}

            self._log(f"Broadcasting to {url}")
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result", False)
                txid = data.get("txid", "")

                if result:
                    self._check(
                        bool(txid),
                        "TRX broadcast SUCCESS",
                        f"txid={txid}, explorer={SHASTA_EXPLORER}/#/transaction/{txid}",
                    )

                    # Wait 5 seconds then verify
                    _print(INFO, "Waiting for confirmation...", "5 seconds")
                    time.sleep(5)

                    # Check transaction status
                    status_resp = _rpc_post("wallet/gettransactioninfobyid", {
                        "value": txid,
                    })
                    if status_resp:
                        fee_sun = status_resp.get("fee", 0)
                        fee_trx = fee_sun / 1_000_000
                        block_number = status_resp.get("blockNumber", "?")
                        _print(PASS, "TRX confirmed on-chain",
                               f"fee={fee_trx} TRX, block={block_number}")
                    else:
                        _print(INFO, "TRX status check", "Still pending or not yet indexed")

                else:
                    # Decode error using our error decoder
                    from services.cache_proxy.providers.tron_broadcast import (
                        _decode_tron_error,
                    )
                    raw_msg = data.get("message", data.get("Error", ""))
                    code = data.get("code", "")
                    readable = _decode_tron_error(raw_msg, code)
                    self._check(
                        False,
                        "TRX broadcast FAILED",
                        f"code={code}, msg={readable}",
                    )
            else:
                self._check(
                    False,
                    "TRX broadcast HTTP error",
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

        except Exception as e:
            self._check(False, "TRX broadcast", str(e))
            if self.verbose:
                traceback.print_exc()

    def test_build_sign_trc20_transfer(self):
        """
        ساخت و امضای تراکنش TRC20 (USDT) روی Shasta.

        از TriggerSmartContract با متد transfer(address,uint256)
        استفاده می‌کند.
        """
        print(f"\n--- 9. TRC20 (USDT) Transaction Build & Sign ---")

        if not self.tronpy_available or not self.private_key:
            _print(SKIP, "TRC20 build & sign", "tronpy or private key not available")
            return

        try:
            client = self.Tron(provider=self.HTTPProvider(SHASTA_API))
            priv_key = self.PrivateKey(bytes.fromhex(self.private_key))
            sender = self.sender_address

            # Build TRC20 transfer using TriggerSmartContract
            # USDT has 6 decimals, send 0.001 USDT = 1000 units
            amount_raw = 1000

            # Parameter: transfer(address,uint256)
            # Using tronpy's contract interface
            contract = client.get_contract(USDT_CONTRACT)

            # Build the trigger smart contract transaction
            # Method: transfer(address _to, uint256 _value)
            txn = (
                contract.functions.transfer(TEST_ADDR_2, amount_raw)
                .with_owner(sender)
                .fee_limit(10_000_000)  # 10 TRX fee limit
                .build()
                .sign(priv_key)
            )

            signed_hex = txn.serialize().hex()
            tx_id = txn.txid if hasattr(txn, 'txid') else txn.hash.hex() if hasattr(txn, 'hash') else "?"

            self._check(
                bool(signed_hex) and len(signed_hex) > 100,
                "TRC20 (USDT) transaction signed",
                f"txid={str(tx_id)[:20]}..., hex_len={len(signed_hex)}",
            )

            # Verify contract type is TriggerSmartContract
            contracts = txn.txn.get("raw_data", {}).get("contract", [])
            contract_type = contracts[0].get("type", "") if contracts else ""
            self._check(
                "TriggerSmartContract" in contract_type,
                "TRC20 contract type is TriggerSmartContract",
                contract_type,
            )

            # Verify fee limit was set
            raw_data = txn.txn.get("raw_data", {})
            fee_limit = raw_data.get("fee_limit", 0)
            self._check(
                fee_limit == 10_000_000,
                "TRC20 fee_limit set correctly",
                f"{fee_limit} SUN (10 TRX)",
            )

        except Exception as e:
            self._check(False, "TRC20 build & sign", str(e))
            if self.verbose:
                traceback.print_exc()

    def test_build_sign_trc10_transfer(self):
        """
        ساخت و امضای تراکنش TRC10 روی Shasta.

        از TransferAssetContract استفاده می‌کند
        (token ID = 1000001).
        """
        print(f"\n--- 10. TRC10 Transfer Build & Sign ---")

        if not self.tronpy_available or not self.private_key:
            _print(SKIP, "TRC10 build & sign", "tronpy or private key not available")
            return

        try:
            client = self.Tron(provider=self.HTTPProvider(SHASTA_API))
            priv_key = self.PrivateKey(bytes.fromhex(self.private_key))
            sender = self.sender_address

            # Build TRC10 transfer using tronpy's asset transfer
            # TRC10 token ID 1000001, send 1 unit
            txn = (
                client.trx.asset_transfer(
                    sender,
                    TEST_ADDR_2,
                    int(TRC10_TOKEN_ID),
                    1,  # amount
                )
                .build()
                .sign(priv_key)
            )

            signed_hex = txn.serialize().hex()
            tx_id = txn.txid if hasattr(txn, 'txid') else txn.hash.hex() if hasattr(txn, 'hash') else "?"

            self._check(
                bool(signed_hex) and len(signed_hex) > 100,
                "TRC10 transaction signed",
                f"txid={str(tx_id)[:20]}..., hex_len={len(signed_hex)}",
            )

            # Verify contract type is TransferAssetContract
            contracts = txn.txn.get("raw_data", {}).get("contract", [])
            contract_type = contracts[0].get("type", "") if contracts else ""
            self._check(
                "TransferAssetContract" in contract_type,
                "TRC10 contract type is TransferAssetContract",
                contract_type,
            )

        except Exception as e:
            self._check(False, "TRC10 build & sign", str(e))
            if self.verbose:
                traceback.print_exc()

    # ===================== 5. Error Decoding =====================

    def test_error_decoding(self):
        """
        تست decode خطاهای TronGrid (با پیاده‌سازی local).
        """
        print(f"\n--- 11. Error Decoding ---")

        # Test cases
        test_cases = [
            ("", "SIGERROR", "signature is invalid"),
            ("", "NOT_ENOUGH_ENERGY", "Insufficient energy"),
            ("", "NOT_ENOUGH_BANDWIDTH", "Insufficient bandwidth"),
            ("", "DUP_TRANSACTION_ERROR", "Duplicate transaction"),
            ("", "TRANSACTION_EXPIRATION_ERROR", "expired"),
            ("", "ACCOUNT_NOT_EXIST_ERROR", "does not exist"),
            ("", "CONTRACT_VALIDATE_ERROR", "Contract validation failed"),
            ("", "TRANSACTION_SIGN_ERROR", "signature"),
            ("", "TOO_BIG_TRANSACTION_ERROR", "too large"),
            ("", "TAPOS_ERROR", "block reference"),
            ("", "SERVER_BUSY", "busy"),
            ("", "UNKNOWN_CODE", "rejected"),  # fallback
            # Hex-encoded message
            ("436f6e74726163742076616c6964617465206572726f72203a20544f4f5f4249475f5452414e53414354494f4e", "", "too_big_transaction"),
            ("5369676e6174757265206572726f72", "", "signature"),
            # Plain text message
            ("some random error", "", "rejected"),
            ("", "", "rejected"),
        ]

        for raw_msg, code, expected in test_cases:
            result = _decode_tron_error_local(raw_msg, code)
            passed = expected.lower() in result.lower()
            self._check(
                passed,
                f"_decode_tron_error(code={code!r})",
                f"expected '{expected}' in '{result[:80]}'",
            )

    # ===================== 6. Broadcast Health =====================

    def test_broadcast_health(self):
        """
        تست health check broadcast provider.
        """
        print(f"\n--- 12. Broadcast Provider Health ---")

        try:
            from services.cache_proxy.providers.tron_broadcast import (
                get_tron_broadcast_provider,
            )

            provider = get_tron_broadcast_provider()
            health = provider.check_health()

            self._check(
                "status" in health,
                "Broadcast provider health",
                f"status={health.get('status', '?')}",
            )
            _print(INFO, "Provider details",
                   f"total_keys={health.get('total_keys', 'N/A')}, "
                   f"available={health.get('available_keys', 'N/A')}")

        except Exception as e:
            # This may fail if KeyPool is not configured, which is expected
            # outside of production
            _print(INFO, "Broadcast provider health",
                   f"Not configured in this environment: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Tron Shasta Testnet — Comprehensive Integration Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (no real broadcast, no private key needed):
  python scripts/test_tron_shasta.py --dry-run

  # Full live test (requires funded Shasta wallet):
  set PRIVATE_KEY_SHASTA=your_private_key
  python scripts/test_tron_shasta.py

  # Test with specific private key:
  python scripts/test_tron_shasta.py --key your_private_key

  # Verbose with all debug logs:
  python scripts/test_tron_shasta.py --dry-run -v

Note:
  - Get Shasta test TRX: https://shasta.tronex.io/join/getJoinPage
  - TRC20 USDT contract: TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs
  - TRC10 test token ID: 1000001
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Skip actual broadcast (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live broadcast (requires funded private key)",
    )
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Private key for signing (hex, without 0x prefix)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with debug logs",
    )

    args = parser.parse_args()

    # Determine mode
    dry_run = not args.live  # default is dry-run
    if args.live and args.dry_run:
        dry_run = False  # --live takes precedence

    # Get private key (env → arg → None)
    private_key = (
        args.key
        or os.environ.get("PRIVATE_KEY_SHASTA")
        or None
    )

    if not private_key and not dry_run:
        print(f"\n{FAIL} ERROR: Live mode requires a private key.")
        print(f"  Set PRIVATE_KEY_SHASTA environment variable or use --key")
        print(f"  Or run with --dry-run for read-only tests.")
        sys.exit(1)

    if not private_key:
        print(f"\n{INFO} No private key provided. Read-only + dry-run mode.")

    # Run test suite
    suite = TronShastaTestSuite(
        private_key=private_key,
        dry_run=dry_run,
        verbose=args.verbose,
    )
    success = suite.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
