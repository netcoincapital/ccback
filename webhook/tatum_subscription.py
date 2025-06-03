import os
import requests
import json
import re
import time
from dotenv import load_dotenv

# Import the logging configuration
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()

# Setup logging
logger = get_logger(__file__)

# Tatum API key
TATUM_API_KEY = os.getenv('TATUM_API_KEY')
if not TATUM_API_KEY:
    logger.critical("TATUM_API_KEY not found in environment variables")
    raise ValueError("TATUM_API_KEY not found in environment variables")

# Base URL for Tatum API
TATUM_API_BASE_URL = "https://api.tatum.io/v3"

# Maximum URL length supported by Tatum
MAX_URL_LENGTH = 500

# Webhook base URL configuration
DEFAULT_WEBHOOK_BASE_URL = "https://coinceeper.com"
WEBHOOK_ENDPOINT = "/webhook/tatum/transaction"  # آدرس صحیح وب‌هوک

# Map our internal blockchain names to Tatum's expected chain values
BLOCKCHAIN_MAPPING = {
    # Internal name -> Tatum API name
    "ETH": "ethereum-mainnet",
    "BTC": "bitcoin-mainnet",
    "MATIC": "polygon-mainnet", 
    "BSC": "bsc-mainnet",
    "AVAX": "avax-mainnet",
    "SOL": "solana-mainnet",
    "TRX": "tron-mainnet",
    "DOT": None,  # Polkadot not supported in the new API format
    "XRP": "ripple-mainnet",
    "BNB": "bsc-mainnet",  # BNB uses BSC mainnet
    "ARB": "arb-one-mainnet"
}

# Define which blockchains use EVM addresses
EVM_BLOCKCHAINS = ["ETH", "MATIC", "AVAX", "ARB", "BSC", "BNB"]

# Define blockchains with special address formats
SPECIAL_FORMAT_BLOCKCHAINS = {
    "TRX": "TRON address (T... format)",
    "TRON": "TRON address (T... format)",
    "XRP": "XRP address (r... format)",
    "SOL": "Solana address (base58 format)",
    "BNB": "BNB Chain address (0x... format)",
    "BSC": "BSC Chain address (0x... format)"
}

def normalize_blockchain_name(chain):
    """
    Normalize blockchain name to a format expected by Tatum API.
    
    Args:
        chain (str): Our internal blockchain name
        
    Returns:
        str: Normalized blockchain name for Tatum API or None if unsupported
    """
    if not chain:
        logger.warning("Empty blockchain name provided")
        return None
        
    chain_upper = chain.upper().strip()
    
    # Check if blockchain is explicitly not supported
    if chain_upper == "DOT":
        logger.warning(f"Blockchain {chain} is not supported by Tatum API")
        return None
    
    tatum_chain = BLOCKCHAIN_MAPPING.get(chain_upper)
    
    if tatum_chain is None:
        # Try to find a close match
        if chain_upper in ["BINANCE", "BINANCESMARTCHAIN", "BINANCECOIN"]:
            tatum_chain = "bsc-mainnet"
            logger.info(f"Mapped {chain_upper} to bsc-mainnet for Tatum API")
        elif chain_upper in ["POLYGON"]:
            tatum_chain = "polygon-mainnet"
        elif chain_upper in ["AVALANCHE"]:
            tatum_chain = "avax-mainnet"
        elif chain_upper in ["ETHEREUM"]:
            tatum_chain = "ethereum-mainnet"
        elif chain_upper in ["ARBITRUM"]:
            tatum_chain = "arb-one-mainnet"
        elif chain_upper in ["TRON"]:
            tatum_chain = "tron-mainnet"
        elif chain_upper in ["BITCOIN"]:
            tatum_chain = "bitcoin-mainnet"
        elif chain_upper in ["RIPPLE"]:
            tatum_chain = "ripple-mainnet"
        elif chain_upper in ["SOLANA"]:
            tatum_chain = "solana-mainnet"
        else:
            # Handle unsupported blockchains
            logger.warning(f"Blockchain {chain} is not supported by Tatum API")
            return None
    
    logger.debug(f"Normalized blockchain name: {chain} -> {tatum_chain}")
    return tatum_chain

def apply_checksum_to_eth_address(address):
    """
    Apply checksum to Ethereum address based on EIP-55
    
    Args:
        address (str): Ethereum address
    
    Returns:
        str: Checksummed address
    """
    if not address:
        return address
        
    # Remove '0x' prefix if it exists
    if address.startswith('0x'):
        address_without_prefix = address[2:]
    else:
        address_without_prefix = address
        
    # Ensure the address is 40 characters
    if len(address_without_prefix) != 40:
        logger.error(f"Invalid Ethereum address length: {address}")
        return None
        
    # Convert to lowercase for processing
    address_without_prefix = address_without_prefix.lower()
    
    try:
        import hashlib
        
        # Calculate keccak-256 hash of the address
        hash_obj = hashlib.sha3_256(address_without_prefix.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        
        # Apply checksum based on the hash
        checksum_address = '0x'
        for i in range(40):
            # Get the corresponding hex digit from the hash
            hash_digit = int(hash_hex[i], 16)
            # If the hash digit >= 8, uppercase the address digit if it's a letter
            if hash_digit >= 8 and 'a' <= address_without_prefix[i] <= 'f':
                checksum_address += address_without_prefix[i].upper()
            else:
                checksum_address += address_without_prefix[i]
                
        logger.debug(f"EIP-55 checksum applied: {address} -> {checksum_address}")
        return checksum_address
        
    except Exception as e:
        logger.error(f"Error applying EIP-55 checksum to {address}: {str(e)}")
        # Just return the normalized format as fallback
        return '0x' + address_without_prefix.lower()

def validate_and_format_address(address, chain):
    """
    Validate and format wallet address based on blockchain.
    
    Args:
        address (str): Wallet address to validate and format
        chain (str): Blockchain name
        
    Returns:
        str: Formatted address or None if invalid
    """
    if not address:
        return None
        
    normalized_chain = chain.upper() if chain else ""
    
    try:
        # ETH, MATIC, AVAX, ARB all use same Ethereum address format
        if normalized_chain in ["ETH", "MATIC", "AVAX", "ARB"]:
            # Clean and format address
            clean_address = address.strip()
            
            # Remove 0x prefix if it exists
            if clean_address.startswith('0x'):
                address_without_prefix = clean_address[2:]
            else:
                address_without_prefix = clean_address
                
            # Check if it's a valid hex string
            if not all(c in '0123456789abcdefABCDEF' for c in address_without_prefix):
                logger.error(f"Invalid characters in Ethereum address: {address}")
                return None
                
            # Ensure address is exactly 40 characters
            if len(address_without_prefix) != 40:
                logger.warning(f"Invalid Ethereum address length: {address} (length: {len(address_without_prefix)})")
                # If it's close to 40 characters, try to fix
                if 36 <= len(address_without_prefix) <= 44:
                    if len(address_without_prefix) > 40:
                        address_without_prefix = address_without_prefix[:40]
                        logger.info(f"Trimmed address to 40 characters")
                    else:
                        padding_needed = 40 - len(address_without_prefix)
                        address_without_prefix = '0' * padding_needed + address_without_prefix
                        logger.info(f"Padded address to 40 characters")
                else:
                    logger.error(f"Ethereum address length too far from standard (40 chars): {address}")
                    return None
                    
            # Convert to lowercase for consistent processing
            address_without_prefix = address_without_prefix.lower()
            
            # Return with 0x prefix and lowercase
            formatted_address = '0x' + address_without_prefix.lower()
            logger.debug(f"Formatted EVM address: {address} -> {formatted_address}")
            return formatted_address
            
        # BNB Chain Addresses
        elif normalized_chain == "BNB":
            # Clean address
            clean_address = address.strip()
            
            # BNB Chain uses the same address format as ETH
            if clean_address.startswith('0x'):
                address_without_prefix = clean_address[2:]
            else:
                address_without_prefix = clean_address
            
            # Check if it's a valid hex string
            if not all(c in '0123456789abcdefABCDEF' for c in address_without_prefix):
                logger.error(f"Invalid characters in BNB address: {address}")
                return None
                
            # Ensure address is exactly 40 characters
            if len(address_without_prefix) != 40:
                logger.warning(f"Invalid BNB address length: {address} (length: {len(address_without_prefix)})")
                if 36 <= len(address_without_prefix) <= 44:
                    if len(address_without_prefix) > 40:
                        address_without_prefix = address_without_prefix[:40]
                    else:
                        padding_needed = 40 - len(address_without_prefix)
                        address_without_prefix = '0' * padding_needed + address_without_prefix
                else:
                    logger.error(f"BNB address length too far from standard (40 chars): {address}")
                    return None
            
            # BNB format with 0x and lowercase
            formatted_address = '0x' + address_without_prefix.lower()
            logger.debug(f"Formatted BNB address: {address} -> {formatted_address}")
            return formatted_address
        
        # BSC Addresses
        elif normalized_chain == "BSC":
            # Clean address
            clean_address = address.strip()
            
            # BSC uses the same address format as ETH
            if clean_address.startswith('0x'):
                address_without_prefix = clean_address[2:]
            else:
                address_without_prefix = clean_address
            
            # Check if it's a valid hex string
            if not all(c in '0123456789abcdefABCDEF' for c in address_without_prefix):
                logger.error(f"Invalid characters in BSC address: {address}")
                return None
                
            # Ensure address is exactly 40 characters
            if len(address_without_prefix) != 40:
                logger.warning(f"Invalid BSC address length: {address} (length: {len(address_without_prefix)})")
                if 36 <= len(address_without_prefix) <= 44:
                    if len(address_without_prefix) > 40:
                        address_without_prefix = address_without_prefix[:40]
                    else:
                        padding_needed = 40 - len(address_without_prefix)
                        address_without_prefix = '0' * padding_needed + address_without_prefix
                else:
                    logger.error(f"BSC address length too far from standard (40 chars): {address}")
                    return None
            
            # BSC format with 0x and lowercase
            formatted_address = '0x' + address_without_prefix.lower()
            logger.debug(f"Formatted BSC address: {address} -> {formatted_address}")
            return formatted_address
            
        # Bitcoin addresses
        elif normalized_chain == "BTC":
            # Basic validation for Bitcoin address formats
            if address.startswith('bc1'):  # Bech32
                if not re.match(r'^bc1[a-zA-Z0-9]{25,87}$', address):
                    logger.warning(f"Invalid Bitcoin Bech32 address format: {address}")
                    return None
            elif address.startswith('1'):  # P2PKH
                if not re.match(r'^1[a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
                    logger.warning(f"Invalid Bitcoin P2PKH address format: {address}")
                    return None
            elif address.startswith('3'):  # P2SH
                if not re.match(r'^3[a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
                    logger.warning(f"Invalid Bitcoin P2SH address format: {address}")
                    return None
            else:
                logger.warning(f"Invalid Bitcoin address format: {address}")
                return None
            return address.lower()
            
        # Ripple (XRP) addresses - SPECIAL FORMAT
        elif normalized_chain == "XRP":
            # Clean the address
            clean_address = address.strip()
            
            # Ensure it starts with 'r'
            if not clean_address.startswith('r'):
                logger.warning(f"Invalid XRP address format (must start with 'r'): {address}")
                # Try to fix if it's a simple case of lowercase
                if clean_address.lower().startswith('r'):
                    clean_address = 'r' + clean_address[1:]
                    logger.info(f"Fixed XRP address prefix: {clean_address}")
                else:
                    return None
                    
            # Validate length (XRP addresses are typically 25-35 characters)
            if not (25 <= len(clean_address) <= 35):
                logger.warning(f"Invalid XRP address length: {address} (should be 25-35 chars)")
                return None
                
            # Check valid XRP base58 character set
            if not re.match(r'^r[a-zA-Z0-9]{24,34}$', clean_address):
                logger.warning(f"Invalid XRP address format: {address}")
                return None
            
            # XRP addresses should be returned as is, preserving case (typically starting with 'r')
            logger.debug(f"Formatted XRP address: {address} -> {clean_address}")
            return clean_address
            
        # Tron addresses - SPECIAL FORMAT
        elif normalized_chain == "TRX" or normalized_chain == "TRON":
            # Clean the address
            clean_address = address.strip()
            
            # TRON addresses must start with T
            if not clean_address.startswith('T'):
                # Try to fix simple case issues
                if clean_address.lower().startswith('t'):
                    # Only fix the first character, keep the rest of the address unchanged
                    clean_address = 'T' + clean_address[1:]
                    logger.info(f"Fixed TRON address prefix: {clean_address}")
                else:
                    logger.warning(f"Invalid Tron address format (must start with 'T'): {address}")
                    return None
                    
            # TRON addresses must be exactly 34 characters
            if len(clean_address) != 34:
                logger.warning(f"Invalid Tron address length: {address} (should be 34 chars)")
                return None
                
            # Validate TRON address format
            if not re.match(r'^T[A-Za-z0-9]{33}$', clean_address):
                logger.warning(f"Invalid Tron address format: {address}")
                return None
                
            # Return the address in its original format, only fixing the T prefix if needed
            # Do NOT convert to uppercase
            logger.debug(f"Formatted TRON address: {address} -> {clean_address}")
            return clean_address
            
        # Solana addresses - SPECIAL FORMAT
        elif normalized_chain == "SOL":
            # Clean the address
            clean_address = address.strip()
            
            # Validate Solana address length (typically 32-44 characters in base58)
            if not (32 <= len(clean_address) <= 44):
                logger.warning(f"Invalid Solana address length: {address} (should be 32-44 chars)")
                return None
                
            # Check base58 character set (a-z, A-Z, 0-9, excluding 0, O, I, l)
            base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
            if not all(c in base58_chars for c in clean_address):
                logger.warning(f"Invalid Solana address characters (must be base58): {address}")
                return None
                
            # Solana addresses are case-sensitive and should be preserved as is
            logger.debug(f"Formatted Solana address: {address} -> {clean_address}")
            return clean_address
            
        # Polkadot addresses
        elif normalized_chain == "DOT":
            # Basic validation for Polkadot address format
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{45,65}$', address):
                logger.warning(f"Invalid Polkadot address format: {address}")
                return None
            return address
            
        # For other chains, return as is but lowercase
        else:
            logger.warning(f"No validation rule for {normalized_chain}, returning address as is")
            return address
            
    except Exception as e:
        logger.error(f"Error validating address {address} for {normalized_chain}: {str(e)}")
        return None

def get_webhook_url():
    """
    Get the webhook URL from environment variable.
    
    Returns:
        str: The webhook URL to use for subscriptions
    """
    webhook_base_url = os.getenv('WEBHOOK_BASE_URL', DEFAULT_WEBHOOK_BASE_URL)
    # Ensure no trailing slash in base URL
    if webhook_base_url.endswith('/'):
        webhook_base_url = webhook_base_url[:-1]
    
    # Ensure endpoint starts with a slash
    endpoint = WEBHOOK_ENDPOINT
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    
    webhook_url = f"{webhook_base_url}{endpoint}"
    # Maximum length check for Tatum API
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.warning(f"Webhook URL is too long: {len(webhook_url)} chars, truncating")
        webhook_url = webhook_url[:MAX_URL_LENGTH]
    
    logger.debug(f"Using webhook URL: {webhook_url}")
    return webhook_url

def create_contract_subscription(contract_address, chain, webhook_url=None):
    """
    Create a subscription for a smart contract on Tatum.
    
    Args:
        contract_address (str): The address of the smart contract
        chain (str): The blockchain (ETH, BSC, MATIC, etc.)
        webhook_url (str, optional): The URL to send webhook notifications to.
                                     If None, the default webhook URL from app config will be used.
    
    Returns:
        dict: The subscription response data or None if failed
    """
    logger.info(f"Creating contract subscription for {contract_address} on {chain}")
    
    # Use the default webhook URL if none is provided
    if webhook_url is None:
        webhook_url = get_webhook_url()
    
    # Validate webhook URL format
    if not webhook_url.startswith(('http://', 'https://')):
        logger.error(f"Invalid webhook URL format: {webhook_url}. Must start with http:// or https://")
        return None
        
    # Ensure URL is not too long
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.warning(f"Webhook URL is too long: {len(webhook_url)} chars, truncating")
        webhook_url = webhook_url[:MAX_URL_LENGTH]
    
    # Normalize blockchain name
    normalized_chain = normalize_blockchain_name(chain)
    
    # Validate and format the contract address
    formatted_address = validate_and_format_address(contract_address, chain)
    if not formatted_address:
        logger.error(f"Invalid contract address format for {chain}: {contract_address}")
        return None
    
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "type": "CONTRACT_LOG_EVENT",
        "attr": {
            "address": formatted_address,
            "chain": normalized_chain,
            "url": webhook_url
        }
    }
    
    logger.debug(f"Sending request to Tatum API with payload: {json.dumps(payload)}")
    
    # Retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.post(
                f"{TATUM_API_BASE_URL}/subscription", 
                json=payload, 
                headers=headers,
                timeout=30  # Add timeout to prevent hanging requests
            )
            
            response_text = response.text
            
            if response.status_code == 200:
                subscription_data = response.json()
                logger.info(f"Successfully created subscription for contract {contract_address} on {chain}")
                logger.info(f"Subscription ID: {subscription_data.get('id')}")
                return subscription_data
            elif response.status_code == 400 and "already exists" in response_text:
                # Subscription already exists, which is fine
                logger.info(f"Subscription for contract {contract_address} on {chain} already exists")
                # Return a simulated success response
                return {"id": "existing", "message": "Subscription already exists"}
            elif response.status_code == 403:
                # API Key permissions issue
                logger.error(f"API Key permission error: {response_text}")
                # No retry for auth errors
                return None
            elif response.status_code == 401:
                # Authentication error
                logger.error(f"Authentication error: {response_text}")
                # No retry for auth errors
                return None
            elif response.status_code in [429, 500, 502, 503, 504]:
                # Rate limiting or server error, retry
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.warning(f"Rate limit or server error: {response.status_code}, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Failed to create subscription: {response.status_code} - {response_text}")
                return None
                
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"Network error creating subscription after {max_retries} retries: {str(e)}")
                return None
            
            wait_time = 2 ** retry_count
            logger.warning(f"Network error, retrying in {wait_time}s (attempt {retry_count}/{max_retries}): {str(e)}")
            time.sleep(wait_time)
        
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return None
    
    logger.error(f"Failed to create subscription after {max_retries} retries")
    return None

def list_subscriptions():
    """
    List all active subscriptions on Tatum.
    
    Returns:
        list: A list of all active subscriptions or empty list if failed
    """
    logger.info("Retrieving all active subscriptions")
    
    headers = {
        "x-api-key": TATUM_API_KEY
    }
    
    try:
        logger.debug(f"Sending GET request to {TATUM_API_BASE_URL}/subscription")
        response = requests.get(
            f"{TATUM_API_BASE_URL}/subscription?pageSize=50", 
            headers=headers
        )
        
        if response.status_code == 200:
            subscriptions = response.json()
            logger.info(f"Retrieved {len(subscriptions)} active subscriptions")
            return subscriptions
        else:
            logger.error(f"Failed to list subscriptions: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}")
        return []

def delete_subscription(subscription_id):
    """
    Delete a subscription by ID.
    
    Args:
        subscription_id (str): The ID of the subscription to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Attempting to delete subscription with ID: {subscription_id}")
    
    headers = {
        "x-api-key": TATUM_API_KEY
    }
    
    try:
        logger.debug(f"Sending DELETE request to {TATUM_API_BASE_URL}/subscription/{subscription_id}")
        response = requests.delete(
            f"{TATUM_API_BASE_URL}/subscription/{subscription_id}", 
            headers=headers
        )
        
        if response.status_code == 204:
            logger.info(f"Successfully deleted subscription {subscription_id}")
            return True
        else:
            logger.error(f"Failed to delete subscription: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting subscription: {str(e)}")
        return False

def create_address_subscription(wallet_address, chain, webhook_url=None):
    """
    Create a subscription for a wallet address on Tatum to monitor all transactions.
    
    Args:
        wallet_address (str): The wallet address to monitor
        chain (str): The blockchain (ETH, BSC, MATIC, etc.)
        webhook_url (str, optional): The URL to send webhook notifications to.
                                     If None, the default webhook URL from app config will be used.
    
    Returns:
        dict: The subscription response data or None if failed
    """
    logger.info(f"Creating address subscription for {wallet_address} on {chain}")
    
    # Use the default webhook URL if none is provided
    if webhook_url is None:
        webhook_url = get_webhook_url()
    
    # Validate webhook URL format
    if not webhook_url.startswith(('http://', 'https://')):
        logger.error(f"Invalid webhook URL format: {webhook_url}. Must start with http:// or https://")
        return None
        
    # Ensure URL is not too long
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.warning(f"Webhook URL is too long: {len(webhook_url)} chars, truncating")
        webhook_url = webhook_url[:MAX_URL_LENGTH]
    
    # Special case for BNB - log extra debug info
    if chain.upper() == "BNB":
        logger.info(f"Processing BNB subscription with special attention")
    
    # Normalize blockchain name
    normalized_chain = normalize_blockchain_name(chain)
    logger.info(f"Normalized chain for {chain}: {normalized_chain}")
    
    # Check if the blockchain is supported
    if normalized_chain is None:
        logger.error(f"Blockchain {chain} is not supported by Tatum API")
        return None
    
    # Validate and format the wallet address
    formatted_address = validate_and_format_address(wallet_address, chain)
    if not formatted_address:
        logger.error(f"Invalid wallet address format for {chain}: {wallet_address}")
        return None
        
    # Handle special formats based on blockchain
    if chain.upper() in ["TRX", "TRON"]:
        logger.info(f"Using original format for TRON address: {formatted_address}")
        # TRON addresses should maintain their original case format after validation
    elif chain.upper() == "XRP":
        logger.info(f"Using special format for XRP address: {formatted_address}")
        # XRP addresses should maintain their case
    elif chain.upper() == "SOL":
        logger.info(f"Using special format for Solana address: {formatted_address}")
        # Solana addresses are case-sensitive
    elif chain.upper() == "BNB":
        logger.info(f"Using BNB Chain address format: {formatted_address}")
        # Ensure BNB addresses use 0x prefix and are lowercase
        if formatted_address != formatted_address.lower() and formatted_address.startswith('0x'):
            formatted_address = formatted_address.lower()
    elif chain.upper() in ["ETH", "MATIC", "AVAX", "ARB", "BSC"]:
        # EVM addresses should be lowercase
        if formatted_address != formatted_address.lower() and formatted_address.startswith('0x'):
            formatted_address = formatted_address.lower()
            logger.debug(f"Converted EVM address to lowercase: {formatted_address}")
        
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Ensure we're using ADDRESS_TRANSACTION type for all wallet addresses
    payload = {
        "type": "ADDRESS_TRANSACTION",
        "attr": {
            "address": formatted_address,
            "chain": normalized_chain,
            "url": webhook_url
        }
    }
    
    logger.debug(f"Sending request to Tatum API with payload: {json.dumps(payload, indent=2)}")
    logger.info(f"Creating subscription for {formatted_address} on {normalized_chain}")
    
    # Retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.post(
                f"{TATUM_API_BASE_URL}/subscription", 
                json=payload, 
                headers=headers,
                timeout=30  # Add timeout to prevent hanging requests
            )
            
            response_text = response.text
            logger.debug(f"Response status: {response.status_code}, Response: {response_text}")
            
            if response.status_code == 200:
                subscription_data = response.json()
                logger.info(f"Successfully created subscription for address {formatted_address} on {chain}")
                logger.info(f"Subscription ID: {subscription_data.get('id')}")
                return subscription_data
            elif response.status_code == 400 and "already exists" in response_text:
                # Subscription already exists, which is fine
                logger.info(f"Subscription for address {formatted_address} on {chain} already exists")
                # Return a simulated success response
                return {"id": "existing", "message": "Subscription already exists"}
            elif response.status_code == 403 and "already exists" in response_text:
                # Tatum returns 403 for already existing subscriptions
                logger.info(f"Subscription for address {formatted_address} on {chain} already exists (403)")
                # Return a simulated success response
                return {"id": "existing", "message": "Subscription already exists (403)"}
            elif response.status_code == 403:
                # Other API Key permissions issue
                logger.error(f"API Key permission error: {response_text}")
                # No retry for auth errors
                return None
            elif response.status_code == 401:
                # Authentication error
                logger.error(f"Authentication error: {response_text}")
                # No retry for auth errors
                return None
            elif response.status_code == 400:
                # Validation failed
                logger.error(f"Validation failed for {chain} address {formatted_address}: {response_text}")
                
                # Special case for BNB
                if chain.upper() == "BNB":
                    if retry_count == 0:
                        logger.info(f"BNB validation failed, trying BSC as chain value instead")
                        # Try with BSC as chain value for BNB addresses
                        payload["attr"]["chain"] = "BSC"
                        retry_count += 1
                        continue
                # For certain blockchains, try some format corrections on validation failure
                elif chain.upper() in ["TRX", "TRON"]:
                    if retry_count == 0 and not "already exists" in response_text:
                        # Try with original format for Tron
                        if wallet_address != formatted_address:
                            logger.info(f"Trying original format for TRON address: {wallet_address}")
                            payload["attr"]["address"] = wallet_address
                            retry_count += 1
                            continue
                elif chain.upper() == "XRP":
                    if retry_count == 0 and not "already exists" in response_text:
                        # Try original address format if different from formatted
                        if wallet_address != formatted_address:
                            logger.info(f"Trying original format for XRP address: {wallet_address}")
                            payload["attr"]["address"] = wallet_address
                            retry_count += 1
                            continue
                elif chain.upper() == "SOL":
                    if retry_count == 0 and not "already exists" in response_text:
                        # Try original case-sensitive format
                        if wallet_address != formatted_address:
                            logger.info(f"Trying original case-sensitive format for Solana address: {wallet_address}")
                            payload["attr"]["address"] = wallet_address
                            retry_count += 1
                            continue
                
                return None
                
            elif response.status_code in [429, 500, 502, 503, 504]:
                # Rate limiting or server error, retry
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.warning(f"Rate limit or server error: {response.status_code}, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Failed to create address subscription: {response.status_code} - {response_text}")
                return None
                
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"Network error creating address subscription after {max_retries} retries: {str(e)}")
                return None
            
            wait_time = 2 ** retry_count
            logger.warning(f"Network error, retrying in {wait_time}s (attempt {retry_count}/{max_retries}): {str(e)}")
            time.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Error creating address subscription: {str(e)}")
            return None
    
    logger.error(f"Failed to create address subscription after {max_retries} retries")
    return None

def create_batch_address_subscription(addresses, chain, webhook_url=None):
    """
    Create individual subscriptions for multiple wallet addresses on Tatum.
    
    Args:
        addresses (list): List of wallet addresses to monitor
        chain (str): The blockchain (ETH, BSC, MATIC, etc.)
        webhook_url (str, optional): The URL to send webhook notifications to.
    
    Returns:
        list: List of created subscription data or empty list if all failed
    """
    if not addresses:
        logger.warning("No addresses provided for batch subscription")
        return []
    
    logger.info(f"Creating individual subscriptions for {len(addresses)} addresses on {chain}")
    
    # Use the default webhook URL if none is provided
    if webhook_url is None:
        webhook_url = get_webhook_url()
    
    # Validate webhook URL format
    if not webhook_url.startswith(('http://', 'https://')):
        logger.error(f"Invalid webhook URL format: {webhook_url}. Must start with http:// or https://")
        return []
        
    # Ensure URL is not too long
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.warning(f"Webhook URL is too long: {len(webhook_url)} chars, truncating")
        webhook_url = webhook_url[:MAX_URL_LENGTH]
    
    # Make sure we don't have duplicates
    unique_addresses = list(set(addresses))
    
    # Keep track of successful subscriptions
    results = []
    
    # Create individual subscriptions for each address
    for address in unique_addresses:
        subscription_data = create_address_subscription(address, chain, webhook_url)
        if subscription_data:
            results.append(subscription_data)
    
    logger.info(f"Successfully created {len(results)} out of {len(unique_addresses)} individual subscriptions for {chain}")
    return results

def group_addresses_by_blockchain(addresses_info):
    """
    Group wallet addresses by blockchain.
    
    Args:
        addresses_info (list): List of dictionaries with address information
    
    Returns:
        dict: Dictionary with blockchain symbols as keys and lists of addresses as values
    """
    grouped_addresses = {}
    
    for address_info in addresses_info:
        blockchain_symbol = address_info.get('blockchain_symbol')
        public_address = address_info.get('public_address')
        
        if blockchain_symbol and public_address:
            if blockchain_symbol not in grouped_addresses:
                grouped_addresses[blockchain_symbol] = []
            
            grouped_addresses[blockchain_symbol].append(public_address)
    
    return grouped_addresses

def create_batched_blockchain_subscriptions(addresses_info, webhook_url=None):
    """
    Create batch subscriptions for addresses grouped by blockchain.
    
    Args:
        addresses_info (list): List of dictionaries with address information
        webhook_url (str, optional): Webhook URL to use
        
    Returns:
        dict: Dictionary with blockchain names as keys and lists of subscription results as values
    """
    logger.info(f"Creating batch subscriptions for {len(addresses_info)} addresses")
    
    # Try to fix common issues with problematic addresses
    logger.info("Attempting to fix common issues with addresses")
    fixed_addresses_info = fix_problem_addresses(addresses_info)
    
    # Group addresses by blockchain
    grouped_addresses = group_addresses_by_blockchain(fixed_addresses_info)
    
    # Get existing subscriptions first to avoid duplicates
    logger.info("Fetching existing subscriptions to avoid duplicates")
    existing_subscriptions = list_subscriptions()
    
    # Create a map of existing address subscriptions by blockchain and address
    existing_address_map = {}
    
    for sub in existing_subscriptions:
        if sub.get('type') == 'ADDRESS_TRANSACTION':
            sub_chain = sub.get('attr', {}).get('chain')
            sub_address = sub.get('attr', {}).get('address', '').lower()
            
            if not sub_chain or not sub_address:
                continue
                
            # Create nested dict structure if needed
            if sub_chain not in existing_address_map:
                existing_address_map[sub_chain] = set()
                
            # Add this address to the set
            existing_address_map[sub_chain].add(sub_address)
    
    logger.info(f"Found {sum(len(addresses) for addresses in existing_address_map.values())} existing address subscriptions")
    
    # Track results per blockchain
    results = {}
    
    # Process each blockchain separately
    for blockchain, addresses in grouped_addresses.items():
        logger.info(f"Processing {len(addresses)} addresses for blockchain {blockchain}")
        
        # Skip if blockchain is not supported
        if blockchain.upper() not in BLOCKCHAIN_MAPPING:
            logger.warning(f"Skipping unsupported blockchain: {blockchain}")
            continue
        
        # Get normalized blockchain name
        normalized_chain = normalize_blockchain_name(blockchain)
        if normalized_chain is None:
            logger.warning(f"Blockchain {blockchain} is not supported by Tatum API")
            continue
            
        # Get existing addresses for this blockchain
        existing_addresses = existing_address_map.get(normalized_chain, set())
        logger.info(f"Found {len(existing_addresses)} existing subscriptions for {blockchain}")
        
        # Initialize results for this blockchain
        results[blockchain] = []
        
        # Process in batches of 50 addresses (Tatum maximum)
        batch_size = 50
        for i in range(0, len(addresses), batch_size):
            batch = addresses[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size+1} with {len(batch)} addresses on {blockchain}")
            
            # Create individual subscriptions for each address in batch
            batch_results = {
                "id": f"batch_{blockchain}_{int(time.time())}_{i//batch_size}",
                "addresses_count": 0,
                "successful_subscriptions": [],
                "skipped_subscriptions": 0
            }
            
            new_subscriptions_count = 0
            
            for address in batch:
                # Validate and format address with proper checksum
                formatted_address = validate_and_format_address(address, blockchain)
                if not formatted_address:
                    logger.warning(f"Skipping invalid address for {blockchain}: {address}")
                    continue
                
                # Check if this address already has a subscription
                if formatted_address.lower() in existing_addresses:
                    logger.info(f"Skipping already subscribed address: {formatted_address}")
                    batch_results["skipped_subscriptions"] += 1
                    continue
                
                # Create subscription for this address with ADDRESS_TRANSACTION type
                subscription_result = create_address_subscription(formatted_address, blockchain, webhook_url)
                
                if subscription_result:
                    batch_results["addresses_count"] += 1
                    batch_results["successful_subscriptions"].append({
                        "address": formatted_address,
                        "subscription_id": subscription_result.get("id", "unknown")
                    })
                    
                    # Add to existing addresses to avoid duplicates in future batches
                    existing_addresses.add(formatted_address.lower())
                    
                    # Count new subscriptions
                    if subscription_result.get("id") != "existing":
                        new_subscriptions_count += 1
            
            if batch_results["addresses_count"] > 0 or batch_results["skipped_subscriptions"] > 0:
                results[blockchain].append(batch_results)
                logger.info(f"Batch results: {batch_results['addresses_count']} new subscriptions, {batch_results['skipped_subscriptions']} skipped (already existing)")
                logger.info(f"Created {new_subscriptions_count} new address subscriptions for {blockchain} in batch {i//batch_size+1}")
    
    # Count total subscriptions and addresses
    total_new_subscriptions = sum(sum(1 for sub in batch["successful_subscriptions"] if sub.get("subscription_id") != "existing") 
                               for batches in results.values() 
                               for batch in batches)
    total_skipped = sum(batch["skipped_subscriptions"] for batches in results.values() for batch in batches)
    
    logger.info(f"Created a total of {total_new_subscriptions} new address subscriptions across {len(results)} blockchains")
    logger.info(f"Skipped {total_skipped} already existing subscriptions")
    
    return results

def create_batch_subscription(addresses, chain, webhook_url=None):
    """
    Create a batch subscription for multiple addresses at once on Tatum.
    
    Args:
        addresses (list): List of wallet addresses to monitor (max 50 per batch)
        chain (str): The blockchain (ETH, BSC, MATIC, etc.)
        webhook_url (str, optional): The URL to send webhook notifications to.
    
    Returns:
        dict: The subscription response data or None if failed
    """
    if not addresses:
        logger.warning("No addresses provided for batch subscription")
        return None
    
    if len(addresses) > 50:
        logger.warning(f"Too many addresses provided ({len(addresses)}), max is 50. Truncating to 50 addresses.")
        addresses = addresses[:50]
    
    logger.info(f"Creating batch subscription for {len(addresses)} addresses on {chain}")
    
    # Use the default webhook URL if none is provided
    if webhook_url is None:
        webhook_url = get_webhook_url()
    
    # Validate webhook URL format
    if not webhook_url.startswith(('http://', 'https://')):
        logger.error(f"Invalid webhook URL format: {webhook_url}. Must start with http:// or https://")
        return None
        
    # Ensure URL is not too long
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.warning(f"Webhook URL is too long: {len(webhook_url)} chars, truncating")
        webhook_url = webhook_url[:MAX_URL_LENGTH]
    
    # Normalize blockchain name
    normalized_chain = normalize_blockchain_name(chain)
    
    # Store batch results
    batch_results = {
        "id": f"batch_{chain}_{int(time.time())}",
        "addresses_count": 0,
        "successful_subscriptions": []
    }
    
    # Process each address individually to ensure proper checksumming and type
    for address in addresses:
        # Validate and format the address with proper checksum
        formatted_address = validate_and_format_address(address, chain)
        if not formatted_address:
            logger.warning(f"Skipping invalid address for {chain}: {address}")
            continue
            
        # Create subscription for this specific address
        subscription_result = create_address_subscription(formatted_address, chain, webhook_url)
        if subscription_result:
            batch_results["addresses_count"] += 1
            batch_results["successful_subscriptions"].append({
                "address": formatted_address,
                "subscription_id": subscription_result.get("id", "unknown")
            })
    
    if batch_results["addresses_count"] > 0:
        logger.info(f"Successfully created {batch_results['addresses_count']} address subscriptions for {chain}")
        return batch_results
    else:
        logger.error(f"Failed to create any address subscriptions for {chain}")
        return None

def register_new_addresses_for_webhook(addresses_info):
    """
    Register new wallet addresses with Tatum webhook service.
    This only adds addresses that are not already registered.
    
    Args:
        addresses_info (list): List of dictionaries with address information
        
    Returns:
        dict: Results of subscription operations
    """
    logger.info(f"Registering new addresses with Tatum webhook service")
    
    # Group by blockchain
    grouped_addresses = group_addresses_by_blockchain(addresses_info)
    
    # Get existing subscriptions
    existing_subscriptions = list_subscriptions()
    if not existing_subscriptions:
        logger.warning("Could not retrieve existing subscriptions, creating all new ones")
        return create_batched_blockchain_subscriptions(addresses_info)
        
    results = {}
    
    # Default chunk size for processing addresses
    chunk_size = 20
    
    # Process each blockchain
    for blockchain, addresses in grouped_addresses.items():
        logger.info(f"Processing {len(addresses)} addresses for blockchain {blockchain}")
        
        # Skip if no addresses for this blockchain
        if not addresses:
            continue
            
        # Find existing subscriptions for this blockchain
        blockchain_subscriptions = []
        for subscription in existing_subscriptions:
            if subscription.get('attr', {}).get('chain') == normalize_blockchain_name(blockchain):
                blockchain_subscriptions.append(subscription)
                
        logger.info(f"Found {len(blockchain_subscriptions)} existing subscriptions for {blockchain}")
        
        # If no subscriptions exist for this blockchain, create all new ones
        if not blockchain_subscriptions:
            logger.info(f"No existing subscriptions for {blockchain}, creating all new ones")
            
            # Create new subscriptions for each address
            for address in addresses:
                logger.info(f"Creating new subscription for address {address} on {blockchain}")
                create_address_subscription(address, blockchain)
            
            continue
            
        # Check if any addresses are already registered
        registered_addresses = set()
        for subscription in blockchain_subscriptions:
            registered_addresses.add(subscription.get('attr', {}).get('address', '').lower())
            
        # Filter out addresses that are already registered
        new_addresses = [address for address in addresses if address.lower() not in registered_addresses]
        
        logger.info(f"{len(addresses) - len(new_addresses)} addresses already registered, {len(new_addresses)} new addresses to add")
        
        # If all addresses are already registered, skip
        if not new_addresses:
            logger.info(f"All addresses for {blockchain} are already registered")
            continue
            
        # Create individual subscriptions for each new address
        for address in new_addresses:
            logger.info(f"Creating new subscription for address {address} on {blockchain}")
            create_address_subscription(address, blockchain)
    
    return results

def update_address_subscription(subscription_id, address, chain):
    """
    Update an existing address subscription with a new address.
    
    Args:
        subscription_id (str): The ID of the subscription to update
        address (str): The address to update
        chain (str): The blockchain symbol
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Updating subscription {subscription_id} with address on {chain}")
    
    # Normalize blockchain name
    normalized_chain = normalize_blockchain_name(chain)
    
    # Validate and format the address
    formatted_address = validate_and_format_address(address, chain)
    if not formatted_address:
        logger.error(f"Invalid address format for {chain}: {address}")
        return False
    
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "type": "ADDRESS_TRANSACTION",
        "attr": {
            "address": formatted_address,
            "chain": normalized_chain,
            "url": get_webhook_url()
        }
    }
    
    logger.debug(f"Sending PUT request to update subscription {subscription_id}")
    
    try:
        response = requests.put(
            f"{TATUM_API_BASE_URL}/subscription/{subscription_id}", 
            json=payload, 
            headers=headers
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"Successfully updated subscription {subscription_id}")
            return True
        else:
            logger.error(f"Failed to update subscription: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        return False

def verify_tatum_api_connection():
    """
    Verify if the connection to Tatum API works correctly.
    This function tests the API key and connectivity.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    logger.info("Verifying Tatum API connection...")
    
    headers = {
        "x-api-key": TATUM_API_KEY
    }
    
    try:
        # Try to list the first subscription as an API test
        response = requests.get(
            f"{TATUM_API_BASE_URL}/subscription?pageSize=1", 
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("✅ Tatum API connection successful")
            return True
        elif response.status_code == 403:
            logger.error(f"❌ Tatum API key permission error: {response.text}")
            return False
        elif response.status_code == 401:
            logger.error(f"❌ Tatum API authentication error: {response.text}")
            return False
        else:
            logger.error(f"❌ Tatum API error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Tatum API connection error: {str(e)}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Unexpected error testing Tatum API: {str(e)}")
        return False

def test_blockchain_subscriptions():
    """
    Test subscription for one sample address on each supported blockchain.
    This function helps diagnose issues with different blockchains.
    
    Returns:
        dict: Results for each blockchain with success or error details
    """
    logger.info("Testing subscription for sample addresses on each blockchain")
    
    # Define test addresses for each blockchain
    test_addresses = {
        "BTC": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",  # Example BTC address
        "ETH": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Example ETH address
        "MATIC": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Example MATIC address
        "BSC": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Example BSC address
        "AVAX": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Example AVAX address
        "SOL": "3zVobQ7svvd1L7cQH1mzCfLnBEku3UaLdRP6BAmtTa7D",  # Example SOL address
        "TRX": "TCAzzGQHKkRX7PkBZP8RDgNwY7KEcx56gy",  # Example TRX address
        "XRP": "rLW9gnQo7BQhU6igk5keqYnH3TVrCxGRzm"  # Example XRP address
    }
    
    # Store results
    results = {}
    
    # First verify API connection
    if not verify_tatum_api_connection():
        return {"error": "Failed to connect to Tatum API, check your API key and network connection"}
    
    # Test each blockchain
    for blockchain, address in test_addresses.items():
        logger.info(f"Testing {blockchain} subscription with address {address}")
        
        try:
            # Normalize blockchain name
            normalized_chain = normalize_blockchain_name(blockchain)
            
            # Validate the address format
            formatted_address = validate_and_format_address(address, blockchain)
            if not formatted_address:
                results[blockchain] = {
                    "success": False,
                    "error": f"Invalid address format for {blockchain}: {address}"
                }
                continue
                
            # Prepare request
            webhook_url = get_webhook_url()
            
            headers = {
                "x-api-key": TATUM_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "type": "ADDRESS_TRANSACTION",
                "attr": {
                    "address": formatted_address,
                    "chain": normalized_chain,
                    "url": webhook_url
                }
            }
            
            # Log the full request details for diagnosis
            logger.info(f"Test request for {blockchain}:")
            logger.info(f"URL: {TATUM_API_BASE_URL}/subscription")
            logger.info(f"Headers: x-api-key: [HIDDEN]")
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Make request
            response = requests.post(
                f"{TATUM_API_BASE_URL}/subscription", 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            # Process response
            logger.info(f"{blockchain} test response: {response.status_code}")
            logger.info(f"{blockchain} response text: {response.text}")
            
            if response.status_code == 200:
                # Success
                results[blockchain] = {
                    "success": True,
                    "message": "Subscription successful",
                    "subscription_id": response.json().get("id")
                }
            elif response.status_code == 400 and "already exists" in response.text:
                # Already exists - success
                results[blockchain] = {
                    "success": True,
                    "message": "Subscription already exists"
                }
            else:
                # Error
                results[blockchain] = {
                    "success": False,
                    "error": f"Error code {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            # Exception
            results[blockchain] = {
                "success": False,
                "error": f"Exception: {str(e)}"
            }
    
    # Summary
    successes = sum(1 for r in results.values() if r.get("success"))
    logger.info(f"Test summary: {successes}/{len(test_addresses)} blockchains successful")
    
    return results

def test_address_validation():
    """
    Test address validation for problematic blockchains to diagnose validation issues.
    
    Returns:
        dict: Results of validation tests for each test address
    """
    # Test addresses for each blockchain
    test_addresses = {
        "TRX": [
            "TVBLMXU...EJZXSA1PWS49GJGEQY39H3MDKPX",  # Address from log with issues
            "TVbLMxU...ejzxsa1pws49gjgeqy39h3mdkpx",  # Same address with different casing
            "TVbLMxUejzxsa1pws49gjgeqy39h3mdkpx",     # Fixed address with proper format
            "TCAzzGQHKkRX7PkBZP8RDgNwY7KEcx56gy"      # Example valid Tron address
        ],
        "XRP": [
            "rGSkZVM...CKpZdZnVrM3PwHkOZNYeHKSAk1u",  # Address from log with issues
            "rgskzvmckpzdznvrm3pwhkoznyehksak1u",     # Same in lowercase
            "rLW9gnQo7BQhU6igk5keqYnH3TVrCxGRzm"      # Example valid XRP address
        ],
        "SOL": [
            "3ZVobQ7...svvd1L7cQH1mzCfLnBEku3UaLdRP6BAmtTa7D",  # Address from log with issues
            "3zvobq7svvd1l7cqh1mzcflnbeku3ualdrp6bamtta7d",     # Same in lowercase
            "3zVobQ7svvd1L7cQH1mzCfLnBEku3UaLdRP6BAmtTa7D"      # Proper format
        ]
    }
    
    results = {}
    
    for blockchain, addresses in test_addresses.items():
        results[blockchain] = []
        
        for address in addresses:
            formatted_address = validate_and_format_address(address, blockchain)
            results[blockchain].append({
                "input": address,
                "output": formatted_address,
                "valid": formatted_address is not None
            })
            
    return results

def fix_problem_addresses(addresses_info):
    """
    Fix problematic addresses for specific blockchains based on common issues.
    
    Args:
        addresses_info (list): List of dictionaries with address information
    
    Returns:
        list: Updated list with fixed addresses where possible
    """
    fixed_addresses = []
    
    for address_info in addresses_info:
        blockchain = address_info.get('blockchain_symbol', '').upper()
        address = address_info.get('public_address', '')
        
        if not blockchain or not address:
            fixed_addresses.append(address_info)
            continue
            
        # Fix TRX/TRON addresses
        if blockchain == 'TRX' or blockchain == 'TRON':
            # Ensure address starts with 'T' and has proper format
            if not address.startswith('T') and len(address) >= 34:
                if address.lower().startswith('t'):
                    # Only fix the first character, keep the rest of the address unchanged
                    address = 'T' + address[1:]
                    logger.info(f"Fixed TRON address prefix: {address}")
        
        # Fix XRP addresses
        elif blockchain == 'XRP':
            # Ensure address starts with 'r'
            if not address.startswith('r') and len(address) >= 25:
                if address.lower().startswith('r'):
                    address = 'r' + address[1:]
                    logger.info(f"Fixed XRP address prefix: {address}")
        
        # Fix SOL addresses
        elif blockchain == 'SOL':
            # Make sure it's in proper base58 format
            # Just ensure it's within correct length range for now
            pass
            
        # Update the address in the info dict
        address_info['public_address'] = address
        fixed_addresses.append(address_info)
        
    return fixed_addresses

def create_batch_subscriptions(contracts_config):
    """
    Create batch subscriptions for contracts based on configuration.
    
    Args:
        contracts_config (dict): Configuration with contract addresses grouped by blockchain
        
    Returns:
        list: List of created subscription IDs
    """
    logger.info(f"Creating batch subscriptions for contract configuration")
    
    # Get the default webhook URL
    webhook_url = get_webhook_url()
    
    # Validate webhook URL
    if len(webhook_url) > MAX_URL_LENGTH:
        logger.error(f"Webhook URL too long ({len(webhook_url)} chars), must be <= {MAX_URL_LENGTH}")
        return []
        
    if not webhook_url.startswith(('http://', 'https://')):
        logger.error(f"Webhook URL must start with http:// or https://")
        return []
    
    # Track subscription IDs
    subscription_ids = []
    
    for blockchain, contracts in contracts_config.items():
        logger.info(f"Processing {len(contracts)} contracts for blockchain {blockchain}")
        
        for contract_address in contracts:
            subscription_data = create_contract_subscription(
                contract_address=contract_address,
                chain=blockchain,
                webhook_url=webhook_url
            )
            
            if subscription_data and 'id' in subscription_data:
                subscription_ids.append(subscription_data['id'])
            else:
                logger.error(f"Failed to create subscription for contract {contract_address} on {blockchain}")
    
    logger.info(f"Created {len(subscription_ids)} contract subscriptions")
    return subscription_ids

def test_bnb_subscription(bnb_address):
    """
    Test BNB subscription specifically to diagnose issues.
    
    Args:
        bnb_address (str): The BNB address to test
        
    Returns:
        dict: Results of test including all attempts and responses
    """
    logger.info(f"Testing BNB subscription for address: {bnb_address}")
    
    results = {
        "input_address": bnb_address,
        "attempts": []
    }
    
    # First try with BNB chain value
    try:
        webhook_url = get_webhook_url()
        formatted_address = validate_and_format_address(bnb_address, "BNB")
        
        if not formatted_address:
            results["error"] = "Failed to validate BNB address format"
            return results
            
        results["formatted_address"] = formatted_address
        
        # Try with BNB chain value
        headers = {
            "x-api-key": TATUM_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "type": "ADDRESS_TRANSACTION",
            "attr": {
                "address": formatted_address,
                "chain": "BNB",
                "url": webhook_url
            }
        }
        
        results["attempts"].append({
            "attempt": 1,
            "chain": "BNB",
            "payload": payload
        })
        
        response = requests.post(
            f"{TATUM_API_BASE_URL}/subscription", 
            json=payload, 
            headers=headers,
            timeout=30
        )
        
        results["attempts"][0]["status_code"] = response.status_code
        results["attempts"][0]["response"] = response.text
        
        # If failed, try with BSC chain value
        if response.status_code not in [200, 201]:
            payload["attr"]["chain"] = "BSC"
            
            results["attempts"].append({
                "attempt": 2,
                "chain": "BSC",
                "payload": payload
            })
            
            response = requests.post(
                f"{TATUM_API_BASE_URL}/subscription", 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            results["attempts"][1]["status_code"] = response.status_code
            results["attempts"][1]["response"] = response.text
        
        # Check if either attempt was successful
        if any(attempt.get("status_code") in [200, 201] for attempt in results["attempts"]):
            results["success"] = True
            successful_attempt = next((a for a in results["attempts"] if a.get("status_code") in [200, 201]), None)
            results["successful_chain"] = successful_attempt["chain"]
        else:
            results["success"] = False
            
        return results
        
    except Exception as e:
        logger.error(f"Error testing BNB subscription: {str(e)}")
        results["error"] = str(e)
        return results 