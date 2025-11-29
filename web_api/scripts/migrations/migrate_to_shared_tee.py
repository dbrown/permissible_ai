#!/usr/bin/env python3
"""
Database migration: Refactor from per-session TEE VMs to shared TEE architecture

This migration:
1. Renames 'tees' table to 'collaboration_sessions'
2. Removes VM-specific columns (gcp_project_id, gcp_zone, gcp_instance_id, attestation fields)
3. Updates status enum from TEEStatus to SessionStatus
4. Renames association table from 'tee_participants' to 'session_participants'
5. Updates foreign keys in datasets and queries tables

Run this migration to convert to the shared TEE architecture.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.extensions import db
from app import create_app
from sqlalchemy import text


def migrate_to_shared_tee():
    """Execute migration to shared TEE architecture"""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Migration: Per-Session TEE VMs -> Shared TEE Architecture")
        print("=" * 80)
        print()
        
        try:
            # Check current state
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'collaboration_sessions'
                )
            """))
            has_new_table = result.scalar()
            
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'tees'
                )
            """))
            has_old_table = result.scalar()
            
            if has_new_table and not has_old_table:
                print("✓ Migration already complete - using collaboration_sessions architecture")
                return
            
            if has_new_table and has_old_table:
                print("⚠️  Both old and new tables exist - migrating data...")
                print("\nStep 1: Copying data from tees to collaboration_sessions...")
                
                # Copy data from old table to new table
                db.session.execute(text("""
                    INSERT INTO collaboration_sessions 
                        (id, name, description, creator_id, allow_cross_party_joins, 
                         require_unanimous_approval, status, created_at, closed_at)
                    SELECT 
                        id, name, description, creator_id, allow_cross_party_joins,
                        require_unanimous_approval,
                        CASE status::text
                            WHEN 'creating' THEN 'ACTIVE'::sessionstatus
                            WHEN 'terminated' THEN 'CLOSED'::sessionstatus
                            WHEN 'error' THEN 'CLOSED'::sessionstatus
                            WHEN 'active' THEN 'ACTIVE'::sessionstatus
                            WHEN 'suspended' THEN 'SUSPENDED'::sessionstatus
                            ELSE 'ACTIVE'::sessionstatus
                        END,
                        created_at,
                        CASE status::text
                            WHEN 'terminated' THEN COALESCE(terminated_at, NOW())
                            ELSE NULL
                        END
                    FROM tees
                    ON CONFLICT (id) DO NOTHING
                """))
                print("✓ Data copied")
                
                print("\nStep 2: Copying participant associations...")
                db.session.execute(text("""
                    INSERT INTO session_participants (session_id, user_id, joined_at)
                    SELECT tee_id, user_id, joined_at
                    FROM tee_participants
                    ON CONFLICT DO NOTHING
                """))
                print("✓ Participant associations copied")
                
                print("\nStep 3: Updating foreign keys in datasets...")
                # Just rename the column
                db.session.execute(text("""
                    ALTER TABLE datasets 
                    RENAME COLUMN tee_id TO session_id
                """))
                print("✓ Dataset foreign keys updated")
                
                print("\nStep 4: Updating foreign keys in queries...")
                # Just rename the column
                db.session.execute(text("""
                    ALTER TABLE queries 
                    RENAME COLUMN tee_id TO session_id
                """))
                print("✓ Query foreign keys updated")
                
                print("\nStep 5: Dropping old tables...")
                db.session.execute(text("DROP TABLE IF EXISTS tee_participants CASCADE"))
                db.session.execute(text("DROP TABLE IF EXISTS tees CASCADE"))
                print("✓ Old tables removed")
                
                db.session.commit()
                print("\n✓ Data migration complete - old tables removed")
                return  # Exit successfully
                
            elif not has_new_table:
                print("Creating new table structure from scratch...")
                
                print("\nStep 1: Renaming tees table to collaboration_sessions...")
                db.session.execute(text("""
                    ALTER TABLE tees RENAME TO collaboration_sessions
                """))
                print("✓ Table renamed")
            
            print("\nStep 2: Removing VM-specific columns...")
            # Remove GCP instance columns
            db.session.execute(text("""
                ALTER TABLE collaboration_sessions 
                DROP COLUMN IF EXISTS gcp_project_id,
                DROP COLUMN IF EXISTS gcp_zone,
                DROP COLUMN IF EXISTS gcp_instance_id,
                DROP COLUMN IF EXISTS attestation_token,
                DROP COLUMN IF EXISTS attestation_verified_at,
                DROP COLUMN IF EXISTS activated_at,
                DROP COLUMN IF EXISTS terminated_at
            """))
            print("✓ VM-specific columns removed")
            
            print("\nStep 3: Adding/updating session-specific columns...")
            # Add closed_at column if it doesn't exist
            db.session.execute(text("""
                ALTER TABLE collaboration_sessions 
                ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP
            """))
            print("✓ Session columns added")
            
            print("\nStep 4: Updating status values...")
            # Update status enum values (simplified approach)
            # CREATING -> ACTIVE (no longer need CREATING state)
            # TERMINATED -> CLOSED
            # ERROR can be removed or kept for backwards compatibility
            db.session.execute(text("""
                UPDATE collaboration_sessions 
                SET status = 'active' 
                WHERE status = 'creating'
            """))
            db.session.execute(text("""
                UPDATE collaboration_sessions 
                SET status = 'closed', closed_at = COALESCE(created_at + INTERVAL '1 day', NOW())
                WHERE status = 'terminated'
            """))
            print("✓ Status values updated")
            
            print("\nStep 5: Renaming association table...")
            db.session.execute(text("""
                ALTER TABLE tee_participants RENAME TO session_participants
            """))
            db.session.execute(text("""
                ALTER TABLE session_participants 
                RENAME COLUMN tee_id TO session_id
            """))
            print("✓ Association table renamed")
            
            print("\nStep 6: Updating foreign keys in datasets table...")
            db.session.execute(text("""
                ALTER TABLE datasets 
                RENAME COLUMN tee_id TO session_id
            """))
            print("✓ Datasets table updated")
            
            print("\nStep 7: Updating foreign keys in queries table...")
            db.session.execute(text("""
                ALTER TABLE queries 
                RENAME COLUMN tee_id TO session_id
            """))
            print("✓ Queries table updated")
            
            # Commit all changes
            db.session.commit()
            
            print("\n" + "=" * 80)
            print("✅ Migration completed successfully!")
            print("=" * 80)
            print()
            print("Summary:")
            print("  - Converted to shared TEE architecture")
            print("  - Removed per-session VM management overhead")
            print("  - Simplified collaboration session model")
            print()
            print("Next steps:")
            print("  1. Configure shared TEE service endpoint (TEE_SERVICE_ENDPOINT)")
            print("  2. Set shared TEE instance ID (TEE_INSTANCE_ID)")
            print("  3. Deploy/start the shared TEE service")
            print("  4. Test attestation verification")
            print()
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            print("\nRolling back changes...")
            raise


if __name__ == '__main__':
    print("\n⚠️  WARNING: This migration will modify your database schema!")
    print("Make sure you have a backup before proceeding.")
    print()
    response = input("Do you want to continue? (yes/no): ")
    
    if response.lower() == 'yes':
        migrate_to_shared_tee()
    else:
        print("Migration cancelled")
