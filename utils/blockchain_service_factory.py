from typing import Dict, Type, List, Optional, Any
import importlib
import os
import json
import logging
from utils.logging_config import get_logger

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.blockchains.ethereum_service import EthereumService
from services.blockchains.bsc_service import BSCService
from services.blockchains.tron_service import TronService
from services.blockchains.bitcoin_service import BitcoinService
from services.blockchains.polygon_service import PolygonService
from services.blockchains.xrp_service import XRPService
from services.blockchains.solana_service import SolanaService
from services.blockchains.polkadot_service import PolkadotService
from services.blockchains.litecoin_service import LitecoinService
from services.blockchains.dogecoin_service import DogecoinService
from services.blockchains.dash_service import DashService
from services.blockchains.arbitrum_service import ArbitrumService
from services.blockchains.avalanche_service import AvalancheService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BlockchainServiceFactory:
    """Factory for creating and managing blockchain services"""
    
    # Dictionary to store registered service classes
    _service_classes: Dict[str, Type[BaseBlockchainService]] = {}
    
    # Dictionary to store instantiated services
    _services: Dict[str, BaseBlockchainService] = {}
    
    # Mapping of blockchain name variants to canonical names
    _name_mapping: Dict[str, str] = {}
    
    # Set of disabled blockchains that failed to initialize
    _disabled_blockchains: set = set()
    
    @classmethod
    def register_service(cls, blockchain_name: str, service_class: Type[BaseBlockchainService], name_variants: List[str] = None) -> None:
        """
        Register a blockchain service class.
        
        Args:
            blockchain_name: Canonical name of the blockchain (e.g., 'ethereum')
            service_class: Service class implementing BaseBlockchainService
            name_variants: List of alternative names for this blockchain (e.g., ['eth'])
        """
        if not issubclass(service_class, BaseBlockchainService):
            raise TypeError(f"{service_class.__name__} must be a subclass of BaseBlockchainService")
            
        # Register the canonical name
        cls._service_classes[blockchain_name] = service_class
        cls._name_mapping[blockchain_name] = blockchain_name
        
        logger.info(f"Registered blockchain service: {blockchain_name} -> {service_class.__name__}")
        
        # Register name variants
        if name_variants:
            for variant in name_variants:
                cls._name_mapping[variant.lower()] = blockchain_name
                logger.debug(f"Added name variant: {variant} -> {blockchain_name}")
                
    @classmethod
    def get_service(cls, blockchain_name: str) -> Any:
        """Get a blockchain service instance"""
        normalized_name = cls.normalize_name(blockchain_name)
        if not normalized_name:
            logger.error(f"Unsupported blockchain: {blockchain_name}")
            return None
            
        # Return from cache if available
        if normalized_name in cls._services:
            return cls._services[normalized_name]
            
        # Try to import and instantiate the service
        try:
            class_name = normalized_name.capitalize() + "Service"
            module_name = normalized_name.lower()
            
            # Special handling for certain blockchains
            if module_name == "binance-smart-chain":
                module_name = "bsc"
                class_name = "BSCService"
            elif module_name == "ripple":
                module_name = "xrp"
                class_name = "XRPService"
                
            # Import the module
            module = importlib.import_module(f"services.blockchains.{module_name}_service")
            
            # Get the service class
            service_class = getattr(module, class_name)
            
            # Instantiate the service
            service = service_class()
            
            # Cache the service
            cls._services[normalized_name] = service
            
            return service
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to import blockchain service for {blockchain_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error initializing blockchain service for {blockchain_name}: {e}")
            return None
    
    @staticmethod
    def normalize_name(blockchain_name: str) -> Optional[str]:
        """Normalize blockchain name to a standard format"""
        if not blockchain_name:
            return None
            
        # Convert to lowercase and strip spaces
        name = blockchain_name.lower().strip()
        
        # Mapping of blockchain names to standard format
        name_mapping = {
            # Ethereum
            "eth": "ethereum",
            "ether": "ethereum",
            "erc20": "ethereum",
            
            # Binance Smart Chain
            "bnb": "binance-smart-chain",
            "binance": "binance-smart-chain",
            "bsc": "binance-smart-chain",
            "bnb smart chain": "binance-smart-chain",
            "binancecoin": "binance-smart-chain",
            "binance chain": "binance-smart-chain",
            "binance smart chain": "binance-smart-chain",
            
            # Bitcoin
            "btc": "bitcoin",
            
            # Polygon
            "matic": "polygon",
            "polygon matic": "polygon",
            
            # Avalanche
            "avax": "avalanche",
            
            # Solana
            "sol": "solana",
            
            # Tron
            "trx": "tron",
            
            # XRP - use ripple as the canonical name, but support both
            "xrp": "ripple",
            "ripple": "ripple",
            
            # Cardano
            "ada": "cardano",
            
            # Polkadot
            "dot": "polkadot",
            
            # Litecoin
            "ltc": "litecoin",
            
            # Dogecoin
            "doge": "dogecoin",
            
            # Arbitrum
            "arb": "arbitrum",
            
            # Optimism
            "op": "optimism",
            
            # Crypto.com
            "cro": "crypto-com",
            "crypto.com": "crypto-com",
            "cronos": "crypto-com"
        }
        
        # Return normalized name
        return name_mapping.get(name, name)
        
    @classmethod
    def get_supported_blockchains(cls) -> List[str]:
        """
        Get list of all supported blockchains.
        
        Returns:
            List of canonical blockchain names, excluding disabled ones
        """
        return [name for name in cls._service_classes.keys() if name not in cls._disabled_blockchains]
        
    @classmethod
    def get_all_services(cls) -> Dict[str, BaseBlockchainService]:
        """
        Get all instantiated blockchain services.
        
        Returns:
            Dictionary mapping canonical names to service instances
        """
        # Create any services that haven't been instantiated yet
        for blockchain_name in cls.get_supported_blockchains():
            if blockchain_name not in cls._services and blockchain_name not in cls._disabled_blockchains:
                try:
                    cls.get_service(blockchain_name)
                except Exception as e:
                    logger.warning(f"Skipping {blockchain_name} service due to initialization error: {str(e)}")
                
        return cls._services
        
    @classmethod
    def load_config(cls, config_path: str = None) -> None:
        """
        Load blockchain configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
        """
        if not config_path:
            # Default to a config in the same directory
            config_path = os.path.join(os.path.dirname(__file__), "blockchain_config.json")
            
        if not os.path.exists(config_path):
            logger.warning(f"Blockchain config file not found: {config_path}")
            return
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            for blockchain_config in config.get("blockchains", []):
                blockchain_name = blockchain_config.get("name")
                service_class_path = blockchain_config.get("service_class")
                name_variants = blockchain_config.get("name_variants", [])
                enabled = blockchain_config.get("enabled", True)
                
                if not blockchain_name or not service_class_path:
                    logger.warning(f"Invalid blockchain config: {blockchain_config}")
                    continue
                    
                if not enabled:
                    logger.info(f"Skipping disabled blockchain: {blockchain_name}")
                    continue
                    
                try:
                    # Import the service class
                    module_path, class_name = service_class_path.rsplit(".", 1)
                    module = importlib.import_module(module_path)
                    service_class = getattr(module, class_name)
                    
                    # Register the service
                    cls.register_service(blockchain_name, service_class, name_variants)
                    
                except (ImportError, AttributeError) as e:
                    logger.error(f"Error loading blockchain service {blockchain_name}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error loading blockchain config: {str(e)}")

    @classmethod
    def initialize_all_services(cls) -> Dict[str, str]:
        """
        Try to initialize all blockchain services and report their status.
        
        Returns:
            Dictionary mapping blockchain names to their status ('ok' or error message)
        """
        results = {}
        
        for blockchain_name in cls._service_classes.keys():
            try:
                if blockchain_name not in cls._services:
                    cls.get_service(blockchain_name)
                results[blockchain_name] = "ok"
            except Exception as e:
                results[blockchain_name] = str(e)
                
        return results


# Register all built-in blockchain services
try:
    BlockchainServiceFactory.register_service("ethereum", EthereumService, ["eth"])
except Exception as e:
    logger.error(f"Failed to register ethereum service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("bsc", BSCService, ["binance", "binance-smart-chain", "bnb"])
except Exception as e:
    logger.error(f"Failed to register bsc service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("tron", TronService, ["trx"])
except Exception as e:
    logger.error(f"Failed to register tron service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("bitcoin", BitcoinService, ["btc"])
except Exception as e:
    logger.error(f"Failed to register bitcoin service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("polygon", PolygonService, ["matic"])
except Exception as e:
    logger.error(f"Failed to register polygon service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("ripple", XRPService, ["xrp"])
except Exception as e:
    logger.error(f"Failed to register ripple service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("solana", SolanaService, ["sol"])
except Exception as e:
    logger.error(f"Failed to register solana service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("polkadot", PolkadotService, ["dot"])
except Exception as e:
    logger.error(f"Failed to register polkadot service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("litecoin", LitecoinService, ["ltc"])
except Exception as e:
    logger.error(f"Failed to register litecoin service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("dogecoin", DogecoinService, ["doge"])
except Exception as e:
    logger.error(f"Failed to register dogecoin service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("dash", DashService, [])
except Exception as e:
    logger.error(f"Failed to register dash service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("arbitrum", ArbitrumService, ["arb"])
except Exception as e:
    logger.error(f"Failed to register arbitrum service: {str(e)}")

try:
    BlockchainServiceFactory.register_service("avalanche", AvalancheService, ["avax"])
except Exception as e:
    logger.error(f"Failed to register avalanche service: {str(e)}")

# Try to load additional config if available
try:
    BlockchainServiceFactory.load_config()
except Exception as e:
    logger.error(f"Failed to load blockchain config: {str(e)}") 