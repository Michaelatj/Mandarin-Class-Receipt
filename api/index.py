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

        # --- prepaid receipts and students without an account ---
        with db.engine.connect() as conn:
            if 'user' in table_names:
                ucols = [col['name'] for col in inspector.get_columns('user')]
                if 'managed_by' not in ucols:
                    print("Adding missing 'managed_by' column to user...")
                    conn.execute(text('ALTER TABLE "user" ADD COLUMN managed_by INTEGER'))
            if 'receipt' in table_names:
                rcols2 = [col['name'] for col in inspector.get_columns('receipt')]
                for name, ddl in {'kind': "VARCHAR(10) DEFAULT 'billing'", 'covers': "VARCHAR(200) DEFAULT ''",
                                  'method': "VARCHAR(30) DEFAULT ''", 'period_start': "TIMESTAMP", 'period_end': "TIMESTAMP"}.items():
                    if name not in rcols2:
                        print(f"Adding missing '{name}' column to receipt...")
                        conn.execute(text(f"ALTER TABLE receipt ADD COLUMN {name} {ddl}"))
            conn.commit()

        # --- paid_at on receipt (for revenue by month in Insights) ---
        if 'receipt' in table_names:
            rcols = [col['name'] for col in inspector.get_columns('receipt')]
            if 'paid_at' not in rcols:
                print("Adding missing 'paid_at' column to receipt...")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE receipt ADD COLUMN paid_at TIMESTAMP"))
                    conn.commit()

        # --- Offline classes and roll call columns on schedule ---
        if 'schedule' in table_names:
            columns = [col['name'] for col in inspector.get_columns('schedule')]
            wanted = {
                'mode': "VARCHAR(10) DEFAULT 'online'",
                'location': "VARCHAR(200) DEFAULT ''",
                'rollcall_code': "VARCHAR(8)",
                'rollcall_until': "TIMESTAMP",
            }
            with db.engine.connect() as conn:
                for name, ddl in wanted.items():
                    if name not in columns:
                        print(f"Adding missing '{name}' column to schedule...")
                        conn.execute(text(f"ALTER TABLE schedule ADD COLUMN {name} {ddl}"))
                conn.commit()

        # --- pay-first billing flag on student_fee ---
        if 'student_fee' in table_names:
            fcols = [col['name'] for col in inspector.get_columns('student_fee')]
            if 'pay_first' not in fcols:
                print("Adding missing 'pay_first' column to student_fee...")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE student_fee ADD COLUMN pay_first BOOLEAN DEFAULT FALSE"))
                    conn.commit()

    except Exception as e:
        print(f"⚠️ Startup warning: {e}")
