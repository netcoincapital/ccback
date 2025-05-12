from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class AvalancheService(BaseBlockchainService):
    """Avalanche blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Web3 with Avalanche node
        self.avalanche_node_url = os.getenv('AVALANCHE_NODE_URL')
        if not self.avalanche_node_url:
            raise RuntimeError("AVALANCHE_NODE_URL environment variable is not set")
            
        self.web3 = Web3(Web3.HTTPProvider(self.avalanche_node_url))
        
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
        price = self.web3.eth.gas_price
        self._gas_price_cache['price'] = (now, price)
        return price
        
    def _update_gas_price_cache(self, price: Decimal) -> None:
        """Update gas price cache"""
        self._gas_price_cache["price"] = price
        self._gas_price_cache["timestamp"] = datetime.now()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare an Avalanche transaction"""
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
                    "blockchain": "avalanche",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://snowtrace.io/tx/{transaction_id}",
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
    def send_transaction(self, transaction_id: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared Avalanche transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            # Prepare transaction parameters
            params = {
                'from': tx_data['sender'],
                'to': tx_data['recipient'],
                'value': self.web3.to_wei(Decimal(tx_data['amount']), 'ether'),
                'gas': 21000,  # Standard gas limit for AVAX transfers
                'gasPrice': self._get_cached_gas_price(),
                'nonce': self.web3.eth.get_transaction_count(tx_data['sender']),
                'chainId': 43114  # Avalanche C-Chain mainnet chain ID
            }
            
            try:
                # Sign and send transaction
                signed_tx = self.web3.eth.account.sign_transaction(params, private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                # Update transaction data
                tx_data.update({
                    'tx_hash': tx_hash.hex(),
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat()
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': tx_hash.hex()
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': tx_hash.hex(),
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Error sending transaction via Web3: {str(e)}")
                
                # Fallback to Tatum
                result, error = self.tatum.send_transaction(
                    'avalanche',
                    tx_data['sender'],
                    tx_data['recipient'],
                    tx_data['amount']
                )
                
                if error:
                    return None, f"Failed to send transaction: {error}"
                    
                # Update transaction data
                tx_data.update({
                    'tx_hash': result['txId'],
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat(),
                    'sent_via': 'tatum'
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': result['txId'],
                    'sent_via': 'tatum'
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': result['txId'],
                    'status': 'sent'
                }, None
                
        except Exception as e:
            self.logger.error(f"Error sending transaction: {str(e)}")
            return None, str(e)
            
    @handle_api_errors
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """Estimate Avalanche transaction fee"""
        try:
            # Get gas price
            gas_price = self._get_cached_gas_price()
            
            # Estimate gas limit
            gas_limit = 21000  # Standard gas limit for AVAX transfers
            
            # Calculate total fee
            fee = Decimal(gas_price * gas_limit) / Decimal(10**18)
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Avalanche balance"""
        try:
            # Try Web3 first
            balance = self.web3.eth.get_balance(address)
            return Decimal(balance) / Decimal(10**18), None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Web3: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('avalanche', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Avalanche address"""
        return self.web3.is_address(address)
        
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Avalanche transaction status"""
        try:
            # Try Web3 first
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return 'confirmed' if receipt['status'] == 1 else 'failed', None
            except TransactionNotFound:
                pass
                
            # Check if transaction exists
            try:
                tx = self.web3.eth.get_transaction(tx_hash)
                if tx:
                    return 'pending', None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('avalanche', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Avalanche transaction details"""
        try:
            # Try Web3 first
            try:
                tx = self.web3.eth.get_transaction(tx_hash)
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                
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
                            self.web3.eth.get_block(receipt['blockNumber'])['timestamp']
                        ).isoformat()
                    }, None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('avalanche', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e) 