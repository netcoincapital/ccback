#!/usr/bin/env python3
"""
تست کننده برای جستجوگر قراردادهای 15 دلاری
Test script for $15+ Ethereum Contracts Finder
"""

import os
import sys
from datetime import datetime
import requests

def test_dependencies():
    """تست وجود کتابخانه‌های مورد نیاز"""
    print("🔧 بررسی وابستگی‌ها...")
    
    try:
        import requests
        print("✅ requests")
    except ImportError:
        print("❌ requests - لطفاً نصب کنید: pip install requests")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv")
    except ImportError:
        print("❌ python-dotenv - لطفاً نصب کنید: pip install python-dotenv")
        return False
    
    return True

def test_api_connections():
    """تست اتصال به API ها"""
    print("\n🌐 تست اتصال به API ها...")
    
    # تست CoinGecko
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            eth_price = data.get("ethereum", {}).get("usd", 0)
            print(f"✅ CoinGecko API - قیمت ETH: ${eth_price:,.2f}")
        else:
            print(f"⚠️ CoinGecko API - Status: {response.status_code}")
    except Exception as e:
        print(f"❌ CoinGecko API - خطا: {str(e)}")
    
    # تست Etherscan
    api_key = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
    try:
        response = requests.get(
            f"https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey={api_key}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                latest_block = int(data['result'], 16)
                print(f"✅ Etherscan API - آخرین بلاک: {latest_block:,}")
            else:
                print(f"⚠️ Etherscan API - نتیجه نامعتبر: {data}")
        else:
            print(f"❌ Etherscan API - Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Etherscan API - خطا: {str(e)}")

def test_date_calculations():
    """تست محاسبات تاریخ"""
    print("\n📅 تست محاسبات تاریخ...")
    
    try:
        # تاریخ‌های مشخص شده
        start_date = datetime(2025, 8, 1)
        end_date = datetime(2025, 8, 31, 23, 59, 59)
        
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        print(f"✅ تاریخ شروع: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"✅ تاریخ پایان: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"✅ Timestamp شروع: {start_timestamp}")
        print(f"✅ Timestamp پایان: {end_timestamp}")
        print(f"✅ مدت زمان: {(end_timestamp - start_timestamp) // 86400} روز")
        
        return True
        
    except Exception as e:
        print(f"❌ خطا در محاسبات تاریخ: {str(e)}")
        return False

def test_cost_calculations():
    """تست محاسبات هزینه"""
    print("\n💰 تست محاسبات هزینه...")
    
    try:
        from decimal import Decimal
        
        # نمونه داده‌ها
        gas_used = 2000000  # 2M gas
        gas_price_gwei = 20  # 20 Gwei
        eth_price_usd = 3000  # $3000
        
        # محاسبه
        gas_price_wei = gas_price_gwei * 10**9
        total_cost_wei = gas_used * gas_price_wei
        cost_eth = float(Decimal(total_cost_wei) / Decimal(10**18))
        cost_usd = cost_eth * eth_price_usd
        
        print(f"✅ Gas Used: {gas_used:,}")
        print(f"✅ Gas Price: {gas_price_gwei} Gwei")
        print(f"✅ ETH Price: ${eth_price_usd:,}")
        print(f"✅ هزینه ETH: {cost_eth:.6f}")
        print(f"✅ هزینه USD: ${cost_usd:.2f}")
        
        # بررسی آستانه
        threshold = 15.0
        meets_threshold = cost_usd >= threshold
        print(f"✅ بالای ${threshold}: {'بله' if meets_threshold else 'خیر'}")
        
        return True
        
    except Exception as e:
        print(f"❌ خطا در محاسبات هزینه: {str(e)}")
        return False

def test_file_operations():
    """تست عملیات فایل"""
    print("\n📁 تست عملیات فایل...")
    
    try:
        import json
        import csv
        
        # تست نوشتن JSON
        test_data = {
            "test": True,
            "timestamp": datetime.now().isoformat(),
            "contracts": [
                {
                    "address": "0x1234567890123456789012345678901234567890",
                    "cost_usd": 25.50
                }
            ]
        }
        
        test_json_file = "test_output.json"
        with open(test_json_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ نوشتن JSON: {test_json_file}")
        
        # تست نوشتن CSV
        test_csv_file = "test_output.csv"
        with open(test_csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'cost_usd'])
            writer.writeheader()
            writer.writerow({"address": "0x1234...", "cost_usd": 25.50})
        
        print(f"✅ نوشتن CSV: {test_csv_file}")
        
        # پاک کردن فایل‌های تست
        if os.path.exists(test_json_file):
            os.remove(test_json_file)
        if os.path.exists(test_csv_file):
            os.remove(test_csv_file)
        
        print("✅ پاک‌سازی فایل‌های تست")
        
        return True
        
    except Exception as e:
        print(f"❌ خطا در عملیات فایل: {str(e)}")
        return False

def main():
    """اجرای تست‌های اصلی"""
    print("="*60)
    print("🧪 تست جستجوگر قراردادهای 15 دلاری اتریوم")
    print("Test Suite for Ethereum $15+ Contracts Finder")
    print("="*60)
    
    tests = [
        ("وابستگی‌ها", test_dependencies),
        ("اتصال API", test_api_connections),
        ("محاسبات تاریخ", test_date_calculations),
        ("محاسبات هزینه", test_cost_calculations),
        ("عملیات فایل", test_file_operations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - موفق")
            else:
                print(f"❌ {test_name} - ناموفق")
        except Exception as e:
            print(f"❌ {test_name} - خطا: {str(e)}")
    
    print("\n" + "="*60)
    print(f"📊 نتیجه کلی: {passed}/{total} تست موفق")
    
    if passed == total:
        print("🎉 همه تست‌ها موفق! برنامه آماده اجرا است.")
        return True
    else:
        print("⚠️ برخی تست‌ها ناموفق. لطفاً مشکلات را برطرف کنید.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
