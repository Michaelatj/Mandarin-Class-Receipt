import sys
import os

# Make sure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from sqlalchemy import inspect

app = create_app("production")

# Auto-migration for Serverless environments (Vercel)
# This ensures the database schema matches the models before handling requests
with app.app_context():
    try:
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        
        # Create all tables if they don't exist
        if not table_names:
            db.create_all()
            print("✅ Database tables created.")
        
        # Check student_fee table for packet_type column
        if 'student_fee' in table_names:
            columns = [col['name'] for col in inspector.get_columns('student_fee')]
            if 'packet_type' not in columns:
                print("🔄 Detected missing 'packet_type' column. Adding it now...")
                # Add the column manually since Alembic isn't configured for auto-migrate in this snippet
                with db.engine.connect() as conn:
                    # Default to 'session' for existing rows to maintain backward compatibility
                    conn.execute(db.text("ALTER TABLE student_fee ADD COLUMN packet_type VARCHAR(20) DEFAULT 'session'"))
                    conn.commit()
                print("✅ Column 'packet_type' added successfully.")
    except Exception as e:
        print(f"⚠️ Auto-migration check failed (non-critical if tables exist): {e}")

# Vercel needs the WSGI app exposed as `app`
