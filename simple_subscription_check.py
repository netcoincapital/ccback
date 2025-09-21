#!/usr/bin/env python3
"""
Simple script to check Tatum subscriptions without complex imports
"""
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Tatum API key
TATUM_API_KEY = os.getenv('TATUM_API_KEY')
if not TATUM_API_KEY:
    print("❌ TATUM_API_KEY not found in environment variables")
    exit(1)

print(f"✅ Found Tatum API key: {TATUM_API_KEY[:10]}...")

# Tatum API base URL
TATUM_API_BASE_URL = "https://api.tatum.io/v3"

def count_all_subscriptions():
    """Count total subscriptions with pagination"""
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }
    
    total_count = 0
    page = 0
    page_size = 50
    
    print("🔍 Counting total subscriptions...")
    
    while True:
        offset = page * page_size
        url = f"{TATUM_API_BASE_URL}/subscription?pageSize={page_size}&offset={offset}"
        
        print(f"📄 Checking page {page + 1} (offset: {offset})...")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                break
                
            subscriptions = response.json()
            count = len(subscriptions)
            total_count += count
            
            print(f"   Found {count} subscriptions on page {page + 1}")
            
            # If we got less than page_size, we've reached the end
            if count < page_size:
                print(f"✅ Reached last page (page {page + 1})")
                break
                
            page += 1
            
            # Safety limit
            if page > 200:  # Max 10,000 subscriptions
                print("⚠️ Reached safety limit (200 pages)")
                break
                
        except Exception as e:
            print(f"❌ Error on page {page + 1}: {str(e)}")
            break
    
    return total_count

def delete_all_subscriptions():
    """Delete all subscriptions"""
    headers = {
        "x-api-key": TATUM_API_KEY
    }
    
    deleted_count = 0
    page = 0
    
    print("🗑️ Starting deletion process...")
    
    while True:
        # Always fetch from page 0 since items get deleted
        url = f"{TATUM_API_BASE_URL}/subscription?pageSize=50"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                break
                
            subscriptions = response.json()
            
            if not subscriptions:
                print("✅ No more subscriptions found")
                break
                
            print(f"📄 Found {len(subscriptions)} subscriptions, deleting...")
            
            # Delete each subscription
            for i, sub in enumerate(subscriptions):
                sub_id = sub.get('id')
                if not sub_id:
                    continue
                    
                try:
                    delete_response = requests.delete(
                        f"{TATUM_API_BASE_URL}/subscription/{sub_id}",
                        headers=headers,
                        timeout=30
                    )
                    
                    if delete_response.status_code == 204:
                        deleted_count += 1
                        if (deleted_count % 100 == 0) or (i + 1) % 10 == 0:
                            print(f"✅ Deleted {deleted_count} subscriptions...")
                    else:
                        print(f"❌ Failed to delete {sub_id}: {delete_response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Error deleting {sub_id}: {str(e)}")
            
            page += 1
            
            # Safety limit
            if page > 200:
                print("⚠️ Reached safety limit")
                break
                
        except Exception as e:
            print(f"❌ Error on page {page + 1}: {str(e)}")
            break
    
    return deleted_count

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
        print("🧪 DRY RUN MODE - Only counting subscriptions")
        total = count_all_subscriptions()
        print(f"\n📊 TOTAL SUBSCRIPTIONS: {total}")
        return
    
    # Ask for confirmation
    print("⚠️ WARNING: This will delete ALL Tatum subscriptions!")
    print("This action cannot be undone.")
    confirm = input("Type 'DELETE_ALL' to confirm: ")
    
    if confirm != 'DELETE_ALL':
        print("❌ Operation cancelled")
        return
    
    # Delete all subscriptions
    deleted = delete_all_subscriptions()
    print(f"\n🎯 FINAL RESULT: Deleted {deleted} subscriptions")

if __name__ == "__main__":
    main()
