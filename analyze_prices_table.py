#!/usr/bin/env python3
"""
تحلیل جدول prices برای تشخیص مشکل
Analyze prices table to detect issues
"""

import re
from datetime import datetime
from collections import defaultdict

def analyze_prices_sql():
    """تحلیل فایل SQL جدول prices"""
    
    print("="*60)
    print("🔍 تحلیل جدول Prices")
    print("="*60)
    
    try:
        with open('1/prices(7).sql', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # استخراج خطوط INSERT
        insert_lines = [line.strip() for line in content.split('\n') if line.strip().startswith('(') and 'USD' in line]
        
        print(f"📊 تعداد کل رکوردها: {len(insert_lines)}")
        
        # تحلیل رکوردهای BTC (crypto_id=1)
        btc_records = []
        eth_records = []
        
        for line in insert_lines:
            # استخراج اطلاعات با regex
            match = re.search(r"\((\d+), '(\d+)', '([^']+)', ([^,]+), [^,]*, [^,]*, [^,]*, [^,]*, [^,]*, '([^']+)'", line)
            if match:
                record_id, crypto_id, currency, price, last_updated = match.groups()
                
                if crypto_id == '1' and currency == 'USD':  # BTC
                    btc_records.append({
                        'id': record_id,
                        'price': float(price),
                        'date': last_updated
                    })
                elif crypto_id == '16' and currency == 'USD':  # ETH (معمولاً ID 16)
                    eth_records.append({
                        'id': record_id,
                        'price': float(price),
                        'date': last_updated
                    })
        
        print(f"\n🪙 رکوردهای BTC (USD): {len(btc_records)}")
        print(f"🪙 رکوردهای ETH (USD): {len(eth_records)}")
        
        # تحلیل تاریخ‌ها
        if btc_records:
            print(f"\n📅 تحلیل تاریخ‌های BTC:")
            dates = [record['date'] for record in btc_records]
            unique_dates = list(set([date.split()[0] for date in dates]))
            unique_dates.sort()
            
            for date in unique_dates:
                count = len([d for d in dates if d.startswith(date)])
                print(f"   {date}: {count} رکورد")
            
            # نمایش آخرین رکوردها
            print(f"\n📋 آخرین 5 رکورد BTC:")
            sorted_btc = sorted(btc_records, key=lambda x: x['date'], reverse=True)
            for i, record in enumerate(sorted_btc[:5], 1):
                print(f"   {i}. ID: {record['id']}, قیمت: ${record['price']:,.2f}, تاریخ: {record['date']}")
            
            # بررسی تکراری بودن
            print(f"\n🔄 بررسی تکراری بودن:")
            date_counts = defaultdict(int)
            for record in btc_records:
                date_only = record['date'].split()[0]
                date_counts[date_only] += 1
            
            for date, count in sorted(date_counts.items(), reverse=True):
                if count > 1:
                    print(f"   ⚠️ {date}: {count} رکورد (احتمال آپدیت به جای insert)")
                else:
                    print(f"   ✅ {date}: {count} رکورد (طبیعی)")
        
        # بررسی ساختار جدول
        print(f"\n🏗️ بررسی ساختار جدول:")
        create_table_match = re.search(r'CREATE TABLE `prices` \((.*?)\) ENGINE', content, re.DOTALL)
        if create_table_match:
            fields = create_table_match.group(1)
            print(f"   ✅ جدول شامل فیلد timestamp: {'timestamp' in fields}")
            print(f"   ✅ جدول شامل فیلد is_historical: {'is_historical' in fields}")
            
            # بررسی constraint ها
            if 'unique_crypto_currency_timestamp' in content:
                print(f"   ⚠️ Unique constraint موجود: ممکن است مانع insert شود")
            else:
                print(f"   ✅ Unique constraint مشکلی ندارد")
        
        return btc_records, eth_records
        
    except FileNotFoundError:
        print("❌ فایل SQL یافت نشد")
        return [], []
    except Exception as e:
        print(f"❌ خطا در تحلیل: {str(e)}")
        return [], []

def check_database_structure():
    """بررسی ساختار دیتابیس فعلی"""
    
    print(f"\n" + "="*60)
    print("🔍 بررسی ساختار دیتابیس فعلی")
    print("="*60)
    
    try:
        # بررسی فایل‌های دیتابیس موجود
        import os
        db_files = [f for f in os.listdir('.') if f.endswith('.db')]
        
        print(f"📁 فایل‌های دیتابیس موجود:")
        for db_file in db_files:
            size = os.path.getsize(db_file) / (1024*1024)  # MB
            print(f"   {db_file}: {size:.1f} MB")
        
        if 'coincee.db' in db_files:
            print(f"\n🔍 بررسی coincee.db...")
            
            import sqlite3
            conn = sqlite3.connect('coincee.db')
            cursor = conn.cursor()
            
            # بررسی ساختار جدول prices
            cursor.execute("PRAGMA table_info(prices)")
            columns = cursor.fetchall()
            
            print(f"📋 ستون‌های جدول prices:")
            for col in columns:
                print(f"   {col[1]}: {col[2]} ({'NOT NULL' if col[3] else 'NULL'})")
            
            # بررسی تعداد رکوردها
            cursor.execute("SELECT COUNT(*) FROM prices")
            total_records = cursor.fetchone()[0]
            print(f"\n📊 تعداد کل رکوردها: {total_records:,}")
            
            # بررسی رکوردهای BTC
            cursor.execute("""
                SELECT crypto_id, currency, COUNT(*) as count, 
                       MIN(last_updated) as first_date, 
                       MAX(last_updated) as last_date
                FROM prices 
                WHERE crypto_id = '1' AND currency = 'USD'
                GROUP BY crypto_id, currency
            """)
            
            btc_stats = cursor.fetchone()
            if btc_stats:
                print(f"\n🪙 آمار BTC:")
                print(f"   تعداد رکوردها: {btc_stats[2]}")
                print(f"   اولین رکورد: {btc_stats[3]}")
                print(f"   آخرین رکورد: {btc_stats[4]}")
            
            # بررسی رکوردهای تاریخی vs فعلی
            cursor.execute("""
                SELECT is_historical, COUNT(*) as count
                FROM prices 
                WHERE crypto_id = '1' AND currency = 'USD'
                GROUP BY is_historical
            """)
            
            hist_stats = cursor.fetchall()
            print(f"\n📈 توزیع رکوردها:")
            for is_hist, count in hist_stats:
                record_type = 'تاریخی' if is_hist else 'فعلی'
                print(f"   {record_type}: {count} رکورد")
            
            # بررسی رکوردهای امروز
            cursor.execute("""
                SELECT COUNT(*) 
                FROM prices 
                WHERE crypto_id = '1' AND currency = 'USD' 
                AND DATE(last_updated) = DATE('now')
            """)
            
            today_count = cursor.fetchone()[0]
            print(f"\n📅 رکوردهای امروز BTC: {today_count}")
            
            if today_count > 1:
                print(f"   ⚠️ بیش از یک رکورد امروز - احتمال آپدیت به جای insert")
            elif today_count == 1:
                print(f"   ✅ فقط یک رکورد امروز - طبیعی")
            else:
                print(f"   ❌ هیچ رکورد امروز - مشکل در به‌روزرسانی")
            
            conn.close()
            
        return True
        
    except Exception as e:
        print(f"❌ خطا در بررسی دیتابیس: {str(e)}")
        return False

def main():
    # تحلیل فایل SQL
    btc_records, eth_records = analyze_prices_sql()
    
    # بررسی دیتابیس فعلی
    check_database_structure()
    
    # نتیجه‌گیری
    print(f"\n" + "="*60)
    print("📋 نتیجه‌گیری")
    print("="*60)
    
    if btc_records:
        # بررسی تعداد رکوردهای منحصر به فرد
        unique_dates = set(record['date'].split()[0] for record in btc_records)
        
        if len(btc_records) > len(unique_dates):
            print(f"⚠️ مشکل تشخیص داده شد:")
            print(f"   تعداد رکوردها: {len(btc_records)}")
            print(f"   تعداد تاریخ‌های منحصر به فرد: {len(unique_dates)}")
            print(f"   نتیجه: رکوردها در حال آپدیت هستند به جای insert جدید")
            print(f"\n💡 راه‌حل: تغییر کد برای insert رکوردهای جدید به جای update")
            return False
        else:
            print(f"✅ همه چیز درست است:")
            print(f"   تعداد رکوردها: {len(btc_records)}")
            print(f"   تعداد تاریخ‌های منحصر به فرد: {len(unique_dates)}")
            print(f"   نتیجه: هر تاریخ یک رکورد منحصر به فرد دارد")
            return True
    else:
        print(f"❌ هیچ رکورد BTC یافت نشد")
        return False

if __name__ == "__main__":
    main()
