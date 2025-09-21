#!/usr/bin/env python3
"""
Ethereum Environment Setup Script for CoinCeeper
Sets up proper API keys and RPC endpoints for reliable transaction broadcasting
"""
import os
import sys
from pathlib import Path

def create_env_file():
    """Create .env file with proper Ethereum API configuration"""
    env_content = """# Ethereum API Keys for CoinCeeper
# Replace these with your actual API keys for production

# Primary Ethereum RPC providers (get free keys from their websites)
alchemy_api_key=demo
INFURA_API_KEY=9aa3d95b3bc440fa88ea12eaa4456161

# Tatum API (for additional blockchain support)
TATUM_API_KEY=your_tatum_key_here

# Etherscan API (for transaction verification)
ETHERSCAN_API_KEY=77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY

# Database Configuration
DATABASE_URL=sqlite:///coinceeper.db

# Security Keys
AES_SECRET_KEY=your_aes_secret_key_here
SECRET_KEY=your_flask_secret_key_here
FLASK_ENV=production

# Webhook Configuration
HMAC_SECRET_KEY=my_secret_key
MAIN_URL=http://url/referrals/generate
WEBHOOK_BASE_URL=https://coinceeper.com

# Gas Price Configuration (optional overrides)
# ETH_MIN_GAS_PRICE=2.0  # Minimum gas price in Gwei
# ETH_MAX_GAS_PRICE=200.0  # Maximum gas price in Gwei
"""
    
    env_path = Path('.env')
    
    if env_path.exists():
        print("⚠️  .env file already exists!")
        response = input("Do you want to overwrite it? (y/N): ").lower()
        if response != 'y':
            print("Keeping existing .env file")
            return False
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("✅ Created .env file with Ethereum API configuration")
        return True
    except Exception as e:
        print(f"❌ Error creating .env file: {str(e)}")
        return False

def check_api_keys():
    """Check if API keys are properly configured"""
    print("\n🔑 API Key Configuration Check")
    print("-" * 40)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("❌ python-dotenv not installed. Install with: pip install python-dotenv")
        return False
    
    # Check required keys
    keys_to_check = {
        'alchemy_api_key': 'Alchemy API Key',
        'INFURA_API_KEY': 'Infura API Key', 
        'ETHERSCAN_API_KEY': 'Etherscan API Key',
        'DATABASE_URL': 'Database URL',
        'SECRET_KEY': 'Flask Secret Key'
    }
    
    missing_keys = []
    demo_keys = []
    
    for key, description in keys_to_check.items():
        value = os.getenv(key)
        if not value:
            missing_keys.append(description)
            print(f"❌ {description:20} | Not set")
        elif value in ['demo', 'your_key_here', 'your_tatum_key_here', 'your_aes_secret_key_here', 'your_flask_secret_key_here']:
            demo_keys.append(description)
            print(f"⚠️  {description:20} | Using demo/placeholder value")
        else:
            print(f"✅ {description:20} | Configured")
    
    if missing_keys:
        print(f"\n❌ Missing API keys: {', '.join(missing_keys)}")
        
    if demo_keys:
        print(f"\n⚠️  Using demo/placeholder keys: {', '.join(demo_keys)}")
        print("   These should be replaced with real API keys for production use")
    
    return len(missing_keys) == 0

def test_ethereum_connectivity():
    """Test connectivity to Ethereum network"""
    print("\n🌐 Ethereum Network Connectivity Test")
    print("-" * 45)
    
    try:
        from web3 import Web3
    except ImportError:
        print("❌ web3.py not installed. Install with: pip install web3")
        return False
    
    # Test multiple RPC endpoints
    test_rpcs = [
        ("LlamaRPC", "https://eth.llamarpc.com"),
        ("Ankr", "https://rpc.ankr.com/eth"),
        ("PublicNode", "https://ethereum-rpc.publicnode.com"),
        ("Alchemy Demo", "https://eth-mainnet.g.alchemy.com/v2/demo"),
    ]
    
    working_rpcs = 0
    
    for name, url in test_rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
            if w3.is_connected():
                latest_block = w3.eth.block_number
                print(f"✅ {name:15} | Block: {latest_block:,}")
                working_rpcs += 1
            else:
                print(f"❌ {name:15} | Connection failed")
        except Exception as e:
            print(f"❌ {name:15} | Error: {str(e)[:30]}...")
    
    if working_rpcs > 0:
        print(f"\n✅ {working_rpcs}/{len(test_rpcs)} RPC endpoints working")
        return True
    else:
        print(f"\n❌ No RPC endpoints accessible")
        return False

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing Required Dependencies")
    print("-" * 40)
    
    required_packages = [
        'web3>=6.0.0',
        'python-dotenv>=0.19.0', 
        'flask>=2.0.0',
        'requests>=2.25.0',
        'pycryptodome>=3.15.0'
    ]
    
    try:
        import subprocess
        for package in required_packages:
            print(f"Installing {package}...")
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {package} installed successfully")
            else:
                print(f"❌ Failed to install {package}: {result.stderr}")
        return True
    except Exception as e:
        print(f"❌ Error installing dependencies: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🔥 COINCEEPER ETHEREUM ENVIRONMENT SETUP")
    print("=" * 45)
    print("Setting up environment for reliable Ethereum transactions")
    print()
    
    # Step 1: Install dependencies
    if input("Install required Python packages? (Y/n): ").lower() != 'n':
        install_dependencies()
    
    # Step 2: Create .env file
    print("\n" + "="*50)
    if input("Create/update .env file with API configuration? (Y/n): ").lower() != 'n':
        create_env_file()
    
    # Step 3: Check API keys
    print("\n" + "="*50)
    check_api_keys()
    
    # Step 4: Test connectivity
    print("\n" + "="*50)
    test_ethereum_connectivity()
    
    # Final recommendations
    print("\n🎯 SETUP COMPLETE - NEXT STEPS")
    print("=" * 35)
    print("1. ✅ Update .env file with your real API keys:")
    print("   - Get Alchemy key: https://www.alchemy.com/")
    print("   - Get Infura key: https://infura.io/")
    print("   - Get Etherscan key: https://etherscan.io/apis")
    print()
    print("2. ✅ Test the improved transaction system:")
    print("   python debug_transaction_params_improved.py")
    print()
    print("3. ✅ Run your application:")
    print("   systemctl restart gunicorn")
    print("   ./quick_test.sh")
    print()
    print("4. ✅ Monitor transactions:")
    print("   - Check logs for improved gas price calculations")
    print("   - Verify transactions appear on Etherscan")
    print("   - Confirm public mempool inclusion")
    
    print(f"\n🚀 Your Ethereum transaction system is now configured for success!")

if __name__ == "__main__":
    main()
