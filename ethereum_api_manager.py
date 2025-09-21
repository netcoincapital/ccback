#!/usr/bin/env python3
"""
Ethereum API Manager - Manage API Rate Limits and Errors
مدیر API اتریوم - مدیریت محدودیت‌ها و خطاهای API
"""

import time
import random
from typing import List, Optional

class EthereumAPIManager:
    """کلاس مدیریت API Key و Rate Limiting"""
    
    def __init__(self, api_keys: List[str], max_requests_per_second: int = 4):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.max_requests_per_second = max_requests_per_second
        self.request_times = []
        self.failed_requests = 0
        self.total_requests = 0
        
        # محدودیت‌های مختلف برای کلیدهای مختلف
        self.rate_limits = {
            'free': 5,      # 5 درخواست در ثانیه
            'standard': 10,  # 10 درخواست در ثانیه  
            'pro': 25       # 25 درخواست در ثانیه
        }
        
        print(f"🔑 API Manager راه‌اندازی شد با {len(api_keys)} کلید")
    
    def get_current_api_key(self) -> str:
        """دریافت کلید API فعلی"""
        return self.api_keys[self.current_key_index]
    
    def rotate_api_key(self):
        """تغییر به کلید API بعدی"""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            print(f"🔄 تغییر به کلید API شماره {self.current_key_index + 1}")
    
    def wait_for_rate_limit(self):
        """انتظار برای رعایت محدودیت نرخ درخواست"""
        current_time = time.time()
        
        # حذف درخواست‌های قدیمی (بیش از 1 ثانیه)
        self.request_times = [t for t in self.request_times if current_time - t < 1.0]
        
        # اگر تعداد درخواست‌ها از حد مجاز بیشتر باشد، صبر کنیم
        if len(self.request_times) >= self.max_requests_per_second:
            sleep_time = 1.0 - (current_time - self.request_times[0])
            if sleep_time > 0:
                print(f"⏳ انتظار {sleep_time:.2f} ثانیه برای رعایت محدودیت API...")
                time.sleep(sleep_time)
        
        # اضافه کردن زمان درخواست فعلی
        self.request_times.append(current_time)
        self.total_requests += 1
    
    def handle_api_error(self, error_message: str) -> bool:
        """مدیریت خطاهای API و تصمیم‌گیری برای ادامه یا توقف"""
        self.failed_requests += 1
        
        # انواع خطاهای شناخته شده
        if "rate limit" in error_message.lower():
            print(f"🚫 محدودیت نرخ درخواست - تغییر کلید API")
            self.rotate_api_key()
            time.sleep(5)  # صبر 5 ثانیه
            return True  # ادامه
        
        elif "timeout" in error_message.lower():
            print(f"⏰ Timeout - افزایش تاخیر")
            time.sleep(random.uniform(2, 5))  # تاخیر تصادفی
            return True  # ادامه
        
        elif "connection" in error_message.lower():
            print(f"🔌 مشکل اتصال - تلاش مجدد")
            time.sleep(3)
            return True  # ادامه
        
        elif self.failed_requests > 10:
            print(f"❌ تعداد خطاها زیاد شده ({self.failed_requests}) - توقف")
            return False  # توقف
        
        else:
            print(f"⚠️ خطای نامشخص: {error_message}")
            time.sleep(1)
            return True  # ادامه
    
    def get_optimal_delay(self) -> float:
        """محاسبه تاخیر بهینه بر اساس وضعیت API"""
        base_delay = 1.0 / self.max_requests_per_second
        
        # اگر خطاهای زیادی داشتیم، تاخیر بیشتر
        if self.failed_requests > 5:
            base_delay *= 2
        
        # اضافه کردن تاخیر تصادفی کوچک
        return base_delay + random.uniform(0.1, 0.3)
    
    def print_stats(self):
        """نمایش آمار API"""
        success_rate = ((self.total_requests - self.failed_requests) / self.total_requests * 100) if self.total_requests > 0 else 0
        
        print(f"\n📊 آمار API:")
        print(f"   🔢 کل درخواست‌ها: {self.total_requests}")
        print(f"   ❌ درخواست‌های ناموفق: {self.failed_requests}")
        print(f"   ✅ نرخ موفقیت: {success_rate:.1f}%")
        print(f"   🔑 کلید فعلی: {self.current_key_index + 1}/{len(self.api_keys)}")

def create_api_manager() -> EthereumAPIManager:
    """ایجاد مدیر API با کلیدهای مختلف"""
    
    # لیست کلیدهای API (می‌توانید کلیدهای بیشتری اضافه کنید)
    api_keys = [
        "77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY",  # کلید اصلی
        # "YOUR_SECOND_API_KEY",  # کلید دوم
        # "YOUR_THIRD_API_KEY",   # کلید سوم
    ]
    
    return EthereumAPIManager(api_keys, max_requests_per_second=4)

if __name__ == "__main__":
    # تست API Manager
    manager = create_api_manager()
    
    print("🧪 تست API Manager...")
    for i in range(10):
        manager.wait_for_rate_limit()
        print(f"درخواست {i+1} - کلید: {manager.get_current_api_key()[:8]}...")
        
        # شبیه‌سازی خطا
        if i == 5:
            manager.handle_api_error("Rate limit exceeded")
        
        time.sleep(0.1)
    
    manager.print_stats()
