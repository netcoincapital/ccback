import logging
import uuid
import os
import sys
import time
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from web3 import Web3, HTTPProvider
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.exceptions import TransactionNotFound
from requests.exceptions import Timeout
import tronpy
from tronpy import Tron
from tronpy.keys import PrivateKey as TronPrivateKey
import bitcoinlib
from bitcoinlib.wallets import Wallet
from bitcoinlib.transactions import Transaction as BTCTransaction
import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet as XRPWallet
from xrpl.models.transactions import Payment
from xrpl.transaction import autofill, sign
import solana
from solana.rpc.api import Client as SolanaClient
from solana.publickey import PublicKey
from solders.keypair import Keypair
from solders.transaction import Transaction
from solana.system_program import TransferParams, transfer
from substrateinterface import SubstrateInterface
from substrateinterface import SubstrateInterface, Keypair as SubstrateKeypair

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import logging configuration
from CC.utils.logging_config import get_logger, get_log_directory

# Configure logging
logger = get_logger(__file__)

# RPC Providers for failover
ETHEREUM_RPC_PROVIDERS = [
    "https://mainnet.infura.io/v3/{}",  # Primary
    "https://rpc.ankr.com/eth",         # Backup 1
    "https://eth.public-rpc.com",       # Backup 2
]

# Timeout settings
RPC_TIMEOUT = 20  # seconds

class LocalBlockchainService:
    """Service class for locally signing blockchain transactions"""
    
    def __init__(self):
        """Initialize with blockchain providers"""
        # Get Infura API key from environment variables
        infura_api_key = os.getenv('INFURA_API_KEY')
        if not infura_api_key:
            error_msg = "INFURA_API_KEY environment variable is not set. Please set it to connect to Ethereum networks."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        # Initialize providers with failover support
        self.providers = self._initialize_providers(infura_api_key)
        
        # Set gas price strategy for EVM chains
        for chain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum"]:
            if self.providers[chain]:
                self.providers[chain].eth.set_gas_price_strategy(medium_gas_price_strategy)
                logger.debug(f"Gas price strategy set for {chain}")
    
    def _initialize_providers(self, infura_api_key: str) -> Dict[str, Any]:
        """Initialize blockchain providers with failover support"""
        providers = {}
        
        # Initialize Ethereum provider with failover
        ethereum_provider = None
        for rpc_url in ETHEREUM_RPC_PROVIDERS:
            try:
                formatted_url = rpc_url.format(infura_api_key) if "{}" in rpc_url else rpc_url
                provider = HTTPProvider(formatted_url, request_kwargs={'timeout': RPC_TIMEOUT})
                web3 = Web3(provider)
                
                # Test connection
                if web3.is_connected():
                    logger.info(f"Successfully connected to Ethereum RPC: {formatted_url}")
                    ethereum_provider = web3
                    break
                else:
                    logger.warning(f"Failed to connect to Ethereum RPC: {formatted_url}")
            except Exception as e:
                logger.warning(f"Error connecting to Ethereum RPC {formatted_url}: {str(e)}")
        
        if not ethereum_provider:
            raise RuntimeError("Could not connect to any Ethereum RPC provider")
        
        providers["ethereum"] = ethereum_provider
        
        # Initialize other providers
        providers.update({
            "bsc": Web3(HTTPProvider("https://bsc-dataseed.binance.org/", request_kwargs={'timeout': RPC_TIMEOUT})),
            "polygon": Web3(HTTPProvider("https://polygon-rpc.com", request_kwargs={'timeout': RPC_TIMEOUT})),
            "avalanche": Web3(HTTPProvider("https://api.avax.network/ext/bc/C/rpc", request_kwargs={'timeout': RPC_TIMEOUT})),
            "arbitrum": Web3(HTTPProvider("https://arb1.arbitrum.io/rpc", request_kwargs={'timeout': RPC_TIMEOUT})),
            "tron": Tron(network="mainnet"),
            "bitcoin": None,
            "xrp": JsonRpcClient("https://s1.ripple.com:51234"),
            "solana": SolanaClient("https://api.mainnet-beta.solana.com"),
            "polkadot": SubstrateInterface(url="wss://rpc.polkadot.io")
        })
        
        return providers
    
    def _switch_ethereum_provider(self, current_provider: Web3, infura_api_key: str) -> Tuple[Web3, bool]:
        """Switch to next available Ethereum RPC provider"""
        current_url = current_provider.provider.endpoint_uri
        current_index = ETHEREUM_RPC_PROVIDERS.index(current_url) if current_url in ETHEREUM_RPC_PROVIDERS else -1
        
        for next_index in range(current_index + 1, len(ETHEREUM_RPC_PROVIDERS)):
            try:
                next_url = ETHEREUM_RPC_PROVIDERS[next_index]
                formatted_url = next_url.format(infura_api_key) if "{}" in next_url else next_url
                provider = HTTPProvider(formatted_url, request_kwargs={'timeout': RPC_TIMEOUT})
                web3 = Web3(provider)
                
                if web3.is_connected():
                    logger.info(f"Switched to backup Ethereum RPC: {formatted_url}")
                    return web3, True
            except Exception as e:
                logger.warning(f"Failed to switch to backup RPC {formatted_url}: {str(e)}")
        
        return current_provider, False
    
    def _get_chain_details(self, blockchain_name: str) -> Tuple[str, Any]:
        """Get chain name and provider with error handling"""
        try:
            blockchain_name = blockchain_name.lower()
            
            # Map common names to standard names
            chain_mapping = {
                "eth": "ethereum",
                "bnb": "bsc",
                "binance smart chain": "bsc",
                "matic": "polygon",
                "avax": "avalanche",
                "arb": "arbitrum",
                "dot": "polkadot",
                "btc": "bitcoin",
                "sol": "solana"
            }
            
            chain = chain_mapping.get(blockchain_name, blockchain_name)
            
            if chain not in self.providers:
                error_msg = f"Unsupported blockchain: {blockchain_name}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            return chain, self.providers[chain]
            
        except Exception as e:
            logger.error(f"Error getting chain details: {str(e)}")
            raise
    
    def sign_evm_transaction(self, blockchain_name: str, sender_address: str, private_key: str,
                           recipient_address: str, amount: str, smart_contract_address=None) -> Tuple[Dict, Optional[str]]:
        """Sign a transaction for EVM-compatible chains with improved error handling and logging"""
        logger.info(f"Starting EVM transaction signing for blockchain: {blockchain_name}")
        
        try:
            chain, web3 = self._get_chain_details(blockchain_name)
            
            # Validate addresses
            if not web3.is_address(sender_address):
                error_msg = f"Invalid sender address format for {blockchain_name}"
                logger.error(error_msg)
                return {}, error_msg
                
            if not web3.is_address(recipient_address):
                error_msg = f"Invalid recipient address format for {blockchain_name}"
                logger.error(error_msg)
                return {}, error_msg
            
            # Get current balance with error handling and failover
            try:
                logger.debug(f"Getting balance for address {sender_address}")
                sender_balance_before = web3.from_wei(web3.eth.get_balance(sender_address), 'ether')
                logger.debug(f"Balance retrieved: {sender_balance_before} ETH")
            except (Timeout, Exception) as e:
                logger.warning(f"Error getting balance from primary RPC: {str(e)}")
                if chain == "ethereum":
                    web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                    if switched:
                        try:
                            sender_balance_before = web3.from_wei(web3.eth.get_balance(sender_address), 'ether')
                            logger.debug(f"Balance retrieved from backup RPC: {sender_balance_before} ETH")
                        except Exception as e2:
                            error_msg = f"Error getting balance from backup RPC: {str(e2)}"
                            logger.error(error_msg)
                            return {}, error_msg
                    else:
                        error_msg = f"Error getting balance: {str(e)}"
                        logger.error(error_msg)
                        return {}, error_msg
                else:
                    error_msg = f"Error getting balance: {str(e)}"
                    logger.error(error_msg)
                    return {}, error_msg
            
            # Get nonce with error handling and failover
            try:
                logger.debug(f"Getting transaction count for address {sender_address}")
                nonce = web3.eth.get_transaction_count(sender_address)
                logger.debug(f"Nonce retrieved: {nonce}")
            except (Timeout, Exception) as e:
                logger.warning(f"Error getting nonce from primary RPC: {str(e)}")
                if chain == "ethereum":
                    web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                    if switched:
                        try:
                            nonce = web3.eth.get_transaction_count(sender_address)
                            logger.debug(f"Nonce retrieved from backup RPC: {nonce}")
                        except Exception as e2:
                            error_msg = f"Error getting nonce from backup RPC: {str(e2)}"
                            logger.error(error_msg)
                            return {}, error_msg
                    else:
                        error_msg = f"Error getting nonce: {str(e)}"
                        logger.error(error_msg)
                        return {}, error_msg
                else:
                    error_msg = f"Error getting nonce: {str(e)}"
                    logger.error(error_msg)
                    return {}, error_msg
            
            # Convert amount to Wei
            amount_wei = web3.to_wei(amount, 'ether')
            
            # Gas price estimation with error handling and failover
            try:
                logger.debug("Estimating gas price")
                gas_price = web3.eth.generate_gas_price()
                if not gas_price:
                    gas_price = web3.eth.gas_price
                logger.debug(f"Gas price estimated: {web3.from_wei(gas_price, 'gwei')} gwei")
            except (Timeout, Exception) as e:
                logger.warning(f"Error estimating gas price from primary RPC: {str(e)}")
                if chain == "ethereum":
                    web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                    if switched:
                        try:
                            gas_price = web3.eth.generate_gas_price()
                            if not gas_price:
                                gas_price = web3.eth.gas_price
                            logger.debug(f"Gas price estimated from backup RPC: {web3.from_wei(gas_price, 'gwei')} gwei")
                        except Exception as e2:
                            error_msg = f"Error estimating gas price from backup RPC: {str(e2)}"
                            logger.error(error_msg)
                            return {}, error_msg
                    else:
                        error_msg = f"Error estimating gas price: {str(e)}"
                        logger.error(error_msg)
                        return {}, error_msg
                else:
                    error_msg = f"Error estimating gas price: {str(e)}"
                    logger.error(error_msg)
                    return {}, error_msg
            
            # Build transaction
            if smart_contract_address:
                # Token transfer via contract
                try:
                    contract = web3.eth.contract(address=smart_contract_address, abi=[])
                    transfer_function_signature = web3.keccak(text="transfer(address,uint256)").hex()[:10]
                    padded_address = '0' * 24 + recipient_address[2:]
                    padded_amount = format(int(amount_wei), '064x')
                    data = transfer_function_signature + padded_address + padded_amount
                    
                    tx_params = {
                        'from': sender_address,
                        'to': smart_contract_address,
                        'value': 0,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'data': data
                    }
                    
                    # Estimate gas with error handling and failover
                    try:
                        logger.debug("Estimating gas for token transfer")
                        gas_limit = web3.eth.estimate_gas(tx_params)
                        logger.debug(f"Gas limit estimated: {gas_limit}")
                    except (Timeout, Exception) as e:
                        logger.warning(f"Error estimating gas from primary RPC: {str(e)}")
                        if chain == "ethereum":
                            web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                            if switched:
                                try:
                                    gas_limit = web3.eth.estimate_gas(tx_params)
                                    logger.debug(f"Gas limit estimated from backup RPC: {gas_limit}")
                                except Exception as e2:
                                    logger.warning(f"Failed to estimate gas from backup RPC: {str(e2)}. Using default value.")
                                    gas_limit = 100000  # Default for token transfers
                            else:
                                logger.warning(f"Failed to estimate gas: {str(e)}. Using default value.")
                                gas_limit = 100000  # Default for token transfers
                        else:
                            logger.warning(f"Failed to estimate gas: {str(e)}. Using default value.")
                            gas_limit = 100000  # Default for token transfers
                    
                    tx_params['gas'] = gas_limit
                except Exception as e:
                    error_msg = f"Error preparing token transfer: {str(e)}"
                    logger.error(error_msg)
                    return {}, error_msg
            else:
                # Native token transfer
                tx_params = {
                    'from': sender_address,
                    'to': recipient_address,
                    'value': amount_wei,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                }
                
                # Estimate gas with error handling and failover
                try:
                    logger.debug("Estimating gas for native transfer")
                    gas_limit = web3.eth.estimate_gas(tx_params)
                    logger.debug(f"Gas limit estimated: {gas_limit}")
                except (Timeout, Exception) as e:
                    logger.warning(f"Error estimating gas from primary RPC: {str(e)}")
                    if chain == "ethereum":
                        web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                        if switched:
                            try:
                                gas_limit = web3.eth.estimate_gas(tx_params)
                                logger.debug(f"Gas limit estimated from backup RPC: {gas_limit}")
                            except Exception as e2:
                                logger.warning(f"Failed to estimate gas from backup RPC: {str(e2)}. Using default value.")
                                gas_limit = 21000  # Default for native transfers
                        else:
                            logger.warning(f"Failed to estimate gas: {str(e)}. Using default value.")
                            gas_limit = 21000  # Default for native transfers
                    else:
                        logger.warning(f"Failed to estimate gas: {str(e)}. Using default value.")
                        gas_limit = 21000  # Default for native transfers
                
                tx_params['gas'] = gas_limit
            
            # Sign transaction - never log private key!
            try:
                logger.debug(f"Signing transaction for address {sender_address}")
                signed_tx = web3.eth.account.sign_transaction(tx_params, private_key)
                signed_tx_hex = signed_tx.rawTransaction.hex()
                logger.info(f"Successfully signed transaction for sender {sender_address}")
            except (Timeout, Exception) as e:
                logger.warning(f"Error signing transaction with primary RPC: {str(e)}")
                if chain == "ethereum":
                    web3, switched = self._switch_ethereum_provider(web3, os.getenv('INFURA_API_KEY'))
                    if switched:
                        try:
                            signed_tx = web3.eth.account.sign_transaction(tx_params, private_key)
                            signed_tx_hex = signed_tx.rawTransaction.hex()
                            logger.info(f"Successfully signed transaction with backup RPC for sender {sender_address}")
                        except Exception as e2:
                            error_msg = f"Error signing transaction with backup RPC: {str(e2)}"
                            logger.error(error_msg)
                            return {}, error_msg
                    else:
                        error_msg = f"Error signing transaction: {str(e)}"
                        logger.error(error_msg)
                        return {}, error_msg
                else:
                    error_msg = f"Error signing transaction: {str(e)}"
                    logger.error(error_msg)
                    return {}, error_msg
            
            # Calculate estimated fee
            estimated_fee_wei = int(tx_params['gas']) * int(gas_price)
            estimated_fee = web3.from_wei(estimated_fee_wei, 'ether')
            
            # Calculate estimated balance after
            balance_after = float(sender_balance_before) - float(amount) - float(estimated_fee)
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": blockchain_name,
                "signed_tx": signed_tx_hex,
                "gas_price": str(web3.from_wei(gas_price, 'gwei')),
                "gas_limit": str(tx_params['gas']),
                "estimated_fee": str(estimated_fee),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error in sign_evm_transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def sign_tron_transaction(self, sender_address: str, private_key: str,
                            recipient_address: str, amount: str, token_address=None) -> Tuple[Dict, Optional[str]]:
        """Sign a Tron transaction"""
        try:
            chain, client = self._get_chain_details("tron")
            
            # Validate addresses (basic validation)
            if not sender_address.startswith('T') or len(sender_address) != 34:
                return {}, "Invalid Tron sender address format"
                
            if not recipient_address.startswith('T') or len(recipient_address) != 34:
                return {}, "Invalid Tron recipient address format"
            
            # Get current balance
            account_info = client.get_account(sender_address)
            sender_balance_before = account_info.get('balance', 0) / 1_000_000  # Convert SUN to TRX
            
            # Convert amount to SUN (TRX * 10^6)
            amount_sun = int(float(amount) * 1_000_000)
            
            # Create private key instance
            logger.debug(f"Creating private key instance for Tron transaction from address {sender_address}")
            priv_key = TronPrivateKey(bytes.fromhex(private_key))
            
            # Build transaction
            if token_address:
                # Token transfer (TRC20)
                contract = client.get_contract(token_address)
                tx = contract.functions.transfer(recipient_address, amount_sun).with_owner(sender_address).build()
                estimated_fee = 30  # Default estimated fee for token transfer
            else:
                # Native TRX transfer
                tx = client.transfer(sender_address, recipient_address, amount_sun)
                estimated_fee = 3  # Default estimated fee for TRX transfer
            
            # Sign transaction
            logger.debug(f"Signing Tron transaction for address {sender_address}")
            signed_tx = priv_key.sign_transaction(tx)
            
            # Convert to hex for storage
            signed_tx_hex = signed_tx.to_json()
            
            # Calculate estimated balance after
            balance_after = sender_balance_before - float(amount) - estimated_fee/1_000_000
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": "tron",
                "signed_tx": signed_tx_hex,
                "gas_price": "NA",
                "gas_limit": "NA",
                "estimated_fee": str(estimated_fee/1_000_000),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error signing Tron transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def sign_bitcoin_transaction(self, sender_address: str, private_key: str,
                               recipient_address: str, amount: str) -> Tuple[Dict, Optional[str]]:
        """Sign a Bitcoin transaction"""
        wallet = None
        try:
            # For Bitcoin we'll use bitcoinlib
            # Note: This is a simplified implementation
            
            # Convert amount to satoshis
            amount_satoshi = int(float(amount) * 100_000_000)
            
            # Create wallet with private key
            wallet_name = f"temp_wallet_{uuid.uuid4().hex[:8]}"
            logger.debug(f"Creating temporary Bitcoin wallet '{wallet_name}' for address {sender_address}")
            wallet = Wallet.create(wallet_name, keys=private_key, network="bitcoin")
            
            # Get UTXO info and balance
            wallet.scan()
            sender_balance_before = wallet.balance() / 100_000_000  # Convert to BTC
            
            # Create transaction
            tx = wallet.send_to(recipient_address, amount_satoshi, fee=None, offline=True)
            
            # Get raw signed transaction
            signed_tx_hex = tx.raw_hex()
            
            # Get estimated fee
            estimated_fee = tx.fee / 100_000_000  # Convert to BTC
            
            # Calculate balance after
            balance_after = sender_balance_before - float(amount) - estimated_fee
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": "bitcoin",
                "signed_tx": signed_tx_hex,
                "gas_price": "NA",
                "gas_limit": "NA",
                "estimated_fee": str(estimated_fee),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error signing Bitcoin transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
        finally:
            # Cleanup temporary wallet
            if wallet:
                try:
                    # Try to delete wallet if possible
                    if hasattr(wallet, 'wallet_delete') and callable(wallet.wallet_delete):
                        wallet.wallet_delete()
                        logger.debug(f"Temporary Bitcoin wallet deleted successfully")
                    else:
                        # Try to remove wallet files manually if API doesn't provide delete method
                        import os
                        from bitcoinlib.wallets import WalletError
                        try:
                            wallet_path = os.path.join(os.path.expanduser("~"), ".bitcoinlib", "wallets")
                            wallet_file = os.path.join(wallet_path, f"{wallet.name}.wallet")
                            if os.path.exists(wallet_file):
                                os.remove(wallet_file)
                                logger.debug(f"Manually removed temporary Bitcoin wallet file: {wallet_file}")
                        except (OSError, WalletError) as e:
                            logger.warning(f"Failed to manually delete Bitcoin wallet file: {str(e)}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary Bitcoin wallet: {str(e)}")
    
    def sign_xrp_transaction(self, sender_address: str, private_key: str,
                           recipient_address: str, amount: str) -> Tuple[Dict, Optional[str]]:
        """Sign an XRP (Ripple) transaction"""
        try:
            chain, client = self._get_chain_details("xrp")
            
            # Create wallet from private key
            logger.debug(f"Creating XRP wallet for address {sender_address}")
            wallet = XRPWallet(private_key, algorithm="secp256k1")
            
            # Validate addresses
            if not sender_address.startswith('r'):
                return {}, "Invalid XRP sender address format"
                
            if not recipient_address.startswith('r'):
                return {}, "Invalid XRP recipient address format"
            
            # Get account info
            account_info = client.request(
                "account_info",
                {"account": sender_address, "ledger_index": "validated"}
            )
            sender_balance_before = float(account_info.result["account_data"]["Balance"]) / 1_000_000  # Convert to XRP
            
            # Convert amount to drops (XRP * 10^6)
            amount_drops = str(int(float(amount) * 1_000_000))
            
            # Build payment transaction
            payment = Payment(
                account=sender_address,
                destination=recipient_address,
                amount=amount_drops
            )
            
            # First autofill the transaction with network data
            logger.debug(f"Autofilling XRP transaction for address {sender_address}")
            autofilled_tx = autofill(payment, client)
            
            # Then sign the transaction
            logger.debug(f"Signing XRP transaction for address {sender_address}")
            signed_tx = sign(autofilled_tx, wallet)
            
            # Convert to hex format for storage
            signed_tx_hex = signed_tx.to_xrpl()
            
            # Get fee from autofilled transaction
            estimated_fee = float(autofilled_tx.fee) / 1_000_000  # Convert drops to XRP
            
            # Calculate balance after
            balance_after = sender_balance_before - float(amount) - estimated_fee
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": "xrp",
                "signed_tx": signed_tx_hex,
                "gas_price": "NA",
                "gas_limit": "NA",
                "estimated_fee": str(estimated_fee),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error signing XRP transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def sign_solana_transaction(self, sender_address: str, private_key: str,
                              recipient_address: str, amount: str) -> Tuple[Dict, Optional[str]]:
        """Sign a Solana transaction"""
        try:
            chain, client = self._get_chain_details("solana")
            
            # Create keypair from private key
            logger.debug(f"Creating Solana keypair for address {sender_address}")
            keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
            
            # Get balance
            balance_response = client.get_balance(PublicKey(sender_address))
            sender_balance_before = balance_response["result"]["value"] / 10**9  # Convert lamports to SOL
            
            # Convert amount to lamports (SOL * 10^9)
            amount_lamports = int(float(amount) * 10**9)
            
            # Create transaction
            tx = Transaction()
            tx.add(solana.system_program.transfer(
                PublicKey(sender_address),
                PublicKey(recipient_address),
                amount_lamports
            ))
            
            # Get recent blockhash
            blockhash = client.get_recent_blockhash()["result"]["value"]["blockhash"]
            tx.recent_blockhash = blockhash
            
            # Sign transaction
            logger.debug(f"Signing Solana transaction for address {sender_address}")
            tx.sign(keypair)
            
            # Serialize to hex for storage
            signed_tx_hex = tx.serialize().hex()
            
            # Estimated fee (default 0.000005 SOL)
            estimated_fee = 0.000005
            
            # Calculate balance after
            balance_after = sender_balance_before - float(amount) - estimated_fee
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": "solana",
                "signed_tx": signed_tx_hex,
                "gas_price": "NA",
                "gas_limit": "NA",
                "estimated_fee": str(estimated_fee),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error signing Solana transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def sign_polkadot_transaction(self, sender_address: str, private_key: str,
                                recipient_address: str, amount: str) -> Tuple[Dict, Optional[str]]:
        """Sign a Polkadot transaction"""
        try:
            chain, substrate = self._get_chain_details("polkadot")
            
            # Create keypair from private key
            logger.debug(f"Creating Polkadot keypair for address {sender_address}")
            keypair = SubstrateKeypair.create_from_private_key(bytes.fromhex(private_key))
            
            # Get account info
            account_info = substrate.query("System", "Account", [sender_address])
            sender_balance_before = float(account_info.value['data']['free']) / 10**10  # Convert Planck to DOT
            
            # Convert amount to Planck (DOT * 10^10)
            amount_planck = int(float(amount) * 10**10)
            
            # Create call
            call = substrate.compose_call(
                call_module='Balances',
                call_function='transfer',
                call_params={
                    'dest': recipient_address,
                    'value': amount_planck
                }
            )
            
            # Get nonce
            nonce = substrate.get_account_nonce(sender_address)
            
            # Create extrinsic
            logger.debug(f"Signing Polkadot transaction for address {sender_address}")
            extrinsic = substrate.create_signed_extrinsic(
                call=call,
                keypair=keypair,
                nonce=nonce
            )
            
            # Estimate fee
            payment_info = substrate.get_payment_info(extrinsic, keypair.ss58_address)
            estimated_fee = float(payment_info.get('partialFee', 0)) / 10**10  # Convert to DOT
            
            # Serialize to hex for storage
            signed_tx_hex = extrinsic.serialize()
            
            # Calculate balance after
            balance_after = sender_balance_before - float(amount) - estimated_fee
            sender_balance_after = max(0, balance_after)
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "blockchain": "polkadot",
                "signed_tx": signed_tx_hex,
                "gas_price": "NA",
                "gas_limit": "NA",
                "estimated_fee": str(estimated_fee),
                "sender_balance_before": str(sender_balance_before),
                "sender_balance_after": str(sender_balance_after),
                "transaction_id": str(uuid.uuid4())
            }
            
            return tx_details, None
            
        except Exception as e:
            error_msg = f"Error signing Polkadot transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def sign_transaction(self, blockchain_name: str, sender_address: str, private_key: str,
                       recipient_address: str, amount: str, smart_contract_address=None) -> Tuple[Dict, Optional[str]]:
        """Sign a transaction locally based on blockchain type with improved error handling"""
        logger.info(f"Starting transaction signing for blockchain: {blockchain_name}")
        
        try:
            blockchain_name = blockchain_name.lower()
            
            # Route to appropriate signing method based on blockchain
            if blockchain_name in ["ethereum", "eth", "bsc", "binance", "polygon", "matic", "avalanche", "avax", "arbitrum", "arb"]:
                return self.sign_evm_transaction(blockchain_name, sender_address, private_key, recipient_address, amount, smart_contract_address)
                
            elif blockchain_name in ["tron", "trx"]:
                return self.sign_tron_transaction(sender_address, private_key, recipient_address, amount, smart_contract_address)
                
            elif blockchain_name in ["bitcoin", "btc"]:
                return self.sign_bitcoin_transaction(sender_address, private_key, recipient_address, amount)
                
            elif blockchain_name in ["xrp", "ripple"]:
                return self.sign_xrp_transaction(sender_address, private_key, recipient_address, amount)
                
            elif blockchain_name in ["solana", "sol"]:
                return self.sign_solana_transaction(sender_address, private_key, recipient_address, amount)
                
            elif blockchain_name in ["polkadot", "dot"]:
                return self.sign_polkadot_transaction(sender_address, private_key, recipient_address, amount)
                
            else:
                error_msg = f"Unsupported blockchain for local signing: {blockchain_name}"
                logger.error(error_msg)
                return {}, error_msg
                
        except Exception as e:
            error_msg = f"Error in sign_transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def broadcast_transaction(self, blockchain_name: str, signed_tx: str, sender_address: str = None) -> Tuple[Dict, Optional[str]]:
        """Broadcast a signed transaction to the blockchain"""
        try:
            blockchain_name = blockchain_name.lower()
            
            # EVM chains (Ethereum, BSC, Polygon, etc.)
            if blockchain_name in ["ethereum", "eth", "bsc", "binance", "polygon", "matic", "avalanche", "avax", "arbitrum", "arb"]:
                chain, web3 = self._get_chain_details(blockchain_name)
                
                # Convert hex to bytes if needed
                if isinstance(signed_tx, str) and signed_tx.startswith('0x'):
                    tx_bytes = bytes.fromhex(signed_tx[2:])
                elif isinstance(signed_tx, str):
                    tx_bytes = bytes.fromhex(signed_tx)
                else:
                    tx_bytes = signed_tx
                
                # Send transaction
                tx_hash = web3.eth.send_raw_transaction(tx_bytes).hex()
                
                # Verify transaction hash was received
                if not tx_hash:
                    error_msg = f"Failed to retrieve transaction hash after broadcasting to {blockchain_name} network"
                    logger.error(error_msg)
                    return {}, error_msg
                
                logger.info(f"Successfully broadcast transaction to {blockchain_name} network: {tx_hash}", extra={'blockchain': chain})
                
                # Log transaction broadcast event
                logger.info(f"Broadcast {blockchain_name} transaction for address {sender_address}", extra={'blockchain': chain})
                
                result = {
                    "transaction_hash": tx_hash,
                    "status": "Unconfirmed",
                    "description": f"Transaction has been submitted to the {blockchain_name} network"
                }
                
                return result, None
            
            # Tron
            elif blockchain_name in ["tron", "trx"]:
                chain, client = self._get_chain_details("tron")
                
                # Parse signed transaction JSON
                if isinstance(signed_tx, str):
                    import json
                    tx_data = json.loads(signed_tx)
                else:
                    tx_data = signed_tx
                
                # Broadcast transaction
                result = client.broadcast(tx_data)
                
                if 'txid' in result:
                    logger.info(f"Successfully broadcast transaction to Tron network: {result['txid']}")
                    return {
                        "transaction_hash": result['txid'],
                        "status": "Unconfirmed",
                        "description": "Transaction has been submitted to the Tron network"
                    }, None
                else:
                    error_msg = f"Failed to retrieve transaction hash after broadcasting to Tron network: {result}"
                    logger.error(error_msg)
                    return {}, f"Failed to broadcast Tron transaction: {result}"
            
            # Bitcoin
            elif blockchain_name in ["bitcoin", "btc"]:
                # Use bitcoinlib for broadcasting
                from bitcoinlib.services.services import Service
                
                service = Service(network="bitcoin")
                tx_hash = service.sendrawtransaction(signed_tx)
                
                if not tx_hash:
                    error_msg = "Failed to retrieve transaction hash after broadcasting to Bitcoin network"
                    logger.error(error_msg)
                    return {}, error_msg
                
                logger.info(f"Successfully broadcast transaction to Bitcoin network: {tx_hash}")
                
                result = {
                    "transaction_hash": tx_hash,
                    "status": "Unconfirmed",
                    "description": "Transaction has been submitted to the Bitcoin network"
                }
                
                return result, None
            
            # XRP (Ripple)
            elif blockchain_name in ["xrp", "ripple"]:
                chain, client = self._get_chain_details("xrp")
                
                # Submit transaction
                response = client.request("submit", {"tx_blob": signed_tx})
                
                if 'result' in response and 'tx_json' in response['result']:
                    tx_hash = response['result']['tx_json']['hash']
                    logger.info(f"Successfully broadcast transaction to XRP network: {tx_hash}")
                    return {
                        "transaction_hash": tx_hash,
                        "status": "Unconfirmed",
                        "description": "Transaction has been submitted to the XRP network"
                    }, None
                else:
                    error_msg = f"Failed to retrieve transaction hash after broadcasting to XRP network: {response}"
                    logger.error(error_msg)
                    return {}, f"Failed to broadcast XRP transaction: Transaction hash not found in response"
            
            # Solana
            elif blockchain_name in ["solana", "sol"]:
                chain, client = self._get_chain_details("solana")
                
                # Convert hex to bytes
                if isinstance(signed_tx, str):
                    tx_bytes = bytes.fromhex(signed_tx)
                else:
                    tx_bytes = signed_tx
                
                # Send transaction
                response = client.send_raw_transaction(tx_bytes)
                
                if 'result' in response:
                    tx_hash = response['result']
                    logger.info(f"Successfully broadcast transaction to Solana network: {tx_hash}")
                    return {
                        "transaction_hash": tx_hash,
                        "status": "Unconfirmed",
                        "description": "Transaction has been submitted to the Solana network"
                    }, None
                else:
                    error_msg = f"Failed to retrieve transaction hash after broadcasting to Solana network: {response}"
                    logger.error(error_msg)
                    return {}, f"Failed to broadcast Solana transaction: Transaction hash not found in response"
            
            # Polkadot
            elif blockchain_name in ["polkadot", "dot"]:
                chain, substrate = self._get_chain_details("polkadot")
                
                # Submit extrinsic
                response = substrate.submit_extrinsic(signed_tx)
                
                if hasattr(response, 'extrinsic_hash'):
                    tx_hash = response.extrinsic_hash
                    logger.info(f"Successfully broadcast transaction to Polkadot network: {tx_hash}")
                    return {
                        "transaction_hash": tx_hash,
                        "status": "Unconfirmed",
                        "description": "Transaction has been submitted to the Polkadot network"
                    }, None
                else:
                    error_msg = f"Failed to retrieve transaction hash after broadcasting to Polkadot network: {response}"
                    logger.error(error_msg)
                    return {}, f"Failed to broadcast Polkadot transaction: Transaction hash not found in response"
            
            else:
                return {}, f"Unsupported blockchain for local broadcast: {blockchain_name}"
            
        except Exception as e:
            error_msg = f"Error broadcasting {blockchain_name} transaction: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg 