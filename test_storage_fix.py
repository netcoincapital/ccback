#!/usr/bin/env python3
"""
Test script to verify the storage fix works
"""

import sys
import os
import requests
import json
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.abspath('.'))

def test_storage_fix():
    """Test that prepare and confirm now use the same storage"""
    
    test_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
        "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
        "amount": "0.002",
        "smart_contract_address": ""
    }
    
    print("🔧 Testing Storage Fix")
    print("=" * 40)
    
    # Step 1: Test prepare
    print("\n1️⃣ Testing PREPARE...")
    try:
        response = requests.post(
            "https://coinceeper.com/api/send/prepare",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ PREPARE SUCCESS")
            print(f"Transaction ID: {result.get('transaction_id')}")
            transaction_id = result.get('transaction_id')
            
            if not transaction_id:
                print("❌ No transaction_id returned!")
                return
        else:
            print(f"❌ PREPARE FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            return
            
    except Exception as e:
        print(f"❌ PREPARE ERROR: {e}")
        return
    
    # Step 2: Test confirm immediately (should work now)
    print(f"\n2️⃣ Testing CONFIRM...")
    confirm_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "transaction_id": transaction_id,
        "private_key": "test_private_key"  # Will fail but should find the transaction
    }
    
    try:
        response = requests.post(
            "https://coinceeper.com/api/send/confirm",
            json=confirm_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"text": response.text}
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if "not found or expired" in str(result):
            print("❌ STORAGE ISSUE STILL EXISTS!")
        elif "private key" in str(result).lower() or "credentials" in str(result).lower():
            print("✅ STORAGE ISSUE FIXED! Transaction found, failing on private key (as expected)")
        else:
            print("⚠️ Unexpected response - needs investigation")
            
    except Exception as e:
        print(f"❌ CONFIRM ERROR: {e}")

if __name__ == "__main__":
    test_storage_fix()
