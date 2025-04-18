import os
import requests
import json
import re
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
    "DOT": "DOT",  # Polkadot is not directly supported in the same way
    "XRP": "ripple-mainnet",
    "BNB": "bsc-mainnet",
    "ARB": "arb-one-mainnet"
}

def normalize_blockchain_name(chain):
    """
    Normalize blockchain name to a format expected by Tatum API.
    
    Args:
        chain (str): Our internal blockchain name
        
    Returns:
        str: Normalized blockchain name for Tatum API
    """
    chain_upper = chain.upper() if chain else ""
    tatum_chain = BLOCKCHAIN_MAPPING.get(chain_upper, chain)
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
    if not address or not address.startswith('0x'):
        return address
    
    # Remove '0x' prefix for processing
    address = address.lower().replace('0x', '')
    
    try:
        import hashlib
        # Calculate keccak-256 hash of the lowercase address
        hash_addr = hashlib.sha3_256(address.encode('utf-8')).hexdigest()
        
        # Apply checksum
        checksum_addr = '0x'
        for i, char in enumerate(address):
            if char in '0123456789':
                # Numbers remain as is
                checksum_addr += char
            else:
                # Letters are uppercase if corresponding hash byte is 8 or higher
                hash_char = int(hash_addr[i], 16)
                if hash_char >= 8:
                    checksum_addr += char.upper()
                else:
                    checksum_addr += char
                    
        return checksum_addr
    except ImportError:
        logger.warning("hashlib.sha3_256 not available, using simplified checksum")
        # Fallback to a simplified version
        result = '0x'
        for i, char in enumerate(address):
            if char in '0123456789':
                result += char
            else:
                # Simple alternating pattern
                result += char.upper() if i % 2 == 0 else char
        return result

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
        # ETH, BSC, MATIC, AVAX, ARB all use same Ethereum address format
        if normalized_chain in ["ETH", "BSC", "MATIC", "AVAX", "ARB"]:
            # Validate it's a valid Ethereum address
            if not address.startswith('0x') or len(address) != 42:
                logger.warning(f"Invalid Ethereum address format: {address}")
                return None
                
            # Apply proper checksum
            checksummed = apply_checksum_to_eth_address(address)
            logger.debug(f"Applied checksum to address: {address} -> {checksummed}")
            return checksummed
            
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
            return address
            
        # Ripple (XRP) addresses
        elif normalized_chain == "XRP":
            # Basic validation for XRP address format
            if not re.match(r'^r[a-zA-Z0-9]{24,34}$', address):
                logger.warning(f"Invalid XRP address format: {address}")
                return None
            return address
            
        # Tron addresses
        elif normalized_chain == "TRX":
            # Basic validation for Tron address format
            if not re.match(r'^T[a-zA-Z0-9]{33}$', address):
                logger.warning(f"Invalid Tron address format: {address}")
                return None
            return address
            
        # Solana addresses
        elif normalized_chain == "SOL":
            # Basic validation for Solana address format
            if not re.match(r'^[a-zA-Z0-9]{32,44}$', address):
                logger.warning(f"Invalid Solana address format: {address}")
                return None
            return address
            
        # Polkadot addresses
        elif normalized_chain == "DOT":
            # Basic validation for Polkadot address format
            if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{45,65}$', address):
                logger.warning(f"Invalid Polkadot address format: {address}")
                return None
            return address
            
        # For other chains, return as is
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
            "chain": normalized_chain
        },
        "url": webhook_url
    }
    
    logger.debug(f"Sending request to Tatum API with payload: {payload}")
    
    try:
        response = requests.post(
            f"{TATUM_API_BASE_URL}/subscription", 
            json=payload, 
            headers=headers
        )
        
        if response.status_code == 200:
            subscription_data = response.json()
            logger.info(f"Successfully created subscription for contract {contract_address} on {chain}")
            logger.info(f"Subscription ID: {subscription_data.get('id')}")
            return subscription_data
        else:
            logger.error(f"Failed to create subscription: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
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
    
    # Normalize blockchain name
    normalized_chain = normalize_blockchain_name(chain)
    
    # Validate and format the wallet address
    formatted_address = validate_and_format_address(wallet_address, chain)
    if not formatted_address:
        logger.error(f"Invalid wallet address format for {chain}: {wallet_address}")
        return None
    
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
    
    logger.debug(f"Sending request to Tatum API with payload: {json.dumps(payload)}")
    
    try:
        response = requests.post(
            f"{TATUM_API_BASE_URL}/subscription", 
            json=payload, 
            headers=headers
        )
        
        response_text = response.text
        logger.debug(f"Response status: {response.status_code}, Response: {response_text}")
        
        if response.status_code == 200:
            subscription_data = response.json()
            logger.info(f"Successfully created subscription for address {wallet_address} on {chain}")
            logger.info(f"Subscription ID: {subscription_data.get('id')}")
            return subscription_data
        else:
            logger.error(f"Failed to create address subscription: {response.status_code} - {response_text}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating address subscription: {str(e)}")
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
    Create individual subscriptions for addresses grouped by blockchain.
    
    Args:
        addresses_info (list): List of dictionaries with address information
        webhook_url (str, optional): Webhook URL to use
        
    Returns:
        list: List of created subscription IDs
    """
    logger.info(f"Creating individual subscriptions for {len(addresses_info)} addresses")
    
    # Group addresses by blockchain
    grouped_addresses = group_addresses_by_blockchain(addresses_info)
    
    # Track successful subscriptions
    subscription_ids = []
    
    # Process each blockchain separately
    for blockchain, addresses in grouped_addresses.items():
        logger.info(f"Processing {len(addresses)} addresses for blockchain {blockchain}")
        
        # Skip if blockchain is not supported
        if blockchain.upper() not in BLOCKCHAIN_MAPPING:
            logger.warning(f"Skipping unsupported blockchain: {blockchain}")
            continue
            
        # Process in smaller chunks to avoid rate limiting
        chunk_size = 20  # Process 20 addresses at a time
        for i in range(0, len(addresses), chunk_size):
            chunk = addresses[i:i+chunk_size]
            logger.info(f"Creating subscriptions for chunk of {len(chunk)} addresses on {blockchain}")
            
            # Create subscriptions for this chunk
            subscription_results = create_batch_address_subscription(chunk, blockchain, webhook_url)
            
            # Extract subscription IDs from results
            for result in subscription_results:
                if 'id' in result:
                    subscription_ids.append(result['id'])
    
    logger.info(f"Created {len(subscription_ids)} individual subscriptions")
    return subscription_ids

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
            "chain": normalized_chain
        },
        "url": get_webhook_url()
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