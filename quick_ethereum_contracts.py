#!/usr/bin/env python3
"""
Quick Ethereum Contracts Finder
جستجوگر سریع قراردادهای اتریوم با API مختلف
"""

import requests
import json
from datetime import datetime, timedelta
import os

def get_recent_contracts_quick():
    """دریافت سریع قراردادهای اخیر"""
    
    api_key = '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY'
    base_url = "https://api.etherscan.io/api"
    
    print("🚀 جستجوی سریع قراردادهای اتریوم...")
    
    contracts_found = []
    
    try:
        # دریافت آخرین بلاک
        latest_url = f"{base_url}?module=proxy&action=eth_blockNumber&apikey={api_key}"
        response = requests.get(latest_url)
        latest_block = int(response.json()['result'], 16)
        
        print(f"📦 آخرین بلاک: {latest_block}")
        
        # محاسبه تاریخ اول ماه (درست!)
        now = datetime.now()
        first_of_month = datetime(now.year, now.month, 1)
        start_timestamp = int(first_of_month.timestamp())
        
        print(f"📅 جستجو از: {first_of_month.strftime('%Y-%m-%d')}")
        print(f"🕐 Timestamp: {start_timestamp}")
        
        # جستجوی مستقیم در بلاک‌های اخیر
        blocks_to_check = 100000  # حدود 2 هفته
        start_block = latest_block - blocks_to_check
        
        print(f"🔍 بررسی از بلاک {start_block} تا {latest_block}")
        
        # روش جدید: استفاده از getLogs برای رویدادهای ایجاد قرارداد
        print("🔍 جستجوی رویدادهای ایجاد قرارداد...")
        
        # جستجوی logs مربوط به contract creation
        logs_url = f"{base_url}?module=logs&action=getLogs&fromBlock={start_block}&toBlock=latest&apikey={api_key}"
        
        logs_response = requests.get(logs_url)
        logs_data = logs_response.json()
        
        print(f"📊 وضعیت logs: {logs_data.get('status')}")
        
        # روش دیگر: جستجوی تراکنش‌های خاص
        print("🔄 جستجوی تراکنش‌های ایجاد قرارداد...")
        
        # بررسی چند صفحه از تراکنش‌های اخیر
        for page in range(1, 20):  # 20 صفحه
            print(f"📄 صفحه {page}...")
            
            tx_url = f"{base_url}?module=account&action=txlist&startblock={start_block}&endblock=latest&page={page}&offset=100&sort=desc&apikey={api_key}"
            
            tx_response = requests.get(tx_url)
            tx_data = tx_response.json()
            
            if tx_data.get('status') != '1':
                print(f"⚠️ خطا در صفحه {page}: {tx_data.get('message', 'نامشخص')}")
                continue
            
            transactions = tx_data.get('result', [])
            
            if not transactions:
                print(f"⚠️ صفحه {page} خالی است")
                continue
            
            page_contracts = 0
            for tx in transactions:
                # بررسی تراکنش ایجاد قرارداد
                if tx.get('to') == '' and tx.get('input', '0x') != '0x':
                    tx_timestamp = int(tx.get('timeStamp', 0))
                    
                    # بررسی تاریخ
                    if tx_timestamp >= start_timestamp:
                        # دریافت آدرس قرارداد
                        receipt_url = f"{base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx['hash']}&apikey={api_key}"
                        
                        try:
                            receipt_response = requests.get(receipt_url)
                            receipt_data = receipt_response.json()
                            
                            if receipt_data.get('result') and receipt_data['result'].get('contractAddress'):
                                contract_address = receipt_data['result']['contractAddress']
                                date_str = datetime.fromtimestamp(tx_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                                
                                contract_info = {
                                    'address': contract_address,
                                    'creator': tx['from'],
                                    'tx_hash': tx['hash'],
                                    'block': tx['blockNumber'],
                                    'date': date_str,
                                    'timestamp': tx_timestamp,
                                    'gas_used': tx.get('gasUsed', '0')
                                }
                                
                                contracts_found.append(contract_info)
                                page_contracts += 1
                                print(f"✅ {contract_address} - {date_str}")
                                
                        except Exception as e:
                            print(f"❌ خطا در دریافت receipt: {str(e)}")
            
            print(f"📊 صفحه {page}: {page_contracts} قرارداد یافت شد")
            
            # اگر تعداد کافی پیدا شد، متوقف شو
            if len(contracts_found) >= 30:
                print(f"✅ تعداد کافی قرارداد یافت شد: {len(contracts_found)}")
                break
            
            # اگر صفحه خالی بود، احتمالاً به انتها رسیده‌ایم
            if page_contracts == 0 and page > 5:
                print("⚠️ به نظر می‌رسد به انتهای نتایج رسیده‌ایم")
                break
        
        return contracts_found
        
    except Exception as e:
        print(f"❌ خطای کلی: {str(e)}")
        return []

def main():
    print("=" * 50)
    print("⚡ Quick Ethereum Contracts Finder")
    print("=" * 50)
    
    contracts = get_recent_contracts_quick()
    
    if contracts:
        print(f"\n🎉 تعداد کل: {len(contracts)} قرارداد یافت شد!")
        
        # ذخیره نتایج
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"quick_ethereum_contracts_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'total_count': len(contracts),
                'search_date': datetime.now().isoformat(),
                'contracts': contracts
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 ذخیره شد در: {filename}")
        
        # نمایش خلاصه
        print(f"\n📋 خلاصه یافته‌ها:")
        for i, contract in enumerate(contracts[:10], 1):  # فقط 10 تای اول
            print(f"{i:2d}. {contract['address']} ({contract['date']})")
        
        if len(contracts) > 10:
            print(f"    ... و {len(contracts) - 10} قرارداد دیگر")
        
        # آمار
        creators = set(c['creator'] for c in contracts)
        print(f"\n📊 آمار:")
        print(f"   کل قراردادها: {len(contracts)}")
        print(f"   سازندگان منحصر به فرد: {len(creators)}")
        
        # قراردادهای امروز
        today = datetime.now().date()
        today_contracts = [c for c in contracts if datetime.fromtimestamp(c['timestamp']).date() == today]
        print(f"   قراردادهای امروز: {len(today_contracts)}")
        
    else:
        print("😔 هیچ قراردادی یافت نشد")
        print("💡 ممکن است نیاز به:")
        print("   - بررسی کلید API")
        print("   - افزایش بازه جستجو")
        print("   - تغییر روش جستجو")

if __name__ == "__main__":
    main()
