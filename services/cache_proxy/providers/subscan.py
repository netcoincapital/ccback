"""
Subscan Proxy — Polkadot & Kusama Blockchain API
=================================================
Wrapper برای Subscan API.

پشتیبانی:
  - Polkadot (DOT)
  - Kusama (KSM)
"""

from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

REQUEST_TIMEOUT = 15  # ثانیه

# Subscan chain endpoints
CHAIN_MAP = {
    "polkadot": "polkadot",
    "dot": "polkadot",
    "kusama": "kusama",
    "ksm": "kusama",
}

SUBSCAN_BASE = "https://{chain}.api.subscan.io/api"


class SubscanProxy:
    """
    Proxy برای Subscan API.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._pool_manager = get_key_pool_manager()
        self._pool = self._pool_manager.get_pool("subscan")

    def _get_chain(self, chain: str) -> Optional[str]:
        """نرمال‌سازی نام chain."""
        return CHAIN_MAP.get(chain.lower().replace("-", "").replace(" ", ""))

    def _get_headers(self) -> Dict[str, str]:
        """ساخت headers با API key."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._pool:
            key_tuple = self._pool.get_next_key()
            if key_tuple:
                api_key, _ = key_tuple
                headers["X-API-Key"] = api_key
        return headers

    def _request(
        self, chain: str, path: str, json_data: Dict = None,
        namespace: str = None, cache_key: str = None, ttl: int = None,
    ) -> Optional[Dict]:
        """
        درخواست به Subscan API.
        
        Args:
            chain: نام chain (polkadot, kusama)
            path: مسیر API
            json_data: body
            namespace: فضای نام کش
            cache_key: کلید کش
            ttl: TTL
            
        Returns:
            پاسخ JSON یا None
        """
        chain_name = self._get_chain(chain)
        if not chain_name:
            return None

        # Cache check
        if cache_key and namespace:
            cached = self.cache.get(namespace, cache_key)
            if cached is not None:
                return cached

        url = SUBSCAN_BASE.format(chain=chain_name) + path
        try:
            resp = requests.post(
                url, json=json_data or {},
                headers=self._get_headers(), timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    # ذخیره در کش
                    if cache_key and namespace and data:
                        self.cache.set(namespace, cache_key, data, ttl)
                    return data
                else:
                    logger.warning("Subscan: API error: %s", data.get("message", "unknown"))
                    return None
            elif resp.status_code == 429:
                logger.warning("Subscan: rate limited")
                return None
            else:
                logger.warning("Subscan: %s returned %d", path, resp.status_code)
                return None

        except requests.Timeout:
            raise ProviderTimeoutError("Subscan", REQUEST_TIMEOUT * 1000)
        except requests.RequestException as e:
            raise ProviderError("Subscan", str(e))

    # ===================== Public APIs =====================

    def get_account_info(self, chain: str, address: str) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات حساب (balance, nonce, etc.).
        
        Args:
            chain: نام chain
            address: آدرس
            
        Returns:
            اطلاعات حساب یا None
        """
        cache_key = address.lower()
        return self._request(
            chain, "/scan/account", {"address": address},
            namespace=f"subscan_{self._get_chain(chain)}_account",
            cache_key=cache_key, ttl=15,
        )

    def get_balance(self, chain: str, address: str) -> Optional[float]:
        """
        دریافت balance.
        
        Args:
            chain: نام chain
            address: آدرس
            
        Returns:
            balance DOT/KSM یا None
        """
        info = self.get_account_info(chain, address)
        if info and info.get("data"):
            balance_str = info["data"].get("balance", "0")
            try:
                return float(balance_str)
            except (ValueError, TypeError):
                return None
        return None

    def get_transactions(
        self, chain: str, address: str, page: int = 0, limit: int = 25
    ) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش.
        
        Args:
            chain: نام chain
            address: آدرس
            page: شماره صفحه
            limit: تعداد در هر صفحه
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        cache_key = f"{address.lower()}_{page}_{limit}"
        result = self._request(
            chain, "/scan/transfers",
            {
                "address": address,
                "page": page,
                "row": min(limit, 100),
            },
            namespace=f"subscan_{self._get_chain(chain)}_tx",
            cache_key=cache_key, ttl=30,
        )
        if result and result.get("data"):
            return result["data"].get("transfers", [])
        return None

    def get_token_balance(self, chain: str, address: str) -> Optional[List[Dict]]:
        """
        دریافت balance همه توکن‌های یک account.
        
        Args:
            chain: نام chain
            address: آدرس
            
        Returns:
            لیست توکن‌ها با balance یا None
        """
        cache_key = f"tokens_{address.lower()}"
        result = self._request(
            chain, "/scan/account/tokens",
            {"address": address},
            namespace=f"subscan_{self._get_chain(chain)}_tokens",
            cache_key=cache_key, ttl=30,
        )
        if result and result.get("data"):
            return result["data"]
        return None


# ===================== Singleton =====================

_subscan_proxy_instance: Optional[SubscanProxy] = None


def get_subscan_proxy() -> SubscanProxy:
    global _subscan_proxy_instance
    if _subscan_proxy_instance is None:
        _subscan_proxy_instance = SubscanProxy()
    return _subscan_proxy_instance
