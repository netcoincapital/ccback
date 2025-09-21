#!/usr/bin/env python3
"""
دریافت اطلاعات 1 سال گذشته همه کریپتوها
Fetch 1-year historical data for all cryptocurrencies
"""

import requests
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database models
try:
    from database import engine
    from database.prices import Price
    from database.Currencies import Currencies
except ImportError as e:
    print(f"❌ خطا در import: {str(e)}")
    print("لطفاً مطمئن شوید که در مسیر صحیح پروژه هستید")
    exit(1)

class HistoricalDataFetcher:
    """کلاس دریافت اطلاعات تاریخی"""
    
    def __init__(self):
        # API Keys - پشتیبانی از چندین کلید CMC از .env
        cmc_keys_str = os.getenv('CMC_API_KEYS', '')
        if not cmc_keys_str:
            # اگر CMC_API_KEYS نبود، CMC_API_KEY را امتحان کن
            cmc_keys_str = os.getenv('CMC_API_KEY', '')
        
        if not cmc_keys_str:
            print("❌ خطا: هیچ کلید CMC در .env پیدا نشد")
            print("لطفاً CMC_API_KEYS یا CMC_API_KEY را در فایل .env تنظیم کنید")
            exit(1)
        
        self.cmc_api_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
        self.current_cmc_key_index = 0
        self.cmc_key_errors = {i: 0 for i in range(len(self.cmc_api_keys))}
        
        # فیلتر کردن کلیدهای نامعتبر (اگر می‌دانیم کدامند)
        self.invalid_keys = set()  # لیست کلیدهای نامعتبر شناسایی شده
        
        self.coingecko_api_key = os.getenv('COINGECKO_API_KEY', '')
        
        # API URLs
        self.cmc_base_url = "https://pro-api.coinmarketcap.com/v1"
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        
        # تنظیمات محافظه‌کارانه برای جلوگیری از Rate Limiting
        self.batch_size = 10  # کاهش batch size برای کاهش فشار روی API
        self.delay_between_batches = 300  # 5 دقیقه انتظار بین batch ها
        self.delay_between_requests = 5  # 5 ثانیه انتظار بین درخواست‌ها
        self.max_retries_per_key = 2  # حداکثر 2 تلاش برای هر کلید
        
        # آمار
        self.stats = {
            'total_currencies': 0,
            'processed_currencies': 0,
            'total_records_inserted': 0,
            'api_calls_made': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        print("🔍 Historical Data Fetcher راه‌اندازی شد")
        print(f"🔑 تعداد CMC API Keys: {len(self.cmc_api_keys)}")
        for i, key in enumerate(self.cmc_api_keys[:5]):  # نمایش 5 تای اول
            print(f"   کلید {i+1}: {key[:8]}...")
        if len(self.cmc_api_keys) > 5:
            print(f"   ... و {len(self.cmc_api_keys) - 5} کلید دیگر")

    def get_current_cmc_key(self):
        """دریافت کلید CMC فعلی"""
        return self.cmc_api_keys[self.current_cmc_key_index]

    def rotate_cmc_key(self, reason="Rate limit"):
        """تغییر به کلید CMC بعدی"""
        if len(self.cmc_api_keys) <= 1:
            return False
        
        old_index = self.current_cmc_key_index
        self.current_cmc_key_index = (self.current_cmc_key_index + 1) % len(self.cmc_api_keys)
        
        print(f"🔄 تغییر CMC key به دلیل {reason}")
        print(f"   از کلید {old_index + 1} ({self.cmc_api_keys[old_index][:8]}...)")
        print(f"   به کلید {self.current_cmc_key_index + 1} ({self.cmc_api_keys[self.current_cmc_key_index][:8]}...)")
        
        # تاخیر پس از تغییر کلید
        time.sleep(5)
        return True

    def handle_cmc_error(self, status_code, response_data=None):
        """مدیریت خطاهای CMC API"""
        self.cmc_key_errors[self.current_cmc_key_index] += 1
        
        if status_code == 429:  # Rate limit
            print(f"🚫 Rate limit برای کلید {self.current_cmc_key_index + 1}")
            # اگر همه کلیدها rate limit شدند، انتظار طولانی‌تر
            if self.all_keys_rate_limited():
                print("⚠️ همه کلیدها rate limit شده‌اند، انتظار 10 دقیقه...")
                time.sleep(600)  # 10 دقیقه انتظار
                self.reset_key_errors()  # ریست کردن خطاها
                return True
            return self.rotate_cmc_key("Rate limit")
        
        elif status_code == 401:  # Unauthorized
            print(f"🔐 کلید {self.current_cmc_key_index + 1} نامعتبر است")
            self.invalid_keys.add(self.current_cmc_key_index)
            return self.rotate_cmc_key("Invalid key")
        
        elif status_code == 403:  # Forbidden
            print(f"🚫 دسترسی مسدود برای کلید {self.current_cmc_key_index + 1}")
            return self.rotate_cmc_key("Forbidden")
        
        elif self.cmc_key_errors[self.current_cmc_key_index] > self.max_retries_per_key:
            print(f"❌ کلید {self.current_cmc_key_index + 1} خطاهای زیادی دارد")
            return self.rotate_cmc_key("Too many errors")
        
        return False

    def all_keys_rate_limited(self):
        """بررسی اینکه آیا همه کلیدها rate limit شده‌اند"""
        for i, errors in self.cmc_key_errors.items():
            if i not in self.invalid_keys and errors < self.max_retries_per_key:
                return False
        return True

    def reset_key_errors(self):
        """ریست کردن خطاهای کلیدها"""
        self.cmc_key_errors = {i: 0 for i in range(len(self.cmc_api_keys))}
        print("🔄 خطاهای کلیدها ریست شد")

    def get_all_currencies(self):
        """دریافت لیست همه کریپتوها از دیتابیس"""
        session = Session(bind=engine)
        
        try:
            currencies = session.query(Currencies).filter(
                Currencies.CMC_ID.isnot(None)  # فقط ارزهایی که CMC_ID دارند
            ).all()
            
            currency_list = []
            for currency in currencies:
                currency_list.append({
                    'currency_id': currency.CurrencyID,
                    'symbol': currency.Symbol,
                    'name': currency.CurrencyName,
                    'cmc_id': currency.CMC_ID
                })
            
            self.stats['total_currencies'] = len(currency_list)
            
            print(f"📊 تعداد کل کریپتوها: {len(currency_list)}")
            
            # نمایش لیست
            print(f"📋 لیست کریپتوها:")
            for currency in currency_list[:10]:  # نمایش 10 تای اول
                print(f"   {currency['symbol']} ({currency['name']}) - CMC_ID: {currency['cmc_id']}")
            
            if len(currency_list) > 10:
                print(f"   ... و {len(currency_list) - 10} ارز دیگر")
            
            return currency_list
            
        except Exception as e:
            print(f"❌ خطا در دریافت لیست ارزها: {str(e)}")
            return []
        finally:
            session.close()

    def fetch_historical_data_cmc(self, cmc_ids, days=365):
        """دریافت اطلاعات تاریخی از CoinMarketCap"""
        
        # محدود کردن به 100 ارز (محدودیت API)
        cmc_ids_str = ','.join(map(str, cmc_ids[:100]))
        
        # محاسبه تاریخ شروع
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"{self.cmc_base_url}/cryptocurrency/quotes/historical"
        
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': self.get_current_cmc_key(),
        }
        
        params = {
            'id': cmc_ids_str,
            'time_start': start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'time_end': end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'interval': 'daily',
            'convert': 'USD'
        }
        
        try:
            print(f"🔄 درخواست تاریخی برای {len(cmc_ids)} ارز...")
            
            response = requests.get(url, headers=headers, params=params, timeout=60)
            self.stats['api_calls_made'] += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status', {}).get('error_code') == 0:
                    return data.get('data', {})
                else:
                    error_msg = data.get('status', {}).get('error_message', 'Unknown error')
                    print(f"❌ خطای API: {error_msg}")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
                # مدیریت خطا و تغییر کلید
                if self.handle_cmc_error(response.status_code, response.json() if response.text else None):
                    # تلاش مجدد با کلید جدید
                    print("🔄 تلاش مجدد با کلید جدید...")
                    time.sleep(2)
                    
                    # تغییر header با کلید جدید
                    headers['X-CMC_PRO_API_KEY'] = self.get_current_cmc_key()
                    
                    # تلاش مجدد
                    retry_response = requests.get(url, headers=headers, params=params, timeout=60)
                    self.stats['api_calls_made'] += 1
                    
                    if retry_response.status_code == 200:
                        retry_data = retry_response.json()
                        if retry_data.get('status', {}).get('error_code') == 0:
                            print("✅ تلاش مجدد موفق")
                            return retry_data.get('data', {})
                    
                    print("❌ تلاش مجدد نیز ناموفق")
                
                return None
                
        except Exception as e:
            print(f"❌ خطا در درخواست CMC: {str(e)}")
            self.stats['errors'] += 1
            return None

    def fetch_historical_data_coingecko(self, symbol, days=365):
        """دریافت اطلاعات تاریخی از CoinGecko (پشتیبان)"""
        
        url = f"{self.coingecko_base_url}/coins/{symbol.lower()}/market_chart"
        
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'daily'
        }
        
        headers = {}
        if self.coingecko_api_key:
            headers['x-cg-pro-api-key'] = self.coingecko_api_key
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            self.stats['api_calls_made'] += 1
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"❌ CoinGecko Error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ خطا در درخواست CoinGecko: {str(e)}")
            return None

    def insert_historical_records(self, currency_data, historical_data):
        """insert رکوردهای تاریخی در دیتابیس"""
        
        session = Session(bind=engine)
        inserted_count = 0
        
        try:
            currency_id = currency_data['currency_id']
            symbol = currency_data['symbol']
            
            print(f"💾 ذخیره رکوردهای {symbol} ({currency_id})...")
            
            # پردازش داده‌های CMC
            if 'quotes' in historical_data:
                quotes = historical_data['quotes']
                
                for quote_data in quotes:
                    try:
                        # استخراج timestamp
                        timestamp_str = quote_data.get('timestamp', '')
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        # استخراج اطلاعات قیمت
                        usd_quote = quote_data.get('quote', {}).get('USD', {})
                        
                        if usd_quote:
                            # بررسی عدم وجود رکورد با همین timestamp
                            existing = session.query(Price).filter_by(
                                crypto_id=currency_id,
                                currency='USD',
                                timestamp=timestamp
                            ).first()
                            
                            if not existing:
                                new_record = Price(
                                    crypto_id=currency_id,
                                    currency='USD',
                                    price=Decimal(str(usd_quote.get('price', 0))),
                                    market_cap=Decimal(str(usd_quote.get('market_cap', 0))) if usd_quote.get('market_cap') else None,
                                    volume_24h=Decimal(str(usd_quote.get('volume_24h', 0))) if usd_quote.get('volume_24h') else None,
                                    change_1h=Decimal(str(usd_quote.get('percent_change_1h', 0))) if usd_quote.get('percent_change_1h') else None,
                                    change_24h=Decimal(str(usd_quote.get('percent_change_24h', 0))) if usd_quote.get('percent_change_24h') else None,
                                    change_7d=Decimal(str(usd_quote.get('percent_change_7d', 0))) if usd_quote.get('percent_change_7d') else None,
                                    timestamp=timestamp,
                                    is_historical=True,
                                    last_updated=datetime.now()
                                )
                                
                                session.add(new_record)
                                inserted_count += 1
                            
                    except Exception as e:
                        print(f"   ❌ خطا در پردازش رکورد: {str(e)}")
                        continue
                
                # Commit تمام رکوردهای یک ارز
                session.commit()
                print(f"   ✅ {inserted_count} رکورد ذخیره شد")
                
            # پردازش داده‌های CoinGecko
            elif 'prices' in historical_data:
                prices = historical_data['prices']
                market_caps = historical_data.get('market_caps', [])
                volumes = historical_data.get('total_volumes', [])
                
                for i, price_data in enumerate(prices):
                    try:
                        timestamp = datetime.fromtimestamp(price_data[0] / 1000)  # تبدیل از milliseconds
                        price = price_data[1]
                        
                        market_cap = market_caps[i][1] if i < len(market_caps) else None
                        volume = volumes[i][1] if i < len(volumes) else None
                        
                        # بررسی عدم وجود رکورد
                        existing = session.query(Price).filter_by(
                            crypto_id=currency_id,
                            currency='USD',
                            timestamp=timestamp
                        ).first()
                        
                        if not existing:
                            new_record = Price(
                                crypto_id=currency_id,
                                currency='USD',
                                price=Decimal(str(price)),
                                market_cap=Decimal(str(market_cap)) if market_cap else None,
                                volume_24h=Decimal(str(volume)) if volume else None,
                                timestamp=timestamp,
                                is_historical=True,
                                last_updated=datetime.now()
                            )
                            
                            session.add(new_record)
                            inserted_count += 1
                        
                    except Exception as e:
                        print(f"   ❌ خطا در پردازش رکورد CoinGecko: {str(e)}")
                        continue
                
                session.commit()
                print(f"   ✅ {inserted_count} رکورد CoinGecko ذخیره شد")
            
            self.stats['total_records_inserted'] += inserted_count
            return inserted_count
            
        except Exception as e:
            print(f"❌ خطا در insert رکوردها: {str(e)}")
            session.rollback()
            self.stats['errors'] += 1
            return 0
        finally:
            session.close()

    def process_currencies_batch(self, currencies_batch):
        """پردازش یک batch از ارزها"""
        
        print(f"\n📦 پردازش batch {len(currencies_batch)} ارز...")
        
        # دریافت CMC_IDs
        cmc_ids = [c['cmc_id'] for c in currencies_batch if c['cmc_id']]
        
        if not cmc_ids:
            print("⚠️ هیچ CMC_ID معتبری یافت نشد")
            return
        
        # تلاش با CMC API
        historical_data = self.fetch_historical_data_cmc(cmc_ids)
        
        if historical_data:
            # پردازش داده‌های CMC
            for currency in currencies_batch:
                if currency['cmc_id'] and str(currency['cmc_id']) in historical_data:
                    currency_historical = historical_data[str(currency['cmc_id'])]
                    inserted = self.insert_historical_records(currency, currency_historical)
                    
                    if inserted > 0:
                        self.stats['processed_currencies'] += 1
                        print(f"   ✅ {currency['symbol']}: {inserted} رکورد")
                    else:
                        print(f"   ⚠️ {currency['symbol']}: هیچ رکورد جدیدی")
        else:
            # CMC API موفق نبود - این batch را رد کن
            print("❌ CMC API موفق نبود، این batch رد شد")
            print("⚠️ لطفاً کمی صبر کنید تا Rate Limit برطرف شود")

    def run_historical_fetch(self):
        """اجرای دریافت اطلاعات تاریخی"""
        
        print("🚀 شروع دریافت اطلاعات 1 سال گذشته...")
        
        try:
            # دریافت لیست ارزها
            currencies = self.get_all_currencies()
            
            if not currencies:
                print("❌ هیچ ارزی یافت نشد")
                return
            
            # تقسیم به batch ها
            batches = [currencies[i:i + self.batch_size] for i in range(0, len(currencies), self.batch_size)]
            
            print(f"📦 تقسیم به {len(batches)} batch")
            
            # پردازش هر batch
            for batch_num, batch in enumerate(batches, 1):
                print(f"\n{'='*50}")
                print(f"📦 Batch {batch_num}/{len(batches)}")
                print(f"{'='*50}")
                
                # نمایش ارزهای این batch
                symbols = [c['symbol'] for c in batch]
                print(f"🪙 ارزهای این batch: {', '.join(symbols)}")
                
                # پردازش batch
                self.process_currencies_batch(batch)
                
                # نمایش پیشرفت
                progress = (batch_num / len(batches)) * 100
                print(f"📊 پیشرفت کلی: {progress:.1f}%")
                
                # وقفه بین batch ها (جز آخری)
                if batch_num < len(batches):
                    print(f"⏳ انتظار {self.delay_between_batches} ثانیه...")
                    time.sleep(self.delay_between_batches)
            
            # نمایش آمار نهایی
            self.print_final_stats()
            
        except KeyboardInterrupt:
            print("\n⏹️ عملیات توسط کاربر متوقف شد")
            self.print_final_stats()
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")

    def print_final_stats(self):
        """نمایش آمار نهایی"""
        
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']
        
        print(f"\n" + "="*60)
        print("📊 آمار نهایی")
        print("="*60)
        
        print(f"🕐 زمان شروع: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 زمان پایان: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ مدت زمان کل: {duration}")
        
        print(f"\n📊 آمار پردازش:")
        print(f"   🔢 کل ارزها: {self.stats['total_currencies']}")
        print(f"   ✅ پردازش شده: {self.stats['processed_currencies']}")
        print(f"   ❌ ناموفق: {self.stats['total_currencies'] - self.stats['processed_currencies']}")
        
        print(f"\n💾 آمار دیتابیس:")
        print(f"   📈 رکوردهای جدید: {self.stats['total_records_inserted']:,}")
        print(f"   🌐 API calls: {self.stats['api_calls_made']}")
        print(f"   ❌ خطاها: {self.stats['errors']}")
        
        print(f"\n🔑 آمار کلیدهای CMC:")
        for i, key in enumerate(self.cmc_api_keys):
            error_count = self.cmc_key_errors.get(i, 0)
            status = "🟢 فعال" if i == self.current_cmc_key_index else "⚪ غیرفعال"
            print(f"   کلید {i+1} ({key[:8]}...): {error_count} خطا {status}")
        
        print(f"   📊 کلید فعلی: {self.current_cmc_key_index + 1}/{len(self.cmc_api_keys)}")
        
        if self.stats['processed_currencies'] > 0:
            avg_records = self.stats['total_records_inserted'] / self.stats['processed_currencies']
            print(f"   📊 میانگین رکورد/ارز: {avg_records:.1f}")
        
        # بررسی امکان ساخت چارت
        print(f"\n📈 امکان ساخت چارت:")
        if self.stats['total_records_inserted'] >= 365:
            print("   ✅ چارت سالانه: بله")
        if self.stats['total_records_inserted'] >= 30:
            print("   ✅ چارت ماهانه: بله")
        if self.stats['total_records_inserted'] >= 7:
            print("   ✅ چارت هفتگی: بله")
        if self.stats['total_records_inserted'] >= 1:
            print("   ✅ چارت روزانه: بله")

def create_quick_test():
    """ایجاد تست سریع برای چند ارز"""
    
    print(f"\n" + "="*60)
    print("🧪 ایجاد تست سریع")
    print("="*60)
    
    test_code = '''#!/usr/bin/env python3
"""
تست سریع برای چند ارز مهم
Quick test for major cryptocurrencies
"""

from historical_data_fetcher_1year import HistoricalDataFetcher

def quick_test():
    fetcher = HistoricalDataFetcher()
    
    # فقط ارزهای مهم برای تست
    test_currencies = [
        {'currency_id': '1', 'symbol': 'BTC', 'name': 'Bitcoin', 'cmc_id': 1},
        {'currency_id': '16', 'symbol': 'ETH', 'name': 'Ethereum', 'cmc_id': 1027},
        {'currency_id': '3', 'symbol': 'BNB', 'name': 'BNB', 'cmc_id': 1839}
    ]
    
    print(f"🧪 تست سریع با {len(test_currencies)} ارز...")
    
    fetcher.stats['total_currencies'] = len(test_currencies)
    fetcher.process_currencies_batch(test_currencies)
    fetcher.print_final_stats()

if __name__ == "__main__":
    quick_test()
'''
    
    with open('quick_historical_test.py', 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print(f"💾 تست سریع در فایل quick_historical_test.py ذخیره شد")

def main():
    print("🔍 Historical Data Fetcher - 1 Year")
    print("دریافت‌کننده اطلاعات تاریخی - 1 سال")
    print("="*60)
    
    # ایجاد fetcher
    fetcher = HistoricalDataFetcher()
    
    # انتخاب نوع اجرا
    print(f"\n📋 گزینه‌های اجرا:")
    print("1. اجرای کامل (همه ارزها - زمان‌بر)")
    print("2. تست سریع (3 ارز مهم)")
    print("3. فقط ایجاد فایل‌های تست")
    
    choice = input("\nانتخاب کنید (1/2/3): ").strip()
    
    if choice == '1':
        print(f"\n⚠️ هشدار: این عملیات ممکن است چند ساعت طول بکشد")
        confirm = input("ادامه می‌دهید؟ (y/n): ").strip().lower()
        
        if confirm == 'y':
            fetcher.run_historical_fetch()
        else:
            print("❌ عملیات لغو شد")
            
    elif choice == '2':
        print(f"\n🧪 اجرای تست سریع...")
        # ایجاد تست سریع
        create_quick_test()
        print(f"برای اجرا: python quick_historical_test.py")
        
    elif choice == '3':
        print(f"\n📁 ایجاد فایل‌های تست...")
        create_quick_test()
        print(f"✅ فایل‌های تست آماده شد")
        
    else:
        print("❌ انتخاب نامعتبر")

if __name__ == "__main__":
    main()
