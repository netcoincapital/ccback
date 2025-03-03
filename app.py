# Add compatibility patch for Python 3.12
import sys
if sys.version_info >= (3, 10):
    import collections
    import collections.abc
    collections.Mapping = collections.abc.Mapping
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Sequence = collections.abc.Sequence

# Add compatibility patch for inspect.getargspec
if sys.version_info >= (3, 11):
    import inspect
    inspect.getargspec = inspect.getfullargspec


from flask import Flask, after_this_request, jsonify, request
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_openapi3 import OpenAPI, Info
from database import init_db, SessionLocal
from generate import generate_bp
from WI import import_bp
from CU import CUpdate_bp, CPost_bp
from TA import phrase_key_bp, receive_bp, gasfee_bp
from security.validators import SecurityUtils, ValidationError
from schemas import WalletGenerationResponse, WalletGenerationRequest
import logging
import os
from datetime import datetime, timezone
from utils.error_handlers import APIErrorHandler, handle_api_errors
from pydantic import Field
import json
import uuid
from services.wallet_service import WalletService
from config.queue import get_rabbitmq_connection
from config.swagger import register_swagger
from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)
logger.info("Starting IronWallet application")

# Check if RabbitMQ is available
rabbitmq_available = True
try:
    connection = get_rabbitmq_connection()
    connection.close()
    logger.info("RabbitMQ connection successful")
except Exception as e:
    logger.warning(f"RabbitMQ server is not available. Using synchronous processing instead: {str(e)}")
    rabbitmq_available = False

info = Info(title="IronWallet API", version="1.0.0")
app = OpenAPI(__name__, info=info)

# Set a secret key for the application
app.secret_key = os.environ.get('SECRET_KEY', 'ironwallet-dev-secret-key')

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Enable CSRF protection but disable it for API endpoints
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF globally for API usage
csrf = CSRFProtect(app)

# Register blueprints
app.register_blueprint(generate_bp, url_prefix='/generate')
app.register_blueprint(import_bp, url_prefix='')
app.register_blueprint(CUpdate_bp, url_prefix='')
app.register_blueprint(CPost_bp, url_prefix='')
app.register_blueprint(phrase_key_bp, url_prefix='')
app.register_blueprint(receive_bp, url_prefix='')
app.register_blueprint(gasfee_bp, url_prefix='')

# Initialize database
init_db()

# Register Swagger UI
register_swagger(app)

@app.route('/')
def index():
    """API root endpoint"""
    return jsonify({
        'name': 'IronWallet API',
        'version': '1.0.0',
        'documentation': '/api/docs',
        'status': 'online',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.post("/generate-wallet", responses={"202": WalletGenerationResponse})
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def generate_wallet(body: WalletGenerationRequest):
    """
    Generate a new wallet asynchronously
    ---
    tags:
      - Wallet Management
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/WalletGenerationRequest'
    responses:
      202:
        description: Wallet generation started
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WalletGenerationResponse'
      400:
        description: Invalid input data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
      429:
        description: Rate limit exceeded
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
    """
    global rabbitmq_available
    
    try:
        # Validate input
        wallet_name = body.WalletName
        
        # Generate a task ID
        task_id = str(uuid.uuid4())
        
        if rabbitmq_available:
            # Send task to RabbitMQ
            try:
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                
                channel.queue_declare(queue='wallet_generation')
                channel.basic_publish(
                    exchange='',
                    routing_key='wallet_generation',
                    body=json.dumps({
                        'task_id': task_id,
                        'wallet_name': wallet_name
                    })
                )
                
                connection.close()
                
                logger.info(f"Wallet generation task {task_id} queued for processing")
                
                # Return response with task ID
                return jsonify({
                    'task_id': task_id,
                    'status': 'processing',
                    'message': 'Wallet generation in progress',
                    'success': True
                }), 202
            except Exception as e:
                logger.error(f"Error connecting to RabbitMQ: {str(e)}")
                # Fall back to synchronous processing
                rabbitmq_available = False
        
        # If RabbitMQ is not available, process synchronously
        if not rabbitmq_available:
            logger.info(f"Processing wallet generation synchronously for {wallet_name}")
            session = SessionLocal()
            try:
                # Use service to create wallet
                wallet_service = WalletService(session)
                with session.begin():
                    user_id, mnemonic, addresses = wallet_service.create_wallet(wallet_name)

                # Log success
                logger.info(f"Wallet generated synchronously for user {user_id}")

                return jsonify({
                    'UserID': user_id,
                    'Mnemonic': mnemonic,
                    'Addresses': addresses,
                    'success': True
                }), 201
            finally:
                session.close()
        
    except Exception as e:
        logger.error(f"Error in generate_wallet: {str(e)}")
        raise

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Content Security Policy
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # XSS Protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # HTTP Strict Transport Security
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

@app.after_request
def add_keep_alive_headers(response):
    """Add keep-alive headers to all responses"""
    response.headers['Connection'] = 'keep-alive'
    response.headers['Keep-Alive'] = 'timeout=5, max=1000'
    return response

@app.errorhandler(ValidationError)
@app.errorhandler(CSRFError)
@app.errorhandler(Exception)
def handle_error(e):
    """Global error handler"""
    return APIErrorHandler.handle_error(e, request)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
