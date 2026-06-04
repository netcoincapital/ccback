"""
Rate Limiter — Token Bucket + Sliding Window
=============================================
دو سطح محدودیت:

LEVEL_1: "per IP"     = 100 req/min — جلوگیری از سوءاستفاده عمومی
LEVEL_2: "per address" = 30 req/min — انصاف بین کاربران واقعی

Endpointهای حساس (broadcast): 5 req/min per address
"""

import time
import threading
import functools
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field

from utils.logging_config import get_logger
from .errors import RateLimitError

logger = get_logger(__file__)


@dataclass
class TokenBucket:
    """پیاده‌سازی Token Bucket با نرخ ثابت."""
    capacity: int           # حداکثر تعداد token
    refill_rate: float      # token per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def _refill(self):
        """پر کردن مجدد tokenها بر اساس زمان گذشته."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, count: int = 1) -> bool:
        """
        مصرف token. برمی‌گرداند آیا مجاز است یا نه.
        
        Returns:
            True اگر مجاز باشد، False اگر محدودیت اعمال شود
        """
        self._refill()
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False

    @property
    def wait_time(self) -> float:
        """زمان انتظار تا داشتن token کافی (بر حسب ثانیه)."""
        self._refill()
        if self.tokens >= 1:
            return 0.0
        return (1 - self.tokens) / self.refill_rate if self.refill_rate > 0 else float('inf')


class RateLimiter:
    """
    Rate limiter با دو سطح: IP و Blockchain Address.
    برای endpointهای حساس محدودیت سخت‌تر اعمال می‌کند.
    """

    # محدودیت‌های پیش‌فرض
    DEFAULT_LIMITS = {
        "ip": {
            "capacity": 100,        # 100 req
            "refill_rate": 100/60,  # در دقیقه
        },
        "address": {
            "capacity": 30,
            "refill_rate": 30/60,   # 30 req/min
        },
        "broadcast": {
            "capacity": 5,
            "refill_rate": 5/60,    # 5 req/min
        },
    }

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def check_ip(self, ip: str) -> bool:
        """بررسی محدودیت IP."""
        return self._check(f"ip:{ip}", "ip")

    def check_address(self, address: str) -> bool:
        """بررسی محدودیت Blockchain Address."""
        return self._check(f"addr:{address}", "address")

    def check_broadcast(self, address: str) -> bool:
        """بررسی محدودیت Broadcast (سخت‌تر)."""
        return self._check(f"broadcast:{address}", "broadcast")

    def check_or_raise_ip(self, ip: str):
        """بررسی IP و پرتاب RateLimitError در صورت محدودیت."""
        if not self.check_ip(ip):
            wait = self._get_wait_time(f"ip:{ip}", "ip")
            raise RateLimitError(
                message=f"IP rate limit exceeded. Retry after {wait:.0f}s",
                retry_after=int(wait),
            )

    def check_or_raise_address(self, address: str):
        """بررسی Address و پرتاب RateLimitError."""
        if not self.check_address(address):
            wait = self._get_wait_time(f"addr:{address}", "address")
            raise RateLimitError(
                message=f"Address rate limit exceeded. Retry after {wait:.0f}s",
                retry_after=int(wait),
            )

    def get_status(self) -> Dict[str, int]:
        """وضعیت فعلی rate limiter (تعداد bucketهای فعال)."""
        with self._lock:
            return {
                "ip_buckets": sum(1 for k in self._buckets if k.startswith("ip:")),
                "address_buckets": sum(1 for k in self._buckets if k.startswith("addr:")),
                "broadcast_buckets": sum(1 for k in self._buckets if k.startswith("broadcast:")),
                "total_buckets": len(self._buckets),
            }

    # --- Private ---

    def _check(self, bucket_key: str, limit_type: str) -> bool:
        config = self.DEFAULT_LIMITS.get(limit_type, self.DEFAULT_LIMITS["ip"])
        with self._lock:
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=config["capacity"],
                    refill_rate=config["refill_rate"],
                )
                self._buckets[bucket_key] = bucket
            return bucket.consume()

    def _get_wait_time(self, bucket_key: str, limit_type: str) -> float:
        with self._lock:
            bucket = self._buckets.get(bucket_key)
            if bucket:
                return bucket.wait_time
        return 0.0


# ===================== Singleton =====================

_rate_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance


# ===================== Decorator Helpers =====================


def rate_limit_ip(func: Callable) -> Callable:
    """دکوریتور محدودیت IP برای routeهای Flask."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request
        ip = request.remote_addr or "unknown"
        get_rate_limiter().check_or_raise_ip(ip)
        return func(*args, **kwargs)
    return wrapper


def rate_limit_address(func: Callable) -> Callable:
    """دکوریتور محدودیت Address برای routeهای Flask (مقدار address را از body می‌خواند)."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request
        data = request.get_json(silent=True) or {}
        address = data.get("address", "") or kwargs.get("address", "")
        if address:
            get_rate_limiter().check_or_raise_address(address)
        return func(*args, **kwargs)
    return wrapper
