#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test for Ethereum Transaction Finder
"""

from ethereum_transaction_finder import EthereumTransactionFinder

def test_basic_functionality():
    """Test basic program functionality"""
    print("🧪 Starting Ethereum Transaction Finder test")
    print("-" * 40)
    
    # Create instance
    finder = EthereumTransactionFinder()
    
    # Test ETH price fetching
    print("1️⃣ Testing ETH price fetch...")
    price = finder.get_eth_price()
    if price:
        print(f"   ✅ ETH Price: ${price:,.2f}")
    else:
        print("   ❌ Error fetching price")
        return False
    
    # Test recent blocks fetch
    print("\n2️⃣ Testing recent blocks fetch...")
    blocks = finder.get_latest_blocks(3)
    if blocks:
        print(f"   ✅ {len(blocks)} blocks retrieved")
        print(f"   🔗 Latest block: {blocks[0]}")
    else:
        print("   ❌ Error fetching blocks")
        return False
    
    # Test block transactions (with one transaction from first block)
    print("\n3️⃣ Testing block transactions fetch...")
    if blocks:
        tx_hashes = finder.get_block_transactions(blocks[0])
        if tx_hashes:
            print(f"   ✅ {len(tx_hashes)} transactions in first block")
            
            # Test transaction analysis
            print("\n4️⃣ Testing transaction analysis...")
            if len(tx_hashes) > 0:
                tx_data = finder.get_transaction_details(tx_hashes[0])
                if tx_data:
                    analyzed = finder.analyze_transaction(tx_data)
                    if analyzed:
                        print(f"   ✅ Transaction analyzed: Fee ${analyzed['fee_usd']:.2f}")
                        print(f"   📤 From: {analyzed['sender_address']}")
                        print(f"   📥 To: {analyzed['receiver_address']}")
                    else:
                        print("   ⚠️ Transaction not analyzed (might be exchange/old wallet)")
                else:
                    print("   ❌ Error fetching transaction details")
        else:
            print("   ❌ Error fetching transactions")
    
    print("\n✅ Tests completed")
    return True

def test_small_search():
    """Test small search"""
    print("\n🔍 Testing small search (3 transactions)")
    print("-" * 40)
    
    finder = EthereumTransactionFinder()
    
    # Small search with simulated dates
    transactions = finder.find_transactions(
        target_fee_usd=50,  # Small target
        max_transactions=3  # Small count
    )
    
    # Show simulated dates
    if transactions:
        print("\n📅 Sample simulated dates:")
        for i, tx in enumerate(transactions[:3]):
            print(f"  {i+1}. Simulated date: {tx['transaction_date']}")
            print(f"      Actual date: {tx['actual_date']}")
            print(f"      Hash: {tx['hash'][:16]}...")
            print(f"      From: {tx['sender_address'][:16]}... ({tx['sender_type']})")
            print(f"      To: {tx['receiver_address'][:16]}... ({tx['receiver_type']})")
    
    if transactions:
        finder.print_summary(transactions)
        return True
    else:
        print("❌ No transactions found")
        return False

if __name__ == "__main__":
    print("🚀 Starting Ethereum Transaction Finder Tests")
    print("=" * 50)
    
    # Test basic functionality
    if test_basic_functionality():
        # Test small search
        test_small_search()
    
    print("\n🏁 Tests completed")
