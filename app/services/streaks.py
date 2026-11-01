"""
services/streaks.py - attendance streaks for scheduled classes.

A streak counts the scheduled classes a student joined in a row, going back from the most
recent one that has already started. Missing one class resets it. A class only counts for
a student if it is open to everyone or the student was invited, it was not cancelled, and it
was held after the student registered. A class still running (or about to start) is skipped
so nobody loses a streak for a class that has not really finished.
"""
from datetime import datetime, timedelta

from .. import db
from ..models import Schedule, ScheduleInvite, ScheduleJoin, User

# (classes in a row, character, English name)
TIERS = [
    (3,  "勤", "Steady"),
    (5,  "恒", "Dedicated"),
    (10, "毅", "Devoted"),
    (20, "卓", "Outstanding"),
]


def tier_for(n):
    """Highest tier reached for a streak of n classes, or None."""
    reached = None
    for need, char, name in TIERS:
        if n >= need:
            reached = {"min": need, "char": char, "name": name}
    return reached


def _next_target(n):
    for need, _c, _n in TIERS:
        if n < need:
            return need
    return None


def compute_streaks(student_ids, now=None, grace_minutes=60):
    """Return {student_id: info} for many students with a handful of queries."""
    now = now or datetime.utcnow()
    student_ids = list(student_ids)
    empty = {"current": 0, "best": 0, "attended": 0, "total": 0, "tier": None, "next_at": TIERS[0][0], "progress": 0}
    if not student_ids:
        return {}

    cutoff = now - timedelta(minutes=grace_minutes)
    past = (Schedule.query
            .filter(Schedule.cancelled.is_(False), Schedule.scheduled_at <= cutoff)
            .order_by(Schedule.scheduled_at.asc()).all())
    if not past:
        return {sid: dict(empty) for sid in student_ids}

    sched_ids = [s.id for s in past]
    invites = {}
    for sched_id, stu_id in (db.session.query(ScheduleInvite.schedule_id, ScheduleInvite.student_id)
                             .filter(ScheduleInvite.schedule_id.in_(sched_ids))):
        invites.setdefault(sched_id, set()).add(stu_id)

    joined = {}
    for sched_id, stu_id in (db.session.query(ScheduleJoin.schedule_id, ScheduleJoin.student_id)
                             .filter(ScheduleJoin.schedule_id.in_(sched_ids),
                                     ScheduleJoin.student_id.in_(student_ids))):
        joined.setdefault(stu_id, set()).add(sched_id)

    created = {u.id: u.created_at for u in User.query.filter(User.id.in_(student_ids)).all()}

    result = {}
    for sid in student_ids:
        since = created.get(sid)
        # oldest to newest; only classes this student was part of
        mine = [s for s in past
                if (not invites.get(s.id) or sid in invites[s.id])
                and (since is None or s.scheduled_at >= since - timedelta(days=1))]
        hit = joined.get(sid, set())

        best = run = 0
        for s in mine:
            run = run + 1 if s.id in hit else 0
            best = max(best, run)
        current = run                      # the run that is still open at the newest class

        nxt = _next_target(current)
        floor = max([t[0] for t in TIERS if t[0] <= current], default=0)
        progress = 100 if nxt is None else int(round((current - floor) / (nxt - floor) * 100))
        result[sid] = {
            "current": current, "best": best,
            "attended": sum(1 for s in mine if s.id in hit), "total": len(mine),
            "tier": tier_for(current), "next_at": nxt, "progress": progress,
        }
    return result


def attendance_streak(student_id, now=None):
    return compute_streaks([student_id], now=now).get(student_id)
