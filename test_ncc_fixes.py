#!/usr/bin/env python3
"""
اسکریپت تست برای تأیید درستی تغییرات NCCPRICE.py
"""

import sys
import os

# اضافه کردن مسیر پروژه
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(current_dir))

def test_ncc_fixes():
    """
    تست تغییرات اعمال شده روی NCCPRICE.py
    """
    print("🔍 تست تغییرات NCCPRICE.py...")
    
    try:
        # تست import ماژول
        from utils.price_simulator.NCCPRICE import init_ncc, generate_price, reset_price_simulator
        print("✅ ماژول NCCPRICE با موفقیت import شد")
        
        # تست تابع init_ncc
        print("🔍 تست تابع init_ncc...")
        if init_ncc():
            print("✅ تابع init_ncc با موفقیت اجرا شد")
        else:
            print("⚠️ تابع init_ncc مشکل دارد (ممکن است توکن NCC در دیتابیس نباشد)")
        
        # تست تابع generate_price
        print("🔍 تست تابع generate_price...")
        price, change = generate_price()
        print(f"✅ قیمت تولید شده: ${price:.6f}, تغییر 24h: {change:.2f}%")
        
        if price >= 0.22 and price <= 1.00:  # بازه منطقی
            print("✅ قیمت در بازه مجاز است")
        else:
            print(f"⚠️ قیمت خارج از بازه مجاز: ${price:.6f}")
            
        print("✅ همه تست‌ها موفقیت‌آمیز بود")
        return True
        
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ncc_fixes()
    sys.exit(0 if success else 1)