"""
Database migration: Add PENDING and FAILED states to DatasetStatus enum

Run this migration to update the existing database schema.
"""

from sqlalchemy import create_engine, text
import os

def upgrade():
    """Add new enum values to datasetstatus"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/permissible_ai')
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            print("Adding PENDING to datasetstatus enum...")
            conn.execute(text("ALTER TYPE datasetstatus ADD VALUE IF NOT EXISTS 'PENDING'"))
            conn.commit()
            
            print("Adding FAILED to datasetstatus enum...")
            conn.execute(text("ALTER TYPE datasetstatus ADD VALUE IF NOT EXISTS 'FAILED'"))
            conn.commit()
            
            print("✓ Migration complete!")
            
        except Exception as e:
            trans.rollback()
            print(f"✗ Migration failed: {e}")
            raise


def downgrade():
    """
    Note: PostgreSQL does not support removing enum values directly.
    You would need to:
    1. Create a new enum type without those values
    2. Alter the column to use the new type
    3. Drop the old type
    """
    print("Downgrade not supported for enum values in PostgreSQL")
    print("Manual intervention required if you need to remove these values")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()
