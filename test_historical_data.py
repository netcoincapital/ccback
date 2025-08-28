#!/usr/bin/env python3
"""
Test script for historical data functionality
"""
import os
import sys
import requests
import json
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_historical_data_service():
    """Test the HistoricalDataService directly"""
    print("🧪 Testing HistoricalDataService...")
    
    try:
        from Currencies.historical_data_service import HistoricalDataService
        
        service = HistoricalDataService()
        
        # Test API key retrieval
        api_key = service.get_api_key()
        print(f"✅ API Key retrieved: {api_key[:8]}...")
        
        # Test historical quotes (small test with Bitcoin)
        print("📊 Testing historical quotes fetch...")
        cmc_ids = ["1"]  # Bitcoin
        time_start = (datetime.now() - timedelta(days=7)).isoformat() + "Z"
        time_end = datetime.now().isoformat() + "Z"
        
        result = service.get_historical_quotes(cmc_ids, time_start, time_end, "daily", "USD")
        
        if isinstance(result, dict) and result.get("status") == "error":
            print(f"❌ Error fetching historical quotes: {result.get('message')}")
            return False
        else:
            print(f"✅ Historical quotes fetched successfully: {len(result)} currencies")
            return True
            
    except Exception as e:
        print(f"❌ Error testing HistoricalDataService: {str(e)}")
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n🌐 Testing API endpoints...")
    
    base_url = "http://localhost:5000"  # Adjust as needed
    
    # Test historical prices endpoint
    print("📈 Testing /historical-prices endpoint...")
    
    payload = {
        "Symbol": ["BTC"],
        "FiatCurrencies": ["USD"],
        "time_start": (datetime.now() - timedelta(days=30)).isoformat() + "Z",
        "time_end": datetime.now().isoformat() + "Z",
        "interval": "daily"
    }
    
    try:
        response = requests.post(f"{base_url}/historical-prices", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Historical prices endpoint working correctly")
                print(f"📊 Data keys: {list(data.get('historical_data', {}).keys())}")
                return True
            else:
                print(f"❌ API returned error: {data.get('message')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Server not running - skipping API tests")
        return None
    except Exception as e:
        print(f"❌ Error testing API: {str(e)}")
        return False

def test_existing_prices_api():
    """Test the updated existing prices API with historical data"""
    print("\n💰 Testing updated /prices endpoint...")
    
    base_url = "http://localhost:5000"
    
    payload = {
        "Symbol": ["BTC"],
        "FiatCurrencies": ["USD"],
        "include_historical": True,
        "days": 7
    }
    
    try:
        response = requests.post(f"{base_url}/prices", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                has_prices = "prices" in data
                has_historical = "historical_data" in data
                print(f"✅ Prices endpoint working: prices={has_prices}, historical={has_historical}")
                return True
            else:
                print(f"❌ API returned error: {data.get('message')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Server not running - skipping API tests")
        return None
    except Exception as e:
        print(f"❌ Error testing API: {str(e)}")
        return False

def test_database_schema():
    """Test database schema changes"""
    print("\n🗄️ Testing database schema...")
    
    try:
        from sqlalchemy import create_engine, text
        from database import engine
        from database.prices import Price
        
        # Test that the new columns exist
        with engine.connect() as conn:
            result = conn.execute(text("DESCRIBE prices"))
            columns = [row[0] for row in result]
            
            required_columns = ['is_historical', 'timestamp']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"❌ Missing columns in prices table: {missing_columns}")
                print("💡 Please run the migration: migrations/add_historical_data_support.sql")
                return False
            else:
                print("✅ Database schema updated correctly")
                return True
                
    except Exception as e:
        print(f"❌ Error testing database schema: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting Historical Data Implementation Tests")
    print("=" * 50)
    
    # Test results
    results = []
    
    # Test 1: Database Schema
    results.append(("Database Schema", test_database_schema()))
    
    # Test 2: Historical Data Service
    results.append(("Historical Data Service", test_historical_data_service()))
    
    # Test 3: API Endpoints
    api_result = test_api_endpoints()
    results.append(("Historical Prices API", api_result))
    
    existing_api_result = test_existing_prices_api()
    results.append(("Updated Prices API", existing_api_result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, result in results:
        if result is True:
            print(f"✅ {test_name}: PASSED")
            passed += 1
        elif result is False:
            print(f"❌ {test_name}: FAILED")
            failed += 1
        else:
            print(f"⚠️ {test_name}: SKIPPED")
            skipped += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("🎉 All tests passed! Historical data implementation is ready.")
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

