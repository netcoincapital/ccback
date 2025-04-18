import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import and_, or_
from datetime import datetime
from decimal import Decimal
import os

# Import the logging configuration
from utils.logging_config import get_logger

# Setup logging
logger = get_logger(__file__)

# تعریف URL پایه API تاتوم
TATUM_API_BASE_URL = "https://api.tatum.io/v3"

# Create a Blueprint for webhook routes
webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook/tatum/transaction', methods=['POST'])
def handle_tatum_transaction():
    """
    Handle incoming webhook notifications from Tatum for smart contract events or address transactions.
    """
    # Check if the request has JSON data
    if not request.is_json:
        logger.error("Received non-JSON webhook data")
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    # Get the webhook data
    webhook_data = request.json
    logger.info(f"🔥 WEBHOOK RECEIVED 🔥: {webhook_data}")
    
    try:
        # Debug database connection before processing
        try:
            from sqlalchemy import create_engine, text
            from config import DATABASE_URL
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info(f"Database connection test: {result.scalar()}")
        except Exception as db_error:
            logger.error(f"Database connection test failed: {str(db_error)}", exc_info=True)
        
        # Extract relevant information
        blockchain = webhook_data.get('chain')
        # Convert Tatum blockchain name to our internal format if needed
        blockchain = convert_tatum_chain_to_internal_format(blockchain)
        
        # Use 'txId' instead of 'transactionId' for Tatum webhooks
        transaction_id = webhook_data.get('txId') or webhook_data.get('transactionId')
        
        if not transaction_id:
            logger.error("Missing transaction ID in webhook data")
            return jsonify({"status": "error", "message": "Missing transaction ID"}), 200
            
        logger.info(f"📝 Processing webhook for transaction {transaction_id} on {blockchain}")
        
        # Handle different webhook types
        webhook_type = webhook_data.get('type')
        subscription_type = webhook_data.get('subscriptionType')
        
        logger.info(f"Webhook type: {webhook_type}, Subscription type: {subscription_type}")
        
        # Extract sender and recipient addresses
        from_address = webhook_data.get('from') or webhook_data.get('address')
        to_address = webhook_data.get('to') or webhook_data.get('counterAddress')
        value = webhook_data.get('value') or webhook_data.get('amount', '0')
        
        logger.info(f"Transaction details - From: {from_address}, To: {to_address}, Value: {value}, Type: {webhook_type}")
        
        # Process based on type
        if webhook_type == 'CONTRACT_LOG_EVENT' or subscription_type == 'CONTRACT_LOG_EVENT':
            # This is a smart contract event
            contract_address = webhook_data.get('address')
            log_events = webhook_data.get('logs', [])
            
            logger.info(f"Contract event on {blockchain} for contract {contract_address}")
            logger.info(f"Transaction ID: {transaction_id}")
            logger.debug(f"Log events: {log_events}")
            
            # Process the log events
            process_contract_log_events(blockchain, contract_address, transaction_id, log_events, webhook_data)
            
        elif webhook_type == 'ADDRESS_TRANSACTION' or subscription_type == 'ADDRESS_TRANSACTION' or webhook_type == 'fee' or webhook_type == 'native':
            # This is a wallet address transaction or fee transaction
            logger.info(f"Address transaction on {blockchain} with type {webhook_type}")
            logger.info(f"From: {from_address}, To: {to_address}, Value: {value}")
            logger.info(f"Transaction ID: {transaction_id}")
            
            # Process the address transaction
            process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data)
        
        else:
            logger.warning(f"Unsupported webhook/subscription type: {webhook_type}/{subscription_type}")
            return jsonify({"status": "ignored", "reason": "Unsupported webhook type"}), 200
        
        logger.info(f"Successfully processed webhook for transaction {transaction_id}")
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        # Still return 200 to avoid Tatum retrying
        return jsonify({"status": "error", "message": str(e)}), 200

def convert_tatum_chain_to_internal_format(chain):
    """
    Convert Tatum blockchain name format to our internal format.
    
    Args:
        chain (str): The blockchain name from Tatum webhook
        
    Returns:
        str: Blockchain name in our internal format
    """
    if not chain:
        return None
    
    # Define mapping from Tatum chain format to our internal format
    TATUM_TO_INTERNAL_MAPPING = {
        "ethereum-mainnet": "ETH",
        "bitcoin-mainnet": "BTC",
        "polygon-mainnet": "MATIC",
        "bsc-mainnet": "BSC",
        "avax-mainnet": "AVAX",
        "solana-mainnet": "SOL",
        "tron-mainnet": "TRX",
        "ripple-mainnet": "XRP",
        "arb-one-mainnet": "ARB"
    }
    
    # Additional variants
    BSC_VARIANTS = ["BSC", "BNB", "Binance", "BINANCE", "bsc", "bnb", "binance"]
    ETH_VARIANTS = ["ETH", "Ethereum", "ETHEREUM", "eth", "ethereum"]
    
    # Log the original chain name for debugging
    logger.info(f"Original chain name from Tatum: {chain}")
    
    # Check if the chain is already in our format (just the symbol)
    if chain in ["ETH", "BTC", "MATIC", "BSC", "AVAX", "SOL", "TRX", "XRP", "ARB"]:
        logger.debug(f"Chain {chain} is already in internal format")
        return chain
    
    # Try to convert from Tatum format to our format
    internal_chain = TATUM_TO_INTERNAL_MAPPING.get(chain)
    if internal_chain:
        logger.info(f"Converted Tatum chain format '{chain}' to internal format '{internal_chain}'")
        return internal_chain
    
    # If we can't convert, try to extract the blockchain name from the chain
    if "-" in chain:
        # Try to extract just the chain name from formats like "xxx-mainnet"
        chain_parts = chain.split("-")
        if chain_parts[0].upper() in ["ETH", "BTC", "MATIC", "BSC", "AVAX", "SOL", "TRX", "XRP", "ARB"]:
            logger.info(f"Extracted chain '{chain_parts[0].upper()}' from '{chain}'")
            return chain_parts[0].upper()
        
        # Handle special cases
        if chain_parts[0].lower() == "ethereum":
            return "ETH"
        elif chain_parts[0].lower() == "bitcoin":
            return "BTC"
        elif chain_parts[0].lower() == "polygon":
            return "MATIC"
        elif chain_parts[0].lower() == "bsc":
            return "BSC"
        elif chain_parts[0].lower() == "avax":
            return "AVAX"
        elif chain_parts[0].lower() == "solana":
            return "SOL"
        elif chain_parts[0].lower() == "tron":
            return "TRX"
        elif chain_parts[0].lower() == "ripple":
            return "XRP"
        elif chain_parts[0].lower() == "arb":
            return "ARB"
    
    # Check for BSC variants
    if chain.lower() in [v.lower() for v in BSC_VARIANTS]:
        logger.info(f"Matched chain '{chain}' to BSC variant")
        return "BSC"
    
    # Check for ETH variants
    if chain.lower() in [v.lower() for v in ETH_VARIANTS]:
        logger.info(f"Matched chain '{chain}' to ETH variant")
        return "ETH"
    
    # If we couldn't convert it, log a warning and return the original value
    logger.warning(f"Could not convert Tatum chain format '{chain}' to internal format")
    return chain

def process_contract_log_events(blockchain, contract_address, transaction_id, log_events, webhook_data):
    """
    Process log events from a smart contract.
    
    Args:
        blockchain (str): The blockchain (ETH, BSC, etc.)
        contract_address (str): The contract address
        transaction_id (str): Transaction hash/ID
        log_events (list): List of log events
        webhook_data (dict): The complete webhook data
    """
    logger.info(f"Processing log events for transaction {transaction_id} on contract {contract_address}")
    
    # Get the list of user wallet addresses from the database
    user_addresses = get_user_addresses_from_db()
    logger.debug(f"Retrieved {len(user_addresses)} user addresses from database")
    
    # Check if this transaction is relevant to any of our users
    is_relevant = False
    relevant_addresses = []
    
    for log_idx, log in enumerate(log_events):
        # Extract data and topics from the log
        log_data = log.get('data', '')
        topics = log.get('topics', [])
        
        logger.debug(f"Processing log #{log_idx} with {len(topics)} topics")
        
        # Check if any of our user wallet addresses are in the log data or topics
        for address_info in user_addresses:
            public_address = address_info['public_address']
            if is_address_in_log(public_address, log_data, topics):
                is_relevant = True
                relevant_addresses.append(address_info)
                logger.info(f"Found relevant address {public_address} in log data/topics")
    
    if is_relevant:
        logger.info(f"Found relevant transaction for {len(relevant_addresses)} user addresses")
        
        # Extract additional information
        block_number = webhook_data.get('blockHeight')
        timestamp = webhook_data.get('timestamp')
        
        logger.debug(f"Transaction details: Block: {block_number}, Timestamp: {timestamp}")
        
        # Save transaction to database
        save_transaction_to_db(
            blockchain=blockchain,
            contract_address=contract_address,
            transaction_id=transaction_id,
            relevant_addresses=relevant_addresses,
            block_number=block_number,
            timestamp=timestamp,
            webhook_data=webhook_data
        )
        
        # Update balances
        for address_info in relevant_addresses:
            logger.debug(f"Updating balance for address {address_info['public_address']}")
            update_wallet_balance(address_info, blockchain)
        
        # Send notification to frontend
        notify_frontend(
            transaction_type='contract_event',
            transaction_id=transaction_id,
            relevant_addresses=relevant_addresses,
            webhook_data=webhook_data
        )
    else:
        logger.info("Transaction is not relevant to any of our users")

def process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data):
    """
    Process a transaction between addresses.
    
    Args:
        blockchain (str): The blockchain (ETH, BSC, etc.)
        from_address (str): Sender address
        to_address (str): Recipient address
        value (str): Transaction value
        transaction_id (str): Transaction hash/ID
        webhook_data (dict): The complete webhook data
    """
    logger.info(f"Processing address transaction {transaction_id} on {blockchain}")
    
    # بررسی نوع وبهوک در اولین قدم - خیلی مهم!
    webhook_type = webhook_data.get('type')
    logger.info(f"Webhook type: {webhook_type}")
    
    # بررسی مخصوص برای وبهوک‌های نوع 'fee'
    if webhook_type == 'fee':
        logger.info(f"*** DETECTED FEE WEBHOOK *** for transaction {transaction_id}: {webhook_data.get('amount')}")
        
        # جایگزین کردن مقدار منفی با مقدار مثبت برای کارمزد
        fee_amount = webhook_data.get('amount')
        if fee_amount and fee_amount.startswith('-'):
            fee_amount = fee_amount[1:]  # حذف علامت منفی
            logger.info(f"Converted negative fee amount to positive: {fee_amount}")
        
        # به‌روزرسانی تراکنش اصلی در دیتابیس
        result = update_transaction_fee_in_db(transaction_id, fee_amount)
        if result:
            logger.info(f"✅ Successfully updated fee {fee_amount} for transaction {transaction_id}")
        else:
            logger.warning(f"❌ Failed to update fee for transaction {transaction_id}")
        
        # تراکنش کارمزد را به عنوان تراکنش جداگانه در دیتابیس ذخیره نمی‌کنیم
        return
    
    # Get the list of user wallet addresses from the database
    user_addresses = get_user_addresses_from_db()
    logger.debug(f"Retrieved {len(user_addresses)} user addresses from database")
    
    # Check if this transaction is relevant to any of our users
    relevant_addresses = []
    
    # Create a dictionary for fast lookup - normalize addresses to lowercase
    address_dict = {address_info['public_address'].lower(): address_info for address_info in user_addresses}
    
    # Extract additional information - handle new Tatum webhook field names
    block_number = webhook_data.get('blockNumber') or webhook_data.get('blockHeight')
    timestamp = webhook_data.get('timestamp')
    
    # Правильно получаем символ токена из webhook
    token_symbol = webhook_data.get('tokenSymbol', None)
    
    # В Tatum webhooks, 'asset' может содержать имя токена или адрес контракта
    token_contract = webhook_data.get('asset', None)
    
    # Извлекаем значение fee из webhook
    fee_value = webhook_data.get('fee', None)
    
    # اگر fee در پاسخ وبهوک موجود نباشد، جزئیات تراکنش را از API تاتوم دریافت می‌کنیم
    if fee_value is None and transaction_id and blockchain:
        fee_value = get_transaction_fee_from_tatum(transaction_id, blockchain)
    
    # Проверяем, если 'asset' содержит символ блокчейна, перемещаем его в token_symbol
    if token_contract in ['ETH', 'TRON', 'BNB', 'MATIC', 'BSC']:
        token_symbol = token_contract
        token_contract = None
    
    # Use value provided to function or from webhook
    amount = value or webhook_data.get('amount', '0')
    
    logger.debug(f"Transaction details: Block: {block_number}, Timestamp: {timestamp}")
    logger.debug(f"Token info: Symbol: {token_symbol}, Asset/Contract: {token_contract}")
    
    # Direct address from Tatum webhook
    webhook_address = webhook_data.get('address')
    counter_address = webhook_data.get('counterAddress')
    
    # Log all potential addresses for debugging
    logger.info(f"Address candidates: from={from_address}, to={to_address}, address={webhook_address}, counter={counter_address}")
    
    # First check the new Tatum webhook format
    if webhook_address and counter_address:
        webhook_address_lower = webhook_address.lower()
        counter_address_lower = counter_address.lower()
        
        # Check if webhook address is one of our user addresses
        if webhook_address_lower in address_dict:
            address_info = address_dict[webhook_address_lower]
            # This is our address sending to counterAddress
            address_info['direction'] = 'outbound'
            relevant_addresses.append(address_info)
            logger.info(f"Found our address {webhook_address} in transaction (as 'address' field)")
            
            # Set from_address to ensure correct data in database
            if not from_address:
                from_address = webhook_address
                
        # Check if counter address is one of our user addresses
        if counter_address_lower in address_dict:
            address_info = address_dict[counter_address_lower]
            # This is counterAddress sending to our address
            address_info['direction'] = 'inbound'
            relevant_addresses.append(address_info)
            logger.info(f"Found our address {counter_address} in transaction (as 'counterAddress' field)")
            
            # Set to_address to ensure correct data in database
            if not to_address:
                to_address = counter_address
    
    # Then check traditional from/to format as backup
    if from_address and from_address.lower() in address_dict:
        address_lower = from_address.lower()
        # Check if this address was already processed from webhook_address
        if not any(a['public_address'].lower() == address_lower for a in relevant_addresses):
            address_info = address_dict[address_lower]
            address_info['direction'] = 'outbound'
            relevant_addresses.append(address_info)
            logger.info(f"Found sender address {from_address} in our user addresses")
    
    if to_address and to_address.lower() in address_dict:
        address_lower = to_address.lower()
        # Check if this address was already processed from counter_address
        if not any(a['public_address'].lower() == address_lower for a in relevant_addresses):
            address_info = address_dict[address_lower]
            address_info['direction'] = 'inbound'
            relevant_addresses.append(address_info)
            logger.info(f"Found recipient address {to_address} in our user addresses")
    
    # Special handling for fee transactions
    if webhook_data.get('type') == 'fee' and webhook_address and webhook_address.lower() in address_dict:
        address_lower = webhook_address.lower()
        # Check if this address was already processed
        if not any(a['public_address'].lower() == address_lower for a in relevant_addresses):
            address_info = address_dict[address_lower]
            address_info['direction'] = 'outbound'  # Fees are always outbound
            relevant_addresses.append(address_info)
            logger.info(f"Found address {webhook_address} in fee transaction")
    
    if relevant_addresses:
        logger.info(f"Found relevant transaction for {len(relevant_addresses)} user addresses")
        
        # Более точное определение токеновой транзакции
        native_assets = ['TRON', 'ETH', 'BNB', 'MATIC', 'BSC']
        is_token_transaction = token_contract is not None and token_contract not in native_assets
        
        if is_token_transaction:
            logger.info(f"This is a token transaction: Token {token_symbol or 'Unknown'}, Contract: {token_contract or 'Unknown'}")
            # Try to get token details from the database
            token_info = get_token_info(token_contract, blockchain, token_symbol)
            if token_info:
                logger.debug(f"Found token info in database: {token_info}")
                token_symbol = token_info.get('symbol', token_symbol)
                token_contract = token_info.get('contract_address', token_contract)
        else:
            # Если это нативная транзакция, перемещаем символ блокчейна в token_symbol
            logger.info(f"This is a native coin transaction on {blockchain}")
            if not token_symbol and blockchain:
                token_symbol = blockchain
        
        # Handle special case for fee transactions
        if webhook_data.get('type') == 'fee':
            asset_type = 'fee'
        else:
            # Determine asset type
            asset_type = 'token' if is_token_transaction else 'native'
        
        # If we have a fee transaction with missing from_address, set it to the webhook address
        if asset_type == 'fee' and not from_address and webhook_address:
            from_address = webhook_address
            logger.info(f"Using webhook address {webhook_address} as from_address for fee transaction")
        
        # Save transaction to database
        save_transaction_to_db(
            blockchain=blockchain,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            transaction_id=transaction_id,
            relevant_addresses=relevant_addresses,
            block_number=block_number,
            timestamp=timestamp,
            token_symbol=token_symbol,
            token_contract=token_contract,
            asset_type=asset_type,
            fee=fee_value,
            webhook_data=webhook_data
        )
        
        # اطمینان از ثبت لاگ برای ردیابی بهتر
        logger.info(f"Transaction {transaction_id} saved to database, now updating fee and status")
        
        # به روزرسانی کارمزد و وضعیت تراکنش با استفاده از اطلاعات جدید از API تاتوم
        try:
            update_transaction_fee_and_status(transaction_id, blockchain)
            logger.info(f"Successfully updated fee and status for transaction {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to update fee and status for transaction {transaction_id}: {str(e)}", exc_info=True)
        
        # Update balances for affected addresses
        for address_info in relevant_addresses:
            logger.debug(f"Updating balance for address {address_info['public_address']}")
            update_wallet_balance(address_info, blockchain, token_contract, token_symbol)
        
        # Send notification to frontend
        notify_frontend(
            transaction_type='address_transaction',
            transaction_id=transaction_id,
            relevant_addresses=relevant_addresses,
            webhook_data=webhook_data
        )
    else:
        logger.info("Transaction is not relevant to any of our users")

def is_address_in_log(address, log_data, topics):
    """
    Check if an address is mentioned in the log data or topics.
    
    Args:
        address (str): The wallet address to check
        log_data (str): The log data
        topics (list): The log topics
    
    Returns:
        bool: True if the address is found in the log, False otherwise
    """
    address = address.lower()
    
    # Check in log data
    if address in log_data.lower():
        logger.debug(f"Found address {address} in log data")
        return True
    
    # Check in topics
    for idx, topic in enumerate(topics):
        if address in topic.lower():
            logger.debug(f"Found address {address} in topic #{idx}")
            return True
    
    return False

def get_user_addresses_from_db():
    """
    Get all user wallet addresses from the database.
    Returns a list of dictionaries with address information.
    
    Returns:
        list: List of dictionaries with address information
    """
    logger.info("Fetching user addresses from database")
    
    from database.Address import Address
    from database.Blockchains import Blockchains
    from database.wallets import Wallets
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from database.base import Base
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    
    try:
        # Create engine and session
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # Query to get all addresses with their blockchain and wallet information
            query = select(
                Address.AddressID,
                Address.PublicAddress,
                Address.WalletID,
                Address.BlockchainID,
                Blockchains.BlockchainName,
                Blockchains.Symbol.label('BlockchainSymbol')
            ).join(
                Blockchains, Address.BlockchainID == Blockchains.BlockchainID
            ).join(
                Wallets, Address.WalletID == Wallets.WalletID
            )
            
            result = session.execute(query).all()
            
            # Convert result to list of dictionaries
            addresses = []
            for row in result:
                addresses.append({
                    'address_id': row.AddressID,
                    'public_address': row.PublicAddress,
                    'wallet_id': row.WalletID,
                    'blockchain_id': row.BlockchainID,
                    'blockchain_name': row.BlockchainName,
                    'blockchain_symbol': row.BlockchainSymbol
                })
            
            logger.info(f"Retrieved {len(addresses)} addresses from database")
            return addresses
    except Exception as e:
        logger.error(f"Error fetching user addresses: {str(e)}", exc_info=True)
        return []

def save_transaction_to_db(blockchain, transaction_id, relevant_addresses, webhook_data, **kwargs):
    """
    Save transaction details to the database.
    
    Args:
        blockchain (str): The blockchain symbol (ETH, BSC, etc.)
        transaction_id (str): Transaction hash/ID
        relevant_addresses (list): List of relevant address info dictionaries
        webhook_data (dict): Complete webhook data
        **kwargs: Additional transaction details like from_address, to_address, amount, etc.
    """
    logger.info(f"💾 Saving transaction {transaction_id} to database with {len(relevant_addresses)} relevant addresses")
    
    # Log important parameters for debugging
    logger.info(f"Transaction parameters: blockchain={blockchain}, txid={transaction_id}")
    logger.info(f"Additional parameters: {kwargs}")
    
    from database.Transfers import Transfers
    from database.Blockchains import Blockchains
    from database.users import Users
    from database.wallets import Wallets
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from database.base import Base
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    from datetime import datetime
    
    try:
        # Debug the database URL (without revealing sensitive info)
        db_url_parts = DATABASE_URL.split("://")
        if len(db_url_parts) >= 2:
            db_type = db_url_parts[0]
            db_creds = db_url_parts[1].split("@")
            if len(db_creds) >= 2:
                masked_url = f"{db_type}://****@{db_creds[-1]}"
                logger.info(f"Using database connection: {masked_url}")
        
        # Create engine and session
        engine = create_engine(DATABASE_URL)
        logger.info("Database engine created")
        
        with Session(engine) as session:
            logger.info("Database session started")
            
            # Dump all blockchains in the database for debugging
            try:
                logger.info("Dumping all blockchains from database for debugging:")
                blockchains_query = select(Blockchains.BlockchainID, Blockchains.BlockchainName, Blockchains.Symbol)
                all_blockchains = session.execute(blockchains_query).fetchall()
                for bc in all_blockchains:
                    logger.info(f"ID: {bc[0]}, Name: {bc[1]}, Symbol: {bc[2]}")
            except Exception as dump_error:
                logger.error(f"Error dumping blockchains: {str(dump_error)}")
            
            # Try different variations of the blockchain name
            blockchain_variations = [
                blockchain,  # Original
                blockchain.upper(),  # Uppercase
                blockchain.lower(),  # Lowercase
                blockchain.replace('-mainnet', ''),  # Remove -mainnet suffix
                blockchain.split('-')[0] if '-' in blockchain else blockchain,  # Get first part before dash
            ]
            
            if blockchain.lower() == 'bsc-mainnet' or blockchain.lower() == 'bsc':
                blockchain_variations.extend(['BNB', 'Binance', 'BINANCE'])
            elif blockchain.lower() == 'eth-mainnet' or blockchain.lower() == 'ethereum-mainnet' or blockchain.lower() == 'eth':
                blockchain_variations.extend(['ETH', 'Ethereum', 'ETHEREUM'])
            
            logger.info(f"Trying blockchain variations: {blockchain_variations}")
            
            # Try each variation
            blockchain_id = None
            found_blockchain = None
            
            for bc_var in blockchain_variations:
                logger.info(f"Trying to find blockchain with Symbol = '{bc_var}'")
                blockchain_query = select(Blockchains.BlockchainID).where(
                    Blockchains.Symbol == bc_var
                )
                blockchain_id_result = session.execute(blockchain_query).first()
                
                if blockchain_id_result:
                    blockchain_id = blockchain_id_result[0]
                    found_blockchain = bc_var
                    logger.info(f"Found blockchain ID {blockchain_id} for symbol {bc_var}")
                    break
                    
                # Try by name too
                logger.info(f"Trying to find blockchain with BlockchainName = '{bc_var}'")
                blockchain_query = select(Blockchains.BlockchainID).where(
                    Blockchains.BlockchainName == bc_var
                )
                blockchain_id_result = session.execute(blockchain_query).first()
                
                if blockchain_id_result:
                    blockchain_id = blockchain_id_result[0]
                    found_blockchain = bc_var
                    logger.info(f"Found blockchain ID {blockchain_id} for name {bc_var}")
                    break
            
            if not blockchain_id:
                logger.error(f"Could not find blockchain ID for any variation of {blockchain}")
                return
            
            # Extract additional information from kwargs
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            amount = kwargs.get('amount', '0')
            block_number = kwargs.get('block_number')
            timestamp_str = kwargs.get('timestamp')
            token_symbol = kwargs.get('token_symbol')
            token_contract = kwargs.get('token_contract', kwargs.get('contract_address'))
            fee = kwargs.get('fee')
            
            logger.info(f"Preparing transaction data: amount={amount}, block_number={block_number}")
            
            # Convert timestamp string to datetime if available
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    logger.info(f"Parsed timestamp: {timestamp}")
                except ValueError:
                    logger.warning(f"Could not parse timestamp: {timestamp_str}")
                    # Если не удалось распарсить, используем текущее время
                    timestamp = datetime.utcnow()
                    logger.info(f"Using current time as fallback: {timestamp}")
            else:
                # Если timestamp не предоставлен, используем текущее время
                timestamp = datetime.utcnow()
                logger.info(f"No timestamp provided, using current time: {timestamp}")
            
            # Determine asset type (native, token, or fee)
            # Use provided asset_type or determine based on token_contract
            asset_type = kwargs.get('asset_type')
            if not asset_type:
                if webhook_data.get('type') == 'fee':
                    asset_type = 'fee'
                elif token_contract and token_contract not in ['ETH', 'TRON', 'BNB', 'MATIC', 'BSC']:
                    asset_type = 'token'
                else:
                    asset_type = 'native'
            
            # Дополнительная проверка и коррекция token_symbol и token_contract
            if asset_type == 'native':
                # Если это нативная транзакция, убедимся, что token_contract не заполнен
                # а token_symbol содержит символ блокчейна
                if token_contract in ['ETH', 'TRON', 'BNB', 'MATIC', 'BSC']:
                    token_symbol = token_contract
                    token_contract = None
                elif not token_symbol and blockchain:
                    token_symbol = blockchain
            
            logger.info(f"Asset type determined as: {asset_type}")
            logger.info(f"Final token_symbol: {token_symbol}, token_contract: {token_contract}")
            
            # Get txId as a fallback for transaction_id
            if not transaction_id and webhook_data.get('txId'):
                transaction_id = webhook_data.get('txId')
                logger.info(f"Using txId from webhook data: {transaction_id}")
            
            # Create explorer URL based on blockchain
            explorer_url = None
            if found_blockchain in ['ETH', 'Ethereum', 'ETHEREUM']:
                explorer_url = f"https://etherscan.io/tx/{transaction_id}"
            elif found_blockchain in ['BSC', 'BNB', 'Binance', 'BINANCE']:
                explorer_url = f"https://bscscan.com/tx/{transaction_id}"
            elif found_blockchain in ['MATIC', 'Polygon', 'POLYGON']:
                explorer_url = f"https://polygonscan.com/tx/{transaction_id}"
            elif found_blockchain in ['TRX', 'Tron', 'TRON']:
                explorer_url = f"https://tronscan.org/#/transaction/{transaction_id}"
            # Add more chains as needed
            
            logger.info(f"Generated explorer URL: {explorer_url}")
            logger.info(f"Processing {len(relevant_addresses)} relevant addresses")
            
            # For each relevant address, create a transfer record
            transfers_created = 0
            for idx, address_info in enumerate(relevant_addresses):
                logger.info(f"Processing address [{idx+1}/{len(relevant_addresses)}]: {address_info['public_address']}")
                direction = address_info.get('direction', 'inbound')
                
                # Debug address information
                logger.info(f"Address info: id={address_info['address_id']}, wallet_id={address_info['wallet_id']}, direction={direction}")
                
                # Get the user associated with this wallet to check updatedAt time
                try:
                    user_query = select(Users.UpdatedAt).join(
                        Wallets, Users.UserID == Wallets.UserID
                    ).where(
                        Wallets.WalletID == address_info['wallet_id']
                    )
                    user_updated_at_result = session.execute(user_query).first()
                    
                    if not user_updated_at_result:
                        logger.warning(f"No user found for wallet ID {address_info['wallet_id']}, skipping transaction check")
                        continue
                    
                    user_updated_at = user_updated_at_result[0]
                    logger.info(f"User last updated at: {user_updated_at}")
                    
                except Exception as user_query_error:
                    logger.error(f"Error querying user info: {str(user_query_error)}", exc_info=True)
                    continue
                
                logger.info(f"Creating transfer record for address ID {address_info['address_id']} with direction {direction}")
                
                try:
                    # Проверяем, существует ли уже запись с этим transaction_id и address_id
                    existing_transfer_query = select(Transfers).where(
                        Transfers.AddressID == address_info['address_id'],
                        Transfers.TxHash == transaction_id
                    )
                    existing_transfer = session.execute(existing_transfer_query).first()
                    
                    if existing_transfer:
                        logger.info(f"Transaction {transaction_id} already exists for address ID {address_info['address_id']}, skipping.")
                        continue
                    
                    # Try to convert amount to Decimal, default to 0 if conversion fails
                    decimal_amount = 0
                    if amount:
                        try:
                            from decimal import Decimal
                            decimal_amount = Decimal(str(amount))
                            logger.info(f"Converted amount {amount} to Decimal: {decimal_amount}")
                        except Exception as amount_error:
                            logger.warning(f"Error converting amount '{amount}' to Decimal: {str(amount_error)}")
                            decimal_amount = Decimal('0')
                    
                    # Convert fee to Decimal if it exists
                    decimal_fee = None
                    if fee:
                        try:
                            from decimal import Decimal
                            decimal_fee = Decimal(str(fee))
                            logger.info(f"Converted fee {fee} to Decimal: {decimal_fee}")
                        except Exception as fee_error:
                            logger.warning(f"Error converting fee '{fee}' to Decimal: {str(fee_error)}")
                    
                    # Dump table structure for debugging
                    try:
                        from sqlalchemy import inspect
                        inspector = inspect(engine)
                        columns = inspector.get_columns('Transfers')
                        logger.info("Transfers table columns:")
                        for column in columns:
                            logger.info(f"Column: {column['name']}, Type: {column['type']}")
                    except Exception as inspect_error:
                        logger.error(f"Error inspecting Transfers table: {str(inspect_error)}")
                    
                    # Create new transfer record
                    transfer = Transfers(
                        BlockchainID=blockchain_id,
                        AddressID=address_info['address_id'],
                        WalletID=address_info['wallet_id'],
                        TxHash=transaction_id,
                        BlockNumber=block_number,
                        Timestamp=timestamp,
                        FromAddress=from_address,
                        ToAddress=to_address,
                        Amount=decimal_amount,
                        TokenSymbol=token_symbol,
                        TokenContract=token_contract,
                        AssetType=asset_type,
                        Fee=decimal_fee,
                        Direction=direction,
                        Status='pending',
                        IsSuccessful=True,
                        ExplorerUrl=explorer_url,
                        CreatedAt=datetime.utcnow()
                    )
                    
                    # Log the transfer object data
                    logger.info(f"Transfer record: BlockchainID={blockchain_id}, AddressID={address_info['address_id']}, "
                               f"WalletID={address_info['wallet_id']}, TxHash={transaction_id}, Amount={decimal_amount}, "
                               f"Direction={direction}")
                    
                    session.add(transfer)
                    transfers_created += 1
                    logger.info(f"Added transfer record for address {address_info['public_address']}")
                    
                except Exception as transfer_error:
                    logger.error(f"Error creating transfer record: {str(transfer_error)}", exc_info=True)
                    continue
            
            # Commit all changes
            try:
                if transfers_created > 0:
                    logger.info(f"Committing {transfers_created} transfer records to database")
                    session.commit()
                    logger.info(f"✅ Successfully saved transaction {transaction_id} for {transfers_created} addresses")
                    
                    # به‌روزرسانی خودکار تراکنش بعد از ثبت در دیتابیس
                    try:
                        logger.info(f"🔄 Starting automatic update for transaction {transaction_id}")
                        # بستن session فعلی و ایجاد یک session جدید برای اطمینان از عدم تداخل
                        session.close()
                        
                        # فراخوانی تابع به‌روزرسانی تراکنش با session جدید
                        update_result = fetch_and_update_transaction(transaction_id, blockchain)
                        
                        if update_result:
                            logger.info(f"✅ Successfully updated transaction {transaction_id} with fee and status")
                        else:
                            logger.warning(f"⚠️ Failed to automatically update transaction {transaction_id}")
                    except Exception as update_error:
                        logger.error(f"❌ Error during automatic transaction update: {str(update_error)}", exc_info=True)
                        
                else:
                    logger.warning(f"No transfer records created for transaction {transaction_id}, nothing to commit")
            except Exception as commit_error:
                logger.error(f"Error committing transaction to database: {str(commit_error)}", exc_info=True)
                session.rollback()
            
    except Exception as e:
        logger.error(f"Error saving transaction to database: {str(e)}", exc_info=True)

def get_token_info(contract_address, blockchain, token_symbol=None):
    """
    Get token information from the database.
    
    Args:
        contract_address (str): The token contract address
        blockchain (str): The blockchain symbol (ETH, BSC, etc.)
        token_symbol (str, optional): The token symbol, if known
        
    Returns:
        dict: Token information or None if not found
    """
    logger.info(f"Looking up token info for contract {contract_address} on {blockchain}")
    
    if not contract_address:
        logger.warning("No contract address provided for token lookup")
        return None
    
    from database.Currencies import Currencies
    from database.Blockchains import Blockchains
    from sqlalchemy.orm import Session
    from sqlalchemy import select, or_
    from database.base import Base
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    
    try:
        # Create engine and session
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # Query to get the token information
            # This can match by contract address or symbol on the specific blockchain
            query = select(
                Currencies.CurrencyID,
                Currencies.CurrencyName,
                Currencies.Symbol,
                Currencies.SmartContractAddress,
                Currencies.DecimalPlaces,
                Blockchains.BlockchainID,
                Blockchains.Symbol.label('blockchain_symbol')
            ).join(
                Blockchains, Currencies.BlockchainID == Blockchains.BlockchainID
            ).where(
                or_(
                    # Match by contract address (primary match)
                    Currencies.SmartContractAddress.ilike(f"%{contract_address}%"),
                    # If contract address doesn't match but we have a symbol and blockchain, try that
                    and_(
                        token_symbol is not None,
                        Currencies.Symbol == token_symbol,
                        Blockchains.Symbol == blockchain
                    )
                )
            )
            
            result = session.execute(query).first()
            
            if result:
                logger.info(f"Found token in database: {result.CurrencyName} ({result.Symbol})")
                return {
                    'currency_id': result.CurrencyID,
                    'name': result.CurrencyName,
                    'symbol': result.Symbol,
                    'contract_address': result.SmartContractAddress,
                    'decimals': result.DecimalPlaces,
                    'blockchain_id': result.BlockchainID,
                    'blockchain_symbol': result.blockchain_symbol
                }
            else:
                logger.warning(f"Token not found in database: {contract_address} on {blockchain}")
                return None
    except Exception as e:
        logger.error(f"Error fetching token info: {str(e)}", exc_info=True)
        return None

def update_wallet_balance(address_info, blockchain, token_contract=None, token_symbol=None):
    """
    Update the balance for a wallet after a new transaction.
    
    Args:
        address_info (dict): Address information dictionary
        blockchain (str): The blockchain symbol (ETH, BSC, etc.)
        token_contract (str, optional): Contract address for token transactions
        token_symbol (str, optional): Symbol for the token
    """
    try:
        address_id = address_info['address_id']
        wallet_id = address_info['wallet_id']
        
        logger.info(f"Updating balance for address ID {address_id} on {blockchain}")
        
        # Создаем сессию базы данных и сервис баланса
        from database.base import Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from config import DATABASE_URL
        from services.balance_service import BalanceService
        from database.Transfers import Transfers
        
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            try:
                logger.debug(f"Querying last transfer for address {address_id}")
                
                # Build the query to get the last transfer
                query = session.query(Transfers).filter(
                    Transfers.AddressID == address_id,
                    Transfers.BlockchainID == address_info['blockchain_id']
                )
                
                # If this is a token transaction, add token filter
                if token_contract:
                    logger.debug(f"Filtering for token contract: {token_contract}")
                    query = query.filter(Transfers.TokenContract.ilike(f"%{token_contract}%"))
                elif token_symbol:
                    logger.debug(f"Filtering for token symbol: {token_symbol}")
                    query = query.filter(Transfers.TokenSymbol == token_symbol)
                
                # Get the most recent transfer
                last_transfer = query.order_by(Transfers.Timestamp.desc()).first()
                
                if last_transfer:
                    logger.info(f"Found last transfer with ID {last_transfer.TransferID} for address {address_id}")
                    
                    # Создаем экземпляр сервиса баланса
                    balance_service = BalanceService(session)
                    
                    # Применяем транзакцию к балансу пользователя
                    logger.debug(f"Applying transfer {last_transfer.TransferID} to user balance")
                    result = balance_service.apply_transfer_to_user_holding(last_transfer)
                    
                    if result:
                        logger.info(f"Successfully updated balance for address {address_id} based on transfer {last_transfer.TransferID}")
                    else:
                        logger.warning(f"Failed to update balance for address {address_id}")
                    
                    return result
                else:
                    logger.warning(f"No transfers found for address {address_id} on blockchain {blockchain}")
                    return False
                    
            except Exception as inner_e:
                logger.error(f"Error updating balance in database session: {str(inner_e)}", exc_info=True)
                session.rollback()
                return False
        
    except Exception as e:
        logger.error(f"Error updating wallet balance: {str(e)}", exc_info=True)
        return False

def notify_frontend(transaction_type, transaction_id, relevant_addresses, webhook_data):
    """
    Send notification to frontend about new transaction.
    
    Args:
        transaction_type (str): Type of transaction ('contract_event' or 'address_transaction')
        transaction_id (str): Transaction hash/ID
        relevant_addresses (list): List of relevant address info dictionaries
        webhook_data (dict): Complete webhook data
    """
    try:
        logger.info(f"Sending notification for transaction {transaction_id}")
        
        # Extract wallet IDs and user IDs (assuming they are available)
        wallet_ids = list(set([address_info['wallet_id'] for address_info in relevant_addresses]))
        
        # Prepare notification data
        notification_data = {
            'type': 'new_transaction',
            'transaction_type': transaction_type,
            'transaction_id': transaction_id,
            'affected_wallets': wallet_ids,
            'timestamp': webhook_data.get('timestamp'),
            'blockchain': webhook_data.get('chain')
        }
        
        logger.debug(f"Notification data: {notification_data}")
        
        # Attempt WebSocket notification if Flask-SocketIO is available
        try:
            from flask_socketio import SocketIO
            from app import socketio
            
            logger.debug("WebSocket module is available, attempting to send notifications")
            
            # Send notification to all connected clients with this wallet ID
            for wallet_id in wallet_ids:
                logger.info(f"Emitting WebSocket notification for wallet {wallet_id}")
                socketio.emit(
                    'new_transaction', 
                    notification_data,
                    room=f"wallet_{wallet_id}"
                )
                
            logger.info(f"Successfully sent WebSocket notifications for transaction {transaction_id}")
            
        except ImportError:
            logger.info("Flask-SocketIO not available, skipping WebSocket notification")
        except Exception as ws_error:
            logger.warning(f"Error sending WebSocket notification: {str(ws_error)}")
        
        # Attempt Firebase notification if available
        try:
            import firebase_admin
            from firebase_admin import messaging
            
            logger.debug("Firebase module is available, attempting to send notifications")
            
            # Get device tokens for these wallets
            device_tokens = get_device_tokens_for_wallets(wallet_ids)
            
            if device_tokens:
                for token in device_tokens:
                    token_preview = token[:10] + "..." if len(token) > 10 else token
                    logger.info(f"Sending Firebase notification to device token {token_preview}")
                    
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title="New Transaction",
                            body=f"Transaction {transaction_id[:8]}... on {webhook_data.get('chain')}"
                        ),
                        data={k: str(v) for k, v in notification_data.items() if k != 'affected_wallets'},
                        token=token
                    )
                    
                    response = messaging.send(message)
                    logger.info(f"Firebase notification sent: {response}")
                    
            else:
                logger.info("No device tokens found for the affected wallets")
                
        except ImportError:
            logger.info("Firebase admin not available, skipping Firebase notification")
        except Exception as fcm_error:
            logger.warning(f"Error sending Firebase notification: {str(fcm_error)}")
        
    except Exception as e:
        logger.error(f"Error sending frontend notification: {str(e)}", exc_info=True)

def get_device_tokens_for_wallets(wallet_ids):
    """
    Get device tokens for the given wallet IDs.
    
    Args:
        wallet_ids (list): List of wallet IDs
        
    Returns:
        list: List of device tokens associated with these wallets
    """
    logger.info(f"Getting device tokens for {len(wallet_ids)} wallets")
    
    try:
        from database.base import Base
        from sqlalchemy import create_engine, Table, Column, MetaData
        from sqlalchemy.orm import Session
        from config import DATABASE_URL
        
        engine = create_engine(DATABASE_URL)
        
        # We'll assume there's a DeviceTokens table that associates wallets with device tokens
        # If this table doesn't exist, you'll need to create it or adapt this function
        with Session(engine) as session:
            # Check if DeviceTokens table exists using reflection
            metadata = MetaData()
            try:
                logger.debug("Reflecting database schema to check for DeviceTokens table")
                metadata.reflect(bind=engine, only=['DeviceTokens'])
                if 'DeviceTokens' in metadata.tables:
                    device_tokens_table = metadata.tables['DeviceTokens']
                    
                    # Query for device tokens
                    query = f"""
                        SELECT TokenValue FROM DeviceTokens 
                        WHERE WalletID IN ({','.join(['%s' for _ in wallet_ids])})
                    """
                    logger.debug(f"Executing query: {query} with wallet IDs: {wallet_ids}")
                    result = session.execute(query, wallet_ids).fetchall()
                    
                    # Extract token values from result
                    tokens = [row[0] for row in result]
                    logger.info(f"Found {len(tokens)} device tokens for {len(wallet_ids)} wallets")
                    return tokens
                else:
                    logger.warning("DeviceTokens table not found in database")
                    return []
            except Exception as reflect_error:
                logger.warning(f"Error checking for DeviceTokens table: {str(reflect_error)}")
                return []
                
    except Exception as e:
        logger.error(f"Error getting device tokens: {str(e)}", exc_info=True)
        return []

@webhook_bp.route('/webhook/test', methods=['GET'])
def test_webhook():
    """
    Simple test endpoint to check if webhook routes are registered correctly
    """
    logger.info("Webhook test endpoint called")
    return jsonify({
        "status": "success",
        "message": "Webhook routes are working correctly",
        "timestamp": datetime.now().isoformat()
    })

def init_app(app):
    """
    Register the webhook blueprint with the Flask app.
    This function should be called only once when the app starts.
    """
    # جلوگیری از ثبت چندباره بلوپرینت
    # بررسی می‌کنیم که آیا قبلاً بلوپرینت ثبت شده است یا خیر
    blueprint_registered = False
    for rule in app.url_map.iter_rules():
        if "webhook" in rule.rule:
            # بلوپرینت قبلاً ثبت شده است
            logger.info("Webhook blueprint already registered, skipping registration")
            blueprint_registered = True
            break
    
    if not blueprint_registered:
        logger.info("Registering webhook blueprint with routes:")
        
        # Получение всех маршрутов blueprint перед регистрацией
        routes = []
        for rule in webhook_bp.deferred_functions:
            if hasattr(rule, '__name__'):
                routes.append(f"Function: {rule.__name__}")
            else:
                routes.append(f"Rule: {str(rule)}")
                
        for route in routes:
            logger.info(f"  - {route}")
        
        # Регистрация blueprint
        app.register_blueprint(webhook_bp)
        
        # Проверка регистрации маршрутов после регистрации blueprint
        webhook_routes = []
        for rule in app.url_map.iter_rules():
            if "webhook" in rule.rule:
                webhook_routes.append(f"{rule.endpoint}: {rule.rule} [{','.join(rule.methods)}]")
        
        if webhook_routes:
            logger.info("Webhook routes successfully registered:")
            for route in webhook_routes:
                logger.info(f"  - {route}")
        else:
            logger.warning("No webhook routes found after blueprint registration!")
            
        logger.info("Webhook blueprint registration completed")

def get_transaction_fee_from_tatum(transaction_id, blockchain):
    """
    دریافت جزئیات تراکنش و استخراج مقدار fee از API تاتوم
    
    Args:
        transaction_id (str): شناسه تراکنش
        blockchain (str): نام بلاکچین
        
    Returns:
        str: مقدار fee یا None در صورت عدم موفقیت
    """
    try:
        import requests
        import os
        
        # تبدیل نام بلاکچین به فرمت مورد نیاز API تاتوم
        normalized_chain = normalize_blockchain_name(blockchain)
        
        # دریافت API key تاتوم
        tatum_api_key = os.getenv('TATUM_API_KEY')
        if not tatum_api_key:
            logger.error("TATUM_API_KEY not found in environment variables")
            return None
            
        headers = {
            "x-api-key": tatum_api_key
        }
        
        # ایجاد API endpoint مناسب براساس نوع بلاکچین
        if normalized_chain == "tron-mainnet":
            url = f"{TATUM_API_BASE_URL}/tron/transaction/{transaction_id}"
        elif normalized_chain == "ethereum-mainnet":
            url = f"{TATUM_API_BASE_URL}/ethereum/transaction/{transaction_id}"
        elif normalized_chain == "bsc-mainnet":
            url = f"{TATUM_API_BASE_URL}/bsc/transaction/{transaction_id}"
        else:
            logger.warning(f"No API endpoint defined for blockchain {normalized_chain}")
            return None
            
        logger.info(f"Fetching transaction details from Tatum API: {url}")
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            transaction_data = response.json()
            logger.info(f"Transaction details received from Tatum API: {transaction_data}")
            
            # استخراج مقدار fee براساس نوع بلاکچین
            fee = None
            
            if normalized_chain == "tron-mainnet":
                # در ترون، هزینه تراکنش در فیلد fee قرار دارد
                fee = transaction_data.get('fee')
                if fee:
                    # تبدیل واحد از SUN به TRX
                    try:
                        fee_in_sun = int(fee)
                        fee = str(fee_in_sun / 1_000_000)
                        logger.info(f"Converted Tron fee from SUN to TRX: {fee}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert Tron fee: {fee}")
                        
            elif normalized_chain in ["ethereum-mainnet", "bsc-mainnet"]:
                # در اتریوم و BSC، هزینه = (gasUsed * gasPrice) / 10^18
                gas_used = transaction_data.get('gasUsed')
                gas_price = transaction_data.get('gasPrice')
                
                if gas_used and gas_price:
                    try:
                        gas_used_int = int(gas_used)
                        gas_price_int = int(gas_price)
                        fee_in_wei = gas_used_int * gas_price_int
                        fee = str(fee_in_wei / 10**18)
                        logger.info(f"Calculated fee from gas: {fee}")
                    except (ValueError, TypeError):
                        logger.warning(f"Could not calculate fee from gas: gasUsed={gas_used}, gasPrice={gas_price}")
            
            logger.info(f"Extracted fee from transaction details: {fee}")
            return fee
        else:
            logger.error(f"Failed to get transaction details: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching transaction fee from Tatum: {str(e)}", exc_info=True)
        return None

def update_transaction_fee_and_status(transaction_id, blockchain):
    """
    دریافت کارمزد شبکه و وضعیت تراکنش از API تاتوم و به روزرسانی آنها در دیتابیس
    
    Args:
        transaction_id (str): شناسه تراکنش
        blockchain (str): نام بلاکچین
    """
    if not transaction_id or not blockchain:
        logger.error("Missing transaction_id or blockchain for update_transaction_fee_and_status")
        return False
        
    logger.info(f"Updating fee and status for transaction {transaction_id} on {blockchain}")
    
    try:
        # دریافت اطلاعات تراکنش از API تاتوم
        transaction_details = get_transaction_details_from_tatum(transaction_id, blockchain)
        
        if not transaction_details:
            logger.warning(f"Could not retrieve transaction details for {transaction_id}")
            return False
        
        # استخراج کارمزد
        fee = transaction_details.get('fee')
        logger.info(f"Retrieved fee from Tatum API: {fee}")
        
        # استخراج وضعیت تراکنش
        status = 'confirmed'  # پیش‌فرض
        
        # تعیین وضعیت براساس اطلاعات تراکنش
        if transaction_details.get('status') == 'FAILED':
            status = 'failed'
        elif 'blockNumber' in transaction_details and transaction_details.get('blockNumber'):
            # اگر شماره بلاک موجود باشد، تراکنش تایید شده است
            status = 'confirmed'
        else:
            # اگر شماره بلاک موجود نباشد، تراکنش هنوز در انتظار است
            status = 'pending'
            
        logger.info(f"Extracted fee: {fee}, status: {status} for transaction {transaction_id}")
        
        # به روزرسانی رکوردهای تراکنش در دیتابیس
        result = update_transaction_records_in_db(transaction_id, fee, status)
        
        if result:
            logger.info(f"Successfully updated transaction {transaction_id} with fee={fee}, status={status}")
            return True
        else:
            logger.warning(f"Failed to update transaction {transaction_id} in database")
            return False
        
    except Exception as e:
        logger.error(f"Error updating fee and status for transaction {transaction_id}: {str(e)}", exc_info=True)
        return False

def get_transaction_details_from_tatum(transaction_id, blockchain):
    """
    دریافت جزئیات کامل تراکنش از API تاتوم
    
    Args:
        transaction_id (str): شناسه تراکنش
        blockchain (str): نام بلاکچین
        
    Returns:
        dict: جزئیات کامل تراکنش یا None در صورت عدم موفقیت
    """
    try:
        import requests
        import os
        import json
        
        # اطمینان از اینکه TATUM_API_BASE_URL تعریف شده است
        if 'TATUM_API_BASE_URL' not in globals():
            global TATUM_API_BASE_URL
            TATUM_API_BASE_URL = "https://api.tatum.io/v3"
            logger.info(f"TATUM_API_BASE_URL was not defined, set to {TATUM_API_BASE_URL}")
        
        # تبدیل نام بلاکچین به فرمت مورد نیاز API تاتوم
        normalized_chain = normalize_blockchain_name(blockchain)
        logger.info(f"Original blockchain: {blockchain}, normalized to: {normalized_chain}")
        
        # دریافت API key تاتوم
        tatum_api_key = os.getenv('TATUM_API_KEY')
        if not tatum_api_key:
            logger.error("❌ TATUM_API_KEY not found in environment variables")
            return None
            
        headers = {
            "x-api-key": tatum_api_key
        }
        
        # تعیین نام واقعی بلاکچین برای API تاتوم
        api_blockchain = None
        if normalized_chain.startswith('tron'):
            api_blockchain = 'tron'
        elif normalized_chain.startswith('ethereum'):
            api_blockchain = 'ethereum'
        elif normalized_chain.startswith('bsc'):
            api_blockchain = 'bsc'
        else:
            # اگر بلاکچین شناخته شده نباشد، از قسمت اول normalized_chain استفاده می‌کنیم
            api_blockchain = normalized_chain.split('-')[0]
        
        # ساخت آدرس API
        url = f"{TATUM_API_BASE_URL}/{api_blockchain}/transaction/{transaction_id}"
        logger.info(f"🔍 Fetching transaction details from Tatum API: {url}")
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            transaction_data = response.json()
            try:
                # نمایش داده‌های تراکنش برای دیباگ بیشتر
                logger.info(f"✅ Transaction details received: {json.dumps(transaction_data, indent=2)[:500]}...")
            except:
                logger.info(f"Transaction data received (could not convert to JSON)")
            
            # پردازش و استاندارد‌سازی داده‌ها
            processed_data = {}
            
            # اطلاعات عمومی که در همه بلاکچین‌ها وجود دارد
            processed_data['txId'] = transaction_id
            processed_data['blockchain'] = blockchain
            
            if api_blockchain == 'tron':
                # پردازش داده‌های مخصوص ترون
                if 'ret' in transaction_data and transaction_data['ret']:
                    ret_info = transaction_data['ret'][0]
                    processed_data['status'] = ret_info.get('contractRet', 'UNKNOWN')
                
                processed_data['blockNumber'] = transaction_data.get('blockNumber')
                
                # محاسبه کارمزد در TRX
                fee = 0
                energy_fee = transaction_data.get('energy_fee', 0)
                net_fee = transaction_data.get('net_fee', 0)
                
                if energy_fee:
                    try:
                        fee += int(energy_fee)
                        logger.info(f"Added energy_fee: {energy_fee}")
                    except:
                        logger.warning(f"Could not convert energy_fee: {energy_fee}")
                
                if net_fee:
                    try:
                        fee += int(net_fee)
                        logger.info(f"Added net_fee: {net_fee}")
                    except:
                        logger.warning(f"Could not convert net_fee: {net_fee}")
                
                # پایه کارمزد در ترون (SUN)
                fee_base = 1_000_000  # SUN to TRX
                
                if fee > 0:
                    fee_in_trx = fee / fee_base
                    processed_data['fee'] = str(fee_in_trx)
                    logger.info(f"Calculated TRX fee: {fee} SUN = {fee_in_trx} TRX")
                else:
                    # جستجوی کارمزد در فیلدهای دیگر
                    fee_fields = ['fee', 'feeLimit', 'fee_limit']
                    for fee_field in fee_fields:
                        if fee_field in transaction_data and transaction_data[fee_field]:
                            try:
                                fee_value = int(transaction_data[fee_field])
                                fee_in_trx = fee_value / fee_base
                                processed_data['fee'] = str(fee_in_trx)
                                logger.info(f"Found fee in {fee_field}: {fee_value} SUN = {fee_in_trx} TRX")
                                break
                            except:
                                logger.warning(f"Could not convert {fee_field}: {transaction_data[fee_field]}")
                
                # تعیین وضعیت نهایی تراکنش
                status = processed_data.get('status', 'UNKNOWN')
                if status == 'SUCCESS':
                    processed_data['status'] = 'confirmed'
                elif status in ['REVERT', 'FAILED']:
                    processed_data['status'] = 'failed'
                else:
                    # اگر وضعیت مشخص نباشد، از شماره بلاک استفاده می‌کنیم
                    if processed_data.get('blockNumber'):
                        processed_data['status'] = 'confirmed'
                    else:
                        processed_data['status'] = 'pending'
                
                logger.info(f"Tron transaction status: {status} -> {processed_data['status']}")
                
            elif api_blockchain in ['ethereum', 'bsc']:
                # پردازش داده‌های مخصوص اتریوم و BSC
                processed_data['blockNumber'] = transaction_data.get('blockNumber')
                
                # تعیین وضعیت تراکنش
                api_status = transaction_data.get('status')
                
                # تبدیل hex به int اگر لازم باشد
                if isinstance(api_status, str) and api_status.startswith('0x'):
                    try:
                        api_status = int(api_status, 16)
                        logger.info(f"Converted hex status {transaction_data['status']} to int: {api_status}")
                    except:
                        logger.warning(f"Could not convert hex status: {api_status}")
                
                # تعیین وضعیت نهایی
                if api_status == 1:
                    processed_data['status'] = 'confirmed'
                elif api_status == 0:
                    processed_data['status'] = 'failed'
                else:
                    # اگر وضعیت مشخص نباشد، از شماره بلاک استفاده می‌کنیم
                    if processed_data.get('blockNumber'):
                        processed_data['status'] = 'confirmed'
                    else:
                        processed_data['status'] = 'pending'
                
                logger.info(f"Ethereum/BSC transaction status: {api_status} -> {processed_data['status']}")
                
                # محاسبه کارمزد از gasUsed و gasPrice
                gas_used = transaction_data.get('gasUsed')
                gas_price = transaction_data.get('gasPrice')
                
                # تبدیل hex به int اگر لازم باشد
                if isinstance(gas_used, str) and gas_used.startswith('0x'):
                    try:
                        gas_used = int(gas_used, 16)
                        logger.info(f"Converted hex gasUsed {transaction_data['gasUsed']} to int: {gas_used}")
                    except:
                        logger.warning(f"Could not convert hex gasUsed: {gas_used}")
                        gas_used = 0
                
                if isinstance(gas_price, str) and gas_price.startswith('0x'):
                    try:
                        gas_price = int(gas_price, 16)
                        logger.info(f"Converted hex gasPrice {transaction_data['gasPrice']} to int: {gas_price}")
                    except:
                        logger.warning(f"Could not convert hex gasPrice: {gas_price}")
                        gas_price = 0
                
                # اگر هنوز به عدد تبدیل نشده‌اند
                if not isinstance(gas_used, (int, float)):
                    try:
                        gas_used = int(gas_used or 0)
                    except:
                        gas_used = 0
                
                if not isinstance(gas_price, (int, float)):
                    try:
                        gas_price = int(gas_price or 0)
                    except:
                        gas_price = 0
                
                # محاسبه کارمزد نهایی
                fee = 0
                if gas_used and gas_price:
                    fee = (gas_used * gas_price) / 10**18  # تبدیل به ETH یا BNB
                    processed_data['fee'] = str(fee)
                    logger.info(f"Calculated fee: {gas_used} * {gas_price} / 10^18 = {fee}")
            
            # بررسی نهایی داده‌ها
            if 'fee' not in processed_data or not processed_data['fee']:
                logger.warning("No fee information found in transaction data")
                processed_data['fee'] = "0"  # مقدار پیش‌فرض
            
            if 'status' not in processed_data or not processed_data['status']:
                logger.warning("No status information found in transaction data")
                # اگر شماره بلاک موجود باشد، وضعیت تراکنش تایید شده است
                if processed_data.get('blockNumber'):
                    processed_data['status'] = 'confirmed'
                else:
                    processed_data['status'] = 'pending'  # مقدار پیش‌فرض
            
            logger.info(f"📊 Processed transaction data: {processed_data}")
            return processed_data
            
        else:
            logger.error(f"❌ Failed to get transaction details: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error fetching transaction details from Tatum: {str(e)}", exc_info=True)
        return None

def fetch_and_update_transaction(transaction_id, blockchain_symbol):
    """
    دریافت جزئیات تراکنش از تاتوم و به‌روزرسانی fee و status در جدول transfers
    
    Args:
        transaction_id (str): شناسه تراکنش
        blockchain_symbol (str): سمبل بلاکچین
        
    Returns:
        bool: نتیجه عملیات به‌روزرسانی
    """
    logger.info(f"🔄 Fetching and updating transaction {transaction_id} on {blockchain_symbol}")
    
    # اطمینان از اینکه TATUM_API_BASE_URL تعریف شده است
    if 'TATUM_API_BASE_URL' not in globals():
        global TATUM_API_BASE_URL
        TATUM_API_BASE_URL = "https://api.tatum.io/v3"
        logger.info(f"TATUM_API_BASE_URL was not defined, set to {TATUM_API_BASE_URL}")
    
    # اطمینان از اینکه API Key تاتوم تنظیم شده است
    tatum_api_key = os.getenv('TATUM_API_KEY')
    if not tatum_api_key:
        logger.error("❌ TATUM_API_KEY not found in environment variables")
        return False
    
    logger.info(f"Using Tatum API Key: {tatum_api_key[:5]}... (masked)")
    
    # دریافت جزئیات تراکنش از تاتوم
    transaction_details = get_transaction_details_from_tatum(transaction_id, blockchain_symbol)
    
    if not transaction_details:
        logger.error(f"❌ Failed to get transaction details for {transaction_id}")
        return False
    
    # استخراج کارمزد و وضعیت
    fee = transaction_details.get('fee')
    status = transaction_details.get('status', 'pending')
    
    logger.info(f"📝 Extracted fee: {fee}, status: {status} for transaction {transaction_id}")
    
    # به‌روزرسانی در دیتابیس
    from database.Transfers import Transfers
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    from decimal import Decimal
    
    try:
        # تبدیل کارمزد به Decimal
        decimal_fee = None
        if fee:
            try:
                decimal_fee = Decimal(str(fee))
                logger.info(f"💰 Converted fee {fee} to Decimal: {decimal_fee}")
            except Exception as fee_error:
                logger.warning(f"⚠️ Error converting fee '{fee}' to Decimal: {str(fee_error)}")
        
        # ایجاد اتصال به دیتابیس
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # پیدا کردن تراکنش در دیتابیس
            transfers = session.query(Transfers).filter(Transfers.TxHash == transaction_id).all()
            
            if not transfers:
                logger.warning(f"❓ No transfer records found for transaction {transaction_id}")
                return False
                
            logger.info(f"🔍 Found {len(transfers)} transfer records for transaction {transaction_id}")
            
            # نمایش اطلاعات بیشتر برای دیباگ
            if transfers:
                tx_sample = transfers[0]
                logger.info(f"Sample transaction details - ID: {tx_sample.TransferID}, Status: {tx_sample.Status}, Fee: {tx_sample.Fee}")
            
            # به‌روزرسانی فیلدهای مورد نظر برای هر رکورد
            for transfer in transfers:
                # نمایش مقادیر قبلی
                logger.info(f"🔄 Updating transfer ID {transfer.TransferID}: Old fee={transfer.Fee}, Old status={transfer.Status}")
                
                # به‌روزرسانی کارمزد
                if decimal_fee is not None:
                    transfer.Fee = decimal_fee
                    logger.info(f"Updated fee to {decimal_fee}")
                else:
                    logger.warning(f"No fee value to update for transfer {transfer.TransferID}")
                
                # به‌روزرسانی وضعیت
                if status:
                    transfer.Status = status
                    # به‌روزرسانی فیلد IsSuccessful بر اساس وضعیت
                    transfer.IsSuccessful = (status != 'failed')
                    logger.info(f"Updated status to {status}, IsSuccessful to {transfer.IsSuccessful}")
                else:
                    logger.warning(f"No status value to update for transfer {transfer.TransferID}")
                
                logger.info(f"✅ New values: Fee={transfer.Fee}, Status={transfer.Status}, IsSuccessful={transfer.IsSuccessful}")
            
            # ذخیره تغییرات
            try:
                session.commit()
                logger.info(f"✅ Successfully updated all {len(transfers)} transfer records for transaction {transaction_id}")
                return True
            except Exception as commit_error:
                logger.error(f"❌ Error committing changes to database: {str(commit_error)}", exc_info=True)
                session.rollback()
                return False
            
    except Exception as e:
        logger.error(f"❌ Error updating transaction in database: {str(e)}", exc_info=True)
        return False

@webhook_bp.route('/webhook/update-transaction/<blockchain>/<tx_hash>', methods=['GET'])
def manual_update_transaction(blockchain, tx_hash):
    """
    مسیر برای به‌روزرسانی دستی جزئیات تراکنش
    """
    logger.info(f"🔄 Manual update requested for transaction {tx_hash} on {blockchain}")
    
    try:
        # به‌روزرسانی تراکنش
        result = fetch_and_update_transaction(tx_hash, blockchain)
        
        if result:
            return jsonify({
                "status": "success",
                "message": f"Transaction {tx_hash} updated successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to update transaction {tx_hash}"
            }), 400
    
    except Exception as e:
        logger.error(f"❌ Error in manual update: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500 

def normalize_blockchain_name(blockchain):
    """
    تبدیل نام بلاکچین به فرمت استاندارد برای استفاده در API تاتوم
    
    Args:
        blockchain (str): نام بلاکچین (مانند 'ETH', 'TRX', 'BSC', ...)
        
    Returns:
        str: نام استاندارد شده بلاکچین برای API تاتوم
    """
    if not blockchain:
        logger.error("No blockchain name provided for normalization")
        return None
    
    logger.info(f"Normalizing blockchain name: {blockchain}")
    
    # تبدیل به حروف کوچک
    bc_lower = blockchain.lower()
    
    # نگاشت بلاکچین‌های رایج به فرمت استاندارد
    blockchain_mapping = {
        'eth': 'ethereum-mainnet',
        'ethereum': 'ethereum-mainnet',
        'bsc': 'bsc-mainnet',
        'binance': 'bsc-mainnet',
        'bnb': 'bsc-mainnet',
        'trx': 'tron-mainnet',
        'tron': 'tron-mainnet',
        'matic': 'polygon-mainnet',
        'polygon': 'polygon-mainnet',
        'btc': 'bitcoin-mainnet',
        'bitcoin': 'bitcoin-mainnet',
        'avax': 'avax-mainnet',
        'avalanche': 'avax-mainnet',
        'sol': 'solana-mainnet',
        'solana': 'solana-mainnet'
    }
    
    # اگر نام بلاکچین در نگاشت موجود باشد، از آن استفاده می‌کنیم
    if bc_lower in blockchain_mapping:
        normalized = blockchain_mapping[bc_lower]
        logger.info(f"Successfully normalized blockchain {blockchain} to {normalized}")
        return normalized
    
    # اگر نام بلاکچین قبلاً فرمت استاندارد دارد، آن را برمی‌گردانیم
    if bc_lower in ['ethereum-mainnet', 'bsc-mainnet', 'tron-mainnet', 'polygon-mainnet', 'bitcoin-mainnet']:
        logger.info(f"Blockchain {blockchain} is already in standard format")
        return bc_lower
    
    # در غیر این صورت، فرض می‌کنیم نام بلاکچین یک سمبل است و آن را به فرمت استاندارد تبدیل می‌کنیم
    normalized = f"{bc_lower}-mainnet"
    logger.info(f"Normalized blockchain {blockchain} to {normalized} (as best guess)")
    return normalized