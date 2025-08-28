"""
Automatic Historical Data Scheduler
Fetches historical data automatically at scheduled intervals
"""
import time
import threading
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine, Currencies
from Currencies.historical_data_service import HistoricalDataService
from utils.logging_config import get_logger
import os

logger = get_logger(__file__)

class HistoricalDataScheduler:
    """Automatic scheduler for historical data updates"""
    
    def __init__(self):
        self.service = HistoricalDataService()
        self.running = False
        self.thread = None
        
        # Configuration
        self.update_interval_hours = int(os.getenv('HISTORICAL_UPDATE_INTERVAL_HOURS', '24'))  # روزانه
        self.max_currencies_per_batch = int(os.getenv('HISTORICAL_MAX_CURRENCIES', '10'))
        self.days_to_fetch = int(os.getenv('HISTORICAL_DAYS_TO_FETCH', '7'))  # هفته‌ای
        
        logger.info(f"Historical scheduler initialized: {self.update_interval_hours}h intervals, {self.days_to_fetch} days per fetch")
    
    def get_currencies_to_update(self) -> list:
        """Get list of currencies that need historical data updates"""
        try:
            session = Session(bind=engine)
            try:
                # Get currencies with CMC_ID that are active
                currencies = session.query(Currencies).filter(
                    Currencies.CMC_ID.isnot(None),
                    Currencies.CMC_ID != '',
                    Currencies.CMC_ID != '0'
                ).limit(self.max_currencies_per_batch).all()
                
                currency_ids = [c.CurrencyID for c in currencies]
                logger.info(f"Found {len(currency_ids)} currencies for historical update")
                return currency_ids
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error getting currencies for update: {str(e)}")
            return []
    
    def update_historical_data(self):
        """Update historical data for selected currencies"""
        try:
            logger.info("Starting automatic historical data update")
            
            # Get currencies to update
            currency_ids = self.get_currencies_to_update()
            
            if not currency_ids:
                logger.warning("No currencies found for historical update")
                return
            
            # Calculate time range (last week)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=self.days_to_fetch)
            
            time_start = start_time.isoformat() + "Z"
            time_end = end_time.isoformat() + "Z"
            
            logger.info(f"Updating historical data for {len(currency_ids)} currencies from {time_start} to {time_end}")
            
            # Update data
            result = self.service.store_historical_data(
                currency_ids=currency_ids,
                time_start=time_start,
                time_end=time_end,
                interval='daily',
                fiat_currencies=['USD']
            )
            
            if result.get('success'):
                records_added = result.get('records_added', 0)
                logger.info(f"Automatic update completed: {records_added} historical records added")
            else:
                logger.error(f"Automatic update failed: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"Error in automatic historical update: {str(e)}", exc_info=True)
    
    def scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Historical data scheduler started")
        
        while self.running:
            try:
                # Update historical data
                self.update_historical_data()
                
                # Wait for next update
                logger.info(f"Next historical update in {self.update_interval_hours} hours")
                
                # Sleep in small intervals to allow for clean shutdown
                total_sleep = self.update_interval_hours * 3600  # Convert to seconds
                sleep_interval = 60  # Check every minute for shutdown
                
                for _ in range(0, total_sleep, sleep_interval):
                    if not self.running:
                        break
                    time.sleep(sleep_interval)
                    
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)
                # Wait a bit before retrying
                time.sleep(300)  # 5 minutes
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Historical scheduler is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self.scheduler_loop, daemon=True, name="HistoricalDataScheduler")
        self.thread.start()
        logger.info("Historical data scheduler started in background")
    
    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            logger.warning("Historical scheduler is not running")
            return
            
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        logger.info("Historical data scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.running and self.thread and self.thread.is_alive()

# Global scheduler instance
_scheduler = None

def get_historical_scheduler():
    """Get the global historical scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = HistoricalDataScheduler()
    return _scheduler

def start_historical_scheduler():
    """Start the historical data scheduler"""
    scheduler = get_historical_scheduler()
    scheduler.start()
    return scheduler

def stop_historical_scheduler():
    """Stop the historical data scheduler"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
