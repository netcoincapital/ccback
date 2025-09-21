#!/usr/bin/env python3
"""
اسکریپت اجرایی برای جستجوی قراردادهای هوشمند اتریوم
"""

import sys
import os

def main():
    print("🔍 Ethereum Smart Contracts Finder")
    print("=" * 40)
    print("1. ساده (Simple) - سریع و کم حجم")
    print("2. کامل (Full) - جزئیات کامل") 
    print("3. پیشرفته (Advanced) - تحلیل عمیق")
    print("=" * 40)
    
    choice = input("انتخاب کنید (1/2/3): ").strip()
    
    if choice == '1':
        print("\n🚀 اجرای نسخه ساده...")
        os.system("python simple_ethereum_contracts.py")
        
    elif choice == '2':
        print("\n🚀 اجرای نسخه کامل...")
        os.system("python ethereum_smart_contracts_finder.py")
        
    elif choice == '3':
        print("\n🚀 اجرای نسخه پیشرفته...")
        os.system("python advanced_ethereum_contracts.py")
        
    else:
        print("❌ انتخاب نامعتبر!")
        return
    
    print("\n✅ تمام شد!")

if __name__ == "__main__":
    main()
