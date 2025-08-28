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
    """Decorator to log transaction requests safely"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
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
            logger.info(f"Transaction request: {request.method} {request.path}")
            logger.debug(f"Request data: {json.dumps(safe_data, indent=2)}")
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in transaction request logging: {str(e)}")
            return func(*args, **kwargs)
    return wrapper 