"""
migrate_streak_recover.py - brings back streak history that was lost when classes were deleted
BEFORE the streak history table (streak_entry) existed.

Deleted classes cannot be known any more, but every attendance a student made is still in the
attendance table. This script turns each attendance that no class explains into one frozen
"attended" record in streak_entry, so the streak counts it again. (A class the student MISSED
and that was deleted early cannot be recovered; the streak simply continues over the days
they did attend.)

Usage (it only PRINTS what it would do unless you add --apply):
    python migrate_streak_recover.py            # preview
    python migrate_streak_recover.py --apply    # write it

For the live database set DATABASE_URL first (the same value as on Vercel), e.g. on Windows:
    set DATABASE_URL=postgresql://...
    python migrate_streak_recover.py --apply

Safe to run more than once: after the first run nothing is left to add.
"""
import os
import sys
from datetime import timedelta

from app import create_app
from app.config import config_map
from app.models import WIB_OFFSET, Attendance, Schedule, StreakEntry, User
from app import db

APPLY = "--apply" in sys.argv
BEFORE, AFTER = timedelta(hours=3), timedelta(hours=4)   # a class "explains" an attendance this close to it

app = create_app(config_map["production" if os.environ.get("DATABASE_URL") else "development"])
with app.app_context():
    classes = Schedule.query.filter(Schedule.cancelled.is_(False)).all()
    class_times = [s.scheduled_at for s in classes]                  # WIB wall-clock
    total = 0
    for stu in User.query.filter_by(role="student").order_by(User.id).all():
        known = [e.class_at for e in StreakEntry.query.filter_by(student_id=stu.id).all()]
        known += class_times
        adds = []
        for att in (Attendance.query.filter_by(student_id=stu.id).order_by(Attendance.date.asc()).all()):
            when = att.date + WIB_OFFSET
            if any(k - AFTER <= when <= k + BEFORE for k in known):    # a class or saved record already explains it
                continue
            adds.append((when, att))
            known.append(when)                                          # attendances close together = one class
        if adds:
            print(f"{stu.name()}: +{len(adds)} classes recovered")
            total += len(adds)
            if APPLY:
                for when, att in adds:
                    db.session.add(StreakEntry(student_id=stu.id, schedule_id=None, class_at=when,
                                               title=(att.note or "Recovered class")[:200], attended=True))
    if APPLY:
        db.session.commit()
        print(f"Done. {total} classes written.")
    else:
        print(f"Preview only: {total} classes would be written. Run again with --apply to write them.")
