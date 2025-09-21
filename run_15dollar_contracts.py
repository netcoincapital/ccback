#!/usr/bin/env python3
"""
اجرای جستجوگر قراردادهای 15 دلاری اتریوم
Run Ethereum $15+ Contracts Finder
"""

import os
import sys
from datetime import datetime

def main():
    print("="*70)
    print("🔍 Ethereum Smart Contracts Finder - $15+ Creation Cost")
    print("جستجوگر قراردادهای هوشمند اتریوم با هزینه ساخت بالای 15 دلار")
    print("="*70)
    
    print("📋 اطلاعات جستجو:")
    print("📅 بازه زمانی: 01-08-2025 تا 31-08-2025")
    print("💰 حد آستانه هزینه: $15")
    print("🌐 منبع داده: Etherscan.io API")
    print("💱 قیمت‌گذاری: CoinGecko API")
    
    print("\n🔧 پیش‌نیازها:")
    print("✅ Python 3.7+")
    print("✅ کتابخانه‌های: requests, python-dotenv")
    print("✅ کلید API Etherscan")
    print("✅ اتصال اینترنت")
    
    print("\n" + "="*50)
    
    # بررسی وجود فایل اصلی
    main_script = "ethereum_contracts_15dollar_finder.py"
    if not os.path.exists(main_script):
        print(f"❌ فایل {main_script} یافت نشد!")
        print("لطفاً ابتدا اسکریپت اصلی را ایجاد کنید.")
        return
    
    print("🚀 شروع جستجو...")
    print(f"⏰ زمان شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # اجرای اسکریپت اصلی
        os.system(f"python {main_script}")
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطا در اجرا: {str(e)}")
    
    print(f"\n⏰ زمان پایان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

if __name__ == "__main__":
    main()
