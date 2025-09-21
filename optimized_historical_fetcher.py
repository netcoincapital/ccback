#!/usr/bin/env python3
"""
نسخه بهینه شده دریافت‌کننده اطلاعات تاریخی
Optimized Historical Data Fetcher
"""

import requests
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from database import engine
    from database.prices import Price
    from database.Currencies import Currencies
except ImportError as e:
    print(f"❌ خطا در import: {str(e)}")
    exit(1)

class OptimizedHistoricalFetcher:
    """نسخه بهینه شده برای دریافت اطلاعات تاریخی"""
    
    def __init__(self):
        # CMC API Keys
        cmc_keys_str = os.getenv('CMC_API_KEYS', '')
        self.cmc_api_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
        self.current_cmc_key_index = 0
        
        # تنظیمات محافظه‌کارانه
        self.batch_size = 3  # کاهش به 3 ارز در هر batch
        self.delay_between_batches = 120  # 2 دقیقه تاخیر
        self.delay_between_currencies = 10  # 10 ثانیه بین ارزها
        
        # آمار
        self.stats = {
            'total_currencies': 0,
            'processed_currencies': 0,
            'total_records_inserted': 0,
            'api_calls_made': 0,
            'errors': 0,
            'start_time': datetime.now(),
            'key_rotations': 0
        }
        
        print(f"🔍 Optimized Historical Fetcher")
        print(f"🔑 کلیدهای CMC: {len(self.cmc_api_keys)}")

    def get_current_cmc_key(self):
        return self.cmc_api_keys[self.current_cmc_key_index]

    def rotate_cmc_key(self):
        if len(self.cmc_api_keys) <= 1:
            return False
        
        old_index = self.current_cmc_key_index
        self.current_cmc_key_index = (self.current_cmc_key_index + 1) % len(self.cmc_api_keys)
        self.stats['key_rotations'] += 1
        
        print(f"🔄 تغییر به کلید {self.current_cmc_key_index + 1}")
        time.sleep(10)
        return True

    def fetch_single_currency_data(self, cmc_id, days=30):
        """دریافت اطلاعات یک ارز (کاهش به 30 روز)"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/historical"
        
        for attempt in range(3):  # 3 تلاش
            try:
                headers = {
                    'Accepts': 'application/json',
                    'X-CMC_PRO_API_KEY': self.get_current_cmc_key(),
                }
                
                params = {
                    'id': str(cmc_id),
                    'time_start': start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'time_end': end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'interval': 'daily',
                    'convert': 'USD'
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                self.stats['api_calls_made'] += 1
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status', {}).get('error_code') == 0:
                        return data.get('data', {}).get(str(cmc_id), {})
                    else:
                        error_msg = data.get('status', {}).get('error_message', 'Unknown')
                        print(f"   ❌ API Error: {error_msg}")
                        
                elif response.status_code == 429:
                    print(f"   🚫 Rate limit - تغییر کلید...")
                    if not self.rotate_cmc_key():
                        print(f"   ❌ تمام کلیدها محدود شده")
                        time.sleep(300)  # 5 دقیقه انتظار
                        
                elif response.status_code in [401, 403]:
                    print(f"   🔐 مشکل احراز هویت - تغییر کلید...")
                    if not self.rotate_cmc_key():
                        break
                        
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                
                time.sleep(5)  # تاخیر بین تلاش‌ها
                
            except Exception as e:
                print(f"   ❌ خطا در تلاش {attempt + 1}: {str(e)}")
                time.sleep(2)
        
        self.stats['errors'] += 1
        return None

    def insert_currency_data(self, currency_info, historical_data):
        """insert اطلاعات یک ارز"""
        
        if not historical_data or 'quotes' not in historical_data:
            return 0
        
        session = Session(bind=engine)
        inserted_count = 0
        
        try:
            currency_id = currency_info['currency_id']
            symbol = currency_info['symbol']
            
            quotes = historical_data['quotes']
            
            for quote_data in quotes:
                try:
                    # استخراج timestamp
                    timestamp_str = quote_data.get('timestamp', '')
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    
                    # استخراج اطلاعات USD
                    usd_quote = quote_data.get('quote', {}).get('USD', {})
                    
                    if usd_quote and usd_quote.get('price'):
                        # بررسی عدم وجود رکورد مشابه
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
                    print(f"   ❌ خطا در رکورد: {str(e)}")
                    continue
            
            session.commit()
            self.stats['total_records_inserted'] += inserted_count
            
            return inserted_count
            
        except Exception as e:
            print(f"❌ خطا در insert: {str(e)}")
            session.rollback()
            return 0
        finally:
            session.close()

    def process_important_currencies(self):
        """پردازش ارزهای مهم ابتدا"""
        
        # ارزهای مهم با CMC_ID معتبر
        important_currencies = [
            {'currency_id': '1', 'symbol': 'BTC', 'name': 'Bitcoin', 'cmc_id': 1},
            {'currency_id': '16', 'symbol': 'ETH', 'name': 'Ethereum', 'cmc_id': 1027},
            {'currency_id': '3', 'symbol': 'BNB', 'name': 'BNB', 'cmc_id': 1839},
            {'currency_id': '10', 'symbol': 'ADA', 'name': 'Cardano', 'cmc_id': 2010},
            {'currency_id': '11', 'symbol': 'SOL', 'name': 'Solana', 'cmc_id': 5426},
            {'currency_id': '12', 'symbol': 'XRP', 'name': 'XRP', 'cmc_id': 52},
            {'currency_id': '14', 'symbol': 'MATIC', 'name': 'Polygon', 'cmc_id': 3890},
            {'currency_id': '18', 'symbol': 'XLM', 'name': 'Stellar', 'cmc_id': 512},
            {'currency_id': '19', 'symbol': 'LINK', 'name': 'Chainlink', 'cmc_id': 1975},
            {'currency_id': '20', 'symbol': 'DOT', 'name': 'Polkadot', 'cmc_id': 6636}
        ]
        
        print(f"🎯 پردازش {len(important_currencies)} ارز مهم...")
        
        for i, currency in enumerate(important_currencies, 1):
            print(f"\n📦 {i}/{len(important_currencies)}: {currency['symbol']} ({currency['name']})")
            
            # دریافت اطلاعات
            historical_data = self.fetch_single_currency_data(currency['cmc_id'], days=30)  # 30 روز برای تست
            
            if historical_data:
                # ذخیره اطلاعات
                inserted = self.insert_currency_data(currency, historical_data)
                
                if inserted > 0:
                    self.stats['processed_currencies'] += 1
                    print(f"   ✅ {inserted} رکورد ذخیره شد")
                else:
                    print(f"   ⚠️ هیچ رکورد جدیدی")
            else:
                print(f"   ❌ دریافت اطلاعات ناموفق")
            
            # تاخیر بین ارزها
            if i < len(important_currencies):
                print(f"   ⏳ انتظار {self.delay_between_currencies} ثانیه...")
                time.sleep(self.delay_between_currencies)

    def print_final_stats(self):
        """نمایش آمار نهایی"""
        
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']
        
        print(f"\n" + "="*60)
        print("📊 آمار نهایی")
        print("="*60)
        
        print(f"🕐 مدت زمان: {duration}")
        print(f"📊 ارزهای پردازش شده: {self.stats['processed_currencies']}")
        print(f"📈 رکوردهای جدید: {self.stats['total_records_inserted']:,}")
        print(f"🌐 API calls: {self.stats['api_calls_made']}")
        print(f"🔄 تغییر کلیدها: {self.stats['key_rotations']}")
        print(f"❌ خطاها: {self.stats['errors']}")
        
        if self.stats['processed_currencies'] > 0:
            avg_records = self.stats['total_records_inserted'] / self.stats['processed_currencies']
            print(f"📊 میانگین رکورد/ارز: {avg_records:.1f}")

    def run(self):
        """اجرای بهینه شده"""
        
        print("🚀 شروع دریافت اطلاعات بهینه شده...")
        
        try:
            self.process_important_currencies()
            self.print_final_stats()
            
            if self.stats['total_records_inserted'] > 0:
                print(f"\n🎉 موفق! {self.stats['total_records_inserted']} رکورد ذخیره شد")
                print(f"📈 حالا می‌توانید چارت بسازید")
            else:
                print(f"\n😔 هیچ رکوردی ذخیره نشد")
                
        except KeyboardInterrupt:
            print(f"\n⏹️ متوقف شد توسط کاربر")
            self.print_final_stats()
        except Exception as e:
            print(f"❌ خطا: {str(e)}")

def main():
    print("🚀 Historical Data Fetcher - Optimized")
    print("="*50)
    
    fetcher = OptimizedHistoricalFetcher()
    
    if len(fetcher.cmc_api_keys) < 5:
        print("⚠️ تعداد کلیدهای CMC کم است")
        print("💡 برای عملکرد بهتر حداقل 5 کلید نیاز است")
    
    confirm = input(f"\nآیا می‌خواهید شروع کنید؟ (y/n): ").strip().lower()
    
    if confirm == 'y':
        fetcher.run()
    else:
        print("❌ لغو شد")

if __name__ == "__main__":
    main()
