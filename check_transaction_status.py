#!/usr/bin/env python3
"""
Check transaction status on blockchain
"""
import requests
import json
from web3 import Web3

def check_transaction_status():
    print("🔍 Checking Transaction Status")
    print("==============================")
    
    # Connect to Ethereum
    w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    
    if not w3.is_connected():
        print("❌ Not connected to Ethereum")
        return
        
    print("✅ Connected to Ethereum")
    
    # Test address
    address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
    
    # Get current nonce and recent transactions
    try:
        current_nonce = w3.eth.get_transaction_count(address)
        balance_wei = w3.eth.get_balance(address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        print(f"Address: {address}")
        print(f"Current nonce: {current_nonce}")
        print(f"Balance: {balance_eth} ETH")
        print("")
        
        # Check recent blocks for transactions from this address
        latest_block = w3.eth.block_number
        print(f"Latest block: {latest_block}")
        
        # Check last 50 blocks for transactions  
        print("🔍 Checking recent transactions (last 50 blocks)...")
        found_transactions = []
        
        for block_num in range(latest_block - 50, latest_block + 1):
            try:
                block = w3.eth.get_block(block_num, full_transactions=True)
                for tx in block.transactions:
                    if tx['from'] and tx['from'].lower() == address.lower():
                        found_transactions.append({
                            'block': block_num,
                            'hash': tx['hash'].hex(),
                            'to': tx['to'],
                            'value': w3.from_wei(tx['value'], 'ether'),
                            'nonce': tx['nonce'],
                            'gas': tx['gas'],
                            'gasPrice': w3.from_wei(tx['gasPrice'], 'gwei')
                        })
            except Exception as e:
                print(f"Error checking block {block_num}: {str(e)}")
                
        if found_transactions:
            print(f"✅ Found {len(found_transactions)} recent transactions:")
            for tx in found_transactions:
                print(f"  Block {tx['block']}: {tx['hash']}")
                print(f"    To: {tx['to']}")
                print(f"    Value: {tx['value']} ETH")
                print(f"    Nonce: {tx['nonce']}")
                print(f"    Gas: {tx['gas']}, Price: {tx['gasPrice']} Gwei")
                print("")
        else:
            print("❌ No recent transactions found")
            
        # Check pending transactions
        print("🔍 Checking pending transactions...")
        try:
            # This might not work on all nodes
            pending_block = w3.eth.get_block('pending', full_transactions=True)
            pending_txs = [tx for tx in pending_block.transactions if tx['from'] and tx['from'].lower() == address.lower()]
            
            if pending_txs:
                print(f"⏳ Found {len(pending_txs)} pending transactions:")
                for tx in pending_txs:
                    print(f"  Hash: {tx['hash'].hex()}")
                    print(f"  To: {tx['to']}")
                    print(f"  Value: {w3.from_wei(tx['value'], 'ether')} ETH")
            else:
                print("✅ No pending transactions")
                
        except Exception as e:
            print(f"Cannot check pending transactions: {str(e)}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_transaction_status()
