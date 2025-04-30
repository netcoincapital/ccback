import requests
import logging
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import uuid
import aiohttp
import os
import sys
from decimal import Decimal
from utils.logging_config import get_logger

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TatumService:
    """Service class for interacting with Tatum API"""
    
    def __init__(self):
        self.api_key = os.getenv('TATUM_API_KEY')
        if not self.api_key:
            raise RuntimeError("TATUM_API_KEY environment variable is not set")

        self.base_url = "https://api.tatum.io/v3"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        self.logger = get_logger(__file__)
        
        # Mapping blockchain names to Tatum chain identifiers
        self.chain_mapping = {
            "ethereum": "eth",
            "bitcoin": "btc",
            "tron": "tron",
            "binance smart chain": "bsc",
            "binance": "bsc",
            "bsc": "bsc",
            "BSC": "bsc",
            "polygon": "polygon",
            "avalanche": "avalanche",
            "arbitrum": "arbitrum",
            "polkadot": "dot",
            "xrp": "xrp",
            "solana": "solana"
        }

        # Token contract address to currency mapping for BSC
        self.bsc_token_mapping = {
            "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD_BSC",  # BUSD
            "0x55d398326f99059ff775485246999027b3197955": "USDT_BSC",  # USDT
            "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC_BSC",  # USDC
            "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c": "BBTC",      # BTCB
            "0x2170ed0880ac9a755fd29b2688956bd959f933f8": "BETH",      # ETH
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB"       # WBNB
        }
    
    def _get_chain_name(self, blockchain_name: str) -> str:
        """Convert blockchain name to Tatum chain identifier"""
        chain = self.chain_mapping.get(blockchain_name.lower())
        if not chain:
            self.logger.error(f"Unsupported blockchain: {blockchain_name}")
            raise ValueError(f"Unsupported blockchain: {blockchain_name}")
        return chain
    
    def _get_bsc_currency(self, contract_address: str = None) -> str:
        """Get the appropriate currency code for BSC transactions"""
        if not contract_address:
            return "BSC"  # Native BSC token
        
        # Convert contract address to lowercase for comparison
        contract_address = contract_address.lower()
        currency = self.bsc_token_mapping.get(contract_address)
        
        if not currency:
            self.logger.warning(f"Unknown BSC token contract: {contract_address}, defaulting to BSC")
            return "BSC"
            
        return currency

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
                
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"Tatum API error: {response.status_code}, {response.text}"
                self.logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            error_msg = f"Error calling Tatum API: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg

    def get_balance(self, blockchain_name: str, address: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get balance for an address"""
        try:
            chain = self._get_chain_name(blockchain_name)
            
            # ✅ مسیر صحیح برای ETH
            if chain == "eth":
                endpoint = f"/ethereum/account/balance/{address}"
            
            # ✅ مسیر صحیح برای BSC
            elif chain == "bsc":
                endpoint = f"/bsc/account/balance/{address}"
            
            # ✅ مسیر پیش‌فرض برای بقیه
            else:
                endpoint = f"/ledger/account/{chain}/{address}/balance"
            
            self.logger.debug(f"Getting balance from endpoint: {endpoint}")
            return self._make_request('get', endpoint)

        except ValueError as e:
            return None, str(e)
        except Exception as e:
            error_msg = f"Error getting balance: {str(e)}"
            self.logger.error(error_msg)
            return None, error_msg

    
    def validate_address(self, blockchain_name: str, address: str) -> bool:
        """Validate if an address is valid for a specific blockchain"""
        try:
            chain = self._get_chain_name(blockchain_name)
            
            # Basic validation based on blockchain rules
            if chain == 'btc' and (address.startswith('1') or address.startswith('3') or address.startswith('bc1')):
                return len(address) >= 26 and len(address) <= 35
            
            elif chain in ['eth', 'bsc', 'polygon', 'avalanche', 'arbitrum']:
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
        chain = self._get_chain_name(blockchain_name)
        
        # Use complete blockchain names in endpoint URLs
        if chain == "eth":
            endpoint = f"/ethereum/transaction/{tx_hash}"
        elif chain == "bsc":
            endpoint = f"/Binance Smart Chain/transaction/{tx_hash}"
        elif chain == "btc":
            endpoint = f"/bitcoin/transaction/{tx_hash}"
        elif chain == "polygon":
            endpoint = f"/polygon/transaction/{tx_hash}"
        elif chain == "tron":
            endpoint = f"/tron/transaction/{tx_hash}"
        elif chain == "solana":
            endpoint = f"/solana/transaction/{tx_hash}"
        elif chain == "xrp":
            endpoint = f"/xrp/transaction/{tx_hash}"
        elif chain == "avalanche":
            endpoint = f"/avalanche/transaction/{tx_hash}"
        elif chain == "arbitrum":
            endpoint = f"/arbitrum/transaction/{tx_hash}"
        else:
            # For other chains, use the chain identifier
            endpoint = f"/{chain}/transaction/{tx_hash}"
        
        return self._make_request('get', endpoint)
    
    async def prepare_transaction(self, blockchain_name: str, sender_address: str, recipient_address: str, 
                                amount: str, smart_contract_address: Optional[str] = None) -> Tuple[Dict, Optional[str]]:
        """
        Prepare transaction parameters and estimates without broadcasting
        
        Args:
            blockchain_name: Name of the blockchain (e.g., "ethereum", "bsc")
            sender_address: Address sending the transaction
            recipient_address: Address receiving the transaction
            amount: Amount to send
            smart_contract_address: Optional contract address for token transfers
            
        Returns:
            Tuple of (response_data, error_message)
        """
        # Validate and clean amount
        try:
            if not amount:
                return {}, "Amount must not be empty"
            
            # Convert to float and validate
            amount_float = float(amount)
            if amount_float <= 0:
                return {}, "Amount must be a positive number"
            
            # Convert back to string with 18 decimal precision
            amount = str(round(amount_float, 18))
            
        except ValueError:
            return {}, "Amount must be a valid number"

        try:
            # Get chain name and validate addresses
            chain = self._get_chain_name(blockchain_name)
            
            if not self.validate_address(blockchain_name, sender_address):
                return {}, f"Invalid sender address format for {blockchain_name}"
                
            if not self.validate_address(blockchain_name, recipient_address):
                return {}, f"Invalid recipient address format for {blockchain_name}"
            
            # Get current balance
            balance_data, error = await self._make_request('get', f"{blockchain_name.lower()}/account/balance/{sender_address}")
            if error:
                return {}, f"Error getting sender balance: {error}"
            
            sender_balance_before = balance_data.get('balance', '0')
            
            # Get gas estimation
            gas_data, gas_error = await self._make_request('post', f"/{blockchain_name.lower()}/gas", data={
                "from": sender_address,
                "to": recipient_address,
                "amount": amount,  # Use cleaned amount
                "data": "" if not smart_contract_address else "0xa9059cbb"  # Transfer method ID for tokens
            })
            
            # Set default gas values if estimation failed
            if gas_error:
                gas_limit = "21000"
                gas_price = "5"
                estimated_fee = "0.0001"
            else:
                gas_limit = gas_data.get("gasLimit", "21000")
                gas_price = gas_data.get("gasPrice", "5")
                estimated_fee = str(round(float(gas_price) * float(gas_limit) / 1e9, 18))
            
            # Calculate estimated balance after
            try:
                balance_after = float(sender_balance_before) - float(amount) - float(estimated_fee)
                sender_balance_after = str(round(balance_after, 18))
            except (ValueError, TypeError):
                sender_balance_after = "Unknown"
            
            # Prepare details dictionary with all required fields
            details = {
                "amount": amount,
                "sender": sender_address,
                "recipient": recipient_address,
                "chain": chain,
                "estimated_fee": estimated_fee,
                "gas_limit": str(gas_limit),
                "gas_price": str(gas_price),
                "sender_balance_before": sender_balance_before,
                "sender_balance_after": sender_balance_after,
                "contract_address": smart_contract_address,
                "currency": blockchain_name.upper(),
                "is_token": bool(smart_contract_address)
            }
            
            # Return flat response structure
            return {
                "success": True,
                "details": details,
                "transaction_id": None,
                "expires_at": None
            }, None
            
        except ValueError as e:
            return {}, str(e)
        except Exception as e:
            error_msg = f"Error preparing transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
    
    def send_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                        recipient_address: str, amount: str, tx_details: Dict) -> Tuple[Dict, Optional[str]]:
        """Send a transaction using Tatum API"""
        try:
            chain = self._get_chain_name(blockchain_name)
            
            # Validate addresses
            if not self.validate_address(blockchain_name, sender_address):
                return {}, f"Invalid sender address format for {blockchain_name}"
                
            if not self.validate_address(blockchain_name, recipient_address):
                return {}, f"Invalid recipient address format for {blockchain_name}"
            
            # If we have a signature ID, use KMS endpoint
            if tx_details.get('signature_id'):
                endpoint = f"/kms/{tx_details['signature_id']}"
                request_data = {
                    "fromPrivateKey": private_key
                }
            else:
                # Prepare request data
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": tx_details.get('currency')
                }
                
                # Set endpoint and add chain-specific parameters
                if chain == "bsc":
                    endpoint = "/Binance Smart Chain/transaction"
                    if tx_details.get('is_token'):
                        request_data["contractAddress"] = tx_details.get('contract_address')
                    else:
                        request_data["fee"] = {
                            "gasLimit": "21000",
                            "gasPrice": "5"
                        }
                elif chain == "eth":
                    endpoint = "/ethereum/transaction"
                    if tx_details.get('is_token'):
                        request_data["contractAddress"] = tx_details.get('contract_address')
                    else:
                        request_data["fee"] = {
                            "gasLimit": "21000",
                            "gasPrice": "20"
                        }
                else:
                    # For other chains, use the chain identifier
                    endpoint = f"/{chain}/transaction"
                    if tx_details.get('is_token'):
                        request_data["contractAddress"] = tx_details.get('contract_address')
            
            # Log request details
            self.logger.debug(f"Sending {chain} transaction")
            self.logger.debug(f"Request data: {request_data}")
            
            # Send transaction
            response_data, error = self._make_request('post', endpoint, data=request_data)
            
            if error:
                return {}, error
            
            # Extract transaction hash from response
            tx_hash = response_data.get('txId')
            
            if not tx_hash:
                return {}, "Transaction hash not found in response"
            
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
            
            return result, None
            
        except ValueError as e:
            return {}, str(e)
        except Exception as e:
            error_msg = f"Error sending transaction: {str(e)}"
            self.logger.error(error_msg)
            return {}, error_msg
    
    def check_transaction_status(self, blockchain_name: str, tx_hash: str) -> Tuple[str, str]:
        """Check the status of a transaction"""
        chain = self._get_chain_name(blockchain_name)
        
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
            chain = self._get_chain_name(blockchain_name)
            
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
            if chain == "bsc":
                # First get gas estimate
                gas_data, gas_error = self._make_request('post', "/bsc/gas", data={
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
            chain = self._get_chain_name(blockchain_name)
            
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
        endpoint = f"{blockchain.lower()}/gas"
        url = f"{self.base_url.rstrip('/')}/{endpoint}"

        try:
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
                    
        except aiohttp.ClientError as e:
            error_msg = f"Network error while getting gas price: {str(e)}"
            self.logger.error(error_msg)
            return 0, error_msg
        except Exception as e:
            error_msg = f"Exception getting gas price: {str(e)}"
            self.logger.error(error_msg)
            return 0, error_msg 