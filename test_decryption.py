#!/usr/bin/env python3
"""
Test private key decryption directly
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_decryption():
    try:
        from database import SessionLocal, Address, Blockchains
        from security.encryption import decrypt_private_key_aes
        from utils.blockchain_service_factory import BlockchainServiceFactory
        
        print("🔍 Testing private key decryption...")
        
        # Test address
        test_address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        
        session = SessionLocal()
        try:
            # Find blockchain
            blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike('ethereum')
            ).first()
            
            if not blockchain:
                print("❌ Ethereum blockchain not found in database")
                return
                
            print(f"✅ Found blockchain: {blockchain.BlockchainName} (ID: {blockchain.BlockchainID})")
            
            # Find address
            address_record = session.query(Address).filter(
                Address.PublicAddress == test_address,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            if not address_record:
                print(f"❌ Address {test_address} not found in database")
                return
                
            print(f"✅ Found address record (ID: {address_record.AddressID})")
            
            # Check if private key exists
            if not address_record.PrivateKey:
                print("❌ No private key stored for this address")
                return
                
            print("✅ Private key exists in database")
            
            # Test decryption
            try:
                decrypted_key = decrypt_private_key_aes(address_record.PrivateKey)
                if decrypted_key:
                    print(f"✅ Private key decrypted successfully (length: {len(decrypted_key)})")
                    
                    # Test if it looks like a valid Ethereum private key
                    if decrypted_key.startswith('0x') and len(decrypted_key) == 66:
                        print("✅ Private key format looks correct (0x + 64 hex chars)")
                    elif len(decrypted_key) == 64:
                        print("✅ Private key format looks correct (64 hex chars, missing 0x)")
                    else:
                        print(f"⚠️ Private key format unusual: length={len(decrypted_key)}, starts_with_0x={decrypted_key.startswith('0x')}")
                        
                else:
                    print("❌ Decryption returned empty result")
                    
            except Exception as decrypt_error:
                print(f"❌ Decryption failed: {str(decrypt_error)}")
                import traceback
                traceback.print_exc()
                
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_decryption()
