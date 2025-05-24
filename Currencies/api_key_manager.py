"""
ماژول مدیریت کلیدهای API برای سرویس‌های مختلف
"""
import os
import time
import random
from utils.logging_config import get_logger
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# بارگذاری فایل .env
load_dotenv()

logger = get_logger(__file__)
logger.info("Initializing API key manager")

class ApiKeyError(Exception):
    """خطای پایه برای مشکلات API"""
    pass

class RateLimitError(ApiKeyError):
    """خطای محدودیت نرخ درخواست"""
    pass

class ApiKeyManager:
    """کلاس مدیریت کلیدهای API برای سرویس‌های مختلف"""
    
    _instance = None
    
    def __new__(cls):
        """الگوی Singleton برای اطمینان از وجود تنها یک نمونه از مدیریت کلیدها"""
        if cls._instance is None:
            cls._instance = super(ApiKeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """مقداردهی اولیه مدیریت کلیدها"""
        if self._initialized:
            return
        
        self.api_keys = {}
        self.current_key_index = {}
        self.last_used_time = {}
        self.key_errors = {}  # ثبت خطاهای هر کلید
        self.key_cooldown = {}  # زمان سرد شدن هر کلید
        self.load_keys()
        self._initialized = True
        
    def load_keys(self):
        """بارگذاری کلیدهای API از متغیرهای محیطی"""
        # CoinMarketCap API Keys
        cmc_keys_str = os.getenv('CMC_API_KEYS', '')
        if cmc_keys_str:
            cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
            if cmc_keys:
                self.api_keys['coinmarketcap'] = cmc_keys
                self.current_key_index['coinmarketcap'] = 0
                # زمان استفاده از هر کلید را مقداردهی اولیه می‌کنیم
                self.last_used_time['coinmarketcap'] = {key: 0 for key in cmc_keys}
                self.key_errors['coinmarketcap'] = {key: 0 for key in cmc_keys}
                self.key_cooldown['coinmarketcap'] = {key: 0 for key in cmc_keys}
                logger.info(f"Loaded {len(cmc_keys)} CoinMarketCap API keys")
            else:
                logger.warning("No CoinMarketCap API keys found in environment variables")
        else:
            logger.warning("CMC_API_KEYS environment variable not found")
        
        # می‌توان کلیدهای API دیگر را در اینجا اضافه کرد
    
    def is_key_in_cooldown(self, service_name: str, key: str) -> bool:
        """بررسی اینکه آیا کلید در حالت سرد شدن است یا خیر"""
        if service_name not in self.key_cooldown or key not in self.key_cooldown[service_name]:
            return False
        
        cooldown_time = self.key_cooldown[service_name][key]
        return time.time() < cooldown_time
    
    def set_key_cooldown(self, service_name: str, key: str, duration_seconds: int = 300):
        """تنظیم زمان سرد شدن برای یک کلید"""
        if service_name not in self.key_cooldown:
            self.key_cooldown[service_name] = {}
        self.key_cooldown[service_name][key] = time.time() + duration_seconds
    
    def increment_key_errors(self, service_name: str, key: str):
        """افزایش شمارنده خطاهای یک کلید"""
        if service_name not in self.key_errors:
            self.key_errors[service_name] = {}
        self.key_errors[service_name][key] = self.key_errors[service_name].get(key, 0) + 1
        
        # اگر تعداد خطاها از حد معینی بیشتر شد، کلید را در حالت سرد شدن قرار بده
        if self.key_errors[service_name][key] >= 3:
            self.set_key_cooldown(service_name, key, 600)  # 10 دقیقه سرد شدن
            logger.warning(f"Key {key[:8]}... for {service_name} has been put in cooldown due to multiple errors")
    
    def reset_key_errors(self, service_name: str, key: str):
        """بازنشانی شمارنده خطاهای یک کلید"""
        if service_name in self.key_errors and key in self.key_errors[service_name]:
            self.key_errors[service_name][key] = 0
    
    def get_api_key(self, service_name: str, min_interval_seconds: int = 1) -> Optional[str]:
        """
        دریافت کلید API برای سرویس مورد نظر به صورت چرخشی
        
        Args:
            service_name (str): نام سرویس (مثل 'coinmarketcap')
            min_interval_seconds (int): حداقل فاصله زمانی بین استفاده مجدد از یک کلید
            
        Returns:
            str: کلید API یا None در صورت عدم دسترسی به کلید
        """
        if service_name not in self.api_keys or not self.api_keys[service_name]:
            logger.error(f"No API keys available for {service_name}")
            return None
        
        keys = self.api_keys[service_name]
        
        # اگر فقط یک کلید داریم، آن را برگردان
        if len(keys) == 1:
            key = keys[0]
            if self.is_key_in_cooldown(service_name, key):
                logger.warning(f"Only available key for {service_name} is in cooldown")
                return None
            return key
        
        current_time = time.time()
        available_keys = []
        
        # بررسی کلیدهایی که فاصله زمانی مناسب از آخرین استفاده دارند و در حالت سرد شدن نیستند
        for key in keys:
            if self.is_key_in_cooldown(service_name, key):
                continue
                
            last_time = self.last_used_time[service_name].get(key, 0)
            if current_time - last_time >= min_interval_seconds:
                available_keys.append(key)
        
        # اگر هیچ کلیدی با فاصله زمانی مناسب نیست، کلید با بیشترین فاصله را انتخاب کن
        if not available_keys:
            logger.warning(f"All {service_name} API keys were recently used or in cooldown. Selecting least recently used key.")
            key_times = [(key, self.last_used_time[service_name].get(key, 0)) 
                        for key in keys 
                        if not self.is_key_in_cooldown(service_name, key)]
            
            if not key_times:
                logger.error(f"No available keys for {service_name} (all in cooldown)")
                return None
                
            key_times.sort(key=lambda x: x[1])  # مرتب‌سازی بر اساس زمان استفاده
            selected_key = key_times[0][0]  # کلید با کمترین زمان استفاده
        else:
            # انتخاب تصادفی از کلیدهای در دسترس
            selected_key = random.choice(available_keys)
        
        # به‌روزرسانی زمان استفاده از کلید
        self.last_used_time[service_name][selected_key] = current_time
        
        # به‌روزرسانی شاخص کلید فعلی برای استفاده بعدی
        current_index = keys.index(selected_key)
        self.current_key_index[service_name] = (current_index + 1) % len(keys)
        
        logger.debug(f"Selected API key for {service_name}: {selected_key[:8]}...")
        return selected_key
    
    def handle_api_error(self, service_name: str, key: str, error: Exception):
        """
        مدیریت خطای API و اعمال سیاست‌های مناسب
        
        Args:
            service_name (str): نام سرویس
            key (str): کلید API
            error (Exception): خطای رخ داده
        """
        if isinstance(error, RateLimitError):
            logger.warning(f"Rate limit hit with API key {key[:8]}...")
            self.increment_key_errors(service_name, key)
            self.set_key_cooldown(service_name, key, 300)  # 5 دقیقه سرد شدن
        else:
            logger.error(f"API error with key {key[:8]}...: {str(error)}")
            self.increment_key_errors(service_name, key)
    
    def get_key_stats(self, service_name: str) -> Dict[str, Any]:
        """
        دریافت آمار استفاده از کلیدها
        
        Args:
            service_name (str): نام سرویس
            
        Returns:
            dict: آمار کلیدها
        """
        if service_name not in self.api_keys:
            return {"error": f"Service {service_name} not found"}
        
        keys = self.api_keys[service_name]
        stats = {
            "total_keys": len(keys),
            "current_key_index": self.current_key_index.get(service_name, 0),
            "keys": {}
        }
        
        current_time = time.time()
        for key in keys:
            last_used = self.last_used_time[service_name].get(key, 0)
            error_count = self.key_errors[service_name].get(key, 0)
            cooldown_time = self.key_cooldown[service_name].get(key, 0)
            
            stats["keys"][key[-8:]] = {
                "last_used": last_used,
                "seconds_since_last_use": current_time - last_used if last_used > 0 else None,
                "error_count": error_count,
                "in_cooldown": current_time < cooldown_time,
                "cooldown_remaining": max(0, cooldown_time - current_time) if current_time < cooldown_time else 0
            }
        
        return stats 