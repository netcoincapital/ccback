#!/usr/bin/env python3
"""
IMPROVED Debug script for Ethereum transaction parameters
Analyzes network conditions and transaction readiness for public mempool broadcasting
"""
from web3 import Web3
import time
import concurrent.futures

def get_gas_recommendations():
    """Get comprehensive gas price recommendations from multiple sources"""
    print("🔥 IMPROVED Gas Price Analysis")
    print("==============================")
    
    # Multiple RPC endpoints for comparison
    rpcs = [
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Ankr", "https://rpc.ankr.com/eth"),
        ("PublicNode", "https://ethereum-rpc.publicnode.com"),
        ("1RPC", "https://1rpc.io/eth"),
    ]
    
    gas_data = {}
    
    def check_rpc_gas(name, url):
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if not w3.is_connected():
                return name, None
                
            # Get current network state
            latest_block = w3.eth.get_block('latest')
            base_fee = latest_block.get('baseFeePerGas', 0)
            gas_price = w3.eth.gas_price
            
            # Try to get priority fee
            try:
                priority_fee = w3.eth.max_priority_fee
            except:
                priority_fee = w3.to_wei(2, 'gwei')  # Fallback
            
            return name, {
                'base_fee': base_fee,
                'gas_price': gas_price,
                'priority_fee': priority_fee,
                'block_number': latest_block['number'],
                'connected': True
            }
        except Exception as e:
            return name, {'error': str(e), 'connected': False}
    
    # Check all RPCs in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(check_rpc_gas, name, url) for name, url in rpcs]
        
        for future in concurrent.futures.as_completed(futures, timeout=15):
            try:
                name, data = future.result()
                gas_data[name] = data
            except Exception as e:
                print(f"   ❌ Error checking RPC: {str(e)}")
    
    # Analyze results
    print("\n📊 RPC Gas Price Comparison:")
    print("-" * 50)
    
    working_rpcs = []
    for name, data in gas_data.items():
        if data and data.get('connected'):
            base_gwei = data['base_fee'] / 10**9 if data['base_fee'] else 0
            gas_gwei = data['gas_price'] / 10**9 if data['gas_price'] else 0
            priority_gwei = data['priority_fee'] / 10**9 if data['priority_fee'] else 0
            
            print(f"✅ {name:12} | Block: {data['block_number']:8} | Base: {base_gwei:6.2f} | Gas: {gas_gwei:6.2f} | Priority: {priority_gwei:6.2f} Gwei")
            working_rpcs.append(data)
        else:
            error_msg = data.get('error', 'Unknown') if data else 'No response'
            print(f"❌ {name:12} | Error: {error_msg[:40]}")
    
    if not working_rpcs:
        print("❌ No working RPCs found!")
        return None
    
    # Calculate recommendations based on working RPCs
    avg_base = sum(d['base_fee'] for d in working_rpcs) / len(working_rpcs)
    avg_priority = sum(d['priority_fee'] for d in working_rpcs) / len(working_rpcs)
    max_gas = max(d['gas_price'] for d in working_rpcs)
    
    print(f"\n🎯 RECOMMENDED GAS PRICES:")
    print("-" * 30)
    print(f"🟢 Conservative: {(avg_base + avg_priority + Web3.to_wei(10, 'gwei')) / 10**9:.2f} Gwei")
    print(f"🟡 Standard:     {(avg_base + avg_priority * 1.2 + Web3.to_wei(20, 'gwei')) / 10**9:.2f} Gwei")
    print(f"🔴 Fast:         {(avg_base + avg_priority * 1.5 + Web3.to_wei(30, 'gwei')) / 10**9:.2f} Gwei")
    print(f"⚡ Network Max:   {max_gas / 10**9:.2f} Gwei")
    
    return {
        'base_fee': avg_base,
        'priority_fee': avg_priority,
        'recommended_conservative': avg_base + avg_priority + Web3.to_wei(10, 'gwei'),
        'recommended_standard': avg_base + avg_priority * 1.2 + Web3.to_wei(20, 'gwei'),
        'recommended_fast': avg_base + avg_priority * 1.5 + Web3.to_wei(30, 'gwei'),
        'network_max': max_gas
    }

def check_address_readiness(address):
    """Check if address is ready for transactions"""
    print(f"\n👤 ADDRESS READINESS CHECK: {address}")
    print("=" * 60)
    
    # Use most reliable RPC
    w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    
    if not w3.is_connected():
        print("❌ Cannot connect to Ethereum network")
        return False
    
    try:
        # Get address state
        balance = w3.eth.get_balance(address)
        nonce = w3.eth.get_transaction_count(address)
        pending_nonce = w3.eth.get_transaction_count(address, 'pending')
        
        balance_eth = w3.from_wei(balance, 'ether')
        pending_txs = pending_nonce - nonce
        
        print(f"💰 Balance:           {balance_eth:.6f} ETH")
        print(f"🔢 Confirmed Nonce:   {nonce}")
        print(f"⏳ Pending Nonce:     {pending_nonce}")
        print(f"📊 Pending TXs:       {pending_txs}")
        
        # Check for issues
        issues = []
        if balance_eth < 0.001:
            issues.append(f"⚠️  Low balance: {balance_eth:.6f} ETH (may not cover gas fees)")
        
        if pending_txs > 0:
            issues.append(f"⚠️  {pending_txs} pending transactions detected")
            
            # Try to get pending transaction details
            try:
                pending_block = w3.eth.get_block('pending', full_transactions=True)
                user_pending = [tx for tx in pending_block.transactions 
                              if tx and tx.get('from') and tx['from'].lower() == address.lower()]
                
                if user_pending:
                    print(f"\n🔍 PENDING TRANSACTIONS ANALYSIS:")
                    for i, tx in enumerate(user_pending[:3]):  # Show max 3
                        gas_gwei = w3.from_wei(tx.get('gasPrice', 0), 'gwei')
                        value_eth = w3.from_wei(tx.get('value', 0), 'ether')
                        print(f"   TX {i+1}: Nonce={tx.get('nonce')} | Gas={gas_gwei:.2f} Gwei | Value={value_eth:.6f} ETH")
                        
                        # Check if gas price is too low
                        latest_block = w3.eth.get_block('latest')
                        base_fee = latest_block.get('baseFeePerGas', 0)
                        if tx.get('gasPrice', 0) < base_fee:
                            issues.append(f"❌ TX {i+1} gas price too low ({gas_gwei:.2f} < {base_fee/10**9:.2f} Gwei)")
                            
            except Exception as e:
                print(f"   Cannot analyze pending transactions: {str(e)}")
        
        # Overall readiness assessment
        if not issues:
            print(f"\n✅ ADDRESS IS READY FOR TRANSACTIONS")
            return True
        else:
            print(f"\n⚠️  ISSUES DETECTED:")
            for issue in issues:
                print(f"   {issue}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking address: {str(e)}")
        return False

def test_rpc_broadcast_capabilities():
    """Test which RPCs support transaction broadcasting"""
    print(f"\n🧪 RPC BROADCAST CAPABILITY TEST")
    print("=" * 40)
    
    test_rpcs = [
        "https://eth.llamarpc.com",
        "https://rpc.ankr.com/eth", 
        "https://ethereum-rpc.publicnode.com",
        "https://1rpc.io/eth",
        "https://eth.api.onfinality.io/public"
    ]
    
    def test_rpc(url):
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if not w3.is_connected():
                return url, "❌ Connection failed"
            
            # Test with invalid transaction to check error response
            try:
                w3.eth.send_raw_transaction(b'0x00')
            except Exception as e:
                error_msg = str(e).lower()
                if 'method not found' in error_msg or 'not supported' in error_msg:
                    return url, "❌ No broadcast support"
                elif 'invalid' in error_msg or 'decode' in error_msg or 'rlp' in error_msg:
                    return url, "✅ Supports broadcasting"
                else:
                    return url, f"⚠️  Unknown: {error_msg[:30]}..."
                    
        except Exception as e:
            return url, f"❌ Error: {str(e)[:30]}..."
    
    # Test all RPCs
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(test_rpc, url) for url in test_rpcs]
        
        for future in concurrent.futures.as_completed(futures, timeout=20):
            try:
                url, result = future.result()
                rpc_name = url.split('//')[1].split('/')[0].split('.')[0]
                print(f"{rpc_name:15} | {result}")
            except Exception as e:
                print(f"Test error: {str(e)}")

def main():
    print("🔥 COINCEEPER ETHEREUM TRANSACTION DIAGNOSTICS")
    print("=" * 55)
    print("Analyzing network conditions and transaction readiness...")
    print()
    
    # Test address from your logs
    test_address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    
    # 1. Get gas recommendations
    gas_data = get_gas_recommendations()
    
    # 2. Check address readiness
    address_ready = check_address_readiness(test_address)
    
    # 3. Test RPC capabilities
    test_rpc_broadcast_capabilities()
    
    # 4. Final recommendations
    print(f"\n🎯 FINAL RECOMMENDATIONS")
    print("=" * 30)
    
    if gas_data and address_ready:
        recommended_gas = gas_data['recommended_standard'] / 10**9
        print(f"✅ Use gas price: {recommended_gas:.2f} Gwei or higher")
        print(f"✅ Address is ready for transactions")
        print(f"✅ Use multiple RPC endpoints for broadcasting")
        print(f"✅ Monitor transaction on Etherscan after sending")
    else:
        print(f"⚠️  Fix identified issues before sending transactions")
    
    print(f"\n🔗 Monitor transactions at: https://etherscan.io/address/{test_address}")

if __name__ == "__main__":
    main()
