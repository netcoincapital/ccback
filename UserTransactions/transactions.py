import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine, select, and_, or_, desc
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from database.Transfers import Transfers
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from database import engine, SessionLocal  # استفاده از engine و session موجود
from utils.logging_config import get_logger
from datetime import datetime
import uuid

# تنظیم لاگر
logger = get_logger(__file__)

# ایجاد blueprint
transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/api/transactions', methods=['POST'])
def get_user_transactions():
    """
    API برای دریافت تراکنش‌های کاربر
    
    فرمت‌های ورودی:
    1. {"UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d"} - تمام تراکنش‌های کاربر
    2. {"UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d", "TokenSymbol": ["BSC", "TRON"]} - تراکنش‌های مربوط به توکن‌های خاص
    """
    try:
        # دریافت داده‌های ورودی
        request_data = request.json
        logger.info(f"Received transaction request: {request_data}")
        
        # بررسی وجود UserID
        if 'UserID' not in request_data:
            return jsonify({
                "status": "error",
                "message": "UserID is required"
            }), 400
            
        user_id = request_data.get('UserID')
        token_symbols = request_data.get('TokenSymbol', [])
        
        # پارامترهای صفحه‌بندی
        page = request.args.get('page', request_data.get('page', 1), type=int)
        per_page = request.args.get('per_page', request_data.get('per_page', 50), type=int)
        
        # تبدیل UUID به فرمت مناسب
        try:
            user_id_uuid = uuid.UUID(user_id)
            logger.info(f"Processing transactions for user: {user_id_uuid}")
        except ValueError:
            logger.error(f"Invalid UserID format: {user_id}")
            return jsonify({
                "status": "error",
                "message": "Invalid UserID format"
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
                Blockchains.BlockchainName,
                Blockchains.Symbol.label('BlockchainSymbol'),
                Address.PublicAddress,
                Wallets.WalletID
            ).join(
                Wallets, Transfers.WalletID == Wallets.WalletID
            ).join(
                Address, Transfers.AddressID == Address.AddressID
            ).join(
                Blockchains, Transfers.BlockchainID == Blockchains.BlockchainID
            ).where(
                Wallets.UserID == user_id
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
    
    for tx in transactions:
        try:
            # تبدیل مقادیر Decimal به str برای سریالیزیشن JSON
            amount = str(tx.Amount) if tx.Amount is not None else "0"
            fee = str(tx.Fee) if tx.Fee is not None else "0"
            
            # تبدیل تاریخ‌ها به رشته ISO
            timestamp = tx.Timestamp.isoformat() if tx.Timestamp else None
            created_at = tx.CreatedAt.isoformat() if tx.CreatedAt else None
            updated_at = tx.UpdatedAt.isoformat() if tx.UpdatedAt else None
            
            formatted_tx = {
                "id": tx.TransferID,
                "txHash": tx.TxHash,
                "blockNumber": tx.BlockNumber,
                "timestamp": timestamp,
                "fromAddress": tx.FromAddress,
                "toAddress": tx.ToAddress,
                "amount": amount,
                "tokenSymbol": tx.TokenSymbol,
                "tokenContract": tx.TokenContract,
                "assetType": tx.AssetType,
                "fee": fee,
                "direction": tx.Direction,
                "status": tx.Status,
                "isSuccessful": tx.IsSuccessful,
                "explorerUrl": tx.ExplorerUrl,
                "blockchainName": tx.BlockchainName,
                "blockchainSymbol": tx.BlockchainSymbol,
                "publicAddress": tx.PublicAddress,
                "walletId": tx.WalletID,
                "createdAt": created_at,
                "updatedAt": updated_at
            }
            
            formatted_result.append(formatted_tx)
        except Exception as e:
            logger.error(f"Error formatting transaction: {str(e)}", exc_info=True)
            # ادامه دادن با تراکنش بعدی در صورت بروز خطا
            continue
    
    return formatted_result 