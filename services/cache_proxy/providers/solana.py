"""
Solana Proxy — Solana RPC API Wrapper
=======================================
Wrapper برای Solana RPC با استفاده از کلیدهای Helius از vm_api_keys.env.

منابع:
  - Helius (HELIUS_API_KEY_1..9)          ← اولویت اول
  - SolanaTracker (SOLANA_RPC_URL_1..3)   ← Fallback
  - Public Solana RPC                      ← Last resort

Endpointهای پشتیبانی شده:
  - getBalance
  - getSignaturesForAddress (تاریخچه تراکنش)
  - getTransaction (جزئیات تراکنش)
  - getTokenAccountBalance (balance SPL توکن)
  - getAccountInfo
"""

import time
import os
import threading
from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager, KeyPool
from ..core.errors import ProviderError, ProviderTimeoutError

logger = get_logger(__file__)

REQUEST_TIMEOUT = 15  # ثانیه

# ============================================================
# بارگذاری RPC URLها از env
# ============================================================

def _build_solana_rpc_urls() -> List[str]:
    """
    ساخت لیست RPC URLs برای Solana از متغیرهای محیطی.
    
    اولویت:
      1. HELIUS_API_KEY_1..9 → https://mainnet.helius-rpc.com/?api-key={KEY}
      2. SOLANA_RPC_URL_1..3 (SolanaTracker)
      3. Public endpoint (last resort)
    """
    urls: List[str] = []
    pool_manager = get_key_pool_manager()
    helius_pool = pool_manager.get_pool("helius")

    # ۱. Helius
    if helius_pool:
        for _ in range(helius_pool.total_keys):
            key_tuple = helius_pool.get_next_key()
            if key_tuple:
                api_key, _ = key_tuple
                urls.append(f"https://mainnet.helius-rpc.com/?api-key={api_key}")

    # ۲. SolanaTracker
    for idx in range(1, 4):
        url = os.environ.get(f"SOLANA_RPC_URL_{idx}", "").strip()
        if url and url not in urls:
            urls.append(url)

    # ۳. Public
    public_url = "https://api.mainnet-beta.solana.com"
    if public_url not in urls:
        urls.append(public_url)

    return urls


class SolanaProxy:
    """
    Proxy برای Solana RPC.
    Thread-safe.
    """

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._rpc_urls = _build_solana_rpc_urls()
        self._url_index = 0
        self._lock = threading.Lock()
        logger.info("SolanaProxy: initialized with %d RPC endpoints", len(self._rpc_urls))

    def _request(self, method: str, params: List[Any] = None) -> Optional[Dict]:
        """
        درخواست JSON-RPC به Solana.
        در صورت خطا به URL بعدی می‌رود (round-robin failover).
        """
        params = params or []
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 100000,
            "method": method,
            "params": params,
        }

        # تلاش روی همه URLs
        for attempt in range(len(self._rpc_urls)):
            with self._lock:
                url = self._rpc_urls[self._url_index]
                self._url_index = (self._url_index + 1) % len(self._rpc_urls)

            try:
                resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT,
                                     headers={"Content-Type": "application/json"})

                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data and data["error"]:
                        logger.debug("SolanaProxy: RPC error on %s...: %s",
                                     url[:30], data["error"].get("message", ""))
                        continue
                    return data

                elif resp.status_code == 429:
                    logger.debug("SolanaProxy: rate limited on %s...", url[:30])
                    continue
                else:
                    logger.debug("SolanaProxy: %s returned %d", url[:30], resp.status_code)
                    continue

            except requests.Timeout:
                logger.debug("SolanaProxy: timeout on %s...", url[:30])
                continue
            except requests.ConnectionError as e:
                logger.debug("SolanaProxy: connection error on %s...: %s", url[:30], e)
                continue
            except Exception as e:
                logger.debug("SolanaProxy: error on %s...: %s", url[:30], e)
                continue

        logger.warning("SolanaProxy: all RPC endpoints failed for %s", method)
        return None

    # ===================== Public APIs =====================

    def get_balance(self, address: str) -> Optional[int]:
        """
        دریافت balance SOL.
        
        Args:
            address: آدرس Solana (base58)
            
        Returns:
            balance (lamports) یا None
        """
        result = self._request("getBalance", [address])
        if result and "result" in result:
            return result["result"].get("value")
        return None

    def get_transactions(
        self, address: str, limit: int = 25, before: str = None
    ) -> Optional[List[Dict]]:
        """
        دریافت تاریخچه تراکنش.
        
        Args:
            address: آدرس Solana
            limit: تعداد
            before: signature برای page before
            
        Returns:
            لیست signatureها یا None
        """
        params = [address, {"limit": min(limit, 100)}]
        if before:
            params[1]["before"] = before

        result = self._request("getSignaturesForAddress", params)
        if result and "result" in result:
            return result["result"]
        return None

    def get_transaction_detail(self, tx_signature: str) -> Optional[Dict]:
        """
        دریافت جزئیات یک تراکنش.
        
        Args:
            tx_signature: signature تراکنش
            
        Returns:
            جزئیات تراکنش یا None
        """
        result = self._request(
            "getTransaction",
            [tx_signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        if result and "result" in result:
            return result["result"]
        return None

    def get_token_balance(self, address: str, token_mint: str = None) -> Optional[List[Dict]]:
        """
        دریافت balance همه توکن‌های SPL یک آدرس.
        
        Args:
            address: آدرس Solana
            token_mint: (اختیاری) فیلتر بر اساس mint توکن
            
        Returns:
            لیست token balances یا None
        """
        result = self._request("getTokenAccountsByOwner", [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}
            if not token_mint else {"mint": token_mint},
            {"encoding": "jsonParsed"},
        ])
        if result and "result" in result:
            return result["result"].get("value", [])
        return None

    def get_account_info(self, address: str) -> Optional[Dict]:
        """
        دریافت اطلاعات حساب.
        
        Args:
            address: آدرس Solana
            
        Returns:
            اطلاعات حساب یا None
        """
        result = self._request("getAccountInfo", [address, {"encoding": "jsonParsed"}])
        if result and "result" in result:
            return result["result"]
        return None

    def get_recent_blockhash(self) -> Optional[str]:
        """
        دریافت recent blockhash (برای ساخت تراکنش).
        
        Returns:
            blockhash یا None
        """
        result = self._request("getRecentBlockhash")
        if result and "result" in result:
            return result["result"].get("value", {}).get("blockhash")
        return None

    def get_supported_chains(self) -> List[str]:
        return ["solana"]


# Singleton
_solana_proxy_instance: Optional[SolanaProxy] = None


def get_solana_proxy() -> SolanaProxy:
    global _solana_proxy_instance
    if _solana_proxy_instance is None:
        _solana_proxy_instance = SolanaProxy()
    return _solana_proxy_instance
