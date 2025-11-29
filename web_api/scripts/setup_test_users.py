#!/usr/bin/env python
"""
Setup test users and API keys for TEE workflow examples

This script creates test users (Alice and Bob) with API keys for testing
the TEE workflow without requiring Google OAuth authentication.

Usage:
    python scripts/setup_test_users.py
"""

import sys
import os

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.api_key import APIKey


def setup_test_users():
    """Create test users and API keys for TEE workflow examples"""
    app = create_app()
    
    with app.app_context():
        print("Setting up test users for TEE workflow...")
        print("=" * 60)
        
        # Check if users already exist
        alice = User.query.filter_by(email='alice@hospital-a.org').first()
        bob = User.query.filter_by(email='bob@hospital-b.org').first()
        
        # Create Alice if she doesn't exist
        if not alice:
            print("\n📝 Creating Alice (alice@hospital-a.org)...")
            alice = User(
                google_id='test_alice_google_id',
                email='alice@hospital-a.org',
                name='Alice Anderson',
                picture='https://example.com/alice.jpg',
                is_admin=False
            )
            db.session.add(alice)
            db.session.commit()
            print("✅ Alice created successfully")
        else:
            print("\n✓ Alice already exists")
        
        # Create Bob if he doesn't exist
        if not bob:
            print("\n📝 Creating Bob (bob@hospital-b.org)...")
            bob = User(
                google_id='test_bob_google_id',
                email='bob@hospital-b.org',
                name='Bob Brown',
                picture='https://example.com/bob.jpg',
                is_admin=False
            )
            db.session.add(bob)
            db.session.commit()
            print("✅ Bob created successfully")
        else:
            print("\n✓ Bob already exists")
        
        # Create or regenerate API keys
        print("\n🔑 Setting up API keys...")
        
        # Alice's API key
        alice_key = APIKey.query.filter_by(user_id=alice.id, name='TEE Workflow Test Key').first()
        if alice_key:
            print(f"\n✓ Alice's existing API key: {alice_key.key}")
        else:
            alice_key = APIKey(
                user_id=alice.id,
                key=APIKey.generate_key(),
                name='TEE Workflow Test Key'
            )
            db.session.add(alice_key)
            db.session.commit()
            print(f"\n✅ Alice's new API key: {alice_key.key}")
        
        # Bob's API key
        bob_key = APIKey.query.filter_by(user_id=bob.id, name='TEE Workflow Test Key').first()
        if bob_key:
            print(f"✓ Bob's existing API key: {bob_key.key}")
        else:
            bob_key = APIKey(
                user_id=bob.id,
                key=APIKey.generate_key(),
                name='TEE Workflow Test Key'
            )
            db.session.add(bob_key)
            db.session.commit()
            print(f"✅ Bob's new API key: {bob_key.key}")
        
        print("\n" + "=" * 60)
        print("🎉 Setup complete!")
        print("\nUpdate your example_tee_workflow.py with these values:")
        print("-" * 60)
        print(f'API_KEY_ALICE = "{alice_key.key}"')
        print(f'API_KEY_BOB = "{bob_key.key}"')
        print("-" * 60)
        print("\nUsers created:")
        print(f"  • Alice: {alice.email} (ID: {alice.id})")
        print(f"  • Bob: {bob.email} (ID: {bob.id})")
        print("\n✨ You can now run the TEE workflow example!")
        
        return True


if __name__ == '__main__':
    try:
        success = setup_test_users()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
