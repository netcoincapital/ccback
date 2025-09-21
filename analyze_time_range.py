#!/usr/bin/env python3
"""
تحلیل بازه زمانی قراردادهای اتریوم
Analyze time range of Ethereum contracts
"""

import json
from datetime import datetime

def analyze_time_range(filename):
    """تحلیل بازه زمانی قراردادها"""
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        contracts = data.get('contracts', [])
        
        if not contracts:
            print("❌ هیچ قراردادی در فایل یافت نشد")
            return
        
        # استخراج تاریخ‌ها
        dates = []
        timestamps = []
        blocks = []
        
        for contract in contracts:
            date_str = contract.get('date', '')
            timestamp = contract.get('timestamp', 0)
            block_number = contract.get('block_number', 0)
            
            if date_str:
                dates.append(date_str)
            if timestamp:
                timestamps.append(timestamp)
            if block_number:
                blocks.append(block_number)
        
        # مرتب‌سازی
        dates.sort()
        timestamps.sort()
        blocks.sort()
        
        print("="*70)
        print("📅 تحلیل بازه زمانی قراردادهای اتریوم")
        print("="*70)
        
        print(f"📄 فایل: {filename}")
        print(f"🔢 تعداد کل قراردادها: {len(contracts):,}")
        
        if dates:
            print(f"\n⏰ بازه زمانی:")
            print(f"   🟢 اولین قرارداد: {dates[0]}")
            print(f"   🔴 آخرین قرارداد: {dates[-1]}")
            
            # محاسبه مدت زمان
            try:
                start_time = datetime.strptime(dates[0], '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(dates[-1], '%Y-%m-%d %H:%M:%S')
                duration = end_time - start_time
                
                print(f"   ⏱️ مدت زمان کل: {duration}")
                print(f"   📊 مدت زمان: {duration.total_seconds() / 3600:.1f} ساعت")
                print(f"   📊 مدت زمان: {duration.total_seconds() / 60:.0f} دقیقه")
                
            except ValueError as e:
                print(f"   ⚠️ خطا در محاسبه مدت زمان: {e}")
        
        if blocks:
            print(f"\n📦 بازه بلاک‌ها:")
            print(f"   🟢 اولین بلاک: {blocks[0]:,}")
            print(f"   🔴 آخرین بلاک: {blocks[-1]:,}")
            print(f"   📊 تعداد بلاک‌ها: {blocks[-1] - blocks[0] + 1:,}")
        
        # آمار ساعتی
        print(f"\n🕐 توزیع ساعتی:")
        hour_distribution = {}
        
        for date_str in dates:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                hour = dt.hour
                hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
            except ValueError:
                continue
        
        # نمایش توزیع ساعتی
        for hour in sorted(hour_distribution.keys()):
            count = hour_distribution[hour]
            bar = "█" * (count // 2) if count > 1 else "▌" if count == 1 else ""
            print(f"   {hour:2d}:00 - {count:2d} قرارداد {bar}")
        
        # آمار روزانه (اگر بیش از یک روز باشد)
        print(f"\n📆 توزیع روزانه:")
        date_distribution = {}
        
        for date_str in dates:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                date_only = dt.strftime('%Y-%m-%d')
                date_distribution[date_only] = date_distribution.get(date_only, 0) + 1
            except ValueError:
                continue
        
        for date_key in sorted(date_distribution.keys()):
            count = date_distribution[date_key]
            print(f"   {date_key}: {count:3d} قرارداد")
        
        # نمایش چند نمونه
        print(f"\n📋 نمونه‌هایی از قراردادها:")
        
        # اولین 3 قرارداد
        sorted_contracts = sorted(contracts, key=lambda x: x.get('date', ''))
        print(f"   🟢 اولین قراردادها:")
        for i, contract in enumerate(sorted_contracts[:3], 1):
            print(f"      {i}. {contract.get('date', 'نامشخص')} - {contract.get('contract_address', '')[:15]}... - ${contract.get('transaction_fee_usd', 0):.2f}")
        
        # آخرین 3 قرارداد
        print(f"   🔴 آخرین قراردادها:")
        for i, contract in enumerate(sorted_contracts[-3:], 1):
            print(f"      {i}. {contract.get('date', 'نامشخص')} - {contract.get('contract_address', '')[:15]}... - ${contract.get('transaction_fee_usd', 0):.2f}")
        
        # اطلاعات اسکن
        scan_info = data.get('scan_info', {})
        if scan_info:
            print(f"\n🔍 اطلاعات اسکن:")
            print(f"   📅 تاریخ اسکن: {scan_info.get('scan_date', 'نامشخص')}")
            print(f"   💰 قیمت ETH: ${scan_info.get('eth_price_usd', 0):,.2f}")
            print(f"   🎯 آستانه هزینه: ${scan_info.get('min_fee_threshold_usd', 0)}")
            
            stats = scan_info.get('statistics', {})
            if stats:
                print(f"   📦 بلاک‌های اسکن شده: {stats.get('blocks_scanned', 0):,}")
                print(f"   🔍 تراکنش‌های بررسی شده: {stats.get('transactions_checked', 0):,}")
                print(f"   🌐 API calls: {stats.get('api_calls', 0):,}")
        
        print("\n" + "="*70)
        
    except FileNotFoundError:
        print(f"❌ فایل {filename} یافت نشد")
    except json.JSONDecodeError:
        print(f"❌ خطا در خواندن فایل JSON: {filename}")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")

def main():
    filename = "ethereum_expensive_contracts_20250901_021213.json"
    
    print("📅 تحلیل‌گر بازه زمانی قراردادهای اتریوم")
    print("Ethereum Contracts Time Range Analyzer")
    
    analyze_time_range(filename)

if __name__ == "__main__":
    main()
