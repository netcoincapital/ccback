"""
ماژول سرویس قیمت برای مدیریت عملیات‌های مربوط به قیمت ارزها
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import engine, Currencies
from database.prices import Price
from Currencies.currency_price_service import CurrencyPriceService, fiat_symbols
from utils.logging_config import get_logger
import time
from datetime import datetime, timedelta

# تنظیم لاگر
logger = get_logger(__file__)
logger.info("Initializing price service module")

class PriceDbService:
    """سرویس مدیریت قیمت‌ها در دیتابیس"""
    
    @staticmethod
    def get_prices(currency_ids, fiat_currencies):
        """
        دریافت قیمت‌های ارز از دیتابیس
        
        Args:
            currency_ids (list): لیست شناسه‌های ارز
            fiat_currencies (list): لیست ارزهای فیات
            
        Returns:
            dict: دیکشنری از قیمت‌های ارز
        """
        logger.info(f"Fetching prices for {len(currency_ids)} currencies in {len(fiat_currencies)} fiats")
        logger.debug(f"Currency IDs: {currency_ids}, Fiat currencies: {fiat_currencies}")
        
        session = Session(bind=engine)
        try:
            # تبدیل currency_ids به هر دو فرمت رشته‌ای و عددی برای جستجو
            string_ids = [str(cid) for cid in currency_ids]
            
            # پرس و جو از دیتابیس با فرمت رشته‌ای
            logger.debug("Running ORM query...")
            query = (
                session.query(Price)
                .filter(Price.crypto_id.in_(string_ids))
                .filter(Price.currency.in_(fiat_currencies))
            )
            
            logger.debug(f"Generated SQL query: {str(query)}")
            
            results = query.all()
            logger.debug(f"Found {len(results)} price records")
            
            # لاگ تمام رکوردهای یافت شده
            for record in results:
                logger.debug(f"Price record: crypto_id={record.crypto_id}, fiat={record.currency}, price={record.price}, change={record.change_24h}")
            
            # ساخت یک نگاشت از crypto_id به CurrencyID اصلی برای حفظ مقادیر اصلی
            crypto_id_to_currency_id = {}
            for cid in currency_ids:
                crypto_id_to_currency_id[str(cid)] = cid
            
            # ساخت دیکشنری نتیجه
            prices_dict = {}
            for currency_id in currency_ids:
                # از همان currency_id اصلی در نتیجه استفاده می‌کنیم
                prices_dict[currency_id] = {}
                
                # جستجو با رشته برای تطابق با دیتابیس
                string_currency_id = str(currency_id)
                
                for fiat in fiat_currencies:
                    # جستجوی رکورد مناسب
                    matching_records = [p for p in results if p.crypto_id == string_currency_id and p.currency == fiat]
                    
                    if matching_records:
                        price_record = matching_records[0]
                        # اطمینان از تبدیل به float
                        price_value = float(price_record.price) if price_record.price is not None else 0.0
                        change_value = float(price_record.change_24h) if price_record.change_24h is not None else 0.0
                        
                        prices_dict[currency_id][fiat] = {
                            "price": price_value,
                            "change_24h": change_value,
                            "updated_at": price_record.last_updated
                        }
                        
                        logger.debug(f"Found price record for {currency_id} in {fiat}: price={price_value}, change={change_value}")
                    else:
                        # در صورت عدم وجود، مقادیر پیش‌فرض
                        logger.warning(f"No price record found for {currency_id} in {fiat}, using default values")
                        prices_dict[currency_id][fiat] = {
                            "price": 0.0,
                            "change_24h": 0.0,
                            "updated_at": None
                        }
            
            return prices_dict
            
        except Exception as e:
            logger.error(f"Error fetching prices: {str(e)}", exc_info=True)
            return {}
        finally:
            session.close()
    
    @staticmethod
    def get_price_stats():
        """
        دریافت آمار به‌روزرسانی قیمت‌ها
        
        Returns:
            dict: آمار قیمت‌ها
        """
        session = Session(bind=engine)
        try:
            # تعداد کل رکوردها
            total_records = session.query(func.count(Price.id)).scalar()
            
            # آخرین به‌روزرسانی
            latest_update = session.query(func.max(Price.last_updated)).scalar()
            
            # تعداد ارزهای منحصر به فرد
            unique_cryptos = session.query(func.count(func.distinct(Price.crypto_id))).scalar()
            
            # تعداد ارزهای فیات منحصر به فرد
            unique_fiats = session.query(func.count(func.distinct(Price.currency))).scalar()
            
            # رکوردهای به‌روز نشده در 24 ساعت گذشته
            one_day_ago = datetime.now() - timedelta(days=1)
            outdated_records = session.query(func.count(Price.id)).filter(Price.last_updated < one_day_ago).scalar()
            
            return {
                "total_records": total_records,
                "latest_update": latest_update,
                "unique_cryptos": unique_cryptos,
                "unique_fiats": unique_fiats,
                "outdated_records": outdated_records,
                "up_to_date_percentage": (
                    ((total_records - outdated_records) / total_records) * 100 
                    if total_records > 0 else 0
                )
            }
            
        finally:
            session.close()
    
    @staticmethod
    def update_prices(currency_ids=None, fiat_currencies=None):
        """
        به‌روزرسانی قیمت‌ها در دیتابیس
        
        Args:
            currency_ids (list, optional): لیست شناسه‌های ارز. اگر None باشد، همه ارزها به‌روز می‌شوند.
            fiat_currencies (list, optional): لیست ارزهای فیات. اگر None باشد، همه ارزهای فیات به‌روز می‌شوند.
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        start_time = time.time()
        logger.info("Starting price update process")
        
        # اگر currency_ids مشخص نشده باشد، همه ارزها را بگیر
        # ما همه currency_ids را به CurrencyPriceService می‌فرستیم
        # و آن سرویس خودش CMC_ID های مربوطه را استخراج می‌کند
        if currency_ids is None:
            session = Session(bind=engine)
            try:
                all_cryptos = session.query(Currencies).order_by(Currencies.CurrencyID.asc()).all()
                currency_ids = [c.CurrencyID for c in all_cryptos]
                logger.info(f"Updating all {len(currency_ids)} currencies")
            finally:
                session.close()
        
        # اگر ارزهای فیات مشخص نشده باشند، از همه پشتیبانی شده‌ها استفاده کن
        if fiat_currencies is None:
            fiat_currencies = list(fiat_symbols.keys())
            logger.info(f"Updating for all {len(fiat_currencies)} supported fiat currencies")
        
        # استفاده از سرویس به‌روزرسانی قیمت
        # ما currency_ids را ارسال می‌کنیم (نه CMC_ID ها) و سرویس خودش آنها را به CMC_ID تبدیل می‌کند
        service = CurrencyPriceService()
        result = service.update_prices(currency_ids, fiat_currencies)
        
        elapsed_time = time.time() - start_time
        
        if result:
            logger.info(f"Price update completed successfully in {elapsed_time:.2f} seconds")
            return {
                "success": True,
                "message": f"Successfully updated prices for {len(currency_ids)} currencies in {len(fiat_currencies)} fiat currencies",
                "elapsed_time": elapsed_time,
                "currencies_count": len(currency_ids),
                "fiats_count": len(fiat_currencies)
            }
        else:
            logger.error(f"Price update failed after {elapsed_time:.2f} seconds")
            return {
                "success": False,
                "message": "Failed to update prices",
                "elapsed_time": elapsed_time
            } 