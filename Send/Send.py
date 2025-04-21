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
from typing import Optional, Dict, Any
import os

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
logger.setLevel(logging.DEBUG)  # Set logging level to DEBUG
logger.info("Initializing send transaction module")

# Add file handler for detailed logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'send_transactions.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

send_bp = Blueprint('send', __name__)

# Initialize Tatum service with API key
TATUM_API_KEY = "t-67e5053a3320cff8fd79c921-0762aaf42dbc4c979d692389"
tatum_service = TatumService(TATUM_API_KEY)

# Add common alternative names and their Tatum API equivalents
BLOCKCHAIN_ALIASES = {
    "BNB": "bsc",
    "BSC": "bsc",
    "Binance Smart Chain": "bsc",
    "BINANCE SMART CHAIN": "bsc",
    "MATIC": "polygon",
    "Polygon": "polygon",
    "POLYGON": "polygon",
    "AVAX": "avalanche",
    "Avalanche": "avalanche",
    "AVALANCHE": "avalanche",
    "ARB": "arbitrum",
    "Arbitrum": "arbitrum",
    "ARBITRUM": "arbitrum",
    "DOT": "polkadot",
    "Polkadot": "polkadot",
    "POLKADOT": "polkadot",
    "SOL": "solana",
    "Solana": "solana",
    "SOLANA": "solana",
    "ETH": "ethereum",
    "Ethereum": "ethereum",
    "ETHEREUM": "ethereum",
    "BTC": "bitcoin",
    "Bitcoin": "bitcoin",
    "BITCOIN": "bitcoin",
    "TRX": "tron",
    "Tron": "tron",
    "TRON": "tron",
    "XRP": "xrp",
    "XRP": "xrp"
}

# Transaction URLs for different blockchains
TRANSACTION_URLS = {
    "ethereum": "https://etherscan.io/tx/{}",
    "bitcoin": "https://www.blockchain.com/btc/tx/{}",
    "tron": "https://tronscan.org/#/transaction/{}",
    "bsc": "https://bscscan.com/tx/{}",
    "polygon": "https://polygonscan.com/tx/{}",
    "avalanche": "https://snowtrace.io/tx/{}",
    "arbitrum": "https://arbiscan.io/tx/{}",
    "polkadot": "https://polkadot.subscan.io/extrinsic/{}",
    "xrp": "https://xrpscan.com/tx/{}",
    "solana": "https://explorer.solana.com/tx/{}"
}

# Add uppercase variants for compatibility
TRANSACTION_URLS.update({name.upper(): url for name, url in TRANSACTION_URLS.copy().items()})

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
    
    # Check if monitor is already running and thread is alive
    if transaction_monitor_running and transaction_monitor_thread and transaction_monitor_thread.is_alive():
        logger.debug("Transaction monitor already running, skipping initialization")
        return
        
    # Reset state if thread exists but is not alive
    if transaction_monitor_thread and not transaction_monitor_thread.is_alive():
        transaction_monitor_running = False
        transaction_monitor_thread = None
        logger.info("Resetting dead transaction monitor thread")
    
    transaction_monitor_running = True
    
    try:
        # Create and start the monitor thread
        transaction_monitor_thread = threading.Thread(target=monitor_transactions)
        transaction_monitor_thread.daemon = True
        transaction_monitor_thread.start()
        logger.info("Transaction monitor thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start transaction monitor thread: {str(e)}")
        transaction_monitor_running = False
        transaction_monitor_thread = None

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

def get_tatum_blockchain_name(blockchain_name: str) -> str:
    """Convert blockchain name to Tatum API compatible name"""
    return BLOCKCHAIN_ALIASES.get(blockchain_name, blockchain_name.lower())

@send_bp.route('/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def prepare_transaction():
    """
    Prepare a cryptocurrency transaction
    """
    try:
        logger.debug("Received prepare transaction request")
        
        # Get request data
        try:
            data = request.get_json()
            logger.debug(f"Request data: {data}")
        except Exception as e:
            logger.error(f"Error parsing JSON data: {str(e)}", exc_info=True)
            return jsonify({
                "success": False,
                "message": "Invalid JSON data in request",
                "error": str(e)
            }), 400

        if not data:
            logger.warning("No data received in request")
            return jsonify({
                "success": False,
                "message": "Invalid request data"
            }), 400

        try:
            # Extract parameters
            blockchain_name = data.get('blockchain_name')
            sender_address = data.get('sender_address')
            recipient_address = data.get('recipient_address')
            amount = data.get('amount')
            smart_contract_address = data.get('smart_contract_address')

            logger.debug(f"Extracted parameters - Blockchain: {blockchain_name}, Sender: {sender_address}, Recipient: {recipient_address}, Amount: {amount}")

            # Validate required fields
            if not all([blockchain_name, sender_address, recipient_address, amount]):
                missing_fields = []
                if not blockchain_name: missing_fields.append('blockchain_name')
                if not sender_address: missing_fields.append('sender_address')
                if not recipient_address: missing_fields.append('recipient_address')
                if not amount: missing_fields.append('amount')
                
                logger.warning(f"Missing required fields: {', '.join(missing_fields)}")
                return jsonify({
                    "success": False,
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400

            # Convert blockchain name to Tatum compatible format
            tatum_blockchain_name = get_tatum_blockchain_name(blockchain_name)
            
            # Validate blockchain
            if tatum_blockchain_name not in TRANSACTION_URLS:
                logger.warning(f"Unsupported blockchain: {blockchain_name}")
                return jsonify({
                    "success": False,
                    "message": f"Unsupported blockchain. Supported blockchains are: {', '.join(sorted(set(BLOCKCHAIN_ALIASES.keys())))}"
                }), 400

            # Get private key from database
            session = SessionLocal()
            try:
                logger.debug("Attempting to get private key from database")
                try:
                    private_key = get_private_key_from_db(session, sender_address, blockchain_name)
                except ValueError as ve:
                    logger.warning(f"Error getting private key: {str(ve)}")
                    return jsonify({
                        "success": False,
                        "message": str(ve)
                    }), 400
                except Exception as e:
                    logger.error(f"Unexpected error getting private key: {str(e)}")
                    return jsonify({
                        "success": False,
                        "message": "An unexpected error occurred while accessing wallet credentials"
                    }), 500

                # Use the global tatum_service instance
                logger.debug("Using Tatum service for transaction preparation")
                tx_details, error = tatum_service.prepare_transaction(
                    blockchain_name=tatum_blockchain_name,
                    sender_address=sender_address,
                    private_key=private_key,
                    recipient_address=recipient_address,
                    amount=amount,
                    smart_contract_address=smart_contract_address
                )

                if error:
                    logger.error(f"Error preparing transaction: {error}")
                    return jsonify({
                        "success": False,
                        "message": error
                    }), 400

                # Use transaction hash from Tatum as transaction_id
                transaction_id = tx_details.get("transaction_hash")
                if not transaction_id:
                    logger.error("Transaction hash not found in response")
                    return jsonify({
                        "success": False,
                        "message": "Transaction hash not found in response"
                    }), 500
                    
                logger.debug(f"Using transaction hash as ID: {transaction_id}")

                # Store transaction details with expiration time (2 minutes from now)
                expiration_time = datetime.now() + timedelta(minutes=2)
                PENDING_TRANSACTIONS[transaction_id] = {
                    'data': {
                        'blockchain_name': blockchain_name,
                        'sender_address': sender_address,
                        'private_key': private_key,
                        'recipient_address': recipient_address,
                        'amount': amount,
                        'smart_contract_address': smart_contract_address,
                        'tx_details': tx_details
                    },
                    'expires_at': expiration_time
                }

                logger.info(f"Transaction prepared successfully. Hash: {transaction_id}")
                return jsonify({
                    "success": True,
                    "message": "Transaction prepared successfully",
                    "transaction_id": transaction_id,
                    "expires_at": expiration_time.isoformat(),
                    "details": {
                        "sender": sender_address,
                        "recipient": recipient_address,
                        "amount": amount,
                        "blockchain": blockchain_name,
                        "estimated_fee": tx_details.get("estimated_fee"),
                        "sender_balance_before": tx_details.get("sender_balance_before"),
                        "sender_balance_after": tx_details.get("sender_balance_after"),
                        "explorer_url": get_transaction_url(blockchain_name, transaction_id)
                    }
                }), 200

            except Exception as db_error:
                logger.error(f"Database error: {str(db_error)}", exc_info=True)
                return jsonify({
                    "success": False,
                    "message": "Database error occurred",
                    "error": str(db_error)
                }), 500
            finally:
                session.close()

        except Exception as validation_error:
            logger.error(f"Validation error: {str(validation_error)}", exc_info=True)
            return jsonify({
                "success": False,
                "message": "Error validating transaction data",
                "error": str(validation_error)
            }), 400

    except Exception as e:
        logger.error(f"Unexpected error in prepare_transaction: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "An unexpected error occurred",
            "error": str(e)
        }), 500

@send_bp.route('/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
def confirm_transaction():
    """
    Confirm and send a prepared transaction
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data"
            }), 400

        # Use tx_hash parameter for the transaction identifier
        tx_hash = data.get('tx_hash')
        if not tx_hash:
            # For backward compatibility, also check for transaction_id
            tx_hash = data.get('transaction_id')
            
        if not tx_hash:
            return jsonify({
                "success": False,
                "message": "Transaction hash (tx_hash) is required"
            }), 400

        # Get blockchain name from request
        blockchain_name = data.get('blockchain')
        if not blockchain_name:
            return jsonify({
                "success": False,
                "message": "Blockchain name is required"
            }), 400

        # Clean up expired transactions
        expired_ids = cleanup_expired_transactions()
        
        # Check if the transaction has expired
        if tx_hash in expired_ids:
            return jsonify({
                "success": False,
                "message": "Transaction has expired. Please create a new transaction."
            }), 400
        
        # Check if transaction exists
        if tx_hash not in PENDING_TRANSACTIONS:
            return jsonify({
                "success": False,
                "message": "Transaction not found or has expired. Please create a new transaction."
            }), 404
        
        # Get transaction data
        tx_data = PENDING_TRANSACTIONS[tx_hash]['data']
        
        # Use the global tatum_service instance
        logger.debug("Using Tatum service for transaction confirmation")

        # Send the transaction
        result, error = tatum_service.send_transaction(
            blockchain_name=blockchain_name,
            sender_address=tx_data['sender_address'],
            private_key=tx_data['private_key'],
            recipient_address=tx_data['recipient_address'],
            amount=tx_data['amount'],
            tx_details=tx_data['tx_details']
        )

        if error:
            return jsonify({
                "success": False,
                "message": error
            }), 400

        # Remove the transaction from pending transactions
        PENDING_TRANSACTIONS.pop(tx_hash, None)

        return jsonify({
            "success": True,
            "message": "Transaction sent successfully",
            "transaction_hash": result["transaction_hash"],
            "status": result["status"],
            "fee": result["actual_fee"],
            "sender_balance_after": result["sender_balance_after"],
            "explorer_url": get_transaction_url(blockchain_name, result["transaction_hash"])
        }), 200

    except Exception as e:
        logger.error(f"Error confirming transaction: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error confirming transaction: {str(e)}"
        }), 500

@send_bp.route('/<transaction_hash>/status', methods=['GET'])
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

def get_private_key_from_db(session, address, blockchain_name):
    """Get private key from database"""
    try:
        # Get blockchain ID
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainName.ilike(blockchain_name)
        ).first()
        
        if not blockchain:
            logger.warning(f"Blockchain {blockchain_name} not found")
            raise ValueError(f"Blockchain {blockchain_name} not supported")
        
        # Get address record
        address_record = session.query(Address).filter(
            Address.PublicAddress == address,
            Address.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not address_record:
            logger.warning(f"Address {address} not found for blockchain {blockchain_name}")
            raise ValueError(f"Address {address} not found for blockchain {blockchain_name}")
        
        # Decrypt private key
        try:
            private_key = decrypt_private_key_aes(address_record.PrivateKey)
            if not private_key:
                raise ValueError("Failed to decrypt private key")
            return private_key
        except Exception as e:
            logger.error(f"Error decrypting private key: {str(e)}")
            raise ValueError(f"Error accessing wallet credentials: {str(e)}")
            
    except ValueError as ve:
        # Re-raise ValueError with same message
        raise
    except Exception as e:
        logger.error(f"Error getting private key from database: {str(e)}")
        raise ValueError(f"Database error occurred: {str(e)}")

@send_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify routing is working"""
    logger.debug("Test endpoint called")
    return jsonify({
        "success": True,
        "message": "Send blueprint is working correctly",
        "timestamp": datetime.now().isoformat()
    }) 