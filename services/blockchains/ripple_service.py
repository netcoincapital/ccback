from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.utils import xrp_to_drops, drops_to_xrp

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class RippleService(BaseBlockchainService):
    """Ripple blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Ripple node URL
        self.ripple_node_url = os.getenv('RIPPLE_NODE_URL', 'wss://xrplcluster.com')
        
        # Initialize Ripple client
        self.client = JsonRpcClient(self.ripple_node_url)
        
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a Ripple transaction"""
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
                    "blockchain": "ripple",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://livenet.xrpl.org/transactions/{transaction_id}",
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
        """Send a prepared Ripple transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            try:
                # Create wallet from private key
                wallet = Wallet.from_private_key(private_key)
                
                # Get account info
                account_info = self.client.request(xrpl.models.requests.AccountInfo(
                    account=tx_data['sender'],
                    ledger_index="validated",
                    strict=True
                ))
                
                # Create payment transaction
                payment = Payment(
                    account=tx_data['sender'],
                    destination=tx_data['recipient'],
                    amount=xrp_to_drops(str(tx_data['amount'])),
                    fee=xrp_to_drops(str(tx_data['fee'])),
                    sequence=account_info.result['account_data']['Sequence']
                )
                
                # Sign and submit transaction
                signed_tx = xrpl.transaction.safe_sign_and_submit_transaction(
                    payment,
                    wallet,
                    self.client
                )
                
                # Update transaction data
                tx_data.update({
                    'tx_hash': signed_tx.result['hash'],
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat()
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': signed_tx.result['hash']
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': signed_tx.result['hash'],
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Error sending transaction via Ripple client: {str(e)}")
                
                # Fallback to Tatum
                result, error = self.tatum.send_transaction(
                    'ripple',
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
        """Estimate Ripple transaction fee"""
        try:
            # Get server info for current fee
            server_info = self.client.request(xrpl.models.requests.ServerInfo())
            fee = Decimal(drops_to_xrp(server_info.result['info']['validated_ledger']['base_fee_xrp']))
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Ripple balance"""
        try:
            # Try Ripple client first
            account_info = self.client.request(xrpl.models.requests.AccountInfo(
                account=address,
                ledger_index="validated",
                strict=True
            ))
            
            balance = Decimal(drops_to_xrp(account_info.result['account_data']['Balance']))
            return balance, None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Ripple client: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('ripple', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Ripple address"""
        try:
            # Check if address is a valid base58 string
            if not address or len(address) != 25:
                return False
                
            # Try to get account info
            account_info = self.client.request(xrpl.models.requests.AccountInfo(
                account=address,
                ledger_index="validated",
                strict=True
            ))
            return True
            
        except:
            return False
            
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Ripple transaction status"""
        try:
            # Try Ripple client first
            try:
                tx_info = self.client.request(xrpl.models.requests.Tx(
                    transaction=tx_hash
                ))
                
                if tx_info.result['validated']:
                    if tx_info.result['meta']['TransactionResult'] == 'tesSUCCESS':
                        return 'confirmed', None
                    return 'failed', None
                return 'pending', None
                
            except:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('ripple', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Ripple transaction details"""
        try:
            # Try Ripple client first
            try:
                tx_info = self.client.request(xrpl.models.requests.Tx(
                    transaction=tx_hash
                ))
                
                if tx_info.result['validated']:
                    return {
                        'hash': tx_hash,
                        'from': tx_info.result['Account'],
                        'to': tx_info.result['Destination'],
                        'value': str(Decimal(drops_to_xrp(tx_info.result['Amount']))),
                        'status': 'confirmed' if tx_info.result['meta']['TransactionResult'] == 'tesSUCCESS' else 'failed',
                        'ledger_index': tx_info.result['ledger_index'],
                        'timestamp': datetime.fromtimestamp(
                            tx_info.result['date']
                        ).isoformat()
                    }, None
            except:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('ripple', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e) 