"""
EVM Explorer Proxy — Etherscan-family API Wrapper
==================================================
یک interface واحد برای همه EVM explorerها:
  - Ethereum → api.etherscan.io
  - BSC      → api.bscscan.com
  - Polygon  → api.polygonscan.com
  - Avalanche → api.snowtrace.io
  - Arbitrum → api.arbiscan.io

از KeyPool برای round-robin کلیدها و CacheLayer برای کش استفاده می‌کند.
"""

import time
import threading
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager, KeyPool
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

# ============================================================
# EVM Chain Configuration
# ============================================================

@dataclass
class ExplorerConfig:
    """تنظیمات یک explorer."""
    name: str
    chain_key: str
    base_url: str
    pool_name: str
    native_symbol: str
    decimals: int


EXPLORER_CHAINS: Dict[str, ExplorerConfig] = {
    "ethereum": ExplorerConfig(
        name="Ethereum", chain_key="ETH",
        base_url="https://api.etherscan.io/api",
        pool_name="etherscan", native_symbol="ETH", decimals=18,
    ),
    "bsc": ExplorerConfig(
        name="BSC", chain_key="BSC",
        base_url="https://api.bscscan.com/api",
        pool_name="bscscan", native_symbol="BNB", decimals=18,
    ),
    "polygon": ExplorerConfig(
        name="Polygon", chain_key="POLYGON",
        base_url="https://api.polygonscan.com/api",
        pool_name="polygonscan", native_symbol="POL", decimals=18,
    ),
    "avalanche": ExplorerConfig(
        name="Avalanche", chain_key="AVAX",
        base_url="https://api.snowtrace.io/api",
        pool_name="avalanche", native_symbol="AVAX", decimals=18,
    ),
    "arbitrum": ExplorerConfig(
        name="Arbitrum", chain_key="ARBITRUM",
        base_url="https://api.arbiscan.io/api",
        pool_name="arbiscan", native_symbol="ETH", decimals=18,
    ),
}

REQUEST_TIMEOUT = 15  # ثانیه


class EvmExplorerProxy:
    """
    Proxy یکپارچه برای همه EVM explorerها.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._pool_manager = get_key_pool_manager()

    def _get_config(self, chain: str) -> Optional[ExplorerConfig]:
        """دریافت تنظیمات یک chain."""
        chain_lower = chain.lower().replace("-", "").replace(" ", "")
        return EXPLORER_CHAINS.get(chain_lower)

    def _get_pool(self, pool_name: str) -> Optional[KeyPool]:
        """دریافت KeyPool برای یک explorer."""
        return self._pool_manager.get_pool(pool_name)

    def _request(
        self, config: ExplorerConfig, params: Dict[str, str],
        namespace: str, cache_key: str = None, ttl: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        درخواست به explorer API با key rotation + caching.
        
        Args:
            config: تنظیمات explorer
            params: پارامترهای API
            namespace: فضای نام کش
            cache_key: کلید کش (اگر None، از params ساخته می‌شود)
            ttl: TTL کش
            
        Returns:
            پاسخ API یا None
        """
        # Cache check
        if cache_key:
            cached = self.cache.get(namespace, cache_key)
            if cached is not None:
                return cached

        pool = self._get_pool(config.pool_name)
        if not pool or pool.total_keys == 0:
            logger.warning("EvmExplorer: no key pool for %s", config.name)
            return None

        # Key rotation
        key_tuple = pool.get_next_key()
        if not key_tuple:
            logger.warning("EvmExplorer: no available keys for %s", config.name)
            return None

        api_key, key_obj = key_tuple

        try:
            params_copy = dict(params)
            params_copy["apikey"] = api_key

            resp = requests.get(config.base_url, params=params_copy, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 200:
                data = resp.json()

                # بررسی خطاهای API
                status = data.get("status", "")
                message = data.get("message", "")

                if status == "0" and "rate limit" in message.lower():
                    pool.mark_rate_limited(api_key, cooldown=30)
                    return None
                if status == "0" and "max" in message.lower():
                    pool.mark_exhausted(api_key)
                    return None

                pool.mark_success(api_key)

                # ذخیره در کش
                if cache_key and data:
                    self.cache.set(namespace, cache_key, data, ttl)

                return data

            elif resp.status_code == 429:
                pool.mark_rate_limited(api_key, cooldown=60)
                return None
            elif resp.status_code == 403:
                pool.mark_exhausted(api_key)
                return None
            else:
                pool.mark_error(api_key)
                logger.warning("EvmExplorer: %s returned %d", config.name, resp.status_code)
                return None

        except requests.Timeout:
            pool.mark_error(api_key)
            raise ProviderTimeoutError(config.name, REQUEST_TIMEOUT * 1000)
        except requests.RequestException as e:
            pool.mark_error(api_key)
            raise ProviderError(config.name, str(e))

    # ===================== Public APIs =====================

    def get_transactions(
        self, chain: str, address: str, page: int = 1, limit: int = 25
    ) -> Optional[List[Dict[str, Any]]]:
        """
        تاریخچه تراکنش‌های یک address.
        
        Args:
            chain: نام بلاکچین (ethereum, bsc, polygon, avalanche, arbitrum)
            address: آدرس کیف پول
            page: شماره صفحه
            limit: تعداد در هر صفحه
            
        Returns:
            لیست تراکنش‌ها یا None
        """
        config = self._get_config(chain)
        if not config:
            logger.warning("EvmExplorer: unsupported chain %s", chain)
            return None

        cache_key = f"{address.lower()}_{page}_{limit}"
        namespace = f"tx_{config.chain_key.lower()}"

        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": str(page),
            "offset": str(limit),
            "sort": "desc",
        }

        result = self._request(config, params, namespace, cache_key, ttl=30)
        if result and result.get("status") == "1":
            return result.get("result", [])
        return None

    def get_internal_transactions(
        self, chain: str, address: str, page: int = 1, limit: int = 25
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Internal transactions (مثل contract calls).
        
        Args:
            chain: نام بلاکچین
            address: آدرس کیف پول
            page: شماره صفحه
            limit: تعداد در هر صفحه
            
        Returns:
            لیست internal txها یا None
        """
        config = self._get_config(chain)
        if not config:
            return None

        cache_key = f"internal_{address.lower()}_{page}_{limit}"
        namespace = f"internal_tx_{config.chain_key.lower()}"

        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": str(page),
            "offset": str(limit),
            "sort": "desc",
        }

        result = self._request(config, params, namespace, cache_key, ttl=30)
        if result and result.get("status") == "1":
            return result.get("result", [])
        return None

    def get_token_transactions(
        self, chain: str, address: str, page: int = 1, limit: int = 25,
        contract_address: str = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Token transfer history (ERC20).
        
        Args:
            chain: نام بلاکچین
            address: آدرس کیف پول
            page: شماره صفحه
            limit: تعداد در هر صفحه
            contract_address: (اختیاری) فیلتر بر اساس آدرس قرارداد توکن
            
        Returns:
            لیست token txها یا None
        """
        config = self._get_config(chain)
        if not config:
            return None

        cache_parts = [f"token_{address.lower()}", str(page), str(limit)]
        if contract_address:
            cache_parts.append(contract_address.lower())
        cache_key = "_".join(cache_parts)
        namespace = f"token_tx_{config.chain_key.lower()}"

        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": str(page),
            "offset": str(limit),
            "sort": "desc",
        }
        if contract_address:
            params["contractaddress"] = contract_address

        result = self._request(config, params, namespace, cache_key, ttl=30)
        if result and result.get("status") == "1":
            return result.get("result", [])
        return None

    def get_native_balance(self, chain: str, address: str) -> Optional[str]:
        """
        Balance native coin.
        
        Args:
            chain: نام بلاکچین
            address: آدرس کیف پول
            
        Returns:
            balance به صورت string (wei) یا None
        """
        config = self._get_config(chain)
        if not config:
            return None

        cache_key = address.lower()
        namespace = f"balance_{config.chain_key.lower()}"

        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        }

        result = self._request(config, params, namespace, cache_key, ttl=15)
        if result and result.get("status") == "1":
            return result.get("result")
        return None

    def get_token_balance(
        self, chain: str, address: str, contract_address: str
    ) -> Optional[str]:
        """
        Balance یک توکن ERC20.
        
        Args:
            chain: نام بلاکچین
            address: آدرس کیف پول
            contract_address: آدرس قرارداد توکن
            
        Returns:
            balance به صورت string یا None
        """
        config = self._get_config(chain)
        if not config:
            return None

        cache_key = f"{address.lower()}_{contract_address.lower()}"
        namespace = f"token_balance_{config.chain_key.lower()}"

        params = {
            "module": "account",
            "action": "tokenbalance",
            "address": address,
            "contractaddress": contract_address,
            "tag": "latest",
        }

        result = self._request(config, params, namespace, cache_key, ttl=30)
        if result and result.get("status") == "1":
            return result.get("result")
        return None

    def get_token_metadata(self, chain: str, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Metadata یک توکن (supply, decimals, symbol, name).
        
        Args:
            chain: نام بلاکچین
            contract_address: آدرس قرارداد توکن
            
        Returns:
            metadata یا None
        """
        config = self._get_config(chain)
        if not config:
            return None

        cache_key = contract_address.lower()
        namespace = f"token_meta_{config.chain_key.lower()}"

        params = {
            "module": "token",
            "action": "tokeninfo",
            "contractaddress": contract_address,
        }

        result = self._request(config, params, namespace, cache_key, ttl=3600)
        if result and result.get("status") == "1":
            return result.get("result", [None])[0] if isinstance(result.get("result"), list) else None
        return None

    def get_supported_chains(self) -> List[str]:
        """لیست chainهای پشتیبانی شده."""
        return list(EXPLORER_CHAINS.keys())


# ===================== Singleton =====================

_evm_explorer_instance: Optional[EvmExplorerProxy] = None


def get_evm_explorer() -> EvmExplorerProxy:
    global _evm_explorer_instance
    if _evm_explorer_instance is None:
        _evm_explorer_instance = EvmExplorerProxy()
    return _evm_explorer_instance
