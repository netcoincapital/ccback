import unittest
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, timedelta
from services.blockchain_router import BlockchainServiceRouter
from services.blockchains.ethereum_service import EthereumService
from services.blockchains.bsc_service import BSCService
from services.blockchains.tron_service import TronService
from services.blockchains.polygon_service import PolygonService

class TestBlockchainServices(unittest.TestCase):
    """Test cases for blockchain services"""
    
    def setUp(self):
        """Set up test environment"""
        self.router = BlockchainServiceRouter()
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'INFURA_PROJECT_ID': 'test_infura_id',
            'BSC_NODE_URL': 'test_bsc_url',
            'TRON_NODE_URL': 'test_tron_url',
            'POLYGON_NODE_URL': 'test_polygon_url',
            'REDIS_URL': 'redis://localhost:6379'
        })
        self.env_patcher.start()
        
    def tearDown(self):
        """Clean up test environment"""
        self.env_patcher.stop()
        
    def test_router_initialization(self):
        """Test blockchain router initialization"""
        # Check if all services are initialized
        self.assertIsNotNone(self.router.get_service('ethereum'))
        self.assertIsNotNone(self.router.get_service('bsc'))
        self.assertIsNotNone(self.router.get_service('tron'))
        self.assertIsNotNone(self.router.get_service('polygon'))
        
        # Check aliases
        self.assertIsNotNone(self.router.get_service('eth'))
        self.assertIsNotNone(self.router.get_service('binance'))
        self.assertIsNotNone(self.router.get_service('trx'))
        self.assertIsNotNone(self.router.get_service('matic'))
        
    def test_ethereum_service(self):
        """Test Ethereum service"""
        service = self.router.get_service('ethereum')
        
        # Test address validation
        self.assertTrue(service.validate_address('0x742d35Cc6634C0532925a3b844Bc454e4438f44e'))
        self.assertFalse(service.validate_address('invalid_address'))
        
        # Test transaction preparation
        with patch.object(service, 'get_balance') as mock_balance, \
             patch.object(service, 'estimate_fee') as mock_fee:
            
            mock_balance.return_value = (Decimal('1.0'), None)
            mock_fee.return_value = (Decimal('0.001'), None)
            
            result, error = service.prepare_transaction(
                sender='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                recipient='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                amount=Decimal('0.1')
            )
            
            self.assertIsNone(error)
            self.assertIn('transaction_id', result)
            self.assertIn('fee', result)
            self.assertIn('expires_at', result)
            
    def test_bsc_service(self):
        """Test BSC service"""
        service = self.router.get_service('bsc')
        
        # Test address validation
        self.assertTrue(service.validate_address('0x742d35Cc6634C0532925a3b844Bc454e4438f44e'))
        self.assertFalse(service.validate_address('invalid_address'))
        
        # Test transaction preparation
        with patch.object(service, 'get_balance') as mock_balance, \
             patch.object(service, 'estimate_fee') as mock_fee:
            
            mock_balance.return_value = (Decimal('1.0'), None)
            mock_fee.return_value = (Decimal('0.001'), None)
            
            result, error = service.prepare_transaction(
                sender='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                recipient='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                amount=Decimal('0.1')
            )
            
            self.assertIsNone(error)
            self.assertIn('transaction_id', result)
            self.assertIn('fee', result)
            self.assertIn('expires_at', result)
            
    def test_tron_service(self):
        """Test TRON service"""
        service = self.router.get_service('tron')
        
        # Test address validation
        self.assertTrue(service.validate_address('TJRabPrwbZy45sbavfcjinPJC18kjpRTv8'))
        self.assertFalse(service.validate_address('invalid_address'))
        
        # Test transaction preparation
        with patch.object(service, 'get_balance') as mock_balance, \
             patch.object(service, 'estimate_fee') as mock_fee:
            
            mock_balance.return_value = (Decimal('100.0'), None)
            mock_fee.return_value = (Decimal('0.1'), None)
            
            result, error = service.prepare_transaction(
                sender='TJRabPrwbZy45sbavfcjinPJC18kjpRTv8',
                recipient='TJRabPrwbZy45sbavfcjinPJC18kjpRTv8',
                amount=Decimal('10.0')
            )
            
            self.assertIsNone(error)
            self.assertIn('transaction_id', result)
            self.assertIn('fee', result)
            self.assertIn('expires_at', result)
            
    def test_polygon_service(self):
        """Test Polygon service"""
        service = self.router.get_service('polygon')
        
        # Test address validation
        self.assertTrue(service.validate_address('0x742d35Cc6634C0532925a3b844Bc454e4438f44e'))
        self.assertFalse(service.validate_address('invalid_address'))
        
        # Test transaction preparation
        with patch.object(service, 'get_balance') as mock_balance, \
             patch.object(service, 'estimate_fee') as mock_fee:
            
            mock_balance.return_value = (Decimal('1.0'), None)
            mock_fee.return_value = (Decimal('0.001'), None)
            
            result, error = service.prepare_transaction(
                sender='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                recipient='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                amount=Decimal('0.1')
            )
            
            self.assertIsNone(error)
            self.assertIn('transaction_id', result)
            self.assertIn('fee', result)
            self.assertIn('expires_at', result)
            
    def test_transaction_storage(self):
        """Test transaction storage functionality"""
        service = self.router.get_service('ethereum')
        
        # Test storing transaction
        tx_data = {
            'sender': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'recipient': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
            'amount': '0.1',
            'fee': '0.001',
            'timestamp': datetime.now().isoformat(),
            'status': 'prepared'
        }
        
        # Store transaction
        expires_at = service._store_transaction('test_tx_id', tx_data)
        self.assertIsInstance(expires_at, datetime)
        
        # Get stored transaction
        stored_tx = service._get_stored_transaction('test_tx_id')
        self.assertIsNotNone(stored_tx)
        self.assertEqual(stored_tx['sender'], tx_data['sender'])
        self.assertEqual(stored_tx['recipient'], tx_data['recipient'])
        self.assertEqual(stored_tx['amount'], tx_data['amount'])
        
        # Test transaction expiration
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now() + timedelta(minutes=16)
            expired_tx = service._get_stored_transaction('test_tx_id')
            self.assertIsNone(expired_tx)
            
if __name__ == '__main__':
    unittest.main() 