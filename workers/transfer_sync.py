import sys
import os
import logging
import time
from datetime import datetime, timedelta

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Transfers, Wallets
from services.balance_service import BalanceService
from utils.logging_config import setup_logging, get_logger
from sqlalchemy import text

# Configure logging
logger = get_logger(__name__)

def sync_transfers_with_holdings(hours_back=1):
    """
    همگام‌سازی تراکنش‌های جدید با موجودی کاربران
    این فرآیند تراکنش‌های اخیر را بررسی و موجودی متناظر را به‌روز می‌کند
    
    Args:
        hours_back (int): تعداد ساعت‌هایی که برای بررسی تراکنش‌ها به عقب برمی‌گردیم
    """
    logger.info(f"Starting transfers sync job, looking back {hours_back} hours")
    
    session = SessionLocal()
    try:
        # یافتن تراکنش‌های اخیر
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_transfers = session.query(Transfers).\
            filter(Transfers.CreatedAt >= cutoff_time).\
            order_by(Transfers.CreatedAt).all()
        
        logger.info(f"Found {len(recent_transfers)} transfers in the last {hours_back} hours")
        
        if not recent_transfers:
            logger.info("No recent transfers to process")
            return
            
        # ایجاد سرویس موجودی
        balance_service = BalanceService(session)
        
        success_count = 0
        error_count = 0
        already_processed_count = 0
        
        # اعمال هر تراکنش به موجودی کاربر
        for transfer in recent_transfers:
            try:
                wallet = session.query(Wallets).filter(Wallets.WalletID == transfer.WalletID).first()
                if not wallet:
                    logger.warning(f"Could not find wallet {transfer.WalletID} for transfer {transfer.TransferID}")
                    continue
                    
                user_id = wallet.UserID
                
                # بررسی اینکه آیا این تراکنش قبلاً پردازش شده است یا خیر
                check_processed_query = text("""
                    SELECT COUNT(*) FROM balance_update_log 
                    WHERE wallet_id = :wallet_id AND tx_id = :tx_id
                """)
                
                try:
                    processed_count = session.execute(check_processed_query, {
                        'wallet_id': transfer.WalletID,
                        'tx_id': transfer.TxHash
                    }).scalar()
                    
                    if processed_count > 0:
                        logger.info(f"Transaction {transfer.TxHash} already processed for wallet {transfer.WalletID}. Skipping.")
                        already_processed_count += 1
                        continue
                except Exception as e:
                    # اگر جدول balance_update_log وجود نداشته باشد، این خطا را نادیده می‌گیریم
                    logger.warning(f"Error checking if transaction was already processed: {str(e)}")
                    # در این حالت ممکن است پردازش دوباره انجام شود، اما چون خطای مهمی نیست ادامه می‌دهیم
                
                logger.info(f"Processing transfer {transfer.TransferID} for user {user_id}")
                
                # اعمال تراکنش به موجودی کاربر
                result = balance_service.apply_transfer_to_user_holding(transfer)
                
                if result:
                    success_count += 1
                    logger.info(f"Successfully applied transfer {transfer.TransferID} to user holdings")
                    
                else:
                    error_count += 1
                    logger.warning(f"Failed to apply transfer {transfer.TransferID} to user holdings")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing transfer {transfer.TransferID}: {str(e)}", exc_info=True)
                
        logger.info(f"Sync complete. Successfully processed {success_count} transfers, Failed: {error_count}, Already processed: {already_processed_count}")
        
    except Exception as e:
        logger.error(f"Error in sync_transfers_with_holdings: {str(e)}", exc_info=True)
    finally:
        session.close()

def run_sync_service():
    """
    راه‌اندازی سرویس همگام‌سازی تراکنش‌ها با فاصله زمانی مشخص
    """
    logger.info("Starting transfer sync service")
    
    # فاصله زمانی بررسی (به ثانیه) - هر 1 دقیقه
    sync_interval = 60
    
    # تعداد ساعت‌هایی که به عقب برمی‌گردیم
    hours_back = 2
    
    try:
        while True:
            try:
                logger.debug(f"Running transfer sync job at {datetime.now().isoformat()}")
                sync_transfers_with_holdings(hours_back)
            except Exception as e:
                logger.error(f"Error in sync job: {str(e)}", exc_info=True)
                
            logger.debug(f"Sleeping for {sync_interval} seconds until next sync")
            time.sleep(sync_interval)
            
    except KeyboardInterrupt:
        logger.info("Transfer sync service stopped by user")
        
if __name__ == "__main__":
    # تنظیم logging
    setup_logging()
    
    # اجرای سرویس به صورت مداوم
    run_sync_service() 