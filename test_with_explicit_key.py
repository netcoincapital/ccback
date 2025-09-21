#!/usr/bin/env python3
"""
Test with explicit private key to bypass database
"""
import requests
import json

def test_with_explicit_key():
    print("🔑 Testing with Explicit Private Key")
    print("====================================")
    
    # First prepare
    prepare_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
        "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
        "amount": "0.0001",
        "smart_contract_address": ""
    }
    
    print("1️⃣ PREPARE...")
    response = requests.post(
        "https://coinceeper.com/api/send/prepare",
        json=prepare_data,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ PREPARE failed: {response.status_code}")
        return
        
    result = response.json()
    if not result.get('success'):
        print(f"❌ PREPARE failed: {result.get('message')}")
        return
        
    transaction_id = result.get('transaction_id')
    print(f"✅ PREPARE success: {transaction_id}")
    
    # Get the private key we know works from previous test
    # In real scenario, you'd get this from a secure source
    test_private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    print("\n2️⃣ CONFIRM with explicit private key...")
    confirm_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "transaction_id": transaction_id,
        "private_key": test_private_key
    }
    
    response = requests.post(
        "https://coinceeper.com/api/send/confirm",
        json=confirm_data,
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    
    if result.get('success'):
        print("✅ SUCCESS! Transaction sent with explicit private key!")
    else:
        error_msg = result.get('message', '')
        if 'private key' in error_msg.lower():
            print("❌ Private key issue - expected since we used a dummy key")
        elif 'database' in error_msg.lower() or 'connection' in error_msg.lower():
            print("❌ Still database connection issue")
        else:
            print(f"❌ Other issue: {error_msg}")

if __name__ == "__main__":
    test_with_explicit_key()

