import os
import requests
from typing import Dict, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta

from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class TatumHelper:
    """Helper class for Tatum API interactions"""
    
    def __init__(self):
        self.logger = get_logger(__file__)
        
        self.api_key = os.getenv('TATUM_API_KEY')
        if not self.api_key:
            raise RuntimeError("TATUM_API_KEY environment variable is not set")
            
        self.base_url = "https://api.tatum.io/v3"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
    @handle_api_errors
    def get_balance(self, blockchain_name: str, address: str) -> Tuple[Dict, Optional[str]]:
        """Get balance for an address using Tatum API"""
        try:
            # Normalize blockchain name for Tatum API
            chain = self._normalize_chain_name(blockchain_name)
            
            # Use correct blockchain names in endpoint URLs
            if chain == "eth":
                endpoint = f"/ethereum/account/balance/{address}"
            elif chain == "bsc":
                endpoint = f"/bsc/account/balance/{address}"
            else:
                endpoint = f"/{chain}/account/balance/{address}"
                
            self.logger.debug(f"Getting balance from Tatum endpoint: {endpoint}")
            return self._make_request('get', endpoint)
            
        except Exception as e:
            error_msg = f"Error getting balance from Tatum: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    @handle_api_errors
    def send_transaction(self, blockchain_name: str, sender_address: str, private_key: str,
                        recipient_address: str, amount: str, tx_details: Dict) -> Tuple[Dict, Optional[str]]:
        """Send a transaction using Tatum API"""
        try:
            chain = self._normalize_chain_name(blockchain_name)
            
            # Prepare request data
            request_data = {
                "from": sender_address,
                "to": recipient_address,
                "amount": amount,
                "fromPrivateKey": private_key
            }
            
            # Add blockchain-specific parameters
            if chain == "bsc":
                endpoint = "/bsc/transaction"
                if tx_details.get("contract_address"):
                    request_data["contractAddress"] = tx_details["contract_address"]
                request_data["fee"] = {
                    "gasLimit": tx_details.get("gas_limit", "21000"),
                    "gasPrice": tx_details.get("gas_price", "5")
                }
            elif chain == "eth":
                # For Ethereum, we expect a pre-signed transaction
                if not tx_details.get("signed_tx"):
                    return {}, "Missing signed transaction data for Ethereum"
                endpoint = "/ethereum/broadcast"
                request_data = {
                    "txData": tx_details["signed_tx"]
                }
            else:
                endpoint = f"/{chain}/transaction"
                if tx_details.get("contract_address"):
                    request_data["contractAddress"] = tx_details["contract_address"]
                    
            # Log request (without private key)
            safe_request_data = request_data.copy()
            if 'fromPrivateKey' in safe_request_data:
                safe_request_data['fromPrivateKey'] = '***'
            self.logger.debug(f"Sending {chain} transaction via Tatum")
            self.logger.debug(f"Request data: {safe_request_data}")
            
            # Send transaction
            response_data, error = self._make_request('post', endpoint, data=request_data)
            if error:
                return {}, error
                
            tx_hash = response_data.get('txId')
            if not tx_hash:
                return {}, "Transaction hash not found in response"
                
            return {
                "transaction_hash": tx_hash,
                "status": "pending"
            }, None
            
        except Exception as e:
            error_msg = f"Error sending transaction via Tatum: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    @handle_api_errors
    def check_transaction_status(self, blockchain_name: str, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Check transaction status using Tatum API"""
        try:
            chain = self._normalize_chain_name(blockchain_name)
            
            # Get transaction data
            tx_data, error = self.get_transaction(blockchain_name, tx_hash)
            if error:
                return "unknown", error
                
            # Different chains have different fields to check for confirmation
            if 'confirmations' in tx_data:
                confirmations = int(tx_data['confirmations'])
                if confirmations > 0:
                    return "confirmed", None
                return "pending", None
                
            elif 'status' in tx_data:
                status = tx_data['status'].lower()
                if status in ['confirmed', 'success']:
                    return "confirmed", None
                elif status in ['failed', 'error']:
                    return "failed", None
                return "pending", None
                
            return "unknown", "Could not determine transaction status"
            
        except Exception as e:
            error_msg = f"Error checking transaction status via Tatum: {str(e)}"
            self.logger.error(error_msg)
            return "unknown", error_msg
            
    @handle_api_errors
    def get_transaction(self, blockchain_name: str, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get transaction details using Tatum API"""
        try:
            chain = self._normalize_chain_name(blockchain_name)
            
            # Use correct blockchain names in endpoint URLs
            if chain == "eth":
                endpoint = f"/ethereum/transaction/{tx_hash}"
            elif chain == "bsc":
                endpoint = f"/bsc/transaction/{tx_hash}"
            else:
                endpoint = f"/{chain}/transaction/{tx_hash}"
                
            return self._make_request('get', endpoint)
            
        except Exception as e:
            error_msg = f"Error getting transaction details via Tatum: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[Dict, Optional[str]]:
        """Make request to Tatum API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            self.logger.debug(f"Making {method} request to {url}")
            
            if method.lower() == 'get':
                response = requests.get(url, headers=self.headers)
            elif method.lower() == 'post':
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return {}, f"Unsupported HTTP method: {method}"
                
            self.logger.debug(f"Response status code: {response.status_code}")
            self.logger.debug(f"Response body: {response.text}")
            
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"Tatum API error: {response.status_code}, {response.text}"
                self.logger.error(error_msg)
                return {}, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    def _normalize_chain_name(self, blockchain_name: str) -> str:
        """Normalize blockchain name for Tatum API"""
        name = blockchain_name.lower().strip()
        
        # Map common names to Tatum API names
        name_map = {
            "ethereum": "eth",
            "binance smart chain": "binance smart chain",
            "bsc": "binance smart chain",
            "bnb": "binance smart chain",
            "polygon": "polygon",
            "matic": "polygon",
            "tron": "tron",
            "trx": "tron"
        }
        
        return name_map.get(name, name)

    def get_chain_currency(self, blockchain_name: str) -> str:
        """Get the currency code for a blockchain"""
        # Normalize blockchain name
        blockchain_name = blockchain_name.lower().strip()
        
        # Special handling for Binance Smart Chain
        if blockchain_name in ["bsc", "binance smart chain", "binancesmartchain"]:
            return "BNB"
        
        # Map common names to Tatum API names
        name_map = {
            "ethereum": "ETH",
            "polygon": "MATIC",
            "tron": "TRX"
        }
        
        return name_map.get(blockchain_name, blockchain_name.upper()) 