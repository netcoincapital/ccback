import sys, os
# اضافه کردن مسیر اصلی پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
sys.path.append(project_root)

import time
import random
import numpy as np
from datetime import datetime, timedelta
import logging
import schedule
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from CC.database.Currencies import Currencies
from CC.database.prices import Price
from CC.utils.logging_config import get_logger

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
NCC_SMART_CONTRACT_1 = "TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1"
NCC_SMART_CONTRACT_2 = "T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf"
NCC_CURRENCY_IDS_TO_FIND = [8517, 8519]  # هر دو شناسه NCC
price_history = []  # تاریخچه قیمت مشترک - یک لیست از تاپل (زمان، قیمت)
last_updated = None  # آخرین زمان به‌روزرسانی مشترک برای همه توکن‌ها

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_ncc():
    """
    مقداردهی اولیه توکن‌های NCC - جستجو برای هر دو آیدی 8517 و 8519
    """
    global NCC_CURRENCY_IDS
    session = Session()
    found_currencies = []
    
    logger.info("🔍 جستجوی توکن‌های NCC در دیتابیس...")
    
    for currency_id in NCC_CURRENCY_IDS_TO_FIND:
        ncc_token = session.query(Currencies).filter(Currencies.CurrencyID == str(currency_id)).first()
        if ncc_token:
            found_currencies.append(currency_id)
            logger.info(f"✅ توکن NCC با آیدی {currency_id} یافت شد - شناسه ارز: {currency_id}")
        else:
            logger.warning(f"⚠️ توکن NCC با آیدی {currency_id} در دیتابیس یافت نشد")
    
    if found_currencies:
        NCC_CURRENCY_IDS = found_currencies
        logger.info(f"✅ تعداد {len(NCC_CURRENCY_IDS)} توکن NCC یافت شد: {NCC_CURRENCY_IDS}")
    else:
        NCC_CURRENCY_IDS = []
        logger.error("❌ هیچ توکن NCC در دیتابیس یافت نشد")
        session.close()
        return False
    
    session.close()
    return True

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
    # استفاده از اولین شناسه ارز برای دریافت قیمت - تبدیل به string
    currency_id_str = str(NCC_CURRENCY_IDS[0])
    price = session.query(Price).filter(
        Price.crypto_id == currency_id_str,
        Price.currency == fiat
    ).order_by(Price.last_updated.desc()).first()
    session.close()
    
    if price:
        logger.debug(f"📊 قیمت فعلی برای NCC (ID: {currency_id_str}) به {fiat}: {float(price.price)} {FIAT_CURRENCIES.get(fiat, '')}")
        return float(price.price)
    else:
        logger.debug(f"⚠️ هیچ قیمتی برای NCC (ID: {currency_id_str}) به {fiat} در دیتابیس پیدا نشد")
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
        # استفاده از اولین شناسه ارز - تبدیل به string
        currency_id_str = str(NCC_CURRENCY_IDS[0])
        # روش اول: جستجو برای قیمت بین 23 تا 25 ساعت قبل
        price = session.query(Price).filter(
            Price.crypto_id == currency_id_str,
            Price.currency == fiat,
            Price.last_updated < now - timedelta(hours=23),
            Price.last_updated > now - timedelta(hours=25)
        ).order_by(Price.last_updated.desc()).first()
        
        # اگر نتیجه‌ای نداشت، قدیمی‌ترین قیمت موجود را برگردان
        if not price:
            price = session.query(Price).filter(
                Price.crypto_id == currency_id_str,
                Price.currency == fiat
            ).order_by(Price.last_updated.asc()).first()
            
            if price:
                logger.debug(f"📊 قیمت دقیقاً 24 ساعت قبل یافت نشد، از قدیمی‌ترین قیمت موجود استفاده می‌شود")
                
        if price:
            logger.debug(f"📊 قیمت 24 ساعت قبل برای NCC (ID: {currency_id_str}) به {fiat}: {float(price.price)} {FIAT_CURRENCIES.get(fiat, '')}")
            return float(price.price)
        else:
            logger.debug(f"⚠️ هیچ قیمتی برای 24 ساعت قبل NCC (ID: {currency_id_str}) به {fiat} پیدا نشد")
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
        base = get_current_price("USD") or INITIAL_PRICE
        logger.info(f"🆕 شروع جدید شبیه‌ساز قیمت NCC از قیمت پایه: ${base:.8f}")
        
        price_history.append((now, base))
        last_updated = now
        
        # برای اولین قیمت، تغییر را صفر تنظیم می‌کنیم
        change_24h = 0.0
        logger.info(f"🆕 ثبت قیمت پایه NCC: ${base:.8f} (تغییر: {change_24h:.2f}%)")
        return base, change_24h

    last_price = price_history[-1][1]
    days_passed = (now - last_updated).total_seconds() / (60 * 60 * 24)
    total_days = 12 * 30  # یعنی 360 روز
    drift = (TARGET_PRICE - INITIAL_PRICE) / total_days
    volatility = 0.02

    drift_component = drift * days_passed
    random_component = np.random.normal(0, volatility) * last_price * np.sqrt(days_passed)
    new_price = last_price + drift_component + random_component
    new_price = max(new_price, INITIAL_PRICE)

    # احتمالات پامپ و دامپ
    pump_chance = 0.05  # احتمال 5% برای پامپ
    dump_chance = 0.05  # احتمال 5% برای دامپ
    
    if random.random() < pump_chance:
        pump_factor = random.uniform(1.10, 1.30)  # افزایش 10% تا 30%
        old_price = new_price
        new_price *= pump_factor
        logger.warning(f"🚀 پامپ! قیمت از ${old_price:.8f} به ${new_price:.8f} ({((pump_factor-1)*100):.1f}% افزایش)")
        
    elif random.random() < dump_chance:
        dump_factor = random.uniform(0.70, 0.90)  # کاهش 10% تا 30%
        old_price = new_price
        new_price *= dump_factor
        logger.warning(f"💥 دامپ! قیمت از ${old_price:.8f} به ${new_price:.8f} ({((1-dump_factor)*100):.1f}% کاهش)")

    # محاسبه درصد تغییر بر اساس تاریخچه داخلی
    if len(price_history) > 1:
        # استفاده از قیمت قبلی در تاریخچه به عنوان قیمت 24 ساعت قبل
        price_24h = price_history[-2][1] if len(price_history) > 1 else price_history[0][1]
        change_24h = ((new_price / price_24h - 1) * 100)
        logger.debug(f"محاسبه تغییر بر اساس تاریخچه داخلی: ${price_24h:.8f} -> ${new_price:.8f}")
    else:
        # اگر فقط یک قیمت در تاریخچه داریم، تغییر کوچکی تولید می‌کنیم
        change_24h = random.uniform(-1.0, 2.0)
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
    به‌روزرسانی قیمت برای همه توکن‌های NCC (8517 و 8519)
    """
    if not NCC_CURRENCY_IDS:
        logger.warning("⚠️ هیچ شناسه ارز NCC برای به‌روزرسانی وجود ندارد")
        return False
    logger.info(f"NCC_CURRENCY_IDS at start: {NCC_CURRENCY_IDS}")
    session = Session()
    success = True
    now = datetime.now()
    try:
        volume = 400000 + random.random() * 200000
        market_cap = usd_price * 100000000
        change_1h = change_24h / 24
        for currency_id in NCC_CURRENCY_IDS:
            logger.info(f"Trying to update price for currency_id: {currency_id}")
            for fiat in FIAT_CURRENCIES.keys():
                try:
                    fiat_price = calculate_fiat_price(usd_price, fiat)
                    # تبدیل currency_id به string برای کوئری دیتابیس
                    currency_id_str = str(currency_id)
                    price = session.query(Price).filter(
                        Price.crypto_id == currency_id_str,
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
                            crypto_id=currency_id_str,
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
    اجرای فرآیند به‌روزرسانی قیمت برای همه توکن‌های NCC (8517 و 8519)
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

def reset_price_simulator():
    """
    ریست کردن شبیه‌ساز قیمت NCC به حالت اولیه (5 سنت)
    """
    global price_history, last_updated
    logger.info("🔄 ریست کردن شبیه‌ساز قیمت NCC به حالت اولیه...")

    # پاک کردن تاریخچه قیمت
    price_history = []
    last_updated = None

    # حذف همه قیمت‌های قبلی NCC از دیتابیس
    session = Session()
    try:
        for currency_id in NCC_CURRENCY_IDS:
            # تبدیل currency_id به string برای کوئری دیتابیس
            currency_id_str = str(currency_id)
            deleted = session.query(Price).filter(Price.crypto_id == currency_id_str).delete()
            logger.info(f"🗑️ {deleted} رکورد قیمت قبلی برای NCC با شناسه {currency_id} حذف شد")
        session.commit()
    except Exception as e:
        logger.error(f"❌ خطا در حذف قیمت‌های قبلی NCC: {str(e)}")
        session.rollback()
    finally:
        session.close()

    # ثبت قیمت اولیه (۵ سنت) بدون استفاده از generate_price
    usd_price = INITIAL_PRICE
    change = 0.0
    if update_price(usd_price, change):
        logger.info(f"✅ شبیه‌ساز قیمت NCC با موفقیت ریست شد - قیمت جدید: ${usd_price:.8f}")
        return True
    else:
        logger.error("❌ خطا در ریست کردن شبیه‌ساز قیمت NCC")
        return False

def main():
    """
    تابع اصلی برنامه
    """
    logger.info("==================== شروع شبیه‌ساز قیمت NCC ====================")
    try:
        if not init_ncc():
            logger.error("❌ مقداردهی اولیه NCC با شکست مواجه شد - خروج از برنامه")
            return
        
        # بررسی آرگومان‌های خط فرمان برای ریست
        if len(sys.argv) > 1 and sys.argv[1] == "--reset":
            if reset_price_simulator():
                logger.info("✅ شبیه‌ساز قیمت با موفقیت ریست شد")
            else:
                logger.error("❌ خطا در ریست کردن شبیه‌ساز قیمت")
            return
        
        # بررسی وجود قیمت‌های متفاوت برای دو NCC و ریست خودکار در صورت لزوم
        logger.info("🔍 بررسی همسانی قیمت‌های NCC...")
        session = Session()
        try:
            prices_8517 = session.query(Price).filter(Price.crypto_id == '8517', Price.currency == 'USD').first()
            prices_8519 = session.query(Price).filter(Price.crypto_id == '8519', Price.currency == 'USD').first()
            
            # اگر قیمت‌ها متفاوت هستند یا از 5 سنت فاصله دارند، ریست کن
            need_reset = False
            if prices_8517 and prices_8519:
                price_8517 = float(prices_8517.price)
                price_8519 = float(prices_8519.price)
                if abs(price_8517 - price_8519) > 0.001 or abs(price_8517 - INITIAL_PRICE) > 0.001:
                    logger.warning(f"⚠️ قیمت‌های NCC متفاوت هستند: 8517=${price_8517:.8f}, 8519=${price_8519:.8f}")
                    need_reset = True
            elif prices_8517 or prices_8519:
                logger.warning("⚠️ تنها یکی از توکن‌های NCC قیمت دارد")
                need_reset = True
                
            if need_reset:
                logger.info("🔄 ریست خودکار شبیه‌ساز برای همسان‌سازی قیمت‌ها...")
                session.close()
                if reset_price_simulator():
                    logger.info("✅ ریست خودکار موفقیت‌آمیز بود")
                else:
                    logger.error("❌ خطا در ریست خودکار")
                    return
            else:
                session.close()
                logger.info("✅ قیمت‌های NCC همسان هستند")
        except Exception as e:
            session.close()
            logger.error(f"❌ خطا در بررسی قیمت‌ها: {str(e)}")
        
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
