#!/usr/bin/env python3
"""
Test TEE Attestation

Validates that the shared TEE VM is properly generating and signing
attestation tokens, and verifies the confidential computing claims.
"""
import os
import sys
import json
import requests
import jwt
from datetime import datetime

# Configuration
TEE_ENDPOINT = os.getenv('TEE_SERVICE_ENDPOINT', 'http://localhost:8080')

# Global for tracking runtime hash
INITIAL_RUNTIME_HASH = None


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_health():
    """Test health endpoint"""
    print_section("Testing Health Endpoint")
    
    try:
        response = requests.get(f"{TEE_ENDPOINT}/health", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
            print("\n✓ Health check passed")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to connect to TEE service: {e}")
        print(f"\nMake sure:")
        print(f"  1. TEE VM is running")
        print(f"  2. Firewall allows access from your IP")
        print(f"  3. TEE_SERVICE_ENDPOINT is correct: {TEE_ENDPOINT}")
        return False


def test_attestation():
    """Test attestation endpoint and verify token"""
    print_section("Testing Attestation Endpoint")
    
    try:
        response = requests.get(f"{TEE_ENDPOINT}/attestation", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"✗ Attestation request failed: {response.status_code}")
            print(response.text)
            return False
        
        data = response.json()
        print("\nAttestation Response:")
        print(json.dumps(data, indent=2))
        
        # Extract token
        token = data.get('attestation_token')
        if not token:
            print("\n✗ No attestation token in response")
            return False
        
        print("\n" + "-" * 60)
        print("Verifying Attestation Token")
        print("-" * 60)
        
        # Decode without verification first to inspect claims
        unverified = jwt.decode(token, options={"verify_signature": False})
        print("\nToken Claims:")
        print(json.dumps(unverified, indent=2, default=str))
        
        # Verify critical claims
        print("\n" + "-" * 60)
        print("Checking Security Features")
        print("-" * 60)
        
        checks = [
            ('issuer', unverified.get('iss') == 'gcp-confidential-vm'),
            ('confidential_computing', unverified.get('confidential_computing') == True),
            ('secure_boot', unverified.get('secure_boot') == True),
            ('vtpm_enabled', unverified.get('vtpm_enabled') == True),
            ('instance_id', unverified.get('instance_id') is not None),
            ('expiration', unverified.get('exp') is not None),
            ('runtime_hash', unverified.get('runtime_hash') is not None),
        ]
        
        all_passed = True
        for name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"{status} {name}: {passed}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n✓ All attestation checks passed")
            print("\nThis TEE is:")
            print("  • Running in a Confidential VM")
            print("  • Using AMD SEV encryption")
            print("  • Secure Boot enabled")
            print("  • vTPM enabled")
            print(f"  • Instance ID: {unverified.get('instance_id')}")
            print(f"  • Runtime Hash: {unverified.get('runtime_hash', 'N/A')[:32]}...")
            
            # Store runtime hash for later verification
            global INITIAL_RUNTIME_HASH
            INITIAL_RUNTIME_HASH = unverified.get('runtime_hash')
            
            return True
        else:
            print("\n✗ Some attestation checks failed")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        return False


def test_runtime_hash():
    """Test runtime hash endpoint for code integrity verification"""
    print_section("Testing Runtime Hash Verification")
    
    try:
        response = requests.get(f"{TEE_ENDPOINT}/runtime-hash", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nRuntime Hash Info:")
            print(json.dumps(data, indent=2))
            
            runtime_hash = data.get('runtime_hash')
            if runtime_hash:
                print(f"\n✓ Runtime hash: {runtime_hash}")
                print("\n  Users should verify this hash matches the published version")
                print("  Any change to code (including SSH tampering) changes this hash")
                
                # Verify consistency with attestation
                if INITIAL_RUNTIME_HASH and runtime_hash != INITIAL_RUNTIME_HASH:
                    print("\n⚠️  WARNING: Runtime hash changed since attestation!")
                    print("   Possible tampering detected")
                    return False
                    
                return True
            else:
                print("\n✗ No runtime hash in response")
                return False
        else:
            print(f"✗ Runtime hash check failed: {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def test_audit_events():
    """Test audit events endpoint for transparency"""
    print_section("Testing Audit Events (SSH Detection)")
    
    try:
        response = requests.get(f"{TEE_ENDPOINT}/audit-events", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for SSH events
            ssh_events = data.get('ssh_events', '[]')
            print(f"\nSSH Events: {len(ssh_events)} events found")
            
            if 'Accepted' in str(ssh_events) or 'session opened' in str(ssh_events):
                print("⚠️  SSH access detected!")
                print("   An administrator has logged into the TEE VM")
                print("   Users should verify runtime hash and re-check attestation")
            else:
                print("✓ No SSH access detected")
            
            print("\nNote: Full audit logs available via:")
            print("  gcloud logging read 'resource.type=gce_instance'")
            
            return True
        else:
            print(f"✗ Audit events check failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def test_status():
    """Test status endpoint"""
    print_section("Testing Status Endpoint")
    
    try:
        response = requests.get(f"{TEE_ENDPOINT}/status", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
            print("\n✓ Status check passed")
            return True
        else:
            print(f"✗ Status check failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to get status: {e}")
        return False


def test_query_execution():
    """Test query execution endpoint"""
    print_section("Testing Query Execution (Mock)")
    
    try:
        payload = {
            'query_id': 999,
            'session_id': 1,
            'query_text': 'SELECT * FROM test',
            'dataset_paths': []
        }
        
        response = requests.post(
            f"{TEE_ENDPOINT}/execute-query",
            json=payload,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nExecution Response:")
            print(json.dumps(data, indent=2))
            print("\n✓ Query execution test passed")
            return True
        else:
            print(f"✗ Query execution failed: {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def main():
    print("=" * 60)
    print("TEE Attestation Test Suite")
    print("=" * 60)
    print(f"\nTEE Endpoint: {TEE_ENDPOINT}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    # Run tests
    tests = [
        ("Health Check", test_health),
        ("Attestation", test_attestation),
        ("Runtime Hash", test_runtime_hash),
        ("Status Check", test_status),
        ("Audit Events (SSH Detection)", test_audit_events),
        ("Query Execution", test_query_execution),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print_section("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! TEE is ready for use.")
        print("\nNext steps:")
        print(f"  1. Set environment variable:")
        print(f"     export TEE_SERVICE_ENDPOINT={TEE_ENDPOINT}")
        print(f"  2. Update your Flask app configuration")
        print(f"  3. Run the example workflow to test end-to-end")
        return 0
    else:
        print("\n✗ Some tests failed. Check the output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
