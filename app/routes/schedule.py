"""
routes/schedule.py — Schedule Blueprint
Teacher: create / edit / cancel schedules
Student: view upcoming schedules, click Join (auto-marks attendance)
"""
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from markupsafe import escape
from .. import db
from ..models import User, Schedule, ScheduleJoin, ScheduleInvite, ScheduleAbsent, Attendance
from ..services.attendance import add_attendance, delete_attendance
from ..services.i18n import tr, fmt_date
from ..services.security import is_rate_limited, record_failed_attempt, clear_attempts

logger = logging.getLogger(__name__)
schedule_bp = Blueprint("schedule", __name__)

def _user():
    return db.session.get(User, session.get("user_id"))

def _is_ajax():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return w

def teacher_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        u = _user()
        if not u or u.role != "teacher":
            return redirect(url_for("student.dashboard"))
        return f(*a, **kw)
    return w

def _enrich(schedules, viewer_id=None, viewer_role=None):
    for s in schedules:
        joins = ScheduleJoin.query.filter_by(schedule_id=s.id).all()
        s.joined_by   = {j.student_id for j in joins}
        s.join_count  = len(s.joined_by)
        s.already_joined = viewer_id in s.joined_by if viewer_id else False
        teacher = db.session.get(User, s.teacher_id)
        s.teacher_name = teacher.name() if teacher else "?"
        invites = ScheduleInvite.query.filter_by(schedule_id=s.id).all()
        s.invited_ids = {inv.student_id for inv in invites}
        s.invite_all  = len(s.invited_ids) == 0 
    return schedules

@schedule_bp.route("/teacher/schedule/create", methods=["POST"])
@teacher_required
def create():
    teacher = _user()
    title   = request.form.get("title", "").strip()[:200]
    desc    = request.form.get("description", "").strip()[:500]
    link    = request.form.get("meet_link", "").strip()[:500]
    dt_str  = request.form.get("scheduled_at", "")
    mode     = "offline" if request.form.get("mode") == "offline" else "online"
    location = request.form.get("location", "").strip()[:200] if mode == "offline" else ""
    if mode == "offline":
        link = ""          # no Meet link for an in-person class

    if not title:
        if _is_ajax(): return jsonify(ok=False, msg="Title is required")
        flash("Title is required", "err"); return redirect(url_for("teacher.dashboard"))

    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        if _is_ajax(): return jsonify(ok=False, msg="Invalid date/time")
        flash("Invalid date/time", "err"); return redirect(url_for("teacher.dashboard"))

    if link and not link.startswith("http"):
        link = "https://" + link

    s = Schedule(teacher_id=teacher.id, title=title, description=desc, meet_link=link, scheduled_at=dt,
                 mode=mode, location=location)
    db.session.add(s)
    db.session.flush() 

    invited_ids = request.form.getlist("invited_students")
    for sid_str in invited_ids:
        try:
            sid = int(sid_str)
            db.session.add(ScheduleInvite(schedule_id=s.id, student_id=sid))
        except (ValueError, TypeError):
            pass

    db.session.commit()

    invited_names = []
    for sid_str in invited_ids:
        u = db.session.get(User, int(sid_str))
        if u: invited_names.append(u.name())

    if _is_ajax():
        card_html = _render_schedule_card_teacher(s, teacher, invited_names)
        return jsonify(ok=True, msg="Class scheduled!", card_html=card_html, schedule_id=s.id)
    flash("Class scheduled!", "ok")
    return redirect(url_for("teacher.dashboard"))

@schedule_bp.route("/teacher/schedule/edit/<int:sid>", methods=["POST"])
@teacher_required
def edit(sid):
    teacher = _user()
    s = Schedule.query.filter_by(id=sid, teacher_id=teacher.id).first()
    if not s:
        if _is_ajax(): return jsonify(ok=False, msg="Not found")
        return redirect(url_for("teacher.dashboard"))

    s.title       = request.form.get("title", s.title).strip()[:200]
    s.description = request.form.get("description", s.description).strip()[:500]
    link          = request.form.get("meet_link", s.meet_link).strip()[:500]
    if link and not link.startswith("http"):
        link = "https://" + link
    s.mode        = "offline" if request.form.get("mode", s.mode) == "offline" else "online"
    if s.is_offline:
        s.location  = request.form.get("location", s.location or "").strip()[:200]
        link        = ""
    else:
        s.location  = ""
        s.rollcall_code, s.rollcall_until = None, None
    s.meet_link   = link
    dt_str        = request.form.get("scheduled_at", "")
    try:
        s.scheduled_at = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        pass

    ScheduleInvite.query.filter_by(schedule_id=sid).delete()
    for sid_str in request.form.getlist("invited_students"):
        try:
            db.session.add(ScheduleInvite(schedule_id=sid, student_id=int(sid_str)))
        except (ValueError, TypeError):
            pass

    db.session.commit()
    if _is_ajax():
        dt_fmt = s.scheduled_at.strftime("%a, %d %b %Y · %H:%M")
        at_iso = s.scheduled_at.strftime("%Y-%m-%dT%H:%M")
        invites = ScheduleInvite.query.filter_by(schedule_id=sid).all()
        invite_all = len(invites) == 0
        return jsonify(ok=True, msg=tr("ok_saved"), schedule_id=sid, title=s.title,
                       description=s.description or '', meet_link=s.meet_link or '',
                       mode=s.mode or 'online', location=s.location or '',
                       dt_fmt=dt_fmt, at_iso=at_iso, invite_all=invite_all)
    flash(tr("ok_saved"), "ok")
    return redirect(url_for("teacher.dashboard"))

@schedule_bp.route("/teacher/schedule/cancel/<int:sid>", methods=["POST"])
@teacher_required
def cancel(sid):
    teacher = _user()
    s = Schedule.query.filter_by(id=sid, teacher_id=teacher.id).first()
    if not s:
        if _is_ajax(): return jsonify(ok=False, msg="Not found")
        return redirect(url_for("teacher.dashboard"))
    s.cancelled = True
    db.session.commit()
    if _is_ajax(): return jsonify(ok=True, msg="Class cancelled")
    flash("Class cancelled", "ok")
    return redirect(url_for("teacher.dashboard"))

@schedule_bp.route("/teacher/schedule/delete/<int:sid>", methods=["POST"])
@teacher_required
def delete(sid):
    teacher = _user()
    s = Schedule.query.filter_by(id=sid, teacher_id=teacher.id).first()
    if not s:
        if _is_ajax(): return jsonify(ok=False, msg="Not found")
        return redirect(url_for("teacher.dashboard"))
    ScheduleJoin.query.filter_by(schedule_id=sid).delete()
    ScheduleInvite.query.filter_by(schedule_id=sid).delete()
    ScheduleAbsent.query.filter_by(schedule_id=sid).delete()
    db.session.delete(s)
    db.session.commit()
    if _is_ajax(): return jsonify(ok=True, msg="Deleted")
    flash(tr("ok_deleted"), "ok")
    return redirect(url_for("teacher.dashboard"))

@schedule_bp.route("/teacher/schedule/bulk_delete", methods=["POST"])
@teacher_required
def bulk_delete():
    teacher = _user()
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify(ok=False, msg="No IDs provided")
    
    ids = data['ids']
    schedules = Schedule.query.filter(Schedule.id.in_(ids), Schedule.teacher_id==teacher.id).all()
    valid_ids = [s.id for s in schedules]
    
    if valid_ids:
        ScheduleJoin.query.filter(ScheduleJoin.schedule_id.in_(valid_ids)).delete(synchronize_session=False)
        ScheduleInvite.query.filter(ScheduleInvite.schedule_id.in_(valid_ids)).delete(synchronize_session=False)
        ScheduleAbsent.query.filter(ScheduleAbsent.schedule_id.in_(valid_ids)).delete(synchronize_session=False)
        Schedule.query.filter(Schedule.id.in_(valid_ids)).delete(synchronize_session=False)
        db.session.commit()
        
    return jsonify(ok=True, msg=f"Deleted {len(valid_ids)} classes", deleted_ids=valid_ids)

@schedule_bp.route("/schedule/join/<int:sid>", methods=["POST"])
@login_required
def join(sid):
    student = _user()
    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Not a student")
        return redirect(url_for("student.dashboard"))

    s = Schedule.query.get(sid)
    if not s or s.cancelled:
        if _is_ajax(): return jsonify(ok=False, msg="Class not found or cancelled")
        return redirect(url_for("student.dashboard"))

    existing = ScheduleJoin.query.filter_by(schedule_id=sid, student_id=student.id).first()
    if existing:
        if _is_ajax():
            return jsonify(ok=True, already=True, meet_link=s.meet_link, msg="You already joined this class")
        return redirect(s.meet_link or url_for("student.dashboard"))

    # --- BUG 1 FIX: 90-Min Cooldown Radar 📡 ---
    COOLDOWN_SECONDS = 90 * 60
    last_att = (Attendance.query
                .filter(Attendance.student_id==student.id,
                        Attendance.source.in_(['student','join']))
                .order_by(Attendance.date.desc())
                .first())
    
    cooldown_blocked = False
    att = None

    # Check if they just submitted an attendance recently
    if last_att:
        elapsed_sec = (datetime.utcnow() - last_att.date).total_seconds()
        if 0 < elapsed_sec < COOLDOWN_SECONDS:
            cooldown_blocked = True
            att = last_att  # Link to the existing one! No double records! 🛑

    # Only create a new attendance if they passed the cooldown
    if not cooldown_blocked:
        att = add_attendance(student_id=student.id, teacher_id=s.teacher_id,
                             date=datetime.utcnow(), note=f"Joined: {s.title}", source='join')

    sj = ScheduleJoin(schedule_id=sid, student_id=student.id, attendance_id=att.id if att else None)
    db.session.add(sj)
    db.session.commit()

    msg = "Opening Meet…" if not cooldown_blocked else "Joining Meet (attendance already recorded in last 90 min)"

    if _is_ajax():
        from ..models import Attendance as _Att
        unbilled_cnt   = _Att.query.filter_by(student_id=student.id, billed=False).count()
        total_sessions = _Att.query.filter_by(student_id=student.id).count()
        return jsonify(ok=True, already=False, meet_link=s.meet_link, msg=msg,
                       cooldown_blocked=cooldown_blocked, cycle_count=unbilled_cnt, total_sessions=total_sessions)
    if s.meet_link:
        return redirect(s.meet_link)
    flash("Attendance marked!", "ok")
    return redirect(url_for("student.dashboard"))

def _render_schedule_card_teacher(s, teacher, invited_names=None):
    dt      = s.scheduled_at
    now     = datetime.utcnow()
    is_past = dt < now
    status  = "cancelled" if s.cancelled else ("past" if is_past else "upcoming")
    dt_fmt  = dt.strftime("%a, %d %b %Y · %H:%M")
    at_iso  = dt.strftime("%Y-%m-%dT%H:%M")
    e       = lambda v: str(escape(v or ""))
    offline = s.is_offline

    desc_html = f'<div class="sc-desc">{e(s.description)}</div>' if s.description else ''
    if offline:
        link_html = f'<div class="sc-link sc-loc">📍 <span class="sc-loc-text">{e(s.location) or "Offline class"}</span></div>'
    elif s.meet_link:
        link_html = f'<div class="sc-link">🔗 <a href="{e(s.meet_link)}" target="_blank" rel="noopener">{e(s.meet_link)}</a></div>'
    else:
        link_html = ''

    if invited_names is not None:
        invite_html = '<span class="sc-invites specific">🎯 Specific students only</span>'
    else:
        inv_count = ScheduleInvite.query.filter_by(schedule_id=s.id).count()
        invite_html = ('<span class="sc-invites specific">🎯 Specific students only</span>' if inv_count > 0
                       else '<span class="sc-invites open">🌐 All students</span>')

    data = (f'data-id="{s.id}" data-title="{e(s.title)}" data-desc="{e(s.description)}" data-link="{e(s.meet_link)}"'
            f' data-at="{at_iso}" data-mode="{e(s.mode or "online")}" data-location="{e(s.location)}"')
    action_btns = ''
    if not s.cancelled:
        label = '点名 Attendance' if offline else '👥 Attendance'
        action_btns += (f'<button class="btn br bsm rollcall-btn" data-id="{s.id}" data-title="{e(s.title)}"'
                        f' data-mode="{"offline" if offline else "online"}">{label}</button>')
    if not s.cancelled and not is_past:
        action_btns += (f'<button class="btn bgh bsm edit-sc-btn" {data}>✏️ Edit</button>'
                        f'<button class="btn bdel-outline bsm cancel-sc-btn" data-id="{s.id}">✕ Cancel</button>')
    action_btns += (f'<button class="btn bgh bsm dup-sc-btn" {data}>📋 Duplicate</button>'
                    f'<button class="btn bdel bsm delete-sc-btn" data-id="{s.id}">🗑</button>')

    badge_label = 'CANCELLED' if s.cancelled else ('ENDED' if is_past else 'UPCOMING')
    mode_pill = '<span class="sc-mode offline">Offline</span>' if offline else ''
    checkbox_html = (f'<input type="checkbox" class="sc-check" value="{s.id}" '
                     'style="width:16px;height:16px;cursor:pointer;accent-color:var(--red);margin-top:2px;">')
    joined_word = "present" if offline else "joined"

    return (
        f'<div class="sc-card {status}" id="sc-{s.id}">'
        f'<div class="sc-head">'
        f'<div style="display:flex;gap:12px;flex:1;min-width:0;">'
        f'{checkbox_html}'
        f'<div style="min-width:0;flex:1">'
        f'<div class="sc-title">{e(s.title)}</div>'
        f'<div class="sc-time">📅 {dt_fmt} {mode_pill}</div>'
        f'</div></div>'
        f'<span class="sc-badge {status}">{badge_label}</span>'
        f'</div>{desc_html}{link_html}'
        f'<div class="sc-foot">'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">'
        f'<span class="sc-joined">👥 {getattr(s, "join_count", 0)} students {joined_word}</span>'
        f'{invite_html}</div>'
        f'<div style="display:flex;gap:7px;flex-shrink:0;flex-wrap:wrap;">{action_btns}</div>'
        f'</div></div>'
    )

@schedule_bp.route("/teacher/schedule/invites/<int:sid>", methods=["GET"])
@teacher_required
def get_invites(sid):
    teacher = _user()
    s = Schedule.query.filter_by(id=sid, teacher_id=teacher.id).first()
    if not s:
        return jsonify(ok=False, msg="Not found")
    invites = ScheduleInvite.query.filter_by(schedule_id=sid).all()
    return jsonify(ok=True, invited_ids=[inv.student_id for inv in invites])


# ---------------------------------------------------------------------
# Roll call (点名) for offline classes
#   The teacher opens a roll call, which makes a 4-digit code. Students in the room type it in
#   their app, and that records their attendance. The teacher can also tick students by hand.
# ---------------------------------------------------------------------
ROLLCALL_MINUTES = (10, 20, 30, 60)


def _own_offline(sid):
    t = _user()
    s = Schedule.query.filter_by(id=sid, teacher_id=t.id).first()
    return t, s


def _own_class(sid):
    """Any class of this teacher that is not cancelled (online or offline)."""
    t, s = _own_offline(sid)
    if s and s.cancelled:
        s = None
    return t, s


def _class_students(s):
    """Students expected at this class: the invited ones, or every student when it is open to all."""
    ids = [i.student_id for i in ScheduleInvite.query.filter_by(schedule_id=s.id).all()]
    from ..services.prepaid import visible_students
    q = visible_students(s.teacher_id)
    if ids:
        q = q.filter(User.id.in_(ids))
    return sorted(q.all(), key=lambda u: u.name().lower())


def _rollcall_state(s):
    now = datetime.utcnow()
    present = {j.student_id for j in ScheduleJoin.query.filter_by(schedule_id=s.id).all()}
    absent = {a.student_id for a in ScheduleAbsent.query.filter_by(schedule_id=s.id).all()}
    is_open = s.is_offline and s.rollcall_open(now)
    return {
        "ok": True,
        "title": s.title,
        "location": s.location or "",
        "offline": s.is_offline,
        "started": s.scheduled_at <= now,
        "open": is_open,
        "code": s.rollcall_code if is_open else None,
        "seconds_left": int((s.rollcall_until - now).total_seconds()) if is_open else 0,
        "students": [{"id": u.id, "name": u.name(), "username": u.username,
                      "present": u.id in present, "absent": u.id in absent and u.id not in present}
                     for u in _class_students(s)],
        "present_count": len(present),
    }


def _mark_present(s, student, source="rollcall", note=None):
    """Record attendance for one student at a class (idempotent). Also lifts a manual absent mark."""
    ScheduleAbsent.query.filter_by(schedule_id=s.id, student_id=student.id).delete()
    join = ScheduleJoin.query.filter_by(schedule_id=s.id, student_id=student.id).first()
    if join:
        db.session.commit()
        return join
    att = add_attendance(student_id=student.id, teacher_id=s.teacher_id, date=datetime.utcnow(),
                         note=note or f"Roll call: {s.title}", source=source)
    join = ScheduleJoin(schedule_id=s.id, student_id=student.id, attendance_id=att.id if att else None)
    db.session.add(join)
    db.session.commit()
    return join


def _mark_absent(s, student, teacher):
    """The teacher says this student did not attend. Takes back the attendance this class created
    (when it is not billed yet and no other class uses it) and remembers the decision, so the
    streak does not count the class even if the student submitted something close to its time."""
    join = ScheduleJoin.query.filter_by(schedule_id=s.id, student_id=student.id).first()
    if join:
        att = db.session.get(Attendance, join.attendance_id) if join.attendance_id else None
        shared = bool(att) and ScheduleJoin.query.filter(ScheduleJoin.attendance_id == att.id,
                                                          ScheduleJoin.id != join.id).count() > 0
        db.session.delete(join)
        db.session.commit()
        if att and not shared and att.source in ("rollcall", "schedule", "manual") and not att.billed:
            delete_attendance(att.id, teacher.id)
    if not ScheduleAbsent.query.filter_by(schedule_id=s.id, student_id=student.id).first():
        db.session.add(ScheduleAbsent(schedule_id=s.id, student_id=student.id))
    db.session.commit()


@schedule_bp.route("/teacher/schedule/<int:sid>/rollcall", methods=["GET"])
@teacher_required
def rollcall_status(sid):
    _t, s = _own_class(sid)
    if not s:
        return jsonify(ok=False, msg="Class not found"), 404
    return jsonify(_rollcall_state(s))


@schedule_bp.route("/teacher/schedule/<int:sid>/rollcall/open", methods=["POST"])
@teacher_required
def rollcall_open(sid):
    _t, s = _own_offline(sid)
    if not s or not s.is_offline or s.cancelled:
        return jsonify(ok=False, msg="Not an offline class"), 404
    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get("minutes", 20))
    except (TypeError, ValueError):
        minutes = 20
    if minutes not in ROLLCALL_MINUTES:
        minutes = 20
    s.rollcall_code = f"{secrets.randbelow(10000):04d}"
    s.rollcall_until = datetime.utcnow() + timedelta(minutes=minutes)
    db.session.commit()
    return jsonify(_rollcall_state(s))


@schedule_bp.route("/teacher/schedule/<int:sid>/rollcall/close", methods=["POST"])
@teacher_required
def rollcall_close(sid):
    _t, s = _own_offline(sid)
    if not s or not s.is_offline:
        return jsonify(ok=False, msg="Not an offline class"), 404
    s.rollcall_code, s.rollcall_until = None, None
    db.session.commit()
    return jsonify(_rollcall_state(s))


@schedule_bp.route("/teacher/schedule/<int:sid>/rollcall/mark", methods=["POST"])
@teacher_required
def rollcall_mark(sid):
    t, s = _own_class(sid)
    if not s:
        return jsonify(ok=False, msg="Class not found"), 404
    data = request.get_json(silent=True) or {}
    student = db.session.get(User, data.get("student_id"))
    if not student or student.role != "student" or student not in _class_students(s):
        return jsonify(ok=False, msg="Student not found"), 404

    if data.get("present"):
        _mark_present(s, student, source="manual", note=f"Marked by teacher: {s.title}")
    else:
        _mark_absent(s, student, t)
    return jsonify(_rollcall_state(s))


@schedule_bp.route("/schedule/<int:sid>/rollcall", methods=["POST"])
@login_required
def rollcall_checkin(sid):
    student = _user()
    if not student or student.role != "student":
        return jsonify(ok=False, msg="Only students can check in"), 403
    s = db.session.get(Schedule, sid)
    if not s or s.cancelled or not s.is_offline:
        return jsonify(ok=False, msg="Class not found"), 404

    invited = {i.student_id for i in ScheduleInvite.query.filter_by(schedule_id=sid).all()}
    if invited and student.id not in invited:
        return jsonify(ok=False, msg="You are not invited to this class"), 403

    if ScheduleJoin.query.filter_by(schedule_id=sid, student_id=student.id).first():
        return jsonify(ok=True, already=True, msg="You are already marked present")
    if ScheduleAbsent.query.filter_by(schedule_id=sid, student_id=student.id).first():
        return jsonify(ok=False, msg="Your teacher marked you absent for this class. Please ask them.")

    if not s.rollcall_open():
        return jsonify(ok=False, msg="Roll call is not open yet. Ask your teacher to open it.")

    key = f"rc:{student.id}:{sid}"
    # a 4-digit code is easy to guess, so only 5 wrong tries per student per class every 5 minutes
    if is_rate_limited(key, max_attempts=5, lockout_secs=300):
        return jsonify(ok=False, msg="Too many wrong codes. Wait a few minutes and try again."), 429

    data = request.get_json(silent=True) or request.form
    code = str(data.get("code", "")).strip()
    if not hmac.compare_digest(code.encode(), (s.rollcall_code or "").encode()):
        record_failed_attempt(key)
        return jsonify(ok=False, msg="That code is not right. Check the code your teacher shows.")

    clear_attempts(key)
    _mark_present(s, student)
    return jsonify(ok=True, already=False, msg="You are marked present. 谢谢!")


@schedule_bp.route("/schedule/<int:sid>/attend", methods=["POST"])
@login_required
def attend(sid):
    """One tap "I was there" on a class card, for online and offline classes.
    When the teacher has opened a roll call code for an offline class, the code is asked for
    instead (needs_code), because the teacher chose to verify the room."""
    student = _user()
    if not student or student.role != "student":
        return jsonify(ok=False, msg="Only students can submit attendance"), 403
    s = db.session.get(Schedule, sid)
    if not s or s.cancelled:
        return jsonify(ok=False, msg="Class not found or cancelled"), 404

    invited = {i.student_id for i in ScheduleInvite.query.filter_by(schedule_id=sid).all()}
    if invited and student.id not in invited:
        return jsonify(ok=False, msg="You are not invited to this class"), 403

    if ScheduleJoin.query.filter_by(schedule_id=sid, student_id=student.id).first():
        return jsonify(ok=True, already=True, msg="Your attendance is already recorded")
    if ScheduleAbsent.query.filter_by(schedule_id=sid, student_id=student.id).first():
        return jsonify(ok=False, msg="Your teacher marked you absent for this class. Please ask them.")
    if not s.in_attend_window(datetime.now()):      # same clock the class card uses
        return jsonify(ok=False, msg="Attendance for this class is closed")
    if s.is_offline and s.rollcall_open():
        return jsonify(ok=False, needs_code=True, msg="Enter the code your teacher shows")

    _mark_present(s, student, source="schedule", note=f"Submitted: {s.title}")
    return jsonify(ok=True, already=False, msg="Attendance recorded. 谢谢!")
