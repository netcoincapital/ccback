from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
import requests
import traceback
from datetime import datetime, timedelta
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class BSCService(BaseBlockchainService):
    """Binance Smart Chain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Default BSC node URLs if environment variable is not set
        DEFAULT_BSC_NODES = [
            "https://bsc-dataseed.binance.org",
            "https://bsc-dataseed1.binance.org",
            "https://bsc-dataseed2.binance.org",
            "https://bsc-dataseed3.binance.org",
            "https://bsc-dataseed4.binance.org"
        ]
        
        # Initialize Web3 with BSC node
        self.bsc_node_url = os.getenv('BSC_NODE_URL')
        if not self.bsc_node_url:
            self.bsc_node_url = DEFAULT_BSC_NODES[0]
            self.logger.warning(
                f"BSC_NODE_URL environment variable is not set. "
                f"Using default BSC node: {self.bsc_node_url}"
            )
        
        self.w3 = Web3(Web3.HTTPProvider(self.bsc_node_url))
        
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
        # Cache for gas prices (expires after 30 seconds)
        self._gas_price_cache = {}
        self._gas_price_expiry = timedelta(seconds=30)
        
    def _get_cached_gas_price(self) -> int:
        """Get cached gas price or fetch new one"""
        now = datetime.now()
        if 'price' in self._gas_price_cache:
            cache_time, price = self._gas_price_cache['price']
            if now - cache_time < self._gas_price_expiry:
                return price
                
        # Fetch new gas price
        try:
            price = self.w3.eth.gas_price
            self._gas_price_cache['price'] = (now, price)
            return price
        except Exception as e:
            self.logger.error(f"Error getting gas price: {str(e)}")
            # Return a default gas price in case of error (5 Gwei)
            return 5 * 10**9
        
    def _update_gas_price_cache(self, price: Decimal) -> None:
        """Update gas price cache"""
        self._gas_price_cache["price"] = price
        self._gas_price_cache["timestamp"] = datetime.now()
        
    @handle_api_errors
    def prepare_transaction(self, sender_address: str, recipient_address: str, 
                          amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a BSC transaction"""
        try:
            # Validate addresses
            if not self.validate_address(sender_address):
                return {}, "Invalid sender address"
            if not self.validate_address(recipient_address):
                return {}, "Invalid recipient address"
                
            # Get sender's balance
            balance, error = self.get_balance(sender_address)
            if error:
                return {}, f"Error getting sender balance: {error}"
                
            # Calculate transaction fee
            fee, error = self.estimate_fee(sender_address, recipient_address, amount, smart_contract_address)
            if error:
                return {}, f"Error estimating fee: {error}"
                
            # Check if sender has enough balance
            amount_decimal = Decimal(amount)
            if balance < amount_decimal + fee:
                return {}, "Insufficient balance for transaction"
                
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Calculate balance after transaction
            balance_after = balance - amount_decimal - fee
            
            # Prepare transaction detailsً
            tx_details = {
                "transaction_id": transaction_id,
                "details": {
                    "amount": amount,
                    "blockchain": "Bsc",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://bscscan.com/tx/{transaction_id}",
                    "recipient": recipient_address,
                    "sender": sender_address,
                    "sender_balance_after": str(balance_after),
                    "sender_balance_before": str(balance)
                },
                "expires_at": (datetime.now() + timedelta(minutes=10)).isoformat(),
                "message": "Transaction prepared successfully",
                "success": True
            }
            
            # Store transaction
            self._store_transaction(transaction_id, tx_details)
            
            # Log preparation
            self._log_transaction(transaction_id, 'prepared', tx_details)
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error preparing transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    @handle_api_errors
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared BSC transaction using Tatum API broadcast endpoint"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            # Extract transaction details
            sender = tx_data.get('details', {}).get('sender')
            recipient = tx_data.get('details', {}).get('recipient')
            amount_str = tx_data.get('details', {}).get('amount')
            
            if not all([sender, recipient, amount_str]):
                self.logger.error(f"Transaction data is incomplete: {tx_data}")
                return None, "Transaction data is incomplete"
                
            # If this is a token transfer
            if tx_data.get('token_address'):
                # Create signed transaction for token transfer
                token_address = tx_data.get('token_address')
                contract_abi = self._get_token_abi(token_address)
                contract = self.w3.eth.contract(address=token_address, abi=contract_abi)
                
                # Convert amount to token units based on decimals
                token_decimals = contract.functions.decimals().call()
                amount = int(float(amount_str) * 10**token_decimals)
                
                # Build token transfer transaction
                gas_price = self._get_cached_gas_price()
                nonce = self.w3.eth.get_transaction_count(sender)
                
                tx = contract.functions.transfer(
                    recipient,
                    amount
                ).build_transaction({
                    'from': sender,
                    'gas': 100000,  # Estimated gas limit for token transfers
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': 56  # BSC mainnet
                })
            else:
                # Create signed transaction for native token (BNB) transfer
                amount = self.w3.to_wei(float(amount_str), 'ether')
                gas_price = self._get_cached_gas_price()
                nonce = self.w3.eth.get_transaction_count(sender)
                
                tx = {
                    'from': sender,
                    'to': recipient,
                    'value': amount,
                    'gas': 21000,  # Standard gas limit for BNB transfers
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': 56  # BSC mainnet
                }
            
            # Sign the transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key)
            
            # Use Tatum API to broadcast the transaction
            tatum_url = f"{self.tatum.base_url}/v3/bsc/broadcast"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.tatum.api_key
            }
            payload = {
                "txData": signed_tx.rawTransaction.hex()
            }
            
            self.logger.info(f"Broadcasting BSC transaction via Tatum API")
            response = requests.post(tatum_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                tx_hash = response.json()
                
                # Update transaction record with the transaction hash
                tx_data['hash'] = tx_hash
                tx_data['status'] = 'SENT'
                self._update_transaction(transaction_id, tx_data)
                
                self.logger.info(f"BSC transaction sent successfully: {tx_hash}")
                return {'txId': tx_hash}, None
            else:
                error_msg = f"Failed to broadcast BSC transaction: {response.text}"
                self.logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            self.logger.error(f"Error sending BSC transaction: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None, f"Error sending BSC transaction: {str(e)}"
            
    @handle_api_errors
    def estimate_fee(self, sender_address: str, recipient_address: str,
                    amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Decimal, Optional[str]]:
        """Estimate BSC transaction fee"""
        try:
            # Try to use Tatum BSC-specific gas endpoint first
            try:
                # Prepare request data
                data = {
                    "from": sender_address,
                    "to": recipient_address,
                    "amount": amount
                }
                
                # Add contract data if it's a token transfer
                if smart_contract_address:
                    data["contractAddress"] = smart_contract_address
                
                # Make direct request to BSC-specific endpoint
                url = f"{self.tatum.base_url}/bsc/gas"
                self.logger.debug(f"Making BSC gas estimation request to {url}")
                self.logger.debug(f"Request data: {data}")
                
                response = requests.post(
                    url, 
                    headers=self.tatum.headers, 
                    json=data
                )
                
                if response.status_code == 200:
                    gas_data = response.json()
                    self.logger.debug(f"BSC gas response: {gas_data}")
                    
                    gas_price = Decimal(str(gas_data.get('gasPrice', '5000000000'))) / Decimal('1e9')  # Wei to Gwei
                    gas_limit = Decimal(str(gas_data.get('gasLimit', '21000')))
                    
                    # Calculate and return fee in BNB
                    fee = (gas_price * gas_limit) / Decimal('1e9')  # Gwei to BNB
                    return fee, None
                else:
                    self.logger.warning(f"Tatum BSC gas endpoint returned error: {response.status_code} - {response.text}")
            except Exception as e:
                self.logger.warning(f"Error using Tatum BSC gas endpoint: {str(e)}")
            
            # Fallback to local estimation
            # Try to get cached gas price first
            gas_price = self._get_cached_gas_price()
            
            if not gas_price:
                # Get gas price from Web3
                try:
                    gas_price = Decimal(str(self.w3.eth.gas_price)) / Decimal('1e9')  # Convert from Wei to Gwei
                    self._update_gas_price_cache(gas_price)
                except Exception as e:
                    self.logger.warning(f"Failed to get gas price from Web3: {str(e)}")
                    # Fallback to default
                    gas_price = Decimal('5')  # Default gas price in Gwei for BSC
                    
            # Estimate gas limit
            gas_limit = 21000  # Default for BNB transfers
            if smart_contract_address:
                gas_limit = 65000  # Default for token transfers
                
            # Calculate total fee
            fee = gas_price * gas_limit / Decimal('1e9')  # Convert to BNB
            
            return fee, None
            
        except Exception as e:
            error_msg = f"Error estimating fee: {str(e)}"
            self.logger.error(error_msg)
            return Decimal('0'), error_msg
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get BSC balance"""
        try:
            # Try Web3 first
            try:
                balance_wei = self.w3.eth.get_balance(address)
                return Decimal(str(balance_wei)) / Decimal('1e18'), None
            except Exception as e:
                self.logger.warning(f"Failed to get balance from Web3: {str(e)}")
                
            # Fallback to Tatum
            balance_data, error = self.tatum.get_balance("binance smart chain", address)
            if error:
                return Decimal('0'), error
                
            return Decimal(str(balance_data.get('balance', '0'))), None
            
        except Exception as e:
            error_msg = f"Error getting balance: {str(e)}"
            self.logger.error(error_msg)
            return Decimal('0'), error_msg
            
    def validate_address(self, address: str) -> bool:
        """Validate BSC address"""
        return self.w3.is_address(address)
        
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get BSC transaction status"""
        try:
            # Try Web3 first
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if not tx:
                    return "not_found", None
                    
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return "confirmed" if receipt["status"] == 1 else "failed", None
                    
                # Transaction is in mempool
                return "pending", None
                
            except TransactionNotFound:
                # Not found in mempool, could be in a different node
                self.logger.warning(f"Transaction {tx_hash} not found in Web3, checking Tatum")
                
            except Exception as e:
                self.logger.warning(f"Error getting transaction status from Web3: {str(e)}")
                
            # Fallback to Tatum
            return self.tatum.check_transaction_status("binance smart chain", tx_hash)
            
        except Exception as e:
            error_msg = f"Error getting transaction status: {str(e)}"
            self.logger.error(error_msg)
            return "unknown", error_msg
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """Get detailed BSC transaction information"""
        try:
            # Try Web3 first
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx:
                    receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                    
                    # Format transaction details
                    details = {
                        "hash": tx_hash,
                        "blockNumber": tx.get("blockNumber"),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "value": str(self.w3.from_wei(tx.get("value", 0), "ether")),
                        "gasPrice": str(self.w3.from_wei(tx.get("gasPrice", 0), "gwei")),
                        "gas": tx.get("gas"),
                        "nonce": tx.get("nonce")
                    }
                    
                    if receipt:
                        details.update({
                            "status": "confirmed" if receipt.get("status") == 1 else "failed",
                            "blockHash": receipt.get("blockHash"),
                            "gasUsed": receipt.get("gasUsed"),
                            "confirmations": 1  # Placeholder since Web3 doesn't provide this directly
                        })
                    else:
                        details["status"] = "pending"
                        
                    return details, None
                    
            except Exception as e:
                self.logger.warning(f"Error getting transaction details from Web3: {str(e)}")
                
            # Fallback to Tatum
            return self.tatum.get_transaction("binance smart chain", tx_hash)
            
        except Exception as e:
            error_msg = f"Error getting transaction details: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    def _get_stored_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get stored transaction data"""
        try:
            # Use the unified storage system from base class
            tx_data = self.storage.get_transaction(transaction_id)
            if tx_data:
                self.logger.debug(f"Retrieved BSC transaction {transaction_id} from storage")
                return tx_data
                
            self.logger.warning(f"BSC transaction {transaction_id} not found in storage")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving transaction {transaction_id}: {str(e)}")
            return None

    def _store_transaction(self, transaction_id: str, tx_details: Dict) -> None:
        """Store transaction details"""
        try:
            # Use the unified storage system from base class
            self.storage.store_transaction(transaction_id, tx_details)
            self.logger.debug(f"Stored BSC transaction {transaction_id}")
        except Exception as e:
            self.logger.error(f"Error storing BSC transaction {transaction_id}: {str(e)}")
            raise
        
    def _log_transaction(self, transaction_id: str, action: str, details: Dict = None) -> None:
        """Log transaction activity"""
        log_data = {
            "transaction_id": transaction_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            log_data["details"] = details
            
        self.logger.info(f"BSC transaction log: {json.dumps(log_data)}") 