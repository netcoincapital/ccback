"""Bitcoin transaction fee estimator module."""

import math
from typing import Dict, Any, Optional, Union, List
import requests

from .base import FeeEstimator, APIClient, logger

# Constants
BTC_BYTES_PER_INPUT = 148  # Approximate size of one input in bytes
BTC_BYTES_PER_OUTPUT = 34  # Approximate size of one output in bytes
BTC_BYTES_OVERHEAD = 10    # Transaction overhead bytes
DEFAULT_INPUTS = 1         # Default number of inputs to estimate
DEFAULT_OUTPUTS = 2        # Default number of outputs (recipient + change)
ESTIMATED_TX_SIZE = (BTC_BYTES_OVERHEAD + 
                     (BTC_BYTES_PER_INPUT * DEFAULT_INPUTS) + 
                     (BTC_BYTES_PER_OUTPUT * DEFAULT_OUTPUTS))

# APIs for fee estimation
BLOCKSTREAM_API = "https://blockstream.info/api"
MEMPOOL_SPACE_API = "https://mempool.space/api"
BITCOIN_FEES_API = "https://bitcoinfees.earn.com/api/v1/fees/recommended"


class BitcoinFeeEstimator(FeeEstimator):
    """Bitcoin fee estimator for BTC transfers."""
    
    def __init__(self):
        """Initialize the Bitcoin fee estimator."""
        self.blockstream_client = APIClient(base_url=BLOCKSTREAM_API, rate_limit=0.5)
        self.mempool_client = APIClient(base_url=MEMPOOL_SPACE_API, rate_limit=0.5)
    
    def _get_fee_rates(self) -> Dict[str, float]:
        """
        Get fee rates from various APIs and average them.
        
        Returns:
            Dictionary with fee rates in satoshis/byte for different priorities
        """
        fee_rates = {"slow": [], "average": [], "fast": []}
        
        # Try Mempool.space API
        try:
            mempool_response = requests.get(f"{MEMPOOL_SPACE_API}/v1/fees/recommended", timeout=10)
            mempool_response.raise_for_status()
            mempool_data = mempool_response.json()
            
            fee_rates["slow"].append(float(mempool_data.get("hourFee", 10)))
            fee_rates["average"].append(float(mempool_data.get("halfHourFee", 20)))
            fee_rates["fast"].append(float(mempool_data.get("fastestFee", 50)))
        except Exception as e:
            logger.warning(f"Error fetching Mempool.space fees: {e}")
        
        # Try Bitcoinfees.earn.com API
        try:
            bitcoinfees_response = requests.get(BITCOIN_FEES_API, timeout=10)
            bitcoinfees_response.raise_for_status()
            bitcoinfees_data = bitcoinfees_response.json()
            
            fee_rates["slow"].append(float(bitcoinfees_data.get("hourFee", 10)))
            fee_rates["average"].append(float(bitcoinfees_data.get("halfHourFee", 20)))
            fee_rates["fast"].append(float(bitcoinfees_data.get("fastestFee", 50)))
        except Exception as e:
            logger.warning(f"Error fetching Bitcoinfees.earn.com fees: {e}")
        
        # Try Blockstream API
        try:
            blockstream_response = requests.get(f"{BLOCKSTREAM_API}/fee-estimates", timeout=10)
            blockstream_response.raise_for_status()
            blockstream_data = blockstream_response.json()
            
            # Convert blocks to priority categories
            fee_rates["slow"].append(float(blockstream_data.get("6", 10)))  # ~1 hour
            fee_rates["average"].append(float(blockstream_data.get("3", 20)))  # ~30 min
            fee_rates["fast"].append(float(blockstream_data.get("1", 50)))  # ~10 min
        except Exception as e:
            logger.warning(f"Error fetching Blockstream fees: {e}")
        
        # If all APIs failed, use default values
        if not any(fee_rates.values()):
            logger.warning("All fee APIs failed, using default values")
            return {
                "slow": 10.0,
                "average": 20.0,
                "fast": 50.0
            }
        
        # Average the collected fee rates
        result = {}
        for priority, rates in fee_rates.items():
            if rates:
                result[priority] = sum(rates) / len(rates)
            else:
                # Fallback values if specific priority has no data
                fallbacks = {"slow": 10.0, "average": 20.0, "fast": 50.0}
                result[priority] = fallbacks[priority]
        
        return result
    
    def _estimate_tx_size(self, from_address: str, to_address: str, 
                         inputs: Optional[int] = None, 
                         outputs: Optional[int] = None) -> int:
        """
        Estimate transaction size in bytes.
        
        Args:
            from_address: Source address (not used in simple estimation)
            to_address: Destination address (not used in simple estimation)
            inputs: Number of inputs, if known
            outputs: Number of outputs, if known
            
        Returns:
            Estimated transaction size in bytes
        """
        # Try to get UTXO data for better estimation, if available
        if inputs is None:
            try:
                # This is a simplified example; in a real system, you would use
                # an indexer or your own node to get accurate UTXO information
                utxo_response = requests.get(
                    f"{BLOCKSTREAM_API}/address/{from_address}/utxo",
                    timeout=10
                )
                if utxo_response.status_code == 200:
                    utxos = utxo_response.json()
                    inputs = len(utxos)
                else:
                    inputs = DEFAULT_INPUTS
            except Exception:
                inputs = DEFAULT_INPUTS
        
        if outputs is None:
            outputs = DEFAULT_OUTPUTS  # Typically recipient + change
        
        # Calculate size: overhead + inputs + outputs
        tx_size = (
            BTC_BYTES_OVERHEAD + 
            (BTC_BYTES_PER_INPUT * inputs) + 
            (BTC_BYTES_PER_OUTPUT * outputs)
        )
        
        return tx_size
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for BTC transfer.
        
        Args:
            from_address: Source BTC address
            to_address: Destination BTC address
            amount: Amount to transfer in BTC
            
        Returns:
            Dict with fee estimation details
        """
        # Get fee rates (satoshis/byte)
        fee_rates = self._get_fee_rates()
        
        # Estimate transaction size
        tx_size = self._estimate_tx_size(from_address, to_address)
        
        # Calculate fee options in satoshis
        fee_options = {
            speed: math.ceil(rate * tx_size)
            for speed, rate in fee_rates.items()
        }
        
        # Get current BTC/USD price
        btc_usd_price = self._get_btc_usd_price()
        
        # Calculate USD equivalent of the average fee
        avg_fee_btc = fee_options['average'] / 100_000_000  # Convert satoshis to BTC
        usd_price = float(avg_fee_btc) * btc_usd_price if btc_usd_price else None
        
        # Format priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_btc": fee / 100_000_000,  # Convert to BTC
                "fee_rate": f"{fee_rates[speed]:.1f} sat/byte"
            } for speed, fee in fee_options.items()
        }
        
        return self.format_fee_response(
            fee=fee_options['average'],
            fee_currency="BTC",
            priority_options=priority_options,
            unit="satoshi",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for token transfer.
        
        Bitcoin doesn't have tokens like Ethereum. This method is included for API compatibility.
        For assets like Omni or Liquid, specialized estimation would be needed.
        
        Args:
            from_address: Source BTC address
            to_address: Destination BTC address
            amount: Amount to transfer
            token_contract: Token identifier (not applicable for BTC)
            
        Returns:
            Dict with fee estimation details and error message
        """
        # Bitcoin doesn't have native tokens like Ethereum
        # We'll return a basic error response for compatibility
        logger.warning(f"Token transfers not supported for Bitcoin. Token: {token_contract}")
        
        response = self.format_fee_response(
            fee=0,
            fee_currency="BTC",
            unit="satoshi"
        )
        
        response["error"] = "Native token transfers are not supported on Bitcoin. For Omni or Liquid assets, use specialized endpoints."
        return response
    
    def _get_btc_usd_price(self) -> Optional[float]:
        """Get current BTC/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("bitcoin", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get BTC/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for BTC transfer.
    
    Args:
        from_address: Source BTC address
        to_address: Destination BTC address
        amount: Amount to transfer in BTC
        
    Returns:
        Dict with fee estimation details
    """
    estimator = BitcoinFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for token transfer on Bitcoin.
    
    Note: Bitcoin doesn't have native tokens like Ethereum. This is included for API compatibility.
    
    Args:
        from_address: Source BTC address
        to_address: Destination BTC address
        amount: Amount to transfer
        token_contract: Token identifier (not applicable for BTC)
        
    Returns:
        Dict with fee estimation details and error message
    """
    estimator = BitcoinFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 