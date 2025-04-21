import sys
import os
import logging
import time
import schedule
from datetime import datetime

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import setup_logging, get_logger
from workers.rebuild_user_holdings import rebuild_user_holdings

# Configure logging
logger = get_logger(__name__)

def scheduled_rebuild_job():
    """
    اجرای دوره‌ای فرآیند بازسازی دارایی‌ها برای همه کاربران
    فقط تراکنش‌های 7 روز اخیر بررسی می‌شوند
    """
    logger.info(f"Starting scheduled rebuild job at {datetime.now().isoformat()}")
    
    try:
        # بازسازی دارایی‌ها بر اساس تراکنش‌های 7 روز اخیر
        rebuild_user_holdings(days_back=7, force_rebuild=False)
        logger.info(f"Completed scheduled rebuild job at {datetime.now().isoformat()}")
    except Exception as e:
        logger.error(f"Error in scheduled rebuild job: {str(e)}", exc_info=True)

def run_scheduler():
    """
    راه‌اندازی زمان‌بندی برای اجرای دوره‌ای فرآیند بازسازی
    """
    # تنظیم زمان‌بندی برای اجرای فرآیند بازسازی هر روز در ساعت 3 صبح
    schedule.every().day.at("03:00").do(scheduled_rebuild_job)
    
    logger.info("Rebuild scheduler started")
    
    while True:
        try:
            # اجرای وظایف زمان‌بندی شده
            schedule.run_pending()
            time.sleep(60)  # بررسی هر یک دقیقه
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)
            time.sleep(300)  # در صورت خطا، 5 دقیقه صبر می‌کنیم و دوباره تلاش می‌کنیم

if __name__ == "__main__":
    # تنظیم logging
    setup_logging()
    
    # اجرای زمان‌بندی
    run_scheduler() 