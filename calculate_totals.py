#!/usr/bin/env python3
"""
محاسبه مجموع هزینه‌های قراردادهای اتریوم
Calculate total costs of Ethereum contracts
"""

import json

def calculate_contract_totals(filename):
    """محاسبه آمار کلی فایل قراردادها"""
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        contracts = data.get('contracts', [])
        
        if not contracts:
            print("❌ هیچ قراردادی در فایل یافت نشد")
            return
        
        # محاسبه مجموع
        total_usd = sum(contract.get('transaction_fee_usd', 0) for contract in contracts)
        
        # آمار کلی
        print("="*60)
        print("📊 آمار کلی قراردادهای اتریوم")
        print("="*60)
        
        print(f"📄 نام فایل: {filename}")
        print(f"📅 تاریخ اسکن: {data.get('scan_info', {}).get('scan_date', 'نامشخص')}")
        print(f"💰 قیمت ETH: ${data.get('scan_info', {}).get('eth_price_usd', 0):,.2f}")
        
        print(f"\n🔢 تعداد کل قراردادها: {len(contracts):,}")
        print(f"💵 مجموع کل هزینه‌های تراکنش: ${total_usd:,.2f}")
        print(f"📊 میانگین هزینه هر قرارداد: ${total_usd/len(contracts):,.2f}")
        
        # یافتن گران‌ترین و ارزان‌ترین
        max_contract = max(contracts, key=lambda x: x.get('transaction_fee_usd', 0))
        min_contract = min(contracts, key=lambda x: x.get('transaction_fee_usd', 0))
        
        print(f"\n🏆 گران‌ترین قرارداد:")
        print(f"   هزینه: ${max_contract['transaction_fee_usd']:,.2f}")
        print(f"   آدرس: {max_contract['contract_address']}")
        print(f"   تاریخ: {max_contract['date']}")
        
        print(f"\n💎 ارزان‌ترین قرارداد:")
        print(f"   هزینه: ${min_contract['transaction_fee_usd']:,.2f}")
        print(f"   آدرس: {min_contract['contract_address']}")
        
        # تحلیل بر اساس آستانه‌های مختلف
        thresholds = [1, 5, 10, 15, 20, 50, 100]
        
        print(f"\n📈 تحلیل بر اساس آستانه‌های هزینه:")
        for threshold in thresholds:
            above_threshold = [c for c in contracts if c.get('transaction_fee_usd', 0) >= threshold]
            total_above = sum(c.get('transaction_fee_usd', 0) for c in above_threshold)
            
            if above_threshold:
                print(f"   بالای ${threshold}: {len(above_threshold):,} قرارداد - مجموع: ${total_above:,.2f}")
        
        # آمار Gas
        total_gas_used = sum(contract.get('gas_used', 0) for contract in contracts)
        avg_gas_price = sum(contract.get('gas_price_gwei', 0) for contract in contracts) / len(contracts)
        
        print(f"\n⛽ آمار Gas:")
        print(f"   مجموع Gas مصرفی: {total_gas_used:,}")
        print(f"   میانگین Gas Price: {avg_gas_price:.2f} Gwei")
        
        # 10 گران‌ترین قرارداد
        sorted_contracts = sorted(contracts, key=lambda x: x.get('transaction_fee_usd', 0), reverse=True)
        
        print(f"\n🎯 10 گران‌ترین قرارداد:")
        for i, contract in enumerate(sorted_contracts[:10], 1):
            print(f"   {i:2d}. ${contract['transaction_fee_usd']:8.2f} - {contract['contract_address'][:10]}...")
        
        print("\n" + "="*60)
        
        return {
            'total_contracts': len(contracts),
            'total_usd': total_usd,
            'average_usd': total_usd/len(contracts),
            'max_usd': max_contract['transaction_fee_usd'],
            'min_usd': min_contract['transaction_fee_usd']
        }
        
    except FileNotFoundError:
        print(f"❌ فایل {filename} یافت نشد")
        return None
    except json.JSONDecodeError:
        print(f"❌ خطا در خواندن فایل JSON: {filename}")
        return None
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")
        return None

def main():
    filename = "ethereum_expensive_contracts_20250901_021213.json"
    
    print("🔍 محاسبه‌گر آمار قراردادهای اتریوم")
    print("Ethereum Contracts Statistics Calculator")
    
    stats = calculate_contract_totals(filename)
    
    if stats:
        print(f"\n✅ محاسبات تکمیل شد!")
        print(f"📊 خلاصه: {stats['total_contracts']:,} قرارداد با مجموع ${stats['total_usd']:,.2f}")

if __name__ == "__main__":
    main()
