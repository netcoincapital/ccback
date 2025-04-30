"""XRP (Ripple) transaction fee estimator module."""

from typing import Dict, Any, Optional, List
import json
import requests
from decimal import Decimal

from .base import FeeEstimator, APIClient, logger

# Constants
RIPPLE_API_URL = "https://xrplcluster.com"
XRP_DEFAULT_FEE = 10  # Default fee in drops (10 drops = 0.00001 XRP)
XRP_DROPS_PER_XRP = 1_000_000  # 1 XRP = 1,000,000 drops


class XRPFeeEstimator(FeeEstimator):
    """XRP fee estimator for XRP transfers and tokens."""
    
    def __init__(self, api_url: str = RIPPLE_API_URL):
        """
        Initialize the XRP fee estimator.
        
        Args:
            api_url: XRP API URL
        """
        self.api_url = api_url
        self.client = APIClient(base_url=api_url, rate_limit=0.5)  # 2 req/sec
    
    def _get_network_fee(self) -> int:
        """
        Get current network fee from XRPL.
        
        Returns:
            Fee in drops
        """
        try:
            payload = {
                "method": "fee",
                "params": [{}]
            }
            response = requests.post(f"{self.api_url}", json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "drops" in data["result"]:
                # We can use open_ledger_fee for average rate
                return int(data["result"]["drops"]["open_ledger_fee"])
            
            logger.warning("Failed to get network fee from response")
            return XRP_DEFAULT_FEE
        except Exception as e:
            logger.warning(f"Failed to get network fee: {e}")
            return XRP_DEFAULT_FEE
    
    def _get_account_info(self, address: str) -> Dict[str, Any]:
        """
        Get account information for an XRP address.
        
        Args:
            address: XRP address
            
        Returns:
            Account information
        """
        try:
            payload = {
                "method": "account_info",
                "params": [{"account": address, "strict": True, "ledger_index": "current"}]
            }
            response = requests.post(f"{self.api_url}", json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "account_data" in data["result"]:
                return data["result"]["account_data"]
            
            logger.warning("Failed to get account info from response")
            return {}
        except Exception as e:
            logger.warning(f"Failed to get account info: {e}")
            return {}
    
    def _check_account_exists(self, address: str) -> bool:
        """
        Check if an XRP account exists.
        
        Args:
            address: XRP address
            
        Returns:
            True if account exists, False otherwise
        """
        try:
            payload = {
                "method": "account_info",
                "params": [{"account": address, "strict": True, "ledger_index": "current"}]
            }
            response = requests.post(f"{self.api_url}", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # If account exists, the result will be successful
                return "result" in data and "account_data" in data["result"]
            
            return False
        except Exception as e:
            logger.warning(f"Failed to check account existence: {e}")
            return True  # Safer to assume it exists if we can't check
    
    def _is_token_trustline_established(self, address: str, token_currency: str, token_issuer: str) -> bool:
        """
        Check if a trustline is established for a token.
        
        Args:
            address: XRP address
            token_currency: Token currency code
            token_issuer: Token issuer address
            
        Returns:
            True if trustline established, False otherwise
        """
        try:
            payload = {
                "method": "account_lines",
                "params": [
                    {
                        "account": address,
                        "peer": token_issuer,
                        "ledger_index": "current"
                    }
                ]
            }
            response = requests.post(f"{self.api_url}", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "result" in data and "lines" in data["result"]:
                    # Check if there's a trustline for this currency
                    for line in data["result"]["lines"]:
                        if (line.get("currency", "") == token_currency and 
                            line.get("account", "") == token_issuer):
                            return True
            
            return False
        except Exception as e:
            logger.warning(f"Failed to check trustline: {e}")
            return False
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native XRP transfer.
        
        Args:
            from_address: Source XRP address
            to_address: Destination XRP address
            amount: Amount to transfer in XRP
            
        Returns:
            Dict with fee estimation details
        """
        # Check if destination account exists
        destination_exists = self._check_account_exists(to_address)
        
        # Get current network fee
        base_fee = self._get_network_fee()
        
        # If destination doesn't exist, the first transaction needs to include
        # the reserve amount of XRP (currently 10 XRP)
        reserve_amount = 10 * XRP_DROPS_PER_XRP if not destination_exists else 0
        
        # Convert amount to drops
        amount_drops = int(Decimal(str(amount)) * Decimal(XRP_DROPS_PER_XRP))
        
        # XRP has a simple fee structure, but we'll create slow/avg/fast options
        # for consistency with other chains
        fee_options = {
            "slow": base_fee,
            "average": base_fee * 1.2,
            "fast": base_fee * 1.5
        }
        
        # Round fees to integers
        fee_options = {k: int(v) for k, v in fee_options.items()}
        
        # Get current XRP/USD price
        xrp_usd_price = self._get_xrp_usd_price()
        
        # Convert the fee to USD
        fee_in_xrp = base_fee / XRP_DROPS_PER_XRP
        usd_price = fee_in_xrp * xrp_usd_price if xrp_usd_price else None
        
        # Create priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_xrp": fee / XRP_DROPS_PER_XRP
            } for speed, fee in fee_options.items()
        }
        
        response = self.format_fee_response(
            fee=fee_options["average"],
            fee_currency="XRP",
            priority_options=priority_options,
            unit="drops",
            usd_price=usd_price
        )
        
        # Add XRP-specific details
        response["destination_exists"] = destination_exists
        if not destination_exists:
            response["reserve_required"] = reserve_amount
            response["reserve_required_xrp"] = reserve_amount / XRP_DROPS_PER_XRP
        
        return response
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for token transfer (IOU tokens in XRP).
        
        In XRP, tokens are specified by currency code and issuer address, 
        separated by a colon, e.g. "USD:rDsbeomae4FXwgQTJp9Rs64Qg9vDiTCdBv"
        
        Args:
            from_address: Source XRP address
            to_address: Destination XRP address
            amount: Amount to transfer in token units
            token_contract: Token identifier (currency:issuer)
            
        Returns:
            Dict with fee estimation details
        """
        # Parse token identifier
        if ":" not in token_contract:
            error_response = self.format_fee_response(
                fee=0,
                fee_currency="XRP",
                unit="drops"
            )
            error_response["error"] = "Invalid token format. Expected 'CURRENCY:ISSUER'"
            return error_response
        
        token_parts = token_contract.split(":")
        if len(token_parts) != 2:
            error_response = self.format_fee_response(
                fee=0,
                fee_currency="XRP",
                unit="drops"
            )
            error_response["error"] = "Invalid token format. Expected 'CURRENCY:ISSUER'"
            return error_response
            
        currency, issuer = token_parts
        
        # Check if destination account exists
        destination_exists = self._check_account_exists(to_address)
        
        # Check if trustline is established for the token
        trustline_exists = self._is_token_trustline_established(to_address, currency, issuer)
        
        # Get current network fee
        base_fee = self._get_network_fee()
        
        # For token transfers, if destination doesn't exist or trustline is not established,
        # these need to be set up in separate transactions
        
        # XRP has a simple fee structure, but we'll create slow/avg/fast options
        # for consistency with other chains
        fee_options = {
            "slow": base_fee,
            "average": base_fee * 1.2,
            "fast": base_fee * 1.5
        }
        
        # Round fees to integers
        fee_options = {k: int(v) for k, v in fee_options.items()}
        
        # Get current XRP/USD price
        xrp_usd_price = self._get_xrp_usd_price()
        
        # Convert the fee to USD
        fee_in_xrp = base_fee / XRP_DROPS_PER_XRP
        usd_price = fee_in_xrp * xrp_usd_price if xrp_usd_price else None
        
        # Create priority options
        priority_options = {
            speed: {
                "fee": fee,
                "fee_xrp": fee / XRP_DROPS_PER_XRP
            } for speed, fee in fee_options.items()
        }
        
        response = self.format_fee_response(
            fee=fee_options["average"],
            fee_currency="XRP",
            priority_options=priority_options,
            unit="drops",
            usd_price=usd_price
        )
        
        # Add XRP-specific details
        response["destination_exists"] = destination_exists
        response["trustline_exists"] = trustline_exists
        
        # If setting up is needed, estimate additional fees
        additional_fees = []
        
        if not destination_exists:
            # Account creation
            reserve_amount = 10 * XRP_DROPS_PER_XRP
            additional_fees.append({
                "type": "account_creation",
                "fee": base_fee,
                "reserve_required": reserve_amount,
                "reserve_required_xrp": reserve_amount / XRP_DROPS_PER_XRP
            })
        
        if not trustline_exists:
            # Trustline setup
            additional_fees.append({
                "type": "trustline_setup",
                "fee": base_fee,
                "currency": currency,
                "issuer": issuer
            })
        
        if additional_fees:
            response["additional_setup_fees"] = additional_fees
            
        return response
    
    def _get_xrp_usd_price(self) -> Optional[float]:
        """Get current XRP/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("ripple", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get XRP/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native XRP transfer.
    
    Args:
        from_address: Source XRP address
        to_address: Destination XRP address
        amount: Amount to transfer in XRP
        
    Returns:
        Dict with fee estimation details
    """
    estimator = XRPFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for token transfer (IOU tokens in XRP).
    
    In XRP, tokens are specified by currency code and issuer address, 
    separated by a colon, e.g. "USD:rDsbeomae4FXwgQTJp9Rs64Qg9vDiTCdBv"
    
    Args:
        from_address: Source XRP address
        to_address: Destination XRP address
        amount: Amount to transfer in token units
        token_contract: Token identifier (currency:issuer)
        
    Returns:
        Dict with fee estimation details
    """
    estimator = XRPFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 