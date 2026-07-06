"""
TronGrid Proxy — Tron Blockchain API Wrapper
=============================================
Wrapper برای TronGrid API v1.

Endpoints پشتیبانی شده:
  - تاریخچه تراکنش (transactions)
  - Balance TRX (native)
  - Balance TRC20 (توکن)
  - Token metadata
  - Account info
"""

import time
from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

TRONGRID_BASE = "https://api.trongrid.io"
REQUEST_TIMEOUT = 15  # ثانیه


class TronGridProxy:
    """
    Proxy برای TronGrid API v1.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._pool_manager = get_key_pool_manager()
        # TronGrid key pool
        self._pool = self._pool_manager.get_pool("trongrid")

    def _get_headers(self) -> Dict[str, str]:
        """ساخت headers با API key در صورت وجود."""
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._pool:
            key_tuple = self._pool.get_next_key()
            if key_tuple:
                api_key, _ = key_tuple
                headers["TRON-PRO-API-KEY"] = api_key
        return headers

    def _request(
        self, method: str, path: str, params: Dict = None,
        json_data: Dict = None, namespace: str = None, cache_key: str = None, ttl: int = None,
    ) -> Optional[Dict]:
        """
        درخواست به TronGrid API.
        
        Args:
            method: HTTP method
            path: مسیر API (بدون base)
            params: query parameters
            json_data: body
            namespace: فضای نام کش
            cache_key: کلید کش
            ttl: TTL
            
        Returns:
            پاسخ JSON یا None
        """
        # Cache check
        if cache_key and namespace:
            cached = self.cache.get(namespace, cache_key)
            if cached is not None:
                return cached

        url = f"{TRONGRID_BASE}{path}"
        try:
            resp = requests.request(
                method=method, url=url, params=params, json=json_data,
                headers=self._get_headers(), timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()

                # Success
                if self._pool:
                    key_str = self._get_used_key()
                    if key_str:
                        self._pool.mark_success(key_str)

                # ذخیره در کش
                if cache_key and namespace and data:
                    self.cache.set(namespace, cache_key, data, ttl)

                return data

            elif resp.status_code == 429:
                if self._pool:
                    key_str = self._get_used_key()
                    if key_str:
                        self._pool.mark_rate_limited(key_str, cooldown=30)
                return None
            else:
                if self._pool:
                    key_str = self._get_used_key()
                    if key_str:
                        self._pool.mark_error(key_str)
                logger.warning("TronGrid: %s returned %d", path, resp.status_code)
                return None

        except requests.Timeout:
            raise ProviderTimeoutError("TronGrid", REQUEST_TIMEOUT * 1000)
        except requests.RequestException as e:
            raise ProviderError("TronGrid", str(e))

    def _get_used_key(self) -> Optional[str]:
        """Helper برای گرفتن کلید استفاده شده (آخرین key از headers)."""
        return None  # نمی‌توان از headers کلید را برگرداند

    # ===================== Public APIs =====================

    def get_account(self, address: str) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات حساب (شامل balance TRX).
        
        Args:
            address: آدرس Tron (base58)
            
        Returns:
            data account یا None
        """
        cache_key = address.lower()
        return self._request(
            "GET", f"/v1/accounts/{address}",
            namespace="tron_account", cache_key=cache_key, ttl=15,
        )

    def get_balance(self, address: str) -> Optional[float]:
        """
        دریافت balance TRX.
        
        Args:
            address: آدرس Tron
            
        Returns:
            balance TRX یا None
        """
        account = self.get_account(address)
        if account and account.get("data"):
            balance_sun = int(account["data"][0].get("balance", 0))
            return balance_sun / 1e6  # SUN → TRX
        return None

    def get_transactions(
        self, address: str, limit: int = 25, only_to: bool = False,
        min_timestamp: int = None, max_timestamp: int = None,
    ) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش.
        
        Args:
            address: آدرس Tron
            limit: تعداد تراکنش
            only_to: فقط تراکنش‌های دریافتی
            min_timestamp: حداقل timestamp (ms)
            max_timestamp: حداکثر timestamp (ms)
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        params = {"limit": min(limit, 200), "only_to": only_to or False}
        if min_timestamp:
            params["min_timestamp"] = min_timestamp
        if max_timestamp:
            params["max_timestamp"] = max_timestamp

        cache_key = f"{address.lower()}_{limit}_{only_to}"
        result = self._request(
            "GET", f"/v1/accounts/{address}/transactions",
            params=params, namespace="tron_tx", cache_key=cache_key, ttl=30,
        )
        if result:
            return result.get("data", [])
        return None

    def get_trc20_transactions(
        self, address: str, limit: int = 25, contract_address: str = None,
    ) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش‌های TRC20.
        
        Args:
            address: آدرس Tron
            limit: تعداد
            contract_address: فیلتر بر اساس آدرس توکن
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        params = {
            "limit": min(limit, 200),
            "only_confirmed": True,
        }
        if contract_address:
            params["contract_address"] = contract_address

        cache_parts = [f"trc20_{address.lower()}", str(limit)]
        if contract_address:
            cache_parts.append(contract_address.lower())
        cache_key = "_".join(cache_parts)

        result = self._request(
            "GET", f"/v1/accounts/{address}/transactions/trc20",
            params=params, namespace="tron_trc20", cache_key=cache_key, ttl=30,
        )
        if result:
            return result.get("data", [])
        return None

    def get_trc20_balance(self, address: str, contract_address: str) -> Optional[str]:
        """
        دریافت balance یک توکن TRC20.
        
        Args:
            address: آدرس Tron
            contract_address: آدرس قرارداد توکن
            
        Returns:
            balance خام (raw, بدون decimals) یا None
        """
        cache_key = f"{address.lower()}_{contract_address.lower()}"
        result = self._request(
            "GET", f"/v1/accounts/{address}",
            namespace="tron_trc20_balance", cache_key=cache_key, ttl=30,
        )
        if result and result.get("data"):
            trc20 = result["data"][0].get("trc20", [])
            for token in trc20:
                if contract_address in token:
                    return token[contract_address]
        return None

    def get_token_info(self, contract_address: str) -> Optional[Dict]:
        """
        دریافت اطلاعات یک توکن TRC20 از قرارداد هوشمند.
        
        از TronGrid v1 endpoint استفاده می‌کند:
          GET /v1/contracts/{contractAddress}
        (برای TRC10 از /v1/tokens/ استفاده کنید)
        
        Args:
            contract_address: آدرس قرارداد توکن (Base58)
            
        Returns:
            اطلاعات توکن (شامل name, symbol, decimals) یا None
        """
        cache_key = contract_address.lower()
        result = self._request(
            "GET", f"/v1/contracts/{contract_address}",
            namespace="tron_token_info", cache_key=cache_key, ttl=3600,
        )
        if result:
            return result.get("data", [None])[0] if result.get("data") else None
        return None


# ===================== Singleton =====================

_trongrid_proxy_instance: Optional[TronGridProxy] = None


def get_trongrid_proxy() -> TronGridProxy:
    global _trongrid_proxy_instance
    if _trongrid_proxy_instance is None:
        _trongrid_proxy_instance = TronGridProxy()
    return _trongrid_proxy_instance
