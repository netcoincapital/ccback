from flask import Blueprint, jsonify, request, g
import logging
from typing import Dict, Optional, Any
import os
import uuid
import json
from datetime import datetime

from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors
from security.validators import SecurityUtils, ValidationError
from services.transaction_storage import TransactionStorage
from utils.blockchain_service_factory import BlockchainServiceFactory
from api.middleware import normalize_parameters

# Configure logging
logger = get_logger(__file__)

# Create the blockchain API blueprint
blockchain_api = Blueprint('blockchain_api', __name__)

# Initialize Transaction Storage
transaction_storage = TransactionStorage()

def blockchain_api_handler(func):
    """Decorator for API error handling and request processing"""
    @normalize_parameters  # Add parameter normalization
    def wrapper(*args, **kwargs):
        try:
            # Log the request before anything else
            logger.debug(f"Received API request: {request.method} {request.path}")
            logger.debug(f"Request headers: {dict(request.headers)}")
            
            # If content type is json but no data, handle gracefully
            if request.is_json and not request.data:
                logger.warning("Empty JSON request body received")
                return jsonify({"success": False, "message": "Empty request body"}), 400
                
            # Handle non-JSON requests gracefully
            if not request.is_json and request.method != 'GET':
                logger.warning(f"Non-JSON request received: {request.content_type}")
                
                # For non-GET requests, require JSON
                if request.method != 'GET':
                    return jsonify({"success": False, "message": "Invalid content type, must be application/json"}), 415
            
            # For POST requests, extract JSON data safely
            data = None
            if request.method == 'POST':
                if request.is_json:
                    data = request.get_json(silent=True)
                    if data is None:
                        logger.warning("Failed to parse JSON from request")
                        return jsonify({"success": False, "message": "Invalid JSON data"}), 400
                else:
                    # For non-JSON POST requests, try to handle form data
                    try:
                        data = request.form.to_dict()
                        logger.debug(f"Converted form data to dict: {data}")
                        if not data:
                            logger.warning("Empty form data in request")
                            return jsonify({"success": False, "message": "No data provided"}), 400
                    except Exception as form_err:
                        logger.error(f"Error processing form data: {str(form_err)}")
                        return jsonify({"success": False, "message": "Invalid request data format"}), 400
            
            # For GET requests, use query parameters
            elif request.method == 'GET':
                data = request.args.to_dict()
            
            # If we still don't have data, use an empty dict
            if data is None:
                data = {}
                
            # If we have normalized data in g, use it instead
            if hasattr(g, 'normalized_data'):
                data = g.normalized_data
                logger.debug("Using normalized data from middleware")
                
            # Log the request data (without private key if present)
            safe_data = {k: v for k, v in data.items() if k != 'private_key'}
            logger.debug(f"API request data: {json.dumps(safe_data, indent=2)}")
            
            # DEBUG - specific logging for "Authentication required" errors
            if data and 'Authentication' in str(data):
                logger.critical(f"AUTHENTICATION DEBUG - Full request details (except private key): {json.dumps(safe_data, indent=2)}")
                logger.critical(f"AUTHENTICATION DEBUG - Request method: {request.method}")
                logger.critical(f"AUTHENTICATION DEBUG - Request path: {request.path}")
                logger.critical(f"AUTHENTICATION DEBUG - Request content type: {request.content_type}")

            # Call the actual function
            return func(data, *args, **kwargs)
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return jsonify({"success": False, "message": str(ve)}), 400
        except Exception as e:
            logger.exception(f"API error: {str(e)}")
            return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    return wrapper

# Generic handler for prepare transaction endpoint
def handle_prepare(blockchain_name, data):
    """Handle prepare transaction request for any blockchain"""
    try:
        # Log detailed information about the request
        logger.info(f"Processing prepare transaction request for blockchain: {blockchain_name}")
        logger.debug(f"Request data: {data}")
        
        # Get blockchain service
        try:
            blockchain_service = BlockchainServiceFactory.get_service(blockchain_name)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400
            
        # Extract common parameters, support both snake_case and camelCase
        sender = data.get('sender_address') or data.get('senderAddress')
        recipient = data.get('recipient_address') or data.get('recipientAddress')
        raw_amount = data.get('amount')
        contract = data.get('smart_contract_address') or data.get('smartContractAddress')
        
        # Get UserID if present in any format
        user_id = (data.get('UserId') or data.get('userId') or 
                  data.get('UserID') or data.get('userid') or 
                  data.get('user_id'))
        
        logger.debug(f"Extracted parameters - sender: {sender}, recipient: {recipient}, amount: {raw_amount}, userId: {user_id}")
        
        # Validate required fields
        if not sender or not recipient or not raw_amount:
            return jsonify({
                "success": False, 
                "message": "Missing required fields: sender_address, recipient_address, or amount"
            }), 400
        
        # Convert amount to a string to avoid issues with Decimal
        try:
            # First convert to Decimal to normalize the value
            from decimal import Decimal
            amount_decimal = Decimal(str(raw_amount).strip())
            # Then convert back to string for consistent handling
            amount = str(amount_decimal)
            logger.debug(f"Converted amount from {raw_amount} ({type(raw_amount)}) to {amount} (string)")
        except Exception as e:
            logger.error(f"Error converting amount to string: {e}")
            return jsonify({
                "success": False,
                "message": f"Invalid amount format: {raw_amount}"
            }), 400
        
        # Check for authentication error
        if isinstance(data, dict) and 'success' in data and not data.get('success'):
            if 'authentication' in data.get('message', '').lower():
                logger.critical(f"Authentication error detected in prepare transaction: {data}")
                # Return with more helpful message
                return jsonify({
                    "success": False,
                    "message": "UserID parameter is required for this request",
                    "original_error": data.get('message')
                }), 400
                
        # Call the service's prepare method - note: removed 'contract' parameter since it's not used in most calls
        tx_details, error = blockchain_service.prepare_transaction(sender, recipient, amount)
        
        if error:
            logger.error(f"Error in prepare_transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
        
        # If we have a UserID, add it to the response
        if user_id and isinstance(tx_details, dict):
            tx_details['UserID'] = user_id
        
        # Log successful preparation
        logger.info(f"Successfully prepared transaction for {amount} {blockchain_name}")    
        return jsonify(tx_details), 200
    except Exception as e:
        logger.exception(f"Error in prepare endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error preparing transaction: {str(e)}"}), 500

# Generic handler for confirm transaction endpoint
def handle_confirm(blockchain_name, data):
    """Handle confirm transaction request for any blockchain"""
    try:
        # Get blockchain service
        try:
            blockchain_service = BlockchainServiceFactory.get_service(blockchain_name)
        except ValueError as e:
            logger.error(f"Blockchain service error: {str(e)}")
            return jsonify({"success": False, "message": str(e)}), 400
            
        # Extract transaction ID and private key
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        if not transaction_id:
            return jsonify({"success": False, "message": "Missing transaction_id parameter"}), 400
        
        if not private_key:
            return jsonify({"success": False, "message": "Missing private_key parameter"}), 400
            
        # Get transaction details from storage
        tx_data = transaction_storage.get_transaction(transaction_id)
        
        if not tx_data:
            logger.error(f"Transaction {transaction_id} not found")
            return jsonify({"success": False, "message": "Transaction not found or expired"}), 404
            
        # Log attempt to send transaction (without private key)
        logger.info(f"Attempting to send {blockchain_name} transaction with ID: {transaction_id}")
            
        # Call the service's send method
        result, error = blockchain_service.send_transaction(transaction_id, private_key)
        
        if error:
            logger.error(f"Error sending transaction: {error}")
            return jsonify({"success": False, "message": error}), 400
            
        # Get transaction hash from result
        tx_hash = None
        if result:
            # Check different possible key names for transaction hash
            for key in ['transaction_hash', 'tx_hash', 'txHash', 'hash', 'txId']:
                if key in result:
                    tx_hash = result[key]
                    break
            
        if not tx_hash:
            logger.warning(f"Transaction sent but no hash found in result: {result}")
            
        # Return the result
        return jsonify({
            "success": True,
            "transaction_hash": tx_hash,
            "status": result.get("status", "pending"),
            "message": "Transaction sent successfully"
        }), 200
    except Exception as e:
        logger.exception(f"Error in confirm endpoint: {str(e)}")
        return jsonify({"success": False, "message": f"Error confirming transaction: {str(e)}"}), 500

# Dynamically generate API endpoints for all supported blockchains
def register_blockchain_endpoints():
    """Register blockchain-specific API endpoints"""
    logger.info(f"Starting blockchain API endpoint registration")
    
    # Get all supported blockchains
    supported_blockchains = BlockchainServiceFactory.get_supported_blockchains()
    logger.info(f"Found {len(supported_blockchains)} supported blockchains: {supported_blockchains}")
    
    # Make sure BSC is included specifically
    if 'bsc' not in supported_blockchains:
        logger.warning("BSC not found in supported blockchains, checking manually...")
        
        # Check if BSC service is registered
        try:
            bsc_service = BlockchainServiceFactory.get_service('bsc')
            if bsc_service:
                logger.info("Successfully got BSC service, adding to endpoints")
                register_blockchain_endpoint('bsc')
        except Exception as e:
            logger.error(f"Failed to get BSC service: {str(e)}")
    
    for blockchain_name in supported_blockchains:
        register_blockchain_endpoint(blockchain_name)
        
# Helper function to register a single blockchain endpoint
def register_blockchain_endpoint(blockchain_name):
    """Register API endpoints for a single blockchain"""
    logger.info(f"Registering API endpoints for blockchain: {blockchain_name}")
    
    # Create prepare endpoint
    @blockchain_api.route(f'/{blockchain_name}/prepare', methods=['POST'])
    @SecurityUtils.rate_limit(requests=10, window=60)  # Only apply rate limiting, no auth
    @blockchain_api_handler
    def prepare_route(data, blockchain=blockchain_name):
        """Prepare a transaction for a specific blockchain"""
        logger.info(f"Handling prepare request for {blockchain}")
        return handle_prepare(blockchain, data)
    
    # Rename the function to avoid overriding
    prepare_route.__name__ = f'{blockchain_name}_prepare'
    
    # Create confirm endpoint
    @blockchain_api.route(f'/{blockchain_name}/confirm', methods=['POST'])
    @SecurityUtils.rate_limit(requests=5, window=60)  # Only apply rate limiting, no auth
    @blockchain_api_handler
    def confirm_route(data, blockchain=blockchain_name):
        """Confirm a transaction for a specific blockchain"""
        logger.info(f"Handling confirm request for {blockchain}")
        return handle_confirm(blockchain, data)
    
    # Rename the function to avoid overriding
    confirm_route.__name__ = f'{blockchain_name}_confirm'
    
    # Add a OPTIONS endpoint to respond to CORS preflight requests
    @blockchain_api.route(f'/{blockchain_name}/prepare', methods=['OPTIONS'])
    def prepare_options(blockchain=blockchain_name):
        response = jsonify({"success": True, "message": "CORS options request successful"})
        response.headers["Allow"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response
        
    # Add a OPTIONS endpoint for confirm
    @blockchain_api.route(f'/{blockchain_name}/confirm', methods=['OPTIONS'])
    def confirm_options(blockchain=blockchain_name):
        response = jsonify({"success": True, "message": "CORS options request successful"})
        response.headers["Allow"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response
    
    # Rename the options functions to avoid overriding
    prepare_options.__name__ = f'{blockchain_name}_prepare_options'
    confirm_options.__name__ = f'{blockchain_name}_confirm_options'
    
    logger.info(f"Successfully registered API endpoints for blockchain: {blockchain_name}")

# Register all blockchain endpoints
register_blockchain_endpoints()

# Add test endpoint
@blockchain_api.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint for blockchain API"""
    return jsonify({
        "success": True,
        "message": "Blockchain API is working",
        "available_blockchains": BlockchainServiceFactory.get_supported_blockchains()
    })

# Add endpoint to get blockchain details
@blockchain_api.route('/blockchains', methods=['GET'])
def get_blockchains():
    """Get list of all supported blockchains with their details"""
    try:
        # Get blockchain configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "blockchain_config.json")
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Filter only enabled blockchains
        available_blockchains = BlockchainServiceFactory.get_supported_blockchains()
        blockchains = [b for b in config.get("blockchains", []) if b.get("name") in available_blockchains]
            
        return jsonify({
            "success": True,
            "blockchains": blockchains
        }), 200
    except Exception as e:
        logger.exception(f"Error getting blockchain list: {str(e)}")
        
        # Fallback to simple list if config file is not available
        return jsonify({
            "success": True,
            "blockchains": [{"name": name} for name in BlockchainServiceFactory.get_supported_blockchains()]
        }), 200
        
# Add status endpoint to check blockchain services
@blockchain_api.route('/status', methods=['GET'])
def blockchain_status():
    """
    Get status of all blockchain services
    
    Returns a JSON object with the status of all configured blockchain services
    """
    try:
        # Get status of all services
        status = BlockchainServiceFactory.initialize_all_services()
        
        # Get list of all registered blockchains
        all_blockchains = list(BlockchainServiceFactory._service_classes.keys())
        
        # Get list of disabled blockchains
        disabled = list(BlockchainServiceFactory._disabled_blockchains)
        
        # Get list of name variants to help with API usage
        name_variants = {}
        for variant, canonical in BlockchainServiceFactory._name_mapping.items():
            if variant != canonical:  # Only include actual variants
                if canonical not in name_variants:
                    name_variants[canonical] = []
                name_variants[canonical].append(variant)
        
        # Get active blockchains (registered but not disabled)
        active = [b for b in all_blockchains if b not in disabled]
        
        result = {
            "active_blockchains": active,
            "disabled_blockchains": disabled,
            "status_details": status,
            "name_variants": name_variants
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting blockchain status: {str(e)}")
        return jsonify({
            "error": "Failed to get blockchain status",
            "message": str(e)
        }), 500

@blockchain_api.route('/debug-registry', methods=['GET'])
def debug_registry():
    """Debug endpoint for blockchain registry"""
    try:
        result = {
            "registered_classes": list(BlockchainServiceFactory._service_classes.keys()),
            "instantiated_services": list(BlockchainServiceFactory._services.keys()),
            "name_mapping": BlockchainServiceFactory._name_mapping,
            "disabled_blockchains": list(BlockchainServiceFactory._disabled_blockchains),
            "supported_blockchains": BlockchainServiceFactory.get_supported_blockchains()
        }
        return jsonify(result), 200
    except Exception as e:
        logger.exception(f"Error in blockchain registry debug endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@blockchain_api.route('/debug-bsc', methods=['GET'])
def debug_bsc():
    """Debug endpoint for BSC service"""
    try:
        # Try to get the BSC service
        try:
            bsc_service = BlockchainServiceFactory.get_service('bsc')
            
            # Get configuration details
            result = {
                "success": True,
                "service_available": True,
                "node_url": bsc_service.bsc_node_url,
                "web3_available": bsc_service.web3 is not None,
                "tatum_available": bsc_service.tatum is not None
            }
            
            # Add additional service details
            if hasattr(bsc_service, '_gas_price_cache'):
                result["gas_price_cache"] = bool(bsc_service._gas_price_cache)
                
            # Add map registration info
            result["name_mapping"] = {
                "bsc_normalized": BlockchainServiceFactory.normalize_name("bsc"),
                "binance_normalized": BlockchainServiceFactory.normalize_name("binance"),
                "bnb_normalized": BlockchainServiceFactory.normalize_name("bnb"),
                "binance_smart_chain_normalized": BlockchainServiceFactory.normalize_name("binance-smart-chain")
            }
            
            # Add API test info
            result["api_mapping"] = {
                "bsc_api": get_api_name("bsc"),
                "binance_api": get_api_name("binance"),
                "binance_smart_chain_api": get_api_name("binance-smart-chain")
            }
                
            return jsonify(result), 200
            
        except Exception as e:
            # BSC service not available
            return jsonify({
                "success": False,
                "service_available": False,
                "error": str(e),
                "mappings": {
                    "name_mapping": BlockchainServiceFactory._name_mapping,
                    "registered_services": list(BlockchainServiceFactory._service_classes.keys()),
                    "disabled_blockchains": list(BlockchainServiceFactory._disabled_blockchains)
                }
            }), 200
            
    except Exception as e:
        logger.exception(f"Error in BSC debug endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@blockchain_api.route('/debug-tron', methods=['GET'])
def debug_tron():
    """Debug endpoint for TRON service"""
    try:
        # Try to get the TRON service
        try:
            tron_service = BlockchainServiceFactory.get_service('tron')
            
            # Get configuration details
            result = {
                "success": True,
                "service_available": True,
                "node_url": tron_service.tron_node_url,
                "client_available": tron_service.tron_available,
                "tatum_available": tron_service.tatum is not None
            }
            
            # Try to validate a test address to check functionality
            test_address = "TAzsQ9Gx8eqFNFSZYxZ4W8YjQxZA3wNVn8"
            validation_result = tron_service.validate_address(test_address)
            result["address_validation_test"] = validation_result
            
            # Add API test info
            result["api_mapping"] = {
                "tron_api": get_api_name("tron"),
                "trx_api": get_api_name("trx")
            }
            
            # Test balance retrieval if service is available
            if tron_service.tron_available:
                try:
                    # Use a known TRON address for testing
                    test_balance, error = tron_service.get_balance("TM1zzNDZD2DPASbKcgdVoTYhfmYgtfwx9R")
                    result["balance_test"] = {
                        "success": error is None,
                        "balance": str(test_balance) if error is None else None,
                        "error": error
                    }
                except Exception as balance_error:
                    result["balance_test"] = {
                        "success": False,
                        "error": str(balance_error)
                    }
                
            return jsonify(result), 200
            
        except Exception as e:
            # TRON service not available
            return jsonify({
                "success": False,
                "service_available": False,
                "error": str(e),
                "mappings": {
                    "name_mapping": BlockchainServiceFactory._name_mapping,
                    "registered_services": list(BlockchainServiceFactory._service_classes.keys()),
                    "disabled_blockchains": list(BlockchainServiceFactory._disabled_blockchains)
                }
            }), 200
            
    except Exception as e:
        logger.exception(f"Error in TRON debug endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@blockchain_api.route('/debug-tron-balance', methods=['GET'])
def debug_tron_balance():
    """Debug endpoint for TRON balance lookup"""
    try:
        # Get address from query parameter
        address = request.args.get('address')
        if not address:
            return jsonify({
                "success": False,
                "error": "Missing address parameter",
                "example": "/api/debug-tron-balance?address=TRON_ADDRESS_HERE"
            }), 400
            
        # Try to get the TRON service
        try:
            tron_service = BlockchainServiceFactory.get_service('tron')
            
            # Check stages of balance lookup
            result = {
                "success": True,
                "address": address,
                "stages": {}
            }
            
            # Check database for balance first
            try:
                from database import SessionLocal, Address, UserHolding, Blockchains
                from sqlalchemy import text
                
                with SessionLocal() as session:
                    # Find wallet for this address
                    wallet_query = text("""
                        SELECT a.WalletID, a.AddressID, a.BlockchainID
                        FROM address a
                        WHERE a.PublicAddress = :address
                    """)
                    
                    wallet_result = session.execute(wallet_query, {"address": address}).fetchone()
                    
                    if wallet_result:
                        wallet_id = wallet_result[0]
                        address_id = wallet_result[1]
                        blockchain_id = wallet_result[2]
                        
                        result["stages"]["address_lookup"] = {
                            "success": True,
                            "wallet_id": wallet_id,
                            "address_id": address_id,
                            "blockchain_id": blockchain_id
                        }
                        
                        # Try to find user holding for TRX
                        trx_query = text("""
                            SELECT h.HoldingID, h.Balance, h.Symbol, c.CurrencyID
                            FROM userholding h
                            JOIN currencies c ON h.CurrencyID = c.CurrencyID
                            JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                            JOIN wallets w ON h.UserID = w.UserID
                            WHERE w.WalletID = :wallet_id
                            AND (c.Symbol = 'TRX' OR c.CurrencyName = 'Tron')
                            AND (b.BlockchainName = 'Tron' OR b.BlockchainName = 'TRX')
                        """)
                        
                        trx_result = session.execute(trx_query, {"wallet_id": wallet_id}).fetchone()
                        
                        if trx_result:
                            holding_id = trx_result[0]
                            balance = str(trx_result[1])
                            symbol = trx_result[2]
                            currency_id = trx_result[3]
                            
                            result["stages"]["balance_in_database"] = {
                                "success": True,
                                "holding_id": holding_id,
                                "balance": balance,
                                "symbol": symbol,
                                "currency_id": currency_id
                            }
                        else:
                            result["stages"]["balance_in_database"] = {
                                "success": False,
                                "message": "No TRX balance found in database for this wallet"
                            }
                    else:
                        result["stages"]["address_lookup"] = {
                            "success": False,
                            "message": "Address not found in database"
                        }
            except Exception as db_error:
                result["stages"]["database_lookup"] = {
                    "success": False,
                    "error": str(db_error)
                }
            
            # Try direct TRON client
            if tron_service.tron_available:
                try:
                    balance = tron_service.client.get_account_balance(address)
                    result["stages"]["tron_client"] = {
                        "success": True,
                        "balance": str(balance / 1000000),  # Convert from SUN to TRX
                        "raw_balance": str(balance)
                    }
                except Exception as client_error:
                    result["stages"]["tron_client"] = {
                        "success": False,
                        "error": str(client_error)
                    }
            else:
                result["stages"]["tron_client"] = {
                    "success": False,
                    "message": "TRON client is not available"
                }
                
            # Try Tatum API
            if tron_service.tatum:
                try:
                    balance, error = tron_service.tatum.get_balance('tron', address)
                    if error:
                        result["stages"]["tatum_api"] = {
                            "success": False,
                            "error": error
                        }
                    else:
                        result["stages"]["tatum_api"] = {
                            "success": True,
                            "balance": str(balance)
                        }
                except Exception as tatum_error:
                    result["stages"]["tatum_api"] = {
                        "success": False,
                        "error": str(tatum_error)
                    }
            else:
                result["stages"]["tatum_api"] = {
                    "success": False,
                    "message": "Tatum API is not available"
                }
                
            # Call the actual get_balance method
            try:
                balance, error = tron_service.get_balance(address)
                result["final_balance_result"] = {
                    "success": error is None,
                    "balance": str(balance),
                    "error": error
                }
            except Exception as balance_error:
                result["final_balance_result"] = {
                    "success": False,
                    "error": str(balance_error)
                }
                
            return jsonify(result), 200
            
        except Exception as e:
            # TRON service not available
            return jsonify({
                "success": False,
                "service_available": False,
                "error": str(e)
            }), 500
            
    except Exception as e:
        logger.exception(f"Error in TRON balance debug endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@blockchain_api.route('/tron/parameter-debug', methods=['POST', 'GET'])
def tron_parameter_debug():
    """Debug endpoint to echo back all parameters from the TRON API requests"""
    try:
        # Collect all info about the request
        result = {
            "success": True,
            "message": "Debug information for TRON API request",
            "timestamp": datetime.now().isoformat(),
            "request_info": {
                "method": request.method,
                "url": request.url,
                "content_type": request.content_type,
                "headers": {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']}
            }
        }
        
        # Extract parameters from everywhere they might be
        params = {}
        
        # JSON data
        if request.is_json:
            try:
                json_data = request.get_json(silent=True)
                if json_data:
                    params.update({"json_body": json_data})
            except Exception as e:
                result["json_error"] = str(e)
                
        # Form data
        if request.form:
            form_data = request.form.to_dict()
            params.update({"form_data": form_data})
        
        # URL parameters
        if request.args:
            args_data = request.args.to_dict()
            params.update({"url_params": args_data})
            
        # Look for the UserID in various formats
        user_id = None
        search_locations = []
        
        # Check in JSON
        if "json_body" in params:
            for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
                if key in params["json_body"]:
                    user_id = params["json_body"][key]
                    search_locations.append(f"json_body.{key}")
                    
        # Check in form data
        if "form_data" in params:
            for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
                if key in params["form_data"]:
                    user_id = params["form_data"][key]
                    search_locations.append(f"form_data.{key}")
                    
        # Check in URL params
        if "url_params" in params:
            for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
                if key in params["url_params"]:
                    user_id = params["url_params"][key]
                    search_locations.append(f"url_params.{key}")
                    
        # Add UserID info to result
        result["user_id_info"] = {
            "found": user_id is not None,
            "value": user_id,
            "locations": search_locations
        }
        
        # Add all parameters
        result["all_parameters"] = params
        
        # Log for debugging
        logger.info(f"Debug request received: {result}")
        
        return jsonify(result), 200
    except Exception as e:
        logger.exception(f"Error in parameter debug endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error generating debug information",
            "error": str(e)
        }), 500

def get_api_name(blockchain_name):
    """Helper to get API name for blockchain in Send.py"""
    from CC.Send.Send import get_api_blockchain_name
    normalized = BlockchainServiceFactory.normalize_name(blockchain_name)
    return get_api_blockchain_name(normalized) if normalized else None

# Add a special debug endpoint for Tron API to diagnose issues
@blockchain_api.route('/tron/debug', methods=['POST'])
def tron_debug():
    """Debug endpoint for TRON API issues"""
    try:
        # Log the request details
        logger.info(f"TRON debug endpoint called with method: {request.method}")
        
        # Extract data from request
        data = None
        if request.is_json:
            data = request.get_json(silent=True)
        elif request.form:
            data = request.form.to_dict()
        elif request.args:
            data = request.args.to_dict()
        
        # Create a safe copy of data without private keys
        safe_data = {}
        if data:
            safe_data = {k: v for k, v in data.items() if k != 'private_key'}
            
        logger.info(f"TRON debug request data: {json.dumps(safe_data, indent=2)}")
        
        # Try to get the TRON service
        try:
            tron_service = BlockchainServiceFactory.get_service('tron')
            service_available = True
            
            # Test if basic functionality is working
            test_address = "TM1zzNDZD2DPASbKcgdVoTYhfmYgtfwx9R"
            address_valid = tron_service.validate_address(test_address)
            
            # If we have sender and recipient, try preparing a test transaction
            test_tx_result = None
            if data and 'sender_address' in data and 'recipient_address' in data:
                try:
                    # Use tiny amount for test
                    test_amount = "0.000001"
                    sender = data.get('sender_address')
                    recipient = data.get('recipient_address')
                    
                    # Only prepare, don't send
                    logger.info(f"Attempting test prepare with sender:{sender}, recipient:{recipient}")
                    test_tx_result, test_error = tron_service.prepare_transaction(sender, recipient, test_amount)
                    
                    if test_error:
                        logger.error(f"Test transaction preparation failed: {test_error}")
                except Exception as prepare_error:
                    logger.error(f"Error in test transaction: {str(prepare_error)}")
                    test_tx_result = {
                        "success": False,
                        "error": str(prepare_error)
                    }
            
            result = {
                "success": True,
                "tron_service_available": service_available,
                "address_validation_working": address_valid,
                "test_transaction_result": test_tx_result,
                "node_url": tron_service.tron_node_url,
                "client_initialized": tron_service.tron_available
            }
            
            return jsonify(result), 200
            
        except Exception as service_error:
            logger.error(f"Error getting TRON service: {str(service_error)}")
            return jsonify({
                "success": False,
                "error": f"TRON service error: {str(service_error)}"
            }), 500
            
    except Exception as e:
        logger.exception(f"Error in TRON debug endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Override the prepare endpoint for TRON with extra debug information
@blockchain_api.route('/tron/prepare', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
def tron_prepare_with_debug():
    """Enhanced TRON prepare endpoint with detailed error handling"""
    try:
        # Get the request data
        data = None
        if request.is_json:
            data = request.get_json(silent=True)
        elif request.form:
            data = request.form.to_dict()
            
        if not data:
            logger.error("No data in TRON prepare request")
            return jsonify({
                "success": False,
                "message": "Missing request data",
                "error_code": "NO_DATA"
            }), 400
            
        # Log request details (excluding private key)
        safe_data = {k: v for k, v in data.items() if k != 'private_key'}
        logger.info(f"TRON prepare request: {json.dumps(safe_data, indent=2)}")
        
        # Check for UserID parameter in any format
        user_id = None
        for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
            if key in data and data[key]:
                user_id = data[key]
                logger.info(f"Found UserID in key {key}: {user_id}")
                break
                
        # Make sure we have the essential parameters
        if not data.get('sender_address'):
            return jsonify({
                "success": False,
                "message": "sender_address is required",
                "error_code": "MISSING_SENDER"
            }), 400
            
        if not data.get('recipient_address'):
            return jsonify({
                "success": False,
                "message": "recipient_address is required",
                "error_code": "MISSING_RECIPIENT"
            }), 400
            
        if not data.get('amount'):
            return jsonify({
                "success": False,
                "message": "amount is required",
                "error_code": "MISSING_AMOUNT"
            }), 400
            
        # Try to get the TRON service
        try:
            tron_service = BlockchainServiceFactory.get_service('tron')
            logger.info("TRON service initialized successfully")
        except Exception as service_error:
            logger.error(f"Error initializing TRON service: {str(service_error)}")
            return jsonify({
                "success": False,
                "message": f"TRON service error: {str(service_error)}",
                "error_code": "SERVICE_INIT_ERROR"
            }), 500
            
        # Try to prepare the transaction
        try:
            tx_details, error = tron_service.prepare_transaction(
                data.get('sender_address'),
                data.get('recipient_address'),
                data.get('amount')
            )
            
            if error:
                logger.error(f"Error preparing TRON transaction: {error}")
                return jsonify({
                    "success": False,
                    "message": error,
                    "error_code": "PREPARE_ERROR"
                }), 400
                
            # Add UserID to the response if provided
            if user_id and tx_details:
                tx_details['UserID'] = user_id
                
            logger.info(f"TRON transaction prepared successfully: {tx_details.get('transaction_id')}")
            return jsonify(tx_details), 200
            
        except Exception as prepare_error:
            logger.exception(f"Unhandled error in TRON prepare: {str(prepare_error)}")
            return jsonify({
                "success": False,
                "message": f"Unhandled error: {str(prepare_error)}",
                "error_code": "UNHANDLED_ERROR"
            }), 500
            
    except Exception as e:
        logger.exception(f"Unhandled error in TRON prepare endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}",
            "error_code": "SERVER_ERROR"
        }), 500 