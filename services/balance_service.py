from sqlalchemy.orm import Session
from database import Users, Wallets, Address, Blockchains, Currencies, UserHolding, Transfers
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging
import requests
from web3 import Web3
from utils.logging_config import get_logger
from config.api_config import Web3Manager, ERC20_ABI, EXTERNAL_APIS
from sqlalchemy import func
from datetime import datetime
import concurrent.futures

# Configure logging
logger = get_logger(__file__)

class BalanceService:
    """User balance management service"""
    
    def __init__(self, session: Session):
        self.session = session
        self.web3_providers = {}
        self.erc20_abi = ERC20_ABI
        self.api_keys = self._load_api_keys_from_config()
        
    def _load_api_keys_from_config(self):
        """Load API keys from api_config.py instead of .env"""
        api_keys = {}
        
        # Extract API keys directly from EXTERNAL_APIS dictionary
        for blockchain, config in EXTERNAL_APIS.items():
            if isinstance(config, dict) and "key_env" in config:
                key_name = config["key_env"]
                # Check if the API key is directly in EXTERNAL_APIS
                if key_name in EXTERNAL_APIS:
                    api_keys[key_name] = EXTERNAL_APIS[key_name]
                    
        # Add any direct API keys that might be in EXTERNAL_APIS
        for key_name, value in EXTERNAL_APIS.items():
            if key_name.endswith("_API_KEY") and isinstance(value, str):
                api_keys[key_name] = value
                
        logger.info(f"Loaded {len(api_keys)} API keys from config")
        return api_keys
        
    def initialize_web3_providers(self):
        """Initialize Web3 connections for different blockchains"""
        try:
            logger.info(f"Starting Web3 provider initialization for all blockchains")
            
            # دریافت ارائه‌دهندگان Web3 از Web3Manager
            web3_providers = Web3Manager.get_web3_providers()
            logger.info(f"Received Web3 providers from Web3Manager: {list(web3_providers.keys())}")
            
            # اطمینان از اضافه کردن نام‌های متنوع برای هر بلاکچین
            if 'ethereum' in web3_providers:
                web3_providers['eth'] = web3_providers['ethereum']
                logger.debug(f"Added alias 'eth' for ethereum provider")
                
            if 'binance smart chain' in web3_providers:
                web3_providers['bsc'] = web3_providers['binance smart chain']
                web3_providers['bnb'] = web3_providers['binance smart chain']
                logger.debug(f"Added aliases 'bsc' and 'bnb' for binance smart chain provider")
                
            if 'polygon' in web3_providers:
                web3_providers['matic'] = web3_providers['polygon']
                logger.debug(f"Added alias 'matic' for polygon provider")
                
            if 'avalanche' in web3_providers:
                web3_providers['avax'] = web3_providers['avalanche']
                logger.debug(f"Added alias 'avax' for avalanche provider")
                
            if 'arbitrum' in web3_providers:
                web3_providers['arb'] = web3_providers['arbitrum']
                logger.debug(f"Added alias 'arb' for arbitrum provider")
            
            self.web3_providers = web3_providers
            logger.info(f"Initialized Web3 providers for {len(set(web3_providers.values()))} unique blockchains: {list(set(web3_providers.keys()))}")
        except Exception as e:
            logger.error(f"Error initializing Web3 providers: {str(e)}", exc_info=True)
            raise
    
    def get_token_balance(self, address: str, contract_address: str, blockchain_name: str) -> Decimal:
        """Get token balance for an address"""
        try:
            # نرمال‌سازی نام بلاکچین
            original_blockchain_name = blockchain_name
            blockchain_name = blockchain_name.lower().strip()
            
            logger.info(f"Getting token balance for address {address} on blockchain {original_blockchain_name} (normalized to {blockchain_name})")
            
            # Skip if address format doesn't match the blockchain
            if not self._is_valid_address_for_blockchain(address, blockchain_name):
                logger.warning(f"Skipping token balance check for {address} on {original_blockchain_name} - invalid address format")
                return Decimal('0')
            
            # نگاشت نام‌های مختلف به نام‌های استاندارد
            blockchain_mapping = {
                'ethereum': 'ethereum',
                'eth': 'ethereum',
                'binance smart chain': 'binance smart chain',
                'bsc': 'binance smart chain',
                'bnb': 'binance smart chain',
                'polygon': 'polygon',
                'matic': 'polygon',
                'avalanche': 'avalanche',
                'avax': 'avalanche',
                'arbitrum': 'arbitrum',
                'arb': 'arbitrum',
                'tron': 'tron',
                'trx': 'tron',
                'solana': 'solana',
                'sol': 'solana',
                'polkadot': 'polkadot',
                'dot': 'polkadot',
                'xrp': 'xrp',
                'ripple': 'xrp'
            }
            
            # استاندارد‌سازی نام بلاکچین
            standardized_name = blockchain_mapping.get(blockchain_name, blockchain_name)
            logger.debug(f"Standardized blockchain name: {blockchain_name} -> {standardized_name}")
            
            # پردازش بر اساس نوع بلاکچین
            if standardized_name in ['ethereum', 'binance smart chain', 'polygon', 'avalanche', 'arbitrum']:
                if not Web3.is_address(address):
                    logger.warning(f"Invalid EVM address format: {address}")
                    return Decimal('0')
                
                # Get the appropriate Web3 provider
                # اول با نام استاندارد تلاش می‌کنیم
                w3 = self.web3_providers.get(standardized_name)
                logger.debug(f"Checking web3 provider for {standardized_name}: {'Found' if w3 else 'Not found'}")
                
                # اگر پیدا نشد، با نام‌های متفاوت آزمایش می‌کنیم
                if not w3:
                    logger.debug(f"Web3 provider not found with standardized name, trying alternative names")
                    for key, value in blockchain_mapping.items():
                        if value == standardized_name and key in self.web3_providers:
                            w3 = self.web3_providers[key]
                            logger.debug(f"Found Web3 provider using alternative name: {key}")
                            break
                
                if not w3:
                    logger.error(f"No Web3 provider for {original_blockchain_name} (standardized as {standardized_name})")
                    logger.debug(f"Available Web3 providers: {list(self.web3_providers.keys())}")
                    return Decimal('0')

                try:
                    # Get token contract
                    logger.debug(f"Creating token contract instance for {contract_address}")
                    token_contract = w3.eth.contract(
                        address=Web3.to_checksum_address(contract_address),
                        abi=self.erc20_abi
                    )

                    # Get balance
                    logger.debug(f"Calling balanceOf for address {address}")
                    balance = token_contract.functions.balanceOf(
                        Web3.to_checksum_address(address)
                    ).call()

                    # Get decimals
                    try:
                        logger.debug(f"Getting token decimals")
                        decimals = token_contract.functions.decimals().call()
                    except Exception as dec_error:
                        logger.warning(f"Error getting token decimals, using default 18: {str(dec_error)}")
                        decimals = 18  # Default decimals
                    
                    # Convert to proper decimal value
                    token_balance = Decimal(balance) / Decimal(10 ** decimals)
                    logger.info(f"Token balance for {address} on {original_blockchain_name}: {token_balance} (raw: {balance}, decimals: {decimals})")
                    return token_balance
                except Exception as e:
                    logger.error(f"Error getting EVM token balance on {original_blockchain_name}: {str(e)}", exc_info=True)
                    return Decimal('0')

            elif standardized_name == 'tron':
                return self.get_tron_token_balance(address, contract_address)
            elif standardized_name == 'solana':
                return self.get_solana_token_balance(address, contract_address)
            elif standardized_name == 'polkadot':
                return self.get_polkadot_token_balance(address, contract_address)
            elif standardized_name == 'xrp':
                return self.get_xrp_token_balance(address, contract_address)
            else:
                logger.warning(f"Unsupported blockchain for token balance: {original_blockchain_name}")
                return Decimal('0')

        except Exception as e:
            logger.error(f"Error getting token balance for {address} on {blockchain_name}: {str(e)}", exc_info=True)
            return Decimal('0')
    
    def _is_valid_address_for_blockchain(self, address: str, blockchain_name: str) -> bool:
        """Validate if address format matches the blockchain type"""
        try:
            # نرمال‌سازی نام بلاکچین با حروف کوچک و حذف فاصله‌های اضافی
            blockchain_name = blockchain_name.lower().strip()
            logger.debug(f"Validating address format for blockchain: {blockchain_name}")
            
            # EVM-compatible chains (Ethereum, BSC, Polygon, etc.)
            if blockchain_name in ['ethereum', 'binance smart chain', 'polygon', 'avalanche', 'arbitrum', 'bnb', 'matic', 'avax', 'arb']:
                is_valid = Web3.is_address(address)
                logger.debug(f"EVM address validation for {blockchain_name}: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # Bitcoin addresses start with 1, 3, or bc1
            elif blockchain_name == 'bitcoin' or blockchain_name == 'btc':
                is_valid = address.startswith(('1', '3', 'bc1'))
                logger.debug(f"Bitcoin address validation: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # XRP addresses start with r
            elif blockchain_name == 'xrp' or blockchain_name == 'ripple':
                is_valid = address.startswith('r')
                logger.debug(f"XRP address validation: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # Solana addresses are 32-44 characters long base58 strings
            elif blockchain_name == 'solana' or blockchain_name == 'sol':
                is_valid = len(address) >= 32 and len(address) <= 44
                logger.debug(f"Solana address validation: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # Tron addresses start with T
            elif blockchain_name == 'tron' or blockchain_name == 'trx':
                is_valid = address.startswith('T')
                logger.debug(f"Tron address validation: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # Polkadot addresses are 47-48 characters long
            elif blockchain_name == 'polkadot' or blockchain_name == 'dot':
                is_valid = len(address) in [47, 48]
                logger.debug(f"Polkadot address validation: {address} is {'valid' if is_valid else 'invalid'}")
                return is_valid
            
            # Default case
            else:
                logger.warning(f"No address validation rule for blockchain: {blockchain_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error validating address format: {str(e)}", exc_info=True)
            return False
    
    def get_native_balance(self, address: str, blockchain_name: str) -> Decimal:
        """Get native balance for a blockchain address"""
        try:
            # نرمال‌سازی نام بلاکچین
            original_blockchain_name = blockchain_name
            blockchain_name = blockchain_name.lower().strip()
            
            logger.info(f"Getting native balance for address {address} on blockchain {original_blockchain_name} (normalized to {blockchain_name})")
            
            # First, validate the address for the given blockchain
            if not self._is_valid_address_for_blockchain(address, blockchain_name):
                logger.warning(f"Address {address} is not valid for blockchain {original_blockchain_name}")
                return Decimal('0')
            
            # برای بلاکچین‌های غیر-EVM از متدهای خاص استفاده می‌کنیم
            if blockchain_name in ['bitcoin', 'btc']:
                return self.get_bitcoin_balance(address)
            elif blockchain_name in ['tron', 'trx']:
                return self.get_tron_native_balance(address)
            elif blockchain_name in ['solana', 'sol']:
                return self.get_solana_native_balance(address)
            elif blockchain_name in ['polkadot', 'dot']:
                return self.get_polkadot_native_balance(address)
            elif blockchain_name in ['xrp', 'ripple']:
                return self.get_xrp_native_balance(address)
            
            # نگاشت نام‌های مختلف به نام‌های استاندارد برای بلاکچین‌های EVM
            evm_chain_mapping = {
                'ethereum': 'ethereum',
                'eth': 'ethereum',
                'binance smart chain': 'binance smart chain',
                'bsc': 'binance smart chain',
                'bnb': 'binance smart chain',
                'polygon': 'polygon',
                'matic': 'polygon',
                'avalanche': 'avalanche',
                'avax': 'avalanche',
                'arbitrum': 'arbitrum',
                'arb': 'arbitrum'
            }
            
            # تبدیل نام بلاکچین به فرمت استاندارد برای جستجو در web3_providers
            standardized_name = evm_chain_mapping.get(blockchain_name, blockchain_name)
            logger.debug(f"Standardized blockchain name for native balance: {blockchain_name} -> {standardized_name}")
            
            # برای بلاکچین‌های سازگار با EVM
            if standardized_name not in self.web3_providers:
                logger.debug(f"Web3 provider not found with standardized name '{standardized_name}', trying alternative names")
                # تلاش برای اتصال به نود با نام متفاوت
                for key, provider in self.web3_providers.items():
                    if key in evm_chain_mapping and evm_chain_mapping[key] == standardized_name:
                        standardized_name = key
                        logger.debug(f"Found Web3 provider using alternative name: {key}")
                        break
                
                if standardized_name not in self.web3_providers:
                    logger.error(f"No Web3 provider for blockchain: {original_blockchain_name} (standardized as {standardized_name})")
                    logger.debug(f"Available Web3 providers: {list(self.web3_providers.keys())}")
                    return Decimal('0')
            
            web3 = self.web3_providers[standardized_name]
            logger.debug(f"Using Web3 provider for {standardized_name}")
            
            # Double-check that the address is a valid EVM address
            if not web3.is_address(address):
                logger.warning(f"Invalid EVM address format for {address} on {original_blockchain_name}")
                return Decimal('0')
                
            try:
                # Convert address to checksum format
                checksum_address = Web3.to_checksum_address(address)
                logger.debug(f"Converted to checksum address: {checksum_address}")
                
                # Get balance
                logger.debug(f"Calling get_balance for address {checksum_address}")
                balance_wei = web3.eth.get_balance(checksum_address)
                
                # Convert to ETH (or native currency similar to ETH)
                balance = Decimal(balance_wei) / Decimal(10 ** 18)
                logger.info(f"Native balance for {address} on {original_blockchain_name}: {balance} (raw: {balance_wei})")
                
                return balance
            except ValueError as ve:
                logger.warning(f"Invalid hex address format: {str(ve)}")
                return Decimal('0')
        except Exception as e:
            logger.error(f"Error getting native balance for {address} on {blockchain_name}: {str(e)}", exc_info=True)
            return Decimal('0')
    
    def get_bitcoin_balance(self, address: str) -> Decimal:
        """Get Bitcoin balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Bitcoin"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            url = api_config["url"].format(address=address)
            
            if api_key:
                url += f"?token={api_key}"
                
            response = requests.get(url)
            data = response.json()
            
            # Convert from satoshi to Bitcoin
            balance_satoshi = data.get("final_balance", 0)
            balance = Decimal(balance_satoshi) / Decimal(10 ** 8)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Bitcoin balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_tron_native_balance(self, address: str) -> Decimal:
        """Get Tron (TRX) balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Tron"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            url = api_config["url"].format(address=address)
            
            headers = {}
            if api_key:
                headers["TRON-PRO-API-KEY"] = api_key
                
            response = requests.get(url, headers=headers)
            data = response.json()
            
            # Get TRX balance
            balance_sun = 0
            if data.get("success", False) and data.get("data", []):
                balance_sun = int(data["data"][0].get("balance", 0))
            
            # Convert from sun to TRX (1 TRX = 1,000,000 sun)
            balance = Decimal(balance_sun) / Decimal(10 ** 6)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Tron balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_tron_token_balance(self, address: str, contract_address: str) -> Decimal:
        """Get Tron token (TRC20) balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Tron"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            url = api_config["token_url"].format(address=address)
            params = {"contract_address": contract_address}
            
            headers = {}
            if api_key:
                headers["TRON-PRO-API-KEY"] = api_key
                
            response = requests.get(url, params=params, headers=headers)
            data = response.json()
            
            # Get token balance
            balance_raw = 0
            decimals = 18  # Default decimals
            
            if data.get("success", False) and data.get("data", []):
                for token in data["data"]:
                    if token.get("contract_address", "").lower() == contract_address.lower():
                        balance_raw = int(token.get("balance", 0))
                        decimals = int(token.get("decimals", 18))
                        break
            
            # Convert to actual value
            balance = Decimal(balance_raw) / Decimal(10 ** decimals)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Tron token balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_solana_native_balance(self, address: str) -> Decimal:
        """Get Solana (SOL) balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Solana"]
            rpc_url = api_config["url"]
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            
            response = requests.post(rpc_url, json=payload)
            data = response.json()
            
            # Get SOL balance (in lamports)
            balance_lamports = 0
            if "result" in data and "value" in data["result"]:
                balance_lamports = int(data["result"]["value"])
            
            # Convert from lamports to SOL (1 SOL = 1,000,000,000 lamports)
            balance = Decimal(balance_lamports) / Decimal(10 ** 9)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Solana balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_solana_token_balance(self, address: str, token_mint: str) -> Decimal:
        """Get Solana token (SPL) balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Solana"]
            rpc_url = api_config["url"]
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"mint": token_mint},
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = requests.post(rpc_url, json=payload)
            data = response.json()
            
            # Get token balance
            balance_raw = 0
            decimals = 9  # Default decimals for SPL tokens
            
            if "result" in data and "value" in data["result"]:
                for account in data["result"]["value"]:
                    info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    if info.get("mint") == token_mint:
                        balance_raw = int(info.get("tokenAmount", {}).get("amount", 0))
                        decimals = int(info.get("tokenAmount", {}).get("decimals", 9))
                        break
            
            # Convert to actual value
            balance = Decimal(balance_raw) / Decimal(10 ** decimals)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Solana token balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_polkadot_native_balance(self, address: str) -> Decimal:
        """Get Polkadot (DOT) balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Polkadot"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            url = api_config["url"]
            
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
                
            payload = {"address": address}
            
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            # Get DOT balance
            balance_planck = 0
            if data.get("code") == 0 and "data" in data:
                balance_planck = int(data["data"].get("balance", 0))
            
            # Convert from Planck to DOT (1 DOT = 10^10 Planck)
            balance = Decimal(balance_planck) / Decimal(10 ** 10)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Polkadot balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_polkadot_token_balance(self, address: str, asset_id: str) -> Decimal:
        """Get Polkadot token balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Polkadot"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            url = api_config["token_url"]
            
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-API-Key"] = api_key
                
            payload = {
                "address": address,
                "asset_id": asset_id
            }
            
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            # Get token balance
            balance_raw = 0
            decimals = 12  # Default decimals for Polkadot tokens
            
            if data.get("code") == 0 and "data" in data:
                balance_raw = int(data["data"].get("balance", 0))
                decimals = int(data["data"].get("decimals", 12))
            
            # Convert to actual value
            balance = Decimal(balance_raw) / Decimal(10 ** decimals)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Polkadot token balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_xrp_native_balance(self, address: str) -> Decimal:
        """Get XRP balance for an address"""
        try:
            api_config = EXTERNAL_APIS["XRP"]
            url = api_config["url"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            
            payload = {
                "method": "account_info",
                "params": [
                    {
                        "account": address,
                        "strict": True,
                        "ledger_index": "current"
                    }
                ]
            }
            
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key
                
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            # Get XRP balance
            balance_drops = 0
            if "result" in data and "account_data" in data["result"]:
                balance_drops = int(data["result"]["account_data"].get("Balance", 0))
            
            # Convert from drops to XRP (1 XRP = 1,000,000 drops)
            balance = Decimal(balance_drops) / Decimal(10 ** 6)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting XRP balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_xrp_token_balance(self, address: str, token_id: str) -> Decimal:
        """Get XRP token balance for an address"""
        try:
            api_config = EXTERNAL_APIS["XRP"]
            url = api_config["url"]
            api_key = self.api_keys.get(api_config["key_env"], '')
            
            payload = {
                "method": "account_lines",
                "params": [{
                    "account": address,
                    "ledger_index": "current"
                }]
            }
            
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key
                
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            # Get token balance
            balance = Decimal('0')
            
            if "result" in data and "lines" in data["result"]:
                for line in data["result"]["lines"]:
                    if line.get("currency") == token_id:
                        balance = Decimal(line.get("balance", "0"))
                        break
            
            return balance
        except Exception as e:
            logger.error(f"Error getting XRP token balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_user_balance(self, user_id: str) -> Dict[str, Any]:
        """Get user balance"""
        try:
            # Check if user exists
            user = self.session.query(Users).filter(Users.UserID == user_id).first()
            
            if not user:
                return {
                    'success': False,
                    'error_type': 'not_found',
                    'message': 'User not found'
                }
                
            # Get user holdings
            holdings = self.session.query(UserHolding).filter(UserHolding.UserID == user_id).all()
            
            # Only load from UserHolding, don't update balances automatically
            if not holdings:
                logger.info(f"No holdings found for user {user_id}")
                return {
                    'UserID': user_id,
                    'Balances': [],
                    'success': True
                }
            
            # Convert to a list of balance items
            balances_list = []
            
            for holding in holdings:
                try:
                    # Skip empty balances
                    if not holding.Balance or holding.Balance <= 0:
                        continue
                    
                    # استفاده مستقیم از فیلدهای موجود به جای تجزیه متن
                    symbol = holding.Symbol
                    balance = holding.Balance
                    blockchain_name = holding.Blockchain
                    
                    # دریافت اطلاعات ارز از رابطه در صورت نیاز
                    currency_name = None
                    if hasattr(holding, 'currency') and holding.currency:
                        currency_name = holding.currency.CurrencyName
                    
                    balance_info = {
                        'balance': str(balance),
                        'symbol': symbol, 
                        'blockchain': blockchain_name,
                        'is_token': holding.IsToken,
                        'currency_name': currency_name
                    }
                    
                    balances_list.append(balance_info)
                    
                except Exception as e:
                    logger.error(f"Error processing holding {holding.HoldingID}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(balances_list)} tokens with balances for user {user_id}")
            
            return {
                'UserID': user_id,
                'Balances': balances_list,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error getting user balance for {user_id}: {str(e)}")
            return {
                'success': False,
                'error_type': 'server_error',
                'message': f'Error retrieving balance data: {str(e)}'
            }
    
    def _update_user_balance(self, user_id: str) -> Dict[str, Any]:
        """Internal method to update user balance from blockchain - only used when importing wallets"""
        try:
            logger.info(f"Starting balance update for user {user_id}")
            
            # Check if user exists
            user = self.session.query(Users).filter(Users.UserID == user_id).first()
            
            if not user:
                logger.warning(f"User not found: {user_id}")
                return {
                    'success': False,
                    'error_type': 'not_found',
                    'message': 'User not found'
                }
                
            # Find all user wallets
            wallets = self.session.query(Wallets).filter(Wallets.UserID == user_id).all()
            
            if not wallets:
                logger.warning(f"No wallets found for user: {user_id}")
                return {
                    'success': False,
                    'error_type': 'not_found',
                    'message': 'No wallets found for user'
                }
            
            logger.info(f"Found {len(wallets)} wallets for user {user_id}")
                
            # Initialize Web3 connections
            logger.info(f"Initializing Web3 providers for blockchain connections")
            self.initialize_web3_providers()
            
            # Get all currencies and supported tokens
            currencies = self.session.query(Currencies).all()
            currency_dict = {c.CurrencyID: c for c in currencies}
            
            # Get all blockchains
            blockchains = self.session.query(Blockchains).all()
            blockchain_dict = {b.BlockchainID: b for b in blockchains}
            
            # Group currencies by blockchain
            blockchain_currencies = {}
            for currency in currencies:
                if currency.BlockchainID not in blockchain_currencies:
                    blockchain_currencies[currency.BlockchainID] = []
                blockchain_currencies[currency.BlockchainID].append(currency)
            
            logger.info(f"Found {len(currencies)} currencies and {len(blockchains)} blockchains")
            
            # Log all blockchains for debugging
            blockchain_names = [b.BlockchainName for b in blockchains]
            logger.debug(f"Available blockchains: {blockchain_names}")
            
            # Store balances
            holdings = {}
            
            # Prepare a list of all address-blockchain pairs for parallel processing
            address_blockchain_pairs = []
            token_check_tasks = []
            
            for wallet in wallets:
                addresses = self.session.query(Address).filter(Address.WalletID == wallet.WalletID).all()
                logger.info(f"Found {len(addresses)} addresses for wallet {wallet.WalletID}")
                
                for address in addresses:
                    blockchain = blockchain_dict.get(address.BlockchainID)
                    
                    if not blockchain:
                        logger.warning(f"Blockchain not found for address {address.PublicAddress}")
                        continue
                    
                    logger.debug(f"Processing address {address.PublicAddress} on blockchain {blockchain.BlockchainName}")
                    
                    # Add to list for native currency checks
                    native_currency = next((c for c in blockchain_currencies.get(address.BlockchainID, []) 
                                          if not c.IsToken), None)
                    
                    if native_currency:
                        address_blockchain_pairs.append({
                            'address': address.PublicAddress,
                            'blockchain_name': blockchain.BlockchainName,
                            'currency_id': native_currency.CurrencyID,
                            'is_token': False
                        })
                        logger.debug(f"Added task to check native balance for {native_currency.Symbol} at {address.PublicAddress}")
                    else:
                        logger.warning(f"No native currency found for blockchain {blockchain.BlockchainName}")
                    
                    # Prepare token check tasks
                    tokens_for_blockchain = 0
                    for currency in blockchain_currencies.get(address.BlockchainID, []):
                        if currency.IsToken and currency.SmartContractAddress:
                            token_check_tasks.append({
                                'address': address.PublicAddress,
                                'contract_address': currency.SmartContractAddress,
                                'blockchain_name': blockchain.BlockchainName,
                                'currency_id': currency.CurrencyID,
                                'is_token': True
                            })
                            tokens_for_blockchain += 1
                            logger.debug(f"Added task to check token balance for {currency.Symbol} at {address.PublicAddress}")
                    
                    logger.debug(f"Added {tokens_for_blockchain} token check tasks for blockchain {blockchain.BlockchainName}")
            
            logger.info(f"Prepared {len(address_blockchain_pairs)} native currency checks and {len(token_check_tasks)} token checks")
            
            # Use ThreadPoolExecutor for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Map function to check native balances
                def check_native_balance(item):
                    logger.debug(f"Checking native balance for {item['address']} on {item['blockchain_name']}")
                    balance = self.get_native_balance(item['address'], item['blockchain_name'])
                    return {'currency_id': item['currency_id'], 'balance': balance}
                
                # Execute all native balance checks in parallel
                future_to_item = {executor.submit(check_native_balance, item): item for item in address_blockchain_pairs}
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_item):
                    try:
                        result = future.result()
                        item = future_to_item[future]
                        if result['balance'] > 0:
                            currency_id = result['currency_id']
                            if currency_id in holdings:
                                holdings[currency_id] += result['balance']
                            else:
                                holdings[currency_id] = result['balance']
                            logger.info(f"Added native balance {result['balance']} for currency {currency_id} on {item['blockchain_name']}")
                        else:
                            logger.debug(f"Zero native balance for {item['address']} on {item['blockchain_name']}")
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error checking native balance for {item['address']} on {item['blockchain_name']}: {str(e)}", exc_info=True)
            
            # Process token balances in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Map function to check token balances
                def check_token_balance(item):
                    logger.debug(f"Checking token balance for {item['address']} on {item['blockchain_name']} (contract: {item['contract_address']})")
                    balance = self.get_token_balance(
                        item['address'], 
                        item['contract_address'], 
                        item['blockchain_name']
                    )
                    return {'currency_id': item['currency_id'], 'balance': balance}
                
                # Execute all token balance checks in parallel
                future_to_item = {executor.submit(check_token_balance, item): item for item in token_check_tasks}
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_item):
                    try:
                        result = future.result()
                        item = future_to_item[future]
                        if result['balance'] > 0:
                            currency_id = result['currency_id']
                            if currency_id in holdings:
                                holdings[currency_id] += result['balance']
                            else:
                                holdings[currency_id] = result['balance']
                            
                            # Get currency symbol for better logging
                            currency = currency_dict.get(currency_id)
                            symbol = currency.Symbol if currency else "Unknown"
                            
                            logger.info(f"Added token balance {result['balance']} for currency {symbol} ({currency_id}) on {item['blockchain_name']}")
                        else:
                            logger.debug(f"Zero token balance for address {item['address']} on {item['blockchain_name']} (contract: {item['contract_address']})")
                    except Exception as e:
                        item = future_to_item[future]
                        logger.error(f"Error checking token balance for {item['address']} on {item['blockchain_name']}: {str(e)}", exc_info=True)
            
            logger.info(f"Found {len(holdings)} holdings with non-zero balances for user {user_id}")
            
            # Delete previous balances
            deleted = self.session.query(UserHolding).filter(UserHolding.UserID == user_id).delete()
            logger.info(f"Deleted {deleted} previous holdings for user {user_id}")
            
            # Store new balances in database
            balances_list = []
            
            for currency_id, balance in holdings.items():
                if balance > 0:
                    # بررسی وجود ارز در دیکشنری
                    currency = currency_dict.get(currency_id)
                    if not currency:
                        logger.warning(f"Currency ID {currency_id} not found in database")
                        continue
                        
                    # بررسی وجود بلاکچین مرتبط با ارز
                    blockchain = blockchain_dict.get(currency.BlockchainID)
                    if not blockchain:
                        logger.warning(f"Blockchain not found for currency {currency.CurrencyName}")
                        blockchain_name = "Unknown"
                    else:
                        blockchain_name = blockchain.BlockchainName
                    
                    # Create new record in UserHolding with all required fields
                    new_holding = UserHolding(
                        UserID=user_id,
                        CurrencyID=currency.CurrencyID,
                        Balance=balance,
                        Symbol=currency.Symbol,
                        Blockchain=blockchain_name,
                        IsToken=currency.IsToken,
                        LastUpdated=datetime.now(),
                        RawData={"original_balance": str(balance)}
                    )
                    
                    self.session.add(new_holding)
                    logger.info(f"Added new holding for currency {currency.Symbol} with balance {balance} on {blockchain_name}")
                    
                    # Add to response list
                    balance_info = {
                        'balance': str(balance),
                        'currency_name': currency.CurrencyName,
                        'symbol': currency.Symbol,
                        'blockchain': blockchain_name,
                        'is_token': currency.IsToken
                    }
                    balances_list.append(balance_info)
            
            self.session.commit()
            logger.info(f"Successfully committed {len(balances_list)} holdings for user {user_id}")
            
            return {
                'UserID': user_id,
                'Balances': balances_list,
                'success': True
            }
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating balance for user {user_id}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error_type': 'server_error',
                'message': f'Error updating balance data: {str(e)}'
            }
    
    def apply_transfer_to_user_holding(self, transfer: Transfers):
        """
        Apply a transfer to update user holdings
        Simplified version for debugging that logs but doesn't make API calls
        
        Args:
            transfer: Transfer object to apply
        """
        try:
            logger.info(f"Applying transfer {transfer.TransferID} to user holdings (simplified version)")
            
            # Get wallet
            wallet = self.session.query(Wallets).filter(Wallets.WalletID == transfer.WalletID).first()
            if not wallet:
                logger.error(f"Wallet {transfer.WalletID} not found for transfer {transfer.TransferID}")
                return
            
            # Log transfer details but don't actually apply changes
            logger.info(f"Would apply transfer: ID={transfer.TransferID}, "
                       f"Direction={transfer.Direction}, "
                       f"Amount={transfer.Amount}, "
                       f"Symbol={transfer.TokenSymbol}, "
                       f"Blockchain={transfer.blockchain.BlockchainName if transfer.blockchain else 'Unknown'}")
            
            logger.info("Transfer application skipped for debugging purposes")
            return
            
            # Original implementation is commented out
            """
            # Get user and address
            user_id = wallet.UserID
            
            # Determine currency details
            blockchain_name = transfer.blockchain.BlockchainName
            token_symbol = transfer.TokenSymbol
            
            # Find currency record
            currency = self.session.query(Currencies).filter(
                Currencies.Symbol == token_symbol,
                Currencies.BlockchainID == transfer.BlockchainID
            ).first()
            
            if not currency:
                logger.warning(f"Currency {token_symbol} on {blockchain_name} not found, creating placeholder")
                currency = Currencies(
                    CurrencyID=f"{token_symbol.lower()}_{blockchain_name.lower().replace(' ', '_')}",
                    Symbol=token_symbol,
                    Name=token_symbol,
                    BlockchainID=transfer.BlockchainID,
                    TokenContract=transfer.TokenContract,
                    IsToken=(transfer.AssetType == 'token'),
                    Decimals=18,  # Default for most tokens
                    CreatedAt=datetime.utcnow(),
                    UpdatedAt=datetime.utcnow()
                )
                self.session.add(currency)
                self.session.commit()
            
            # Find existing holding or create new one
            holding = self.session.query(UserHolding).filter(
                UserHolding.UserID == user_id,
                UserHolding.Symbol == token_symbol,
                UserHolding.Blockchain == blockchain_name
            ).first()
            
            if not holding:
                holding = UserHolding(
                    UserID=user_id,
                    CurrencyID=currency.CurrencyID,
                    Balance=0,
                    Symbol=token_symbol,
                    Blockchain=blockchain_name,
                    IsToken=(transfer.AssetType == 'token'),
                    CreatedAt=datetime.utcnow(),
                    UpdatedAt=datetime.utcnow(),
                    LastUpdated=datetime.utcnow()
                )
                self.session.add(holding)
            
            # Update balance based on transfer direction
            if transfer.Direction == 'inbound' and transfer.IsSuccessful:
                # Increment balance for incoming transfers
                holding.Balance += transfer.Amount
                holding.UpdatedAt = datetime.utcnow()
                holding.LastUpdated = datetime.utcnow()
                logger.info(f"Added {transfer.Amount} {token_symbol} to user {user_id}")
            elif transfer.Direction == 'outbound' and transfer.IsSuccessful:
                # Decrement balance for outgoing transfers
                if holding.Balance >= transfer.Amount:
                    holding.Balance -= transfer.Amount
                    holding.UpdatedAt = datetime.utcnow()
                    holding.LastUpdated = datetime.utcnow()
                    logger.info(f"Subtracted {transfer.Amount} {token_symbol} from user {user_id}")
                else:
                    logger.warning(f"Insufficient balance for user {user_id}: {holding.Balance} {token_symbol} < {transfer.Amount}")
            
            # Commit changes
            self.session.commit()
            logger.info(f"Successfully applied transfer {transfer.TransferID}")
            """
        except Exception as e:
            logger.error(f"Error applying transfer {transfer.TransferID}: {str(e)}")
            # Don't propagate the exception to avoid breaking the caller
    
    def check_balance_changes(self, user_id: str, last_balance: Dict[str, Any]) -> Dict[str, Any]:
        """Check balance changes for a user"""
        try:
            # Get current balance
            current_balance = self.get_user_balance(user_id)
            
            # If balance changed, update
            if current_balance['success'] and last_balance['success']:
                # مقایسه لیست‌های Balances
                current_balances = current_balance.get('Balances', [])
                last_balances = last_balance.get('Balances', [])
                
                # تبدیل به مجموعه‌های قابل مقایسه
                current_set = {(b.get('symbol'), b.get('balance'), b.get('blockchain')) for b in current_balances}
                last_set = {(b.get('symbol'), b.get('balance'), b.get('blockchain')) for b in last_balances}
                
                if current_set != last_set:
                    return current_balance
            
            return last_balance
        except Exception as e:
            logger.error(f"Error checking balance changes for user {user_id}: {str(e)}")
            return last_balance
    
    def get_simple_user_balance(self, user_id: str):
        """
        Simplified version of get_user_balance that doesn't rely on external APIs
        This is used for debugging when external APIs might be causing issues
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user balance information
        """
        logger.info(f"Getting simplified balance for user {user_id} (no external APIs)")
        
        try:
            # Check if user exists
            user = self.session.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                return {
                    "success": False,
                    "error_type": "not_found",
                    "message": "User not found"
                }
                
            # Get user holdings from database
            holdings = self.session.query(UserHolding).filter(UserHolding.UserID == user_id).all()
            
            # Prepare response data
            balances = []
            
            for holding in holdings:
                balances.append({
                    "Symbol": holding.Symbol,
                    "Blockchain": holding.Blockchain,
                    "Balance": str(holding.Balance),
                    "IsToken": holding.IsToken
                })
                
            # If no holdings found, return empty list
            return {
                "UserID": user_id,
                "Balances": balances,
                "success": True,
                "debug_info": "Using simplified balance service (no external APIs)"
            }
            
        except Exception as e:
            logger.error(f"Error getting simple user balance: {str(e)}")
            return {
                "success": False,
                "error_type": "internal_error",
                "message": f"Error getting balance: {str(e)}"
            } 