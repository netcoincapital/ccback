#!/usr/bin/env python3
"""
تست اسکنر با حد آستانه پایین
Test scanner with low threshold
"""

import sys
from datetime import datetime, timedelta

# import کردن کلاس اسکنر
from ethereum_date_range_scanner import EthereumDateRangeScanner

def test_low_threshold():
    """تست با حد آستانه پایین"""
    
    print("="*60)
    print("🧪 تست اسکنر با حد آستانه پایین")
    print("="*60)
    
    try:
        # ایجاد اسکنر
        scanner = EthereumDateRangeScanner()
        
        # تنظیمات تست - حد آستانه خیلی پایین
        scanner.min_fee_usd = 1.0  # 1 دلار
        scanner.max_total_usd = 50.0  # 50 دلار مجموع
        
        print(f"\n🔧 تنظیمات تست:")
        print(f"   💰 حد آستانه هر قرارداد: ${scanner.min_fee_usd}")
        print(f"   🎯 حد آستانه مجموع: ${scanner.max_total_usd}")
        
        # دریافت قیمت ETH
        scanner.get_eth_price()
        
        # تست با بازه زمانی امروز
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        start_date = yesterday.strftime('%d-%m-%Y')
        end_date = today.strftime('%d-%m-%Y')
        
        print(f"\n📅 بازه زمانی تست:")
        print(f"   🟢 از: {start_date}")
        print(f"   🔴 تا: {end_date}")
        
        # اجرای اسکن
        expensive_contracts = scanner.scan_date_range(start_date, end_date)
        
        # نمایش نتایج
        scanner.print_summary(expensive_contracts)
        
        # ذخیره در صورت یافتن قرارداد
        if expensive_contracts:
            filename = scanner.save_results(expensive_contracts, start_date, end_date)
            print(f"\n✅ فایل ذخیره شد: {filename}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ تست توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")

if __name__ == "__main__":
    test_low_threshold()
