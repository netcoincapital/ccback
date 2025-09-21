#!/usr/bin/env python3
"""
تست سیستم جدید insert قیمت‌ها
Test new price insertion system
"""

import sys
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine
from database.prices import Price

def test_new_price_insertion():
    """تست insert رکوردهای جدید"""
    
    print("="*60)
    print("🧪 تست سیستم جدید insert قیمت‌ها")
    print("="*60)
    
    session = Session(bind=engine)
    
    try:
        # شمارش رکوردهای فعلی
        current_count = session.query(Price).filter_by(crypto_id='1', currency='USD').count()
        print(f"📊 تعداد رکوردهای فعلی BTC: {current_count}")
        
        # ایجاد چند رکورد تست با timestamp های مختلف
        test_timestamps = [
            datetime.now() - timedelta(hours=3),
            datetime.now() - timedelta(hours=2), 
            datetime.now() - timedelta(hours=1),
            datetime.now()
        ]
        
        test_prices = [65000.00, 65150.25, 64980.50, 65432.50]
        
        print(f"\n🔄 ایجاد {len(test_timestamps)} رکورد تست...")
        
        for i, (timestamp, price) in enumerate(zip(test_timestamps, test_prices)):
            try:
                new_price = Price(
                    crypto_id='1',  # BTC
                    currency='USD',
                    price=price,
                    market_cap=price * 19500000,  # تقریبی
                    volume_24h=25000000000,
                    change_1h=0.15,
                    change_24h=2.45,
                    change_7d=-1.25,
                    timestamp=timestamp,
                    is_historical=True,
                    last_updated=timestamp
                )
                
                session.add(new_price)
                session.commit()
                
                print(f"   ✅ رکورد {i+1}: ${price:,.2f} در {timestamp.strftime('%H:%M:%S')}")
                
            except Exception as e:
                session.rollback()
                print(f"   ❌ خطا در رکورد {i+1}: {str(e)}")
        
        # بررسی نتایج
        new_count = session.query(Price).filter_by(crypto_id='1', currency='USD').count()
        print(f"\n📈 تعداد رکوردهای جدید BTC: {new_count}")
        print(f"📊 رکوردهای اضافه شده: {new_count - current_count}")
        
        # نمایش آخرین رکوردها
        latest_records = session.query(Price).filter_by(
            crypto_id='1', currency='USD'
        ).order_by(Price.timestamp.desc()).limit(5).all()
        
        print(f"\n📋 آخرین 5 رکورد BTC:")
        for i, record in enumerate(latest_records, 1):
            timestamp_str = record.timestamp.strftime('%Y-%m-%d %H:%M:%S') if record.timestamp else 'None'
            print(f"   {i}. ${record.price:,.2f} - {timestamp_str} - Historical: {record.is_historical}")
        
        # تست امکان ساخت چارت
        if new_count >= 4:
            print(f"\n✅ امکان ساخت چارت: بله ({new_count} نقطه داده)")
        else:
            print(f"\n❌ امکان ساخت چارت: خیر (کمتر از 4 نقطه)")
            
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")
        session.rollback()
    finally:
        session.close()

def create_hourly_scheduler():
    """ایجاد scheduler ساعتی برای قیمت‌ها"""
    
    print(f"\n" + "="*60)
    print("⏰ ایجاد Scheduler ساعتی")
    print("="*60)
    
    scheduler_code = '''#!/usr/bin/env python3
"""
Scheduler ساعتی برای ذخیره قیمت‌های تاریخی
Hourly scheduler for historical price storage
"""

import time
import schedule
from datetime import datetime
from sqlalchemy.orm import Session
from database import engine
from database.prices import Price
from Currencies.currency_price_service import CurrencyPriceService

def save_hourly_prices():
    """ذخیره قیمت‌های ساعتی"""
    
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - شروع ذخیره قیمت‌های ساعتی")
    
    session = Session(bind=engine)
    price_service = CurrencyPriceService()
    
    try:
        # لیست ارزهای مهم
        important_currencies = [
            '1',   # BTC
            '16',  # ETH  
            '3',   # BNB
            '10',  # ADA
            '11',  # SOL
            '12',  # XRP
            '14',  # MATIC
            '18',  # XLM
            '19',  # LINK
            '20',  # DOT
            '21'   # UNI
        ]
        
        current_time = datetime.now()
        success_count = 0
        
        for crypto_id in important_currencies:
            try:
                # فرض: دریافت قیمت فعلی (باید از API واقعی بیاید)
                # اینجا فقط برای تست از قیمت فعلی استفاده می‌کنیم
                
                # دریافت آخرین قیمت
                latest_price = session.query(Price).filter_by(
                    crypto_id=crypto_id, 
                    currency='USD',
                    is_historical=False
                ).first()
                
                if latest_price:
                    # ایجاد رکورد تاریخی جدید
                    historical_price = Price(
                        crypto_id=crypto_id,
                        currency='USD',
                        price=latest_price.price,
                        market_cap=latest_price.market_cap,
                        volume_24h=latest_price.volume_24h,
                        change_1h=latest_price.change_1h,
                        change_24h=latest_price.change_24h,
                        change_7d=latest_price.change_7d,
                        timestamp=current_time,
                        is_historical=True,
                        last_updated=current_time
                    )
                    
                    session.add(historical_price)
                    session.commit()
                    success_count += 1
                    
                    print(f"   ✅ {crypto_id}: ${latest_price.price:,.2f}")
                
            except Exception as e:
                session.rollback()
                print(f"   ❌ خطا در {crypto_id}: {str(e)}")
        
        print(f"✅ ذخیره شد: {success_count}/{len(important_currencies)} ارز")
        
    except Exception as e:
        print(f"❌ خطای کلی: {str(e)}")
        session.rollback()
    finally:
        session.close()

def run_scheduler():
    """اجرای scheduler"""
    
    print("🚀 راه‌اندازی Scheduler ساعتی")
    
    # زمان‌بندی هر ساعت
    schedule.every().hour.at(":00").do(save_hourly_prices)
    
    # اجرای فوری برای تست
    print("🧪 اجرای فوری برای تست...")
    save_hourly_prices()
    
    print("⏰ منتظر زمان‌بندی ساعتی...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # بررسی هر دقیقه

if __name__ == "__main__":
    run_scheduler()
'''
    
    # ذخیره کد scheduler
    with open('hourly_price_scheduler.py', 'w', encoding='utf-8') as f:
        f.write(scheduler_code)
    
    print(f"💾 Scheduler ساعتی در فایل hourly_price_scheduler.py ذخیره شد")
    
    print(f"\n🔄 برای راه‌اندازی:")
    print("   python hourly_price_scheduler.py")

def main():
    # تست سیستم جدید
    test_new_price_insertion()
    
    # ایجاد scheduler
    create_hourly_scheduler()
    
    print(f"\n" + "="*60)
    print("📋 خلاصه اصلاحات")
    print("="*60)
    
    print("✅ تغییرات اعمال شده:")
    print("   1. حذف منطق UPDATE موجود")
    print("   2. اضافه کردن INSERT همیشگی") 
    print("   3. timestamp منحصر به فرد برای هر رکورد")
    print("   4. علامت‌گذاری is_historical=True")
    
    print(f"\n🎯 نتیجه:")
    print("   - هر بار قیمت آپدیت شود، رکورد جدید ایجاد می‌شود")
    print("   - تاریخچه کامل قیمت‌ها حفظ می‌شود")
    print("   - امکان ساخت چارت‌های تاریخی فراهم می‌شود")

if __name__ == "__main__":
    main()
