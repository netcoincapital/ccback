#!/usr/bin/env python3
"""
تست با تاریخ‌های واقعی
Test with real dates
"""

import sys
from datetime import datetime, timedelta

# import کردن کلاس اسکنر
from ethereum_date_range_scanner import EthereumDateRangeScanner

def test_real_dates():
    """تست با تاریخ‌های واقعی (گذشته)"""
    
    print("="*60)
    print("🧪 تست اسکنر با تاریخ‌های واقعی")
    print("="*60)
    
    try:
        # ایجاد اسکنر
        scanner = EthereumDateRangeScanner()
        
        # تنظیمات تست
        scanner.min_fee_usd = 5.0  # 5 دلار
        scanner.max_total_usd = 100.0  # 100 دلار مجموع
        
        print(f"\n🔧 تنظیمات تست:")
        print(f"   💰 حد آستانه هر قرارداد: ${scanner.min_fee_usd}")
        print(f"   🎯 حد آستانه مجموع: ${scanner.max_total_usd}")
        
        # استفاده از تاریخ‌های واقعی (آگوست 2024)
        start_date = "20-08-2024"
        end_date = "22-08-2024"  # فقط 3 روز برای تست
        
        print(f"\n📅 بازه زمانی تست:")
        print(f"   🟢 از: {start_date}")
        print(f"   🔴 تا: {end_date}")
        
        # اجرای اسکن
        scanner.run(start_date, end_date)
        
    except KeyboardInterrupt:
        print(f"\n⏹️ تست توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")

if __name__ == "__main__":
    test_real_dates()
