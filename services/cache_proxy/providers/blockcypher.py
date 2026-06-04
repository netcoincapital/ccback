"""
BlockCypher Proxy — Bitcoin & UTXO-based Blockchains
=====================================================
Wrapper برای BlockCypher API.

پشتیبانی:
  - Bitcoin (BTC)
  - Dogecoin (DOGE)
  - Dash (DASH)
  - Litecoin (LTC)
"""

from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

REQUEST_TIMEOUT = 15  # ثانیه

# BlockCypher chain names
CHAIN_MAP = {
    "bitcoin": "btc",
    "btc": "btc",
    "dogecoin": "doge",
    "doge": "doge",
    "dash": "dash",
    "litecoin": "ltc",
    "ltc": "ltc",
}

BLOCKCYPHER_BASE = "https://api.blockcypher.com/v1"


class BlockCypherProxy:
    """
    Proxy برای BlockCypher API.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._pool_manager = get_key_pool_manager()
        self._pool = self._pool_manager.get_pool("blockcypher")

    def _get_chain(self, chain: str) -> Optional[str]:
        """نرمال‌سازی نام chain."""
        return CHAIN_MAP.get(chain.lower().replace("-", "").replace(" ", ""))

    def _get_token(self) -> str:
        """دریافت توکن از pool."""
        if self._pool:
            key_tuple = self._pool.get_next_key()
            if key_tuple:
                api_key, key_obj = key_tuple
                return api_key
        return ""

    def _request(
        self, path: str, params: Dict = None,
        namespace: str = None, cache_key: str = None, ttl: int = None,
    ) -> Optional[Dict]:
        """
        درخواست به BlockCypher API.
        
        Args:
            path: مسیر API (مثل /btc/main/addrs/ADDR)
            params: query parameters
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

        params = dict(params or {})
        token = self._get_token()
        if token:
            params["token"] = token

        url = f"{BLOCKCYPHER_BASE}{path}"
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 200:
                data = resp.json()

                if self._pool and token:
                    self._pool.mark_success(token)

                # ذخیره در کش
                if cache_key and namespace and data:
                    self.cache.set(namespace, cache_key, data, ttl)

                return data

            elif resp.status_code == 429:
                if self._pool and token:
                    self._pool.mark_rate_limited(token, cooldown=60)
                return None
            else:
                if self._pool and token:
                    self._pool.mark_error(token)
                logger.warning("BlockCypher: %s returned %d", path, resp.status_code)
                return None

        except requests.Timeout:
            raise ProviderTimeoutError("BlockCypher", REQUEST_TIMEOUT * 1000)
        except requests.RequestException as e:
            raise ProviderError("BlockCypher", str(e))

    # ===================== Public APIs =====================

    def get_address_info(self, chain: str, address: str) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات کامل یک آدرس (balance, total tx count, etc.).
        
        Args:
            chain: نام بلاکچین (btc, doge, dash, ltc)
            address: آدرس
            
        Returns:
            اطلاعات آدرس یا None
        """
        chain_name = self._get_chain(chain)
        if not chain_name:
            logger.warning("BlockCypher: unsupported chain %s", chain)
            return None

        cache_key = address.lower()
        return self._request(
            f"/{chain_name}/main/addrs/{address}",
            namespace=f"bc_addr_{chain_name}", cache_key=cache_key, ttl=15,
        )

    def get_balance(self, chain: str, address: str) -> Optional[float]:
        """
        دریافت balance.
        
        Args:
            chain: نام بلاکچین
            address: آدرس
            
        Returns:
            balance (native coin) یا None
        """
        info = self.get_address_info(chain, address)
        if info:
            # BlockCypher balance بر حسب satoshi
            balance_sat = info.get("balance", 0)
            return balance_sat / 1e8  # satoshi → BTC
        return None

    def get_transactions(
        self, chain: str, address: str, limit: int = 25
    ) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش.
        
        Args:
            chain: نام بلاکچین
            address: آدرس
            limit: تعداد تراکنش
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        chain_name = self._get_chain(chain)
        if not chain_name:
            return None

        cache_key = f"tx_{address.lower()}_{limit}"
        result = self._request(
            f"/{chain_name}/main/addrs/{address}",
            params={"limit": min(limit, 50)},
            namespace=f"bc_tx_{chain_name}", cache_key=cache_key, ttl=30,
        )
        if result:
            return result.get("txs", [])
        return None


# ===================== Singleton =====================

_blockcypher_proxy_instance: Optional[BlockCypherProxy] = None


def get_blockcypher_proxy() -> BlockCypherProxy:
    global _blockcypher_proxy_instance
    if _blockcypher_proxy_instance is None:
        _blockcypher_proxy_instance = BlockCypherProxy()
    return _blockcypher_proxy_instance
