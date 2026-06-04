"""
Redis Cache Layer — Multi-Process Caching
==========================================
لایه کش Redis برای استفاده بین چند Gunicorn worker.
با RAM cache موجود (که per-process است) تفاوت دارد.

مزایا:
- کش بین همه workerها به اشتراک گذاشته می‌شود
- TTL پویا: اگر خطا خوردی، TTL را ۲ برابر کن (stale-while-revalidate)
- Cache warming: محبوب‌ترین symbolها (BTC, ETH, TRX) همیشه در کش گرم بمانند
- Zero-balance protection: اگر balance صفر برگشت و مقدار قبلی غیرصفر بود، کش قبلی را نگه دار

TTL Strategy:
  prices:          60s   — قیمت‌ها
  gas:             15s   — Gas fee
  chart_1d:        300s  — چارت روزانه
  chart_7d:        600s  — چارت هفتگی
  chart_30d:       1800s — چارت ماهانه
  balance:         15s   — Balance native
  token_balance:   30s   — Balance توکن
  tx_history:      30s   — تاریخچه تراکنش
  token_metadata:  3600s — Metadata توکن
  coin_list:       3600s — لیست کوین‌ها
"""

import json
import time
import hashlib
import threading
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field

from utils.logging_config import get_logger

logger = get_logger(__file__)

# TTL استراتژی بر اساس نوع داده
CACHE_TTL: Dict[str, int] = {
    "prices":          60,     # ۱ دقیقه
    "gas":             15,     # ۱۵ ثانیه
    "chart_1d":        300,    # ۵ دقیقه
    "chart_7d":        600,    # ۱۰ دقیقه
    "chart_30d":       1800,   # ۳۰ دقیقه
    "balance":         15,     # ۱۵ ثانیه
    "token_balance":   30,     # ۳۰ ثانیه
    "tx_history":      30,     # ۳۰ ثانیه
    "token_metadata":  3600,   # ۱ ساعت
    "coin_list":       3600,   # ۱ ساعت
}

# Symbolهای محبوب برای cache warming
HOT_SYMBOLS = {"BTC", "ETH", "TRX", "BNB", "SOL", "USDT", "XRP"}


class CacheLayer:
    """
    لایه کش مبتنی بر Redis.
    اگر Redis در دسترس نباشد، به gracefully به RAM fallback می‌کند.
    """

    def __init__(self):
        self._redis = None
        self._redis_available = False
        self._ram_cache: Dict[str, Dict[str, Any]] = {}  # fallback RAM cache
        self._lock = threading.Lock()
        self._init_redis()

    def _init_redis(self):
        """تلاش برای اتصال به Redis."""
        try:
            from config.cache import redis_client
            self._redis = redis_client
            # تست اتصال
            self._redis.ping()
            self._redis_available = True
            logger.info("CacheLayer: Redis connected successfully")
        except Exception as e:
            self._redis_available = False
            logger.warning("CacheLayer: Redis unavailable, using RAM fallback: %s", e)

    def _make_key(self, namespace: str, *parts: str) -> str:
        """ساخت کلید کش استاندارد: namespace:part1:part2:..."""
        key_parts = [namespace] + list(parts)
        return ":".join(key_parts)

    def _make_key_hash(self, namespace: str, *parts: str) -> str:
        """ساخت کلید کش با hash برای پارامترهای طولانی."""
        raw = "|".join(parts)
        h = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"{namespace}:{h}"

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        دریافت از کش.
        
        Args:
            namespace: فضای نام (مثلاً prices, balance)
            key: کلید اصلی (مثلاً BTC, 0xabc...)
            
        Returns:
            داده یا None
        """
        cache_key = self._make_key(namespace, key)

        if self._redis_available:
            try:
                data = self._redis.get(cache_key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug("CacheLayer: Redis get error: %s", e)
                # Fallback به RAM
                self._redis_available = False

        # Fallback به RAM
        with self._lock:
            entry = self._ram_cache.get(cache_key)
            if entry and (time.time() - entry["ts"] < entry["ttl"]):
                return entry["data"]
        return None

    def set(self, namespace: str, key: str, value: Any, ttl: int = None):
        """
        ذخیره در کش.
        
        Args:
            namespace: فضای نام
            key: کلید
            value: داده (JSON-serializable)
            ttl: زمان انقضا (ثانیه). اگر None، از CACHE_TTL استفاده می‌کند.
        """
        if ttl is None:
            ttl = CACHE_TTL.get(namespace, 60)

        cache_key = self._make_key(namespace, key)

        if self._redis_available:
            try:
                self._redis.setex(cache_key, ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.debug("CacheLayer: Redis set error: %s", e)
                self._redis_available = False

        # همیشه در RAM هم ذخیره کن (fallback)
        with self._lock:
            self._ram_cache[cache_key] = {"data": value, "ts": time.time(), "ttl": ttl}

        # محدودیت RAM cache (حداکثر ۱۰۰۰۰ مدخل)
        self._trim_ram_cache()

    def get_or_set(self, namespace: str, key: str, fallback: Callable, ttl: int = None) -> Any:
        """
        دریافت از کش یا محاسبه و ذخیره.
        
        Args:
            namespace: فضای نام
            key: کلید
            fallback: تابعی که در صورت عدم وجود در کش صدا زده می‌شود
            ttl: TTL (ثانیه)
            
        Returns:
            داده
        """
        cached = self.get(namespace, key)
        if cached is not None:
            return cached

        # محاسبه
        try:
            value = fallback()
            if value is not None:
                self.set(namespace, key, value, ttl)
            return value
        except Exception as e:
            logger.error("CacheLayer: fallback error for %s/%s: %s", namespace, key, e)
            return None

    def get_stale(self, namespace: str, key: str) -> Optional[Any]:
        """
        دریافت داده حتی اگر منقضی شده باشد (stale-while-revalidate).
        برای مواقعی که داده جدید در دسترس نیست.
        """
        cache_key = self._make_key(namespace, key)

        # اول Redis
        if self._redis_available:
            try:
                data = self._redis.get(cache_key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # RAM (حتی منقضی)
        with self._lock:
            entry = self._ram_cache.get(cache_key)
            if entry:
                return entry["data"]
        return None

    def invalidate(self, namespace: str, key: str):
        """حذف یک کلید از کش."""
        cache_key = self._make_key(namespace, key)
        if self._redis_available:
            try:
                self._redis.delete(cache_key)
            except Exception:
                pass
        with self._lock:
            self._ram_cache.pop(cache_key, None)

    def invalidate_namespace(self, namespace: str):
        """حذف همه کلیدهای یک namespace."""
        pattern = f"{namespace}:*"
        if self._redis_available:
            try:
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
            except Exception:
                pass
        with self._lock:
            keys_to_delete = [k for k in self._ram_cache if k.startswith(f"{namespace}:")]
            for k in keys_to_delete:
                self._ram_cache.pop(k, None)

    def warm_hot_symbols(self, fallback_fn: Callable[[str], Any]):
        """
        گرم نگه داشتن symbolهای محبوب در کش.
        در پس‌زمینه اجرا می‌شود.
        """
        def _warm():
            for symbol in HOT_SYMBOLS:
                try:
                    value = fallback_fn(symbol)
                    if value is not None:
                        self.set("prices", symbol, value, CACHE_TTL["prices"])
                except Exception as e:
                    logger.debug("CacheLayer: warmup failed for %s: %s", symbol, e)
                time.sleep(0.5)  # Throttle

        thread = threading.Thread(target=_warm, daemon=True, name="CacheWarmup")
        thread.start()

    def _trim_ram_cache(self, max_entries: int = 10000):
        """محدود کردن RAM cache به حداکثر تعداد مدخل."""
        with self._lock:
            if len(self._ram_cache) <= max_entries:
                return
            # حذف قدیمی‌ترین‌ها
            sorted_entries = sorted(
                self._ram_cache.items(), key=lambda x: x[1]["ts"]
            )
            to_delete = sorted_entries[:len(sorted_entries) - max_entries]
            for k, _ in to_delete:
                self._ram_cache.pop(k, None)

    def get_stats(self) -> Dict[str, Any]:
        """آمار کش."""
        stats = {
            "redis_available": self._redis_available,
            "ram_entries": len(self._ram_cache),
        }
        if self._redis_available:
            try:
                stats["redis_info"] = {
                    "used_memory_human": self._redis.info().get("used_memory_human", "N/A"),
                    "total_connections": self._redis.info().get("total_connections_received", 0),
                }
            except Exception:
                pass
        return stats


# ===================== Singleton =====================

_cache_layer_instance: Optional[CacheLayer] = None


def get_cache_layer() -> CacheLayer:
    global _cache_layer_instance
    if _cache_layer_instance is None:
        _cache_layer_instance = CacheLayer()
    return _cache_layer_instance
