"""
ماژول سرویس قیمت برای دریافت اطلاعات قیمت از CoinMarketCap
"""
import logging
import json
import requests
import time
from sqlalchemy.orm import Session
from database import engine
from database.prices import Price
from utils.logging_config import get_logger
from Currencies.api_key_manager import ApiKeyManager
from database.Currencies import Currencies

# تنظیم لاگر
logger = get_logger(__file__)
logger.info("Initializing currency price service module")

# ارزهای فیات پشتیبانی شده و نماد آنها
fiat_symbols = {
    "USD": "$", "CAD": "CA$", "AUD": "AU$", "GBP": "£", "EUR": "€",
    "KWD": "KD", "TRY": "₺", "SAR": "﷼", "CNY": "¥",
    "KRW": "₩", "JPY": "¥", "INR": "₹", "RUB": "₽", "IQD": "ع.د",
    "TND": "د.ت", "BHD": "ب.د"
}

def dynamic_decimal_format(price_value: float) -> str:
    """
    Format decimal values based on their magnitude
    
    Args:
        price_value (float): The price value to format
        
    Returns:
        str: Formatted price string with appropriate decimal places
    """
    if price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    else:
        return f"{price_value:,.8f}"

# Define CurrencyPriceService class
class CurrencyPriceService:
    """Service for retrieving cryptocurrency prices"""
    
    def __init__(self):
        logger.debug("Initializing CurrencyPriceService")
        self.api_key_manager = ApiKeyManager()
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        
    def get_api_key(self):
        """
        Get a valid API key for CoinMarketCap
        
        Returns:
            str: Valid API key
        """
        # Get key with at least 5 seconds interval between uses of the same key
        api_key = self.api_key_manager.get_api_key('coinmarketcap', min_interval_seconds=5)
        if not api_key:
            logger.error("No CoinMarketCap API key available")
            # Fallback to default key if no key is available from the manager
            api_key = "d1b7bd0f-e5d7-41e8-8f8a-accef3ac9d17"
            logger.warning(f"Using fallback API key: {api_key[:8]}...")
        return api_key
        
    def get_latest_prices(self, cmc_ids, fiat="USD"):
        """
        Get latest prices for specified CMC IDs in the given fiat currency
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of prices by CMC ID
        """
        try:
            logger.info(f"Fetching latest prices for {len(cmc_ids)} symbols in {fiat}")
            logger.debug(f"CMC IDs for price fetch: {cmc_ids}")
            
            # Join CMC IDs for API request
            id_str = ",".join(str(cid) for cid in cmc_ids)
            
            # Get API key from manager
            api_key = self.get_api_key()
            
            # Make API request - استفاده از پارامتر id برای CMC_ID
            url = f"{self.base_url}/cryptocurrency/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            params = {
                "id": id_str,  # استفاده از پارامتر id برای CMC_ID
                "convert": fiat
            }
            
            logger.debug(f"Making API request to {url} with API key: {api_key[:8]}...")
            logger.debug(f"Request params: {params}")
            response = requests.get(url, headers=headers, params=params)
            
            # Check for API rate limit errors
            if response.status_code == 429:
                logger.warning(f"Rate limit hit with API key {api_key[:8]}...")
                # Try with a different API key after a longer delay
                time.sleep(5)  # Wait 5 seconds before trying again
                api_key = self.get_api_key()
                headers["X-CMC_PRO_API_KEY"] = api_key
                logger.debug(f"Retrying with API key: {api_key[:8]}...")
                response = requests.get(url, headers=headers, params=params)
                
                # If still getting rate limit error, wait even longer
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit again with API key {api_key[:8]}...")
                    time.sleep(15)  # Wait 15 seconds before final attempt
                    api_key = self.get_api_key()
                    headers["X-CMC_PRO_API_KEY"] = api_key
                    logger.debug(f"Final retry with API key: {api_key[:8]}...")
                    response = requests.get(url, headers=headers, params=params)
            
            data = response.json()
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code}, Response: {data}")
                return {"status": "error", "message": f"API error: {response.status_code}"}
            
            # Extract prices - استخراج بر اساس CMC_ID ها
            result = {}
            if "data" in data:
                for cmc_id, info in data["data"].items():
                    if "quote" in info and fiat in info["quote"]:
                        result[cmc_id] = info["quote"][fiat]["price"]
            
            logger.info(f"Successfully fetched prices for {len(result)} symbols in {fiat}")
            return result
        except Exception as e:
            logger.error(f"Error fetching latest prices: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def get_24h_changes(self, cmc_ids, fiat="USD"):
        """
        Get 24-hour price changes for specified CMC IDs in the given fiat currency
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of 24h price changes by CMC ID
        """
        try:
            logger.info(f"Fetching 24h changes for {len(cmc_ids)} symbols in {fiat}")
            logger.debug(f"CMC IDs for changes fetch: {cmc_ids}")
            
            # Join CMC IDs for API request
            id_str = ",".join(str(cid) for cid in cmc_ids)
            
            # Get API key from manager
            api_key = self.get_api_key()
            
            # Make API request - استفاده از پارامتر id برای CMC_ID
            url = f"{self.base_url}/cryptocurrency/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            params = {
                "id": id_str,  # استفاده از پارامتر id برای CMC_ID
                "convert": fiat
            }
            
            logger.debug(f"Making API request to {url} with API key: {api_key[:8]}...")
            logger.debug(f"Request params: {params}")
            response = requests.get(url, headers=headers, params=params)
            
            # Check for API rate limit errors
            if response.status_code == 429:
                logger.warning(f"Rate limit hit with API key {api_key[:8]}...")
                # Try with a different API key after a longer delay
                time.sleep(5)  # Wait 5 seconds before trying again
                api_key = self.get_api_key()
                headers["X-CMC_PRO_API_KEY"] = api_key
                logger.debug(f"Retrying with API key: {api_key[:8]}...")
                response = requests.get(url, headers=headers, params=params)
                
                # If still getting rate limit error, wait even longer
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit again with API key {api_key[:8]}...")
                    time.sleep(15)  # Wait 15 seconds before final attempt
                    api_key = self.get_api_key()
                    headers["X-CMC_PRO_API_KEY"] = api_key
                    logger.debug(f"Final retry with API key: {api_key[:8]}...")
                    response = requests.get(url, headers=headers, params=params)
            
            data = response.json()
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code}, Response: {data}")
                return {"status": "error", "message": f"API error: {response.status_code}"}
            
            # Extract 24h changes - استخراج بر اساس CMC_ID ها
            result = {}
            if "data" in data:
                for cmc_id, info in data["data"].items():
                    if "quote" in info and fiat in info["quote"]:
                        result[cmc_id] = info["quote"][fiat]["percent_change_24h"]
            
            logger.info(f"Successfully fetched changes for {len(result)} symbols in {fiat}")
            return result
        except Exception as e:
            logger.error(f"Error fetching 24h changes: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
            
    def update_prices(self, symbols, fiat_currencies=None):
        """
        Updates prices for cryptocurrency symbols in the database
        
        Args:
            symbols (list): List of cryptocurrency IDs (CurrencyID در دیتابیس داخلی)
            fiat_currencies (list): List of fiat currency codes
            
        Returns:
            bool: Success status
        """
        if fiat_currencies is None:
            fiat_currencies = ["USD"]
            
        try:
            logger.info(f"Starting update_prices for {len(symbols)} currency IDs in {len(fiat_currencies)} currencies")
            logger.debug(f"Currency IDs to update: {symbols}")
            logger.debug(f"Fiat currencies to update: {fiat_currencies}")
            
            # قبل از هر چیز، باید CMC_ID را برای هر CurrencyID از دیتابیس بگیریم
            session = Session(bind=engine)
            try:
                # دریافت مپینگ CurrencyID به CMC_ID از دیتابیس
                currency_mapping = {}
                
                # اگر symbols خالی باشد، همه ارزها را بگیر
                if not symbols:
                    logger.info("No specific symbols provided, fetching all currencies from database")
                    currencies = session.query(Currencies).filter(Currencies.CMC_ID.isnot(None)).all()
                else:
                    currencies = session.query(Currencies).filter(Currencies.CurrencyID.in_(symbols), Currencies.CMC_ID.isnot(None)).all()
                
                # ساخت مپینگ بین CurrencyID و CMC_ID
                for currency in currencies:
                    if currency.CMC_ID:  # فقط ارزهایی که CMC_ID دارند
                        currency_mapping[currency.CurrencyID] = str(currency.CMC_ID)
                
                logger.info(f"Found {len(currency_mapping)} currencies with valid CMC_ID")
                logger.debug(f"Currency mapping: {currency_mapping}")
                
                # بررسی ارزهایی که CMC_ID ندارند
                missing_cmc_ids = [c_id for c_id in symbols if c_id not in currency_mapping]
                if missing_cmc_ids:
                    logger.warning(f"These currencies have no CMC_ID and will be skipped: {missing_cmc_ids}")
                    
                # اگر هیچ ارزی با CMC_ID پیدا نشد
                if not currency_mapping:
                    logger.error("No currencies with valid CMC_ID found in database")
                    return False
                    
            finally:
                session.close()
            
            success_count = 0
            fail_count = 0
            currency_ids = list(currency_mapping.keys())  # لیست CurrencyID ها
            
            for fiat in fiat_currencies:
                logger.info(f"Processing {fiat} currency updates")
                
                # تبدیل CurrencyID ها به CMC_ID ها برای فراخوانی API
                # اینجا باید از CMC_ID برای فراخوانی API استفاده کنیم نه CurrencyID
                cmc_ids = [currency_mapping[c_id] for c_id in currency_ids if c_id in currency_mapping]
                
                if not cmc_ids:
                    logger.warning(f"No valid CMC IDs found for currencies, skipping {fiat}")
                    continue
                    
                logger.debug(f"Using CMC IDs for API call: {cmc_ids}")
                
                # Get latest prices and changes using CMC_IDs
                # اطمینان از اینکه cmc_ids شناسه‌های مناسب برای API هستند
                prices = self.get_latest_prices(cmc_ids, fiat)
                changes = self.get_24h_changes(cmc_ids, fiat)
                
                # بررسی کامل داده‌های دریافتی
                logger.debug(f"Prices received from API: {prices}")
                logger.debug(f"Changes received from API: {changes}")
                
                # Check for errors
                if isinstance(prices, dict) and prices.get("status") == "error":
                    logger.error(f"Error fetching prices for {fiat}: {prices.get('message')}")
                    continue
                    
                if isinstance(changes, dict) and changes.get("status") == "error":
                    logger.error(f"Error fetching changes for {fiat}: {changes.get('message')}")
                    continue
                
                # تهیه یک مپینگ معکوس از CMC_ID به CurrencyID برای استفاده در به‌روزرسانی دیتابیس
                reverse_mapping = {v: k for k, v in currency_mapping.items()}
                
                # Update database - create a new session for each fiat currency
                session = Session(bind=engine)
                try:
                    logger.debug(f"Starting database updates for {len(currency_ids)} currencies in {fiat}")
                    fiat_success = 0
                    fiat_fail = 0
                    
                    # لاگ اتصال به دیتابیس
                    try:
                        logger.debug(f"Testing database connection...")
                        connection_test = session.execute("SELECT 1").first()
                        logger.debug(f"Database connection test result: {connection_test}")
                    except Exception as conn_err:
                        logger.error(f"Database connection error: {str(conn_err)}", exc_info=True)
                        
                    # اطلاعات جدول قیمت‌ها
                    try:
                        price_count = session.query(Price).count()
                        logger.debug(f"Current price records in database: {price_count}")
                    except Exception as table_err:
                        logger.error(f"Error checking price table: {str(table_err)}", exc_info=True)
                    
                    # Update database - اینجا از مپینگ معکوس استفاده می‌کنیم
                    for cmc_id, currency_id in reverse_mapping.items():
                        # بررسی اگر CMC_ID در نتایج API وجود دارد
                        price_value = prices.get(cmc_id)
                        change_value = changes.get(cmc_id)
                        
                        logger.debug(f"Processing CMC_ID {cmc_id} (CurrencyID {currency_id}) in {fiat}: price={price_value}, change={change_value}")
                        
                        if not isinstance(price_value, (int, float)):
                            logger.warning(f"Invalid price value for CMC_ID {cmc_id} (CurrencyID {currency_id}) in {fiat}: {price_value}")
                            fiat_fail += 1
                            continue
                        
                        try:
                            # استفاده از CurrencyID برای به‌روزرسانی دیتابیس
                            existing_price = session.query(Price).filter_by(
                                crypto_id=currency_id, 
                                currency=fiat
                            ).first()
                            
                            if existing_price:
                                # Update existing price
                                logger.debug(f"Updating existing record for CurrencyID {currency_id} (CMC_ID {cmc_id}) in {fiat}: {existing_price.price} → {price_value}")
                                existing_price.price = price_value
                                existing_price.change_24h = change_value
                                # Don't modify other fields if they already have values
                            else:
                                # Create new price entry with minimal required fields
                                logger.debug(f"Creating new price record for CurrencyID {currency_id} (CMC_ID {cmc_id}) in {fiat}: {price_value}")
                                new_price = Price(
                                    crypto_id=currency_id,  # استفاده از CurrencyID داخلی
                                    currency=fiat,
                                    price=price_value,
                                    change_24h=change_value
                                )
                                session.add(new_price)
                            
                            # Commit each record individually to avoid batch errors
                            logger.debug(f"Committing transaction for CurrencyID {currency_id} (CMC_ID {cmc_id}) in {fiat}")
                            session.commit()
                            fiat_success += 1
                            logger.debug(f"Successfully saved price for CurrencyID {currency_id} (CMC_ID {cmc_id}) in {fiat}")
                            
                        except Exception as record_error:
                            # If error occurs for one record, rollback that transaction and continue with others
                            session.rollback()
                            fiat_fail += 1
                            logger.error(f"Error updating price for CurrencyID {currency_id} (CMC_ID {cmc_id}) in {fiat}: {str(record_error)}", exc_info=True)
                            # بررسی دقیق‌تر خطای SQL 
                            if hasattr(record_error, 'orig') and record_error.orig:
                                logger.error(f"SQL error details: {str(record_error.orig)}")
                    
                    success_count += fiat_success
                    fail_count += fiat_fail
                    logger.info(f"Completed {fiat} updates: {fiat_success} successful, {fiat_fail} failed")
                
                except Exception as batch_error:
                    session.rollback()
                    logger.error(f"Error in batch update for {fiat}: {str(batch_error)}", exc_info=True)
                    # بررسی دقیق‌تر خطای SQL 
                    if hasattr(batch_error, 'orig') and batch_error.orig:
                        logger.error(f"SQL error details: {str(batch_error.orig)}")
                finally:
                    session.close()
                    logger.debug(f"Closed database session for {fiat}")
            
            logger.info(f"Price update complete. Total: {success_count} successful, {fail_count} failed")
            return True
            
        except Exception as e:
            logger.error(f"Error in update_prices: {str(e)}", exc_info=True)
            return False 