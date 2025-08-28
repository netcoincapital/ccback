#!/usr/bin/env python3
"""
Test script for Polygon Transaction Finder
"""

from polygon_transaction_finder import PolygonTransactionFinder

def test_basic_functionality():
    """Test basic functionality with offline mode"""
    print("🧪 Testing Polygon Transaction Finder...")
    print("="*50)
    
    # Create finder in offline mode for testing
    finder = PolygonTransactionFinder(offline_mode=True)
    
    # Test price fetching
    print("💰 Testing POL price fetching...")
    pol_price = finder.get_pol_price()
    print(f"✅ POL Price: ${pol_price}")
    
    # Test conversion functions
    print("\n🔄 Testing conversion functions...")
    test_wei = 1000000000000000000  # 1 POL in Wei
    pol_amount = finder.wei_to_pol(test_wei)
    usd_amount = finder.pol_to_usd(pol_amount, pol_price)
    print(f"✅ {test_wei} Wei = {pol_amount} POL = ${usd_amount}")
    
    # Test transaction finding (offline mode)
    print("\n🔍 Testing transaction search (offline mode)...")
    transactions = finder.find_transactions(target_total_fee=52, max_transactions=5)
    
    if transactions:
        print(f"✅ Found {len(transactions)} test transactions")
        finder.print_summary(transactions)
        
        # Test export
        print("\n📁 Testing export functionality...")
        filename = finder.export_results(transactions, "test_polygon_output.json")
        print(f"✅ Export test completed: {filename}")
    else:
        print("❌ No transactions found in test mode")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    test_basic_functionality()
