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
                    msg = data.get("message", data.get("Error", "unknown"))
                    logger.warning("Tron broadcast rejected: %s", msg)
                    self._mark_error(used_key)
                    return None

            elif resp.status_code == 429:
                self._mark_rate_limited(used_key, cooldown=30)
                logger.warning("Tron broadcast: rate limited (429)")
                return None

            else:
                self._mark_error(used_key)
                logger.warning(
                    "Tron broadcast: %d %s",
                    resp.status_code, resp.text[:200],
                )
                return None

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


# ===================== Singleton =====================

_tron_broadcast_instance: Optional[TronBroadcastProvider] = None


def get_tron_broadcast_provider() -> TronBroadcastProvider:
    global _tron_broadcast_instance
    if _tron_broadcast_instance is None:
        _tron_broadcast_instance = TronBroadcastProvider()
    return _tron_broadcast_instance
