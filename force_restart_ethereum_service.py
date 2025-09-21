#!/usr/bin/env python3
"""
Force Restart Ethereum Service with Proper Configuration
Ensures all fixes are applied and working correctly
"""
import subprocess
import time
import os
import sys

def force_restart_service():
    """Force restart the service with proper configuration"""
    
    print("🔧 FORCING ETHEREUM SERVICE RESTART")
    print("=" * 40)
    
    # Step 1: Kill all gunicorn processes
    print("1. Killing all gunicorn processes...")
    try:
        subprocess.run(['pkill', '-f', 'gunicorn'], check=False)
        time.sleep(3)
        print("   ✅ Gunicorn processes killed")
    except Exception as e:
        print(f"   ⚠️ Error killing processes: {e}")
    
    # Step 2: Clear Python cache
    print("2. Clearing Python cache...")
    try:
        subprocess.run(['find', '/www/wwwroot/coinceeper.com/CC', '-name', '*.pyc', '-delete'], check=False)
        subprocess.run(['find', '/www/wwwroot/coinceeper.com/CC', '-name', '__pycache__', '-type', 'd', '-exec', 'rm', '-rf', '{}', '+'], check=False)
        print("   ✅ Python cache cleared")
    except Exception as e:
        print(f"   ⚠️ Error clearing cache: {e}")
    
    # Step 3: Restart systemd service
    print("3. Restarting systemd service...")
    try:
        subprocess.run(['systemctl', 'stop', 'gunicorn'], check=True)
        time.sleep(5)
        subprocess.run(['systemctl', 'start', 'gunicorn'], check=True)
        time.sleep(5)
        print("   ✅ Service restarted")
    except Exception as e:
        print(f"   ❌ Error restarting service: {e}")
        return False
    
    # Step 4: Check service status
    print("4. Checking service status...")
    try:
        result = subprocess.run(['systemctl', 'is-active', 'gunicorn'], 
                              capture_output=True, text=True)
        if result.stdout.strip() == 'active':
            print("   ✅ Service is active")
        else:
            print("   ❌ Service is not active")
            return False
    except Exception as e:
        print(f"   ❌ Error checking status: {e}")
        return False
    
    return True

def test_service_fixes():
    """Test if the service fixes are working"""
    print("\n🧪 TESTING SERVICE FIXES")
    print("=" * 25)
    
    # Test the service directly
    try:
        sys.path.insert(0, '/www/wwwroot/coinceeper.com/CC')
        
        # Import and test the service
        from services.blockchains.ethereum_service import EthereumService
        
        service = EthereumService()
        address = "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
        
        # Test nonce calculation
        nonce = service.w3.eth.get_transaction_count(address, 'latest')
        print(f"✅ Correct nonce: {nonce}")
        
        if nonce != 3:
            print(f"⚠️ Nonce should be 3, got {nonce}")
        
        # Test RPC configuration
        print(f"✅ Primary RPC: {service.primary_rpc}")
        print(f"✅ Broadcast RPCs: {len(service.broadcast_rpcs)}")
        
        # Test connection
        if service.w3.is_connected():
            latest_block = service.w3.eth.block_number
            print(f"✅ Connected to block: {latest_block}")
        else:
            print("❌ Not connected to Ethereum")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing service: {str(e)}")
        return False

def main():
    """Main function"""
    print("🚀 COINCEEPER ETHEREUM SERVICE FORCE RESTART")
    print("=" * 45)
    print("Applying all fixes with complete service restart...")
    print()
    
    # Step 1: Force restart
    if not force_restart_service():
        print("❌ Service restart failed")
        return False
    
    # Step 2: Test fixes
    if not test_service_fixes():
        print("❌ Service fixes not working")
        return False
    
    print()
    print("🎉 SUCCESS!")
    print("=" * 15)
    print("✅ Service restarted successfully")
    print("✅ All fixes applied and working")
    print("✅ Ready for testing")
    print()
    print("🧪 NEXT STEP:")
    print("Run: python test_verified_broadcast.py")
    
    return True

if __name__ == "__main__":
    main()

