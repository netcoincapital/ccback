"""
Multi-Interval Historical Data Scheduler
Different update frequencies for different time ranges
"""
import time
import threading
from datetime import datetime, timedelta
from Currencies.historical_data_service import HistoricalDataService
from utils.logging_config import get_logger
import os

logger = get_logger(__file__)

class MultiIntervalScheduler:
    """Scheduler with multiple update intervals for different data types"""
    
    def __init__(self):
        self.service = HistoricalDataService()
        self.running = False
        self.threads = {}
        
        # Different intervals for different needs
        self.intervals = {
            'hourly': {
                'interval_minutes': int(os.getenv('HISTORICAL_HOURLY_INTERVAL', '60')),  # هر 1 ساعت
                'data_range_hours': 24,  # آخرین 24 ساعت
                'api_interval': '1h',
                'currencies_limit': 5  # محدود برای سرعت
            },
            'daily': {
                'interval_minutes': int(os.getenv('HISTORICAL_DAILY_INTERVAL', '360')),  # هر 6 ساعت
                'data_range_days': 7,  # آخرین هفته
                'api_interval': 'daily',
                'currencies_limit': 10
            },
            'weekly': {
                'interval_minutes': int(os.getenv('HISTORICAL_WEEKLY_INTERVAL', '1440')),  # هر 24 ساعت
                'data_range_days': 30,  # آخرین ماه
                'api_interval': 'daily',
                'currencies_limit': 20
            }
        }
        
        logger.info("Multi-interval scheduler initialized")
        for name, config in self.intervals.items():
            logger.info(f"  {name}: every {config['interval_minutes']} minutes")
    
    def get_priority_currencies(self, limit: int) -> list:
        """Get priority currencies for updates (most popular ones)"""
        try:
            from sqlalchemy.orm import Session
            from database import engine, Currencies
            
            session = Session(bind=engine)
            try:
                # Get currencies with CMC_ID, prioritize by common ones
                priority_symbols = ['BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE']
                
                # First get priority currencies
                priority_currencies = []
                for symbol in priority_symbols:
                    currency = session.query(Currencies).filter(
                        Currencies.Symbol == symbol,
                        Currencies.CMC_ID.isnot(None)
                    ).first()
                    if currency:
                        priority_currencies.append(currency.CurrencyID)
                        if len(priority_currencies) >= limit:
                            break
                
                # If we need more, get others
                if len(priority_currencies) < limit:
                    remaining = limit - len(priority_currencies)
                    other_currencies = session.query(Currencies).filter(
                        Currencies.CMC_ID.isnot(None),
                        ~Currencies.CurrencyID.in_(priority_currencies)
                    ).limit(remaining).all()
                    
                    priority_currencies.extend([c.CurrencyID for c in other_currencies])
                
                logger.debug(f"Selected {len(priority_currencies)} priority currencies")
                return priority_currencies
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error getting priority currencies: {str(e)}")
            return [1]  # Fallback to BTC only
    
    def update_interval_data(self, interval_name: str):
        """Update data for specific interval"""
        try:
            config = self.intervals[interval_name]
            logger.info(f"Starting {interval_name} historical data update")
            
            # Get currencies to update
            currency_ids = self.get_priority_currencies(config['currencies_limit'])
            
            # Calculate time range
            end_time = datetime.now()
            
            if 'data_range_hours' in config:
                start_time = end_time - timedelta(hours=config['data_range_hours'])
            else:
                start_time = end_time - timedelta(days=config['data_range_days'])
            
            time_start = start_time.isoformat() + "Z"
            time_end = end_time.isoformat() + "Z"
            
            logger.info(f"{interval_name} update: {len(currency_ids)} currencies from {time_start}")
            
            # Update data
            result = self.service.store_historical_data(
                currency_ids=currency_ids,
                time_start=time_start,
                time_end=time_end,
                interval=config['api_interval'],
                fiat_currencies=['USD']
            )
            
            if result.get('success'):
                records_added = result.get('records_added', 0)
                logger.info(f"{interval_name} update completed: {records_added} records added")
            else:
                logger.error(f"{interval_name} update failed: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"Error in {interval_name} update: {str(e)}", exc_info=True)
    
    def interval_loop(self, interval_name: str):
        """Loop for specific interval updates"""
        config = self.intervals[interval_name]
        interval_seconds = config['interval_minutes'] * 60
        
        logger.info(f"{interval_name} scheduler loop started (every {config['interval_minutes']} minutes)")
        
        while self.running:
            try:
                # Update data for this interval
                self.update_interval_data(interval_name)
                
                # Wait for next update
                logger.debug(f"Next {interval_name} update in {config['interval_minutes']} minutes")
                
                # Sleep in small intervals to allow clean shutdown
                sleep_interval = 60  # Check every minute
                for _ in range(0, interval_seconds, sleep_interval):
                    if not self.running:
                        break
                    time.sleep(sleep_interval)
                    
            except Exception as e:
                logger.error(f"Error in {interval_name} loop: {str(e)}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes before retry
        
        logger.info(f"{interval_name} scheduler loop stopped")
    
    def start(self):
        """Start all interval schedulers"""
        if self.running:
            logger.warning("Multi-interval scheduler is already running")
            return
            
        self.running = True
        
        # Start thread for each interval
        for interval_name in self.intervals.keys():
            thread = threading.Thread(
                target=self.interval_loop,
                args=(interval_name,),
                daemon=True,
                name=f"HistoricalScheduler_{interval_name}"
            )
            thread.start()
            self.threads[interval_name] = thread
            logger.info(f"Started {interval_name} scheduler thread")
        
        logger.info("Multi-interval historical scheduler started")
    
    def stop(self):
        """Stop all schedulers"""
        if not self.running:
            logger.warning("Multi-interval scheduler is not running")
            return
            
        self.running = False
        
        # Wait for all threads to stop
        for interval_name, thread in self.threads.items():
            if thread.is_alive():
                thread.join(timeout=10)
                logger.info(f"Stopped {interval_name} scheduler")
        
        self.threads.clear()
        logger.info("Multi-interval historical scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if any scheduler is running"""
        return self.running and any(thread.is_alive() for thread in self.threads.values())
    
    def get_status(self) -> dict:
        """Get status of all schedulers"""
        status = {
            'running': self.running,
            'intervals': {}
        }
        
        for interval_name, thread in self.threads.items():
            status['intervals'][interval_name] = {
                'thread_alive': thread.is_alive() if thread else False,
                'config': self.intervals[interval_name]
            }
        
        return status

# Global instance
_multi_scheduler = None

def get_multi_interval_scheduler():
    """Get global multi-interval scheduler"""
    global _multi_scheduler
    if _multi_scheduler is None:
        _multi_scheduler = MultiIntervalScheduler()
    return _multi_scheduler

def start_multi_interval_scheduler():
    """Start multi-interval scheduler"""
    scheduler = get_multi_interval_scheduler()
    scheduler.start()
    return scheduler
