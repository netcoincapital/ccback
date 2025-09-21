#!/usr/bin/env python3
"""
Test mempool visibility for recent transaction
"""
import requests
import json

# Test the recent transaction
tx_hash = "0x4eccdee5a7c79bb6ffc543abbe367744b9228557876304be75d0ecc1af342272"

print(f"🔍 Testing Mempool Visibility for: {tx_hash}")
print("=" * 60)

# Test different RPC endpoints manually
rpcs = [
    "https://1rpc.io/eth",
    "https://eth-mainnet.public.blastapi.io", 
    "https://eth.llamarpc.com",
    "https://rpc.payload.de",
    "https://ethereum.blockpi.network/v1/rpc/public"
]

from web3 import Web3

visible_count = 0
total_count = len(rpcs)

for i, rpc in enumerate(rpcs, 1):
    print(f"\n{i}. Testing {rpc.split('/')[-1]}...")
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
        
        if not w3.is_connected():
            print("   ❌ Connection failed")
            continue
            
        tx_data = w3.eth.get_transaction(tx_hash)
        if tx_data:
            block_number = tx_data.get('blockNumber')
            if block_number:
                print(f"   ✅ CONFIRMED in block {block_number}")
            else:
                print("   ⏳ PENDING in mempool")
            visible_count += 1
        else:
            print("   ❌ NOT FOUND")
            
    except Exception as e:
        error_msg = str(e).lower()
        if 'not found' in error_msg:
            print("   ❌ NOT FOUND")
        else:
            print(f"   ⚠️ Error: {str(e)[:50]}")

print(f"\n" + "=" * 60)
print(f"📊 Visibility Summary:")
print(f"   Visible: {visible_count}/{total_count} RPCs ({visible_count/total_count:.1%})")

if visible_count == 0:
    print("   🚨 Transaction NOT visible in public mempool!")
    print("   💡 This confirms it's a private submission issue")
elif visible_count < total_count // 2:
    print("   ⚠️ Limited visibility - partially private")
else:
    print("   ✅ Good visibility in public mempool")

print(f"\n🔗 Etherscan: https://etherscan.io/tx/{tx_hash}")

