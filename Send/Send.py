from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
import logging
import json
from decimal import Decimal
import uuid
import time
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
import os
from sqlalchemy import func

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, Transfers, UserHolding
from security.validators import InputValidator, SecurityUtils, ValidationError
from security.encryption import decrypt_private_key_aes, mask_private_key
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from services.tatum_service import TatumService, transaction_manager

# Configure logging
logger = get_logger(__file__)

# Initialize Tatum service
tatum_service = TatumService()

send_bp = Blueprint('send', __name__)

@send_bp.route('/prepare', methods=['POST'])
def prepare():
    """Prepare a transaction for sending"""
    try:
        data = request.get_json()
        logger.debug(f"Prepare request data: {json.dumps(data, indent=2)}")
        
        # Validate input data
        required_fields = ['sender_address', 'recipient_address', 'amount', 'blockchain']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({"success": False, "message": f'Missing required field: {field}'}), 400
        
        # Normalize the blockchain name for consistent handling
        original_blockchain = data['blockchain']
        normalized_blockchain = normalize_blockchain_name(original_blockchain)
        data['blockchain'] = normalized_blockchain
        
        if original_blockchain != normalized_blockchain:
            logger.debug(f"Normalized blockchain name from '{original_blockchain}' to '{normalized_blockchain}'")
                
        if normalized_blockchain not in tatum_service.SUPPORTED_BLOCKCHAINS:
            logger.error(f"Unsupported blockchain: {normalized_blockchain}")
            return jsonify({"success": False, "message": f"Unsupported blockchain: {normalized_blockchain}"}), 400
            
        try:
            amount = Decimal(str(data['amount']))
        except (ValueError, TypeError):
            logger.error(f"Invalid amount format: {data['amount']}")
            return jsonify({"success": False, "message": 'Invalid amount format'}), 400
            
        # Extract input data
        blockchain_name = normalized_blockchain
        sender_address = data['sender_address']
        recipient_address = data['recipient_address']
        smart_contract_address = data.get('smart_contract_address')
        
        # Log the key information
        logger.debug(f"Preparing transaction: {blockchain_name}, from {sender_address} to {recipient_address}, amount {amount}")
        
        # Generate a unique transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Store the raw transaction data
        tx_data = {
            'blockchain_name': blockchain_name,
            'sender_address': sender_address,
            'recipient_address': recipient_address,
            'amount': str(amount),
            'smart_contract_address': smart_contract_address,
            'created_at': datetime.now().isoformat()
        }
        
        # استفاده از تابع جدید برای ذخیره تراکنش
        expires_at = store_pending_transaction(transaction_id, tx_data, expires_minutes=15)
        
        # Get fee information based on blockchain
        if blockchain_name.lower() == 'tron':
            # For TRON, return with minimal information as fees are very low
            response = {
                "success": True,
                "details": {
                    "blockchain": blockchain_name,
                    "amount": str(amount),
                    "estimated_fee": "0",
                    "sender": sender_address,
                    "recipient": recipient_address,
                    "sender_balance_before": "Unknown",  # Would need a balance check
                    "sender_balance_after": "Unknown"
                },
                "transaction_id": transaction_id,
                "expires_at": expires_at.isoformat(),
                "message": "Transaction prepared successfully. TRON transactions typically have very low fees."
            }
        else:
            # For other blockchains, get fee estimate if available
            try:
                # Get a very basic fee estimate for the response
                fee_estimate = "0.0001"  # Default minimal estimate
                
                response = {
                    "success": True,
                    "details": {
                        "blockchain": blockchain_name,
                        "amount": str(amount),
                        "estimated_fee": fee_estimate,
                        "sender": sender_address,
                        "recipient": recipient_address,
                        "sender_balance_before": "Unknown",
                        "sender_balance_after": "Unknown"
                    },
                    "transaction_id": transaction_id,
                    "expires_at": expires_at.isoformat(),
                    "message": "Transaction prepared successfully"
                }
            except Exception as e:
                logger.error(f"Error getting fee estimate: {str(e)}")
                # Continue without fee estimate
                response = {
                    "success": True,
                    "details": {
                        "blockchain": blockchain_name,
                        "amount": str(amount),
                        "estimated_fee": "Unknown",
                        "sender": sender_address,
                        "recipient": recipient_address
                    },
                    "transaction_id": transaction_id,
                    "expires_at": expires_at.isoformat(),
                    "message": "Transaction prepared with unknown fee estimate"
                }
        
        logger.debug(f"Prepare response: {json.dumps(response, indent=2)}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.exception(f"Error in prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error preparing transaction: {str(e)}"}), 500

# ✅ TODO: Improve debugging for transaction confirmation:
# - Log the full error returned from tatum_service.send_transaction
# - Ensure unexpected exceptions are properly caught and logged with full traceback
@send_bp.route('/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
def confirm_transaction():
    """Confirm and execute a prepared transaction."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request data"}), 400
        
        # لاگ کامل داده‌های دریافتی برای دیباگ بهتر (حذف کلید خصوصی اگر وجود داشت)
        safe_data = {k: v for k, v in data.items() if k != 'private_key'}
        logger.debug(f"Confirm request data: {json.dumps(safe_data, indent=2)}")
        
        # Normalize blockchain name if present
        if 'blockchain_name' in data:
            original_blockchain = data['blockchain_name']
            normalized_blockchain = normalize_blockchain_name(data['blockchain_name'])
            data['blockchain_name'] = normalized_blockchain
            if original_blockchain != normalized_blockchain:
                logger.debug(f"Normalized blockchain name from '{original_blockchain}' to '{normalized_blockchain}'")
        
        # اطمینان از مخفی کردن کلید خصوصی در لاگ‌ها
        # تبدیل کل متن به رشته و کلیدهای خصوصی را مخفی کردن
        safe_log = mask_private_key(json.dumps(data))
            
        transaction_id = data.get('transaction_id')
        if not transaction_id:
            return jsonify({"success": False, "message": "Transaction ID is required"}), 400
        
        # برداشتن داده‌های اضافی اختیاری که کلاینت ممکن است ارسال کند
        sender_address = data.get('sender_address')
        recipient_address = data.get('recipient_address')
        amount = data.get('amount')
        blockchain_name = data.get('blockchain_name')
        
        logger.debug(f"Processing confirm for transaction ID: {transaction_id}")
        logger.debug(f"Additional data: sender={sender_address}, recipient={recipient_address}, amount={amount}, blockchain={blockchain_name}")
        
        # تلاش برای بازیابی داده‌های تراکنش
        tx_data = get_transaction(transaction_id)
        
        # Debug all pending transactions
        logger.debug(f"Current pending transactions: {list(transaction_manager.pending_transactions.keys())}")
        
        if not tx_data:
            logger.error(f"Transaction {transaction_id} not found. Available IDs: {list(transaction_manager.pending_transactions.keys())}")
            
            # اگر تراکنش با ID مشخص پیدا نشد، سعی کنیم تراکنش را مجدداً بر اساس آدرس‌ها و مقدار ایجاد کنیم
            if sender_address and recipient_address and amount and blockchain_name:
                logger.info(f"Trying to recreate transaction data from request parameters")
                
                # Normalize blockchain name
                normalized_blockchain = normalize_blockchain_name(blockchain_name)
                if blockchain_name != normalized_blockchain:
                    logger.debug(f"Normalized blockchain name in recreation: '{blockchain_name}' -> '{normalized_blockchain}'")
                
                tx_data = {
                    'blockchain_name': normalized_blockchain,
                    'sender_address': sender_address,
                    'recipient_address': recipient_address,
                    'amount': amount,
                    'smart_contract_address': '',
                    'created_at': datetime.now().isoformat()
                }
                
                # ذخیره تراکنش جدید
                store_pending_transaction(transaction_id, tx_data)
                logger.info(f"Recreated transaction data for ID: {transaction_id}")
            else:
                return jsonify({"success": False, "message": "Transaction data not found and could not be recreated from request"}), 400
            
        # بررسی فیلدهای ضروری
        for field in ['blockchain_name', 'sender_address', 'recipient_address', 'amount']:
            if field not in tx_data:
                return jsonify({"success": False, "message": f"Missing {field} in transaction data"}), 400
                
        # استخراج آدرس فرستنده و نام بلاکچین از داده‌های تراکنش
        blockchain_name = tx_data['blockchain_name']
        sender_address = tx_data['sender_address']
        
        # Ensure blockchain name is normalized for database lookup
        blockchain_name = normalize_blockchain_name(blockchain_name)
        logger.debug(f"Using normalized blockchain name for DB lookup: {blockchain_name}")
        
        # اگر آدرس فرستنده در درخواست ارسال شده با آدرس در تراکنش ذخیره شده متفاوت باشد
        if sender_address and data.get('sender_address') and sender_address != data.get('sender_address'):
            logger.warning(f"Sender address mismatch: {sender_address} (stored) vs {data.get('sender_address')} (request)")
            logger.info(f"Using stored sender address: {sender_address} for key retrieval")
        
        # بازیابی کلید خصوصی از دیتابیس
        session = SessionLocal()
        try:
            # بازیابی کلید خصوصی
            private_key = get_private_key_from_db(session, sender_address, blockchain_name)
            if not private_key:
                logger.error(f"Failed to retrieve private key for address {sender_address} on blockchain {blockchain_name}")
                return jsonify({"success": False, "message": "Error retrieving wallet credentials"}), 400
            
            logger.debug(f"Successfully retrieved private key for {sender_address}")
            
            # ارسال تراکنش با استفاده از کلید بازیابی شده
            logger.debug(f"Sending transaction with ID: {transaction_id}")
            result, error = tatum_service.send_transaction_by_id(
                transaction_id=transaction_id,
                private_key=private_key
            )
            
            if error:
                logger.error(f"Error from send_transaction_by_id: {error}")
                return jsonify({"success": False, "message": error}), 400
                
            # حذف تراکنش از لیست در انتظار
            transaction_manager.remove_transaction(transaction_id)
            logger.debug(f"Removed transaction {transaction_id} from pending transactions")
                
            logger.debug(f"Transaction confirmed successfully: {json.dumps(result, default=str)}")
            return jsonify({
                "success": True, 
                "transaction_hash": result.get("transaction_hash", ""),
                "status": "Confirmed",
                "description": "Transaction has been submitted to the blockchain network.",
                "message": "Transaction sent successfully"
            }), 200
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return jsonify({"success": False, "message": str(ve)}), 400
        except Exception as e:
            logger.exception(f"Exception in confirm_transaction: {str(e)}")
            return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500
        finally:
            session.close()
            
    except Exception as e:
        logger.exception(f"Error in confirm_transaction: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

def store_pending_transaction(transaction_id, tx_data, expires_minutes=30):
    """Store a transaction in the pending transactions dictionary with expiry time."""
    # Ensure blockchain name is normalized
    if 'blockchain_name' in tx_data:
        original_blockchain = tx_data['blockchain_name']
        normalized_blockchain = normalize_blockchain_name(original_blockchain)
        if original_blockchain != normalized_blockchain:
            logger.debug(f"Normalizing blockchain name in transaction data: '{original_blockchain}' -> '{normalized_blockchain}'")
            tx_data['blockchain_name'] = normalized_blockchain
            
    # Store transaction using TransactionManager
    transaction_manager.store_transaction(transaction_id, tx_data)
    
    logger.debug(f"Stored transaction {transaction_id}")
    logger.debug(f"Transaction data: {json.dumps({k: v for k, v in tx_data.items() if k != 'private_key'}, indent=2)}")
    logger.debug(f"Current pending transactions: {list(transaction_manager.pending_transactions.keys())}")
    
    # Get the stored transaction info and return its expiration time
    tx_info = transaction_manager.pending_transactions.get(transaction_id)
    return tx_info["expires_at"] if tx_info else None

@send_bp.route('/debug-transactions', methods=['GET'])
def debug_transactions():
    """Debug endpoint to see current pending transactions."""
    result = {}
    for tx_id, tx_info in transaction_manager.pending_transactions.items():
        result[tx_id] = {
            'expires_at': tx_info['expires_at'].isoformat(),
            'created_at': tx_info['created_at'].isoformat() if 'created_at' in tx_info else 'unknown',
            'data': {k: v for k, v in tx_info['data'].items() if k != 'private_key'}  # Don't include private key
        }
    return jsonify(result), 200

def get_transaction(transaction_id):
    """
    Get transaction data from TransactionManager.
    """
    tx_data = transaction_manager.get_transaction(transaction_id)
    if tx_data:
        logger.debug(f"Found transaction data for {transaction_id}")
        return tx_data
    
    logger.warning(f"Transaction {transaction_id} not found in pending transactions")
    logger.debug(f"Available transaction IDs: {list(transaction_manager.pending_transactions.keys())}")
    return None

@send_bp.route('/debug-transaction/<transaction_id>', methods=['GET'])
def debug_transaction(transaction_id):
    """Debug endpoint to see a specific transaction."""
    tx_data = transaction_manager.get_transaction(transaction_id)
    if tx_data:
        result = {
            'exists': True,
            'data': {k: v for k, v in tx_data.items() if k != 'private_key'}  # Don't include private key
        }
    else:
        result = {
            'exists': False,
            'all_transactions': list(transaction_manager.pending_transactions.keys())
        }
    return jsonify(result), 200

def normalize_blockchain_name(blockchain_name):
    """Normalize blockchain names to ensure consistency across API and database"""
    if not blockchain_name:
        return ""
        
    name = blockchain_name.lower().strip()
    
    # Map of common variations to standard names
    name_mapping = {
        "eth": "ethereum",
        "btc": "bitcoin",
        "bnb": "bsc",
        "binance": "bsc",
        "binance smart chain": "bsc",
        "bnb smart chain": "bsc",
        "binancecoin": "bsc",
        "matic": "polygon",
        "xrp": "ripple",
        "xlm": "stellar",
        "avax": "avalanche",
        "arb": "arbitrum",
        "dot": "polkadot",
        "ada": "cardano",
        "trx": "tron"
    }
    
    return name_mapping.get(name, name)

def get_private_key_from_db(session, address, blockchain_name):
    """Get private key from database"""
    try:
        logger.debug(f"Retrieving private key for address {address} on blockchain {blockchain_name}")
        
        # Blockchain name should already be normalized, but ensure consistency
        normalized_blockchain_name = normalize_blockchain_name(blockchain_name)
        if blockchain_name != normalized_blockchain_name:
            logger.debug(f"Normalized blockchain name from '{blockchain_name}' to '{normalized_blockchain_name}' for database lookup")
            blockchain_name = normalized_blockchain_name
        
        # Get blockchain ID - first try exact match
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainName.ilike(blockchain_name)
        ).first()
        
        if not blockchain:
            # Try with case-insensitive 'contains' logic as fallback
            blockchain = session.query(Blockchains).filter(
                func.lower(Blockchains.BlockchainName).contains(blockchain_name.lower())
            ).first()
            
            if not blockchain:
                logger.warning(f"Blockchain {blockchain_name} not found in database")
                raise ValueError(f"Blockchain {blockchain_name} not supported")
            
        logger.debug(f"Found blockchain ID: {blockchain.BlockchainID} with name: {blockchain.BlockchainName}")
        
        # Get address record
        address_record = session.query(Address).filter(
            Address.PublicAddress == address,
            Address.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not address_record:
            logger.warning(f"Address {address} not found for blockchain {blockchain_name}")
            raise ValueError(f"Address {address} not found for blockchain {blockchain_name}")
            
        logger.debug(f"Found address record with ID: {address_record.AddressID} in wallet: {address_record.WalletID}")
        
        # Check if PrivateKey exists
        if not address_record.PrivateKey:
            logger.warning(f"No private key stored for address {address}")
            raise ValueError(f"No private key stored for address {address}")
        
        # Decrypt private key
        try:
            logger.debug("Attempting to decrypt private key")
            private_key = decrypt_private_key_aes(address_record.PrivateKey)
            
            if not private_key:
                logger.error("Decryption returned empty private key")
                raise ValueError("Failed to decrypt private key")
            
            # Never log the actual private key
            logger.debug(f"Successfully decrypted private key for address {address} (length: {len(private_key)})")
            
            return private_key
        except Exception as e:
            # Make sure we don't log any sensitive information
            logger.error(f"Error decrypting private key for address {address}: {str(e)}")
            raise ValueError(f"Error accessing wallet credentials: {str(e)}")
            
    except ValueError as ve:
        # Re-raise ValueError with same message
        logger.error(f"ValueError: {str(ve)}")
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