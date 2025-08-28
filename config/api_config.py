from web3 import Web3
import logging
from CC.utils.logging_config import get_logger
import time
import threading
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# بارگذاری فایل .env
load_dotenv()

logger = get_logger(__file__)

# دریافت کلید API از محیط
def get_api_key(key_name, default_value=""):
    """دریافت کلید API از متغیرهای محیطی"""
    return os.environ.get(key_name, default_value)

# Class to manage API rate limiting
class APIRateLimiter:
    def __init__(self):
        self.api_calls = {}
        self.locks = {}
        self.api_limits = {
            # EVM APIs - Free tier rate limits
            "Etherscan": {"limit": 5, "window": 1},         # 5 calls per sec for free tier
            "Moralis": {"limit": 1, "window": 1},           # 1 call per sec for free tier 
            "Covalent": {"limit": 3, "window": 60},         # 3 calls per min for free tier
            
            # Non-EVM APIs
            "Trongrid": {"limit": 5, "window": 1},          # 5 calls per sec for free tier
            "Solana": {"limit": 5, "window": 1},            # 5 calls per sec for free RPC
            "Blockcypher": {"limit": 3, "window": 1},       # 3 calls per sec for free tier
            "Subscan": {"limit": 5, "window": 60},          # 5 calls per min for free tier
            "XRPScan": {"limit": 5, "window": 60}           # 5 calls per min estimated
        }
        
        # Initialize locks for each API
        for api in self.api_limits:
            self.locks[api] = threading.Lock()
            self.api_calls[api] = []
    
    def check_rate_limit(self, api_name):
        """Check if we can make a call to the API based on rate limits"""
        if api_name not in self.api_limits:
            logger.warning(f"No rate limit defined for API: {api_name}")
            return True
            
        with self.locks[api_name]:
            now = datetime.now()
            limit_config = self.api_limits[api_name]
            
            # Remove old calls
            window_start = now - timedelta(seconds=limit_config["window"])
            self.api_calls[api_name] = [t for t in self.api_calls[api_name] if t > window_start]
            
            # Check if we're within limits
            if len(self.api_calls[api_name]) < limit_config["limit"]:
                self.api_calls[api_name].append(now)
                return True
            else:
                oldest_call = min(self.api_calls[api_name])
                wait_time = (oldest_call + timedelta(seconds=limit_config["window"]) - now).total_seconds()
                
                if wait_time > 0:
                    logger.warning(f"Rate limit for {api_name} reached. Waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                    
                # Add the current call and return
                self.api_calls[api_name].append(datetime.now())
                return True

# Global rate limiter instance
rate_limiter = APIRateLimiter()

class Web3Manager:
    """مدیریت اتصالات Web3 با بلاکچین‌های مختلف"""
    
    @staticmethod
    def get_web3_providers():
        """
        Get dictionary of Web3 providers for different blockchains
        Returns:
            dict: Dictionary of blockchain name to Web3 provider
        """
        try:
            from web3 import Web3
            
            # Dictionary of blockchain name to RPC URL
            rpc_urls = {
                "ethereum": get_api_key("ETHEREUM_RPC_URL", "https://mainnet.infura.io/v3/" + get_api_key("INFURA_API_KEY", "")),
                "binance smart chain": get_api_key("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
                "polygon": get_api_key("POLYGON_RPC_URL", "https://polygon-rpc.com"),
                "avalanche": get_api_key("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
                "arbitrum": get_api_key("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
                # توجه: برای بلاکچین‌های غیر-EVM (مانند Tron، Solana) نیازی به تعریف اینجا نیست
            }
            
            # ایجاد فراهم‌کننده‌های Web3 برای هر بلاکچین
            providers = {}
            for blockchain, rpc_url in rpc_urls.items():
                try:
                    # اضافه کردن HTTPProvider با خطای بازنشست نامعتبر غیرفعال شده
                    provider = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 60}))
                    providers[blockchain] = provider
                    logger.info(f"Successfully initialized Web3 provider for {blockchain}")
                except Exception as e:
                    logger.error(f"Error creating Web3 provider for {blockchain}: {str(e)}")
            
            # اضافه کردن نام‌های مستعار برای بلاکچین‌ها
            if 'ethereum' in providers:
                providers['eth'] = providers['ethereum']
                
            if 'binance smart chain' in providers:
                providers['bsc'] = providers['binance smart chain']
                providers['bnb'] = providers['binance smart chain']
                
            if 'polygon' in providers:
                providers['matic'] = providers['polygon']
                
            if 'avalanche' in providers:
                providers['avax'] = providers['avalanche']
                
            if 'arbitrum' in providers:
                providers['arb'] = providers['arbitrum']
                
            logger.info(f"Initialized Web3 providers for {len(set(providers.values()))} unique blockchains")
            return providers
        except ImportError:
            logger.error("Web3 module not available")
            return {}

# Standard ABI for ERC20 tokens
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# External API configurations - کلیدها از فایل .env خوانده می‌شوند
EXTERNAL_APIS = {
    # کلیدهای API از متغیرهای محیطی
    "TATUM_API_KEY": get_api_key("TATUM_API_KEY"),  
    "ETHERSCAN_API_KEY": get_api_key("ETHERSCAN_API_KEY"),  
    "BSCSCAN_API_KEY": get_api_key("BSCSCAN_API_KEY"),    
    "POLYGONSCAN_API_KEY": get_api_key("POLYGONSCAN_API_KEY"), 
    "TRONGRID_API_KEY": get_api_key("TRONGRID_API_KEY"),   
    "SOLANA_API_KEY": get_api_key("SOLANA_API_KEY"),     
    "AVALANCHE_API_KEY": get_api_key("AVALANCHE_API_KEY"),
    "ARBITRUM_API_KEY": get_api_key("ARBITRUM_API_KEY"),
    "XRP_API_KEY": get_api_key("XRP_API_KEY"),
    "POLKADOT_API_KEY": get_api_key("POLKADOT_API_KEY"),
    "BITCOIN_API_KEY": get_api_key("BITCOIN_API_KEY"),
    
    # RPC URLs
    "EthereumRPC": get_api_key("ETHEREUM_RPC_URL", "https://mainnet.infura.io/v3/" + get_api_key("INFURA_API_KEY", "")),
    "BSCRPC": get_api_key("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
    "PolygonRPC": get_api_key("POLYGON_RPC_URL", "https://polygon-rpc.com"),
    "AvalancheRPC": get_api_key("AVALANCHE_RPC_URL", "https://api.avax.network/ext/bc/C/rpc"),
    "ArbitrumRPC": get_api_key("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
    
    # تنظیمات API برای Ethereum
    "Ethereum": {
        "key_env": "ETHERSCAN_API_KEY",
        "url": "https://api.etherscan.io/api",
        "balance_url": "https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
        "token_url": "https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
    },
    
    # تنظیمات API برای Binance Smart Chain
    "Binance Smart Chain": {
        "key_env": "BSCSCAN_API_KEY",
        "url": "https://api.bscscan.com/api",
        "balance_url": "https://api.bscscan.com/api?module=account&action=balance&address={address}&tag=latest",
        "token_url": "https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
    },
    
    # تنظیمات API برای Bitcoin
    "Bitcoin": {
        "key_env": "BITCOIN_API_KEY",
        "url": "https://api.blockchain.info/rawaddr/{address}"
    },
    
    # تنظیمات API برای Tron
    "Tron": {
        "key_env": "TRONGRID_API_KEY",
        "url": "https://api.trongrid.io/v1/accounts/{address}",
        "token_url": "https://api.trongrid.io/v1/accounts/{address}/tokens"
    },
    
    # تنظیمات API برای Polygon
    "Polygon": {
        "key_env": "POLYGONSCAN_API_KEY",
        "url": "https://api.polygonscan.com/api",
        "balance_url": "https://api.polygonscan.com/api?module=account&action=balance&address={address}&tag=latest",
        "token_url": "https://api.polygonscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
    },
    
    # تنظیمات API برای Solana
    "Solana": {
        "key_env": "SOLANA_API_KEY",
        "url": "https://api.mainnet-beta.solana.com",
    },
    
    # تنظیمات API برای Avalanche
    "Avalanche": {
        "key_env": "AVALANCHE_API_KEY",
        "url": "https://api.avax.network/ext/bc/C/rpc",
        "balance_url": "https://api.snowtrace.io/api?module=account&action=balance&address={address}&tag=latest",
        "token_url": "https://api.snowtrace.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
    },
    
    # تنظیمات API برای Arbitrum
    "Arbitrum": {
        "key_env": "ARBITRUM_API_KEY",
        "url": "https://arb1.arbitrum.io/rpc",
        "balance_url": "https://api.arbiscan.io/api?module=account&action=balance&address={address}&tag=latest",
        "token_url": "https://api.arbiscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
    },
    
    # تنظیمات API برای XRP
    "XRP": {
        "key_env": "XRP_API_KEY",
        "url": "https://xrplcluster.com/",
    },
    
    # تنظیمات API برای Polkadot
    "Polkadot": {
        "key_env": "POLKADOT_API_KEY",
        "url": "https://polkadot.api.subscan.io/api/scan/account",
        "token_url": "https://polkadot.api.subscan.io/api/scan/tokens"
    }
}

# Helper function to make rate-limited API calls
def make_api_request(api_name, url, method="get", headers=None, params=None, data=None):
    """Make an API request with rate limiting"""
    if rate_limiter.check_rate_limit(api_name):
        try:
            import requests
            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=params)
            elif method.lower() == "post":
                response = requests.post(url, headers=headers, params=params, json=data)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
                
            # Log the response status
            logger.debug(f"API response from {api_name}: status {response.status_code}")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception as e:
                    logger.error(f"JSON parsing error for {api_name} response: {str(e)}")
                    logger.debug(f"Raw response: {response.text[:500]}")
                    return None
            else:
                logger.warning(f"API request to {api_name} failed with status {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Error making API request to {api_name}: {str(e)}")
            return None
    return None 

# اضافه کردن تابع برای بررسی کلیدهای API
def check_api_keys():
    """بررسی کلیدهای API که از فایل .env خوانده شده‌اند"""
    missing_keys = []
    
    # کلیدهای حیاتی که نبود آنها باعث خطای بحرانی می‌شود
    critical_keys = ["TATUM_API_KEY", "ETHERSCAN_API_KEY", "BSCSCAN_API_KEY"]
    
    # کلیدهای غیر بحرانی که می‌توانند نباشند
    optional_keys = [
        "POLYGONSCAN_API_KEY", "TRONGRID_API_KEY", "SOLANA_API_KEY",
        "AVALANCHE_API_KEY", "ARBITRUM_API_KEY", "XRP_API_KEY", 
        "POLKADOT_API_KEY", "BITCOIN_API_KEY", "INFURA_API_KEY"
    ]
    
    # بررسی کلیدهای حیاتی
    critical_missing = []
    for key in critical_keys:
        if not get_api_key(key):
            critical_missing.append(key)
    
    # بررسی کلیدهای غیرحیاتی
    optional_missing = []
    for key in optional_keys:
        if not get_api_key(key):
            optional_missing.append(key)
    
    # هشدار برای کلیدهای حیاتی
    if critical_missing:
        logger.error(f"Critical API keys missing in .env file: {', '.join(critical_missing)}")
        missing_keys.extend(critical_missing)
    
    # هشدار برای کلیدهای غیرحیاتی
    if optional_missing:
        logger.debug(f"Optional API keys missing in .env file: {', '.join(optional_missing)}")
        missing_keys.extend(optional_missing)
    
    if not missing_keys:
        logger.info("All API keys are properly configured in .env file")
    
    return missing_keys

# بررسی کلیدهای API در زمان راه‌اندازی
check_api_keys() 