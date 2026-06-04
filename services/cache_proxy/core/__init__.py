"""
Cache Proxy — Core Module
==========================
ماژول‌های هسته معماری Hybrid Backend Proxy:

- cache.py:        لایه کش Redis با TTL پویا و stale-while-revalidate
- rate_limiter.py: Token bucket rate limiter per IP/Address
- key_pool.py:     مدیریت Round-Robin Key Pool با health tracking
- errors.py:       Custom exceptions یکپارچه
- metrics.py:      Prometheus metrics + in-memory counters
"""

from .cache import CacheLayer, CACHE_TTL, get_cache_layer
from .rate_limiter import RateLimiter, rate_limit_ip, rate_limit_address, get_rate_limiter
from .key_pool import KeyPool, KeyStatus, get_key_pool_manager
from .errors import (
    ProxyError,
    RateLimitError,
    KeyExhaustedError,
    ProviderError,
    ProviderTimeoutError,
    CircuitBreakerOpenError,
)
from .metrics import MetricsCollector, get_metrics

__all__ = [
    "CacheLayer",
    "CACHE_TTL",
    "get_cache_layer",
    "RateLimiter",
    "rate_limit_ip",
    "rate_limit_address",
    "get_rate_limiter",
    "KeyPool",
    "KeyStatus",
    "get_key_pool_manager",
    "MetricsCollector",
    "get_metrics",
    "ProxyError",
    "RateLimitError",
    "KeyExhaustedError",
    "ProviderError",
    "ProviderTimeoutError",
    "CircuitBreakerOpenError",
]
