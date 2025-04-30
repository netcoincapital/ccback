import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# تنظیم سطح لاگینگ اصلی
DEFAULT_LOG_LEVEL = logging.DEBUG  # تغییر از INFO به DEBUG برای ثبت همه پیام‌ها

# برای ذخیره لاگ‌ها در فایل
LOG_DIR = 'Logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# تنظیم فرمت لاگ
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# تابع setup_logging برای استفاده در اسکریپت‌های اجرایی
def setup_logging(level=DEFAULT_LOG_LEVEL):
    """
    تنظیم لاگینگ برای اسکریپت‌های اجرایی
    
    Args:
        level: سطح لاگینگ، پیش‌فرض DEFAULT_LOG_LEVEL
    """
    # تنظیم لاگر اصلی
    log_dir = get_log_directory()
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                os.path.join(log_dir, "script.log"),
                maxBytes=10*1024*1024,
                backupCount=5
            )
        ]
    )
    
    # تنظیم سطح لاگرهای کتابخانه‌های خارجی به WARNING
    for log_name, log_obj in logging.Logger.manager.loggerDict.items():
        if log_name != "root" and isinstance(log_obj, logging.Logger):
            log_obj.setLevel(logging.WARNING)
    
    logging.info("Logging setup complete")
    return logging.getLogger()

def get_log_directory():
    """
    Create and return the log directory path for the current date
    
    Returns:
        str: Path to the log directory for today
    """
    # Get the project root directory (where CC folder is located)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Create main Logs directory
    logs_dir = os.path.join(project_root, "Logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create date-specific directory
    today = datetime.now().strftime('%Y-%m-%d')
    today_dir = os.path.join(logs_dir, today)
    os.makedirs(today_dir, exist_ok=True)
    
    return today_dir

def setup_logger(name, level=logging.INFO):
    """
    Set up a logger with file and console handlers
    
    Args:
        name (str): Logger name (typically the module name without extension)
        level (int, optional): Logging level. Defaults to logging.INFO.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers = []
    
    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    log_dir = get_log_directory()
    log_file = os.path.join(log_dir, f"{name}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name):
    """
    ایجاد یک لاگر با تنظیمات پیشرفته
    
    Args:
        name: نام لاگر، معمولاً مسیر فایل (__file__)
        
    Returns:
        یک شیء لاگر نام‌گذاری شده
    """
    # استخراج نام پایه فایل بدون مسیر کامل و پسوند
    base_name = os.path.basename(name)
    if base_name.endswith('.py'):
        base_name = base_name[:-3]
        
    # ایجاد لاگر
    logger = logging.getLogger(base_name)
    
    # اگر از قبل تنظیم شده باشد، همان را برگردان
    if logger.handlers:
        return logger
        
    # تنظیم سطح لاگینگ
    logger.setLevel(DEFAULT_LOG_LEVEL)
    
    # ایجاد هندلر کنسول
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(DEFAULT_LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ایجاد هندلر فایل
    log_dir = get_log_directory()
    log_file = os.path.join(log_dir, f"{base_name}.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)  # 10MB
    file_handler.setLevel(DEFAULT_LOG_LEVEL)
    file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # اطمینان از عدم انتشار لاگ‌ها به لاگر والد
    logger.propagate = False
    
    # اضافه کردن یک پیام تشخیصی
    logger.debug(f"Logger initialized for {base_name} at level {logging.getLevelName(DEFAULT_LOG_LEVEL)}")
    
    return logger

# تنظیم لاگر اصلی برای بخش‌هایی که از لاگر اختصاصی استفاده نمی‌کنند
def setup_root_logger():
    """تنظیم لاگر اصلی برای استفاده عمومی"""
    root_logger = logging.getLogger()
    root_logger.setLevel(DEFAULT_LOG_LEVEL)
    
    # پاک کردن هندلرهای موجود
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # تنظیم لاگ کنسول
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(DEFAULT_LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # تنظیم لاگ فایل
    log_dir = get_log_directory()
    log_file = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)  # 10MB
    file_handler.setLevel(DEFAULT_LOG_LEVEL)
    file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    return root_logger

# تنظیم لاگر اصلی در هنگام ورود ماژول
setup_root_logger()

# تنظیم کلیه لاگرهای کتابخانه‌های خارجی به سطح WARNING
for log_name, log_obj in logging.Logger.manager.loggerDict.items():
    if log_name != "root" and isinstance(log_obj, logging.Logger):
        log_obj.setLevel(logging.WARNING) 