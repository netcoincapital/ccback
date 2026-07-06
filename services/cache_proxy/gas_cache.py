"""
Gas Cache — Non-Custodial Gas Fee Proxy
=========================================

کارمزد شبکه‌های مختلف را از public RPC می‌گیرد و در RAM کش می‌کند.
هر ۱ دقیقه یکبار تازه می‌شود. بدون UserID.

⚡ Non-blocking: اولین بار در پس‌زمینه پر می‌شود، درخواست را مسدود نمی‌کند.
⚡ Warmup: به محض import ماژول، یک نخ پس‌زمینه شروع به پر کردن کش می‌کند.

شبکه‌های پشتیبانی شده:
- Ethereum (EIP-1559), BSC, Polygon, Avalanche C-Chain
- Arbitrum, Optimism, Tron, Solana
"""

import time
import threading
from typing import Dict, Optional, Any

import requests

from utils.logging_config import get_logger

logger = get_logger(__file__)


class GasCache:
    """
    کش کارمزد شبکه‌ها در RAM.
    از public RPC endpoints استفاده می‌کند.
    Non-blocking: اگر کش خالی باشد {} برمی‌گرداند و در پس‌زمینه رفرش می‌کند.
    """

    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds  # 1 دقیقه
        self._cache: Dict[str, Any] = {}
        self._last_update: float = 0.0
        self._lock = threading.Lock()
        self._refresh_in_progress = False

    def get_all_gas(self) -> Dict[str, Any]:
        """برگرداندن کارمزد همه شبکه‌ها. هیچوقت مسدود نمی‌کند."""
        self._ensure_fresh()
        return dict(self._cache)

    def get_gas(self, blockchain: str) -> Optional[Dict[str, Any]]:
        """کارمزد یک شبکه خاص. هیچوقت مسدود نمی‌کند."""
        self._ensure_fresh()
        blockchain_lower = blockchain.lower().replace("-", "").replace(" ", "")
        for key in self._cache:
            if key.lower().replace("-", "").replace(" ", "") == blockchain_lower:
                return self._cache[key]
            if self._cache[key].get("symbol", "").lower() == blockchain_lower:
                return self._cache[key]
        return None

    def ready(self) -> bool:
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
            name="GasCacheRefresh",
        )
        thread.start()

    def _background_refresh(self):
        try:
            result: Dict[str, Any] = {}

            # 1) Ethereum
            try:
                eth_gas = self._fetch_evm_gas_fees(
                    "https://eth.llamarpc.com", "Ethereum", "ETH"
                )
                if eth_gas:
                    result["Ethereum"] = eth_gas
            except Exception as e:
                logger.warning("GasCache: ETH fetch failed: %s", e)

            # 2) BSC
            try:
                bsc_gas = self._fetch_evm_gas_fees(
                    "https://bsc-dataseed.binance.org", "BSC", "BNB"
                )
                if bsc_gas:
                    result["BSC"] = bsc_gas
            except Exception as e:
                logger.warning("GasCache: BSC fetch failed: %s", e)

            # 3) Polygon
            try:
                poly_gas = self._fetch_evm_gas_fees(
                    "https://polygon-rpc.com", "Polygon", "MATIC"
                )
                if poly_gas:
                    result["Polygon"] = poly_gas
            except Exception as e:
                logger.warning("GasCache: Polygon fetch failed: %s", e)

            # 4) Avalanche
            try:
                avax_gas = self._fetch_evm_gas_fees(
                    "https://api.avax.network/ext/bc/C/rpc", "Avalanche", "AVAX"
                )
                if avax_gas:
                    result["Avalanche"] = avax_gas
            except Exception as e:
                logger.warning("GasCache: Avalanche fetch failed: %s", e)

            # 5) Arbitrum
            try:
                arb_gas = self._fetch_evm_gas_fees(
                    "https://arb1.arbitrum.io/rpc", "Arbitrum", "ETH"
                )
                if arb_gas:
                    result["Arbitrum"] = arb_gas
            except Exception as e:
                logger.warning("GasCache: Arbitrum fetch failed: %s", e)

            # 6) Optimism
            try:
                op_gas = self._fetch_evm_gas_fees(
                    "https://mainnet.optimism.io", "Optimism", "ETH"
                )
                if op_gas:
                    result["Optimism"] = op_gas
            except Exception as e:
                logger.warning("GasCache: Optimism fetch failed: %s", e)

            # 7) Tron
            try:
                tron_gas = self._fetch_tron_fees()
                if tron_gas:
                    result["Tron"] = tron_gas
            except Exception as e:
                logger.warning("GasCache: Tron fetch failed: %s", e)

            # 8) Solana
            try:
                sol_gas = self._fetch_solana_fees()
                if sol_gas:
                    result["Solana"] = sol_gas
            except Exception as e:
                logger.warning("GasCache: Solana fetch failed: %s", e)

            if result:
                self._cache = result
                self._last_update = time.time()
                logger.info("GasCache: refreshed %d chains (background)", len(result))
            else:
                logger.warning("GasCache: no gas data fetched")

        except Exception as e:
            logger.error("GasCache: background refresh error: %s", e, exc_info=True)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    # --- EVM-based chains ---

    def _fetch_evm_gas_fees(
        self, rpc_url: str, chain_name: str, symbol: str
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_gasPrice",
            "params": [],
            "id": 1,
        }
        resp = requests.post(rpc_url, json=payload, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        gas_price_wei = int(data.get("result", "0x0"), 16)
        gas_price_gwei = gas_price_wei / 1e9

        max_fee = gas_price_gwei
        try:
            fee_history = {
                "jsonrpc": "2.0",
                "method": "eth_feeHistory",
                "params": [1, "latest", [25, 50, 75]],
                "id": 2,
            }
            fh_resp = requests.post(rpc_url, json=fee_history, timeout=10)
            if fh_resp.status_code == 200:
                fh_data = fh_resp.json()
                base_fee_per_gas = int(
                    fh_data.get("result", {}).get("baseFeePerGas", ["0x0"])[0], 16
                ) / 1e9
                max_fee = base_fee_per_gas * 1.5
        except Exception:
            pass

        estimated_cost_usd = self._estimate_usd_cost(gas_price_gwei, symbol)

        return {
            "chain": chain_name,
            "symbol": symbol,
            "gas_price_gwei": round(gas_price_gwei, 2),
            "max_fee_gwei": round(max_fee, 2),
            "estimated_tx_cost_usd": round(estimated_cost_usd, 4),
            "currency": "USD",
            "unit": "Gwei",
        }

    def _estimate_usd_cost(self, gas_price_gwei: float, symbol: str) -> float:
        """تخمین هزینه تراکنش بر حسب USD با استفاده از قیمت کش شده."""
        try:
            from .price_cache import get_price_cache
            pc = get_price_cache()
            prices = pc.get_all_prices()
            token_price = None

            mapping = {"ETH": "ETH", "BNB": "BNB", "MATIC": "MATIC", "AVAX": "AVAX"}
            mapped = mapping.get(symbol)
            if mapped and prices.get(mapped):
                token_price = prices[mapped].get("price")

            if token_price:
                gas_limit = 21000
                eth_cost = (gas_price_gwei * gas_limit) / 1e9
                return eth_cost * token_price
        except Exception:
            pass
        return 0.0

    # --- Tron ---

    def _fetch_tron_fees(self) -> Optional[Dict[str, Any]]:
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_gasPrice",
                "params": [],
                "id": 1,
            }
            resp = requests.post(
                "https://api.trongrid.io/jsonrpc", json=payload, timeout=10
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            gas_price = int(data.get("result", "0x0"), 16) / 1e6

            return {
                "chain": "Tron",
                "symbol": "TRX",
                "gas_price_sun": int(gas_price * 1e6),
                "energy_fee_trx": 0.000042,
                "bandwidth_free": True,
                "estimated_tx_cost_trx": 0.0001,
                "note": "Tron uses Energy + Bandwidth model",
            }
        except Exception as e:
            logger.warning("GasCache: Tron error: %s", e)
            return None

    # --- Solana ---

    def _fetch_solana_fees(self) -> Optional[Dict[str, Any]]:
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "getRecentPerformanceSamples",
                "params": [1],
                "id": 1,
            }
            resp = requests.post(
                "https://api.mainnet-beta.solana.com", json=payload, timeout=10
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            samples = data.get("result", [])
            if not samples:
                return None

            sample = samples[0]
            num_transactions = sample.get("numTransactions", 0)
            sample_period = sample.get("samplePeriodSecs", 60)

            priority_fee_payload = {
                "jsonrpc": "2.0",
                "method": "getRecentPrioritizationFees",
                "params": [],
                "id": 2,
            }
            pf_resp = requests.post(
                "https://api.mainnet-beta.solana.com",
                json=priority_fee_payload,
                timeout=10,
            )

            avg_priority_fee = 0.000005
            if pf_resp.status_code == 200:
                pf_data = pf_resp.json()
                fees = pf_data.get("result", [])
                if fees:
                    valid_fees = [
                        f.get("prioritizationFee", 0) for f in fees
                        if f.get("prioritizationFee", 0) > 0
                    ]
                    if valid_fees:
                        avg_priority_fee = (sum(valid_fees) / len(valid_fees)) / 1e9

            tps = num_transactions / max(sample_period, 1)
            estimated_fee_sol = 0.000005 + avg_priority_fee

            return {
                "chain": "Solana",
                "symbol": "SOL",
                "tps": round(tps, 1),
                "estimated_fee_sol": round(estimated_fee_sol, 9),
                "avg_priority_fee_sol": round(avg_priority_fee, 9),
                "note": "Solana uses a base fee of 0.000005 SOL + priority fee",
            }
        except Exception as e:
            logger.warning("GasCache: Solana error: %s", e)
            return None


# Singleton
_gas_cache_instance: Optional[GasCache] = None


def get_gas_cache() -> GasCache:
    global _gas_cache_instance
    if _gas_cache_instance is None:
        _gas_cache_instance = GasCache()
    return _gas_cache_instance


# ===================== Warmup on import =====================

def _warmup_gas_cache():
    """Warmup with random stagger (0-60s) to prevent thundering herd across Gunicorn workers."""
    import random
    delay = random.uniform(0, 60)
    logger.info("GasCache: warmup will start in %.1fs (stagger)", delay)
    time.sleep(delay)
    try:
        gc = get_gas_cache()
        gc._start_background_refresh()
        logger.info("GasCache: warmup initiated (background thread started)")
    except Exception as e:
        logger.warning("GasCache: warmup failed: %s", e)


_warmup_gas = threading.Thread(
    target=_warmup_gas_cache, daemon=True, name="GasCacheWarmup"
)
_warmup_gas.start()
