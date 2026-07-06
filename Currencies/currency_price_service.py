"""
ماژول سرویس قیمت برای دریافت اطلاعات قیمت از CoinMarketCap
"""
import logging
import json
import requests
import time
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine
from database.prices import Price
from utils.logging_config import get_logger
from Currencies.api_key_manager import ApiKeyManager
from database.Currencies import Currencies
from Currencies.historical_data_service import HistoricalDataService

# تنظیم لاگر
logger = get_logger(__file__)
logger.info("Initializing currency price service module")

# اگر جدول current_prices نباشد، به‌روزرسانی باید در جدول قدیمی prices نوشته شود.
_use_new_price_tables_cache = None  # type: ignore[var-annotated]

# MySQL named lock for legacy `prices` inserts when `id` has no AUTO_INCREMENT.
LEGACY_PRICES_BATCH_LOCK = "coinceeper_prices_batch"


def _use_new_price_tables() -> bool:
    global _use_new_price_tables_cache
    if _use_new_price_tables_cache is not None:
        return _use_new_price_tables_cache
    try:
        from sqlalchemy import inspect as sqla_inspect

        names = {t.lower() for t in sqla_inspect(engine).get_table_names()}
        _use_new_price_tables_cache = "current_prices" in names
        logger.info(
            "Price persistence mode: %s",
            "new_schema(current_prices)" if _use_new_price_tables_cache else "legacy(prices)",
        )
    except Exception as e:
        logger.warning("Could not inspect DB for price tables, defaulting to legacy: %s", e)
        _use_new_price_tables_cache = False
    return _use_new_price_tables_cache

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
    if price_value == 0:
        return "0.00000000"
    elif price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    elif price_value >= 0.00000001:
        return f"{price_value:,.8f}"
    else:
        # برای اعداد خیلی کوچک، از نمایش علمی جلوگیری کنیم
        return f"{price_value:.12f}".rstrip('0').rstrip('.')

# Define CurrencyPriceService class
class CurrencyPriceService:
    """Service for retrieving cryptocurrency prices"""
    
    def __init__(self):
        logger.debug("Initializing CurrencyPriceService")
        self.api_key_manager = ApiKeyManager()
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        self.historical_service = HistoricalDataService()
        
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
        
    def get_complete_market_data(self, cmc_ids, fiat="USD"):
        """
        Get complete market data including price, market cap, volume, and all changes for specified CMC IDs
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary with complete market data by CMC ID
        """
        try:
            logger.info(f"Fetching complete market data for {len(cmc_ids)} symbols in {fiat}")
            logger.debug(f"CMC IDs for market data fetch: {cmc_ids}")
            
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
            
            # Extract complete market data - استخراج تمام داده‌های بازار
            result = {}
            if "data" in data:
                for cmc_id, info in data["data"].items():
                    if "quote" in info and fiat in info["quote"]:
                        quote_data = info["quote"][fiat]
                        result[cmc_id] = {
                            "price": quote_data.get("price", 0),
                            "market_cap": quote_data.get("market_cap", None),
                            "volume_24h": quote_data.get("volume_24h", None),
                            "change_1h": quote_data.get("percent_change_1h", None),
                            "change_24h": quote_data.get("percent_change_24h", None),
                            "change_7d": quote_data.get("percent_change_7d", None)
                        }
            
            logger.info(f"Successfully fetched complete market data for {len(result)} symbols in {fiat}")
            return result
        except Exception as e:
            logger.error(f"Error fetching complete market data: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_latest_prices(self, cmc_ids, fiat="USD"):
        """
        Get latest prices for specified CMC IDs in the given fiat currency
        (Backward compatibility method - now uses complete market data)
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of prices by CMC ID
        """
        try:
            # Use the complete market data method and extract only prices
            complete_data = self.get_complete_market_data(cmc_ids, fiat)
            
            if isinstance(complete_data, dict) and complete_data.get("status") == "error":
                return complete_data
            
            # Extract only prices for backward compatibility
            result = {}
            for cmc_id, data in complete_data.items():
                if isinstance(data, dict) and "price" in data:
                    result[cmc_id] = data["price"]
            
            return result
        except Exception as e:
            logger.error(f"Error fetching latest prices: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def get_24h_changes(self, cmc_ids, fiat="USD"):
        """
        Get 24-hour price changes for specified CMC IDs in the given fiat currency
        (Backward compatibility method - now uses complete market data)
        
        Args:
            cmc_ids (list): List of CoinMarketCap IDs
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of 24h price changes by CMC ID
        """
        try:
            # Use the complete market data method and extract only 24h changes
            complete_data = self.get_complete_market_data(cmc_ids, fiat)
            
            if isinstance(complete_data, dict) and complete_data.get("status") == "error":
                return complete_data
            
            # Extract only 24h changes for backward compatibility
            result = {}
            for cmc_id, data in complete_data.items():
                if isinstance(data, dict) and "change_24h" in data:
                    result[cmc_id] = data["change_24h"]
            
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
        
        # فیلتر کردن NCC توکن‌ها (8517, 8519) - آن‌ها توسط شبیه‌ساز اختصاصی کنترل می‌شوند
        symbols = [s for s in symbols if s not in [8517, 8519]]
        if len(symbols) == 0:
            logger.info("No symbols to update after filtering NCC tokens")
            return {"success": True, "message": "No symbols to update", "updated_count": 0}
            
        try:
            logger.info(f"Starting update_prices for {len(symbols)} currency IDs in {len(fiat_currencies)} currencies (NCC tokens filtered out)")
            logger.debug(f"Currency IDs to update: {symbols}")
            logger.debug(f"Fiat currencies to update: {fiat_currencies}")
            
            # قبل از هر چیز، باید CMC_ID را برای هر CurrencyID از دیتابیس بگیریم
            session = Session(bind=engine)
            try:
                # دریافت مپینگ CurrencyID به CMC_ID از دیتابیس
                currency_mapping = {}
                cmc_to_currency_ids = {}  # مپینگ CMC_ID به لیست CurrencyID ها
                
                # اگر symbols خالی باشد، همه ارزها را بگیر
                if not symbols:
                    logger.info("No specific symbols provided, fetching all currencies from database")
                    currencies = session.query(Currencies).filter(Currencies.CMC_ID.isnot(None)).all()
                else:
                    currencies = session.query(Currencies).filter(Currencies.CurrencyID.in_(symbols), Currencies.CMC_ID.isnot(None)).all()
                
                # ساخت مپینگ بین CurrencyID و CMC_ID و گروه‌بندی بر اساس CMC_ID
                for currency in currencies:
                    if currency.CMC_ID:  # فقط ارزهایی که CMC_ID دارند
                        cmc_id_str = str(currency.CMC_ID)
                        currency_mapping[currency.CurrencyID] = cmc_id_str
                        
                        # گروه‌بندی CurrencyID ها بر اساس CMC_ID
                        if cmc_id_str not in cmc_to_currency_ids:
                            cmc_to_currency_ids[cmc_id_str] = []
                        cmc_to_currency_ids[cmc_id_str].append(currency.CurrencyID)
                
                # حذف CMC_ID های تکراری برای API call
                unique_cmc_ids = list(cmc_to_currency_ids.keys())
                
                logger.info(f"Found {len(currency_mapping)} total currency records with valid CMC_ID")
                logger.info(f"Unique CMC_IDs for API calls: {len(unique_cmc_ids)} (optimized from {len(currency_mapping)} records)")
                logger.debug(f"Currency mapping: {currency_mapping}")
                logger.debug(f"CMC_ID grouping: {cmc_to_currency_ids}")
                
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
            
            # متغیرهای مشترک برای همه fiat currencies
            success_count = 0
            fail_count = 0
            currency_ids = list(currency_mapping.keys())  # لیست CurrencyID ها
            
            for fiat in fiat_currencies:
                logger.info(f"Processing {fiat} currency updates")
                
                # استفاده از CMC_ID های یکتا برای فراخوانی API (بهینه‌سازی شده)
                if not unique_cmc_ids:
                    logger.warning(f"No valid unique CMC IDs found for currencies, skipping {fiat}")
                    continue
                    
                logger.debug(f"Using unique CMC IDs for API call: {unique_cmc_ids} (total: {len(unique_cmc_ids)})")
                
                # Get complete market data using unique CMC_IDs
                market_data = self.get_complete_market_data(unique_cmc_ids, fiat)
                
                # بررسی کامل داده‌های دریافتی
                logger.debug(f"Market data received from API: {market_data}")
                
                # Check for errors
                if isinstance(market_data, dict) and market_data.get("status") == "error":
                    logger.error(f"Error fetching market data for {fiat}: {market_data.get('message')}")
                    continue
                
                # Update database - create a new session for each fiat currency
                session = Session(bind=engine)
                legacy_prices_lock_held = False
                legacy_lock_miss_logged = False
                try:
                    logger.debug(f"Starting database updates for {len(currency_ids)} currencies in {fiat}")
                    fiat_success = 0
                    fiat_fail = 0

                    if fiat == "USD" and not _use_new_price_tables():
                        try:
                            lk = session.execute(
                                text("SELECT GET_LOCK(:ln, 7200)"),
                                {"ln": LEGACY_PRICES_BATCH_LOCK},
                            ).scalar()
                            legacy_prices_lock_held = lk == 1
                            if not legacy_prices_lock_held:
                                logger.error(
                                    "Legacy prices: GET_LOCK returned %s; USD inserts skipped for this batch.",
                                    lk,
                                )
                        except Exception as lock_e:
                            logger.error(
                                "Legacy prices GET_LOCK failed: %s",
                                lock_e,
                                exc_info=True,
                            )

                    legacy_next_price_id = None
                    if legacy_prices_lock_held:
                        legacy_next_price_id = int(
                            session.execute(
                                text(
                                    "SELECT COALESCE(MAX(id), 0) + 1 AS n FROM prices"
                                )
                            ).scalar_one()
                        )
                    
                    # لاگ اتصال به دیتابیس
                    try:
                        logger.debug(f"Testing database connection...")
                        connection_test = session.execute(text("SELECT 1")).first()
                        logger.debug(f"Database connection test result: {connection_test}")
                    except Exception as conn_err:
                        logger.error(f"Database connection error: {str(conn_err)}", exc_info=True)
                        
                    # Update database - به‌روزرسانی همه CurrencyID های مربوط به هر CMC_ID
                    for cmc_id in unique_cmc_ids:
                        # بررسی اگر CMC_ID در نتایج API وجود دارد
                        cmc_market_data = market_data.get(cmc_id)
                        
                        if not isinstance(cmc_market_data, dict) or not cmc_market_data.get("price"):
                            logger.warning(f"Invalid market data for CMC_ID {cmc_id} in {fiat}: {cmc_market_data}")
                            # تمام CurrencyID های این CMC_ID را fail حساب کن
                            fiat_fail += len(cmc_to_currency_ids.get(cmc_id, []))
                            continue
                        
                        # استخراج تمام داده‌های بازار
                        price_value = cmc_market_data.get("price")
                        market_cap_value = cmc_market_data.get("market_cap")
                        volume_24h_value = cmc_market_data.get("volume_24h")
                        change_1h_value = cmc_market_data.get("change_1h")
                        change_24h_value = cmc_market_data.get("change_24h")
                        change_7d_value = cmc_market_data.get("change_7d")
                        
                        # به‌روزرسانی همه CurrencyID هایی که این CMC_ID را دارند
                        currency_ids_for_cmc = cmc_to_currency_ids.get(cmc_id, [])
                        logger.debug(f"Processing CMC_ID {cmc_id} in {fiat}: price={price_value}, market_cap={market_cap_value}, volume_24h={volume_24h_value}")
                        logger.debug(f"Changes - 1h: {change_1h_value}%, 24h: {change_24h_value}%, 7d: {change_7d_value}%")
                        logger.debug(f"Updating {len(currency_ids_for_cmc)} currency records: {currency_ids_for_cmc}")
                        
                        for currency_id in currency_ids_for_cmc:
                            try:
                                # استفاده از CurrencyID برای به‌روزرسانی دیتابیس
                                from datetime import datetime

                                current_timestamp = datetime.now()

                                if fiat == "USD" and _use_new_price_tables():
                                    logger.debug(f"Upserting ticks_recent for symbol_id {currency_id}")
                                    tick_stmt = text("""
                                        INSERT INTO ticks_recent (symbol_id, price, volume_24h, market_cap, timestamp)
                                        VALUES (:symbol_id, :price, :volume_24h, :market_cap, :timestamp)
                                    """)
                                    try:
                                        session.execute(tick_stmt, {
                                            'symbol_id': currency_id,
                                            'price': price_value,
                                            'volume_24h': volume_24h_value,
                                            'market_cap': market_cap_value,
                                            'timestamp': current_timestamp
                                        })
                                        session.commit()
                                        logger.debug(f"Tick inserted for symbol_id {currency_id}")
                                    except Exception as te:
                                        session.rollback()
                                        logger.warning(f"Could not insert tick for {currency_id}: {str(te)}")
                                    
                                    logger.debug(f"Upserting current_prices for symbol_id {currency_id}")
                                    curr_stmt = text("""
                                        INSERT INTO current_prices 
                                        (symbol_id, price, volume_24h, market_cap, change_1h, change_24h, change_7d, last_updated)
                                        VALUES (:symbol_id, :price, :volume_24h, :market_cap, :change_1h, :change_24h, :change_7d, :last_updated)
                                        ON DUPLICATE KEY UPDATE
                                            price = VALUES(price),
                                            volume_24h = VALUES(volume_24h),
                                            market_cap = VALUES(market_cap),
                                            change_1h = VALUES(change_1h),
                                            change_24h = VALUES(change_24h),
                                            change_7d = VALUES(change_7d),
                                            last_updated = VALUES(last_updated)
                                    """)
                                    
                                    try:
                                        session.execute(curr_stmt, {
                                            'symbol_id': currency_id,
                                            'price': price_value,
                                            'volume_24h': volume_24h_value,
                                            'market_cap': market_cap_value,
                                            'change_1h': change_1h_value,
                                            'change_24h': change_24h_value,
                                            'change_7d': change_7d_value,
                                            'last_updated': current_timestamp
                                        })
                                        session.commit()
                                        fiat_success += 1
                                        logger.debug(f"Successfully updated current_prices and ticks for symbol_id {currency_id}")
                                    except Exception as ce:
                                        session.rollback()
                                        logger.warning(f"Could not update current_prices for {currency_id}: {str(ce)}")
                                        fiat_fail += 1
                                elif fiat == "USD":
                                    # اسکیمای قدیمی: جدول prices — اگر id بدون AUTO_INCREMENT باشد، id صریح + شمارنده زیر قفل دسته‌ای.
                                    if (
                                        not legacy_prices_lock_held
                                        or legacy_next_price_id is None
                                    ):
                                        session.rollback()
                                        fiat_fail += 1
                                        if not legacy_lock_miss_logged:
                                            legacy_lock_miss_logged = True
                                            logger.error(
                                                "Legacy prices: batch lock not held; "
                                                "all USD legacy inserts skipped for this batch."
                                            )
                                        continue
                                    try:
                                        rec = Price(
                                            id=legacy_next_price_id,
                                            crypto_id=str(currency_id),
                                            currency=fiat,
                                            price=Decimal(str(price_value)),
                                            market_cap=Decimal(str(market_cap_value)) if market_cap_value is not None else None,
                                            volume_24h=Decimal(str(volume_24h_value)) if volume_24h_value is not None else None,
                                            change_1h=Decimal(str(change_1h_value)) if change_1h_value is not None else None,
                                            change_24h=Decimal(str(change_24h_value)) if change_24h_value is not None else None,
                                            change_7d=Decimal(str(change_7d_value)) if change_7d_value is not None else None,
                                            is_historical=False,
                                            timestamp=current_timestamp,
                                        )
                                        session.add(rec)
                                        session.commit()
                                        legacy_next_price_id += 1
                                        fiat_success += 1
                                    except Exception as le:
                                        session.rollback()
                                        fiat_fail += 1
                                        logger.warning(
                                            "Legacy prices insert failed for %s: %s",
                                            currency_id,
                                            le,
                                        )
                                        try:
                                            legacy_next_price_id = int(
                                                session.execute(
                                                    text(
                                                        "SELECT COALESCE(MAX(id), 0) + 1 AS n FROM prices"
                                                    )
                                                ).scalar_one()
                                            )
                                        except Exception as sync_e:
                                            logger.warning(
                                                "Could not resync legacy_next_price_id: %s",
                                                sync_e,
                                            )
                                else:
                                    logger.debug(f"Skipping non-USD currency {fiat} (will be calculated from fiat_rates)")
                                    fiat_success += 1
                                
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
                    if legacy_prices_lock_held:
                        try:
                            session.execute(
                                text("SELECT RELEASE_LOCK(:ln)"),
                                {"ln": LEGACY_PRICES_BATCH_LOCK},
                            )
                        except Exception as rel_e:
                            logger.warning(
                                "Legacy prices RELEASE_LOCK: %s",
                                rel_e,
                            )
                    session.close()
                    logger.debug(f"Closed database session for {fiat}")
            
            logger.info(f"Price update complete. Total: {success_count} successful, {fail_count} failed")
            return True
            
        except Exception as e:
            logger.error(f"Error in update_prices: {str(e)}", exc_info=True)
            return False
    
    def get_historical_data(self, currency_ids, time_start=None, time_end=None, interval="daily", fiat_currencies=None):
        """
        Get historical price data for specified currencies
        
        Args:
            currency_ids (list): List of internal currency IDs
            time_start (str): Start time in ISO format
            time_end (str): End time in ISO format
            interval (str): Time interval (daily, hourly, etc.)
            fiat_currencies (list): List of fiat currency codes
            
        Returns:
            dict: Historical data result
        """
        try:
            logger.info(f"Getting historical data for {len(currency_ids)} currencies")
            
            # First try to get from stored data
            stored_data = self.historical_service.get_stored_historical_data(
                currency_ids, time_start, time_end, fiat_currencies
            )
            
            if stored_data.get("success") and stored_data.get("data"):
                logger.info("Retrieved historical data from database")
                return stored_data
            
            # If no stored data, fetch from API and store
            logger.info("No stored data found, fetching from API")
            result = self.historical_service.store_historical_data(
                currency_ids, time_start, time_end, interval, fiat_currencies
            )
            
            if result.get("success"):
                # Now get the stored data
                stored_data = self.historical_service.get_stored_historical_data(
                    currency_ids, time_start, time_end, fiat_currencies
                )
                return stored_data
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}", exc_info=True)
            return {"success": False, "message": str(e)}
    
    def update_historical_data(self, currency_ids=None, time_start=None, time_end=None, interval="daily", fiat_currencies=None):
        """
        Update historical data for specified currencies
        
        Args:
            currency_ids (list): List of internal currency IDs (if None, update all)
            time_start (str): Start time in ISO format
            time_end (str): End time in ISO format
            interval (str): Time interval
            fiat_currencies (list): List of fiat currency codes
            
        Returns:
            dict: Update result
        """
        try:
            logger.info("Starting historical data update")
            
            # If no specific currencies provided, get all currencies with CMC_ID
            if not currency_ids:
                session = Session(bind=engine)
                try:
                    currencies = session.query(Currencies).filter(Currencies.CMC_ID.isnot(None)).all()
                    currency_ids = [c.CurrencyID for c in currencies]
                    logger.info(f"Found {len(currency_ids)} currencies with CMC_ID for historical update")
                finally:
                    session.close()
            
            if not currency_ids:
                return {"success": False, "message": "No currencies found for historical update"}
            
            # Update historical data
            result = self.historical_service.store_historical_data(
                currency_ids, time_start, time_end, interval, fiat_currencies
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating historical data: {str(e)}", exc_info=True)
            return {"success": False, "message": str(e)} 