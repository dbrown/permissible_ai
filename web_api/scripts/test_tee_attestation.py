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
        
        # Extract attestation data and signature
        attestation_data = data.get('attestation')
        signature = data.get('signature')
        
        if not attestation_data or not signature:
            print("\n✗ Missing attestation data or signature")
            return False
        
        print("\n" + "-" * 60)
        print("Verifying Attestation Signature")
        print("-" * 60)
        
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            import base64
            
            # Load public key from attestation data
            public_key_pem = attestation_data['public_key'].encode('utf-8')
            public_key = serialization.load_pem_public_key(public_key_pem)
            
            # Verify signature
            signature_bytes = base64.b64decode(signature)
            message = json.dumps(attestation_data, sort_keys=True).encode('utf-8')
            
            public_key.verify(
                signature_bytes,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            print("✓ Signature verified successfully")
            
        except Exception as e:
            print(f"✗ Signature verification failed: {e}")
            return False
        
        print("\n" + "-" * 60)
        print("Checking Security Features")
        print("-" * 60)
        
        checks = [
            ('tee_type', attestation_data.get('tee_type') == 'gcp_confidential_vm'),
            ('confidential_computing', attestation_data.get('confidential_computing') == True),
            ('secure_boot', attestation_data.get('secure_boot') == True),
            ('instance_id', attestation_data.get('instance_id') is not None),
            ('code_measurement', attestation_data.get('code_measurement') is not None),
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
            print("  • Secure Boot enabled")
            print(f"  • Instance ID: {attestation_data.get('instance_id')}")
            print(f"  • Code Measurement: {attestation_data.get('code_measurement')[:32]}...")
            
            # Store runtime hash for later verification
            global INITIAL_RUNTIME_HASH
            INITIAL_RUNTIME_HASH = attestation_data.get('code_measurement')
            
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


def test_query_execution():
    """Test query execution endpoint"""
    print_section("Testing Query Execution (Mock)")
    
    try:
        # Note: This will likely fail with 403 because we don't have valid datasets
        # But we want to check if the endpoint exists and handles the request
        payload = {
            'query_id': 999,
            'session_id': 1,
            'query_text': 'SELECT 1',
            'dataset_ids': []
        }
        
        response = requests.post(
            f"{TEE_ENDPOINT}/execute",
            json=payload,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        # 200 OK or 400/403/500 are acceptable as long as it's not 404
        if response.status_code != 404:
            if response.status_code == 200:
                data = response.json()
                print("\nExecution Response:")
                print(json.dumps(data, indent=2))
            else:
                print(f"\nEndpoint reachable (Status {response.status_code})")
                print(f"Response: {response.text}")
                
            print("\n✓ Query execution endpoint test passed")
            return True
        else:
            print(f"✗ Query execution failed: {response.status_code}")
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
        return 0
    else:
        print("\n✗ Some tests failed. Check the output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
