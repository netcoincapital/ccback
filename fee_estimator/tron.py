"""TRON transaction fee estimator module."""

from typing import Dict, Any, Optional
import json
import requests
from decimal import Decimal

from .base import FeeEstimator, APIClient, logger

# Constants
TRONGRID_API = "https://api.trongrid.io"
ENERGY_PRICE = 420  # Sun per energy unit
BANDWIDTH_PRICE = 1000  # Sun per bandwidth unit
TRX_TRANSFER_BANDWIDTH = 300  # Bandwidth points for TRX transfer
TRC20_TRANSFER_ENERGY = 42000  # Estimated energy for TRC20 transfer
ACTIVATION_FEE = 1_000_000  # 1 TRX in Sun - account activation fee


class TronFeeEstimator(FeeEstimator):
    """TRON fee estimator for TRX and TRC20 tokens."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TRON fee estimator.
        
        Args:
            api_key: TronGrid API key (for increased rate limits)
        """
        self.api_key = api_key
        self.headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
        self.client = APIClient(base_url=TRONGRID_API, rate_limit=0.5)  # 2 req/sec
    
    def _get_account_info(self, address: str) -> Dict[str, Any]:
        """
        Get account information including resources (energy, bandwidth).
        
        Args:
            address: TRON address
            
        Returns:
            Account information dict
        """
        try:
            url = f"{TRONGRID_API}/wallet/getaccountresource"
            payload = {"address": address, "visible": True}
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to get account resources: {e}")
            return {}
    
    def _check_account_exists(self, address: str) -> bool:
        """
        Check if an account exists on the TRON blockchain.
        
        Args:
            address: TRON address
            
        Returns:
            True if account exists, False otherwise
        """
        try:
            url = f"{TRONGRID_API}/wallet/getaccount"
            payload = {"address": address, "visible": True}
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # If address exists, response will contain account data
                return bool(data)
            return False
        except Exception as e:
            logger.warning(f"Failed to check account existence: {e}")
            return True  # Safer to assume it exists if we can't check
    
    def _check_is_trc20_token(self, token_contract: str) -> bool:
        """
        Check if a token is a TRC20 token.
        
        Args:
            token_contract: Token contract address
            
        Returns:
            True if it's a TRC20 token, False otherwise
        """
        try:
            url = f"{TRONGRID_API}/wallet/getcontract"
            payload = {"value": token_contract, "visible": True}
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Check for TRC20 interface implementation
                return "name" in data and "abi" in data
            return False
        except Exception as e:
            logger.warning(f"Failed to check TRC20 token status: {e}")
            return True  # Assume it's a token if we can't check
    
    def _estimate_trx_fee(self, from_address: str, to_address: str) -> Dict[str, Any]:
        """
        Estimate fee for TRX transfer.
        
        Args:
            from_address: Source TRON address
            to_address: Destination TRON address
            
        Returns:
            Fee estimation details
        """
        is_new_account = not self._check_account_exists(to_address)
        account_info = self._get_account_info(from_address)
        
        # Check free bandwidth
        free_bandwidth = account_info.get("freeNetUsed", 0)
        free_bandwidth_limit = account_info.get("freeNetLimit", 0)
        available_free_bandwidth = free_bandwidth_limit - free_bandwidth
        
        # Calculate bandwidth needed
        bandwidth_needed = TRX_TRANSFER_BANDWIDTH
        bandwidth_fee = 0
        
        # If free bandwidth is insufficient, calculate the fee
        if available_free_bandwidth < bandwidth_needed:
            bandwidth_to_buy = bandwidth_needed - available_free_bandwidth
            bandwidth_fee = bandwidth_to_buy * BANDWIDTH_PRICE
        
        # Account activation fee if target account doesn't exist
        activation_fee = ACTIVATION_FEE if is_new_account else 0
        
        # Total fee in Sun
        total_fee = bandwidth_fee + activation_fee
        
        return {
            "bandwidth_fee": bandwidth_fee,
            "activation_fee": activation_fee,
            "total_fee": total_fee,
            "is_new_account": is_new_account
        }
    
    def _estimate_trc20_fee(self, from_address: str, to_address: str, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for TRC20 token transfer.
        
        Args:
            from_address: Source TRON address
            to_address: Destination TRON address
            token_contract: Token contract address
            
        Returns:
            Fee estimation details
        """
        is_new_account = not self._check_account_exists(to_address)
        account_info = self._get_account_info(from_address)
        
        # Check if the token is a TRC20 token
        is_trc20 = self._check_is_trc20_token(token_contract)
        if not is_trc20:
            logger.warning(f"Token {token_contract} is not a TRC20 token")
            return {"error": "Token is not a valid TRC20 token"}
        
        # Check available energy
        energy_limit = account_info.get("EnergyLimit", 0)
        energy_used = account_info.get("EnergyUsed", 0)
        available_energy = energy_limit - energy_used
        
        # Estimate energy needed
        energy_needed = TRC20_TRANSFER_ENERGY
        energy_fee = 0
        
        # If available energy is insufficient, calculate the energy fee
        if available_energy < energy_needed:
            energy_to_buy = energy_needed - available_energy
            energy_fee = energy_to_buy * ENERGY_PRICE
        
        # Account activation fee if target account doesn't exist
        activation_fee = ACTIVATION_FEE if is_new_account else 0
        
        # Total fee in Sun
        total_fee = energy_fee + activation_fee
        
        return {
            "energy_fee": energy_fee,
            "activation_fee": activation_fee,
            "total_fee": total_fee,
            "is_new_account": is_new_account
        }
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native TRX transfer.
        
        Args:
            from_address: Source TRON address
            to_address: Destination TRON address
            amount: Amount to transfer in TRX
            
        Returns:
            Dict with fee estimation details
        """
        fee_details = self._estimate_trx_fee(from_address, to_address)
        
        # Get current TRX/USD price
        trx_usd_price = self._get_trx_usd_price()
        
        # Convert the fee to USD
        total_fee_trx = fee_details["total_fee"] / 1_000_000  # Convert Sun to TRX
        usd_price = total_fee_trx * trx_usd_price if trx_usd_price else None
        
        # Create priority options (TRON doesn't have priority, but keeping consistent API)
        priority_options = {
            "slow": {"fee": fee_details["total_fee"]},
            "average": {"fee": fee_details["total_fee"]},
            "fast": {"fee": fee_details["total_fee"]}
        }
        
        response = self.format_fee_response(
            fee=fee_details["total_fee"],
            fee_currency="TRX",
            priority_options=priority_options,
            unit="sun",
            usd_price=usd_price
        )
        
        # Add TRON-specific details
        response["activation_required"] = fee_details["is_new_account"]
        if fee_details["is_new_account"]:
            response["activation_fee"] = fee_details["activation_fee"]
        
        response["bandwidth_fee"] = fee_details["bandwidth_fee"]
        
        return response
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for TRC20 token transfer.
        
        Args:
            from_address: Source TRON address
            to_address: Destination TRON address
            amount: Amount to transfer in token units
            token_contract: Token contract address
            
        Returns:
            Dict with fee estimation details
        """
        fee_details = self._estimate_trc20_fee(from_address, to_address, token_contract)
        
        # Check for errors
        if "error" in fee_details:
            response = self.format_fee_response(
                fee=0,
                fee_currency="TRX",
                unit="sun"
            )
            response["error"] = fee_details["error"]
            return response
        
        # Get current TRX/USD price
        trx_usd_price = self._get_trx_usd_price()
        
        # Convert the fee to USD
        total_fee_trx = fee_details["total_fee"] / 1_000_000  # Convert Sun to TRX
        usd_price = total_fee_trx * trx_usd_price if trx_usd_price else None
        
        # Create priority options (TRON doesn't have priority, but keeping consistent API)
        priority_options = {
            "slow": {"fee": fee_details["total_fee"]},
            "average": {"fee": fee_details["total_fee"]},
            "fast": {"fee": fee_details["total_fee"]}
        }
        
        response = self.format_fee_response(
            fee=fee_details["total_fee"],
            fee_currency="TRX",
            priority_options=priority_options,
            unit="sun",
            usd_price=usd_price
        )
        
        # Add TRON-specific details
        response["activation_required"] = fee_details["is_new_account"]
        if fee_details["is_new_account"]:
            response["activation_fee"] = fee_details["activation_fee"]
        
        response["energy_fee"] = fee_details["energy_fee"]
        
        return response
    
    def _get_trx_usd_price(self) -> Optional[float]:
        """Get current TRX/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("tron", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get TRX/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native TRX transfer.
    
    Args:
        from_address: Source TRON address
        to_address: Destination TRON address
        amount: Amount to transfer in TRX
        
    Returns:
        Dict with fee estimation details
    """
    estimator = TronFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for TRC20 token transfer.
    
    Args:
        from_address: Source TRON address
        to_address: Destination TRON address
        amount: Amount to transfer in token units
        token_contract: Token contract address
        
    Returns:
        Dict with fee estimation details
    """
    estimator = TronFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 