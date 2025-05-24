# API package initialization
# این پکیج حاوی API‌های مختلف برای سیستم است 

from flask import Blueprint, Flask
from flask_cors import CORS
from functools import wraps

# Import the blockchain API blueprint
from api.blockchain_api import blockchain_api

def init_api_routes(app: Flask):
    """Initialize API routes"""
    
    # Apply CORS specifically for the API
    CORS(blockchain_api, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
    
    # Register the Blueprint
    app.register_blueprint(blockchain_api, url_prefix='/api')
    
    # Log registration
    app.logger.info("Registered blockchain API routes")

def add_cors_headers(response):
    """Add CORS headers to responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response
    
def cors_enabled(f):
    """Decorator to add CORS headers to responses"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        response = f(*args, **kwargs)
        return add_cors_headers(response)
    return wrapped 