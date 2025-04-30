"""Cosmos transaction fee estimator module."""

from typing import Dict, Any, Optional, List
import json
import requests
from decimal import Decimal

from .base import FeeEstimator, APIClient, logger

# Constants
COSMOS_RPC_URL = "https://cosmos-rpc.polkachu.com"
COSMOS_REST_URL = "https://cosmos-api.polkachu.com"
UATOM_PER_ATOM = 1_000_000  # 1 ATOM = 10^6 uatom
DEFAULT_GAS_LIMIT = 100_000  # Default gas units for a transfer


class CosmosFeeEstimator(FeeEstimator):
    """Cosmos fee estimator for ATOM and tokens."""
    
    def __init__(self, rpc_url: str = COSMOS_RPC_URL, rest_url: str = COSMOS_REST_URL):
        """
        Initialize the Cosmos fee estimator.
        
        Args:
            rpc_url: Cosmos RPC URL
            rest_url: Cosmos REST API URL
        """
        self.rpc_url = rpc_url
        self.rest_url = rest_url
        self.client = APIClient(base_url=rpc_url, rate_limit=0.5)  # 2 req/sec
    
    def _get_gas_prices(self) -> Dict[str, float]:
        """
        Get current gas prices from chain.
        
        Returns:
            Gas prices in different denominations
        """
        try:
            # In a real implementation, you would query the chain for min-gas-prices
            # or use a gas price oracle
            # Most validators accept a minimum of 0.025 uatom per gas unit
            return {
                "uatom": 0.025  # 0.025 uatom per gas unit
            }
        except Exception as e:
            logger.warning(f"Failed to get gas prices: {e}")
            # Default value
            return {"uatom": 0.025}
    
    def _estimate_gas(self, from_address: str, to_address: str, 
                     amount: float, denom: str = "uatom", 
                     is_token_transfer: bool = False) -> int:
        """
        Estimate gas needed for a transaction.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount to transfer
            denom: Denomination
            is_token_transfer: Whether it's an IBC or CW20 token transfer
            
        Returns:
            Estimated gas units
        """
        # For basic transfers, we can use default values
        # In a real implementation, you would use the simulate transaction endpoint
        
        # Native ATOM transfer
        if denom == "uatom" and not is_token_transfer:
            return DEFAULT_GAS_LIMIT
            
        # IBC token transfer (cross-chain)
        if is_token_transfer and denom.startswith("ibc/"):
            return DEFAULT_GAS_LIMIT * 2
            
        # CW20 token transfer
        if is_token_transfer:
            return DEFAULT_GAS_LIMIT * 1.5
            
        # Default fallback
        return DEFAULT_GAS_LIMIT
    
    def _calculate_fee(self, gas_limit: int, gas_price: float, denom: str = "uatom") -> Dict[str, Any]:
        """
        Calculate transaction fee based on gas limit and price.
        
        Args:
            gas_limit: Gas limit
            gas_price: Gas price per unit
            denom: Denomination
            
        Returns:
            Fee details
        """
        # Cosmos fees are calculated as gas * gas_price
        fee_amount = int(gas_limit * gas_price)
        
        return {
            "amount": fee_amount,
            "denom": denom,
            "gas_limit": gas_limit
        }
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native ATOM transfer.
        
        Args:
            from_address: Source Cosmos address
            to_address: Destination Cosmos address
            amount: Amount to transfer in ATOM
            
        Returns:
            Dict with fee estimation details
        """
        # Get current gas prices
        gas_prices = self._get_gas_prices()
        gas_price = gas_prices.get("uatom", 0.025)
        
        # Convert amount to uatom
        amount_uatom = int(Decimal(str(amount)) * Decimal(UATOM_PER_ATOM))
        
        # Estimate gas needed
        gas_limit = self._estimate_gas(from_address, to_address, amount_uatom)
        
        # Calculate fee
        fee_details = self._calculate_fee(gas_limit, gas_price)
        fee = fee_details["amount"]
        
        # Get ATOM/USD price
        atom_usd_price = self._get_atom_usd_price()
        
        # Convert to USD
        fee_in_atom = fee / UATOM_PER_ATOM
        usd_price = fee_in_atom * atom_usd_price if atom_usd_price else None
        
        # In Cosmos, gas prices are fixed, but we can adjust gas limit for "priority"
        # These are just slight variations for API consistency
        fee_options = {
            "slow": int(fee * 0.9),
            "average": fee,
            "fast": int(fee * 1.2)  # Faster inclusion by paying higher fees
        }
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee_amount,
                "fee_atom": fee_amount / UATOM_PER_ATOM,
                "gas_limit": int(gas_limit * (1.0 if speed == "average" else (0.9 if speed == "slow" else 1.2)))
            } for speed, fee_amount in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee,
            fee_currency="ATOM",
            priority_options=priority_options,
            unit="uatom",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for token transfer.
        
        In Cosmos, this can be either an IBC token (ibc/...) or a CW20 token.
        The contract parameter should specify the type and identifier.
        
        Args:
            from_address: Source Cosmos address
            to_address: Destination Cosmos address
            amount: Amount to transfer in token units
            token_contract: Token identifier (format: "ibc/{hash}" for IBC or contract address for CW20)
            
        Returns:
            Dict with fee estimation details
        """
        # Get current gas prices
        gas_prices = self._get_gas_prices()
        gas_price = gas_prices.get("uatom", 0.025)
        
        # Determine token type and estimate gas
        is_ibc_token = token_contract.startswith("ibc/")
        
        # Estimate gas with higher limit for token transfers
        gas_limit = self._estimate_gas(
            from_address, to_address, amount, 
            denom=token_contract if is_ibc_token else "uatom",
            is_token_transfer=True
        )
        
        # Calculate fee
        fee_details = self._calculate_fee(gas_limit, gas_price)
        fee = fee_details["amount"]
        
        # Get ATOM/USD price
        atom_usd_price = self._get_atom_usd_price()
        
        # Convert to USD
        fee_in_atom = fee / UATOM_PER_ATOM
        usd_price = fee_in_atom * atom_usd_price if atom_usd_price else None
        
        # Create similar fee options
        fee_options = {
            "slow": int(fee * 0.9),
            "average": fee,
            "fast": int(fee * 1.2)
        }
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee_amount,
                "fee_atom": fee_amount / UATOM_PER_ATOM,
                "gas_limit": int(gas_limit * (1.0 if speed == "average" else (0.9 if speed == "slow" else 1.2)))
            } for speed, fee_amount in fee_options.items()
        }
        
        response = self.format_fee_response(
            fee=fee,
            fee_currency="ATOM",
            priority_options=priority_options,
            unit="uatom",
            usd_price=usd_price
        )
        
        # Add Cosmos-specific token details
        response["token_denom"] = token_contract
        response["token_type"] = "ibc" if is_ibc_token else "cw20"
        
        return response
    
    def _get_atom_usd_price(self) -> Optional[float]:
        """Get current ATOM/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=cosmos&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("cosmos", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get ATOM/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native ATOM transfer.
    
    Args:
        from_address: Source Cosmos address
        to_address: Destination Cosmos address
        amount: Amount to transfer in ATOM
        
    Returns:
        Dict with fee estimation details
    """
    estimator = CosmosFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for token transfer.
    
    Args:
        from_address: Source Cosmos address
        to_address: Destination Cosmos address
        amount: Amount to transfer in token units
        token_contract: Token identifier
        
    Returns:
        Dict with fee estimation details
    """
    estimator = CosmosFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 