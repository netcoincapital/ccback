from services.transaction_storage import TransactionStorage
from utils.logging_config import get_logger

class SharedTransactionStorage:
    """Singleton shared transaction storage for all blockchain services"""
    
    _instance = None
    _storage = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedTransactionStorage, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = get_logger(__file__)
            try:
                self._storage = TransactionStorage()
                self.logger.info("Shared transaction storage initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize shared transaction storage: {str(e)}")
                self._storage = None
            self._initialized = True
    
    def store_transaction(self, transaction_id: str, tx_data: dict, expires_minutes: int = 30):
        """Store transaction data"""
        if self._storage:
            return self._storage.store_transaction(transaction_id, tx_data, expires_minutes)
        else:
            self.logger.error("Shared storage not available")
            return None
    
    def get_transaction(self, transaction_id: str):
        """Get transaction data"""
        if self._storage:
            return self._storage.get_transaction(transaction_id)
        else:
            self.logger.error("Shared storage not available")
            return None
    
    def delete_transaction(self, transaction_id: str):
        """Delete transaction data"""
        if self._storage:
            return self._storage.delete_transaction(transaction_id)
        else:
            self.logger.error("Shared storage not available")
            return False
    
    def get_all_transactions(self):
        """Get all transactions"""
        if self._storage:
            return self._storage.get_all_transactions()
        else:
            self.logger.error("Shared storage not available")
            return {}
    
    def get_storage_info(self):
        """Get storage information"""
        if self._storage:
            return self._storage.get_storage_info()
        else:
            return {
                "storage_type": "unavailable",
                "error": "Shared storage not initialized"
            }

# Global instance
shared_storage = SharedTransactionStorage() 