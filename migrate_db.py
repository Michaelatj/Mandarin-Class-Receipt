"""
migrate_db.py — Run this ONCE to add new columns to existing database.

Usage:
    python migrate_db.py

Safe to run multiple times — skips columns that already exist.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "attendance.db")

if not os.path.exists(DB_PATH):
    print(f"Database not found at: {DB_PATH}")
    print("Run 'python run.py' first to create it, then run this script.")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

migrations = []

# 1. Add email column to user table
cur.execute("PRAGMA table_info(user)")
existing_cols = {row[1] for row in cur.fetchall()}
if "email" not in existing_cols:
    cur.execute("ALTER TABLE user ADD COLUMN email VARCHAR(200) DEFAULT ''")
    migrations.append("✓ Added 'email' column to user table")
else:
    migrations.append("· 'email' column already exists — skipped")

# 2. Add source column to attendance table
cur.execute("PRAGMA table_info(attendance)")
att_cols = {row[1] for row in cur.fetchall()}
if "source" not in att_cols:
    cur.execute("ALTER TABLE attendance ADD COLUMN source VARCHAR(10) DEFAULT 'teacher'")
    migrations.append("✓ Added 'source' column to attendance table")
else:
    migrations.append("· 'source' column already exists — skipped")

# 2. Create otp_token table if not exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='otp_token'")
if not cur.fetchone():
    cur.execute("""
        CREATE TABLE otp_token (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES user(id),
            code       VARCHAR(6) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            used       BOOLEAN DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX ix_otp_token_user_id ON otp_token (user_id)")
    migrations.append("✓ Created 'otp_token' table")
else:
    migrations.append("· 'otp_token' table already exists — skipped")

conn.commit()
conn.close()

print("\nDatabase migration complete:")
for m in migrations:
    print(" ", m)
print("\nYou can now run 'python run.py' normally.")
