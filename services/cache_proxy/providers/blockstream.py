"""
Blockstream Proxy — Bitcoin Public API Wrapper
===============================================
wrapper برای Blockstream API (blockstream.info).
این API عمومی است و نیازی به API Key ندارد.

محدودیت: 1 req/10s (غیررسمی) — cache TTL کوتاه جبران می‌کند.

Endpointهای پشتیبانی شده:
  - balance (از address utxo summary)
  - تاریخچه تراکنش
  - جزئیات تراکنش
  - وضعیت بلاک
"""

from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

BLOCKSTREAM_API = "https://blockstream.info/api"
REQUEST_TIMEOUT = 15  # ثانیه


class BlockstreamProxy:
    """
    Proxy برای Blockstream API (Bitcoin).
    بدون نیاز به API Key. عمومی و رایگان.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()

    def _request(self, path: str, namespace: str = None, cache_key: str = None, ttl: int = None) -> Optional[Any]:
        """
        درخواست GET به Blockstream API.
        
        Args:
            path: مسیر API (مثلاً /address/ADDR)
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

        url = f"{BLOCKSTREAM_API}{path}"
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/json"})

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

                # ذخیره در کش
                if cache_key and namespace and data is not None:
                    self.cache.set(namespace, cache_key, data, ttl)

                return data
            else:
                logger.debug("Blockstream: %s returned %d", path, resp.status_code)
                return None

        except requests.Timeout:
            raise ProviderTimeoutError("Blockstream", REQUEST_TIMEOUT * 1000)
        except requests.RequestException as e:
            raise ProviderError("Blockstream", str(e))

    # ===================== Public APIs =====================

    def get_address_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات کامل آدرس (balance, tx count, utxo).
        
        Args:
            address: آدرس Bitcoin
            
        Returns:
            اطلاعات آدرس یا None
        """
        cache_key = address.lower()
        return self._request(
            f"/address/{address}",
            namespace="bs_addr", cache_key=cache_key, ttl=15,
        )

    def get_balance(self, address: str) -> Optional[int]:
        """
        دریافت balance (satoshis).
        
        Args:
            address: آدرس Bitcoin
            
        Returns:
            balance (sat) یا None
        """
        info = self.get_address_info(address)
        if info:
            chain_stats = info.get("chain_stats", {})
            mempool_stats = info.get("mempool_stats", {})
            funded = chain_stats.get("funded_txo_sum", 0) + mempool_stats.get("funded_txo_sum", 0)
            spent = chain_stats.get("spent_txo_sum", 0) + mempool_stats.get("spent_txo_sum", 0)
            return funded - spent
        return None

    def get_transactions(self, address: str, limit: int = 25) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش.
        
        Args:
            address: آدرس Bitcoin
            limit: تعداد تراکنش
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        cache_key = f"tx_{address.lower()}_{limit}"
        result = self._request(
            f"/address/{address}/txs",
            namespace="bs_tx", cache_key=cache_key, ttl=30,
        )
        if result and isinstance(result, list):
            return result[:limit]
        return None

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """
        دریافت جزئیات یک تراکنش.
        
        Args:
            tx_hash: هش تراکنش
            
        Returns:
            جزئیات تراکنش یا None
        """
        cache_key = tx_hash.lower()
        return self._request(
            f"/tx/{tx_hash}",
            namespace="bs_tx_detail", cache_key=cache_key, ttl=60,
        )

    def get_latest_block_height(self) -> Optional[int]:
        """
        دریافت آخرین ارتفاع بلاک.
        
        Returns:
            height یا None
        """
        result = self._request("/blocks/tip/height", ttl=15)
        if result is not None:
            try:
                return int(result) if not isinstance(result, dict) else None
            except (ValueError, TypeError):
                return None
        return None

    def get_supported_chains(self) -> List[str]:
        return ["bitcoin"]


# Singleton
_blockstream_proxy_instance: Optional[BlockstreamProxy] = None


def get_blockstream_proxy() -> BlockstreamProxy:
    global _blockstream_proxy_instance
    if _blockstream_proxy_instance is None:
        _blockstream_proxy_instance = BlockstreamProxy()
    return _blockstream_proxy_instance
