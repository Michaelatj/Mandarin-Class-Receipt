"""
routes/schedule.py — Schedule Blueprint
Teacher: create / edit / cancel schedules
Student: view upcoming schedules, click Join (auto-marks attendance)
"""
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from .. import db
from ..models import User, Schedule, ScheduleJoin, ScheduleInvite, Attendance
from ..services.attendance import add_attendance
from ..services.i18n import tr, fmt_date

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

    s = Schedule(teacher_id=teacher.id, title=title, description=desc, meet_link=link, scheduled_at=dt)
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

    desc_html   = '<div class="sc-desc">'  + s.description + '</div>' if s.description else ''
    link_html   = '<div class="sc-link">🔗 <a href="' + s.meet_link + '" target="_blank" rel="noopener">' + s.meet_link + '</a></div>' if s.meet_link else ''
    
    if invited_names is not None:
        invite_html = '<span class="sc-invites specific">🎯 Specific students only</span>'
    else:
        inv_count = ScheduleInvite.query.filter_by(schedule_id=s.id).count()
        invite_html = '<span class="sc-invites specific">🎯 Specific students only</span>' if inv_count > 0 else '<span class="sc-invites open">🌐 All students</span>'

    action_btns = ''
    if not s.cancelled and not is_past:
        action_btns = (
            f'<button class="btn bgh bsm edit-sc-btn" data-id="{s.id}" data-title="{s.title}" data-desc="{s.description or ""}"'
            f' data-link="{s.meet_link or ""}" data-at="{at_iso}">✏️ Edit</button>'
            f'<button class="btn bdel-outline bsm cancel-sc-btn" data-id="{s.id}">✕ Cancel</button>'
        )
    
    # Tambah Duplicate button
    action_btns += (
        f'<button class="btn bgh bsm dup-sc-btn" data-id="{s.id}" data-title="{s.title}"'
        f' data-desc="{s.description or ""}" data-link="{s.meet_link or ""}" data-at="{at_iso}">📋 Duplicate</button>'
        f'<button class="btn bdel bsm delete-sc-btn" data-id="{s.id}">🗑</button>'
    )

    badge_label = 'CANCELLED' if s.cancelled else ('ENDED' if is_past else 'UPCOMING')

    # Checkbox untuk select
    checkbox_html = f'<input type="checkbox" class="sc-check" value="{s.id}" style="width:16px;height:16px;cursor:pointer;accent-color:var(--red);margin-top:2px;">'

    return (
        f'<div class="sc-card {status}" id="sc-{s.id}">'
        f'<div class="sc-head">'
        f'<div style="display:flex;gap:12px;flex:1;min-width:0;">'
        f'{checkbox_html}'
        f'<div style="min-width:0;flex:1">'
        f'<div class="sc-title">{s.title}</div>'
        f'<div class="sc-time">📅 {dt_fmt}</div>'
        f'</div></div>'
        f'<span class="sc-badge {status}">{badge_label}</span>'
        f'</div>{desc_html}{link_html}'
        f'<div class="sc-foot">'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">'
        f'<span class="sc-joined">👥 {getattr(s, "join_count", 0)} students joined</span>'
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
