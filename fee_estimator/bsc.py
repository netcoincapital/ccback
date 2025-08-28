"""BSC (Binance Smart Chain) fee estimator implementation."""

from decimal import Decimal
from typing import Dict, Any, Optional
from web3 import Web3
import requests
import logging

from .base import FeeEstimator, logger

# Constants
DEFAULT_GAS_LIMIT = 21000  # Standard gas limit for BNB transfers
DEFAULT_TOKEN_GAS_LIMIT = 65000  # Standard gas limit for token transfers
DEFAULT_GAS_PRICE = 5  # Default gas price in Gwei

class BSCFeeEstimator(FeeEstimator):
    """Fee estimator for Binance Smart Chain."""
    
    def __init__(self):
        """Initialize BSC fee estimator."""
        self.web3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))
        
    def _get_current_gas_prices(self) -> Dict[str, float]:
        """
        Get current gas prices from BSC network.
        
        Returns:
            Dict with gas prices for different speeds
        """
        try:
            # Get current gas price from Web3
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = self.web3.from_wei(gas_price, 'gwei')
            
            # Create priority options
            return {
                "slow": float(gas_price_gwei) * 0.9,  # 10% lower
                "average": float(gas_price_gwei),
                "fast": float(gas_price_gwei) * 1.1   # 10% higher
            }
        except Exception as e:
            logger.warning(f"Failed to get gas prices from BSC: {e}")
            # Return default values
            return {
                "slow": DEFAULT_GAS_PRICE * 0.9,
                "average": DEFAULT_GAS_PRICE,
                "fast": DEFAULT_GAS_PRICE * 1.1
            }
    
    def _estimate_gas_usage(self, from_address: str, to_address: str, 
                          amount: float, token_contract: Optional[str] = None) -> int:
        """
        Estimate gas usage for a transaction.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount to transfer
            token_contract: Token contract address (optional)
            
        Returns:
            Estimated gas units
        """
        try:
            if token_contract:
                # For token transfers, use a higher gas limit
                return DEFAULT_TOKEN_GAS_LIMIT
            else:
                # For native BNB transfers, use standard gas limit
                return DEFAULT_GAS_LIMIT
        except Exception as e:
            logger.warning(f"Failed to estimate gas usage: {e}")
            return DEFAULT_GAS_LIMIT
    
    def _get_bnb_usd_price(self) -> Optional[float]:
        """Get current BNB/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=binancecoin&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("binancecoin", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get BNB/USD price: {e}")
            return None
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native BNB transfer.
        
        Args:
            from_address: Source BSC address
            to_address: Destination BSC address
            amount: Amount to transfer in BNB
            
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
        
        # Get current BNB/USD price
        bnb_usd_price = self._get_bnb_usd_price()
        
        # Convert the base fee (average) to USD
        avg_fee_bnb = self.web3.from_wei(fee_options['average'], 'ether')
        usd_price = float(avg_fee_bnb) * bnb_usd_price if bnb_usd_price else None
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_bnb": float(self.web3.from_wei(fee, 'ether'))
            } for speed, fee in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee_options['average'],
            fee_currency="BNB",
            gas_used=gas_limit,
            gas_price=int(self.web3.to_wei(gas_prices['average'], 'gwei')),
            priority_options=priority_options,
            unit="wei",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for BEP20 token transfer.
        
        Args:
            from_address: Source BSC address
            to_address: Destination BSC address
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
        
        # Get current BNB/USD price
        bnb_usd_price = self._get_bnb_usd_price()
        
        # Convert the base fee (average) to USD
        avg_fee_bnb = self.web3.from_wei(fee_options['average'], 'ether')
        usd_price = float(avg_fee_bnb) * bnb_usd_price if bnb_usd_price else None
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_bnb": float(self.web3.from_wei(fee, 'ether'))
            } for speed, fee in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee_options['average'],
            fee_currency="BNB",
            gas_used=gas_limit,
            gas_price=int(self.web3.to_wei(gas_prices['average'], 'gwei')),
            priority_options=priority_options,
            unit="wei",
            usd_price=usd_price
        )


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native BNB transfer.
    
    Args:
        from_address: Source BSC address
        to_address: Destination BSC address
        amount: Amount to transfer in BNB
        
    Returns:
        Dict with fee estimation details
    """
    estimator = BSCFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for BEP20 token transfer.
    
    Args:
        from_address: Source BSC address
        to_address: Destination BSC address
        amount: Amount to transfer in token units
        token_contract: Token contract address
        
    Returns:
        Dict with fee estimation details
    """
    estimator = BSCFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 