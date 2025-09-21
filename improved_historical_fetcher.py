#!/usr/bin/env python3
"""
دریافت‌کننده بهبود یافته داده‌های تاریخی با مدیریت بهتر خطا و batch processing
Improved historical data fetcher with better error handling and batch processing
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

class ImprovedHistoricalFetcher:
    """کلاس بهبود یافته برای دریافت داده‌های تاریخی"""
    
    def __init__(self):
        self.historical_service = HistoricalDataService()
        self.stats = {
            'total_currencies': 0,
            'processed_currencies': 0,
            'total_records_added': 0,
            'total_api_calls': 0,
            'failed_currencies': 0,
            'start_time': datetime.now()
        }
        
        logger.info("🚀 Improved Historical Fetcher initialized")

    def get_all_currencies_with_cmc_id(self):
        """دریافت تمام ارزهایی که CMC_ID دارند"""
        session = Session(bind=engine)
        
        try:
            currencies = session.query(Currencies).filter(
                Currencies.CMC_ID.isnot(None)
            ).order_by(Currencies.CurrencyID.asc()).all()
            
            currency_ids = [c.CurrencyID for c in currencies]
            
            logger.info(f"📊 Found {len(currency_ids)} currencies with valid CMC_ID")
            
            # نمایش نمونه ارزها
            sample_currencies = currencies[:10]
            logger.info("📋 Sample currencies:")
            for currency in sample_currencies:
                logger.info(f"   {currency.Symbol} ({currency.CurrencyName}) - ID: {currency.CurrencyID}, CMC_ID: {currency.CMC_ID}")
            
            if len(currencies) > 10:
                logger.info(f"   ... and {len(currencies) - 10} more currencies")
            
            self.stats['total_currencies'] = len(currency_ids)
            return currency_ids
            
        except Exception as e:
            logger.error(f"❌ Error fetching currencies: {str(e)}")
            return []
        finally:
            session.close()

    def fetch_historical_data(self, currency_ids=None, days=365, batch_size=25, fiat_currencies=None):
        """
        دریافت داده‌های تاریخی با batch processing بهبود یافته
        
        Args:
            currency_ids (list): لیست currency IDs (اگر None باشد، همه ارزها)
            days (int): تعداد روزهای گذشته
            batch_size (int): اندازه هر batch
            fiat_currencies (list): لیست ارزهای فیات
        """
        try:
            if currency_ids is None:
                currency_ids = self.get_all_currencies_with_cmc_id()
            
            if not currency_ids:
                logger.error("❌ No currencies found to process")
                return
            
            if fiat_currencies is None:
                fiat_currencies = ["USD"]
            
            # محاسبه تاریخ شروع و پایان
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            time_start = start_date.isoformat() + "Z"
            time_end = end_date.isoformat() + "Z"
            
            logger.info(f"🔍 Fetching {days} days of historical data")
            logger.info(f"📅 Time range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            logger.info(f"💰 Fiat currencies: {fiat_currencies}")
            logger.info(f"📦 Batch size: {batch_size}")
            
            # شروع پردازش
            result = self.historical_service.store_historical_data(
                currency_ids=currency_ids,
                time_start=time_start,
                time_end=time_end,
                interval="daily",
                fiat_currencies=fiat_currencies,
                batch_size=batch_size
            )
            
            # به‌روزرسانی آمار
            if result.get("success"):
                self.stats['total_records_added'] = result.get("records_added", 0)
                self.stats['total_api_calls'] = result.get("api_calls_made", 0)
                self.stats['failed_currencies'] = result.get("records_failed", 0)
                self.stats['processed_currencies'] = len(currency_ids) - self.stats['failed_currencies']
                
                logger.info("✅ Historical data fetch completed successfully")
            else:
                logger.error(f"❌ Historical data fetch failed: {result.get('message')}")
            
            self.print_final_stats()
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in fetch_historical_data: {str(e)}", exc_info=True)
            self.print_final_stats()

    def fetch_recent_data(self, currency_ids=None, days=30, batch_size=50):
        """دریافت داده‌های اخیر (30 روز گذشته)"""
        logger.info(f"🔄 Fetching recent {days} days data...")
        return self.fetch_historical_data(
            currency_ids=currency_ids,
            days=days,
            batch_size=batch_size,
            fiat_currencies=["USD"]
        )

    def fetch_sample_data(self, sample_size=20, days=90):
        """دریافت داده‌های نمونه برای تست"""
        logger.info(f"🧪 Fetching sample data for {sample_size} currencies...")
        
        all_currencies = self.get_all_currencies_with_cmc_id()
        if not all_currencies:
            return
        
        # انتخاب نمونه تصادفی
        import random
        sample_currencies = random.sample(all_currencies, min(sample_size, len(all_currencies)))
        
        logger.info(f"📋 Selected {len(sample_currencies)} currencies for sample: {sample_currencies}")
        
        return self.fetch_historical_data(
            currency_ids=sample_currencies,
            days=days,
            batch_size=10,
            fiat_currencies=["USD"]
        )

    def print_final_stats(self):
        """نمایش آمار نهایی"""
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']
        
        print(f"\n" + "="*70)
        print("📊 آمار نهایی - Improved Historical Fetcher")
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
        
        if self.stats['processed_currencies'] > 0:
            avg_records = self.stats['total_records_added'] / self.stats['processed_currencies']
            print(f"   📊 میانگین رکورد/ارز: {avg_records:.1f}")
        
        print(f"\n📈 امکان ساخت چارت:")
        if self.stats['total_records_added'] >= 365:
            print("   ✅ چارت سالانه: بله")
        if self.stats['total_records_added'] >= 30:
            print("   ✅ چارت ماهانه: بله")
        if self.stats['total_records_added'] >= 7:
            print("   ✅ چارت هفتگی: بله")
        if self.stats['total_records_added'] >= 1:
            print("   ✅ چارت روزانه: بله")

def main():
    """تابع اصلی"""
    print("🔍 Improved Historical Data Fetcher")
    print("دریافت‌کننده بهبود یافته داده‌های تاریخی")
    print("="*70)
    
    fetcher = ImprovedHistoricalFetcher()
    
    print(f"\n📋 گزینه‌های موجود:")
    print("1. دریافت داده‌های کامل (1 سال - همه ارزها)")
    print("2. دریافت داده‌های اخیر (30 روز - همه ارزها)")
    print("3. تست نمونه (90 روز - 20 ارز)")
    print("4. سفارشی")
    
    try:
        choice = input("\nانتخاب کنید (1/2/3/4): ").strip()
        
        if choice == '1':
            print(f"\n⚠️ هشدار: این عملیات ممکن است چند ساعت طول بکشد")
            confirm = input("ادامه می‌دهید؟ (y/n): ").strip().lower()
            
            if confirm == 'y':
                fetcher.fetch_historical_data(days=365, batch_size=25)
            else:
                print("❌ عملیات لغو شد")
                
        elif choice == '2':
            print(f"\n🔄 دریافت داده‌های 30 روز اخیر...")
            fetcher.fetch_recent_data()
            
        elif choice == '3':
            print(f"\n🧪 اجرای تست نمونه...")
            fetcher.fetch_sample_data()
            
        elif choice == '4':
            try:
                days = int(input("تعداد روزها (پیش‌فرض: 90): ") or "90")
                batch_size = int(input("اندازه batch (پیش‌فرض: 25): ") or "25")
                
                print(f"\n🔄 دریافت داده‌های {days} روز با batch size {batch_size}...")
                fetcher.fetch_historical_data(days=days, batch_size=batch_size)
                
            except ValueError:
                print("❌ مقادیر نامعتبر وارد شد")
        else:
            print("❌ انتخاب نامعتبر")
            
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد")
        fetcher.print_final_stats()
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")
        fetcher.print_final_stats()

if __name__ == "__main__":
    main()


