from web3 import Web3
import logging
from utils.logging_config import get_logger

logger = get_logger(__file__)

class Web3Manager:
    # List of Infura API keys
    INFURA_API_KEYS = [
        "445d27fca1f44ba1962415baa6b98c7e",
        "2c95896c1065483d9a2d0c3b3c647e20",
        "d03b0c5c95024c99a25b67ac755b3b3f",
        "e6f9f4a7c4c24f1a9b2d0c3b3c647e20"
    ]
    
    # Public RPC endpoints as fallback
    PUBLIC_RPC_ENDPOINTS = {
        "Ethereum": [
            "https://eth.llamarpc.com",
            "https://ethereum.publicnode.com",
            "https://1rpc.io/eth"
        ],
        "Polygon": [
            "https://polygon-rpc.com",
            "https://rpc-mainnet.matic.network",
            "https://matic-mainnet.chainstacklabs.com"
        ],
        "Arbitrum": [
            "https://arb1.arbitrum.io/rpc",
            "https://arbitrum.llamarpc.com"
        ],
        "Avalanche": [
            "https://api.avax.network/ext/bc/C/rpc",
            "https://avalanche.public-rpc.com"
        ],
        "Binance": [
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io"
        ]
    }

    @classmethod
    def get_web3_providers(cls):
        """Get Web3 providers for all supported chains"""
        web3_providers = {}
        
        # Try Infura first for supported chains
        for chain in ["Ethereum", "Polygon", "Arbitrum"]:
            provider_set = False
            
            # Try each Infura API key
            for api_key in cls.INFURA_API_KEYS:
                try:
                    if chain == "Ethereum":
                        provider_url = f"https://mainnet.infura.io/v3/{api_key}"
                    elif chain == "Polygon":
                        provider_url = f"https://polygon-mainnet.infura.io/v3/{api_key}"
                    elif chain == "Arbitrum":
                        provider_url = f"https://arbitrum-mainnet.infura.io/v3/{api_key}"
                        
                    w3 = Web3(Web3.HTTPProvider(provider_url))
                    # Test the connection
                    w3.eth.block_number
                    web3_providers[chain] = w3
                    provider_set = True
                    logger.info(f"Successfully connected to {chain} using Infura")
                    break
                except Exception as e:
                    logger.warning(f"Failed to connect to {chain} using Infura key {api_key}: {str(e)}")
                    continue
            
            # If all Infura keys failed, try public RPCs
            if not provider_set and chain in cls.PUBLIC_RPC_ENDPOINTS:
                cls._try_public_rpcs(chain, web3_providers)

        # For non-Infura chains, use public RPCs directly
        for chain in ["Avalanche", "Binance"]:
            if chain not in web3_providers and chain in cls.PUBLIC_RPC_ENDPOINTS:
                cls._try_public_rpcs(chain, web3_providers)

        # Add non-EVM chains
        web3_providers.update({
            "Tron": None,
            "Solana": None,
            "Polkadot": None,
            "XRP": None,
            "Bitcoin": None
        })
        
        connected_chains = [chain for chain, provider in web3_providers.items() if provider is not None]
        logger.info(f"Successfully initialized Web3 providers for chains: {', '.join(connected_chains)}")
        
        return web3_providers

    @classmethod
    def _try_public_rpcs(cls, chain: str, web3_providers: dict):
        """Try to connect using public RPC endpoints"""
        for rpc_url in cls.PUBLIC_RPC_ENDPOINTS[chain]:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url))
                # Test the connection
                w3.eth.block_number
                web3_providers[chain] = w3
                logger.info(f"Successfully connected to {chain} using public RPC: {rpc_url}")
                break
            except Exception as e:
                logger.warning(f"Failed to connect to {chain} using RPC {rpc_url}: {str(e)}")
                continue

# Standard ABI for ERC20 tokens
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# External API configurations
EXTERNAL_APIS = {
    "Bitcoin": {
        "url": "https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance",
        "key_env": "BLOCKCYPHER_API_KEY"
    },
    "Tron": {
        "url": "https://api.trongrid.io/v1/accounts/{address}",
        "key_env": "TRONGRID_API_KEY"
    },
    "Solana": {
        "url": "https://api.mainnet-beta.solana.com",
        "key_env": "SOLANA_API_KEY"
    },
    "Polkadot": {
        "url": "https://polkadot.api.subscan.io/api/scan/account",
        "key_env": "POLKADOT_API_KEY"
    },
    "XRP": {
        "url": "https://xrplcluster.com/",
        "key_env": "RIPPLE_API_KEY"
    }
} 