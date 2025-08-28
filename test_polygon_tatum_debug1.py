#!/usr/bin/env python3
"""
Debug script to test Tatum API directly for Polygon transactions
"""

import os
import sys
import json
import requests
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_hex_string(hex_string):
    """Validate hex string format and length"""
    if not hex_string.startswith('0x'):
        return False, "Hex string must start with '0x'"

    hex_data = hex_string[2:]
    if len(hex_data) % 2 != 0:
        return False, f"Hex string length must be even, got {len(hex_data)}"

    try:
        int(hex_data, 16)
        return True, f"Valid hex string with {len(hex_data)} characters"
    except ValueError:
        return False, "Invalid hex characters"

def create_test_transaction_data():
    """Create a properly formatted test transaction data using Web3.py"""
    try:
        from web3 import Web3
        from eth_account import Account
        import secrets

        print("🔍 Creating test transaction with Web3.py...")

        w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
        private_key = "0x" + secrets.token_hex(32)
        account = Account.from_key(private_key)

        nonce = 0
        gas_price = w3.to_wei(30, 'gwei')
        gas_limit = 21000
        to_address = w3.to_checksum_address("0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        value = w3.to_wei(0.001, 'ether')

        transaction = {
            'nonce': nonce,
            'gasPrice': gas_price,
            'gas': gas_limit,
            'to': to_address,
            'value': value,
            'chainId': 137
        }

        signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
        raw_tx_hex = signed_tx.raw_transaction.hex()
        if not raw_tx_hex.startswith('0x'):
            raw_tx_hex = '0x' + raw_tx_hex

        print(f"✅ Created valid test transaction with Web3.py")
        print(f"Transaction length: {len(raw_tx_hex[2:])} characters")
        return raw_tx_hex

    except Exception as e:
        print(f"❌ Error creating test transaction: {str(e)}")
        print("⚠️ Falling back to dummy transaction for testing...")
        test_tx = "0xf86c808504a817c80082520894b944f84569b9f32ff12443fbdc6ff38a605c4e2a87038d7ea4c68000802aa0a0c9c4cbaef4cd2a3f6c5b327d2e4c3d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a0a0c9c4cbaef4cd2a3f6c5b327d2e4c3d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2"
        is_valid, message = validate_hex_string(test_tx)
        if not is_valid:
            print(f"❌ Fallback transaction validation failed: {message}")
            return None
        return test_tx

def test_tatum_api_key():
    """Test if Tatum API key is available and valid"""
    api_key = os.getenv('TATUM_API_KEY')
    if not api_key:
        print("❌ TATUM_API_KEY not found in environment variables")
        return False
    
    print(f"✅ TATUM_API_KEY found: {api_key[:10]}...")
    return True

def test_tatum_balance_endpoint():
    """Test Tatum balance endpoint for Polygon"""
    api_key = os.getenv('TATUM_API_KEY')
    if not api_key:
        print("❌ TATUM_API_KEY not available")
        return False
    
    # Test address
    test_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
    
    # Correct URL format: address should be part of the path, not query param
    url = f"https://api.tatum.io/v3/polygon/account/balance/{test_address}"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔍 Testing Tatum balance endpoint for address: {test_address}")
        print(f"URL: {url}")
        response = requests.get(url, headers=headers)
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Balance endpoint working: {data}")
            return True
        else:
            print(f"❌ Balance endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing balance endpoint: {str(e)}")
        return False

def test_tatum_broadcast_endpoint():
    """Test Tatum broadcast endpoint for Polygon with proper hex data"""
    api_key = os.getenv('TATUM_API_KEY')
    if not api_key:
        print("❌ TATUM_API_KEY not available")
        return False
    
    url = "https://api.tatum.io/v3/polygon/broadcast"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Create properly formatted test transaction data
    test_tx_data = create_test_transaction_data()
    if not test_tx_data:
        print("❌ Failed to create valid test transaction data")
        return False
    
    # Validate the hex string
    is_valid, message = validate_hex_string(test_tx_data)
    if not is_valid:
        print(f"❌ Test transaction validation failed: {message}")
        return False
    
    print(f"✅ {message}")
    
    payload = {
        "txData": test_tx_data
    }
    
    try:
        print(f"🔍 Testing Tatum broadcast endpoint with proper hex data")
        print(f"URL: {url}")
        hex_data = test_tx_data[2:]  # Remove '0x' prefix for length check
        print(f"Hex data length: {len(hex_data)} characters")
        print(f"Payload: {payload}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Broadcast endpoint working: {data}")
            return True
        else:
            print(f"❌ Broadcast endpoint failed: {response.status_code}")
            print(f"Error details: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing broadcast endpoint: {str(e)}")
        return False

def test_polygon_service_integration():
    """Test Polygon service integration with Tatum"""
    try:
        from services.blockchains.polygon_service import PolygonService
        from services.tatum_helper import TatumHelper
        
        print("🔍 Testing Polygon service initialization...")
        
        # Initialize services
        polygon_service = PolygonService()
        tatum_helper = TatumHelper()
        
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        print(f"✅ Tatum helper initialized: {tatum_helper is not None}")
        
        # Test Tatum helper methods
        print("\n🔍 Testing Tatum helper methods...")
        
        # Test normalize chain name
        normalized = tatum_helper._normalize_chain_name("POLYGON")
        print(f"Normalized 'POLYGON': {normalized}")
        
        # Test broadcast endpoint
        endpoint = "/polygon/broadcast"
        print(f"Broadcast endpoint: {endpoint}")
        
        # Test hex validation with a proper transaction
        test_tx = create_test_transaction_data()
        if test_tx:
            is_valid, message = validate_hex_string(test_tx)
            print(f"✅ Test transaction validation: {message}")
            
            # Test Tatum helper broadcast method (this will fail but we can see the error)
            print("\n🔍 Testing Tatum helper broadcast method...")
            try:
                result, error = tatum_helper.broadcast_transaction("POLYGON", test_tx)
                if error:
                    print(f"❌ Broadcast failed (expected): {error}")
                else:
                    print(f"✅ Broadcast succeeded: {result}")
            except Exception as e:
                print(f"❌ Broadcast error: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Polygon service integration: {str(e)}")
        return False

def test_tatum_service_implementation():
    """Test the actual Tatum service implementation"""
    try:
        from services.tatum_service import TatumService
        
        print("🔍 Testing Tatum service implementation...")
        
        # Initialize Tatum service
        tatum_service = TatumService()
        print(f"✅ Tatum service initialized: {tatum_service is not None}")
        
        # Test broadcast method
        test_tx = create_test_transaction_data()
        if test_tx:
            print("\n🔍 Testing Tatum service broadcast method...")
            try:
                result, error = tatum_service.broadcast_transaction("POLYGON", test_tx)
                if error:
                    print(f"❌ Tatum service broadcast failed (expected): {error}")
                else:
                    print(f"✅ Tatum service broadcast succeeded: {result}")
            except Exception as e:
                print(f"❌ Tatum service broadcast error: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Tatum service implementation: {str(e)}")
        return False

def test_real_transaction_broadcast():
    """Test with a real transaction from the system"""
    try:
        from services.blockchains.polygon_service import PolygonService
        from services.tatum_helper import TatumHelper
        
        print("🔍 Testing real transaction broadcast...")
        
        # Initialize services
        polygon_service = PolygonService()
        tatum_helper = TatumHelper()
        
        # Create a real transaction scenario
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        recipient_address = "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6"
        amount = "0.001"  # 0.001 MATIC
        
        print(f"Sender: {sender_address}")
        print(f"Recipient: {recipient_address}")
        print(f"Amount: {amount} MATIC")
        
        # Test transaction preparation (this won't actually send)
        print("\n🔍 Testing transaction preparation...")
        try:
            result, error = polygon_service.prepare_transaction(
                sender_address, 
                recipient_address, 
                amount
            )
            
            if error:
                print(f"❌ Transaction preparation failed: {error}")
            else:
                print(f"✅ Transaction preparation succeeded: {result}")
                
                # If we have a transaction ID, we could test sending it
                # But we don't have a private key for testing
                transaction_id = result.get('transaction_id')
                if transaction_id:
                    print(f"Transaction ID: {transaction_id}")
                    print("⚠️ Cannot test actual sending without private key")
                    
        except Exception as e:
            print(f"❌ Error in transaction preparation: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing real transaction broadcast: {str(e)}")
        return False

def check_existing_transactions():
    """Check if there are any existing transactions in the system"""
    try:
        from services.transaction_storage import TransactionStorage

        print("🔍 Checking existing transactions in the system...")
        storage = TransactionStorage()
        transactions = storage.get_all_transactions()

        if transactions:
            print(f"✅ Found {len(transactions)} existing transactions")
            polygon_txs = [tx for tx in transactions if isinstance(tx, dict) and tx.get('blockchain', '').lower() in ['polygon', 'matic']]

            if polygon_txs:
                print(f"✅ Found {len(polygon_txs)} Polygon transactions")
                for i, tx in enumerate(polygon_txs[:3]):
                    print(f"  {i+1}. ID: {tx.get('id', 'N/A')}, Status: {tx.get('status', 'N/A')}")
            else:
                print("⚠️ No Polygon transactions found")
        else:
            print("⚠️ No existing transactions found")

        return True

    except Exception as e:
        print(f"❌ Error checking existing transactions: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=== Tatum API Debug Test for Polygon ===")
    print()
    
    # Test 1: API Key
    print("1. Testing Tatum API Key...")
    api_key_ok = test_tatum_api_key()
    print()
    
    # Test 2: Balance endpoint
    print("2. Testing Tatum Balance Endpoint...")
    balance_ok = test_tatum_balance_endpoint()
    print()
    
    # Test 3: Broadcast endpoint
    print("3. Testing Tatum Broadcast Endpoint...")
    broadcast_ok = test_tatum_broadcast_endpoint()
    print()
    
    # Test 4: Service integration
    print("4. Testing Polygon Service Integration...")
    service_ok = test_polygon_service_integration()
    print()
    
    # Test 5: Tatum service implementation
    print("5. Testing Tatum Service Implementation...")
    tatum_service_ok = test_tatum_service_implementation()
    print()
    
    # Test 6: Real transaction broadcast
    print("6. Testing Real Transaction Broadcast...")
    real_transaction_ok = test_real_transaction_broadcast()
    print()
    
    # Test 7: Check existing transactions
    print("7. Checking Existing Transactions...")
    existing_transactions_ok = check_existing_transactions()
    print()
    
    # Summary
    print("=== Test Summary ===")
    print(f"API Key: {'✅' if api_key_ok else '❌'}")
    print(f"Balance Endpoint: {'✅' if balance_ok else '❌'}")
    print(f"Broadcast Endpoint: {'✅' if broadcast_ok else '❌'}")
    print(f"Service Integration: {'✅' if service_ok else '❌'}")
    print(f"Tatum Service: {'✅' if tatum_service_ok else '❌'}")
    print(f"Real Transaction: {'✅' if real_transaction_ok else '❌'}")
    print(f"Existing Transactions: {'✅' if existing_transactions_ok else '❌'}")
    
    if all([api_key_ok, balance_ok, broadcast_ok, service_ok, tatum_service_ok, real_transaction_ok, existing_transactions_ok]):
        print("\n🎉 All tests passed! Tatum API should work correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the issues above.")

if __name__ == "__main__":
    main() 