"""Ethereum transaction fee estimator module."""

import json
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import requests
from web3 import Web3

from .base import FeeEstimator, APIClient, logger

# Constants
ETH_GAS_STATION_API = "https://ethgasstation.info/api/ethgasAPI.json"
INFURA_URL = "https://mainnet.infura.io/v3/"  # Add your key after deploying
ETH_TRANSFER_GAS = 21000  # Standard ETH transfer gas
ERC20_TRANSFER_GAS = 65000  # Estimated gas for ERC20 transfer

# EVM Chain configurations
EVM_CHAIN_CONFIGS = {
    "ethereum": {
        "rpc_url": "https://eth.llamarpc.com",
        "gas_api": "https://ethgasstation.info/api/ethgasAPI.json",
        "chain_id": 1,
        "currency": "ETH",
        "default_gas_price": 20  # Gwei
    },
    "bsc": {
        "rpc_url": "https://bsc-dataseed.binance.org/",
        "gas_api": "https://api.bscscan.com/api?module=gastracker&action=gasoracle",
        "chain_id": 56,
        "currency": "BNB", 
        "default_gas_price": 5  # Gwei
    },
    "polygon": {
        "rpc_url": "https://polygon-rpc.com/",
        "gas_api": "https://api.polygonscan.com/api?module=gastracker&action=gasoracle",
        "chain_id": 137,
        "currency": "MATIC",
        "default_gas_price": 30  # Gwei
    },
    "avalanche": {
        "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
        "gas_api": None,  # No specific gas API
        "chain_id": 43114,
        "currency": "AVAX",
        "default_gas_price": 25  # Gwei
    },
    "arbitrum": {
        "rpc_url": "https://arb1.arbitrum.io/rpc",
        "gas_api": None,
        "chain_id": 42161,
        "currency": "ETH",
        "default_gas_price": 0.1  # Gwei (much lower on L2)
    },
    "optimism": {
        "rpc_url": "https://mainnet.optimism.io",
        "gas_api": None,
        "chain_id": 10,
        "currency": "ETH", 
        "default_gas_price": 0.001  # Gwei (very low on L2)
    },
    "fantom": {
        "rpc_url": "https://rpc.ftm.tools/",
        "gas_api": None,
        "chain_id": 250,
        "currency": "FTM",
        "default_gas_price": 22  # Gwei
    },
    "base": {
        "rpc_url": "https://mainnet.base.org",
        "gas_api": None,
        "chain_id": 8453,
        "currency": "ETH",
        "default_gas_price": 0.001  # Gwei (L2)
    }
}

# ERC20 Transfer function signature
ERC20_TRANSFER_SIGNATURE = "0xa9059cbb"

class EthereumFeeEstimator(FeeEstimator):
    """Ethereum fee estimator for ETH and ERC20 tokens on EVM chains."""
    
    def __init__(self, chain: str = "ethereum", infura_key: Optional[str] = None):
        """
        Initialize the EVM fee estimator.
        
        Args:
            chain: EVM chain name (ethereum, bsc, polygon, etc.)
            infura_key: Infura API key, if None will use chain-specific RPC
        """
        self.chain = chain.lower()
        self.infura_key = infura_key
        
        # Get chain configuration
        if self.chain not in EVM_CHAIN_CONFIGS:
            raise ValueError(f"Unsupported EVM chain: {self.chain}")
        
        self.config = EVM_CHAIN_CONFIGS[self.chain]
        
        # Connect to blockchain node
        if infura_key and self.chain == "ethereum":
            self.web3 = Web3(Web3.HTTPProvider(f"{INFURA_URL}{infura_key}"))
        else:
            # Use chain-specific RPC
            self.web3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))
        
        self.gas_client = APIClient(base_url="", rate_limit=0.2)  # Max 5 req/sec
    
    def _get_current_gas_prices(self) -> Dict[str, float]:
        """
        Get current gas prices from chain-specific gas station API.
        
        Returns:
            Dictionary with gas prices in Gwei for different priorities
        """
        try:
            # Try to get gas prices from chain-specific gas price API
            if self.config["gas_api"]:
                response = requests.get(self.config["gas_api"], timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Handle different API response formats
                if self.chain == "ethereum":
                    # ETH Gas Station format
                    return {
                        "slow": data.get("safeLow", 50) / 10,
                        "average": data.get("average", 100) / 10,
                        "fast": data.get("fast", 200) / 10
                    }
                elif self.chain in ["bsc", "polygon"]:
                    # BSCScan/PolygonScan format
                    result = data.get("result", {})
                    return {
                        "slow": float(result.get("SafeGasPrice", self.config["default_gas_price"] * 0.8)),
                        "average": float(result.get("StandardGasPrice", self.config["default_gas_price"])),
                        "fast": float(result.get("FastGasPrice", self.config["default_gas_price"] * 1.5))
                    }
                    
        except Exception as e:
            logger.warning(f"Error fetching gas prices from API: {e}")
            
        # Fallback: try to get from the node
        try:
            gas_price_wei = self.web3.eth.gas_price
            gas_price_gwei = self.web3.from_wei(gas_price_wei, 'gwei')
            
            # Create simulated tiers
            return {
                "slow": gas_price_gwei * 0.8,
                "average": gas_price_gwei,
                "fast": gas_price_gwei * 1.5
            }
        except Exception as e2:
            logger.error(f"Failed to get fallback gas price: {e2}")
            
            # Final fallback: use chain-specific default values
            default_price = self.config["default_gas_price"]
            return {
                "slow": default_price * 0.8,
                "average": default_price,
                "fast": default_price * 1.5
            }
    
    def _get_token_decimals(self, token_address: str) -> int:
        """Get the decimal places of an ERC20 token."""
        try:
            # Minimal ABI for decimals method
            abi = json.loads('''[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"}]''')
            token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(token_address), abi=abi)
            return token_contract.functions.decimals().call()
        except Exception as e:
            logger.warning(f"Failed to get token decimals: {e}. Using default 18.")
            return 18  # Default for most ERC20 tokens
    
    def _estimate_gas_usage(self, from_address: str, to_address: str, amount: float, 
                            token_contract: Optional[str] = None) -> int:
        """
        Estimate gas usage for a transaction.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount to transfer
            token_contract: Optional token contract address for ERC20 transfers
            
        Returns:
            Estimated gas units
        """
        try:
            from_address = self.web3.to_checksum_address(from_address)
            to_address = self.web3.to_checksum_address(to_address)
            
            if not token_contract:
                # For ETH transfers, we know the gas usage is constant
                return ETH_TRANSFER_GAS
            
            token_contract = self.web3.to_checksum_address(token_contract)
            decimals = self._get_token_decimals(token_contract)
            
            # Convert amount to token units with proper decimals
            amount_in_units = int(Decimal(str(amount)) * Decimal(10) ** decimals)
            
            # Create the data for the transfer function call
            token_abi = json.loads('''[{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"}]''')
            token = self.web3.eth.contract(address=token_contract, abi=token_abi)
            
            # Estimate gas
            try:
                gas_estimate = token.functions.transfer(
                    to_address, amount_in_units
                ).estimate_gas({'from': from_address})
                return gas_estimate
            except Exception as e:
                logger.warning(f"Failed to estimate token transfer gas: {e}")
                # Return default value
                return ERC20_TRANSFER_GAS
                
        except Exception as e:
            logger.error(f"Error in gas estimation: {e}")
            # Return default values if estimation fails
            return ERC20_TRANSFER_GAS if token_contract else ETH_TRANSFER_GAS
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native ETH transfer.
        
        Args:
            from_address: Source ETH address
            to_address: Destination ETH address
            amount: Amount to transfer in ETH
            
        Returns:
            Dict with fee estimation details
        """
        gas_prices = self._get_current_gas_prices()
        gas_limit = self._estimate_gas_usage(from_address, to_address, amount)
        
        # Calculate fee options in wei
        fee_options = {
            speed: int(self.web3.to_wei(price, 'gwei') * gas_limit)
            for speed, price in gas_prices.items()
        }
        
        # Get current ETH/USD price (simplified, could be replaced with a proper price API)
        eth_usd_price = self._get_eth_usd_price()
        
        # Convert the base fee (average) to USD
        avg_fee_eth = self.web3.from_wei(fee_options['average'], 'ether')
        usd_price = float(avg_fee_eth) * eth_usd_price if eth_usd_price else None
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_eth": float(self.web3.from_wei(fee, 'ether'))
            } for speed, fee in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee_options['average'],
            fee_currency=self.config["currency"],
            gas_used=gas_limit,
            gas_price=int(self.web3.to_wei(gas_prices['average'], 'gwei')),
            priority_options=priority_options,
            unit="wei",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for ERC20 token transfer.
        
        Args:
            from_address: Source ETH address
            to_address: Destination ETH address
            amount: Amount to transfer in token units
            token_contract: Token contract address
            
        Returns:
            Dict with fee estimation details
        """
        gas_prices = self._get_current_gas_prices()
        gas_limit = self._estimate_gas_usage(from_address, to_address, amount, token_contract)
        
        # Calculate fee options in wei
        fee_options = {
            speed: int(self.web3.to_wei(price, 'gwei') * gas_limit)
            for speed, price in gas_prices.items()
        }
        
        # Get current ETH/USD price
        eth_usd_price = self._get_eth_usd_price()
        
        # Convert the base fee (average) to USD
        avg_fee_eth = self.web3.from_wei(fee_options['average'], 'ether')
        usd_price = float(avg_fee_eth) * eth_usd_price if eth_usd_price else None
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_eth": float(self.web3.from_wei(fee, 'ether'))
            } for speed, fee in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee_options['average'],
            fee_currency=self.config["currency"],
            gas_used=gas_limit,
            gas_price=int(self.web3.to_wei(gas_prices['average'], 'gwei')),
            priority_options=priority_options,
            unit="wei",
            usd_price=usd_price
        )
    
    def _get_eth_usd_price(self) -> Optional[float]:
        """Get current ETH/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("ethereum", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get ETH/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float, chain: str = "ethereum") -> Dict[str, Any]:
    """
    Estimate fee for native token transfer on EVM chains.
    
    Args:
        from_address: Source address
        to_address: Destination address
        amount: Amount to transfer
        chain: EVM chain name (ethereum, bsc, polygon, etc.)
        
    Returns:
        Dict with fee estimation details
    """
    estimator = EthereumFeeEstimator(chain=chain)
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str, chain: str = "ethereum") -> Dict[str, Any]:
    """
    Estimate fee for ERC20 token transfer on EVM chains.
    
    Args:
        from_address: Source address
        to_address: Destination address
        amount: Amount to transfer in token units
        token_contract: Token contract address
        chain: EVM chain name (ethereum, bsc, polygon, etc.)
        
    Returns:
        Dict with fee estimation details
    """
    estimator = EthereumFeeEstimator(chain=chain)
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 