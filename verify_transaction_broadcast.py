#!/usr/bin/env python3
"""
Transaction Broadcast Verification Tool
Verifies that Ethereum transactions are properly broadcast to public mempool
"""
from web3 import Web3
import time
import concurrent.futures

def verify_transaction_in_public_mempool(tx_hash, timeout=30):
    """Verify transaction exists in public mempool across multiple RPCs"""
    
    # List of reliable public RPCs for verification
    verification_rpcs = [
        ("PublicNode", "https://ethereum-rpc.publicnode.com"),
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Ankr", "https://rpc.ankr.com/eth"),
        ("Cloudflare", "https://cloudflare-eth.com"),
        ("Alchemy", "https://eth-mainnet.g.alchemy.com/v2/demo"),
    ]
    
    print(f"🔍 VERIFYING TRANSACTION: {tx_hash}")
    print("=" * 60)
    print(f"Checking across {len(verification_rpcs)} public RPCs...")
    print()
    
    def check_tx_on_rpc(name, url):
        """Check if transaction exists on specific RPC"""
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if not w3.is_connected():
                return name, {'status': 'connection_failed', 'error': 'Cannot connect'}
            
            # Check if transaction exists
            tx_data = w3.eth.get_transaction(tx_hash)
            if tx_data:
                # Check if confirmed or pending
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    status = 'confirmed' if receipt['status'] == 1 else 'failed'
                    block_number = receipt['blockNumber']
                except:
                    status = 'pending'
                    block_number = None
                
                return name, {
                    'status': status,
                    'block': block_number,
                    'gas_price': tx_data.get('gasPrice', 0) / 10**9 if tx_data.get('gasPrice') else 0,
                    'nonce': tx_data.get('nonce'),
                    'value': w3.from_wei(tx_data.get('value', 0), 'ether'),
                    'found': True
                }
            else:
                return name, {'status': 'not_found', 'found': False}
                
        except Exception as e:
            error_msg = str(e).lower()
            if 'not found' in error_msg or 'null' in error_msg:
                return name, {'status': 'not_found', 'found': False}
            else:
                return name, {'status': 'error', 'error': str(e)[:50], 'found': False}
    
    # Check all RPCs in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(check_tx_on_rpc, name, url) for name, url in verification_rpcs]
        
        for future in concurrent.futures.as_completed(futures, timeout=timeout):
            try:
                name, result = future.result()
                results[name] = result
            except Exception as e:
                print(f"❌ Error checking RPC: {str(e)}")
    
    # Analyze results
    print("📊 VERIFICATION RESULTS:")
    print("-" * 30)
    
    found_count = 0
    confirmed_count = 0
    pending_count = 0
    
    for name, result in results.items():
        if result.get('found'):
            found_count += 1
            status = result['status']
            
            if status == 'confirmed':
                confirmed_count += 1
                print(f"✅ {name:12} | CONFIRMED in block {result.get('block', 'N/A')}")
            elif status == 'pending':
                pending_count += 1
                gas_price = result.get('gas_price', 0)
                print(f"⏳ {name:12} | PENDING (Gas: {gas_price:.2f} Gwei)")
            elif status == 'failed':
                print(f"❌ {name:12} | FAILED in block {result.get('block', 'N/A')}")
            else:
                print(f"⚠️  {name:12} | {status.upper()}")
        else:
            status = result.get('status', 'unknown')
            if status == 'not_found':
                print(f"❌ {name:12} | NOT FOUND")
            elif status == 'connection_failed':
                print(f"🔌 {name:12} | CONNECTION FAILED")
            else:
                error = result.get('error', 'Unknown error')
                print(f"❌ {name:12} | ERROR: {error}")
    
    # Summary
    total_rpcs = len(results)
    visibility_ratio = found_count / total_rpcs if total_rpcs > 0 else 0
    
    print()
    print("🎯 SUMMARY:")
    print("-" * 15)
    print(f"📊 Visibility: {found_count}/{total_rpcs} RPCs ({visibility_ratio:.1%})")
    
    if confirmed_count > 0:
        print(f"✅ Status: CONFIRMED on {confirmed_count} RPC(s)")
        return 'confirmed'
    elif pending_count > 0:
        print(f"⏳ Status: PENDING on {pending_count} RPC(s)")
        return 'pending'
    elif found_count > 0:
        print(f"⚠️  Status: MIXED RESULTS")
        return 'mixed'
    else:
        print(f"❌ Status: NOT FOUND - Transaction not in public mempool!")
        return 'not_found'

def main():
    """Main verification function"""
    print("🔍 ETHEREUM TRANSACTION VERIFICATION TOOL")
    print("=" * 45)
    
    # Get transaction hash from user or use the one from recent test
    tx_hash = input("Enter transaction hash to verify (or press Enter for recent): ").strip()
    
    if not tx_hash:
        # Use the transaction hash from the recent test
        tx_hash = "0x02c3f9cb338c07329f4ad3c9304f03eef1e90d380753897b0730c387da48a2b6"
        print(f"Using recent transaction: {tx_hash}")
    
    print()
    
    # Verify the transaction
    result = verify_transaction_in_public_mempool(tx_hash)
    
    print()
    print("🎯 RECOMMENDATIONS:")
    print("-" * 20)
    
    if result == 'confirmed':
        print("✅ Transaction is confirmed and working properly!")
        print("✅ Your Ethereum broadcast system is functioning correctly.")
    elif result == 'pending':
        print("⏳ Transaction is pending - this is normal for recent transactions.")
        print("✅ Your broadcast system successfully reached the public mempool.")
        print("💡 Wait a few minutes for confirmation.")
    elif result == 'mixed':
        print("⚠️  Mixed results - some RPCs see it, others don't.")
        print("💡 This may indicate network propagation delays.")
        print("💡 Wait a few minutes and check again.")
    else:
        print("❌ CRITICAL: Transaction not found in public mempool!")
        print("❌ This indicates your RPC is not broadcasting properly.")
        print()
        print("🛠️  FIXES NEEDED:")
        print("1. Use different RPC endpoints")
        print("2. Verify gas prices are competitive")
        print("3. Check if RPC supports public broadcasting")
        print("4. Consider using premium RPC services (Alchemy, Infura)")
    
    print(f"\n🔗 Check on Etherscan: https://etherscan.io/tx/{tx_hash}")

if __name__ == "__main__":
    main()
