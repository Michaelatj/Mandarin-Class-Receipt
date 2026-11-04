"""
migrate_attendance_override.py - adds what the attendance override and pay-first billing need
to an existing local SQLite database:
  * student_fee.pay_first      (pay first, then have class)
  * schedule_absent table      (teacher marks a student absent for a class)

Usage:
    python migrate_attendance_override.py

Safe to run more than once. Production (PostgreSQL) does this automatically in api/index.py
(db.create_all() makes the new table, and the column is added there).
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

cur.execute("PRAGMA table_info(student_fee)")
have = {row[1] for row in cur.fetchall()}
if "pay_first" in have:
    print("  student_fee.pay_first already exists, skipped")
else:
    cur.execute("ALTER TABLE student_fee ADD COLUMN pay_first BOOLEAN DEFAULT 0")
    print("  added student_fee.pay_first")

cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule_absent (
        id INTEGER PRIMARY KEY,
        schedule_id INTEGER NOT NULL REFERENCES schedule(id),
        student_id INTEGER NOT NULL REFERENCES user(id),
        CONSTRAINT uq_schedule_absent UNIQUE (schedule_id, student_id)
    )
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_schedule_absent_schedule_id ON schedule_absent (schedule_id)")
print("  schedule_absent table ready")

conn.commit()
conn.close()
print("Done.")
