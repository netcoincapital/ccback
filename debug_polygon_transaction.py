#!/usr/bin/env python3
"""
Debug script for Polygon transaction issues
"""

import os
import sys
from decimal import Decimal
import json
from eth_account import Account
import requests

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.blockchains.polygon_service import PolygonService
from utils.logging_config import get_logger

# Set up environment
os.environ['POLYGON_NODE_URL'] = 'https://polygon-rpc.com'

def debug_polygon_transaction():
    """Debug Polygon transaction issues"""
    
    logger = get_logger(__file__)
    logger.info("🔍 Starting Polygon transaction debugging")
    
    # Test data from your frontend logs
    test_private_key = 'b7b9c47587f84c99d92d7f3207db9fa8a1c6689e7aa783d461c025bf216270d7'
    test_amount = '0.01'
    
    print("=" * 60)
    print("🔍 POLYGON TRANSACTION DEBUG")
    print("=" * 60)
    
    # 1. Check private key validity and get corresponding address
    try:
        account = Account.from_key(test_private_key)
        derived_address = account.address
        print(f"✅ Private key is valid")
        print(f"🔑 Private key: {test_private_key[:10]}...")
        print(f"📍 Corresponding address: {derived_address}")
    except Exception as e:
        print(f"❌ Invalid private key: {e}")
        return False
    
    print("\n" + "-" * 40)
    
    # 2. Check balance for the derived address
    service = PolygonService()
    balance, balance_error = service.get_balance(derived_address)
    
    if balance_error:
        print(f"❌ Error getting balance: {balance_error}")
        return False
    
    print(f"💰 Balance for {derived_address}: {balance} MATIC")
    
    # 3. Check fee estimation
    fee, fee_error = service.estimate_fee(derived_address, derived_address, test_amount)
    
    if fee_error:
        print(f"❌ Error estimating fee: {fee_error}")
    else:
        print(f"⛽ Estimated fee: {fee} MATIC")
        
        # 4. Calculate requirements
        amount = Decimal(test_amount)
        total_required = amount + fee
        
        print(f"📊 Transaction Analysis:")
        print(f"   Amount to send: {amount} MATIC")
        print(f"   Fee required: {fee} MATIC")
        print(f"   Total required: {total_required} MATIC")
        print(f"   Available balance: {balance} MATIC")
        print(f"   Sufficient funds: {'✅ YES' if balance >= total_required else '❌ NO'}")
        
        if balance < total_required:
            shortage = total_required - balance
            print(f"   Shortage: {shortage} MATIC")
    
    print("\n" + "-" * 40)
    
    # 5. Test prepare transaction
    print("🔄 Testing transaction preparation...")
    
    try:
        tx_details, prepare_error = service.prepare_transaction(
            derived_address,  # sender
            derived_address,  # recipient (self-transfer for testing)
            test_amount
        )
        
        if prepare_error:
            print(f"❌ Prepare transaction failed: {prepare_error}")
            return False
        else:
            print(f"✅ Transaction prepared successfully")
            print(f"   Transaction ID: {tx_details.get('transaction_id')}")
            return tx_details.get('transaction_id')
            
    except Exception as e:
        print(f"❌ Exception during prepare: {e}")
        return False

def test_tatum_direct():
    """Test Tatum API directly"""
    
    print("\n" + "=" * 60)
    print("🌐 TESTING TATUM API DIRECTLY")
    print("=" * 60)
    
    test_private_key = 'b7b9c47587f84c99d92d7f3207db9fa8a1c6689e7aa783d461c025bf216270d7'
    
    # Get address from private key
    account = Account.from_key(test_private_key)
    address = account.address
    
    print(f"📍 Testing with address: {address}")
    
    # Test Tatum balance endpoint
    try:
        tatum_api_key = os.getenv('TATUM_API_KEY', 'your_tatum_api_key_here')
        
        balance_url = f"https://api.tatum.io/v3/polygon/account/balance/{address}"
        headers = {
            'x-api-key': tatum_api_key,
            'Content-Type': 'application/json'
        }
        
        print(f"🔗 Calling Tatum balance API: {balance_url}")
        
        response = requests.get(balance_url, headers=headers)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            balance_data = response.json()
            print(f"✅ Tatum balance: {balance_data}")
        else:
            print(f"❌ Tatum balance error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error calling Tatum API: {e}")

def main():
    """Main debugging function"""
    
    print("\n🚀 Starting comprehensive Polygon debugging...\n")
    
    # Run debug tests
    transaction_id = debug_polygon_transaction()
    
    # Test Tatum directly
    test_tatum_direct()
    
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS")
    print("=" * 60)
    
    print("""
1. ✅ Check if the private key in your frontend corresponds to the sender address
   
2. 🔄 If using test data, make sure the test address has sufficient MATIC for:
   - The amount you want to send (0.01 MATIC)
   - Gas fees (~0.0005-0.001 MATIC)
   
3. 🔑 For production, use the actual user's private key, not the hardcoded test key
   
4. 🌐 Verify your Tatum API key is valid and has sufficient credits
   
5. 📱 In your Flutter app, ensure you're getting the correct private key:
   ```dart
   String? privateKey = await SecureStorage.instance.getPrivateKeyForSelectedWallet();
   ```
   
6. 🔍 Add debugging to verify address derivation in your app:
   ```dart
   // Derive address from private key and compare with expected sender
   final account = EthereumAccount.fromPrivateKey(privateKey);
   print('Derived address: ${account.address}');
   print('Expected sender: $senderAddress');
   ```
    """)

if __name__ == "__main__":
    main() 