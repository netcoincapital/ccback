#!/usr/bin/env python3
"""
Test Alchemy connection and RPC detection
"""
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

def test_alchemy():
    print("🔍 Testing Alchemy Connection")
    print("==============================")
    
    # Check environment variable
    alchemy_key = os.getenv('alchemy_api_key')
    print(f"Alchemy API Key: {alchemy_key}")
    
    if not alchemy_key:
        print("❌ Alchemy API key not found in environment")
        return
        
    alchemy_url = f'https://eth-mainnet.g.alchemy.com/v2/{alchemy_key}'
    print(f"Alchemy URL: {alchemy_url}")
    
    # Test connection
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(alchemy_url))
        
        if w3.is_connected():
            print("✅ Connected to Alchemy")
            
            # Test basic operations
            latest_block = w3.eth.block_number
            print(f"Latest block: {latest_block}")
            
            # Test if it supports sendRawTransaction
            try:
                # Try with invalid transaction to see error type
                w3.eth.send_raw_transaction(b'0x00')
            except Exception as e:
                error_msg = str(e).lower()
                if 'method not found' in error_msg:
                    print("❌ Alchemy doesn't support sendRawTransaction")
                elif 'invalid' in error_msg or 'rlp' in error_msg:
                    print("✅ Alchemy supports sendRawTransaction (got expected invalid tx error)")
                else:
                    print(f"✅ Alchemy supports sendRawTransaction (error: {str(e)[:50]})")
                    
        else:
            print("❌ Cannot connect to Alchemy")
            
    except Exception as e:
        print(f"❌ Error testing Alchemy: {str(e)}")
        
    # Test EthereumService detection
    print("\n🔧 Testing EthereumService RPC Detection:")
    try:
        from utils.blockchain_service_factory import BlockchainServiceFactory
        service = BlockchainServiceFactory.get_service('ethereum')
        
        if service:
            print(f"Primary RPC: {service.primary_rpc}")
            print(f"Broadcast RPCs: {len(service.broadcast_rpcs)}")
            for i, rpc in enumerate(service.broadcast_rpcs[:3]):
                print(f"  {i+1}. {rpc}")
                
            # Check if Alchemy is being used
            if 'alchemy' in service.primary_rpc:
                print("✅ EthereumService is using Alchemy")
            else:
                print("❌ EthereumService is NOT using Alchemy")
                print("Check environment variable loading")
        else:
            print("❌ Cannot get EthereumService")
            
    except Exception as e:
        print(f"❌ Error testing EthereumService: {str(e)}")

if __name__ == "__main__":
    test_alchemy()
