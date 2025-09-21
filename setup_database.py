#!/usr/bin/env python3
"""
راه‌اندازی دیتابیس برای داده‌های تاریخی
Database setup for historical data
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from database import engine
from database.prices import Price
from database.Currencies import Currencies

def setup_database():
    """راه‌اندازی دیتابیس"""
    
    print("🔧 راه‌اندازی دیتابیس...")
    
    try:
        # ایجاد جداول
        from database.base import Base
        Base.metadata.create_all(bind=engine)
        print("✅ جداول ایجاد شد")
        
        # بررسی وجود داده‌ها
        session = Session(bind=engine)
        
        currencies_count = session.query(Currencies).count()
        prices_count = session.query(Price).count()
        
        print(f"📊 آمار فعلی:")
        print(f"   ارزها: {currencies_count}")
        print(f"   قیمت‌ها: {prices_count}")
        
        # بررسی ایندکس‌ها
        print(f"\n🔍 بررسی ایندکس‌های مهم...")
        
        # بررسی ایندکس timestamp
        result = session.execute(text("SHOW INDEX FROM prices WHERE Key_name = 'timestamp_idx'"))
        timestamp_index = result.fetchall()
        
        if timestamp_index:
            print("   ✅ ایندکس timestamp موجود است")
        else:
            print("   ⚠️ ایندکس timestamp موجود نیست - ایجاد می‌شود...")
            session.execute(text("CREATE INDEX timestamp_idx ON prices (timestamp)"))
            session.commit()
        
        session.close()
        
        return True
        
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی: {str(e)}")
        return False

def verify_setup():
    """تایید راه‌اندازی"""
    
    print(f"\n🔍 تایید راه‌اندازی...")
    
    try:
        session = Session(bind=engine)
        
        # تست insert یک رکورد
        from datetime import datetime
        
        test_record = Price(
            crypto_id='999',  # ID تست
            currency='USD',
            price=1000.0,
            timestamp=datetime.now(),
            is_historical=True,
            last_updated=datetime.now()
        )
        
        session.add(test_record)
        session.commit()
        
        # حذف رکورد تست
        session.delete(test_record)
        session.commit()
        session.close()
        
        print("✅ تست insert/delete موفق")
        return True
        
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 راه‌اندازی سیستم داده‌های تاریخی")
    print("="*50)
    
    if setup_database():
        if verify_setup():
            print("\n🎉 راه‌اندازی موفق!")
            print("حالا می‌توانید historical_data_fetcher_1year.py را اجرا کنید")
        else:
            print("\n❌ مشکل در تست راه‌اندازی")
    else:
        print("\n❌ مشکل در راه‌اندازی دیتابیس")
