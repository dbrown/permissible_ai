"""
Database migration script to add TEE tables

Run this to add TEE functionality to an existing database:
    python migrate_add_tee.py

This adds:
- tees table for Trusted Execution Environments
- datasets table for uploaded datasets
- queries table for submitted queries
- query_results table for query outputs
- tee_participants association table
- query_approvals association table
"""
import os
import sys
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.tee import TEE, Dataset, Query, QueryResult


def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting TEE tables migration...")
        
        # Create all tables (will only create missing ones)
        db.create_all()
        
        print("✓ Migration completed successfully!")
        print("\nNew tables added:")
        print("  - tees")
        print("  - tee_participants")
        print("  - datasets")
        print("  - queries")
        print("  - query_results")
        print("  - query_approvals")
        
        # Verify tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['tees', 'tee_participants', 'datasets', 'queries', 'query_results', 'query_approvals']
        missing = [t for t in expected_tables if t not in tables]
        
        if missing:
            print(f"\n⚠ Warning: Some tables may not have been created: {missing}")
        else:
            print("\n✓ All TEE tables verified!")


if __name__ == '__main__':
    migrate()
