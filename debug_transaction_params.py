#!/usr/bin/env python3
"""
Debug transaction parameters to find why transactions are cancelled
"""
from web3 import Web3

def debug_transaction():
    print("🔍 Debugging Transaction Parameters")
    print("===================================")
    
    # Connect to Ethereum
    w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    
    if not w3.is_connected():
        print("❌ Not connected")
        return
        
    address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    
    # Get current network state
    latest_block = w3.eth.get_block('latest')
    gas_price = w3.eth.gas_price
    base_fee = latest_block.get('baseFeePerGas', 0)
    
    print(f"📊 Network State:")
    print(f"   Latest block: {latest_block['number']}")
    print(f"   Base fee: {w3.from_wei(base_fee, 'gwei'):.2f} Gwei")
    print(f"   Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} Gwei")
    print("")
    
    # Get address state
    balance = w3.eth.get_balance(address)
    nonce = w3.eth.get_transaction_count(address)
    pending_nonce = w3.eth.get_transaction_count(address, 'pending')
    
    print(f"👤 Address State:")
    print(f"   Balance: {w3.from_wei(balance, 'ether')} ETH")
    print(f"   Confirmed nonce: {nonce}")
    print(f"   Pending nonce: {pending_nonce}")
    print(f"   Pending transactions: {pending_nonce - nonce}")
    print("")
    
    # Check for stuck transactions
    if pending_nonce > nonce:
        print("⚠️ ISSUE FOUND: Pending transactions detected!")
        print("This could cause new transactions to be stuck.")
        print("")
        
        # Check pending transactions
        try:
            pending_block = w3.eth.get_block('pending', full_transactions=True)
            pending_txs = [tx for tx in pending_block.transactions 
                          if tx['from'] and tx['from'].lower() == address.lower()]
            
            if pending_txs:
                print(f"🔍 Found {len(pending_txs)} pending transactions:")
                for i, tx in enumerate(pending_txs):
                    print(f"   {i+1}. Hash: {tx['hash'].hex()}")
                    print(f"      Nonce: {tx['nonce']}")
                    print(f"      Gas Price: {w3.from_wei(tx['gasPrice'], 'gwei'):.2f} Gwei")
                    print(f"      Value: {w3.from_wei(tx['value'], 'ether')} ETH")
                    
                    # Check if gas price is too low
                    if tx['gasPrice'] < base_fee:
                        print(f"      ❌ Gas price too low! ({w3.from_wei(tx['gasPrice'], 'gwei'):.2f} < {w3.from_wei(base_fee, 'gwei'):.2f})")
                    else:
                        print(f"      ✅ Gas price OK")
                    print("")
                    
        except Exception as e:
            print(f"Cannot check pending transactions: {str(e)}")
    
    # Gas price analysis
    print("⛽ Gas Price Analysis:")
    recommended_gas = base_fee + w3.to_wei(2, 'gwei')  # Base + 2 Gwei tip
    current_gas = gas_price
    
    print(f"   Recommended: {w3.from_wei(recommended_gas, 'gwei'):.2f} Gwei")
    print(f"   Current: {w3.from_wei(current_gas, 'gwei'):.2f} Gwei")
    
    if current_gas < recommended_gas:
        print(f"   ❌ Current gas price too low!")
        print(f"   💡 Increase gas price by {w3.from_wei(recommended_gas - current_gas, 'gwei'):.2f} Gwei")
    else:
        print(f"   ✅ Gas price adequate")
    
    print("")
    print("🔧 Recommendations:")
    print("===================")
    
    if pending_nonce > nonce:
        print("1. Cancel or speed up pending transactions")
        print("2. Use higher gas price for new transactions")
        print("3. Check for nonce gaps")
    
    if current_gas < recommended_gas:
        print("4. Increase gas price to at least", w3.from_wei(recommended_gas, 'gwei'), "Gwei")
    
    print("5. Monitor transactions on Etherscan for confirmation")

if __name__ == "__main__":
    debug_transaction()
