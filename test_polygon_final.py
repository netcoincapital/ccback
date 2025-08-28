#!/usr/bin/env python3
"""
Final Polygon API test with proper logging
"""

import requests
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.shared_storage import shared_storage

def test_polygon_final():
    """Final test for Polygon API"""
    
    print("=== Final Polygon API Test ===")
    
    # Test data
    sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
    recipient_address = "0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A"
    amount = "0.001"
    user_id = "final_test_user"
    
    print(f"Sender: {sender_address}")
    print(f"Recipient: {recipient_address}")
    print(f"Amount: {amount} MATIC")
    print(f"User ID: {user_id}")
    
    # Step 1: Check storage before prepare
    print("\n1. Checking storage before prepare...")
    storage_info = shared_storage.get_storage_info()
    print(f"Storage info: {storage_info}")
    
    # Step 2: Prepare transaction
    print("\n2. Preparing Polygon transaction...")
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
            
            # Step 3: Check storage immediately after prepare
            print(f"\n3. Checking storage immediately after prepare...")
            storage_info_after = shared_storage.get_storage_info()
            print(f"Storage info after: {storage_info_after}")
            
            # Step 4: Try to retrieve the transaction
            print(f"\n4. Trying to retrieve transaction {transaction_id}...")
            stored_tx = shared_storage.get_transaction(transaction_id)
            if stored_tx:
                print(f"✅ Transaction found in storage: {stored_tx.get('transaction_id')}")
            else:
                print(f"❌ Transaction {transaction_id} not found in storage")
                
                # Check all transactions
                all_txs = shared_storage.get_all_transactions()
                print(f"All transactions in storage: {list(all_txs.keys())}")
                
                if all_txs:
                    first_key = list(all_txs.keys())[0]
                    first_tx = all_txs[first_key]
                    print(f"First transaction in storage: {first_tx.get('transaction_id')}")
            
            # Step 5: Try confirm
            print(f"\n5. Trying to confirm transaction {transaction_id}...")
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
    test_polygon_final() 