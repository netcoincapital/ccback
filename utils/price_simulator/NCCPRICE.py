import sys, os
# اضافه کردن مسیر اصلی پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# از utils/price_simulator به CC directory (یعنی 2 سطح بالا)
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
# اضافه کردن parent directory که شامل CC است
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

# تغییر مسیر کاری به CC directory
os.chdir(project_root)

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

# تنظیم لاگر با استفاده از ماژول لاگینگ پروژه
try:
    logger = get_logger(__file__)
    logger.info("📊 راه‌اندازی ماژول شبیه‌ساز قیمت NCC")
except Exception as e:
    # اگر لاگر اصلی مشکل دارد، از لاگر پایه استفاده کن
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger('NCCPRICE')
    logger.error(f"❌ خطا در راه‌اندازی لاگر اصلی: {str(e)}")
    logger.info("📊 راه‌اندازی ماژول شبیه‌ساز قیمت NCC با لاگر پایه")

# تنظیمات قیمت - الگوریتم کانال طبیعی با نوسانات
START_PRICE = 0.22      # قیمت شروع: 22 سنت
TARGET_PRICE = 0.80     # قیمت هدف: 80 سنت
DURATION_MONTHS = 9     # مدت زمان: 9 ماه
DURATION_DAYS = 270     # 9 ماه = 270 روز
MIN_CHANNEL_PERCENT = 0.40  # حداقل 40% پیشرفت در کانال
MAX_CHANNEL_PERCENT = 0.60  # حداکثر 60% پیشرفت در کانال

# تنظیمات نوسانات طبیعی
MAX_DROP_PERCENT = 0.30     # حداکثر 30% کاهش از بالاترین قیمت
MIN_DROP_PERCENT = 0.20     # حداقل 20% کاهش از بالاترین قیمت
VOLATILITY_CYCLES = [30, 45, 60, 90]  # چرخه‌های نوسان (روز)

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

# متغیرهای نوسانات طبیعی
highest_price_ever = START_PRICE  # بالاترین قیمت تاریخی
current_cycle_phase = "growth"    # فاز فعلی: "growth" یا "correction"
cycle_start_time = None          # زمان شروع فاز فعلی
next_cycle_duration = random.choice(VOLATILITY_CYCLES)  # مدت فاز بعدی

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_ncc():
    """
    مقداردهی اولیه توکن‌های NCC - جستجو برای هر دو آیدی 8517 و 8519
    """
    global NCC_CURRENCY_IDS
    session = Session()
    found_currencies = []
    
    try:
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
            return True
        else:
            NCC_CURRENCY_IDS = []
            logger.error("❌ هیچ توکن NCC در دیتابیس یافت نشد")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در مقداردهی اولیه NCC: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()

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
    try:
        # استفاده از اولین شناسه ارز برای دریافت قیمت - تبدیل به string
        currency_id_str = str(NCC_CURRENCY_IDS[0])
        price = session.query(Price).filter(
            Price.crypto_id == currency_id_str,
            Price.currency == fiat
        ).order_by(Price.last_updated.desc()).first()
        
        if price:
            logger.debug(f"📊 قیمت فعلی برای NCC (ID: {currency_id_str}) به {fiat}: {float(price.price)} {FIAT_CURRENCIES.get(fiat, '')}")
            return float(price.price)
        else:
            logger.debug(f"⚠️ هیچ قیمتی برای NCC (ID: {currency_id_str}) به {fiat} در دیتابیس پیدا نشد")
            return None
    except Exception as e:
        logger.error(f"❌ خطا در دریافت قیمت فعلی: {str(e)}")
        session.rollback()
        return None
    finally:
        session.close()

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
            # اگر هیچ قیمتی یافت نشد، از قیمت شروع استفاده می‌کنیم
            return START_PRICE
    finally:
        session.close()

def calculate_channel_bounds(days_passed):
    """
    محاسبه کانال قیمت بر اساس روزهای گذشته
    
    Args:
        days_passed: تعداد روزهای گذشته از شروع
        
    Returns:
        tuple: (min_price, max_price, ideal_price)
    """
    # محاسبه پیشرفت (0 تا 1)
    progress = min(days_passed / DURATION_DAYS, 1.0)
    
    # قیمت ایده‌آل بر اساس پیشرفت زمانی
    ideal_price = START_PRICE + (TARGET_PRICE - START_PRICE) * progress
    
    # محاسبه رشد کل تا این نقطه
    total_growth_so_far = (ideal_price - START_PRICE) / START_PRICE
    
    # محاسبه کانال (40% تا 60% از رشد کل)
    min_growth = total_growth_so_far * MIN_CHANNEL_PERCENT
    max_growth = total_growth_so_far * MAX_CHANNEL_PERCENT
    
    min_price = START_PRICE * (1 + min_growth)
    max_price = START_PRICE * (1 + max_growth)
    
    # اطمینان از حداقل‌ها
    min_price = max(min_price, START_PRICE)
    max_price = max(max_price, START_PRICE)
    
    return min_price, max_price, ideal_price

def determine_market_phase(days_passed):
    """
    تعیین فاز بازار (رشد یا اصلاح) بر اساس چرخه‌های طبیعی
    
    Args:
        days_passed: روزهای گذشته از شروع
        
    Returns:
        tuple: (phase, phase_progress, target_correction)
    """
    global current_cycle_phase, cycle_start_time, next_cycle_duration
    
    if cycle_start_time is None:
        cycle_start_time = datetime.now()
        current_cycle_phase = "growth"
        next_cycle_duration = random.choice(VOLATILITY_CYCLES)
    
    # محاسبه زمان گذشته از شروع فاز فعلی
    phase_days = (datetime.now() - cycle_start_time).total_seconds() / (24 * 3600)
    
    # اگر فاز فعلی تمام شد، تغییر فاز
    if phase_days >= next_cycle_duration:
        if current_cycle_phase == "growth":
            current_cycle_phase = "correction"
            next_cycle_duration = random.randint(7, 21)  # اصلاح 1-3 هفته
        else:
            current_cycle_phase = "growth"
            next_cycle_duration = random.choice(VOLATILITY_CYCLES)
        
        cycle_start_time = datetime.now()
        phase_days = 0
        logger.info(f"🔄 تغییر فاز بازار به: {current_cycle_phase} برای {next_cycle_duration} روز")
    
    phase_progress = phase_days / next_cycle_duration
    
    # محاسبه هدف اصلاح
    if current_cycle_phase == "correction":
        correction_percent = MIN_DROP_PERCENT + (MAX_DROP_PERCENT - MIN_DROP_PERCENT) * random.random()
        target_correction = correction_percent
    else:
        target_correction = 0
    
    return current_cycle_phase, phase_progress, target_correction

def generate_price():
    """
    تولید قیمت جدید با الگوریتم طبیعی شامل رشد و اصلاحات
    قیمت در 9 ماه از 22 سنت به 80 سنت با نوسانات واقعی
    
    Returns:
        tuple: قیمت جدید و درصد تغییر 24 ساعته
    """
    global price_history, last_updated, highest_price_ever
    now = datetime.now()

    # بررسی قیمت فعلی در دیتابیس برای اطمینان از شروع صحیح
    current_db_price = get_current_price("USD")
    
    # اولین اجرا یا اگر قیمت در دیتابیس بالاتر از حد مجاز است - ریست کامل
    if not price_history or (current_db_price and current_db_price > TARGET_PRICE * 2):
        if current_db_price and current_db_price > TARGET_PRICE * 2:
            logger.warning(f"⚠️ قیمت فعلی در دیتابیس بسیار بالا است: ${current_db_price:.6f} - ریست کامل انجام می‌شود")
            # ریست کامل متغیرهای global
            price_history = []
            highest_price_ever = START_PRICE
            last_updated = None
        
        logger.info(f"🆕 شروع الگوریتم طبیعی NCC از ${START_PRICE:.2f} به ${TARGET_PRICE:.2f} در {DURATION_MONTHS} ماه")
        logger.info(f"📊 نوسانات: {MIN_DROP_PERCENT*100:.0f}%-{MAX_DROP_PERCENT*100:.0f}% کاهش در چرخه‌های طبیعی")
        
        price_history.append((now, START_PRICE))
        last_updated = now
        highest_price_ever = START_PRICE
        
        change_24h = 0.0
        logger.info(f"🆕 قیمت پایه NCC: ${START_PRICE:.6f}")
        return START_PRICE, change_24h

    # محاسبه زمان گذشته
    start_time = price_history[0][0]
    days_passed = (now - start_time).total_seconds() / (24 * 3600)
    
    # اگر 9 ماه گذشته، قیمت را روی 80 سنت ثابت نگه دار
    if days_passed >= DURATION_DAYS:
        new_price = TARGET_PRICE
        logger.info(f"🎯 9 ماه تکمیل شد - قیمت نهایی: ${TARGET_PRICE:.2f}")
    else:
        # محاسبه کانال اصلی و قیمت ایده‌آل
        min_price, max_price, ideal_price = calculate_channel_bounds(days_passed)
        
        # تعیین فاز بازار
        market_phase, phase_progress, target_correction = determine_market_phase(days_passed)
        
        last_price = price_history[-1][1]
        
        if market_phase == "growth":
            # فاز رشد - حرکت به سمت قیمت ایده‌آل یا بالاتر
            growth_target = min(ideal_price * 1.1, max_price)  # تا 10% بالاتر از ایده‌آل
            trend_component = (growth_target - last_price) * 0.15  # 15% حرکت به سمت هدف
            
            # نوسانات مثبت بیشتر
            volatility = (max_price - min_price) * 0.03  # 3% نوسان
            noise_component = random.uniform(-volatility * 0.3, volatility)  # بیشتر مثبت
            
        else:  # correction phase
            # فاز اصلاح - کاهش قوی‌تر از ATH
            correction_target = highest_price_ever * (1 - target_correction)
            correction_target = max(correction_target, min_price)  # نباید زیر کانال برود
            
            trend_component = (correction_target - last_price) * 0.6  # 60% حرکت به سمت اصلاح
            
            # نوسانات منفی قوی‌تر برای اصلاح طبیعی
            volatility = (max_price - min_price) * 0.03
            noise_component = random.uniform(-volatility * 1.2, volatility * 0.2)  # بیشتر منفی
        
        # محاسبه قیمت جدید
        new_price = last_price + trend_component + noise_component
        
        # اطمینان از ماندن در کانال کلی
        new_price = max(min_price, min(new_price, max_price))
        
        # محدود کردن تغییرات شدید (حداکثر 3% در 15 دقیقه)
        max_change = last_price * 0.03
        new_price = max(last_price - max_change, min(new_price, last_price + max_change))
        
        # به‌روزرسانی بالاترین قیمت
        if new_price > highest_price_ever:
            highest_price_ever = new_price

    # محاسبه درصد تغییر 24 ساعته
    price_24h_ago = last_price
    if len(price_history) >= 96:  # 96 = 24 ساعت * 4 (هر 15 دقیقه)
        price_24h_ago = price_history[-96][1]
    elif len(price_history) > 1:
        price_24h_ago = price_history[0][1]
    
    change_24h = ((new_price / price_24h_ago - 1) * 100)

    # حذف تاریخچه قدیمی
    if len(price_history) > 500:
        price_history = price_history[-500:]

    price_history.append((now, new_price))
    last_updated = now

    # لاگ جزئیات
    progress_percent = min(days_passed / DURATION_DAYS * 100, 100)
    change_sign = "+" if change_24h > 0 else ""
    phase_icon = "📈" if market_phase == "growth" else "📉"
    
    # لاگ اضافی برای دیباگ
    logger.debug(f"محاسبه تغییر بر اساس تاریخچه داخلی: ${last_price:.8f} -> ${new_price:.8f}")
    logger.info(f"{phase_icon} NCC: ${new_price:.6f} | فاز: {market_phase} | ATH: ${highest_price_ever:.6f} | پیشرفت: {progress_percent:.1f}% | 24h: {change_sign}{change_24h:.2f}%")
    
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
    ریست کردن شبیه‌ساز قیمت NCC به حالت اولیه (22 سنت)
    """
    global price_history, last_updated, highest_price_ever, current_cycle_phase, cycle_start_time, next_cycle_duration
    logger.info("🔄 ریست کردن شبیه‌ساز قیمت NCC به حالت اولیه...")

    # پاک کردن تاریخچه قیمت و متغیرهای نوسان
    price_history = []
    last_updated = None
    highest_price_ever = START_PRICE
    current_cycle_phase = "growth"
    cycle_start_time = None
    next_cycle_duration = random.choice(VOLATILITY_CYCLES)

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

    # ثبت قیمت اولیه (22 سنت) با الگوریتم کانال صعودی
    usd_price = START_PRICE  # شروع از 22 سنت
    change = 0.0
    if update_price(usd_price, change):
        logger.info(f"✅ الگوریتم کانال صعودی ریست شد - شروع: ${START_PRICE:.2f} → هدف: ${TARGET_PRICE:.2f} ({DURATION_MONTHS} ماه)")
        return True
    else:
        logger.error("❌ خطا در ریست کردن الگوریتم کانال صعودی")
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
            
            # اگر قیمت‌ها متفاوت هستند یا زیر قیمت شروع (22 سنت) هستند، ریست کن
            need_reset = False
            if prices_8517 and prices_8519:
                price_8517 = float(prices_8517.price)
                price_8519 = float(prices_8519.price)
                if abs(price_8517 - price_8519) > 0.001 or price_8517 < START_PRICE or price_8519 < START_PRICE:
                    logger.warning(f"⚠️ قیمت‌های NCC متفاوت هستند یا زیر حداقل: 8517=${price_8517:.8f}, 8519=${price_8519:.8f}")
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
        
        # زمانبندی اجرای دوره‌ای - هر 15 دقیقه برای رشد طبیعی‌تر
        schedule.every(15).minutes.do(run_price_update)
        logger.info("⏱️ زمانبندی به‌روزرسانی هر 15 دقیقه تنظیم شد")
        
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
