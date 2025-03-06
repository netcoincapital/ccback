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

# Load environment variables
load_dotenv()

# Logging configuration
logger = get_logger(__file__)

class BalanceService:
    """User balance management service"""
    
    def __init__(self, session: Session):
        self.session = session
        self.web3_providers = {}  # Store Web3 connections for different blockchains
        
    def initialize_web3_providers(self):
        """Initialize Web3 connections for different blockchains"""
        try:
            infura_api_key = os.getenv('INFURA_API_KEY')
            if not infura_api_key:
                logger.error("INFURA_API_KEY not found in environment variables")
                return

            # Initialize providers for each blockchain
            self.web3_providers = {
                "Ethereum": Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{infura_api_key}")),
                "Polygon": Web3(Web3.HTTPProvider(f"https://polygon-mainnet.infura.io/v3/{infura_api_key}")),
                "Arbitrum": Web3(Web3.HTTPProvider(f"https://arbitrum-mainnet.infura.io/v3/{infura_api_key}")),
                "Avalanche": Web3(Web3.HTTPProvider("https://api.avax.network/ext/bc/C/rpc")),
                "Binance": Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/")),
                "Tron": None,  # Tron doesn't use Web3
                "Solana": None,  # Solana doesn't use Web3
                "Polkadot": None,  # Polkadot doesn't use Web3
                "XRP": None  # XRP doesn't use Web3
            }
            
            logger.info(f"Initialized Web3 providers for {len(self.web3_providers)} blockchains")
        except Exception as e:
            logger.error(f"Error initializing Web3 providers: {str(e)}")
            raise
    
    def get_token_balance(self, address: str, contract_address: str, blockchain_name: str) -> Decimal:
        """Get token balance for an address"""
        try:
            # For non-EVM blockchains, use specific methods
            if blockchain_name == "Tron":
                return self.get_tron_token_balance(address, contract_address)
            elif blockchain_name == "Solana":
                return self.get_solana_token_balance(address, contract_address)
            elif blockchain_name == "Polkadot":
                return self.get_polkadot_token_balance(address, contract_address)
            elif blockchain_name == "XRP":
                return self.get_xrp_token_balance(address, contract_address)
            
            # For EVM-compatible blockchains
            if blockchain_name not in self.web3_providers:
                logger.warning(f"No Web3 provider for blockchain: {blockchain_name}")
                return Decimal('0')
                
            web3 = self.web3_providers[blockchain_name]
            
            # Standard ABI for balanceOf functions in ERC20 tokens
            abi = [
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
                }
            ]
            
            # Create contract object
            contract = web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
            
            # Get balance and decimals
            balance = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            decimals = contract.functions.decimals().call()
            
            # Convert to actual value
            actual_balance = Decimal(balance) / Decimal(10 ** decimals)
            
            return actual_balance
        except Exception as e:
            logger.error(f"Error getting token balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')
    
    def get_native_balance(self, address: str, blockchain_name: str) -> Decimal:
        """Get native balance for a blockchain address"""
        try:
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
            
            # Get balance
            balance_wei = web3.eth.get_balance(Web3.to_checksum_address(address))
            
            # Convert to ETH (or native currency similar to ETH)
            balance = Decimal(balance_wei) / Decimal(10 ** 18)
            
            return balance
        except Exception as e:
            logger.error(f"Error getting native balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')
    
    def get_bitcoin_balance(self, address: str) -> Decimal:
        """Get Bitcoin balance for an address"""
        try:
            # Use blockchain API to get Bitcoin balance
            api_key = os.getenv('BLOCKCYPHER_API_KEY', '')
            url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
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
            api_key = os.getenv('TRONGRID_API_KEY', '')
            url = f"https://api.trongrid.io/v1/accounts/{address}"
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
            api_key = os.getenv('TRONGRID_API_KEY', '')
            url = f"https://api.trongrid.io/v1/accounts/{address}/trc20"
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
            rpc_url = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
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
            rpc_url = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
            
            # First, find the token account
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
            balance = Decimal('0')
            
            if "result" in data and "value" in data["result"]:
                for account in data["result"]["value"]:
                    info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    if info.get("mint") == token_mint:
                        token_amount = info.get("tokenAmount", {})
                        amount = token_amount.get("amount", "0")
                        decimals = token_amount.get("decimals", 0)
                        balance = Decimal(amount) / Decimal(10 ** decimals)
                        break
            
            return balance
        except Exception as e:
            logger.error(f"Error getting Solana token balance for {address}: {str(e)}")
            return Decimal('0')
    
    def get_polkadot_native_balance(self, address: str) -> Decimal:
        """Get Polkadot (DOT) balance for an address"""
        try:
            api_key = os.getenv('POLKADOT_API_KEY', '')
            # Using Subscan API for Polkadot
            url = "https://polkadot.api.subscan.io/api/scan/account"
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
    
    def get_polkadot_token_balance(self, address: str, token_id: str) -> Decimal:
        """Get Polkadot token balance for an address"""
        # Polkadot doesn't have tokens in the same way as Ethereum
        # This is a placeholder for future implementation
        logger.warning(f"Polkadot token balance retrieval not fully implemented for {address}")
        return Decimal('0')
    
    def get_xrp_native_balance(self, address: str) -> Decimal:
        """Get XRP balance for an address"""
        try:
            api_key = os.getenv('RIPPLE_API_KEY', '')
            # Using XRPL API
            url = "https://xrplcluster.com/"
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
            api_key = os.getenv('RIPPLE_API_KEY', '')
            # Using XRPL API
            url = "https://xrplcluster.com/"
            payload = {
                "method": "account_lines",
                "params": [
                    {
                        "account": address,
                        "ledger_index": "current"
                    }
                ]
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
                        balance += Decimal(line.get("balance", "0"))
            
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
                        
                    # Check native currency balance for blockchain
                    native_currency = None
                    for currency in currencies:
                        if currency.BlockchainID == blockchain.BlockchainID and not currency.IsToken:
                            native_currency = currency
                            break
                    
                    if native_currency:
                        # Get native currency balance
                        if blockchain.BlockchainName == "Bitcoin":
                            balance = self.get_bitcoin_balance(address.PublicAddress)
                        else:
                            balance = self.get_native_balance(address.PublicAddress, blockchain.BlockchainName)
                        
                        if balance > 0:
                            logger.info(f"Found native balance {balance} for {blockchain.BlockchainName}")
                            if native_currency.CurrencyID in holdings:
                                holdings[native_currency.CurrencyID] += balance
                            else:
                                holdings[native_currency.CurrencyID] = balance
                    
                    # Check token balances
                    for currency in currencies:
                        if currency.BlockchainID == blockchain.BlockchainID and currency.IsToken and currency.SmartContractAddress:
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
                    tokens_str = f"{currency_id} : {balance}"
                    
                    # Create new record in UserHolding
                    new_holding = UserHolding(
                        UserID=user_id,
                        Balance=balance,
                        Tokens=tokens_str
                    )
                    
                    self.session.add(new_holding)
                    logger.info(f"Added new holding for currency {currency_id} with balance {balance}")
                    
                    # Get currency information for response
                    currency = currency_dict.get(currency_id)
                    if currency:
                        blockchain = blockchain_dict.get(currency.BlockchainID)
                        
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