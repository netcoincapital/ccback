#!/usr/bin/env python3
"""
دیباگ اسکنر اتریوم
Debug Ethereum Scanner
"""

import sys
import traceback
from datetime import datetime

# import کردن کلاس اسکنر
from ethereum_date_range_scanner import EthereumDateRangeScanner

def debug_test():
    """تست دیباگ"""
    
    print("="*60)
    print("🐛 دیباگ اسکنر اتریوم")
    print("="*60)
    
    try:
        # ایجاد اسکنر
        scanner = EthereumDateRangeScanner()
        
        # تنظیمات تست
        scanner.min_fee_usd = 15.0
        scanner.max_total_usd = 1470.0
        
        print(f"\n🔧 تنظیمات:")
        print(f"   💰 حد آستانه: ${scanner.min_fee_usd}")
        print(f"   🎯 حد مجموع: ${scanner.max_total_usd}")
        print(f"   🔑 تعداد کلیدها: {len(scanner.api_keys)}")
        
        # تست با بازه کوچک
        start_date = "20-08-2024"
        end_date = "20-08-2024"  # فقط یک روز
        
        print(f"\n📅 تست با یک روز:")
        print(f"   🟢 از: {start_date}")
        print(f"   🔴 تا: {end_date}")
        
        # اجرای اسکن
        print(f"\n🚀 شروع اسکن...")
        scanner.run(start_date, end_date)
        
    except Exception as e:
        print(f"\n❌ خطای دیباگ:")
        print(f"   نوع خطا: {type(e).__name__}")
        print(f"   پیام خطا: {str(e)}")
        print(f"\n📋 جزئیات کامل:")
        traceback.print_exc()

if __name__ == "__main__":
    debug_test()
