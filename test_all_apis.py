#!/usr/bin/env python3
"""
تست کامل تمام API های آپدیت شده
Complete test for all updated APIs
"""

import requests
import json
from datetime import datetime, timedelta
import time

class CoinCeeperAPITester:
    """کلاس تست کامل API های CoinCeeper"""
    
    def __init__(self, base_url="http://localhost:5000/api"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'CoinCeeper-Tester/1.0'
        })

    def test_manual_update(self):
        """تست Manual Update API"""
        print("="*60)
        print("🔧 تست Manual Update API")
        print("="*60)
        
        payload = {
            "Symbol": ["BTC", "ETH"],
            "FiatCurrencies": ["USD", "EUR"],
            "force_update": True,
            "include_market_data": True
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/manual-update",
                json=payload,
                timeout=30
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    print(f"   آپدیت شده: {data['data']['updated_currencies']}")
                    print(f"   زمان پاسخ: {data['metadata']['response_time_ms']}ms")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_auto_all_currencies(self):
        """تست Automatic All Currencies API"""
        print("\n" + "="*60)
        print("🤖 تست Automatic All Currencies API")
        print("="*60)
        
        # محاسبه بازه زمانی (7 روز گذشته)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        payload = {
            "time_start": start_date.isoformat() + "Z",
            "time_end": end_date.isoformat() + "Z",
            "interval": "daily",
            "fiat_currencies": ["USD"],
            "max_currencies": 10
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/historical-prices-auto",
                json=payload,
                timeout=60
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    print(f"   ارزهای پردازش شده: {data['data']['currencies_processed']}")
                    print(f"   رکوردهای اضافه شده: {data['data']['records_added']}")
                    print(f"   زمان پردازش: {data['data']['processing_time_minutes']} دقیقه")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_long_term_data(self):
        """تست Long-term Data API"""
        print("\n" + "="*60)
        print("📊 تست Long-term Data API")
        print("="*60)
        
        payload = {
            "Symbol": ["BTC", "ETH"],
            "months": 3,
            "interval": "daily",
            "fiat_currencies": ["USD"]
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/historical-prices-bulk",
                json=payload,
                timeout=120
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    print(f"   نمادهای پردازش شده: {data['data']['symbols_processed']}")
                    print(f"   ماه‌های پردازش شده: {data['data']['months_processed']}")
                    print(f"   کل رکوردها: {data['data']['total_records_added']}")
                    print(f"   زمان پردازش: {data['metadata']['processing_time_minutes']} دقیقه")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_custom_historical(self):
        """تست Custom Historical Data API"""
        print("\n" + "="*60)
        print("📈 تست Custom Historical Data API")
        print("="*60)
        
        # بازه زمانی 24 ساعت گذشته
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)
        
        payload = {
            "Symbol": ["BTC"],
            "FiatCurrency": "USD",
            "time_start": start_date.isoformat() + "Z",
            "time_end": end_date.isoformat() + "Z",
            "interval": "hourly",
            "include_volume": True,
            "include_market_cap": True
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/historical-prices",
                json=payload,
                timeout=30
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    print(f"   نماد: {data['data']['symbol']}")
                    print(f"   تعداد نقاط: {data['data']['time_range']['total_points']}")
                    print(f"   بازه زمانی: {data['data']['time_range']['interval']}")
                    
                    if 'statistics' in data['data']:
                        stats = data['data']['statistics']
                        print(f"   بالاترین: ${stats['period_high']:,.2f}")
                        print(f"   پایین‌ترین: ${stats['period_low']:,.2f}")
                        print(f"   نوسان: {stats['volatility']:.2f}%")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_live_chart_update(self):
        """تست Live Chart Update API"""
        print("\n" + "="*60)
        print("⚡ تست Live Chart Update API")
        print("="*60)
        
        payload = {
            "Symbol": ["BTC", "ETH", "ADA"],
            "FiatCurrency": "USD"
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/chart-live-update",
                json=payload,
                timeout=15
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    live_prices = data['data']['live_prices']
                    print(f"   تعداد ارزها: {len(live_prices)}")
                    
                    for symbol, price_data in live_prices.items():
                        print(f"   {symbol}: {price_data['price_formatted']} ({price_data['change_formatted']})")
                    
                    print(f"   آپدیت بعدی: {data['metadata']['next_update_in_seconds']} ثانیه")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_main_chart(self):
        """تست Main Chart API"""
        print("\n" + "="*60)
        print("📊 تست Main Chart API")
        print("="*60)
        
        payload = {
            "Symbol": "BTC",
            "FiatCurrency": "USD",
            "timeframe": "1d",
            "points": 24,
            "include_volume": True,
            "include_indicators": True
        }
        
        try:
            print(f"📤 Request: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/chart-data",
                json=payload,
                timeout=30
            )
            
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ موفق:")
                if data.get('status') == 'success':
                    chart_data = data['data']
                    print(f"   نماد: {chart_data['symbol']}")
                    print(f"   بازه زمانی: {chart_data['timeframe']}")
                    print(f"   تعداد نقاط: {chart_data['total_points']}")
                    
                    if 'statistics' in chart_data:
                        stats = chart_data['statistics']
                        print(f"   بالاترین: ${stats['period_high']:,.2f}")
                        print(f"   پایین‌ترین: ${stats['period_low']:,.2f}")
                        print(f"   میانگین: ${stats['period_average']:,.2f}")
                    
                    if 'technical_indicators' in chart_data:
                        indicators = chart_data['technical_indicators']
                        print(f"   RSI: {indicators.get('rsi', 'N/A')}")
                        print(f"   SMA 20: ${indicators.get('sma_20', 0):,.2f}")
                    
                    print(f"   کیفیت داده: {chart_data['chart_config']['data_quality']}")
                else:
                    print(f"   خطا: {data.get('error', {}).get('message', 'Unknown')}")
            else:
                print(f"❌ خطا: {response.text}")
                
        except Exception as e:
            print(f"❌ خطا در تست: {str(e)}")

    def test_all_timeframes(self):
        """تست تمام بازه‌های زمانی چارت"""
        print("\n" + "="*60)
        print("⏰ تست تمام بازه‌های زمانی")
        print("="*60)
        
        timeframes = [
            ("1h", "ساعتی", 12),
            ("1d", "روزانه", 24),
            ("1w", "هفتگی", 168),
            ("1m", "ماهانه", 720),
            ("3m", "سه‌ماهه", 2160),
            ("6m", "شش‌ماهه", 4320),
            ("1y", "سالانه", 8760)
        ]
        
        for timeframe, description, max_points in timeframes:
            print(f"\n🔍 تست {description} ({timeframe}):")
            
            payload = {
                "Symbol": "BTC",
                "FiatCurrency": "USD",
                "timeframe": timeframe,
                "points": min(50, max_points)  # محدود کردن برای تست
            }
            
            try:
                response = self.session.post(
                    f"{self.base_url}/chart-data",
                    json=payload,
                    timeout=20
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        chart_data = data['data']
                        print(f"   ✅ {chart_data['total_points']} نقطه یافت شد")
                        print(f"   📊 کیفیت: {chart_data.get('chart_config', {}).get('data_quality', 'N/A')}")
                    else:
                        print(f"   ❌ خطا: {data.get('error', {}).get('message', 'Unknown')}")
                else:
                    print(f"   ❌ HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ خطا: {str(e)}")
            
            time.sleep(1)  # تاخیر بین درخواست‌ها

    def test_error_cases(self):
        """تست موارد خطا"""
        print("\n" + "="*60)
        print("🛡️ تست موارد خطا")
        print("="*60)
        
        test_cases = [
            {
                "name": "نماد نامعتبر",
                "endpoint": "/prices",
                "payload": {"Symbol": ["INVALID_SYMBOL"], "FiatCurrencies": ["USD"]}
            },
            {
                "name": "timeframe نامعتبر",
                "endpoint": "/chart-data",
                "payload": {"Symbol": "BTC", "timeframe": "invalid"}
            },
            {
                "name": "ارز فیات نامعتبر",
                "endpoint": "/chart-live-update",
                "payload": {"Symbol": ["BTC"], "FiatCurrency": "INVALID_FIAT"}
            },
            {
                "name": "تاریخ نامعتبر",
                "endpoint": "/historical-prices",
                "payload": {"Symbol": ["BTC"], "time_start": "invalid_date"}
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🔍 {test_case['name']}:")
            
            try:
                response = self.session.post(
                    f"{self.base_url}{test_case['endpoint']}",
                    json=test_case['payload'],
                    timeout=10
                )
                
                if response.status_code == 400:
                    data = response.json()
                    if data.get('status') == 'error':
                        print(f"   ✅ خطا به درستی تشخیص داده شد:")
                        print(f"      کد: {data['error']['code']}")
                        print(f"      پیام: {data['error']['message']}")
                    else:
                        print(f"   ⚠️ پاسخ غیرمنتظره: {data}")
                else:
                    print(f"   ⚠️ Status غیرمنتظره: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ خطا در تست: {str(e)}")

    def test_performance(self):
        """تست عملکرد API ها"""
        print("\n" + "="*60)
        print("⚡ تست عملکرد")
        print("="*60)
        
        performance_tests = [
            {
                "name": "Live Update سریع",
                "endpoint": "/chart-live-update",
                "payload": {"Symbol": ["BTC"], "FiatCurrency": "USD"},
                "expected_time": 200  # ms
            },
            {
                "name": "Chart Data متوسط",
                "endpoint": "/chart-data", 
                "payload": {"Symbol": "ETH", "timeframe": "1d", "points": 24},
                "expected_time": 500  # ms
            },
            {
                "name": "Prices API سریع",
                "endpoint": "/prices",
                "payload": {"Symbol": ["BTC", "ETH"], "FiatCurrencies": ["USD"]},
                "expected_time": 300  # ms
            }
        ]
        
        for test in performance_tests:
            print(f"\n🔍 {test['name']}:")
            
            try:
                start_time = time.time()
                
                response = self.session.post(
                    f"{self.base_url}{test['endpoint']}",
                    json=test['payload'],
                    timeout=10
                )
                
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        print(f"   ✅ موفق در {response_time_ms:.0f}ms")
                        
                        if response_time_ms <= test['expected_time']:
                            print(f"   🚀 عملکرد عالی (انتظار: {test['expected_time']}ms)")
                        else:
                            print(f"   ⚠️ کندتر از انتظار (انتظار: {test['expected_time']}ms)")
                    else:
                        print(f"   ❌ خطا: {data.get('error', {}).get('message', 'Unknown')}")
                else:
                    print(f"   ❌ HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ خطا: {str(e)}")

    def run_all_tests(self):
        """اجرای تمام تست‌ها"""
        print("🧪 شروع تست کامل API های CoinCeeper")
        print("=" * 80)
        print(f"🕐 زمان شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Base URL: {self.base_url}")
        
        try:
            # تست Manual Update
            self.test_manual_update()
            time.sleep(2)
            
            # تست Auto All Currencies  
            self.test_auto_all_currencies()
            time.sleep(2)
            
            # تست Long-term Data
            self.test_long_term_data()
            time.sleep(2)
            
            # تست Custom Historical
            self.test_custom_historical()
            time.sleep(2)
            
            # تست Live Chart Update
            self.test_live_chart_update()
            time.sleep(2)
            
            # تست Main Chart
            self.test_main_chart()
            time.sleep(1)
            
            # تست تمام timeframes
            self.test_all_timeframes()
            time.sleep(1)
            
            # تست موارد خطا
            self.test_error_cases()
            time.sleep(1)
            
            # تست عملکرد
            self.test_performance()
            
            print(f"\n✅ تمام تست‌ها تکمیل شد!")
            print(f"🕐 زمان پایان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except KeyboardInterrupt:
            print(f"\n⏹️ تست‌ها متوقف شد توسط کاربر")
        except Exception as e:
            print(f"❌ خطای کلی: {str(e)}")

def main():
    """اجرای تست اصلی"""
    
    print("🚀 تست‌گر کامل API های CoinCeeper")
    print("=" * 60)
    
    # دریافت URL سرور
    base_url = input("🌐 Base URL سرور (پیش‌فرض: http://localhost:5000/api): ").strip()
    if not base_url:
        base_url = "http://localhost:5000/api"
    
    # ایجاد تست‌گر
    tester = CoinCeeperAPITester(base_url)
    
    # اجرای تست‌ها
    tester.run_all_tests()

if __name__ == "__main__":
    main()
