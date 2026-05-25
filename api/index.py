import sys
import os

# Make sure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from sqlalchemy import inspect, text

# Create the Flask application instance
# This MUST be at the top level (not inside any function or block) for Vercel to find it
app = create_app("production")

# Auto-migration for Serverless environments (Vercel)
# We run this immediately after creating the app, using the app context
with app.app_context():
    try:
        # 1. Ensure all tables exist first (safe no-op if they already exist)
        db.create_all()
        print("✅ Database tables verified/created.")

        # 2. Specific column migration for 'packet_type'
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        
        if 'student_fee' in table_names:
            columns = [col['name'] for col in inspector.get_columns('student_fee')]
            
            if 'packet_type' not in columns:
                print("🔄 Detected missing 'packet_type' column. Adding it now...")
                try:
                    with db.engine.connect() as conn:
                        # Use text() for raw SQL execution
                        conn.execute(text("ALTER TABLE student_fee ADD COLUMN packet_type VARCHAR(20) DEFAULT 'session'"))
                        conn.commit()
                    print("✅ Column 'packet_type' added successfully.")
                except Exception as col_err:
                    # If column already exists or error occurs, log but don't crash
                    print(f"⚠️ Could not add column (might already exist): {col_err}")
            else:
                print("✅ Column 'packet_type' already exists.")
        else:
            print("⚠️ Table 'student_fee' not found (fresh DB). db.create_all() should handle this.")
            
    except Exception as e:
        # Critical error during startup, but we log it and let Vercel try to serve anyway
        print(f"⚠️ Auto-migration check warning: {e}")

# Vercel needs the WSGI app exposed as `app` at the module level.
# It is already defined above, so we just leave it here.
