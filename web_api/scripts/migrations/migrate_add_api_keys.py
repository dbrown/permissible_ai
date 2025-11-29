#!/usr/bin/env python
"""
Database migration script for API Keys feature

This script will add the api_keys table to your existing database.
Run this after updating to the version with API key support.

Usage:
    python migrate_add_api_keys.py
"""

import sys
import os

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.api_key import APIKey

def migrate():
    """Add API Keys table to database"""
    app = create_app()
    
    with app.app_context():
        print("Starting migration: Adding API Keys table...")
        
        # Create the api_keys table
        try:
            db.create_all()
            print("✅ Successfully created api_keys table")
            print("\nMigration complete! Users can now manage API keys from their dashboard.")
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    return True

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
