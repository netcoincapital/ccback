#!/usr/bin/env python3
"""
Webhook Batch Setup - Setup batch subscriptions for all user addresses grouped by blockchain
This script automatically:
1. Fetches all user wallet addresses from the database
2. Groups them by blockchain
3. Creates batch subscriptions (50 addresses per batch)
4. Outputs subscription IDs and statistics
"""

import sys
import os
import json
from dotenv import load_dotenv

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import logging configuration
from utils.logging_config import get_logger

# Import webhook modules
from webhook.webhook_handler import get_user_addresses_from_db
from webhook.tatum_subscription import (
    group_addresses_by_blockchain,
    create_batched_blockchain_subscriptions,
    list_subscriptions
)

# Configure logging
logger = get_logger(__file__)

# Load environment variables
load_dotenv()

def main():
    """Main function to setup batch webhooks"""
    print("🔧 Coinceeper Batch Webhook Setup")
    print("================================\n")
    
    # Check if Tatum API key is set
    from webhook.tatum_subscription import TATUM_API_KEY
    if not TATUM_API_KEY:
        print("❌ Error: TATUM_API_KEY not found in environment variables")
        print("Please set the TATUM_API_KEY environment variable and try again")
        sys.exit(1)
    
    # Step 1: Get all addresses
    print("📋 Step 1: Fetching user addresses from database...")
    user_addresses = get_user_addresses_from_db()
    
    if not user_addresses:
        print("❌ No user addresses found in database")
        print("Please add user addresses to the database first")
        sys.exit(1)
    
    print(f"✅ Found {len(user_addresses)} user addresses")
    
    # Step 2: Group addresses by blockchain
    print("\n📋 Step 2: Grouping addresses by blockchain...")
    grouped_addresses = group_addresses_by_blockchain(user_addresses)
    
    print("Address distribution by blockchain:")
    for blockchain, addresses in grouped_addresses.items():
        print(f"  • {blockchain}: {len(addresses)} addresses")
    
    # Step 3: Check existing subscriptions
    print("\n📋 Step 3: Checking existing subscriptions...")
    existing_subscriptions = list_subscriptions()
    
    if existing_subscriptions:
        existing_batch_count = sum(1 for sub in existing_subscriptions 
                                 if sub.get('type') == 'ADDRESS_TRANSACTION' 
                                 and 'addresses' in sub.get('attr', {}))
        
        if existing_batch_count > 0:
            print(f"⚠️ Warning: Found {existing_batch_count} existing batch subscriptions")
            confirmation = input("Do you want to continue and create additional subscriptions? (y/N): ")
            if confirmation.lower() != 'y':
                print("Operation cancelled.")
                sys.exit(0)
    
    # Step 4: Create batch subscriptions
    print("\n📋 Step 4: Creating batch subscriptions...")
    
    confirmation = input(f"This will create batch subscriptions for {len(user_addresses)} addresses across {len(grouped_addresses)} blockchains. Continue? (y/N): ")
    if confirmation.lower() != 'y':
        print("Operation cancelled.")
        sys.exit(0)
    
    print("\nCreating subscriptions, please wait...")
    results = create_batched_blockchain_subscriptions(user_addresses)
    
    # Step 5: Display results
    total_subscriptions = sum(len(subs) for subs in results.values())
    total_addresses = sum(sum(sub['addresses_count'] for sub in subs) for subs in results.values())
    
    print("\n🎉 Results Summary:")
    print(f"Created {total_subscriptions} batch subscriptions for {total_addresses} addresses across {len(results)} blockchains")
    
    print("\nDetailed results by blockchain:")
    for blockchain, subscriptions in results.items():
        print(f"\n{blockchain}:")
        for idx, sub in enumerate(subscriptions, 1):
            print(f"  {idx}. Batch of {sub['addresses_count']} addresses - ID: {sub['subscription_id']}")
    
    # Save results to file
    results_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_subscriptions.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_file}")
    print("\n✅ Batch webhook setup completed successfully")

if __name__ == "__main__":
    main() 