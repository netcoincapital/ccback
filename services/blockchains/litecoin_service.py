from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
from bitcoinlib.transactions import Transaction
from bitcoinlib.keys import Key
from bitcoinlib.scripts import Script

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class LitecoinService(BaseBlockchainService):
    """Litecoin blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Litecoin node URL
        self.litecoin_node_url = os.getenv('LITECOIN_NODE_URL')
        if not self.litecoin_node_url:
            raise RuntimeError("LITECOIN_NODE_URL environment variable is not set")
            
        # Initialize Tatum helper for fallback
        self.tatum = TatumHelper()
        
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: Decimal, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a Litecoin transaction"""
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
                    "blockchain": "litecoin",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://blockchair.com/litecoin/transaction/{transaction_id}",
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
        """Send a prepared Litecoin transaction"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return None, "Transaction not found or expired"
                
            try:
                # Create key from private key
                key = Key(private_key)
                
                # Create transaction
                tx = Transaction()
                
                # Add inputs (UTXOs)
                utxos, error = self._get_utxos(tx_data['sender'])
                if error:
                    return None, f"Error getting UTXOs: {error}"
                    
                for utxo in utxos:
                    tx.add_input(utxo['txid'], utxo['vout'])
                    
                # Add output
                tx.add_output(
                    tx_data['recipient'],
                    int(Decimal(tx_data['amount']) * Decimal(10**8))  # Convert to litoshis
                )
                
                # Add change output if needed
                total_input = sum(utxo['amount'] for utxo in utxos)
                change_amount = total_input - Decimal(tx_data['amount']) - Decimal(tx_data['fee'])
                if change_amount > 0:
                    tx.add_output(
                        tx_data['sender'],
                        int(change_amount * Decimal(10**8))
                    )
                    
                # Sign transaction
                tx.sign(key)
                
                # Send transaction
                result = self._broadcast_transaction(tx.serialize())
                
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
                self.logger.error(f"Error sending transaction via Litecoin client: {str(e)}")
                
                # Fallback to Tatum
                result, error = self.tatum.send_transaction(
                    'litecoin',
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
        """Estimate Litecoin transaction fee"""
        try:
            # Get current fee rate
            response = requests.get(f"{self.litecoin_node_url}/fees")
            if response.status_code != 200:
                return Decimal('0'), "Failed to get fee rate"
                
            fee_rate = response.json()['fastestFee']
            
            # Estimate transaction size (in bytes)
            # Standard P2PKH input: 148 bytes
            # Standard P2PKH output: 34 bytes
            # Transaction overhead: 10 bytes
            num_inputs = 1  # Conservative estimate
            num_outputs = 2  # Recipient + change
            tx_size = (num_inputs * 148) + (num_outputs * 34) + 10
            
            # Calculate fee in litoshis
            fee_litoshis = tx_size * fee_rate
            
            # Convert to LTC
            fee = Decimal(fee_litoshis) / Decimal(10**8)
            
            return fee, None
            
        except Exception as e:
            self.logger.error(f"Error estimating fee: {str(e)}")
            return Decimal('0'), str(e)
            
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Litecoin balance"""
        try:
            # Try Litecoin node first
            response = requests.get(f"{self.litecoin_node_url}/address/{address}/balance")
            if response.status_code == 200:
                balance_litoshis = response.json()['balance']
                balance = Decimal(balance_litoshis) / Decimal(10**8)
                return balance, None
                
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('litecoin', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
        except Exception as e:
            self.logger.error(f"Error getting balance: {str(e)}")
            return Decimal('0'), str(e)
            
    def validate_address(self, address: str) -> bool:
        """Validate Litecoin address"""
        try:
            # Check if address is a valid base58 string
            if not address or len(address) < 26 or len(address) > 35:
                return False
                
            # Try to decode address
            script = Script.from_address(address)
            return script is not None
            
        except:
            return False
            
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Litecoin transaction status"""
        try:
            # Try Litecoin node first
            response = requests.get(f"{self.litecoin_node_url}/tx/{tx_hash}")
            if response.status_code == 200:
                tx_data = response.json()
                if tx_data['confirmations'] > 0:
                    return 'confirmed', None
                return 'pending', None
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('litecoin', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Litecoin transaction details"""
        try:
            # Try Litecoin node first
            response = requests.get(f"{self.litecoin_node_url}/tx/{tx_hash}")
            if response.status_code == 200:
                tx_data = response.json()
                return {
                    'hash': tx_hash,
                    'from': tx_data['vin'][0]['prevout']['scriptpubkey_address'],
                    'to': tx_data['vout'][0]['scriptpubkey_address'],
                    'value': str(Decimal(tx_data['vout'][0]['value']) / Decimal(10**8)),
                    'status': 'confirmed' if tx_data['confirmations'] > 0 else 'pending',
                    'block_number': tx_data['block_height'],
                    'timestamp': datetime.fromtimestamp(
                        tx_data['block_time']
                    ).isoformat()
                }, None
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('litecoin', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e)
            
    def _get_utxos(self, address: str) -> Tuple[list, Optional[str]]:
        """Get unspent transaction outputs for an address"""
        try:
            response = requests.get(f"{self.litecoin_node_url}/address/{address}/utxo")
            if response.status_code != 200:
                return [], "Failed to get UTXOs"
                
            utxos = []
            for utxo in response.json():
                utxos.append({
                    'txid': utxo['txid'],
                    'vout': utxo['vout'],
                    'amount': Decimal(utxo['value']) / Decimal(10**8)
                })
                
            return utxos, None
            
        except Exception as e:
            self.logger.error(f"Error getting UTXOs: {str(e)}")
            return [], str(e)
            
    def _broadcast_transaction(self, raw_tx: str) -> Dict:
        """Broadcast a raw transaction to the Litecoin network"""
        try:
            response = requests.post(
                f"{self.litecoin_node_url}/tx/send",
                json={'rawtx': raw_tx}
            )
            if response.status_code != 200:
                raise Exception("Failed to broadcast transaction")
                
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error broadcasting transaction: {str(e)}")
            raise 