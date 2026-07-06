# Add compatibility patch for Python 3.12
import sys
import os

# Set up project path (both root and parent for "CC." imports)
_project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.dirname(_project_root))  # enables "from CC.database import ..."

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

from flask import Flask, after_this_request, jsonify, request, send_from_directory, redirect, Response
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_openapi3 import OpenAPI, Info
import logging
from datetime import datetime, timezone
import traceback
import json
import uuid
import importlib
import time
import threading
from sqlalchemy import text
import requests

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
from schemas import WalletGenerationResponse, WalletGenerationRequest, WalletGenerationSyncResponse

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

# Initialize SocketIO for WebSocket support
try:
    from chat.websocket_handler import init_socketio, register_socketio_events
    socketio = init_socketio(app)
    register_socketio_events(socketio)
    logger.info("SocketIO initialized successfully for real-time chat")
except Exception as socketio_error:
    logger.error(f"Failed to initialize SocketIO: {str(socketio_error)}")
    logger.error(traceback.format_exc())
    socketio = None

# --- محدودیت API (غیرفعال؛ برای استفاده بعدی کامنت برداری کنید) ---
# def _parse_allowed_origins():
#     raw = os.environ.get('ALLOWED_ORIGINS', 'coinceeper.com,www.coinceeper.com,localhost,127.0.0.1')
#     return [o.strip().lower() for o in raw.split(',') if o.strip()]
#
# def _host_from_url(url_or_host):
#     """Extract host from Origin/Referer URL or return as-is if already a host."""
#     if not url_or_host:
#         return ''
#     s = url_or_host.strip().lower()
#     for prefix in ('https://', 'http://'):
#         if s.startswith(prefix):
#             s = s[len(prefix):]
#     if '/' in s:
#         s = s.split('/')[0]
#     if ':' in s:
#         s = s.split(':')[0]
#     return s
#
# ALLOWED_ORIGINS_LIST = _parse_allowed_origins()
# Enable CORS only for allowed origins (when using allowlist, uncomment above and use block below):
# if ALLOWED_ORIGINS_LIST:
#     _cors_origin_list = []
#     for h in ALLOWED_ORIGINS_LIST:
#         if h in ('localhost', '127.0.0.1'):
#             _cors_origin_list.extend([f'http://{h}', f'https://{h}', f'http://{h}:3000', f'http://{h}:5173', f'http://{h}:8080'])
#         else:
#             _cors_origin_list.extend([f'https://{h}', f'https://www.{h}', f'http://{h}', f'http://www.{h}'])
#     CORS(app, resources={r"/*": {"origins": _cors_origin_list}}, supports_credentials=True)
# else:
#     CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

BLOCKED_ORIGINS = os.environ.get('BLOCKED_ORIGINS', 'laxce.com,laxce').split(',')
BLOCKED_ORIGINS = [o.strip().lower() for o in BLOCKED_ORIGINS if o.strip()]

# Enable CORS (حالت قبلی: همه دامنه‌ها)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set additional Flask configurations for proper routing
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF globally for API usage
app.config['JSON_SORT_KEYS'] = False  # Preserve JSON key order in responses
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # Don't pretty-print JSON in production
app.config['TRAP_HTTP_EXCEPTIONS'] = True  # Trap HTTP exceptions for custom handling
app.config['TRAP_BAD_REQUEST_ERRORS'] = True  # Trap bad request errors
csrf = CSRFProtect(app)

# --- کلید API (غیرفعال؛ برای استفاده بعدی کامنت برداری کنید) ---
# CC_API_KEY = os.environ.get('CC_API_KEY', '').strip()
# API_KEY_EXEMPT_PATHS = ('/ping', '/api/ping', '/api/app-health')

@app.before_request
def restrict_api_to_coinceeper():
    """Block requests from blocked origins (e.g. laxce). API key and allowlist are commented out."""
    if not request.path.startswith('/api/'):
        return
    origin = request.headers.get('Origin', '').lower()
    referer = request.headers.get('Referer', '').lower()
    host = request.headers.get('Host', '').lower()

    # 1) Require API key (غیرفعال؛ برای فعال‌سازی کامنت را بردارید و _parse_allowed_origins / _host_from_url / ALLOWED_ORIGINS_LIST را هم فعال کنید)
    # path = request.path.rstrip('/') or request.path
    # exempt = any(path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/') for p in API_KEY_EXEMPT_PATHS)
    # if CC_API_KEY and not exempt:
    #     api_key = request.headers.get('X-API-Key', '').strip()
    #     if not api_key and request.headers.get('Authorization', '').startswith('Bearer '):
    #         api_key = request.headers.get('Authorization', '')[7:].strip()
    #     if api_key != CC_API_KEY:
    #         logger.warning(f"Blocked request (invalid/missing API key): Path={request.path}")
    #         return jsonify({'success': False, 'error': 'Access denied. Invalid or missing API key.', 'message': 'API access restricted'}), 403

    # 2) Block known bad origins (فعال)
    for blocked in BLOCKED_ORIGINS:
        if blocked in origin or blocked in referer or blocked in host:
            logger.warning(f"Blocked request from blocked origin: Origin={origin}, Referer={referer}, Host={host}, Path={request.path}")
            return jsonify({
                'success': False,
                'error': 'Access denied. This API is only available for coinceeper project.',
                'message': 'API access restricted'
            }), 403

    # 3) Allowlist (غیرفعال؛ برای استفاده بعدی کامنت برداری کنید)
    # origin_host = _host_from_url(origin)
    # referer_host = _host_from_url(referer)
    # has_origin_or_referer = bool(origin.strip() or referer.strip())
    # if has_origin_or_referer:
    #     allowed = origin_host in ALLOWED_ORIGINS_LIST or referer_host in ALLOWED_ORIGINS_LIST
    #     if not allowed:
    #         logger.warning(f"Blocked request (allowlist): Origin={origin}, Referer={referer}, Path={request.path}")
    #         return jsonify({'success': False, 'error': 'Access denied. This API is only available for coinceeper project.', 'message': 'API access restricted'}), 403

# Initialize database
try:
    init_db()
    logger.info("Database initialized successfully")
    
    # Run migration to increase DeviceToken field length
    try:
        # from migrations.add_user_device_token_length import run_migration
        # migration_result = run_migration()
        # if migration_result:
        #     logger.info("DeviceToken field length migration completed successfully")
        # else:
        #     logger.warning("DeviceToken field length migration was not needed or failed")
        logger.info("Skipping DeviceToken migration - migrations module not available")
    except Exception as migration_error:
        logger.error(f"Error running DeviceToken migration: {str(migration_error)}", exc_info=True)
        
except Exception as db_init_error:
    logger.critical(f"Failed to initialize database: {str(db_init_error)}")
    # Continue without database to allow API to start but return errors on DB operations

# Initialize shop and chat database
try:
    from database_shop_chat import init_shop_chat_db
    init_shop_chat_db()
    logger.info("Shop and Chat database initialized successfully")
except Exception as shop_chat_db_error:
    logger.critical(f"Failed to initialize shop and chat database: {str(shop_chat_db_error)}")
    logger.critical(traceback.format_exc())

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
    from Currencies.chart_api import chart_bp
    from Transactions import receive_bp, gasfee_bp
    from Send import send_bp
    from balance import balance_api
    from UserTransactions import transactions_bp
    from fee_estimator.api import fee_estimator_bp
    from api.notification_api import notification_api
    from api.notifications_admin_api import notifications_admin_bp
    from api.ads_api import ads_api
    from api.app_version_api import app_version_bp
    from api.blockchains_api import blockchains_bp
    from api import init_api_routes
    from shop.shop_api import shop_api
    from chat.dm_api import dm_api
    from chat.report_block_api import report_block_api
    from chat.moderation_api import moderation_api
    from services.cache_proxy import cache_proxy_bp, cache_proxy_v3_bp
    # Authentication middleware removed - using UserID-based authentication
    
    # Register blueprints
    logger.info("Registering blueprints")
    
    app.register_blueprint(generate_bp, url_prefix='/api')
    logger.info("Registered generate_bp")
    app.register_blueprint(import_bp, url_prefix='/api')
    logger.info("Registered import_bp")
    app.register_blueprint(Prices_bp, url_prefix='/api')
    logger.info(f"Registered Prices_bp - contains {len(Prices_bp.deferred_functions)} routes")
    app.register_blueprint(CPost_bp, url_prefix='/api')
    logger.info("Registered CPost_bp")
    app.register_blueprint(chart_bp, url_prefix='/api')
    logger.info("Registered chart_bp")
    app.register_blueprint(receive_bp, url_prefix='/api')
    logger.info("Registered receive_bp")
    app.register_blueprint(gasfee_bp, url_prefix='/api')
    logger.info("Registered gasfee_bp")
    app.register_blueprint(balance_api, url_prefix='/api')
    logger.info(f"Registered balance_api - contains {len(balance_api.deferred_functions)} routes")
    app.register_blueprint(send_bp, url_prefix='/api/send')
    logger.info("Registered send_bp")
    app.register_blueprint(transactions_bp, url_prefix='/api')
    logger.info("Registered transactions_bp")
    app.register_blueprint(notification_api, url_prefix='/api')
    logger.info("Registered notification_api without prefix")
    
    # Register Notification Admin API (security, price alerts, broadcast)
    app.register_blueprint(notifications_admin_bp, url_prefix='/api')
    logger.info("Registered notifications_admin_api")

    # Register Ads API
    app.register_blueprint(ads_api, url_prefix='/api')
    logger.info("Registered ads_api")

    # Register App Version API (force update detection)
    app.register_blueprint(app_version_bp, url_prefix='/api')
    logger.info("Registered app_version_api")

    # Register Blockchains List API
    app.register_blueprint(blockchains_bp, url_prefix='/api')
    logger.info("Registered blockchains_api")
    
    # نمایش تمام مسیرهای ثبت شده
    logger.info("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"Route: {rule.rule}, Methods: {rule.methods}, Endpoint: {rule.endpoint}")
    
    # Register Fee Estimator endpoints
    app.register_blueprint(fee_estimator_bp, url_prefix='/api')
    logger.info("Registered Fee Estimator endpoints")
    
    # Register Shop API endpoints
    app.register_blueprint(shop_api, url_prefix='/api')
    logger.info("Registered shop_api")
    
    # Register Chat API endpoints
    app.register_blueprint(dm_api, url_prefix='/api')
    logger.info("Registered dm_api")
    app.register_blueprint(report_block_api, url_prefix='/api')
    logger.info("Registered report_block_api")
    app.register_blueprint(moderation_api, url_prefix='/api')
    logger.info("Registered moderation_api")

    # Register Cache Proxy V2 endpoints (Non-Custodial — no UserID required)
    app.register_blueprint(cache_proxy_bp)
    logger.info("Registered cache_proxy_v2 (public, non-custodial endpoints)")

    # Register Cache Proxy V3 Enhanced endpoints
    app.register_blueprint(cache_proxy_v3_bp)
    logger.info("Registered cache_proxy_v3 (enhanced: explorer, balance, rpc, broadcast, token-metadata)")
    
    # Register blockchain API endpoints (commented to avoid conflict with send_bp)
    # init_api_routes(app)
    # logger.info("Registered blockchain API endpoints")
    
    # Authentication middleware removed - using UserID-based authentication instead
    logger.info("Using UserID-based authentication instead of session-based")
    
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

# فقط یک worker گیکورن باید schedulerها را اجرا کند؛ وگرنه چندین نخ روی همان DB pool می‌نشیند و API گیر می‌کند.
_background_job_lock_fp = None


def _this_worker_runs_background_jobs() -> bool:
    global _background_job_lock_fp
    if os.getenv("ENABLE_BACKGROUND_JOBS", "true").lower() != "true":
        logger.info("Background jobs disabled by ENABLE_BACKGROUND_JOBS")
        return False
    try:
        import fcntl

        lock_path = os.getenv(
            "BACKGROUND_JOB_LOCK_PATH", "/tmp/coinceeper_background_jobs.lock"
        )
        fp = open(lock_path, "a+", encoding="utf-8")
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _background_job_lock_fp = fp
        logger.info("Background job lock acquired in this Gunicorn worker")
        return True
    except BlockingIOError:
        logger.info(
            "Background jobs skipped in this worker (lock held by another process)"
        )
        return False
    except Exception as e:
        logger.warning("Could not acquire background job lock, skipping jobs: %s", e)
        return False


run_background_jobs = _this_worker_runs_background_jobs()

# Check price scheduler status
if run_background_jobs:
    try:
        # Import the price scheduler
        from Currencies.price_scheduler import run_scheduler
        
        # Create a thread for the price scheduler if it's not already running
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
else:
    app.logger.info("Background jobs are not running in this worker")

# اضافه کردن شبیه‌ساز قیمت NCC با الگوریتم جدید
if run_background_jobs:
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
            app.logger.info("Starting NCC price simulator with natural volatility algorithm...")
            app.logger.info("🚀 NCC: $0.22 → $0.80 در 9 ماه با نوسانات 20-30%")
            ncc_simulator_thread = threading.Thread(
                target=ncc_price_simulator, daemon=True, name="NCCPriceSimulator"
            )
            ncc_simulator_thread.start()
            app.logger.info("NCC price simulator started successfully")

    except Exception as ncc_error:
        app.logger.error(f"Error starting NCC price simulator: {str(ncc_error)}", exc_info=True)
        # نمایش جزئیات خطا برای عیب‌یابی
        app.logger.error(f"NCC price simulator error details: {traceback.format_exc()}")
        # در صورت خطا برنامه ادامه پیدا می‌کند

# اضافه کردن Historical Data Scheduler
if run_background_jobs:
    try:
        # بررسی اینکه Historical Data Scheduler از قبل در حال اجرا نباشد
        historical_scheduler_thread = None
        
        for thread in threading.enumerate():
            if thread.name == "HistoricalDataScheduler":
                historical_scheduler_thread = thread
                app.logger.info(f"Historical data scheduler is already running in thread: {thread.name}")
                break
        
        if not historical_scheduler_thread:
            from Currencies.historical_scheduler import start_historical_scheduler
            app.logger.info("Starting historical data scheduler...")
            scheduler = start_historical_scheduler()
            app.logger.info("📊 Historical data will be updated every 24 hours automatically")
            app.logger.info("Historical data scheduler started successfully")
        
    except Exception as historical_error:
        app.logger.error(f"Error starting historical data scheduler: {str(historical_error)}", exc_info=True)
        # در صورت خطا برنامه ادامه پیدا می‌کند

# Notification Scheduler (gas alerts, portfolio summaries)
if run_background_jobs:
    try:
        from services.notifications.scheduler import start_scheduler
        app.logger.info("Starting notification scheduler (gas=5min, portfolio=1hr)...")
        notif_threads = start_scheduler()
        app.logger.info(f"Notification scheduler started with {len(notif_threads)} background workers")
    except Exception as notif_error:
        app.logger.error(f"Error starting notification scheduler: {str(notif_error)}", exc_info=True)

# Block Chain Scanners (ONLY in the background-job worker, NOT in all 4 Gunicorn workers)
# This prevents 4 x 10 = 40 scanner threads from saturating Gunicorn workers.
if run_background_jobs:
    try:
        from services.cache_proxy.block_scanner import start_all_scanners
        start_all_scanners()
        app.logger.info("Blockchain scanners started in background-job worker")
    except Exception as scanner_error:
        app.logger.error(f"Error starting blockchain scanners: {str(scanner_error)}", exc_info=True)

@app.route('/')
def index():
    """Serve frontend index.html"""
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/tools', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/tools/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def phpmyadmin_proxy(subpath=''):
    """Reverse proxy to phpMyAdmin on aaPanel port"""
    try:
        target_url = f"https://127.0.0.1:16914/dbc"
        if subpath:
            target_url += f"/{subpath}"
        if request.query_string:
            target_url += f"?{request.query_string.decode()}"
        
        headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'connection']}
        
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            verify=False,
            timeout=30
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                           if name.lower() not in excluded_headers]
        
        response_headers.append(('X-Proxy-Status', 'Working'))
        response_headers.append(('Cache-Control', 'no-cache, no-store, must-revalidate'))
        
        return Response(resp.content, resp.status_code, response_headers)
    except Exception as e:
        logger.error(f"phpMyAdmin proxy error: {str(e)}")
        return jsonify({"error": str(e), "message": "phpMyAdmin proxy failed", "traceback": traceback.format_exc()}), 500

@app.route('/api-docs')
@app.route('/api-docs/')
def api_docs_index():
    """Serve API documentation index page"""
    api_docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api-docs')
    return send_from_directory(api_docs_dir, 'index.html')

@app.route('/api-docs/<path:filename>')
def api_docs_files(filename):
    """Serve API documentation files"""
    api_docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api-docs')
    try:
        return send_from_directory(api_docs_dir, filename)
    except:
        return send_from_directory(api_docs_dir, 'index.html')

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Serve uploaded files (ad images, etc.)"""
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    try:
        return send_from_directory(uploads_dir, filename)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "فایل یافت نشد"}), 404

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    if path.startswith('api/') or path.startswith('tools') or path.startswith('api-docs') or path.startswith('uploads/') or path in ['balance', 'update-balance', 'test-api', 'generate-wallet', 'test-db', 'debug-api', 'prices', 'update-prices', 'historical-prices', 'generate-wallet-v1', 'import_wallet', 'validate_mnemonic', 'all-currencies', 'chart-data', 'chart-live-update', 'Recive', 'record-deposit', 'gasfee', 'transactions', 'notifications', 'estimate-fee', 'supported-chains', 'health']:
        from werkzeug.exceptions import NotFound
        raise NotFound()
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    try:
        return send_from_directory(frontend_dir, path)
    except:
        return send_from_directory(frontend_dir, 'index.html')

@app.route("/api/generate-wallet", methods=["POST"])
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def generate_wallet():
    """
    Generate a new wallet synchronously
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
      201:
        description: Wallet generated successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WalletGenerationSyncResponse'
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
    try:
        # Only accept JSON payloads for Flutter compatibility.
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raw_body = request.get_data(cache=False, as_text=True) or ""
            if raw_body.strip():
                try:
                    payload = json.loads(raw_body)
                except Exception:
                    payload = None

        wallet_name = payload.get('WalletName') if isinstance(payload, dict) else None
        if not wallet_name or not isinstance(wallet_name, str):
            return jsonify({
                'success': False,
                'UserID': None,
                'WalletID': None,
                'Mnemonic': None,
                'message': 'WalletName is required and must be a string'
            }), 400
        
        # Get user IP and device info
        user_ip = request.remote_addr
        user_device = request.headers.get('User-Agent', 'Unknown Device')
        logger.info(f"Generate wallet request from IP: {user_ip}, Device: {user_device}")
        
        session = SessionLocal()
        try:
            # Use service to create wallet
            wallet_service = WalletService(session)
            with session.begin():
                user_id, wallet_id, mnemonic, addresses = wallet_service.create_wallet(wallet_name, 5, user_ip, user_device)

            # Log success
            logger.info(f"Wallet generated for user {user_id} with wallet {wallet_id}")

            return jsonify({
                'success': True,
                'UserID': user_id,
                'WalletID': wallet_id,
                'Mnemonic': mnemonic,
                'message': 'Wallet generated successfully'
            }), 201
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error in generate_wallet: {str(e)}")
        return jsonify({
            'success': False,
            'UserID': None,
            'WalletID': None,
            'Mnemonic': None,
            'message': str(e)
        }), 400

@app.route('/api/test-db', methods=['GET'])
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

@app.route('/api/ping', methods=['GET'])
def ping():
    """Ultra-lightweight connectivity check for Flutter EnhancedNetworkManager.
    Returns immediately without DB query to avoid timeout."""
    return jsonify({"status": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route('/api/app-health', methods=['GET'])
def app_health():
    """Application health check"""
    try:
        # Check database connection first
        db_status = "ok"
        try:
            session = SessionLocal()
            try:
                session.execute(text("SELECT 1")).scalar()
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

@app.route('/api/historical-scheduler-status', methods=['GET'])
def historical_scheduler_status():
    """Get historical data scheduler status"""
    try:
        from Currencies.historical_scheduler import get_historical_scheduler
        
        scheduler = get_historical_scheduler()
        
        # Check if thread is running
        is_running = scheduler.is_running()
        
        # Get thread info
        thread_info = None
        for thread in threading.enumerate():
            if thread.name == "HistoricalDataScheduler":
                thread_info = {
                    'name': thread.name,
                    'alive': thread.is_alive(),
                    'daemon': thread.daemon
                }
                break
        
        return jsonify({
            'success': True,
            'scheduler_running': is_running,
            'thread_info': thread_info,
            'config': {
                'update_interval_hours': scheduler.update_interval_hours,
                'max_currencies_per_batch': scheduler.max_currencies_per_batch,
                'days_to_fetch': scheduler.days_to_fetch
            },
            'message': 'Historical scheduler is running' if is_running else 'Historical scheduler is stopped'
        })
        
    except Exception as e:
        logger.error(f"Error checking historical scheduler status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error checking scheduler status'
        }), 500

@app.route('/api/historical-scheduler-control', methods=['POST'])
def historical_scheduler_control():
    """Control historical data scheduler (start/stop/restart)"""
    try:
        data = request.get_json() or {}
        action = data.get('action', '').lower()
        
        if action not in ['start', 'stop', 'restart']:
            return jsonify({
                'success': False,
                'error': 'Invalid action. Use: start, stop, or restart'
            }), 400
        
        from Currencies.historical_scheduler import get_historical_scheduler
        scheduler = get_historical_scheduler()
        
        if action == 'start':
            if scheduler.is_running():
                return jsonify({
                    'success': False,
                    'message': 'Historical scheduler is already running'
                }), 400
            scheduler.start()
            message = 'Historical scheduler started'
            
        elif action == 'stop':
            if not scheduler.is_running():
                return jsonify({
                    'success': False,
                    'message': 'Historical scheduler is not running'
                }), 400
            scheduler.stop()
            message = 'Historical scheduler stopped'
            
        elif action == 'restart':
            if scheduler.is_running():
                scheduler.stop()
                time.sleep(2)
            scheduler.start()
            message = 'Historical scheduler restarted'
        
        return jsonify({
            'success': True,
            'action': action,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error controlling historical scheduler: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add this code after the line importing BlockchainServiceFactory
from utils.blockchain_service_factory import BlockchainServiceFactory
try:
    # Print detailed information about the blockchain registry
    app.logger.info("Initializing blockchain services registry...")
    app.logger.info(f"Registered blockchain classes: {list(BlockchainServiceFactory._service_classes.keys())}")
    app.logger.info(f"Name mappings available: {BlockchainServiceFactory._name_mapping}")
    
    # Test BSC specifically since it's causing issues
    bsc_mapping = BlockchainServiceFactory.normalize_name('bsc')
    app.logger.info(f"BSC name mapping test: 'bsc' -> '{bsc_mapping}'")
    
    binance_mapping = BlockchainServiceFactory.normalize_name('binance-smart-chain')
    app.logger.info(f"BSC name mapping test: 'binance-smart-chain' -> '{binance_mapping}'")
    
    # Initialize all blockchain services and handle any initialization errors
    service_status = BlockchainServiceFactory.initialize_all_services()
    for blockchain, status in service_status.items():
        if status != "ok":
            app.logger.warning(f"Blockchain service {blockchain} is disabled: {status}")
        else:
            app.logger.info(f"Blockchain service {blockchain} initialized successfully")
    
    # Check which services are now available
    app.logger.info(f"Available blockchain services: {BlockchainServiceFactory.get_supported_blockchains()}")
except Exception as e:
    app.logger.error(f"Error initializing blockchain services: {str(e)}")
    # Continue with application startup even if some services failed to initialize

if __name__ == '__main__':
    if socketio:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)
