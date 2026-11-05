"""
migrate_prepaid.py - adds the columns for prepaid receipts and students without an account
to an existing local SQLite database.

Usage:
    python migrate_prepaid.py

Safe to run more than once. Production (PostgreSQL) does this automatically in api/index.py.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "attendance.db")

if not os.path.exists(DB_PATH):
    print(f"Database not found at: {DB_PATH}")
    print("Run 'python run.py' first to create it, then run this script.")
    raise SystemExit(1)

WANTED = {
    "user": {"managed_by": "INTEGER"},
    "receipt": {
        "kind": "VARCHAR(10) DEFAULT 'billing'",
        "covers": "VARCHAR(200) DEFAULT ''",
        "method": "VARCHAR(30) DEFAULT ''",
        "period_start": "DATETIME",
        "period_end": "DATETIME",
    },
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
for table, columns in WANTED.items():
    cur.execute(f'PRAGMA table_info("{table}")')
    have = {row[1] for row in cur.fetchall()}
    for name, ddl in columns.items():
        if name in have:
            print(f"  {table}.{name} already exists, skipped")
        else:
            cur.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}')
            print(f"  added {table}.{name}")
conn.commit()
conn.close()
print("Done.")
