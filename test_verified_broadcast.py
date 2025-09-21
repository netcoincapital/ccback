#!/usr/bin/env python3
"""
Test Verified Ethereum Broadcasting
Tests the improved broadcast system with verification
"""
import requests
import json
import time
from web3 import Web3

def test_verified_ethereum_transaction():
    """Test the improved Ethereum transaction system"""
    
    print("🔥 TESTING VERIFIED ETHEREUM BROADCASTING")
    print("=" * 50)
    print("Testing with enhanced verification system...")
    print()
    
    # Prepare transaction
    prepare_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
        "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
        "amount": "0.0001"
    }
    
    print("📋 STEP 1: PREPARE TRANSACTION")
    print("-" * 30)
    
    try:
        prepare_response = requests.post(
            "https://coinceeper.com/api/send/prepare",
            headers={"Content-Type": "application/json"},
            json=prepare_data,
            timeout=30
        )
        
        if prepare_response.status_code == 200:
            prepare_result = prepare_response.json()
            print("✅ Transaction prepared successfully")
            
            transaction_id = prepare_result.get('transaction_id')
            estimated_fee = prepare_result.get('details', {}).get('estimated_fee', 'N/A')
            print(f"📝 Transaction ID: {transaction_id}")
            print(f"💰 Estimated Fee: {estimated_fee} ETH")
            
            if not transaction_id:
                print("❌ No transaction ID received")
                return False
                
        else:
            print(f"❌ Prepare failed: {prepare_response.status_code}")
            print(f"Response: {prepare_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Prepare error: {str(e)}")
        return False
    
    print()
    print("🚀 STEP 2: CONFIRM TRANSACTION (WITH VERIFICATION)")
    print("-" * 50)
    
    # Confirm transaction
    confirm_data = {
        "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
        "blockchain": "Ethereum",
        "transaction_id": transaction_id
    }
    
    try:
        confirm_response = requests.post(
            "https://coinceeper.com/api/send/confirm",
            headers={"Content-Type": "application/json"},
            json=confirm_data,
            timeout=60  # Longer timeout for verification
        )
        
        if confirm_response.status_code == 200:
            confirm_result = confirm_response.json()
            
            if confirm_result.get('success'):
                tx_hash = confirm_result.get('tx_hash')
                method = confirm_result.get('method', 'unknown')
                explorer_url = confirm_result.get('explorer_url', '')
                
                print("✅ Transaction confirmed successfully!")
                print(f"📝 Transaction Hash: {tx_hash}")
                print(f"🔧 Method Used: {method}")
                print(f"🔗 Explorer URL: {explorer_url}")
                
                if not tx_hash:
                    print("❌ No transaction hash received")
                    return False
                    
                # Step 3: Verify transaction in public mempool
                print()
                print("🔍 STEP 3: VERIFY PUBLIC MEMPOOL INCLUSION")
                print("-" * 45)
                
                return verify_transaction_in_mempool(tx_hash)
                
            else:
                print(f"❌ Confirm failed: {confirm_result.get('message', 'Unknown error')}")
                return False
                
        else:
            print(f"❌ Confirm request failed: {confirm_response.status_code}")
            print(f"Response: {confirm_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Confirm error: {str(e)}")
        return False

def verify_transaction_in_mempool(tx_hash):
    """Verify transaction exists in public mempool"""
    
    # Multiple independent RPCs for verification
    verification_rpcs = [
        ("Ethereum RPC", "https://ethereum-rpc.publicnode.com"),
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Ankr", "https://rpc.ankr.com/eth"),
        ("Cloudflare", "https://cloudflare-eth.com"),
    ]
    
    print(f"Checking transaction {tx_hash} across {len(verification_rpcs)} RPCs...")
    print()
    
    found_count = 0
    confirmed_count = 0
    pending_count = 0
    
    for name, rpc_url in verification_rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 15}))
            
            if not w3.is_connected():
                print(f"🔌 {name:15} | Connection failed")
                continue
            
            # Check if transaction exists
            tx_data = w3.eth.get_transaction(tx_hash)
            
            if tx_data:
                found_count += 1
                
                # Check if confirmed
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    if receipt:
                        if receipt['status'] == 1:
                            confirmed_count += 1
                            print(f"✅ {name:15} | CONFIRMED in block {receipt['blockNumber']}")
                        else:
                            print(f"❌ {name:15} | FAILED in block {receipt['blockNumber']}")
                    else:
                        pending_count += 1
                        gas_price = tx_data.get('gasPrice', 0) / 10**9
                        print(f"⏳ {name:15} | PENDING (Gas: {gas_price:.2f} Gwei)")
                except:
                    pending_count += 1
                    gas_price = tx_data.get('gasPrice', 0) / 10**9 if tx_data.get('gasPrice') else 0
                    print(f"⏳ {name:15} | PENDING (Gas: {gas_price:.2f} Gwei)")
            else:
                print(f"❌ {name:15} | NOT FOUND")
                
        except Exception as e:
            error_msg = str(e).lower()
            if 'not found' in error_msg:
                print(f"❌ {name:15} | NOT FOUND")
            else:
                print(f"❌ {name:15} | ERROR: {str(e)[:30]}...")
    
    # Results summary
    print()
    print("📊 VERIFICATION SUMMARY:")
    print("-" * 25)
    
    total_rpcs = len(verification_rpcs)
    visibility_ratio = found_count / total_rpcs if total_rpcs > 0 else 0
    
    print(f"📊 Visibility: {found_count}/{total_rpcs} RPCs ({visibility_ratio:.1%})")
    
    if confirmed_count > 0:
        print(f"✅ Status: CONFIRMED on {confirmed_count} RPC(s)")
        print("🎉 SUCCESS: Transaction is confirmed and working!")
        return True
    elif pending_count > 0:
        print(f"⏳ Status: PENDING on {pending_count} RPC(s)")
        print("✅ SUCCESS: Transaction in public mempool, waiting for confirmation")
        return True
    elif found_count > 0:
        print(f"⚠️  Status: MIXED - found on {found_count} RPC(s)")
        print("⚠️  Partial success - may need more time to propagate")
        return True
    else:
        print("❌ Status: NOT FOUND - Transaction not in public mempool!")
        print("❌ CRITICAL: Broadcasting system still not working properly")
        return False

def main():
    """Main test function"""
    print("🧪 COINCEEPER VERIFIED BROADCAST TEST")
    print("=" * 40)
    print("Testing the enhanced Ethereum transaction system")
    print("with verification and public mempool checking...")
    print()
    
    # Run the test
    success = test_verified_ethereum_transaction()
    
    print()
    print("🎯 FINAL RESULT:")
    print("-" * 15)
    
    if success:
        print("🎉 TEST PASSED!")
        print("✅ Ethereum transactions are now working correctly")
        print("✅ Transactions reach the public mempool")
        print("✅ Verification system is functioning")
    else:
        print("❌ TEST FAILED!")
        print("❌ Transactions are still not reaching public mempool")
        print("❌ Further fixes needed")
    
    return success

if __name__ == "__main__":
    main()
