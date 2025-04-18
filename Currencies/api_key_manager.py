"""
ماژول مدیریت کلیدهای API برای سرویس‌های مختلف
"""
import os
import time
import random
from utils.logging_config import get_logger
from dotenv import load_dotenv

# بارگذاری فایل .env
load_dotenv()

logger = get_logger(__file__)
logger.info("Initializing API key manager")

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
                logger.info(f"Loaded {len(cmc_keys)} CoinMarketCap API keys")
            else:
                logger.warning("No CoinMarketCap API keys found in environment variables")
        else:
            logger.warning("CMC_API_KEYS environment variable not found")
        
        # می‌توان کلیدهای API دیگر را در اینجا اضافه کرد
    
    def get_api_key(self, service_name, min_interval_seconds=1):
        """
        دریافت کلید API برای سرویس مورد نظر به صورت چرخشی
        
        Args:
            service_name (str): نام سرویس (مثل 'coinmarketcap')
            min_interval_seconds (int): حداقل فاصله زمانی بین استفاده مجدد از یک کلید
            
        Returns:
            str: کلید API
        """
        if service_name not in self.api_keys or not self.api_keys[service_name]:
            logger.error(f"No API keys available for {service_name}")
            return None
        
        keys = self.api_keys[service_name]
        
        # اگر فقط یک کلید داریم، آن را برگردان
        if len(keys) == 1:
            return keys[0]
        
        current_time = time.time()
        available_keys = []
        
        # بررسی کلیدهایی که فاصله زمانی مناسب از آخرین استفاده دارند
        for key in keys:
            last_time = self.last_used_time[service_name].get(key, 0)
            if current_time - last_time >= min_interval_seconds:
                available_keys.append(key)
        
        # اگر هیچ کلیدی با فاصله زمانی مناسب نیست، کلید با بیشترین فاصله را انتخاب کن
        if not available_keys:
            logger.warning(f"All {service_name} API keys were recently used. Selecting least recently used key.")
            key_times = [(key, self.last_used_time[service_name].get(key, 0)) for key in keys]
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
    
    def get_key_stats(self, service_name):
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
            stats["keys"][key[-8:]] = {
                "last_used": last_used,
                "seconds_since_last_use": current_time - last_used if last_used > 0 else None
            }
        
        return stats 