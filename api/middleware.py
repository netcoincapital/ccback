"""
API Middleware for handling common request processing tasks.
"""
import json
import logging
from functools import wraps
from flask import request, jsonify, g
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of sensitive fields that should never be logged
SENSITIVE_FIELDS = [
    'private_key', 'privateKey', 'fromPrivateKey', 
    'fromSecret', 'secret', 'mnemonic', 'passphrase', 
    'password', 'seed', 'key', 'token', 'secret_key',
    'authKey'
]

def sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive data for logging purposes"""
    if not data or not isinstance(data, dict):
        return {}
        
    safe_data = data.copy()
    
    # Mask sensitive fields
    for field in SENSITIVE_FIELDS:
        if field in safe_data:
            safe_data[field] = '***'
            
    # Also check for nested dictionaries
    for key, value in safe_data.items():
        if isinstance(value, dict):
            safe_data[key] = sanitize_data(value)
    
    return safe_data

def debug_auth_middleware(app):
    """
    Middleware to debug authentication errors.
    This intercepts responses with 'Authentication required' and adds more debug information.
    """
    @app.after_request
    def debug_auth_response(response):
        try:
            if response.status_code == 400:
                try:
                    resp_data = json.loads(response.get_data(as_text=True))
                    if 'success' in resp_data and not resp_data.get('success') and 'authentication' in resp_data.get('message', '').lower():
                        # Log debug information
                        logger.critical(f"Authentication error detected in response")
                        logger.critical(f"Request method: {request.method}")
                        logger.critical(f"Request URL: {request.url}")
                        logger.critical(f"Request content type: {request.content_type}")
                        
                        # Don't log raw headers - they may contain auth tokens
                        safe_headers = {k: v for k, v in dict(request.headers).items() 
                                       if k.lower() not in ['authorization', 'x-auth-token', 'token']}
                        logger.critical(f"Request headers (sanitized): {safe_headers}")
                        
                        # Get request data without sensitive information
                        data = {}
                        if request.is_json and request.get_data():
                            try:
                                data = request.get_json(silent=True) or {}
                            except Exception:
                                pass
                        elif request.form:
                            data = request.form.to_dict()
                        elif request.args:
                            data = request.args.to_dict()
                        
                        # Sanitize data using our utility function
                        safe_data = sanitize_data(data)
                        logger.critical(f"Request data (sanitized): {json.dumps(safe_data, indent=2)}")
                        
                        # Check for UserID in various formats
                        user_id = None
                        for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
                            if key in data:
                                user_id = data[key]
                                logger.critical(f"Found UserID '{user_id}' in key: {key}")
                                break
                        
                        # Update response with more helpful message
                        new_response = {
                            "success": False,
                            "message": "UserID parameter is required for this request",
                            "debug_info": {
                                "note": "Please add UserID parameter to your request",
                                "request_url": request.url,
                                "content_type": request.content_type,
                                "user_id_found": user_id is not None,
                                "user_id_key": user_id is not None and [k for k in data if k.lower() in ['userid', 'user_id'] and data.get(k) == user_id][0] if user_id else None
                            }
                        }
                        
                        # Create a new response
                        response.set_data(json.dumps(new_response))
                except Exception as e:
                    logger.error(f"Error in debug middleware: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing response in debug middleware: {str(e)}")
        return response
    
    return app

# Utility to check if a userId is present in the request
def requires_user_id(func):
    """Decorator to check if userId is present in request"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        elif request.form:
            data = request.form.to_dict()
        elif request.args:
            data = request.args.to_dict()
        
        # Look for userId in various formats and casing
        user_id = (data.get('UserId') or data.get('userId') or 
                  data.get('UserID') or data.get('userid') or 
                  data.get('user_id'))
        
        if not user_id:
            logger.warning("Missing userId in request")
            return jsonify({
                "success": False,
                "message": "UserID is required but not provided in the request"
            }), 400
            
        # Store the user_id for use in the view function
        g.user_id = user_id
        
        return func(*args, **kwargs)
    return wrapper

def normalize_parameters(func):
    """Middleware to normalize parameter names, adding userId if missing but found in variant formats"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get request data in appropriate format
        data = {}
        if request.is_json:
            data = request.get_json(silent=True) or {}
        elif request.form:
            data = request.form.to_dict()
        elif request.args:
            data = request.args.to_dict()
        
        # Create a normalized copy to avoid modifying the original
        normalized_data = data.copy()
        
        # Normalize UserID/userId parameters
        user_id = None
        for key in ['UserId', 'userId', 'UserID', 'userid', 'user_id']:
            if key in data and data[key]:
                user_id = data[key]
                break
        
        # If we found a userId, add it to the data with standard keys
        if user_id:
            normalized_data['userId'] = user_id
            normalized_data['UserID'] = user_id
        
        # Normalize other common parameters
        param_mappings = {
            'sender_address': ['senderAddress', 'from', 'sender'],
            'recipient_address': ['recipientAddress', 'to', 'recipient'],
            'amount': ['value', 'amount'],
            'smart_contract_address': ['contractAddress', 'contract', 'token'],
            'transaction_id': ['txId', 'id', 'tx_id'],
            'blockchain': ['chain', 'network']
        }
        
        for target_key, variants in param_mappings.items():
            # Check if any variants are present
            for variant in variants:
                if variant in data and data[variant] and target_key not in normalized_data:
                    normalized_data[target_key] = data[variant]
        
        # Store the normalized data for use in the route function
        g.normalized_data = normalized_data
        
        # Continue with the original request data
        return func(*args, **kwargs)
    return wrapper

def log_transaction_request(func):
    """Middleware to log transaction requests with sensitive data sanitized"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            method = request.method
            path = request.path
            endpoint = request.endpoint
            
            # Get request data
            data = {}
            if request.is_json:
                data = request.get_json(silent=True) or {}
            elif request.form:
                data = request.form.to_dict()
            elif request.args:
                data = request.args.to_dict()
                
            # Sanitize and log
            safe_data = sanitize_data(data)
            logger.info(f"Transaction request: {method} {path} ({endpoint})")
            logger.debug(f"Transaction data (sanitized): {json.dumps(safe_data, indent=2)}")
            
        except Exception as e:
            logger.error(f"Error in transaction logging middleware: {str(e)}")
            
        return func(*args, **kwargs)
    return wrapper 