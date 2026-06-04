"""
Coin Cache — Non-Custodial Coin List Proxy
============================================

لیست کامل ارزهای دیجیتال را از CoinGecko می‌گیرد و در RAM کش می‌کند.
یکبار در روز تازه می‌شود. بدون UserID.

⚡ Non-blocking: اولین بار در پس‌زمینه پر می‌شود، درخواست را مسدود نمی‌کند.
⚡ Warmup: به محض import ماژول، یک نخ پس‌زمینه شروع به پر کردن کش می‌کند.

Fallback: از دیتابیس محلی (جدول currencies) می‌خواند.
"""

import time
import threading
from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger
from .core.key_pool import get_key_pool_manager

logger = get_logger(__file__)


class CoinCache:
    """
    کش لیست ارزها در RAM.
    هر ۲۴ ساعت یکبار تازه می‌شود.
    Non-blocking: اگر کش خالی باشد، بلافاصله [] برمی‌گرداند و در پس‌زمینه رفرش می‌کند.
    """

    def __init__(self, ttl_seconds: int = 86400):
        self.ttl = ttl_seconds  # 24 ساعت
        self._cache: List[Dict[str, Any]] = []
        self._last_update: float = 0.0
        self._lock = threading.Lock()
        self._refresh_in_progress = False
        self._cg_pool = get_key_pool_manager().get_pool("coingecko")

    def get_all_coins(self) -> List[Dict[str, Any]]:
        """برگرداندن لیست همه ارزها. هیچوقت مسدود نمی‌کند."""
        self._ensure_fresh()
        return list(self._cache)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """جستجو در لیست ارزها بر اساس نام یا سمبل. هیچوقت مسدود نمی‌کند."""
        self._ensure_fresh()
        q = query.lower()
        results = []
        for coin in self._cache:
            if (
                q in coin.get("symbol", "").lower()
                or q in coin.get("name", "").lower()
            ):
                results.append(coin)
        return results

    def ready(self) -> bool:
        """آیا کش آماده است؟ (داده دارد)"""
        return len(self._cache) > 0

    def get_refresh_status(self) -> str:
        if self._refresh_in_progress:
            return "refreshing"
        if self._cache:
            return "ready"
        return "empty"

    def get_age_seconds(self) -> float:
        age = time.time() - self._last_update
        if self._last_update == 0:
            return float("inf")  # هرگز رفرش نشده
        return age

    # --- Non-blocking refresh ---

    def _ensure_fresh(self):
        """اگر کش منقضی شده و رفرش در حال اجرا نیست، در پس‌زمینه رفرش کن."""
        needs_refresh = (
            self._last_update == 0
            or time.time() - self._last_update > self.ttl
        )
        if needs_refresh:
            self._start_background_refresh()

    def _start_background_refresh(self):
        """شروع رفرش در یک نخ پس‌زمینه."""
        with self._lock:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True

        thread = threading.Thread(
            target=self._background_refresh,
            daemon=True,
            name="CoinCacheRefresh",
        )
        thread.start()
        logger.debug("CoinCache: background refresh started")

    def _background_refresh(self):
        """رفرش واقعی در نخ پس‌زمینه."""
        try:
            success = self._fetch_from_coingecko()
            if success:
                self._last_update = time.time()
                logger.info(
                    "CoinCache: refreshed %d coins from CoinGecko (background)",
                    len(self._cache),
                )
            else:
                db_success = self._fetch_from_db()
                if db_success:
                    self._last_update = time.time()
                    logger.info(
                        "CoinCache: fallback refreshed %d coins from DB (background)",
                        len(self._cache),
                    )
                else:
                    logger.warning("CoinCache: background refresh failed")
        except Exception as e:
            logger.error("CoinCache: background refresh error: %s", e, exc_info=True)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    # --- CoinGecko fetch ---

    def _fetch_from_coingecko(self) -> bool:
        """
        دریافت لیست ارزها از CoinGecko با کلید API.
        بدون include_platform برای سرعت بیشتر (۱۰ برابر سریع‌تر).
        """
        try:
            url = "https://api.coingecko.com/api/v3/coins/list"
            headers = {"Accept": "application/json"}
            used_key = None
            if self._cg_pool:
                key_tuple = self._cg_pool.get_next_key()
                if key_tuple:
                    used_key, _ = key_tuple
                    headers["x-cg-demo-api-key"] = used_key

            logger.debug("CoinCache: fetching list from CoinGecko")
            resp = requests.get(url, headers=headers, timeout=15)

            if self._cg_pool and used_key:
                if resp.status_code == 200:
                    self._cg_pool.mark_success(used_key)
                elif resp.status_code == 429:
                    self._cg_pool.mark_rate_limited(used_key, cooldown=60)

            if resp.status_code != 200:
                logger.warning(
                    "CoinCache: CoinGecko returned %s", resp.status_code
                )
                return False

            data = resp.json()
            if not isinstance(data, list):
                return False

            coins = []
            for item in data:
                coin_id = item.get("id", "")
                symbol = item.get("symbol", "")
                name = item.get("name", "")

                if coin_id and symbol:
                    coins.append({
                        "id": coin_id,
                        "symbol": symbol.upper(),
                        "name": name,
                    })

            self._cache = coins
            return True

        except requests.RequestException as e:
            logger.warning("CoinCache: CoinGecko request failed: %s", e)
            return False
        except Exception as e:
            logger.error("CoinCache: parse error: %s", e, exc_info=True)
            return False

    # --- DB fallback ---

    def _fetch_from_db(self) -> bool:
        """Fallback: خواندن لیست ارزها از دیتابیس."""
        try:
            from database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT Symbol, CurrencyName, CMC_ID
                        FROM currencies
                        ORDER BY CurrencyID ASC
                    """)
                ).fetchall()

                coins = []
                for row in rows:
                    symbol = row[0] if row[0] else ""
                    name = row[1] if row[1] else ""
                    coins.append({
                        "id": str(row[2]) if row[2] else symbol,
                        "symbol": symbol.upper(),
                        "name": name,
                        "source": "db",
                    })

                self._cache = coins
                return True

        except Exception as e:
            logger.warning("CoinCache: DB fallback failed: %s", e)
            return False


# ===================== Singleton =====================

_coin_cache_instance: Optional[CoinCache] = None


def get_coin_cache() -> CoinCache:
    global _coin_cache_instance
    if _coin_cache_instance is None:
        _coin_cache_instance = CoinCache()
    return _coin_cache_instance


# ===================== Warmup on import =====================
# اولین رفرش بلافاصله در پس‌زمینه شروع می‌شود
_cache_for_warmup: Optional[CoinCache] = None


def _warmup_coin_cache():
    """
    Warmup with random stagger (0-60s) to prevent thundering herd across Gunicorn workers.
    """
    global _cache_for_warmup
    import random
    delay = random.uniform(0, 60)
    logger.info("CoinCache: warmup will start in %.1fs (stagger)", delay)
    time.sleep(delay)
    try:
        cc = get_coin_cache()
        _cache_for_warmup = cc
        cc._start_background_refresh()
        logger.info("CoinCache: warmup initiated (background thread started)")
    except Exception as e:
        logger.warning("CoinCache: warmup failed (will warm on first request): %s", e)


# شروع warmup در نخ جداگانه
_warmup_thread = threading.Thread(target=_warmup_coin_cache, daemon=True, name="CoinCacheWarmup")
_warmup_thread.start()
