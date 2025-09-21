#!/usr/bin/env python3
"""
Test gas estimation and basic transaction parameters
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_gas_estimation():
    try:
        from web3 import Web3
        
        # Use the same node as EthereumService
        w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
        
        print("🔍 Testing Gas Estimation")
        print("=========================")
        
        # Test addresses
        sender = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        recipient = "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
        
        print(f"Sender: {sender}")
        print(f"Recipient: {recipient}")
        print("")
        
        # Check connection
        if not w3.is_connected():
            print("❌ Not connected to Ethereum node")
            return
            
        print("✅ Connected to Ethereum node")
        
        # Get current block
        latest_block = w3.eth.block_number
        print(f"Latest block: {latest_block}")
        
        # Get sender balance
        try:
            balance_wei = w3.eth.get_balance(sender)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            print(f"Sender balance: {balance_eth} ETH ({balance_wei} wei)")
        except Exception as e:
            print(f"❌ Error getting balance: {str(e)}")
            return
            
        # Get current gas price
        try:
            gas_price = w3.eth.gas_price
            gas_price_gwei = w3.from_wei(gas_price, 'gwei')
            print(f"Current gas price: {gas_price_gwei} Gwei ({gas_price} wei)")
        except Exception as e:
            print(f"❌ Error getting gas price: {str(e)}")
            return
            
        # Get nonce
        try:
            nonce = w3.eth.get_transaction_count(sender)
            print(f"Sender nonce: {nonce}")
        except Exception as e:
            print(f"❌ Error getting nonce: {str(e)}")
            return
            
        print("")
        
        # Test gas estimation for different amounts
        test_amounts = [0.001, 0.002, 0.005]
        
        for amount_eth in test_amounts:
            print(f"Testing gas estimation for {amount_eth} ETH:")
            
            try:
                # Prepare transaction for estimation
                transaction = {
                    'from': w3.to_checksum_address(sender),
                    'to': w3.to_checksum_address(recipient),
                    'value': w3.to_wei(amount_eth, 'ether'),
                    'gasPrice': gas_price
                }
                
                # Estimate gas
                estimated_gas = w3.eth.estimate_gas(transaction)
                gas_cost_wei = estimated_gas * gas_price
                gas_cost_eth = w3.from_wei(gas_cost_wei, 'ether')
                
                total_required = amount_eth + float(gas_cost_eth)
                
                print(f"  Gas needed: {estimated_gas}")
                print(f"  Gas cost: {gas_cost_eth} ETH")
                print(f"  Total required: {total_required} ETH")
                print(f"  Sufficient balance: {float(balance_eth) >= total_required}")
                
                if float(balance_eth) < total_required:
                    shortage = total_required - float(balance_eth)
                    print(f"  ❌ Shortage: {shortage} ETH")
                else:
                    print(f"  ✅ Balance sufficient")
                    
            except Exception as e:
                print(f"  ❌ Gas estimation failed: {str(e)}")
                
            print("")
            
        # Test with a very small amount
        print("Testing with minimal amount (0.0001 ETH):")
        try:
            small_amount = 0.0001
            transaction = {
                'from': w3.to_checksum_address(sender),
                'to': w3.to_checksum_address(recipient),
                'value': w3.to_wei(small_amount, 'ether'),
                'gasPrice': gas_price
            }
            
            estimated_gas = w3.eth.estimate_gas(transaction)
            gas_cost_wei = estimated_gas * gas_price
            gas_cost_eth = w3.from_wei(gas_cost_wei, 'ether')
            
            print(f"  Amount: {small_amount} ETH")
            print(f"  Gas cost: {gas_cost_eth} ETH")
            print(f"  Total: {small_amount + float(gas_cost_eth)} ETH")
            print(f"  Available: {balance_eth} ETH")
            
            if float(balance_eth) >= (small_amount + float(gas_cost_eth)):
                print("  ✅ This amount should work!")
            else:
                print("  ❌ Even minimal amount doesn't work")
                
        except Exception as e:
            print(f"  ❌ Minimal amount estimation failed: {str(e)}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gas_estimation()

