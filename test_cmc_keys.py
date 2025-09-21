#!/usr/bin/env python3
"""
تست کلیدهای CoinMarketCap
Test CoinMarketCap API Keys
"""

import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def test_cmc_keys():
    """تست تمام کلیدهای CMC"""
    
    print("="*60)
    print("🧪 تست کلیدهای CoinMarketCap")
    print("="*60)
    
    # خواندن کلیدها
    cmc_keys_str = os.getenv('CMC_API_KEYS', os.getenv('CMC_API_KEY', ''))
    cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
    
    print(f"🔑 تعداد کلیدهای یافت شده: {len(cmc_keys)}")
    
    if not cmc_keys:
        print("❌ هیچ کلید CMC یافت نشد!")
        print("لطفاً فایل .env را بررسی کنید")
        return
    
    base_url = "https://pro-api.coinmarketcap.com/v1"
    working_keys = []
    
    for i, api_key in enumerate(cmc_keys):
        print(f"\n🔍 تست کلید {i+1}: {api_key[:8]}...")
        
        try:
            # تست ساده: دریافت اطلاعات BTC
            url = f"{base_url}/cryptocurrency/quotes/latest"
            headers = {
                'Accepts': 'application/json',
                'X-CMC_PRO_API_KEY': api_key,
            }
            params = {
                'id': '1',  # BTC
                'convert': 'USD'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status', {}).get('error_code') == 0:
                    btc_data = data.get('data', {}).get('1', {})
                    if btc_data:
                        price = btc_data.get('quote', {}).get('USD', {}).get('price', 0)
                        print(f"   ✅ کار می‌کند - قیمت BTC: ${price:,.2f}")
                        working_keys.append(api_key)
                    else:
                        print(f"   ❌ داده نامعتبر")
                else:
                    error_msg = data.get('status', {}).get('error_message', 'Unknown')
                    print(f"   ❌ خطای API: {error_msg}")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                
                if response.status_code == 429:
                    print(f"   🚫 Rate limit - کلید محدود شده")
                elif response.status_code == 401:
                    print(f"   🔐 کلید نامعتبر")
                elif response.status_code == 403:
                    print(f"   🚫 دسترسی مسدود")
                
        except Exception as e:
            print(f"   ❌ خطا در تست: {str(e)}")
        
        # تاخیر بین تست‌ها
        time.sleep(1)
    
    print(f"\n📊 خلاصه:")
    print(f"   🔑 کل کلیدها: {len(cmc_keys)}")
    print(f"   ✅ کلیدهای کارآمد: {len(working_keys)}")
    print(f"   ❌ کلیدهای خراب: {len(cmc_keys) - len(working_keys)}")
    
    if working_keys:
        print(f"\n🎉 کلیدهای کارآمد:")
        for i, key in enumerate(working_keys):
            print(f"   {i+1}. {key[:8]}...")
        
        print(f"\n💡 توصیه:")
        if len(working_keys) >= 5:
            print(f"   ✅ تعداد کلیدها کافی است ({len(working_keys)} کلید)")
            print(f"   🚀 می‌توانید اجرای کامل را شروع کنید")
        elif len(working_keys) >= 2:
            print(f"   ⚠️ تعداد کلیدها محدود است ({len(working_keys)} کلید)")
            print(f"   📊 اجرای تست سریع توصیه می‌شود")
        else:
            print(f"   ❌ تعداد کلیدها ناکافی است")
            print(f"   💡 لطفاً کلیدهای بیشتری تهیه کنید")
    else:
        print(f"\n😔 هیچ کلید کارآمدی یافت نشد!")
        print(f"💡 لطفاً کلیدهای CMC را بررسی کنید")
    
    return working_keys

def test_historical_endpoint():
    """تست endpoint تاریخی CMC"""
    
    print(f"\n" + "="*60)
    print("📈 تست Historical Endpoint")
    print("="*60)
    
    cmc_keys_str = os.getenv('CMC_API_KEYS', os.getenv('CMC_API_KEY', ''))
    cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
    
    if not cmc_keys:
        print("❌ هیچ کلید CMC یافت نشد")
        return
    
    # استفاده از اولین کلید برای تست
    api_key = cmc_keys[0]
    
    print(f"🔍 تست historical endpoint با کلید: {api_key[:8]}...")
    
    try:
        from datetime import datetime, timedelta
        
        # محاسبه بازه 7 روز گذشته برای تست
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/historical"
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': api_key,
        }
        params = {
            'id': '1',  # BTC
            'time_start': start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'time_end': end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'interval': 'daily',
            'convert': 'USD'
        }
        
        print(f"📅 بازه تست: {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status', {}).get('error_code') == 0:
                btc_data = data.get('data', {}).get('1', {})
                if btc_data and 'quotes' in btc_data:
                    quotes = btc_data['quotes']
                    print(f"   ✅ موفق - {len(quotes)} نقطه داده دریافت شد")
                    
                    # نمایش چند نقطه اول
                    for i, quote in enumerate(quotes[:3]):
                        timestamp = quote.get('timestamp', '')
                        price = quote.get('quote', {}).get('USD', {}).get('price', 0)
                        print(f"      {i+1}. {timestamp[:10]} - ${price:,.2f}")
                    
                    return True
                else:
                    print(f"   ❌ داده نامعتبر")
            else:
                error_msg = data.get('status', {}).get('error_message', 'Unknown')
                print(f"   ❌ خطای API: {error_msg}")
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            
            if response.status_code == 429:
                print(f"   🚫 Rate limit - باید صبر کنید")
            elif response.status_code == 401:
                print(f"   🔐 کلید نامعتبر")
                
    except Exception as e:
        print(f"   ❌ خطا: {str(e)}")
    
    return False

def main():
    print("🧪 تست‌گر کلیدهای CoinMarketCap")
    print("=" * 60)
    
    # تست کلیدهای اصلی
    working_keys = test_cmc_keys()
    
    # تست historical endpoint
    if working_keys:
        test_historical_endpoint()
    
    print(f"\n✅ تست تکمیل شد!")

if __name__ == "__main__":
    main()
