from typing import Dict, Optional
from datetime import datetime, timedelta
import json
import redis
import os
from utils.logging_config import get_logger

class TransactionStorage:
    """Handles storage and retrieval of transaction data"""
    
    def __init__(self):
        self.logger = get_logger(__file__)
        
        # Initialize Redis connection
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis = redis.from_url(redis_url)
        
        # Default expiration time for transactions (15 minutes)
        self.default_expiry = 15 * 60  # 15 minutes in seconds
        
    def store_transaction(self, transaction_id: str, tx_data: Dict, expires_minutes: int = 15) -> datetime:
        """
        Store transaction data with expiration.
        
        Args:
            transaction_id: Unique identifier for the transaction
            tx_data: Transaction data to store
            expires_minutes: Minutes until transaction expires (default: 15)
            
        Returns:
            datetime: Expiration time
        """
        try:
            # Calculate expiration time
            expires_at = datetime.now() + timedelta(minutes=expires_minutes)
            
            # Add expiration time to transaction data
            tx_data['expires_at'] = expires_at.isoformat()
            
            # Store in Redis with expiration
            self.redis.setex(
                f"tx:{transaction_id}",
                expires_minutes * 60,  # Convert to seconds
                json.dumps(tx_data)
            )
            
            self.logger.debug(f"Stored transaction {transaction_id} with expiration {expires_at}")
            return expires_at
            
        except Exception as e:
            self.logger.error(f"Error storing transaction {transaction_id}: {str(e)}")
            raise
            
    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """
        Retrieve transaction data.
        
        Args:
            transaction_id: ID of the transaction to retrieve
            
        Returns:
            Dict containing transaction data or None if not found/expired
        """
        try:
            # Get from Redis
            tx_data = self.redis.get(f"tx:{transaction_id}")
            
            if not tx_data:
                self.logger.debug(f"Transaction {transaction_id} not found or expired")
                return None
                
            # Parse JSON data
            data = json.loads(tx_data)
            
            # Check if expired
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now() > expires_at:
                self.logger.debug(f"Transaction {transaction_id} has expired")
                self.redis.delete(f"tx:{transaction_id}")
                return None
                
            return data
            
        except Exception as e:
            self.logger.error(f"Error retrieving transaction {transaction_id}: {str(e)}")
            return None
            
    def delete_transaction(self, transaction_id: str) -> bool:
        """
        Delete a transaction.
        
        Args:
            transaction_id: ID of the transaction to delete
            
        Returns:
            bool: True if deleted, False if not found
        """
        try:
            result = self.redis.delete(f"tx:{transaction_id}")
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error deleting transaction {transaction_id}: {str(e)}")
            return False
            
    def get_all_transactions(self) -> Dict[str, Dict]:
        """
        Get all stored transactions.
        
        Returns:
            Dict mapping transaction IDs to their data
        """
        try:
            transactions = {}
            for key in self.redis.scan_iter("tx:*"):
                tx_id = key.decode('utf-8')[3:]  # Remove 'tx:' prefix
                tx_data = self.get_transaction(tx_id)
                if tx_data:
                    transactions[tx_id] = tx_data
            return transactions
        except Exception as e:
            self.logger.error(f"Error getting all transactions: {str(e)}")
            return {}
            
    def cleanup_expired(self) -> int:
        """
        Clean up expired transactions.
        
        Returns:
            int: Number of transactions cleaned up
        """
        try:
            count = 0
            for key in self.redis.scan_iter("tx:*"):
                tx_id = key.decode('utf-8')[3:]
                if not self.get_transaction(tx_id):  # This will delete expired transactions
                    count += 1
            return count
        except Exception as e:
            self.logger.error(f"Error cleaning up expired transactions: {str(e)}")
            return 0 