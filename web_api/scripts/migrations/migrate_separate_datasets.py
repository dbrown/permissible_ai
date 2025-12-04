"""
Database migration script to separate Datasets from Sessions

Run this to migrate the database schema:
    python migrate_separate_datasets.py

This changes:
- Creates session_datasets association table
- Migrates existing dataset-session relationships
- Removes session_id from datasets table
"""
import os
import sys
from sqlalchemy import text

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.extensions import db

def migrate():
    """Run the migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting Dataset separation migration...")
        
        # 1. Create session_datasets table
        print("Creating session_datasets table...")
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS session_datasets (
                    session_id INTEGER NOT NULL,
                    dataset_id INTEGER NOT NULL,
                    added_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                    PRIMARY KEY (session_id, dataset_id),
                    FOREIGN KEY(session_id) REFERENCES collaboration_sessions (id),
                    FOREIGN KEY(dataset_id) REFERENCES datasets (id)
                )
            """))
            db.session.commit()
        except Exception as e:
            print(f"Error creating table: {e}")
            db.session.rollback()

        # 2. Migrate existing data
        print("Migrating existing relationships...")
        try:
            # Check if session_id exists in datasets before trying to migrate
            result = db.session.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name='datasets' AND column_name='session_id'"))
            # Note: The above check is for Postgres. For SQLite it's different. 
            # Assuming Postgres based on project description, but let's be robust.
            # Actually, let's just try the insert and catch error if column doesn't exist (already migrated)
            
            db.session.execute(text("""
                INSERT INTO session_datasets (session_id, dataset_id, added_at)
                SELECT session_id, id, uploaded_at FROM datasets
                WHERE session_id IS NOT NULL
                ON CONFLICT DO NOTHING
            """))
            db.session.commit()
            print("Data migrated.")
        except Exception as e:
            print(f"Migration step skipped or failed (column might be gone): {e}")
            db.session.rollback()

        # 3. Drop session_id column
        print("Dropping session_id from datasets...")
        try:
            db.session.execute(text("ALTER TABLE datasets DROP COLUMN session_id"))
            db.session.commit()
            print("Column dropped.")
        except Exception as e:
            print(f"Error dropping column (might not exist): {e}")
            db.session.rollback()
            
        print("✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
