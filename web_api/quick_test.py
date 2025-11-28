#!/usr/bin/env python
"""
Quick test script to verify API key functionality works

This script runs a subset of critical tests to quickly verify
that the API key system is working correctly.
"""

import subprocess
import sys

CRITICAL_TESTS = [
    "tests/test_api_key_model.py::TestAPIKeyModel::test_generate_key",
    "tests/test_api_key_model.py::TestAPIKeyModel::test_create_api_key",
    "tests/test_api_key_routes.py::TestAPIKeyRoutes::test_create_key_success",
    "tests/test_api_key_routes.py::TestAPIKeyRoutes::test_delete_key_success",
    "tests/test_api_authentication.py::TestAPIKeyAuthentication::test_api_endpoint_with_bearer_token",
]

def run_quick_tests():
    """Run critical tests quickly"""
    print("🚀 Running critical API key tests...\n")
    
    for test in CRITICAL_TESTS:
        print(f"Testing: {test.split('::')[-1]}")
    
    print()
    
    result = subprocess.run(
        ["pytest", "-v"] + CRITICAL_TESTS,
        capture_output=False
    )
    
    if result.returncode == 0:
        print("\n✅ All critical tests passed!")
        print("Run 'pytest' for full test suite")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    run_quick_tests()
