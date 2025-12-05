"""
Database migration: Add is_public column to datasets table
"""

from sqlalchemy import create_engine, text
import os

def upgrade():
    """Add is_public column to datasets table"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/permissible_ai')
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            print("Adding is_public column to datasets table...")
            conn.execute(text("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE NOT NULL"))
            trans.commit()
            
            print("✓ Migration complete!")
            
        except Exception as e:
            trans.rollback()
            print(f"✗ Migration failed: {e}")
            raise

if __name__ == '__main__':
    upgrade()
