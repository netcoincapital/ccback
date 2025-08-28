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
        
        # Initialize Redis connection with improved authentication support
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_password = os.getenv('REDIS_PASSWORD')
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_db = int(os.getenv('REDIS_DB', '0'))
        
        self.redis = None
        self.use_memory_fallback = False
        self.memory_storage = {}  # Fallback storage
        
        self.logger.info(f"Attempting Redis connection - URL: {redis_url}, Host: {redis_host}, Port: {redis_port}, DB: {redis_db}")
        
        try:
            # Try different connection methods
            connection_methods = []
            
            # Method 1: Using Redis URL
            if redis_url and redis_url != 'redis://localhost:6379':
                connection_methods.append(('URL', lambda: redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)))
            
            # Method 2: Using individual parameters with password
            if redis_password:
                connection_methods.append(('Password Auth', lambda: redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    decode_responses=False
                )))
            
            # Method 3: Using individual parameters without password
            connection_methods.append(('No Auth', lambda: redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=False
            )))
            
            # Try each connection method
            for method_name, connection_func in connection_methods:
                try:
                    self.logger.info(f"Trying Redis connection method: {method_name}")
                    self.redis = connection_func()
                    
                    # Test the connection
                    ping_result = self.redis.ping()
                    self.logger.info(f"Redis connection successful using {method_name}: {ping_result}")
                    break
                    
                except redis.exceptions.AuthenticationError as e:
                    self.logger.warning(f"Redis authentication failed for method {method_name}: {str(e)}")
                    continue
                except redis.exceptions.ConnectionError as e:
                    self.logger.warning(f"Redis connection failed for method {method_name}: {str(e)}")
                    continue
                except Exception as e:
                    self.logger.warning(f"Redis connection error for method {method_name}: {str(e)}")
                    continue
            
            # If no connection method worked, fall back to memory
            if not self.redis:
                raise Exception("All Redis connection methods failed")
                
        except Exception as e:
            self.logger.error(f"All Redis connection attempts failed: {str(e)}")
            self.logger.warning("Falling back to in-memory storage for transactions")
            self.use_memory_fallback = True
            self.redis = None
        
        # Extended expiration time for transactions (30 minutes for testing)
        self.default_expiry = 30 * 60  # 30 minutes in seconds
        
        # Log the final storage method
        if self.use_memory_fallback:
            self.logger.warning("Using in-memory storage for transactions - data will not persist across restarts")
        else:
            self.logger.info("Using Redis storage for transactions")
        
    def store_transaction(self, transaction_id: str, tx_data: Dict, expires_minutes: int = 30) -> datetime:
        """
        Store transaction data with expiration.
        
        Args:
            transaction_id: Unique identifier for the transaction
            tx_data: Transaction data to store
            expires_minutes: Minutes until transaction expires (default: 30)
            
        Returns:
            datetime: Expiration time
        """
        try:
            # Calculate expiration time
            expires_at = datetime.now() + timedelta(minutes=expires_minutes)
            
            # Add expiration time to transaction data
            tx_data['expires_at'] = expires_at.isoformat()
            tx_data['stored_at'] = datetime.now().isoformat()
            
            self.logger.info(f"Storing transaction {transaction_id} with expiration {expires_at}")
            
            if self.use_memory_fallback:
                # Use in-memory storage
                self.memory_storage[f"tx:{transaction_id}"] = {
                    'data': tx_data,
                    'expires_at': expires_at
                }
                self.logger.debug(f"Stored transaction {transaction_id} in memory with expiration {expires_at}")
            else:
                # Store in Redis with expiration
                try:
                    redis_key = f"tx:{transaction_id}"
                    self.redis.setex(
                        redis_key,
                        expires_minutes * 60,  # Convert to seconds
                        json.dumps(tx_data)
                    )
                    self.logger.debug(f"Stored transaction {transaction_id} in Redis with expiration {expires_at}")
                    
                    # Verify storage
                    stored_data = self.redis.get(redis_key)
                    if stored_data:
                        self.logger.debug(f"Verified transaction {transaction_id} is stored in Redis")
                    else:
                        self.logger.error(f"Failed to verify transaction {transaction_id} storage in Redis")
                        
                except redis.exceptions.AuthenticationError as e:
                    self.logger.error(f"Redis authentication error storing transaction {transaction_id}: {str(e)}")
                    self.logger.warning("Switching to memory fallback due to Redis authentication error")
                    self.use_memory_fallback = True
                    self.redis = None
                    # Store in memory instead
                    self.memory_storage[f"tx:{transaction_id}"] = {
                        'data': tx_data,
                        'expires_at': expires_at
                    }
                    self.logger.debug(f"Stored transaction {transaction_id} in memory with expiration {expires_at}")
            
            return expires_at
            
        except Exception as e:
            self.logger.error(f"Error storing transaction {transaction_id}: {str(e)}")
            # Try memory fallback if Redis fails
            if not self.use_memory_fallback:
                self.logger.warning("Redis storage failed, falling back to memory storage for this transaction")
                expires_at = datetime.now() + timedelta(minutes=expires_minutes)
                tx_data['expires_at'] = expires_at.isoformat()
                tx_data['stored_at'] = datetime.now().isoformat()
                self.memory_storage[f"tx:{transaction_id}"] = {
                    'data': tx_data,
                    'expires_at': expires_at
                }
                self.use_memory_fallback = True  # Switch to memory fallback permanently
                return expires_at
            else:
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
            self.logger.debug(f"Retrieving transaction {transaction_id}")
            
            if self.use_memory_fallback:
                # Get from memory storage
                tx_key = f"tx:{transaction_id}"
                if tx_key not in self.memory_storage:
                    self.logger.warning(f"Transaction {transaction_id} not found in memory storage")
                    self.logger.debug(f"Available transactions in memory: {list(self.memory_storage.keys())}")
                    return None
                
                tx_entry = self.memory_storage[tx_key]
                
                # Check if expired
                if datetime.now() > tx_entry['expires_at']:
                    self.logger.warning(f"Transaction {transaction_id} has expired (stored until {tx_entry['expires_at']})")
                    del self.memory_storage[tx_key]
                    return None
                
                self.logger.debug(f"Successfully retrieved transaction {transaction_id} from memory")
                return tx_entry['data']
            else:
                # Get from Redis
                redis_key = f"tx:{transaction_id}"
                try:
                    tx_data = self.redis.get(redis_key)
                    
                    if not tx_data:
                        self.logger.warning(f"Transaction {transaction_id} not found in Redis")
                        # Check if the key exists with TTL
                        ttl = self.redis.ttl(redis_key)
                        if ttl == -2:
                            self.logger.debug(f"Transaction {transaction_id} key does not exist in Redis")
                        elif ttl == -1:
                            self.logger.debug(f"Transaction {transaction_id} key exists but has no expiration")
                        else:
                            self.logger.debug(f"Transaction {transaction_id} key exists with TTL: {ttl} seconds")
                        return None
                        
                    # Parse JSON data
                    try:
                        data = json.loads(tx_data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse transaction data for {transaction_id}: {str(e)}")
                        return None
                    
                    # Check if expired (double-check even though Redis should handle this)
                    if 'expires_at' in data:
                        expires_at = datetime.fromisoformat(data['expires_at'])
                        if datetime.now() > expires_at:
                            self.logger.warning(f"Transaction {transaction_id} has expired (stored until {expires_at})")
                            self.redis.delete(redis_key)
                            return None
                    
                    self.logger.debug(f"Successfully retrieved transaction {transaction_id} from Redis")
                    return data
                    
                except redis.exceptions.AuthenticationError as e:
                    self.logger.error(f"Redis authentication error for transaction {transaction_id}: {str(e)}")
                    self.logger.warning("Switching to memory fallback due to Redis authentication error")
                    self.use_memory_fallback = True
                    self.redis = None
                    # Try memory storage
                    return self.get_transaction(transaction_id)
                    
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
            self.logger.debug(f"Deleting transaction {transaction_id}")
            
            if self.use_memory_fallback:
                tx_key = f"tx:{transaction_id}"
                if tx_key in self.memory_storage:
                    del self.memory_storage[tx_key]
                    self.logger.debug(f"Deleted transaction {transaction_id} from memory")
                    return True
                return False
            else:
                result = self.redis.delete(f"tx:{transaction_id}")
                success = bool(result)
                self.logger.debug(f"Deleted transaction {transaction_id} from Redis: {success}")
                return success
        except Exception as e:
            self.logger.error(f"Error deleting transaction {transaction_id}: {str(e)}")
            return False
            
    def get_all_transactions(self) -> Dict[str, Dict]:
        """
        Get all stored transactions.
        
        Returns:
            Dict mapping transaction IDs to transaction data
        """
        try:
            if self.use_memory_fallback:
                # Get all from memory storage
                result = {}
                for tx_key, tx_entry in self.memory_storage.items():
                    # Remove 'tx:' prefix from key
                    transaction_id = tx_key.replace('tx:', '')
                    result[transaction_id] = tx_entry['data']
                return result
            else:
                # Get all from Redis
                try:
                    result = {}
                    # Get all keys with 'tx:' prefix
                    pattern = "tx:*"
                    keys = self.redis.keys(pattern)
                    
                    for key in keys:
                        tx_data = self.redis.get(key)
                        if tx_data:
                            try:
                                data = json.loads(tx_data)
                                # Remove 'tx:' prefix from key
                                transaction_id = key.decode('utf-8').replace('tx:', '')
                                result[transaction_id] = data
                            except json.JSONDecodeError as e:
                                self.logger.error(f"Failed to parse transaction data for {key}: {str(e)}")
                                continue
                    
                    return result
                    
                except redis.exceptions.AuthenticationError as e:
                    self.logger.error(f"Redis authentication error in get_all_transactions: {str(e)}")
                    self.logger.warning("Switching to memory fallback due to Redis authentication error")
                    self.use_memory_fallback = True
                    self.redis = None
                    # Try memory storage
                    return self.get_all_transactions()
                    
        except Exception as e:
            self.logger.error(f"Error getting all transactions: {str(e)}")
            return {}
            
    def get_all_transaction_keys(self) -> list:
        """
        Get all transaction keys (IDs) currently stored.
        
        Returns:
            list: List of transaction IDs
        """
        try:
            keys = []
            
            if self.use_memory_fallback:
                current_time = datetime.now()
                for key, tx_entry in self.memory_storage.items():
                    if key.startswith("tx:"):
                        tx_id = key[3:]  # Remove 'tx:' prefix
                        # Check if expired
                        if current_time <= tx_entry['expires_at']:
                            keys.append(tx_id)
                        else:
                            # Remove expired transaction
                            del self.memory_storage[key]
            else:
                for key in self.redis.scan_iter("tx:*"):
                    tx_id = key.decode('utf-8')[3:]  # Remove 'tx:' prefix
                    # Check if transaction is still valid
                    if self.get_transaction(tx_id):
                        keys.append(tx_id)
                        
            return keys
        except Exception as e:
            self.logger.error(f"Error getting all transaction keys: {str(e)}")
            return []
            
    def cleanup_expired(self) -> int:
        """
        Clean up expired transactions.
        
        Returns:
            int: Number of transactions cleaned up
        """
        try:
            count = 0
            
            if self.use_memory_fallback:
                current_time = datetime.now()
                expired_keys = []
                
                for key, tx_entry in self.memory_storage.items():
                    if key.startswith("tx:") and current_time > tx_entry['expires_at']:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.memory_storage[key]
                    count += 1
            else:
                for key in self.redis.scan_iter("tx:*"):
                    tx_id = key.decode('utf-8')[3:]
                    if not self.get_transaction(tx_id):  # This will delete expired transactions
                        count += 1
                        
            if count > 0:
                self.logger.info(f"Cleaned up {count} expired transactions")
            return count
        except Exception as e:
            self.logger.error(f"Error cleaning up expired transactions: {str(e)}")
            return 0
            
    def get_storage_info(self) -> Dict:
        """
        Get information about the storage system.
        
        Returns:
            Dict with storage system information
        """
        try:
            info = {
                'storage_type': 'memory' if self.use_memory_fallback else 'redis',
                'default_expiry_minutes': self.default_expiry // 60,
                'current_time': datetime.now().isoformat()
            }
            
            if self.use_memory_fallback:
                info['transaction_count'] = len([k for k in self.memory_storage.keys() if k.startswith('tx:')])
                info['memory_storage_keys'] = list(self.memory_storage.keys())
            else:
                try:
                    info['redis_connected'] = self.redis.ping()
                    info['transaction_count'] = len(list(self.redis.scan_iter("tx:*")))
                except:
                    info['redis_connected'] = False
                    info['transaction_count'] = 0
            
            return info
        except Exception as e:
            self.logger.error(f"Error getting storage info: {str(e)}")
            return {'error': str(e)} 