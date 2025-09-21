#!/usr/bin/env python3
"""
اسکنر ساده قراردادهای 15 دلاری
Simple $15+ Contracts Scanner
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

class Simple15DollarScanner:
    def __init__(self):
        # API Keys
        api_keys_str = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
        self.api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
        self.current_api_index = 0
        
        self.base_url = "https://api.etherscan.io/api"
        
        # تنظیمات
        self.min_fee_usd = 15.0
        self.max_total_usd = 1470.0
        self.current_total_usd = 0.0
        self.eth_price_usd = None
        
        # آمار
        self.contracts_found = []
        self.api_calls = 0
        self.errors = 0
        
        print(f"🔍 اسکنر ساده قراردادهای بالای ${self.min_fee_usd}")
        print(f"🎯 توقف در مجموع: ${self.max_total_usd}")
        print(f"🔑 تعداد کلیدها: {len(self.api_keys)}")

    def get_current_api_key(self):
        return self.api_keys[self.current_api_index]

    def rotate_api_key(self):
        old_index = self.current_api_index
        self.current_api_index = (self.current_api_index + 1) % len(self.api_keys)
        print(f"🔄 تغییر از کلید {old_index + 1} به کلید {self.current_api_index + 1}")
        time.sleep(3)

    def get_eth_price(self):
        """دریافت قیمت ETH"""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.eth_price_usd = float(data["ethereum"]["usd"])
                print(f"💰 قیمت ETH: ${self.eth_price_usd:,.2f}")
                return True
        except:
            pass
        
        self.eth_price_usd = 3000.0
        print(f"⚠️ استفاده از قیمت پیش‌فرض: ${self.eth_price_usd}")
        return True

    def wei_to_eth(self, wei):
        return float(Decimal(wei) / Decimal(10**18))

    def safe_api_call(self, url, max_retries=3):
        """درخواست API با مدیریت خطا"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=20)
                self.api_calls += 1
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # بررسی خطاهای API
                    if data.get('message') and 'rate limit' in data.get('message', '').lower():
                        print(f"🚫 Rate limit - کلید {self.current_api_index + 1}")
                        if len(self.api_keys) > 1:
                            self.rotate_api_key()
                            continue
                        else:
                            time.sleep(5)
                            continue
                    
                    return data
                else:
                    print(f"❌ HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout - تلاش {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
            except Exception as e:
                print(f"❌ خطا: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        self.errors += 1
        return None

    def get_latest_block(self):
        """دریافت آخرین بلاک"""
        url = f"{self.base_url}?module=proxy&action=eth_blockNumber&apikey={self.get_current_api_key()}"
        data = self.safe_api_call(url)
        
        if data and data.get('result'):
            try:
                return int(data['result'], 16)
            except:
                pass
        return None

    def scan_recent_blocks(self, num_blocks=1000):
        """اسکن بلاک‌های اخیر"""
        print(f"\n🔍 اسکن {num_blocks} بلاک اخیر...")
        
        # دریافت آخرین بلاک
        latest_block = self.get_latest_block()
        if not latest_block:
            print("❌ نتوانستم آخرین بلاک را دریافت کنم")
            return
        
        print(f"📦 آخرین بلاک: {latest_block:,}")
        print(f"🔍 اسکن از بلاک {latest_block - num_blocks:,} تا {latest_block:,}")
        
        for i in range(num_blocks):
            current_block = latest_block - i
            
            print(f"📦 بلاک {current_block:,} ({i+1}/{num_blocks})")
            
            # دریافت تراکنش‌های بلاک
            block_hex = hex(current_block)
            url = f"{self.base_url}?module=proxy&action=eth_getBlockByNumber&tag={block_hex}&boolean=true&apikey={self.get_current_api_key()}"
            
            block_data = self.safe_api_call(url)
            
            if not block_data or not block_data.get('result'):
                continue
            
            transactions = block_data['result'].get('transactions', [])
            
            # بررسی تراکنش‌های ایجاد قرارداد
            for tx in transactions:
                if tx.get('to') is None or tx.get('to') == '':
                    # تراکنش ایجاد قرارداد
                    try:
                        gas_used = int(tx.get('gas', '0x0'), 16)
                        gas_price = int(tx.get('gasPrice', '0x0'), 16)
                        
                        # محاسبه هزینه اولیه
                        fee_wei = gas_used * gas_price
                        fee_eth = self.wei_to_eth(fee_wei)
                        fee_usd = fee_eth * self.eth_price_usd
                        
                        # اگر هزینه بالای حد آستانه است
                        if fee_usd >= self.min_fee_usd:
                            # دریافت receipt برای آدرس قرارداد
                            receipt_url = f"{self.base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx['hash']}&apikey={self.get_current_api_key()}"
                            receipt_data = self.safe_api_call(receipt_url)
                            
                            if receipt_data and receipt_data.get('result') and receipt_data['result'].get('contractAddress'):
                                contract_address = receipt_data['result']['contractAddress']
                                
                                # محاسبه هزینه واقعی
                                actual_gas_used = int(receipt_data['result'].get('gasUsed', '0x0'), 16)
                                actual_fee_wei = actual_gas_used * gas_price
                                actual_fee_eth = self.wei_to_eth(actual_fee_wei)
                                actual_fee_usd = actual_fee_eth * self.eth_price_usd
                                
                                if actual_fee_usd >= self.min_fee_usd:
                                    # بررسی حد مجموع
                                    if self.current_total_usd + actual_fee_usd > self.max_total_usd:
                                        print(f"🛑 حد آستانه ${self.max_total_usd} رسیده!")
                                        print(f"   مجموع فعلی: ${self.current_total_usd:.2f}")
                                        print(f"   قرارداد جدید: ${actual_fee_usd:.2f}")
                                        return True  # توقف
                                    
                                    # اضافه کردن قرارداد
                                    contract_info = {
                                        'contract_address': contract_address,
                                        'creator_address': tx['from'],
                                        'transaction_hash': tx['hash'],
                                        'block_number': current_block,
                                        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'gas_used': actual_gas_used,
                                        'gas_price_gwei': gas_price / 10**9,
                                        'transaction_fee_eth': actual_fee_eth,
                                        'transaction_fee_usd': actual_fee_usd
                                    }
                                    
                                    self.contracts_found.append(contract_info)
                                    self.current_total_usd += actual_fee_usd
                                    
                                    print(f"✅ قرارداد گران: {contract_address}")
                                    print(f"   هزینه: ${actual_fee_usd:.2f}")
                                    print(f"   مجموع: ${self.current_total_usd:.2f} / ${self.max_total_usd}")
                                    print()
                                    
                                    # بررسی رسیدن به حد
                                    if self.current_total_usd >= self.max_total_usd:
                                        print(f"🎯 حد آستانه رسیده شد!")
                                        return True  # توقف
                    
                    except Exception as e:
                        print(f"❌ خطا در پردازش تراکنش: {str(e)}")
                        continue
            
            # نمایش پیشرفت
            if (i + 1) % 50 == 0:
                print(f"📊 پیشرفت: {i+1}/{num_blocks} - {len(self.contracts_found)} قرارداد - ${self.current_total_usd:.2f}")
            
            # تاخیر
            time.sleep(1)
        
        return False  # اتمام عادی

    def save_results(self):
        """ذخیره نتایج"""
        filename = f"simple_scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_data = {
            'scan_info': {
                'scan_date': datetime.now().isoformat(),
                'eth_price_usd': self.eth_price_usd,
                'min_fee_threshold': self.min_fee_usd,
                'max_total_threshold': self.max_total_usd,
                'actual_total': self.current_total_usd,
                'api_calls': self.api_calls,
                'errors': self.errors
            },
            'total_contracts': len(self.contracts_found),
            'contracts': self.contracts_found
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 فایل ذخیره شد: {filename}")
            return filename
        except Exception as e:
            print(f"❌ خطا در ذخیره: {str(e)}")
            return None

    def run(self, num_blocks=500):
        """اجرای اسکن"""
        try:
            # دریافت قیمت ETH
            self.get_eth_price()
            
            # اسکن بلاک‌ها
            stopped_early = self.scan_recent_blocks(num_blocks)
            
            # نمایش نتایج
            print(f"\n📊 نتایج نهایی:")
            print(f"   🔢 قراردادهای یافت شده: {len(self.contracts_found)}")
            print(f"   💰 مجموع هزینه‌ها: ${self.current_total_usd:.2f}")
            print(f"   🌐 API calls: {self.api_calls}")
            print(f"   ❌ خطاها: {self.errors}")
            
            if stopped_early:
                print(f"   🛑 متوقف شد: حد آستانه رسیده")
            else:
                print(f"   ✅ اسکن کامل انجام شد")
            
            # ذخیره فایل
            if self.contracts_found:
                self.save_results()
            
        except KeyboardInterrupt:
            print(f"\n⏹️ متوقف شد توسط کاربر")
            if self.contracts_found:
                self.save_results()
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")

def main():
    print("="*50)
    print("🔍 اسکنر ساده قراردادهای 15 دلاری")
    print("="*50)
    
    scanner = Simple15DollarScanner()
    
    # دریافت تعداد بلاک
    try:
        num_blocks = input(f"\nتعداد بلاک برای اسکن (پیش‌فرض: 500): ").strip()
        num_blocks = int(num_blocks) if num_blocks else 500
    except:
        num_blocks = 500
    
    print(f"🚀 شروع اسکن {num_blocks} بلاک...")
    scanner.run(num_blocks)

if __name__ == "__main__":
    main()
