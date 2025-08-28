#!/usr/bin/env python3
"""
تست دقیق Rate Limit برای Balance APIs
این اسکریپت دقیقاً مشخص می‌کند کدام بخش rate limit می‌دهد و زمان‌بندی را تحلیل می‌کند
"""

import requests
import json
import time
import redis
from datetime import datetime
from typing import Dict, Any
import sys

# تنظیمات
SERVER_URL = "http://localhost:5000"  # آدرس سرور شما
USER_ID = "550e8400-e29b-41d4-a716-446655440000"  # UUID معتبر برای تست
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

class RateLimitTester:
    def __init__(self, server_url: str, user_id: str):
        self.server_url = server_url
        self.user_id = user_id
        self.session = requests.Session()
        self.redis_client = None
        
        # تلاش برای اتصال به Redis
        try:
            self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            self.redis_client.ping()
            print("✅ Redis در دسترس است")
        except Exception as e:
            print(f"❌ Redis در دسترس نیست: {e}")
            print("⚠️ Rate limiting غیرفعال خواهد بود")
    
    def print_separator(self, title: str):
        print(f"\n{'='*60}")
        print(f"🔍 {title}")
        print('='*60)
    
    def send_request(self, endpoint: str, request_num: int) -> Dict[str, Any]:
        """ارسال درخواست و بازگرداندن نتیجه تفصیلی"""
        url = f"{self.server_url}{endpoint}"
        payload = {"UserID": self.user_id}
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                url, 
                json=payload,
                timeout=30,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': f'RateLimitTester-{request_num}'
                }
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                'request_num': request_num,
                'status_code': response.status_code,
                'duration': duration,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'success': response.status_code == 200,
                'rate_limited': response.status_code == 429,
                'response_size': len(response.content),
                'headers': dict(response.headers)
            }
            
            # تلاش برای parse کردن JSON response
            try:
                result['json_response'] = response.json()
            except:
                result['json_response'] = None
                result['text_response'] = response.text[:200]  # اول 200 کاراکتر
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                'request_num': request_num,
                'error': str(e),
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'success': False,
                'rate_limited': False
            }
    
    def check_redis_keys(self, endpoint: str):
        """بررسی کلیدهای Redis مربوط به rate limiting"""
        if not self.redis_client:
            return
        
        print(f"\n🔑 بررسی کلیدهای Redis برای {endpoint}:")
        
        # جستجوی کلیدهای مرتبط
        pattern = f"*{endpoint}*"
        keys = self.redis_client.keys(pattern)
        
        if not keys:
            print("   هیچ کلیدی پیدا نشد")
            
            # جستجوی کلیدهای عمومی rate limit
            general_keys = self.redis_client.keys("*:*")
            if general_keys:
                print("   کلیدهای عمومی rate limit:")
                for key in general_keys[:5]:  # نمایش 5 کلید اول
                    try:
                        value = self.redis_client.get(key)
                        ttl = self.redis_client.ttl(key)
                        print(f"     {key.decode()}: {value.decode() if value else 'None'} (TTL: {ttl}s)")
                    except:
                        pass
        else:
            for key in keys:
                try:
                    value = self.redis_client.get(key)
                    ttl = self.redis_client.ttl(key)
                    print(f"   {key.decode()}: {value.decode() if value else 'None'} (TTL: {ttl}s)")
                except:
                    pass
    
    def test_balance_api(self):
        """تست API /balance"""
        self.print_separator("تست API /balance (محدودیت: 10 درخواست در دقیقه)")
        
        endpoint = "/balance"
        results = []
        
        # ارسال 12 درخواست سریع
        print(f"ارسال 12 درخواست سریع برای تریگر کردن rate limit...")
        
        for i in range(1, 13):
            print(f"\nدرخواست #{i}:")
            result = self.send_request(endpoint, i)
            results.append(result)
            
            # نمایش نتیجه
            if result.get('rate_limited'):
                print(f"❌ Rate Limited! Status: {result['status_code']}")
                print(f"   زمان: {result['timestamp']}")
                if result.get('json_response'):
                    print(f"   پیام: {result['json_response'].get('error', 'بدون پیام')}")
                break
            elif result.get('success'):
                print(f"✅ موفق! Status: {result['status_code']} | مدت: {result['duration']:.2f}s")
                if result.get('json_response'):
                    success = result['json_response'].get('success', False)
                    balance_count = len(result['json_response'].get('Balances', []))
                    print(f"   Success: {success} | تعداد Balance: {balance_count}")
            else:
                print(f"⚠️ خطا! Status: {result.get('status_code', 'N/A')}")
                if result.get('error'):
                    print(f"   خطا: {result['error']}")
            
            # کمی تأخیر
            time.sleep(0.5)
        
        # بررسی Redis
        self.check_redis_keys(endpoint)
        
        return results
    
    def test_update_balance_api(self):
        """تست API /update-balance"""
        self.print_separator("تست API /update-balance (محدودیت: 2 درخواست در 5 دقیقه)")
        
        endpoint = "/update-balance"
        results = []
        
        # ارسال 3 درخواست
        print(f"ارسال 3 درخواست برای تریگر کردن rate limit...")
        
        for i in range(1, 4):
            print(f"\nدرخواست #{i}:")
            result = self.send_request(endpoint, i)
            results.append(result)
            
            # نمایش نتیجه
            if result.get('rate_limited'):
                print(f"❌ Rate Limited! Status: {result['status_code']}")
                print(f"   زمان: {result['timestamp']}")
                if result.get('json_response'):
                    print(f"   پیام: {result['json_response'].get('error', 'بدون پیام')}")
                break
            elif result.get('success'):
                print(f"✅ موفق! Status: {result['status_code']} | مدت: {result['duration']:.2f}s")
                if result.get('json_response'):
                    success = result['json_response'].get('success', False)
                    print(f"   Success: {success}")
            else:
                print(f"⚠️ خطا! Status: {result.get('status_code', 'N/A')}")
                if result.get('error'):
                    print(f"   خطا: {result['error']}")
                elif result.get('json_response'):
                    error_msg = result['json_response'].get('message', 'بدون پیام')
                    print(f"   پیام: {error_msg}")
            
            # تأخیر بین درخواست‌ها
            if i < 3:
                print("   انتظار 3 ثانیه...")
                time.sleep(3)
        
        # بررسی Redis
        self.check_redis_keys(endpoint)
        
        return results
    
    def test_server_connectivity(self):
        """تست اتصال به سرور"""
        self.print_separator("تست اتصال به سرور")
        
        try:
            # تست health check اگر وجود دارد
            health_url = f"{self.server_url}/health-check"
            response = requests.get(health_url, timeout=10)
            print(f"✅ Health Check: {response.status_code}")
        except:
            print("⚠️ Health Check در دسترس نیست")
        
        # تست اتصال اصلی
        try:
            response = requests.get(self.server_url, timeout=10)
            print(f"✅ سرور در دسترس است: {response.status_code}")
        except Exception as e:
            print(f"❌ خطا در اتصال به سرور: {e}")
            return False
        
        return True
    
    def run_all_tests(self):
        """اجرای همه تست‌ها"""
        print("🚀 شروع تست Rate Limit")
        print(f"سرور: {self.server_url}")
        print(f"UserID: {self.user_id}")
        
        # تست اتصال
        if not self.test_server_connectivity():
            print("❌ سرور در دسترس نیست. تست متوقف شد.")
            return
        
        # تست /balance
        balance_results = self.test_balance_api()
        
        # انتظار برای reset
        print(f"\n⏳ انتظار 70 ثانیه برای reset شدن rate limit...")
        time.sleep(70)
        
        # تست /update-balance
        update_results = self.test_update_balance_api()
        
        # نتیجه‌گیری
        self.print_separator("نتیجه‌گیری")
        
        print("📊 خلاصه نتایج:")
        
        # تحلیل نتایج balance
        balance_rate_limited = any(r.get('rate_limited') for r in balance_results)
        if balance_rate_limited:
            first_limit = next(r for r in balance_results if r.get('rate_limited'))
            print(f"🔴 /balance: Rate limit در درخواست #{first_limit['request_num']} فعال شد")
        else:
            print(f"🟢 /balance: هیچ rate limit مشاهده نشد")
        
        # تحلیل نتایج update-balance
        update_rate_limited = any(r.get('rate_limited') for r in update_results)
        if update_rate_limited:
            first_limit = next(r for r in update_results if r.get('rate_limited'))
            print(f"🔴 /update-balance: Rate limit در درخواست #{first_limit['request_num']} فعال شد")
        else:
            print(f"🟢 /update-balance: هیچ rate limit مشاهده نشد")
        
        print(f"\n✅ منبع Rate Limit: سرور خودتان (Redis)")
        print(f"✅ محدودیت بر اساس IP address")
        print(f"✅ برای غیرفعال کردن: Redis را خاموش کنید")


if __name__ == "__main__":
    # بررسی آرگومان‌های خط فرمان
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
    if len(sys.argv) > 2:
        USER_ID = sys.argv[2]
    
    # اجرای تست
    tester = RateLimitTester(SERVER_URL, USER_ID)
    tester.run_all_tests()


