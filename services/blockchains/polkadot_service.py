from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class PolkadotService(BaseBlockchainService):
    """Polkadot blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Polkadot node URL
        self.polkadot_node_url = os.getenv('POLKADOT_NODE_URL', 'wss://rpc.polkadot.io')
        
        # Initialize Substrate interface
        self.substrate = SubstrateInterface(
            url=self.polkadot_node_url,
            ss58_format=0,  # Polkadot uses 0 as SS58 format
            type_registry_preset='polkadot'
        )
        
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a Polkadot transaction"""
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
                    "blockchain": "polkadot",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://polkascan.io/polkadot/transaction/{transaction_id}",
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
        """Send a prepared Polkadot transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            try:
                # Create keypair from private key
                keypair = Keypair.create_from_private_key(private_key, ss58_format=0)
                
                # Get account info
                account_info = self.substrate.query(
                    module='System',
                    storage_function='Account',
                    params=[tx_data['sender']]
                )
                
                # Create transfer extrinsic
                call = self.substrate.compose_call(
                    call_module='Balances',
                    call_function='transfer',
                    call_params={
                        'dest': tx_data['recipient'],
                        'value': int(Decimal(tx_data['amount']) * Decimal(10**10))  # Convert to Planck
                    }
                )
                
                # Create extrinsic
                extrinsic = self.substrate.create_signed_extrinsic(
                    call=call,
                    keypair=keypair,
                    era={'period': 64},  # 5 minutes
                    nonce=account_info['nonce']
                )
                
                # Submit extrinsic
                receipt = self.substrate.submit_extrinsic(
                    extrinsic=extrinsic,
                    wait_for_inclusion=True
                )
                
                # Update transaction data
                tx_data.update({
                    'tx_hash': receipt.extrinsic_hash,
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat()
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': receipt.extrinsic_hash
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': receipt.extrinsic_hash,
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Error sending transaction via Polkadot client: {str(e)}")
                
                # Fallback to Tatum
                result, error = self.tatum.send_transaction(
                    'polkadot',
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
        """Estimate Polkadot transaction fee"""
        try:
            # Create transfer call
            call = self.substrate.compose_call(
                call_module='Balances',
                call_function='transfer',
                call_params={
                    'dest': recipient,
                    'value': int(amount * Decimal(10**10))  # Convert to Planck
                }
            )
            
            # Get payment info
            payment_info = self.substrate.get_payment_info(
                call=call,
                keypair=Keypair(ss58_address=sender)
            )
            
            # Convert fee from Planck to DOT
            fee = Decimal(payment_info['partialFee']) / Decimal(10**10)
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Polkadot balance"""
        try:
            # Try Substrate interface first
            account_info = self.substrate.query(
                module='System',
                storage_function='Account',
                params=[address]
            )
            
            # Get free balance in Planck
            free_balance = Decimal(account_info['data']['free'])
            
            # Convert to DOT
            balance = free_balance / Decimal(10**10)
            return balance, None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Polkadot client: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('polkadot', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Polkadot address"""
        try:
            # Check if address is a valid SS58 string
            if not address or len(address) < 32 or len(address) > 48:
                return False
                
            # Try to decode address
            keypair = Keypair(ss58_address=address)
            return True
            
        except:
            return False
            
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Polkadot transaction status"""
        try:
            # Try Substrate interface first
            try:
                receipt = self.substrate.get_extrinsic_by_hash(tx_hash)
                
                if receipt.is_success:
                    return 'confirmed', None
                return 'failed', None
                
            except:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('polkadot', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Polkadot transaction details"""
        try:
            # Try Substrate interface first
            try:
                receipt = self.substrate.get_extrinsic_by_hash(tx_hash)
                
                if receipt:
                    return {
                        'hash': tx_hash,
                        'from': receipt.signer,
                        'to': receipt.call.args['dest'],
                        'value': str(Decimal(receipt.call.args['value']) / Decimal(10**10)),
                        'status': 'confirmed' if receipt.is_success else 'failed',
                        'block_number': receipt.block_number,
                        'timestamp': datetime.fromtimestamp(
                            receipt.block_datetime.timestamp()
                        ).isoformat()
                    }, None
            except:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('polkadot', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e) 