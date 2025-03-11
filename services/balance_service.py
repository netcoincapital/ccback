from sqlalchemy.orm import Session
from database import Users, Wallets, Address, Blockchains, Currencies, UserHolding
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging
import os
from web3 import Web3
import requests
from utils.logging_config import get_logger
from dotenv import load_dotenv
from config.api_config import Web3Manager, ERC20_ABI, EXTERNAL_APIS

# Load environment variables
load_dotenv()

# Logging configuration
logger = get_logger(__file__)

class BalanceService:
    """User balance management service"""
    
    def __init__(self, session: Session):
        self.session = session
        self.web3_providers = {}
        self.erc20_abi = ERC20_ABI
        
    def initialize_web3_providers(self):
        """Initialize Web3 connections for different blockchains"""
        try:
            self.web3_providers = Web3Manager.get_web3_providers()
            logger.info(f"Initialized Web3 providers for {len(self.web3_providers)} blockchains")
        except Exception as e:
            logger.error(f"Error initializing Web3 providers: {str(e)}")
            raise
    
    def get_token_balance(self, address: str, contract_address: str, blockchain_name: str) -> Decimal:
        """Get token balance for an address"""
        try:
            # Skip if address format doesn't match the blockchain
            if not self._is_valid_address_for_blockchain(address, blockchain_name):
                logger.debug(f"Skipping token balance check for {address} on {blockchain_name} - invalid address format")
                return Decimal('0')

            # Handle different blockchain types
            if blockchain_name.lower() in ['ethereum', 'binance smart chain', 'polygon', 'avalanche', 'arbitrum']:
                if not Web3.is_address(address):
                    logger.debug(f"Invalid EVM address format: {address}")
                    return Decimal('0')
                    
                # Get the appropriate Web3 provider
                w3 = self.web3_providers.get(blockchain_name.lower())
                if not w3:
                    logger.error(f"No Web3 provider for {blockchain_name}")
                    return Decimal('0')

                # Get token contract
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=self.erc20_abi
                )

                # Get balance
                balance = token_contract.functions.balanceOf(
                    Web3.to_checksum_address(address)
                ).call()

                return Decimal(str(balance))

            elif blockchain_name.lower() == 'tron':
                return self._get_tron_token_balance(address, contract_address)
            elif blockchain_name.lower() == 'solana':
                return self._get_solana_token_balance(address, contract_address)
            elif blockchain_name.lower() == 'polkadot':
                return self._get_polkadot_token_balance(address, contract_address)
            elif blockchain_name.lower() == 'xrp':
                return self._get_xrp_token_balance(address, contract_address)
            else:
                logger.warning(f"Unsupported blockchain for token balance: {blockchain_name}")
                return Decimal('0')

        except Exception as e:
            logger.error(f"Error getting token balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')
    
    def _is_valid_address_for_blockchain(self, address: str, blockchain_name: str) -> bool:
        """Validate if address format matches the blockchain type"""
        try:
            blockchain_name = blockchain_name.lower()
            
            # EVM-compatible chains (Ethereum, BSC, Polygon, etc.)
            if blockchain_name in ['ethereum', 'binance smart chain', 'polygon', 'avalanche', 'arbitrum']:
                return Web3.is_address(address)
            
            # Bitcoin addresses start with 1, 3, or bc1
            elif blockchain_name == 'bitcoin':
                return address.startswith(('1', '3', 'bc1'))
            
            # XRP addresses start with r
            elif blockchain_name == 'xrp':
                return address.startswith('r')
            
            # Solana addresses are 32-44 characters long base58 strings
            elif blockchain_name == 'solana':
                return len(address) >= 32 and len(address) <= 44
            
            # Tron addresses start with T
            elif blockchain_name == 'tron':
                return address.startswith('T')
            
            # Polkadot addresses are 47-48 characters long
            elif blockchain_name == 'polkadot':
                return len(address) in [47, 48]
            
            # Default case
            else:
                logger.warning(f"No address validation rule for blockchain: {blockchain_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error validating address format: {str(e)}")
            return False
    
    def get_native_balance(self, address: str, blockchain_name: str) -> Decimal:
        """Get native balance for a blockchain address"""
        try:
            # First, validate the address for the given blockchain
            if not self._is_valid_address_for_blockchain(address, blockchain_name):
                logger.debug(f"Address {address} is not valid for blockchain {blockchain_name}")
                return Decimal('0')
                
            # For non-EVM blockchains, use specific methods
            if blockchain_name == "Bitcoin":
                return self.get_bitcoin_balance(address)
            elif blockchain_name == "Tron":
                return self.get_tron_native_balance(address)
            elif blockchain_name == "Solana":
                return self.get_solana_native_balance(address)
            elif blockchain_name == "Polkadot":
                return self.get_polkadot_native_balance(address)
            elif blockchain_name == "XRP":
                return self.get_xrp_native_balance(address)
            
            # For EVM-compatible blockchains
            if blockchain_name not in self.web3_providers:
                logger.warning(f"No Web3 provider for blockchain: {blockchain_name}")
                return Decimal('0')
                
            web3 = self.web3_providers[blockchain_name]
            
            # Double-check that the address is a valid EVM address
            if not web3.is_address(address):
                logger.debug(f"Invalid EVM address format for {address} on {blockchain_name}")
                return Decimal('0')
                
            try:
                # Convert address to checksum format
                checksum_address = Web3.to_checksum_address(address)
                
                # Get balance
                balance_wei = web3.eth.get_balance(checksum_address)
                
                # Convert to ETH (or native currency similar to ETH)
                balance = Decimal(balance_wei) / Decimal(10 ** 18)
                
                return balance
            except ValueError as ve:
                logger.debug(f"Invalid hex address format: {str(ve)}")
                return Decimal('0')
        except Exception as e:
            logger.error(f"Error getting native balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')
    
    def get_bitcoin_balance(self, address: str) -> Decimal:
        """Get Bitcoin balance for an address"""
        try:
            api_config = EXTERNAL_APIS["Bitcoin"]
            api_key = os.getenv(api_config["key_env"], '')
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
            api_key = os.getenv(api_config["key_env"], '')
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
            api_key = os.getenv(api_config["key_env"], '')
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
            api_key = os.getenv(api_config["key_env"], '')
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
            api_key = os.getenv(api_config["key_env"], '')
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
            api_key = os.getenv(api_config["key_env"], '')
            
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
            api_key = os.getenv(api_config["key_env"], '')
            
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
            
            if not holdings:
                return {
                    'UserID': user_id,
                    'Tokens': {},
                    'success': True
                }
                
            # Convert to dictionary
            tokens_dict = {}
            for holding in holdings:
                if holding.Balance and holding.Balance > 0:
                    # Get currency information
                    currency = self.session.query(Currencies).filter(Currencies.CurrencyID == holding.CurrencyID).first()
                    
                    if currency:
                        # Get blockchain information
                        blockchain = self.session.query(Blockchains).filter(Blockchains.BlockchainID == currency.BlockchainID).first()
                        
                        tokens_dict[holding.CurrencyID] = {
                            'balance': str(holding.Balance),
                            'currency_name': currency.CurrencyName,
                            'symbol': currency.Symbol,
                            'blockchain': blockchain.BlockchainName if blockchain else None,
                            'is_token': currency.IsToken
                        }
            
            return {
                'UserID': user_id,
                'Tokens': tokens_dict,
                'success': True
            }
        except Exception as e:
            logger.error(f"Error getting balance for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error_type': 'server_error',
                'message': 'Error retrieving balance data'
            }
    
    def update_user_balance(self, user_id: str) -> Dict[str, Any]:
        """Update user balance"""
        try:
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
            
            # Store balances
            holdings = {}
            
            # Check wallet addresses
            for wallet in wallets:
                addresses = self.session.query(Address).filter(Address.WalletID == wallet.WalletID).all()
                logger.info(f"Found {len(addresses)} addresses for wallet {wallet.WalletID}")
                
                for address in addresses:
                    blockchain = blockchain_dict.get(address.BlockchainID)
                    
                    if not blockchain:
                        logger.warning(f"Blockchain not found for address {address.PublicAddress}")
                        continue
                        
                    logger.info(f"Processing {blockchain.BlockchainName} address: {address.PublicAddress}")
                    
                    # Get currencies for this blockchain
                    blockchain_specific_currencies = blockchain_currencies.get(blockchain.BlockchainID, [])
                    
                    # Check native currency balance
                    native_currency = next((c for c in blockchain_specific_currencies if not c.IsToken), None)
                    
                    if native_currency:
                        # Get native currency balance
                        balance = self.get_native_balance(address.PublicAddress, blockchain.BlockchainName)
                        
                        if balance > 0:
                            logger.info(f"Found native balance {balance} for {blockchain.BlockchainName}")
                            if native_currency.CurrencyID in holdings:
                                holdings[native_currency.CurrencyID] += balance
                            else:
                                holdings[native_currency.CurrencyID] = balance
                    
                    # Check token balances only for tokens of this blockchain
                    for currency in blockchain_specific_currencies:
                        if currency.IsToken and currency.SmartContractAddress:
                            balance = self.get_token_balance(
                                address.PublicAddress, 
                                currency.SmartContractAddress, 
                                blockchain.BlockchainName
                            )
                            
                            if balance > 0:
                                logger.info(f"Found token balance {balance} for {currency.CurrencyName}")
                                if currency.CurrencyID in holdings:
                                    holdings[currency.CurrencyID] += balance
                                else:
                                    holdings[currency.CurrencyID] = balance
            
            logger.info(f"Found {len(holdings)} holdings for user {user_id}")
            
            # Delete previous balances
            deleted = self.session.query(UserHolding).filter(UserHolding.UserID == user_id).delete()
            logger.info(f"Deleted {deleted} previous holdings for user {user_id}")
            
            # Store new balances in database
            tokens_dict = {}
            for currency_id, balance in holdings.items():
                if balance > 0:
                    # Convert to string for column Tokens
                    currency = currency_dict.get(currency_id)
                    blockchain = blockchain_dict.get(currency.BlockchainID) if currency else None
                    
                    tokens_str = (
                        f"{currency.Symbol if currency else currency_id} : {balance}\n"
                        f"Blockchain : {blockchain.BlockchainName if blockchain else 'Unknown'}"
                    )
                    
                    # Create new record in UserHolding
                    new_holding = UserHolding(
                        UserID=user_id,
                        Balance=balance,
                        Tokens=tokens_str
                    )
                    
                    self.session.add(new_holding)
                    logger.info(f"Added new holding for currency {currency_id} with balance {balance}")
                    
                    # Add to response dictionary
                    if currency:
                        tokens_dict[currency.Symbol] = {
                            'balance': str(balance),
                            'currency_name': currency.CurrencyName,
                            'symbol': currency.Symbol,
                            'blockchain': blockchain.BlockchainName if blockchain else None,
                            'is_token': currency.IsToken
                        }
            
            self.session.commit()
            logger.info(f"Successfully committed {len(tokens_dict)} holdings for user {user_id}")
            
            return {
                'UserID': user_id,
                'Tokens': tokens_dict,
                'success': True
            }
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating balance for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error_type': 'server_error',
                'message': f'Error updating balance data: {str(e)}'
            }
    
    def check_balance_changes(self, user_id: str, last_balance: Dict[str, Any]) -> Dict[str, Any]:
        """Check balance changes for a user"""
        try:
            # Get current balance
            current_balance = self.get_user_balance(user_id)
            
            # If balance changed, update
            if current_balance['success'] and last_balance['success']:
                if current_balance['Tokens'] != last_balance['Tokens']:
                    return current_balance
            
            return last_balance
        except Exception as e:
            logger.error(f"Error checking balance changes for user {user_id}: {str(e)}")
            return last_balance 