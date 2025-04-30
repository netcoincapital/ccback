"""Solana transaction fee estimator module."""

from typing import Dict, Any, Optional, List
import base64
import struct
import requests

from .base import FeeEstimator, APIClient, logger

# Constants
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
SOLANA_DEFAULT_PRIORITY_FEE = 4000  # 4000 micro-lamports per compute unit
SOL_TRANSFER_COMPUTE_UNITS = 200000  # Base compute units for SOL transfer
SPL_TRANSFER_COMPUTE_UNITS = 250000  # Base compute units for SPL token transfer
LAMPORTS_PER_SOL = 1_000_000_000     # 1 SOL = 10^9 lamports
DEFAULT_FEE = 5000                    # Default fee in lamports


class SolanaFeeEstimator(FeeEstimator):
    """Solana fee estimator for SOL and SPL token transfers."""
    
    def __init__(self, rpc_url: str = SOLANA_RPC_URL):
        """
        Initialize the Solana fee estimator.
        
        Args:
            rpc_url: Solana RPC URL
        """
        self.rpc_url = rpc_url
        self.client = APIClient(base_url=rpc_url, rate_limit=1.0)  # 1 req/sec
    
    def _get_recent_blockhash(self) -> str:
        """
        Get recent blockhash from the Solana network.
        
        Returns:
            Recent blockhash as string
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getRecentBlockhash"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "value" in data["result"]:
                return data["result"]["value"]["blockhash"]
            
            logger.warning("Failed to get recent blockhash from response")
            return ""
        except Exception as e:
            logger.warning(f"Failed to get recent blockhash: {e}")
            return ""
    
    def _get_priority_fee_estimate(self) -> int:
        """
        Get estimated priority fee from Solana network.
        
        Returns:
            Priority fee in micro-lamports per compute unit
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getRecentPrioritizationFees"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and isinstance(data["result"], list) and data["result"]:
                # Take average of recent priority fees
                fees = [fee["prioritizationFee"] for fee in data["result"]]
                avg_fee = sum(fees) / len(fees)
                return int(avg_fee)
            
            logger.warning("Failed to get priority fees from response")
            return SOLANA_DEFAULT_PRIORITY_FEE
        except Exception as e:
            logger.warning(f"Failed to get priority fees: {e}")
            return SOLANA_DEFAULT_PRIORITY_FEE
    
    def _check_token_account_exists(self, wallet_address: str, token_mint: str) -> bool:
        """
        Check if token account exists for the given wallet and token mint.
        
        Args:
            wallet_address: Wallet address
            token_mint: Token mint address
            
        Returns:
            True if token account exists, False otherwise
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"mint": token_mint},
                    {"encoding": "jsonParsed"}
                ]
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "value" in data["result"]:
                return len(data["result"]["value"]) > 0
            
            return False
        except Exception as e:
            logger.warning(f"Failed to check token account: {e}")
            # Assume it doesn't exist for safety
            return False
    
    def _simulate_transaction(self, from_address: str, to_address: str, 
                             is_token_transfer: bool = False, token_mint: Optional[str] = None) -> Dict[str, Any]:
        """
        Simulate a transaction to get more accurate fee estimate.
        This is a simplified implementation - in production you would build
        and simulate an actual transaction.
        
        Args:
            from_address: Source address
            to_address: Destination address
            is_token_transfer: Whether it's a token transfer
            token_mint: Token mint address for token transfers
            
        Returns:
            Simulation result with units and fee
        """
        # In a real implementation, you would:
        # 1. Build a real transaction using the Solana web3.js library or solana-py
        # 2. Serialize the transaction
        # 3. Send it to simulateTransaction RPC method
        
        # For this example, we'll estimate based on typical values
        if is_token_transfer:
            compute_units = SPL_TRANSFER_COMPUTE_UNITS
            # Check if destination token account exists
            needs_account_creation = not self._check_token_account_exists(to_address, token_mint) if token_mint else True
            
            # If token account needs to be created, add more compute units
            if needs_account_creation:
                compute_units += 150000  # Additional units for account creation
        else:
            compute_units = SOL_TRANSFER_COMPUTE_UNITS
        
        # Get priority fee (micro-lamports per compute unit)
        priority_fee = self._get_priority_fee_estimate()
        
        # Calculate total priority fee in lamports
        total_priority_fee = (priority_fee * compute_units) // 1_000_000
        
        # Base fee (5000 lamports) + priority fee
        total_fee = DEFAULT_FEE + total_priority_fee
        
        return {
            "compute_units": compute_units,
            "fee": total_fee,
            "priority_fee_per_cu": priority_fee
        }
    
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native SOL transfer.
        
        Args:
            from_address: Source Solana address
            to_address: Destination Solana address
            amount: Amount to transfer in SOL
            
        Returns:
            Dict with fee estimation details
        """
        # Simulate the transaction
        simulation = self._simulate_transaction(from_address, to_address)
        
        # Get SOL price for USD conversion
        sol_usd_price = self._get_sol_usd_price()
        
        # Calculate USD price
        fee_in_sol = simulation["fee"] / LAMPORTS_PER_SOL
        usd_price = fee_in_sol * sol_usd_price if sol_usd_price else None
        
        # Create "tiered" fee options
        # Solana doesn't have tiered gas like Ethereum, but we include this for API consistency
        # We'll simulate price options by adjusting priority fee
        priority_fee = simulation["priority_fee_per_cu"]
        
        priority_options = {
            "slow": {
                "fee": int(DEFAULT_FEE + ((priority_fee * 0.8 * simulation["compute_units"]) // 1_000_000)),
                "fee_sol": (DEFAULT_FEE + ((priority_fee * 0.8 * simulation["compute_units"]) // 1_000_000)) / LAMPORTS_PER_SOL
            },
            "average": {
                "fee": simulation["fee"],
                "fee_sol": simulation["fee"] / LAMPORTS_PER_SOL
            },
            "fast": {
                "fee": int(DEFAULT_FEE + ((priority_fee * 1.5 * simulation["compute_units"]) // 1_000_000)),
                "fee_sol": (DEFAULT_FEE + ((priority_fee * 1.5 * simulation["compute_units"]) // 1_000_000)) / LAMPORTS_PER_SOL
            }
        }
        
        return self.format_fee_response(
            fee=simulation["fee"],
            fee_currency="SOL",
            priority_options=priority_options,
            unit="lamports",
            usd_price=usd_price
        )
    
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for SPL token transfer.
        
        Args:
            from_address: Source Solana address
            to_address: Destination Solana address
            amount: Amount to transfer in token units
            token_contract: Token mint address
            
        Returns:
            Dict with fee estimation details
        """
        # Simulate the token transfer transaction
        simulation = self._simulate_transaction(
            from_address, to_address, 
            is_token_transfer=True, 
            token_mint=token_contract
        )
        
        # Get SOL price for USD conversion
        sol_usd_price = self._get_sol_usd_price()
        
        # Calculate USD price
        fee_in_sol = simulation["fee"] / LAMPORTS_PER_SOL
        usd_price = fee_in_sol * sol_usd_price if sol_usd_price else None
        
        # Create "tiered" fee options (similar to native transfer)
        priority_fee = simulation["priority_fee_per_cu"]
        
        priority_options = {
            "slow": {
                "fee": int(DEFAULT_FEE + ((priority_fee * 0.8 * simulation["compute_units"]) // 1_000_000)),
                "fee_sol": (DEFAULT_FEE + ((priority_fee * 0.8 * simulation["compute_units"]) // 1_000_000)) / LAMPORTS_PER_SOL
            },
            "average": {
                "fee": simulation["fee"],
                "fee_sol": simulation["fee"] / LAMPORTS_PER_SOL
            },
            "fast": {
                "fee": int(DEFAULT_FEE + ((priority_fee * 1.5 * simulation["compute_units"]) // 1_000_000)),
                "fee_sol": (DEFAULT_FEE + ((priority_fee * 1.5 * simulation["compute_units"]) // 1_000_000)) / LAMPORTS_PER_SOL
            }
        }
        
        response = self.format_fee_response(
            fee=simulation["fee"],
            fee_currency="SOL",
            priority_options=priority_options,
            unit="lamports",
            usd_price=usd_price
        )
        
        # Add Solana-specific details
        needs_account_creation = not self._check_token_account_exists(to_address, token_contract)
        response["token_account_creation_needed"] = needs_account_creation
        
        if needs_account_creation:
            # In real implementation, get the actual rent exemption amount
            # This is an approximation
            rent_exemption = 2_039_280  # Typical SPL token account rent exemption
            response["rent_exemption_fee"] = rent_exemption
            
        return response
    
    def _get_sol_usd_price(self) -> Optional[float]:
        """Get current SOL/USD price."""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                timeout=10
            )
            data = response.json()
            return data.get("solana", {}).get("usd")
        except Exception as e:
            logger.warning(f"Failed to get SOL/USD price: {e}")
            return None


# Function exports for direct use
def estimate_native_fee(from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
    """
    Estimate fee for native SOL transfer.
    
    Args:
        from_address: Source Solana address
        to_address: Destination Solana address
        amount: Amount to transfer in SOL
        
    Returns:
        Dict with fee estimation details
    """
    estimator = SolanaFeeEstimator()
    return estimator.estimate_native_fee(from_address, to_address, amount)


def estimate_token_fee(from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
    """
    Estimate fee for SPL token transfer.
    
    Args:
        from_address: Source Solana address
        to_address: Destination Solana address
        amount: Amount to transfer in token units
        token_contract: Token mint address
        
    Returns:
        Dict with fee estimation details
    """
    estimator = SolanaFeeEstimator()
    return estimator.estimate_token_fee(from_address, to_address, amount, token_contract) 