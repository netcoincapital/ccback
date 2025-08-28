"""
Batch fetcher for large historical data requests
Optimized for long-term data collection (24 months+)
"""
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from Currencies.historical_data_service import HistoricalDataService
from utils.logging_config import get_logger

logger = get_logger(__file__)

class BatchHistoricalFetcher:
    """Optimized fetcher for large historical data requests"""
    
    def __init__(self):
        self.service = HistoricalDataService()
        self.max_days_per_request = 30  # Limit per API call
        self.delay_between_requests = 2  # Seconds between API calls
        
    def fetch_long_term_data(self, currency_ids: List[int], months: int, 
                           interval: str = "daily", fiat_currencies: List[str] = None) -> Dict:
        """
        Fetch historical data for multiple months in batches
        
        Args:
            currency_ids: List of currency IDs
            months: Number of months to fetch
            interval: Time interval (daily recommended for long periods)
            fiat_currencies: List of fiat currencies
            
        Returns:
            Dict with results and statistics
        """
        if fiat_currencies is None:
            fiat_currencies = ["USD"]
            
        try:
            logger.info(f"Starting long-term fetch for {months} months, {len(currency_ids)} currencies")
            
            # Calculate time range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            
            # Split into batches
            batches = []
            current_start = start_date
            
            while current_start < end_date:
                batch_end = min(current_start + timedelta(days=self.max_days_per_request), end_date)
                batches.append({
                    'start': current_start.isoformat() + "Z",
                    'end': batch_end.isoformat() + "Z"
                })
                current_start = batch_end + timedelta(days=1)
            
            logger.info(f"Split into {len(batches)} batches of ~{self.max_days_per_request} days each")
            
            total_success = 0
            total_failed = 0
            
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i+1}/{len(batches)}: {batch['start']} to {batch['end']}")
                
                # Process batch
                result = self.service.store_historical_data(
                    currency_ids=currency_ids,
                    time_start=batch['start'],
                    time_end=batch['end'],
                    interval=interval,
                    fiat_currencies=fiat_currencies
                )
                
                if result.get('success'):
                    batch_added = result.get('records_added', 0)
                    total_success += batch_added
                    logger.info(f"Batch {i+1} success: {batch_added} records added")
                else:
                    total_failed += 1
                    logger.error(f"Batch {i+1} failed: {result.get('message')}")
                
                # Delay between requests to respect API limits
                if i < len(batches) - 1:  # Don't delay after last batch
                    logger.debug(f"Waiting {self.delay_between_requests} seconds before next batch...")
                    time.sleep(self.delay_between_requests)
            
            return {
                'success': True,
                'total_records_added': total_success,
                'total_batches_failed': total_failed,
                'total_batches': len(batches),
                'months_processed': months,
                'message': f'Long-term fetch completed: {total_success} records added from {len(batches)} batches'
            }
            
        except Exception as e:
            logger.error(f"Error in long-term fetch: {str(e)}", exc_info=True)
            return {'success': False, 'message': str(e)}
    
    def fetch_all_available_data(self, currency_ids: List[int], 
                               fiat_currencies: List[str] = None) -> Dict:
        """
        Fetch all available historical data (limited by API plan)
        
        Args:
            currency_ids: List of currency IDs
            fiat_currencies: List of fiat currencies
            
        Returns:
            Dict with results
        """
        # For Hobbyist plan: 12 months maximum
        return self.fetch_long_term_data(
            currency_ids=currency_ids,
            months=12,  # Maximum for your plan
            interval="daily",
            fiat_currencies=fiat_currencies
        )
