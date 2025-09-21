#!/usr/bin/env python3
"""
تست سریع اسکنر با بازه کوچک
Quick test scanner with small range
"""

import os
import sys
from datetime import datetime

# اضافه کردن مسیر فعلی
sys.path.append('.')

# import کردن کلاس اسکنر
from ethereum_date_range_scanner import EthereumDateRangeScanner

def quick_test():
    """تست سریع با بازه کوچک"""
    
    print("="*60)
    print("🚀 تست سریع اسکنر قراردادهای اتریوم")
    print("="*60)
    
    try:
        # ایجاد اسکنر
        scanner = EthereumDateRangeScanner()
        
        # تنظیمات تست
        scanner.min_fee_usd = 10.0  # کاهش حد آستانه برای تست
        scanner.max_total_usd = 100.0  # کاهش حد مجموع برای تست سریع
        
        print(f"\n🔧 تنظیمات تست:")
        print(f"   💰 حد آستانه هر قرارداد: ${scanner.min_fee_usd}")
        print(f"   🎯 حد آستانه مجموع: ${scanner.max_total_usd}")
        
        # دریافت قیمت ETH
        scanner.get_eth_price()
        
        # تست دریافت آخرین بلاک
        print(f"\n📦 تست دریافت بلاک...")
        current_timestamp = int(datetime.now().timestamp())
        yesterday_timestamp = current_timestamp - 86400  # 24 ساعت قبل
        
        latest_block = scanner.get_block_by_timestamp(current_timestamp, 'before')
        yesterday_block = scanner.get_block_by_timestamp(yesterday_timestamp, 'before')
        
        if latest_block and yesterday_block:
            print(f"   ✅ بلاک امروز: {latest_block:,}")
            print(f"   ✅ بلاک دیروز: {yesterday_block:,}")
            print(f"   📊 تفاوت: {latest_block - yesterday_block:,} بلاک")
            
            # تست اسکن تعداد کمی بلاک
            print(f"\n🔍 تست اسکن 10 بلاک اخیر...")
            
            all_contracts = []
            for i in range(10):
                current_block = latest_block - i
                print(f"📦 اسکن بلاک {current_block:,} ({i+1}/10)")
                
                contracts, should_stop = scanner.scan_block_for_expensive_contracts(current_block)
                all_contracts.extend(contracts)
                
                if should_stop:
                    print(f"🛑 توقف به دلیل رسیدن به حد آستانه!")
                    break
                
                if len(all_contracts) > 0:
                    print(f"   ✅ {len(contracts)} قرارداد یافت شد")
            
            # نمایش نتایج
            if all_contracts:
                print(f"\n🎉 تعداد کل قراردادهای یافت شده: {len(all_contracts)}")
                print(f"💰 مجموع هزینه‌ها: ${scanner.current_total_usd:.2f}")
                
                for contract in all_contracts:
                    print(f"   • {contract['contract_address']} - ${contract['transaction_fee_usd']:.2f}")
            else:
                print(f"\n😔 هیچ قراردادی یافت نشد")
            
            # آمار API Keys
            print(f"\n🔑 آمار استفاده از کلیدها:")
            for i, key in enumerate(scanner.api_keys):
                requests_count = scanner.api_request_counts.get(i, 0)
                errors_count = scanner.api_error_counts.get(i, 0)
                print(f"   کلید {i+1} ({key[:8]}...): {requests_count} درخواست, {errors_count} خطا")
            
        else:
            print(f"❌ نتوانستم بلاک‌ها را دریافت کنم")
            
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")

if __name__ == "__main__":
    quick_test()
