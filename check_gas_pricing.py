#!/usr/bin/env python3
"""
Quick test to check current gas pricing vs our settings
"""
from web3 import Web3
import requests

def check_current_gas_conditions():
    print("⛽ Current Ethereum Gas Conditions")
    print("=" * 35)
    
    # Test multiple RPC endpoints
    rpcs = [
        "https://cloudflare-eth.com",
        "https://rpc.ankr.com/eth",
        "https://ethereum.publicnode.com"
    ]
    
    for rpc in rpcs:
        print(f"\n📡 Testing: {rpc}")
        try:
            w3 = Web3(Web3.HTTPProvider(rpc))
            
            if not w3.is_connected():
                print("   ❌ Not connected")
                continue
                
            # Get current block info
            latest_block = w3.eth.get_block('latest')
            try:
                pending_block = w3.eth.get_block('pending')
            except:
                pending_block = latest_block
            
            # Get fees
            base_fee_latest = latest_block.get('baseFeePerGas', 0)
            base_fee_pending = pending_block.get('baseFeePerGas', base_fee_latest)
            gas_price = w3.eth.gas_price
            
            try:
                priority_fee = w3.eth.max_priority_fee
            except:
                priority_fee = 0
            
            print(f"   ✅ Connected - Block #{latest_block['number']}")
            print(f"   📊 BaseFee (latest): {base_fee_latest / 10**9:.3f} Gwei")
            print(f"   📊 BaseFee (pending): {base_fee_pending / 10**9:.3f} Gwei")
            print(f"   📊 Gas Price: {gas_price / 10**9:.3f} Gwei")
            print(f"   📊 Priority Fee: {priority_fee / 10**9:.3f} Gwei")
            
            # Calculate our fees
            our_priority_2gwei = w3.to_wei('2', 'gwei')
            our_method1_fee = base_fee_pending + our_priority_2gwei + w3.to_wei('25', 'gwei')
            our_method2_fee = base_fee_pending + w3.to_wei('4', 'gwei') + w3.to_wei('35', 'gwei')
            
            print(f"\n   🔧 Our Method 1 MaxFee: {our_method1_fee / 10**9:.3f} Gwei")
            print(f"   🔧 Our Method 2 MaxFee: {our_method2_fee / 10**9:.3f} Gwei")
            
            # Check if our fees are competitive
            if our_method1_fee > base_fee_pending:
                print("   ✅ Our fees are above BaseFee - should be mineable")
            else:
                print("   ❌ Our fees are below BaseFee - will NOT be mined")
                
            break  # Use first working RPC
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

def check_mempool_services():
    print("\n🌐 Checking Mempool Services")
    print("=" * 30)
    
    # Test mempool services
    services = [
        {
            'name': 'Etherscan Gas Tracker',
            'url': 'https://api.etherscan.io/api?module=gastracker&action=gasoracle'
        }
    ]
    
    for service in services:
        try:
            response = requests.get(service['url'], timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    result = data['result']
                    print(f"   📈 {service['name']}:")
                    print(f"      Safe: {result.get('SafeGasPrice', 'N/A')} Gwei")
                    print(f"      Standard: {result.get('ProposeGasPrice', 'N/A')} Gwei") 
                    print(f"      Fast: {result.get('FastGasPrice', 'N/A')} Gwei")
                else:
                    print(f"   ⚠️ {service['name']}: API error")
            else:
                print(f"   ❌ {service['name']}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ {service['name']}: {e}")

if __name__ == "__main__":
    check_current_gas_conditions()
    check_mempool_services()
    
    print("\n" + "=" * 50)
    print("💡 Key Insights:")
    print("1. Check if BaseFee is higher than our gas prices")
    print("2. Ensure priority fee > 0 for EIP-1559")
    print("3. Compare our fees with network recommendations")
    print("4. Verify RPC endpoints support public broadcasting")

