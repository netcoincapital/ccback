#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اجرای ساده تولیدکننده کیف پول BSC
"""

from bsc_wallet_generator import BSCWalletGenerator
import os

def run_quick_test():
    """تست سریع با تولید 10 کیف پول"""
    print("🧪 تست سریع - تولید 10 کیف پول...")
    
    generator = BSCWalletGenerator()
    
    # تغییر تنظیمات برای تست
    global WALLET_COUNT, OUTPUT_FILE
    original_count = 100000
    test_file = "test_wallets.csv"
    
    # تولید 10 کیف پول برای تست
    wallets = []
    for i in range(1, 11):
        wallet = generator.generate_wallet()
        if wallet:
            wallet['index'] = i
            wallets.append(wallet)
    
    # ذخیره تست
    if generator.save_wallets_batch(wallets, test_file, 'w'):
        print(f"✅ تست موفق! {len(wallets)} کیف پول در {test_file} ذخیره شد.")
        
        # نمایش نمونه
        print("\n📋 نمونه کیف پول‌های تولید شده:")
        for i, wallet in enumerate(wallets[:3]):
            print(f"\n🔹 کیف پول #{i+1}:")
            print(f"   Mnemonic: {wallet['mnemonic']}")
            print(f"   Private Key: {wallet['private_key']}")
            print(f"   Address: {wallet['address']}")
    else:
        print("❌ خطا در تست!")

if __name__ == "__main__":
    print("انتخاب کنید:")
    print("1. تست سریع (10 کیف پول)")
    print("2. تولید کامل (100,000 کیف پول)")
    
    choice = input("\nانتخاب شما (1 یا 2): ").strip()
    
    if choice == "1":
        run_quick_test()
    elif choice == "2":
        from bsc_wallet_generator import main
        main()
    else:
        print("❌ انتخاب نامعتبر!")
