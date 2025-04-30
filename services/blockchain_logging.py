import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from CC.utils.logging_config import get_log_directory, DEFAULT_LOG_LEVEL

# تنظیم فرمت لاگ برای سرویس بلاکچین
BLOCKCHAIN_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(blockchain)s] - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def get_blockchain_logger(name, blockchain=None):
    """
    ایجاد یک لاگر اختصاصی برای سرویس‌های بلاکچین
    
    Args:
        name: نام لاگر، معمولاً مسیر فایل (__file__)
        blockchain: نام بلاکچین (اختیاری)
        
    Returns:
        یک شیء لاگر اختصاصی برای سرویس‌های بلاکچین
    """
    # استخراج نام پایه فایل بدون مسیر کامل و پسوند
    base_name = os.path.basename(name)
    if base_name.endswith('.py'):
        base_name = base_name[:-3]
        
    # ایجاد لاگر
    logger = logging.getLogger(f"blockchain_{base_name}")
    
    # اگر از قبل تنظیم شده باشد، همان را برگردان
    if logger.handlers:
        return logger
        
    # تنظیم سطح لاگینگ
    logger.setLevel(DEFAULT_LOG_LEVEL)
    
    # ایجاد هندلر کنسول
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(DEFAULT_LOG_LEVEL)
    console_formatter = logging.Formatter(BLOCKCHAIN_LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ایجاد هندلر فایل
    log_dir = get_log_directory()
    blockchain_log_dir = os.path.join(log_dir, "blockchain")
    os.makedirs(blockchain_log_dir, exist_ok=True)
    
    log_file = os.path.join(blockchain_log_dir, f"{base_name}.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)  # 10MB
    file_handler.setLevel(DEFAULT_LOG_LEVEL)
    file_formatter = logging.Formatter(BLOCKCHAIN_LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # اضافه کردن یک فایل خطا برای لاگ‌های سطح ERROR و بالاتر
    error_log_file = os.path.join(blockchain_log_dir, f"{base_name}_error.log")
    error_handler = RotatingFileHandler(error_log_file, maxBytes=10*1024*1024, backupCount=5)
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(BLOCKCHAIN_LOG_FORMAT, DATE_FORMAT)
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)
    
    # اطمینان از عدم انتشار لاگ‌ها به لاگر والد
    logger.propagate = False
    
    # ایجاد یک فیلتر برای اضافه کردن اطلاعات بلاکچین به لاگ‌ها
    class BlockchainFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, 'blockchain'):
                record.blockchain = blockchain or 'unknown'
            return True
    
    # اضافه کردن فیلتر به تمام هندلرها
    blockchain_filter = BlockchainFilter()
    for handler in logger.handlers:
        handler.addFilter(blockchain_filter)
    
    # اضافه کردن یک پیام تشخیصی
    logger.debug(f"Blockchain logger initialized for {base_name}")
    
    return logger

def log_transaction_event(logger, event_type, tx_hash=None, blockchain=None, details=None):
    """
    ثبت رویدادهای مربوط به تراکنش‌های بلاکچین
    
    Args:
        logger: شیء لاگر
        event_type: نوع رویداد (prepared, signed, broadcast, confirmed, failed)
        tx_hash: هش تراکنش (اختیاری)
        blockchain: نام بلاکچین (اختیاری)
        details: جزئیات بیشتر به صورت دیکشنری (اختیاری)
    """
    # ساخت پیام لاگ
    log_msg = f"Transaction {event_type}"
    if tx_hash:
        log_msg += f" - Hash: {tx_hash}"
    
    # تنظیم اطلاعات اضافی برای لاگ
    extra = {'blockchain': blockchain or 'unknown'}
    
    # لاگ کردن با سطح مناسب
    if event_type == 'failed':
        if details:
            logger.error(f"{log_msg} - Details: {details}", extra=extra)
        else:
            logger.error(log_msg, extra=extra)
    elif event_type in ['prepared', 'signed']:
        if details:
            logger.info(f"{log_msg} - Details: {details}", extra=extra)
        else:
            logger.info(log_msg, extra=extra)
    elif event_type == 'broadcast':
        if details:
            logger.info(f"{log_msg} - Details: {details}", extra=extra)
        else:
            logger.info(log_msg, extra=extra)
    elif event_type == 'confirmed':
        if details:
            logger.info(f"{log_msg} - Details: {details}", extra=extra)
        else:
            logger.info(log_msg, extra=extra)
    else:
        if details:
            logger.debug(f"{log_msg} - Details: {details}", extra=extra)
        else:
            logger.debug(log_msg, extra=extra) 