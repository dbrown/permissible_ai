"""
Cleanup script to remove all datasets from the database.
Useful for resetting state after schema changes.

Run with:
    python scripts/cleanup_datasets.py
"""
import os
import sys
from sqlalchemy import text

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db

def cleanup():
    """Delete all datasets and related associations"""
    app = create_app()
    
    with app.app_context():
        print("WARNING: This will delete ALL datasets from the database.")
        confirm = input("Are you sure? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return

        print("Cleaning up...")
        try:
            # 1. Clear session_datasets association table
            print("Clearing session_datasets...")
            db.session.execute(text("DELETE FROM session_datasets"))
            
            # 2. Clear datasets table
            print("Clearing datasets...")
            db.session.execute(text("DELETE FROM datasets"))
            
            db.session.commit()
            print("✓ All datasets deleted successfully.")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            db.session.rollback()

if __name__ == '__main__':
    cleanup()
