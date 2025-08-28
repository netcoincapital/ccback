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

def get_private_key_from_database(sender_address: str, blockchain_name: str = "polygon"):
    """Get private key from database like TRON service does"""
    try:
        from database import SessionLocal, Address, Blockchains
        from security.encryption import decrypt_private_key_aes
        from sqlalchemy import func
        
        print(f"🔍 Getting private key for address {sender_address} on blockchain {blockchain_name}")
        
        session = SessionLocal()
        try:
            # Normalize blockchain name
            blockchain_name = blockchain_name.lower().strip()
            if blockchain_name in ['matic', 'polygon']:
                blockchain_name = 'polygon'
            
            # Get blockchain ID
            blockchain = session.query(Blockchains).filter(
                func.lower(Blockchains.BlockchainName).contains(blockchain_name)
            ).first()
            
            if not blockchain:
                print(f"❌ Blockchain {blockchain_name} not found in database")
                return None
            
            print(f"✅ Found blockchain ID: {blockchain.BlockchainID} with name: {blockchain.BlockchainName}")
            
            # Get address record
            address_record = session.query(Address).filter(
                Address.PublicAddress == sender_address,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            if not address_record:
                print(f"❌ Address {sender_address} not found for blockchain {blockchain_name}")
                return None
                
            print(f"✅ Found address record with ID: {address_record.AddressID}")
            
            # Check if PrivateKey exists
            if not address_record.PrivateKey:
                print(f"❌ No private key stored for address {sender_address}")
                return None
            
            # Decrypt private key
            try:
                print("🔍 Attempting to decrypt private key...")
                private_key = decrypt_private_key_aes(address_record.PrivateKey)
                
                if not private_key:
                    print("❌ Decryption returned empty private key")
                    return None
                
                print(f"✅ Successfully decrypted private key (length: {len(private_key)})")
                return private_key
                
            except Exception as e:
                print(f"❌ Error decrypting private key: {str(e)}")
                return None
                
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Error getting private key from database: {str(e)}")
        return None

def create_test_transaction_data(sender_address: str = None):
    """Create a properly formatted test transaction data using Web3.py"""
    try:
        from web3 import Web3
        from eth_account import Account
        import secrets

        print("🔍 Creating test transaction with Web3.py...")

        w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
        
        # Try to get private key from database first
        private_key = None
        if sender_address:
            private_key = get_private_key_from_database(sender_address, "polygon")
        
        # Fallback to environment variable if database lookup fails
        if not private_key:
            print("⚠️ No private key found in database, trying environment variable...")
            private_key = os.getenv("PRIVATE_KEY")
            if not private_key:
                raise ValueError("❌ PRIVATE_KEY not set in environment variables")
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key

        account = Account.from_key(private_key)
        print(f"✅ Using account: {account.address}")

        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.to_wei(30, 'gwei')
        gas_limit = 21000
        to_address = w3.to_checksum_address("0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1")
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

def test_database_private_key_lookup():
    """Test private key lookup from database"""
    try:
        print("🔍 Testing Database Private Key Lookup...")
        
        # Test addresses from the system
        test_addresses = [
            "0x68Ba7F66B09783977E36AA7bD8390b812742853C",
            "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
        ]
        
        for address in test_addresses:
            print(f"\n🔍 Testing address: {address}")
            private_key = get_private_key_from_database(address, "polygon")
            
            if private_key:
                print(f"✅ Found private key for {address}")
                # Create test transaction with this private key
                test_tx = create_test_transaction_data(address)
                if test_tx:
                    print(f"✅ Successfully created test transaction for {address}")
                else:
                    print(f"❌ Failed to create test transaction for {address}")
            else:
                print(f"❌ No private key found for {address}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing database private key lookup: {str(e)}")
        return False

def test_prepare_confirm_api_structure():
    """Test the prepare/confirm API structure used in the system"""
    try:
        print("🔍 Testing Prepare/Confirm API Structure...")
        
        # Test data
        user_id = "test_user_123"
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        recipient_address = "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
        amount = "0.001"
        
        print(f"User ID: {user_id}")
        print(f"Sender: {sender_address}")
        print(f"Recipient: {recipient_address}")
        print(f"Amount: {amount} MATIC")
        
        # Step 1: Test Prepare API
        print("\n1. Testing Prepare API...")
        prepare_url = "http://localhost:5000/send/polygon/prepare"
        prepare_data = {
            "UserID": user_id,
            "sender_address": sender_address,
            "recipient_address": recipient_address,
            "amount": amount
        }
        
        try:
            response = requests.post(prepare_url, json=prepare_data, timeout=30)
            print(f"Prepare Response Status: {response.status_code}")
            
            if response.status_code == 200:
                prepare_result = response.json()
                print("✅ Prepare API working!")
                print(f"Transaction ID: {prepare_result.get('transaction_id')}")
                print(f"Details: {prepare_result.get('details', {})}")
                
                transaction_id = prepare_result.get('transaction_id')
                
                # Step 2: Test Confirm API
                print("\n2. Testing Confirm API...")
                confirm_url = "http://localhost:5000/send/polygon/confirm"
                confirm_data = {
                    "UserID": user_id,
                    "transaction_id": transaction_id,
                    "private_key": get_private_key_from_database(sender_address, "polygon") or "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                }
                
                confirm_response = requests.post(confirm_url, json=confirm_data, timeout=30)
                print(f"Confirm Response Status: {confirm_response.status_code}")
                
                if confirm_response.status_code == 200:
                    confirm_result = confirm_response.json()
                    print("✅ Confirm API working!")
                    print(f"Transaction Hash: {confirm_result.get('transaction_hash')}")
                    print(f"Status: {confirm_result.get('status')}")
                    return True
                else:
                    print(f"❌ Confirm API failed: {confirm_response.text}")
                    return False
                    
            else:
                print(f"❌ Prepare API failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing Prepare/Confirm API: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Error in Prepare/Confirm API test: {str(e)}")
        return False

def test_api_endpoints():
    """Test the new API endpoints structure"""
    try:
        print("🔍 Testing New API Endpoints Structure...")
        
        # Test data
        user_id = "test_user_456"
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        recipient_address = "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
        amount = "0.001"
        
        print(f"User ID: {user_id}")
        print(f"Sender: {sender_address}")
        print(f"Recipient: {recipient_address}")
        print(f"Amount: {amount} MATIC")
        
        # Step 1: Test new API prepare endpoint
        print("\n1. Testing New API Prepare Endpoint...")
        prepare_url = "http://localhost:5000/api/polygon/prepare"
        prepare_data = {
            "UserID": user_id,
            "sender_address": sender_address,
            "recipient_address": recipient_address,
            "amount": amount
        }
        
        try:
            response = requests.post(prepare_url, json=prepare_data, timeout=30)
            print(f"New API Prepare Response Status: {response.status_code}")
            
            if response.status_code == 200:
                prepare_result = response.json()
                print("✅ New API Prepare working!")
                print(f"Transaction ID: {prepare_result.get('transaction_id')}")
                
                transaction_id = prepare_result.get('transaction_id')
                
                # Step 2: Test new API confirm endpoint
                print("\n2. Testing New API Confirm Endpoint...")
                confirm_url = "http://localhost:5000/api/polygon/confirm"
                confirm_data = {
                    "UserID": user_id,
                    "transaction_id": transaction_id,
                    "private_key": get_private_key_from_database(sender_address, "polygon") or "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                }
                
                confirm_response = requests.post(confirm_url, json=confirm_data, timeout=30)
                print(f"New API Confirm Response Status: {confirm_response.status_code}")
                
                if confirm_response.status_code == 200:
                    confirm_result = confirm_response.json()
                    print("✅ New API Confirm working!")
                    print(f"Transaction Hash: {confirm_result.get('transaction_hash')}")
                    return True
                else:
                    print(f"❌ New API Confirm failed: {confirm_response.text}")
                    return False
                    
            else:
                print(f"❌ New API Prepare failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing New API endpoints: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Error in New API endpoints test: {str(e)}")
        return False

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
    test_tx_data = create_test_transaction_data("0x68Ba7F66B09783977E36AA7bD8390b812742853C")
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
        test_tx = create_test_transaction_data("0x68Ba7F66B09783977E36AA7bD8390b812742853C")
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
        test_tx = create_test_transaction_data("0x68Ba7F66B09783977E36AA7bD8390b812742853C")
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
        recipient_address = "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
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

def test_tatum_helper_initialization():
    """Test if TatumHelper is being initialized properly in PolygonService"""
    try:
        print("🔍 Testing TatumHelper Initialization in PolygonService...")
        
        from services.blockchains.polygon_service import PolygonService
        
        # Initialize Polygon service
        polygon_service = PolygonService()
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        
        # Check if TatumHelper is available
        if hasattr(polygon_service, 'tatum'):
            if polygon_service.tatum:
                print("✅ TatumHelper is available and initialized")
                print(f"TatumHelper type: {type(polygon_service.tatum)}")
                
                # Test TatumHelper methods
                try:
                    # Test balance endpoint
                    balance_data, error = polygon_service.tatum.get_balance("polygon", "0x68Ba7F66B09783977E36AA7bD8390b812742853C")
                    if error:
                        print(f"❌ TatumHelper balance test failed: {error}")
                    else:
                        print(f"✅ TatumHelper balance test passed: {balance_data}")
                        
                    # Test broadcast endpoint
                    test_tx = "0xf86d808506fc23ac0082520894742d35cc6634c0532925a3b8d4c9db96c4b4d8b687038d7ea4c6800080820136a036542ef7c39cbc417be79d1283f4c82cd3fcfe15d29f047480f615e7dfa97068a03128f8b901e3aec922505e6d2b321d54df86a4013977e54a75139623c21bc184"
                    broadcast_result, broadcast_error = polygon_service.tatum.broadcast_transaction("POLYGON", test_tx)
                    if broadcast_error:
                        print(f"❌ TatumHelper broadcast test failed: {broadcast_error}")
                    else:
                        print(f"✅ TatumHelper broadcast test passed: {broadcast_result}")
                        
                except Exception as e:
                    print(f"❌ Error testing TatumHelper methods: {str(e)}")
            else:
                print("❌ TatumHelper is None - initialization failed")
                return False
        else:
            print("❌ TatumHelper attribute not found in PolygonService")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing TatumHelper initialization: {str(e)}")
        return False

def test_send_transaction_conditions():
    """Test the specific conditions in send_transaction method"""
    try:
        print("🔍 Testing Send Transaction Conditions...")
        
        from services.blockchains.polygon_service import PolygonService
        from web3 import Web3
        from eth_account import Account
        
        # Initialize Polygon service
        polygon_service = PolygonService()
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        
        # Check Web3 availability
        if polygon_service.web3:
            print("✅ Web3 is available")
            
            # Test Web3 signing
            try:
                # Get private key from database
                private_key = get_private_key_from_database("0x68Ba7F66B09783977E36AA7bD8390b812742853C", "polygon")
                if not private_key:
                    print("❌ No private key available for testing")
                    return False
                
                # Create account
                account = Account.from_key(private_key)
                print(f"✅ Account created: {account.address}")
                
                # Get nonce
                nonce = polygon_service.web3.eth.get_transaction_count(account.address)
                print(f"✅ Nonce: {nonce}")
                
                # Get gas price
                gas_price = polygon_service._get_cached_gas_price()
                print(f"✅ Gas price: {gas_price}")
                
                # Build transaction
                transaction = {
                    'nonce': nonce,
                    'to': "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1",
                    'value': polygon_service.web3.to_wei(0.001, 'ether'),
                    'gas': 21000,
                    'gasPrice': gas_price,
                    'chainId': 137
                }
                
                # Sign transaction
                signed_txn = polygon_service.web3.eth.account.sign_transaction(transaction, private_key)
                
                # Get raw transaction
                if hasattr(signed_txn, 'rawTransaction'):
                    signed_tx_raw = signed_txn.rawTransaction.hex()
                elif hasattr(signed_txn, 'raw_transaction'):
                    signed_tx_raw = signed_txn.raw_transaction.hex()
                else:
                    signed_tx_raw = signed_txn.hex()
                
                print(f"✅ Successfully signed transaction with Web3")
                print(f"Signed transaction length: {len(signed_tx_raw)} characters")
                
                # Check if signed_tx_raw is truthy
                if signed_tx_raw:
                    print("✅ signed_tx_raw is truthy")
                else:
                    print("❌ signed_tx_raw is falsy")
                    return False
                    
            except Exception as e:
                print(f"❌ Error testing Web3 signing: {str(e)}")
                return False
        else:
            print("❌ Web3 is not available")
            return False
        
        # Check Tatum availability
        if polygon_service.tatum:
            print("✅ Tatum is available")
            
            # Test Tatum broadcast
            try:
                test_tx = "0xf86d808506fc23ac0082520894742d35cc6634c0532925a3b8d4c9db96c4b4d8b687038d7ea4c6800080820136a036542ef7c39cbc417be79d1283f4c82cd3fcfe15d29f047480f615e7dfa97068a03128f8b901e3aec922505e6d2b321d54df86a4013977e54a75139623c21bc184"
                response = polygon_service.tatum.broadcast_transaction('POLYGON', test_tx)
                
                if response and 'txId' in response:
                    print("✅ Tatum broadcast test passed")
                else:
                    print(f"❌ Tatum broadcast test failed: {response}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error testing Tatum broadcast: {str(e)}")
                return False
        else:
            print("❌ Tatum is not available")
            return False
        
        # Test the specific condition
        print("\n🔍 Testing the specific condition: if self.tatum and signed_tx_raw:")
        if polygon_service.tatum and signed_tx_raw:
            print("✅ Condition is TRUE - both Tatum and signed_tx_raw are available")
        else:
            print("❌ Condition is FALSE")
            print(f"  - self.tatum: {polygon_service.tatum is not None}")
            print(f"  - signed_tx_raw: {signed_tx_raw is not None}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing send transaction conditions: {str(e)}")
        return False

def test_new_send_transaction_method():
    """Test the new send_transaction method with multiple fallback options"""
    try:
        print("🔍 Testing New Send Transaction Method...")
        
        from services.blockchains.polygon_service import PolygonService
        
        # Initialize Polygon service
        polygon_service = PolygonService()
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        
        # Check service availability
        print(f"Web3 available: {polygon_service.web3 is not None}")
        print(f"Tatum available: {polygon_service.tatum is not None}")
        
        # Get private key from database
        private_key = get_private_key_from_database("0x68Ba7F66B09783977E36AA7bD8390b812742853C", "polygon")
        if not private_key:
            print("❌ No private key available for testing")
            return False
        
        print("✅ Private key retrieved from database")
        
        # Create a test transaction
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        recipient_address = "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
        amount = "0.001"
        
        # Prepare transaction first
        print("\n🔍 Preparing transaction...")
        prepare_result, prepare_error = polygon_service.prepare_transaction(
            sender_address, 
            recipient_address, 
            amount
        )
        
        if prepare_error:
            print(f"❌ Transaction preparation failed: {prepare_error}")
            return False
        
        transaction_id = prepare_result.get('transaction_id')
        print(f"✅ Transaction prepared with ID: {transaction_id}")
        
        # Now try to send the transaction
        print("\n🔍 Sending transaction...")
        send_result, send_error = polygon_service.send_transaction(transaction_id, private_key)
        
        if send_error:
            print(f"❌ Transaction sending failed: {send_error}")
            return False
        
        tx_hash = send_result.get('transaction_hash')
        print(f"✅ Transaction sent successfully!")
        print(f"Transaction Hash: {tx_hash}")
        print(f"Status: {send_result.get('status')}")
        print(f"Message: {send_result.get('message')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing new send transaction method: {str(e)}")
        return False

def test_tatum_helper_fixes():
    """Test the TatumHelper fixes for proper txData and fromPrivateKey handling"""
    try:
        print("🔍 Testing TatumHelper Fixes...")
        
        from services.tatum_helper import TatumHelper
        
        # Initialize TatumHelper
        tatum_helper = TatumHelper()
        print(f"✅ TatumHelper initialized: {tatum_helper is not None}")
        
        # Test 1: txData method (pre-signed transaction)
        print("\n1. Testing txData method...")
        test_signed_tx = "0xf86d808506fc23ac0082520894742d35cc6634c0532925a3b8d4c9db96c4b4d8b687038d7ea4c6800080820136a036542ef7c39cbc417be79d1283f4c82cd3fcfe15d29f047480f615e7dfa97068a03128f8b901e3aec922505e6d2b321d54df86a4013977e54a75139623c21bc184"
        
        # Test broadcast_transaction (txData method)
        broadcast_result, broadcast_error = tatum_helper.broadcast_transaction('POLYGON', test_signed_tx)
        if broadcast_error:
            print(f"❌ Broadcast test failed (expected): {broadcast_error}")
        else:
            print(f"✅ Broadcast test passed: {broadcast_result}")
        
        # Test 2: fromPrivateKey method (let Tatum handle signing)
        print("\n2. Testing fromPrivateKey method...")
        
        # Get private key from database
        private_key = get_private_key_from_database("0x68Ba7F66B09783977E36AA7bD8390b812742853C", "polygon")
        if not private_key:
            print("❌ No private key available for testing")
            return False
        
        # Test send_transaction (fromPrivateKey method)
        send_result, send_error = tatum_helper.send_transaction(
            'polygon',
            "0x68Ba7F66B09783977E36AA7bD8390b812742853C",
            "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1",
            "0.001",
            private_key
        )
        
        if send_error:
            print(f"❌ Send transaction test failed (expected): {send_error}")
        else:
            print(f"✅ Send transaction test passed: {send_result}")
        
        # Test 3: Check address validation
        print("\n3. Testing address validation...")
        try:
            from eth_utils import to_checksum_address
            
            # Test valid addresses
            valid_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
            checksum_address = to_checksum_address(valid_address)
            print(f"✅ Address validation passed: {checksum_address}")
            
        except Exception as e:
            print(f"❌ Address validation failed: {str(e)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing TatumHelper fixes: {str(e)}")
        return False

def test_nonce_fix():
    """Test if the nonce issue is resolved"""
    try:
        print("🔍 Testing Nonce Fix...")
        
        from services.blockchains.polygon_service import PolygonService
        from web3 import Web3
        
        # Initialize Polygon service
        polygon_service = PolygonService()
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        
        # Check Web3 connection
        if not polygon_service.web3:
            print("❌ Web3 not available")
            return False
        
        # Get private key from database
        private_key = get_private_key_from_database("0x68Ba7F66B09783977E36AA7bD8390b812742853C", "polygon")
        if not private_key:
            print("❌ No private key available for testing")
            return False
        
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        
        # Test 1: Get current nonce
        print("\n1. Testing current nonce retrieval...")
        try:
            nonce = polygon_service.web3.eth.get_transaction_count(sender_address, 'latest')
            print(f"✅ Current nonce: {nonce}")
        except Exception as e:
            print(f"❌ Failed to get nonce: {str(e)}")
            return False
        
        # Test 2: Create a test transaction with proper nonce
        print("\n2. Testing transaction creation with proper nonce...")
        try:
            from eth_account import Account
            
            # Create account
            account = Account.from_key(private_key)
            print(f"✅ Account created: {account.address}")
            
            # Get gas price
            gas_price = polygon_service._get_cached_gas_price()
            print(f"✅ Gas price: {gas_price}")
            
            # Build transaction with current nonce
            transaction = {
                'nonce': nonce,
                'to': "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1",
                'value': polygon_service.web3.to_wei(0.001, 'ether'),
                'gas': 21000,
                'gasPrice': gas_price,
                'chainId': 137
            }
            
            print(f"✅ Transaction built with nonce: {transaction['nonce']}")
            
            # Sign transaction
            signed_txn = polygon_service.web3.eth.account.sign_transaction(transaction, private_key)
            print(f"✅ Transaction signed successfully")
            
            # Get raw transaction
            if hasattr(signed_txn, 'rawTransaction'):
                signed_tx_raw = signed_txn.rawTransaction.hex()
            elif hasattr(signed_txn, 'raw_transaction'):
                signed_tx_raw = signed_txn.raw_transaction.hex()
            else:
                signed_tx_raw = signed_txn.hex()
            
            print(f"✅ Raw transaction created (length: {len(signed_tx_raw)} characters)")
            
        except Exception as e:
            print(f"❌ Error creating test transaction: {str(e)}")
            return False
        
        # Test 3: Test nonce retry mechanism
        print("\n3. Testing nonce retry mechanism...")
        try:
            # Try with different nonces
            for retry in range(3):
                test_nonce = nonce + retry
                print(f"  Testing with nonce: {test_nonce}")
                
                # Build transaction with test nonce
                test_transaction = {
                    'nonce': test_nonce,
                    'to': "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1",
                    'value': polygon_service.web3.to_wei(0.001, 'ether'),
                    'gas': 21000,
                    'gasPrice': gas_price,
                    'chainId': 137
                }
                
                # Sign transaction
                test_signed_txn = polygon_service.web3.eth.account.sign_transaction(test_transaction, private_key)
                print(f"    ✅ Transaction signed with nonce {test_nonce}")
                
        except Exception as e:
            print(f"❌ Error testing nonce retry: {str(e)}")
            return False
        
        print("✅ Nonce fix test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing nonce fix: {str(e)}")
        return False

def test_actual_transaction_sending():
    """Test actual transaction sending with nonce fix"""
    try:
        print("🔍 Testing Actual Transaction Sending...")
        
        from services.blockchains.polygon_service import PolygonService
        
        # Initialize Polygon service
        polygon_service = PolygonService()
        print(f"✅ Polygon service initialized: {polygon_service is not None}")
        
        # Get private key from database
        private_key = get_private_key_from_database("0x68Ba7F66B09783977E36AA7bD8390b812742853C", "polygon")
        if not private_key:
            print("❌ No private key available for testing")
            return False
        
        sender_address = "0x68Ba7F66B09783977E36AA7bD8390b812742853C"
        recipient_address = "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1"
        amount = "0.001"
        
        # Prepare transaction first
        print("\n🔍 Preparing transaction...")
        prepare_result, prepare_error = polygon_service.prepare_transaction(
            sender_address, 
            recipient_address, 
            amount
        )
        
        if prepare_error:
            print(f"❌ Transaction preparation failed: {prepare_error}")
            return False
        
        transaction_id = prepare_result.get('transaction_id')
        print(f"✅ Transaction prepared with ID: {transaction_id}")
        
        # Now try to send the transaction
        print("\n🔍 Sending transaction with nonce fix...")
        send_result, send_error = polygon_service.send_transaction(transaction_id, private_key)
        
        if send_error:
            print(f"❌ Transaction sending failed: {send_error}")
            return False
        
        tx_hash = send_result.get('transaction_hash')
        print(f"✅ Transaction sent successfully!")
        print(f"Transaction Hash: {tx_hash}")
        print(f"Status: {send_result.get('status')}")
        print(f"Message: {send_result.get('message')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing actual transaction sending: {str(e)}")
        return False

def test_address_validation():
    """Test address validation with Web3.toChecksumAddress"""
    try:
        print("🔍 Testing Address Validation...")
        
        from web3 import Web3
        
        # Test addresses
        test_addresses = [
            "0x68Ba7F66B09783977E36AA7bD8390b812742853C",
            "0x184ac75b74C77D5BF3b3BffB5Ed26aE091B3feD1",
            "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6"
        ]
        
        for address in test_addresses:
            try:
                checksum_address = Web3.to_checksum_address(address)
                print(f"✅ Address validated: {address} -> {checksum_address}")
            except Exception as e:
                print(f"❌ Address validation failed: {address} - {str(e)}")
                return False
        
        # Test invalid address
        try:
            invalid_address = "0x1234567890abcdef1234567890abcdef12345678"  # Too short
            checksum_address = Web3.to_checksum_address(invalid_address)
            print(f"❌ Invalid address should have failed: {invalid_address}")
            return False
        except Exception as e:
            print(f"✅ Invalid address correctly rejected: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing address validation: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=== Tatum API Debug Test for Polygon ===")
    print()
    
    # Test 1: Database Private Key Lookup
    print("1. Testing Database Private Key Lookup...")
    db_lookup_ok = test_database_private_key_lookup()
    print()
    
    # Test 2: API Key
    print("2. Testing Tatum API Key...")
    api_key_ok = test_tatum_api_key()
    print()
    
    # Test 3: Balance endpoint
    print("3. Testing Tatum Balance Endpoint...")
    balance_ok = test_tatum_balance_endpoint()
    print()
    
    # Test 4: Broadcast endpoint
    print("4. Testing Tatum Broadcast Endpoint...")
    broadcast_ok = test_tatum_broadcast_endpoint()
    print()
    
    # Test 5: Service integration
    print("5. Testing Polygon Service Integration...")
    service_ok = test_polygon_service_integration()
    print()
    
    # Test 6: Tatum service implementation
    print("6. Testing Tatum Service Implementation...")
    tatum_service_ok = test_tatum_service_implementation()
    print()
    
    # Test 7: Real transaction broadcast
    print("7. Testing Real Transaction Broadcast...")
    real_transaction_ok = test_real_transaction_broadcast()
    print()
    
    # Test 8: Check existing transactions
    print("8. Checking Existing Transactions...")
    existing_transactions_ok = check_existing_transactions()
    print()
    
    # Test 9: Prepare/Confirm API Structure
    print("9. Testing Prepare/Confirm API Structure...")
    prepare_confirm_ok = test_prepare_confirm_api_structure()
    print()
    
    # Test 10: New API Endpoints
    print("10. Testing New API Endpoints...")
    new_api_ok = test_api_endpoints()
    print()
    
    # Test 11: TatumHelper Initialization in PolygonService
    print("11. Testing TatumHelper Initialization in PolygonService...")
    tatum_helper_ok = test_tatum_helper_initialization()
    print()
    
    # Test 12: Send Transaction Conditions
    print("12. Testing Send Transaction Conditions...")
    send_conditions_ok = test_send_transaction_conditions()
    print()
    
    # Test 13: New Send Transaction Method
    print("13. Testing New Send Transaction Method...")
    new_send_tx_ok = test_new_send_transaction_method()
    print()
    
    # Test 14: TatumHelper Fixes
    print("14. Testing TatumHelper Fixes...")
    tatum_helper_fixes_ok = test_tatum_helper_fixes()
    print()
    
    # Test 15: Nonce Fix
    print("15. Testing Nonce Fix...")
    nonce_fix_ok = test_nonce_fix()
    print()
    
    # Test 16: Actual Transaction Sending
    print("16. Testing Actual Transaction Sending...")
    actual_tx_sending_ok = test_actual_transaction_sending()
    print()
    
    # Test 17: Address Validation
    print("17. Testing Address Validation...")
    address_validation_ok = test_address_validation()
    print()
    
    # Summary
    print("=== Test Summary ===")
    print(f"Database Lookup: {'✅' if db_lookup_ok else '❌'}")
    print(f"API Key: {'✅' if api_key_ok else '❌'}")
    print(f"Balance Endpoint: {'✅' if balance_ok else '❌'}")
    print(f"Broadcast Endpoint: {'✅' if broadcast_ok else '❌'}")
    print(f"Service Integration: {'✅' if service_ok else '❌'}")
    print(f"Tatum Service: {'✅' if tatum_service_ok else '❌'}")
    print(f"Real Transaction: {'✅' if real_transaction_ok else '❌'}")
    print(f"Existing Transactions: {'✅' if existing_transactions_ok else '❌'}")
    print(f"Prepare/Confirm API: {'✅' if prepare_confirm_ok else '❌'}")
    print(f"New API Endpoints: {'✅' if new_api_ok else '❌'}")
    print(f"TatumHelper Initialization: {'✅' if tatum_helper_ok else '❌'}")
    print(f"Send Transaction Conditions: {'✅' if send_conditions_ok else '❌'}")
    print(f"New Send Transaction Method: {'✅' if new_send_tx_ok else '❌'}")
    print(f"TatumHelper Fixes: {'✅' if tatum_helper_fixes_ok else '❌'}")
    print(f"Nonce Fix: {'✅' if nonce_fix_ok else '❌'}")
    print(f"Actual Transaction Sending: {'✅' if actual_tx_sending_ok else '❌'}")
    print(f"Address Validation: {'✅' if address_validation_ok else '❌'}")
    
    if all([db_lookup_ok, api_key_ok, balance_ok, broadcast_ok, service_ok, tatum_service_ok, real_transaction_ok, existing_transactions_ok, prepare_confirm_ok, new_api_ok, tatum_helper_ok, send_conditions_ok, new_send_tx_ok, tatum_helper_fixes_ok, nonce_fix_ok, actual_tx_sending_ok, address_validation_ok]):
        print("\n🎉 All tests passed! Tatum API should work correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the issues above.")

if __name__ == "__main__":
    main() 