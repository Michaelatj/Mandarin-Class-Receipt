"""One-off, safe to run more than once: creates the tables added by the Bonus Courses / quiz updates
(bonus_access, hsk_known, hsk_activity, hsk_game, quiz_story, notification). Existing tables and data are not touched.

    python migrate_new_tables.py

On Vercel this is not needed: api/index.py already runs db.create_all() at start-up.
"""
import os

from app import create_app, db
from app.config import config_map
import app.models  # noqa: F401  (registers every table)

app = create_app(config_map.get(os.environ.get("FLASK_ENV", "development"), config_map["default"]))
with app.app_context():
    db.create_all()
    print("OK: all tables exist.")
