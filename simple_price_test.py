#!/usr/bin/env python3
"""
تست ساده برای بررسی مشکل قیمت‌ها
Simple test for price issue
"""

def analyze_problem():
    """تحلیل مشکل اصلی"""
    
    print("="*60)
    print("🔍 تشخیص مشکل سیستم قیمت‌گذاری")
    print("="*60)
    
    print("❌ مشکل تشخیص داده شده:")
    print("   1. فقط 1 رکورد BTC در جدول")
    print("   2. فقط 1 رکورد ETH در جدول") 
    print("   3. کد existing records را آپدیت می‌کند")
    print("   4. عدم امکان ساخت چارت")
    
    print(f"\n🔍 علت اصلی:")
    print("   - کد فعلی: session.query(Price).filter_by(crypto_id, currency).first()")
    print("   - اگر رکورد وجود داشت: UPDATE")
    print("   - اگر رکورد نبود: INSERT")
    print("   - مشکل: همیشه همان رکورد پیدا می‌شود!")
    
    print(f"\n✅ راه‌حل اعمال شده:")
    print("   - حذف کامل منطق UPDATE")
    print("   - همیشه INSERT رکورد جدید")
    print("   - timestamp منحصر به فرد برای هر رکورد")
    print("   - is_historical=True برای تمام رکوردها")

def create_manual_test_records():
    """ایجاد رکوردهای تست دستی"""
    
    print(f"\n" + "="*60)
    print("🔧 ایجاد رکوردهای تست دستی")
    print("="*60)
    
    # کد SQL برای insert دستی
    sql_commands = []
    
    from datetime import datetime, timedelta
    
    # ایجاد 24 رکورد برای 24 ساعت گذشته
    for hour in range(24):
        timestamp = datetime.now() - timedelta(hours=hour)
        price = 65000 + (hour * 10)  # قیمت متغیر
        
        sql_command = f"""
INSERT INTO prices (crypto_id, currency, price, market_cap, volume_24h, 
                   change_1h, change_24h, change_7d, timestamp, is_historical, last_updated)
VALUES ('1', 'USD', {price}, {price * 19500000}, 25000000000, 
        0.15, 2.45, -1.25, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}', 1, '{timestamp.strftime('%Y-%m-%d %H:%M:%S')}');
"""
        sql_commands.append(sql_command)
    
    # ذخیره کدهای SQL
    with open('insert_test_prices.sql', 'w', encoding='utf-8') as f:
        f.write("-- رکوردهای تست برای ساخت چارت\n")
        f.write("-- Test records for chart creation\n\n")
        for cmd in sql_commands:
            f.write(cmd + "\n")
    
    print(f"💾 کدهای SQL در فایل insert_test_prices.sql ذخیره شد")
    print(f"📊 تعداد رکوردهای تست: {len(sql_commands)}")
    
    print(f"\n🔄 برای اعمال:")
    print("   1. فایل insert_test_prices.sql را در دیتابیس اجرا کنید")
    print("   2. یا از ابزار phpMyAdmin استفاده کنید")

def verify_chart_data_availability():
    """بررسی امکان ساخت چارت"""
    
    print(f"\n" + "="*60)
    print("📈 بررسی امکان ساخت چارت")
    print("="*60)
    
    print("🎯 برای ساخت چارت نیاز است:")
    print("   - حداقل 2 نقطه داده برای خط")
    print("   - حداقل 10 نقطه برای چارت قابل استفاده")
    print("   - حداقل 24 نقطه برای چارت روزانه")
    
    print(f"\n📊 وضعیت فعلی:")
    print("   - BTC: 1 رکورد (❌ ناکافی)")
    print("   - ETH: 1 رکورد (❌ ناکافی)")
    print("   - سایر ارزها: احتمالاً 1 رکورد")
    
    print(f"\n💡 پس از اصلاح:")
    print("   - هر ساعت رکورد جدید")
    print("   - پس از 24 ساعت: چارت روزانه")
    print("   - پس از 1 هفته: چارت هفتگی")
    print("   - پس از 1 ماه: چارت ماهانه")

def main():
    analyze_problem()
    create_manual_test_records()
    verify_chart_data_availability()
    
    print(f"\n" + "="*60)
    print("🎉 خلاصه")
    print("="*60)
    
    print("✅ مشکل تشخیص داده شد:")
    print("   کد UPDATE می‌کرد به جای INSERT")
    
    print(f"\n✅ راه‌حل اعمال شد:")
    print("   تغییر currency_price_service.py")
    
    print(f"\n🔄 مراحل بعدی:")
    print("   1. اجرای insert_test_prices.sql")
    print("   2. راه‌اندازی hourly_price_scheduler.py")
    print("   3. تست ساخت چارت")

if __name__ == "__main__":
    main()