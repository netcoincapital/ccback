from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
import requests
from datetime import datetime, timedelta
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class ArbitrumService(BaseBlockchainService):
    """Arbitrum blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Web3 with Arbitrum node
        self.arbitrum_node_url = os.getenv('ARBITRUM_NODE_URL')
        if not self.arbitrum_node_url:
            raise RuntimeError("ARBITRUM_NODE_URL environment variable is not set")
            
        self.w3 = Web3(Web3.HTTPProvider(self.arbitrum_node_url))
        
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
        price = self.w3.eth.gas_price
        self._gas_price_cache['price'] = (now, price)
        return price
        
    def _update_gas_price_cache(self, price: Decimal) -> None:
        """Update gas price cache"""
        self._gas_price_cache["price"] = price
        self._gas_price_cache["timestamp"] = datetime.now()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare an Arbitrum transaction"""
        try:
            # Validate addresses
            if not self.validate_address(sender):
                return None, "Invalid sender address"
            if not self.validate_address(recipient):
                return None, "Invalid recipient address"
                
            # Get sender's balance
            balance, error = self.get_balance(sender)
            if error:
                return None, f"Error getting balance: {error}"
                
            # Estimate fee
            fee, error = self.estimate_fee(sender, recipient, amount)
            if error:
                return None, f"Error estimating fee: {error}"
                
            # Check if sender has enough balance
            if balance < amount + fee:
                return None, "Insufficient balance"
                
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Calculate balance after transaction
            balance_after = balance - amount - fee
            
            # Prepare transaction details
            tx_details = {
                "transaction_id": transaction_id,
                "details": {
                    "amount": str(amount),
                    "blockchain": "arbitrum",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://arbiscan.io/tx/{transaction_id}",
                    "recipient": recipient,
                    "sender": sender,
                    "sender_balance_after": str(balance_after),
                    "sender_balance_before": str(balance)
                },
                "expires_at": (datetime.now() + timedelta(minutes=15)).isoformat(),
                "message": "Transaction prepared successfully",
                "success": True
            }
            
            # Store transaction
            self._store_transaction(transaction_id, tx_details)
            
            # Log preparation
            self._log_transaction(transaction_id, 'prepared', tx_details)
            
            return tx_details, None
            
        except Exception as e:
            self.logger.error(f"Error preparing transaction: {str(e)}")
            return None, str(e)
            
    @handle_api_errors
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared Arbitrum transaction using Tatum API broadcast endpoint"""
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
                
            # Convert amount to Decimal for calculations
            try:
                amount = Decimal(amount_str)
            except Exception as e:
                self.logger.error(f"Error converting amount to Decimal: {str(e)}")
                return None, f"Invalid amount format: {amount_str}"
                
            # Prepare transaction parameters
            params = {
                'from': sender,
                'to': recipient,
                'value': self.w3.to_wei(amount, 'ether'),
                'gas': 21000,  # Standard gas limit for ETH transfers on Arbitrum
                'gasPrice': self._get_cached_gas_price(),
                'nonce': self.w3.eth.get_transaction_count(sender),
                'chainId': 42161  # Arbitrum mainnet
            }
            
            try:
                # Sign transaction
                self.logger.debug("Signing Arbitrum transaction with private key")
                signed_tx = self.w3.eth.account.sign_transaction(params, private_key)
                
                # Get raw transaction data
                raw_tx = signed_tx.rawTransaction.hex()
                if not raw_tx.startswith('0x'):
                    raw_tx = '0x' + raw_tx
                
                self.logger.debug(f"Signed transaction raw data: {raw_tx[:10]}...")
                
                # Use Tatum broadcast endpoint
                url = f"{self.tatum.base_url}/arb/broadcast"
                self.logger.debug(f"Making Arbitrum broadcast request to {url}")
                
                broadcast_data = {
                    "txData": raw_tx
                }
                
                self.logger.debug(f"Broadcast request data: {broadcast_data}")
                
                # Send to Tatum API
                response = requests.post(
                    url, 
                    headers=self.tatum.headers, 
                    json=broadcast_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.debug(f"Arbitrum broadcast response: {result}")
                    
                    tx_hash = result.get('txId')
                    if not tx_hash:
                        self.logger.error(f"Missing transaction hash in response: {result}")
                        return None, "Missing transaction hash in response"
                        
                    # Update transaction data
                    tx_data.update({
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'tatum_broadcast'
                    })
                    self._store_transaction(transaction_id, tx_data)
                    
                    # Log sending
                    self._log_transaction(transaction_id, 'sent', {
                        'tx_hash': tx_hash,
                        'sent_via': 'tatum_broadcast'
                    })
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash,
                        'transaction_hash': tx_hash,
                        'status': 'sent'
                    }, None
                else:
                    error_msg = f"Tatum Arbitrum broadcast error: {response.status_code} - {response.text}"
                    self.logger.error(error_msg)
                    
                    # Try direct Web3 broadcast as fallback
                    self.logger.debug("Falling back to direct Web3 broadcast")
                    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                    tx_hash_hex = tx_hash.hex()
                    
                    # Update transaction data
                    tx_data.update({
                        'tx_hash': tx_hash_hex,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'web3'
                    })
                    self._store_transaction(transaction_id, tx_data)
                    
                    # Log sending
                    self._log_transaction(transaction_id, 'sent', {
                        'tx_hash': tx_hash_hex,
                        'sent_via': 'web3'
                    })
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash_hex,
                        'transaction_hash': tx_hash_hex,
                        'status': 'sent'
                    }, None
                
            except Exception as e:
                self.logger.error(f"Error sending transaction via Web3 or Tatum broadcast: {str(e)}")
                
                # Final fallback to Tatum generic send
                self.logger.debug("Falling back to Tatum generic send_transaction")
                result, error = self.tatum.send_transaction(
                    'arbitrum',
                    sender,
                    recipient,
                    amount_str,  # Use string form for Tatum API
                    private_key
                )
                
                if error:
                    return None, f"Failed to send transaction: {error}"
                    
                # Get transaction hash from result
                tx_hash = result.get('txId') or result.get('transaction_hash')
                if not tx_hash:
                    self.logger.error(f"Missing transaction hash in Tatum response: {result}")
                    return None, "Missing transaction hash in response"
                    
                # Update transaction data
                tx_data.update({
                    'tx_hash': tx_hash,
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat(),
                    'sent_via': 'tatum'
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': tx_hash,
                    'sent_via': 'tatum'
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': tx_hash,
                    'transaction_hash': tx_hash,
                    'status': 'sent'
                }, None
                
        except Exception as e:
            self.logger.error(f"Error sending transaction: {str(e)}")
            return None, str(e)
            
    @handle_api_errors
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """Estimate Arbitrum transaction fee"""
        try:
            # Get gas price
            gas_price = self._get_cached_gas_price()
            
            # Estimate gas limit
            gas_limit = 21000  # Standard gas limit for ETH transfers
            
            # Calculate total fee
            fee = Decimal(gas_price * gas_limit) / Decimal(10**18)
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Arbitrum balance"""
        try:
            # Try Web3 first
            balance = self.w3.eth.get_balance(address)
            return Decimal(balance) / Decimal(10**18), None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Web3: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('arbitrum', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Arbitrum address"""
        return self.w3.is_address(address)
        
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Arbitrum transaction status"""
        try:
            # Try Web3 first
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return 'confirmed' if receipt['status'] == 1 else 'failed', None
            except TransactionNotFound:
                pass
                
            # Check if transaction exists
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx:
                    return 'pending', None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('arbitrum', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Arbitrum transaction details"""
        try:
            # Try Web3 first
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                
                if tx and receipt:
                    return {
                        'hash': tx_hash,
                        'from': tx['from'],
                        'to': tx['to'],
                        'value': str(Decimal(tx['value']) / Decimal(10**18)),
                        'gas_price': str(Decimal(tx['gasPrice']) / Decimal(10**18)),
                        'gas_used': receipt['gasUsed'],
                        'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                        'block_number': receipt['blockNumber'],
                        'timestamp': datetime.fromtimestamp(
                            self.w3.eth.get_block(receipt['blockNumber'])['timestamp']
                        ).isoformat()
                    }, None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('arbitrum', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e) 