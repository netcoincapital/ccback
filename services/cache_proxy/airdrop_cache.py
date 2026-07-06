"""
Airdrop Cache — Cryptorank Airdrop Proxy
=========================================

لیست airdropها را از CryptoRank API می‌گیرد و در RAM کش می‌کند.

Cryptorank Endpoints:
- /v3/drophunting/map    — Basic list of all airdrop activities
- /v3/drophunting/list   — Detailed list of all airdrop activities
- /v3/drophunting/{id}   — Details for a specific airdrop
- /v3/drophunting/{id}/tasks — Tasks for a specific airdrop

⚡ Non-blocking: اولین بار در پس‌زمینه پر می‌شود
⚡ Cache: لیست هر ۵ دقیقه، جزئیات هر ۱۰ دقیقه
"""

import os
import time
import threading
from typing import Dict, Optional, Any, List

import requests

from utils.logging_config import get_logger

logger = get_logger(__file__)

CRYPTORANK_BASE_URL = "https://api.cryptorank.io/v3"
CRYPTORANK_API_KEY = os.getenv("CRYPTORANK_API_KEY", "")

# TTL مقادیر
LIST_TTL = 300      # 5 دقیقه برای لیست
DETAIL_TTL = 600    # 10 دقیقه برای جزئیات


class AirdropCache:
    """
    لیست airdropها را از CryptoRank می‌گیرد و در RAM کش می‌کند.
    Thread-safe. Non-blocking.
    """

    def __init__(self, list_ttl: int = LIST_TTL, detail_ttl: int = DETAIL_TTL):
        self.list_ttl = list_ttl
        self.detail_ttl = detail_ttl
        self._list_cache: List[Dict[str, Any]] = []
        self._detail_cache: Dict[str, Dict[str, Any]] = {}  # id → data
        self._list_last_update: float = 0.0
        self._detail_last_update: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._refresh_in_progress = False

        if not CRYPTORANK_API_KEY:
            logger.warning("AirdropCache: CRYPTORANK_API_KEY not set in .env")

    # --- دسترسی عمومی ---

    def get_all_airdrops(self) -> List[Dict[str, Any]]:
        """
        برگرداندن لیست همه airdropها.
        هیچوقت مسدود نمی‌کند — اگر کش خالی باشد [] برمی‌گرداند و در پس‌زمینه رفرش می‌کند.
        """
        self._ensure_list_fresh()
        return list(self._list_cache)

    def get_airdrop_detail(self, airdrop_id: str) -> Optional[Dict[str, Any]]:
        """
        دریافت جزئیات یک airdrop خاص.
        اگر در کش موجود نباشد و زمان اجازه دهد، در پس‌زمینه رفرش می‌کند.
        """
        # اول از کش برمی‌گردانیم
        self._ensure_detail_fresh(airdrop_id)
        return self._detail_cache.get(airdrop_id)

    def ready(self) -> bool:
        """آیا کش آماده است؟"""
        return len(self._list_cache) > 0

    def get_refresh_status(self) -> str:
        if self._refresh_in_progress:
            return "refreshing"
        if self._list_cache:
            return "ready"
        return "empty"

    def get_list_age_seconds(self) -> float:
        if self._list_last_update == 0:
            return float("inf")
        return time.time() - self._list_last_update

    def get_count(self) -> int:
        return len(self._list_cache)

    # --- Non-blocking refresh (لیست) ---

    def _ensure_list_fresh(self):
        needs_refresh = (
            self._list_last_update == 0
            or time.time() - self._list_last_update > self.list_ttl
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
            name="AirdropCacheRefresh",
        )
        thread.start()

    def _background_refresh(self):
        try:
            success = self._fetch_airdrop_list()
            if success:
                self._list_last_update = time.time()
                logger.info(
                    "AirdropCache: refreshed %d airdrops from CryptoRank",
                    len(self._list_cache),
                )
            else:
                logger.warning("AirdropCache: list refresh failed")
        except Exception as e:
            logger.error("AirdropCache: background refresh error: %s", e, exc_info=True)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    # --- Non-blocking refresh (جزئیات) ---

    def _ensure_detail_fresh(self, airdrop_id: str):
        now = time.time()
        last_update = self._detail_last_update.get(airdrop_id, 0)
        needs_refresh = (
            airdrop_id not in self._detail_cache
            or now - last_update > self.detail_ttl
        )
        if needs_refresh:
            self._start_detail_refresh(airdrop_id)

    def _start_detail_refresh(self, airdrop_id: str):
        thread = threading.Thread(
            target=self._background_detail_refresh,
            args=(airdrop_id,),
            daemon=True,
            name=f"AirdropDetail-{airdrop_id[:8]}",
        )
        thread.start()

    def _background_detail_refresh(self, airdrop_id: str):
        try:
            data = self._fetch_airdrop_detail(airdrop_id)
            if data:
                with self._lock:
                    self._detail_cache[airdrop_id] = data
                    self._detail_last_update[airdrop_id] = time.time()
                logger.info("AirdropCache: detail refreshed for %s", airdrop_id)
        except Exception as e:
            logger.error(
                "AirdropCache: detail refresh error for %s: %s",
                airdrop_id, e, exc_info=True,
            )

    # --- CryptoRank API calls ---

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "X-Api-Key": CRYPTORANK_API_KEY,
        }

    def _fetch_airdrop_list(self) -> bool:
        """
        دریافت لیست airdropها از /v3/drophunting/map.
        بازگشت True در صورت موفقیت.
        """
        try:
            url = f"{CRYPTORANK_BASE_URL}/drophunting/map"
            headers = self._get_headers()

            logger.debug("AirdropCache: fetching list from CryptoRank (map)")
            resp = requests.get(url, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "AirdropCache: CryptoRank returned %s for list",
                    resp.status_code,
                )
                return False

            data = resp.json()

            # CryptoRank معمولاً داده را در keyهای مختلف برمی‌گرداند
            # سعی می‌کنیم داده را از ساختار response استخراج کنیم
            airdrops = self._extract_list_data(data)

            if airdrops is not None and len(airdrops) > 0:
                with self._lock:
                    self._list_cache = airdrops
                return True

            logger.warning("AirdropCache: no airdrops found in response")
            return False

        except requests.RequestException as e:
            logger.warning("AirdropCache: CryptoRank request failed: %s", e)
            return False
        except Exception as e:
            logger.error("AirdropCache: CryptoRank parse error: %s", e, exc_info=True)
            return False

    def _fetch_airdrop_detail(self, airdrop_id: str) -> Optional[Dict[str, Any]]:
        """
        دریافت جزئیات یک airdrop خاص از /v3/drophunting/{id}.
        """
        try:
            url = f"{CRYPTORANK_BASE_URL}/drophunting/{airdrop_id}"
            headers = self._get_headers()

            logger.debug("AirdropCache: fetching detail for %s", airdrop_id)
            resp = requests.get(url, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "AirdropCache: CryptoRank returned %s for detail %s",
                    resp.status_code, airdrop_id,
                )
                return None

            data = resp.json()
            return self._extract_detail_data(data)

        except requests.RequestException as e:
            logger.warning(
                "AirdropCache: CryptoRank detail request failed for %s: %s",
                airdrop_id, e,
            )
            return None
        except Exception as e:
            logger.error(
                "AirdropCache: detail parse error for %s: %s",
                airdrop_id, e, exc_info=True,
            )
            return None

    def fetch_airdrop_tasks(self, airdrop_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        دریافت tasks یک airdrop خاص از /v3/drophunting/{id}/tasks.
        این متد عمومی است چون ممکن است همیشه کش نشود.
        """
        try:
            url = f"{CRYPTORANK_BASE_URL}/drophunting/{airdrop_id}/tasks"
            headers = self._get_headers()

            logger.debug("AirdropCache: fetching tasks for %s", airdrop_id)
            resp = requests.get(url, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "AirdropCache: CryptoRank returned %s for tasks %s",
                    resp.status_code, airdrop_id,
                )
                return None

            data = resp.json()
            return self._extract_tasks_data(data)

        except requests.RequestException as e:
            logger.warning(
                "AirdropCache: tasks request failed for %s: %s",
                airdrop_id, e,
            )
            return None
        except Exception as e:
            logger.error(
                "AirdropCache: tasks parse error for %s: %s",
                airdrop_id, e, exc_info=True,
            )
            return None

    # --- Response parsers (انعطاف‌پذیر برای ساختارهای مختلف پاسخ) ---

    def _extract_list_data(self, data: Any) -> Optional[List[Dict[str, Any]]]:
        """
        استخراج لیست airdropها از ساختار پاسخ CryptoRank.
        CryptoRank ممکن است داده را در keyهای مختلف برگرداند:
        - data
        - results
        - items
        - یا مستقیماً یک آرایه
        """
        if data is None:
            return None

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("data", "results", "items", "list", "records", "activities"):
                if key in data and isinstance(data[key], list):
                    return data[key]

            # اگر هیچکدام نبود، کلید اولی که آرایه است را برگردان
            for value in data.values():
                if isinstance(value, list):
                    return value

        return None

    def _extract_detail_data(self, data: Any) -> Optional[Dict[str, Any]]:
        """
        استخراج جزئیات یک airdrop.
        """
        if data is None:
            return None

        if isinstance(data, dict):
            for key in ("data", "result", "item", "activity"):
                if key in data and isinstance(data[key], dict):
                    return data[key]
            return data  # خود dict را برگردان

        return None

    def _extract_tasks_data(self, data: Any) -> Optional[List[Dict[str, Any]]]:
        """
        استخراج tasks از پاسخ CryptoRank.
        """
        if data is None:
            return None

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("data", "results", "items", "tasks", "list"):
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return val
                    if isinstance(val, dict):
                        return [val]
            return []

        return None


# ===================== Singleton =====================

_airdrop_cache_instance: Optional[AirdropCache] = None


def get_airdrop_cache() -> AirdropCache:
    global _airdrop_cache_instance
    if _airdrop_cache_instance is None:
        _airdrop_cache_instance = AirdropCache()
    return _airdrop_cache_instance


# ===================== Warmup on import =====================

def _warmup_airdrop_cache():
    """Warmup with random stagger (0-30s) to prevent thundering herd."""
    import random
    delay = random.uniform(0, 30)
    logger.info("AirdropCache: warmup will start in %.1fs (stagger)", delay)
    time.sleep(delay)
    try:
        ac = get_airdrop_cache()
        ac._start_background_refresh()
        logger.info("AirdropCache: warmup initiated (background thread started)")
    except Exception as e:
        logger.warning("AirdropCache: warmup failed: %s", e)


_warmup_thread = threading.Thread(
    target=_warmup_airdrop_cache, daemon=True, name="AirdropCacheWarmup"
)
_warmup_thread.start()
