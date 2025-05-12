from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
from tronpy import Tron
from tronpy.keys import PrivateKey

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class TronService(BaseBlockchainService):
    """TRON blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Tron client
        self.tron_node_url = os.getenv('TRON_NODE_URL')
        if not self.tron_node_url:
            raise RuntimeError("TRON_NODE_URL environment variable is not set")
            
        self.client = Tron(network='mainnet', provider_url=self.tron_node_url)
        
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a TRON transaction"""
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
                    "blockchain": "tron",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://tronscan.org/#/transaction/{transaction_id}",
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
        """Send a prepared TRON transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            try:
                # Create private key object
                priv_key = PrivateKey(bytes.fromhex(private_key))
                
                # Prepare transaction
                txn = (
                    self.client.trx.transfer(
                        tx_data['sender'],
                        tx_data['recipient'],
                        int(Decimal(tx_data['amount']) * Decimal(10**6))  # Convert to SUN
                    )
                    .build()
                    .sign(priv_key)
                )
                
                # Send transaction
                result = txn.broadcast()
                
                # Update transaction data
                tx_data.update({
                    'tx_hash': result['txid'],
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat()
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': result['txid']
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': result['txid'],
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Error sending transaction via TRON client: {str(e)}")
                
                # Fallback to Tatum
                result, error = self.tatum.send_transaction(
                    'tron',
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
        """Estimate TRON transaction fee"""
        try:
            # TRON has fixed fees
            return Decimal('0.1'), None  # Fixed fee in TRX
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get TRON balance"""
        try:
            # Try TRON client first
            balance = self.client.get_account_balance(address)
            return Decimal(balance) / Decimal(10**6), None  # Convert from SUN to TRX
            
        except Exception as e:
            self.logger.error(f"Error getting balance via TRON client: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('tron', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate TRON address"""
        try:
            return self.client.is_address(address)
        except:
            return False
            
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get TRON transaction status"""
        try:
            # Try TRON client first
            try:
                tx = self.client.get_transaction(tx_hash)
                if tx:
                    if tx.get('ret', [{}])[0].get('contractRet') == 'SUCCESS':
                        return 'confirmed', None
                    return 'failed', None
            except:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('tron', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get TRON transaction details"""
        try:
            # Try TRON client first
            try:
                tx = self.client.get_transaction(tx_hash)
                if tx:
                    return {
                        'hash': tx_hash,
                        'from': tx['raw_data']['contract'][0]['parameter']['value']['owner_address'],
                        'to': tx['raw_data']['contract'][0]['parameter']['value']['to_address'],
                        'value': str(Decimal(tx['raw_data']['contract'][0]['parameter']['value']['amount']) / Decimal(10**6)),
                        'status': 'confirmed' if tx.get('ret', [{}])[0].get('contractRet') == 'SUCCESS' else 'failed',
                        'timestamp': datetime.fromtimestamp(tx['raw_data']['timestamp'] / 1000).isoformat()
                    }, None
            except:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('tron', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e)
            
    def _get_stored_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get stored transaction data"""
        # TODO: Implement transaction storage/retrieval
        return None 