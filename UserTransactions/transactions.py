import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine, select, and_, or_, desc, text
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from database.Transfers import Transfers
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from database import engine, SessionLocal  # استفاده از engine و session موجود
from utils.logging_config import get_logger
from datetime import datetime
import uuid
from sqlalchemy import inspect

# تنظیم لاگر
logger = get_logger(__file__)

# ایجاد blueprint
transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions', methods=['POST'])
def get_user_transactions_post():
    """
    [DEPRECATED] API برای دریافت تراکنش‌های کاربر با متد POST
    
    ⚠️ DEPRECATED: Transaction history should be read directly from block explorer.
    The HistoryIndexer on the client side already supports direct blockchain reads.
    This endpoint will be removed in a future version.
    
    فرمت‌های ورودی:
    1. {"UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d"} - تمام تراکنش‌های کاربر
    2. {"UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d", "TokenSymbol": ["BSC", "TRON"]} - تراکنش‌های مربوط به توکن‌های خاص
    """
    try:
        # چاپ اطلاعات درخواست برای دیباگ
        logger.info(f"Received transaction POST request: Headers: {dict(request.headers)}")
        logger.info(f"Received transaction POST request: Content-Type: {request.content_type}")
        logger.info(f"Received transaction POST request: Data: {request.data}")
        
        # دریافت داده‌های ورودی
        request_data = None
        
        try:
            if request.is_json:
                request_data = request.get_json()
                logger.info(f"Parsed JSON data: {request_data}")
            else:
                logger.error(f"Request is not JSON. Content-Type: {request.content_type}, Data: {request.data}")
                return jsonify({
                    "status": "error",
                    "message": "Request must be JSON",
                    "received_content_type": request.content_type
                }), 400
        except Exception as json_error:
            logger.error(f"Error parsing JSON: {str(json_error)}")
            return jsonify({
                "status": "error",
                "message": f"Invalid JSON format: {str(json_error)}",
                "raw_data": request.data.decode('utf-8', errors='ignore') if hasattr(request.data, 'decode') else str(request.data)
            }), 400
        
        # بررسی وجود UserID
        if not request_data or 'UserID' not in request_data:
            logger.error(f"UserID not found in request data: {request_data}")
            return jsonify({
                "status": "error",
                "message": "UserID is required",
                "received_data": request_data
            }), 400
            
        user_id = request_data.get('UserID')
        token_symbols = request_data.get('TokenSymbol', [])
        
        # لاگ اطلاعات دریافتی
        logger.info(f"Processing request with UserID: {user_id}, TokenSymbol: {token_symbols}")
        
        # پارامترهای صفحه‌بندی
        page = request.args.get('page', request_data.get('page', 1), type=int)
        per_page = request.args.get('per_page', request_data.get('per_page', 50), type=int)
        
        # تبدیل UUID به فرمت مناسب
        try:
            user_id_uuid = uuid.UUID(user_id)
            logger.info(f"Processing transactions for user: {user_id_uuid}")
        except ValueError as uuid_error:
            logger.error(f"Invalid UserID format: {user_id}, Error: {str(uuid_error)}")
            return jsonify({
                "status": "error",
                "message": f"Invalid UserID format: {user_id}",
                "details": str(uuid_error)
            }), 400
        
        # اطمینان از وجود module دیتابیس
        try:
            # تست اتصال دیتابیس
            session = SessionLocal()
            try:
                result = session.execute(text("SELECT 1")).scalar()
                logger.info(f"Database connection test successful: {result}")
                
                # بررسی وجود جداول مورد نیاز
                inspector = inspect(engine)
                
                # Use actual physical table names (lowercase) from ORM models.
                required_tables = [
                    Wallets.__tablename__,
                    Address.__tablename__,
                    Blockchains.__tablename__,
                    Transfers.__tablename__,
                    'users',  # imported in raw SQL checks below, keep explicit for clarity
                ]
                existing_tables = set(inspector.get_table_names())
                missing_tables = [table for table in required_tables if table not in existing_tables]
                
                if missing_tables:
                    logger.error(f"Missing required tables: {missing_tables}")
                    return jsonify({
                        "status": "error",
                        "message": "Database schema error: Missing required tables",
                        "missing_tables": missing_tables
                    }), 500
            except Exception as db_test_inner_error:
                logger.error(f"Database connection test inner error: {str(db_test_inner_error)}")
                return jsonify({
                    "status": "error", 
                    "message": f"Database connection test inner failed: {str(db_test_inner_error)}"
                }), 500
            finally:
                session.close()
        except Exception as db_test_error:
            logger.error(f"Database connection test failed: {str(db_test_error)}")
            return jsonify({
                "status": "error",
                "message": f"Database connection failed: {str(db_test_error)}"
            }), 500
        
        # دریافت تراکنش‌ها از دیتابیس
        try:
            transactions = get_user_transactions_from_db(user_id_uuid, token_symbols, page, per_page)
            logger.info(f"Successfully retrieved {len(transactions) if transactions else 0} transactions")
            
            # بررسی کنید که آیا تراکنشی یافت شده است یا خیر
            if not transactions:
                return jsonify({
                    "status": "success",
                    "message": "No transactions found for this user",
                    "count": 0,
                    "page": page,
                    "per_page": per_page,
                    "transactions": []
                }), 200
        except Exception as db_error:
            logger.error(f"Error retrieving transactions from database: {str(db_error)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Failed to retrieve transactions: {str(db_error)}",
                "error_type": type(db_error).__name__
            }), 500
        
        # تبدیل تراکنش‌ها به فرمت مناسب
        try:
            formatted_transactions = format_transactions(transactions)
            logger.info(f"Successfully formatted {len(formatted_transactions)} transactions")
        except Exception as format_error:
            logger.error(f"Error formatting transactions: {str(format_error)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Failed to format transactions: {str(format_error)}",
                "error_type": type(format_error).__name__
            }), 500
        
        # برگرداندن پاسخ
        return jsonify({
            "status": "success",
            "count": len(formatted_transactions),
            "page": page,
            "per_page": per_page,
            "transactions": formatted_transactions,
            "deprecation_notice": (
                "This endpoint is deprecated. "
                "Transaction history should be read from block explorer directly."
            )
        }), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in transaction request processing: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}",
            "error_type": type(e).__name__
        }), 500

# اضافه کردن مسیر GET
@transactions_bp.route('/transactions', methods=['GET'])
def get_user_transactions_get():
    """
    API برای دریافت تراکنش‌های کاربر با متد GET
    
    پارامترهای مورد قبول:
    - user_id: شناسه کاربر (الزامی)
    - token_symbols: لیست توکن‌ها (اختیاری)
    - page: شماره صفحه (پیش‌فرض 1)
    - per_page: تعداد نتایج در هر صفحه (پیش‌فرض 50)
    """
    try:
        logger.info(f"Received transaction GET request: {request.args}")
        
        # دریافت پارامترها از درخواست GET
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                "status": "error",
                "message": "user_id is required"
            }), 400
            
        # دریافت سایر پارامترها
        token_symbols_str = request.args.get('token_symbols', '')
        token_symbols = token_symbols_str.split(',') if token_symbols_str else []
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # تبدیل UUID به فرمت مناسب
        try:
            user_id_uuid = uuid.UUID(user_id)
            logger.info(f"Processing transactions for user: {user_id_uuid}")
        except ValueError:
            logger.error(f"Invalid user_id format: {user_id}")
            return jsonify({
                "status": "error",
                "message": "Invalid user_id format"
            }), 400
        
        # دریافت تراکنش‌ها از دیتابیس
        transactions = get_user_transactions_from_db(user_id_uuid, token_symbols, page, per_page)
        
        # تبدیل تراکنش‌ها به فرمت مناسب
        formatted_transactions = format_transactions(transactions)
        
        return jsonify({
            "status": "success",
            "count": len(formatted_transactions),
            "page": page,
            "per_page": per_page,
            "transactions": formatted_transactions
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing transaction request: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "An error occurred while processing your request"
        }), 500

# ایجاد یک endpoint تست ساده برای بررسی وضعیت API
@transactions_bp.route('/transactions/status', methods=['GET'])
def get_transactions_status():
    """
    API برای بررسی وضعیت سرویس تراکنش‌ها
    """
    try:
        return jsonify({
            "status": "success",
            "message": "Transactions API is working"
        }), 200
    except Exception as e:
        logger.error(f"Error in status endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "An error occurred"
        }), 500

@transactions_bp.route('/transactions/debug', methods=['POST'])
def debug_transactions():
    """
    یک API برای دیباگ تراکنش‌ها و بررسی تنظیمات دیتابیس
    """
    try:
        # بررسی تنظیمات دیتابیس
        inspector = inspect(engine)
        
        # دریافت لیست تمامی جداول موجود در دیتابیس
        tables = inspector.get_table_names()
        logger.info(f"Available tables in database: {tables}")
        
        # بررسی ساختار جدول transfers
        if 'transfers' in tables:
            columns = inspector.get_columns('transfers')
            column_names = [col['name'] for col in columns]
            logger.info(f"Columns in transfers table: {column_names}")
        else:
            logger.error("Table 'transfers' not found in database!")
            
        # بررسی وجود کاربر مورد نظر
        user_id = request.json.get('UserID', None)
        if user_id:
            session = SessionLocal()
            try:
                # بررسی وجود کاربر با استفاده از کوئری SQL خام
                user_query = session.execute(text(f"SELECT UserID FROM users WHERE UserID = '{user_id}'")).fetchone()
                logger.info(f"User query result: {user_query}")
                
                # بررسی تعداد کیف پول‌ها
                wallet_query = session.execute(text(f"SELECT COUNT(*) FROM wallets WHERE UserID = '{user_id}'")).scalar()
                logger.info(f"Number of wallets for user {user_id}: {wallet_query}")
                
                # بررسی تعداد آدرس‌ها
                address_count = session.execute(text(f"""
                    SELECT COUNT(*) FROM address a
                    JOIN wallets w ON a.WalletID = w.WalletID
                    WHERE w.UserID = '{user_id}'
                """)).scalar()
                logger.info(f"Number of addresses for user {user_id}: {address_count}")
                
                # بررسی تعداد تراکنش‌ها
                tx_count = session.execute(text(f"""
                    SELECT COUNT(*) FROM transfers t
                    JOIN wallets w ON t.WalletID = w.WalletID
                    WHERE w.UserID = '{user_id}'
                """)).scalar()
                logger.info(f"Number of transactions for user {user_id}: {tx_count}")
                
                # نمونه کوئری برای یافتن تراکنش‌ها با متد دیگر
                sample_query = f"""
                    SELECT t.TransferID, t.TxHash, t.Amount, t.TokenSymbol, t.Direction
                    FROM transfers t
                    JOIN wallets w ON t.WalletID = w.WalletID
                    WHERE w.UserID = '{user_id}'
                    LIMIT 5
                """
                sample_txs = session.execute(text(sample_query)).fetchall()
                logger.info(f"Sample transactions: {sample_txs}")
                
            except Exception as e:
                logger.error(f"Error in database queries: {str(e)}", exc_info=True)
                return jsonify({
                    "status": "error",
                    "message": f"Database query error: {str(e)}",
                    "error_type": type(e).__name__
                }), 500
            finally:
                session.close()
        
        # برگرداندن اطلاعات دیباگ
        return jsonify({
            "status": "success",
            "database_info": {
                "tables": tables,
                "transfers_available": 'transfers' in tables,
                "users_available": 'users' in tables,
                "wallets_available": 'wallets' in tables,
                "address_available": 'address' in tables,
                "blockchains_available": 'blockchains' in tables
            },
            "user_info": {
                "user_id": user_id,
                "user_found": bool(user_query) if user_id else None,
                "wallet_count": wallet_query if user_id else None,
                "address_count": address_count if user_id else None,
                "transaction_count": tx_count if user_id else None
            },
            "engine_info": {
                "url": str(engine.url).replace(str(engine.url.password or ''), '******') if hasattr(engine, 'url') else None,
                "dialect": engine.dialect.name if hasattr(engine, 'dialect') else None,
                "driver": engine.driver if hasattr(engine, 'driver') else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Debug endpoint error: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": str(e.__traceback__.tb_frame.f_code.co_filename) + ":" + str(e.__traceback__.tb_lineno) if e.__traceback__ else None
        }), 500

def get_user_transactions_from_db(user_id, token_symbols=None, page=1, per_page=50):
    """
    دریافت تراکنش‌های کاربر از دیتابیس
    
    Args:
        user_id (UUID): شناسه کاربر
        token_symbols (list, optional): لیست سمبل‌های توکن برای فیلتر
        page (int): شماره صفحه
        per_page (int): تعداد نتایج در هر صفحه
        
    Returns:
        list: لیست تراکنش‌ها
    """
    logger.info(f"Getting transactions for user {user_id} with token filters: {token_symbols}, page={page}, per_page={per_page}")
    
    try:
        # استفاده از session ارائه شده در ماژول database
        session = SessionLocal()
        
        try:
            # بررسی وجود کاربر با استفاده از کوئری SQL خام
            user_exists = session.execute(
                text(f"SELECT UserID FROM users WHERE UserID = '{user_id}'")
            ).fetchone()
            
            if not user_exists:
                logger.warning(f"User with ID {user_id} not found in database")
                return []
                
            # ساخت کوئری پایه برای دریافت تراکنش‌های کاربر
            query = select(
                Transfers.TransferID,
                Transfers.TxHash, 
                Transfers.BlockNumber,
                Transfers.Timestamp, 
                Transfers.FromAddress, 
                Transfers.ToAddress, 
                Transfers.Amount, 
                Transfers.TokenSymbol, 
                Transfers.TokenContract,
                Transfers.AssetType,
                Transfers.Fee, 
                Transfers.Direction, 
                Transfers.Status, 
                Transfers.IsSuccessful,
                Transfers.ExplorerUrl,
                Transfers.CreatedAt,
                Transfers.UpdatedAt,
                Transfers.Price,
                Blockchains.BlockchainName,
                Blockchains.Symbol.label('BlockchainSymbol'),
                Address.PublicAddress,
                Wallets.WalletID
            ).join(
                Wallets, Transfers.WalletID == Wallets.WalletID, isouter=True
            ).join(
                Address, Transfers.AddressID == Address.AddressID, isouter=True
            ).join(
                Blockchains, Transfers.BlockchainID == Blockchains.BlockchainID, isouter=True
            ).where(
                Wallets.UserID == str(user_id)
            )
            
            # اضافه کردن فیلتر توکن اگر مشخص شده باشد
            if token_symbols and len(token_symbols) > 0:
                logger.info(f"Filtering by token symbols: {token_symbols}")
                query = query.where(
                    or_(
                        Transfers.TokenSymbol.in_(token_symbols),
                        Blockchains.Symbol.in_(token_symbols)
                    )
                )
            
            # مرتب‌سازی براساس زمان (جدیدترین تراکنش‌ها اول)
            query = query.order_by(desc(Transfers.Timestamp))
            
            # پیاده‌سازی صفحه‌بندی
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)
            
            # اجرای کوئری
            result = session.execute(query).fetchall()
            logger.info(f"Found {len(result)} transactions for user {user_id} on page {page}")
            
            return result
        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            # نمایش کوئری SQL اصلی در صورت وجود خطا
            try:
                query_str = str(query.compile(compile_kwargs={"literal_binds": True}))
                logger.error(f"Failed SQL query: {query_str}")
            except:
                pass
            raise
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error fetching transactions from database: {str(e)}", exc_info=True)
        return []

def format_transactions(transactions):
    """
    تبدیل تراکنش‌ها به فرمت مناسب برای پاسخ API
    
    Args:
        transactions (list): لیست تراکنش‌ها از دیتابیس
        
    Returns:
        list: لیست تراکنش‌ها با فرمت مناسب
    """
    formatted_result = []
    
    if not transactions:
        logger.warning("No transactions to format")
        return []
    
    logger.info(f"Formatting {len(transactions)} transactions")
    
    for i, tx in enumerate(transactions):
        try:
            # لاگ کردن ساختار داده خام برای دیباگ اولین تراکنش
            if i == 0:
                logger.info(f"Transaction structure: {tx._mapping.keys()}")
            
            # تبدیل مقادیر Decimal به str برای سریالیزیشن JSON
            amount = str(tx.Amount) if tx.Amount is not None else "0"
            fee = str(tx.Fee) if tx.Fee is not None and tx.Fee != 0 else "0"
            price = str(tx.Price) if tx.Price is not None else "0"
            
            # تبدیل تاریخ‌ها به رشته ISO
            timestamp = tx.Timestamp.isoformat() if tx.Timestamp else None
            
            # فقط فیلدهای مورد نیاز را اضافه می‌کنیم
            formatted_tx = {
                "amount": amount,
                "assetType": tx.AssetType if tx.AssetType else None,
                "blockchainName": tx.BlockchainName if tx.BlockchainName else None,
                "timestamp": timestamp,
                "txHash": tx.TxHash if tx.TxHash else None,
                "from": tx.PublicAddress if tx.PublicAddress else None,
                "to": tx.ToAddress if tx.ToAddress else None,
                "tokenSymbol": tx.TokenSymbol if tx.TokenSymbol else None,
                "tokenContract": tx.TokenContract if tx.TokenContract else None,
                "explorerUrl": tx.ExplorerUrl if tx.ExplorerUrl else None,
                "direction": tx.Direction if tx.Direction else None,
                "fee": fee,
                "price": price,
            }
            
            formatted_result.append(formatted_tx)
        except Exception as e:
            # اگر خطا برای همه تراکنش‌ها تکرار شود، استثنا پرتاب کنید
            logger.error(f"Error formatting transaction {i}: {str(e)}", exc_info=True)
            
            # اگر error_count خیلی زیاد است، کل عملیات را متوقف کنید
            if i == 0:  # اگر حتی نتوانیم اولین تراکنش را فرمت کنیم، احتمالاً مشکل جدی وجود دارد
                error_detail = f"Sample transaction data: {dir(tx)}" if tx else "No transaction data"
                logger.error(f"Critical formatting error on first transaction. {error_detail}")
                raise Exception(f"Critical error formatting transactions: {str(e)}")
            
            # در غیر این صورت، این تراکنش را رد کنید و ادامه دهید
            continue
    
    return formatted_result 