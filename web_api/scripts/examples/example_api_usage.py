#!/usr/bin/env python
"""
Example API usage script

This demonstrates how to use the Permissible API with API keys.

Prerequisites:
1. Create an API key from the web interface at /api-keys
2. Copy your API key
3. Set it as an environment variable: export API_KEY="your-key-here"
4. Run this script: python example_api_usage.py
"""

import os
import requests
import json

# Configuration
BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5000')
API_KEY = os.getenv('API_KEY')

if not API_KEY:
    print("❌ Error: API_KEY environment variable not set")
    print("Please set your API key: export API_KEY='your-key-here'")
    exit(1)

# Set up headers with API key
headers = {
    'Authorization': f'Bearer {API_KEY}'
}

def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))

def main():
    """Run API examples"""
    print(f"🔑 Using API Base URL: {BASE_URL}")
    print(f"🔑 Using API Key: {API_KEY[:12]}...")
    
    # Example 1: Health check (no auth required)
    print("\n\n📍 Example 1: Health Check (Public endpoint)")
    response = requests.get(f'{BASE_URL}/api/health')
    print_response("GET /api/health", response)
    
    # Example 2: Get current user info
    print("\n\n📍 Example 2: Get Current User Info")
    response = requests.get(f'{BASE_URL}/api/me', headers=headers)
    print_response("GET /api/me", response)
    
    # Example 3: List all users (admin only)
    print("\n\n📍 Example 3: List All Users (Admin only)")
    response = requests.get(f'{BASE_URL}/api/users', headers=headers)
    print_response("GET /api/users", response)
    
    # Example 4: Using X-API-Key header instead
    print("\n\n📍 Example 4: Using X-API-Key Header")
    alt_headers = {'X-API-Key': API_KEY}
    response = requests.get(f'{BASE_URL}/api/me', headers=alt_headers)
    print_response("GET /api/me (with X-API-Key)", response)
    
    # Example 5: Using query parameter (less secure)
    print("\n\n📍 Example 5: Using Query Parameter")
    response = requests.get(f'{BASE_URL}/api/me?api_key={API_KEY}')
    print_response("GET /api/me?api_key=...", response)
    
    print("\n\n✅ All examples completed!")
    print("\n💡 Tips:")
    print("  - Use Authorization header in production")
    print("  - Keep your API keys secure")
    print("  - Create separate keys for different applications")
    print("  - Rotate keys regularly")

if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Could not connect to {BASE_URL}")
        print("Make sure the Flask application is running")
    except Exception as e:
        print(f"\n❌ Error: {e}")
