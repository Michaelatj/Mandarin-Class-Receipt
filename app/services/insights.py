"""
services/insights.py - numbers for the teacher's Insights tab: revenue, classes, students, quizzes.
Everything is calculated for one teacher from the data that is already stored; nothing new is
saved. Dates are stored in UTC and grouped by month in WIB (UTC+7) like the rest of the app.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from .. import db
from ..models import (Attendance, Quiz, QuizAttempt, Receipt, Schedule, ScheduleJoin,
                      StudentFee, User)
from . import quiz_logic as ql
from .streaks import compute_streaks

WIB = timedelta(hours=7)
MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DAYS_SHORT = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
DAYS_LONG = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def idr(n):
    """1250000 -> 'Rp 1.250.000'"""
    return "Rp " + f"{int(round(n or 0)):,}".replace(",", ".")


def idr_short(n):
    """For chart labels: 1250000 -> 'Rp 1,25 jt', 600000 -> 'Rp 600 rb'."""
    n = int(round(n or 0))
    if n >= 1_000_000_000:
        v, unit = n / 1_000_000_000, " M"
    elif n >= 1_000_000:
        v, unit = n / 1_000_000, " jt"
    elif n >= 1_000:
        v, unit = n / 1_000, " rb"
    else:
        return f"Rp {n}"
    text = f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return "Rp " + text + unit


def _wib(dt):
    return dt + WIB


def _month_key(dt):
    w = _wib(dt)
    return (w.year, w.month)


def _last_months(now, n=6):
    w = now + WIB
    y, m = w.year, w.month
    out = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _label(key):
    y, m = key
    return MONTHS_SHORT[m - 1] + (f" {str(y)[2:]}" if m == 1 else "")


def _pct_change(now_v, before_v):
    if not before_v:
        return None
    return round((now_v - before_v) / before_v * 100)


def _bars(values, key_list):
    top = max(values) if values and max(values) > 0 else 1
    return [round(v / top * 100, 1) for v in values]


def build_insights(teacher, now=None):
    now = now or datetime.utcnow()
    months = _last_months(now, 6)
    this_m, prev_m = months[-1], months[-2]
    labels = [_label(k) for k in months]

    # ───────── revenue ─────────
    receipts = [r for r in Receipt.query.filter_by(teacher_id=teacher.id).all() if (r.total_fee or 0) > 0]
    issued = defaultdict(int)
    collected = defaultdict(int)
    for r in receipts:
        issued[_month_key(r.issue_date or now)] += r.total_fee
        if r.paid:
            collected[_month_key(r.paid_at or r.issue_date or now)] += r.total_fee

    unpaid = [r for r in receipts if not r.paid]
    total_issued = sum(r.total_fee for r in receipts)
    total_paid = sum(r.total_fee for r in receipts if r.paid)
    outstanding = sum(r.total_fee for r in unpaid)

    by_student = {}
    for r in unpaid:
        row = by_student.setdefault(r.student_id, {"name": r.student_name, "amount": 0, "count": 0, "oldest_days": 0})
        row["amount"] += r.total_fee
        row["count"] += 1
        row["oldest_days"] = max(row["oldest_days"], (now - (r.issue_date or now)).days)
    owing = sorted(by_student.values(), key=lambda x: (-x["amount"], -x["oldest_days"]))[:6]

    iss_vals = [issued[k] for k in months]
    col_vals = [collected[k] for k in months]
    top = max(iss_vals + col_vals + [1])
    revenue_rows = [{
        "label": labels[i], "issued": iss_vals[i], "collected": col_vals[i],
        "issued_pct": round(iss_vals[i] / top * 100, 1), "collected_pct": round(col_vals[i] / top * 100, 1),
    } for i in range(len(months))]

    # compare the days of this month so far with the same days of last month, so the first
    # days of a month are not judged against a full month
    day_now = (now + WIB).day
    paid_events = [((r.paid_at or r.issue_date or now), r.total_fee) for r in receipts if r.paid]
    prev_same_days = sum(v for dt, v in paid_events if _month_key(dt) == prev_m and _wib(dt).day <= day_now)

    revenue = {
        "rows": revenue_rows,
        "collected_this": collected[this_m], "collected_prev": collected[prev_m],
        "collected_delta": _pct_change(collected[this_m], prev_same_days),
        "issued_this": issued[this_m],
        "outstanding": outstanding, "outstanding_count": len(unpaid),
        "oldest_unpaid_days": max([(now - (r.issue_date or now)).days for r in unpaid], default=0),
        "total_collected": total_paid,
        "paid_share": round(total_paid / total_issued * 100) if total_issued else None,
        "avg_receipt": round(total_issued / len(receipts)) if receipts else 0,
        "receipt_count": len(receipts),
        "owing": owing,
        "has_paid_at_gap": any(r.paid and not r.paid_at for r in receipts),
    }

    # ───────── classes ─────────
    start_utc = datetime(months[0][0], months[0][1], 1) - WIB
    att = (Attendance.query.filter(Attendance.teacher_id == teacher.id, Attendance.date >= start_utc).all())
    sessions = defaultdict(int)
    for a in att:
        sessions[_month_key(a.date)] += 1
    ses_vals = [sessions[k] for k in months]

    past = (Schedule.query.filter(Schedule.teacher_id == teacher.id, Schedule.cancelled.is_(False),
                                  Schedule.scheduled_at >= start_utc, Schedule.scheduled_at <= now).all())
    join_counts = {}
    if past:
        for sid, n in (db.session.query(ScheduleJoin.schedule_id, func.count(ScheduleJoin.id))
                       .filter(ScheduleJoin.schedule_id.in_([s.id for s in past]))
                       .group_by(ScheduleJoin.schedule_id)):
            join_counts[sid] = n
    online = defaultdict(int)
    offline = defaultdict(int)
    for s in past:
        (offline if s.is_offline else online)[_month_key(s.scheduled_at)] += 1
    avg_attendees = round(sum(join_counts.get(s.id, 0) for s in past) / len(past), 1) if past else None

    recent = [a for a in att if a.date >= now - timedelta(days=120)]
    weekday = [0] * 7
    hours = defaultdict(int)
    for a in recent:
        w = _wib(a.date)
        weekday[w.weekday()] += 1
        hours[w.hour] += 1
    wmax = max(weekday) if weekday and max(weekday) else 1
    top_hours = sorted(hours.items(), key=lambda kv: (-kv[1], kv[0]))[:3]

    prev_sessions_same_days = sum(1 for a in att if _month_key(a.date) == prev_m and _wib(a.date).day <= day_now)

    classes = {
        "labels": labels, "sessions": ses_vals,
        "sessions_pct": _bars(ses_vals, months),
        "sessions_this": sessions[this_m], "sessions_prev": sessions[prev_m],
        "sessions_delta": _pct_change(sessions[this_m], prev_sessions_same_days),
        "online": [online[k] for k in months], "offline": [offline[k] for k in months],
        "scheduled_total": len(past), "scheduled_offline": sum(1 for s in past if s.is_offline),
        "avg_attendees": avg_attendees,
        "weekday": [{"label": DAYS_SHORT[i], "full": DAYS_LONG[i], "n": weekday[i], "pct": round(weekday[i] / wmax * 100)} for i in range(7)],
        "busiest_day": DAYS_LONG[weekday.index(max(weekday))] if recent else None,
        "top_hours": [{"hour": f"{h:02d}:00", "n": n} for h, n in top_hours],
    }

    # ───────── students ─────────
    ids = set()
    for model in (Attendance, Receipt, StudentFee):
        ids |= {sid for (sid,) in db.session.query(model.student_id).filter(model.teacher_id == teacher.id).distinct()}
    students = User.query.filter(User.id.in_(ids), User.role == "student").all() if ids else []
    sid_list = [s.id for s in students]
    last_seen = {}
    if sid_list:
        for sid, last in (db.session.query(Attendance.student_id, func.max(Attendance.date))
                          .filter(Attendance.teacher_id == teacher.id, Attendance.student_id.in_(sid_list))
                          .group_by(Attendance.student_id)):
            last_seen[sid] = last
    cutoff = now - timedelta(days=30)
    active = [s for s in students if last_seen.get(s.id) and last_seen[s.id] >= cutoff]
    at_risk = sorted(
        ({"name": s.name(), "last": _wib(last_seen[s.id]), "days": (now - last_seen[s.id]).days}
         for s in students if last_seen.get(s.id) and last_seen[s.id] < cutoff),
        key=lambda x: -x["days"])[:8]
    new_by_month = defaultdict(int)
    for s in students:
        if s.created_at:
            new_by_month[_month_key(s.created_at)] += 1
    streaks = compute_streaks(sid_list) if sid_list else {}
    names = {s.id: s.name() for s in students}
    leaders = sorted(({"name": names[sid], "current": v["current"], "best": v["best"], "tier": v["tier"],
                       "attended": v["attended"], "total": v["total"]}
                      for sid, v in streaks.items() if v["current"] > 0),
                     key=lambda x: (-x["current"], -x["best"]))[:5]

    students_info = {
        "total": len(students), "active": len(active), "inactive": len(students) - len(active),
        "new_this": new_by_month[this_m], "new_prev": new_by_month[prev_m],
        "at_risk": at_risk, "leaders": leaders,
        "unbilled_note": None,
    }

    # ───────── quizzes ─────────
    quizzes = Quiz.query.filter_by(teacher_id=teacher.id).all()
    qmap = {q.id: q for q in quizzes}
    attempts = (QuizAttempt.query.filter(QuizAttempt.quiz_id.in_(list(qmap)), QuizAttempt.submitted_at.isnot(None))
                .limit(3000).all()) if qmap else []
    per_quiz = defaultdict(list)
    q_stats = defaultdict(lambda: [0, 0])      # (quiz_id, qid) -> [correct, seen]
    for at in attempts:
        per_quiz[at.quiz_id].append(at)
        quiz = qmap[at.quiz_id]
        for q in quiz.questions or []:
            value = ((at.answers or {}).get(q.get("id")) or {}).get("value")
            try:
                ok = bool(value is not None and ql.is_answer_correct(q, value))
            except Exception:
                ok = False
            stat = q_stats[(quiz.id, q.get("id"))]
            stat[1] += 1
            stat[0] += 1 if ok else 0
    quiz_rows = []
    for qid, lst in per_quiz.items():
        scores = [a.accuracy_score for a in lst if a.accuracy_score is not None]
        quiz_rows.append({"title": qmap[qid].title, "attempts": len(lst),
                          "students": len({a.student_id for a in lst}),
                          "avg": round(sum(scores) / len(scores)) if scores else None})
    quiz_rows.sort(key=lambda r: -r["attempts"])
    hardest = []
    for (quiz_id, question_id), (ok, seen) in q_stats.items():
        if seen < 2:
            continue
        quiz = qmap[quiz_id]
        q = next((x for x in (quiz.questions or []) if x.get("id") == question_id), None)
        if not q:
            continue
        text = (q.get("question") or "").strip()
        hardest.append({"text": text if len(text) <= 90 else text[:87] + "...", "quiz": quiz.title,
                        "rate": round(ok / seen * 100), "seen": seen})
    hardest.sort(key=lambda x: (x["rate"], -x["seen"]))

    return {
        "months": labels, "generated": _wib(now),
        "revenue": revenue, "classes": classes, "students": students_info,
        "quiz": {"count": len(quizzes), "attempts": len(attempts), "rows": quiz_rows[:8], "hardest": hardest[:5]},
    }
