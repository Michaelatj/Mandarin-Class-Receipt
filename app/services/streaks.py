"""
services/streaks.py - attendance streaks for scheduled classes.

A streak counts the scheduled classes a student attended in a row, going back from the most
recent one that has started. Missing one class resets it to zero (the best streak is kept as
history). A class counts for a student if it is open to everyone or the student was invited, it
was not cancelled, and it was held after the student registered.

A student attended a class when any of these is true:
  * they pressed Join for it (online) or checked in to its roll call (offline),
  * they submitted attendance, or the teacher recorded it, close to the class time.
That way a student who shows up and is recorded through the normal attendance button is not
punished, and a student who does none of these loses the streak.

A class that started less than GRACE_MINUTES ago is not counted yet, because the student can
still join; it is listed in "live" so the app can remind them to attend to keep the streak.
"""
from bisect import bisect_left
from datetime import datetime, timedelta

from .. import db
from ..models import Attendance, Schedule, ScheduleInvite, ScheduleJoin, User

GRACE_MINUTES = 60          # after this long, a class nobody attended counts as missed
BEFORE = timedelta(minutes=60)   # attendance this early before the class still counts for it
AFTER = timedelta(hours=4)       # and this long after it starts

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


def _eligible(schedule, student_id, invites, since):
    if invites.get(schedule.id) and student_id not in invites[schedule.id]:
        return False
    return since is None or schedule.scheduled_at >= since - timedelta(days=1)


def compute_streaks(student_ids, now=None, grace_minutes=GRACE_MINUTES):
    """Return {student_id: info} for many students with a handful of queries."""
    now = now or datetime.utcnow()
    student_ids = list(student_ids)
    empty = {"current": 0, "best": 0, "attended": 0, "total": 0, "tier": None,
             "next_at": TIERS[0][0], "progress": 0, "live": []}
    if not student_ids:
        return {}

    cutoff = now - timedelta(minutes=grace_minutes)
    past = (Schedule.query
            .filter(Schedule.cancelled.is_(False), Schedule.scheduled_at <= cutoff)
            .order_by(Schedule.scheduled_at.asc()).all())
    running = (Schedule.query
               .filter(Schedule.cancelled.is_(False), Schedule.scheduled_at > cutoff, Schedule.scheduled_at <= now)
               .order_by(Schedule.scheduled_at.asc()).all())
    if not past and not running:
        return {sid: {**empty, "live": []} for sid in student_ids}

    sched_ids = [s.id for s in past + running]
    invites = {}
    for sched_id, stu_id in (db.session.query(ScheduleInvite.schedule_id, ScheduleInvite.student_id)
                             .filter(ScheduleInvite.schedule_id.in_(sched_ids))):
        invites.setdefault(sched_id, set()).add(stu_id)

    joined = {}
    for sched_id, stu_id in (db.session.query(ScheduleJoin.schedule_id, ScheduleJoin.student_id)
                             .filter(ScheduleJoin.schedule_id.in_(sched_ids), ScheduleJoin.student_id.in_(student_ids))):
        joined.setdefault(stu_id, set()).add(sched_id)

    # attendance rows, grouped per (student, teacher) and sorted, so a class can be matched by time
    earliest = min(s.scheduled_at for s in past + running) - BEFORE
    marks = {}
    for stu_id, teacher_id, when in (db.session.query(Attendance.student_id, Attendance.teacher_id, Attendance.date)
                                     .filter(Attendance.student_id.in_(student_ids), Attendance.date >= earliest)
                                     .order_by(Attendance.date.asc())):
        marks.setdefault((stu_id, teacher_id), []).append(when)

    def attended(schedule, sid):
        if schedule.id in joined.get(sid, ()):
            return True
        times = marks.get((sid, schedule.teacher_id))
        if not times:
            return False
        i = bisect_left(times, schedule.scheduled_at - BEFORE)
        return i < len(times) and times[i] <= schedule.scheduled_at + AFTER

    created = {u.id: u.created_at for u in User.query.filter(User.id.in_(student_ids)).all()}

    result = {}
    for sid in student_ids:
        since = created.get(sid)
        mine = [s for s in past if _eligible(s, sid, invites, since)]
        hits = [attended(s, sid) for s in mine]

        best = run = 0
        for ok in hits:
            run = run + 1 if ok else 0
            best = max(best, run)
        current = run                      # the run that is still open at the newest class

        live = [{"title": s.title, "at": s.scheduled_at, "minutes_left": max(1, int((s.scheduled_at - cutoff).total_seconds() // 60))}
                for s in running if _eligible(s, sid, invites, since) and not attended(s, sid)]

        nxt = _next_target(current)
        floor = max([t[0] for t in TIERS if t[0] <= current], default=0)
        progress = 100 if nxt is None else int(round((current - floor) / (nxt - floor) * 100))
        result[sid] = {
            "current": current, "best": best,
            "attended": sum(hits), "total": len(mine),
            "tier": tier_for(current), "next_at": nxt, "progress": progress, "live": live,
        }
    return result


def attendance_streak(student_id, now=None):
    return compute_streaks([student_id], now=now).get(student_id)
