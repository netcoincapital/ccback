#!/usr/bin/env python3
"""
تست همگام‌سازی قیمت‌های NCC
این اسکریپت بررسی می‌کند که آیا هر دو توکن NCC قیمت یکسان دارند یا خیر
"""

import sys
import os
from decimal import Decimal
from datetime import datetime

# اضافه کردن مسیر اصلی پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from CC.database.prices import Price
from CC.utils.logging_config import get_logger

# تنظیم لاگر
logger = get_logger(__file__)

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://coincee:09387270277Mn!!??@localhost/coincee")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def check_ncc_prices():
    """
    بررسی قیمت‌های NCC و مقایسه آن‌ها
    """
    session = Session()
    try:
        logger.info("🔍 بررسی قیمت‌های NCC...")
        
        # دریافت قیمت‌های USD برای هر دو NCC
        price_8517 = session.query(Price).filter(
            Price.crypto_id == '8517',
            Price.currency == 'USD'
        ).first()
        
        price_8519 = session.query(Price).filter(
            Price.crypto_id == '8519', 
            Price.currency == 'USD'
        ).first()
        
        print("=" * 60)
        print("📊 گزارش قیمت‌های NCC")
        print("=" * 60)
        
        if price_8517:
            print(f"💰 NCC 8517 (USD): ${float(price_8517.price):.8f}")
            print(f"   📅 آخرین به‌روزرسانی: {price_8517.last_updated}")
            print(f"   📈 تغییر 24 ساعته: {float(price_8517.change_24h):.2f}%")
        else:
            print("❌ قیمت NCC 8517 یافت نشد")
            
        if price_8519:
            print(f"💰 NCC 8519 (USD): ${float(price_8519.price):.8f}")
            print(f"   📅 آخرین به‌روزرسانی: {price_8519.last_updated}")
            print(f"   📈 تغییر 24 ساعته: {float(price_8519.change_24h):.2f}%")
        else:
            print("❌ قیمت NCC 8519 یافت نشد")
            
        print("-" * 60)
        
        # مقایسه قیمت‌ها
        if price_8517 and price_8519:
            diff = abs(float(price_8517.price) - float(price_8519.price))
            if diff < 0.00000001:  # تفاوت کمتر از 1 satoshi
                print("✅ قیمت‌های NCC کاملاً همسان هستند")
                return True
            else:
                print(f"⚠️ قیمت‌های NCC متفاوت هستند - اختلاف: ${diff:.8f}")
                return False
        else:
            print("❌ نمی‌توان قیمت‌ها را مقایسه کرد - یکی از قیمت‌ها موجود نیست")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا در بررسی قیمت‌ها: {str(e)}")
        return False
    finally:
        session.close()

def main():
    """
    تابع اصلی تست
    """
    logger.info("==================== شروع تست همگام‌سازی NCC ====================")
    
    try:
        result = check_ncc_prices()
        if result:
            logger.info("✅ تست موفقیت‌آمیز - قیمت‌ها همسان هستند")
        else:
            logger.warning("⚠️ تست ناموفق - قیمت‌ها همسان نیستند")
        return result
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        return False
    finally:
        logger.info("==================== پایان تست همگام‌سازی NCC ====================")

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 