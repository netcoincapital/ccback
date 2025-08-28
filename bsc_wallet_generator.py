#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSC (BEP-20) Wallet Generator
تولید کیف پول BSC با استفاده از bip39

این اسکریپت 100,000 کیف پول BSC (BEP-20) تولید می‌کند و اطلاعات آن‌ها را ذخیره می‌کند:
- 12 کلمه mnemonic
- کلید خصوصی (Private Key)
- آدرس عمومی (Public Address)
"""

import csv
import time
import os
from datetime import datetime
from mnemonic import Mnemonic
from eth_account import Account
import secrets

# تنظیمات
WALLET_COUNT = 100000
OUTPUT_FILE = "bsc_wallets.csv"
BATCH_SIZE = 1000  # ذخیره هر 1000 کیف پول
PROGRESS_INTERVAL = 5000  # نمایش پیشرفت هر 5000 کیف پول

class BSCWalletGenerator:
    def __init__(self):
        # فعال کردن ویژگی mnemonic
        Account.enable_unaudited_hdwallet_features()
        self.mnemo = Mnemonic("english")
        self.generated_count = 0
        self.start_time = None
        
    def generate_wallet(self):
        """تولید یک کیف پول BSC"""
        try:
            # تولید mnemonic 12 کلمه‌ای
            mnemonic_phrase = self.mnemo.generate(strength=128)
            
            # تبدیل mnemonic به seed
            seed = self.mnemo.to_seed(mnemonic_phrase)
            
            # تولید حساب از seed
            account = Account.from_mnemonic(mnemonic_phrase)
            
            return {
                'mnemonic': mnemonic_phrase,
                'private_key': account.key.hex(),
                'address': account.address
            }
        except Exception as e:
            print(f"خطا در تولید کیف پول: {e}")
            return None
    
    def save_wallets_batch(self, wallets, filename, mode='a'):
        """ذخیره دسته‌ای کیف پول‌ها"""
        try:
            with open(filename, mode, newline='', encoding='utf-8') as csvfile:
                fieldnames = ['index', 'mnemonic', 'private_key', 'address']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # اگر فایل جدید است، هدر را بنویس
                if mode == 'w':
                    writer.writeheader()
                
                for wallet in wallets:
                    writer.writerow(wallet)
            
            return True
        except Exception as e:
            print(f"خطا در ذخیره فایل: {e}")
            return False
    
    def display_progress(self, current, total):
        """نمایش پیشرفت"""
        percentage = (current / total) * 100
        elapsed_time = time.time() - self.start_time
        
        if current > 0:
            avg_time_per_wallet = elapsed_time / current
            remaining_wallets = total - current
            estimated_time = remaining_wallets * avg_time_per_wallet
            
            print(f"\r🔄 پیشرفت: {current:,}/{total:,} ({percentage:.2f}%) | "
                  f"زمان سپری شده: {elapsed_time:.1f}s | "
                  f"زمان تخمینی باقی‌مانده: {estimated_time:.1f}s", end="")
    
    def generate_bulk_wallets(self):
        """تولید انبوه کیف پول‌ها"""
        print(f"🚀 شروع تولید {WALLET_COUNT:,} کیف پول BSC...")
        print(f"📁 فایل خروجی: {OUTPUT_FILE}")
        print("=" * 60)
        
        self.start_time = time.time()
        wallets_batch = []
        
        # ایجاد فایل CSV با هدر
        if not self.save_wallets_batch([], OUTPUT_FILE, 'w'):
            print("❌ خطا در ایجاد فایل خروجی!")
            return False
        
        for i in range(1, WALLET_COUNT + 1):
            # تولید کیف پول
            wallet = self.generate_wallet()
            
            if wallet:
                wallet['index'] = i
                wallets_batch.append(wallet)
                self.generated_count += 1
                
                # ذخیره دسته‌ای
                if len(wallets_batch) >= BATCH_SIZE:
                    if self.save_wallets_batch(wallets_batch, OUTPUT_FILE):
                        wallets_batch = []
                    else:
                        print(f"\n❌ خطا در ذخیره کیف پول {i}")
                        return False
                
                # نمایش پیشرفت
                if i % PROGRESS_INTERVAL == 0:
                    self.display_progress(i, WALLET_COUNT)
            else:
                print(f"\n⚠️ خطا در تولید کیف پول {i}")
        
        # ذخیره کیف پول‌های باقی‌مانده
        if wallets_batch:
            self.save_wallets_batch(wallets_batch, OUTPUT_FILE)
        
        # نمایش نتیجه نهایی
        total_time = time.time() - self.start_time
        print(f"\n\n✅ تکمیل شد!")
        print(f"📊 آمار نهایی:")
        print(f"   • تعداد کیف پول تولید شده: {self.generated_count:,}")
        print(f"   • زمان کل: {total_time:.2f} ثانیه")
        print(f"   • میانگین زمان هر کیف پول: {total_time/self.generated_count:.4f} ثانیه")
        print(f"   • فایل ذخیره شده: {OUTPUT_FILE}")
        print(f"   • حجم فایل: {os.path.getsize(OUTPUT_FILE) / (1024*1024):.2f} MB")
        
        return True
    
    def show_sample_wallets(self, count=5):
        """نمایش نمونه کیف پول‌های تولید شده"""
        print(f"\n📋 نمایش {count} کیف پول نمونه:")
        print("=" * 100)
        
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for i, row in enumerate(reader):
                    if i >= count:
                        break
                    print(f"\n🔹 کیف پول #{row['index']}:")
                    print(f"   Mnemonic: {row['mnemonic']}")
                    print(f"   Private Key: {row['private_key']}")
                    print(f"   Address: {row['address']}")
        except Exception as e:
            print(f"خطا در خواندن فایل: {e}")

def main():
    """تابع اصلی"""
    print("🔐 تولیدکننده کیف پول BSC (BEP-20)")
    print("=" * 50)
    print(f"تاریخ و زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"تعداد کیف پول: {WALLET_COUNT:,}")
    print("=" * 50)
    
    # بررسی وجود فایل قبلی
    if os.path.exists(OUTPUT_FILE):
        response = input(f"\n⚠️ فایل {OUTPUT_FILE} از قبل وجود دارد. آیا می‌خواهید آن را جایگزین کنید؟ (y/n): ")
        if response.lower() != 'y':
            print("❌ عملیات لغو شد.")
            return
    
    # شروع تولید
    generator = BSCWalletGenerator()
    
    if generator.generate_bulk_wallets():
        generator.show_sample_wallets()
        
        print(f"\n💡 نکات مهم:")
        print(f"   • همه کیف پول‌ها با شبکه BSC (Binance Smart Chain) سازگار هستند")
        print(f"   • این آدرس‌ها برای توکن‌های BEP-20 قابل استفاده هستند")
        print(f"   • حتماً کلیدهای خصوصی را در مکان امن نگهداری کنید")
        print(f"   • هرگز کلید خصوصی را با دیگران به اشتراک نگذارید")
    else:
        print("❌ خطا در تولید کیف پول‌ها!")

if __name__ == "__main__":
    main()
