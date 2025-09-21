#!/usr/bin/env python3
"""
تست ساده برای یافتن قراردادهای اتریوم
Simple test for finding Ethereum contracts
"""

import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
import time

def get_eth_price():
    """دریافت قیمت ETH"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return float(data["ethereum"]["usd"])
    except:
        pass
    return 3000.0  # قیمت پیش‌فرض

def wei_to_eth(wei):
    """تبدیل Wei به ETH"""
    return float(Decimal(wei) / Decimal(10**18))

def find_recent_contracts():
    """یافتن قراردادهای اخیر"""
    api_key = "77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY"
    base_url = "https://api.etherscan.io/api"
    
    print("🔍 جستجوی قراردادهای اخیر...")
    
    # دریافت قیمت ETH
    eth_price = get_eth_price()
    print(f"💰 قیمت ETH: ${eth_price:,.2f}")
    
    # دریافت آخرین بلاک
    try:
        response = requests.get(f"{base_url}?module=proxy&action=eth_blockNumber&apikey={api_key}")
        data = response.json()
        latest_block = int(data['result'], 16)
        print(f"📦 آخرین بلاک: {latest_block:,}")
        
        # جستجو در 5000 بلاک اخیر (حدود 1 روز)
        start_block = latest_block - 5000
        
        print(f"🔍 جستجو در بلاک‌های {start_block:,} تا {latest_block:,}")
        
        contracts_found = []
        
        # جستجوی تراکنش‌های اخیر
        for page in range(1, 4):  # 3 صفحه اول
            print(f"📄 صفحه {page}...")
            
            tx_url = f"{base_url}?module=account&action=txlist&startblock={start_block}&endblock={latest_block}&page={page}&offset=100&sort=desc&apikey={api_key}"
            
            response = requests.get(tx_url)
            if response.status_code != 200:
                print(f"❌ خطا در درخواست: {response.status_code}")
                continue
                
            tx_data = response.json()
            
            if tx_data.get('status') != '1' or not tx_data.get('result'):
                print(f"⚠️ هیچ تراکنشی در صفحه {page} یافت نشد")
                continue
            
            transactions = tx_data['result']
            print(f"📊 {len(transactions)} تراکنش یافت شد")
            
            # بررسی تراکنش‌های ایجاد قرارداد
            for tx in transactions:
                if tx.get('to') == '':  # تراکنش ایجاد قرارداد
                    print(f"🔍 بررسی تراکنش ایجاد قرارداد: {tx['hash']}")
                    
                    # دریافت آدرس قرارداد
                    receipt_url = f"{base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx['hash']}&apikey={api_key}"
                    receipt_response = requests.get(receipt_url)
                    
                    if receipt_response.status_code == 200:
                        receipt_data = receipt_response.json()
                        
                        if receipt_data.get('result') and receipt_data['result'].get('contractAddress'):
                            contract_address = receipt_data['result']['contractAddress']
                            
                            # محاسبه هزینه
                            gas_used = int(tx.get('gasUsed', 0))
                            gas_price = int(tx.get('gasPrice', 0))
                            
                            if gas_used > 0 and gas_price > 0:
                                cost_wei = gas_used * gas_price
                                cost_eth = wei_to_eth(cost_wei)
                                cost_usd = cost_eth * eth_price
                                
                                timestamp = int(tx.get('timeStamp', 0))
                                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                                
                                contract_info = {
                                    'contract_address': contract_address,
                                    'creator_address': tx['from'],
                                    'transaction_hash': tx['hash'],
                                    'block_number': int(tx['blockNumber']),
                                    'date': date_str,
                                    'timestamp': timestamp,
                                    'gas_used': gas_used,
                                    'gas_price_gwei': gas_price / 10**9,
                                    'creation_cost_eth': cost_eth,
                                    'creation_cost_usd': cost_usd
                                }
                                
                                contracts_found.append(contract_info)
                                
                                print(f"✅ قرارداد یافت شد:")
                                print(f"   آدرس: {contract_address}")
                                print(f"   هزینه: ${cost_usd:.2f} ({cost_eth:.6f} ETH)")
                                print(f"   تاریخ: {date_str}")
                                print()
                    
                    time.sleep(0.2)  # Rate limiting
            
            time.sleep(0.5)  # Rate limiting بین صفحات
        
        return contracts_found, eth_price
        
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        return [], 0

def main():
    print("="*60)
    print("🔍 تست ساده جستجوی قراردادهای اتریوم")
    print("="*60)
    
    contracts, eth_price = find_recent_contracts()
    
    if contracts:
        print(f"\n🎉 تعداد کل قراردادهای یافت شده: {len(contracts)}")
        
        # فیلتر قراردادهای بالای 5 دلار
        expensive_contracts = [c for c in contracts if c['creation_cost_usd'] >= 5.0]
        print(f"💰 قراردادهای بالای $5: {len(expensive_contracts)}")
        
        # فیلتر قراردادهای بالای 15 دلار
        very_expensive_contracts = [c for c in contracts if c['creation_cost_usd'] >= 15.0]
        print(f"💎 قراردادهای بالای $15: {len(very_expensive_contracts)}")
        
        if expensive_contracts:
            # مرتب‌سازی بر اساس هزینه
            sorted_contracts = sorted(expensive_contracts, key=lambda x: x['creation_cost_usd'], reverse=True)
            
            print(f"\n🏆 گران‌ترین قراردادها:")
            for i, contract in enumerate(sorted_contracts[:10], 1):
                print(f"{i:2d}. ${contract['creation_cost_usd']:8.2f} - {contract['contract_address']}")
                print(f"     تاریخ: {contract['date']}")
                print(f"     سازنده: {contract['creator_address']}")
                print()
            
            # ذخیره در فایل
            filename = f"ethereum_contracts_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            output_data = {
                'search_info': {
                    'search_date': datetime.now().isoformat(),
                    'eth_price_usd': eth_price,
                    'total_contracts': len(contracts),
                    'contracts_above_5usd': len(expensive_contracts),
                    'contracts_above_15usd': len(very_expensive_contracts)
                },
                'contracts': sorted_contracts
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 نتایج در فایل {filename} ذخیره شد")
        
    else:
        print("😔 هیچ قراردادی یافت نشد")

if __name__ == "__main__":
    main()
