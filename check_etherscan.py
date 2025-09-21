#!/usr/bin/env python3
"""
Check transactions via Etherscan API
"""
import requests
import json

def check_etherscan():
    print("🔍 Checking via Etherscan API")
    print("==============================")
    
    address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    
    # Get recent transactions
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc&apikey=YourApiKeyToken"
    
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if data.get('status') == '1' and data.get('result'):
            transactions = data['result']
            print(f"✅ Found {len(transactions)} recent transactions:")
            
            for i, tx in enumerate(transactions[:5]):  # Show last 5
                print(f"\n{i+1}. Transaction:")
                print(f"   Hash: {tx['hash']}")
                print(f"   Block: {tx['blockNumber']}")
                print(f"   From: {tx['from']}")
                print(f"   To: {tx['to']}")
                print(f"   Value: {int(tx['value']) / 1e18} ETH")
                print(f"   Gas Used: {tx['gasUsed']}")
                print(f"   Status: {'Success' if tx['isError'] == '0' else 'Failed'}")
                print(f"   Timestamp: {tx['timeStamp']}")
                
                # Check if transaction failed
                if tx['isError'] != '0':
                    print(f"   ❌ Transaction failed!")
                    
        else:
            print("❌ No transactions found or API error")
            print(f"Response: {data}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_etherscan()
