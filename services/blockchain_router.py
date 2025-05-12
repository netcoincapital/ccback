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
from .blockchains.ripple_service import RippleService
from .blockchains.polkadot_service import PolkadotService

class BlockchainServiceRouter:
    """Router for blockchain services"""
    
    def __init__(self):
        self._services: Dict[str, BaseBlockchainService] = {}
        self._initialize_services()
        
    def _initialize_services(self):
        """Initialize all blockchain services"""
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
            'ripple': RippleService,
            'xrp': RippleService,
            'polkadot': PolkadotService,
            'dot': PolkadotService
        }
        
        # Initialize each service
        for name, service_class in service_map.items():
            try:
                self._services[name] = service_class()
            except Exception as e:
                print(f"Failed to initialize {name} service: {str(e)}")
                
    def get_service(self, blockchain: str) -> Optional[BaseBlockchainService]:
        """Get blockchain service by name"""
        # Normalize blockchain name
        blockchain = blockchain.lower()
        
        # Try to get service
        service = self._services.get(blockchain)
        if service:
            return service
            
        # If not found, try to find by alias
        for name, service in self._services.items():
            if name.startswith(blockchain):
                return service
                
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