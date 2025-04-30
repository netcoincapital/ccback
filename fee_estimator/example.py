"""
Example usage of the fee estimator module.

This script demonstrates how to use the fee estimator to get transaction fee
estimates for various blockchains.
"""

import json
import sys
from typing import Dict, Any

from .estimator import estimate_fee, get_supported_chains, get_chain_info


def print_fee_estimate(result: Dict[str, Any]) -> None:
    """Print fee estimate in a readable format."""
    print(json.dumps(result, indent=2))


def main() -> None:
    """Main example function to demonstrate fee estimation."""
    print("Fee Estimator Example")
    print("====================")
    print("\nSupported blockchains:")
    
    # Get and display supported chains
    chains = get_supported_chains()
    for i, chain in enumerate(chains, 1):
        info = get_chain_info(chain)
        print(f"{i}. {info['name']} ({info['symbol']})")
    
    print("\nExample fee estimates:")
    
    # Example ETH transfer
    print("\n1. Ethereum (ETH) transfer:")
    eth_result = estimate_fee(
        blockchain="ethereum",
        from_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        amount=0.1
    )
    print_fee_estimate(eth_result)
    
    # Example ERC20 token transfer
    print("\n2. Ethereum ERC20 token transfer (USDC):")
    erc20_result = estimate_fee(
        blockchain="ethereum",
        from_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        amount=100,
        token_contract="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC contract
    )
    print_fee_estimate(erc20_result)
    
    # Example BTC transfer
    print("\n3. Bitcoin (BTC) transfer:")
    btc_result = estimate_fee(
        blockchain="bitcoin",
        from_address="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        to_address="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        amount=0.01
    )
    print_fee_estimate(btc_result)
    
    # Example SOL transfer
    print("\n4. Solana (SOL) transfer:")
    sol_result = estimate_fee(
        blockchain="solana",
        from_address="9tMkz5BZjWGpK5SgmN9jdLiLXHNkANmMwx6P8GpTyQ2v",
        to_address="9tMkz5BZjWGpK5SgmN9jdLiLXHNkANmMwx6P8GpTyQ2v",
        amount=1.0
    )
    print_fee_estimate(sol_result)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) 