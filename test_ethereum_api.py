#!/usr/bin/env python3
"""
تست ساده API اتریوم
"""

import requests
from datetime import datetime

def test_ethereum_api():
    api_key = '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY'
    base_url = "https://api.etherscan.io/api"
    
    print("🧪 تست API اتریوم...")
    
    # تست 1: دریافت آخرین بلاک
    print("\n1️⃣ تست آخرین بلاک:")
    try:
        url = f"{base_url}?module=proxy&action=eth_blockNumber&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('result'):
            latest_block = int(data['result'], 16)
            print(f"✅ آخرین بلاک: {latest_block}")
        else:
            print(f"❌ خطا: {data}")
    except Exception as e:
        print(f"❌ خطا: {e}")
    
    # تست 2: دریافت یک بلاک خاص
    print("\n2️⃣ تست دریافت بلاک:")
    try:
        block_num = latest_block - 10  # 10 بلاک قبل
        url = f"{base_url}?module=proxy&action=eth_getBlockByNumber&tag=0x{block_num:x}&boolean=true&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('result'):
            block_data = data['result']
            tx_count = len(block_data.get('transactions', []))
            print(f"✅ بلاک {block_num}: {tx_count} تراکنش")
            
            # بررسی تراکنش‌های ایجاد قرارداد
            contract_txs = 0
            for tx in block_data.get('transactions', []):
                if tx.get('to') is None:
                    contract_txs += 1
            
            print(f"📊 تراکنش‌های ایجاد قرارداد: {contract_txs}")
            
        else:
            print(f"❌ خطا: {data}")
    except Exception as e:
        print(f"❌ خطا: {e}")
    
    # تست 3: جستجوی تراکنش‌های اخیر
    print("\n3️⃣ تست تراکنش‌های اخیر:")
    try:
        start_block = latest_block - 1000
        url = f"{base_url}?module=account&action=txlist&startblock={start_block}&endblock={latest_block}&page=1&offset=10&sort=desc&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == '1' and data.get('result'):
            transactions = data['result']
            print(f"✅ دریافت {len(transactions)} تراکنش")
            
            # بررسی تراکنش‌های ایجاد قرارداد
            for tx in transactions:
                if tx.get('to') == '':
                    timestamp = int(tx.get('timeStamp', 0))
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"🔍 تراکنش ایجاد قرارداد: {tx['hash']} ({date_str})")
        else:
            print(f"❌ خطا: {data}")
    except Exception as e:
        print(f"❌ خطا: {e}")
    
    # تست 4: محاسبه timestamp
    print("\n4️⃣ تست محاسبه زمان:")
    try:
        now = datetime.now()
        first_of_month = datetime(now.year, now.month, 1)
        start_timestamp = int(first_of_month.timestamp())
        
        print(f"📅 امروز: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 اول ماه: {first_of_month.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 Timestamp اول ماه: {start_timestamp}")
        print(f"✅ تبدیل برگشت: {datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ خطا: {e}")

if __name__ == "__main__":
    test_ethereum_api()
