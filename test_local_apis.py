#!/usr/bin/env python3
"""
تست API های محلی Prices و Chart
Test local Prices and Chart APIs
"""

import requests
import json
from datetime import datetime

def test_prices_api():
    """تست Prices API"""
    
    print("="*50)
    print("💰 تست Prices API")
    print("="*50)
    
    # URL محلی (تنظیم کنید)
    url = "http://localhost:5000/api/prices"
    
    # درخواست نمونه
    payload = {
        "Symbol": ["BTC", "ETH", "ADA"],
        "FiatCurrencies": ["USD", "EUR"]
    }
    
    try:
        print(f"🔍 ارسال درخواست به: {url}")
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n📥 Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ پاسخ موفق:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ خطا:")
            print(f"   Status: {response.status_code}")
            print(f"   Text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ خطای اتصال - آیا سرور روشن است؟")
    except Exception as e:
        print(f"❌ خطا: {str(e)}")

def test_chart_api():
    """تست Chart API"""
    
    print("\n" + "="*50)
    print("📈 تست Chart API")
    print("="*50)
    
    # URL محلی
    url = "http://localhost:5000/api/chart-data"
    
    # درخواست نمونه
    payload = {
        "Symbol": "BTC",
        "FiatCurrency": "USD",
        "timeframe": "1d",
        "points": 24
    }
    
    try:
        print(f"🔍 ارسال درخواست به: {url}")
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n📥 Response:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ پاسخ موفق:")
            
            # نمایش خلاصه
            if data.get('status') == 'success':
                chart_data = data['data']
                print(f"   📊 نماد: {chart_data['symbol']}")
                print(f"   💱 ارز: {chart_data['fiat_currency']}")
                print(f"   ⏰ بازه: {chart_data['timeframe']}")
                print(f"   📈 تعداد نقاط: {chart_data['total_points']}")
                
                # آمار
                stats = chart_data['statistics']
                print(f"\n📊 آمار:")
                print(f"   🔺 بالاترین: ${stats['highest_price']:,.2f}")
                print(f"   🔻 پایین‌ترین: ${stats['lowest_price']:,.2f}")
                print(f"   📊 میانگین: ${stats['average_price']:,.2f}")
                print(f"   📈 تغییر 24ساعته: {stats['percentage_change_24h']:.2f}%")
                
                # نمونه نقاط
                price_data = chart_data['price_data']
                print(f"\n📈 نمونه نقاط (اول و آخر):")
                print(f"   🟢 اولین: {price_data[0]['datetime']} - ${price_data[0]['price']:,.2f}")
                print(f"   🔴 آخرین: {price_data[-1]['datetime']} - ${price_data[-1]['price']:,.2f}")
            
            # نمایش کامل (اختیاری)
            # print(f"\n📋 پاسخ کامل:")
            # print(json.dumps(data, indent=2, ensure_ascii=False))
            
        else:
            print(f"\n❌ خطا:")
            print(f"   Status: {response.status_code}")
            print(f"   Text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ خطای اتصال - آیا سرور روشن است؟")
    except Exception as e:
        print(f"❌ خطا: {str(e)}")

def test_different_timeframes():
    """تست بازه‌های زمانی مختلف"""
    
    print("\n" + "="*50)
    print("⏰ تست بازه‌های زمانی مختلف")
    print("="*50)
    
    client = CoinCeeperAPIClient()
    
    timeframes = [
        ("1h", "ساعتی"),
        ("1d", "روزانه"),
        ("1w", "هفتگی"),
        ("1m", "ماهانه"),
        ("3m", "سه‌ماهه"),
        ("1y", "سالانه")
    ]
    
    for timeframe, description in timeframes:
        print(f"\n🔍 تست {description} ({timeframe}):")
        
        result = client.get_chart_data("ETH", "USD", timeframe, 10)
        
        if result and result.get('status') == 'success':
            data = result['data']
            print(f"   ✅ {data['total_points']} نقطه یافت شد")
            
            if data['price_data']:
                first_point = data['price_data'][0]
                last_point = data['price_data'][-1]
                print(f"   📊 از {first_point['datetime']} تا {last_point['datetime']}")
                print(f"   💰 قیمت: ${first_point['price']:,.2f} → ${last_point['price']:,.2f}")
        else:
            print(f"   ❌ خطا در {description}")

def test_error_cases():
    """تست موارد خطا"""
    
    print("\n" + "="*50)
    print("🛡️ تست موارد خطا")
    print("="*50)
    
    client = CoinCeeperAPIClient()
    
    # تست 1: نماد نامعتبر
    print(f"🔍 تست 1: نماد نامعتبر")
    result = client.get_prices(["INVALID_SYMBOL"])
    if result:
        print(f"   پاسخ: {result.get('status', 'unknown')}")
    
    # تست 2: timeframe نامعتبر
    print(f"\n🔍 تست 2: timeframe نامعتبر")
    result = client.get_chart_data("BTC", "USD", "invalid_timeframe")
    if result:
        print(f"   پاسخ: {result.get('status', 'unknown')}")
    
    # تست 3: ارز فیات نامعتبر
    print(f"\n🔍 تست 3: ارز فیات نامعتبر")
    result = client.get_prices(["BTC"], ["INVALID_FIAT"])
    if result:
        print(f"   پاسخ: {result.get('status', 'unknown')}")

def main():
    """اجرای تمام تست‌ها"""
    
    print("🧪 تست کامل API های CoinCeeper")
    print("=" * 60)
    print(f"🕐 زمان شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # تست Prices API
        test_prices_api()
        
        # تست Chart API
        test_chart_api()
        
        # تست بازه‌های مختلف
        test_different_timeframes()
        
        # تست موارد خطا
        test_error_cases()
        
        print(f"\n✅ تمام تست‌ها تکمیل شد!")
        print(f"🕐 زمان پایان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ تست‌ها متوقف شد")
    except Exception as e:
        print(f"❌ خطای کلی: {str(e)}")

if __name__ == "__main__":
    main()
