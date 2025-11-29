"""
Example usage of the Shared TEE API

This script demonstrates the complete workflow of:
1. Creating a collaboration session (instant - no VM provisioning)
2. Uploading datasets from multiple parties
3. Submitting and approving a query
4. Retrieving results

Prerequisites:
- Running Flask application
- Valid API keys for multiple users

DEVELOPMENT MODE:
This example runs in development mode WITHOUT requiring actual GCP infrastructure:

1. Dataset Upload Warnings (EXPECTED):
   - References to GCS buckets (hospital-a-data, hospital-b-data) don't exist
   - API will show warning: "Dataset record created but encryption failed"
   - This is NORMAL - datasets are still created and usable for testing
   
2. Query Execution:
   - Uses mock execution instead of real TEE infrastructure
   - Generates sample results automatically
   - Demonstrates the full approval and execution workflow

3. Production Setup:
   - Create actual GCS buckets for dataset storage
   - Deploy shared TEE service on GCP Confidential Computing
   - Configure KMS encryption keys
   - Replace mock execution with real TEE calls

The warnings you see are EXPECTED and do not indicate a problem with the workflow.
"""
import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5000/api/tee"
SESSIONS_URL = f"{BASE_URL}/sessions"
API_KEY_ALICE = "_y85Td_uz4mwE0rNOEUCkxU3WzYqT1RqKj8Vwsle2nlYiCOK3QePzf1uz3vgBhlz"
API_KEY_BOB = "R6VakK6j3SzKMk12Rc-zolNdGFZbBo1vpnsZ4DLHwFjDzJxIy4Gvrj12SyBSbDxH"

headers_alice = {"Authorization": f"Bearer {API_KEY_ALICE}"}
headers_bob = {"Authorization": f"Bearer {API_KEY_BOB}"}


def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)


def cleanup_old_sessions():
    """Clean up old test collaboration sessions"""
    print("\n0. Cleaning up old test sessions...")
    
    # Get all sessions
    response = requests.get(
        SESSIONS_URL,
        headers=headers_alice
    )
    
    if response.status_code != 200:
        print("  Could not fetch sessions")
        return
    
    sessions = response.json().get('sessions', [])
    
    # Close old test sessions
    closed_count = 0
    for session in sessions:
        # Close if it's a test session
        if 'test' in session['name'].lower() or 'healthcare' in session['name'].lower():
            print(f"  Closing session {session['id']}: {session['name']} (status: {session['status']})")
            response = requests.delete(
                f"{SESSIONS_URL}/{session['id']}",
                headers=headers_alice
            )
            if response.status_code == 200:
                closed_count += 1
            else:
                print(f"    Failed: {response.status_code}")
    
    if closed_count > 0:
        print(f"✓ Closed {closed_count} old session(s)")
    else:
        print("  No old sessions to clean up")


def main():
    print("Shared TEE API Workflow Example")
    print("=" * 60)
    print("\n⚠️  DEVELOPMENT MODE - Expected Warnings:")
    print("   • Dataset encryption warnings (GCS buckets don't exist)")
    print("   • Using mock data and simulated TEE execution")
    print("   • This is NORMAL for development - workflow will complete successfully\n")
    print("=" * 60)
    
    # Step 0: Clean up old test sessions
    cleanup_old_sessions()
    
    # Step 1: Create collaboration session (Alice as creator)
    print("\n1. Creating collaboration session (Alice)...")
    session_data = {
        "name": "Healthcare Research Collaboration",
        "description": "Multi-hospital patient outcomes study",
        "allow_cross_party_joins": True,
        "require_unanimous_approval": True,
        "participant_emails": ["bob@hospital-b.org"]  # Bob's email
    }
    
    response = requests.post(
        SESSIONS_URL,
        headers=headers_alice,
        json=session_data
    )
    print_response("Session Creation Response", response)
    
    if response.status_code != 201:
        print("Failed to create session. Exiting.")
        return
    
    session_id = response.json()['session']['id']
    print(f"\n✓ Collaboration session created with ID: {session_id}")
    print("  (Instant creation - no VM provisioning needed with shared TEE!)")
    
    # Verify session is active
    response = requests.get(
        f"{SESSIONS_URL}/{session_id}",
        headers=headers_alice
    )
    if response.status_code == 200:
        status = response.json()['session']['status']
        print(f"  Session status: {status}")
    
    # Step 2: Alice uploads her dataset
    print("\n2. Alice uploading dataset...")
    dataset_alice = {
        "name": "Hospital A Patient Data",
        "description": "De-identified patient records Q4 2024",
        "schema": {
            "columns": [
                {"name": "patient_id", "type": "string"},
                {"name": "diagnosis_code", "type": "string"},
                {"name": "treatment_outcome", "type": "string"}
            ]
        },
        "gcs_bucket": "hospital-a-data",
        "gcs_path": "patients/2024-q4.csv"
    }
    
    response = requests.post(
        f"{SESSIONS_URL}/{session_id}/datasets",
        headers=headers_alice,
        json=dataset_alice
    )
    print_response("Dataset Upload (Alice)", response)
    
    if response.status_code != 201:
        print("Failed to upload Alice's dataset. Exiting.")
        return
    
    dataset_alice_id = response.json()['dataset']['id']
    print(f"\n✓ Alice's dataset uploaded with ID: {dataset_alice_id}")
    
    # Note about encryption warning
    if 'warning' in response.json():
        print("  ℹ️  Encryption warning is expected (development mode - no real GCS buckets)")
    
    # Step 3: Bob uploads his dataset
    print("\n3. Bob uploading dataset...")
    dataset_bob = {
        "name": "Hospital B Patient Data",
        "description": "De-identified patient records Q4 2024",
        "schema": {
            "columns": [
                {"name": "patient_id", "type": "string"},
                {"name": "diagnosis_code", "type": "string"},
                {"name": "treatment_outcome", "type": "string"}
            ]
        },
        "gcs_bucket": "hospital-b-data",
        "gcs_path": "patients/2024-q4.csv"
    }
    
    response = requests.post(
        f"{SESSIONS_URL}/{session_id}/datasets",
        headers=headers_bob,
        json=dataset_bob
    )
    print_response("Dataset Upload (Bob)", response)
    
    if response.status_code != 201:
        print("Failed to upload Bob's dataset. Exiting.")
        return
    
    dataset_bob_id = response.json()['dataset']['id']
    print(f"\n✓ Bob's dataset uploaded with ID: {dataset_bob_id}")
    
    # Note about encryption warning
    if 'warning' in response.json():
        print("  ℹ️  Encryption warning is expected (development mode - no real GCS buckets)")
    
    # Step 4: Marking datasets as available (simulating encryption completion)
    print("\n4. Marking datasets as available...")
    
    response = requests.post(
        f"{BASE_URL}/datasets/{dataset_alice_id}/mark-available",
        headers=headers_alice
    )
    print(f"Alice's dataset: {response.status_code}")
    
    response = requests.post(
        f"{BASE_URL}/datasets/{dataset_bob_id}/mark-available",
        headers=headers_bob
    )
    print(f"Bob's dataset: {response.status_code}")
    
    # Step 5: Alice submits a query
    print("\n5. Alice submitting query...")
    query_data = {
        "name": "Cross-hospital readmission analysis",
        "description": "Calculate 30-day readmission rates by diagnosis",
        "query_text": """
            SELECT 
                diagnosis_code,
                COUNT(*) as total_cases,
                SUM(CASE WHEN treatment_outcome = 'readmitted' THEN 1 ELSE 0 END) as readmissions,
                ROUND(100.0 * SUM(CASE WHEN treatment_outcome = 'readmitted' THEN 1 ELSE 0 END) / COUNT(*), 2) as readmission_rate
            FROM 
                (SELECT * FROM dataset_{} UNION ALL SELECT * FROM dataset_{})
            GROUP BY diagnosis_code
            HAVING COUNT(*) >= 10
            ORDER BY readmission_rate DESC
        """.format(dataset_alice_id, dataset_bob_id),
        "accesses_datasets": [dataset_alice_id, dataset_bob_id],
        "privacy_level": "aggregate_only"
    }
    
    response = requests.post(
        f"{SESSIONS_URL}/{session_id}/queries",
        headers=headers_alice,
        json=query_data
    )
    print_response("Query Submission", response)
    
    if response.status_code != 201:
        print("Failed to submit query. Exiting.")
        return
    
    query_id = response.json()['query']['id']
    print(f"\n✓ Query submitted with ID: {query_id}")
    
    # Step 6: Both Alice and Bob review and approve the query
    print("\n6. Reviewing query...")
    
    # Get query details
    response = requests.get(
        f"{BASE_URL}/queries/{query_id}",
        headers=headers_alice
    )
    print_response("Query Details", response)
    
    # Alice approves
    print("\n7. Alice approving query...")
    approval_data = {
        "notes": "Verified - query only returns aggregated statistics with k-anonymity (k>=10)"
    }
    
    response = requests.post(
        f"{BASE_URL}/queries/{query_id}/approve",
        headers=headers_alice,
        json=approval_data
    )
    print_response("Alice's Approval", response)
    
    if response.status_code != 200:
        print("Failed to approve query as Alice. Exiting.")
        return
    
    # Check if query needs more approvals
    response_data = response.json()
    approvals = response_data.get('approvals', '0/0')
    print(f"\nApprovals: {approvals}")
    
    # Bob approves
    print("\n8. Bob approving query...")
    approval_data = {
        "notes": "Approved - no individual patient data exposed"
    }
    
    response = requests.post(
        f"{BASE_URL}/queries/{query_id}/approve",
        headers=headers_bob,
        json=approval_data
    )
    print_response("Bob's Approval", response)
    
    if response.status_code != 200:
        print("Failed to approve query as Bob. Exiting.")
        return
    
    # Check final status
    response_data = response.json()
    print(f"\n✓ Query fully approved: {response_data.get('message')}")
    
    # Step 9: Check query status (should be completed after all approvals in dev mode)
    print("\n9. Checking query status...")
    response = requests.get(
        f"{BASE_URL}/queries/{query_id}",
        headers=headers_alice
    )
    
    if response.status_code == 200:
        query_status = response.json()['query']['status']
        print(f"Query status: {query_status}")
    
    # Step 10: Retrieve results
    print("\n10. Retrieving query results...")
    response = requests.get(
        f"{BASE_URL}/queries/{query_id}/results",
        headers=headers_alice
    )
    print_response("Query Results (Alice's view)", response)
    
    # Bob can also access the same results
    response = requests.get(
        f"{BASE_URL}/queries/{query_id}/results",
        headers=headers_bob
    )
    print_response("Query Results (Bob's view)", response)
    
    # Step 11: List all sessions
    print("\n11. Listing Alice's collaboration sessions...")
    response = requests.get(
        SESSIONS_URL,
        headers=headers_alice
    )
    print_response("Alice's Sessions", response)
    
    print("\n" + "="*60)
    print("Workflow completed successfully!")
    print("="*60)
    print("\nKey Points:")
    print("- Session created instantly (no VM provisioning wait!)")
    print("- Both parties contributed data without seeing each other's raw data")
    print("- Query was verified by both parties before execution")
    print("- Results are available to all participants")
    print("- Shared TEE provides attestation and secure execution for all sessions")


if __name__ == '__main__':
    print("\nIMPORTANT: Update API_KEY_ALICE and API_KEY_BOB before running!")
    print("You can generate API keys at: http://localhost:5000/api-keys/\n")
    
    input("Press Enter to continue with the demo...")
    main()
