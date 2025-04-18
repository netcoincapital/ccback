import sys
import os
from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)

# اضافه کردن مسیر پروژه به sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    logger.debug(f"Added {BASE_DIR} to sys.path")

# ایمپورت تابع run_updater از فایل Prices.py (حساس به حروف)
logger.info("Importing run_updater from Currencies.Prices")
from Currencies.Prices import run_updater

def run_price_updater():
    """تابعی جهت اجرای به‌روزرسانی قیمت‌ها؛ برای ایمپورت در بخش‌های دیگر استفاده شود."""
    logger.info("Starting price updater execution")
    run_updater()
    logger.info("Price updater execution completed")

if __name__ == "__main__":
    logger.info("==================== PRICE UPDATER SCRIPT STARTED ====================")
    run_price_updater()
    logger.info("==================== PRICE UPDATER SCRIPT FINISHED ====================")
