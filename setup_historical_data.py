#!/usr/bin/env python3
"""
راه‌اندازی سیستم داده‌های تاریخی
Setup historical data system
"""

import os
import sys
from datetime import datetime, timedelta

def create_env_template():
    """ایجاد فایل .env نمونه"""
    
    env_content = '''# API Keys for Historical Data Fetcher
# کلیدهای API برای دریافت اطلاعات تاریخی

# CoinMarketCap API Key (required)
CMC_API_KEY=your_coinmarketcap_api_key_here

# CoinGecko API Key (optional, for backup)
COINGECKO_API_KEY=your_coingecko_api_key_here

# Etherscan API Keys (for blockchain data)
ETHERSCAN_API_KEY=77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY,BCTHDT3BE3MXPM8HFH61GEBK6QNR33IY3V,MZK8AEDPYRDA2GB91K6VUQYMUTSU6JBI5W

# Database settings (if needed)
# DATABASE_URL=sqlite:///coincee.db
'''
    
    with open('.env.template', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"💾 فایل .env.template ایجاد شد")

def create_requirements():
    """ایجاد فایل requirements"""
    
    requirements = '''# Requirements for Historical Data Fetcher
# متطلبات برای دریافت‌کننده اطلاعات تاریخی

# Core dependencies
requests>=2.28.0
python-dotenv>=0.19.0
sqlalchemy>=1.4.0
schedule>=1.2.0

# Database drivers
# For MySQL/MariaDB
pymysql>=1.0.0

# For PostgreSQL
# psycopg2-binary>=2.9.0

# For SQLite (built-in)
# No additional package needed

# Optional for better performance
urllib3>=1.26.0

# For decimal calculations
# decimal is built-in

# For datetime operations
# datetime is built-in
'''
    
    with open('requirements_historical.txt', 'w', encoding='utf-8') as f:
        f.write(requirements)
    
    print(f"💾 فایل requirements_historical.txt ایجاد شد")

def create_database_setup():
    """ایجاد اسکریپت راه‌اندازی دیتابیس"""
    
    setup_code = '''#!/usr/bin/env python3
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
        print(f"\\n🔍 بررسی ایندکس‌های مهم...")
        
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
    
    print(f"\\n🔍 تایید راه‌اندازی...")
    
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
            print("\\n🎉 راه‌اندازی موفق!")
            print("حالا می‌توانید historical_data_fetcher_1year.py را اجرا کنید")
        else:
            print("\\n❌ مشکل در تست راه‌اندازی")
    else:
        print("\\n❌ مشکل در راه‌اندازی دیتابیس")
'''
    
    with open('setup_database.py', 'w', encoding='utf-8') as f:
        f.write(setup_code)
    
    print(f"💾 فایل setup_database.py ایجاد شد")

def create_manual_sql_insert():
    """ایجاد فایل SQL برای insert دستی"""
    
    print(f"📝 ایجاد فایل SQL برای insert دستی...")
    
    # ایجاد 24 رکورد تست برای BTC
    sql_commands = []
    
    base_price = 65000
    
    for hour in range(24):
        timestamp = datetime.now() - timedelta(hours=hour)
        price = base_price + (hour * 50) - 600  # تغییرات قیمت واقعی‌تر
        market_cap = price * 19500000
        volume = 25000000000 + (hour * 1000000000)
        
        sql_command = f"""INSERT INTO prices (crypto_id, currency, price, market_cap, volume_24h, change_1h, change_24h, change_7d, timestamp, is_historical, last_updated)
VALUES ('1', 'USD', {price:.2f}, {market_cap:.2f}, {volume:.2f}, 0.15, 2.45, -1.25, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}', 1, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}');"""
        
        sql_commands.append(sql_command)
    
    # ایجاد رکوردهای ETH
    for hour in range(24):
        timestamp = datetime.now() - timedelta(hours=hour)
        price = 4400 + (hour * 10) - 120
        market_cap = price * 120000000
        volume = 15000000000 + (hour * 500000000)
        
        sql_command = f"""INSERT INTO prices (crypto_id, currency, price, market_cap, volume_24h, change_1h, change_24h, change_7d, timestamp, is_historical, last_updated)
VALUES ('16', 'USD', {price:.2f}, {market_cap:.2f}, {volume:.2f}, -0.25, 1.85, 3.25, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}', 1, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}');"""
        
        sql_commands.append(sql_command)
    
    # ذخیره فایل SQL
    with open('insert_24h_test_data.sql', 'w', encoding='utf-8') as f:
        f.write("-- رکوردهای تست 24 ساعته برای BTC و ETH\n")
        f.write("-- 24-hour test records for BTC and ETH\n\n")
        
        for cmd in sql_commands:
            f.write(cmd + "\n")
    
    print(f"💾 فایل insert_24h_test_data.sql ایجاد شد")
    print(f"📊 شامل {len(sql_commands)} رکورد (24 BTC + 24 ETH)")

def main():
    print("🚀 راه‌اندازی سیستم داده‌های تاریخی")
    print("Historical Data System Setup")
    print("="*60)
    
    # ایجاد فایل‌های مورد نیاز
    create_env_template()
    create_requirements()
    create_database_setup()
    create_manual_sql_insert()
    
    print(f"\n✅ فایل‌های ایجاد شده:")
    print("   1. historical_data_fetcher_1year.py - فچر اصلی")
    print("   2. .env.template - نمونه تنظیمات")
    print("   3. requirements_historical.txt - وابستگی‌ها")
    print("   4. setup_database.py - راه‌اندازی دیتابیس")
    print("   5. insert_24h_test_data.sql - داده‌های تست")
    print("   6. quick_historical_test.py - تست سریع")
    
    print(f"\n🔄 مراحل اجرا:")
    print("1. نصب وابستگی‌ها: pip install -r requirements_historical.txt")
    print("2. تنظیم .env با کلیدهای API")
    print("3. راه‌اندازی دیتابیس: python setup_database.py")
    print("4. تست سریع: python quick_historical_test.py")
    print("5. اجرای کامل: python historical_data_fetcher_1year.py")
    
    print(f"\n💡 برای تست فوری:")
    print("   اجرای فایل insert_24h_test_data.sql در دیتابیس")

if __name__ == "__main__":
    main()
