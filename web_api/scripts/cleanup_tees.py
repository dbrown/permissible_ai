#!/usr/bin/env python3
"""
Cleanup script to delete old TEEs and terminate their GCP instances

This helps prevent runaway costs from test VMs left running.
"""
import requests
import json
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000/api/tee"
API_KEY_ALICE = "_y85Td_uz4mwE0rNOEUCkxU3WzYqT1RqKj8Vwsle2nlYiCOK3QePzf1uz3vgBhlz"

headers = {"Authorization": f"Bearer {API_KEY_ALICE}"}


def cleanup_tees(dry_run=False, delete_all=False):
    """
    Clean up TEEs
    
    Args:
        dry_run: If True, only show what would be deleted
        delete_all: If True, delete all TEEs (otherwise only test/error TEEs)
    """
    print("TEE Cleanup Utility")
    print("=" * 60)
    
    # Get all TEEs
    response = requests.get(f"{BASE_URL}/environments", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch TEEs: {response.status_code}")
        return
    
    tees = response.json().get('tees', [])
    
    if not tees:
        print("✓ No TEEs found")
        return
    
    print(f"\nFound {len(tees)} TEE(s):\n")
    
    to_delete = []
    
    for tee in tees:
        print(f"TEE {tee['id']}: {tee['name']}")
        print(f"  Status: {tee['status']}")
        print(f"  Instance: {tee.get('gcp_instance_id', 'None')}")
        print(f"  Created: {tee.get('created_at', 'Unknown')}")
        
        should_delete = False
        reason = ""
        
        if delete_all:
            should_delete = True
            reason = "delete_all flag"
        elif tee['status'] in ['error']:
            should_delete = True
            reason = f"status is '{tee['status']}'"
        elif 'test' in tee['name'].lower():
            should_delete = True
            reason = "name contains 'test'"
        elif tee['status'] == 'creating':
            # Check age - delete if creating for more than 10 minutes
            try:
                created = datetime.fromisoformat(tee['created_at'].replace('Z', '+00:00'))
                age = datetime.now(created.tzinfo) - created
                if age > timedelta(minutes=10):
                    should_delete = True
                    reason = f"stuck in 'creating' for {age.seconds // 60} minutes"
            except:
                pass
        
        if should_delete:
            to_delete.append((tee['id'], tee['name'], reason))
            print(f"  → Will DELETE ({reason})")
        else:
            print(f"  → Keep")
        
        print()
    
    if not to_delete:
        print("✓ No TEEs to delete")
        return
    
    print("=" * 60)
    print(f"Will delete {len(to_delete)} TEE(s)")
    print("=" * 60)
    
    if dry_run:
        print("\n[DRY RUN] No actual deletions performed")
        return
    
    # Confirm deletion
    if not delete_all:
        confirm = input("\nProceed with deletion? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled")
            return
    
    print("\nDeleting TEEs...")
    success_count = 0
    
    for tee_id, name, reason in to_delete:
        print(f"\nDeleting TEE {tee_id}: {name}")
        print(f"  Reason: {reason}")
        
        response = requests.delete(
            f"{BASE_URL}/environments/{tee_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"  ✓ Deleted successfully")
            success_count += 1
        else:
            print(f"  ❌ Failed: {response.status_code}")
            try:
                print(f"  Error: {response.json().get('error', 'Unknown')}")
            except:
                pass
    
    print("\n" + "=" * 60)
    print(f"Cleanup complete: {success_count}/{len(to_delete)} TEEs deleted")
    print("=" * 60)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up old TEEs')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--all', action='store_true',
                       help='Delete ALL TEEs (use with caution!)')
    
    args = parser.parse_args()
    
    cleanup_tees(dry_run=args.dry_run, delete_all=args.all)
