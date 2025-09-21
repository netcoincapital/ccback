#!/usr/bin/env python3
"""
Simple Ethereum Smart Contracts Finder
استخراج ساده آدرس قراردادهای هوشمند اتریوم
"""

import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_recent_contracts():
    """دریافت قراردادهای اخیر به صورت ساده"""
    
    # API Key
    api_key = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
    base_url = "https://api.etherscan.io/api"
    
    print("🔍 جستجوی قراردادهای هوشمند اتریوم...")
    print(f"🔑 API Key: {api_key[:8]}...")
    
    contracts_found = []
    
    try:
        # دریافت آخرین بلاک
        url = f"{base_url}?module=proxy&action=eth_blockNumber&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        latest_block = int(data['result'], 16)
        
        print(f"📦 آخرین بلاک: {latest_block}")
        
        # جستجو در 10000 بلاک اخیر (حدود 2 روز)
        start_block = latest_block - 10000
        
        print(f"🔄 جستجو از بلاک {start_block} تا {latest_block}")
        
        # دریافت تراکنش‌های اخیر
        for page in range(1, 6):  # 5 صفحه اول
            print(f"📄 پردازش صفحه {page}...")
            
            # جستجوی تراکنش‌های عمومی
            tx_url = f"{base_url}?module=account&action=txlist&startblock={start_block}&endblock={latest_block}&page={page}&offset=200&sort=desc&apikey={api_key}"
            
            tx_response = requests.get(tx_url)
            tx_data = tx_response.json()
            
            if tx_data.get('status') == '1' and tx_data.get('result'):
                transactions = tx_data['result']
                
                # پیدا کردن تراکنش‌های ایجاد قرارداد
                for tx in transactions:
                    if tx.get('to') == '':  # تراکنش ایجاد قرارداد
                        # دریافت آدرس قرارداد از receipt
                        receipt_url = f"{base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx['hash']}&apikey={api_key}"
                        receipt_response = requests.get(receipt_url)
                        receipt_data = receipt_response.json()
                        
                        if receipt_data.get('result') and receipt_data['result'].get('contractAddress'):
                            contract_address = receipt_data['result']['contractAddress']
                            timestamp = int(tx.get('timeStamp', 0))
                            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # محاسبه تاریخ اول ماه
                            now = datetime.now()
                            first_of_month = datetime(now.year, now.month, 1)
                            
                            # فقط قراردادهای این ماه
                            if timestamp >= int(first_of_month.timestamp()):
                                contract_info = {
                                    'address': contract_address,
                                    'creator': tx['from'],
                                    'tx_hash': tx['hash'],
                                    'block': tx['blockNumber'],
                                    'date': date_str,
                                    'timestamp': timestamp
                                }
                                
                                contracts_found.append(contract_info)
                                print(f"✅ قرارداد: {contract_address} - {date_str}")
        
        return contracts_found
        
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        return []

def main():
    print("=" * 50)
    print("🔍 Simple Ethereum Contracts Finder")
    print("=" * 50)
    
    contracts = get_recent_contracts()
    
    if contracts:
        print(f"\n🎉 تعداد کل: {len(contracts)} قرارداد")
        
        # ذخیره در فایل
        filename = f"ethereum_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'total_count': len(contracts),
                'search_date': datetime.now().isoformat(),
                'contracts': contracts
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 ذخیره شد در: {filename}")
        
        # نمایش آدرس‌ها
        print(f"\n📋 آدرس قراردادها:")
        for i, contract in enumerate(contracts, 1):
            print(f"{i:2d}. {contract['address']}")
        
    else:
        print("😔 هیچ قراردادی یافت نشد")

if __name__ == "__main__":
    main()
