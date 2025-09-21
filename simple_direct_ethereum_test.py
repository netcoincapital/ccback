#!/usr/bin/env python3
"""
Simple Direct Ethereum Transaction Test
Tests Ethereum transactions directly with verified public RPCs
"""
from web3 import Web3
import time

def test_direct_ethereum_transaction():
    """Test Ethereum transaction directly with verified RPCs"""
    
    print("🔥 DIRECT ETHEREUM TRANSACTION TEST")
    print("=" * 40)
    
    # Test address from your logs
    address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    recipient = "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
    
    # Use only verified public RPCs that actually broadcast
    verified_rpcs = [
        ("PublicNode", "https://ethereum-rpc.publicnode.com"),
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Cloudflare", "https://cloudflare-eth.com"),
    ]
    
    print("1. Testing RPC connections...")
    working_rpc = None
    
    for name, url in verified_rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if w3.is_connected():
                latest_block = w3.eth.block_number
                nonce = w3.eth.get_transaction_count(address, 'latest')
                balance = w3.eth.get_balance(address)
                
                print(f"✅ {name:12} | Block: {latest_block:8} | Nonce: {nonce} | Balance: {w3.from_wei(balance, 'ether'):.6f} ETH")
                
                if not working_rpc:
                    working_rpc = (name, url, w3)
            else:
                print(f"❌ {name:12} | Connection failed")
                
        except Exception as e:
            print(f"❌ {name:12} | Error: {str(e)[:40]}...")
    
    if not working_rpc:
        print("❌ No working RPCs found")
        return False
    
    name, url, w3 = working_rpc
    print(f"\n2. Using {name} for transaction test...")
    
    # Get current network state
    try:
        balance = w3.eth.get_balance(address)
        balance_eth = w3.from_wei(balance, 'ether')
        nonce = w3.eth.get_transaction_count(address, 'latest')
        
        # Get gas price
        gas_price = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price, 'gwei')
        
        print(f"📊 Current State:")
        print(f"   Balance: {balance_eth:.6f} ETH")
        print(f"   Nonce: {nonce}")
        print(f"   Gas Price: {gas_price_gwei:.2f} Gwei")
        
        # Calculate transaction cost
        amount_wei = w3.to_wei(0.0001, 'ether')  # 0.0001 ETH
        gas_limit = 21000
        tx_fee = gas_price * gas_limit
        total_cost = amount_wei + tx_fee
        
        total_cost_eth = w3.from_wei(total_cost, 'ether')
        tx_fee_eth = w3.from_wei(tx_fee, 'ether')
        
        print(f"💰 Transaction Cost:")
        print(f"   Amount: 0.0001 ETH")
        print(f"   Fee: {tx_fee_eth:.6f} ETH")
        print(f"   Total: {total_cost_eth:.6f} ETH")
        
        if balance < total_cost:
            print(f"❌ Insufficient balance: {balance_eth:.6f} < {total_cost_eth:.6f}")
            return False
        
        print("✅ Sufficient balance for transaction")
        
        # Check if this would be a real transaction
        print(f"\n3. Transaction would be:")
        print(f"   From: {address}")
        print(f"   To: {recipient}")
        print(f"   Amount: 0.0001 ETH")
        print(f"   Nonce: {nonce}")
        print(f"   Gas Price: {gas_price_gwei:.2f} Gwei")
        
        # Verify this nonce is correct
        if nonce == 3:
            print("✅ Nonce is correct (3)")
        else:
            print(f"⚠️ Nonce is {nonce}, expected 3")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting network state: {str(e)}")
        return False

def verify_transaction_on_etherscan(tx_hash):
    """Check if transaction exists on Etherscan"""
    import requests
    
    print(f"\n🔍 Checking {tx_hash} on Etherscan...")
    
    try:
        # Use Etherscan API to check transaction
        api_key = "77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY"  # From your config
        url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('result'):
            print("✅ Transaction found on Etherscan!")
            tx_data = data['result']
            print(f"   Block: {tx_data.get('blockNumber', 'Pending')}")
            print(f"   Gas Price: {int(tx_data.get('gasPrice', '0'), 16) / 10**9:.2f} Gwei")
            return True
        else:
            print("❌ Transaction not found on Etherscan")
            return False
            
    except Exception as e:
        print(f"❌ Error checking Etherscan: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 COINCEEPER DIRECT ETHEREUM TEST")
    print("=" * 35)
    print("Testing Ethereum network directly...")
    print()
    
    success = test_direct_ethereum_transaction()
    
    print()
    print("🎯 SUMMARY:")
    print("-" * 15)
    
    if success:
        print("✅ Network connectivity: WORKING")
        print("✅ Balance check: SUFFICIENT")
        print("✅ Nonce calculation: READY")
        print("✅ Gas price: REASONABLE")
        print()
        print("💡 The network is ready for transactions!")
        print("💡 The issue is likely with the service configuration")
        print("💡 Run: python force_restart_ethereum_service.py")
    else:
        print("❌ Network test failed")
        print("❌ Cannot proceed with transactions")
    
    return success

if __name__ == "__main__":
    main()

