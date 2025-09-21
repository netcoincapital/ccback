#!/usr/bin/env python3
"""
Ethereum Date Range Scanner - Find Contracts in Specific Date Range
اسکنر بازه زمانی اتریوم - یافتن قراردادها در بازه زمانی مشخص
"""

import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EthereumDateRangeScanner:
    def __init__(self):
        # API Keys - پردازش چندین کلید از متغیر محیطی
        api_keys_str = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
        self.api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
        self.current_api_index = 0
        self.api_request_counts = {i: 0 for i in range(len(self.api_keys))}
        self.api_error_counts = {i: 0 for i in range(len(self.api_keys))}
        self.last_request_time = {i: 0 for i in range(len(self.api_keys))}
        
        self.etherscan_base_url = "https://api.etherscan.io/api"
        
        # حد آستانه هزینه (15 دلار)
        self.min_fee_usd = 15.0
        
        # حد آستانه مجموع هزینه‌ها (1470 دلار)
        self.max_total_usd = 1470.0
        self.current_total_usd = 0.0
        
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
        
        print("🔍 اسکنر بازه زمانی اتریوم - یافتن قراردادهای بالای $15")
        print(f"💰 حد آستانه هر قرارداد: ${self.min_fee_usd}")
        print(f"🎯 حد آستانه مجموع: ${self.max_total_usd}")
        print(f"🔑 تعداد API Keys: {len(self.api_keys)}")
        for i, key in enumerate(self.api_keys):
            print(f"   کلید {i+1}: {key[:8]}...")

    def get_current_api_key(self):
        """دریافت کلید API فعلی"""
        return self.api_keys[self.current_api_index]
    
    def rotate_api_key(self, reason="محدودیت API"):
        """تغییر به کلید API بعدی"""
        old_index = self.current_api_index
        self.current_api_index = (self.current_api_index + 1) % len(self.api_keys)
        
        print(f"🔄 تغییر API Key به دلیل {reason}")
        print(f"   از کلید {old_index + 1} ({self.api_keys[old_index][:8]}...)")
        print(f"   به کلید {self.current_api_index + 1} ({self.api_keys[self.current_api_index][:8]}...)")
        
        # اضافه کردن تاخیر پس از تغییر کلید
        time.sleep(2)
    
    def handle_api_error(self, error_message, endpoint="unknown"):
        """مدیریت خطاهای API و تصمیم‌گیری برای تغییر کلید"""
        self.api_error_counts[self.current_api_index] += 1
        
        # بررسی انواع خطاهای مختلف
        should_rotate = False
        wait_time = 1
        
        error_lower = error_message.lower()
        
        if any(phrase in error_lower for phrase in ['rate limit', 'too many requests', 'exceeded']):
            print(f"🚫 محدودیت نرخ درخواست - کلید {self.current_api_index + 1}")
            should_rotate = True
            wait_time = 3
            
        elif any(phrase in error_lower for phrase in ['timeout', 'timed out']):
            print(f"⏰ Timeout - کلید {self.current_api_index + 1}")
            if self.api_error_counts[self.current_api_index] > 3:
                should_rotate = True
            wait_time = 2
            
        elif any(phrase in error_lower for phrase in ['connection', 'network', 'unreachable']):
            print(f"🔌 مشکل اتصال - کلید {self.current_api_index + 1}")
            if self.api_error_counts[self.current_api_index] > 2:
                should_rotate = True
            wait_time = 3
            
        elif any(phrase in error_lower for phrase in ['invalid', 'unauthorized', 'forbidden']):
            print(f"🔐 مشکل احراز هویت - کلید {self.current_api_index + 1}")
            should_rotate = True
            wait_time = 1
            
        elif 'expecting value' in error_lower or 'json' in error_lower:
            print(f"📄 پاسخ نامعتبر JSON - کلید {self.current_api_index + 1}")
            if self.api_error_counts[self.current_api_index] > 5:
                should_rotate = True
            wait_time = 1
        
        # اگر کلید فعلی خطاهای زیادی دارد، تغییر کن
        if self.api_error_counts[self.current_api_index] > 10:
            should_rotate = True
            print(f"❌ کلید {self.current_api_index + 1} خطاهای زیادی دارد ({self.api_error_counts[self.current_api_index]} خطا)")
        
        # تغییر کلید در صورت نیاز
        if should_rotate and len(self.api_keys) > 1:
            self.rotate_api_key(f"خطا در {endpoint}")
        
        # تاخیر قبل از تلاش مجدد
        if wait_time > 0:
            print(f"⏳ انتظار {wait_time} ثانیه...")
            time.sleep(wait_time)
        
        return True  # ادامه عملیات
    
    def wait_for_rate_limit(self):
        """انتظار برای رعایت محدودیت نرخ درخواست"""
        current_time = time.time()
        last_request = self.last_request_time[self.current_api_index]
        
        # حداقل 0.3 ثانیه بین درخواست‌ها
        min_interval = 0.3
        if current_time - last_request < min_interval:
            sleep_time = min_interval - (current_time - last_request)
            time.sleep(sleep_time)
        
        self.last_request_time[self.current_api_index] = time.time()
        self.api_request_counts[self.current_api_index] += 1
    
    def make_api_request(self, url, timeout=15, max_retries=3):
        """ارسال درخواست API با مدیریت خطا و تکرار"""
        for attempt in range(max_retries):
            try:
                # انتظار برای رعایت محدودیت
                self.wait_for_rate_limit()
                
                # ارسال درخواست
                response = requests.get(url, timeout=timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    self.stats['api_calls'] += 1
                    return data
                else:
                    error_msg = f"HTTP {response.status_code}"
                    if attempt < max_retries - 1:
                        self.handle_api_error(error_msg, "HTTP Request")
                    else:
                        print(f"❌ درخواست ناموفق پس از {max_retries} تلاش: {error_msg}")
                        return None
                        
            except requests.exceptions.Timeout:
                error_msg = "Request timed out"
                if attempt < max_retries - 1:
                    self.handle_api_error(error_msg, "Timeout")
                else:
                    print(f"❌ Timeout پس از {max_retries} تلاش")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                if attempt < max_retries - 1:
                    self.handle_api_error(error_msg, "Connection")
                else:
                    print(f"❌ خطای اتصال پس از {max_retries} تلاش")
                    return None
                    
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON response: {str(e)}"
                if attempt < max_retries - 1:
                    self.handle_api_error(error_msg, "JSON Parse")
                else:
                    print(f"❌ پاسخ JSON نامعتبر پس از {max_retries} تلاش")
                    return None
                    
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                if attempt < max_retries - 1:
                    self.handle_api_error(error_msg, "Unknown")
                else:
                    print(f"❌ خطای غیرمنتظره پس از {max_retries} تلاش: {str(e)}")
                    return None
        
        return None

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

    def get_block_by_timestamp(self, timestamp, closest='before'):
        """دریافت شماره بلاک بر اساس timestamp"""
        url = f"{self.etherscan_base_url}?module=block&action=getblocknobytime&timestamp={timestamp}&closest={closest}&apikey={self.get_current_api_key()}"
        data = self.make_api_request(url, timeout=10)
        
        if data and data.get('result') and data['result'] != 'Error! Block timestamp too far in the future':
            try:
                block_number = int(data['result'])
                return block_number
            except ValueError:
                print(f"❌ خطا در تبدیل شماره بلاک: {data['result']}")
                return None
        else:
            error_msg = data.get('result', 'Unknown error') if data else 'No response'
            print(f"❌ خطا در دریافت بلاک برای timestamp {timestamp}: {error_msg}")
            return None

    def get_block_transactions(self, block_number):
        """دریافت تراکنش‌های یک بلاک"""
        # تبدیل شماره بلاک به hex
        block_hex = hex(block_number)
        
        url = f"{self.etherscan_base_url}?module=proxy&action=eth_getBlockByNumber&tag={block_hex}&boolean=true&apikey={self.get_current_api_key()}"
        data = self.make_api_request(url, timeout=20)
        
        if data and data.get('result') and data['result'].get('transactions'):
            transactions = data['result']['transactions']
            return transactions
        else:
            return []

    def get_transaction_receipt(self, tx_hash):
        """دریافت receipt تراکنش برای یافتن آدرس قرارداد"""
        url = f"{self.etherscan_base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={self.get_current_api_key()}"
        data = self.make_api_request(url, timeout=10)
        
        if data and data.get('result'):
            return data['result']
        else:
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
                    
                    # همه قراردادها را بررسی کن (نه فقط بالای حد آستانه)
                    if fee_usd > 0:
                        # دریافت receipt برای یافتن آدرس قرارداد
                        receipt = self.get_transaction_receipt(tx['hash'])
                        
                        if receipt and receipt.get('contractAddress'):
                            contract_address = receipt['contractAddress']
                            
                            # محاسبه gas واقعی استفاده شده از receipt
                            actual_gas_used = int(receipt.get('gasUsed', '0x0'), 16)
                            actual_fee_eth, actual_fee_usd = self.calculate_transaction_fee_usd(actual_gas_used, gas_price_int)
                            
                            # فقط قراردادهای بالای حد آستانه را پردازش کن
                            if actual_fee_usd >= self.min_fee_usd:
                                # بررسی اینکه آیا با اضافه کردن این قرارداد از حد مجاز عبور می‌کنیم
                                if self.current_total_usd + actual_fee_usd > self.max_total_usd:
                                    print(f"🛑 حد آستانه مجموع ${self.max_total_usd} رسیده است!")
                                    print(f"   مجموع فعلی: ${self.current_total_usd:.2f}")
                                    print(f"   قرارداد جدید: ${actual_fee_usd:.2f}")
                                    print(f"   مجموع کل: ${self.current_total_usd + actual_fee_usd:.2f}")
                                    return expensive_contracts, True  # برگرداندن flag برای توقف
                                
                                # اضافه کردن هزینه به مجموع (فقط قراردادهای بالای $15)
                                self.current_total_usd += actual_fee_usd
                                
                                # دریافت timestamp بلاک
                                block_timestamp = int(tx.get('timestamp', '0x0'), 16) if tx.get('timestamp') else 0
                                
                                contract_info = {
                                    'contract_address': contract_address,
                                    'creator_address': tx['from'],
                                    'transaction_hash': tx['hash'],
                                    'block_number': block_number,
                                    'block_timestamp': block_timestamp,
                                    'date': datetime.fromtimestamp(block_timestamp).strftime('%Y-%m-%d %H:%M:%S') if block_timestamp else 'نامشخص',
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
                                print(f"   تاریخ: {contract_info['date']}")
                                print(f"   💰 مجموع تا کنون: ${self.current_total_usd:.2f} / ${self.max_total_usd}")
                                print()
                                
                                # بررسی رسیدن به حد آستانه مجموع
                                if self.current_total_usd >= self.max_total_usd:
                                    print(f"🎯 حد آستانه مجموع ${self.max_total_usd} رسیده شد!")
                                    print(f"📊 مجموع نهایی: ${self.current_total_usd:.2f}")
                                    return expensive_contracts, True  # توقف فوری
                            else:
                                # قراردادهای زیر $15 را نادیده بگیر
                                print(f"📝 قرارداد زیر حد آستانه نادیده گرفته شد: ${actual_fee_usd:.2f}")
                        
                        time.sleep(0.5)  # Rate limiting - افزایش تاخیر
                    
                    self.stats['contracts_found'] += 1
                    
            except Exception as e:
                print(f"❌ خطا در پردازش تراکنش {tx.get('hash', 'unknown')}: {str(e)}")
                continue
        
        return expensive_contracts, False  # برگرداندن flag برای ادامه

    def scan_date_range(self, start_date_str, end_date_str):
        """اسکن بازه زمانی مشخص"""
        try:
            # تبدیل رشته‌های تاریخ به datetime
            start_date = datetime.strptime(start_date_str, '%d-%m-%Y')
            end_date = datetime.strptime(end_date_str, '%d-%m-%Y')
            end_date = end_date.replace(hour=23, minute=59, second=59)  # انتهای روز
            
            print(f"📅 بازه زمانی مورد نظر:")
            print(f"   🟢 از: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   🔴 تا: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # تبدیل به timestamp
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            print(f"🔍 یافتن شماره بلاک‌ها...")
            
            # دریافت شماره بلاک‌های شروع و پایان
            start_block = self.get_block_by_timestamp(start_timestamp, 'after')
            end_block = self.get_block_by_timestamp(end_timestamp, 'before')
            
            if not start_block or not end_block:
                print("❌ نتوانستم شماره بلاک‌ها را دریافت کنم")
                return []
            
            print(f"📦 بازه بلاک‌ها:")
            print(f"   🟢 بلاک شروع: {start_block:,}")
            print(f"   🔴 بلاک پایان: {end_block:,}")
            print(f"   📊 تعداد بلاک‌ها: {end_block - start_block + 1:,}")
            
            # بررسی اینکه بازه خیلی بزرگ نباشد
            total_blocks = end_block - start_block + 1
            if total_blocks > 5000:
                print(f"⚠️ بازه بلاک‌ها خیلی بزرگ است ({total_blocks:,} بلاک)")
                print(f"💡 توصیه: برای جلوگیری از محدودیت API، حداکثر 5000 بلاک اسکن کنید")
                print(f"🔄 یا از چند اجرای کوچک‌تر استفاده کنید")
                response = input("آیا می‌خواهید ادامه دهید؟ (y/n): ")
                if response.lower() != 'y':
                    print("❌ عملیات لغو شد")
                    return []
                
                # اگر بازه خیلی بزرگ باشد، تاخیر بیشتری اعمال کنیم
                if total_blocks > 20000:
                    print("⚠️ بازه خیلی بزرگ است، تاخیر بین درخواست‌ها افزایش می‌یابد")
                    self.extended_delay = True
                else:
                    self.extended_delay = False
            
            # شروع اسکن
            all_expensive_contracts = []
            
            print(f"🔍 شروع اسکن {total_blocks:,} بلاک...")
            
            for current_block in range(start_block, end_block + 1):
                print(f"📦 اسکن بلاک {current_block:,} ({current_block - start_block + 1}/{total_blocks})")
                
                # اسکن بلاک
                try:
                    result = self.scan_block_for_expensive_contracts(current_block)
                    if isinstance(result, tuple) and len(result) == 2:
                        expensive_contracts, should_stop = result
                    else:
                        expensive_contracts = result if isinstance(result, list) else []
                        should_stop = False
                except Exception as e:
                    print(f"❌ خطا در اسکن بلاک {current_block}: {str(e)}")
                    expensive_contracts = []
                    should_stop = False
                all_expensive_contracts.extend(expensive_contracts)
                
                self.stats['blocks_scanned'] += 1
                
                # بررسی آیا باید متوقف شویم
                if should_stop:
                    print(f"🛑 عملیات متوقف شد - حد آستانه مجموع ${self.max_total_usd} رسیده است!")
                    print(f"📊 مجموع نهایی: ${self.current_total_usd:.2f}")
                    break
                
                # نمایش پیشرفت
                if (current_block - start_block + 1) % 100 == 0:
                    print(f"📊 پیشرفت: {current_block - start_block + 1:,}/{total_blocks:,} بلاک - {len(all_expensive_contracts)} قرارداد گران یافت شد")
                    print(f"💰 مجموع هزینه‌ها: ${self.current_total_usd:.2f} / ${self.max_total_usd}")
                
                # Rate limiting - تاخیر متغیر بر اساس اندازه بازه
                if hasattr(self, 'extended_delay') and self.extended_delay:
                    time.sleep(2.0)  # تاخیر بیشتر برای بازه‌های بزرگ
                else:
                    time.sleep(1.0)  # تاخیر عادی
            
            return all_expensive_contracts
            
        except ValueError as e:
            print(f"❌ خطا در تبدیل تاریخ: {str(e)}")
            print("فرمت صحیح: DD-MM-YYYY (مثال: 20-08-2025)")
            return []
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")
            return []

    def save_results(self, contracts, start_date, end_date, filename=None):
        """ذخیره نتایج"""
        if not filename:
            filename = f"ethereum_contracts_{start_date.replace('-', '')}_{end_date.replace('-', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            output_data = {
                'scan_info': {
                    'scan_date': datetime.now().isoformat(),
                    'start_date': start_date,
                    'end_date': end_date,
                    'eth_price_usd': self.eth_price_usd,
                    'min_fee_threshold_usd': self.min_fee_usd,
                    'max_total_threshold_usd': self.max_total_usd,
                    'actual_total_usd': self.current_total_usd,
                    'threshold_reached': self.current_total_usd >= self.max_total_usd,
                    'statistics': self.stats,
                    'api_keys_info': {
                        'total_keys': len(self.api_keys),
                        'active_key_index': self.current_api_index,
                        'key_usage': {
                            f'key_{i+1}': {
                                'requests': self.api_request_counts.get(i, 0),
                                'errors': self.api_error_counts.get(i, 0),
                                'key_preview': key[:8] + '...'
                            } for i, key in enumerate(self.api_keys)
                        }
                    }
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
        print(f"🎯 مجموع هزینه‌های قراردادهای بالای ${self.min_fee_usd}: ${self.current_total_usd:.2f}")
        print(f"🚩 حد آستانه مجموع: ${self.max_total_usd}")
        print(f"🌐 تعداد API calls: {self.stats['api_calls']:,}")
        print(f"💵 قیمت ETH: ${self.eth_price_usd:,.2f}")
        
        # آمار API Keys
        print(f"\n🔑 آمار API Keys:")
        for i, key in enumerate(self.api_keys):
            requests_count = self.api_request_counts.get(i, 0)
            errors_count = self.api_error_counts.get(i, 0)
            success_rate = ((requests_count - errors_count) / requests_count * 100) if requests_count > 0 else 0
            status = "🟢 فعال" if i == self.current_api_index else "⚪ غیرفعال"
            print(f"   کلید {i+1} ({key[:8]}...): {requests_count:,} درخواست, {errors_count} خطا, {success_rate:.1f}% موفقیت {status}")
        
        if self.current_total_usd >= self.max_total_usd:
            print(f"\n✅ حد آستانه مجموع رسیده شد!")
        else:
            print(f"\n⏳ باقی‌مانده تا حد آستانه: ${self.max_total_usd - self.current_total_usd:.2f}")
        
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

    def run(self, start_date, end_date):
        """اجرای اسکن اصلی"""
        print("\n🚀 شروع اسکن بازه زمانی...")
        
        try:
            # دریافت قیمت ETH
            self.get_eth_price()
            
            # اسکن بازه زمانی
            expensive_contracts = self.scan_date_range(start_date, end_date)
            
            # نمایش خلاصه
            self.print_summary(expensive_contracts)
            
            # ذخیره نتایج - همیشه فایل بساز (حتی اگر لیست خالی باشد)
            filename = self.save_results(expensive_contracts, start_date, end_date)
            
            if expensive_contracts:
                if self.current_total_usd >= self.max_total_usd:
                    print(f"\n🎯 حد آستانه مجموع ${self.max_total_usd} رسیده شد!")
                    print(f"✅ اسکن متوقف شد! {len(expensive_contracts)} قرارداد گران یافت شد.")
                    print(f"💰 مجموع نهایی: ${self.current_total_usd:.2f}")
                else:
                    print(f"\n✅ اسکن تکمیل شد! {len(expensive_contracts)} قرارداد گران یافت شد.")
                    print(f"💰 مجموع: ${self.current_total_usd:.2f}")
            else:
                print(f"\n😔 هیچ قراردادی با هزینه بالای ${self.min_fee_usd} در این بازه زمانی یافت نشد")
                if self.current_total_usd > 0:
                    print(f"💰 مجموع هزینه‌های قراردادهای بالای ${self.min_fee_usd}: ${self.current_total_usd:.2f}")
                else:
                    print(f"💰 هیچ قراردادی برای محاسبه مجموع یافت نشد")
            
            if filename:
                print(f"📁 فایل ذخیره شده: {filename}")
            else:
                print(f"❌ خطا در ذخیره فایل")
            
        except KeyboardInterrupt:
            print("\n⏹️ اسکن توسط کاربر متوقف شد")
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")

def main():
    print("="*70)
    print("🔍 Ethereum Date Range Scanner - Find $15+ Transaction Fee Contracts")
    print("اسکنر بازه زمانی اتریوم - یافتن قراردادهای بالای 15 دلار هزینه تراکنش")
    print("="*70)
    
    try:
        scanner = EthereumDateRangeScanner()
        
        # دریافت بازه زمانی از کاربر
        print("\n📅 لطفاً بازه زمانی مورد نظر را وارد کنید:")
        start_date = input("🟢 تاریخ شروع (DD-MM-YYYY مثال: 20-08-2025): ").strip()
        end_date = input("🔴 تاریخ پایان (DD-MM-YYYY مثال: 31-08-2025): ").strip()
        
        if not start_date or not end_date:
            print("❌ تاریخ‌ها نمی‌توانند خالی باشند")
            return
        
        # تغییر حد آستانه در صورت نیاز
        threshold = input(f"\n💰 حد آستانه هزینه هر قرارداد (پیش‌فرض: {scanner.min_fee_usd}$): ").strip()
        if threshold:
            try:
                scanner.min_fee_usd = float(threshold)
                print(f"💰 حد آستانه هر قرارداد تغییر یافت به: ${scanner.min_fee_usd}")
            except ValueError:
                print("⚠️ مقدار نامعتبر، از حد آستانه پیش‌فرض استفاده می‌شود")
        
        # تغییر حد آستانه مجموع در صورت نیاز
        total_threshold = input(f"\n🎯 حد آستانه مجموع (پیش‌فرض: {scanner.max_total_usd}$): ").strip()
        if total_threshold:
            try:
                scanner.max_total_usd = float(total_threshold)
                print(f"🎯 حد آستانه مجموع تغییر یافت به: ${scanner.max_total_usd}")
            except ValueError:
                print("⚠️ مقدار نامعتبر، از حد آستانه پیش‌فرض استفاده می‌شود")
        
        print(f"\n📦 شروع اسکن از {start_date} تا {end_date} برای قراردادهای بالای ${scanner.min_fee_usd}...")
        
        scanner.run(start_date, end_date)
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")
    
    print("\n" + "="*70)
    print("✅ پایان عملیات")

if __name__ == "__main__":
    main()
