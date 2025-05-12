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

class BSCService(BaseBlockchainService):
    """Binance Smart Chain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # Initialize Web3 with BSC node
        self.bsc_node_url = os.getenv('BSC_NODE_URL')
        if not self.bsc_node_url:
            raise RuntimeError("BSC_NODE_URL environment variable is not set")
            
        self.web3 = Web3(Web3.HTTPProvider(self.bsc_node_url))
        
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
            
            # Prepare transaction details
            tx_details = {
                "transaction_id": transaction_id,
                "details": {
                    "amount": amount,
                    "blockchain": "bsc",
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
        """Send a BSC transaction"""
        try:
            # Get transaction details from storage
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return {}, "Transaction not found or expired"
                
            # Prepare transaction parameters
            params = {
                "from": tx_data["sender_address"],
                "to": tx_data["recipient_address"],
                "value": self.web3.to_wei(tx_data["amount"], "ether"),
                "gas": 21000,  # Default gas limit for BNB transfers
                "gasPrice": self._get_cached_gas_price(),
                "nonce": self.web3.eth.get_transaction_count(tx_data["sender_address"]),
                "chainId": 56  # BSC mainnet chain ID
            }
            
            # Add contract data if it's a token transfer
            if tx_data.get("smart_contract_address"):
                # TODO: Implement BEP20 token transfer data
                pass
                
            # Sign and send transaction
            try:
                signed_tx = self.web3.eth.account.sign_transaction(params, private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                # Log transaction
                self._log_transaction("send", {
                    "transaction_id": transaction_id,
                    "tx_hash": tx_hash.hex()
                })
                
                return {
                    "transaction_hash": tx_hash.hex(),
                    "status": "pending"
                }, None
                
            except Exception as e:
                # Fallback to Tatum if Web3 fails
                self.logger.warning(f"Web3 transaction failed, falling back to Tatum: {str(e)}")
                return self.tatum.send_transaction(
                    "binance smart chain",
                    tx_data["sender_address"],
                    private_key,
                    tx_data["recipient_address"],
                    tx_data["amount"],
                    tx_data
                )
                
        except Exception as e:
            error_msg = f"Error sending transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
            
    @handle_api_errors
    def estimate_fee(self, sender_address: str, recipient_address: str,
                    amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Decimal, Optional[str]]:
        """Estimate BSC transaction fee"""
        try:
            # Try to get cached gas price first
            gas_price = self._get_cached_gas_price()
            
            if not gas_price:
                # Get gas price from Web3
                try:
                    gas_price = Decimal(str(self.web3.eth.gas_price)) / Decimal('1e9')  # Convert from Wei to Gwei
                    self._update_gas_price_cache(gas_price)
                except Exception as e:
                    self.logger.warning(f"Failed to get gas price from Web3: {str(e)}")
                    # Fallback to Tatum
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
                balance_wei = self.web3.eth.get_balance(address)
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
        return self.web3.is_address(address)
        
    @handle_api_errors
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get BSC transaction status"""
        try:
            # Try Web3 first
            try:
                tx = self.web3.eth.get_transaction(tx_hash)
                if not tx:
                    return "not_found", None
                    
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
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
                tx = self.web3.eth.get_transaction(tx_hash)
                if tx:
                    receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                    
                    # Format transaction details
                    details = {
                        "hash": tx_hash,
                        "blockNumber": tx.get("blockNumber"),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "value": str(self.web3.from_wei(tx.get("value", 0), "ether")),
                        "gasPrice": str(self.web3.from_wei(tx.get("gasPrice", 0), "gwei")),
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
        # TODO: Implement transaction storage/retrieval
        return None 