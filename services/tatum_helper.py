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
            if chain == "ethereum":
                endpoint = f"/ethereum/account/balance/{address}"
            elif chain == "binance smart chain":
                endpoint = f"/binance smart chain/account/balance/{address}"
            else:
                endpoint = f"/{chain}/account/balance/{address}"
                
            self.logger.debug(f"Getting balance from Tatum endpoint: {endpoint}")
            return self._make_request('get', endpoint)
            
        except Exception as e:
            error_msg = f"Error getting balance from Tatum: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    @handle_api_errors
    def send_transaction(self, blockchain_name: str, sender_address: str, 
                       recipient_address: str, amount: str, private_key: str = None,
                       tx_details: Dict = None) -> Tuple[Dict, Optional[str]]:
        """Send a transaction using Tatum API broadcast endpoints"""
        try:
            if tx_details is None:
                tx_details = {}
            
            # Make sure amount is a string, not Decimal
            if not isinstance(amount, str):
                self.logger.warning(f"Converting amount from {type(amount)} to string")
                amount = str(amount)
                
            # Normalize blockchain name
            chain = self._normalize_chain_name(blockchain_name)
            
            # Get the appropriate broadcast endpoint for this blockchain
            broadcast_endpoint, request_data = self._get_broadcast_params(
                chain, 
                sender_address, 
                recipient_address, 
                amount, 
                private_key, 
                tx_details
            )
            
            # Remove private key from request data before logging
            safe_request_data = self._sanitize_request_data(request_data)
            self.logger.debug(f"Sending {chain} transaction via Tatum")
            self.logger.debug(f"Using endpoint: {broadcast_endpoint}")
            self.logger.debug(f"Request data: {safe_request_data}")
            
            # Send transaction
            response_data, error = self._make_request('post', broadcast_endpoint, data=request_data)
            if error:
                return {}, error
                
            # Extract transaction hash from response
            tx_hash = self._extract_tx_hash(response_data)
            if not tx_hash:
                self.logger.error(f"Transaction hash not found in response: {response_data}")
                return {}, "Transaction hash not found in response"
                
            return {
                "transaction_hash": tx_hash,
                "txId": tx_hash,
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
            if chain == "ethereum":
                endpoint = f"/ethereum/transaction/{tx_hash}"
            elif chain == "binance smart chain":
                endpoint = f"/binance smart chain/transaction/{tx_hash}"
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
            
            # CRITICAL BSC DEBUG: یافتن خطای BSC
            if data and ('blockchain' in data or 'blockchain_name' in data):
                blockchain = data.get('blockchain', data.get('blockchain_name', ''))
                if blockchain and blockchain.lower() in ['bsc', 'binance smart chain', 'binance-smart-chain', 'bnb']:
                    self.logger.warning(f"🔎 BSC DEBUG: BSC request detected in tatum_helper._make_request")
                    self.logger.warning(f"🔎 BSC DEBUG: Endpoint: {endpoint}")
                    self.logger.warning(f"🔎 BSC DEBUG: Data: {data}")
                    
                    # اگر BSC در endpoint عمومی استفاده شده، آن را به اتریوم تغییر می‌دهیم
                    if '/bsc/' not in endpoint.lower():
                        self.logger.warning(f"🔴 EMERGENCY HOTFIX: Converting BSC request to Ethereum in tatum_helper")
                        if 'blockchain' in data:
                            data['blockchain'] = 'ethereum'
                        if 'blockchain_name' in data:
                            data['blockchain_name'] = 'ethereum'
            
            # بررسی و اصلاح endpoint برای BSC
            if '/bsc/' not in endpoint.lower() and 'blockchain' in (data or {}) and (data.get('blockchain', '').lower() == 'bsc' or data.get('blockchain_name', '').lower() == 'bsc'):
                self.logger.warning(f"Detected BSC blockchain in generic endpoint. Should use /bsc/ specific endpoint instead.")
                if '/transaction' in endpoint:
                    # تغییر به endpoint مخصوص BSC
                    url = f"{self.base_url}/bsc/transaction"
                    self.logger.warning(f"Redirecting to BSC-specific endpoint: {url}")
                elif '/gas' in endpoint:
                    # تغییر به endpoint مخصوص BSC gas
                    url = f"{self.base_url}/bsc/gas"
                    self.logger.warning(f"Redirecting to BSC-specific gas endpoint: {url}")
                    # حذف فیلد blockchain از درخواست چون در endpoint بی اس سی به آن نیازی نیست
                    if data and 'blockchain' in data:
                        del data['blockchain']
            
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
        
        # Map of common variations to standard names
        name_mapping = {
            "eth": "ethereum",
            "btc": "bitcoin",
            "bnb": "binance-smart-chain",
            "binance": "binance-smart-chain",
            "bsc": "binance-smart-chain",
            "bnb smart chain": "binance-smart-chain",
            "binance smart chain": "binance-smart-chain",
            "binancecoin": "binance-smart-chain",
            "matic": "polygon",
            "xrp": "ripple",
            "xlm": "stellar",
            "avax": "avalanche",
            "arb": "arbitrum",
            "dot": "polkadot",
            "ada": "cardano",
            "trx": "tron"
        }
        
        return name_mapping.get(name, name)

    def get_chain_currency(self, blockchain_name: str) -> str:
        """Get the currency code for a blockchain"""
        # Normalize blockchain name
        blockchain_name = blockchain_name.lower().strip()
        
        # Special handling for Binance Smart Chain
        if blockchain_name in ["bsc", "binance-smart-chain", "binancesmartchain"]:
            return "BNB"
        
        # Map common names to Tatum API names
        name_map = {
            "ethereum": "ETH",
            "polygon": "MATIC",
            "tron": "TRX"
        }
        
        return name_map.get(blockchain_name, blockchain_name.upper())

    def _sanitize_request_data(self, request_data: Dict) -> Dict:
        """Remove sensitive data from request data for logging"""
        if not request_data:
            return {}
            
        safe_data = request_data.copy()
        sensitive_fields = ['fromPrivateKey', 'privateKey', 'fromSecret', 'secret', 'password']
        
        for field in sensitive_fields:
            if field in safe_data:
                safe_data[field] = '***'
                
        return safe_data
        
    def _get_broadcast_params(self, chain: str, sender: str, recipient: str, 
                             amount: str, private_key: str, tx_details: Dict) -> Tuple[str, Dict]:
        """Get the broadcast endpoint and request data for a specific blockchain"""
        # Default structure for most blockchains
        signed_tx = tx_details.get("signed_tx")
        
        # Define broadcast endpoints for each blockchain
        endpoints = {
            "ethereum": "/ethereum/broadcast",
            "binance-smart-chain": "/bsc/broadcast",
            "tron": "/tron/broadcast",
            "bitcoin": "/bitcoin/broadcast",
            "polygon": "/polygon/broadcast",
            "ripple": "/xrp/broadcast",
            "solana": "/solana/broadcast/confirm",
            "avalanche": "/avalanche/broadcast",
            "arbitrum": "/arb/broadcast"
        }
        
        # Get the correct endpoint
        endpoint = endpoints.get(chain)
        if not endpoint:
            endpoint = f"/{chain}/broadcast" 
            self.logger.warning(f"Using default broadcast endpoint pattern for {chain}")
            
        # For blockchains that need raw transaction data
        if signed_tx:
            return endpoint, {"txData": signed_tx}
            
        # Some blockchains have different request formats for broadcasting
        if chain == "ripple" or chain == "xrp":
            request_data = {
                "from": sender,
                "to": recipient,
                "amount": amount,
                "fromSecret": private_key
            }
        elif chain == "solana":
            request_data = {
                "signatureId": tx_details.get("signature_id"),
                "serializedTransaction": tx_details.get("serialized_tx")
            }
        else:
            # Standard request format
            request_data = {
                "from": sender,
                "to": recipient,
                "amount": amount,
                "fromPrivateKey": private_key
            }
            
            # Add contract address for token transfers
            if tx_details.get("contract_address"):
                request_data["contractAddress"] = tx_details.get("contract_address")
                
        return endpoint, request_data
        
    def _extract_tx_hash(self, response_data: Dict) -> Optional[str]:
        """Extract transaction hash from Tatum API response"""
        if not response_data:
            return None
            
        # Different API endpoints use different field names
        hash_fields = ['txId', 'transactionHash', 'hash', 'id', 'result']
        
        for field in hash_fields:
            if field in response_data:
                tx_hash = response_data[field]
                if isinstance(tx_hash, str):
                    return tx_hash
                elif isinstance(tx_hash, dict) and 'txId' in tx_hash:
                    return tx_hash['txId']
                    
        return None 