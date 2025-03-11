import logging
import json
import threading
import time
import os
from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO, emit
from sqlalchemy import and_, not_, exists
from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, UserHolding
from security.validators import InputValidator, SecurityUtils, ValidationError
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from decimal import Decimal
from dotenv import load_dotenv
from web3 import Web3
import requests
from typing import Dict, Any
from datetime import datetime

# Load environment variables
load_dotenv()

# Logging configuration
logger = get_logger(__file__)
logger.info("Initializing balance module")

# Blueprint definition
balance_bp = Blueprint('balance', __name__)

# SocketIO definition
socketio = None

# Dictionary to store active WebSocket connections
active_connections = {}

# Dictionary to store last balance state for users
last_balances = {}

# Variables to control services
wallet_monitor_running = False
balance_monitor_running = False
wallet_monitor_thread = None
balance_monitor_thread = None

class BalanceService:
    """Service for managing user balances"""
    
    def __init__(self, session):
        self.session = session
        self.web3_providers = {}
        
    def initialize_web3_providers(self):
        """Initialize Web3 connections for different blockchains"""
        try:
            infura_api_key = os.getenv('INFURA_API_KEY')
            if not infura_api_key:
                logger.error("INFURA_API_KEY not found in environment variables")
                return

            # Initialize providers for each blockchain
            self.web3_providers = {
                # EVM-compatible networks using Infura
                "Ethereum": Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{infura_api_key}")),
                "Polygon": Web3(Web3.HTTPProvider(f"https://polygon-mainnet.infura.io/v3/{infura_api_key}")),
                "Arbitrum": Web3(Web3.HTTPProvider(f"https://arbitrum-mainnet.infura.io/v3/{infura_api_key}")),
                "Avalanche": Web3(Web3.HTTPProvider(f"https://avalanche-mainnet.infura.io/v3/{infura_api_key}")),
                
                # BSC using public node
                "Binance": Web3(Web3.HTTPProvider(os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/'))),
                
                # Non-EVM blockchains
                "Bitcoin": None,  # Using BlockCypher API
                "Tron": None,    # Using TronGrid API
                "Solana": None,  # Using Solana RPC
                "Polkadot": None,# Using Subscan API
                "XRP": None      # Using XRPL API
            }
            
            logger.info(f"Initialized Web3 providers for {len(self.web3_providers)} blockchains")
        except Exception as e:
            logger.error(f"Error initializing Web3 providers: {str(e)}")
            raise

    def get_token_balance(self, address: str, contract_address: str, blockchain_name: str) -> Decimal:
        """Get token balance for an address"""
        try:
            # For non-EVM blockchains
            if blockchain_name == "Tron":
                return self._get_tron_token_balance(address, contract_address)
            elif blockchain_name == "Solana":
                return self._get_solana_token_balance(address, contract_address)
            elif blockchain_name == "Polkadot":
                return self._get_polkadot_token_balance(address, contract_address)
            elif blockchain_name == "XRP":
                return self._get_xrp_token_balance(address, contract_address)
            
            # For EVM-compatible blockchains
            if blockchain_name not in self.web3_providers:
                logger.warning(f"No Web3 provider for blockchain: {blockchain_name}")
                return Decimal('0')
                
            web3 = self.web3_providers[blockchain_name]
            
            # Standard ERC20 ABI
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
            
            contract = web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
            balance = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            decimals = contract.functions.decimals().call()
            
            return Decimal(balance) / Decimal(10 ** decimals)
        except Exception as e:
            logger.error(f"Error getting token balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')

    def get_native_balance(self, address: str, blockchain_name: str) -> Decimal:
        """Get native balance for a blockchain address"""
        try:
            # For non-EVM blockchains
            if blockchain_name == "Bitcoin":
                return self._get_bitcoin_balance(address)
            elif blockchain_name == "Tron":
                return self._get_tron_native_balance(address)
            elif blockchain_name == "Solana":
                return self._get_solana_native_balance(address)
            elif blockchain_name == "Polkadot":
                return self._get_polkadot_native_balance(address)
            elif blockchain_name == "XRP":
                return self._get_xrp_native_balance(address)
            
            # For EVM-compatible blockchains
            if blockchain_name not in self.web3_providers:
                logger.warning(f"No Web3 provider for blockchain: {blockchain_name}")
                return Decimal('0')
                
            web3 = self.web3_providers[blockchain_name]
            balance_wei = web3.eth.get_balance(Web3.to_checksum_address(address))
            return Decimal(balance_wei) / Decimal(10 ** 18)
        except Exception as e:
            logger.error(f"Error getting native balance for {address} on {blockchain_name}: {str(e)}")
            return Decimal('0')

    def _get_bitcoin_balance(self, address: str) -> Decimal:
        """Get Bitcoin balance using BlockCypher API"""
        try:
            api_key = os.getenv('BLOCKCYPHER_API_KEY', '')
            url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
            if api_key:
                url += f"?token={api_key}"
                
            response = requests.get(url)
            data = response.json()
            balance_satoshi = data.get("final_balance", 0)
            return Decimal(balance_satoshi) / Decimal(10 ** 8)
        except Exception as e:
            logger.error(f"Error getting Bitcoin balance: {str(e)}")
            return Decimal('0')

    def _get_tron_native_balance(self, address: str) -> Decimal:
        """Get Tron balance using TronGrid API"""
        try:
            api_key = os.getenv('TRONGRID_API_KEY', '')
            url = f"https://api.trongrid.io/v1/accounts/{address}"
            headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
            
            response = requests.get(url, headers=headers)
            data = response.json()
            balance_sun = int(data.get("data", [{}])[0].get("balance", 0))
            return Decimal(balance_sun) / Decimal(10 ** 6)
        except Exception as e:
            logger.error(f"Error getting Tron balance: {str(e)}")
            return Decimal('0')

    def _get_tron_token_balance(self, address: str, contract_address: str) -> Decimal:
        """Get Tron token balance using TronGrid API"""
        try:
            api_key = os.getenv('TRONGRID_API_KEY', '')
            url = f"https://api.trongrid.io/v1/accounts/{address}/trc20"
            headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
            params = {"contract_address": contract_address}
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            for token in data.get("data", []):
                if token.get("contract_address").lower() == contract_address.lower():
                    balance = int(token.get("balance", 0))
                    decimals = int(token.get("decimals", 18))
                    return Decimal(balance) / Decimal(10 ** decimals)
            
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error getting Tron token balance: {str(e)}")
            return Decimal('0')

    def _get_solana_native_balance(self, address: str) -> Decimal:
        """Get Solana balance using RPC API"""
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
            balance_lamports = int(data.get("result", {}).get("value", 0))
            return Decimal(balance_lamports) / Decimal(10 ** 9)
        except Exception as e:
            logger.error(f"Error getting Solana balance: {str(e)}")
            return Decimal('0')

    def _get_solana_token_balance(self, address: str, token_mint: str) -> Decimal:
        """Get Solana token balance using RPC API"""
        try:
            rpc_url = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
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
            
            for account in data.get("result", {}).get("value", []):
                info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                if info.get("mint") == token_mint:
                    amount = info.get("tokenAmount", {}).get("amount", "0")
                    decimals = info.get("tokenAmount", {}).get("decimals", 0)
                    return Decimal(amount) / Decimal(10 ** decimals)
            
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error getting Solana token balance: {str(e)}")
            return Decimal('0')

    def _get_polkadot_native_balance(self, address: str) -> Decimal:
        """Get Polkadot balance using Subscan API"""
        try:
            api_key = os.getenv('SUBSCAN_API_KEY', '')
            url = "https://polkadot.api.subscan.io/api/scan/account"
            headers = {"X-API-Key": api_key} if api_key else {}
            payload = {"address": address}
            
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            balance_planck = int(data.get("data", {}).get("balance", 0))
            return Decimal(balance_planck) / Decimal(10 ** 10)
        except Exception as e:
            logger.error(f"Error getting Polkadot balance: {str(e)}")
            return Decimal('0')

    def _get_polkadot_token_balance(self, address: str, token_id: str) -> Decimal:
        """Get Polkadot token balance"""
        # Polkadot doesn't have traditional tokens
        logger.warning("Polkadot token balance retrieval not implemented")
        return Decimal('0')

    def _get_xrp_native_balance(self, address: str) -> Decimal:
        """Get XRP balance using XRPL API"""
        try:
            url = os.getenv('XRPL_RPC_URL', 'https://xrplcluster.com/')
            payload = {
                "method": "account_info",
                "params": [{"account": address, "strict": True, "ledger_index": "current"}]
            }
            
            response = requests.post(url, json=payload)
            data = response.json()
            balance_drops = int(data.get("result", {}).get("account_data", {}).get("Balance", 0))
            return Decimal(balance_drops) / Decimal(10 ** 6)
        except Exception as e:
            logger.error(f"Error getting XRP balance: {str(e)}")
            return Decimal('0')

    def _get_xrp_token_balance(self, address: str, token_id: str) -> Decimal:
        """Get XRP token balance using XRPL API"""
        try:
            url = os.getenv('XRPL_RPC_URL', 'https://xrplcluster.com/')
            payload = {
                "method": "account_lines",
                "params": [{"account": address, "ledger_index": "current"}]
            }
            
            response = requests.post(url, json=payload)
            data = response.json()
            
            for line in data.get("result", {}).get("lines", []):
                if line.get("currency") == token_id:
                    return Decimal(line.get("balance", "0"))
            
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error getting XRP token balance: {str(e)}")
            return Decimal('0')

    def update_user_balance(self, user_id: str) -> Dict[str, Any]:
        """Update balance for a specific user"""
        try:
            # Check if user exists
            user = self.session.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.warning(f"User not found: {user_id}")
                return {'success': False, 'error_type': 'not_found', 'message': 'User not found'}

            # Find all user wallets
            wallets = self.session.query(Wallets).filter(Wallets.UserID == user_id).all()
            if not wallets:
                logger.warning(f"No wallets found for user: {user_id}")
                return {'success': False, 'error_type': 'not_found', 'message': 'No wallets found for user'}

            logger.info(f"Found {len(wallets)} wallets for user {user_id}")

            # Initialize Web3 connections
            self.initialize_web3_providers()

            # Get all currencies and blockchains
            currencies = self.session.query(Currencies).all()
            currency_dict = {c.CurrencyID: c for c in currencies}
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

                    # Check native currency balance
                    native_currency = next((c for c in currencies 
                                         if c.BlockchainID == blockchain.BlockchainID and not c.IsToken), None)
                    
                    if native_currency:
                        balance = self.get_native_balance(address.PublicAddress, blockchain.BlockchainName)
                        if balance > 0:
                            logger.info(f"Found native balance {balance} for {blockchain.BlockchainName}")
                            holdings[native_currency.CurrencyID] = holdings.get(native_currency.CurrencyID, 0) + balance

                    # Check token balances
                    for currency in currencies:
                        if (currency.BlockchainID == blockchain.BlockchainID and 
                            currency.IsToken and currency.SmartContractAddress):
                            balance = self.get_token_balance(
                                address.PublicAddress,
                                currency.SmartContractAddress,
                                blockchain.BlockchainName
                            )
                            if balance > 0:
                                logger.info(f"Found token balance {balance} for {currency.CurrencyName}")
                                holdings[currency.CurrencyID] = holdings.get(currency.CurrencyID, 0) + balance

            logger.info(f"Found {len(holdings)} holdings for user {user_id}")

            # Update database
            deleted = self.session.query(UserHolding).filter(UserHolding.UserID == user_id).delete()
            logger.info(f"Deleted {deleted} previous holdings for user {user_id}")

            # Store new balances
            tokens_dict = {}
            for currency_id, balance in holdings.items():
                if balance > 0:
                    new_holding = UserHolding(
                        UserID=user_id,
                        CurrencyID=currency_id,
                        Balance=balance,
                        Tokens=f"{currency_id} : {balance}"
                    )
                    self.session.add(new_holding)
                    logger.info(f"Added new holding for currency {currency_id} with balance {balance}")

                    currency = currency_dict.get(currency_id)
                    if currency:
                        blockchain = blockchain_dict.get(currency.BlockchainID)
                        tokens_dict[currency_id] = {
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

def initialize_socketio(app):
    """Initialize SocketIO with Flask application"""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect():
        client_id = request.sid
        logger.info(f"New WebSocket connection: {client_id}")
        
    @socketio.on('subscribe')
    def handle_subscribe(data):
        client_id = request.sid
        user_id = data.get('user_id')
        
        if not user_id:
            emit('error', {'message': 'User ID is required'})
            return
            
        if user_id not in active_connections:
            active_connections[user_id] = []
        active_connections[user_id].append(client_id)
        
        logger.info(f"Client {client_id} subscribed to updates for user {user_id}")
        
        # Send initial balance
        session = SessionLocal()
        try:
            balance_service = BalanceService(session)
            current_balance = balance_service.update_user_balance(user_id)
            emit('balance_update', current_balance)
        finally:
            session.close()
        
    @socketio.on('disconnect')
    def handle_disconnect():
        client_id = request.sid
        for user_id, clients in active_connections.items():
            if client_id in clients:
                clients.remove(client_id)
                logger.info(f"Client {client_id} disconnected from user {user_id}")
                if not clients:
                    del active_connections[user_id]
                break

def run_wallet_monitor():
    """Monitor for new wallets and add them to UserHolding"""
    logger.info("Starting wallet monitor service")
    while wallet_monitor_running:
        try:
            session = SessionLocal()
            try:
                # Get all wallets that don't have holdings
                wallets = (
                    session.query(Wallets)
                    .outerjoin(UserHolding, Wallets.UserID == UserHolding.UserID)
                    .filter(UserHolding.HoldingID.is_(None))
                    .all()
                )
                
                for wallet in wallets:
                    # Get active currencies (those that have been used in transactions)
                    active_currencies = (
                        session.query(Currencies)
                        .join(Address, Address.BlockchainID == Currencies.BlockchainID)
                        .join(Wallets, Wallets.WalletID == Address.WalletID)
                        .filter(Wallets.UserID == wallet.UserID)
                        .distinct()
                        .all()
                    )
                    
                    if not active_currencies:
                        # If no active currencies, get main cryptocurrencies
                        active_currencies = (
                            session.query(Currencies)
                            .filter(Currencies.IsToken == False)  # Only native currencies
                            .all()
                        )
                    
                    # Add holdings for active currencies
                    tokens_data = []
                    for currency in active_currencies:
                        blockchain = session.query(Blockchains).filter(
                            Blockchains.BlockchainID == currency.BlockchainID
                        ).first()
                        
                        if blockchain:
                            tokens_data.append(f"{currency.Symbol} : 0\nBlockchain : {blockchain.BlockchainName}")
                    
                    if tokens_data:
                        # Create one holding record with active tokens
                        new_holding = UserHolding(
                            UserID=wallet.UserID,
                            Balance=0,
                            Tokens="\n".join(tokens_data)
                        )
                        session.add(new_holding)
                        session.commit()
                        logger.info(f"Added holdings for wallet {wallet.WalletID}")
                
            except Exception as e:
                logger.error(f"Error in wallet monitor: {str(e)}")
                session.rollback()
            finally:
                session.close()
                
            # Wait before next check
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Critical error in wallet monitor: {str(e)}")
            time.sleep(5)  # Wait before retry on error

def run_balance_monitor():
    """Monitor and update balances for all users"""
    logger.info("Starting balance monitor service")
    while balance_monitor_running:
        try:
            session = SessionLocal()
            try:
                # Initialize balance service
                balance_service = BalanceService(session)
                balance_service.initialize_web3_providers()
                
                # Get all users
                users = session.query(Users).all()
                logger.info(f"Found {len(users)} users to check balances")
                
                for user in users:
                    try:
                        # Update user balance
                        result = balance_service.update_user_balance(user.UserID)
                        
                        if result['success']:
                            logger.info(f"Successfully updated balance for user {user.UserID}")
                            
                            # Emit update via WebSocket if user is connected
                            if user.UserID in active_connections:
                                socketio.emit('balance_update', result, room=user.UserID)
                                logger.info(f"Emitted balance update for user {user.UserID}")
                        else:
                            logger.warning(f"Failed to update balance for user {user.UserID}: {result.get('message', 'Unknown error')}")
                    except Exception as e:
                        logger.error(f"Error updating balance for user {user.UserID}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"Error in balance monitor: {str(e)}")
            finally:
                session.close()
                
            # Wait before next check
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Critical error in balance monitor: {str(e)}")
            time.sleep(5)  # Wait before retry on error

def init_balance_service():
    """Initialize balance monitoring services"""
    global wallet_monitor_running, balance_monitor_running
    global wallet_monitor_thread, balance_monitor_thread
    
    # Start wallet monitor service
    if not wallet_monitor_running:
        wallet_monitor_running = True
        wallet_monitor_thread = threading.Thread(target=run_wallet_monitor)
        wallet_monitor_thread.daemon = True
        wallet_monitor_thread.start()
        logger.info("Wallet monitor service initialized")
    
    # Start balance monitor service
    if not balance_monitor_running:
        balance_monitor_running = True
        balance_monitor_thread = threading.Thread(target=run_balance_monitor)
        balance_monitor_thread.daemon = True
        balance_monitor_thread.start()
        logger.info("Balance monitor service initialized")

@balance_bp.route('/balance', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_balance():
    """Get all user balances and monitor for changes"""
    global wallet_monitor_running, balance_monitor_running
    
    try:
        # Start services if not running
        if not wallet_monitor_running:
            wallet_monitor_running = True
            wallet_monitor_thread = threading.Thread(target=run_wallet_monitor)
            wallet_monitor_thread.daemon = True
            wallet_monitor_thread.start()
            logger.info("Wallet monitor service started")
        
        if not balance_monitor_running:
            balance_monitor_running = True
            balance_monitor_thread = threading.Thread(target=run_balance_monitor)
            balance_monitor_thread.daemon = True
            balance_monitor_thread.start()
            logger.info("Balance monitor service started")
        
        session = SessionLocal()
        try:
            # Get all holdings
            holdings = session.query(UserHolding).all()
            
            # Format response
            result = {}
            for holding in holdings:
                if holding.UserID not in result:
                    result[holding.UserID] = {
                        "Tokens": {},
                        "success": True
                    }
                
                # Parse tokens
                tokens_lines = holding.Tokens.split('\n')
                i = 0
                while i < len(tokens_lines):
                    if i + 1 < len(tokens_lines):
                        token_line = tokens_lines[i]
                        blockchain_line = tokens_lines[i + 1]
                        
                        if ':' in token_line and ':' in blockchain_line:
                            symbol = token_line.split(':')[0].strip()
                            balance = token_line.split(':')[1].strip()
                            blockchain = blockchain_line.split(':')[1].strip()
                            
                            # Only include tokens with positive balance
                            if Decimal(balance) > 0:
                                result[holding.UserID]["Tokens"][symbol] = {
                                    "balance": balance,
                                    "blockchain": blockchain
                                }
                    i += 2
            
            # Remove users with no tokens
            result = {user_id: data for user_id, data in result.items() if data["Tokens"]}
            
            # If no results, return empty success response
            if not result:
                return jsonify({
                    "Tokens": {},
                    "success": True
                })
            
            # Return all user balances
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Database error in get_balance: {str(e)}")
            return jsonify({
                'error_type': 'database_error',
                'message': 'Error retrieving balances',
                'success': False
            }), 500
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Service error in get_balance: {str(e)}")
        return jsonify({
            'error_type': 'service_error',
            'message': 'Error in balance service',
            'success': False
        }), 500
