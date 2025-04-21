#!/usr/bin/env python3
import sys
import os
import argparse
import logging

# Add the parent directory to sys.path to import modules from the project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the required functions
try:
    from webhook.tatum_subscription import list_subscriptions, delete_subscription
    from utils.logging_config import setup_logging, get_logger
except ImportError as e:
    print(f"Error importing modules: {str(e)}")
    print("Make sure to run this script from the project root directory")
    sys.exit(1)

# Set up logging
logger = get_logger(__name__)

def delete_all_subscriptions(dry_run=False):
    """
    Delete all Tatum subscriptions.
    
    Args:
        dry_run (bool): If True, only list subscriptions without deleting them
        
    Returns:
        tuple: (total_count, deleted_count, failed_count)
    """
    logger.info("Retrieving all active Tatum subscriptions")
    
    # Get all subscriptions
    subscriptions = list_subscriptions()
    
    if not subscriptions:
        logger.info("No active subscriptions found")
        return 0, 0, 0
    
    total_count = len(subscriptions)
    logger.info(f"Found {total_count} active subscriptions")
    
    if dry_run:
        logger.info("Dry run mode: Subscriptions will not be deleted")
        # Print subscription details
        for idx, sub in enumerate(subscriptions, 1):
            sub_id = sub.get('id', 'Unknown')
            sub_type = sub.get('type', 'Unknown')
            
            # Get address and chain if available
            address = sub.get('attr', {}).get('address', 'N/A')
            chain = sub.get('attr', {}).get('chain', 'N/A')
            
            print(f"{idx}. ID: {sub_id}, Type: {sub_type}, Chain: {chain}, Address: {address}")
        
        return total_count, 0, 0
    
    # Delete each subscription
    deleted_count = 0
    failed_count = 0
    
    for idx, sub in enumerate(subscriptions, 1):
        sub_id = sub.get('id')
        if not sub_id:
            logger.warning(f"Subscription at index {idx} has no ID, skipping")
            failed_count += 1
            continue
        
        # Get address and chain for logging
        address = sub.get('attr', {}).get('address', 'N/A')
        chain = sub.get('attr', {}).get('chain', 'N/A')
        
        logger.info(f"Deleting subscription {idx}/{total_count}: ID={sub_id}, Chain={chain}, Address={address}")
        
        success = delete_subscription(sub_id)
        
        if success:
            deleted_count += 1
            print(f"✅ Deleted subscription {idx}/{total_count}: {sub_id}")
        else:
            failed_count += 1
            print(f"❌ Failed to delete subscription {idx}/{total_count}: {sub_id}")
    
    logger.info(f"Deleted {deleted_count}/{total_count} subscriptions, Failed: {failed_count}")
    return total_count, deleted_count, failed_count

def main():
    """Main function to parse arguments and execute deletion"""
    parser = argparse.ArgumentParser(description='Delete all Tatum subscriptions')
    parser.add_argument('--dry-run', action='store_true', help='Only list subscriptions without deleting them')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging()
    
    if args.dry_run:
        print("DRY RUN MODE: Subscriptions will only be listed, not deleted")
        total, _, _ = delete_all_subscriptions(dry_run=True)
        print(f"Total subscriptions: {total}")
        return
    
    # Confirmation prompt unless --yes flag is used
    if not args.yes:
        print("⚠️  WARNING: This will delete ALL Tatum subscriptions! ⚠️")
        print("This action cannot be undone.")
        confirmation = input("Are you sure you want to continue? (yes/no): ")
        
        if confirmation.lower() not in ['yes', 'y']:
            print("Operation cancelled.")
            return
    
    # Delete all subscriptions
    total, deleted, failed = delete_all_subscriptions(dry_run=False)
    
    print("\n--- Summary ---")
    print(f"Total subscriptions found: {total}")
    print(f"Successfully deleted: {deleted}")
    print(f"Failed to delete: {failed}")
    
    if failed > 0:
        print("\nSome subscriptions could not be deleted. Check the logs for details.")
        sys.exit(1)
    else:
        print("\nAll subscriptions were successfully deleted.")

if __name__ == "__main__":
    main() 