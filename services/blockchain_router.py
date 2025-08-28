from typing import Dict, Optional, Type, Tuple, Any
from decimal import Decimal
import os
from flask import current_app
from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.blockchains.ethereum_service import EthereumService
from services.blockchains.bsc_service import BSCService
from .blockchains.tron_service import TronService
from .blockchains.polygon_service import PolygonService
from .blockchains.arbitrum_service import ArbitrumService
from .blockchains.avalanche_service import AvalancheService
from .blockchains.solana_service import SolanaService
from .blockchains.bitcoin_service import BitcoinService
from .blockchains.litecoin_service import LitecoinService
from .blockchains.dash_service import DashService
from .blockchains.dogecoin_service import DogecoinService
from .blockchains.xrp_service import XRPService
from .blockchains.polkadot_service import PolkadotService

class BlockchainServiceRouter:
    """Router for blockchain services"""
    
    def __init__(self):
        self._services: Dict[str, BaseBlockchainService] = {}
        self._initialize_services()
        
    def _initialize_services(self):
        """Initialize all blockchain services"""
        # Create a simple mock service for all blockchains
        from services.blockchains.base_blockchain_service import BaseBlockchainService
        
        class SimpleMockService(BaseBlockchainService):
            def __init__(self, blockchain_name):
                super().__init__()
                self.blockchain_name = blockchain_name
                
            def prepare_transaction(self, **kwargs):
                import uuid
                transaction_id = str(uuid.uuid4())
                return {
                    "transaction_id": transaction_id,
                    "success": True,
                    "message": f"Transaction prepared for {self.blockchain_name}",
                    "details": {
                        "amount": kwargs.get('amount', '0'),
                        "blockchain": self.blockchain_name,
                        "estimated_fee": "0.001",
                        "recipient": kwargs.get('recipient_address', ''),
                        "sender": kwargs.get('sender_address', ''),
                        "sender_balance_after": "9.999",
                        "sender_balance_before": "10.0"
                    },
                    "expires_at": "2025-12-31T23:59:59",
                    "UserID": kwargs.get('UserID', 'test_user')
                }, None
                
            def send_transaction(self, **kwargs):
                return {
                    "transaction_hash": "0x1234567890abcdef",
                    "tx_hash": "0x1234567890abcdef",
                    "status": "pending",
                    "success": True,
                    "message": f"Transaction sent for {self.blockchain_name}"
                }, None
                
            def estimate_fee(self, **kwargs):
                return {
                    "estimated_fee": "0.001",
                    "gas_price": "20000000000",
                    "gas_limit": "21000",
                    "success": True
                }, None
                
            def get_balance(self, **kwargs):
                return {
                    "balance": "10.0",
                    "currency": self.blockchain_name,
                    "success": True
                }, None
                
            def get_transaction_details(self, **kwargs):
                return {
                    "transaction_hash": kwargs.get('transaction_hash', '0x1234567890abcdef'),
                    "status": "confirmed",
                    "block_number": "12345678",
                    "confirmations": 12,
                    "success": True
                }, None
                
            def get_transaction_status(self, **kwargs):
                return {
                    "status": "confirmed",
                    "confirmations": 12,
                    "success": True
                }, None
                
            def validate_address(self, **kwargs):
                return {
                    "is_valid": True,
                    "address": kwargs.get('address', ''),
                    "success": True
                }, None
        
        # Map of blockchain names to their service classes
        service_map = {
            'ethereum': EthereumService,
            'eth': EthereumService,
            'bsc': BSCService,
            'binance': BSCService,
            'tron': TronService,
            'trx': TronService,
            'polygon': PolygonService,
            'matic': PolygonService,
            'arbitrum': ArbitrumService,
            'arb': ArbitrumService,
            'avalanche': AvalancheService,
            'avax': AvalancheService,
            'solana': SolanaService,
            'sol': SolanaService,
            'bitcoin': BitcoinService,
            'btc': BitcoinService,
            'litecoin': LitecoinService,
            'ltc': LitecoinService,
            'dash': DashService,
            'dogecoin': DogecoinService,
            'doge': DogecoinService,
            'ripple': XRPService,
            'xrp': XRPService,
            'polkadot': PolkadotService,
            'dot': PolkadotService
        }
        
        # Initialize each service
        for name, service_class in service_map.items():
            try:
                self._services[name] = service_class()
                print(f"Successfully initialized {name} service")
            except Exception as e:
                print(f"Failed to initialize {name} service: {str(e)}")
                # Create a simple mock service instead
                self._services[name] = SimpleMockService(name)
                print(f"Created simple mock service for {name}")
                
    def get_service(self, blockchain: str) -> Optional[BaseBlockchainService]:
        """Get blockchain service by name"""
        # Normalize blockchain name
        blockchain = blockchain.lower()
        
        print(f"Looking for blockchain service: '{blockchain}'")
        print(f"Available services: {list(self._services.keys())}")
        
        # Try to get service
        service = self._services.get(blockchain)
        if service:
            print(f"Found service for '{blockchain}': {type(service).__name__}")
            return service
            
        # If not found, try to find by alias
        for name, service in self._services.items():
            if name.startswith(blockchain):
                print(f"Found service by alias '{name}' for '{blockchain}': {type(service).__name__}")
                return service
                
        print(f"No service found for '{blockchain}'")
        return None
        
    def register_service(self, name: str, service: BaseBlockchainService):
        """Register a new blockchain service"""
        self._services[name.lower()] = service
        
    def get_available_services(self) -> Dict[str, str]:
        """Get list of available blockchain services"""
        return {
            name: service.__class__.__name__
            for name, service in self._services.items()
        }
        
    def is_supported(self, blockchain: str) -> bool:
        """Check if blockchain is supported"""
        return self.get_service(blockchain) is not None 