"""
Cache Proxy — Non-Custodial Caching Layer + Hybrid Backend
============================================================

این ماژول سرور را از Custodial API به Caching Proxy تبدیل می‌کند.
همه endpointهای عمومی (قیمت، نمودار، کارمزد، لیست ارزها، نوتیفیکیشن) بدون UserID
و با کش در RAM/Redis سرویس می‌شوند.

## معماری Hybrid (۳ لایه):

1. **V2 Public Endpoints** (`routes_v2.py`): قیمت، نمودار، کارمزد، لیست ارزها، airdrop، نوتیفیکیشن
2. **V3 Enhanced Endpoints** (`routes_v3.py`): Explorer, Balance, RPC, Broadcast, Token Metadata
3. **Core Modules** (`core/`): Redis Cache, Rate Limiter, Key Pool Manager
4. **Provider Modules** (`providers/`): EVM Explorer, EVM RPC, TronGrid, BlockCypher, Subscan

مزایا:
- Non-Custodial: هیچ UserID یا اطلاعات کاربری ذخیره/ارسال نمی‌شود
- مقیاس‌پذیر: بار سرور ثابت (مستقل از تعداد کاربران)
- هزینه: از CoinGecko رایگان + Public RPC + Block Explorer Free Tier استفاده می‌کند
- سرعت: پاسخ از RAM در زیر ۱ms
- Fallback: اگر سرویسی در دسترس نباشد، به provider بعدی می‌رود
"""

# V2 Caches
from .price_cache import PriceCache, get_price_cache
from .chart_cache import ChartCache, get_chart_cache
from .coin_cache import CoinCache, get_coin_cache
from .gas_cache import GasCache, get_gas_cache
from .airdrop_cache import AirdropCache, get_airdrop_cache

# V2 Routes
from .routes_v2 import cache_proxy_bp

# V3 Enhanced Routes
from .routes_v3 import cache_proxy_v3_bp

# Block Scanner (Auto-starts on import in app.py)
from . import block_scanner

# Core Modules
from . import core

# Provider Modules
from . import providers

__all__ = [
    # V2 Caches
    "PriceCache",
    "get_price_cache",
    "ChartCache",
    "get_chart_cache",
    "CoinCache",
    "get_coin_cache",
    "GasCache",
    "get_gas_cache",
    "AirdropCache",
    "get_airdrop_cache",
    # Routes
    "cache_proxy_bp",
    "cache_proxy_v3_bp",
    # Block Scanner
    "block_scanner",
    # Core
    "core",
    # Providers
    "providers",
]
