#!/usr/bin/env python3
"""
Ethereum Contracts $10+ Filter
قراردادهای اتریوم با هزینه بیش از 10 دلار
"""

import json
import requests
import time
from datetime import datetime

def main():
    print("💰 Ethereum Contracts $10+ Filter")
    print("=" * 40)
    
    # دریافت قیمت اتریوم
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")
        eth_price = response.json()['ethereum']['usd']
        print(f"💰 قیمت ETH: ${eth_price:,.2f}")
    except:
        eth_price = 4471.32
        print(f"💰 قیمت ETH (پیش‌فرض): ${eth_price:,.2f}")
    
    # خواندن نتایج قبلی
    try:
        with open('ethereum_contracts_combined_unique_20250831_200242.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            contracts = data.get('contracts', [])
    except FileNotFoundError:
        print("❌ فایل نتایج یافت نشد")
        return
    
    print(f"📋 بررسی {len(contracts)} قرارداد...")
    
    # فیلتر قراردادهای بیش از 10 دلار
    expensive_contracts_10 = []
    expensive_contracts_50 = []
    total_cost_10 = 0
    total_cost_50 = 0
    
    api_key = '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY'
    base_url = "https://api.etherscan.io/api"
    
    for i, contract in enumerate(contracts, 1):
        print(f"🔍 {i}/{len(contracts)}: {contract['address']}")
        
        try:
            # دریافت جزئیات تراکنش
            tx_url = f"{base_url}?module=proxy&action=eth_getTransactionByHash&txhash={contract['tx_hash']}&apikey={api_key}"
            tx_response = requests.get(tx_url)
            tx_data = tx_response.json()
            
            receipt_url = f"{base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={contract['tx_hash']}&apikey={api_key}"
            receipt_response = requests.get(receipt_url)
            receipt_data = receipt_response.json()
            
            if tx_data.get('result') and receipt_data.get('result'):
                # محاسبه هزینه واقعی
                gas_used = int(receipt_data['result'].get('gasUsed', '0'), 16)
                gas_price = int(tx_data['result'].get('gasPrice', '0'), 16)
                
                cost_eth = (gas_used * gas_price) / (10**18)
                cost_usd = cost_eth * eth_price
                
                contract_info = {
                    **contract,
                    'gas_used': gas_used,
                    'gas_price_gwei': gas_price / 10**9,
                    'cost_eth': cost_eth,
                    'cost_usd': cost_usd
                }
                
                print(f"   💰 ${cost_usd:.2f} ({cost_eth:.6f} ETH)")
                
                # فیلتر 10 دلار
                if cost_usd >= 10:
                    expensive_contracts_10.append(contract_info)
                    total_cost_10 += cost_usd
                    print(f"   ✅ >$10 (مجموع: ${total_cost_10:.2f})")
                
                # فیلتر 50 دلار
                if cost_usd >= 50:
                    expensive_contracts_50.append(contract_info)
                    total_cost_50 += cost_usd
                    print(f"   🏆 >$50 (مجموع: ${total_cost_50:.2f})")
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"   ❌ خطا: {str(e)}")
    
    # نتایج
    print(f"\n" + "="*50)
    print("📊 نتایج نهایی")
    print("="*50)
    
    print(f"💰 قراردادهای >$10:")
    print(f"   تعداد: {len(expensive_contracts_10)}")
    print(f"   مجموع هزینه: ${total_cost_10:.2f}")
    print(f"   هدف $1,400: {'✅ رسیده' if total_cost_10 >= 1400 else '❌ نرسیده'}")
    
    print(f"\n💎 قراردادهای >$50:")
    print(f"   تعداد: {len(expensive_contracts_50)}")
    print(f"   مجموع هزینه: ${total_cost_50:.2f}")
    
    # ذخیره نتایج
    if expensive_contracts_10:
        filename_10 = f"contracts_10dollar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename_10, 'w', encoding='utf-8') as f:
            json.dump({
                'criteria': 'contracts >$10',
                'total_contracts': len(expensive_contracts_10),
                'total_cost_usd': total_cost_10,
                'target_1400_achieved': total_cost_10 >= 1400,
                'contracts': expensive_contracts_10
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 قراردادهای >$10 ذخیره شد: {filename_10}")
        
        # نمایش گران‌ترین‌ها
        sorted_10 = sorted(expensive_contracts_10, key=lambda x: x['cost_usd'], reverse=True)
        print(f"\n💰 گران‌ترین قراردادهای >$10:")
        for i, contract in enumerate(sorted_10[:5], 1):
            print(f"{i}. {contract['address']}")
            print(f"   💰 ${contract['cost_usd']:.2f}")
            print(f"   📅 {contract['date']}")
    
    if expensive_contracts_50:
        filename_50 = f"contracts_50dollar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename_50, 'w', encoding='utf-8') as f:
            json.dump({
                'criteria': 'contracts >$50',
                'total_contracts': len(expensive_contracts_50),
                'total_cost_usd': total_cost_50,
                'contracts': expensive_contracts_50
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 قراردادهای >$50 ذخیره شد: {filename_50}")

if __name__ == "__main__":
    main()
