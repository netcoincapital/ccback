from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
import requests
from datetime import datetime, timedelta
from solana.rpc.api import Client
from solders.transaction import Transaction
from solders.keypair import Keypair
from solana.system_program import TransferParams, transfer

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class SolanaService(BaseBlockchainService):
    """Solana blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Solana client
        self.solana_node_url = os.getenv('SOLANA_NODE_URL')
        if not self.solana_node_url:
            raise RuntimeError("SOLANA_NODE_URL environment variable is not set")
            
        self.client = Client(self.solana_node_url)
        
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a Solana transaction"""
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
                    "blockchain": "solana",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://explorer.solana.com/tx/{transaction_id}",
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
        """Send a prepared Solana transaction using Tatum API broadcast endpoint"""
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
            
            # Try direct Solana client to sign transaction first
            signed_tx_raw = None
            if self.client_available:
                try:
                    self.logger.info(f"Signing Solana transaction using direct client")
                    
                    # Load private key
                    from solders.keypair import Keypair
                    from solders.transaction import Transaction
                    from solana.system_program import TransferParams, transfer
                    
                    # Decode private key
                    keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
                    
                    # Create transaction instruction
                    transfer_instruction = transfer(
                        TransferParams(
                            from_pubkey=keypair.public_key,
                            to_pubkey=recipient,
                            lamports=int(amount * 10**9)  # Convert SOL to lamports
                        )
                    )
                    
                    # Create and sign transaction
                    transaction = Transaction().add(transfer_instruction)
                    transaction.sign(keypair)
                    
                    # Get raw signed transaction
                    signed_tx_raw = transaction.serialize()
                    self.logger.debug(f"Successfully signed Solana transaction")
                except Exception as e:
                    self.logger.warning(f"Error signing transaction via Solana client: {str(e)}")
            
            # Use Tatum broadcast endpoint
            if self.tatum:
                try:
                    self.logger.info(f"Broadcasting Solana transaction via Tatum broadcast endpoint")
                    
                    # For Solana we need to use a special endpoint that includes /confirm
                    url = f"{self.tatum.base_url}/solana/broadcast/confirm"
                    self.logger.debug(f"Making Solana broadcast request to {url}")
                    
                    # If we have a raw signed tx, use it. Otherwise, let Tatum sign it
                    if signed_tx_raw:
                        broadcast_data = {
                            "txData": signed_tx_raw.hex()
                        }
                    else:
                        # Let Tatum handle the signing
                        broadcast_data = {
                            "from": sender,
                            "to": recipient,
                            "amount": str(amount),
                            "fromPrivateKey": private_key
                        }
                    
                    self.logger.debug(f"Broadcast request data: {broadcast_data}")
                    
                    response = requests.post(
                        url, 
                        headers=self.tatum.headers, 
                        json=broadcast_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        self.logger.debug(f"Solana broadcast response: {result}")
                        
                        tx_hash = result.get("txId")
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
                        error_msg = f"Tatum Solana broadcast error: {response.status_code} - {response.text}"
                        self.logger.error(error_msg)
                except Exception as e:
                    self.logger.error(f"Error broadcasting Solana transaction via Tatum: {str(e)}")
            
            # Try direct client as fallback
            if self.client_available:
                try:
                    self.logger.info(f"Attempting to send Solana transaction via direct client")
                    
                    # Reuse or create keypair
                    from solders.keypair import Keypair
                    keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
                    
                    # Try to send transaction (if we already built it above)
                    if signed_tx_raw:
                        from solana.rpc.api import Client
                        client = Client(self.solana_node_url)
                        result = client.send_raw_transaction(signed_tx_raw)
                        tx_hash = result['result']
                        
                        # Update transaction data
                        tx_data.update({
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'sent_at': datetime.now().isoformat(),
                            'sent_via': 'solana_client'
                        })
                        self._store_transaction(transaction_id, tx_data)
                        
                        # Log sending
                        self._log_transaction(transaction_id, 'sent', {
                            'tx_hash': tx_hash,
                            'sent_via': 'solana_client'
                        })
                        
                        return {
                            'transaction_id': transaction_id,
                            'tx_hash': tx_hash,
                            'transaction_hash': tx_hash,
                            'status': 'sent'
                        }, None
                except Exception as e:
                    self.logger.warning(f"Error sending transaction via Solana client: {str(e)}")
            
            # Final fallback to Tatum generic transaction endpoint
            if self.tatum:
                self.logger.info(f"Attempting to send Solana transaction via Tatum transaction endpoint")
                
                result, error = self.tatum.send_transaction(
                    'solana',
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
                    'sent_via': 'tatum_transaction'
                })
                self._store_transaction(transaction_id, tx_data)
                
                # Log sending
                self._log_transaction(transaction_id, 'sent', {
                    'tx_hash': tx_hash,
                    'sent_via': 'tatum_transaction'
                })
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': tx_hash,
                    'transaction_hash': tx_hash,
                    'status': 'sent'
                }, None
            
            return None, "Failed to send transaction: all methods failed"
                
        except Exception as e:
            self.logger.error(f"Error sending Solana transaction: {str(e)}")
            return None, str(e)
            
    @handle_api_errors
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """Estimate Solana transaction fee"""
        try:
            # Get recent blockhash
            recent_blockhash = self.client.get_recent_blockhash()
            if not recent_blockhash['result']['value']:
                return Decimal('0'), "Failed to get recent blockhash"
                
            # Get fee calculator
            fee_calculator = recent_blockhash['result']['value']['feeCalculator']
            
            # Calculate fee in lamports
            fee_lamports = fee_calculator['lamportsPerSignature']
            
            # Convert to SOL
            fee = Decimal(fee_lamports) / Decimal(10**9)
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Solana balance"""
        try:
            # Try Solana client first
            result = self.client.get_balance(address)
            if not result['result']['value']:
                return Decimal('0'), "Failed to get balance"
                
            # Convert lamports to SOL
            balance = Decimal(result['result']['value']) / Decimal(10**9)
            return balance, None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Solana client: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('solana', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Solana address"""
        try:
            # Check if address is a valid base58 string
            if not address or len(address) != 44:
                return False
                
            # Try to get account info
            result = self.client.get_account_info(address)
            return result['result']['value'] is not None
            
        except:
            return False
            
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Solana transaction status"""
        try:
            # Try Solana client first
            try:
                result = self.client.get_transaction(tx_hash)
                if result['result']:
                    if result['result']['meta']['status']['Ok'] is None:
                        return 'confirmed', None
                    return 'failed', None
            except:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('solana', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Solana transaction details"""
        try:
            # Try Solana client first
            try:
                result = self.client.get_transaction(tx_hash)
                if result['result']:
                    return {
                        'hash': tx_hash,
                        'from': result['result']['transaction']['message']['accountKeys'][0],
                        'to': result['result']['transaction']['message']['accountKeys'][1],
                        'value': str(Decimal(result['result']['meta']['postBalances'][1] - 
                                          result['result']['meta']['preBalances'][1]) / Decimal(10**9)),
                        'status': 'confirmed' if result['result']['meta']['status']['Ok'] is None else 'failed',
                        'block_number': result['result']['slot'],
                        'timestamp': datetime.fromtimestamp(
                            result['result']['blockTime']
                        ).isoformat()
                    }, None
            except:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('solana', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e) 