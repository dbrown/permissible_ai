#!/usr/bin/env python3
"""
Migration: Mark insecure mock datasets as requiring re-upload

This script identifies datasets that were created with the old insecure
upload flow and marks them as PENDING with a message requiring re-upload.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app
from app.extensions import db
from app.models.tee import Dataset, DatasetStatus

def migrate_insecure_datasets():
    """Mark all insecure datasets as needing re-upload"""
    app = create_app()
    
    with app.app_context():
        # Find datasets that:
        # 1. Have GCS bucket/path (old flow)
        # 2. Are marked as AVAILABLE
        # 3. Have no encrypted_path (never actually encrypted)
        insecure_datasets = Dataset.query.filter(
            Dataset.gcs_bucket.isnot(None),
            Dataset.status == DatasetStatus.AVAILABLE,
            Dataset.encrypted_path.is_(None)
        ).all()
        
        print(f"Found {len(insecure_datasets)} insecure datasets")
        
        for dataset in insecure_datasets:
            print(f"  - Dataset {dataset.id}: '{dataset.name}' (owner: {dataset.owner_id})")
            print(f"    Old GCS: gs://{dataset.gcs_bucket}/{dataset.gcs_path}")
            
            # Mark as PENDING with explanation
            dataset.status = DatasetStatus.PENDING
            dataset.error_message = (
                "This dataset was created with an insecure upload flow. "
                "Please re-upload using the new secure client-side encryption protocol. "
                "Your data was never actually uploaded - this was just a metadata record."
            )
            
            # Clear old GCS references (no longer used)
            dataset.gcs_bucket = None
            dataset.gcs_path = None
        
        if insecure_datasets:
            db.session.commit()
            print(f"\n✓ Migrated {len(insecure_datasets)} datasets to PENDING status")
            print("Users will need to re-upload these datasets using the secure flow")
        else:
            print("\n✓ No insecure datasets found - database is clean!")

if __name__ == '__main__':
    print("=" * 60)
    print("Dataset Security Migration")
    print("=" * 60)
    print("")
    migrate_insecure_datasets()
    print("")
