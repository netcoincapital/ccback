#!/usr/bin/env python3
"""
Direct test of EthereumService
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_direct_ethereum():
    try:
        from utils.blockchain_service_factory import BlockchainServiceFactory
        from database import SessionLocal, Address, Blockchains
        from security.encryption import decrypt_private_key_aes
        
        print("🔧 Direct EthereumService Test")
        print("==============================")
        
        # Get Ethereum service
        service = BlockchainServiceFactory.get_service('ethereum')
        if not service:
            print("❌ EthereumService not available")
            return
            
        print("✅ EthereumService created")
        
        # Test parameters
        sender = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        recipient = "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
        amount = "0.0001"
        
        print(f"Sender: {sender}")
        print(f"Recipient: {recipient}")
        print(f"Amount: {amount} ETH")
        print("")
        
        # Step 1: Test prepare_transaction
        print("1️⃣ Testing prepare_transaction...")
        try:
            tx_details, error = service.prepare_transaction(sender, recipient, amount, None)
            
            if error:
                print(f"❌ Prepare failed: {error}")
                return
            else:
                print("✅ Prepare successful")
                print(f"Transaction ID: {tx_details.get('transaction_id')}")
                transaction_id = tx_details.get('transaction_id')
                print("")
                
        except Exception as e:
            print(f"❌ Prepare exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return
            
        # Step 2: Get private key
        print("2️⃣ Getting private key...")
        session = SessionLocal()
        try:
            blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike('ethereum')
            ).first()
            
            address_record = session.query(Address).filter(
                Address.PublicAddress == sender,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            private_key = decrypt_private_key_aes(address_record.PrivateKey)
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
                
            print("✅ Private key retrieved")
            print(f"Private key format: {len(private_key)} characters, starts with 0x")
            print("")
            
        finally:
            session.close()
            
        # Step 3: Test send_transaction with detailed logging
        print("3️⃣ Testing send_transaction...")
        print("This will show detailed error messages...")
        print("")
        
        try:
            result, error = service.send_transaction(transaction_id, private_key)
            
            if error:
                print(f"❌ Send failed: {error}")
                print("This error came from EthereumService.send_transaction()")
            else:
                print("✅ Send successful!")
                print(f"Result: {result}")
                
        except Exception as e:
            print(f"❌ Send exception: {str(e)}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_ethereum()

