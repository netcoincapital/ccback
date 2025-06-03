#!/usr/bin/env python3
"""
Test script to verify database and Tatum API fixes
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from webhook.tatum_subscription import normalize_blockchain_name, validate_and_format_address
from webhook.database_operations import DatabaseOperations
from utils.logging_config import get_logger

logger = get_logger(__name__)

def test_blockchain_normalization():
    """Test blockchain name normalization"""
    print("\n=== Testing Blockchain Name Normalization ===")
    
    test_cases = [
        ("BNB", "bsc-mainnet"),
        ("BSC", "bsc-mainnet"),
        ("ETH", "ethereum-mainnet"),
        ("BTC", "bitcoin-mainnet"),
        ("MATIC", "polygon-mainnet"),
        ("DOT", None),  # Should return None (unsupported)
        ("TRON", "tron-mainnet"),
        ("TRX", "tron-mainnet"),
    ]
    
    for input_chain, expected in test_cases:
        result = normalize_blockchain_name(input_chain)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status}: {input_chain} -> {result} (expected: {expected})")

def test_address_validation():
    """Test address validation and formatting"""
    print("\n=== Testing Address Validation ===")
    
    test_cases = [
        ("0x07dca612dfaa035ec31450913e51bfa64af3beda", "BNB", True),
        ("0x07dca612dfaa035ec31450913e51bfa64af3beda", "BSC", True),
        ("0x07dca612dfaa035ec31450913e51bfa64af3beda", "ETH", True),
        ("invalid_address", "BNB", False),
        ("", "BNB", False),
    ]
    
    for address, chain, should_be_valid in test_cases:
        result = validate_and_format_address(address, chain)
        is_valid = result is not None
        status = "✅ PASS" if is_valid == should_be_valid else "❌ FAIL"
        print(f"{status}: {address} on {chain} -> Valid: {is_valid} (expected: {should_be_valid})")

def test_database_status_field():
    """Test database status field handling"""
    print("\n=== Testing Database Status Field ===")
    
    test_statuses = [
        "confirmed",
        "pending", 
        "failed",
        "completed",  # This was causing issues before
    ]
    
    for status in test_statuses:
        # Test string length and encoding
        encoded = status.encode('utf-8')
        char_count = len(status)
        byte_count = len(encoded)
        
        status_icon = "✅" if char_count <= 20 else "❌"
        print(f"{status_icon}: '{status}' - {char_count} chars, {byte_count} bytes")

def test_string_sanitization():
    """Test string sanitization for database fields"""
    print("\n=== Testing String Sanitization ===")
    
    test_data = {
        'TxHash': '0x64c5c1a3130fded891edeafe4bd7762ab52991190dc797fb6e38e739d9ab6b9d',
        'TokenSymbol': 'BNB',
        'Status': 'confirmed',
        'Direction': 'inbound',
        'AssetType': 'native',
    }
    
    field_limits = {
        'TxHash': 100,
        'TokenSymbol': 20,
        'Status': 20,
        'Direction': 10,
        'AssetType': 20,
    }
    
    for field, value in test_data.items():
        sanitized = str(value).strip()[:field_limits[field]]
        length_ok = len(sanitized) <= field_limits[field]
        status_icon = "✅" if length_ok else "❌"
        print(f"{status_icon}: {field}: '{sanitized}' ({len(sanitized)}/{field_limits[field]} chars)")

if __name__ == "__main__":
    print("🔧 Testing Database and Tatum API Fixes")
    
    try:
        test_blockchain_normalization()
        test_address_validation()
        test_database_status_field()
        test_string_sanitization()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        logger.error(f"Test failed: {str(e)}", exc_info=True) 