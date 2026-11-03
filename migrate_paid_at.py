"""
migrate_paid_at.py - adds receipt.paid_at to an existing local SQLite database.

Usage:
    python migrate_paid_at.py

Safe to run more than once. Production (PostgreSQL) does this automatically in api/index.py.
Receipts that were paid before this column existed keep an empty paid_at; the Insights tab
counts them in the month they were issued.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "attendance.db")

if not os.path.exists(DB_PATH):
    print(f"Database not found at: {DB_PATH}")
    print("Run 'python run.py' first to create it, then run this script.")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(receipt)")
have = {row[1] for row in cur.fetchall()}

if "paid_at" in have:
    print("  'paid_at' already exists, skipped")
else:
    cur.execute("ALTER TABLE receipt ADD COLUMN paid_at DATETIME")
    print("  added 'paid_at'")

conn.commit()
conn.close()
print("Done.")
