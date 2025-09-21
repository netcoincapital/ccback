from flask import Blueprint, jsonify, request, redirect, url_for
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
import requests
from functools import wraps

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, Transfers, UserHolding
from security.validators import InputValidator, SecurityUtils, ValidationError
from security.encryption import decrypt_private_key_aes, mask_private_key
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from services.tatum_service import TatumService, transaction_manager
from api.middleware import log_transaction_request, sanitize_data

# Import blockchain service factory
from utils.blockchain_service_factory import BlockchainServiceFactory

# Configure logging
logger = get_logger(__file__)

# Initialize Tatum service
tatum_service = TatumService()

# Create the send blueprint
send_bp = Blueprint('send', __name__)

# Dictionary mapping blockchain names to services (will be populated on demand)
blockchain_services = {}

# Decorator for API error handling and request processing
def blockchain_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Invalid request data"}), 400
                
            # Log the request (without private key if present)
            safe_data = sanitize_sensitive_data(data)
            logger.debug(f"API request data: {json.dumps(safe_data, indent=2)}")
            
            return func(data, *args, **kwargs)
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return jsonify({"success": False, "message": str(ve)}), 400
        except Exception as e:
            logger.exception(f"API error: {str(e)}")
            return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    return wrapper

# Helper function to sanitize sensitive data
def sanitize_sensitive_data(data):
    """Remove sensitive data from request or response data for logging"""
    if not data or not isinstance(data, dict):
        return data
        
    safe_data = data.copy()
    sensitive_fields = [
        'private_key', 'privateKey', 'fromPrivateKey', 
        'fromSecret', 'secret', 'mnemonic', 'passphrase', 
        'password', 'seed', 'key'
    ]
    
    for field in sensitive_fields:
        if field in safe_data:
            safe_data[field] = '***'
            
    return safe_data

# Helper function to get blockchain service
def get_blockchain_service(blockchain_name):
    """Get a blockchain service from factory or cache"""
    try:
        normalized_name = BlockchainServiceFactory.normalize_name(blockchain_name)
        if not normalized_name:
            logger.error(f"Unsupported blockchain: {blockchain_name}")
            return None

        # Return from cache if available
        if normalized_name in blockchain_services:
            return blockchain_services[normalized_name]

        # Get from factory
        service = BlockchainServiceFactory.get_service(normalized_name)
        blockchain_services[normalized_name] = service
        return service
    except Exception as e:
        logger.error(f"Error getting blockchain service for {blockchain_name}: {str(e)}")
        return None

# Helper function to normalize blockchain names
def normalize_blockchain_name(blockchain_name):
    """Normalize blockchain name to standard format"""
    return BlockchainServiceFactory.normalize_name(blockchain_name)

# Map old blockchain names to new API endpoint names
def get_api_blockchain_name(blockchain_name):
    """Convert normalized blockchain name to API endpoint name"""
    # Make sure we handle both BSC and binance-smart-chain correctly
    if blockchain_name and blockchain_name.lower() in ['bsc', 'binance-smart-chain', 'binance', 'bnb']:
        return 'bsc'
        
    api_mapping = {
        "ethereum": "ethereum",
        "binance-smart-chain": "bsc",
        "bsc": "bsc",
        "bitcoin": "bitcoin",
        "tron": "tron",
        "polygon": "polygon",
        "avalanche": "avalanche",
        "arbitrum": "arbitrum",
        "optimism": "optimism"
    }
    return api_mapping.get(blockchain_name, blockchain_name)

# Global API endpoint (backward compatibility) for preparing transactions
@send_bp.route('/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def prepare(data):
    """Global prepare endpoint that routes to the appropriate blockchain service"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for transaction preparation"
            }), 400
        
        # Extract blockchain from request
        blockchain = data.get('blockchain')
        if not blockchain:
            return jsonify({"success": False, "message": "Missing blockchain parameter"}), 400
            
        # Normalize blockchain name
        normalized_blockchain = normalize_blockchain_name(blockchain)
        if not normalized_blockchain:
            return jsonify({"success": False, 
                           "message": f"Unsupported blockchain: {blockchain}"}), 400
        
        # Get API blockchain name for routing
        api_blockchain = get_api_blockchain_name(normalized_blockchain)
        
        # Log the routing
        logger.info(f"Routing prepare request from legacy endpoint to /{api_blockchain}/prepare for user {user_id}")
        
        # First try direct service call
        try:
            # Get service for this blockchain
            service = get_blockchain_service(normalized_blockchain)
            if not service:
                return jsonify({"success": False, "message": f"Blockchain service not available: {normalized_blockchain}"}), 400
                
            # Extract common parameters
            sender = data.get('sender_address')
            recipient = data.get('recipient_address')
            amount = data.get('amount')
            contract = data.get('smart_contract_address')
            
            # Validate required fields
            if not sender or not recipient or not amount:
                return jsonify({"success": False, 
                               "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
                
            # Call the service's prepare method
            logger.info(f"Directly calling prepare_transaction for {normalized_blockchain}")
            tx_details, error = service.prepare_transaction(sender, recipient, amount, contract)
            
            if error:
                return jsonify({"success": False, "message": error}), 400
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                tx_details['userId'] = user_id
                
            logger.info(f"Successfully prepared transaction for {normalized_blockchain} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as direct_error:
            logger.warning(f"Error in direct service call: {str(direct_error)}, trying API endpoint")
            
            # Fall back to API endpoint call
            try:
                # Make request to the blockchain-specific API endpoint
                api_url = f"{request.host_url.rstrip('/')}/api/{api_blockchain}/prepare"
                logger.debug(f"Making API request to: {api_url}")
                
                # Prepare headers
                headers = {"Content-Type": "application/json"}
                
                # Ensure data includes proper UserID
                api_data = data.copy()
                api_data['UserID'] = user_id
                api_data['userId'] = user_id
                
                # Make the API call
                response = requests.post(
                    api_url,
                    json=api_data,
                    headers=headers
                )
                
                # Return the response from the API endpoint
                return jsonify(response.json()), response.status_code
                
            except Exception as api_error:
                logger.error(f"Error in API endpoint call: {str(api_error)}")
                return jsonify({
                    "success": False, 
                    "message": f"Error preparing transaction: {str(api_error)}"
                }), 500
                
    except Exception as e:
        logger.error(f"Error in prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# Global API endpoint (backward compatibility) for confirming transactions
@send_bp.route('/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def confirm(data):
    """Global confirm endpoint that routes to the appropriate blockchain service"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in confirm request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for transaction confirmation"
            }), 400
        
        # Extract blockchain and transaction ID from request
        blockchain = data.get('blockchain')
        transaction_id = data.get('transaction_id')
        
        if not blockchain or not transaction_id:
            return jsonify({"success": False, 
                          "message": "Missing required parameters: blockchain or transaction_id"}), 400
                          
        # Normalize blockchain name
        normalized_blockchain = normalize_blockchain_name(blockchain)
        if not normalized_blockchain:
            return jsonify({"success": False, 
                          "message": f"Unsupported blockchain: {blockchain}"}), 400
        
        # Get API blockchain name for routing
        api_blockchain = get_api_blockchain_name(normalized_blockchain)
        
        # Log the routing (without private key)
        safe_data = {k: v for k, v in data.items() if k != 'private_key'}
        logger.info(f"Routing confirm request from legacy endpoint to /{api_blockchain}/confirm for user {user_id}")
        logger.debug(f"Confirm request data (sanitized): {json.dumps(safe_data, indent=2)}")
        
        # Extract private key (never log this)
        private_key = data.get('private_key')
        
        # ✅ SECURITY IMPROVEMENT: If no private key provided, get it from database
        if not private_key:
            logger.info(f"No private key provided in request, retrieving from database for blockchain {normalized_blockchain}")
            
            # Need to get sender address from transaction data first
            service = get_blockchain_service(normalized_blockchain)
            if not service:
                return jsonify({"success": False, 
                              "message": f"Blockchain service not available: {normalized_blockchain}"}), 503
            
            # Try to get transaction from shared storage
            from services.shared_storage import shared_storage
            tx_data = shared_storage.get_transaction(transaction_id)
            
            if not tx_data:
                return jsonify({"success": False, "message": "Transaction not found or expired"}), 400
            
            # Get sender address from transaction data
            sender_address = tx_data.get('details', {}).get('sender')
            if not sender_address:
                return jsonify({"success": False, "message": "Transaction data incomplete - no sender address"}), 400
            
            # Retrieve private key from database
            session = SessionLocal()
            try:
                private_key = get_private_key_from_db(session, sender_address, normalized_blockchain)
                logger.info(f"Successfully retrieved private key from database for address: {sender_address}")
            except Exception as e:
                logger.error(f"Failed to retrieve private key from database: {str(e)}")
                return jsonify({"success": False, "message": f"Failed to retrieve wallet credentials: {str(e)}"}), 400
            finally:
                session.close()
        else:
            logger.info(f"Private key provided in request for blockchain {normalized_blockchain}")
            
        if not private_key:
            return jsonify({"success": False, "message": "Unable to retrieve private key for transaction"}), 400
            
        # Get service using the helper function
        service = get_blockchain_service(normalized_blockchain)
        if not service:
            return jsonify({"success": False, 
                          "message": f"Blockchain service not available: {normalized_blockchain}"}), 503
        
        # Call the service's send method
        logger.info(f"Directly calling send_transaction for {normalized_blockchain}")
        tx_details, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error in send_transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
        
        # Ensure we have a proper success response
        if not tx_details:
            logger.error(f"No transaction details returned from service")
            return jsonify({"success": False, "message": "No transaction details returned"}), 500
            
        # Get transaction hash for response
        tx_hash = tx_details.get('tx_hash') or tx_details.get('transaction_hash')
        
        # Create a standardized success response
        response = {
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully",
            "UserID": user_id,
            "userId": user_id
        }
        
        # Add additional details if available
        if isinstance(tx_details, dict):
            response.update({
                "transaction_id": tx_details.get('transaction_id', transaction_id),
                "status": tx_details.get('status', 'sent'),
                "method": tx_details.get('method', 'unknown'),
                "explorer_url": tx_details.get('explorer_url', '')
            })
        
        logger.info(f"Successfully confirmed transaction {transaction_id} for {normalized_blockchain} for user {user_id}")
        logger.info(f"Transaction hash: {tx_hash}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# Ethereum specific endpoints
@send_bp.route('/ethereum/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def ethereum_prepare(data):
    """Ethereum-specific prepare endpoint with enhanced error handling"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in Ethereum prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for Ethereum transaction preparation"
            }), 400
        
        # Get Ethereum service
        service = get_blockchain_service('ethereum')
        if not service:
            logger.error("Ethereum service is not available")
            return jsonify({"success": False, "message": "Ethereum service not available"}), 503
            
        # Extract parameters
        sender = data.get('sender_address')
        recipient = data.get('recipient_address')
        amount = data.get('amount')
        contract = data.get('smart_contract_address')
        
        # Log the request details
        logger.info(f"Ethereum prepare request - Sender: {sender}, Recipient: {recipient}, Amount: {amount}, UserID: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not amount:
            logger.warning(f"Missing required fields - Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            return jsonify({"success": False, 
                          "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
            
        # Call the service's prepare method
        try:
            logger.info(f"Calling Ethereum prepare_transaction with sender:{sender}, recipient:{recipient}, amount:{amount}")
            tx_details, error = service.prepare_transaction(sender, recipient, amount, contract)
            
            if error:
                logger.error(f"Error in Ethereum prepare_transaction: {error}")
                return jsonify({"success": False, "message": error}), 400
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                
            logger.info(f"Successfully prepared Ethereum transaction with ID: {tx_details.get('transaction_id', 'unknown')} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.error(f"Error in Ethereum prepare_transaction: {str(prepare_error)}")
            return jsonify({"success": False, "message": f"Error preparing Ethereum transaction: {str(prepare_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in Ethereum prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@send_bp.route('/ethereum/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def ethereum_confirm(data):
    """Ethereum-specific confirm endpoint"""
    try:
        # Get Ethereum service
        service = get_blockchain_service('ethereum')
        if not service:
            return jsonify({"success": False, "message": "Ethereum service not available"}), 503
            
        # Extract parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        # Validate required fields
        if not transaction_id or not private_key:
            return jsonify({"success": False, 
                          "message": "Missing required fields: transaction_id or private_key"}), 400
        
        # Log sanitized request data        
        safe_data = sanitize_sensitive_data(data)
        logger.info(f"Processing Ethereum transaction confirm: {transaction_id}")
        logger.debug(f"Confirm data (sanitized): {json.dumps(safe_data, indent=2)}")
            
        # Call the service's send method
        result, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending Ethereum transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash
        tx_hash = result.get('tx_hash') or result.get('transaction_hash')
        
        logger.info(f"Successfully sent Ethereum transaction: {tx_hash}")
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in Ethereum confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# BSC specific endpoints
@send_bp.route('/bsc/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def bsc_prepare(data):
    """BSC-specific prepare endpoint with enhanced error handling"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in BSC prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for BSC transaction preparation"
            }), 400
        
        # Get BSC service
        service = get_blockchain_service('bsc')
        if not service:
            logger.error("BSC service is not available")
            return jsonify({"success": False, "message": "BSC service not available"}), 503
            
        # Extract parameters
        sender = data.get('sender_address')
        recipient = data.get('recipient_address')
        amount = data.get('amount')
        contract = data.get('smart_contract_address')
        
        # Log the request details
        logger.info(f"BSC prepare request - Sender: {sender}, Recipient: {recipient}, Amount: {amount}, UserID: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not amount:
            logger.warning(f"Missing required fields - Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            return jsonify({"success": False, 
                          "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
            
        # Call the service's prepare method
        try:
            logger.info(f"Calling BSC prepare_transaction with sender:{sender}, recipient:{recipient}, amount:{amount}")
            tx_details, error = service.prepare_transaction(sender, recipient, amount, contract)
            
            if error:
                logger.error(f"Error in BSC prepare_transaction: {error}")
                return jsonify({"success": False, "message": error}), 400
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                
            logger.info(f"Successfully prepared BSC transaction with ID: {tx_details.get('transaction_id', 'unknown')} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.error(f"Error in BSC prepare_transaction: {str(prepare_error)}")
            return jsonify({"success": False, "message": f"Error preparing BSC transaction: {str(prepare_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in BSC prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@send_bp.route('/bsc/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def bsc_confirm(data):
    """BSC-specific confirm endpoint"""
    try:
        # Get BSC service
        service = get_blockchain_service('bsc')
        if not service:
            return jsonify({"success": False, "message": "BSC service not available"}), 503
            
        # Extract parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        # Validate required fields
        if not transaction_id or not private_key:
            return jsonify({"success": False, 
                          "message": "Missing required fields: transaction_id or private_key"}), 400
        
        # Log sanitized request data
        safe_data = sanitize_sensitive_data(data)
        logger.info(f"Processing BSC transaction confirm: {transaction_id}")
        logger.debug(f"Confirm data (sanitized): {json.dumps(safe_data, indent=2)}")
            
        # Call the service's send method
        result, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending BSC transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash
        tx_hash = result.get('tx_hash') or result.get('transaction_hash')
        
        logger.info(f"Successfully sent BSC transaction: {tx_hash}")
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in BSC confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# Tron specific endpoints
@send_bp.route('/tron/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def tron_prepare(data):
    """TRON-specific prepare endpoint with enhanced error handling"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in TRON prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for TRON transaction preparation"
            }), 400
        
        # Get TRON service
        service = get_blockchain_service('tron')
        if not service:
            logger.error("TRON service is not available")
            return jsonify({"success": False, "message": "TRON service not available"}), 503
            
        # Extract parameters
        sender = data.get('sender_address')
        recipient = data.get('recipient_address')
        amount = data.get('amount')
        contract = data.get('smart_contract_address')
        
        # Log the request details
        logger.info(f"TRON prepare request - Sender: {sender}, Recipient: {recipient}, Amount: {amount}, UserID: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not amount:
            logger.warning(f"Missing required fields - Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            return jsonify({"success": False, 
                          "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
            
        # Call the service's prepare method
        try:
            logger.info(f"Calling TRON prepare_transaction with sender:{sender}, recipient:{recipient}, amount:{amount}")
            tx_details, error = service.prepare_transaction(sender, recipient, amount, contract)
            
            if error:
                logger.error(f"Error in TRON prepare_transaction: {error}")
                return jsonify({"success": False, "message": error}), 400
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                
            logger.info(f"Successfully prepared TRON transaction with ID: {tx_details.get('transaction_id', 'unknown')} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.error(f"Error in TRON prepare_transaction: {str(prepare_error)}")
            return jsonify({"success": False, "message": f"Error preparing TRON transaction: {str(prepare_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in TRON prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@send_bp.route('/tron/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def tron_confirm(data):
    """TRON-specific confirm endpoint"""
    try:
        # Get TRON service
        service = get_blockchain_service('tron')
        if not service:
            return jsonify({"success": False, "message": "TRON service not available"}), 503
            
        # Extract parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        # Validate required fields
        if not transaction_id or not private_key:
            return jsonify({"success": False, 
                          "message": "Missing required fields: transaction_id or private_key"}), 400
        
        # Log sanitized request data
        safe_data = sanitize_sensitive_data(data)
        logger.info(f"Processing TRON transaction confirm: {transaction_id}")
        logger.debug(f"Confirm data (sanitized): {json.dumps(safe_data, indent=2)}")
            
        # Call the service's send method
        result, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending TRON transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash
        tx_hash = result.get('tx_hash') or result.get('transaction_hash')
        
        logger.info(f"Successfully sent TRON transaction: {tx_hash}")
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in TRON confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# Bitcoin specific endpoints
@send_bp.route('/bitcoin/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def bitcoin_prepare(data):
    """Bitcoin-specific prepare endpoint with enhanced error handling"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in Bitcoin prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for Bitcoin transaction preparation"
            }), 400
        
        # Get Bitcoin service
        service = get_blockchain_service('bitcoin')
        if not service:
            logger.error("Bitcoin service is not available")
            return jsonify({"success": False, "message": "Bitcoin service not available"}), 503
            
        # Extract parameters
        sender = data.get('sender_address')
        recipient = data.get('recipient_address')
        amount = data.get('amount')
        
        # Log the request details
        logger.info(f"Bitcoin prepare request - Sender: {sender}, Recipient: {recipient}, Amount: {amount}, UserID: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not amount:
            logger.warning(f"Missing required fields - Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            return jsonify({"success": False, 
                          "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
            
        # Call the service's prepare method
        try:
            logger.info(f"Calling Bitcoin prepare_transaction with sender:{sender}, recipient:{recipient}, amount:{amount}")
            tx_details, error = service.prepare_transaction(sender, recipient, amount)
            
            if error:
                logger.error(f"Error in Bitcoin prepare_transaction: {error}")
                return jsonify({"success": False, "message": error}), 400
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                
            logger.info(f"Successfully prepared Bitcoin transaction with ID: {tx_details.get('transaction_id', 'unknown')} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.error(f"Error in Bitcoin prepare_transaction: {str(prepare_error)}")
            return jsonify({"success": False, "message": f"Error preparing Bitcoin transaction: {str(prepare_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in Bitcoin prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@send_bp.route('/bitcoin/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def bitcoin_confirm(data):
    """Bitcoin-specific confirm endpoint"""
    try:
        # Get Bitcoin service
        service = get_blockchain_service('bitcoin')
        if not service:
            return jsonify({"success": False, "message": "Bitcoin service not available"}), 503
            
        # Extract parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        # Validate required fields
        if not transaction_id or not private_key:
            return jsonify({"success": False, 
                          "message": "Missing required fields: transaction_id or private_key"}), 400
        
        # Log sanitized request data
        safe_data = sanitize_sensitive_data(data)
        logger.info(f"Processing Bitcoin transaction confirm: {transaction_id}")
        logger.debug(f"Confirm data (sanitized): {json.dumps(safe_data, indent=2)}")
            
        # Call the service's send method
        result, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending Bitcoin transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash
        tx_hash = result.get('tx_hash') or result.get('transaction_hash')
        
        logger.info(f"Successfully sent Bitcoin transaction: {tx_hash}")
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in Bitcoin confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# Polygon specific endpoints
@send_bp.route('/polygon/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@blockchain_api
def polygon_prepare(data):
    """Polygon-specific prepare endpoint with enhanced error handling"""
    try:
        # Extract UserID in any format - this is required
        user_id = data.get('UserId') or data.get('userId') or data.get('UserID') or data.get('userid') or data.get('user_id')
        if not user_id:
            logger.warning("No UserID found in Polygon prepare request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for Polygon transaction preparation"
            }), 400
        
        # Get Polygon service
        service = get_blockchain_service('polygon')
        if not service:
            logger.error("Polygon service is not available")
            return jsonify({"success": False, "message": "Polygon service not available"}), 503
            
        # Extract parameters
        sender = data.get('sender_address')
        recipient = data.get('recipient_address')
        amount = data.get('amount')
        contract = data.get('smart_contract_address')
        
        # Log the request details
        logger.info(f"Polygon prepare request - Sender: {sender}, Recipient: {recipient}, Amount: {amount}, UserID: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not amount:
            logger.warning(f"Missing required fields - Sender: {sender}, Recipient: {recipient}, Amount: {amount}")
            return jsonify({"success": False, 
                          "message": "Missing required fields: sender_address, recipient_address, or amount"}), 400
            
        # Call the service's prepare method
        try:
            logger.info(f"Calling Polygon prepare_transaction with sender:{sender}, recipient:{recipient}, amount:{amount}")
            
            # Debug: Check storage before prepare
            logger.info(f"Storage before prepare: {service.storage.get_storage_info()}")
            
            tx_details, error = service.prepare_transaction(sender, recipient, amount, contract)
            
            if error:
                logger.error(f"Error in Polygon prepare_transaction: {error}")
                return jsonify({"success": False, "message": error}), 400
            
            # Debug: Check storage after prepare
            logger.info(f"Storage after prepare: {service.storage.get_storage_info()}")
            
            # Debug: Try to retrieve the transaction immediately
            transaction_id = tx_details.get('transaction_id')
            if transaction_id:
                logger.info(f"Trying to retrieve transaction {transaction_id} immediately after prepare...")
                stored_tx = service.storage.get_transaction(transaction_id)
                if stored_tx:
                    logger.info(f"✅ Transaction {transaction_id} found in storage immediately after prepare")
                else:
                    logger.error(f"❌ Transaction {transaction_id} NOT found in storage immediately after prepare")
                    # Check all transactions
                    all_txs = service.storage.get_all_transactions()
                    logger.info(f"All transactions in storage: {list(all_txs.keys())}")
                    
                    # Force store the transaction using shared storage directly
                    logger.info(f"Force storing transaction {transaction_id} using shared storage...")
                    from services.shared_storage import shared_storage
                    shared_storage.store_transaction(transaction_id, tx_details, 30)
                    
                    # Verify storage
                    stored_tx_after = shared_storage.get_transaction(transaction_id)
                    if stored_tx_after:
                        logger.info(f"✅ Transaction {transaction_id} successfully force-stored")
                    else:
                        logger.error(f"❌ Failed to force-store transaction {transaction_id}")
                
            # Always add UserID to response
            if isinstance(tx_details, dict):
                tx_details['UserID'] = user_id
                
            logger.info(f"Successfully prepared Polygon transaction with ID: {tx_details.get('transaction_id', 'unknown')} for user {user_id}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.error(f"Error in Polygon prepare_transaction: {str(prepare_error)}")
            return jsonify({"success": False, "message": f"Error preparing Polygon transaction: {str(prepare_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in Polygon prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@send_bp.route('/polygon/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@log_transaction_request
@blockchain_api
def polygon_confirm(data):
    """Polygon-specific confirm endpoint with database private key retrieval"""
    try:
        # Get Polygon service
        service = get_blockchain_service('polygon')
        if not service:
            return jsonify({"success": False, "message": "Polygon service not available"}), 503
            
        # Extract parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')  # Optional - will get from DB if not provided
        
        # Validate required fields
        if not transaction_id:
            return jsonify({"success": False, 
                          "message": "Missing required field: transaction_id"}), 400
        
        # Log sanitized request data
        safe_data = sanitize_sensitive_data(data)
        logger.info(f"Processing Polygon transaction confirm: {transaction_id}")
        logger.debug(f"Confirm data (sanitized): {json.dumps(safe_data, indent=2)}")
        
        # Try to get transaction from shared storage directly
        from services.shared_storage import shared_storage
        tx_data = shared_storage.get_transaction(transaction_id)
        
        if not tx_data:
            logger.error(f"Transaction {transaction_id} not found in shared storage")
            return jsonify({"success": False, "message": "Transaction not found or expired"}), 400
            
        logger.info(f"Found transaction {transaction_id} in shared storage")
        
        # Get sender address from transaction data
        sender_address = tx_data.get('details', {}).get('sender')
        if not sender_address:
            logger.error(f"No sender address found in transaction {transaction_id}")
            return jsonify({"success": False, "message": "Transaction data incomplete - no sender address"}), 400
        
        # If no private key provided, get it from database
        if not private_key:
            logger.info(f"No private key provided, retrieving from database for address: {sender_address}")
            session = SessionLocal()
            try:
                private_key = get_private_key_from_db(session, sender_address, 'polygon')
                logger.info(f"Successfully retrieved private key from database for address: {sender_address}")
            except Exception as e:
                logger.error(f"Failed to retrieve private key from database: {str(e)}")
                return jsonify({"success": False, "message": f"Failed to retrieve wallet credentials: {str(e)}"}), 400
            finally:
                session.close()
            
        # Call the service's send method
        result, error = service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending Polygon transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash
        tx_hash = result.get('tx_hash') or result.get('transaction_hash')
        
        logger.info(f"Successfully sent Polygon transaction: {tx_hash}")
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "message": "Transaction sent successfully"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in Polygon confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# Testing endpoint
@send_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify routing is working"""
    return jsonify({
        "success": True,
        "message": "Send API is working correctly",
        "available_chains": list(blockchain_services.keys()),
        "timestamp": datetime.now().isoformat()
    })

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

@send_bp.route('/debug-storage', methods=['GET'])
def debug_storage():
    """Debug endpoint to check transaction storage status and configuration."""
    try:
        # Get storage info from a TRON service instance (all services use the same storage)
        service = get_blockchain_service('tron')
        if not service:
            return jsonify({
                "error": "TRON service not available",
                "available_services": list(blockchain_services.keys())
            }), 500
            
        # Get storage information
        storage_info = service.storage.get_storage_info()
        
        # Get all transactions
        all_transactions = service.storage.get_all_transactions()
        
        # Clean up expired transactions
        cleaned_count = service.storage.cleanup_expired()
        
        return jsonify({
            "storage_info": storage_info,
            "transaction_count": len(all_transactions),
            "transactions": {
                tx_id: {
                    "expires_at": tx_data.get("expires_at"),
                    "stored_at": tx_data.get("stored_at"),
                    "blockchain": tx_data.get("details", {}).get("blockchain"),
                    "amount": tx_data.get("details", {}).get("amount"),
                    "sender": tx_data.get("details", {}).get("sender"),
                    "recipient": tx_data.get("details", {}).get("recipient")
                }
                for tx_id, tx_data in all_transactions.items()
            },
            "cleaned_expired_count": cleaned_count,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug storage endpoint: {str(e)}")
        return jsonify({
            "error": f"Debug storage error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

@send_bp.route('/debug-transaction/<transaction_id>', methods=['GET'])
def debug_transaction(transaction_id):
    """Debug endpoint to check a specific transaction's status."""
    try:
        # Get storage info from a TRON service instance
        service = get_blockchain_service('tron')
        if not service:
            return jsonify({
                "error": "TRON service not available",
                "transaction_id": transaction_id
            }), 500
            
        # Try to get the transaction
        tx_data = service.storage.get_transaction(transaction_id)
        
        # Get storage info
        storage_info = service.storage.get_storage_info()
        
        if tx_data:
            return jsonify({
                "transaction_id": transaction_id,
                "found": True,
                "transaction_data": tx_data,
                "storage_info": storage_info,
                "timestamp": datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                "transaction_id": transaction_id,
                "found": False,
                "message": "Transaction not found or expired",
                "storage_info": storage_info,
                "timestamp": datetime.now().isoformat()
            }), 404
            
    except Exception as e:
        logger.error(f"Error in debug transaction endpoint: {str(e)}")
        return jsonify({
            "error": f"Debug transaction error: {str(e)}",
            "transaction_id": transaction_id,
            "timestamp": datetime.now().isoformat()
        }), 500

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
            
            # Validate that private key matches the address (simplified to avoid crashes)
            try:
                # Ensure private key has 0x prefix
                if not private_key.startswith('0x'):
                    private_key = '0x' + private_key
                
                # Basic validation - just check format, not derivation (to avoid crashes)
                if len(private_key) != 66:  # 0x + 64 hex chars
                    raise ValueError(f"Invalid private key format: length {len(private_key)}")
                
                logger.debug(f"✅ Private key format validation successful for address {address}")
                
            except Exception as validation_error:
                logger.error(f"Private key format validation failed: {str(validation_error)}")
                raise ValueError(f"Private key format validation failed: {str(validation_error)}")
            
            # Never log the actual private key
            logger.debug(f"Successfully decrypted and validated private key for address {address} (length: {len(private_key)})")
            
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

@send_bp.route('/debug-blockchain-detection', methods=['POST'])
def debug_blockchain_detection():
    """Debug endpoint to test blockchain detection logic"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        logger.debug(f"Debug blockchain detection request: {json.dumps(data, indent=2)}")
        
        # Run the detection logic
        original_blockchain = data.get('blockchain', '')
        result = {
            "original_blockchain": original_blockchain,
            "request_contains_bnb": "bnb" in json.dumps(data).lower(),
            "request_contains_eth": "eth" in json.dumps(data).lower(),
            "normalized_blockchain": normalize_blockchain_name(original_blockchain)
        }
        
        # Check for various BNB/BSC indicators
        indicators = []
        
        if "bnb" in json.dumps(data).lower():
            indicators.append("BNB mentioned in request")
            
        if data.get("asset", "").lower() == "bnb":
            indicators.append("Asset is explicitly BNB")
            
        if data.get("fee_details") and "bnb" in str(data.get("fee_details")).lower():
            indicators.append("Fee details mention BNB")
            
        # Return the analysis
        result["indicators"] = indicators
        result["detected_blockchain"] = "binance smart chain" if indicators else original_blockchain
        result["api_chain_name"] = tatum_service._get_chain_api_name(result["detected_blockchain"])
            
        return jsonify({"success": True, "analysis": result}), 200
        
    except Exception as e:
        logger.exception(f"Error in debug endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@send_bp.route('/force-bsc', methods=['POST'])
def force_bsc():
    """Force BSC for a transaction that was incorrectly submitted as Ethereum"""
    try:
        data = request.get_json()
        if not data or not data.get('transaction_id'):
            return jsonify({"success": False, "message": "Transaction ID required"}), 400
            
        transaction_id = data.get('transaction_id')
        
        # Get the transaction
        tx_data = get_transaction(transaction_id)
        if not tx_data:
            return jsonify({"success": False, "message": f"Transaction {transaction_id} not found"}), 404
            
        # Update blockchain and api_chain_name
        original_blockchain = tx_data.get('blockchain_name')
        tx_data['blockchain_name'] = 'binance smart chain'
        tx_data['api_chain_name'] = 'bsc'
        
        # Store updated transaction
        transaction_manager.store_transaction(transaction_id, tx_data)
        
        return jsonify({
            "success": True, 
            "message": f"Updated transaction {transaction_id} from {original_blockchain} to binance smart chain",
            "transaction": {k: v for k, v in tx_data.items() if k != 'private_key'}
        }), 200
        
    except Exception as e:
        logger.exception(f"Error forcing BSC: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@send_bp.route('/debug-wallet', methods=['POST'])
def debug_wallet():
    """Debug endpoint to check if wallet exists in database"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        address = data.get('address')
        blockchain = data.get('blockchain', 'ethereum')
        
        if not address:
            return jsonify({"success": False, "message": "Address is required"}), 400
            
        session = SessionLocal()
        try:
            # Normalize blockchain name
            normalized_blockchain = normalize_blockchain_name(blockchain)
            
            # Get blockchain ID
            blockchain_record = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike(normalized_blockchain)
            ).first()
            
            result = {
                "address": address,
                "blockchain": normalized_blockchain,
                "blockchain_found": blockchain_record is not None
            }
            
            if blockchain_record:
                result["blockchain_id"] = blockchain_record.BlockchainID
                result["blockchain_name_in_db"] = blockchain_record.BlockchainName
                
                # Check if address exists
                address_record = session.query(Address).filter(
                    Address.PublicAddress == address,
                    Address.BlockchainID == blockchain_record.BlockchainID
                ).first()
                
                result["address_found"] = address_record is not None
                
                if address_record:
                    result["address_id"] = address_record.AddressID
                    result["wallet_id"] = address_record.WalletID
                    result["has_private_key"] = bool(address_record.PrivateKey)
                    
                    if address_record.PrivateKey:
                        # Test decryption without logging the key
                        try:
                            decrypted_key = decrypt_private_key_aes(address_record.PrivateKey)
                            result["private_key_decrypts"] = bool(decrypted_key)
                            result["private_key_length"] = len(decrypted_key) if decrypted_key else 0
                            
                            # Test private key validation like in confirm endpoint
                            if decrypted_key:
                                try:
                                    from web3 import Web3
                                    from eth_account import Account
                                    
                                    # Ensure private key has 0x prefix
                                    if not decrypted_key.startswith('0x'):
                                        decrypted_key = '0x' + decrypted_key
                                    
                                    # Get the address that corresponds to this private key
                                    account = Account.from_key(decrypted_key)
                                    derived_address = account.address
                                    
                                    result["private_key_matches_address"] = (derived_address.lower() == address.lower())
                                    result["private_key_belongs_to"] = derived_address
                                    
                                    if derived_address.lower() != address.lower():
                                        result["validation_error"] = f"Private key belongs to {derived_address}, not {address}"
                                    else:
                                        result["validation_success"] = True
                                        
                                except Exception as validation_error:
                                    result["validation_error"] = str(validation_error)
                                    result["private_key_matches_address"] = False
                            
                        except Exception as decrypt_error:
                            result["private_key_decrypts"] = False
                            result["decryption_error"] = str(decrypt_error)
                else:
                    result["address_found"] = False
            else:
                result["blockchain_found"] = False
                
            return jsonify({"success": True, "debug_info": result}), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.exception(f"Error in wallet debug endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@send_bp.route('/detect-blockchain', methods=['POST'])
def detect_blockchain():
    """Detect the correct blockchain for a transaction based on various heuristics"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        sender_address = data.get('sender_address')
        recipient_address = data.get('recipient_address')
        amount = data.get('amount')
        original_blockchain = data.get('blockchain', '')
        
        # Start with the provided blockchain
        detected_blockchain = original_blockchain
        confidence = 0.5  # Default medium confidence
        reasons = []
        
        # Check for BNB mentions
        if "bnb" in json.dumps(data).lower():
            detected_blockchain = "binance smart chain"
            confidence = max(confidence, 0.8)  # High confidence
            reasons.append("BNB mentioned in request")
        
        # Check address prefix patterns
        # Both ETH and BSC use the same address format so this isn't conclusive
        if sender_address and sender_address.startswith("0x"):
            # This could be either ETH or BSC
            reasons.append("Address format compatible with ETH/BSC")
        
        # Check database records for this address
        session = SessionLocal()
        try:
            # Check BSC records
            bsc_blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike('binance smart chain')
            ).first()
            
            # Check ETH records
            eth_blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike('ethereum')
            ).first()
            
            if bsc_blockchain and sender_address:
                # Check if address exists in BSC
                bsc_address = session.query(Address).filter(
                    Address.PublicAddress == sender_address,
                    Address.BlockchainID == bsc_blockchain.BlockchainID
                ).first()
                
                if bsc_address:
                    detected_blockchain = "binance smart chain"
                    confidence = 0.9  # Very high confidence
                    reasons.append("Sender address exists in BSC records")
            
            if eth_blockchain and sender_address and detected_blockchain != "binance smart chain":
                # Check if address exists in ETH
                eth_address = session.query(Address).filter(
                    Address.PublicAddress == sender_address,
                    Address.BlockchainID == eth_blockchain.BlockchainID
                ).first()
                
                if eth_address:
                    detected_blockchain = "ethereum"
                    confidence = 0.9  # Very high confidence
                    reasons.append("Sender address exists in ETH records")
                    
        except Exception as e:
            logger.warning(f"Error checking blockchain records: {str(e)}")
            reasons.append(f"Database error: {str(e)}")
        finally:
            session.close()
        
        # Check for transaction value patterns
        try:
            decimal_amount = Decimal(str(amount))
            if decimal_amount < 0.1:
                # Small value transactions are more likely on BSC due to lower fees
                reasons.append("Small transaction amount more typical for BSC")
                if detected_blockchain != "binance smart chain" and confidence < 0.7:
                    detected_blockchain = "binance smart chain"
                    confidence = 0.6
        except:
            pass
        
        # Check user history for transaction patterns
        # This would require a more complex implementation with user history
        
        # Normalize the detected blockchain
        normalized_blockchain = normalize_blockchain_name(detected_blockchain)
        api_chain_name = tatum_service._get_chain_api_name(normalized_blockchain)
        
        result = {
            "original_blockchain": original_blockchain,
            "detected_blockchain": normalized_blockchain,
            "api_chain_name": api_chain_name,
            "confidence": confidence,
            "reasons": reasons
        }
        
        return jsonify({"success": True, "detection": result}), 200
        
    except Exception as e:
        logger.exception(f"Error in blockchain detection: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@send_bp.route('/test-broadcast-capability', methods=['GET'])
def test_broadcast_capability():
    """Test RPC broadcast capabilities"""
    try:
        # Get Ethereum service
        service = get_blockchain_service('ethereum')
        if not service:
            return jsonify({"success": False, "message": "Ethereum service not available"}), 503
        
        # Test broadcast capability
        test_results = service.test_rpc_broadcast_capability()
        
        return jsonify({
            "success": True,
            "message": "RPC broadcast capability test completed",
            "test_results": test_results
        }), 200
        
    except Exception as e:
        logger.exception(f"Error testing broadcast capability: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@send_bp.route('/check-mempool-visibility/<tx_hash>', methods=['GET'])
def check_mempool_visibility(tx_hash):
    """Check transaction visibility across multiple RPCs"""
    try:
        # Get Ethereum service
        service = get_blockchain_service('ethereum')
        if not service:
            return jsonify({"success": False, "message": "Ethereum service not available"}), 503
        
        # Check mempool visibility
        visibility_result = service.check_mempool_visibility(tx_hash)
        
        return jsonify({
            "success": True,
            "tx_hash": tx_hash,
            "visibility": visibility_result
        }), 200
        
    except Exception as e:
        logger.exception(f"Error checking mempool visibility: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500