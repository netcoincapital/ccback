"""
Key Pool Manager — Round-Robin API Key Rotation
================================================
مدیریت هوشمند round-robin بین چند API key با Health Tracking.

**مهم:** این ماژول کلیدها را از متغیرهای محیطی با دو فرمت می‌خواند:
  1. فرمت `secrets/vm_api_keys.env`: `ETHERSCAN_API_KEY_1`, `ETHERSCAN_API_KEY_2`, ...
  2. فرمت قدیمی `.env`: `ETHERSCAN_API_KEY=key1,key2,key3,...`

هر key یک status دارد:
  - active:         در حال استفاده عادی
  - rate_limited:   محدودیت موقت (تا ۶۰ ثانیه)
  - exhausted:      سهمیه روزانه تمام شده
  - error:          خطای غیرمنتظره
"""

import time
import os
import re
import threading
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field

from utils.logging_config import get_logger

logger = get_logger(__file__)


# ============================================================
# Utility: بارگذاری کلیدها با دو فرمت
# ============================================================

def _load_keys(env_prefix: str) -> List[str]:
    """
    بارگذاری کلیدها از متغیر محیطی با دو فرمت ممکن:

    اولویت ۱ (فرمت `secrets/vm_api_keys.env`):
      ETHERSCAN_API_KEY_1=key1
      ETHERSCAN_API_KEY_2=key2
      ...

    اولویت ۲ (فرمت `.env` قدیمی):
      ETHERSCAN_API_KEY=key1,key2,key3,...

    Args:
        env_prefix: پیشوند متغیر محیطی (مثلاً "ETHERSCAN_API_KEY")

    Returns:
        لیست کلیدها (خالی اگر هیچ کلیدی پیدا نشد)
    """
    keys: Set[str] = set()

    # اولویت ۱: جستجوی _1, _2, _3, ...
    index = 1
    found_numbered = False
    while True:
        env_var = f"{env_prefix}_{index}"
        value = os.environ.get(env_var, "").strip()
        if value:
            keys.add(value)
            found_numbered = True
            index += 1
        else:
            break

    if found_numbered:
        return list(keys)

    # اولویت ۲: فرمت comma-separated
    combined = os.environ.get(env_prefix, "").strip()
    if combined:
        for k in combined.split(","):
            k = k.strip()
            if k:
                keys.add(k)
        return list(keys)

    return []


class KeyStatus(Enum):
    """وضعیت یک کلید API."""
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    ERROR = "error"


@dataclass
class ApiKey:
    """یک کلید API با metadata."""
    key: str
    pool: str
    status: KeyStatus = KeyStatus.ACTIVE
    last_used: float = 0.0
    error_count: int = 0
    cooldown_until: float = 0.0
    daily_usage_count: int = 0
    max_daily_usage: int = 100000

    def is_available(self) -> bool:
        if self.status == KeyStatus.ACTIVE:
            return True
        if self.status == KeyStatus.RATE_LIMITED:
            return time.time() > self.cooldown_until
        return False

    def mark_rate_limited(self, cooldown: int = 60):
        self.status = KeyStatus.RATE_LIMITED
        self.cooldown_until = time.time() + cooldown
        self.error_count += 1
        logger.debug("Key %s... in pool '%s': rate limited for %ds",
                     self.key[:8], self.pool, cooldown)

    def mark_exhausted(self):
        self.status = KeyStatus.EXHAUSTED
        logger.warning("Key %s... in pool '%s': daily quota exhausted",
                       self.key[:8], self.pool)

    def mark_error(self):
        self.error_count += 1
        if self.error_count >= 5:
            self.status = KeyStatus.ERROR
            self.cooldown_until = time.time() + 120
            logger.warning("Key %s... in pool '%s': too many errors, cooling down",
                           self.key[:8], self.pool)

    def mark_success(self):
        self.status = KeyStatus.ACTIVE
        self.error_count = 0
        self.cooldown_until = 0.0


class KeyPool:
    """
    مدیریت round-robin بین چند API key.
    Thread-safe.
    """

    def __init__(self, name: str, keys: List[str], max_daily: int = 100000):
        self.name = name
        self._keys: List[ApiKey] = [
            ApiKey(key=k, pool=name, max_daily_usage=max_daily)
            for k in keys if k.strip()
        ]
        self._index = 0
        self._lock = threading.Lock()
        logger.info("KeyPool '%s': initialized with %d keys", name, len(self._keys))

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def available_keys(self) -> int:
        return sum(1 for k in self._keys if k.is_available())

    def get_next_key(self) -> Optional[Tuple[str, ApiKey]]:
        with self._lock:
            if not self._keys:
                return None
            for _ in range(len(self._keys)):
                key_obj = self._keys[self._index]
                self._index = (self._index + 1) % len(self._keys)
                if key_obj.is_available():
                    key_obj.last_used = time.time()
                    return (key_obj.key, key_obj)
            stats = self._get_stats()
            logger.warning("KeyPool '%s': no keys available. Stats: %s", self.name, stats)
            return None

    def mark_success(self, key_str: str):
        with self._lock:
            for k in self._keys:
                if k.key == key_str:
                    k.mark_success()
                    return

    def mark_rate_limited(self, key_str: str, cooldown: int = 60):
        with self._lock:
            for k in self._keys:
                if k.key == key_str:
                    k.mark_rate_limited(cooldown)
                    return

    def mark_exhausted(self, key_str: str):
        with self._lock:
            for k in self._keys:
                if k.key == key_str:
                    k.mark_exhausted()
                    return

    def mark_error(self, key_str: str):
        with self._lock:
            for k in self._keys:
                if k.key == key_str:
                    k.mark_error()
                    return

    def reset_all(self):
        with self._lock:
            for k in self._keys:
                k.status = KeyStatus.ACTIVE
                k.error_count = 0
                k.cooldown_until = 0.0
                k.daily_usage_count = 0
            logger.info("KeyPool '%s': all keys reset", self.name)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            statuses = {}
            for k in self._keys:
                statuses[f"{k.key[:16]}..."] = {
                    "status": k.status.value,
                    "error_count": k.error_count,
                    "cooldown_remaining": max(0, k.cooldown_until - time.time()),
                }
            return {
                "pool": self.name,
                "total": len(self._keys),
                "available": self.available_keys,
                "keys": statuses,
            }

    def _get_stats(self) -> Dict[str, int]:
        counts = {"active": 0, "rate_limited": 0, "exhausted": 0, "error": 0}
        for k in self._keys:
            if k.status == KeyStatus.ACTIVE:
                counts["active"] += 1
            elif k.status == KeyStatus.RATE_LIMITED:
                counts["rate_limited"] += 1
            elif k.status == KeyStatus.EXHAUSTED:
                counts["exhausted"] += 1
            elif k.status == KeyStatus.ERROR:
                counts["error"] += 1
        return counts


# ============================================================
# Key Pool Manager — مطابق ساختار secrets/vm_api_keys.env
# ============================================================

class KeyPoolManager:
    """
    مدیریت متمرکز همه KeyPoolها.
    کلیدها را با دو فرمت از محیط می‌خواند:
      - فرمت `secrets/vm_api_keys.env`: ETHERSCAN_API_KEY_1, ETHERSCAN_API_KEY_2, ...
      - فرمت `.env` قدیمی: ETHERSCAN_API_KEY=key1,key2,key3,...
    """

    POOL_CONFIGS: Dict[str, Dict[str, Any]] = {
        # ---- Explorer APIs (تاریخچه تراکنش) ----
        "etherscan": {
            "env_prefix": "ETHERSCAN_API_KEY",
            "max_daily": 100000,
            "description": "Etherscan — ۵ کلید",
        },
        "bscscan": {
            "env_prefix": "BSCSCAN_API_KEY",
            "max_daily": 100000,
            "description": "BSCScan — ۴ کلید",
        },
        "polygonscan": {
            "env_prefix": "POLYGONSCAN_API_KEY",
            "max_daily": 100000,
            "description": "PolygonScan — ۳ کلید",
        },
        "avalanche_explorer": {
            "env_prefix": "AVALANCHE_API_KEY",
            "max_daily": 100000,
            "description": "SnowTrace — ۳ کلید",
        },
        "arbiscan": {
            "env_prefix": "ARBITRUMSCAN_API_KEY",
            "max_daily": 100000,
            "description": "Arbiscan — ۳ کلید",
        },

        # ---- Tron ----
        "trongrid": {
            "env_prefix": "TRONGRID_API_KEY",
            "max_daily": 100000,
            "description": "TronGrid — ۱۲ کلید",
        },

        # ---- RPC Providers ----
        "drpc": {
            "env_prefix": "DRPC_API_KEY",
            "max_daily": 100000,
            "description": "dRPC — ۷ کلید (lb.drpc.live/{chain}/{key})",
        },
        "ankr": {
            "env_prefix": "ANKR_API_KEY",
            "max_daily": 100000,
            "description": "Ankr — ۷ کلید (rpc.ankr.com/{chain}/{key})",
        },

        # ---- Solana ----
        "helius": {
            "env_prefix": "HELIUS_API_KEY",
            "max_daily": 100000,
            "description": "Helius/Solana — ۹ کلید",
        },

        # ---- Bitcoin & UTXO ----
        "blockcypher": {
            "env_prefix": "BLOCKCYPHER_API_KEY",
            "max_daily": 5000,
            "description": "BlockCypher (BTC/DOGE/DASH/LTC) — ۶ کلید",
        },

        # ---- Polkadot / Kusama ----
        "subscan": {
            "env_prefix": "SUBSCAN_API_KEY",
            "max_daily": 10000,
            "description": "Subscan (Polkadot/Kusama) — ۷ کلید",
        },

        # ---- قیمت‌ها ----
        "coingecko": {
            "env_prefix": "COINGECKO_API_KEY",
            "max_daily": 10000,
            "description": "CoinGecko — ۶ کلید (اختیاری)",
        },
    }

    def __init__(self):
        self._pools: Dict[str, KeyPool] = {}
        self._lock = threading.Lock()
        self._load_pools()

    def _load_pools(self):
        """بارگذاری همه KeyPoolها با دو فرمت از متغیرهای محیطی."""
        for pool_name, config in self.POOL_CONFIGS.items():
            keys = _load_keys(config["env_prefix"])
            if keys:
                pool = KeyPool(pool_name, keys, max_daily=config["max_daily"])
                self._pools[pool_name] = pool
                logger.info("KeyPoolManager: loaded %d keys for '%s' (%s)",
                            len(keys), pool_name, config["description"])
            else:
                logger.info("KeyPoolManager: no keys for '%s' (env: %s_1,2,3...)",
                            pool_name, config["env_prefix"])

        logger.info("KeyPoolManager: initialized %d pools", len(self._pools))

    def get_pool(self, name: str) -> Optional[KeyPool]:
        return self._pools.get(name)

    def get_or_create_pool(self, name: str, keys: List[str]) -> KeyPool:
        with self._lock:
            if name not in self._pools:
                self._pools[name] = KeyPool(name, keys)
            return self._pools[name]

    def get_status_all(self) -> Dict[str, Any]:
        return {
            name: pool.get_status()
            for name, pool in self._pools.items()
        }

    @property
    def total_pools(self) -> int:
        return len(self._pools)

    def reload(self) -> Dict[str, Any]:
        """
        بارگذاری مجدد همه KeyPoolها از متغیرهای محیطی.
        کلیدهای موجود در فایل env را دوباره می‌خواند و poolها را جایگزین می‌کند.
        بدون نیاز به ری‌استارت سرویس.

        Returns:
            dict: گزارش تعداد کلیدهای بارگذاری شده به ازای هر pool
        """
        with self._lock:
            old_pools = self._pools
            self._pools = {}
            self._load_pools()
            report = {
                name: len(pool._keys)
                for name, pool in self._pools.items()
            }
            logger.info("KeyPoolManager: reloaded %d pools — %s",
                        len(self._pools), report)
            return report


# ===================== Singleton =====================

_key_pool_manager_instance: Optional[KeyPoolManager] = None


def get_key_pool_manager() -> KeyPoolManager:
    global _key_pool_manager_instance
    if _key_pool_manager_instance is None:
        _key_pool_manager_instance = KeyPoolManager()
    return _key_pool_manager_instance
