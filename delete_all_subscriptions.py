#!/usr/bin/env python3
import sys
import os
import argparse
import logging

# Add the current directory to sys.path to import modules from the project
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import the required functions
try:
    # Try direct imports first
    from webhook.tatum_subscription import list_subscriptions, delete_subscription
    from utils.logging_config import setup_logging, get_logger
except ImportError as e:
    print(f"Direct import failed: {str(e)}")
    try:
        # Try adding specific paths
        webhook_path = os.path.join(current_dir, 'webhook')
        utils_path = os.path.join(current_dir, 'utils')
        sys.path.insert(0, webhook_path)
        sys.path.insert(0, utils_path)
        
        import tatum_subscription
        import logging_config
        
        list_subscriptions = tatum_subscription.list_subscriptions
        delete_subscription = tatum_subscription.delete_subscription
        setup_logging = logging_config.setup_logging
        get_logger = logging_config.get_logger
        
    except ImportError as e2:
        print(f"Alternative import also failed: {str(e2)}")
        print("Available modules in current directory:")
        for item in os.listdir(current_dir):
            if os.path.isdir(os.path.join(current_dir, item)) and not item.startswith('.'):
                print(f"  - {item}/")
        sys.exit(1)

# Set up logging
logger = get_logger(__name__)

def delete_all_subscriptions(dry_run=False):
    """
    Delete all Tatum subscriptions with pagination support.
    
    Args:
        dry_run (bool): If True, only list subscriptions without deleting them
        
    Returns:
        tuple: (total_count, deleted_count, failed_count)
    """
    logger.info("Retrieving all active Tatum subscriptions with pagination")
    
    # Get all subscriptions with pagination
    all_subscriptions = []
    page = 0
    page_size = 50  # Tatum API default page size
    
    while True:
        logger.info(f"Fetching page {page + 1} (offset: {page * page_size})")
        
        # Get subscriptions for this page
        subscriptions = list_subscriptions(offset=page * page_size, limit=page_size)
        
        if not subscriptions:
            logger.info(f"No more subscriptions found at page {page + 1}")
            break
            
        all_subscriptions.extend(subscriptions)
        logger.info(f"Found {len(subscriptions)} subscriptions on page {page + 1}")
        
        # If we got less than page_size, we've reached the end
        if len(subscriptions) < page_size:
            logger.info("Reached last page")
            break
            
        page += 1
        
        # Safety check to prevent infinite loops
        if page > 200:  # Max 200 pages = 10,000 subscriptions
            logger.warning("Reached maximum page limit (200), stopping pagination")
            break
    
    total_count = len(all_subscriptions)
    logger.info(f"Found {total_count} total active subscriptions across {page + 1} pages")
    
    if dry_run:
        logger.info("Dry run mode: Subscriptions will not be deleted")
        # Print first 20 and last 20 subscription details for overview
        print(f"\n📊 OVERVIEW: Found {total_count} total subscriptions")
        print("First 20 subscriptions:")
        for idx, sub in enumerate(all_subscriptions[:20], 1):
            sub_id = sub.get('id', 'Unknown')
            sub_type = sub.get('type', 'Unknown')
            
            # Get address and chain if available
            address = sub.get('attr', {}).get('address', 'N/A')
            chain = sub.get('attr', {}).get('chain', 'N/A')
            
            print(f"  {idx}. ID: {sub_id}, Type: {sub_type}, Chain: {chain}, Address: {address[:20]}...")
        
        if total_count > 40:
            print(f"\n... ({total_count - 40} subscriptions in between) ...\n")
            print("Last 20 subscriptions:")
            for idx, sub in enumerate(all_subscriptions[-20:], total_count - 19):
                sub_id = sub.get('id', 'Unknown')
                sub_type = sub.get('type', 'Unknown')
                
                address = sub.get('attr', {}).get('address', 'N/A')
                chain = sub.get('attr', {}).get('chain', 'N/A')
                
                print(f"  {idx}. ID: {sub_id}, Type: {sub_type}, Chain: {chain}, Address: {address[:20]}...")
        elif total_count > 20:
            print("\nRemaining subscriptions:")
            for idx, sub in enumerate(all_subscriptions[20:], 21):
                sub_id = sub.get('id', 'Unknown')
                sub_type = sub.get('type', 'Unknown')
                
                address = sub.get('attr', {}).get('address', 'N/A')
                chain = sub.get('attr', {}).get('chain', 'N/A')
                
                print(f"  {idx}. ID: {sub_id}, Type: {sub_type}, Chain: {chain}, Address: {address[:20]}...")
        
        return total_count, 0, 0
    
    # Delete each subscription with progress tracking
    deleted_count = 0
    failed_count = 0
    
    print(f"\n🗑️  Starting deletion of {total_count} subscriptions...")
    
    for idx, sub in enumerate(all_subscriptions, 1):
        sub_id = sub.get('id')
        if not sub_id:
            logger.warning(f"Subscription at index {idx} has no ID, skipping")
            failed_count += 1
            continue
        
        # Get address and chain for logging
        address = sub.get('attr', {}).get('address', 'N/A')
        chain = sub.get('attr', {}).get('chain', 'N/A')
        
        # Show progress every 100 deletions
        if idx % 100 == 0 or idx <= 10 or idx >= total_count - 10:
            logger.info(f"Deleting subscription {idx}/{total_count}: ID={sub_id}, Chain={chain}, Address={address[:30]}...")
        
        success = delete_subscription(sub_id)
        
        if success:
            deleted_count += 1
            if idx % 100 == 0 or idx <= 10 or idx >= total_count - 10:
                print(f"✅ Deleted subscription {idx}/{total_count}: {sub_id}")
        else:
            failed_count += 1
            print(f"❌ Failed to delete subscription {idx}/{total_count}: {sub_id}")
        
        # Show progress every 500 subscriptions
        if idx % 500 == 0:
            progress_percent = (idx / total_count) * 100
            print(f"\n📊 Progress: {idx}/{total_count} ({progress_percent:.1f}%) - Deleted: {deleted_count}, Failed: {failed_count}")
    
    logger.info(f"FINAL RESULT: Deleted {deleted_count}/{total_count} subscriptions, Failed: {failed_count}")
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