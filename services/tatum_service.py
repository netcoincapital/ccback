import requests
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import uuid
import aiohttp
import os
import sys
from decimal import Decimal
from utils.logging_config import get_logger
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.Address import Address
from database.UserHolding import UserHolding
from database.base import SessionLocal
from database.Blockchains import Blockchains
from database.wallets import Wallets
from database.Currencies import Currencies
import time
from web3 import Web3

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TransactionManager:
    """Manages pending transactions in memory"""
    def __init__(self):
        self._pending_transactions = {}
        self.logger = get_logger(__file__)

    def store_transaction(self, transaction_id: str, transaction_data: Dict) -> None:
        """Store a pending transaction"""
        self._pending_transactions[transaction_id] = {
            'data': transaction_data,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=30)  # 30 minutes expiry
        }
        self.logger.info(f"Stored pending transaction: {transaction_id}")
        self.logger.debug(f"Current pending transactions: {list(self._pending_transactions.keys())}")

    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get a pending transaction"""
        if transaction_id not in self._pending_transactions:
            self.logger.warning(f"Transaction not found: {transaction_id}")
            self.logger.debug(f"Available transactions: {list(self._pending_transactions.keys())}")
            return None
        
        transaction = self._pending_transactions[transaction_id]
        if datetime.now() > transaction['expires_at']:
            self.logger.warning(f"Transaction {transaction_id} has expired")
            del self._pending_transactions[transaction_id]
            return None
        
        self.logger.debug(f"Retrieved transaction: {transaction_id}")
        return transaction['data']

    def remove_transaction(self, transaction_id: str) -> None:
        """Remove a pending transaction"""
        if transaction_id in self._pending_transactions:
            del self._pending_transactions[transaction_id]
            self.logger.info(f"Removed pending transaction: {transaction_id}")
        else:
            self.logger.warning(f"Attempted to remove non-existent transaction: {transaction_id}")
            
    @property
    def pending_transactions(self) -> Dict:
        """Get all pending transactions (for debugging only)"""
        return self._pending_transactions

# Initialize transaction manager
transaction_manager = TransactionManager()

class TatumService:
    """Service class for interacting with Tatum API"""
    
    def __init__(self):
        self.logger = get_logger(__file__)
        
        self.api_key = os.getenv('TATUM_API_KEY')
        if not self.api_key:
            raise RuntimeError("TATUM_API_KEY environment variable is not set")
            
        self.infura_project_id = os.getenv('INFURA_PROJECT_ID') or os.getenv('INFURA_API_KEY')
        if not self.infura_project_id:
            raise RuntimeError("INFURA_PROJECT_ID environment variable is not set")

        self.base_url = "https://api.tatum.io/v3"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Infura endpoints for EVM chains
        self.infura_urls = {
            "ethereum": f"https://mainnet.infura.io/v3/{self.infura_project_id}",
            "eth": f"https://mainnet.infura.io/v3/{self.infura_project_id}",
            "binance smart chain": "https://bsc-dataseed.binance.org",
            "polygon": "https://polygon-rpc.com",
            "matic": "https://polygon-rpc.com",
            "avalanche": "https://api.avax.network/ext/bc/C/rpc",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
            "optimism": "https://mainnet.optimism.io"
        }

        # Default gas prices in Gwei
        self.default_gas_prices = {
            "ethereum": 20,
            "eth": 20,
            "binance smart chain": 5,
            "polygon": 30,
            "matic": 30,
            "avalanche": 25,
            "arbitrum": 0.1,
            "optimism": 0.001
        }
        
        # Mapping blockchain names to Tatum chain identifiers and currencies
        self.chain_mapping = {
            "ethereum": {"chain": "ethereum", "currency": "ETH"},
            "binance smart chain": {"chain": "binance smart chain", "currency": "BNB"},
            "polygon": {"chain": "polygon", "currency": "MATIC"},
            "avalanche": {"chain": "avalanche", "currency": "AVAX"},
            "arbitrum": {"chain": "arbitrum", "currency": "ETH"},
            "optimism": {"chain": "optimism", "currency": "ETH"},
            "bitcoin": {"chain": "btc", "currency": "BTC"},
            "btc": {"chain": "btc", "currency": "BTC"},
            "tron": {"chain": "tron", "currency": "TRX"},
            "trx": {"chain": "tron", "currency": "TRX"},
            "solana": {"chain": "solana", "currency": "SOL"},
            "xrp": {"chain": "xrp", "currency": "XRP"},
            "stellar": {"chain": "stellar", "currency": "XLM"},
            "polkadot": {"chain": "dot", "currency": "DOT"}
        }

        # Token contract address to currency mapping for Binance Smart Chain
        self.bnb_token_mapping = {
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB"
        }

        # Token contract address to currency mapping for Ethereum
        self.eth_token_mapping = {
            "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
            "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
            "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC"
        }

        self.SUPPORTED_BLOCKCHAINS = list(self.chain_mapping.keys())
    
    def _is_evm_chain(self, chain: str) -> bool:
        """Check if the chain is an EVM chain"""
        return chain.lower() in ["ethereum", "eth", "binance smart chain", "polygon", "matic", "avalanche", "arbitrum", "optimism"]

    def _get_infura_gas_price(self, chain: str) -> Tuple[float, str]:
        """Get gas price from Infura for EVM chains"""
        try:
            infura_url = self.infura_urls.get(chain.lower())
            if not infura_url:
                return self.default_gas_prices.get(chain, 20), "default"

            payload = {
                "jsonrpc": "2.0",
                "method": "eth_gasPrice",
                "params": [],
                "id": 1
            }
            
            response = requests.post(infura_url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    # Convert from hex to decimal and then to Gwei
                    gas_price_wei = int(data["result"], 16)
                    gas_price_gwei = gas_price_wei / 1e9
                    self.logger.info(f"Successfully got gas price from Infura: {gas_price_gwei} Gwei")
                    return gas_price_gwei, "infura"
        except Exception as e:
            self.logger.warning(f"Failed to get gas price from Infura: {str(e)}")
        
        # Return default if Infura fails
        default_price = self.default_gas_prices.get(chain, 20)
        self.logger.info(f"Using default gas price: {default_price} Gwei")
        return default_price, "default"

    def _get_infura_gas_limit(self, chain: str, from_address: str, to_address: str, 
                             amount: str, contract_address: Optional[str] = None) -> Tuple[int, str]:
        """Get gas limit from Infura for EVM chains"""
        try:
            infura_url = self.infura_urls.get(chain.lower())
            if not infura_url:
                return 21000, "default"

            # For token transfers, use higher default
            if contract_address:
                return 65000, "default"

            # For native transfers, estimate gas limit
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_estimateGas",
                "params": [{
                    "from": from_address,
                    "to": to_address,
                    "value": hex(int(float(amount) * 1e18))  # Convert to Wei
                }],
                "id": 1
            }
            
            response = requests.post(infura_url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    gas_limit = int(data["result"], 16)
                    self.logger.info(f"Successfully got gas limit from Infura: {gas_limit}")
                    return gas_limit, "infura"
        except Exception as e:
            self.logger.warning(f"Failed to get gas limit from Infura: {str(e)}")
        
        # Return default if Infura fails
        default_limit = 65000 if contract_address else 21000
        self.logger.info(f"Using default gas limit: {default_limit}")
        return default_limit, "default"

    def get_gas_price_with_fallback(self, chain: str) -> Tuple[float, str]:
        """
        Get gas price with multiple fallback options.
        Returns tuple of (gas_price_in_gwei, source_name)
        """
        chain = chain.lower()
        self.logger.debug(f"Getting gas price for chain: {chain}")
        
        # For EVM chains, use Infura
        if self._is_evm_chain(chain):
            return self._get_infura_gas_price(chain)
        
        # For non-EVM chains, use Tatum API
        try:
            if chain == "eth":
                endpoint = "/ethereum/gas"
            elif chain == "binance smart chain":
                endpoint = "/binance smart chain/gas"
            else:
                endpoint = f"/{chain}/gas"
                
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                gas_price = float(data.get("gasPrice", 0))
                self.logger.info(f"Successfully got gas price from Tatum: {gas_price} Gwei")
                return gas_price, "tatum"
        except Exception as e:
            self.logger.warning(f"Failed to get gas price from Tatum: {str(e)}")
        
        # Use default values as last resort
        default_price = self.default_gas_prices.get(chain, 20)
        self.logger.info(f"Using default gas price: {default_price} Gwei")
        return default_price, "default"

    def estimate_gas_limit(self, chain: str, from_address: str, to_address: str, 
                         amount: str, contract_address: Optional[str] = None) -> Tuple[int, str]:
        """
        Estimate gas limit for a transaction.
        Returns tuple of (gas_limit, source_name)
        """
        chain = chain.lower()
        self.logger.debug(f"Estimating gas limit for chain: {chain}")
        
        # For EVM chains, use Infura
        if self._is_evm_chain(chain):
            return self._get_infura_gas_limit(chain, from_address, to_address, amount, contract_address)
        
        # For non-EVM chains, use Tatum API
        try:
            if chain == "eth":
                endpoint = "/ethereum/gas"
            elif chain == "binance smart chain":
                endpoint = "/binance smart chain/gas"
            else:
                endpoint = f"/{chain}/gas"
                
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                gas_limit = int(data.get("gasLimit", 0))
                if gas_limit > 0:
                    self.logger.info(f"Successfully got gas limit from Tatum: {gas_limit}")
                    return gas_limit, "tatum"
        except Exception as e:
            self.logger.warning(f"Failed to get gas limit from Tatum: {str(e)}")
        
        # Use default values as fallback
        default_limit = 65000 if contract_address else 21000
        self.logger.info(f"Using default gas limit: {default_limit}")
        return default_limit, "default"

    def _get_chain_currency(self, blockchain_name):
        """
        دریافت نماد ارز و نام بلاکچین از نام بلاکچین
        
        Args:
            blockchain_name (str): نام بلاکچین
            
        Returns:
            tuple: (نام بلاکچین, نماد ارز)
        """
        # نرمال‌سازی نام بلاکچین
        blockchain_name = blockchain_name.lower().strip()
        
        # نگاشت نام‌های بلاکچین به نماد ارز
        chain_mapping = {
            'ethereum': 'ETH',
            'binance smart chain': 'BNB',
            'polygon': 'MATIC',
            'tron': 'TRX',
            'bitcoin': 'BTC',
            'litecoin': 'LTC',
            'dogecoin': 'DOGE',
            'ripple': 'XRP',
            'solana': 'SOL',
            'cardano': 'ADA',
            'polkadot': 'DOT',
            'avalanche': 'AVAX',
            'fantom': 'FTM',
            'arbitrum': 'ARB',
            'optimism': 'OP'
        }
        
        # بررسی وجود نام بلاکچین در نگاشت
        if blockchain_name in chain_mapping:
            return blockchain_name, chain_mapping[blockchain_name]
        
        # اگر نام بلاکچین در نگاشت نبود، از خود نام استفاده می‌کنیم
            return blockchain_name, blockchain_name.upper()

    def _get_token_currency(self, blockchain_name: str, contract_address: str) -> str:
        """
        دریافت نماد ارز توکن از آدرس قرارداد هوشمند
        
        Args:
            blockchain_name (str): نام بلاکچین
            contract_address (str): آدرس قرارداد هوشمند
            
        Returns:
            str: نماد ارز توکن
        """
        # نرمال‌سازی نام بلاکچین
        blockchain_name = blockchain_name.lower().strip()
        
        # نگاشت آدرس‌های قرارداد هوشمند به نماد ارز
        token_mapping = {
            'ethereum': {
                '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2': 'WETH',  # Wrapped ETH
                '0xdAC17F958D2ee523a2206206994597C13D831ec7': 'USDT',  # Tether
                '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48': 'USDC'   # USD Coin
            },
            'binance smart chain': {
                '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c': 'WBNB',  # Wrapped BNB
                '0x55d398326f99059fF775485246999027B3197955': 'USDT',  # Tether
                '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d': 'USDC'   # USD Coin
            }
        }
        
        # بررسی وجود بلاکچین در نگاشت
        if blockchain_name in token_mapping:
            # بررسی وجود آدرس قرارداد در نگاشت
            if contract_address.lower() in [addr.lower() for addr in token_mapping[blockchain_name].keys()]:
                return token_mapping[blockchain_name][contract_address]
        
        # اگر آدرس قرارداد در نگاشت نبود، از نام بلاکچین استفاده می‌کنیم
        return blockchain_name.upper()

    def _clean_decimals(self, obj):
        """
        Recursively convert all Decimal instances to float in a dictionary or list
        
        Args:
            obj: Object to clean (dict, list, or any other type)
            
        Returns:
            Object with all Decimals converted to float
        """
        if isinstance(obj, dict):
            return {k: self._clean_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_decimals(i) for i in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj

    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[Dict, Optional[str]]:
        """
        Make an async HTTP request to Tatum API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body for POST requests
            
        Returns:
            Tuple of (response_data, error_message)
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint}"
        try:
            # Clean any Decimal values in the request data
            if data:
                data = self._clean_decimals(data)
                
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, json=data) as response:
                    content_type = response.headers.get('Content-Type', '')
                    if response.status != 200:
                        text = await response.text()
                        error_msg = f"Tatum API error: {response.status} - {text}"
                        self.logger.error(error_msg)
                        return {}, error_msg
                    if 'application/json' not in content_type:
                        text = await response.text()
                        error_msg = f"Unexpected MIME type: {content_type}, response: {text}"
                        self.logger.error(error_msg)
                        return {}, error_msg
                    return await response.json(), None
        except Exception as e:
            error_msg = f"Error making request to Tatum API: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg

    def _make_request_sync(self, method: str, endpoint: str, params=None, data=None) -> Tuple[Optional[Dict], Optional[str]]:
        """Make request to Tatum API (synchronous version)"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            self.logger.debug(f"Making {method} request to {url}")
            
            # Clean any Decimal values in the request data
            if data:
                data = self._clean_decimals(data)
            
            self.logger.debug(f"Request data: {data}")
            
            if method.lower() == 'get':
                response = requests.get(url, headers=self.headers, params=params)
            elif method.lower() == 'post':
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return None, f"Unsupported HTTP method: {method}"
            
            self.logger.debug(f"Response status code: {response.status_code}")
            self.logger.debug(f"Response body: {response.text}")
            
            # Special handling for TRON responses
            if "tron" in endpoint.lower():
                # If 404 error with "Cannot POST /v3/tron/gas" message, it's a known issue
                if response.status_code == 404 and "Cannot POST /v3/tron/gas" in response.text:
                    self.logger.warning("Tatum API missing TRON gas endpoint, using default values")
                    # Return empty object for gas estimation
                    if "/tron/gas" in endpoint:
                        return {"gasPrice": "0", "gasLimit": "0"}, None
                
                # For other TRON endpoints, if we get an error but the operation might have succeeded
                if response.status_code != 200:
                    error_msg = f"Tatum API error with TRON: {response.status_code}, {response.text}"
                    self.logger.error(error_msg)
                    return None, error_msg
            
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"Tatum API error: {response.status_code}, {response.text}"
                self.logger.error(error_msg)
                return None, error_msg
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to Tatum API: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout connecting to Tatum API: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error calling Tatum API: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg

    def get_balance(self, blockchain_name: str, address: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get balance for an address"""
        try:
            chain, _ = self._get_chain_currency(blockchain_name)
            
            # Use correct blockchain names in endpoint URLs
            if chain == "eth":
                endpoint = f"/ethereum/account/balance/{address}"
            elif chain == "binance smart chain":
                endpoint = f"/binance smart chain/account/balance/{address}"
            else:
                endpoint = f"/{chain}/account/balance/{address}"
            
            self.logger.debug(f"Getting balance from endpoint: {endpoint}")
            return self._make_request_sync('get', endpoint)

        except ValueError as e:
            return None, str(e)
        except Exception as e:
            error_msg = f"Error getting balance: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg

    
    def validate_address(self, blockchain_name: str, address: str) -> bool:
        """Validate if an address is valid for a specific blockchain"""
        try:
            chain, _ = self._get_chain_currency(blockchain_name)
            
            # Basic validation based on blockchain rules
            if chain == 'btc' and (address.startswith('1') or address.startswith('3') or address.startswith('bc1')):
                return len(address) >= 26 and len(address) <= 35
            
            elif chain in ['eth', 'binance smart chain', 'polygon', 'avalanche', 'arbitrum']:
                return address.startswith('0x') and len(address) == 42
                
            elif chain == 'tron':
                return address.startswith('T') and len(address) == 34
                
            elif chain == 'solana':
                return len(address) >= 32 and len(address) <= 44
                
            elif chain == 'xrp':
                return address.startswith('r') and len(address) >= 25 and len(address) <= 35
                
            # For others, we'll just perform a basic length check
            return len(address) >= 10 and len(address) <= 100
            
        except ValueError:
            return False
    
    def get_transaction(self, blockchain_name: str, tx_hash: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get transaction details by hash"""
        chain, _ = self._get_chain_currency(blockchain_name)
        
        # Use correct blockchain names in endpoint URLs
        if chain == "eth":
            endpoint = f"/ethereum/transaction/{tx_hash}"
        elif chain == "binance smart chain":
            endpoint = f"/binance smart chain/transaction/{tx_hash}"
        else:
            endpoint = f"/{chain}/transaction/{tx_hash}"
        
        return self._make_request_sync('get', endpoint)
    
    def calculate_transaction_fee(self, chain: str, from_address: str, to_address: str,
                                amount: str, contract_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate transaction fee with accurate gas estimation.
        Returns dict with fee details.
        """
        chain = chain.lower()
        self.logger.debug(f"Calculating transaction fee for chain: {chain}")
        
        # Get gas price with a more conservative approach
        gas_price, price_source = self.get_gas_price_with_fallback(chain)
        
        # For Ethereum mainnet, use a more conservative gas price
        if chain in ["ethereum", "eth"]:
            gas_price = min(gas_price, 30)  # Cap at 30 Gwei for safety
        
        # Get gas limit
        gas_limit, limit_source = self.estimate_gas_limit(
            chain, from_address, to_address, amount, contract_address
        )
        
        # Calculate fee in Gwei
        fee_gwei = gas_price * gas_limit
        
        # Convert to native currency (e.g., ETH)
        fee_native = fee_gwei / 1e9
        
        # Add a small buffer to prevent insufficient funds errors
        # Buffer is chain-specific:
        # - For ETH: 0.000001 ETH
        # - For BNB: 0.0000001 BNB
        # - For Polygon: 0.000001 MATIC
        buffer_amounts = {
            "ethereum": 0.000001,
            "eth": 0.000001,
            "binance smart chain": 0.0000001,
            "polygon": 0.000001,
            "matic": 0.000001,
            "avalanche": 0.000001,
            "arbitrum": 0.000001,
            "optimism": 0.000001
        }
        
        # Add buffer and round to 9 decimal places
        buffer = buffer_amounts.get(chain, 0.000001)
        fee_native = round(fee_native + buffer, 9)
        
        # Get USD price if available
        try:
            if chain in ["ethereum", "eth"]:
                currency = "ETH"
            elif chain in ["binance smart chain"]:
                currency = "BNB"
            elif chain in ["polygon", "matic"]:
                currency = "MATIC"
            else:
                currency = chain.upper()
                
            # Get price from Tatum
            price_endpoint = f"/tatum/rate/{currency}/USD"
            response = requests.get(
                f"{self.base_url}{price_endpoint}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                usd_price = float(data.get("value", 0))
                fee_usd = fee_native * usd_price
            else:
                fee_usd = 0
        except Exception as e:
            self.logger.warning(f"Failed to get USD price: {str(e)}")
            fee_usd = 0
        
        return {
            "gas_price": gas_price,
            "gas_limit": gas_limit,
            "fee_gwei": fee_gwei,
            "fee_native": fee_native,
            "fee_usd": fee_usd,
            "price_source": price_source,
            "limit_source": limit_source,
            "buffer_added": buffer
        }
    
    def prepare_transaction_sync(self, blockchain_name: str, sender_address: str, recipient_address: str, 
                                amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Dict, Optional[str]]:
        """Synchronous version of prepare_transaction for direct usage with Flask"""
        # Generate a unique transaction ID upfront
        transaction_id = str(uuid.uuid4())
        self.logger.debug(f"Generated transaction ID: {transaction_id} for {blockchain_name} transaction")
        
        try:
            # Get chain and currency info
            chain, base_currency = self._get_chain_currency(blockchain_name)
            
            # For token transfers, get the token currency
            currency = base_currency
            if smart_contract_address:
                token_currency = self._get_token_currency(blockchain_name, smart_contract_address)
                if token_currency:
                    currency = token_currency
                    
            # Get balance
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            if error:
                return {"transaction_id": transaction_id, "success": False, "message": f"Error getting sender balance: {error}"}, f"Error getting sender balance: {error}"
            
            sender_balance_before = balance_data.get('balance', '0')
            
            # Calculate transaction fee with more conservative gas price
            fee_details = self.calculate_transaction_fee(
                chain=chain,
                from_address=sender_address,
                to_address=recipient_address,
                amount=amount,
                contract_address=smart_contract_address
            )
            
            # Convert gas price from Gwei to Wei and ensure it's a string integer
            gas_price_gwei = fee_details["gas_price"]
            gas_price_wei = str(int(round(gas_price_gwei * 1e9)))
            
            estimated_fee = str(fee_details["fee_native"])
            gas_limit = str(fee_details["gas_limit"])
            
            # Calculate balance after
            try:
                balance_after = float(sender_balance_before) - float(amount) - float(estimated_fee)
                if balance_after < 0:
                    return {"transaction_id": transaction_id, "success": False, "message": "Insufficient balance for transaction"}, "Insufficient balance for transaction"
                sender_balance_after = str(balance_after)
            except ValueError:
                return {"transaction_id": transaction_id, "success": False, "message": "Error calculating balance after transaction"}, "Error calculating balance after transaction"
            
            # Store transaction data
            tx_data = {
                "blockchain_name": blockchain_name,
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "smart_contract_address": smart_contract_address,
                "tx_details": {
                    "amount": amount,
                    "sender": sender_address,
                    "recipient": recipient_address,
                    "estimated_fee": estimated_fee,
                    "currency": currency,
                    "gas_limit": gas_limit,
                    "gas_price": gas_price_wei,  # Store gas price in Wei
                    "fee_details": fee_details
                }
            }
            transaction_manager.store_transaction(transaction_id, tx_data)
            
            # Prepare response
            details = {
                "amount": amount,
                "sender": sender_address,
                "recipient": recipient_address,
                "chain": chain,
                "estimated_fee": estimated_fee,
                "gas_limit": gas_limit,
                "gas_price": gas_price_wei,  # Send gas price in Wei
                "sender_balance_before": sender_balance_before,
                "sender_balance_after": sender_balance_after,
                "contract_address": smart_contract_address,
                "currency": currency,
                "is_token": bool(smart_contract_address),
                "fee_details": fee_details
            }
            
            return {
                "success": True,
                "details": details,
                "transaction_id": transaction_id,
                "expires_at": (datetime.now() + timedelta(minutes=10)).isoformat(),
                "message": "Transaction prepared successfully"
            }, None
        
        except Exception as e:
            error_msg = f"Error preparing transaction: {str(e)}"
            self.logger.error(error_msg)
            return {"transaction_id": transaction_id, "success": False, "message": error_msg}, error_msg

    def send_transaction_by_id(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """Send a transaction using stored transaction data and provided private key"""
        try:
            # Get stored transaction data
            tx_data = transaction_manager.get_transaction(transaction_id)
            if not tx_data:
                self.logger.error(f"Transaction {transaction_id} not found or expired")
                return {}, "Transaction not found or expired"
            
            self.logger.debug(f"Sending transaction with ID: {transaction_id}")
            
            # Get chain and currency info
            chain, base_currency = self._get_chain_currency(tx_data["blockchain_name"])
            
            # For token transfers, get the token currency
            currency = base_currency
            if tx_data.get("smart_contract_address"):
                token_currency = self._get_token_currency(tx_data["blockchain_name"], tx_data["smart_contract_address"])
                if token_currency:
                    currency = token_currency
            
            # Get stored gas details from transaction data
            tx_details = tx_data.get("tx_details", {})
            gas_price = tx_details.get("gas_price")  # This is already in Wei
            gas_limit = tx_details.get("gas_limit")
            
            # If gas details are not in transaction data, calculate them
            if not gas_price or not gas_limit:
                fee_details = self.calculate_transaction_fee(
                    chain=chain,
                    from_address=tx_data["sender_address"],
                    to_address=tx_data["recipient_address"],
                    amount=tx_data["amount"],
                    contract_address=tx_data.get("smart_contract_address")
                )
                # Convert gas price from Gwei to Wei
                gas_price = str(int(round(fee_details["gas_price"] * 1e9)))
                gas_limit = str(fee_details["gas_limit"])
            
            # Prepare request data
            request_data = {
                "from": tx_data["sender_address"],
                "to": tx_data["recipient_address"],
                "amount": tx_data["amount"],
                "fromPrivateKey": private_key,
                "currency": currency,
                "fee": {
                    "gasLimit": str(gas_limit),
                    "gasPrice": str(gas_price)  # Already in Wei
                }
            }
            
            # Special handling for TRON
            if chain == "tron":
                endpoint = "/tron/transaction"
                if tx_data.get("smart_contract_address"):
                    request_data["tokenAddress"] = tx_data["smart_contract_address"]
                
                # Format amount for TRON (max 6 decimals)
                try:
                    amount_float = float(tx_data["amount"])
                    request_data["amount"] = f"{amount_float:.6f}"
                except (ValueError, TypeError):
                    self.logger.warning(f"Couldn't parse amount as float: {tx_data['amount']}, using as is")
            
            # Handle EVM chains (ETH, BNB, Polygon, etc.)
            elif chain in ["eth", "binance smart chain", "polygon", "avalanche", "arbitrum", "optimism"]:
                # For Ethereum and BNB, we need to sign the transaction locally and use broadcast endpoint
                if chain in ["eth", "binance smart chain"]:
                    try:
                        # Initialize Web3
                        infura_api_key = os.getenv('INFURA_API_KEY')
                        if not infura_api_key:
                            return {}, "INFURA_API_KEY environment variable not set"
                        
                        # Use appropriate RPC URL based on chain
                if chain == "eth":
                            w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{infura_api_key}'))
                            chain_id = 1  # Mainnet
                        else:  # BNB
                            w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org'))
                            chain_id = 56  # BNB Mainnet
                        
                        # Get nonce
                        nonce = w3.eth.get_transaction_count(tx_data["sender_address"])
                        self.logger.debug(f"Nonce for address {tx_data['sender_address']}: {nonce}")
                        
                        # Get current gas price - use a reasonable value
                        gas_price_wei = w3.eth.gas_price
                        # Cap gas price at 50 Gwei to prevent excessive fees
                        max_gas_price_wei = w3.to_wei(50, 'gwei')
                        if gas_price_wei > max_gas_price_wei:
                            gas_price_wei = max_gas_price_wei
                            
                        self.logger.debug(f"Gas price: {w3.from_wei(gas_price_wei, 'gwei')} Gwei")
                        
                        # For token transfers, we need more gas, for native transfers we need less
                        is_token_transfer = bool(tx_data.get("smart_contract_address"))
                        gas_limit = int(tx_details.get("gas_limit", "65000" if is_token_transfer else "21000"))
                        
                        # Prepare transaction
                        tx = {
                            'nonce': nonce,
                            'to': tx_data["recipient_address"],
                            'value': w3.to_wei(Decimal(tx_data["amount"]), 'ether'),
                            'gas': gas_limit,
                            'gasPrice': gas_price_wei,
                            'chainId': chain_id
                        }
                        
                        # Add contract data if it's a token transfer
                        if tx_data.get("smart_contract_address"):
                            # Convert amount from the token decimals to the smallest unit (usually 10^18 for most ERC20 tokens)
                            token_decimals = int(tx_details.get("token_decimals", 18))
                            token_amount = int(Decimal(tx_data["amount"]) * (10 ** token_decimals))
                            
                            # Format the transfer call data properly
                            transfer_data = "0xa9059cbb" + w3.to_hex(Web3.to_checksum_address(tx_data["recipient_address"]))[2:].zfill(64) + hex(token_amount)[2:].zfill(64)
                            
                            # For token transfers, set value to 0 as we're not sending native currency
                            tx['to'] = Web3.to_checksum_address(tx_data["smart_contract_address"])
                            tx['value'] = 0
                            tx['data'] = transfer_data
                            
                            # Log the debug info
                            self.logger.debug(f"Token transfer data: amount={tx_data['amount']}, decimals={token_decimals}, token_amount={token_amount}")
                            self.logger.debug(f"Transfer data: {transfer_data}")
                        
                        # Calculate total cost (gas * gasPrice)
                        gas_cost_wei = tx['gas'] * tx['gasPrice']
                        gas_cost_native = w3.from_wei(gas_cost_wei, 'ether')
                        self.logger.debug(f"Gas cost: {gas_cost_native} {chain.upper()}")
                        
                        # Sign transaction
                        try:
                            from eth_account.datastructures import SignedTransaction
                            
                            # Check web3.py version
                            import web3
                            web3_version = getattr(web3, '__version__', '5.0.0')
                            self.logger.debug(f"Web3.py version: {web3_version}")
                            
                            # Sign transaction
                            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
                            self.logger.debug(f"Signed transaction type: {type(signed_tx)}")
                            
                            # Extract raw transaction
                            raw_tx = self._extract_raw_transaction(signed_tx, private_key, tx)
                            
                            if not raw_tx:
                                error_msg = "Failed to extract raw transaction data after multiple attempts"
                                self.logger.error(error_msg)
                                return {}, error_msg
                                
                            # Ensure raw transaction has 0x prefix
                            if not raw_tx.startswith('0x'):
                                raw_tx = '0x' + raw_tx
                                
                            self.logger.debug(f"Raw transaction: {raw_tx[:10]}...")
                            
                            # Use broadcast endpoint
                            endpoint = f"/{chain}/broadcast"
                            request_data = {
                                "txData": raw_tx
                            }
                            
                            self.logger.debug(f"Using {chain} broadcast endpoint with signed transaction")
                            
                        except Exception as e:
                            error_msg = f"Error signing {chain} transaction: {str(e)}"
                            self.logger.error(error_msg)
                            return {}, error_msg
                        
                    except Exception as e:
                        error_msg = f"Error preparing {chain} transaction: {str(e)}"
                        self.logger.error(error_msg)
                        return {}, error_msg
                else:
                    # For other EVM chains, still use standard transaction endpoint
                    endpoint = f"/{chain}/transaction"
                
                if tx_data.get("smart_contract_address"):
                    request_data["contractAddress"] = tx_data["smart_contract_address"]
            # Handle other chains
            else:
                endpoint = f"/{chain}/transaction"
                if tx_data.get("smart_contract_address"):
                    request_data["contractAddress"] = tx_data["smart_contract_address"]
            
            # Log request (without private key)
            safe_request_data = request_data.copy()
            safe_request_data['fromPrivateKey'] = '***'
            self.logger.debug(f"Sending {chain} transaction")
            self.logger.debug(f"Request data: {json.dumps(safe_request_data, indent=2)}")
            
            # Send transaction
            response_data, error = self._make_request_sync('post', endpoint, data=request_data)
            if error:
                self.logger.error(f"Error sending transaction: {error}")
                return {}, error
            
            tx_hash = response_data.get('txId')
            if not tx_hash:
                error_msg = "Transaction hash not found in response"
                self.logger.error(error_msg)
                return {}, error_msg
            
            # Get updated balance
            balance_data, error = self.get_balance(tx_data["blockchain_name"], tx_data["sender_address"])
            sender_balance_after = "Unknown"
            if not error and balance_data:
                sender_balance_after = balance_data.get('balance', 'Unknown')
            
            # Remove transaction from pending
            transaction_manager.remove_transaction(transaction_id)
            
            # Prepare result
            result = {
                "transaction_hash": tx_hash,
                "actual_fee": response_data.get('fee', "Unknown"),
                "sender_balance_after": sender_balance_after,
                "status": "Unconfirmed",
                "description": "Transaction has been submitted to the blockchain network and is waiting to be processed."
            }
            
            self.logger.info(f"Transaction sent successfully: {tx_hash}")
            return result, None
            
        except Exception as e:
            error_msg = f"Error sending transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg

    def send_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                         recipient_address: str, amount: str, tx_details: Dict) -> Tuple[Dict, Optional[str]]:
        """Send a transaction with the provided details using Tatum API"""
        try:
            self.logger.info(f"Starting to send {blockchain_name} transaction from {sender_address} to {recipient_address} with amount {amount}")
            
            # Check wallet balance first
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            if error:
                self.logger.error(f"Error getting sender balance: {error}")
                return {}, f"Error getting sender balance: {error}"
                
            sender_balance = Decimal(balance_data.get('balance', '0'))
            self.logger.info(f"Sender balance: {sender_balance} {blockchain_name.upper()}")
            
            # Decrypt private key if needed (implement your decryption logic here)
            decrypted_private_key = private_key  # Replace with actual decryption
            
            chain, _ = self._get_chain_currency(blockchain_name)
            
            # For Ethereum, sign transaction locally using Web3
            if chain == "eth":
                try:
                    # Initialize Web3
                    infura_api_key = os.getenv('INFURA_API_KEY')
                    if not infura_api_key:
                        return {}, "INFURA_API_KEY environment variable not set"
                    w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{infura_api_key}'))
                    
                    # Get nonce
                    nonce = w3.eth.get_transaction_count(sender_address)
                    self.logger.debug(f"Nonce for address {sender_address}: {nonce}")
                    
                    # Get current gas price - use a reasonable value
                    gas_price_wei = w3.eth.gas_price
                    # Cap gas price at 50 Gwei to prevent excessive fees
                    max_gas_price_wei = w3.to_wei(50, 'gwei')
                    if gas_price_wei > max_gas_price_wei:
                        gas_price_wei = max_gas_price_wei
                        
                    self.logger.debug(f"Gas price: {w3.from_wei(gas_price_wei, 'gwei')} Gwei")
                    
                    # For token transfers, we need more gas, for ETH transfers we need less
                    is_token_transfer = bool(tx_details.get("contract_address"))
                    gas_limit = int(tx_details.get("gas_limit", "65000" if is_token_transfer else "21000"))
                    
                    # Prepare transaction
                    tx = {
                        'nonce': nonce,
                        'to': recipient_address,
                        'value': w3.to_wei(Decimal(amount), 'ether'),  # Convert amount to Wei properly
                        'gas': gas_limit,
                        'gasPrice': gas_price_wei,
                        'chainId': 1  # Mainnet
                    }
                    
                    # Add contract data if it's a token transfer
                    if tx_details.get("contract_address"):
                        # Convert amount from the token decimals to the smallest unit (usually 10^18 for most ERC20 tokens)
                        token_decimals = int(tx_details.get("token_decimals", 18))
                        token_amount = int(Decimal(amount) * (10 ** token_decimals))
                        
                        # Format the transfer call data properly
                        transfer_data = "0xa9059cbb" + w3.to_hex(Web3.to_checksum_address(recipient_address))[2:].zfill(64) + hex(token_amount)[2:].zfill(64)
                        
                        # For token transfers, set value to 0 as we're not sending ETH
                        tx['to'] = Web3.to_checksum_address(tx_details["contract_address"])
                        tx['value'] = 0
                        tx['data'] = transfer_data
                        
                        # Use higher gas limit for token transfers
                        tx['gas'] = int(tx_details.get("gas_limit", "100000"))  # Higher default for tokens
                        
                        # Estimate gas (optional, can be slow but more accurate)
                        try:
                            estimated_gas = w3.eth.estimate_gas({
                                'from': sender_address,
                                'to': tx['to'],
                                'data': tx['data'],
                                'value': 0
                            })
                            # Add 20% buffer
                            tx['gas'] = int(estimated_gas * 1.2)
                            self.logger.debug(f"Estimated gas for token transfer: {estimated_gas}, using: {tx['gas']}")
                        except Exception as e:
                            self.logger.warning(f"Could not estimate gas for token transfer: {str(e)}, using default gas limit")
                        
                        # Log the debug info
                        self.logger.debug(f"Token transfer data: amount={amount}, decimals={token_decimals}, token_amount={token_amount}")
                        self.logger.debug(f"Transfer data: {transfer_data}")
                        
                    # Calculate total ETH cost (gas * gasPrice)
                    gas_cost_wei = tx['gas'] * tx['gasPrice']
                    gas_cost_eth = w3.from_wei(gas_cost_wei, 'ether')
                    
                    # For ETH transfers, check if we have enough balance for amount + gas
                    if not tx_details.get("contract_address"):
                        # If amount is "MAX", calculate the maximum possible amount
                        if amount.upper() == "MAX":
                            try:
                                eth_balance = Decimal(w3.from_wei(w3.eth.get_balance(sender_address), 'ether'))
                                # Subtract gas cost from total balance to get maximum sendable amount
                                max_amount = eth_balance - Decimal(gas_cost_eth)
                                # Add a small buffer (0.000001 ETH) to prevent rounding issues
                                max_amount = max_amount - Decimal('0.000001')
                                if max_amount <= 0:
                                    error_msg = f"Insufficient ETH balance for gas fees. Balance: {eth_balance}, Required for gas: {gas_cost_eth}"
                                    self.logger.error(error_msg)
                                    return {}, error_msg
                                amount = str(max_amount)
                                tx['value'] = w3.to_wei(max_amount, 'ether')
                                self.logger.debug(f"MAX amount calculated: {amount} ETH (Balance: {eth_balance}, Gas: {gas_cost_eth})")
                            except Exception as e:
                                self.logger.warning(f"Could not calculate MAX amount: {str(e)}")
                        else:
                            total_required = Decimal(amount) + Decimal(gas_cost_eth)
                            # Get balance again to be sure
                            try:
                                eth_balance = Decimal(w3.from_wei(w3.eth.get_balance(sender_address), 'ether'))
                                if eth_balance < total_required:
                                    error_msg = f"Insufficient ETH balance for transaction and gas. Balance: {eth_balance}, Required: {total_required} (Amount: {amount} + Gas: {gas_cost_eth})"
                                    self.logger.error(error_msg)
                                    return {}, error_msg
                                self.logger.debug(f"ETH Balance check passed: {eth_balance} >= {total_required}")
                            except Exception as e:
                                self.logger.warning(f"Could not verify ETH balance: {str(e)}")
                    else:
                        # For token transfers, we only need enough ETH for gas
                        try:
                            eth_balance = Decimal(w3.from_wei(w3.eth.get_balance(sender_address), 'ether'))
                            if eth_balance < Decimal(gas_cost_eth):
                                error_msg = f"Insufficient ETH balance for token transfer gas fees. Balance: {eth_balance}, Required for gas: {gas_cost_eth}"
                                self.logger.error(error_msg)
                                return {}, error_msg
                            self.logger.debug(f"ETH Balance check for gas passed: {eth_balance} >= {gas_cost_eth}")
                        except Exception as e:
                            self.logger.warning(f"Could not verify ETH balance for gas: {str(e)}")
                    
                    # امضای تراکنش اتریوم
                    try:
                        from eth_account.datastructures import SignedTransaction
                        
                        # برسی نسخه web3.py
                        import web3
                        web3_version = getattr(web3, '__version__', '5.0.0')
                        self.logger.debug(f"Web3.py version: {web3_version}")
                        
                        # امضای تراکنش
                        signed_tx = w3.eth.account.sign_transaction(tx, decrypted_private_key)
                        self.logger.debug(f"Signed transaction type: {type(signed_tx)}")
                        
                        # استخراج تراکنش خام با استفاده از تابع کمکی
                        raw_tx = self._extract_raw_transaction(signed_tx, decrypted_private_key, tx)
                        
                        if not raw_tx:
                            error_msg = "Failed to extract raw transaction data after multiple attempts"
                            self.logger.error(error_msg)
                            return {}, error_msg
                            
                        # Ensure raw transaction has 0x prefix
                        if not raw_tx.startswith('0x'):
                            raw_tx = '0x' + raw_tx
                            
                        self.logger.debug(f"Raw transaction: {raw_tx[:10]}...")
                        
                        # Use Ethereum broadcast endpoint
                        endpoint = "/ethereum/broadcast"
                        request_data = {
                            "txData": raw_tx
                        }
                        
                        self.logger.debug("Using Ethereum broadcast endpoint with signed transaction")
                        
                    except Exception as e:
                        error_msg = f"Error signing Ethereum transaction: {str(e)}"
                        self.logger.error(error_msg)
                        return {}, error_msg
                    
                    # Update tx_details with signed transaction
                    tx_details["signed_tx"] = raw_tx
                    
                except Exception as e:
                    error_msg = f"Error signing Ethereum transaction locally: {str(e)}"
                    self.logger.error(error_msg)
                    return {}, error_msg
            
            # Prepare request data
            request_data = {
                "from": sender_address,
                "to": recipient_address,
                "amount": amount,
                "fromPrivateKey": decrypted_private_key
            }
            
            # Add blockchain-specific parameters
            if chain == "binance smart chain":
                endpoint = "/binance smart chain/transaction"
                if tx_details.get("contract_address"):
                    request_data["contractAddress"] = tx_details["contract_address"]
                request_data["fee"] = {
                    "gasLimit": tx_details.get("gas_limit", "21000"),
                    "gasPrice": tx_details.get("gas_price", "5")
                }
            elif chain == "eth":
                endpoint = "/ethereum/broadcast"
                request_data = {
                    "txData": tx_details["signed_tx"]
                }
            else:
                endpoint = f"/{chain}/transaction"
                if tx_details.get("contract_address"):
                    request_data["contractAddress"] = tx_details["contract_address"]
            
            # Log request (without private key)
            safe_request_data = request_data.copy()
            if 'fromPrivateKey' in safe_request_data:
            safe_request_data['fromPrivateKey'] = '***'
            self.logger.debug(f"Sending {chain} transaction with direct parameters")
            self.logger.debug(f"Request data: {safe_request_data}")
            
            # Send transaction
            response_data, error = self._make_request_sync('post', endpoint, data=request_data)
            if error:
                self.logger.error(f"Error sending transaction: {error}")
                return {}, error
            
            tx_hash = response_data.get('txId')
            if not tx_hash:
                error_msg = "Transaction hash not found in response"
                self.logger.error(error_msg)
                return {}, error_msg
            
            # Get updated balance
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            sender_balance_after = "Unknown"
            if not error and balance_data:
                sender_balance_after = balance_data.get('balance', 'Unknown')
            
            # Prepare result
            result = {
                "transaction_hash": tx_hash,
                "actual_fee": response_data.get('fee', "Unknown"),
                "sender_balance_after": sender_balance_after,
                "status": "Unconfirmed",
                "description": "Transaction has been submitted to the blockchain network and is waiting to be processed."
            }
            
            # Log success (without sensitive data)
            self.logger.info(f"Transaction sent successfully: {tx_hash}")
            return result, None
            
        except Exception as e:
            error_msg = f"Error sending transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg

    def check_transaction_status(self, blockchain_name: str, tx_hash: str) -> Tuple[str, str]:
        """Check the status of a transaction"""
        chain, _ = self._get_chain_currency(blockchain_name)
        
        try:
            # Get transaction data
            tx_data, error = self.get_transaction(blockchain_name, tx_hash)
            
            if error:
                return "Unknown", f"Could not check transaction status: {error}"
                
            # Different chains have different fields to check for confirmation
            if 'confirmations' in tx_data:
                confirmations = int(tx_data['confirmations'])
                
                if confirmations > 0:
                    return "Confirmed", f"Transaction confirmed with {confirmations} confirmations"
                else:
                    return "Unconfirmed", "Transaction is in mempool, waiting to be included in a block"
                    
            elif 'status' in tx_data:
                status = tx_data['status']
                
                if status.lower() == 'confirmed' or status.lower() == 'success':
                    return "Confirmed", "Transaction confirmed"
                elif status.lower() == 'failed' or status.lower() == 'error':
                    return "Failed", "Transaction failed"
                else:
                    return "Unconfirmed", f"Transaction status: {status}"
            
            # Default response if we can't determine status
            return "Unknown", "Could not determine transaction status"
            
        except Exception as e:
            error_msg = f"Error checking transaction status: {str(e)}"
            self.logger.error(error_msg)
            return "Unknown", error_msg
    
    def sign_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                        recipient_address: str, amount: str, smart_contract_address=None) -> Tuple[Dict, Optional[str]]:
        """Sign a transaction without broadcasting using Tatum API"""
        try:
            # Get chain name and validate addresses
            chain, _ = self._get_chain_currency(blockchain_name)
            
            if not self.validate_address(blockchain_name, sender_address):
                return {}, f"Invalid sender address format for {blockchain_name}"
                
            if not self.validate_address(blockchain_name, recipient_address):
                return {}, f"Invalid recipient address format for {blockchain_name}"
            
            # Get current balance first
            balance_data, error = self.get_balance(blockchain_name, sender_address)
            if error:
                return {}, f"Error getting sender balance: {error}"
            
            sender_balance_before = balance_data.get('balance', '0')
            
            # Prepare request data based on blockchain
            if chain == "binance smart chain":
                # First get gas estimate
                gas_data, gas_error = self._make_request('post', "/binance smart chain/gas", data={
                    "from": sender_address,
                    "to": recipient_address,
                    "amount": amount,
                    "data": "" if not smart_contract_address else "0xa9059cbb"  # Transfer method ID for tokens
                })
                
                if gas_error:
                    estimated_fee = "0.0001"  # Default estimate for BSC
                    gas_limit = "21000"
                    gas_price = "5"
                else:
                    gas_limit = gas_data.get('gasLimit', '21000')
                    gas_price = gas_data.get('gasPrice', '5')
                    estimated_fee = str(float(gas_price) * float(gas_limit) / 1e9)
                
                # Prepare request data
                request_data = {
                    "from": sender_address,
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "BSC"
                }
                
                if smart_contract_address:
                    request_data["contractAddress"] = smart_contract_address
                
                request_data["fee"] = {
                    "gasLimit": str(gas_limit),
                    "gasPrice": str(gas_price)
                }
                
            elif chain == "eth":
                estimated_fee = "0.00042"  # Default estimate for ETH
                request_data = {
                    "from": sender_address,
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "ETH",
                    "fee": {
                        "gasLimit": "21000",
                        "gasPrice": "20"
                    }
                }
                
                if smart_contract_address:
                    request_data["contractAddress"] = smart_contract_address
                
            else:
                # For other chains
                estimated_fee = "0.0001"  # Default estimate
                request_data = {
                    "from": sender_address,
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": blockchain_name.upper()
                }
                
                if smart_contract_address:
                    request_data["contractAddress"] = smart_contract_address
            
            # Use transaction/sign endpoint to only sign the transaction
            endpoint = "/transaction/sign"
            
            # Make request to Tatum API
            self.logger.debug(f"Signing {chain} transaction")
            self.logger.debug(f"Request data: {request_data}")
            
            response_data, error = self._make_request('post', endpoint, data=request_data)
            
            if error:
                return {}, f"Error signing transaction: {error}"
            
            # Get signed transaction from response
            signed_tx = response_data.get('signedTx')
            if not signed_tx:
                return {}, "Signed transaction data not found in response"
            
            # Calculate estimated balance after
            try:
                balance_after = float(sender_balance_before) - float(amount) - float(estimated_fee)
                sender_balance_after = str(max(0, balance_after))
            except (ValueError, TypeError):
                sender_balance_after = "Unknown"
            
            # Generate a unique transaction ID
            transaction_id = response_data.get('txId', str(uuid.uuid4()))
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "currency": blockchain_name.upper(),
                "transaction_id": transaction_id,
                "is_token": bool(smart_contract_address),
                "contract_address": smart_contract_address,
                "chain": chain,
                "signed_tx": signed_tx,
                "estimated_fee": estimated_fee,
                "sender_balance_before": sender_balance_before,
                "sender_balance_after": sender_balance_after
            }
            
            return tx_details, None
            
        except ValueError as e:
            return {}, str(e)
        except Exception as e:
            error_msg = f"Error signing transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
    
    def broadcast_transaction(self, blockchain_name: str, signed_tx: str) -> Tuple[Dict, Optional[str]]:
        """Broadcast a signed transaction to the blockchain"""
        try:
            chain, _ = self._get_chain_currency(blockchain_name)
            
            # Prepare request data
            request_data = {
                "txData": signed_tx,
                "chain": chain
            }
            
            # Use transaction/broadcast endpoint
            endpoint = "/transaction/broadcast"
            
            # Log request details
            self.logger.debug(f"Broadcasting {chain} transaction")
            self.logger.debug(f"Request data: {request_data}")
            
            # Send transaction
            response_data, error = self._make_request('post', endpoint, data=request_data)
            
            if error:
                return {}, error
            
            # Extract transaction hash from response
            tx_hash = response_data.get('txId')
            
            if not tx_hash:
                error_msg = "Failed to broadcast transaction: Transaction ID not found in response"
                self.logger.error(error_msg)
                self.logger.error(f"Broadcast response data: {response_data}")
                return {}, error_msg
            
            # Prepare result
            result = {
                "transaction_hash": tx_hash,
                "actual_fee": response_data.get('fee', "Unknown"),
                "status": "Unconfirmed",
                "description": "Transaction has been submitted to the blockchain network and is waiting to be processed."
            }
            
            return result, None
            
        except ValueError as e:
            return {}, str(e)
        except Exception as e:
            error_msg = f"Error broadcasting transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg

    async def get_transaction_count(self, address: str) -> Tuple[int, Optional[str]]:
        """
        Get transaction count (nonce) from Tatum API
        
        Args:
            address: Ethereum address to get nonce for
            
        Returns:
            Tuple of (nonce, error_message)
        """
        endpoint = f"ethereum/transaction/count/{address}"
        url = f"{self.base_url.rstrip('/')}/{endpoint}"

        try:
            self.logger.debug(f"Getting transaction count for address: {address}")
            self.logger.debug(f"Request URL: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        error_msg = f"Unexpected response: {response.status}, content: {text}"
                        self.logger.error(error_msg)
                        return 0, error_msg

                    text = await response.text()
                    self.logger.debug(f"Raw response text: {text}")
                    
                    try:
                        nonce = int(text)
                        self.logger.debug(f"Successfully parsed nonce: {nonce}")
                        return nonce, None
                    except ValueError:
                        error_msg = f"Invalid nonce format from Tatum: {text}"
                        self.logger.error(error_msg)
                        return 0, error_msg
                        
        except aiohttp.ClientError as e:
            error_msg = f"Network error while getting nonce: {str(e)}"
            self.logger.error(error_msg)
            return 0, error_msg
        except Exception as e:
            error_msg = f"Unexpected error while getting nonce: {str(e)}"
            self.logger.error(error_msg)
            return 0, error_msg

    async def get_gas_price(self, blockchain: str = "ethereum") -> Tuple[int, Optional[str]]:
        """
        Get current gas price from Tatum API
        
        Args:
            blockchain: Name of the blockchain (e.g., "ethereum", "bsc")
            
        Returns:
            Tuple of (gas_price_in_wei, error_message)
        """
        try:
            chain, _ = self._get_chain_currency(blockchain)
            endpoint = f"{chain}/gas"
            url = f"{self.base_url.rstrip('/')}/{endpoint}"

            self.logger.debug(f"Getting gas price for blockchain: {blockchain}")
            self.logger.debug(f"Request URL: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        error_msg = f"Error getting gas price: {text}"
                        self.logger.error(error_msg)
                        return 0, error_msg
                        
                    json_data = await response.json()
                    gas_price = int(json_data.get('gasPrice', 0))
                    self.logger.debug(f"Successfully got gas price: {gas_price}")
                    return gas_price, None
                    
        except ValueError as e:
            return 0, str(e)
        except Exception as e:
            error_msg = f"Exception getting gas price: {str(e)}"
            self.logger.error(error_msg)
            return 0, error_msg

    # API compatibility wrapper for the original async method
    def prepare_transaction(self, blockchain_name: str, sender_address: str, recipient_address: str, 
                         amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Dict, Optional[str]]:
        """Prepare a transaction - compatibility wrapper for the sync version"""
        self.logger.debug(f"Called prepare_transaction with params: {blockchain_name}, {sender_address}, {recipient_address}, {amount}")
        return self.prepare_transaction_sync(
            blockchain_name=blockchain_name,
            sender_address=sender_address,
            recipient_address=recipient_address,
            amount=amount,
            smart_contract_address=smart_contract_address
        ) 

    def _extract_raw_transaction(self, signed_tx, private_key, tx):
        """استخراج تراکنش خام از شیء تراکنش امضا شده"""
        raw_tx = None
        
        # 1. دسترسی مستقیم به ویژگی‌ها
        try:
            if hasattr(signed_tx, 'rawTransaction'):
                raw_tx = signed_tx.rawTransaction.hex()
                self.logger.debug("Accessed rawTransaction directly")
                return raw_tx
                
            if hasattr(signed_tx, 'raw_transaction'):
                raw_tx = signed_tx.raw_transaction.hex()
                self.logger.debug("Accessed raw_transaction directly")
                return raw_tx
        except Exception as e:
            self.logger.warning(f"Direct access to raw transaction failed: {str(e)}")
        
        # 2. دسترسی با استفاده از __dict__
        try:
            if hasattr(signed_tx, '__dict__'):
                tx_dict = signed_tx.__dict__
                if 'rawTransaction' in tx_dict:
                    raw_tx = tx_dict['rawTransaction'].hex()
                    self.logger.debug("Accessed rawTransaction via __dict__")
                    return raw_tx
                    
                if 'raw_transaction' in tx_dict:
                    raw_tx = tx_dict['raw_transaction'].hex()
                    self.logger.debug("Accessed raw_transaction via __dict__")
                    return raw_tx
        except Exception as e:
            self.logger.warning(f"__dict__ access to raw transaction failed: {str(e)}")
        
        # 3. سعی در تبدیل به dict
        try:
            tx_dict = dict(signed_tx)
            if 'rawTransaction' in tx_dict:
                raw_tx = tx_dict['rawTransaction'].hex()
                self.logger.debug("Accessed rawTransaction via dict")
                return raw_tx
                
            if 'raw_transaction' in tx_dict:
                raw_tx = tx_dict['raw_transaction'].hex()
                self.logger.debug("Accessed raw_transaction via dict")
                return raw_tx
        except Exception as e:
            self.logger.warning(f"Dict access to raw transaction failed: {str(e)}")
        
        # 4. دسترسی با استفاده از getattr
        try:
            raw_transaction = getattr(signed_tx, 'rawTransaction', None) or getattr(signed_tx, 'raw_transaction', None)
            if raw_transaction:
                raw_tx = raw_transaction.hex()
                self.logger.debug("Accessed raw transaction via getattr")
                return raw_tx
        except Exception as e:
            self.logger.warning(f"Getattr access to raw transaction failed: {str(e)}")
        
        # 5. استفاده از bytes
        try:
            raw_tx = bytes(signed_tx).hex()
            self.logger.debug("Generated raw transaction by bytes conversion")
            return raw_tx
        except Exception as e:
            self.logger.warning(f"Bytes conversion of raw transaction failed: {str(e)}")
        
        # 6. امضای دوباره تراکنش
        try:
            from web3.auto import w3 as w3_auto
            signed_tx_again = w3_auto.eth.account.sign_transaction(tx, private_key)
            
            # سعی در استفاده از هر روش ممکن
            if hasattr(signed_tx_again, 'rawTransaction'):
                raw_tx = signed_tx_again.rawTransaction.hex() 
                self.logger.debug("Used re-signing to get rawTransaction")
                return raw_tx
                
            raw_tx = bytes(signed_tx_again).hex()
            self.logger.debug("Re-signed and used bytes conversion")
            return raw_tx
        except Exception as e:
            self.logger.warning(f"Re-signing transaction failed: {str(e)}")
            
        # 7. استفاده از str و جداسازی
        try:
            tx_str = str(signed_tx)
            if "rawTransaction=HexBytes('" in tx_str:
                start = tx_str.find("rawTransaction=HexBytes('") + 24
                end = tx_str.find("')", start)
                if start > 24 and end > start:
                    raw_tx = tx_str[start:end]
                    self.logger.debug("Extracted raw transaction from string representation")
                    return raw_tx
        except Exception as e:
            self.logger.warning(f"String extraction failed: {str(e)}")
        
        # اگر هیچ روشی موفق نشد
        self.logger.error(f"All methods to extract raw transaction failed. SignedTransaction: {repr(signed_tx)}")
        self.logger.error(f"Object type: {type(signed_tx)}, dir: {dir(signed_tx)}")
        return None 