"""
Migrate student_fee table to add packet_type column.
Run this once after deploying the new code.
Supports both SQLite (local) and PostgreSQL (production).
"""
from app import create_app, db
from sqlalchemy import text
import os

app = create_app()

with app.app_context():
    # Detect database type
    db_uri = os.environ.get('DATABASE_URL', '')
    is_postgres = 'postgresql' in db_uri
    
    if is_postgres:
        print("Detected PostgreSQL database")
        # Check if column already exists for PostgreSQL
        result = db.session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'student_fee' AND column_name = 'packet_type'
        """)).fetchone()
        
        if result:
            print("✓ Column 'packet_type' already exists in student_fee table")
        else:
            print("Adding 'packet_type' column to student_fee table...")
            db.session.execute(text("""
                ALTER TABLE student_fee 
                ADD COLUMN packet_type VARCHAR(20) DEFAULT 'session'
            """))
            db.session.commit()
            print("✓ Migration completed successfully!")
            
            # Verify
            count = db.session.execute(text("""
                SELECT COUNT(*) FROM student_fee WHERE packet_type IS NOT NULL
            """)).fetchone()[0]
            print(f"✓ Verified: {count} records now have packet_type set")
    else:
        print("Detected SQLite database")
        # Check if column already exists for SQLite
        result = db.session.execute(text("""
            SELECT name FROM pragma_table_info('student_fee') 
            WHERE name='packet_type'
        """)).fetchone()
        
        if result:
            print("✓ Column 'packet_type' already exists in student_fee table")
        else:
            print("Adding 'packet_type' column to student_fee table...")
            db.session.execute(text("""
                ALTER TABLE student_fee 
                ADD COLUMN packet_type VARCHAR(20) DEFAULT 'session'
            """))
            db.session.commit()
            print("✓ Migration completed successfully!")
            
            # Verify
            count = db.session.execute(text("""
                SELECT COUNT(*) FROM student_fee WHERE packet_type IS NOT NULL
            """)).fetchone()[0]
            print(f"✓ Verified: {count} records now have packet_type set")
