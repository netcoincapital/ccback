"""
Cache Proxy — External API Provider Wrappers
==============================================
هر provider یک wrapper دور API خارجی است که:
- از KeyPool برای round-robin کلیدها استفاده می‌کند
- از CacheLayer برای کش کردن پاسخ‌ها استفاده می‌کند
- خطاها را به صورت یکپارچه مدیریت می‌کند (rate limit, timeout, circuit breaker)

Providers:
  - evm_explorer: Etherscan-family (Etherscan, BSCScan, PolygonScan, SnowTrace, Arbiscan)
  - evm_rpc:     EVM RPC Pool (dRPC → Ankr → Chainstack → Tenderly → Etox → BlockPI → PublicNode)
  - trongrid:    TronGrid API
  - solana:      Solana RPC (Helius → SolanaTracker → Public)
  - blockcypher: BlockCypher API (Bitcoin, Dogecoin, Dash, Litecoin)
  - blockstream: Blockstream API (Bitcoin public fallback — بدون key)
  - subscan:     Subscan API (Polkadot, Kusama)
"""

from .evm_explorer import EvmExplorerProxy, get_evm_explorer
from .evm_rpc import EvmRpcPool, get_evm_rpc_pool
from .trongrid import TronGridProxy, get_trongrid_proxy
from .solana import SolanaProxy, get_solana_proxy
from .blockcypher import BlockCypherProxy, get_blockcypher_proxy
from .blockstream import BlockstreamProxy, get_blockstream_proxy
from .subscan import SubscanProxy, get_subscan_proxy
from .tron_broadcast import TronBroadcastProvider, get_tron_broadcast_provider

__all__ = [
    "EvmExplorerProxy",
    "get_evm_explorer",
    "EvmRpcPool",
    "get_evm_rpc_pool",
    "TronGridProxy",
    "get_trongrid_proxy",
    "TronBroadcastProvider",
    "get_tron_broadcast_provider",
    "SolanaProxy",
    "get_solana_proxy",
    "BlockCypherProxy",
    "get_blockcypher_proxy",
    "BlockstreamProxy",
    "get_blockstream_proxy",
    "SubscanProxy",
    "get_subscan_proxy",
]
