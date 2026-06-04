"""
Custom Exceptions — Cache Proxy Core
=====================================
خطاهای سفارشی یکپارچه برای تمام لایه‌های proxy.
"""


class ProxyError(Exception):
    """خطای پایه همه خطاهای Proxy."""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class RateLimitError(ProxyError):
    """محدودیت نرخ درخواست — 429 Too Many Requests."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, details={"retry_after": retry_after})


class KeyExhaustedError(ProxyError):
    """همه کلیدهای API یک سرویس تمام شده‌اند — 503 Service Unavailable."""
    def __init__(self, pool_name: str):
        self.pool_name = pool_name
        super().__init__(
            f"All API keys exhausted for {pool_name}",
            status_code=503,
            details={"pool": pool_name},
        )


class ProviderError(ProxyError):
    """خطای provider خارجی — 502 Bad Gateway."""
    def __init__(self, provider: str, original_error: str = ""):
        self.provider = provider
        super().__init__(
            f"Provider {provider} error: {original_error}",
            status_code=502,
            details={"provider": provider, "original_error": original_error},
        )


class ProviderTimeoutError(ProxyError):
    """Timeout در ارتباط با provider خارجی."""
    def __init__(self, provider: str, timeout_ms: int):
        self.provider = provider
        self.timeout_ms = timeout_ms
        super().__init__(
            f"Provider {provider} timed out after {timeout_ms}ms",
            status_code=504,
            details={"provider": provider, "timeout_ms": timeout_ms},
        )


class CircuitBreakerOpenError(ProxyError):
    """مدارشکن provider باز است — 503."""
    def __init__(self, provider: str, cooldown_seconds: int):
        self.provider = provider
        self.cooldown_seconds = cooldown_seconds
        super().__init__(
            f"Circuit breaker open for {provider}, cooldown {cooldown_seconds}s",
            status_code=503,
            details={"provider": provider, "cooldown_seconds": cooldown_seconds},
        )


class ValidationError(ProxyError):
    """خطای اعتبارسنجی ورودی — 400 Bad Request."""
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, status_code=400)


class NotFoundError(ProxyError):
    """منبع درخواستی پیدا نشد — 404."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)
