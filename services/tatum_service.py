import requests
import logging
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)

class TatumService:
    """Service class for interacting with Tatum API"""
    
    def __init__(self, api_key):
        """Initialize with Tatum API key"""
        self.api_key = api_key
        self.base_url = "https://api.tatum.io/v3"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
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
            logger.error(f"Unsupported blockchain: {blockchain_name}")
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
            logger.warning(f"Unknown BSC token contract: {contract_address}, defaulting to BSC")
            return "BSC"
            
        return currency

    def _make_request(self, method: str, endpoint: str, params=None, data=None) -> Tuple[Optional[Dict], Optional[str]]:
        """Make request to Tatum API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            logger.debug(f"Request data: {data}")
            
            if method.lower() == 'get':
                response = requests.get(url, headers=self.headers, params=params)
            elif method.lower() == 'post':
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return None, f"Unsupported HTTP method: {method}"
            
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
                
            if response.status_code == 200:
                return response.json(), None
            else:
                error_msg = f"Tatum API error: {response.status_code}, {response.text}"
                logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            error_msg = f"Error calling Tatum API: {str(e)}"
            logger.error(error_msg)
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
            
            logger.debug(f"Getting balance from endpoint: {endpoint}")
            return self._make_request('get', endpoint)

        except ValueError as e:
            return None, str(e)
        except Exception as e:
            error_msg = f"Error getting balance: {str(e)}"
            logger.error(error_msg)
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
    
    def prepare_transaction(self, blockchain_name: str, sender_address: str, private_key: str, 
                           recipient_address: str, amount: str, smart_contract_address=None) -> Tuple[Dict, Optional[str]]:
        """Prepare a transaction for sending using Tatum API"""
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
            
            # Set endpoint and add chain-specific parameters
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

                # Use the complete blockchain name for BSC endpoint
                endpoint = "/Binance Smart Chain/transaction"
                
                # Prepare request data based on transaction type
                if smart_contract_address:
                    # For token transfers
                    request_data = {
                        "to": recipient_address,
                        "amount": amount,
                        "fromPrivateKey": private_key,
                        "currency": "BSC",
                        "contractAddress": smart_contract_address,
                        "fee": {
                            "gasLimit": gas_limit,
                            "gasPrice": gas_price
                        }
                    }
                else:
                    # For native BNB transfer
                    request_data = {
                        "to": recipient_address,
                        "amount": amount,
                        "fromPrivateKey": private_key,
                        "currency": "BSC",
                        "fee": {
                            "gasLimit": gas_limit,
                            "gasPrice": gas_price
                        }
                    }
            elif chain == "eth":
                # Use the complete blockchain name for Ethereum endpoint
                endpoint = "/ethereum/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "ETH",
                    "fee": {
                        "gasLimit": "21000",
                        "gasPrice": "20"
                    }
                }
                estimated_fee = "0.00042"  # Default estimate for ETH
            elif chain == "polygon":
                # Use the complete blockchain name for Polygon endpoint
                endpoint = "/polygon/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount, 
                    "fromPrivateKey": private_key,
                    "currency": "MATIC"
                }
                estimated_fee = "0.0001"  # Default estimate
            elif chain == "tron":
                # Use the complete blockchain name for Tron endpoint
                endpoint = "/tron/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "TRON"
                }
                estimated_fee = "0.0001"  # Default estimate
            elif chain == "btc":
                # Use the complete blockchain name for Bitcoin endpoint
                endpoint = "/bitcoin/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "BTC"
                }
                estimated_fee = "0.0001"  # Default estimate
            elif chain == "solana":
                # Use the complete blockchain name for Solana endpoint
                endpoint = "/solana/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "SOL"
                }
                estimated_fee = "0.000005"  # Default estimate
            elif chain == "xrp":
                # Use the complete blockchain name for XRP endpoint
                endpoint = "/xrp/transaction" 
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "XRP"
                }
                estimated_fee = "0.00001"  # Default estimate
            elif chain == "avalanche":
                # Use the complete blockchain name for Avalanche endpoint
                endpoint = "/avalanche/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "AVAX"
                }
                estimated_fee = "0.0001"  # Default estimate
            elif chain == "arbitrum":
                # Use the complete blockchain name for Arbitrum endpoint
                endpoint = "/arbitrum/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": "ARB"
                }
                estimated_fee = "0.0001"  # Default estimate
            else:
                # For other chains, use the full name format
                # Convert abbreviated chain name to full endpoint name
                endpoint = f"/{chain}/transaction"
                request_data = {
                    "to": recipient_address,
                    "amount": amount,
                    "fromPrivateKey": private_key,
                    "currency": blockchain_name.upper()
                }
                estimated_fee = "0.0001"  # Default estimate
            
            # Make request to Tatum API
            logger.debug(f"Preparing {chain} transaction")
            logger.debug(f"Request data: {request_data}")
            logger.debug(f"Endpoint: {endpoint}")
            
            response_data, error = self._make_request('post', endpoint, data=request_data)
            
            if error:
                return {}, f"Error preparing transaction: {error}"
            
            # Get transaction hash from response
            transaction_hash = response_data.get('txId')
            if not transaction_hash:
                return {}, "Transaction hash not found in response"
            
            # Calculate estimated balance after
            try:
                balance_after = float(sender_balance_before) - float(amount) - float(estimated_fee)
                sender_balance_after = str(max(0, balance_after))
            except (ValueError, TypeError):
                sender_balance_after = "Unknown"
            
            # Prepare transaction details
            tx_details = {
                "sender_address": sender_address,
                "recipient_address": recipient_address,
                "amount": amount,
                "currency": blockchain_name.upper(),
                "transaction_hash": transaction_hash,
                "is_token": bool(smart_contract_address),
                "contract_address": smart_contract_address,
                "chain": chain,
                "prepared_data": response_data,
                "estimated_fee": estimated_fee,
                "sender_balance_before": sender_balance_before,
                "sender_balance_after": sender_balance_after
            }
            
            return tx_details, None
            
        except ValueError as e:
            return {}, str(e)
        except Exception as e:
            error_msg = f"Error preparing transaction: {str(e)}"
            logger.error(error_msg)
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
            logger.debug(f"Sending {chain} transaction")
            logger.debug(f"Request data: {request_data}")
            
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
            logger.error(error_msg)
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
            logger.error(error_msg)
            return "Unknown", error_msg 