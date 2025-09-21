#!/usr/bin/env python3
"""
دریافت‌کننده صبور داده‌های تاریخی - با مدیریت Rate Limiting
Patient Historical Data Fetcher - with Rate Limiting Management
"""

import os
import sys
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine
from database.Currencies import Currencies
from Currencies.historical_data_service import HistoricalDataService
from utils.logging_config import get_logger

logger = get_logger(__file__)

class PatientHistoricalFetcher:
    """کلاس صبور برای دریافت داده‌های تاریخی با مدیریت Rate Limiting"""
    
    def __init__(self):
        self.historical_service = HistoricalDataService()
        self.stats = {
            'total_currencies': 0,
            'processed_currencies': 0,
            'total_records_added': 0,
            'total_api_calls': 0,
            'failed_currencies': 0,
            'rate_limit_waits': 0,
            'start_time': datetime.now()
        }
        
        logger.info("🐌 Patient Historical Fetcher initialized")

    def check_rate_limits_first(self):
        """بررسی وضعیت Rate Limiting قبل از شروع"""
        print("🔍 بررسی وضعیت Rate Limiting...")
        
        # تست سریع با یک درخواست کوچک
        import requests
        
        cmc_keys_str = os.getenv('CMC_API_KEYS', '')
        if not cmc_keys_str:
            print("❌ کلیدهای CMC پیدا نشد")
            return False
        
        cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
        available_keys = []
        
        for i, api_key in enumerate(cmc_keys, 1):
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
            headers = {
                'X-CMC_PRO_API_KEY': api_key,
                'Accept': 'application/json'
            }
            params = {'start': '1', 'limit': '1', 'convert': 'USD'}
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    print(f"   ✅ کلید {i}: آماده")
                    available_keys.append(api_key)
                elif response.status_code == 429:
                    print(f"   ⚠️ کلید {i}: Rate Limited")
                elif response.status_code == 401:
                    print(f"   ❌ کلید {i}: نامعتبر")
                else:
                    print(f"   ❓ کلید {i}: خطای {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ کلید {i}: خطای اتصال")
        
        print(f"📊 نتیجه: {len(available_keys)} از {len(cmc_keys)} کلید آماده")
        
        if len(available_keys) == 0:
            print("⚠️ هیچ کلیدی آماده نیست - همه Rate Limited هستند")
            return False
        elif len(available_keys) < len(cmc_keys) / 2:
            print("⚠️ کمتر از نیمی از کلیدها آماده هستند")
            return False
        else:
            print("✅ کلیدهای کافی آماده هستند")
            return True

    def wait_for_rate_limits(self, wait_minutes=30):
        """انتظار برای برطرف شدن Rate Limiting"""
        print(f"⏳ انتظار {wait_minutes} دقیقه برای برطرف شدن Rate Limits...")
        
        for minute in range(wait_minutes):
            remaining = wait_minutes - minute
            print(f"   ⏰ {remaining} دقیقه باقی مانده...", end='\r')
            time.sleep(60)  # 1 دقیقه انتظار
        
        print("\n✅ انتظار تمام شد!")
        self.stats['rate_limit_waits'] += 1

    def get_all_currencies_with_cmc_id(self):
        """دریافت تمام ارزهایی که CMC_ID دارند"""
        session = Session(bind=engine)
        
        try:
            currencies = session.query(Currencies).filter(
                Currencies.CMC_ID.isnot(None)
            ).order_by(Currencies.CurrencyID.asc()).all()
            
            currency_ids = [c.CurrencyID for c in currencies]
            
            logger.info(f"📊 Found {len(currency_ids)} currencies with valid CMC_ID")
            self.stats['total_currencies'] = len(currency_ids)
            return currency_ids
            
        except Exception as e:
            logger.error(f"❌ Error fetching currencies: {str(e)}")
            return []
        finally:
            session.close()

    def fetch_with_patience(self, days=365, batch_size=5, max_wait_cycles=5):
        """
        دریافت داده‌های تاریخی با صبر و حوصله
        
        Args:
            days (int): تعداد روزهای گذشته
            batch_size (int): اندازه کوچک batch برای کاهش فشار
            max_wait_cycles (int): حداکثر تعداد دفعات انتظار
        """
        try:
            print("🐌 شروع دریافت صبورانه داده‌های تاریخی...")
            
            # بررسی اولیه Rate Limits
            if not self.check_rate_limits_first():
                print("⚠️ کلیدها Rate Limited هستند، انتظار 30 دقیقه...")
                self.wait_for_rate_limits(30)
            
            currency_ids = self.get_all_currencies_with_cmc_id()
            if not currency_ids:
                print("❌ هیچ ارزی پیدا نشد")
                return
            
            # محاسبه تاریخ
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            time_start = start_date.isoformat() + "Z"
            time_end = end_date.isoformat() + "Z"
            
            print(f"📅 بازه زمانی: {days} روز گذشته")
            print(f"📦 اندازه batch: {batch_size}")
            print(f"⏳ حداکثر انتظار: {max_wait_cycles} بار")
            
            wait_cycle = 0
            
            while wait_cycle < max_wait_cycles:
                print(f"\n🔄 تلاش {wait_cycle + 1} از {max_wait_cycles}")
                
                try:
                    result = self.historical_service.store_historical_data(
                        currency_ids=currency_ids,
                        time_start=time_start,
                        time_end=time_end,
                        interval="daily",
                        fiat_currencies=["USD"],
                        batch_size=batch_size
                    )
                    
                    if result.get("success"):
                        # موفقیت!
                        self.stats['total_records_added'] = result.get("records_added", 0)
                        self.stats['total_api_calls'] = result.get("api_calls_made", 0)
                        self.stats['failed_currencies'] = result.get("records_failed", 0)
                        self.stats['processed_currencies'] = len(currency_ids) - self.stats['failed_currencies']
                        
                        print("✅ دریافت داده‌های تاریخی با موفقیت تکمیل شد!")
                        break
                    else:
                        error_msg = result.get('message', 'Unknown error')
                        print(f"❌ خطا در دریافت: {error_msg}")
                        
                        # اگر خطای Rate Limit باشد، انتظار کن
                        if "rate limit" in error_msg.lower() or "429" in error_msg:
                            wait_cycle += 1
                            if wait_cycle < max_wait_cycles:
                                wait_time = min(30 + (wait_cycle * 15), 60)  # تا 60 دقیقه
                                print(f"⏳ انتظار {wait_time} دقیقه برای برطرف شدن Rate Limit...")
                                self.wait_for_rate_limits(wait_time)
                        else:
                            break
                            
                except Exception as e:
                    print(f"❌ خطای غیرمنتظره: {str(e)}")
                    wait_cycle += 1
                    if wait_cycle < max_wait_cycles:
                        print(f"⏳ انتظار 15 دقیقه قبل از تلاش مجدد...")
                        self.wait_for_rate_limits(15)
            
            if wait_cycle >= max_wait_cycles:
                print("❌ حداکثر تعداد تلاش به پایان رسید")
            
            self.print_final_stats()
            
        except KeyboardInterrupt:
            print("\n⏹️ عملیات توسط کاربر متوقف شد")
            self.print_final_stats()
        except Exception as e:
            print(f"❌ خطای غیرمنتظره: {str(e)}")
            self.print_final_stats()

    def print_final_stats(self):
        """نمایش آمار نهایی"""
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']
        
        print(f"\n" + "="*70)
        print("📊 آمار نهایی - Patient Historical Fetcher")
        print("="*70)
        
        print(f"🕐 زمان شروع: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 زمان پایان: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ مدت زمان کل: {duration}")
        
        print(f"\n📊 آمار پردازش:")
        print(f"   🔢 کل ارزها: {self.stats['total_currencies']}")
        print(f"   ✅ پردازش شده: {self.stats['processed_currencies']}")
        print(f"   ❌ ناموفق: {self.stats['failed_currencies']}")
        
        if self.stats['total_currencies'] > 0:
            success_rate = (self.stats['processed_currencies'] / self.stats['total_currencies']) * 100
            print(f"   📈 نرخ موفقیت: {success_rate:.1f}%")
        
        print(f"\n💾 آمار دیتابیس:")
        print(f"   📈 رکوردهای جدید: {self.stats['total_records_added']:,}")
        print(f"   🌐 تعداد API calls: {self.stats['total_api_calls']}")
        print(f"   ⏳ تعداد انتظارها: {self.stats['rate_limit_waits']}")

def main():
    """تابع اصلی"""
    print("🐌 Patient Historical Data Fetcher")
    print("دریافت‌کننده صبور داده‌های تاریخی")
    print("="*70)
    
    fetcher = PatientHistoricalFetcher()
    
    print(f"\n📋 این ابزار با صبر و حوصله کار می‌کند:")
    print("- در صورت Rate Limiting، خودکار انتظار می‌کند")
    print("- Batch size کوچک برای کاهش فشار روی API")
    print("- تا 5 بار تلاش مجدد با انتظار بین هر تلاش")
    print()
    
    print("📋 گزینه‌های موجود:")
    print("1. دریافت کامل (365 روز، همه ارزها)")
    print("2. دریافت اخیر (90 روز، همه ارزها)")
    print("3. تست کوچک (30 روز، همه ارزها)")
    
    try:
        choice = input("\nانتخاب کنید (1/2/3): ").strip()
        
        if choice == '1':
            print(f"\n⚠️ هشدار: این عملیات ممکن است چندین ساعت طول بکشد")
            confirm = input("ادامه می‌دهید؟ (y/n): ").strip().lower()
            
            if confirm == 'y':
                fetcher.fetch_with_patience(days=365, batch_size=5)
            else:
                print("❌ عملیات لغو شد")
                
        elif choice == '2':
            print(f"\n🔄 دریافت داده‌های 90 روز اخیر...")
            fetcher.fetch_with_patience(days=90, batch_size=8)
            
        elif choice == '3':
            print(f"\n🧪 تست کوچک 30 روز...")
            fetcher.fetch_with_patience(days=30, batch_size=10)
            
        else:
            print("❌ انتخاب نامعتبر")
            
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")

if __name__ == "__main__":
    main()
