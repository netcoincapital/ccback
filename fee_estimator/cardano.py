"""Cardano transaction fee estimator module."""

from typing import Dict, Any, Optional, List
import json
import requests

from .base import FeeEstimator, APIClient, logger

# Constants
CARDANO_API_URL = "https://cardano-mainnet.blockfrost.io/api/v0"
LOVELACE_PER_ADA = 1_000_000  # 1 ADA = 1,000,000 Lovelace
DEFAULT_TX_SIZE = 300  # Bytes for a simple transaction
BYTES_PER_INPUT = 150  # Estimated bytes per input
BYTES_PER_OUTPUT = 100  # Estimated bytes per output
MIN_FEE_A = 44  # Minimum fee per byte (lovelace)
MIN_FEE_B = 155381  # Minimum base fee (lovelace)


class CardanoFeeEstimator(FeeEstimator):
    """Cardano fee estimator for ADA and native tokens."""
    
    def __init__(self, api_key: Optional[str] = None, api_url: str = CARDANO_API_URL):
        """
        Initialize the Cardano fee estimator.
        
        Args:
            api_key: Blockfrost API key
            api_url: Cardano API URL
        """
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {"project_id": api_key} if api_key else {}
        self.client = APIClient(base_url=api_url, rate_limit=0.2)  # 5 req/sec max
    
    def _get_protocol_parameters(self) -> Dict[str, Any]:
        """
        Get current protocol parameters from Cardano network.
        
        Returns:
            Protocol parameters dict
        """
        if not self.api_key:
            # Without API key, return default parameters
            return {
                "min_fee_a": MIN_FEE_A,
                "min_fee_b": MIN_FEE_B
            }
            
        try:
            response = requests.get(
                f"{self.api_url}/epochs/latest/parameters",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to get protocol parameters: {e}")
            # Return default values
            return {
                "min_fee_a": MIN_FEE_A,
                "min_fee_b": MIN_FEE_B
            }
    
    def _estimate_tx_size(self, is_token_transfer: bool = False, token_count: int = 1) -> int:
        """
        Estimate transaction size in bytes.
        
        Args:
            is_token_transfer: Whether it's a token transfer
            token_count: Number of different tokens to transfer
            
        Returns:
            Estimated transaction size in bytes
        """
        # Basic transaction size
        tx_size = DEFAULT_TX_SIZE
        
        # Add size for token transfers
        if is_token_transfer:
            # Each token policy adds overhead
            tx_size += token_count * 40
        
        return tx_size
    
    def _calculate_fee(self, tx_size: int, params: Dict[str, Any]) -> int:
        """
        Calculate transaction fee based on size and protocol parameters.
        
        Args:
            tx_size: Transaction size in bytes
            params: Protocol parameters
            
        Returns:
            Fee in lovelace
        """
        min_fee_a = params.get("min_fee_a", MIN_FEE_A)
        min_fee_b = params.get("min_fee_b", MIN_FEE_B)
        
        # Fee calculation: a * size + b
        fee = (min_fee_a * tx_size) + min_fee_b
        
        return fee
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native ADA transfer.
        
        Args:
            from_address: Source Cardano address
            to_address: Destination Cardano address
            amount: Amount to transfer in ADA
            
        Returns:
            Dict with fee estimation details
        """
        # Get protocol parameters
        params = self._get_protocol_parameters()
        
        # Estimate transaction size
        tx_size = self._estimate_tx_size(is_token_transfer=False)
        
        # Calculate fee
        fee = self._calculate_fee(tx_size, params)
        
        # Get ADA/USD price
        ada_usd_price = self._get_ada_usd_price()
        
        # Convert to USD
        fee_in_ada = fee / LOVELACE_PER_ADA
        usd_price = fee_in_ada * ada_usd_price if ada_usd_price else None
        
        # Cardano doesn't have tiered fees, but we'll create options for API consistency
        fee_options = {
            "slow": fee,
            "average": fee,
            "fast": fee
        }
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee_amount,
                "fee_ada": fee_amount / LOVELACE_PER_ADA
            } for speed, fee_amount in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee,
            fee_currency="ADA",
            priority_options=priority_options,
            unit="lovelace",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for native token transfer.
        
        In Cardano, native tokens are identified by a policy ID.
        
        Args:
            from_address: Source Cardano address
            to_address: Destination Cardano address
            amount: Amount to transfer in token units
            token_contract: Token policy ID
            
        Returns:
            Dict with fee estimation details
        """
        # Get protocol parameters
        params = self._get_protocol_parameters()
        
        # Estimate transaction size for token transfer
        tx_size = self._estimate_tx_size(is_token_transfer=True)
        
        # Calculate fee
        fee = self._calculate_fee(tx_size, params)
        
        # Get ADA/USD price
        ada_usd_price = self._get_ada_usd_price()
        
        # Convert to USD
        fee_in_ada = fee / LOVELACE_PER_ADA
        usd_price = fee_in_ada * ada_usd_price if ada_usd_price else None
        
        # Format priority options (identical since Cardano doesn't have priority options)
        priority_options = {
            "slow": {"fee": fee, "fee_ada": fee / LOVELACE_PER_ADA},
            "average": {"fee": fee, "fee_ada": fee / LOVELACE_PER_ADA},
            "fast": {"fee": fee, "fee_ada": fee / LOVELACE_PER_ADA}
        }
        
        response = self.format_fee_response(
            fee=fee,
            fee_currency="ADA",
            priority_options=priority_options,
            unit="lovelace",
            usd_price=usd_price
        )
        
        # Add Cardano-specific token details
        response["token_policy_id"] = token_contract
        
        return response
    
    def _get_ada_usd_price(self) -> Optional[float]:
        """Get current ADA/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=cardano&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("cardano", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get ADA/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native ADA transfer.
    
    Args:
        from_address: Source Cardano address
        to_address: Destination Cardano address
        amount: Amount to transfer in ADA
        
    Returns:
        Dict with fee estimation details
    """
    estimator = CardanoFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for native token transfer.
    
    Args:
        from_address: Source Cardano address
        to_address: Destination Cardano address
        amount: Amount to transfer in token units
        token_contract: Token policy ID
        
    Returns:
        Dict with fee estimation details
    """
    estimator = CardanoFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 