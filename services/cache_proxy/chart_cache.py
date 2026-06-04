"""
Chart Cache — Non-Custodial Chart Data Proxy
==============================================

داده‌های نمودار (قیمت تاریخی) را از CoinGecko می‌گیرد و در RAM کش می‌کند.
هر ۵ دقیقه یکبار تازه می‌شود. بدون UserID.

⚡ Non-blocking: اگر داده در کش نیست، بلافاصله None برمی‌گرداند و در پس‌زمینه می‌گیرد.
"""

import time
import threading
from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from .price_cache import SYMBOL_TO_COINGECKO_ID
from .core.key_pool import get_key_pool_manager

logger = get_logger(__file__)


class ChartCache:
    """
    کش داده‌های نمودار در RAM.
    هر کلید کش ترکیبی از {symbol}_{days} است.
    Non-blocking: اگر داده در کش نیست، بلافاصله None برمی‌گرداند.
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds  # 5 دقیقه
        self._cache: Dict[str, Any] = {}  # key -> {data, ts}
        self._lock = threading.Lock()
        self._pending: set = set()  # keys currently being fetched
        self._cg_pool = get_key_pool_manager().get_pool("coingecko")

    def get_chart_data(
        self, symbol: str, days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        دریافت داده‌های نمودار برای یک ارز.
        Non-blocking: اگر در کش نباشد None برمی‌گرداند و در پس‌زمینه می‌گیرد.
        """
        cache_key = f"{symbol.upper()}_{days}"

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached["ts"] < self.ttl):
                return cached["data"]

        # اگر در حال fetch نیستیم، در پس‌زمینه شروع کن
        if cache_key not in self._pending:
            self._start_background_fetch(cache_key, symbol, days)

        # اگر داده قدیمی داریم، برگردان
        if cached:
            logger.debug("ChartCache: serving stale data for %s", cache_key)
            return cached["data"]

        return None

    def clear(self):
        with self._lock:
            self._cache.clear()
        logger.info("ChartCache: cleared")

    # --- Non-blocking fetch ---

    def _start_background_fetch(self, cache_key: str, symbol: str, days: int):
        self._pending.add(cache_key)
        thread = threading.Thread(
            target=self._background_fetch,
            args=(cache_key, symbol, days),
            daemon=True,
            name=f"ChartFetch-{symbol}",
        )
        thread.start()

    def _background_fetch(self, cache_key: str, symbol: str, days: int):
        try:
            data = self._fetch_from_coingecko(symbol, days)
            if data:
                with self._lock:
                    self._cache[cache_key] = {"data": data, "ts": time.time()}
                logger.info(
                    "ChartCache: cached %s (%dd) — %d points (background)",
                    symbol, days, len(data.get("prices", [])),
                )
        except Exception as e:
            logger.error("ChartCache: background fetch error: %s", e, exc_info=True)
        finally:
            self._pending.discard(cache_key)

    def _fetch_from_coingecko(
        self, symbol: str, days: int
    ) -> Optional[Dict[str, Any]]:
        """دریافت داده‌های نمودار از CoinGecko با کلید API."""
        try:
            cg_id = SYMBOL_TO_COINGECKO_ID.get(symbol.upper())
            if not cg_id:
                logger.warning("ChartCache: unknown symbol %s", symbol)
                return None

            url = (
                f"https://api.coingecko.com/api/v3/coins/{cg_id}"
                f"/market_chart?vs_currency=usd&days={days}"
            )

            headers = {"Accept": "application/json"}
            used_key = None
            if self._cg_pool:
                key_tuple = self._cg_pool.get_next_key()
                if key_tuple:
                    used_key, _ = key_tuple
                    headers["x-cg-demo-api-key"] = used_key

            logger.debug("ChartCache: fetching %s (%dd) from CoinGecko", symbol, days)
            resp = requests.get(url, headers=headers, timeout=20)

            if self._cg_pool and used_key:
                if resp.status_code == 200:
                    self._cg_pool.mark_success(used_key)
                elif resp.status_code == 429:
                    self._cg_pool.mark_rate_limited(used_key, cooldown=60)

            if resp.status_code != 200:
                logger.warning(
                    "ChartCache: CoinGecko returned %s for %s",
                    resp.status_code, symbol,
                )
                return None

            data = resp.json()
            prices = data.get("prices", [])
            market_caps = data.get("market_caps", [])
            volumes = data.get("total_volumes", [])

            if not prices:
                return None

            result = {
                "prices": [p[1] for p in prices],
                "timestamps": [p[0] for p in prices],
                "market_caps": [m[1] for m in market_caps] if market_caps else [],
                "volumes": [v[1] for v in volumes] if volumes else [],
                "symbol": symbol.upper(),
                "days": days,
                "source": "coingecko",
            }

            return result

        except requests.RequestException as e:
            logger.warning("ChartCache: CoinGecko request failed for %s: %s", symbol, e)
            return None
        except Exception as e:
            logger.error("ChartCache: error for %s: %s", symbol, e, exc_info=True)
            return None


# Singleton
_chart_cache_instance: Optional[ChartCache] = None


def get_chart_cache() -> ChartCache:
    global _chart_cache_instance
    if _chart_cache_instance is None:
        _chart_cache_instance = ChartCache()
    return _chart_cache_instance
