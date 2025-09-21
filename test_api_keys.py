#!/usr/bin/env python3
"""
تست کلیدهای API برای تشخیص مشکل
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_cmc_keys():
    """تست کلیدهای CMC"""
    print("🔍 Testing CMC API Keys")
    print("="*50)
    
    # خواندن کلیدها از .env
    cmc_keys_str = os.getenv('CMC_API_KEYS', '')
    print(f"Raw CMC_API_KEYS from env: {cmc_keys_str}")
    
    if not cmc_keys_str:
        print("❌ CMC_API_KEYS not found in environment")
        return
    
    # تقسیم کلیدها
    cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
    print(f"📊 Found {len(cmc_keys)} keys:")
    
    for i, key in enumerate(cmc_keys, 1):
        print(f"   Key {i}: {key[:8]}...{key[-4:]}")
    
    # تست هر کلید
    for i, api_key in enumerate(cmc_keys, 1):
        print(f"\n🔑 Testing Key {i}: {api_key[:8]}...")
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json'
        }
        params = {
            'start': '1',
            'limit': '1',
            'convert': 'USD'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status', {}).get('error_code') == 0:
                    print(f"   ✅ Key {i} is VALID")
                    # نمایش اطلاعات credit
                    credit_count = data.get('status', {}).get('credit_count', 0)
                    print(f"   📊 Credit used: {credit_count}")
                else:
                    error_msg = data.get('status', {}).get('error_message', 'Unknown error')
                    print(f"   ❌ Key {i} API Error: {error_msg}")
            elif response.status_code == 401:
                print(f"   ❌ Key {i} is INVALID (401 Unauthorized)")
            elif response.status_code == 429:
                print(f"   ⚠️ Key {i} Rate Limited (429)")
            elif response.status_code == 403:
                print(f"   ❌ Key {i} Forbidden (403)")
            else:
                print(f"   ❌ Key {i} HTTP Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Key {i} Connection Error: {str(e)}")

def test_historical_endpoint():
    """تست endpoint تاریخی"""
    print(f"\n🔍 Testing Historical Endpoint")
    print("="*50)
    
    cmc_keys_str = os.getenv('CMC_API_KEYS', '')
    cmc_keys = [key.strip() for key in cmc_keys_str.split(',') if key.strip()]
    
    if not cmc_keys:
        print("❌ No CMC keys found")
        return
    
    # استفاده از اولین کلید معتبر
    for api_key in cmc_keys:
        print(f"🔑 Testing historical endpoint with key: {api_key[:8]}...")
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/historical"
        headers = {
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json'
        }
        params = {
            'id': '1',  # Bitcoin
            'time_start': '2025-09-14T00:00:00.000Z',
            'time_end': '2025-09-15T00:00:00.000Z',
            'interval': 'daily',
            'convert': 'USD'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status', {}).get('error_code') == 0:
                    print("   ✅ Historical endpoint works!")
                    quotes_count = len(data.get('data', {}).get('1', {}).get('quotes', []))
                    print(f"   📊 Retrieved {quotes_count} historical quotes")
                    return True
                else:
                    error_msg = data.get('status', {}).get('error_message', 'Unknown error')
                    print(f"   ❌ Historical API Error: {error_msg}")
            elif response.status_code == 401:
                print(f"   ❌ Historical endpoint - Invalid key (401)")
            elif response.status_code == 402:
                print(f"   💰 Historical endpoint - Payment Required (402) - Need paid plan")
            elif response.status_code == 429:
                print(f"   ⚠️ Historical endpoint - Rate Limited (429)")
            else:
                print(f"   ❌ Historical endpoint HTTP Error: {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                
        except Exception as e:
            print(f"   ❌ Historical endpoint Connection Error: {str(e)}")
    
    return False

if __name__ == "__main__":
    print("🧪 API Keys Test")
    print("="*50)
    
    test_cmc_keys()
    test_historical_endpoint()
    
    print(f"\n📋 Summary:")
    print("- If keys show as INVALID (401), they are wrong or expired")
    print("- If historical endpoint shows 402, you need CMC Pro plan")
    print("- If you see rate limits (429), wait and try again")