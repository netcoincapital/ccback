#!/usr/bin/env python3
"""
Debug script to test transaction broadcasting and identify why transactions remain private
"""
import sys
import os
import time
import requests
import json
from decimal import Decimal

# Add project path
sys.path.insert(0, '/www/wwwroot/coinceeper.com/CC')
sys.path.insert(0, '/www/wwwroot/coinceeper.com')

print("🔍 Transaction Broadcasting Debug Test")
print("=" * 50)

def test_rpc_endpoints():
    """Test different RPC endpoints for transaction broadcasting capability"""
    print("\n📡 Testing RPC Endpoints for Broadcasting...")
    
    rpc_endpoints = [
        "https://cloudflare-eth.com",
        "https://rpc.ankr.com/eth", 
        "https://ethereum.publicnode.com",
        "https://1rpc.io/eth",
        "https://eth.llamarpc.com"
    ]
    
    from web3 import Web3
    
    results = {}
    for rpc in rpc_endpoints:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc))
            if w3.is_connected():
                chain_id = w3.eth.chain_id
                block_num = w3.eth.block_number
                gas_price = w3.eth.gas_price
                
                # Test sendRawTransaction capability
                try:
                    w3.eth.send_raw_transaction(b'0x00')  # Invalid tx to test method
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'method not found' in error_msg:
                        broadcast_support = "❌ No sendRawTransaction"
                    elif 'invalid' in error_msg or 'decode' in error_msg:
                        broadcast_support = "✅ Supports broadcasting"
                    else:
                        broadcast_support = f"⚠️ Unknown: {error_msg[:50]}"
                
                results[rpc] = {
                    'status': '✅ Connected',
                    'chain_id': chain_id,
                    'block': block_num,
                    'gas_price_gwei': round(gas_price / 10**9, 2),
                    'broadcast': broadcast_support
                }
            else:
                results[rpc] = {'status': '❌ Connection failed'}
        except Exception as e:
            results[rpc] = {'status': f'❌ Error: {str(e)[:30]}'}
    
    print("\nRPC Test Results:")
    for rpc, result in results.items():
        print(f"  {rpc}:")
        for key, value in result.items():
            print(f"    {key}: {value}")
    
    return results

def test_current_network_conditions():
    """Test current network conditions"""
    print("\n⛽ Testing Current Network Conditions...")
    
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
        
        if w3.is_connected():
            # Get current block info
            latest_block = w3.eth.get_block('latest')
            pending_block = w3.eth.get_block('pending')
            
            base_fee_latest = latest_block.get('baseFeePerGas', 0)
            base_fee_pending = pending_block.get('baseFeePerGas', 0) 
            
            print(f"  Latest Block: #{latest_block['number']}")
            print(f"  Latest BaseFee: {base_fee_latest / 10**9:.2f} Gwei")
            print(f"  Pending BaseFee: {base_fee_pending / 10**9:.2f} Gwei")
            
            # Get network priority fee
            try:
                network_priority = w3.eth.max_priority_fee
                print(f"  Network Priority Fee: {network_priority / 10**9:.2f} Gwei")
            except:
                print("  Network Priority Fee: Not available")
            
            # Test gas price
            gas_price = w3.eth.gas_price
            print(f"  Current Gas Price: {gas_price / 10**9:.2f} Gwei")
            
            return {
                'base_fee_latest': base_fee_latest,
                'base_fee_pending': base_fee_pending,
                'gas_price': gas_price,
                'network_priority': network_priority if 'network_priority' in locals() else 0
            }
        else:
            print("  ❌ Cannot connect to get network conditions")
            return None
    except Exception as e:
        print(f"  ❌ Error getting network conditions: {e}")
        return None

def test_transaction_preparation():
    """Test transaction preparation with our service"""
    print("\n🔧 Testing Transaction Preparation...")
    
    try:
        from services.blockchains.ethereum_service import EthereumService
        service = EthereumService()
        
        # Test addresses
        sender = '0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956'
        recipient = '0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9'
        amount = Decimal('0.0001')
        
        print(f"  Testing preparation: {amount} ETH from {sender[:10]}... to {recipient[:10]}...")
        
        result, error = service.prepare_transaction(sender, recipient, amount)
        
        if error:
            print(f"  ❌ Preparation failed: {error}")
            return None
        else:
            print(f"  ✅ Preparation successful!")
            print(f"  Transaction ID: {result['transaction_id']}")
            print(f"  Estimated Fee: {result['details']['estimated_fee']} ETH")
            
            # Test RPC broadcast capabilities
            broadcast_results = service.test_rpc_broadcast_capability()
            print(f"  RPC Broadcast Test: {len(broadcast_results)} endpoints tested")
            
            return result
            
    except Exception as e:
        print(f"  ❌ Error in preparation: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_mempool_visibility(tx_hash):
    """Test if transaction is visible in public mempool"""
    print(f"\n👁️ Testing Mempool Visibility for {tx_hash}...")
    
    # Test different mempool APIs
    mempool_apis = [
        f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}",
        f"https://cloudflare-eth.com",  # We'll use JSON-RPC
    ]
    
    # Test Etherscan API
    try:
        response = requests.get(mempool_apis[0], timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                print("  ✅ Transaction found in Etherscan")
            else:
                print("  ❌ Transaction NOT found in Etherscan")
        else:
            print(f"  ⚠️ Etherscan API error: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Etherscan API error: {e}")
    
    # Test direct RPC call
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
        
        tx_data = w3.eth.get_transaction(tx_hash)
        if tx_data:
            print("  ✅ Transaction found via direct RPC")
            print(f"    Block Number: {tx_data.get('blockNumber', 'Pending')}")
            print(f"    Gas Price: {tx_data.get('gasPrice', 0) / 10**9:.2f} Gwei")
        else:
            print("  ❌ Transaction NOT found via direct RPC")
    except Exception as e:
        print(f"  ❌ Direct RPC error: {e}")

def simulate_full_transaction_flow():
    """Simulate the full transaction flow to identify issues"""
    print("\n🚀 Simulating Full Transaction Flow...")
    
    # Step 1: Test network conditions
    network_conditions = test_current_network_conditions()
    
    # Step 2: Test preparation
    prep_result = test_transaction_preparation()
    
    if not prep_result:
        print("  ❌ Cannot proceed - preparation failed")
        return
    
    # Step 3: Test confirmation (without actually sending)
    print("\n📤 Testing Confirmation Process...")
    
    try:
        # Simulate confirmation request
        confirm_data = {
            'UserID': 'test-user-id',
            'blockchain': 'ethereum',
            'transaction_id': prep_result['transaction_id']
        }
        
        # Make request to our confirm endpoint
        response = requests.post(
            'https://coinceeper.com/api/send/confirm',
            json=confirm_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"  Confirm Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                tx_hash = result.get('tx_hash')
                print(f"  ✅ Transaction sent successfully!")
                print(f"  TX Hash: {tx_hash}")
                
                # Wait a bit and test mempool visibility
                print("  ⏳ Waiting 10 seconds before checking mempool...")
                time.sleep(10)
                
                if tx_hash:
                    test_mempool_visibility(tx_hash)
                
            else:
                print(f"  ❌ Transaction failed: {result.get('message', 'Unknown error')}")
        else:
            print(f"  ❌ HTTP Error: {response.text}")
            
    except Exception as e:
        print(f"  ❌ Error in confirmation test: {e}")

if __name__ == "__main__":
    try:
        # Run comprehensive tests
        test_rpc_endpoints()
        simulate_full_transaction_flow()
        
        print("\n" + "=" * 50)
        print("🏁 Debug Test Complete!")
        print("\nKey Points to Check:")
        print("1. Are RPC endpoints supporting public broadcasting?")
        print("2. Is gas price above current BaseFee?")
        print("3. Is priority fee > 0 for EIP-1559?")
        print("4. Are transactions appearing in public mempool?")
        print("5. Check Etherscan for transaction visibility")
        
    except Exception as e:
        print(f"\n❌ Fatal error in debug test: {e}")
        import traceback
        traceback.print_exc()

