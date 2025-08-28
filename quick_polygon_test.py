#!/usr/bin/env python3
"""
Quick test for Polygon API endpoint
"""

import requests
import json

def test_polygon_api():
    """Test Polygon API endpoint"""
    
    print("=== Quick Polygon API Test ===")
    
    # Test data with valid checksummed addresses
    sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
    recipient_address = "0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A"  # Fixed checksum
    amount = "0.001"
    user_id = "quick_test_user"
    
    print(f"Sender: {sender_address}")
    print(f"Recipient: {recipient_address}")
    print(f"Amount: {amount} MATIC")
    print(f"User ID: {user_id}")
    
    # Prepare transaction
    print("\n1. Preparing Polygon transaction...")
    prepare_url = "http://localhost:5000/send/polygon/prepare"
    prepare_data = {
        "blockchain": "polygon",
        "sender_address": sender_address,
        "recipient_address": recipient_address,
        "amount": amount,
        "UserID": user_id
    }
    
    try:
        response = requests.post(prepare_url, json=prepare_data, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            prepare_result = response.json()
            print("✅ Prepare successful!")
            print(f"Transaction ID: {prepare_result.get('transaction_id')}")
            
            transaction_id = prepare_result.get('transaction_id')
            
            # Wait a moment
            print("\n2. Waiting 1 second...")
            import time
            time.sleep(1)
            
            # Try confirm
            print(f"\n3. Trying to confirm transaction {transaction_id}...")
            confirm_url = "http://localhost:5000/send/polygon/confirm"
            confirm_data = {
                "transaction_id": transaction_id,
                "UserID": user_id,
                "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            }
            
            confirm_response = requests.post(confirm_url, json=confirm_data, timeout=30)
            print(f"Confirm response status: {confirm_response.status_code}")
            
            if confirm_response.status_code == 200:
                confirm_result = confirm_response.json()
                print("✅ Confirm successful!")
                print(f"Transaction Hash: {confirm_result.get('transaction_hash')}")
            else:
                print(f"❌ Confirm failed: {confirm_response.text}")
                
        else:
            print(f"❌ Prepare failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error in API test: {e}")

if __name__ == "__main__":
    test_polygon_api() 