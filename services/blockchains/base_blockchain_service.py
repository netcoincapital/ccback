from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
import json
from utils.logging_config import get_logger
from services.transaction_storage import TransactionStorage

class BaseBlockchainService(ABC):
    """Base class for all blockchain services"""
    
    def __init__(self):
        self.logger = get_logger(__file__)
        self.storage = TransactionStorage()
        
    @abstractmethod
    def prepare_transaction(self, sender: str, recipient: str, amount: str, 
                          private_key: str = None) -> Tuple[Dict, Optional[str]]:
        """
        Prepare a transaction for sending.
        
        Args:
            sender: Sender's address
            recipient: Recipient's address
            amount: Amount to send (as a string)
            private_key: Optional private key for signing
            
        Returns:
            Tuple of (transaction details dict, error message if any)
        """
        pass
        
    @abstractmethod
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """
        Send a prepared transaction.
        
        Args:
            transaction_id: ID of the prepared transaction
            private_key: Private key for signing the transaction
            
        Returns:
            Tuple of (transaction result dict, error message if any)
        """
        pass
        
    @abstractmethod
    def estimate_fee(self, sender: str, recipient: str, amount: Decimal) -> Tuple[Decimal, Optional[str]]:
        """
        Estimate the transaction fee.
        
        Args:
            sender: Sender's address
            recipient: Recipient's address
            amount: Amount to send
            
        Returns:
            Tuple of (estimated fee, error message if any)
        """
        pass
        
    @abstractmethod
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """
        Get the balance of an address.
        
        Args:
            address: Address to check
            
        Returns:
            Tuple of (balance, error message if any)
        """
        pass
        
    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """
        Validate a blockchain address.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        pass
        
    @abstractmethod
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """
        Get the status of a transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Tuple of (status, error message if any)
        """
        pass
        
    @abstractmethod
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """
        Get details of a transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Tuple of (transaction details dict, error message if any)
        """
        pass
        
    def _log_transaction(self, transaction_id: str, event: str, details: Dict = None):
        """Log a transaction event"""
        log_data = {
            'transaction_id': transaction_id,
            'event': event,
            'timestamp': datetime.now().isoformat()
        }
        if details:
            log_data.update(details)
        self.logger.info(f"Transaction event: {json.dumps(log_data)}")
        
    def _get_stored_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get stored transaction data"""
        return self.storage.get_transaction(transaction_id)
        
    def _store_transaction(self, transaction_id: str, tx_data: Dict, expires_minutes: int = 15) -> datetime:
        """Store transaction data"""
        return self.storage.store_transaction(transaction_id, tx_data, expires_minutes) 