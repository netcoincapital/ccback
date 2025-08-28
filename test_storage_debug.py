#!/usr/bin/env python3
"""
Simple storage debug test
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.shared_storage import shared_storage

def test_storage():
    print("=== Storage Debug Test ===")
    
    # Test 1: Check storage info
    print("\n1. Storage info:")
    info = shared_storage.get_storage_info()
    print(f"Storage info: {info}")
    
    # Test 2: Store a test transaction
    print("\n2. Storing test transaction...")
    test_tx_id = "test_123"
    test_tx_data = {
        "transaction_id": test_tx_id,
        "details": {
            "amount": "1.0",
            "blockchain": "polygon",
            "sender": "0x123",
            "recipient": "0x456"
        },
        "success": True
    }
    
    try:
        result = shared_storage.store_transaction(test_tx_id, test_tx_data, 30)
        print(f"✅ Stored: {result}")
    except Exception as e:
        print(f"❌ Failed to store: {e}")
        return
    
    # Test 3: Retrieve the transaction
    print("\n3. Retrieving test transaction...")
    retrieved = shared_storage.get_transaction(test_tx_id)
    if retrieved:
        print(f"✅ Retrieved: {retrieved}")
    else:
        print(f"❌ Failed to retrieve")
    
    # Test 4: Get all transactions
    print("\n4. All transactions:")
    all_txs = shared_storage.get_all_transactions()
    print(f"All transactions: {list(all_txs.keys())}")
    
    # Test 5: Clean up
    print("\n5. Cleaning up...")
    shared_storage.delete_transaction(test_tx_id)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_storage() 