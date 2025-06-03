# مسیر: Currencies/price_scheduler.py
from flask import Flask
import time
import threading
from sqlalchemy.orm import Session
from database import engine, Currencies
from Currencies.Prices import fiat_symbols
from Currencies.price_service import PriceDbService
from Currencies.schedule_config import SCHEDULE_CONFIG, BATCH_SIZE
from utils.logging_config import get_logger

logger = get_logger(__file__)

def run_scheduler():
    logger.info("==================== STARTING PRICE SCHEDULER ====================")
    logger.info("Initializing currency price scheduler")

    # دریافت لیست ارزها از دیتابیس - فقط ارزهایی که CMC_ID دارند
    logger.info("Fetching cryptocurrencies from database")
    session = Session(bind=engine)
    try:
        # فقط ارزهایی که CMC_ID دارند را انتخاب می‌کنیم
        all_cryptos = session.query(Currencies).filter(Currencies.CMC_ID.isnot(None)).order_by(Currencies.CurrencyID.asc()).all()
        
        # اگر ارزی پیدا نشد
        if not all_cryptos:
            logger.warning("No cryptocurrencies with valid CMC_ID found in the database.")
            return
            
        # استخراج CurrencyID ها - ما همچنان از CurrencyID استفاده می‌کنیم
        # اما سرویس قیمت خودش آنها را به CMC_ID تبدیل می‌کند
        coin_ids = [c.CurrencyID for c in all_cryptos]
        
        # لاگ کردن تعداد CMC_ID های معتبر برای اطمینان
        logger.info(f"Found {len(coin_ids)} cryptocurrencies with valid CMC_ID")
        if len(coin_ids) > 0:
            # نمایش چند نمونه از ارزها با CurrencyID و CMC_ID آنها برای دیباگ
            sample_coins = all_cryptos[:5]
            for coin in sample_coins:
                logger.debug(f"CurrencyID: {coin.CurrencyID}, CMC_ID: {coin.CMC_ID}")
            
    finally:
        session.close()
        logger.debug("Database session closed")

    # لیست ارزهای فیات
    fiat_list = list(fiat_symbols.keys())
    logger.info(f"Using {len(fiat_list)} fiat currencies: {fiat_list}")

    # تقسیم کریپتوها به پکیج‌های ۵۰تایی
    crypto_packages = [coin_ids[i:i + BATCH_SIZE] for i in range(0, len(coin_ids), BATCH_SIZE)]
    logger.info(f"Created {len(crypto_packages)} packages of {BATCH_SIZE} cryptocurrencies each")

    def schedule_worker(ids_subset, interval, pkg_idx):
        pkg_name = f"Package-{pkg_idx}"
        logger.debug(f"Creating worker for {pkg_name} with interval {interval // 60} minutes")
        
        def task():
            while True:
                try:
                    logger.info(f"[{pkg_name}] Running update for {len(ids_subset)} currencies (every {interval // 60} min)")
                    start_time = time.time()
                    
                    # استفاده از سرویس قیمت‌ها برای به‌روزرسانی
                    # currency_ids را می‌فرستیم، سرویس خودش آنها را به CMC_ID تبدیل می‌کند
                    result = PriceDbService.update_prices(currency_ids=ids_subset, fiat_currencies=fiat_list)
                    
                    elapsed = time.time() - start_time
                    if result["success"]:
                        logger.info(f"[{pkg_name}] Update completed successfully in {elapsed:.2f} seconds")
                    else:
                        logger.error(f"[{pkg_name}] Update failed after {elapsed:.2f} seconds: {result['message']}")
                        
                except Exception as e:
                    logger.error(f"[{pkg_name}] Error in update_prices task: {e}", exc_info=True)
                
                logger.debug(f"[{pkg_name}] Sleeping for {interval // 60} minutes")
                time.sleep(interval)

        thread = threading.Thread(target=task, daemon=True, name=pkg_name)
        thread.start()
        logger.debug(f"Started thread for {pkg_name}")
        return thread

    # ایجاد و راه‌اندازی worker ها بر اساس پیکربندی
    threads = []
    for config in SCHEDULE_CONFIG:
        interval = config["interval"]
        logger.info(f"Setting up schedule for interval {interval // 60} minutes")
        
        for pkg_index in config["packages"]:
            if pkg_index < len(crypto_packages):
                logger.debug(f"Creating worker for package {pkg_index} with {len(crypto_packages[pkg_index])} coins")
                thread = schedule_worker(crypto_packages[pkg_index], interval, pkg_index)
                threads.append(thread)
            else:
                logger.warning(f"Package index {pkg_index} out of range (max: {len(crypto_packages)-1})")
    
    logger.info(f"Started {len(threads)} worker threads")
    logger.info("Scheduler is running. Press Ctrl+C to stop.")

    try:
        while True:
            active_threads = [t for t in threads if t.is_alive()]
            logger.debug(f"Active threads: {len(active_threads)}/{len(threads)}")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        logger.info("==================== PRICE SCHEDULER STOPPED ====================")

if __name__ == "__main__":
    logger.info("Price scheduler script started")
    run_scheduler()