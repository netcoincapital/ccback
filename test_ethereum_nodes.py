#!/usr/bin/env python3
"""
Test Ethereum node connectivity
"""
import requests
import time
import os

def test_node(url, name):
    """Test a single Ethereum node"""
    print(f"Testing {name}: {url}")
    
    # Test basic connectivity
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=10)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                block_number = int(data['result'], 16)
                response_time = round((end_time - start_time) * 1000, 2)
                print(f"  ✅ Success: Block #{block_number}, Response time: {response_time}ms")
                return True
            else:
                print(f"  ❌ Failed: {data}")
                return False
        else:
            print(f"  ❌ Failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"  ❌ Failed: Timeout (>10s)")
        return False
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}")
        return False

def main():
    print("🔗 Testing Ethereum Node Connectivity")
    print("=====================================")
    
    # Check if INFURA_API_KEY exists
    infura_key = os.getenv('INFURA_API_KEY')
    if infura_key:
        print(f"✅ INFURA_API_KEY found: {infura_key[:10]}...")
        infura_url = f"https://mainnet.infura.io/v3/{infura_key}"
        test_node(infura_url, "Infura (Primary)")
    else:
        print("⚠️ INFURA_API_KEY not found, testing public nodes...")
    
    print("")
    
    # Test public nodes
    public_nodes = [
        ("https://eth.llamarpc.com", "LlamaRPC"),
        ("https://ethereum.publicnode.com", "PublicNode"),
        ("https://rpc.ankr.com/eth", "Ankr"),
        ("https://1rpc.io/eth", "1RPC"),
        ("https://cloudflare-eth.com", "Cloudflare")
    ]
    
    working_nodes = []
    
    for url, name in public_nodes:
        if test_node(url, name):
            working_nodes.append((url, name))
        print("")
    
    print("📊 Summary:")
    print("===========")
    if working_nodes:
        print(f"✅ {len(working_nodes)} working nodes found:")
        for url, name in working_nodes:
            print(f"   - {name}: {url}")
    else:
        print("❌ No working nodes found!")
        
    print("")
    print("💡 Recommendations:")
    print("==================")
    if not infura_key:
        print("1. Set INFURA_API_KEY environment variable for better reliability")
        print("   Get free API key from: https://infura.io/")
    
    if not working_nodes:
        print("2. Check server firewall/network connectivity")
        print("3. Try different RPC endpoints")
    elif len(working_nodes) < 3:
        print("2. Consider using multiple backup nodes")

if __name__ == "__main__":
    main()
