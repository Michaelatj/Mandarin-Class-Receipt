"""
services/streaks.py - attendance streaks for scheduled classes.

A streak counts the scheduled classes a student attended in a row, going back from the most
recent one that has started. It runs over every class since the student registered, not per
month: missing a single class resets it to zero (the best streak is kept as history). A class
counts for a student if it is open to everyone or the student was invited, it was not
cancelled, and it was held after the student registered.

The teacher can override a class by hand: marked present counts as attended, marked absent
(a ScheduleAbsent row) never counts, even if the student submitted attendance near that time.

A student attended a class when any of these is true:
  * they pressed Join for it (online) or checked in to its roll call (offline),
  * they submitted attendance with the normal attendance button, or the teacher recorded it,
    close to the class time or on the same day (WIB) as the class.
That way a student who shows up and is recorded through the normal attendance button is not
punished, and a student who does none of these loses the streak. One plain attendance counts for
one class only, so two classes in a day need two attendances.

Class times are WIB wall-clock times and attendance is stored in UTC, so classes are always
compared through Schedule.start_utc.

A class that started less than GRACE_MINUTES ago is not counted yet, because the student can
still join; it is listed in "live" so the app can remind them to attend to keep the streak.
"""
from bisect import bisect_left
from datetime import datetime, timedelta

from .. import db
from ..models import WIB_OFFSET, Attendance, Schedule, ScheduleAbsent, ScheduleInvite, ScheduleJoin, User

GRACE_MINUTES = 60          # after this long, a class nobody attended counts as missed
BEFORE = timedelta(minutes=60)   # attendance this early before the class still counts for it
AFTER = timedelta(hours=4)       # and this long after it starts

# (classes in a row, css key, character, English name, Chinese name)
# Bronze is where everybody starts; the last tier has no upper limit.
TIERS = [
    (0,  "bronze",  "铜", "Bronze",  "青铜"),
    (5,  "silver",  "银", "Silver",  "白银"),
    (11, "gold",    "金", "Gold",    "黄金"),
    (18, "jade",    "翠", "Jade",    "翡翠"),
    (26, "dragon",  "龙", "Dragon",  "神龙"),
]


def tier_for(n):
    """The highest tier reached for a streak of n classes (never None, bronze is the floor)."""
    reached = TIERS[0]
    for t in TIERS:
        if n >= t[0]:
            reached = t
    need, key, char, name, zh = reached
    return {"min": need, "key": key, "char": char, "name": name, "zh": zh, "index": TIERS.index(reached)}


def _next_tier(n):
    for t in TIERS:
        if n < t[0]:
            return t
    return None


def _eligible(schedule, student_id, invites, since):
    if invites.get(schedule.id) and student_id not in invites[schedule.id]:
        return False
    return since is None or schedule.start_utc >= since - timedelta(days=1)


def _wib_day(utc_dt):
    return (utc_dt + WIB_OFFSET).date()


def make_matcher(sid, marks, joined, absent):
    """Return attended(schedule) for one student.

    marks  : {(student_id, teacher_id): [attendance datetimes in UTC, sorted]} of plain attendance
    joined : {student_id: {schedule ids}} the student joined or checked in to
    absent : {(schedule_id, student_id)} the teacher marked absent

    Classes must be asked about in time order, because one plain attendance is used up by the
    first class it matches."""
    used = set()

    def attended(schedule):
        if (schedule.id, sid) in absent:
            return False                       # the teacher said no
        if schedule.id in joined.get(sid, ()):
            return True
        times = marks.get((sid, schedule.teacher_id))
        if not times:
            return False
        start = schedule.start_utc
        # 1) close to the class time
        i = bisect_left(times, start - BEFORE)
        while i < len(times) and times[i] <= start + AFTER:
            if i not in used:
                used.add(i)
                return True
            i += 1
        # 2) anywhere on the same day (WIB), e.g. a student who sends it after getting home
        day = _wib_day(start)
        for i, t in enumerate(times):
            if i not in used and _wib_day(t) == day:
                used.add(i)
                return True
        return False

    return attended


def compute_streaks(student_ids, now=None, grace_minutes=GRACE_MINUTES):
    """Return {student_id: info} for many students with a handful of queries."""
    now = now or datetime.utcnow()
    student_ids = list(student_ids)
    empty = {"current": 0, "best": 0, "attended": 0, "total": 0, "tier": tier_for(0),
             "next_at": TIERS[1][0], "next_name": TIERS[1][3], "progress": 0, "live": []}
    if not student_ids:
        return {}

    cutoff = now - timedelta(minutes=grace_minutes)
    # scheduled_at is WIB wall-clock time, so "now" is shifted into WIB before it is compared in SQL
    cutoff_w, now_w = cutoff + WIB_OFFSET, now + WIB_OFFSET
    past = (Schedule.query
            .filter(Schedule.cancelled.is_(False), Schedule.scheduled_at <= cutoff_w)
            .order_by(Schedule.scheduled_at.asc()).all())
    running = (Schedule.query
               .filter(Schedule.cancelled.is_(False), Schedule.scheduled_at > cutoff_w, Schedule.scheduled_at <= now_w)
               .order_by(Schedule.scheduled_at.asc()).all())
    if not past and not running:
        return {sid: {**empty, "live": []} for sid in student_ids}

    sched_ids = [s.id for s in past + running]
    invites = {}
    for sched_id, stu_id in (db.session.query(ScheduleInvite.schedule_id, ScheduleInvite.student_id)
                             .filter(ScheduleInvite.schedule_id.in_(sched_ids))):
        invites.setdefault(sched_id, set()).add(stu_id)

    absent = set()
    for sched_id, stu_id in (db.session.query(ScheduleAbsent.schedule_id, ScheduleAbsent.student_id)
                             .filter(ScheduleAbsent.schedule_id.in_(sched_ids), ScheduleAbsent.student_id.in_(student_ids))):
        absent.add((sched_id, stu_id))

    sched_set = set(sched_ids)
    joined = {}
    claimed = set()                            # attendance rows that already belong to a joined class
    for sched_id, stu_id, att_id in (db.session.query(ScheduleJoin.schedule_id, ScheduleJoin.student_id,
                                                      ScheduleJoin.attendance_id)
                                     .filter(ScheduleJoin.student_id.in_(student_ids))):
        if sched_id in sched_set:
            joined.setdefault(stu_id, set()).add(sched_id)
        if att_id:
            claimed.add(att_id)

    # plain attendance rows (the normal attendance button, or typed in by the teacher), per
    # (student, teacher) and sorted, so a class can be matched to one by time
    earliest = min(s.start_utc for s in past + running) - timedelta(days=1)
    marks = {}
    for att_id, stu_id, teacher_id, when in (db.session.query(Attendance.id, Attendance.student_id,
                                                              Attendance.teacher_id, Attendance.date)
                                             .filter(Attendance.student_id.in_(student_ids), Attendance.date >= earliest)
                                             .order_by(Attendance.date.asc())):
        if att_id not in claimed:
            marks.setdefault((stu_id, teacher_id), []).append(when)

    created = {u.id: u.created_at for u in User.query.filter(User.id.in_(student_ids)).all()}

    result = {}
    for sid in student_ids:
        since = created.get(sid)
        attended = make_matcher(sid, marks, joined, absent)
        mine = [s for s in past if _eligible(s, sid, invites, since)]
        hits = [attended(s) for s in mine]

        best = run = 0
        for ok in hits:
            run = run + 1 if ok else 0
            best = max(best, run)
        current = run                      # the run that is still open at the newest class

        live = [{"title": s.title, "at": s.scheduled_at, "minutes_left": max(1, int((s.start_utc - cutoff).total_seconds() // 60))}
                for s in running if _eligible(s, sid, invites, since) and not attended(s)]

        tier = tier_for(current)
        nxt_tier = _next_tier(current)
        nxt = nxt_tier[0] if nxt_tier else None
        progress = 100 if nxt is None else int(round((current - tier["min"]) / (nxt - tier["min"]) * 100))
        result[sid] = {
            "current": current, "best": best,
            "attended": sum(hits), "total": len(mine),
            "tier": tier, "next_at": nxt, "next_name": nxt_tier[3] if nxt_tier else None,
            "progress": progress, "live": live,
        }
    return result


def attendance_streak(student_id, now=None):
    return compute_streaks([student_id], now=now).get(student_id)
