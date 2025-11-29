#!/usr/bin/env python3
"""
Quick test to verify TEE creation and status checking
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:5000/api/tee"
API_KEY_ALICE = "_y85Td_uz4mwE0rNOEUCkxU3WzYqT1RqKj8Vwsle2nlYiCOK3QePzf1uz3vgBhlz"

headers = {"Authorization": f"Bearer {API_KEY_ALICE}"}

def main():
    print("Testing TEE Creation and Status Updates")
    print("=" * 60)
    
    # Clean up old test TEEs first
    print("\n0. Cleaning up old test TEEs...")
    response = requests.get(f"{BASE_URL}/environments", headers=headers)
    if response.status_code == 200:
        tees = response.json().get('tees', [])
        for tee in tees:
            if 'test' in tee['name'].lower() or tee['status'] in ['error', 'creating']:
                print(f"  Deleting old TEE {tee['id']}: {tee['name']}")
                requests.delete(f"{BASE_URL}/environments/{tee['id']}", headers=headers)
        if tees:
            time.sleep(5)  # Wait for cleanup
    
    # Create TEE
    print("\n1. Creating TEE...")
    tee_data = {
        "name": "Test Healthcare TEE",
        "description": "Testing TEE creation and status updates",
        "gcp_project_id": "permissible-468314",
        "gcp_zone": "us-central1-a",
        "allow_cross_party_joins": True,
        "require_unanimous_approval": True,
        "participant_emails": ["bob@hospital-b.org"]
    }
    
    response = requests.post(
        f"{BASE_URL}/environments",
        headers=headers,
        json=tee_data
    )
    
    if response.status_code != 201:
        print(f"❌ Failed to create TEE: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return
    
    result = response.json()
    tee_id = result['tee']['id']
    status = result['tee']['status']
    instance_id = result['tee'].get('gcp_instance_id')
    
    print(f"✓ TEE created: ID={tee_id}, Status={status}, Instance={instance_id}")
    
    # Poll for status updates
    print(f"\n2. Polling TEE status (will check every 5 seconds for 60 seconds)...")
    max_attempts = 12
    
    for i in range(max_attempts):
        time.sleep(5)
        
        response = requests.get(
            f"{BASE_URL}/environments/{tee_id}",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get TEE status: {response.status_code}")
            continue
        
        tee = response.json()['tee']
        status = tee['status']
        print(f"  [{i+1}/{max_attempts}] Status: {status}")
        
        if status == 'active':
            print(f"\n✓ TEE is now ACTIVE!")
            print(f"  Instance ID: {tee['gcp_instance_id']}")
            print(f"  Activated at: {tee.get('activated_at', 'N/A')}")
            return
        elif status == 'error':
            print(f"\n❌ TEE creation failed")
            print(json.dumps(tee, indent=2))
            return
    
    print(f"\n⏱️  Timeout: TEE still in '{status}' status after 60 seconds")
    print("The VM may still be provisioning. Check GCP Console or wait longer.")

if __name__ == '__main__':
    main()
