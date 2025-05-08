# Add compatibility patch for Python 3.12
import sys
import os

# Set up project path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

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
import logging
from datetime import datetime, timezone
import traceback
import json
import uuid
import importlib
from sqlalchemy import text

# Configure logging first
from utils.logging_config import get_logger
logger = get_logger(__file__)
logger.info("Starting IronWallet application")

# Import error handlers first (before database)
from utils.error_handlers import APIErrorHandler, handle_api_errors
from security.validators import SecurityUtils, ValidationError
from pydantic import Field

# Import all database models
try:
    from database import (
        init_db, 
        SessionLocal,
        Users,
        Wallets,
        Address,
        Blockchains,
        Currencies,
        UserHolding,
        Transfers,
        Base,
        engine
    )
    
    # Test database connection immediately
    logger.info("Testing database connection...")
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        scalar_result = result.scalar()
        logger.info(f"Database connection successful: {scalar_result}")

except Exception as db_import_error:
    logger.critical(f"Failed to connect to database: {str(db_import_error)}")
    logger.critical(traceback.format_exc())
    # Continue without crashing - API will return database errors when needed

# Import services and config
from config.queue import get_rabbitmq_connection
from config.swagger import register_swagger
from services.wallet_service import WalletService
from config.firebase import initialize_firebase

# Import schemas after services
from schemas import WalletGenerationResponse, WalletGenerationRequest

# Check RabbitMQ availability
rabbitmq_available = True
try:
    connection = get_rabbitmq_connection()
    connection.close()
    logger.info("RabbitMQ connection successful")
except Exception as e:
    logger.warning(f"RabbitMQ server is not available. Using synchronous processing instead: {str(e)}")
    rabbitmq_available = False

# Create the Flask app
info = Info(title="IronWallet API", version="1.0.0")
app = OpenAPI(__name__, info=info)

# Set a secret key for the application
app.secret_key = os.environ.get('SECRET_KEY', 'ironwallet-dev-secret-key')

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set additional Flask configurations for proper routing
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF globally for API usage
app.config['JSON_SORT_KEYS'] = False  # Preserve JSON key order in responses
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # Don't pretty-print JSON in production
app.config['TRAP_HTTP_EXCEPTIONS'] = True  # Trap HTTP exceptions for custom handling
app.config['TRAP_BAD_REQUEST_ERRORS'] = True  # Trap bad request errors
csrf = CSRFProtect(app)

# Initialize database
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as db_init_error:
    logger.critical(f"Failed to initialize database: {str(db_init_error)}")
    # Continue without database to allow API to start but return errors on DB operations

# Initialize Firebase
try:
    if initialize_firebase():
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Firebase initialization failed. Push notifications will be disabled.")
except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}", exc_info=True)

# Import blueprints after app creation to avoid circular imports
try:
    from generate import generate_bp
    from ImportWallet import import_bp
    from Currencies import Prices_bp, CPost_bp
    from Transactions import receive_bp, gasfee_bp
    from Send import send_bp
    from balance import balance_api
    from UserTransactions import transactions_bp
    from fee_estimator.api import fee_estimator_bp
    from api.notification_api import notification_api
    
    # Register blueprints
    logger.info("Registering blueprints")
    
    app.register_blueprint(generate_bp, url_prefix='')
    logger.info("Registered generate_bp")
    app.register_blueprint(import_bp, url_prefix='')
    logger.info("Registered import_bp")
    app.register_blueprint(Prices_bp, url_prefix='')
    logger.info(f"Registered Prices_bp - contains {len(Prices_bp.deferred_functions)} routes")
    app.register_blueprint(CPost_bp, url_prefix='')
    logger.info("Registered CPost_bp")
    app.register_blueprint(receive_bp, url_prefix='')
    logger.info("Registered receive_bp")
    app.register_blueprint(gasfee_bp, url_prefix='')
    logger.info("Registered gasfee_bp")
    app.register_blueprint(balance_api, url_prefix='')
    logger.info(f"Registered balance_api - contains {len(balance_api.deferred_functions)} routes")
    app.register_blueprint(send_bp, url_prefix='/send')
    logger.info("Registered send_bp")
    app.register_blueprint(transactions_bp, url_prefix='')
    logger.info("Registered transactions_bp")
    app.register_blueprint(notification_api, url_prefix='/api')
    logger.info("Registered notification_api with prefix /api")
    
    # Register Fee Estimator endpoints
    app.register_blueprint(fee_estimator_bp, url_prefix='')
    logger.info("Registered Fee Estimator endpoints")
    
    logger.info("All blueprints registered successfully")
except Exception as e:
    logger.error(f"Error registering blueprints: {str(e)}", exc_info=True)
    raise

# Register Swagger UI
register_swagger(app)

# Initialize webhook blueprint
from webhook import init_app as init_webhook
from webhook.database_operations import DatabaseOperations
from webhook.tatum_subscription import create_batched_blockchain_subscriptions, group_addresses_by_blockchain, list_subscriptions

# Register the webhook blueprint
init_webhook(app)

# Setup webhook subscriptions automatically
def setup_webhook_subscriptions():
    """Setup webhook subscriptions for all user addresses automatically"""
    try:
        logger.info("Starting automatic webhook subscription setup")
        
        # Check existing subscriptions first
        existing_subscriptions = list_subscriptions()
        existing_batch_count = sum(1 for sub in existing_subscriptions 
                                 if sub.get('type') == 'ADDRESS_TRANSACTION' 
                                 and 'addresses' in sub.get('attr', {}))
        
        # Get all user addresses
        db_operations = DatabaseOperations()
        user_addresses = db_operations.get_user_addresses()
        
        if not user_addresses:
            logger.warning("No user addresses found in database for webhook setup")
            return
            
        # Group addresses by blockchain
        grouped_addresses = group_addresses_by_blockchain(user_addresses)
        total_addresses = sum(len(addresses) for addresses in grouped_addresses.values())
        
        # Log the address counts by blockchain
        for blockchain, addresses in grouped_addresses.items():
            logger.info(f"Found {len(addresses)} addresses for {blockchain}")
            
        # If we already have batch subscriptions, check if we need to update
        if existing_batch_count > 0:
            logger.info(f"Found {existing_batch_count} existing batch subscriptions")
            
            # Only proceed if force update is enabled or there are many new addresses
            # Here we use a threshold - if more than 20% new addresses, update subscriptions
            # This logic can be adjusted based on requirements
            if os.environ.get('FORCE_WEBHOOK_UPDATE', '').lower() == 'true':
                logger.info("Force webhook update enabled, proceeding with subscription creation")
            else:
                logger.info("Existing subscriptions found, skipping automatic update")
                # You could implement more sophisticated checking here
                return
        
        # Create batch subscriptions
        logger.info(f"Creating batch subscriptions for {total_addresses} addresses across {len(grouped_addresses)} blockchains")
        results = create_batched_blockchain_subscriptions(user_addresses)
        
        # Log the results
        total_subscriptions = sum(len(subs) for subs in results)
        logger.info(f"Successfully created {total_subscriptions} batch subscriptions")
        
        # Save results to a file for reference
        import json
        import os
        results_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webhook", "batch_subscriptions.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved subscription results to {results_file}")
        
    except Exception as e:
        logger.error(f"Error setting up webhook subscriptions: {str(e)}", exc_info=True)
        # Continue with application startup even if webhook setup fails
        
# Run the webhook setup
setup_webhook_subscriptions()

# Check price scheduler status
try:
    # Import the price scheduler
    from Currencies.price_scheduler import run_scheduler
    
    # Create a thread for the price scheduler if it's not already running
    import threading
    scheduler_thread = None
    
    for thread in threading.enumerate():
        if thread.name.startswith("Package-") or thread.name == "PriceScheduler":
            scheduler_thread = thread
            app.logger.info(f"Price scheduler is already running in thread: {thread.name}")
            break
    
    if not scheduler_thread:
        app.logger.info("Starting price scheduler...")
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True, name="PriceScheduler")
        scheduler_thread.start()
        app.logger.info("Price scheduler started successfully")
    
except Exception as scheduler_error:
    app.logger.error(f"Error starting price scheduler: {str(scheduler_error)}", exc_info=True)

# اضافه کردن شبیه‌ساز قیمت NCC
try:
    # بررسی اینکه شبیه‌ساز NCC از قبل در حال اجرا نباشد
    ncc_simulator_thread = None
    
    for thread in threading.enumerate():
        if thread.name == "NCCPriceSimulator":
            ncc_simulator_thread = thread
            app.logger.info(f"NCC price simulator is already running in thread: {thread.name}")
            break
    
    if not ncc_simulator_thread:
        from utils.price_simulator.NCCPRICE import main as ncc_price_simulator
        app.logger.info("Starting NCC price simulator...")
        ncc_simulator_thread = threading.Thread(target=ncc_price_simulator, daemon=True, name="NCCPriceSimulator")
        ncc_simulator_thread.start()
        app.logger.info("NCC price simulator started successfully")
    
except Exception as ncc_error:
    app.logger.error(f"Error starting NCC price simulator: {str(ncc_error)}", exc_info=True)
    # نمایش جزئیات خطا برای عیب‌یابی
    app.logger.error(f"NCC price simulator error details: {traceback.format_exc()}")
    # در صورت خطا برنامه ادامه پیدا می‌کند

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
                # Get user IP and device info
                user_ip = request.remote_addr
                user_device = request.headers.get('User-Agent', 'Unknown Device')
                logger.info(f"Generate wallet request from IP: {user_ip}, Device: {user_device}")
                
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                
                channel.queue_declare(queue='wallet_generation')
                channel.basic_publish(
                    exchange='',
                    routing_key='wallet_generation',
                    body=json.dumps({
                        'task_id': task_id,
                        'wallet_name': wallet_name,
                        'user_ip': user_ip,
                        'user_device': user_device
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
            
            # Get user IP and device info
            user_ip = request.remote_addr
            user_device = request.headers.get('User-Agent', 'Unknown Device')
            logger.info(f"Generate wallet request from IP: {user_ip}, Device: {user_device}")
            
            session = SessionLocal()
            try:
                # Use service to create wallet
                wallet_service = WalletService(session)
                with session.begin():
                    user_id, mnemonic, addresses = wallet_service.create_wallet(wallet_name, 5, user_ip, user_device)

                # Log success
                logger.info(f"Wallet generated synchronously for user {user_id}")

                # Исправление структуры ответа, добавляя поле Addresses для соответствия с другими endpoint
                return jsonify({
                    'UserID': user_id,
                    'Mnemonic': mnemonic,
                    'Addresses': addresses,
                    'success': True
                }), 201
            except Exception as session_error:
                logger.error(f"Database error in generate_wallet: {str(session_error)}")
                raise
            finally:
                session.close()
        
    except Exception as e:
        logger.error(f"Error in generate_wallet: {str(e)}")
        raise

@app.route('/test-db', methods=['GET'])
def test_db_connection():
    """Test database connection"""
    try:
        session = SessionLocal()
        try:
            # Try to execute a simple query
            result = session.execute(text("SELECT 1")).scalar()
            
            # Check if tables exist
            table_status = {}
            from sqlalchemy import inspect
            inspector = inspect(engine)
            all_tables = inspector.get_table_names()
            
            # Check status of important tables
            required_tables = ['Users', 'Wallets', 'Address', 'Blockchains', 'Currencies', 'UserHolding', 'Transfers']
            for table in required_tables:
                table_status[table] = table in all_tables
            
            return jsonify({
                "success": True,
                "message": "Database connection successful",
                "result": result,
                "tables": table_status,
                "all_tables": all_tables
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return jsonify({
            "success": False,
            "error_type": "database_error", 
            "message": f"Database connection failed: {str(e)}"
        }), 500

@app.route('/test-api', methods=['GET'])
def test_api():
    """Test API endpoint for basic functionality"""
    try:
        return jsonify({
            "success": True,
            "message": "API is operating correctly",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "IronWallet API",
            "environment": os.environ.get('FLASK_ENV', 'development')
        })
    except Exception as e:
        logger.error(f"Error in test_api: {str(e)}")
        return jsonify({
            "success": False,
            "error_type": "api_error",
            "message": f"API error: {str(e)}"
        }), 500

@app.route('/api/app-health', methods=['GET'])
def app_health():
    """Application health check"""
    try:
        # Check database connection first
        db_status = "ok"
        try:
            session = SessionLocal()
            try:
                session.execute("SELECT 1").scalar()
            finally:
                session.close()
        except Exception as db_error:
            db_status = f"error: {str(db_error)}"
            logger.error(f"Database health check failed: {str(db_error)}")
        
        # Check RabbitMQ if needed
        rabbitmq_status = "ok" if rabbitmq_available else "unavailable"
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "api": "ok",
                "database": db_status,
                "rabbitmq": rabbitmq_status
            },
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    
    # Ensure JSON is returned with correct content type
    if response.mimetype == 'application/json':
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    return response

@app.after_request
def add_keep_alive_headers(response):
    """Add keep-alive headers to responses"""
    response.headers['Connection'] = 'keep-alive'
    return response

# Register global error handlers
@app.errorhandler(ValidationError)
@app.errorhandler(CSRFError)
@app.errorhandler(Exception)
def handle_error(e):
    """Global error handler"""
    return APIErrorHandler.handle_error(e, request)

@app.route('/debug-api', methods=['GET'])
def debug_api():
    """Special debug endpoint that returns information about the Flask application configuration"""
    try:
        # Get registered blueprint information
        blueprint_data = {}
        for name, bp in app.blueprints.items():
            blueprint_data[name] = {
                "name": bp.name,
                "import_name": bp.import_name,
                "url_map": str(app.url_map),
                "deferred_functions": len(bp.deferred_functions) if hasattr(bp, 'deferred_functions') else 0
            }
        
        # Get registered routes
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                "endpoint": rule.endpoint,
                "methods": list(rule.methods),
                "rule": str(rule)
            })
        
        # Return comprehensive debug data
        return jsonify({
            "app_name": app.name,
            "debug": app.debug,
            "blueprints": blueprint_data,
            "routes": routes,
            "server_info": {
                "timestamp": datetime.now().isoformat(),
                "flask_version": Flask.__version__
            }
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "error": str(e),
            "traceback": str(traceback.format_exc())
        }), 500

# Add Flask error handler for debugging
@app.errorhandler(500)
def handle_500_error(e):
    """Custom error handler for 500 Internal Server Error"""
    logger.error(f"500 error caught by custom handler: {str(e)}", exc_info=True)
    
    # Collect information about the request
    endpoint = request.endpoint
    path = request.path
    method = request.method
    
    return jsonify({
        "error_type": "internal_error",
        "message": "Internal server error caught by custom handler",
        "debug_info": {
            "endpoint": endpoint,
            "path": path,
            "method": method,
            "error": str(e)
        },
        "success": False
    }), 500

@app.route('/api/database-test')
def test_database():
    """API endpoint to test database connection and report problems"""
    from utils.logging_config import get_logger
    logger = get_logger("database_test")
    
    try:
        # Test database connection
        logger.info("Testing database connection...")
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            scalar_result = result.scalar()
            
            # Try to query tables
            tables = []
            try:
                table_query = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                for table in table_query:
                    tables.append(table[0])
            except Exception as table_err:
                logger.error(f"Error querying tables: {str(table_err)}")
            
            return jsonify({
                'success': True,
                'database_connection': 'ok',
                'test_query_result': scalar_result,
                'tables_count': len(tables),
                'tables': tables,
                'message': 'Database connection test was successful'
            })
            
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'database_error',
            'message': str(e),
            'recommendation': 'Check DATABASE_URL environment variable and make sure database server is running'
        }), 500

# Add another test endpoint for API key testing
@app.route('/api/config-test')
def test_config():
    """API endpoint to test configuration variables without exposing sensitive data"""
    from utils.logging_config import get_logger
    logger = get_logger("config_test")
    
    # Check environment variables (without revealing full values)
    env_checks = {}
    critical_vars = [
        'DATABASE_URL', 'AES_SECRET_KEY', 'FLASK_ENV', 
        'RABBITMQ_HOST', 'RABBITMQ_PORT', 'RABBITMQ_USER'
    ]
    
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            # Only show first and last few characters of sensitive data
            if var in ['DATABASE_URL', 'AES_SECRET_KEY']:
                masked_value = f"{value[:5]}...{value[-5:]}" if len(value) > 10 else "***" 
                env_checks[var] = {
                    'status': 'set',
                    'masked_value': masked_value,
                    'length': len(value)
                }
            else:
                env_checks[var] = {
                    'status': 'set',
                    'value': value
                }
        else:
            env_checks[var] = {
                'status': 'missing',
                'recommendation': 'Set this environment variable'
            }
    
    return jsonify({
        'success': True,
        'environment_checks': env_checks,
        'python_version': sys.version,
        'message': 'Configuration test completed'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
