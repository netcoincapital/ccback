from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
import requests
from datetime import datetime, timedelta

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class XRPService(BaseBlockchainService):
    """XRP (Ripple) blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Default XRP node URLs if environment variable is not set
        DEFAULT_XRP_NODES = [
            "https://s1.ripple.com:51234",
            "https://s2.ripple.com:51234",
            "https://xrplcluster.com"
        ]
        
        # Initialize XRP client
        self.xrp_node_url = os.getenv('XRP_NODE_URL') or os.getenv('RIPPLE_NODE_URL')
        if not self.xrp_node_url:
            self.xrp_node_url = DEFAULT_XRP_NODES[0]
            self.logger.warning(
                f"XRP_NODE_URL environment variable is not set. "
                f"Using default XRP node: {self.xrp_node_url}"
            )
        
        try:
            # Import ripple-lib libraries if available
            # import xrpl.wallet
            # import xrpl.clients
            # import xrpl.transaction
            # self.client = xrpl.clients.JsonRpcClient(self.xrp_node_url)
            self.client_available = False  # Set to True if client initialization succeeds
            self.logger.info("XRP client initialization skipped - using Tatum API only")
        except ImportError:
            self.client_available = False
            self.logger.warning("XRP client libraries not available. Using Tatum API only.")
        except Exception as e:
            self.client_available = False
            self.logger.error(f"Failed to initialize XRP client: {str(e)}")
        
        # Initialize Tatum helper for API access
        try:
            self.tatum = TatumHelper()
            self.logger.info("Tatum helper initialized for XRP service")
        except Exception as e:
            self.logger.error(f"Failed to initialize Tatum helper: {str(e)}")
            self.tatum = None
    
    @handle_api_errors
    def prepare_transaction(self, sender: str, recipient: str, amount: str, 
                          smart_contract_address: str = None) -> Tuple[Dict, Optional[str]]:
        """Prepare an XRP transaction"""
        try:
            self.logger.info(f"Starting XRP transaction preparation")
            self.logger.debug(f"Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            
            # Convert amount to Decimal for internal calculations
            try:
                amount_decimal = Decimal(str(amount).strip())
                self.logger.debug(f"Successfully converted amount {amount} to Decimal {amount_decimal}")
            except Exception as e:
                self.logger.error(f"Error converting amount to Decimal: {str(e)}")
                return {}, f"Invalid amount format: {amount}"
                
            # Validate addresses
            if not self.validate_address(sender):
                self.logger.error(f"Invalid sender address: {sender}")
                return {}, "Invalid sender address"
                
            if not self.validate_address(recipient):
                self.logger.error(f"Invalid recipient address: {recipient}")
                return {}, "Invalid recipient address"
                
            # Get sender's balance
            self.logger.debug(f"Getting balance for sender: {sender}")
            balance, error = self.get_balance(sender)
            if error:
                self.logger.error(f"Error getting balance: {error}")
                return {}, f"Error getting balance: {error}"
            else:
                self.logger.info(f"Sender balance: {balance} XRP")
            
            # Estimate fee
            self.logger.debug(f"Estimating fee for transaction")
            fee, error = self.estimate_fee(sender, recipient, amount_decimal)
            if error:
                self.logger.error(f"Error estimating fee: {error}")
                # Use default fee
                fee = Decimal('0.00001')  # Default XRP fee
                self.logger.warning(f"Using default fee: {fee} XRP")
            else:
                self.logger.info(f"Estimated fee: {fee} XRP")
                
            # Check if sender has enough balance
            if balance < amount_decimal + fee:
                self.logger.warning(f"Insufficient balance. Required: {amount_decimal + fee}, Available: {balance}")
                return {}, f"Insufficient balance. Available: {balance}, Required: {amount_decimal + fee}"
                
            # Account for XRP reserve requirement (20 XRP minimum balance)
            xrp_reserve = Decimal('20')  # XRP account reserve
            if (balance - amount_decimal - fee) < xrp_reserve:
                self.logger.warning(f"Transaction would bring balance below reserve requirement of {xrp_reserve} XRP")
                return {}, f"Transaction would bring balance below reserve requirement of {xrp_reserve} XRP"
                
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            self.logger.debug(f"Generated transaction ID: {transaction_id}")
            
            # Calculate balance after transaction
            balance_after = balance - amount_decimal - fee
            
            # Prepare transaction details
            tx_details = {
                "transaction_id": transaction_id,
                "details": {
                    "amount": str(amount_decimal),
                    "blockchain": "xrp",
                    "estimated_fee": str(fee),
                    "explorer_url": f"https://xrpscan.com/tx/{transaction_id}",
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
            
            self.logger.info(f"Successfully prepared XRP transaction: {transaction_id}")
            return tx_details, None
            
        except Exception as e:
            self.logger.error(f"Error preparing XRP transaction: {str(e)}")
            return {}, str(e)
    
    @handle_api_errors
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared XRP transaction using Tatum API broadcast endpoint"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return {}, "Transaction not found or expired"
            
            # Extract transaction details
            sender = tx_data.get('details', {}).get('sender')
            recipient = tx_data.get('details', {}).get('recipient')
            amount_str = tx_data.get('details', {}).get('amount')
            
            if not all([sender, recipient, amount_str]):
                self.logger.error(f"Transaction data is incomplete: {tx_data}")
                return {}, "Transaction data is incomplete"
                
            # Convert amount to string for Tatum API
            try:
                amount = Decimal(amount_str)
                amount_str = str(amount)
            except Exception as e:
                self.logger.error(f"Error converting amount to Decimal: {str(e)}")
                return {}, f"Invalid amount format: {amount_str}"
            
            # Use Tatum XRP broadcast endpoint
            if not self.tatum:
                return {}, "Tatum helper not initialized"
            
            self.logger.info(f"Broadcasting XRP transaction via Tatum broadcast endpoint")
            
            # Call TatumHelper's send_transaction method
            result, error = self.tatum.send_transaction(
                'xrp', 
                sender, 
                recipient, 
                amount_str, 
                private_key
            )
            
            if error:
                self.logger.error(f"Error broadcasting XRP transaction: {error}")
                return {}, f"Error broadcasting transaction: {error}"
                
            tx_hash = result.get('transaction_hash') or result.get('txId')
            if not tx_hash:
                self.logger.error(f"Missing transaction hash in response: {result}")
                return {}, "Missing transaction hash in response"
            
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
            
        except Exception as e:
            self.logger.error(f"Error sending XRP transaction: {str(e)}")
            return {}, str(e)
    
    @handle_api_errors
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """Estimate XRP transaction fee"""
        try:
            # XRP has standard fees that are dynamically adjusted by the network
            # Use Tatum API to get current fee
            if self.tatum:
                try:
                    # Endpoint for XRP fee
                    url = f"{self.tatum.base_url}/xrp/fee"
                    response = requests.get(
                        url, 
                        headers=self.tatum.headers
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        fee = Decimal(str(result.get('fee', '0.00001')))
                        self.logger.debug(f"XRP fee from Tatum: {fee}")
                        return fee, None
                except Exception as e:
                    self.logger.warning(f"Error getting XRP fee from Tatum: {str(e)}")
            
            # Default XRP fee
            return Decimal('0.00001'), None
            
        except Exception as e:
            self.logger.error(f"Error estimating XRP fee: {str(e)}")
            return Decimal('0.00001'), str(e)
    
    @handle_api_errors
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get XRP balance"""
        try:
            # Use Tatum API
            if self.tatum:
                balance_data, error = self.tatum.get_balance('xrp', address)
                if error:
                    self.logger.error(f"Error getting XRP balance from Tatum: {error}")
                    return Decimal('0'), error
                
                try:
                    balance = Decimal(str(balance_data.get('balance', '0')))
                    return balance, None
                except Exception as e:
                    self.logger.error(f"Error parsing XRP balance: {str(e)}")
            
            return Decimal('0'), "XRP balance retrieval not available"
            
        except Exception as e:
            self.logger.error(f"Error getting XRP balance: {str(e)}")
            return Decimal('0'), str(e)
    
    def validate_address(self, address: str) -> bool:
        """Validate XRP address"""
        # Basic XRP address validation (starts with 'r' and is between 25-35 chars)
        return address.startswith('r') and len(address) >= 25 and len(address) <= 35
    
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get XRP transaction status"""
        try:
            # Use Tatum API
            if self.tatum:
                tx_data, error = self.tatum.get_transaction('xrp', tx_hash)
                if error:
                    return 'unknown', error
                
                # Check status based on fields in the response
                if 'status' in tx_data:
                    status = tx_data.get('status', '').lower()
                    if status in ['success', 'temsuccess']:
                        return 'confirmed', None
                    elif status in ['failed', 'temfailure']:
                        return 'failed', None
                    else:
                        return 'pending', None
                        
                # Check ledger_index to determine if confirmed
                if 'ledger_index' in tx_data:
                    return 'confirmed', None
            
            return 'unknown', "Transaction status retrieval not available"
            
        except Exception as e:
            self.logger.error(f"Error getting XRP transaction status: {str(e)}")
            return 'unknown', str(e)
    
    @handle_api_errors
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get XRP transaction details"""
        try:
            # Use Tatum API
            if self.tatum:
                return self.tatum.get_transaction('xrp', tx_hash)
            
            return {}, "Transaction details retrieval not available"
            
        except Exception as e:
            self.logger.error(f"Error getting XRP transaction details: {str(e)}")
            return {}, str(e) 