# Transaction Fee Estimator Module

A comprehensive module for estimating transaction fees across multiple blockchain networks. This module provides a consistent API for estimating fees for both native cryptocurrency transfers and token transfers.

## Supported Blockchains

- Bitcoin (BTC)
- Ethereum (ETH)
- TRON (TRX)
- Solana (SOL)
- XRP (Ripple)
- Cardano (ADA)
- Polkadot (DOT)
- Cosmos (ATOM)

## Features

- Unified API for consistent fee estimation across different blockchains
- Support for both native coin and token transfers
- Multiple fee priority options (slow, average, fast)
- USD price conversion
- Blockchain-specific details in responses
- Rate limiting and retry logic for API calls
- Comprehensive error handling

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from fee_estimator.estimator import estimate_fee

# Estimate fee for ETH transfer
eth_fee = estimate_fee(
    blockchain="ethereum",
    from_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    amount=0.1
)

# Estimate fee for ERC20 token transfer
token_fee = estimate_fee(
    blockchain="ethereum",
    from_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    amount=100,
    token_contract="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # USDC contract
)
```

### Getting Blockchain Information

```python
from fee_estimator.estimator import get_supported_chains, get_chain_info

# Get list of supported blockchains
chains = get_supported_chains()

# Get information about a specific blockchain
eth_info = get_chain_info("ethereum")
```

## Response Format

The fee estimation response includes:

```json
{
  "fee": 2100000,                   // Base fee amount
  "fee_currency": "ETH",            // Fee currency symbol
  "unit": "wei",                    // Unit of the fee amount
  "timestamp": 1685432865,          // Timestamp of the estimation
  "gas_used": 21000,                // Gas units used (for EVM chains)
  "gas_price": 100000000000,        // Gas price (for EVM chains)
  "priority_options": {             // Different fee options based on priority
    "slow": {
      "fee": 1890000,
      "fee_eth": 0.00000189
    },
    "average": {
      "fee": 2100000,
      "fee_eth": 0.0000021
    },
    "fast": {
      "fee": 3150000,
      "fee_eth": 0.00000315
    }
  },
  "usd_price": 0.00063              // USD equivalent of the fee
}
```

Additional blockchain-specific details may be included in the response.

## Example

See `example.py` for more detailed usage examples.

## Notes for Production Use

For production use, you should:

1. Replace public RPC endpoints with your own dedicated nodes or API keys
2. Implement proper secret management for API keys
3. Consider adding caching to reduce API calls
4. Implement proper error handling and monitoring
5. Regularly update the module to account for blockchain protocol changes

## Dependencies

- requests: HTTP client for API calls
- web3: Ethereum interaction library
- typing-extensions: Type hinting
- urllib3: HTTP client used by requests
- python-dotenv: Environment variable management
- pydantic: Data validation

## License

MIT 