#!/usr/bin/env python3
"""
Test transaction signing directly
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_transaction_signing():
    try:
        from web3 import Web3
        from database import SessionLocal, Address, Blockchains
        from security.encryption import decrypt_private_key_aes
        
        print("🔐 Testing Transaction Signing")
        print("==============================")
        
        # Setup
        w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
        sender = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        recipient = "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
        amount_eth = 0.0001  # Very small amount for testing
        
        print(f"Sender: {sender}")
        print(f"Recipient: {recipient}")
        print(f"Amount: {amount_eth} ETH")
        print("")
        
        # Get private key from database
        session = SessionLocal()
        try:
            blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainName.ilike('ethereum')
            ).first()
            
            address_record = session.query(Address).filter(
                Address.PublicAddress == sender,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            if not address_record or not address_record.PrivateKey:
                print("❌ Private key not found")
                return
                
            private_key = decrypt_private_key_aes(address_record.PrivateKey)
            if not private_key:
                print("❌ Private key decryption failed")
                return
                
            print("✅ Private key retrieved and decrypted")
            
            # Ensure private key has 0x prefix
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
                
            print(f"Private key format: starts with 0x, length: {len(private_key)}")
            
        finally:
            session.close()
            
        # Get transaction parameters
        try:
            sender_checksum = w3.to_checksum_address(sender)
            recipient_checksum = w3.to_checksum_address(recipient)
            nonce = w3.eth.get_transaction_count(sender_checksum)
            gas_price = w3.eth.gas_price
            balance_wei = w3.eth.get_balance(sender_checksum)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            
            print(f"Sender (checksum): {sender_checksum}")
            print(f"Recipient (checksum): {recipient_checksum}")
            print(f"Nonce: {nonce}")
            print(f"Gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")
            print(f"Balance: {balance_eth} ETH")
            print("")
            
        except Exception as e:
            print(f"❌ Error getting transaction parameters: {str(e)}")
            return
            
        # Build transaction
        try:
            transaction = {
                'from': sender_checksum,
                'to': recipient_checksum,
                'value': w3.to_wei(amount_eth, 'ether'),
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': w3.eth.chain_id
            }
            
            print("Transaction built:")
            for key, value in transaction.items():
                if key == 'chainId':
                    print(f"  {key}: {value}")
                elif key in ['value', 'gasPrice']:
                    print(f"  {key}: {value} wei")
                else:
                    print(f"  {key}: {value}")
            print("")
            
        except Exception as e:
            print(f"❌ Error building transaction: {str(e)}")
            return
            
        # Test signing
        try:
            print("🖋️ Testing transaction signing...")
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            print("✅ Transaction signed successfully")
            print(f"Raw transaction length: {len(signed_txn.rawTransaction)} bytes")
            print(f"Transaction hash: {signed_txn.hash.hex()}")
            print("")
            
        except Exception as e:
            print(f"❌ Transaction signing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return
            
        # Test broadcasting (dry run - don't actually send)
        print("📡 Testing transaction broadcasting (DRY RUN)...")
        try:
            # Just validate the transaction without sending
            w3.eth.call(transaction)
            print("✅ Transaction validation successful")
            
            # Calculate total cost
            total_cost = w3.from_wei(transaction['value'] + (transaction['gas'] * transaction['gasPrice']), 'ether')
            print(f"Total cost: {total_cost} ETH")
            print(f"Sufficient balance: {float(balance_eth) >= float(total_cost)}")
            
            if float(balance_eth) >= float(total_cost):
                print("✅ All checks passed - transaction should work!")
                print("")
                print("🚨 ACTUAL BROADCAST TEST (REAL TRANSACTION):")
                print("Do you want to send this test transaction? (y/N)")
                # Don't actually send - just show it would work
                print("Skipping actual broadcast for safety")
            else:
                shortage = float(total_cost) - float(balance_eth)
                print(f"❌ Insufficient balance - shortage: {shortage} ETH")
                
        except Exception as e:
            print(f"❌ Transaction validation failed: {str(e)}")
            
            # Check specific error types
            error_str = str(e).lower()
            if 'insufficient funds' in error_str:
                print("   → Cause: Insufficient balance")
            elif 'nonce too low' in error_str:
                print("   → Cause: Nonce issue")
            elif 'gas price too low' in error_str:
                print("   → Cause: Gas price too low")
            else:
                print(f"   → Cause: {str(e)}")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_transaction_signing()
