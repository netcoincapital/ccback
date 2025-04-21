import os
import sys
import time
import random
import numpy as np
from datetime import datetime, timedelta
import logging
import schedule
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.logging_config import get_logger
from database.Currencies import Currencies
from database.prices import Price

# تنظیم مسیر برای import از ماژول‌های دیگر پروژه
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# تنظیم لاگر با استفاده از ماژول لاگینگ پروژه
logger = get_logger(__file__)
logger.info("📊 راه‌اندازی ماژول شبیه‌ساز قیمت NCC")

# تنظیمات قیمت
INITIAL_PRICE = 0.05
TARGET_PRICE = 0.80
MIN_MONTHS = 5
MAX_MONTHS = 10

# فیات‌های مورد پشتیبانی
FIAT_CURRENCIES = {
    "USD": "$", "CAD": "CA$", "AUD": "AU$", "GBP": "£", "EUR": "€",
    "KWD": "KD", "TRY": "₺", "SAR": "﷼", "CNY": "¥",
    "KRW": "₩", "JPY": "¥", "INR": "₹", "RUB": "₽", "IQD": "ع.د",
    "TND": "د.ت", "BHD": "ب.د"
}

# نرخ تبدیل تقریبی فیات‌های مختلف به دلار آمریکا (برای شبیه‌سازی)
FIAT_EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
    "CNY": 0.14,
    "AUD": 0.66,
    "CAD": 0.73,
    "INR": 0.012,
    "KRW": 0.00074,
    "RUB": 0.011,
    "TRY": 0.031,
    "SAR": 0.27,
    "KWD": 3.25,
    "BHD": 2.65,
    "IQD": 0.00076,
    "TND": 0.32
}

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://coincee:09387270277Mn!!??@localhost/coincee")
NCC_SMART_CONTRACT_ETH = "0x3386F545a78eAa832946b59EA10FfDA34275A479"
NCC_SMART_CONTRACT_TRX = "T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf"
NCC_CURRENCY_IDS = []
price_history = []  # تاریخچه قیمت مشترک - یک لیست از تاپل (زمان، قیمت)
last_updated = None  # آخرین زمان به‌روزرسانی مشترک برای همه توکن‌ها

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_ncc():
    """
    مقداردهی اولیه توکن‌های NCC از دیتابیس
    
    Returns:
        bool: نتیجه مقداردهی اولیه
    """
    global NCC_CURRENCY_IDS
    session = Session()
    
    logger.info("🔍 جستجوی توکن‌های NCC در دیتابیس")
    
    # جستجو برای توکن ETH
    eth_token = session.query(Currencies).filter(
        Currencies.SmartContractAddress == NCC_SMART_CONTRACT_ETH
    ).first()
    
    # جستجو برای توکن TRX
    trx_token = session.query(Currencies).filter(
        Currencies.SmartContractAddress == NCC_SMART_CONTRACT_TRX
    ).first()

    if not eth_token and not trx_token:
        logger.error("❌ هیچ توکن NCC در دیتابیس یافت نشد")
        session.close()
        return False

    if eth_token:
        NCC_CURRENCY_IDS.append(eth_token.CurrencyID)
        logger.info(f"✅ توکن NCC اتریوم یافت شد - شناسه ارز: {eth_token.CurrencyID}")
        
    if trx_token:
        NCC_CURRENCY_IDS.append(trx_token.CurrencyID)
        logger.info(f"✅ توکن NCC ترون یافت شد - شناسه ارز: {trx_token.CurrencyID}")
    
    session.close()
    return len(NCC_CURRENCY_IDS) > 0

def get_current_price(fiat="USD"):
    """
    دریافت آخرین قیمت NCC از دیتابیس
    
    Args:
        fiat: ارز فیات مورد نظر (پیش‌فرض: USD)
        
    Returns:
        float: قیمت فعلی یا None
    """
    if not NCC_CURRENCY_IDS:
        logger.warning("⚠️ هیچ شناسه ارز NCC موجود نیست")
        return None
        
    session = Session()
    # استفاده از اولین شناسه ارز برای دریافت قیمت
    price = session.query(Price).filter(
        Price.crypto_id == NCC_CURRENCY_IDS[0],
        Price.currency == fiat
    ).order_by(Price.last_updated.desc()).first()
    session.close()
    
    if price:
        logger.debug(f"📊 قیمت فعلی برای NCC به {fiat}: {float(price.price)} {FIAT_CURRENCIES.get(fiat, '')}")
        return float(price.price)
    else:
        logger.debug(f"⚠️ هیچ قیمتی برای NCC به {fiat} در دیتابیس پیدا نشد")
        return None

def get_price_24h_ago(fiat="USD"):
    """
    دریافت قیمت NCC در 24 ساعت گذشته
    
    Args:
        fiat: ارز فیات مورد نظر (پیش‌فرض: USD)
        
    Returns:
        float: قیمت 24 ساعت قبل یا None
    """
    if not NCC_CURRENCY_IDS:
        logger.warning("⚠️ هیچ شناسه ارز NCC موجود نیست")
        return None
        
    now = datetime.now()
    session = Session()
    
    try:
        # روش اول: جستجو برای قیمت بین 23 تا 25 ساعت قبل
        price = session.query(Price).filter(
            Price.crypto_id == NCC_CURRENCY_IDS[0],
            Price.currency == fiat,
            Price.last_updated < now - timedelta(hours=23),
            Price.last_updated > now - timedelta(hours=25)
        ).order_by(Price.last_updated.desc()).first()
        
        # اگر نتیجه‌ای نداشت، قدیمی‌ترین قیمت موجود را برگردان
        if not price:
            price = session.query(Price).filter(
                Price.crypto_id == NCC_CURRENCY_IDS[0],
                Price.currency == fiat
            ).order_by(Price.last_updated.asc()).first()
            
            if price:
                logger.debug(f"📊 قیمت دقیقاً 24 ساعت قبل یافت نشد، از قدیمی‌ترین قیمت موجود استفاده می‌شود")
                
        if price:
            logger.debug(f"📊 قیمت 24 ساعت قبل برای NCC به {fiat}: {float(price.price)} {FIAT_CURRENCIES.get(fiat, '')}")
            return float(price.price)
        else:
            logger.debug(f"⚠️ هیچ قیمتی برای 24 ساعت قبل NCC به {fiat} پیدا نشد")
            # اگر هیچ قیمتی یافت نشد، از قیمت پایه با یک اختلاف کوچک استفاده می‌کنیم
            return INITIAL_PRICE * 0.99  # 1٪ کمتر از قیمت پایه
    finally:
        session.close()

def generate_price():
    """
    تولید قیمت جدید برای توکن NCC به دلار آمریکا
    
    Returns:
        tuple: قیمت جدید و درصد تغییر 24 ساعته
    """
    global price_history, last_updated
    now = datetime.now()

    if not price_history:
        # دریافت قیمت فعلی از دیتابیس
        current_price = get_current_price()
        
        # بررسی منبع قیمت (دیتابیس یا قیمت پیش‌فرض)
        if current_price:
            base = current_price
            logger.info(f"🔄 استفاده از قیمت موجود در دیتابیس برای ادامه روند: ${base:.8f}")
        else:
            base = INITIAL_PRICE
            logger.info(f"🆕 هیچ قیمتی در دیتابیس یافت نشد، شروع از قیمت پایه: ${base:.8f}")
        
        price_history.append((now, base))
        last_updated = now
        
        # برای اولین قیمت، تغییر را به صورت مصنوعی بین -2% تا +3% تنظیم می‌کنیم
        # تا صفر نباشد و طبیعی‌تر به نظر برسد
        change_24h = random.uniform(-2.0, 3.0)
        logger.info(f"🆕 شروع ثبت تاریخچه قیمت برای NCC با قیمت پایه: ${base:.8f} و تغییر {change_24h:.2f}%")
        return base, change_24h

    last_price = price_history[-1][1]
    days_passed = (now - last_updated).total_seconds() / (60 * 60 * 24)
    total_days = random.randint(MIN_MONTHS * 30, MAX_MONTHS * 30)
    drift = (TARGET_PRICE - INITIAL_PRICE) / total_days
    volatility = 0.02

    drift_component = drift * days_passed
    random_component = np.random.normal(0, volatility) * last_price * np.sqrt(days_passed)
    new_price = last_price + drift_component + random_component
    new_price = max(new_price, INITIAL_PRICE)

    price_24h = get_price_24h_ago()
    
    # اگر قیمت 24 ساعت قبل وجود نداشت، از قیمت قبلی در تاریخچه استفاده می‌کنیم
    if not price_24h and len(price_history) > 1:
        price_24h = price_history[-2][1]
        logger.debug(f"استفاده از قیمت قبلی در تاریخچه به عنوان قیمت 24 ساعت قبل: ${price_24h:.8f}")
        
    # محاسبه درصد تغییر
    if price_24h:
        change_24h = ((new_price / price_24h - 1) * 100)
    else:
        # اگر هیچ قیمت قبلی نداریم، یک تغییر تصادفی معقول تنظیم می‌کنیم
        change_24h = random.uniform(-3.0, 4.0)
        logger.debug(f"تنظیم تغییر 24 ساعته به صورت تصادفی: {change_24h:.2f}%")

    price_history.append((now, new_price))
    last_updated = now

    change_sign = "+" if change_24h > 0 else ""
    logger.info(f"📈 قیمت جدید NCC (USD): ${new_price:.8f}, تغییر 24 ساعته: {change_sign}{change_24h:.2f}%")
    return new_price, change_24h

def calculate_fiat_price(usd_price, fiat):
    """
    محاسبه قیمت در واحد پولی دیگر بر اساس قیمت دلار
    
    Args:
        usd_price: قیمت به دلار آمریکا
        fiat: ارز فیات مورد نظر
        
    Returns:
        float: قیمت به ارز فیات مورد نظر
    """
    if fiat == "USD":
        return usd_price
        
    exchange_rate = FIAT_EXCHANGE_RATES.get(fiat)
    if not exchange_rate:
        logger.warning(f"⚠️ نرخ تبدیل برای {fiat} یافت نشد، از دلار استفاده می‌شود")
        return usd_price
        
    # افزودن تصادفی 0.5% تغییر برای واقعی‌تر به نظر رسیدن
    noise = 1.0 + (random.random() - 0.5) * 0.01
    fiat_price = usd_price / exchange_rate * noise
    
    return fiat_price

def update_price(usd_price, change_24h):
    """
    به‌روزرسانی قیمت تمام توکن‌های NCC در دیتابیس برای تمام ارزهای فیات
    
    Args:
        usd_price: قیمت جدید به دلار آمریکا
        change_24h: درصد تغییر 24 ساعته
        
    Returns:
        bool: نتیجه به‌روزرسانی
    """
    if not NCC_CURRENCY_IDS:
        logger.warning("⚠️ هیچ شناسه ارز NCC برای به‌روزرسانی وجود ندارد")
        return False
        
    session = Session()
    success = True
    now = datetime.now()
    
    try:
        # مقادیر مشترک برای همه رکوردها
        volume = 400000 + random.random() * 200000
        market_cap = usd_price * 100000000
        change_1h = change_24h / 24
        
        # به‌روزرسانی قیمت برای تمام توکن‌های NCC در تمام ارزهای فیات
        for currency_id in NCC_CURRENCY_IDS:
            for fiat in FIAT_CURRENCIES.keys():
                try:
                    # محاسبه قیمت برای هر ارز فیات
                    fiat_price = calculate_fiat_price(usd_price, fiat)
                    
                    price = session.query(Price).filter(
                        Price.crypto_id == currency_id,
                        Price.currency == fiat
                    ).first()

                    if price:
                        price.price = Decimal(str(fiat_price))
                        price.change_24h = Decimal(str(change_24h))
                        price.change_1h = Decimal(str(change_1h))
                        price.market_cap = Decimal(str(market_cap))
                        price.volume_24h = Decimal(str(volume))
                        price.last_updated = now
                        logger.debug(f"✅ [ID: {currency_id}] رکورد قیمت NCC به {fiat} به‌روزرسانی شد")
                    else:
                        new_entry = Price(
                            crypto_id=currency_id,
                            currency=fiat,
                            price=Decimal(str(fiat_price)),
                            change_24h=Decimal(str(change_24h)),
                            change_1h=Decimal(str(change_1h)),
                            market_cap=Decimal(str(market_cap)),
                            volume_24h=Decimal(str(volume)),
                            change_7d=Decimal('0.00'),
                            last_updated=now
                        )
                        session.add(new_entry)
                        logger.debug(f"✅ [ID: {currency_id}] رکورد قیمت جدید NCC به {fiat} ایجاد شد")
                except Exception as e:
                    logger.error(f"❌ خطا در به‌روزرسانی قیمت ارز {currency_id} به {fiat}: {str(e)}")
                    success = False
                    # ادامه به‌روزرسانی سایر رکوردها
            
            logger.info(f"✅ به‌روزرسانی قیمت NCC برای ارز با شناسه {currency_id} در تمام واحدهای پولی انجام شد")
        
        session.commit()
        return success
    except Exception as e:
        logger.error(f"❌ خطا در به‌روزرسانی قیمت‌های NCC: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()

def run_price_update():
    """
    اجرای فرآیند به‌روزرسانی قیمت برای همه ارزهای NCC
    """
    logger.info("🔄 شروع به‌روزرسانی قیمت NCC برای تمام واحدهای پولی...")
    try:
        # تولید یک قیمت واحد به دلار
        usd_price, change = generate_price()
        if usd_price is not None:
            # اعمال قیمت یکسان برای همه توکن‌های NCC در همه واحدهای پولی
            update_price(usd_price, change)
    except Exception as e:
        logger.error(f"❌ خطا در فرآیند به‌روزرسانی قیمت NCC: {str(e)}")

def main():
    """
    تابع اصلی برنامه
    """
    logger.info("==================== شروع شبیه‌ساز قیمت NCC ====================")
    try:
        if not init_ncc():
            logger.error("❌ مقداردهی اولیه NCC با شکست مواجه شد - خروج از برنامه")
            return
        
        # اجرای اولیه
        run_price_update()
        
        # زمانبندی اجرای دوره‌ای
        schedule.every(1).minutes.do(run_price_update)
        logger.info("⏱️ زمانبندی به‌روزرسانی هر دقیقه تنظیم شد")
        
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره در برنامه اصلی: {str(e)}")
        logger.exception(e)  # ثبت کامل خطا با stack trace
    finally:
        logger.info("==================== پایان شبیه‌ساز قیمت NCC ====================")

if __name__ == '__main__':
    main()
