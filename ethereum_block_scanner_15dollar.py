#!/usr/bin/env python3
"""
Ethereum Block Scanner - Find Contracts with $15+ Transaction Fee
اسکنر بلاک اتریوم - یافتن قراردادها با هزینه تراکنش بالای 15 دلار
"""

import requests
import json
from datetime import datetime
from decimal import Decimal
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EthereumBlockScanner:
    def __init__(self):
        # API Key
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
        self.etherscan_base_url = "https://api.etherscan.io/api"
        
        # حد آستانه هزینه (کاهش به 1 دلار برای تست)
        self.min_fee_usd = 1.0
        
        # قیمت ETH
        self.eth_price_usd = None
        
        # آمار
        self.stats = {
            'blocks_scanned': 0,
            'transactions_checked': 0,
            'contracts_found': 0,
            'expensive_contracts': 0,
            'api_calls': 0
        }
        
        print("🔍 اسکنر بلاک اتریوم - یافتن قراردادهای بالای $15")
        print(f"💰 حد آستانه: ${self.min_fee_usd}")
        print(f"🔑 API Key: {self.etherscan_api_key[:8]}...")

    def get_eth_price(self):
        """دریافت قیمت ETH فعلی"""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.eth_price_usd = float(data["ethereum"]["usd"])
                print(f"💰 قیمت ETH: ${self.eth_price_usd:,.2f}")
                return self.eth_price_usd
            else:
                print("⚠️ نتوانستم قیمت ETH را دریافت کنم، از قیمت پیش‌فرض استفاده می‌کنم")
                self.eth_price_usd = 3000.0
                return self.eth_price_usd
                
        except Exception as e:
            print(f"❌ خطا در دریافت قیمت ETH: {str(e)}")
            self.eth_price_usd = 3000.0
            return self.eth_price_usd

    def wei_to_eth(self, wei):
        """تبدیل Wei به ETH"""
        return float(Decimal(wei) / Decimal(10**18))

    def calculate_transaction_fee_usd(self, gas_used, gas_price):
        """محاسبه هزینه تراکنش به USD"""
        try:
            # محاسبه هزینه به Wei
            fee_wei = int(gas_used) * int(gas_price)
            
            # تبدیل به ETH
            fee_eth = self.wei_to_eth(fee_wei)
            
            # تبدیل به USD
            fee_usd = fee_eth * self.eth_price_usd
            
            return fee_eth, fee_usd
            
        except Exception as e:
            print(f"❌ خطا در محاسبه هزینه: {str(e)}")
            return 0.0, 0.0

    def get_latest_block(self):
        """دریافت شماره آخرین بلاک"""
        try:
            url = f"{self.etherscan_base_url}?module=proxy&action=eth_blockNumber&apikey={self.etherscan_api_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if data.get('result'):
                latest_block = int(data['result'], 16)
                print(f"📦 آخرین بلاک: {latest_block:,}")
                return latest_block
            else:
                print("❌ نتوانستم آخرین بلاک را دریافت کنم")
                return None
                
        except Exception as e:
            print(f"❌ خطا در دریافت آخرین بلاک: {str(e)}")
            return None

    def get_block_transactions(self, block_number):
        """دریافت تراکنش‌های یک بلاک"""
        try:
            # تبدیل شماره بلاک به hex
            block_hex = hex(block_number)
            
            url = f"{self.etherscan_base_url}?module=proxy&action=eth_getBlockByNumber&tag={block_hex}&boolean=true&apikey={self.etherscan_api_key}"
            response = requests.get(url, timeout=15)
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if data.get('result') and data['result'].get('transactions'):
                transactions = data['result']['transactions']
                return transactions
            else:
                return []
                
        except Exception as e:
            print(f"❌ خطا در دریافت تراکنش‌های بلاک {block_number}: {str(e)}")
            return []

    def get_transaction_receipt(self, tx_hash):
        """دریافت receipt تراکنش برای یافتن آدرس قرارداد"""
        try:
            url = f"{self.etherscan_base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={self.etherscan_api_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if data.get('result'):
                return data['result']
            else:
                return None
                
        except Exception as e:
            print(f"❌ خطا در دریافت receipt: {str(e)}")
            return None

    def scan_block_for_expensive_contracts(self, block_number):
        """اسکن یک بلاک برای یافتن قراردادهای گران"""
        expensive_contracts = []
        
        # دریافت تراکنش‌های بلاک
        transactions = self.get_block_transactions(block_number)
        
        if not transactions:
            return expensive_contracts
        
        self.stats['transactions_checked'] += len(transactions)
        
        for tx in transactions:
            try:
                # بررسی اینکه آیا تراکنش ایجاد قرارداد است یا نه
                if tx.get('to') is None or tx.get('to') == '':
                    # این تراکنش ایجاد قرارداد است
                    gas_used = tx.get('gas', '0x0')
                    gas_price = tx.get('gasPrice', '0x0')
                    
                    # تبدیل از hex به int
                    gas_used_int = int(gas_used, 16) if isinstance(gas_used, str) else gas_used
                    gas_price_int = int(gas_price, 16) if isinstance(gas_price, str) else gas_price
                    
                    # محاسبه هزینه
                    fee_eth, fee_usd = self.calculate_transaction_fee_usd(gas_used_int, gas_price_int)
                    
                    # بررسی آستانه هزینه
                    if fee_usd >= self.min_fee_usd:
                        # دریافت receipt برای یافتن آدرس قرارداد
                        receipt = self.get_transaction_receipt(tx['hash'])
                        
                        if receipt and receipt.get('contractAddress'):
                            contract_address = receipt['contractAddress']
                            
                            # محاسبه gas واقعی استفاده شده از receipt
                            actual_gas_used = int(receipt.get('gasUsed', '0x0'), 16)
                            actual_fee_eth, actual_fee_usd = self.calculate_transaction_fee_usd(actual_gas_used, gas_price_int)
                            
                            if actual_fee_usd >= self.min_fee_usd:
                                contract_info = {
                                    'contract_address': contract_address,
                                    'creator_address': tx['from'],
                                    'transaction_hash': tx['hash'],
                                    'block_number': block_number,
                                                                'timestamp': int(receipt.get('blockNumber', '0x0'), 16),
                            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'gas_limit': gas_used_int,
                                    'gas_used': actual_gas_used,
                                    'gas_price': gas_price_int,
                                    'gas_price_gwei': gas_price_int / 10**9,
                                    'transaction_fee_eth': actual_fee_eth,
                                    'transaction_fee_usd': actual_fee_usd,
                                    'value_eth': self.wei_to_eth(int(tx.get('value', '0x0'), 16)),
                                    'status': receipt.get('status', '0x1')
                                }
                                
                                expensive_contracts.append(contract_info)
                                self.stats['expensive_contracts'] += 1
                                
                                print(f"✅ قرارداد گران یافت شد!")
                                print(f"   آدرس: {contract_address}")
                                print(f"   هزینه: ${actual_fee_usd:.2f} ({actual_fee_eth:.6f} ETH)")
                                print(f"   بلاک: {block_number}")
                                print()
                        
                        time.sleep(0.1)  # Rate limiting
                    
                    self.stats['contracts_found'] += 1
                    
            except Exception as e:
                print(f"❌ خطا در پردازش تراکنش {tx.get('hash', 'unknown')}: {str(e)}")
                continue
        
        return expensive_contracts

    def scan_blocks_range(self, start_block, num_blocks=100):
        """اسکن بازه‌ای از بلاک‌ها"""
        all_expensive_contracts = []
        
        print(f"🔍 شروع اسکن {num_blocks} بلاک از {start_block:,}")
        
        for i in range(num_blocks):
            current_block = start_block - i
            
            if current_block < 0:
                break
            
            print(f"📦 اسکن بلاک {current_block:,} ({i+1}/{num_blocks})")
            
            # اسکن بلاک
            expensive_contracts = self.scan_block_for_expensive_contracts(current_block)
            all_expensive_contracts.extend(expensive_contracts)
            
            self.stats['blocks_scanned'] += 1
            
            # نمایش پیشرفت
            if (i + 1) % 10 == 0:
                print(f"📊 پیشرفت: {i+1}/{num_blocks} بلاک - {len(all_expensive_contracts)} قرارداد گران یافت شد")
            
            # Rate limiting
            time.sleep(0.2)
        
        return all_expensive_contracts

    def save_results(self, contracts, filename=None):
        """ذخیره نتایج"""
        if not filename:
            filename = f"ethereum_expensive_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            output_data = {
                'scan_info': {
                    'scan_date': datetime.now().isoformat(),
                    'eth_price_usd': self.eth_price_usd,
                    'min_fee_threshold_usd': self.min_fee_usd,
                    'statistics': self.stats
                },
                'total_expensive_contracts': len(contracts),
                'contracts': contracts
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 نتایج در فایل {filename} ذخیره شد")
            return filename
            
        except Exception as e:
            print(f"❌ خطا در ذخیره: {str(e)}")
            return None

    def print_summary(self, contracts):
        """نمایش خلاصه نتایج"""
        print("\n" + "="*60)
        print("📊 خلاصه نتایج اسکن")
        print("="*60)
        
        print(f"📦 تعداد بلاک‌های اسکن شده: {self.stats['blocks_scanned']:,}")
        print(f"🔍 تعداد تراکنش‌های بررسی شده: {self.stats['transactions_checked']:,}")
        print(f"🏗️ تعداد کل قراردادهای یافت شده: {self.stats['contracts_found']:,}")
        print(f"💰 قراردادهای بالای ${self.min_fee_usd}: {len(contracts):,}")
        print(f"🌐 تعداد API calls: {self.stats['api_calls']:,}")
        print(f"💵 قیمت ETH: ${self.eth_price_usd:,.2f}")
        
        if contracts:
            # آمار هزینه‌ها
            fees = [c['transaction_fee_usd'] for c in contracts]
            avg_fee = sum(fees) / len(fees)
            max_fee = max(fees)
            min_fee = min(fees)
            
            print(f"\n💰 آمار هزینه‌های تراکنش:")
            print(f"   میانگین: ${avg_fee:.2f}")
            print(f"   حداکثر: ${max_fee:.2f}")
            print(f"   حداقل: ${min_fee:.2f}")
            
            # نمایش گران‌ترین قراردادها
            sorted_contracts = sorted(contracts, key=lambda x: x['transaction_fee_usd'], reverse=True)
            print(f"\n🏆 گران‌ترین قراردادها:")
            for i, contract in enumerate(sorted_contracts[:5], 1):
                print(f"   {i}. ${contract['transaction_fee_usd']:.2f} - {contract['contract_address']}")
                print(f"      تاریخ: {contract['date']}")
                print(f"      بلاک: {contract['block_number']:,}")

    def run(self, num_blocks=50):
        """اجرای اسکن اصلی"""
        print("\n🚀 شروع اسکن بلاک‌ها...")
        
        try:
            # دریافت قیمت ETH
            self.get_eth_price()
            
            # دریافت آخرین بلاک
            latest_block = self.get_latest_block()
            if not latest_block:
                print("❌ نتوانستم آخرین بلاک را دریافت کنم")
                return
            
            # شروع اسکن از آخرین بلاک
            expensive_contracts = self.scan_blocks_range(latest_block, num_blocks)
            
            # نمایش خلاصه
            self.print_summary(expensive_contracts)
            
            # ذخیره نتایج
            if expensive_contracts:
                filename = self.save_results(expensive_contracts)
                print(f"\n✅ اسکن تکمیل شد! {len(expensive_contracts)} قرارداد گران یافت شد.")
                if filename:
                    print(f"📁 فایل ذخیره شده: {filename}")
            else:
                print(f"\n😔 هیچ قراردادی با هزینه بالای ${self.min_fee_usd} یافت نشد")
            
        except KeyboardInterrupt:
            print("\n⏹️ اسکن توسط کاربر متوقف شد")
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")

def main():
    print("="*70)
    print("🔍 Ethereum Block Scanner - Find $15+ Transaction Fee Contracts")
    print("اسکنر بلاک اتریوم - یافتن قراردادهای بالای 15 دلار هزینه تراکنش")
    print("="*70)
    
    try:
        scanner = EthereumBlockScanner()
        
        # دریافت تعداد بلاک‌ها از کاربر
        num_blocks = input("\n🔢 تعداد بلاک‌هایی که می‌خواهید اسکن کنید (پیش‌فرض: 50): ")
        try:
            num_blocks = int(num_blocks) if num_blocks.strip() else 50
        except:
            num_blocks = 50
        
        print(f"📦 اسکن {num_blocks} بلاک آخر...")
        
        scanner.run(num_blocks)
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")
    
    print("\n" + "="*70)
    print("✅ پایان عملیات")

if __name__ == "__main__":
    main()
