"""
Tron Broadcast Provider — Broadcast Signed Transactions via TronGrid
=====================================================================
ارسال تراکنش امضا شده به TronGrid wallet/broadcasthex.
Non-custodial: فقط signedTx دریافت می‌کند، هرگز private key را نمی‌بیند.

گردش کار:
  1️⃣ کلاینت (Flutter) تراکنش را محلی امضا می‌کند (tronweb)
  2️⃣ signedTx hex را به POST /api/v2/broadcast می‌فرستد
  3️⃣ بک‌اند به TronGrid /wallet/broadcasthex فوروارد می‌کند (با round-robin کلیدها)
  4️⃣ txId به کلاینت برمی‌گردد

محدودیت‌ها:
  - فقط signedTx (hex) قبول می‌کند — private key هرگز وارد بک‌اند نمی‌شود
  - از KeyPool "trongrid" برای round-robin بین ۱۲ کلید استفاده می‌کند
  - هیچوقت signedTx را ذخیره/لاگ نمی‌کند
"""

import time
from typing import Optional, Dict, Any, Tuple

import requests

from utils.logging_config import get_logger
from ..core.key_pool import get_key_pool_manager, ApiKey
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

TRONGRID_BASE = "https://api.trongrid.io"
REQUEST_TIMEOUT = 30  # broadcast ممکن است کندتر باشد


class TronBroadcastProvider:
    """
    Broadcast تراکنش امضا شده ترون از طریق TronGrid.

    Thread-safe: هر بار یک کلید جدید از KeyPool می‌گیرد (round-robin).
    """

    def __init__(self):
        self._pool_manager = get_key_pool_manager()
        self._pool = self._pool_manager.get_pool("trongrid")

    # ===================== Public API =====================

    def broadcast(self, signed_tx_hex: str) -> Optional[str]:
        """
        ارسال تراکنش امضا شده به شبکه ترون.

        Args:
            signed_tx_hex: signed transaction hex
                          (در Flutter با tronweb: txn.serialize().hex())

        Returns:
            txId (شناسه تراکنش در زنجیره) یا None در صورت خطا
        """
        url = f"{TRONGRID_BASE}/wallet/broadcasthex"
        headers, used_key = self._build_headers()
        payload = {"transaction": signed_tx_hex}

        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") is True:
                    tx_id = data.get("txid")
                    self._mark_success(used_key)
                    logger.info("Tron broadcast: txid=%s", tx_id)
                    return tx_id
                else:
                    # Transaction rejected by TronGrid — extract descriptive error
                    raw_msg = data.get("message", data.get("Error", ""))
                    code = data.get("code", "")
                    readable = _decode_tron_error(raw_msg, code)
                    self._mark_error(used_key)
                    raise ProviderError("TronGrid", readable)

            elif resp.status_code == 429:
                self._mark_rate_limited(used_key, cooldown=30)
                raise ProviderError(
                    "TronGrid",
                    "TRON API rate limit exceeded. Please wait and try again.",
                )

            else:
                self._mark_error(used_key)
                snippet = resp.text[:300]
                raise ProviderError(
                    "TronGrid",
                    f"TRON node returned HTTP {resp.status_code}: {snippet}",
                )

        except requests.Timeout:
            self._mark_error(used_key)
            raise ProviderTimeoutError("TronGrid", REQUEST_TIMEOUT * 1000)

        except requests.RequestException as e:
            self._mark_error(used_key)
            raise ProviderError("TronGrid", str(e))

    def _build_headers(self) -> Tuple[Dict[str, str], Optional[ApiKey]]:
        """ساخت headers با API key از KeyPool (round-robin)."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        used_key: Optional[ApiKey] = None
        if self._pool:
            key_tuple = self._pool.get_next_key()
            if key_tuple:
                api_key, used_key = key_tuple
                headers["TRON-PRO-API-KEY"] = api_key
        return headers, used_key

    # ===================== Health Tracking Helpers =====================

    def _mark_success(self, key: Optional[ApiKey]):
        if key:
            key.mark_success()

    def _mark_rate_limited(self, key: Optional[ApiKey], cooldown: int = 60):
        if key:
            key.mark_rate_limited(cooldown)

    def _mark_error(self, key: Optional[ApiKey]):
        if key:
            key.mark_error()

    # ===================== Health Check =====================

    def check_health(self) -> Dict[str, Any]:
        """
        بررسی سلامت Tron broadcast provider.

        Returns:
            dict: وضعیت (available keys, total keys)
        """
        if not self._pool:
            return {
                "status": "disabled",
                "reason": "No trongrid key pool configured",
            }
        return {
            "status": "active",
            "total_keys": self._pool.total_keys,
            "available_keys": self._pool.available_keys,
        }


# ===================== Error Decoding =====================

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


def _decode_tron_error(raw_message: str, error_code: str = "") -> str:
    """
    تبدیل خطاهای خام TronGrid به پیام‌های خوانا و قابل فهم برای کاربر.

    Args:
        raw_message: پیام خطای خام از TronGrid (ممکن است hex-encoded باشد)
        error_code: کد خطا از پاسخ TronGrid

    Returns:
        str: پیام خطای خوانا به انگلیسی (مناسب برای Frontend)
    """
    # 1. Try to decode hex-encoded message
    decoded_message = raw_message
    if raw_message:
        try:
            decoded_bytes = bytes.fromhex(raw_message)
            decoded_text = decoded_bytes.decode("utf-8", errors="replace")
            if decoded_text and len(decoded_text) < 200:
                decoded_message = decoded_text
        except (ValueError, TypeError):
            decoded_message = raw_message

    # 2. Check known error codes first
    if error_code:
        upper_code = error_code.upper().strip()
        if upper_code in _TRON_ERROR_MESSAGES:
            return _TRON_ERROR_MESSAGES[upper_code]

    # 3. Search for known patterns in the decoded message
    if decoded_message:
        upper_msg = decoded_message.upper()
        for key, readable in _TRON_ERROR_MESSAGES.items():
            if key in upper_msg:
                return readable

    # 4. Return decoded original if we have it, otherwise generic error
    if decoded_message and decoded_message != raw_message:
        return f"TRON broadcast rejected: {decoded_message}"
    if decoded_message:
        return f"TRON broadcast rejected: {decoded_message}"
    return "TRON broadcast rejected. The transaction could not be submitted to the network."


# ===================== Singleton =====================

_tron_broadcast_instance: Optional[TronBroadcastProvider] = None


def get_tron_broadcast_provider() -> TronBroadcastProvider:
    global _tron_broadcast_instance
    if _tron_broadcast_instance is None:
        _tron_broadcast_instance = TronBroadcastProvider()
    return _tron_broadcast_instance
