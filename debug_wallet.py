#!/usr/bin/env python3
"""
Debug script to check wallet and private key decryption
"""
import requests
import json

def debug_wallet():
    url = "https://coinceeper.com/api/send/debug-wallet"
    data = {
        "address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
        "blockchain": "ethereum"
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            debug_info = result.get('debug_info', {})
            
            print("\n=== ANALYSIS ===")
            print(f"Blockchain found: {debug_info.get('blockchain_found')}")
            print(f"Address found: {debug_info.get('address_found')}")
            print(f"Has private key: {debug_info.get('has_private_key')}")
            print(f"Private key decrypts: {debug_info.get('private_key_decrypts')}")
            
            if 'decryption_error' in debug_info:
                print(f"Decryption error: {debug_info['decryption_error']}")
                
        else:
            print("❌ Debug endpoint failed")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_wallet()
