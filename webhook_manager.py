#!/usr/bin/env python3
"""
Webhook Manager - A tool for managing Tatum smart contract subscriptions
"""

import argparse
import json
import os
import sys
from dotenv import load_dotenv

# Import our webhook management modules
from webhook.tatum_subscription import (
    create_contract_subscription,
    list_subscriptions,
    delete_subscription,
    create_address_subscription,
    create_batch_subscriptions,
    create_batched_blockchain_subscriptions,
    group_addresses_by_blockchain
)

# Import DB functions to get user addresses
from webhook.webhook_handler import get_user_addresses_from_db

# Import the logging configuration
from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)

# Load environment variables
load_dotenv()

def create_subscription(args):
    """Create a new subscription"""
    try:
        if args.type == 'contract':
            logger.info(f"Creating contract subscription for address {args.address} on chain {args.chain}")
            result = create_contract_subscription(
                address=args.address,
                chain=args.chain,
                webhook_url=args.webhook_url
            )
        elif args.type == 'address':
            logger.info(f"Creating address subscription for wallet {args.address} on chain {args.chain}")
            result = create_address_subscription(
                address=args.address,
                chain=args.chain,
                webhook_url=args.webhook_url
            )
        else:
            logger.error(f"Invalid subscription type: {args.type}")
            print(f"❌ Invalid subscription type: {args.type}")
            return
            
        if result and 'id' in result:
            logger.info(f"Successfully created {args.type} subscription with ID: {result.get('id')}")
            print(f"✅ Successfully created {args.type} subscription")
            print(f"📋 Subscription ID: {result.get('id')}")
        else:
            logger.error(f"Failed to create {args.type} subscription for {args.address} on {args.chain}")
            print(f"❌ Failed to create {args.type} subscription")
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        print(f"❌ Error: {str(e)}")

def list_all_subscriptions(args):
    """List all active subscriptions"""
    logger.info("Retrieving all active subscriptions")
    subscriptions = list_subscriptions()
    
    if not subscriptions:
        logger.info("No active subscriptions found")
        print("No active subscriptions found.")
        return
    
    logger.info(f"Found {len(subscriptions)} active subscriptions")
    print(f"📋 Found {len(subscriptions)} active subscriptions:")
    
    for idx, sub in enumerate(subscriptions, 1):
        sub_type = sub.get('type', 'Unknown')
        sub_id = sub.get('id', 'Unknown')
        
        if sub_type == 'CONTRACT_LOG_EVENT':
            address = sub.get('attr', {}).get('address', 'Unknown')
            chain = sub.get('attr', {}).get('chain', 'Unknown')
            logger.debug(f"Subscription #{idx}: Contract {address} on {chain} (ID: {sub_id})")
            print(f"{idx}. 📄 Contract: {address} on {chain} (ID: {sub_id})")
        elif sub_type == 'ADDRESS_TRANSACTION':
            # Check if it's a batch subscription (has addresses array)
            addresses = sub.get('attr', {}).get('addresses', [])
            if addresses:
                address_count = len(addresses)
                chain = sub.get('attr', {}).get('chain', 'Unknown')
                logger.debug(f"Subscription #{idx}: Batch with {address_count} addresses on {chain} (ID: {sub_id})")
                print(f"{idx}. 👥 Batch: {address_count} addresses on {chain} (ID: {sub_id})")
                if args.verbose and address_count > 0:
                    print(f"   First address: {addresses[0]}")
                    print(f"   Last address: {addresses[-1]}")
            else:
                address = sub.get('attr', {}).get('address', 'Unknown')
                chain = sub.get('attr', {}).get('chain', 'Unknown')
                logger.debug(f"Subscription #{idx}: Address {address} on {chain} (ID: {sub_id})")
                print(f"{idx}. 👛 Address: {address} on {chain} (ID: {sub_id})")
        else:
            logger.warning(f"Unknown subscription type: {sub_type} with ID: {sub_id}")
            print(f"{idx}. ❓ Unknown type: {sub_type} (ID: {sub_id})")

def remove_subscription(args):
    """Delete a subscription by ID"""
    logger.info(f"Attempting to delete subscription with ID: {args.id}")
    success = delete_subscription(args.id)
    
    if success:
        logger.info(f"Successfully deleted subscription {args.id}")
        print(f"✅ Successfully deleted subscription {args.id}")
    else:
        logger.error(f"Failed to delete subscription {args.id}")
        print(f"❌ Failed to delete subscription {args.id}")
        sys.exit(1)

def batch_create(args):
    """Create multiple subscriptions from a JSON file"""
    logger.info(f"Loading batch subscription config from file: {args.file}")
    try:
        with open(args.file, 'r') as f:
            contracts_config = json.load(f)
    except Exception as e:
        logger.error(f"Error loading config file {args.file}: {str(e)}")
        print(f"❌ Error loading config file: {str(e)}")
        sys.exit(1)
    
    if not isinstance(contracts_config, list):
        logger.error("Config file must contain a JSON array of contract configs")
        print("❌ Config file must contain a JSON array of contract configs")
        sys.exit(1)
    
    logger.info(f"Creating {len(contracts_config)} subscriptions in batch mode")
    print(f"📝 Creating {len(contracts_config)} subscriptions...")
    results = create_batch_subscriptions(contracts_config)
    
    success_count = sum(1 for result in results.values() if isinstance(result, dict) and result.get('status') == 'success')
    fail_count = len(results) - success_count
    
    logger.info(f"Batch creation completed: {success_count} successful, {fail_count} failed")
    print(f"✅ Created {success_count} subscriptions successfully")
    if fail_count > 0:
        logger.warning(f"Failed to create {fail_count} subscriptions")
        print(f"❌ Failed to create {fail_count} subscriptions")
    
    if args.verbose:
        logger.debug("Displaying detailed batch creation results")
        print("\n📋 Detailed results:")
        for address, result in results.items():
            if isinstance(result, dict) and result.get('status') == 'success':
                logger.debug(f"Success: {address} with ID {result.get('subscription_id')}")
                print(f"✅ {address}: {result.get('subscription_id')}")
            else:
                logger.debug(f"Failed: {address} with error {result}")
                print(f"❌ {address}: {result}")

def batch_address_create(args):
    """Create batch subscriptions for user addresses grouped by blockchain"""
    logger.info("Creating batch subscriptions for user wallet addresses")
    print("📊 Analyzing user addresses by blockchain...")
    
    # Get all user addresses from the database
    user_addresses = get_user_addresses_from_db()
    
    if not user_addresses:
        logger.error("No user addresses found in database")
        print("❌ No user addresses found in database")
        sys.exit(1)
    
    # Group addresses by blockchain
    grouped_addresses = group_addresses_by_blockchain(user_addresses)
    
    # Show summary of addresses by blockchain
    print("\n📋 Address distribution by blockchain:")
    for blockchain, addresses in grouped_addresses.items():
        print(f"  • {blockchain}: {len(addresses)} addresses")
    
    # Confirmation
    if not args.force:
        confirmation = input(f"\n⚠️ This will create batch subscriptions for {len(user_addresses)} addresses across {len(grouped_addresses)} blockchains. Continue? (y/N): ")
        if confirmation.lower() != 'y':
            print("Operation cancelled.")
            sys.exit(0)
    
    # Create batch subscriptions
    results = create_batched_blockchain_subscriptions(user_addresses, args.webhook_url)
    
    # Display results
    total_subscriptions = sum(len(subs) for subs in results.values())
    total_addresses = sum(sum(sub['addresses_count'] for sub in subs) for subs in results.values())
    
    print(f"\n✅ Created {total_subscriptions} batch subscriptions for {total_addresses} addresses across {len(results)} blockchains")
    
    if args.verbose:
        print("\n📋 Detailed results by blockchain:")
        for blockchain, subscriptions in results.items():
            print(f"\n{blockchain}:")
            for idx, sub in enumerate(subscriptions, 1):
                print(f"  {idx}. Batch of {sub['addresses_count']} addresses - ID: {sub['subscription_id']}")

def main():
    """Main entry point for the webhook manager"""
    logger.info("Starting Webhook Manager")
    parser = argparse.ArgumentParser(description='Webhook Manager - A tool for managing Tatum smart contract subscriptions')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Create subscription command
    create_parser = subparsers.add_parser('create', help='Create a new subscription')
    create_parser.add_argument('--type', required=True, choices=['contract', 'address'],
                             help='Type of subscription to create')
    create_parser.add_argument('--chain', required=True, 
                             help='Blockchain to monitor (Ethereum, Binance Smart Chain, etc.)')
    create_parser.add_argument('--address', required=True, help='Contract or wallet address to monitor')
    create_parser.add_argument('--webhook-url', required=True, help='Webhook URL to receive notifications')
    create_parser.set_defaults(func=create_subscription)
    
    # List subscriptions command
    list_parser = subparsers.add_parser('list', help='List all active subscriptions')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='Show more details for batch subscriptions')
    list_parser.set_defaults(func=list_all_subscriptions)
    
    # Delete subscription command
    delete_parser = subparsers.add_parser('delete', help='Delete a subscription')
    delete_parser.add_argument('id', help='Subscription ID to delete')
    delete_parser.set_defaults(func=remove_subscription)
    
    # Batch create command
    batch_parser = subparsers.add_parser('batch', help='Create multiple subscriptions from a JSON file')
    batch_parser.add_argument('file', help='Path to JSON config file')
    batch_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed results')
    batch_parser.set_defaults(func=batch_create)
    
    # Batch address create command
    batch_address_parser = subparsers.add_parser('batch-addresses', help='Create batch subscriptions for all user addresses grouped by blockchain')
    batch_address_parser.add_argument('--webhook-url', help='Custom webhook URL (optional)')
    batch_address_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed results')
    batch_address_parser.add_argument('--force', '-f', action='store_true', help='Skip confirmation')
    batch_address_parser.set_defaults(func=batch_address_create)
    
    args = parser.parse_args()
    
    if not args.command:
        logger.warning("No command specified, showing help")
        parser.print_help()
        sys.exit(1)
    
    logger.debug(f"Executing command: {args.command}")
    args.func(args)

if __name__ == '__main__':
    main() 