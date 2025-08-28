#!/usr/bin/env python3
"""
Test script for Polygon API connectivity
"""

import os
import requests
from dotenv import load_dotenv

def test_polygon_api():
    """Test PolygonScan API connectivity"""
    print("🔍 Testing PolygonScan API connectivity...")
    print("="*50)
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('POLYGONSCAN_API_KEY', '')
    
    if not api_key:
        print("❌ No POLYGONSCAN_API_KEY found in .env file")
        print("💡 Please create .env file with your API key:")
        print("   POLYGONSCAN_API_KEY=your_api_key_here")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    # Test API connectivity
    try:
        print("\n🌐 Testing API connection...")
        
        # Test 1: Get latest block number
        response = requests.get(
            "https://api.polygonscan.com/api",
            params={
                'module': 'proxy',
                'action': 'eth_blockNumber',
                'apikey': api_key
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                latest_block = int(data['result'], 16)
                print(f"✅ Latest block: {latest_block:,}")
                
                # Test 2: Get account balance
                print("\n💰 Testing account balance check...")
                balance_response = requests.get(
                    "https://api.polygonscan.com/api",
                    params={
                        'module': 'account',
                        'action': 'balance',
                        'address': '0x0000000000000000000000000000000000000000',
                        'tag': 'latest',
                        'apikey': api_key
                    },
                    timeout=10
                )
                
                if balance_response.status_code == 200:
                    balance_data = balance_response.json()
                    if balance_data.get('status') == '1':
                        print("✅ Account balance API working")
                        
                        print("\n🎉 All tests passed!")
                        print("🚀 Ready to run polygon_transaction_finder.py")
                        return True
                    else:
                        print(f"❌ Balance API error: {balance_data}")
                        return False
                else:
                    print(f"❌ Balance API HTTP error: {balance_response.status_code}")
                    return False
            else:
                print(f"❌ API response error: {data}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def show_next_steps():
    """Show next steps for user"""
    print("\n" + "="*50)
    print("📋 Next Steps:")
    print("1. Make sure your .env file has the correct API key")
    print("2. Run: python polygon_transaction_finder.py")
    print("3. The script will find transactions with total fees = $52")
    print("\n📚 For detailed setup guide, see: SETUP_POLYGON_API.md")

if __name__ == "__main__":
    success = test_polygon_api()
    if success:
        print("\n✅ API test successful!")
    else:
        print("\n❌ API test failed!")
        print("\n💡 Troubleshooting:")
        print("- Check your API key in .env file")
        print("- Make sure you have internet connection")
        print("- Verify API key is valid on polygonscan.com")
    
    show_next_steps()
