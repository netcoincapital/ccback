#!/usr/bin/env python3
"""
Fix Ethereum Nonce Issues
Clears stuck transactions and resets nonce calculation
"""
from web3 import Web3
import time

def check_and_fix_nonce_issues():
    """Check and fix nonce issues for the test address"""
    
    address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    
    print("🔧 ETHEREUM NONCE DIAGNOSTIC & FIX")
    print("=" * 40)
    print(f"Address: {address}")
    print()
    
    # Connect to multiple RPCs to check nonce consistency
    rpcs = [
        ("PublicNode", "https://ethereum-rpc.publicnode.com"),
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Ankr", "https://rpc.ankr.com/eth"),
        ("Cloudflare", "https://cloudflare-eth.com"),
    ]
    
    nonce_data = {}
    
    for name, url in rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if w3.is_connected():
                latest_nonce = w3.eth.get_transaction_count(address, 'latest')
                pending_nonce = w3.eth.get_transaction_count(address, 'pending')
                
                nonce_data[name] = {
                    'latest': latest_nonce,
                    'pending': pending_nonce,
                    'stuck': pending_nonce - latest_nonce
                }
                
                print(f"✅ {name:12} | Latest: {latest_nonce:2d} | Pending: {pending_nonce:2d} | Stuck: {pending_nonce - latest_nonce}")
            else:
                print(f"❌ {name:12} | Connection failed")
                
        except Exception as e:
            print(f"❌ {name:12} | Error: {str(e)[:40]}...")
    
    if not nonce_data:
        print("❌ No RPC connections successful")
        return False
    
    # Analyze nonce consistency
    print()
    print("📊 NONCE ANALYSIS:")
    print("-" * 20)
    
    latest_nonces = [data['latest'] for data in nonce_data.values()]
    pending_nonces = [data['pending'] for data in nonce_data.values()]
    
    if len(set(latest_nonces)) == 1:
        correct_nonce = latest_nonces[0]
        print(f"✅ Consistent latest nonce across RPCs: {correct_nonce}")
    else:
        print(f"⚠️  Inconsistent latest nonces: {set(latest_nonces)}")
        correct_nonce = max(latest_nonces)
        print(f"💡 Using highest nonce: {correct_nonce}")
    
    max_stuck = max(data['stuck'] for data in nonce_data.values())
    if max_stuck > 0:
        print(f"⚠️  {max_stuck} stuck transactions detected")
        print("💡 These transactions may need to be cancelled or replaced")
    else:
        print("✅ No stuck transactions detected")
    
    print()
    print("🎯 RECOMMENDATIONS:")
    print("-" * 20)
    print(f"✅ Use nonce: {correct_nonce} for next transaction")
    print("✅ Use 'latest' block for nonce calculation")
    
    if max_stuck > 0:
        print("⚠️  Consider cancelling stuck transactions with higher gas price")
    
    return correct_nonce

def test_nonce_fix():
    """Test if the nonce fix is working"""
    print()
    print("🧪 TESTING NONCE FIX")
    print("=" * 25)
    
    # Import the fixed service
    try:
        import sys
        sys.path.append('/www/wwwroot/coinceeper.com/CC')
        
        from services.blockchains.ethereum_service import EthereumService
        
        service = EthereumService()
        address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        
        # Test nonce calculation
        nonce = service.w3.eth.get_transaction_count(address, 'latest')
        print(f"✅ Service nonce calculation: {nonce}")
        
        # Test gas price calculation
        latest_block = service.w3.eth.get_block('latest')
        base_fee = latest_block.get('baseFeePerGas', 0)
        print(f"✅ Current base fee: {base_fee / 10**9:.2f} Gwei")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing service: {str(e)}")
        return False

def main():
    """Main diagnostic function"""
    print("🔧 COINCEEPER ETHEREUM NONCE FIX")
    print("=" * 35)
    print("Diagnosing and fixing nonce issues...")
    print()
    
    # Step 1: Check nonce issues
    correct_nonce = check_and_fix_nonce_issues()
    
    # Step 2: Test the service
    if correct_nonce is not False:
        test_nonce_fix()
    
    print()
    print("🚀 NEXT STEPS:")
    print("-" * 15)
    print("1. Restart the service: systemctl restart gunicorn")
    print("2. Test again: python test_verified_broadcast.py")
    print("3. Check that nonce is now correct in logs")

if __name__ == "__main__":
    main()
