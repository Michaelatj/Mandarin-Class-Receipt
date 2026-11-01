"""
migrate_offline_class.py - adds the offline class and roll call columns to the schedule table
of an existing local SQLite database.

Usage:
    python migrate_offline_class.py

Safe to run more than once. Production (PostgreSQL) does this automatically in api/index.py.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "attendance.db")

if not os.path.exists(DB_PATH):
    print(f"Database not found at: {DB_PATH}")
    print("Run 'python run.py' first to create it, then run this script.")
    raise SystemExit(1)

COLUMNS = {
    "mode": "VARCHAR(10) DEFAULT 'online'",
    "location": "VARCHAR(200) DEFAULT ''",
    "rollcall_code": "VARCHAR(8)",
    "rollcall_until": "DATETIME",
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(schedule)")
have = {row[1] for row in cur.fetchall()}

for name, ddl in COLUMNS.items():
    if name in have:
        print(f"  '{name}' already exists, skipped")
    else:
        cur.execute(f"ALTER TABLE schedule ADD COLUMN {name} {ddl}")
        print(f"  added '{name}'")

conn.commit()
conn.close()
print("Done.")
