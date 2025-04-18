import requests
import logging
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)

class TatumService:
    """Service class for interacting with Tatum API"""
    
    def __init__(self, api_key):
        """Initialize with Tatum API key"""
        self.api_key = api_key
        self.base_url = "https://api.tatum.io/v4"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Mapping blockchain names to Tatum chain identifiers
        self.chain_mapping = {
            "ethereum": "ethereum",
            "bitcoin": "bitcoin",
            "tron": "tron",
            "binance": "bsc",
            "polygon": "polygon",
            "avalanche": "avalanche",
            "arbitrum": "arbitrum",
            "polkadot": "polkadot",
            "xrp": "xrp",
            "solana": "solana"
        }
        
    def _get_chain_name(self, blockchain_name: str) -> str:
        """Convert blockchain name to Tatum chain identifier"""
        return self.chain_mapping.get(blockchain_name.lower(), blockchain_name.lower())
    
    def _make_request(self, method: str, endpoint: str, params=None, data=None) -> Tuple[Optional[Dict], Optional[str]]:
        """Make request to Tatum API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.lower() == 'get':
                response = requests.get(url, headers=self.headers, params=params)
            elif method.lower() == 'post':
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return None, f"Unsupported HTTP method: {method}"
                
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"Tatum API error: {response.status_code}, {response.text}"
                logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            error_msg = f"Error calling Tatum API: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def get_balance(self, blockchain_name: str, address: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get balance for an address"""
        chain = self._get_chain_name(blockchain_name)
        endpoint = f"/data/balances/{chain}/{address}"
        
        return self._make_request('get', endpoint)
    
    def validate_address(self, blockchain_name: str, address: str) -> bool:
        """Validate if an address is valid for a specific blockchain"""
        # Basic validation based on blockchain rules
        if blockchain_name.lower() == 'bitcoin' and (address.startswith('1') or address.startswith('3') or address.startswith('bc1')):
            return len(address) >= 26 and len(address) <= 35
        
        elif blockchain_name.lower() == 'ethereum' or blockchain_name.lower() in ['binance', 'polygon', 'avalanche', 'arbitrum']:
            return address.startswith('0x') and len(address) == 42
            
        elif blockchain_name.lower() == 'tron':
            return address.startswith('T') and len(address) == 34
            
        elif blockchain_name.lower() == 'solana':
            return len(address) >= 32 and len(address) <= 44
            
        elif blockchain_name.lower() == 'xrp':
            return address.startswith('r') and len(address) >= 25 and len(address) <= 35
            
        # For others, we'll just perform a basic length check
        return len(address) >= 10 and len(address) <= 100
    
    def get_transaction(self, blockchain_name: str, tx_hash: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get transaction details by hash"""
        chain = self._get_chain_name(blockchain_name)
        endpoint = f"/data/transactions/{chain}/{tx_hash}"
        
        return self._make_request('get', endpoint)
    
    def prepare_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                           recipient_address: str, amount: str, smart_contract_address=None) -> Tuple[Dict, Optional[str]]:
        """Prepare a transaction for sending"""
        chain = self._get_chain_name(blockchain_name)
        
        # Validate recipient address
        if not self.validate_address(blockchain_name, recipient_address):
            return {}, f"Invalid {blockchain_name} recipient address"
        
        try:
            # Get current balance of sender
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            if error:
                return {}, f"Error fetching balance: {error}"
            
            # Extract balance for the specific token or native currency
            sender_balance = 0
            if 'balances' in balance_data:
                for balance in balance_data['balances']:
                    if smart_contract_address and 'tokenAddress' in balance and balance['tokenAddress'].lower() == smart_contract_address.lower():
                        sender_balance = float(balance['balance'])
                        break
                    elif not smart_contract_address and ('type' in balance and balance['type'] == 'native'):
                        sender_balance = float(balance['balance'])
                        break
            
            # Check if balance is sufficient
            amount_float = float(amount)
            if amount_float > sender_balance:
                return {}, f"Insufficient balance: {sender_balance} < {amount_float}"
            
            # Estimate gas fee (this is a simplified example)
            estimated_fee = 0.001  # This should be calculated properly based on the blockchain
            
            # Calculate balance after transaction
            balance_after = sender_balance - amount_float - estimated_fee
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "sender_balance_before": str(sender_balance),
                "estimated_fee": str(estimated_fee),
                "balance_after_tx": str(balance_after),
                "is_token": bool(smart_contract_address),
                "contract_address": smart_contract_address,
                "chain": chain
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error preparing transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def send_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                        recipient_address: str, amount: str, tx_details: Dict) -> Tuple[Dict, Optional[str]]:
        """Send a transaction using Tatum API"""
        chain = self._get_chain_name(blockchain_name)
        
        try:
            # Prepare the request body based on blockchain type and token status
            request_data = {}
            endpoint = ""
            
            is_token = tx_details.get('is_token', False)
            contract_address = tx_details.get('contract_address')
            
            # Create transaction based on blockchain and token type
            if chain == "ethereum" or chain in ["bsc", "polygon", "avalanche", "arbitrum"]:
                if is_token:
                    endpoint = f"/blockchain/token/transaction"
                    request_data = {
                        "chain": chain,
                        "to": recipient_address,
                        "amount": amount,
                        "contractAddress": contract_address,
                        "fromPrivateKey": private_key
                    }
                else:
                    endpoint = f"/blockchain/transaction"
                    request_data = {
                        "chain": chain,
                        "to": recipient_address,
                        "amount": amount,
                        "fromPrivateKey": private_key
                    }
            
            elif chain == "bitcoin":
                endpoint = f"/blockchain/transaction"
                request_data = {
                    "chain": chain,
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key
                }
                
            elif chain == "tron":
                if is_token:
                    endpoint = f"/blockchain/token/transaction"
                    request_data = {
                        "chain": chain,
                        "to": recipient_address,
                        "amount": amount,
                        "contractAddress": contract_address,
                        "fromPrivateKey": private_key
                    }
                else:
                    endpoint = f"/blockchain/transaction"
                    request_data = {
                        "chain": chain,
                        "to": recipient_address,
                        "amount": amount,
                        "fromPrivateKey": private_key
                    }
                    
            elif chain in ["solana", "xrp", "polkadot"]:
                endpoint = f"/blockchain/transaction"
                request_data = {
                    "chain": chain,
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key
                }
            
            # Send transaction
            response_data, error = self._make_request('post', endpoint, data=request_data)
            
            if error:
                return {}, error
                
            # Extract transaction hash from response
            tx_hash = response_data.get('txId')
            
            if not tx_hash:
                return {}, "Transaction hash not found in response"
                
            # Get updated balance
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            sender_balance_after = "Unknown"
            
            if not error and 'balances' in balance_data:
                for balance in balance_data['balances']:
                    if is_token and 'tokenAddress' in balance and balance['tokenAddress'].lower() == contract_address.lower():
                        sender_balance_after = balance['balance']
                        break
                    elif not is_token and ('type' in balance and balance['type'] == 'native'):
                        sender_balance_after = balance['balance']
                        break
            
            # Prepare result
            result = {
                "transaction_hash": tx_hash,
                "actual_fee": tx_details.get('estimated_fee', "Unknown"),  # In real implementation, get actual fee
                "sender_balance_after": sender_balance_after,
                "status": "Unconfirmed",
                "description": "Transaction has been submitted to the blockchain network and is waiting to be processed."
            }
            
            return result, None
            
        except Exception as e:
            error_msg = f"Error sending transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def check_transaction_status(self, blockchain_name: str, tx_hash: str) -> Tuple[str, str]:
        """Check the status of a transaction"""
        chain = self._get_chain_name(blockchain_name)
        
        try:
            # Get transaction data
            tx_data, error = self.get_transaction(blockchain_name, tx_hash)
            
            if error:
                return "Unknown", f"Could not check transaction status: {error}"
                
            # Different chains have different fields to check for confirmation
            if 'confirmations' in tx_data:
                confirmations = int(tx_data['confirmations'])
                
                if confirmations > 0:
                    return "Confirmed", f"Transaction confirmed with {confirmations} confirmations"
                else:
                    return "Unconfirmed", "Transaction is in mempool, waiting to be included in a block"
                    
            elif 'status' in tx_data:
                status = tx_data['status']
                
                if status.lower() == 'confirmed' or status.lower() == 'success':
                    return "Confirmed", "Transaction confirmed"
                elif status.lower() == 'failed' or status.lower() == 'error':
                    return "Failed", "Transaction failed"
                else:
                    return "Unconfirmed", f"Transaction status: {status}"
            
            # Default response if we can't determine status
            return "Unknown", "Could not determine transaction status"
            
        except Exception as e:
            error_msg = f"Error checking transaction status: {str(e)}"
            logger.error(error_msg)
            return "Unknown", error_msg 