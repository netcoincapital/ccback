#!/usr/bin/env python3
"""
Simple test to check why transactions remain private
"""
import requests
import json
import time

def test_transaction_broadcast():
    print("🧪 Simple Transaction Broadcast Test")
    print("=" * 40)
    
    # Step 1: Prepare transaction
    print("1️⃣ Preparing transaction...")
    prepare_data = {
        'sender': '0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956',
        'recipient': '0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9', 
        'amount': '0.0001',
        'blockchain': 'ethereum'
    }
    
    try:
        prep_response = requests.post(
            'https://coinceeper.com/api/send/prepare',
            json=prepare_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if prep_response.status_code != 200:
            print(f"❌ Prepare failed: {prep_response.status_code}")
            return
            
        prep_result = prep_response.json()
        if not prep_result.get('success'):
            print(f"❌ Prepare failed: {prep_result.get('message')}")
            return
            
        transaction_id = prep_result['transaction_id']
        estimated_fee = prep_result['details']['estimated_fee']
        
        print(f"✅ Transaction prepared!")
        print(f"   ID: {transaction_id}")
        print(f"   Fee: {estimated_fee} ETH")
        
        # Step 2: Test RPC broadcast capability
        print("\n2️⃣ Testing RPC broadcast capability...")
        try:
            rpc_response = requests.get(
                'https://coinceeper.com/api/send/test-broadcast-capability',
                timeout=30
            )
            
            if rpc_response.status_code == 200:
                rpc_result = rpc_response.json()
                print("📡 RPC Test Results:")
                for rpc, result in rpc_result.get('test_results', {}).items():
                    print(f"   {rpc}: {result}")
            else:
                print(f"⚠️ RPC test unavailable: {rpc_response.status_code}")
        except:
            print("⚠️ RPC test endpoint not available")
        
        # Step 3: Confirm transaction
        print("\n3️⃣ Confirming transaction...")
        confirm_data = {
            'UserID': 'test-debug-user',
            'blockchain': 'ethereum',
            'transaction_id': transaction_id
        }
        
        confirm_response = requests.post(
            'https://coinceeper.com/api/send/confirm',
            json=confirm_data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        print(f"📤 Confirm Response: {confirm_response.status_code}")
        
        if confirm_response.status_code == 200:
            confirm_result = confirm_response.json()
            if confirm_result.get('success'):
                tx_hash = confirm_result.get('tx_hash')
                print(f"✅ Transaction sent!")
                print(f"   Hash: {tx_hash}")
                
                # Step 4: Check mempool visibility immediately
                print("\n4️⃣ Checking mempool visibility...")
                check_mempool_visibility_api(tx_hash)
                
                # Step 5: Check transaction status
                print("\n5️⃣ Checking transaction status...")
                check_transaction_status(tx_hash)
                
                # Step 6: Wait and check again
                print("\n⏳ Waiting 30 seconds and checking again...")
                time.sleep(30)
                check_mempool_visibility_api(tx_hash)
                check_transaction_status(tx_hash)
                
            else:
                print(f"❌ Transaction failed: {confirm_result.get('message')}")
        else:
            print(f"❌ Confirm failed: {confirm_response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def check_transaction_status(tx_hash):
    """Check transaction status on Etherscan"""
    if not tx_hash:
        print("   ⚠️ No transaction hash to check")
        return
        
    print(f"   🔍 Checking {tx_hash}...")
    
    # Check via Etherscan API
    try:
        etherscan_url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}"
        response = requests.get(etherscan_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('result') and data['result'] != '0x':
                tx_data = data['result']
                block_number = tx_data.get('blockNumber')
                gas_price = int(tx_data.get('gasPrice', '0'), 16) / 10**9
                
                if block_number and block_number != '0x':
                    print(f"   ✅ CONFIRMED in block {int(block_number, 16)}")
                else:
                    print(f"   ⏳ PENDING in mempool")
                    
                print(f"   ⛽ Gas Price: {gas_price:.2f} Gwei")
                print(f"   🌐 Etherscan: https://etherscan.io/tx/{tx_hash}")
            else:
                print(f"   ❌ NOT FOUND in public mempool")
                print(f"   🔗 Check: https://etherscan.io/tx/{tx_hash}")
        else:
            print(f"   ⚠️ Etherscan API error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")

def check_mempool_visibility_api(tx_hash):
    """Check mempool visibility using our new API"""
    if not tx_hash:
        print("   ⚠️ No transaction hash to check")
        return
        
    print(f"   🔍 Checking mempool visibility for {tx_hash[:10]}...")
    
    try:
        visibility_url = f"https://coinceeper.com/api/send/check-mempool-visibility/{tx_hash}"
        response = requests.get(visibility_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                visibility = data['visibility']
                visible_count = visibility['visible_count']
                total_count = visibility['total_count']
                ratio = visibility['visibility_ratio']
                is_public = visibility['public_mempool']
                
                print(f"   📊 Mempool Visibility: {visible_count}/{total_count} RPCs ({ratio:.1%})")
                print(f"   🌐 Public Mempool: {'✅ YES' if is_public else '❌ NO (Private)'}")
                
                # Show detailed results
                for rpc_name, result in visibility['results'].items():
                    status = result['status']
                    if status == 'confirmed':
                        print(f"      ✅ {rpc_name}: CONFIRMED")
                    elif status == 'pending':
                        print(f"      ⏳ {rpc_name}: PENDING")
                    elif status == 'not_found':
                        print(f"      ❌ {rpc_name}: NOT FOUND")
                    else:
                        print(f"      ⚠️ {rpc_name}: {status}")
            else:
                print(f"   ❌ API Error: {data.get('message')}")
        else:
            print(f"   ⚠️ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error checking visibility: {e}")

if __name__ == "__main__":
    test_transaction_broadcast()
