#!/usr/bin/env python3
"""
نمونه‌های استفاده از API های جدید Prices و Chart
Usage examples for updated Prices and Chart APIs
"""

import requests
import json
from datetime import datetime
import time

class CoinCeeperAPIClient:
    """کلاینت API برای سرویس‌های CoinCeeper"""
    
    def __init__(self, base_url="http://localhost:5000/api"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'CoinCeeper-Client/1.0'
        })

    def get_prices(self, symbols, fiat_currencies=None):
        """
        دریافت قیمت‌های ارزهای دیجیتال
        
        Args:
            symbols (list): لیست نمادهای ارز دیجیتال
            fiat_currencies (list): لیست ارزهای فیات (پیش‌فرض: USD)
        
        Returns:
            dict: پاسخ API شامل قیمت‌ها
        """
        if fiat_currencies is None:
            fiat_currencies = ["USD"]
        
        payload = {
            "Symbol": symbols,
            "FiatCurrencies": fiat_currencies
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/prices",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ خطا در دریافت قیمت‌ها: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ خطا در درخواست قیمت‌ها: {str(e)}")
            return None

    def get_chart_data(self, symbol, fiat_currency="USD", timeframe="1d", points=100):
        """
        دریافت داده‌های چارت
        
        Args:
            symbol (str): نماد ارز دیجیتال
            fiat_currency (str): ارز فیات
            timeframe (str): بازه زمانی (1h, 1d, 1w, 1m, 3m, 6m, 1y)
            points (int): تعداد نقاط داده
        
        Returns:
            dict: پاسخ API شامل داده‌های چارت
        """
        payload = {
            "Symbol": symbol,
            "FiatCurrency": fiat_currency,
            "timeframe": timeframe,
            "points": points
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/chart-data",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ خطا در دریافت چارت: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ خطا در درخواست چارت: {str(e)}")
            return None

def example_prices_usage():
    """مثال استفاده از Prices API"""
    
    print("="*50)
    print("💰 مثال استفاده از Prices API")
    print("="*50)
    
    client = CoinCeeperAPIClient()
    
    # درخواست قیمت چند ارز
    symbols = ["BTC", "ETH", "ADA", "DOGE"]
    fiat_currencies = ["USD", "EUR", "IRR"]
    
    print(f"🔍 درخواست قیمت برای: {symbols}")
    print(f"💱 در ارزهای: {fiat_currencies}")
    
    result = client.get_prices(symbols, fiat_currencies)
    
    if result and result.get('status') == 'success':
        data = result['data']
        metadata = result['metadata']
        
        print(f"\n✅ پاسخ موفق:")
        print(f"   📊 تعداد درخواست شده: {metadata['total_requested']}")
        print(f"   ✅ تعداد یافت شده: {metadata['total_found']}")
        print(f"   ⏱️ زمان پاسخ: {metadata['response_time_ms']}ms")
        
        # نمایش قیمت‌ها
        for symbol in symbols:
            if symbol in data:
                print(f"\n🪙 {symbol}:")
                for fiat in fiat_currencies:
                    if fiat in data[symbol]:
                        price_info = data[symbol][fiat]
                        print(f"   {fiat}: {price_info['formatted_price']} ({price_info['formatted_change']})")
            else:
                print(f"\n❌ {symbol}: یافت نشد")
    else:
        print("❌ خطا در دریافت قیمت‌ها")

def example_chart_usage():
    """مثال استفاده از Chart API"""
    
    print("\n" + "="*50)
    print("📈 مثال استفاده از Chart API")
    print("="*50)
    
    client = CoinCeeperAPIClient()
    
    # درخواست داده‌های چارت
    symbol = "ETH"
    timeframe = "1d"
    points = 24  # 24 نقطه برای چارت روزانه
    
    print(f"🔍 درخواست چارت {symbol} در بازه {timeframe}")
    print(f"📊 تعداد نقاط: {points}")
    
    result = client.get_chart_data(symbol, "USD", timeframe, points)
    
    if result and result.get('status') == 'success':
        data = result['data']
        metadata = result['metadata']
        
        print(f"\n✅ پاسخ موفق:")
        print(f"   📊 تعداد نقاط: {data['total_points']}")
        print(f"   ⏱️ زمان پاسخ: {metadata['response_time_ms']}ms")
        print(f"   🎯 کیفیت داده: {metadata['data_quality']}")
        
        # آمار کلی
        stats = data['statistics']
        print(f"\n📈 آمار بازه:")
        print(f"   🔺 بالاترین: ${stats['highest_price']:,.2f}")
        print(f"   🔻 پایین‌ترین: ${stats['lowest_price']:,.2f}")
        print(f"   📊 میانگین: ${stats['average_price']:,.2f}")
        print(f"   📈 تغییر 24ساعته: {stats['percentage_change_24h']:.2f}%")
        print(f"   🌊 نوسان: {stats['volatility']:.2f}%")
        
        # نمایش چند نقطه اول و آخر
        price_data = data['price_data']
        print(f"\n📊 نقاط قیمت (نمونه):")
        
        print(f"   🟢 اولین نقطه:")
        first_point = price_data[0]
        print(f"      زمان: {first_point['datetime']}")
        print(f"      قیمت: ${first_point['price']:,.2f}")
        
        print(f"   🔴 آخرین نقطه:")
        last_point = price_data[-1]
        print(f"      زمان: {last_point['datetime']}")
        print(f"      قیمت: ${last_point['price']:,.2f}")
        print(f"      تغییر: {last_point['change_percentage']:.2f}%")
        
        # قیمت فعلی
        current = data['current_price']
        print(f"\n💰 قیمت فعلی:")
        print(f"   قیمت: ${current['price']:,.2f}")
        print(f"   جهت: {current['trend']}")
        print(f"   آخرین به‌روزرسانی: {current['last_updated']}")
        
    else:
        print("❌ خطا در دریافت داده‌های چارت")

def example_error_handling():
    """مثال مدیریت خطاها"""
    
    print("\n" + "="*50)
    print("🛡️ مثال مدیریت خطاها")
    print("="*50)
    
    client = CoinCeeperAPIClient()
    
    # درخواست با نماد نامعتبر
    print("🔍 تست با نماد نامعتبر...")
    result = client.get_prices(["INVALID_SYMBOL"])
    
    if result and result.get('status') == 'error':
        error = result['error']
        print(f"❌ خطا:")
        print(f"   کد: {error['code']}")
        print(f"   پیام: {error['message']}")
        if 'details' in error:
            print(f"   جزئیات: {error['details']}")
    
    # درخواست چارت با timeframe نامعتبر
    print(f"\n🔍 تست با timeframe نامعتبر...")
    result = client.get_chart_data("BTC", "USD", "invalid_timeframe")
    
    if result and result.get('status') == 'error':
        error = result['error']
        print(f"❌ خطا:")
        print(f"   کد: {error['code']}")
        print(f"   پیام: {error['message']}")

def main():
    """اجرای تمام مثال‌ها"""
    
    print("🚀 نمونه‌های استفاده از API های CoinCeeper")
    print("=" * 60)
    
    try:
        # مثال Prices API
        example_prices_usage()
        
        # وقفه کوتاه
        time.sleep(1)
        
        # مثال Chart API
        example_chart_usage()
        
        # وقفه کوتاه
        time.sleep(1)
        
        # مثال مدیریت خطا
        example_error_handling()
        
        print(f"\n✅ تمام مثال‌ها اجرا شد!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ متوقف شد توسط کاربر")
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {str(e)}")

if __name__ == "__main__":
    main()
