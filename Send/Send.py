from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
import logging
import json
from web3 import Web3
from decimal import Decimal
import uuid
import time
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies
from security.validators import InputValidator, SecurityUtils, ValidationError
from security.encryption import decrypt_private_key_aes
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from services.blockchain_service import get_blockchain_service
from services.tatum_service import TatumService
from services.transfer_service import TransferService

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing send transaction module")

send_bp = Blueprint('send', __name__)

# Initialize Tatum service with API key
TATUM_API_KEY = "t-67e5053a3320cff8fd79c921-0762aaf42dbc4c979d692389"  # Updated to match other parts of the codebase
tatum_service = TatumService(TATUM_API_KEY)

# Transaction URLs for different blockchains
TRANSACTION_URLS = {
    "Ethereum": "https://etherscan.io/tx/{}",
    "ETHEREUM": "https://etherscan.io/tx/{}",
    "Bitcoin": "https://www.blockchain.com/btc/tx/{}",
    "BITCOIN": "https://www.blockchain.com/btc/tx/{}",
    "Tron": "https://tronscan.org/#/transaction/{}",
    "TRON": "https://tronscan.org/#/transaction/{}",
    "Binance": "https://bscscan.com/tx/{}",
    "BINANCE": "https://bscscan.com/tx/{}",
    "Polygon": "https://polygonscan.com/tx/{}",
    "POLYGON": "https://polygonscan.com/tx/{}",
    "Avalanche": "https://snowtrace.io/tx/{}",
    "AVALANCHE": "https://snowtrace.io/tx/{}",
    "Arbitrum": "https://arbiscan.io/tx/{}",
    "ARBITRUM": "https://arbiscan.io/tx/{}",
    "Polkadot": "https://polkadot.subscan.io/extrinsic/{}",
    "POLKADOT": "https://polkadot.subscan.io/extrinsic/{}",
    "XRP": "https://xrpscan.com/tx/{}",
    "Solana": "https://explorer.solana.com/tx/{}",
    "SOLANA": "https://explorer.solana.com/tx/{}"
}

# Store pending transactions with expiration time
# Format: {transaction_id: {'data': transaction_data, 'expires_at': expiration_timestamp}}
PENDING_TRANSACTIONS = {}

# Store transaction status information
# Format: {tx_hash: {'status': status, 'description': description, 'last_checked': timestamp, 'checks': count}}
TRANSACTION_STATUS = {}

# Background thread for monitoring transaction status
transaction_monitor_thread = None
transaction_monitor_running = False
transaction_monitor_executor = ThreadPoolExecutor(max_workers=2)

def get_transaction_url(blockchain_name, txn_id):
    """Get transaction URL for a specific blockchain"""
    # Try exact match first
    url_template = TRANSACTION_URLS.get(blockchain_name)
    
    # If not found, try case-insensitive match
    if not url_template:
        for name, template in TRANSACTION_URLS.items():
            if name.lower() == blockchain_name.lower():
                url_template = template
                break
    
    if url_template:
        return url_template.format(txn_id)
    return None

def get_user_wallet_and_address(session, user_id, blockchain_name):
    """Get user's wallet and address for a specific blockchain"""
    try:
        # Get user's wallet
        wallet = session.query(Wallets).join(Users).filter(Users.UserID == user_id).first()
        
        if not wallet:
            logger.warning(f"No wallet found for user {user_id}")
            return None, None, "No wallet found for this user"
        
        # Get blockchain ID - case insensitive search
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainName.ilike(blockchain_name)
        ).first()
        
        if not blockchain:
            logger.warning(f"Blockchain {blockchain_name} not found")
            return None, None, f"Blockchain {blockchain_name} not supported"
        
        # Get user's address for this blockchain
        address = session.query(Address).filter(
            Address.WalletID == wallet.WalletID,
            Address.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not address:
            logger.warning(f"No {blockchain_name} address found for user {user_id}")
            return None, None, f"No {blockchain_name} address found for this user"
        
        # Decrypt private key
        try:
            private_key = decrypt_private_key_aes(address.PrivateKey)
        except Exception as e:
            logger.error(f"Error decrypting private key: {str(e)}")
            return None, None, "Error accessing wallet credentials"
        
        return address.PublicAddress, private_key, None
    
    except Exception as e:
        logger.error(f"Error getting user wallet and address: {str(e)}")
        return None, None, f"Error: {str(e)}"

def get_currency_details(session, currency_name, blockchain_name):
    """Get currency details for a specific blockchain"""
    try:
        # Get blockchain ID - case insensitive search
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainName.ilike(blockchain_name)
        ).first()
        
        if not blockchain:
            logger.warning(f"Blockchain {blockchain_name} not found")
            return None, f"Blockchain {blockchain_name} not supported"
        
        # Get currency details - case insensitive search
        currency = session.query(Currencies).filter(
            Currencies.Symbol.ilike(currency_name),
            Currencies.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not currency:
            logger.warning(f"Currency {currency_name} not found on {blockchain_name}")
            return None, f"Currency {currency_name} not found on {blockchain_name}"
        
        return currency, None
    
    except Exception as e:
        logger.error(f"Error getting currency details: {str(e)}")
        return None, f"Error: {str(e)}"

def validate_transaction_inputs(user_id, currency_name, recipient_address, amount):
    """Validate transaction inputs"""
    errors = []
    
    try:
        InputValidator.validate_uuid(user_id, "UserID")
    except ValidationError as e:
        errors.append(str(e))
    
    try:
        InputValidator.validate_string(currency_name, "CurrencyName")
    except ValidationError as e:
        errors.append(str(e))
    
    try:
        InputValidator.validate_string(recipient_address, "RecipientAddress", min_length=10, max_length=100)
    except ValidationError as e:
        errors.append(str(e))
    
    try:
        amount_value = float(amount)
        if amount_value <= 0:
            errors.append("Amount must be greater than 0")
    except ValueError:
        errors.append("Amount must be a valid number")
    
    return errors

def update_transaction_status(tx_hash, blockchain_name):
    """Update transaction status by checking with the blockchain"""
    try:
        # Skip if transaction is already confirmed or failed (final states)
        if tx_hash in TRANSACTION_STATUS:
            current_status = TRANSACTION_STATUS[tx_hash].get('status')
            if current_status in ['Confirmed', 'Failed']:
                return TRANSACTION_STATUS[tx_hash]
        
        # Check status using Tatum service
        status, description = tatum_service.check_transaction_status(blockchain_name, tx_hash)
        
        # Get current time
        current_time = datetime.now()
        
        # Update status in our store
        if tx_hash in TRANSACTION_STATUS:
            # Update existing entry
            TRANSACTION_STATUS[tx_hash].update({
                'status': status,
                'description': description,
                'last_checked': current_time,
                'blockchain_name': blockchain_name,
                'checks': TRANSACTION_STATUS[tx_hash].get('checks', 0) + 1
            })
        else:
            # Create new entry
            TRANSACTION_STATUS[tx_hash] = {
                'status': status,
                'description': description,
                'last_checked': current_time,
                'blockchain_name': blockchain_name,
                'checks': 1
            }
        
        logger.info(f"Updated transaction {tx_hash} status: {status} - {description}")
        return TRANSACTION_STATUS[tx_hash]
    except Exception as e:
        logger.error(f"Error updating transaction status for {tx_hash}: {str(e)}")
        return None

def start_transaction_monitor():
    """Start background thread to monitor transaction status"""
    global transaction_monitor_thread, transaction_monitor_running
    
    # Check if monitor is already running
    if transaction_monitor_running and transaction_monitor_thread and transaction_monitor_thread.is_alive():
        logger.info("Transaction monitor already running")
        return  # Already running
    
    def monitor_transactions():
        logger.info("Transaction monitor thread started")
        while transaction_monitor_running:
            try:
                # Make a copy to avoid modification during iteration
                tx_hashes = list(TRANSACTION_STATUS.keys())
                
                for tx_hash in tx_hashes:
                    # Skip transactions that are already in final state
                    if tx_hash in TRANSACTION_STATUS:
                        status_info = TRANSACTION_STATUS[tx_hash]
                        if status_info.get('status') in ['Confirmed', 'Failed']:
                            # If we've confirmed final status and it's older than 30 minutes, clean it up
                            last_checked = status_info.get('last_checked')
                            if last_checked and (datetime.now() - last_checked) > timedelta(minutes=30):
                                TRANSACTION_STATUS.pop(tx_hash, None)
                                logger.info(f"Removed finalized transaction {tx_hash} from monitoring")
                            continue
                        
                        # Check if we should update this transaction status
                        last_checked = status_info.get('last_checked')
                        if last_checked:
                            # Calculate delay based on number of checks
                            checks = status_info.get('checks', 0)
                            delay = min(60, 5 * (2 ** min(4, checks // 2)))  # Exponential backoff, max 60 seconds
                            
                            # Only check if enough time has passed since last check
                            if (datetime.now() - last_checked) < timedelta(seconds=delay):
                                continue
                    
                    # Need to find blockchain for this transaction
                    blockchain_name = None
                    
                    # First check if blockchain_name is already stored in TRANSACTION_STATUS
                    if tx_hash in TRANSACTION_STATUS and 'blockchain_name' in TRANSACTION_STATUS[tx_hash]:
                        blockchain_name = TRANSACTION_STATUS[tx_hash]['blockchain_name']
                        logger.debug(f"Found blockchain_name '{blockchain_name}' in TRANSACTION_STATUS for {tx_hash}")
                    
                    # If not found, look in PENDING_TRANSACTIONS
                    if not blockchain_name:
                        for tx_id, tx_data in PENDING_TRANSACTIONS.items():
                            # Check if tx_data and data exist and are dictionaries
                            if isinstance(tx_data, dict) and 'data' in tx_data and isinstance(tx_data['data'], dict):
                                if tx_data['data'].get('tx_hash') == tx_hash:
                                    # Check if blockchain_name exists in tx_data['data']
                                    if 'blockchain_name' in tx_data['data']:
                                        blockchain_name = tx_data['data']['blockchain_name']
                                        logger.debug(f"Found blockchain_name '{blockchain_name}' in PENDING_TRANSACTIONS for {tx_hash}")
                                        break
                                    else:
                                        logger.warning(f"Missing blockchain_name in transaction data for {tx_hash}")
                            else:
                                logger.warning(f"Invalid tx_data format for {tx_id}: {tx_data}")
                    
                    if blockchain_name:
                        # Update status in background thread to avoid blocking
                        try:
                            transaction_monitor_executor.submit(update_transaction_status, tx_hash, blockchain_name)
                        except Exception as e:
                            logger.error(f"Error submitting transaction status update task for {tx_hash}: {str(e)}")
                    else:
                        # If we can't find blockchain name, skip this transaction
                        logger.warning(f"Could not find blockchain name for transaction {tx_hash}")
                
                # Sleep for 5 seconds before next check
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in transaction monitor thread: {str(e)}")
                time.sleep(10)  # Sleep longer on error
    
    transaction_monitor_running = True
    
    try:
        # Create and start the monitor thread
        transaction_monitor_thread = threading.Thread(target=monitor_transactions)
        transaction_monitor_thread.daemon = True
        transaction_monitor_thread.start()
        logger.info("Transaction monitor thread started")
    except Exception as e:
        logger.error(f"Failed to start transaction monitor thread: {str(e)}")
        transaction_monitor_running = False

# Start the transaction monitor when module is loaded
start_transaction_monitor()

def cleanup_expired_transactions():
    """Remove expired transactions from the pending transactions dictionary"""
    current_time = datetime.now()
    expired_ids = [tx_id for tx_id, tx_data in PENDING_TRANSACTIONS.items() 
                  if tx_data['expires_at'] < current_time]
    
    for tx_id in expired_ids:
        logger.info(f"Transaction {tx_id} expired and removed from pending transactions")
        PENDING_TRANSACTIONS.pop(tx_id, None)
    
    return expired_ids

@send_bp.route('/send', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def send_transaction():
    """
    Send a transaction on a specific blockchain
    ---
    tags:
      - Transactions
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - UserID
              - CurrencyName
              - RecipientAddress
              - Amount
            properties:
              UserID:
                type: string
                description: User ID
              CurrencyName:
                type: string
                description: Currency symbol
              RecipientAddress:
                type: string
                description: Recipient address
              Amount:
                type: string
                description: Amount to send
    responses:
      200:
        description: Transaction details before sending
      400:
        description: Invalid input data
      404:
        description: Wallet or currency not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    # Clean up expired transactions
    cleanup_expired_transactions()
    
    session = SessionLocal()
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Invalid request data",
                "success": False
            }), 400
        
        # Extract parameters
        user_id = data.get('UserID', '')
        currency_name = data.get('CurrencyName', '')
        recipient_address = data.get('RecipientAddress', '')
        amount = data.get('Amount', '')
        
        # Get currency details from database
        currency = session.query(Currencies).filter(
            Currencies.Symbol.ilike(currency_name)
        ).first()
        
        if not currency:
            logger.warning(f"Currency {currency_name} not found")
            return jsonify({
                "message": f"Currency {currency_name} not found",
                "success": False
            }), 404
        
        # Get blockchain details
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainID == currency.BlockchainID
        ).first()
        
        if not blockchain:
            logger.warning(f"Blockchain not found for currency {currency_name}")
            return jsonify({
                "message": f"Blockchain not found for currency {currency_name}",
                "success": False
            }), 404
        
        blockchain_name = blockchain.BlockchainName
        logger.info(f"Currency: {currency_name}, Blockchain: {blockchain_name}, BlockchainID: {blockchain.BlockchainID}")
        
        # Check if it's a token
        is_token = currency.IsToken
        smart_contract_address = currency.SmartContractAddress if is_token else None
        
        # List of main coins that don't need smart contract validation
        MAIN_COINS = ['TRX', 'BTC', 'ETH', 'BNB', 'MATIC', 'AVAX', 'ARB', 'DOT', 'XRP', 'SOL']
        
        # Validate inputs
        validation_errors = validate_transaction_inputs(
            user_id, currency_name, recipient_address, amount
        )
        
        if validation_errors:
            return jsonify({
                "message": "Validation errors",
                "errors": validation_errors,
                "success": False
            }), 400
        
        # Get user's wallet and address
        sender_address, private_key, error = get_user_wallet_and_address(session, user_id, blockchain_name)
        if error:
            return jsonify({
                "message": error,
                "success": False
            }), 404
        
        try:
            # Validate recipient address using Tatum
            if not tatum_service.validate_address(blockchain_name, recipient_address):
                logger.error(f"Invalid {blockchain_name} recipient address: {recipient_address}")
                # For Tron addresses, do a basic validation
                if blockchain_name.lower() == 'tron' and recipient_address.startswith('T') and len(recipient_address) == 34:
                    logger.info(f"Basic validation passed for Tron address: {recipient_address}")
                    # Continue with the transaction despite the validation error
                else:
                    return jsonify({
                        "message": f"Invalid {blockchain_name} recipient address",
                        "success": False
                    }), 400
            
            # For main coins, don't pass smart_contract_address even if it's set
            if currency_name.upper() in MAIN_COINS:
                logger.info(f"{currency_name} is a main coin, not using smart contract address")
                smart_contract_address = None
            
            # Prepare transaction using Tatum service
            tx_details, error = tatum_service.prepare_transaction(
                blockchain_name, sender_address, private_key, recipient_address,
                amount, smart_contract_address
            )
            
            if error:
                return jsonify({
                    "message": error,
                    "success": False
                }), 400
            
            # Generate a transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Store transaction details with expiration time (2 minutes from now)
            expiration_time = datetime.now() + timedelta(minutes=2)
            
            # Store all necessary data for confirming the transaction later
            PENDING_TRANSACTIONS[transaction_id] = {
                'data': {
                    'user_id': user_id,
                    'currency_name': currency_name,
                    'recipient_address': recipient_address,
                    'amount': amount,
                    'blockchain_name': blockchain_name,
                    'smart_contract_address': smart_contract_address,
                    'sender_address': sender_address,
                    'private_key': private_key,
                    'tx_details': tx_details
                },
                'expires_at': expiration_time
            }
            
            # Format transaction details before sending
            before_sending = {
                "details": f"\n📌 **Transaction Details (Before Sending):**\n"
                          f"   🔹 Sender Address: {tx_details['sender_address']}\n"
                          f"   🔹 Recipient Address: {tx_details['recipient_address']}\n"
                          f"   🔹 Blockchain: {blockchain_name}\n"
                          f"   🔹 Currency: {currency_name}\n"
                          f"   🔹 Smart Contract: {smart_contract_address if is_token else 'N/A'}\n"
                          f"   🔹 Amount: {tx_details['amount']} {currency_name}\n"
                          f"   🔹 Sender Balance (Before): {tx_details['sender_balance_before']} {currency_name}\n"
                          f"   🔹 Estimated Fee: {tx_details['estimated_fee']} {blockchain_name}\n"
                          f"   🔹 Sender Balance (After): {tx_details['balance_after_tx']} {blockchain_name}\n",
                "transaction_id": transaction_id,
                "blockchain_name": blockchain_name,
                "expires_at": expiration_time.isoformat(),
                "success": True
            }
            
            return jsonify(before_sending), 200
            
        except ValueError as e:
            return jsonify({
                "message": str(e),
                "success": False
            }), 400
        except Exception as e:
            logger.error(f"Error preparing transaction: {str(e)}")
            return jsonify({
                "message": "Error preparing transaction",
                "success": False
            }), 500
    
    except Exception as e:
        logger.error(f"Error in send_transaction: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500
    finally:
        session.close()

@send_bp.route('/<transaction_id>/confirm', methods=['GET'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
def confirm_transaction(transaction_id):
    """
    Confirm and send a transaction
    ---
    tags:
      - Transactions
    parameters:
      - name: transaction_id
        in: path
        required: true
        schema:
          type: string
        description: Transaction ID from previous request
    responses:
      201:
        description: Transaction sent successfully
      400:
        description: Transaction expired
      404:
        description: Transaction not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    # Clean up expired transactions
    expired_ids = cleanup_expired_transactions()
    
    # Check if the transaction has expired
    if transaction_id in expired_ids:
        return jsonify({
            "message": "Transaction has expired. Please create a new transaction.",
            "success": False
        }), 400
    
    # Check if transaction exists
    if transaction_id not in PENDING_TRANSACTIONS:
        return jsonify({
            "message": "Transaction not found or has expired. Please create a new transaction.",
            "success": False
        }), 404
    
    session = SessionLocal()
    try:
        # Get transaction data
        tx_data = PENDING_TRANSACTIONS[transaction_id]['data']
        user_id = tx_data['user_id']
        currency_name = tx_data['currency_name']
        recipient_address = tx_data['recipient_address']
        amount = tx_data['amount']
        blockchain_name = tx_data['blockchain_name']
        smart_contract_address = tx_data['smart_contract_address']
        sender_address = tx_data['sender_address']
        private_key = tx_data['private_key']
        tx_details = tx_data['tx_details']
        
        # Import the transfer service
        transfer_service = TransferService(session)
        
        # Check if this transaction was already sent
        tx_hash = tx_data.get('tx_hash')
        if tx_hash:
            # If we already sent this transaction, check its status
            status_info = TRANSACTION_STATUS.get(tx_hash, {})
            status = status_info.get('status', 'Unconfirmed')
            description = status_info.get('description', 'Transaction status is being checked')
            
            # Update status if needed
            if status == 'Unconfirmed':
                # Try to update status
                status, description = tatum_service.check_transaction_status(blockchain_name, tx_hash)
                
                # Update our status store
                TRANSACTION_STATUS[tx_hash] = {
                    'status': status,
                    'description': description,
                    'last_checked': datetime.now(),
                    'blockchain_name': blockchain_name,
                    'checks': status_info.get('checks', 0) + 1
                }
            
            # Get transaction URL
            transaction_url = get_transaction_url(blockchain_name, tx_hash)
            
            # Format response
            after_sending = {
                "details": f"\n✅ **Transaction Details:**\n"
                          f"   🔹 Transaction Hash: {tx_hash}\n"
                          f"   🔹 Transaction URL: {transaction_url}\n"
                          f"   🔹 Blockchain: {blockchain_name}\n"
                          f"   🔹 Currency: {currency_name}\n"
                          f"   🔹 Amount: {amount} {currency_name}\n"
                          f"   🔹 Recipient: {recipient_address}\n"
                          f"   🔹 Status: {status}\n"
                          f"   🔹 Status Description: {description}\n",
                "transaction_hash": tx_hash,
                "transaction_url": transaction_url,
                "status": status,
                "description": description,
                "success": True
            }
            
            return jsonify(after_sending), 200
            
        # List of main coins that don't need smart contract validation
        MAIN_COINS = ['TRX', 'BTC', 'ETH', 'BNB', 'MATIC', 'AVAX', 'ARB', 'DOT', 'XRP', 'SOL']
        
        try:
            # For main coins, don't pass smart_contract_address even if it's set
            if currency_name.upper() in MAIN_COINS:
                logger.info(f"{currency_name} is a main coin, not using smart contract address in confirmation")
                # Update tx_details to reflect this is not a token transaction
                tx_details['is_token'] = False
                tx_details['contract_address'] = None
                smart_contract_address = None
            
            # Send transaction using Tatum service
            result, error = tatum_service.send_transaction(
                blockchain_name, sender_address, private_key, recipient_address,
                amount, tx_details
            )
            
            if error:
                logger.error(f"Error sending transaction: {error}")
                return jsonify({
                    "message": f"Error sending transaction: {error}",
                    "details": f"Failed to send {amount} {currency_name} from {sender_address} to {recipient_address}.",
                    "blockchain": blockchain_name,
                    "success": False
                }), 500
            
            # Store transaction hash for later reference
            tx_hash = result["transaction_hash"]
            tx_data['tx_hash'] = tx_hash
            
            # Update transaction status store
            if 'status' in result:
                status = result['status']
                description = result.get('description', 'Transaction has been submitted to the blockchain network')
                
                # Store initial status
                TRANSACTION_STATUS[tx_hash] = {
                    'status': status,
                    'description': description,
                    'last_checked': datetime.now(),
                    'blockchain_name': blockchain_name,
                    'checks': result.get('confirmation_checks', 1)
                }
            else:
                # Default status if not provided
                status = 'Unconfirmed'
                description = 'Transaction has been submitted to the blockchain network and is waiting to be processed.'
                
                # Store initial status
                TRANSACTION_STATUS[tx_hash] = {
                    'status': status,
                    'description': description,
                    'last_checked': datetime.now(),
                    'blockchain_name': blockchain_name,
                    'checks': 1
                }
            
            # Get transaction URL
            transaction_url = get_transaction_url(blockchain_name, tx_hash)
            
            # Record the outgoing transaction in the database
            try:
                # Determine if this is a token or native currency
                asset_type = "token" if smart_contract_address else "native"
                
                # Record the transfer in the database
                transfer_service.record_outgoing_transaction(
                    tx_hash=tx_hash,
                    blockchain_name=blockchain_name,
                    sender_address=sender_address,
                    recipient_address=recipient_address,
                    amount=amount,
                    token_symbol=currency_name,
                    asset_type=asset_type,
                    token_contract=smart_contract_address,
                    fee=result.get('actual_fee', '0'),
                    explorer_url=transaction_url
                )
                
                logger.info(f"Successfully recorded outgoing transaction {tx_hash} in database")
            except Exception as e:
                # Just log the error if recording fails, but don't stop the transaction
                logger.error(f"Error recording transaction in database: {str(e)}")
            
            # Format transaction details after sending
            after_sending = {
                "details": f"\n✅ **Transaction Successfully Sent!**\n"
                          f"   🔹 Transaction Hash: {tx_hash}\n"
                          f"   🔹 Transaction URL: {transaction_url}\n"
                          f"   🔹 Blockchain: {blockchain_name}\n"
                          f"   🔹 Currency: {currency_name}\n"
                          f"   🔹 Amount: {amount} {currency_name}\n"
                          f"   🔹 Recipient: {recipient_address}\n"
                          f"   🔹 Actual Fee: {result['actual_fee']} {blockchain_name}\n"
                          f"   🔹 Sender Balance (After): {result['sender_balance_after']} {blockchain_name}\n"
                          f"   🔹 Status: {status}\n"
                          f"   🔹 Status Description: {description}\n",
                "transaction_hash": tx_hash,
                "transaction_url": transaction_url,
                "status": status,
                "description": description,
                "success": True
            }
            
            # Don't remove the transaction from pending yet - keep it for status checking
            # Instead, update it with the transaction hash
            return jsonify(after_sending), 201
            
        except ValueError as e:
            logger.error(f"Value error in confirm_transaction: {str(e)}")
            return jsonify({
                "message": str(e),
                "success": False
            }), 400
        except Exception as e:
            logger.error(f"Error sending transaction: {str(e)}", exc_info=True)
            return jsonify({
                "message": f"Error sending transaction: {str(e)}",
                "success": False
            }), 500
    
    except Exception as e:
        logger.error(f"Error in confirm_transaction: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500
    finally:
        session.close()

@send_bp.route('/<transaction_id>/cancel', methods=['GET'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
def cancel_transaction(transaction_id):
    """
    Cancel a pending transaction
    ---
    tags:
      - Transactions
    parameters:
      - name: transaction_id
        in: path
        required: true
        schema:
          type: string
        description: Transaction ID to cancel
    responses:
      200:
        description: Transaction cancelled successfully
      404:
        description: Transaction not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    # Clean up expired transactions
    cleanup_expired_transactions()
    
    # Check if transaction exists
    if transaction_id not in PENDING_TRANSACTIONS:
        return jsonify({
            "message": "Transaction not found or has already expired.",
            "success": False
        }), 404
    
    # Remove the transaction from pending transactions
    PENDING_TRANSACTIONS.pop(transaction_id, None)
    
    return jsonify({
        "message": "Transaction cancelled successfully.",
        "success": True
    }), 200

@send_bp.route('/transaction/<tx_hash>/status', methods=['GET'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def check_transaction_status(tx_hash):
    """
    Check the status of a transaction by its hash
    ---
    tags:
      - Transactions
    parameters:
      - name: tx_hash
        in: path
        required: true
        schema:
          type: string
        description: Transaction hash
      - name: blockchain
        in: query
        required: true
        schema:
          type: string
        description: Blockchain name (e.g., 'Tron', 'Ethereum')
    responses:
      200:
        description: Transaction status
      400:
        description: Invalid input
      404:
        description: Transaction not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        # Get blockchain name from query parameters
        blockchain_name = request.args.get('blockchain')
        if not blockchain_name:
            return jsonify({
                "message": "Blockchain name is required as a query parameter",
                "success": False
            }), 400
        
        # Check if we already have status for this transaction
        if tx_hash in TRANSACTION_STATUS:
            status_info = TRANSACTION_STATUS[tx_hash]
            status = status_info.get('status', 'Unknown')
            description = status_info.get('description', 'Transaction status is unknown')
            
            # If status is Unconfirmed, try to update it
            if status == 'Unconfirmed':
                updated_status = update_transaction_status(tx_hash, blockchain_name)
                if updated_status:
                    status = updated_status.get('status', status)
                    description = updated_status.get('description', description)
        else:
            # If we don't have status, try to get it
            status, description = tatum_service.check_transaction_status(blockchain_name, tx_hash)
            
            # Store initial status
            TRANSACTION_STATUS[tx_hash] = {
                'status': status,
                'description': description,
                'last_checked': datetime.now(),
                'blockchain_name': blockchain_name,
                'checks': 1
            }
        
        # Get transaction URL
        transaction_url = get_transaction_url(blockchain_name, tx_hash)
        
        return jsonify({
            "transaction_hash": tx_hash,
            "transaction_url": transaction_url,
            "status": status,
            "description": description,
            "last_checked": TRANSACTION_STATUS[tx_hash].get('last_checked', datetime.now()).isoformat(),
            "success": True
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking transaction status: {str(e)}")
        return jsonify({
            "message": f"Error checking transaction status: {str(e)}",
            "success": False
        }), 500 