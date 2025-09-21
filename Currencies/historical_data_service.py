"""
ماژول سرویس داده‌های تاریخی برای دریافت اطلاعات قیمت تاریخی از CoinMarketCap
"""
import logging
import json
import requests
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine
from database.prices import Price
from utils.logging_config import get_logger
from Currencies.api_key_manager import ApiKeyManager
from database.Currencies import Currencies

# تنظیم لاگر
logger = get_logger(__file__)
logger.info("Initializing historical data service module")

class HistoricalDataService:
    """Service for retrieving historical cryptocurrency prices"""
    
    def __init__(self):
        logger.debug("Initializing HistoricalDataService")
        self.api_key_manager = ApiKeyManager()
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        
    def get_api_key(self):
        """
        Get a valid API key for CoinMarketCap
        
        Returns:
            str: Valid API key
        """
        # Try to get API key from environment first
        api_key = os.getenv('CMC_API_KEY')
        if api_key:
            logger.debug(f"Using CMC_API_KEY from environment: {api_key[:8]}...")
            return api_key
            
        # Fallback to API key manager
        api_key = self.api_key_manager.get_api_key('coinmarketcap', min_interval_seconds=5)
        if not api_key:
            logger.error("No CoinMarketCap API key available")
            # Fallback to your provided key
            api_key = "0d216d8a-ddd0-4ada-bacb-da2d7467468a"
            logger.warning(f"Using fallback API key: {api_key[:8]}...")
        return api_key
    
    def get_historical_quotes(self, cmc_ids, time_start=None, time_end=None, interval="daily", fiat="USD", max_retries=3):
        """
        Get historical quotes for specified CMC IDs with improved error handling
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            time_start (str): Start time in ISO format (YYYY-MM-DDTHH:mm:ss.sssZ)
            time_end (str): End time in ISO format (YYYY-MM-DDTHH:mm:ss.sssZ)
            interval (str): Time interval (5m, 10m, 15m, 30m, 45m, 1h, 2h, 3h, 4h, 6h, 12h, 1d, 2d, 3d, 7d, 14d, 15d, 30d, 60d, 90d, 365d)
            fiat (str): Fiat currency code
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            dict: Dictionary of historical quotes by CMC ID
        """
        import time
        
        try:
            logger.info(f"Fetching historical quotes for {len(cmc_ids)} symbols from {time_start} to {time_end} with interval {interval}")
            logger.debug(f"CMC IDs for historical fetch: {cmc_ids}")
            
            # Set default time range if not provided (last 30 days)
            if not time_end:
                time_end = datetime.now().isoformat() + "Z"
            if not time_start:
                start_date = datetime.now() - timedelta(days=30)
                time_start = start_date.isoformat() + "Z"
            
            # محدود کردن تعداد CMC IDs به 100 (محدودیت API)
            if len(cmc_ids) > 100:
                logger.warning(f"Too many CMC IDs ({len(cmc_ids)}), limiting to first 100")
                cmc_ids = cmc_ids[:100]
            
            # Join CMC IDs for API request
            id_str = ",".join(str(cid) for cid in cmc_ids)
            
            # Make API request with retry logic
            for attempt in range(max_retries):
                try:
                    # Get API key (may rotate if previous failed)
                    api_key = self.get_api_key()
                    
                    url = f"{self.base_url}/cryptocurrency/quotes/historical"
                    headers = {
                        "X-CMC_PRO_API_KEY": api_key,
                        "Accept": "application/json"
                    }
                    params = {
                        "id": id_str,
                        "time_start": time_start,
                        "time_end": time_end,
                        "interval": interval,
                        "convert": fiat
                    }
                    
                    logger.debug(f"Making API request (attempt {attempt + 1}/{max_retries}) to {url} with API key: {api_key[:8]}...")
                    logger.debug(f"Request params: {params}")
                    
                    response = requests.get(url, headers=headers, params=params, timeout=60)
                    
                    # Handle different response codes
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for API-level errors
                        if data.get("status", {}).get("error_code") != 0:
                            error_msg = data.get("status", {}).get("error_message", "Unknown API error")
                            logger.error(f"API returned error: {error_msg}")
                            
                            # If it's a rate limit error, wait and retry
                            if "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                                if attempt < max_retries - 1:
                                    wait_time = (attempt + 1) * 30  # Progressive delay: 30, 60, 90 seconds
                                    logger.warning(f"Rate limit hit, waiting {wait_time} seconds before retry...")
                                    time.sleep(wait_time)
                                    continue
                            
                            return {"status": "error", "message": error_msg}
                        
                        # Extract historical quotes
                        result = {}
                        if "data" in data:
                            for cmc_id, quotes_data in data["data"].items():
                                if "quotes" in quotes_data:
                                    result[cmc_id] = quotes_data["quotes"]
                        
                        logger.info(f"Successfully fetched historical quotes for {len(result)} symbols")
                        return result
                    
                    elif response.status_code == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 60  # Progressive delay: 60, 120, 180 seconds
                            logger.warning(f"Rate limit (429), waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} attempts")
                            return {"status": "error", "message": f"Rate limit exceeded after {max_retries} attempts"}
                    
                    elif response.status_code == 401:  # Unauthorized
                        logger.error(f"API key unauthorized (401): {api_key[:8]}...")
                        # Try to get a different API key if available
                        if hasattr(self.api_key_manager, 'rotate_key'):
                            self.api_key_manager.rotate_key('coinmarketcap')
                        if attempt < max_retries - 1:
                            time.sleep(5)
                            continue
                        return {"status": "error", "message": "API key unauthorized"}
                    
                    elif response.status_code == 403:  # Forbidden
                        logger.error(f"API access forbidden (403): {response.text}")
                        return {"status": "error", "message": "API access forbidden"}
                    
                    else:
                        logger.error(f"API error {response.status_code}: {response.text}")
                        if attempt < max_retries - 1:
                            time.sleep(10)
                            continue
                        return {"status": "error", "message": f"API error: {response.status_code}"}
                
                except requests.exceptions.Timeout:
                    logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(15)
                        continue
                    return {"status": "error", "message": "Request timeout"}
                
                except requests.exceptions.ConnectionError:
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(20)
                        continue
                    return {"status": "error", "message": "Connection error"}
                
                except Exception as req_error:
                    logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {str(req_error)}")
                    if attempt < max_retries - 1:
                        time.sleep(10)
                        continue
                    return {"status": "error", "message": str(req_error)}
            
            return {"status": "error", "message": f"Failed after {max_retries} attempts"}
            
        except Exception as e:
            logger.error(f"Error fetching historical quotes: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def get_ohlcv_historical(self, cmc_ids, time_start=None, time_end=None, interval="daily", fiat="USD"):
        """
        Get OHLCV historical data for specified CMC IDs
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            time_start (str): Start time in ISO format
            time_end (str): End time in ISO format  
            interval (str): Time interval
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of OHLCV data by CMC ID
        """
        try:
            logger.info(f"Fetching OHLCV data for {len(cmc_ids)} symbols")
            
            # Set default time range if not provided (last 30 days)
            if not time_end:
                time_end = datetime.now().isoformat() + "Z"
            if not time_start:
                start_date = datetime.now() - timedelta(days=30)
                time_start = start_date.isoformat() + "Z"
            
            # Join CMC IDs for API request
            id_str = ",".join(str(cid) for cid in cmc_ids)
            
            # Get API key
            api_key = self.get_api_key()
            
            # Make API request
            url = f"{self.base_url}/cryptocurrency/ohlcv/historical"
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            params = {
                "id": id_str,
                "time_start": time_start,
                "time_end": time_end,
                "interval": interval,
                "convert": fiat
            }
            
            logger.debug(f"Making OHLCV API request to {url}")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"OHLCV API error: {response.status_code}, Response: {response.text}")
                return {"status": "error", "message": f"API error: {response.status_code}"}
            
            data = response.json()
            
            # Extract OHLCV data
            result = {}
            if "data" in data:
                for cmc_id, ohlcv_data in data["data"].items():
                    if "quotes" in ohlcv_data:
                        result[cmc_id] = ohlcv_data["quotes"]
            
            logger.info(f"Successfully fetched OHLCV data for {len(result)} symbols")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def store_historical_data(self, currency_ids, time_start=None, time_end=None, interval="daily", fiat_currencies=None, batch_size=50):
        """
        Fetch and store historical data for specified currencies with batch processing
        
        Args:
            currency_ids (list): List of internal currency IDs
            time_start (str): Start time in ISO format
            time_end (str): End time in ISO format
            interval (str): Time interval
            fiat_currencies (list): List of fiat currency codes
            batch_size (int): Number of currencies to process in each batch
            
        Returns:
            dict: Result status and details
        """
        import time
        
        if fiat_currencies is None:
            fiat_currencies = ["USD"]
        
        try:
            logger.info(f"Starting historical data storage for {len(currency_ids)} currencies in batches of {batch_size}")
            
            # Get CMC_ID mapping from database
            session = Session(bind=engine)
            try:
                currency_mapping = {}
                currencies = session.query(Currencies).filter(
                    Currencies.CurrencyID.in_(currency_ids), 
                    Currencies.CMC_ID.isnot(None)
                ).all()
                
                for currency in currencies:
                    if currency.CMC_ID:
                        currency_mapping[currency.CurrencyID] = str(currency.CMC_ID)
                
                if not currency_mapping:
                    return {"success": False, "message": "No currencies with valid CMC_ID found"}
                
                logger.info(f"Found {len(currency_mapping)} currencies with valid CMC_ID")
                
            finally:
                session.close()
            
            success_count = 0
            fail_count = 0
            total_api_calls = 0
            
            # تقسیم ارزها به batch ها
            currency_items = list(currency_mapping.items())
            currency_batches = [currency_items[i:i + batch_size] for i in range(0, len(currency_items), batch_size)]
            
            logger.info(f"Divided {len(currency_mapping)} currencies into {len(currency_batches)} batches")
            
            # Process each fiat currency
            for fiat in fiat_currencies:
                logger.info(f"Processing historical data for {fiat}")
                
                # Process each batch
                for batch_num, currency_batch in enumerate(currency_batches, 1):
                    logger.info(f"Processing batch {batch_num}/{len(currency_batches)} for {fiat} ({len(currency_batch)} currencies)")
                    
                    # Extract CMC IDs for this batch
                    batch_cmc_ids = [cmc_id for _, cmc_id in currency_batch]
                    batch_currency_mapping = {curr_id: cmc_id for curr_id, cmc_id in currency_batch}
                    
                    # Fetch historical quotes for this batch
                    quotes_data = self.get_historical_quotes(
                        batch_cmc_ids, time_start, time_end, interval, fiat
                    )
                    total_api_calls += 1
                    
                    if isinstance(quotes_data, dict) and quotes_data.get("status") == "error":
                        logger.error(f"Error fetching historical data for {fiat} batch {batch_num}: {quotes_data.get('message')}")
                        fail_count += len(currency_batch)
                        
                        # Wait before next batch on error
                        if batch_num < len(currency_batches):
                            logger.info("Waiting 60 seconds before next batch due to error...")
                            time.sleep(60)
                        continue
                    
                    # Store in database for this batch
                    session = Session(bind=engine)
                    try:
                        batch_success = 0
                        reverse_mapping = {cmc_id: curr_id for curr_id, cmc_id in batch_currency_mapping.items()}
                        
                        for cmc_id, quotes in quotes_data.items():
                            currency_id = reverse_mapping.get(cmc_id)
                            if not currency_id:
                                continue
                                
                            for quote in quotes:
                                if "quote" not in quote or fiat not in quote["quote"]:
                                    continue
                                    
                                quote_data = quote["quote"][fiat]
                                timestamp = datetime.fromisoformat(quote["timestamp"].replace("Z", "+00:00"))
                                
                                # Check if record already exists
                                try:
                                    existing = session.query(Price).filter_by(
                                        crypto_id=str(currency_id),  # Ensure string format
                                        currency=fiat,
                                        timestamp=timestamp,
                                        is_historical=True
                                    ).first()
                                    
                                    if not existing:
                                        # Create new historical record with validation
                                        price_value = quote_data.get("price", 0)
                                        if price_value and price_value > 0:
                                            historical_price = Price(
                                                crypto_id=str(currency_id),  # Ensure string format
                                                currency=fiat,
                                                price=price_value,
                                                market_cap=quote_data.get("market_cap"),
                                                volume_24h=quote_data.get("volume_24h"),
                                                change_24h=quote_data.get("percent_change_24h"),
                                                timestamp=timestamp,
                                                is_historical=True
                                            )
                                            session.add(historical_price)
                                            batch_success += 1
                                            logger.debug(f"Added historical record for {currency_id} at {timestamp}")
                                        else:
                                            logger.warning(f"Invalid price value {price_value} for {currency_id} at {timestamp}")
                                    else:
                                        logger.debug(f"Historical record already exists for {currency_id} at {timestamp}")
                                        
                                except Exception as record_error:
                                    logger.error(f"Error processing record for {currency_id} at {timestamp}: {str(record_error)}")
                                    continue
                        
                        # Commit batch
                        session.commit()
                        success_count += batch_success
                        logger.info(f"Successfully stored {batch_success} records for {fiat} batch {batch_num}")
                        
                    except Exception as db_error:
                        session.rollback()
                        logger.error(f"Database error for {fiat} batch {batch_num}: {str(db_error)}", exc_info=True)
                        fail_count += len(currency_batch)
                    finally:
                        session.close()
                    
                    # Wait between batches to avoid rate limiting
                    if batch_num < len(currency_batches):
                        wait_time = 30  # 30 seconds between batches
                        logger.info(f"Waiting {wait_time} seconds before next batch...")
                        time.sleep(wait_time)
            
            return {
                "success": True,
                "message": f"Historical data storage completed. {success_count} records added, {fail_count} failed, {total_api_calls} API calls made",
                "records_added": success_count,
                "records_failed": fail_count,
                "api_calls_made": total_api_calls,
                "batches_processed": len(currency_batches) * len(fiat_currencies)
            }
            
        except Exception as e:
            logger.error(f"Error in store_historical_data: {str(e)}", exc_info=True)
            return {"success": False, "message": str(e)}
    
    def get_stored_historical_data(self, currency_ids, time_start=None, time_end=None, fiat_currencies=None):
        """
        Retrieve stored historical data from database
        
        Args:
            currency_ids (list): List of internal currency IDs
            time_start (datetime): Start time
            time_end (datetime): End time
            fiat_currencies (list): List of fiat currency codes
            
        Returns:
            dict: Historical data organized by currency and fiat
        """
        if fiat_currencies is None:
            fiat_currencies = ["USD"]
        
        try:
            logger.info(f"Retrieving stored historical data for {len(currency_ids)} currencies")
            
            session = Session(bind=engine)
            try:
                query = session.query(Price).filter(
                    Price.crypto_id.in_(currency_ids),
                    Price.currency.in_(fiat_currencies),
                    Price.is_historical == True
                )
                
                if time_start:
                    query = query.filter(Price.timestamp >= time_start)
                if time_end:
                    query = query.filter(Price.timestamp <= time_end)
                
                query = query.order_by(Price.crypto_id, Price.currency, Price.timestamp)
                
                historical_records = query.all()
                
                # Organize data
                result = {}
                for record in historical_records:
                    if record.crypto_id not in result:
                        result[record.crypto_id] = {}
                    if record.currency not in result[record.crypto_id]:
                        result[record.crypto_id][record.currency] = []
                    
                    result[record.crypto_id][record.currency].append({
                        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                        "price": float(record.price),
                        "market_cap": float(record.market_cap) if record.market_cap else None,
                        "volume_24h": float(record.volume_24h) if record.volume_24h else None,
                        "change_24h": float(record.change_24h) if record.change_24h else None
                    })
                
                logger.info(f"Retrieved {len(historical_records)} historical records")
                return {"success": True, "data": result}
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error retrieving historical data: {str(e)}", exc_info=True)
            return {"success": False, "message": str(e)}
