import sys
import os

# Make sure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import ProductionConfig  # Import the config class directly
from app.models import db
from sqlalchemy import inspect, text

# Create the app with the correct Config Class
app = create_app(ProductionConfig)

# Auto-migration for Serverless environments (Vercel)
with app.app_context():
    try:
        # 1. Ensure all tables exist
        db.create_all()
        print("✅ Database tables verified/created.")

        # 2. Add missing columns
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        
        # --- FIX: Tambahkan kolom ke tabel RECEIPT ---
        if 'receipt' in table_names:
            columns = [col['name'] for col in inspector.get_columns('receipt')]
            
            with db.engine.connect() as conn:
                if 'packet_type' not in columns:
                    print("🔄 Adding missing 'packet_type' column to receipt...")
                    conn.execute(text("ALTER TABLE receipt ADD COLUMN packet_type VARCHAR(20);"))
                    
                if 'custom_qty' not in columns:
                    print("🔄 Adding missing 'custom_qty' column to receipt...")
                    conn.execute(text("ALTER TABLE receipt ADD COLUMN custom_qty INTEGER;"))
                    
                conn.commit()
            print("✅ Receipt table migration checked.")
        
        # --- (Tetap pertahankan untuk student_fee) ---
        if 'student_fee' in table_names:
            columns = [col['name'] for col in inspector.get_columns('student_fee')]
            if 'packet_type' not in columns:
                print("🔄 Adding missing 'packet_type' column to student_fee...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE student_fee ADD COLUMN packet_type VARCHAR(20) DEFAULT 'session'"))
                        conn.commit()
                    print("✅ Column 'packet_type' added to student_fee.")
                except Exception as e:
                    print(f"⚠️ Column migration skipped (might exist): {e}")

    except Exception as e:
        print(f"⚠️ Startup warning: {e}")
