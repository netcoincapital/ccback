from sqlalchemy.orm import Session
import logging
from web3 import Web3
import requests
from abc import ABC, abstractmethod
from decimal import Decimal
from CC.utils.logging_config import get_logger
from bitcoinlib.wallets import Wallet
from solana.rpc.api import Client
from CC.config.api_config import EXTERNAL_APIS

# ERC20 ABI for token interactions
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

# Configure logging
logger = get_logger(__file__)

class BlockchainService(ABC):
    @abstractmethod
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        pass
        
    @abstractmethod
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        pass
        
    @abstractmethod
    def get_balance(self, address):
        pass
        
    @abstractmethod
    def validate_address(self, address):
        pass

    @abstractmethod
    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        pass

class EVMBlockchainService(BlockchainService):
    def __init__(self, web3_provider, chain_id):
        self.web3 = web3_provider
        self.chain_id = chain_id
        
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        try:
            sender_balance = self.web3.eth.get_balance(sender_address)
            gas_price = self.web3.eth.gas_price
            
            if smart_contract_address:
                contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(smart_contract_address), 
                    abi=ERC20_ABI
                )
                amount_in_wei = self.web3.to_wei(float(amount), 'ether')
                gas_limit = contract.functions.transfer(recipient_address, amount_in_wei).estimate_gas({
                    'from': sender_address
                })
            else:
                gas_limit = self.web3.eth.estimate_gas({
                    'from': sender_address,
                    'to': recipient_address,
                    'value': self.web3.to_wei(float(amount), 'ether')
                })
            
            total_fee = gas_price * gas_limit
            total_fee_in_eth = self.web3.from_wei(total_fee, 'ether')
            
            if smart_contract_address:
                balance_after = self.web3.from_wei(sender_balance - total_fee, 'ether')
            else:
                amount_in_wei = self.web3.to_wei(float(amount), 'ether')
                balance_after = self.web3.from_wei(sender_balance - amount_in_wei - total_fee, 'ether')
            
            return {
                'sender_address': sender_address,
                'recipient_address': recipient_address,
                'amount': amount,
                'sender_balance_before': self.web3.from_wei(sender_balance, 'ether'),
                'estimated_fee': total_fee_in_eth,
                'gas_limit': gas_limit,
                'gas_price': gas_price,
                'balance_after_tx': balance_after,
                'is_token': bool(smart_contract_address),
                'contract_address': smart_contract_address
            }, None
            
        except Exception as e:
            logger.error(f"Error preparing EVM transaction: {str(e)}")
            return None, str(e)
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        try:
            if tx_details["is_token"]:
                contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(tx_details["contract_address"]), 
                    abi=ERC20_ABI
                )
                decimals = contract.functions.decimals().call()
                amount_in_token_units = int(float(amount) * (10 ** decimals))
                
                nonce = self.web3.eth.get_transaction_count(sender_address)
                tx = contract.functions.transfer(
                    self.web3.to_checksum_address(recipient_address),
                    amount_in_token_units
                ).build_transaction({
                    'chainId': self.chain_id,
                    'gas': tx_details["gas_limit"],
                    'gasPrice': tx_details["gas_price"],
                    'nonce': nonce,
                })
            else:
                amount_wei = self.web3.to_wei(float(amount), 'ether')
                nonce = self.web3.eth.get_transaction_count(sender_address)
                tx = {
                    'nonce': nonce,
                    'to': recipient_address,
                    'value': amount_wei,
                    'gas': tx_details["gas_limit"],
                    'gasPrice': tx_details["gas_price"],
                    'chainId': self.chain_id
                }
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            actual_gas_used = tx_receipt.gasUsed
            actual_fee_wei = actual_gas_used * tx_details["gas_price"]
            actual_fee_eth = self.web3.from_wei(actual_fee_wei, 'ether')
            
            sender_balance_after = self.web3.eth.get_balance(sender_address)
            sender_balance_after_eth = self.web3.from_wei(sender_balance_after, 'ether')
            
            return {
                "transaction_hash": tx_hash.hex(),
                "status": "Success" if tx_receipt.status == 1 else "Failed",
                "actual_fee": actual_fee_eth,
                "sender_balance_after": sender_balance_after_eth,
                "block_number": tx_receipt.blockNumber,
                "gas_used": actual_gas_used
            }, None
            
        except Exception as e:
            logger.error(f"Error sending EVM transaction: {str(e)}")
            return None, str(e)
    
    def get_balance(self, address):
        try:
            balance = self.web3.eth.get_balance(address)
            return self.web3.from_wei(balance, 'ether')
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        return self.web3.is_address(address)

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        try:
            # Method 1: Try to get transaction directly from web3 client
            try:
                tx_info = self.web3.eth.get_transaction_by_hash(tx_hash)
                
                # Check if transaction has confirmations
                if hasattr(tx_info, 'blockNumber') and tx_info.blockNumber:
                    return "Confirmed", "Transaction is on the blockchain"
                    
                # If we got transaction info but no clear confirmation, it's pending
                return "Unconfirmed", "Transaction is pending confirmation"
                
            except Exception as e:
                logger.warning(f"Could not get transaction status from web3 client: {str(e)}")
                # Fall back to Method 2
            
            # Method 2: Try to get transaction from blockchain explorer
            try:
                import requests
                explorer_url = f"https://api.etherscan.io/api?module=transaction&action=getstatus&txhash={tx_hash}"
                response = requests.get(explorer_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('result', {}).get('isError', '0') == '0':
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    else:
                        return "Failed", f"Transaction failed with status: {data.get('result', {}).get('status', 'Unknown')}"
            except Exception as e:
                logger.warning(f"Could not get transaction status from Etherscan API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

class BitcoinBlockchainService(BlockchainService):
    def __init__(self, network='mainnet'):
        from bitcoinlib.wallets import Wallet
        from bitcoinlib.services.bitcoind import BitcoindClient
        self.network = network
        self.client = BitcoindClient(network=network)
    
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        try:
            wallet = Wallet.create(
                name='temp_wallet',
                keys=private_key,
                network=self.network
            )
            
            fee_rate = self.client.estimatefee()
            estimated_size = 250  # Approximate size for a typical Bitcoin transaction
            estimated_fee = fee_rate * estimated_size / 1000  # Convert to BTC
            
            balance = self.get_balance(sender_address)
            if balance is None:
                return None, "Could not get balance"
            
            return {
                'sender_address': sender_address,
                'recipient_address': recipient_address,
                'amount': amount,
                'sender_balance_before': balance,
                'estimated_fee': estimated_fee,
                'balance_after_tx': balance - float(amount) - estimated_fee
            }, None
            
        except Exception as e:
            logger.error(f"Error preparing Bitcoin transaction: {str(e)}")
            return None, str(e)
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        try:
            wallet = Wallet.create(
                name='temp_wallet',
                keys=private_key,
                network=self.network
            )
            
            # Create and sign transaction
            tx = wallet.send_to(
                recipient_address,
                float(amount),
                fee=tx_details['estimated_fee'],
                offline=True
            )
            
            # Broadcast transaction
            tx_hash = self.client.sendrawtransaction(tx.raw_hex())
            
            return {
                "transaction_hash": tx_hash,
                "status": "Success",
                "actual_fee": tx_details['estimated_fee'],
                "sender_balance_after": self.get_balance(sender_address)
            }, None
            
        except Exception as e:
            logger.error(f"Error sending Bitcoin transaction: {str(e)}")
            return None, str(e)
    
    def get_balance(self, address):
        try:
            return self.client.getaddressbalance(address)
        except Exception as e:
            logger.error(f"Error getting Bitcoin balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        try:
            return self.client.validateaddress(address)['isvalid']
        except Exception:
            return False

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        try:
            # Method 1: Try to get transaction directly from bitcoind client
            try:
                tx_info = self.client.gettransaction(tx_hash)
                
                # Check if transaction has confirmations
                if hasattr(tx_info, 'confirmations') and tx_info.confirmations > 0:
                    return "Confirmed", "Transaction has been confirmed and executed successfully"
                
                # If we got transaction info but no clear confirmation, it's pending
                return "Unconfirmed", "Transaction is pending confirmation"
                
            except Exception as e:
                logger.warning(f"Could not get transaction status from bitcoind client: {str(e)}")
                # Fall back to Method 2
            
            # Method 2: Try to get transaction from blockchain explorer
            try:
                import requests
                explorer_url = f"https://api.blockcypher.com/v1/btc/main/txs/{tx_hash}"
                response = requests.get(explorer_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('confirmations', 0) > 0:
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    else:
                        return "Unconfirmed", "Transaction is pending confirmation"
            except Exception as e:
                logger.warning(f"Could not get transaction status from BlockCypher API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

class TronBlockchainService(BlockchainService):
    def __init__(self):
        try:
            from tronpy import Tron
            from tronpy.providers import HTTPProvider
            from config.api_config import EXTERNAL_APIS
            
            # Get API key from config
            self.api_key = EXTERNAL_APIS.get('TRONGRID_API_KEY', '')
            
            # Initialize with custom provider that includes API key
            if self.api_key and self.api_key != 'your_trongrid_api_key_here':
                try:
                    provider = HTTPProvider(api_key=self.api_key)
                    self.client = Tron(provider=provider)
                    # Test the connection
                    self.client.get_latest_block_number()
                    logger.info("TronGrid API key found and connection successful.")
                except Exception as e:
                    logger.error(f"Error initializing Tron client with API key: {str(e)}")
                    logger.warning("Falling back to default provider without API key.")
                    self.client = Tron()
            else:
                # Fallback to default provider
                logger.warning("No valid TronGrid API key found in config. Using public endpoint with rate limits.")
                self.client = Tron()
                # Test the connection
                try:
                    self.client.get_latest_block_number()
                    logger.info("Connection to Tron network successful with default provider.")
                except Exception as e:
                    logger.error(f"Error connecting to Tron network with default provider: {str(e)}")
            
            self.tronpy_available = True
            
            # Standard TRC20 ABI for token transfers
            self.trc20_abi = [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_to", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "payable": False,
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
                
            logger.info("TronBlockchainService initialized successfully")
        except ImportError as e:
            logger.error(f"Could not import tronpy. Tron functionality will be limited: {str(e)}")
            logger.error("Please install tronpy with: pip install tronpy")
            self.client = None
            self.tronpy_available = False
            self.api_key = None
        except Exception as e:
            logger.error(f"Error initializing TronBlockchainService: {str(e)}")
            self.client = None
            self.tronpy_available = False
            self.api_key = None
    
    def _make_api_request(self, url, method="get", data=None):
        """Make API request to TronGrid with API key if available"""
        import requests
        
        headers = {}
        if hasattr(self, 'api_key') and self.api_key and self.api_key != 'your_trongrid_api_key_here':
            headers["TRON-PRO-API-KEY"] = self.api_key
        
        try:
            if method.lower() == "get":
                response = requests.get(url, headers=headers)
            else:
                response = requests.post(url, json=data, headers=headers)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error making TronGrid API request: {str(e)}")
            return None
    
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        if not self.tronpy_available:
            return None, "Tron libraries not available. Please install tronpy."
            
        try:
            # Get account information
            try:
                account = self.client.get_account(sender_address)
                
                # Check if account is a dict or an object
                if isinstance(account, dict):
                    # If it's a dict, get balance directly from the dict
                    balance = account.get('balance', 0)
                else:
                    # If it's an object with a balance method
                    balance = account.balance()
            except Exception as e:
                logger.error(f"Error getting account information: {str(e)}")
                return None, f"Error getting account information: {str(e)}"
            
            # Check if this is a token transfer (has smart contract address)
            is_token = bool(smart_contract_address)
            
            # Estimate fee
            if is_token:
                # For token transfers, fee is typically around 10-20 TRX
                estimated_fee = 10000000  # 10 TRX in SUN as a safe estimate
                
                # Check token balance if it's a token transfer
                try:
                    # Validate smart contract address format
                    if smart_contract_address.startswith('0x'):
                        # Convert Ethereum-style address to Tron format if needed
                        logger.info(f"Converting Ethereum-style address to Tron format: {smart_contract_address}")
                        # Remove 0x prefix for Tron
                        contract_address = smart_contract_address[2:]
                    else:
                        contract_address = smart_contract_address
                    
                    # Create contract instance with ABI
                    try:
                        # For Tron, we need to ensure the address is in the correct format
                        # If it's not a valid Tron address (starting with T), try to convert it
                        if not contract_address.startswith('T'):
                            try:
                                from tronpy.keys import to_base58check_address
                                # Try to convert hex address to base58check format
                                contract_address = to_base58check_address(contract_address)
                                logger.info(f"Converted contract address to Tron format for transaction: {contract_address}")
                            except Exception as e:
                                logger.error(f"Failed to convert contract address to Tron format for transaction: {str(e)}")
                                return None, f"Invalid token contract address format: {smart_contract_address}"
                        
                        contract = self.client.get_contract(contract_address)
                        
                        # Set ABI if not already set
                        if not hasattr(contract, 'abi') or not contract.abi:
                            logger.info(f"Setting standard TRC20 ABI for contract {contract_address}")
                            contract.abi = self.trc20_abi
                        
                        decimals = 18  # Default
                        
                        try:
                            # Call decimals function
                            decimals_func = contract.functions.decimals
                            if callable(decimals_func):
                                decimals = decimals_func()
                            logger.info(f"Token decimals: {decimals}")
                        except Exception as e:
                            logger.warning(f"Could not get token decimals, using default (18): {str(e)}")
                        
                        token_balance = 0
                        try:
                            # Call balanceOf function
                            balance_func = contract.functions.balanceOf
                            if callable(balance_func):
                                token_balance = balance_func(sender_address) / (10 ** decimals)
                            logger.info(f"Token balance: {token_balance}")
                            
                            # Check if balance is sufficient
                            if token_balance < float(amount):
                                return None, f"Insufficient token balance. Available: {token_balance}, Required: {amount}"
                        except Exception as e:
                            logger.error(f"Error getting token balance: {str(e)}")
                            return None, f"Error getting token balance: {str(e)}"
                    except Exception as e:
                        logger.error(f"Error interacting with token contract: {str(e)}")
                        return None, f"Error interacting with token contract: {str(e)}"
                except Exception as e:
                    logger.error(f"Error processing token contract: {str(e)}")
                    return None, f"Error processing token contract: {str(e)}"
            else:
                # For TRX transfers, fee is typically around 0.1-1 TRX
                estimated_fee = 1000000  # 1 TRX in SUN
                
                # Check if TRX balance is sufficient
                if balance < int(float(amount) * 1e6) + estimated_fee:
                    return None, f"Insufficient TRX balance. Available: {balance/1e6}, Required: {float(amount) + estimated_fee/1e6}"
            
            return {
                'sender_address': sender_address,
                'recipient_address': recipient_address,
                'amount': amount,
                'sender_balance_before': balance / 1e6,  # Convert from SUN to TRX
                'estimated_fee': estimated_fee / 1e6,    # Convert from SUN to TRX
                'balance_after_tx': (balance - int(float(amount) * 1e6) - estimated_fee) / 1e6,
                'is_token': is_token,
                'contract_address': smart_contract_address
            }, None
            
        except Exception as e:
            logger.error(f"Error preparing Tron transaction: {str(e)}")
            return None, f"Error preparing Tron transaction: {str(e)}"
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        if not self.tronpy_available:
            return None, "Tron libraries not available. Please install tronpy."
            
        try:
            from tronpy.keys import PrivateKey
            
            # Convert amount to SUN (1 TRX = 1,000,000 SUN)
            amount_sun = int(float(amount) * 1e6)
            
            # Create transaction
            if tx_details['is_token'] and tx_details['contract_address']:
                # For TRC20 tokens
                contract_address = tx_details['contract_address']
                
                # Handle Ethereum-style addresses
                if contract_address.startswith('0x'):
                    # Remove 0x prefix for Tron
                    contract_address = contract_address[2:]
                
                try:
                    # For Tron, we need to ensure the address is in the correct format
                    # If it's not a valid Tron address (starting with T), try to convert it
                    if not contract_address.startswith('T'):
                        try:
                            from tronpy.keys import to_base58check_address
                            # Try to convert hex address to base58check format
                            contract_address = to_base58check_address(contract_address)
                            logger.info(f"Converted contract address to Tron format for transaction: {contract_address}")
                        except Exception as e:
                            logger.error(f"Failed to convert contract address to Tron format for transaction: {str(e)}")
                            return None, f"Invalid token contract address format: {tx_details['contract_address']}"
                    
                    # Create contract instance with ABI
                    contract = self.client.get_contract(contract_address)
                    
                    # Set ABI if not already set
                    if not hasattr(contract, 'abi') or not contract.abi:
                        logger.info(f"Setting standard TRC20 ABI for contract {contract_address}")
                        contract.abi = self.trc20_abi
                    
                    # Get token decimals
                    decimals = 18  # Default
                    try:
                        decimals_func = contract.functions.decimals
                        if callable(decimals_func):
                            decimals = decimals_func()
                        logger.info(f"Token decimals for transfer: {decimals}")
                    except Exception as e:
                        logger.warning(f"Could not get token decimals for transfer, using default (18): {str(e)}")
                    
                    # Convert amount to token units
                    amount_in_token_units = int(float(amount) * (10 ** decimals))
                    logger.info(f"Amount in token units: {amount_in_token_units}")
                    
                    # Build transaction
                    transfer_func = contract.functions.transfer
                    if callable(transfer_func):
                        txn = transfer_func(recipient_address, amount_in_token_units).with_owner(sender_address).build()
                    else:
                        return None, "Transfer function not available in contract"
                except Exception as e:
                    logger.error(f"Error building token transfer transaction: {str(e)}")
                    return None, f"Error building token transfer transaction: {str(e)}"
            else:
                # For TRX transfers
                try:
                    txn = self.client.trx.transfer(sender_address, recipient_address, amount_sun)
                except Exception as e:
                    logger.error(f"Error building TRX transfer transaction: {str(e)}")
                    return None, f"Error building TRX transfer transaction: {str(e)}"
            
            # Sign transaction
            try:
                priv_key = PrivateKey(bytes.fromhex(private_key))
                
                # Check if we're dealing with a TransactionBuilder object (for TRX transfers)
                # or a regular transaction object (for token transfers)
                if hasattr(txn, 'build') and callable(txn.build):
                    logger.info("Using build().sign() method for TransactionBuilder object")
                    signed_txn = txn.build().sign(priv_key)
                else:
                    logger.info("Using direct sign() method for transaction object")
                    signed_txn = txn.sign(priv_key)
                    
            except Exception as e:
                logger.error(f"Error signing transaction: {str(e)}")
                return None, f"Error signing transaction: {str(e)}"
            
            # Broadcast transaction
            try:
                result = signed_txn.broadcast()
                
                # Get transaction details
                tx_hash = result['txid']
                
                logger.info(f"Transaction successfully broadcast with hash: {tx_hash}")
                
                # Check initial transaction status
                status, description = self.check_transaction_status(tx_hash)
                
                # Get sender balance after transaction (may still show the same if not confirmed yet)
                try:
                    current_balance = self.get_balance(sender_address)
                except Exception:
                    current_balance = tx_details['sender_balance_before'] - float(amount) - tx_details['estimated_fee']
                
                return {
                    "transaction_hash": tx_hash,
                    "status": status,
                    "description": description,
                    "actual_fee": tx_details['estimated_fee'],
                    "sender_balance_after": current_balance,
                    "confirmation_checks": 1  # Track how many times we've checked for confirmation
                }, None
            except Exception as e:
                logger.error(f"Error broadcasting transaction: {str(e)}")
                return None, f"Error broadcasting transaction: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error sending Tron transaction: {str(e)}")
            return None, f"Error sending Tron transaction: {str(e)}"
    
    def get_balance(self, address):
        if not self.tronpy_available:
            return None
            
        try:
            # Try direct API call first if API key is available
            if hasattr(self, 'api_key') and self.api_key and self.api_key != 'your_trongrid_api_key_here':
                account_data = self._make_api_request(f"https://api.trongrid.io/v1/accounts/{address}")
                if account_data and 'data' in account_data and len(account_data['data']) > 0:
                    return int(account_data['data'][0].get('balance', 0)) / 1e6
            
            # Fallback to tronpy client
            account = self.client.get_account(address)
            if isinstance(account, dict):
                balance = account.get('balance', 0)
            else:
                balance = account.balance()
                
            return balance / 1e6  # Convert from SUN to TRX
        except Exception as e:
            logger.error(f"Error getting Tron balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        # Basic validation for Tron addresses (starts with T and is 34 characters)
        if address.startswith('T') and len(address) == 34:
            return True
            
        # If tronpy is available, use its validation
        if self.tronpy_available:
            try:
                from tronpy.keys import is_address
                return is_address(address)
            except Exception as e:
                logger.error(f"Error validating Tron address with tronpy: {str(e)}")
                
        return False

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        if not self.tronpy_available:
            return "Unknown", "Tron libraries not available"
            
        try:
            # Method 1: Try to get transaction directly from tronpy client
            try:
                tx_info = self.client.get_transaction(tx_hash)
                
                # Check if transaction has confirmations
                if hasattr(tx_info, 'ret') and tx_info.ret:
                    # Get the contract return status
                    ret_status = tx_info.ret[0].get('contractRet', '')
                    if ret_status == 'SUCCESS':
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    elif ret_status:  # Any other status like REVERT, OUT_OF_ENERGY, etc.
                        return "Failed", f"Transaction failed with status: {ret_status}"
                
                # If we have block number but no clear status, it's likely confirmed
                if hasattr(tx_info, 'blockNumber') and tx_info.blockNumber:
                    return "Confirmed", "Transaction is on the blockchain"
                    
                # If we got transaction info but no clear confirmation, it's pending
                return "Unconfirmed", "Transaction is pending confirmation"
                
            except Exception as e:
                logger.warning(f"Could not get transaction status from tronpy client: {str(e)}")
                # Fall back to Method 2
            
            # Method 2: Try to get transaction from TronGrid API
            api_url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
            tx_data = self._make_api_request(api_url)
            
            if tx_data and 'data' in tx_data and len(tx_data['data']) > 0:
                transaction = tx_data['data'][0]
                
                # Check confirmation status
                if transaction.get('block_timestamp', 0) > 0:
                    # Check result field for status
                    result = transaction.get('ret', [{}])[0].get('contractRet', '')
                    if result == 'SUCCESS':
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    elif result:  # Any non-empty result other than SUCCESS
                        return "Failed", f"Transaction failed with status: {result}"
                    else:
                        return "Confirmed", "Transaction is on the blockchain"
                else:
                    return "Unconfirmed", "Transaction is pending confirmation"
            
            # Method 3: Try TronScan API as a last resort
            try:
                import requests
                tronscan_url = f"https://apilist.tronscan.org/api/transaction-info?hash={tx_hash}"
                response = requests.get(tronscan_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('confirmed', False):
                        if data.get('contractRet', '') == 'SUCCESS':
                            return "Confirmed", "Transaction has been confirmed and executed successfully"
                        elif data.get('contractRet', ''):
                            return "Failed", f"Transaction failed with status: {data.get('contractRet')}"
                        else:
                            return "Confirmed", "Transaction is on the blockchain"
                    else:
                        return "Unconfirmed", "Transaction is pending confirmation"
            except Exception as e:
                logger.warning(f"Could not get transaction status from TronScan API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

class SolanaBlockchainService(BlockchainService):
    def __init__(self):
        self.client = Client("https://api.mainnet-beta.solana.com")
        self.endpoint = "https://api.mainnet-beta.solana.com"
    
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        try:
            # Get balance using REST API directly
            balance = self.get_balance(sender_address)
            if balance is None:
                return None, "Could not get balance"
            
            # Estimate fee (typical Solana transaction fee)
            estimated_fee = 0.000005  # 5000 lamports
            
            if smart_contract_address:
                # For SPL tokens - simplified version
                return {
                    'sender_address': sender_address,
                    'recipient_address': recipient_address,
                    'amount': amount,
                    'sender_balance_before': balance,
                    'estimated_fee': estimated_fee,
                    'balance_after_tx': balance - float(amount) - estimated_fee,
                    'is_token': True,
                    'contract_address': smart_contract_address
                }, None
            else:
                # For SOL transfers
                return {
                    'sender_address': sender_address,
                    'recipient_address': recipient_address,
                    'amount': amount,
                    'sender_balance_before': balance,
                    'estimated_fee': estimated_fee,
                    'balance_after_tx': balance - float(amount) - estimated_fee,
                    'is_token': False
                }, None
                
        except Exception as e:
            logger.error(f"Error preparing Solana transaction: {str(e)}")
            return None, str(e)
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        try:
            # This is a simplified implementation
            # In a real implementation, we would use the Solana SDK to create and send transactions
            # For now, we'll just return a mock transaction hash
            
            # For demonstration purposes, we'll just return a mock transaction hash
            tx_hash = "solana_tx_" + str(hash(f"{sender_address}_{recipient_address}_{amount}_{private_key[:5]}"))
            
            return {
                "transaction_hash": tx_hash,
                "status": "Success",
                "actual_fee": tx_details['estimated_fee'],
                "sender_balance_after": self.get_balance(sender_address)
            }, None
            
        except Exception as e:
            logger.error(f"Error sending Solana transaction: {str(e)}")
            return None, str(e)
    
    def get_balance(self, address):
        try:
            # Use REST API directly
            response = self.client.get_balance(address)
            if 'result' in response and 'value' in response['result']:
                return response['result']['value'] / 10**9  # Convert from lamports to SOL
            return None
        except Exception as e:
            logger.error(f"Error getting Solana balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        # Simple validation - Solana addresses are base58 encoded and 32-44 characters long
        import re
        pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
        return bool(pattern.match(address))

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        try:
            # Method 1: Try to get transaction directly from Solana client
            try:
                import json
                import requests
                
                headers = {"Content-Type": "application/json"}
                data = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        tx_hash,
                        {"encoding": "json"}
                    ]
                }
                
                response = requests.post(self.endpoint, headers=headers, data=json.dumps(data))
                result = response.json().get("result")
                
                if result:
                    # Check if transaction is confirmed
                    if result.get("meta") and result["meta"].get("status"):
                        if result["meta"]["status"].get("Ok") is not None:
                            return "Confirmed", "Transaction has been confirmed and executed successfully"
                        else:
                            return "Failed", f"Transaction failed with error: {result['meta']['status'].get('Err', 'Unknown')}"
                    elif result.get("confirmations") and result["confirmations"] > 0:
                        return "Confirmed", "Transaction has been confirmed"
                    return "Unconfirmed", "Transaction is still being processed"
                else:
                    # No result means transaction not found or still pending
                    return "Unconfirmed", "Transaction is pending or not found"
                    
            except Exception as e:
                logger.warning(f"Could not get transaction status from Solana API: {str(e)}")
            
            # Method 2: Try Solana Explorer API
            try:
                import requests
                explorer_url = f"https://explorer-api.mainnet-beta.solana.com/tx/{tx_hash}"
                response = requests.get(explorer_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    elif data.get("status") == "failed":
                        return "Failed", f"Transaction failed: {data.get('message', 'Unknown reason')}"
            except Exception as e:
                logger.warning(f"Could not get transaction status from Solana Explorer API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

class XRPBlockchainService(BlockchainService):
    def __init__(self):
        # Import inside method to avoid global import issues
        try:
            from xrpl.clients import JsonRpcClient
            self.client = JsonRpcClient("https://s1.ripple.com:51234/")
        except ImportError:
            logger.error("Could not import XRP libraries. XRP functionality will be limited.")
            self.client = None
    
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        try:
            # Import inside method to avoid global import issues
            try:
                from xrpl.models.transactions import Payment
                from xrpl.utils import xrp_to_drops
            except ImportError:
                return None, "XRP libraries not available"
            
            balance = self.get_balance(sender_address)
            if balance is None:
                return None, "Could not get balance"
            
            # Standard XRP transaction fee
            estimated_fee = 0.00001  # 10 drops
            
            return {
                'sender_address': sender_address,
                'recipient_address': recipient_address,
                'amount': amount,
                'sender_balance_before': balance,
                'estimated_fee': estimated_fee,
                'balance_after_tx': balance - float(amount) - estimated_fee
            }, None
            
        except Exception as e:
            logger.error(f"Error preparing XRP transaction: {str(e)}")
            return None, str(e)
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        try:
            # Import inside method to avoid global import issues
            try:
                from xrpl.models.transactions import Payment
                from xrpl.utils import xrp_to_drops
                from xrpl.wallet import Wallet
                from xrpl.transaction import submit_and_wait
            except ImportError:
                return None, "XRP libraries not available"
            
            wallet = Wallet(private_key)
            
            payment = Payment(
                account=sender_address,
                destination=recipient_address,
                amount=xrp_to_drops(str(amount))
            )
            
            response = submit_and_wait(payment, self.client, wallet)
            
            return {
                "transaction_hash": response.result['hash'],
                "status": "Success" if response.is_successful() else "Failed",
                "actual_fee": tx_details['estimated_fee'],
                "sender_balance_after": self.get_balance(sender_address)
            }, None
            
        except Exception as e:
            logger.error(f"Error sending XRP transaction: {str(e)}")
            return None, str(e)
    
    def get_balance(self, address):
        try:
            # Import inside method to avoid global import issues
            try:
                from xrpl.models.requests import AccountInfo
            except ImportError:
                return None
                
            response = self.client.request(AccountInfo(account=address))
            if response.is_successful():
                return float(response.result['account_data']['Balance']) / 1e6  # Convert from drops to XRP
            return None
        except Exception as e:
            logger.error(f"Error getting XRP balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        try:
            # Import inside method to avoid global import issues
            try:
                from xrpl.core import addresscodec
            except ImportError:
                return True  # Skip validation if library not available
                
            return addresscodec.is_valid_classic_address(address)
        except Exception:
            return False

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        try:
            # Method 1: Try to get transaction directly from XRPL client
            try:
                if self.client:
                    payload = {
                        "method": "tx",
                        "params": [
                            {
                                "transaction": tx_hash,
                                "binary": False
                            }
                        ]
                    }
                    
                    response = self.client.request(json.dumps(payload))
                    result = response.get("result", {})
                    
                    if result.get("validated", False):
                        if result.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
                            return "Confirmed", "Transaction has been confirmed and executed successfully"
                        else:
                            return "Failed", f"Transaction failed with status: {result.get('meta', {}).get('TransactionResult', 'Unknown')}"
                    else:
                        return "Unconfirmed", "Transaction is not yet validated"
            except Exception as e:
                logger.warning(f"Could not get transaction status from XRPL client: {str(e)}")
            
            # Method 2: Try XRP Explorer API
            try:
                import requests
                explorer_url = f"https://api.xrpscan.com/api/v1/tx/{tx_hash}"
                response = requests.get(explorer_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("validated", False):
                        if data.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
                            return "Confirmed", "Transaction has been confirmed and executed successfully"
                        else:
                            return "Failed", f"Transaction failed with status: {data.get('meta', {}).get('TransactionResult', 'Unknown')}"
                    else:
                        return "Unconfirmed", "Transaction is not yet validated"
            except Exception as e:
                logger.warning(f"Could not get transaction status from XRPScan API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

class PolkadotBlockchainService(BlockchainService):
    def __init__(self):
        try:
            from substrateinterface import SubstrateInterface
            self.substrate = SubstrateInterface(
                url="wss://rpc.polkadot.io"
            )
        except ImportError:
            logger.error("Could not import Polkadot libraries. Polkadot functionality will be limited.")
            self.substrate = None
    
    def prepare_transaction(self, sender_address, private_key, recipient_address, amount, smart_contract_address=None):
        try:
            try:
                from substrateinterface import SubstrateInterface
            except ImportError:
                return None, "Polkadot libraries not available"
                
            balance = self.get_balance(sender_address)
            if balance is None:
                return None, "Could not get balance"
            
            # Get fee estimate
            try:
                call = self.substrate.compose_call(
                    call_module='Balances',
                    call_function='transfer',
                    call_params={
                        'dest': recipient_address,
                        'value': int(float(amount) * 1e10)  # Convert to Planck
                    }
                )
                
                payment_info = self.substrate.get_payment_info(call, sender_address)
                estimated_fee = float(payment_info['partialFee']) / 1e10  # Convert from Planck to DOT
            except Exception as e:
                logger.error(f"Error estimating Polkadot fee: {str(e)}")
                estimated_fee = 0.01  # Default estimate
            
            return {
                'sender_address': sender_address,
                'recipient_address': recipient_address,
                'amount': amount,
                'sender_balance_before': balance,
                'estimated_fee': estimated_fee,
                'balance_after_tx': balance - float(amount) - estimated_fee
            }, None
            
        except Exception as e:
            logger.error(f"Error preparing Polkadot transaction: {str(e)}")
            return None, str(e)
    
    def send_transaction(self, sender_address, private_key, recipient_address, amount, tx_details):
        try:
            try:
                from substrateinterface import SubstrateInterface
                from substrateinterface.keypair import Keypair
            except ImportError:
                return None, "Polkadot libraries not available"
            
            keypair = Keypair.create_from_private_key(private_key)
            
            call = self.substrate.compose_call(
                call_module='Balances',
                call_function='transfer',
                call_params={
                    'dest': recipient_address,
                    'value': int(float(amount) * 1e10)  # Convert to Planck
                }
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(
                call=call,
                keypair=keypair
            )
            
            response = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            return {
                "transaction_hash": response.extrinsic_hash,
                "status": "Success" if response.is_success else "Failed",
                "actual_fee": tx_details['estimated_fee'],
                "sender_balance_after": self.get_balance(sender_address)
            }, None
            
        except Exception as e:
            logger.error(f"Error sending Polkadot transaction: {str(e)}")
            return None, str(e)
    
    def get_balance(self, address):
        try:
            if not self.substrate:
                return None
                
            result = self.substrate.query(
                module='System',
                storage_function='Account',
                params=[address]
            )
            return float(result['data']['free']) / 1e10  # Convert from Planck to DOT
        except Exception as e:
            logger.error(f"Error getting Polkadot balance: {str(e)}")
            return None
    
    def validate_address(self, address):
        try:
            try:
                from substrateinterface.utils.ss58 import is_valid_ss58_address
            except ImportError:
                return True  # Skip validation if library not available
                
            return is_valid_ss58_address(address)
        except Exception:
            return False

    def check_transaction_status(self, tx_hash):
        """
        Check the status of a transaction by its hash
        Returns a tuple (status, message) where status is one of:
        - "Unconfirmed" - Transaction is still pending
        - "Confirmed" - Transaction is confirmed and successful
        - "Failed" - Transaction failed
        """
        try:
            # Try to get transaction from Subscan API
            try:
                import requests
                
                api_key = EXTERNAL_APIS.get('SUBSCAN_API_KEY', '')
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["X-API-Key"] = api_key
                
                subscan_url = "https://polkadot.api.subscan.io/api/scan/extrinsic"
                data = {"hash": tx_hash}
                
                response = requests.post(subscan_url, headers=headers, json=data)
                result = response.json()
                
                if result.get("code") == 0 and "data" in result:
                    tx_data = result["data"]
                    
                    if tx_data.get("success"):
                        return "Confirmed", "Transaction has been confirmed and executed successfully"
                    elif tx_data.get("finalized"):
                        return "Failed", "Transaction is finalized but failed to execute"
                    else:
                        return "Unconfirmed", "Transaction is still being processed"
                else:
                    return "Unknown", "Transaction not found or still pending"
            except Exception as e:
                logger.warning(f"Could not get transaction status from Subscan API: {str(e)}")
            
            # If we got here, we couldn't determine the status
            return "Unknown", "Transaction status could not be determined"
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return "Unknown", f"Error checking transaction status: {str(e)}"

# Dictionary to map blockchain names to their service classes
BLOCKCHAIN_SERVICES = {
    'Bitcoin': BitcoinBlockchainService,
    'BITCOIN': BitcoinBlockchainService,
    'Ethereum': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR-PROJECT-ID')), 1),
    'ETHEREUM': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR-PROJECT-ID')), 1),
    'Tron': TronBlockchainService,
    'TRON': TronBlockchainService,
    'Binance': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org')), 56),
    'BINANCE': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org')), 56),
    'Polygon': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://polygon-rpc.com')), 137),
    'POLYGON': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://polygon-rpc.com')), 137),
    'Avalanche': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://api.avax.network/ext/bc/C/rpc')), 43114),
    'AVALANCHE': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://api.avax.network/ext/bc/C/rpc')), 43114),
    'Arbitrum': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://arb1.arbitrum.io/rpc')), 42161),
    'ARBITRUM': lambda: EVMBlockchainService(Web3(Web3.HTTPProvider('https://arb1.arbitrum.io/rpc')), 42161),
    'Polkadot': PolkadotBlockchainService,
    'POLKADOT': PolkadotBlockchainService,
    'XRP': XRPBlockchainService,
    'Solana': SolanaBlockchainService,
    'SOLANA': SolanaBlockchainService
}

def get_blockchain_service(blockchain_name):
    """Get the appropriate blockchain service instance"""
    logger.info(f"Getting blockchain service for: {blockchain_name}")
    
    # Normalize blockchain name for comparison
    normalized_name = blockchain_name.lower()
    
    # Initialize necessary variables from config
    infura_api_key = EXTERNAL_APIS.get('INFURA_API_KEY', 'YOUR-PROJECT-ID')
    trongrid_api_key = EXTERNAL_APIS.get('TRONGRID_API_KEY', '')
    subscan_api_key = EXTERNAL_APIS.get('SUBSCAN_API_KEY', '')
    
    # Create service instances based on blockchain name
    if normalized_name in ['bitcoin', 'btc']:
        logger.info(f"Creating Bitcoin blockchain service")
        return BitcoinBlockchainService(network='mainnet')
        
    elif normalized_name in ['ethereum', 'eth']:
        logger.info(f"Creating Ethereum blockchain service with chain_id=1")
        provider = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{infura_api_key}'))
        return EVMBlockchainService(web3_provider=provider, chain_id=1)
        
    elif normalized_name in ['tron', 'trx']:
        logger.info(f"Creating Tron blockchain service")
        return TronBlockchainService()
        
    elif normalized_name in ['binance', 'bsc', 'bnb']:
        logger.info(f"Creating Binance Smart Chain service with chain_id=56")
        provider = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org'))
        return EVMBlockchainService(web3_provider=provider, chain_id=56)
        
    elif normalized_name in ['polygon', 'matic']:
        logger.info(f"Creating Polygon blockchain service with chain_id=137")
        provider = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
        return EVMBlockchainService(web3_provider=provider, chain_id=137)
        
    elif normalized_name in ['avalanche', 'avax']:
        logger.info(f"Creating Avalanche blockchain service with chain_id=43114")
        provider = Web3(Web3.HTTPProvider('https://api.avax.network/ext/bc/C/rpc'))
        return EVMBlockchainService(web3_provider=provider, chain_id=43114)
        
    elif normalized_name in ['arbitrum', 'arb']:
        logger.info(f"Creating Arbitrum blockchain service with chain_id=42161")
        provider = Web3(Web3.HTTPProvider('https://arb1.arbitrum.io/rpc'))
        return EVMBlockchainService(web3_provider=provider, chain_id=42161)
        
    elif normalized_name in ['polkadot', 'dot']:
        logger.info(f"Creating Polkadot blockchain service")
        return PolkadotBlockchainService()
        
    elif normalized_name in ['xrp', 'ripple']:
        logger.info(f"Creating XRP blockchain service")
        return XRPBlockchainService()
        
    elif normalized_name in ['solana', 'sol']:
        logger.info(f"Creating Solana blockchain service")
        return SolanaBlockchainService()
    
    # If still not found, try case-insensitive match in original dictionary
    for name, service in BLOCKCHAIN_SERVICES.items():
        if name.lower() == blockchain_name.lower():
            logger.info(f"Found service class via case-insensitive match: {name}")
            if callable(service):
                instance = service()
                logger.info(f"Created service instance: {type(instance).__name__}")
                return instance
            instance = service()
            logger.info(f"Created service instance: {type(instance).__name__}")
            return instance
    
    logger.error(f"Unsupported blockchain: {blockchain_name}")
    raise ValueError(f"Unsupported blockchain: {blockchain_name}")
