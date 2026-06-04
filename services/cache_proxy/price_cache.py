"""
Price Cache — Non-Custodial Price Proxy
=========================================

قیمت‌ها را از CoinGecko می‌گیرد و در RAM کش می‌کند.
از کلیدهای secrets/vm_api_keys.env (COINGECKO_API_KEY_1..6) برای Rate Limit بالاتر استفاده می‌کند.
هر ۲ دقیقه یکبار تازه می‌شود. بدون UserID.

⚡ Non-blocking: اولین بار در پس‌زمینه پر می‌شود، درخواست را مسدود نمی‌کند.
⚡ Warmup: به محض import ماژول، یک نخ پس‌زمینه شروع به پر کردن کش می‌کند.
⚡ Key Pool: از KeyPoolManager برای round-robin کلیدهای CoinGecko استفاده می‌کند.

Fallback: اگر CoinGecko در دسترس نباشد، از دیتابیس محلی (CoinMarketCap) می‌خواند.
"""

import time
import threading
from typing import Dict, Optional, Any

import requests

from utils.logging_config import get_logger
from .core.key_pool import get_key_pool_manager

logger = get_logger(__file__)

# CoinGecko ID → symbol mapping (ارزهای اصلی)
SYMBOL_TO_COINGECKO_ID: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "USDC": "usd-coin",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "TRX": "tron",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "SHIB": "shiba-inu",
    "DAI": "dai",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "ATOM": "cosmos",
    "XLM": "stellar",
    "UNI": "uniswap",
    "FIL": "filecoin",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "NEAR": "near",
    "ICP": "internet-computer",
    "VET": "vechain",
    "TUSD": "true-usd",
    "FRAX": "frax",
    "AAVE": "aave",
    "ALGO": "algorand",
    "MANA": "decentraland",
    "SAND": "the-sandbox",
    "AXS": "axie-infinity",
    "EGLD": "elrond-erd-2",
    "FLOW": "flow",
    "XTZ": "tezos",
    "EOS": "eos",
    "THETA": "theta-token",
    "KSM": "kusama",
    "YFI": "yearn-finance",
    "MKR": "maker",
    "COMP": "compound",
    "SUSHI": "sushi",
    "GRT": "the-graph",
    "CHZ": "chiliz",
    "ENJ": "enjincoin",
    "RUNE": "thorchain",
    "CRV": "curve-dao-token",
    "1INCH": "1inch",
    "STX": "stacks",
    "IMX": "immutable-x",
    "DYDX": "dydx",
    "GALA": "gala",
    "PEPE": "pepe",
}

# CoinGecko ID → symbol (معکوس)
COINGECKO_ID_TO_SYMBOL: Dict[str, str] = {
    v: k for k, v in SYMBOL_TO_COINGECKO_ID.items()
}


class PriceCache:
    """
    قیمت‌ها را از CoinGecko می‌گیرد و در RAM کش می‌کند.
    Thread-safe. Non-blocking.
    """

    def __init__(self, ttl_seconds: int = 120):
        self.ttl = ttl_seconds  # 2 دقیقه (پیش‌فرض)
        self._cache: Dict[str, Any] = {}
        self._last_update: float = 0.0
        self._lock = threading.Lock()
        self._refresh_in_progress = False

        # CoinGecko Key Pool (از secrets/vm_api_keys.env)
        self._cg_pool = get_key_pool_manager().get_pool("coingecko")
        self._cg_key_index = 0
        if self._cg_pool:
            logger.info("PriceCache: CoinGecko key pool available (%d keys)",
                        self._cg_pool.total_keys)

    # --- دسترسی عمومی (بدون UserID) ---

    def get_all_prices(self) -> Dict[str, Any]:
        """
        برگرداندن همه قیمت‌های کش شده.
        هیچوقت مسدود نمی‌کند — اگر کش خالی باشد {} برمی‌گرداند و در پس‌زمینه رفرش می‌کند.
        """
        self._ensure_fresh()
        return dict(self._cache)

    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """قیمت یک ارز خاص را برمی‌گرداند. هیچوقت مسدود نمی‌کند."""
        self._ensure_fresh()
        return self._cache.get(symbol.upper())

    def ready(self) -> bool:
        """آیا کش آماده است؟"""
        return len(self._cache) > 0

    def get_refresh_status(self) -> str:
        if self._refresh_in_progress:
            return "refreshing"
        if self._cache:
            return "ready"
        return "empty"

    def get_age_seconds(self) -> float:
        if self._last_update == 0:
            return float("inf")
        return time.time() - self._last_update

    # --- Non-blocking refresh ---

    def _ensure_fresh(self):
        needs_refresh = (
            self._last_update == 0
            or time.time() - self._last_update > self.ttl
        )
        if needs_refresh:
            self._start_background_refresh()

    def _start_background_refresh(self):
        with self._lock:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True

        thread = threading.Thread(
            target=self._background_refresh,
            daemon=True,
            name="PriceCacheRefresh",
        )
        thread.start()

    def _background_refresh(self):
        try:
            success = self._fetch_from_coingecko()
            if success:
                self._last_update = time.time()
                logger.info(
                    "PriceCache: refreshed %d prices from CoinGecko (background)",
                    len(self._cache),
                )
            else:
                success = self._fetch_from_db_fallback()
                if success:
                    self._last_update = time.time()
                    logger.info("PriceCache: fallback from DB (background)")
                else:
                    logger.warning("PriceCache: refresh failed (both sources)")
        except Exception as e:
            logger.error("PriceCache: background refresh error: %s", e, exc_info=True)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    def _fetch_from_coingecko(self) -> bool:
        """دریافت قیمت از CoinGecko API با استفاده از Key Pool."""
        try:
            ids = list(COINGECKO_ID_TO_SYMBOL.keys())
            if not ids:
                return False

            url = (
                "https://api.coingecko.com/api/v3/simple/price"
                f"?ids={','.join(ids)}"
                "&vs_currencies=usd"
                "&include_24hr_change=true"
                "&include_market_cap=true"
                "&include_24hr_vol=true"
            )

            headers = {"Accept": "application/json"}
            # استفاده از کلید CoinGecko از KeyPool (در صورت وجود)
            used_key = None
            if self._cg_pool:
                key_tuple = self._cg_pool.get_next_key()
                if key_tuple:
                    used_key, _ = key_tuple
                    headers["x-cg-demo-api-key"] = used_key

            logger.debug("PriceCache: fetching from CoinGecko (%d ids)", len(ids))
            resp = requests.get(url, headers=headers, timeout=15)

            # ثبت نتیجه برای KeyPool
            if self._cg_pool and used_key:
                if resp.status_code == 200:
                    self._cg_pool.mark_success(used_key)
                elif resp.status_code == 429:
                    self._cg_pool.mark_rate_limited(used_key, cooldown=60)
                elif resp.status_code == 403:
                    self._cg_pool.mark_exhausted(used_key)

            if resp.status_code != 200:
                logger.warning("PriceCache: CoinGecko returned %s", resp.status_code)
                return False

            data = resp.json()
            new_cache: Dict[str, Any] = {}

            for cg_id, cg_data in data.items():
                symbol = COINGECKO_ID_TO_SYMBOL.get(cg_id)
                if not symbol:
                    continue

                price = cg_data.get("usd")
                change_24h = cg_data.get("usd_24h_change")
                market_cap = cg_data.get("usd_market_cap")
                volume_24h = cg_data.get("usd_24h_vol")

                if price is not None:
                    new_cache[symbol] = {
                        "price": float(price),
                        "change_24h": float(change_24h) if change_24h is not None else None,
                        "market_cap": float(market_cap) if market_cap is not None else None,
                        "volume_24h": float(volume_24h) if volume_24h is not None else None,
                        "source": "coingecko",
                    }

            if new_cache:
                self._cache = new_cache
                return True
            return False

        except requests.RequestException as e:
            logger.warning("PriceCache: CoinGecko request failed: %s", e)
            return False
        except Exception as e:
            logger.error("PriceCache: CoinGecko parse error: %s", e, exc_info=True)
            return False

    def _fetch_from_db_fallback(self) -> bool:
        """Fallback: خواندن قیمت از current_prices دیتابیس."""
        try:
            from sqlalchemy import text
            from database import engine

            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT s.symbol, cp.price, cp.change_24h,
                               cp.market_cap, cp.volume_24h
                        FROM current_prices cp
                        JOIN symbols s ON cp.symbol_id = s.id
                    """)
                ).fetchall()

                new_cache: Dict[str, Any] = {}
                for row in rows:
                    symbol = row[0].upper() if row[0] else None
                    if not symbol:
                        continue
                    new_cache[symbol] = {
                        "price": float(row[1]) if row[1] else 0.0,
                        "change_24h": float(row[2]) if row[2] else None,
                        "market_cap": float(row[3]) if row[3] else None,
                        "volume_24h": float(row[4]) if row[4] else None,
                        "source": "db_fallback",
                    }

                if new_cache:
                    self._cache = new_cache
                    return True
                return False

        except Exception as e:
            logger.warning("PriceCache: DB fallback failed: %s", e)
            return False


# ===================== Singleton =====================

_price_cache_instance: Optional[PriceCache] = None


def get_price_cache() -> PriceCache:
    global _price_cache_instance
    if _price_cache_instance is None:
        _price_cache_instance = PriceCache()
    return _price_cache_instance


# ===================== Warmup on import =====================

def _warmup_price_cache():
    """Warmup with random stagger (0-60s) to prevent thundering herd across Gunicorn workers."""
    import random
    delay = random.uniform(0, 60)
    logger.info("PriceCache: warmup will start in %.1fs (stagger)", delay)
    time.sleep(delay)
    try:
        pc = get_price_cache()
        pc._start_background_refresh()
        logger.info("PriceCache: warmup initiated (background thread started)")
    except Exception as e:
        logger.warning("PriceCache: warmup failed: %s", e)


_warmup_prices = threading.Thread(
    target=_warmup_price_cache, daemon=True, name="PriceCacheWarmup"
)
_warmup_prices.start()
