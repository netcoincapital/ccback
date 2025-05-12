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

class EthereumService(BaseBlockchainService):
    """Ethereum blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Web3
        infura_api_key = os.getenv('INFURA_API_KEY')
        if not infura_api_key:
            raise RuntimeError("INFURA_API_KEY environment variable not set")
            
        self.w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{infura_api_key}'))
        self.tatum = TatumHelper()
        
        # Cache for gas prices (30 second expiration)
        self._gas_price_cache = {}
        self._gas_price_expiry = timedelta(seconds=30)
        
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare an Ethereum transaction"""
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
                    "blockchain": "ethereum",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://etherscan.io/tx/{transaction_id}",
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
            
    def send_transaction(self, transaction_id: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared Ethereum transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            # Prepare transaction parameters
            params = {
                'from': tx_data['sender'],
                'to': tx_data['recipient'],
                'value': self.w3.to_wei(Decimal(tx_data['amount']), 'ether'),
                'gas': 21000,  # Standard gas limit for ETH transfers
                'gasPrice': self._get_cached_gas_price(),
                'nonce': self.w3.eth.get_transaction_count(tx_data['sender'])
            }
            
            try:
                # Sign and send transaction
                signed_tx = self.w3.eth.account.sign_transaction(params, private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
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
                    'ethereum',
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
            
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """Estimate Ethereum transaction fee"""
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
            
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Ethereum balance"""
        try:
            # Try Web3 first
            balance = self.w3.eth.get_balance(address)
            return Decimal(balance) / Decimal(10**18), None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Web3: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('ethereum', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address"""
        return self.w3.is_address(address)
        
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Ethereum transaction status"""
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
            status, error = self.tatum.check_transaction_status('ethereum', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Ethereum transaction details"""
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
            details, error = self.tatum.get_transaction('ethereum', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e)
            
    def _get_cached_gas_price(self) -> int:
        """Get cached gas price or fetch new one"""
        now = datetime.now()
        if 'price' in self._gas_price_cache:
            cache_time, price = self._gas_price_cache['price']
            if now - cache_time < self._gas_price_expiry:
                return price
                
        try:
            # Try Infura first
            price = self.w3.eth.gas_price
            self._gas_price_cache['price'] = (now, price)
            return price
        except Exception as e:
            self.logger.warning(f"Error getting gas price from Infura: {str(e)}")
            
            try:
                # Fallback to Tatum
                gas_data, error = self.tatum.get_gas_price('ethereum')
                if error:
                    raise Exception(f"Tatum error: {error}")
                    
                price = int(gas_data.get('gasPrice', 0) * 1e9)  # Convert from Gwei to Wei
                self._gas_price_cache['price'] = (now, price)
                return price
            except Exception as e2:
                self.logger.error(f"Error getting gas price from Tatum: {str(e2)}")
                # Use default gas price as last resort
                default_price = 20 * 1e9  # 20 Gwei in Wei
                self._gas_price_cache['price'] = (now, default_price)
                return default_price
        
    def _get_stored_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get stored transaction data"""
        # TODO: Implement transaction storage/retrieval
        return None 