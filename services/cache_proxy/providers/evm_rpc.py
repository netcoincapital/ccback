"""
EVM RPC Pool — Multi-Provider RPC Proxy
=========================================
بازسازی کامل EvmRpcPool فعلی Flutter در Python.

Fallback Chain (مطابق secrets/vm_api_keys.env):
  1. dRPC           (7 key, lb.drpc.live/{chain}/{KEY} + pub fallback)
  2. Ankr           (7 key, rpc.ankr.com/{chain}/{KEY} + pub fallback)
  3. Chainstack     (tokens per-chain از env)
  4. Tenderly       (3 accounts, per-chain URLs)
  5. Etox           (6 accounts, per-chain URLs)
  6. BlockPI        (per-chain URLs از env)
  7. PublicNode     (بدون key, last resort)

Timeout:    5s connect, 10s read
Circuit Breaker: اگر provider ۵ بار متوالی خطا داد → ۳۰ ثانیه skip

نحوه استفاده از کلیدها (مطابق secrets/vm_api_keys.env):
  dRPC:  DRPC_API_KEY_1..7 → https://lb.drpc.live/{chain}/{KEY}
  Ankr:  ANKR_API_KEY_1..7 → https://rpc.ankr.com/{chain}/{KEY}
"""

import time
import os
import threading
import json
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

import requests

from utils.logging_config import get_logger
from ..core.cache import CacheLayer, get_cache_layer
from ..core.key_pool import get_key_pool_manager, KeyPool
from ..core.errors import ProviderError, ProviderTimeoutError, CircuitBreakerOpenError

logger = get_logger(__file__)


# ============================================================
# Chain Names
# ============================================================

CHAIN_ID_MAP: Dict[str, str] = {
    "ethereum": "ethereum", "eth": "ethereum",
    "bsc": "bsc", "bnb": "bsc",
    "polygon": "polygon", "matic": "polygon",
    "avalanche": "avalanche", "avax": "avalanche",
    "arbitrum": "arbitrum", "arb": "arbitrum",
    "optimism": "optimism", "op": "optimism",
}

# dRPC chain names
DRPC_CHAIN_MAP: Dict[str, str] = {
    "ethereum": "ethereum", "bsc": "bsc",
    "polygon": "polygon", "avalanche": "avalanche",
    "arbitrum": "arbitrum", "optimism": "optimism",
}


# ============================================================
# Helper: بارگذاری متغیرهای env با دو فرمت
# ============================================================

def _load_str(env_var: str, default: str = "") -> str:
    """بارگذاری یک رشته از env."""
    return os.environ.get(env_var, default).strip()


# ============================================================
# Circuit Breaker
# ============================================================

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown: int = 30):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = threading.Lock()

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> bool:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning("CircuitBreaker: OPEN (cooldown=%ds)", self.cooldown)
                return True
            return False

    def allow_request(self) -> bool:
        with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time >= self.cooldown:
                    self.state = CircuitBreakerState.HALF_OPEN
                    return True
                return False
            return True


# ============================================================
# RPC Provider — یک منبع RPC
# ============================================================

@dataclass
class RpcProvider:
    """یک provider RPC."""
    name: str
    urls: Dict[str, str]          # chain → url
    priority: int                 # 1 = بالاترین
    timeout_connect: int = 5
    timeout_read: int = 10
    use_key_pool: bool = False    # آیا از KeyPool استفاده کند
    key_pool_name: str = ""       # نام KeyPool
    key_url_template: str = ""    # الگوی URL با {chain} و {key}


def _build_drpc_providers(pool: Optional[KeyPool]) -> List[RpcProvider]:
    """ساخت providerهای dRPC از کلیدهای موجود و public fallback."""
    providers = []

    if pool and pool.total_keys > 0:
        # یک provider برای هر کلید dRPC
        key_tuple = pool.get_next_key()
        if key_tuple:
            api_key, _ = key_tuple
            urls = {}
            for chain, drpc_chain in DRPC_CHAIN_MAP.items():
                urls[chain] = f"https://lb.drpc.live/{drpc_chain}/{api_key}"
            providers.append(RpcProvider(
                name="dRPC_1", urls=urls, priority=1,
            ))
            # بقیه کلیدها با اولویت کمی پایین‌تر
            for idx in range(2, pool.total_keys + 1):
                next_key = pool.get_next_key()
                if next_key:
                    k, _ = next_key
                    urls_k = {}
                    for chain, drpc_chain in DRPC_CHAIN_MAP.items():
                        urls_k[chain] = f"https://lb.drpc.live/{drpc_chain}/{k}"
                    providers.append(RpcProvider(
                        name=f"dRPC_{idx}", urls=urls_k, priority=1,
                    ))

    # Public dRPC endpoints (بدون key — fallback)
    public_urls = {}
    for chain, drpc_chain in DRPC_CHAIN_MAP.items():
        public_urls[chain] = f"https://{drpc_chain}.drpc.org"
    providers.append(RpcProvider(
        name="dRPC_public", urls=public_urls, priority=2,
    ))

    return providers


def _build_ankr_providers(pool: Optional[KeyPool]) -> List[RpcProvider]:
    """ساخت providerهای Ankr از کلیدها."""
    providers = []

    if pool and pool.total_keys > 0:
        for idx in range(1, pool.total_keys + 1):
            key_tuple = pool.get_next_key()
            if key_tuple:
                api_key, _ = key_tuple
                urls = {}
                for chain in CHAIN_ID_MAP:
                    urls[chain] = f"https://rpc.ankr.com/{chain}/{api_key}"
                providers.append(RpcProvider(
                    name=f"Ankr_{idx}", urls=urls, priority=3,
                ))

    # Public Ankr (بدون key)
    public_urls = {}
    for chain in CHAIN_ID_MAP:
        public_urls[chain] = f"https://rpc.ankr.com/{chain}"
    providers.append(RpcProvider(
        name="Ankr_public", urls=public_urls, priority=4,
    ))

    return providers


def _build_chainstack_providers() -> List[RpcProvider]:
    """ساخت provider Chainstack از env varهای CHAINSTACK_*_TOKEN."""
    chain_map = {
        "ethereum": ("CHAINSTACK_ETH_TOKEN", "https://ethereum.chainstacklabs.com/{token}"),
        "bsc":      ("CHAINSTACK_BSC_TOKEN", "https://bsc.chainstacklabs.com/{token}"),
        "polygon":  ("CHAINSTACK_POLYGON_TOKEN", None),  # if exists
        "arbitrum": ("CHAINSTACK_ARB_TOKEN", None),
        "bitcoin":  ("CHAINSTACK_BTC_TOKEN", "https://bitcoin.chainstacklabs.com/{token}"),
    }

    urls = {}
    has_any = False
    for chain, (env_var, template) in chain_map.items():
        token = _load_str(env_var)
        if token and template:
            urls[chain] = template.replace("{token}", token)
            has_any = True

    if has_any:
        return [RpcProvider(name="Chainstack", urls=urls, priority=5)]
    return []


def _build_tenderly_providers() -> List[RpcProvider]:
    """ساخت providerهای Tenderly از env varها (۳ حساب)."""
    providers = []
    tenderly_chain_vars = {
        "ethereum": "TENDERLY_ETH_RPC_URL",
        "polygon":  "TENDERLY_POLYGON_RPC_URL",
        "arbitrum": "TENDERLY_ARBITRUM_RPC_URL",
        "avalanche":"TENDERLY_AVALANCHE_RPC_URL",
    }

    for account_idx in range(1, 4):
        urls = {}
        has_any = False
        for chain, var_prefix in tenderly_chain_vars.items():
            url = _load_str(f"{var_prefix}_{account_idx}")
            if url:
                urls[chain] = url
                has_any = True
        if has_any:
            providers.append(RpcProvider(
                name=f"Tenderly_{account_idx}", urls=urls, priority=6,
            ))

    return providers


def _build_etox_providers() -> List[RpcProvider]:
    """ساخت providerهای Etox از env varها (۶ کلید)."""
    providers = []
    etox_chain_vars = {
        "ethereum": "ETOX_ETH_RPC_URL",
        "arbitrum": "ETOX_ARB_RPC_URL",
        "polygon":  "ETOX_POLYGON_RPC_URL",
    }

    for idx in range(1, 7):
        urls = {}
        has_any = False
        for chain, var_prefix in etox_chain_vars.items():
            url = _load_str(f"{var_prefix}_{idx}")
            if url:
                urls[chain] = url
                has_any = True
        if has_any:
            providers.append(RpcProvider(
                name=f"Etox_{idx}", urls=urls, priority=7,
            ))

    return providers


def _build_blockpi_providers() -> List[RpcProvider]:
    """ساخت provider BlockPI از env varهای BLOCKPI_*_RPC_URL."""
    blockpi_vars = {
        "ethereum": "BLOCKPI_ETH_RPC_URL",
        "polygon":  "BLOCKPI_POLYGON_RPC_URL",
        "arbitrum": "BLOCKPI_ARBITRUM_RPC_URL",
        "bsc":      "BLOCKPI_BSC_RPC_URL",
        "avalanche":"BLOCKPI_AVALANCHE_RPC_URL",
    }

    urls = {}
    has_any = False
    for chain, env_var in blockpi_vars.items():
        url = _load_str(env_var)
        if url:
            urls[chain] = url
            has_any = True

    if has_any:
        return [RpcProvider(name="BlockPI", urls=urls, priority=8)]
    return []


def _build_publicnode_providers() -> List[RpcProvider]:
    """PublicNode — آخرین راهکار."""
    urls = {
        "ethereum": "https://ethereum.publicnode.com",
        "bsc":      "https://bsc.publicnode.com",
        "polygon":  "https://polygon.publicnode.com",
        "avalanche":"https://avalanche.publicnode.com",
        "arbitrum": "https://arbitrum.publicnode.com",
        "optimism": "https://optimism.publicnode.com",
    }
    return [RpcProvider(name="PublicNode", urls=urls, priority=100)]


# ============================================================
# EVM RPC Pool — کلاس اصلی
# ============================================================

class EvmRpcPool:
    """
    EVM RPC Pool با round-robin واقعی + circuit breaker fallback.
    مطابق ساختار secrets/vm_api_keys.env.
    Thread-safe.

    استراتژی:
      - round-robin بین همه providerها (dRPC, Ankr, Tenderly, ...)
      - هر بار call() از یک provider متفاوت شروع می‌کند
      - circuit breaker: ۵ خطا → ۳۰ ثانیه skip
      - PublicNode آخرین راهکار (بدون key)
    """

    READ_METHODS = {
        "eth_blockNumber", "eth_getBalance", "eth_getTransactionCount",
        "eth_call", "eth_getBlockByNumber", "eth_getTransactionReceipt",
        "eth_gasPrice", "eth_feeHistory", "eth_chainId",
        "eth_getLogs", "eth_estimateGas",
    }

    def __init__(self, cache: CacheLayer = None):
        self.cache = cache or get_cache_layer()
        self._pool_manager = get_key_pool_manager()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self._provider_index = 0  # round-robin: هر بار call یک ایندکس متفاوت

        # ساختن providerها از env vars
        self._providers: List[RpcProvider] = []
        self._build_providers()

    def _build_providers(self):
        """ساخت همه providerها از env varها (مطابق vm_api_keys.env)."""
        drpc_pool = self._pool_manager.get_pool("drpc")
        ankr_pool = self._pool_manager.get_pool("ankr")

        self._providers = (
            _build_drpc_providers(drpc_pool)
            + _build_ankr_providers(ankr_pool)
            + _build_chainstack_providers()
            + _build_tenderly_providers()
            + _build_etox_providers()
            + _build_blockpi_providers()
            + _build_publicnode_providers()
        )

        logger.info("EvmRpcPool: built %d providers from env config", len(self._providers))

    def _normalize_chain(self, chain: str) -> Optional[str]:
        chain_lower = chain.lower().replace("-", "").replace(" ", "")
        return CHAIN_ID_MAP.get(chain_lower)

    def _get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        with self._lock:
            if provider_name not in self._circuit_breakers:
                self._circuit_breakers[provider_name] = CircuitBreaker()
            return self._circuit_breakers[provider_name]

    def call(
        self, chain: str, method: str, params: Optional[List[Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Any]:
        """
        فراخوانی یک متد RPC.

        Args:
            chain: نام بلاکچین
            method: متد JSON-RPC
            params: پارامترها
            use_cache: آیا از کش استفاده کند (فقط read methods)

        Returns:
            result یا None
        """
        chain_key = self._normalize_chain(chain)
        if not chain_key:
            logger.warning("EvmRpcPool: unsupported chain %s", chain)
            return None

        params = params or []
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000) % 100000,
        }

        # کش برای read methods
        if use_cache and method in self.READ_METHODS:
            cache_key = f"{method}_{json.dumps(params, sort_keys=True, default=str)}"
            cached = self.cache.get(f"rpc_{chain_key}", cache_key)
            if cached is not None:
                return cached.get("result")

        last_error = None
        total = len(self._providers)
        if total == 0:
            logger.warning("EvmRpcPool: no providers configured for %s/%s", chain, method)
            return None

        # شروع از یک ایندکس چرخشی — round-robin واقعی
        with self._lock:
            start_index = self._provider_index
            self._provider_index = (self._provider_index + 1) % total

        for i in range(total):
            provider = self._providers[(start_index + i) % total]

            # بررسی دسترسی provider به این chain
            url = provider.urls.get(chain_key)
            if not url:
                continue

            cb = self._get_circuit_breaker(provider.name)
            if not cb.allow_request():
                logger.debug("EvmRpcPool: circuit breaker open for %s", provider.name)
                continue

            try:
                resp = requests.post(
                    url, json=payload,
                    timeout=(provider.timeout_connect, provider.timeout_read),
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        cb.record_failure()
                        last_error = data["error"]
                        logger.debug("EvmRpcPool: %s RPC error: %s", provider.name, data["error"])
                        continue

                    cb.record_success()

                    # ذخیره در کش (فقط read methods)
                    if use_cache and method in self.READ_METHODS:
                        self.cache.set(f"rpc_{chain_key}", cache_key, data, ttl=10)

                    return data.get("result")

                else:
                    cb.record_failure()
                    last_error = f"HTTP {resp.status_code}"
                    logger.debug("EvmRpcPool: %s returned %d", provider.name, resp.status_code)

            except requests.Timeout:
                cb.record_failure()
                last_error = "timeout"
            except requests.ConnectionError as e:
                cb.record_failure()
                last_error = f"connection: {e}"
            except Exception as e:
                cb.record_failure()
                last_error = str(e)

        logger.warning("EvmRpcPool: all providers failed for %s/%s: %s",
                       chain, method, last_error)
        return None

    def broadcast_transaction(self, chain: str, signed_tx: str) -> Optional[str]:
        """
        Broadcast یک تراکنش امضا شده.
        هیچوقت signedTx را لاگ/ذخیره نمی‌کند.

        Args:
            chain: نام بلاکچین
            signed_tx: signed raw transaction hex

        Returns:
            tx hash یا None
        """
        result = self.call(chain, "eth_sendRawTransaction", [signed_tx], use_cache=False)
        if result:
            logger.info("EvmRpcPool: broadcast successful: %s...", str(result)[:16])
        return result

    def get_balance(self, chain: str, address: str) -> Optional[int]:
        result = self.call(chain, "eth_getBalance", [address, "latest"])
        if result:
            return int(result, 16)
        return None

    def get_transaction_count(self, chain: str, address: str) -> Optional[int]:
        result = self.call(chain, "eth_getTransactionCount", [address, "latest"])
        if result:
            return int(result, 16)
        return None

    def call_contract(self, chain: str, to: str, data: str) -> Optional[str]:
        call_data = {"to": to, "data": data}
        return self.call(chain, "eth_call", [call_data, "latest"])

    def estimate_gas(self, chain: str, tx_data: Dict[str, Any]) -> Optional[int]:
        result = self.call(chain, "eth_estimateGas", [tx_data], use_cache=False)
        if result:
            return int(result, 16)
        return None

    def get_gas_price(self, chain: str) -> Optional[int]:
        result = self.call(chain, "eth_gasPrice", [])
        if result:
            return int(result, 16)
        return None

    def get_block_number(self, chain: str) -> Optional[int]:
        result = self.call(chain, "eth_blockNumber", [])
        if result:
            return int(result, 16)
        return None

    def get_block_by_number(self, chain: str, block_number: int, full_tx: bool = True) -> Optional[Dict]:
        return self.call(chain, "eth_getBlockByNumber", [hex(block_number), full_tx])

    def get_transaction_receipt(self, chain: str, tx_hash: str) -> Optional[Dict]:
        return self.call(chain, "eth_getTransactionReceipt", [tx_hash])


# ===================== Singleton =====================

_evm_rpc_pool_instance: Optional[EvmRpcPool] = None


def get_evm_rpc_pool() -> EvmRpcPool:
    global _evm_rpc_pool_instance
    if _evm_rpc_pool_instance is None:
        _evm_rpc_pool_instance = EvmRpcPool()
    return _evm_rpc_pool_instance
