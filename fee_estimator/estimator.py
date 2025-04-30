"""Main fee estimator interface module."""

import importlib
from typing import Dict, Any, Optional, List, Union

from .base import logger

# Supported blockchains
SUPPORTED_CHAINS = [
    "bitcoin",
    "ethereum",
    "tron",
    "solana",
    "xrp",
    "cardano",
    "polkadot",
    "cosmos"
]


def estimate_fee(
    blockchain: str,
    from_address: str,
    to_address: str,
    amount: float,
    token_contract: Optional[str] = None
) -> Dict[str, Any]:
    """
    Estimate transaction fee for any supported blockchain.
    
    Args:
        blockchain: Name of the blockchain (e.g., "ethereum", "bitcoin")
        from_address: Source address
        to_address: Destination address
        amount: Amount to transfer
        token_contract: Token contract address or identifier (optional)
        
    Returns:
        Dictionary with fee estimation details
        
    Raises:
        ValueError: If blockchain is not supported
        ImportError: If module for blockchain cannot be loaded
        Exception: If fee estimation fails
    """
    blockchain = blockchain.lower()
    
    if blockchain not in SUPPORTED_CHAINS:
        supported = ", ".join(SUPPORTED_CHAINS)
        raise ValueError(
            f"Unsupported blockchain: {blockchain}. "
            f"Supported blockchains are: {supported}"
        )
    
    try:
        # Dynamically import the appropriate blockchain module
        module_name = f".{blockchain}"
        module = importlib.import_module(module_name, package="fee_estimator")
        
        # Call the appropriate fee estimation function
        if token_contract:
            result = module.estimate_token_fee(from_address, to_address, amount, token_contract)
        else:
            result = module.estimate_native_fee(from_address, to_address, amount)
            
        return result
    
    except ImportError as e:
        logger.error(f"Failed to import module for blockchain {blockchain}: {e}")
        raise ImportError(f"Module for blockchain {blockchain} not found") from e
        
    except Exception as e:
        logger.error(f"Fee estimation failed for {blockchain}: {e}")
        raise


def get_supported_chains() -> List[str]:
    """
    Get list of supported blockchain names.
    
    Returns:
        List of supported blockchain names
    """
    return SUPPORTED_CHAINS.copy()


def get_chain_info(blockchain: str) -> Dict[str, Any]:
    """
    Get information about a supported blockchain.
    
    Args:
        blockchain: Name of the blockchain
    
    Returns:
        Dictionary with blockchain information
        
    Raises:
        ValueError: If blockchain is not supported
    """
    blockchain = blockchain.lower()
    
    if blockchain not in SUPPORTED_CHAINS:
        supported = ", ".join(SUPPORTED_CHAINS)
        raise ValueError(
            f"Unsupported blockchain: {blockchain}. "
            f"Supported blockchains are: {supported}"
        )
    
    # Basic information about each chain
    chain_info = {
        "bitcoin": {
            "name": "Bitcoin",
            "symbol": "BTC",
            "decimals": 8,
            "smallest_unit": "satoshi",
            "units_per_coin": 100_000_000,
            "token_standard": None,
            "supports_tokens": False
        },
        "ethereum": {
            "name": "Ethereum",
            "symbol": "ETH",
            "decimals": 18,
            "smallest_unit": "wei",
            "units_per_coin": 1_000_000_000_000_000_000,
            "token_standard": "ERC20",
            "supports_tokens": True
        },
        "tron": {
            "name": "TRON",
            "symbol": "TRX",
            "decimals": 6,
            "smallest_unit": "sun",
            "units_per_coin": 1_000_000,
            "token_standard": "TRC20",
            "supports_tokens": True
        },
        "solana": {
            "name": "Solana",
            "symbol": "SOL",
            "decimals": 9,
            "smallest_unit": "lamport",
            "units_per_coin": 1_000_000_000,
            "token_standard": "SPL",
            "supports_tokens": True
        },
        "xrp": {
            "name": "XRP Ledger",
            "symbol": "XRP",
            "decimals": 6,
            "smallest_unit": "drop",
            "units_per_coin": 1_000_000,
            "token_standard": "IOU",
            "supports_tokens": True
        },
        "cardano": {
            "name": "Cardano",
            "symbol": "ADA",
            "decimals": 6,
            "smallest_unit": "lovelace",
            "units_per_coin": 1_000_000,
            "token_standard": "Native",
            "supports_tokens": True
        },
        "polkadot": {
            "name": "Polkadot",
            "symbol": "DOT",
            "decimals": 10,
            "smallest_unit": "planck",
            "units_per_coin": 10_000_000_000,
            "token_standard": "PSP",
            "supports_tokens": True
        },
        "cosmos": {
            "name": "Cosmos Hub",
            "symbol": "ATOM",
            "decimals": 6,
            "smallest_unit": "uatom",
            "units_per_coin": 1_000_000,
            "token_standard": "IBC",
            "supports_tokens": True
        }
    }
    
    return chain_info[blockchain] 