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
import asyncio
from web3 import Web3
from eth_account import Account

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, Transfers
from security.validators import InputValidator, SecurityUtils, ValidationError
from security.encryption import decrypt_private_key_aes
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from services.tatum_service import TatumService

# Configure logging
logger = get_logger(__file__)

# Initialize Tatum service
tatum_service = TatumService()

send_bp = Blueprint('send', __name__)

# Store pending transactions with expiration time
PENDING_TRANSACTIONS = {}

@send_bp.route('/prepare', methods=['POST'])
async def prepare():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['sender_address', 'recipient_address', 'amount', 'blockchain']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "message": f'Missing required field: {field}'
                }), 400
        
        # Validate blockchain
        if data['blockchain'] not in ['ethereum', 'bsc']:
            return jsonify({
                "success": False,
                "message": 'Invalid blockchain. Supported values: ethereum, bsc'
            }), 400
        
        # Convert amount to Decimal
        try:
            amount = Decimal(str(data['amount']))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": 'Invalid amount format'
            }), 400
        
        # Prepare transaction
        tx_details, error = await tatum_service.prepare_transaction(
            blockchain_name=data['blockchain'],
            sender_address=data['sender_address'],
            recipient_address=data['recipient_address'],
            amount=amount,
            smart_contract_address=data.get('smart_contract_address')
        )
        
        if error:
            return jsonify({
                "success": False,
                "message": error
            }), 400
        
        # Return flat response structure
        return jsonify(tx_details), 200
        
    except Exception as e:
        logger.error(f"Error in prepare endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "message": 'Internal server error'
        }), 500

@send_bp.route('/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
async def confirm_transaction():
    """
    Finalize a prepared transaction, sign it locally, and broadcast it to the blockchain.
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data"
            }), 400

        # Get transaction ID
        transaction_id = data.get('transaction_id')
        if not transaction_id:
            return jsonify({
                "success": False,
                "message": "Transaction ID is required"
            }), 400

        # Clean up expired transactions
        expired_ids = cleanup_expired_transactions()
        
        # Check if the transaction has expired
        if transaction_id in expired_ids:
            return jsonify({
                "success": False,
                "message": "Transaction has expired. Please create a new transaction."
            }), 400
        
        # Check if transaction exists
        if transaction_id not in PENDING_TRANSACTIONS:
            return jsonify({
                "success": False,
                "message": "Transaction not found or has expired. Please create a new transaction."
            }), 404
        
        # Get transaction data
        tx_data = PENDING_TRANSACTIONS[transaction_id]['data']
        
        # Get private key from database
        session = SessionLocal()
        try:
            private_key = get_private_key_from_db(session, tx_data['sender_address'], tx_data['blockchain_name'])
            if not private_key:
                return jsonify({
                    "success": False,
                    "message": "Failed to get private key"
                }), 400
        finally:
            session.close()

        # Sign and broadcast transaction using Tatum
        tx_hash, error = await tatum_service.broadcast_transaction(
            blockchain_name=tx_data['blockchain_name'],
            signed_tx=tx_data['tx_details']['signed_tx']
        )
        
        if error:
            return jsonify({
                "success": False,
                "message": error
            }), 400

        # Remove the transaction from pending transactions
        PENDING_TRANSACTIONS.pop(transaction_id, None)

        # Return success response with transaction details
        return jsonify({
            "success": True,
            "message": "Transaction sent successfully",
            "transaction_hash": tx_hash,
            "status": "Unconfirmed",
            "description": "Transaction has been submitted to the blockchain network"
        }), 200

    except Exception as e:
        logger.error(f"Error confirming transaction: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error confirming transaction: {str(e)}"
        }), 500

def cleanup_expired_transactions():
    """Remove expired transactions from the pending transactions dictionary"""
    current_time = datetime.now()
    expired_ids = [tx_id for tx_id, tx_data in PENDING_TRANSACTIONS.items() 
                  if tx_data['expires_at'] < current_time]
    
    for tx_id in expired_ids:
        logger.info(f"Transaction {tx_id} expired and removed from pending transactions")
        PENDING_TRANSACTIONS.pop(tx_id, None)
    
    return expired_ids

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
            
            # Never log the private key
            logger.debug(f"Successfully decrypted private key for address {address} on blockchain {blockchain_name}")
            
            return private_key
        except Exception as e:
            # Make sure we don't log any sensitive information
            logger.error(f"Error decrypting private key for address {address}: {str(e)}")
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