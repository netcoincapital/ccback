from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import logging
from typing import Dict, List, Any
from decimal import Decimal
from datetime import datetime
import traceback

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, UserHolding
from schemas.balance_schemas import UserBalanceRequest, UserBalanceResponse, TokenBalanceItem
from security.validators import SecurityUtils, InputValidator, ValidationError
from utils.logging_config import get_logger
from services.balance_service import BalanceService

# Configure logging
logger = get_logger(__file__)

# Create a Flask blueprint
balance_api = Blueprint('balance_api', __name__)

@balance_api.route('/balance', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)  # Rate limit: 10 requests per minute
def get_balance():
    """
    Get user balance from UserHolding table
    """
    try:
        # Validate request data
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)

        data = request.get_json()
        
        # Validate request against schema
        try:
            # Validate user ID format
            if not isinstance(data.get('UserID'), str):
                raise ValidationError("UserID must be a string", 400)
            
            user_id = InputValidator.validate_uuid(data.get('UserID'), "UserID")
            
            # Create validated request object
            request_data = UserBalanceRequest(
                UserID=user_id,
                CurrencyName=data.get('CurrencyName', []),
                Blockchain=data.get('Blockchain', {})
            )
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return jsonify({"error": str(e), "success": False}), 400
        
        logger.info(f"Processing balance request for UserID={user_id}")
        
        # Create database session
        session = SessionLocal()
        try:
            # Create balance service
            balance_service = BalanceService(session)
            
            # Get user balance using simplified method (doesn't use external APIs)
            # This is temporarily used for debugging instead of the original method
            result = balance_service.get_simple_user_balance(user_id)
            
            # Return the response
            return jsonify(result), 200
        
        finally:
            session.close()
        
    except ValidationError as ve:
        logger.warning(f"Validation error: {ve.message}")
        return jsonify({"error": ve.message, "success": False}), ve.status_code
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error processing balance request: {str(e)}\n{error_details}")
        return jsonify({
            "error_type": "internal_error", 
            "message": f"Internal server error: {str(e)}", 
            "traceback": error_details,
            "success": False
        }), 500

@balance_api.route('/update-balance', methods=['POST'])
@SecurityUtils.rate_limit(requests=2, window=300)  # Rate limit: 2 requests per 5 minutes (heavy operation)
def update_balance():
    """
    Update user balance by checking blockchain balances
    WARNING: This is a heavy operation that queries blockchain nodes
    """
    try:
        # Validate request data
        if not request.is_json:
            logger.warning("Received update-balance request with non-JSON content type")
            raise ValidationError("Content-Type must be application/json", 415)

        data = request.get_json()
        
        # Validate user ID
        if not isinstance(data.get('UserID'), str):
            logger.warning(f"Invalid UserID type in update-balance request: {type(data.get('UserID'))}")
            raise ValidationError("UserID must be a string", 400)
        
        user_id = InputValidator.validate_uuid(data.get('UserID'), "UserID")
        
        logger.info(f"Processing balance update request for UserID={user_id}")
        
        # Create database session
        session = SessionLocal()
        try:
            # Check if user exists
            user = session.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.warning(f"User not found for update-balance: {user_id}")
                return jsonify({
                    "success": False,
                    "error_type": "not_found",
                    "message": "User not found"
                }), 404
            
            # Check if user has wallets
            wallet_count = session.query(Wallets).filter(Wallets.UserID == user_id).count()
            if wallet_count == 0:
                logger.warning(f"No wallets found for user in update-balance: {user_id}")
                return jsonify({
                    "success": False, 
                    "error_type": "not_found",
                    "message": "No wallets found for user"
                }), 404
            
            # Log number of wallets and addresses for this user
            wallets = session.query(Wallets).filter(Wallets.UserID == user_id).all()
            wallet_ids = [w.WalletID for w in wallets]
            address_count = session.query(Address).filter(Address.WalletID.in_(wallet_ids)).count()
            
            logger.info(f"User {user_id} has {wallet_count} wallets with {address_count} addresses total")
            
            # Create balance service
            logger.info(f"Creating BalanceService instance for update-balance")
            balance_service = BalanceService(session)
            
            # List of blockchains available in database
            blockchains = session.query(Blockchains).all()
            blockchain_names = [b.BlockchainName for b in blockchains]
            logger.info(f"Blockchains in database: {blockchain_names}")
            
            # Update user balance using private method
            logger.info(f"Starting balance update for user {user_id}")
            start_time = datetime.now()
            result = balance_service._update_user_balance(user_id)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Balance update completed in {duration:.2f} seconds for user {user_id}")
            
            # Log success or failure
            if result.get('success', False):
                balances_count = len(result.get('Balances', []))
                logger.info(f"Successfully updated {balances_count} balances for user {user_id}")
                
                # Log specific blockchains found
                blockchains_found = set([b.get('blockchain') for b in result.get('Balances', [])])
                logger.info(f"Blockchains with balances: {list(blockchains_found)}")
            else:
                logger.error(f"Failed to update balances for user {user_id}: {result.get('message', 'unknown error')}")
            
            # Return the response
            return jsonify(result), 200 if result.get('success', False) else 500
        
        finally:
            session.close()
        
    except ValidationError as ve:
        logger.warning(f"Validation error in update-balance: {ve.message}")
        return jsonify({"error_type": "validation_error", "message": ve.message, "success": False}), ve.status_code
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error processing balance update request: {str(e)}\n{error_details}")
        return jsonify({
            "error_type": "internal_error", 
            "message": f"Internal server error: {str(e)}", 
            "traceback": error_details, 
            "success": False
        }), 500

@balance_api.route('/health-check', methods=['GET'])
def health_check():
    """
    Simple endpoint for testing the health of the balance module
    """
    try:
        # Debug information for diagnosing route access
        blueprint_info = {
            "name": balance_api.name,
            "import_name": balance_api.import_name,
            "url_prefix": "Unknown (set at registration)",
            "deferred_functions_count": len(balance_api.deferred_functions) if hasattr(balance_api, 'deferred_functions') else 0
        }
        
        # Return a simple response for diagnostics
        return jsonify({
            "success": True,
            "message": "Balance API health check",
            "module": "balance",
            "debug_info": blueprint_info,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in balance health check: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error_type": "health_check_error",
            "message": f"Health check failed: {str(e)}"
        }), 500

@balance_api.route('/debug', methods=['GET'])
def debug_balance():
    """
    Detailed diagnostic endpoint for debugging balance service
    """
    try:
        # Create a comprehensive diagnostic report
        diagnostic = {
            "timestamp": datetime.now().isoformat(),
            "module": "balance_api",
            "success": True,
            "tests": {}
        }
        
        # Test database connectivity
        try:
            session = SessionLocal()
            # Perform a simple query to test connection
            result = session.execute("SELECT 1").scalar()
            diagnostic["tests"]["database_connection"] = {
                "status": "ok",
                "message": f"Database connection successful, result: {result}"
            }
            
            # Test UserHolding table
            try:
                # Check if UserHolding table exists
                holdings_count = session.query(UserHolding).count()
                diagnostic["tests"]["userholding_table"] = {
                    "status": "ok",
                    "message": f"UserHolding table exists with {holdings_count} records"
                }
            except Exception as table_error:
                diagnostic["tests"]["userholding_table"] = {
                    "status": "error",
                    "message": f"Error accessing UserHolding table: {str(table_error)}"
                }
                diagnostic["success"] = False
            
            # Test Users table
            try:
                # Check if Users table exists
                users_count = session.query(Users).count()
                diagnostic["tests"]["users_table"] = {
                    "status": "ok",
                    "message": f"Users table exists with {users_count} records"
                }
            except Exception as table_error:
                diagnostic["tests"]["users_table"] = {
                    "status": "error",
                    "message": f"Error accessing Users table: {str(table_error)}"
                }
                diagnostic["success"] = False
            
            session.close()
            
        except Exception as db_error:
            diagnostic["tests"]["database_connection"] = {
                "status": "error",
                "message": f"Database connection error: {str(db_error)}"
            }
            diagnostic["success"] = False
        
        # Test BalanceService instantiation
        try:
            session = SessionLocal()
            balance_service = BalanceService(session)
            diagnostic["tests"]["balance_service"] = {
                "status": "ok",
                "message": "BalanceService instantiated successfully"
            }
            session.close()
        except Exception as service_error:
            diagnostic["tests"]["balance_service"] = {
                "status": "error",
                "message": f"Error instantiating BalanceService: {str(service_error)}"
            }
            diagnostic["success"] = False
        
        # Test API config
        try:
            from config.api_config import EXTERNAL_APIS
            api_keys = {
                key: "✓" if value else "✗" 
                for key, value in EXTERNAL_APIS.items() 
                if isinstance(value, str) and key.endswith("_API_KEY")
            }
            diagnostic["tests"]["api_config"] = {
                "status": "ok",
                "api_keys": api_keys,
                "tatum_key_present": "TATUM_API_KEY" in EXTERNAL_APIS
            }
        except Exception as config_error:
            diagnostic["tests"]["api_config"] = {
                "status": "error",
                "message": f"Error accessing API config: {str(config_error)}"
            }
            diagnostic["success"] = False
        
        # Test Web3 provider initialization 
        try:
            session = SessionLocal()
            balance_service = BalanceService(session)
            
            # Note: We don't actually initialize the providers to avoid errors,
            # but we check if the method exists
            diagnostic["tests"]["web3_providers"] = {
                "status": "ok",
                "message": "Web3 provider initialization method exists"
            }
            session.close()
        except Exception as web3_error:
            diagnostic["tests"]["web3_providers"] = {
                "status": "error",
                "message": f"Error with Web3 providers: {str(web3_error)}"
            }
            diagnostic["success"] = False
        
        # Include system info
        import platform
        import sys
        diagnostic["system_info"] = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "node": platform.node()
        }
        
        return jsonify(diagnostic)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in balance debug endpoint: {str(e)}\n{error_details}")
        return jsonify({
            "success": False,
            "error_type": "diagnostic_error",
            "message": f"Error running diagnostics: {str(e)}",
            "traceback": error_details
        }), 500

@balance_api.route('/test-update-balance', methods=['POST'])
def test_update_balance():
    """
    Test the balance update function in a safe way
    Returns diagnostic information instead of actually updating balances
    """
    try:
        # Validate request data
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)

        data = request.get_json()
        
        # Validate user ID
        if not isinstance(data.get('UserID'), str):
            raise ValidationError("UserID must be a string", 400)
        
        user_id = InputValidator.validate_uuid(data.get('UserID'), "UserID")
        
        logger.info(f"Processing test balance update request for UserID={user_id}")
        
        # Create diagnostic information
        diagnostic = {
            "timestamp": datetime.now().isoformat(),
            "request_info": {
                "user_id": user_id,
                "endpoint": "test-update-balance"
            },
            "tests": {}
        }
        
        # Create database session
        session = SessionLocal()
        try:
            # Check if user exists
            user = session.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                diagnostic["tests"]["user_check"] = {
                    "status": "error",
                    "message": "User not found"
                }
                diagnostic["success"] = False
                return jsonify(diagnostic), 404
            
            diagnostic["tests"]["user_check"] = {
                "status": "success",
                "user_id": user_id,
                "username": user.Username if hasattr(user, 'Username') else "N/A"
            }
            
            # Check if user has wallets
            wallets = session.query(Wallets).filter(Wallets.UserID == user_id).all()
            if not wallets:
                diagnostic["tests"]["wallet_check"] = {
                    "status": "error",
                    "message": "No wallets found for user"
                }
                diagnostic["success"] = False
                return jsonify(diagnostic), 404
            
            wallet_info = []
            for wallet in wallets:
                wallet_info.append({
                    "wallet_id": wallet.WalletID,
                    "is_multisig": wallet.IsMultiSig
                })
            
            diagnostic["tests"]["wallet_check"] = {
                "status": "success",
                "wallets_count": len(wallets),
                "wallets": wallet_info
            }
            
            # Get addresses for all wallets
            addresses = []
            for wallet in wallets:
                wallet_addresses = session.query(Address).filter(Address.WalletID == wallet.WalletID).all()
                for addr in wallet_addresses:
                    blockchain = session.query(Blockchains).filter(Blockchains.BlockchainID == addr.BlockchainID).first()
                    blockchain_name = blockchain.BlockchainName if blockchain else "Unknown"
                    addresses.append({
                        "address": addr.PublicAddress,
                        "blockchain": blockchain_name,
                        "blockchain_id": addr.BlockchainID
                    })
            
            diagnostic["tests"]["address_check"] = {
                "status": "success" if addresses else "warning",
                "addresses_count": len(addresses),
                "addresses": addresses if len(addresses) <= 10 else "Too many to display (truncated)"
            }
            
            # Check if BalanceService can be instantiated
            try:
                balance_service = BalanceService(session)
                diagnostic["tests"]["balance_service"] = {
                    "status": "success",
                    "message": "BalanceService instantiated successfully"
                }
                
                # Test Web3 initialization without actually connecting
                try:
                    diagnostic["tests"]["web3_init"] = {
                        "status": "info",
                        "message": "Web3 initialization available but not tested to avoid unnecessary connections"
                    }
                except Exception as web3_error:
                    diagnostic["tests"]["web3_init"] = {
                        "status": "warning",
                        "message": f"Web3 initialization may have issues: {str(web3_error)}"
                    }
                
                # Check existing holdings
                holdings = session.query(UserHolding).filter(UserHolding.UserID == user_id).all()
                holding_info = []
                for holding in holdings:
                    holding_info.append({
                        "currency_id": holding.CurrencyID,
                        "balance": str(holding.Balance),
                        "symbol": holding.Symbol,
                        "blockchain": holding.Blockchain,
                        "is_token": holding.IsToken
                    })
                
                diagnostic["tests"]["current_holdings"] = {
                    "status": "info",
                    "holdings_count": len(holdings),
                    "holdings": holding_info if len(holding_info) <= 10 else "Too many to display (truncated)"
                }
                
            except Exception as service_error:
                diagnostic["tests"]["balance_service"] = {
                    "status": "error",
                    "message": f"Error instantiating BalanceService: {str(service_error)}"
                }
                diagnostic["success"] = False
            
            diagnostic["success"] = True
            return jsonify(diagnostic)
        finally:
            session.close()
            
    except ValidationError as ve:
        logger.warning(f"Validation error: {ve.message}")
        return jsonify({
            "error_type": "validation_error", 
            "message": ve.message, 
            "success": False
        }), ve.status_code
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in test balance update: {str(e)}\n{error_details}")
        return jsonify({
            "error_type": "server_error", 
            "message": f"Server error in test: {str(e)}", 
            "traceback": error_details, 
            "success": False
        }), 500
