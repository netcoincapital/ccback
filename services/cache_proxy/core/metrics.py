"""
Prometheus Metrics — Cache Proxy Monitoring
=============================================
ماژول مانیتورینگ برای:
  - تعداد درخواست‌ها per endpoint (counter)
  - تأخیر پاسخ per endpoint (histogram)
  - وضعیت KeyPool (تعداد کلیدهای active/exhausted/rate_limited)
  - وضعیت Cache (hit/miss ratio, size)
  - خطاها per provider (counter)
  - Rate limit hits (counter)

در صورت نبود Prometheus، ماژول gracefully غیرفعال می‌شود.
"""

import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from utils.logging_config import get_logger

logger = get_logger(__file__)

# تلاش برای import Prometheus client
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("Metrics: prometheus_client not installed, using in-memory counters")


class MetricsCollector:
    """
    جمع‌آوری metrics با دو حالت:
    1. Prometheus client (اگر installed باشد)
    2. In-memory counters (Fallback)
    """

    def __init__(self):
        self._enabled = PROMETHEUS_AVAILABLE
        self._lock = threading.Lock()

        # In-memory counters (Fallback)
        self._request_count: Dict[str, int] = {}
        self._error_count: Dict[str, int] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._rate_limit_hits: int = 0
        self._total_latency_ms: Dict[str, float] = {}
        self._latency_count: Dict[str, int] = {}

        if self._enabled:
            self._init_prometheus()

    def _init_prometheus(self):
        """راه‌اندازی metrics Prometheus."""
        try:
            self._req_counter = Counter(
                "proxy_requests_total", "Total requests per endpoint",
                ["endpoint", "method", "status"],
            )
            self._error_counter = Counter(
                "proxy_errors_total", "Total errors per provider",
                ["provider", "error_type"],
            )
            self._latency_histogram = Histogram(
                "proxy_request_duration_ms", "Request latency per endpoint (ms)",
                ["endpoint"], buckets=[10, 25, 50, 100, 200, 500, 1000, 2000, 5000],
            )
            self._cache_hits_gauge = Gauge("proxy_cache_hits_total", "Cache hits")
            self._cache_misses_gauge = Gauge("proxy_cache_misses_total", "Cache misses")
            self._rate_limit_gauge = Gauge("proxy_rate_limit_hits_total", "Rate limit hits")
            self._active_keys_gauge = Gauge(
                "proxy_keypool_active_keys", "Active keys per pool",
                ["pool"],
            )
            self._exhausted_keys_gauge = Gauge(
                "proxy_keypool_exhausted_keys", "Exhausted keys per pool",
                ["pool"],
            )
            logger.info("Metrics: Prometheus metrics initialized")
        except Exception as e:
            self._enabled = False
            logger.warning("Metrics: Prometheus init failed: %s", e)

    # ===================== Record Methods =====================

    def record_request(self, endpoint: str, method: str = "GET", status: int = 200, latency_ms: float = 0):
        """ثبت یک درخواست."""
        ep = endpoint.rstrip("/") or "root"

        if self._enabled:
            try:
                self._req_counter.labels(endpoint=ep, method=method, status=str(status)).inc()
                self._latency_histogram.labels(endpoint=ep).observe(latency_ms)
            except Exception:
                pass
        else:
            with self._lock:
                key = f"{method}:{ep}:{status}"
                self._request_count[key] = self._request_count.get(key, 0) + 1
                self._total_latency_ms[ep] = self._total_latency_ms.get(ep, 0) + latency_ms
                self._latency_count[ep] = self._latency_count.get(ep, 0) + 1

    def record_error(self, provider: str, error_type: str = "unknown"):
        """ثبت خطا."""
        if self._enabled:
            try:
                self._error_counter.labels(provider=provider, error_type=error_type).inc()
            except Exception:
                pass
        else:
            with self._lock:
                key = f"{provider}:{error_type}"
                self._error_count[key] = self._error_count.get(key, 0) + 1

    def record_cache_hit(self):
        """ثبت Cache Hit."""
        if self._enabled:
            try:
                self._cache_hits_gauge.inc()
            except Exception:
                pass
        else:
            with self._lock:
                self._cache_hits += 1

    def record_cache_miss(self):
        """ثبت Cache Miss."""
        if self._enabled:
            try:
                self._cache_misses_gauge.inc()
            except Exception:
                pass
        else:
            with self._lock:
                self._cache_misses += 1

    def record_rate_limit(self):
        """ثبت Rate Limit hit."""
        if self._enabled:
            try:
                self._rate_limit_gauge.inc()
            except Exception:
                pass
        else:
            with self._lock:
                self._rate_limit_hits += 1

    def update_keypool_gauges(self, pool_name: str, active: int, exhausted: int):
        """به‌روزرسانی Gaugeهای KeyPool."""
        if self._enabled:
            try:
                self._active_keys_gauge.labels(pool=pool_name).set(active)
                self._exhausted_keys_gauge.labels(pool=pool_name).set(exhausted)
            except Exception:
                pass

    # ===================== Export =====================

    def export_prometheus(self) -> Optional[bytes]:
        """خروجی Prometheus format."""
        if self._enabled:
            try:
                return generate_latest(REGISTRY)
            except Exception as e:
                logger.error("Metrics: export error: %s", e)
        return None

    def export_json(self) -> Dict[str, Any]:
        """خروجی JSON (برای Fallback)."""
        with self._lock:
            total_requests = sum(self._request_count.values())
            total_errors = sum(self._error_count.values())
            cache_ratio = 0.0
            if self._cache_hits + self._cache_misses > 0:
                cache_ratio = self._cache_hits / (self._cache_hits + self._cache_misses)

            # میانگین latency per endpoint
            avg_latency = {}
            for ep in self._total_latency_ms:
                if self._latency_count.get(ep, 0) > 0:
                    avg_latency[ep] = round(
                        self._total_latency_ms[ep] / self._latency_count[ep], 2
                    )

            return {
                "requests": {
                    "total": total_requests,
                    "per_endpoint": dict(self._request_count),
                },
                "errors": {
                    "total": total_errors,
                    "per_provider": dict(self._error_count),
                },
                "cache": {
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "hit_ratio": round(cache_ratio, 4),
                },
                "rate_limits": self._rate_limit_hits,
                "avg_latency_ms": avg_latency,
            }

    @property
    def is_prometheus_enabled(self) -> bool:
        return self._enabled


# ===================== Singleton =====================

_metrics_instance: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance
