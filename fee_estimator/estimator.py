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

# EVM chain aliases that use Ethereum fee estimation logic
EVM_CHAIN_ALIASES = {
    "bsc": "ethereum",
    "binance": "ethereum",
    "polygon": "ethereum",
    "matic": "ethereum",
    "avalanche": "ethereum",
    "avax": "ethereum",
    "arbitrum": "ethereum",
    "arb": "ethereum",
    "optimism": "ethereum",
    "op": "ethereum",
    "fantom": "ethereum",
    "ftm": "ethereum",
    "base": "ethereum"
}

# All supported chains including aliases
ALL_SUPPORTED_CHAINS = SUPPORTED_CHAINS + list(EVM_CHAIN_ALIASES.keys())


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

    if blockchain not in ALL_SUPPORTED_CHAINS:
        supported = ", ".join(ALL_SUPPORTED_CHAINS)
        raise ValueError(
            f"Unsupported blockchain: {blockchain}. "
            f"Supported blockchains are: {supported}"
        )

    try:
        # Map EVM chain aliases to ethereum
        target_blockchain = EVM_CHAIN_ALIASES.get(blockchain, blockchain)
        
        # Dynamically import the appropriate blockchain module
        module_name = f".{target_blockchain}"
        module = importlib.import_module(module_name, package="fee_estimator")

        # Call the appropriate fee estimation function
        if token_contract:
            if target_blockchain == "ethereum":
                # For EVM chains, pass the original blockchain name as chain parameter
                original_chain = blockchain if blockchain in EVM_CHAIN_ALIASES else "ethereum"
                result = module.estimate_token_fee(from_address, to_address, amount, token_contract, chain=original_chain)
            else:
                result = module.estimate_token_fee(from_address, to_address, amount, token_contract)
        else:
            if target_blockchain == "ethereum":
                # For EVM chains, pass the original blockchain name as chain parameter
                original_chain = blockchain if blockchain in EVM_CHAIN_ALIASES else "ethereum"
                result = module.estimate_native_fee(from_address, to_address, amount, chain=original_chain)
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
    return ALL_SUPPORTED_CHAINS.copy()


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

    # Check if the blockchain is supported
    if blockchain not in ALL_SUPPORTED_CHAINS:
        return {"error": f"Blockchain '{blockchain}' is not supported"}
    
    # Map EVM chain aliases to get base info, but preserve original name for specific details
    target_blockchain = EVM_CHAIN_ALIASES.get(blockchain, blockchain)
    
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
            "name": "XRP",
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
            "token_standard": "Substrate",
            "supports_tokens": True
        },
        "cosmos": {
            "name": "Cosmos",
            "symbol": "ATOM",
            "decimals": 6,
            "smallest_unit": "uatom",
            "units_per_coin": 1_000_000,
            "token_standard": "IBC",
            "supports_tokens": True
        }
    }
    
    # EVM chain specific information
    evm_chain_specifics = {
        "bsc": {
            "name": "BNB Smart Chain",
            "symbol": "BNB",
            "chain_id": 56,
            "explorer": "https://bscscan.com"
        },
        "polygon": {
            "name": "Polygon",
            "symbol": "MATIC", 
            "chain_id": 137,
            "explorer": "https://polygonscan.com"
        },
        "matic": {
            "name": "Polygon",
            "symbol": "MATIC",
            "chain_id": 137, 
            "explorer": "https://polygonscan.com"
        },
        "avalanche": {
            "name": "Avalanche",
            "symbol": "AVAX",
            "chain_id": 43114,
            "explorer": "https://snowtrace.io"
        },
        "avax": {
            "name": "Avalanche", 
            "symbol": "AVAX",
            "chain_id": 43114,
            "explorer": "https://snowtrace.io"
        },
        "arbitrum": {
            "name": "Arbitrum One",
            "symbol": "ETH",
            "chain_id": 42161,
            "explorer": "https://arbiscan.io"
        },
        "arb": {
            "name": "Arbitrum One",
            "symbol": "ETH", 
            "chain_id": 42161,
            "explorer": "https://arbiscan.io"
        },
        "optimism": {
            "name": "Optimism",
            "symbol": "ETH",
            "chain_id": 10,
            "explorer": "https://optimistic.etherscan.io"
        },
        "op": {
            "name": "Optimism",
            "symbol": "ETH",
            "chain_id": 10,
            "explorer": "https://optimistic.etherscan.io"
        },
        "fantom": {
            "name": "Fantom",
            "symbol": "FTM",
            "chain_id": 250,
            "explorer": "https://ftmscan.com"
        },
        "ftm": {
            "name": "Fantom",
            "symbol": "FTM",
            "chain_id": 250,
            "explorer": "https://ftmscan.com"
        },
        "base": {
            "name": "Base",
            "symbol": "ETH",
            "chain_id": 8453,
            "explorer": "https://basescan.org"
        },
        "binance": {
            "name": "BNB Smart Chain",
            "symbol": "BNB",
            "chain_id": 56,
            "explorer": "https://bscscan.com"
        }
    }
    
    # Get base chain info
    info = chain_info.get(target_blockchain, {}).copy()
    
    # Override with EVM chain specifics if available
    if blockchain in evm_chain_specifics:
        evm_info = evm_chain_specifics[blockchain]
        info.update({
            "name": evm_info["name"],
            "symbol": evm_info["symbol"],
            "chain_id": evm_info.get("chain_id"),
            "explorer": evm_info.get("explorer")
        })
    
    # Add common EVM properties for all EVM chains
    if target_blockchain == "ethereum":
        info.update({
            "decimals": 18,
            "smallest_unit": "wei", 
            "units_per_coin": 1_000_000_000_000_000_000,
            "token_standard": "ERC20",
            "supports_tokens": True
        })
    
    return info 