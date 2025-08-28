#!/usr/bin/env python3
"""
Test Polygon service directly with the latest changes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.blockchains.polygon_service import PolygonService
from services.shared_storage import shared_storage
import uuid

def test_polygon_service():
    print("🧪 Testing Polygon Service with Latest Changes")
    print("=" * 50)
    
    # Initialize service
    polygon_service = PolygonService()
    
    # Test addresses
    sender = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
    recipient = "0xF0F3d4dD1b8A86f4Fe65401524701915F00b4E3B"
    amount = "0.001"
    private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    try:
        # Step 1: Prepare transaction
        print("\n🔧 Step 1: Prepare Transaction")
        tx_details, error = polygon_service.prepare_transaction(sender, recipient, amount)
        
        if error:
            print(f"❌ Prepare failed: {error}")
            return
            
        print(f"✅ Prepare successful!")
        print(f"Transaction ID: {tx_details.get('transaction_id')}")
        
        transaction_id = tx_details.get('transaction_id')
        if not transaction_id:
            print("❌ No transaction ID received")
            return
            
        # Step 2: Send transaction
        print("\n📤 Step 2: Send Transaction")
        result, error = polygon_service.send_transaction(transaction_id, private_key)
        
        if error:
            print(f"❌ Send failed: {error}")
            # Check what happened in the logs
            print("\n🔍 Checking what methods were tried:")
            
        else:
            print(f"✅ Send successful!")
            print(f"Transaction Hash: {result.get('transaction_hash')}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_polygon_service() 