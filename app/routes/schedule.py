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

# ── Auth helpers ──────────────────────────────────────────
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

# ── Helpers ───────────────────────────────────────────────
def _enrich(schedules, viewer_id=None, viewer_role=None):
    """Attach .joined_by, .already_joined, .invited_ids to each schedule."""
    for s in schedules:
        joins = ScheduleJoin.query.filter_by(schedule_id=s.id).all()
        s.joined_by   = {j.student_id for j in joins}
        s.join_count  = len(s.joined_by)
        s.already_joined = viewer_id in s.joined_by if viewer_id else False
        teacher = db.session.get(User, s.teacher_id)
        s.teacher_name = teacher.name() if teacher else "?"
        invites = ScheduleInvite.query.filter_by(schedule_id=s.id).all()
        s.invited_ids = {inv.student_id for inv in invites}
        s.invite_all  = len(s.invited_ids) == 0  # empty = all students invited
    return schedules


# ════════════════════════════════════════════════════════
#  TEACHER ROUTES
# ════════════════════════════════════════════════════════

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

    # Normalise Meet link
    if link and not link.startswith("http"):
        link = "https://" + link

    s = Schedule(teacher_id=teacher.id, title=title,
                 description=desc, meet_link=link, scheduled_at=dt)
    db.session.add(s)
    db.session.flush()  # get s.id before commit

    # Save per-student invites
    invited_ids = request.form.getlist("invited_students")
    for sid_str in invited_ids:
        try:
            sid = int(sid_str)
            db.session.add(ScheduleInvite(schedule_id=s.id, student_id=sid))
        except (ValueError, TypeError):
            pass

    db.session.commit()
    logger.info("Schedule #%d created by teacher %s (invites: %s)", s.id, teacher.name(), invited_ids)

    # Build invited names for card display
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
    s.description = request.form.get("description", s.description or "").strip()[:500]
    link          = request.form.get("meet_link", s.meet_link or "").strip()[:500]
    if link and not link.startswith("http"):
        link = "https://" + link
    s.meet_link   = link

    dt_str = request.form.get("scheduled_at", "")
    try:
        s.scheduled_at = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        pass

    # Update invites if provided
    if "update_invites" in request.form:
        ScheduleInvite.query.filter_by(schedule_id=sid).delete()
        for sid_str in request.form.getlist("invited_students"):
            try:
                db.session.add(ScheduleInvite(schedule_id=sid, student_id=int(sid_str)))
            except (ValueError, TypeError):
                pass

    db.session.commit()

    if _is_ajax():
        invited_names = [db.session.get(User, inv.student_id).name()
                         for inv in ScheduleInvite.query.filter_by(schedule_id=sid).all()
                         if db.session.get(User, inv.student_id)]
        card_html = _render_schedule_card_teacher(s, teacher, invited_names)
        return jsonify(ok=True, msg=tr("ok_saved"),
                       schedule_id=sid,
                       card_html=card_html,
                       title=s.title,
                       description=s.description or '',
                       meet_link=s.meet_link or '',
                       dt_fmt=s.scheduled_at.strftime("%a, %d %b %Y · %H:%M"),
                       at_iso=s.scheduled_at.strftime("%Y-%m-%dT%H:%M"))
    flash(tr("ok_saved"), "ok")
    return redirect(url_for("teacher.dashboard"))


@schedule_bp.route("/teacher/schedule/invites/<int:sid>")
@teacher_required
def get_invites(sid):
    """Return invited student IDs for a schedule (used by edit modal)."""
    invites = ScheduleInvite.query.filter_by(schedule_id=sid).all()
    return jsonify(invited_ids=[inv.student_id for inv in invites])


@schedule_bp.route("/teacher/schedule/students/<int:sid>")
@teacher_required
def get_students(sid):
    """Return all students with join status for a schedule card."""
    s = Schedule.query.get(sid)
    if not s:
        return jsonify(ok=False, msg="Not found")

    all_students = User.query.filter_by(role="student").all()
    joins = {j.student_id for j in ScheduleJoin.query.filter_by(schedule_id=sid).all()}
    invites = {i.student_id for i in ScheduleInvite.query.filter_by(schedule_id=sid).all()}
    invite_all = len(invites) == 0

    students = []
    for st in all_students:
        # Only include if invited (or open to all)
        if invite_all or st.id in invites:
            students.append({
                "id":     st.id,
                "name":   st.name(),
                "joined": st.id in joins,
            })

    return jsonify(ok=True, students=students, invite_all=invite_all)


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


# ════════════════════════════════════════════════════════
#  STUDENT ROUTES
# ════════════════════════════════════════════════════════

@schedule_bp.route("/schedule/join/<int:sid>", methods=["POST"])
@login_required
def join(sid):
    """Student clicks Join — opens Meet link AND auto-marks attendance."""
    student = _user()
    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Not a student")
        return redirect(url_for("student.dashboard"))

    s = Schedule.query.get(sid)
    if not s or s.cancelled:
        if _is_ajax(): return jsonify(ok=False, msg="Class not found or cancelled")
        return redirect(url_for("student.dashboard"))

    # Prevent double-join
    existing = ScheduleJoin.query.filter_by(schedule_id=sid, student_id=student.id).first()
    if existing:
        if _is_ajax():
            return jsonify(ok=True, already=True,
                           meet_link=s.meet_link,
                           msg="You already joined this class")
        return redirect(s.meet_link or url_for("student.dashboard"))

    # Auto-mark attendance
    att = add_attendance(student_id=student.id,
                         teacher_id=s.teacher_id,
                         date=s.scheduled_at,
                         note=f"Joined: {s.title}")

    sj = ScheduleJoin(schedule_id=sid, student_id=student.id,
                      attendance_id=att.id if att else None)
    db.session.add(sj)
    db.session.commit()
    logger.info("Student %s joined schedule #%d", student.name(), sid)

    if _is_ajax():
        # Build progress_html identical to mark_attendance route
        unbilled = Attendance.query.filter_by(student_id=student.id, billed=False)\
                       .order_by(Attendance.date.asc()).all()
        total_sessions = Attendance.query.filter_by(student_id=student.id).count()
        for a in unbilled:
            t = db.session.get(User, a.teacher_id)
            a.teacher_name = t.name() if t else "?"
        cnt = len(unbilled)
        pct = min(int(cnt / 8 * 100), 100)
        rem = 8 - cnt
        rem_txt = f"{rem} more {'class' if rem==1 else 'classes'} until next receipt"
        cells = ""
        for i in range(8):
            if i < cnt:
                a = unbilled[i]
                from ..services.i18n import to_wib
                ld = to_wib(a.date)
                cells += (f'<div class="cycle-cell done">'
                          f'<div class="cell-num">#{i+1}</div>'
                          f'<div class="cell-day">{ld.strftime("%a")}</div>'
                          f'<div class="cell-date">{ld.strftime("%d %b")}</div>'
                          f'<div class="cell-time">{ld.strftime("%H:%M")}</div>'
                          f'</div>')
            else:
                cells += (f'<div class="cycle-cell empty-cell">'
                          f'<div class="cell-num">#{i+1}</div>'
                          f'<div class="cell-empty">—</div>'
                          f'</div>')
        if cnt > 0:
            teacher_name = s.teacher_name if hasattr(s, 'teacher_name') else (db.session.get(User, s.teacher_id).name() if db.session.get(User, s.teacher_id) else '?')
            progress_html = (
                f'<div class="cycle-card">'
                f'<div class="cycle-header"><div>'
                f'<div class="cycle-title">{cnt} / 8 classes done</div>'
                f'<div class="cycle-sub">with {teacher_name} · {rem_txt}</div>'
                f'</div><div class="cycle-pct">{pct}%</div></div>'
                f'<div class="cycle-bar"><div class="cycle-fill" style="width:{pct}%"></div></div>'
                f'<div class="cycle-grid">{cells}</div>'
                f'</div>'
            )
        else:
            progress_html = '<div class="empty-state"><div class="empty-icon">📊</div><div class="empty-title">No progress yet</div></div>'

        return jsonify(ok=True, already=False,
                       meet_link=s.meet_link,
                       msg="Attendance marked! Opening Meet…",
                       progress_html=progress_html,
                       cycle_count=cnt,
                       total_sessions=total_sessions)
    if s.meet_link:
        return redirect(s.meet_link)
    flash("Attendance marked!", "ok")
    return redirect(url_for("student.dashboard"))


# ── Internal HTML renderer (for AJAX card injection) ─────
def _render_schedule_card_teacher(s, teacher, invited_names=None):
    dt      = s.scheduled_at
    now     = datetime.utcnow()
    is_past = dt < now
    status  = "cancelled" if s.cancelled else ("past" if is_past else "upcoming")
    dt_fmt  = dt.strftime("%a, %d %b %Y · %H:%M")
    at_iso  = dt.strftime("%Y-%m-%dT%H:%M")

    desc_html   = '<div class="sc-desc">'  + s.description + '</div>' if s.description else ''
    link_html   = '<div class="sc-link">🔗 <a href="' + s.meet_link + '" target="_blank" rel="noopener">' + s.meet_link + '</a></div>' if s.meet_link else ''
    invite_html = ''
    if invited_names:
        invite_html = '<span class="sc-invites">🎯 Specific students only</span>'
    else:
        invite_html = '<span class="sc-invites open">🌐 All students</span>'

    action_btns = ''
    if not s.cancelled and not is_past:
        action_btns = (
            '<button class="btn bgh bsm edit-sc-btn"'
            ' data-id="'    + str(s.id)   + '"'
            ' data-title="' + s.title     + '"'
            ' data-desc="'  + (s.description or '') + '"'
            ' data-link="'  + (s.meet_link or '')   + '"'
            ' data-at="'    + at_iso      + '">✏️ Edit</button>'
            '<button class="btn bdel-outline bsm cancel-sc-btn" data-id="' + str(s.id) + '">✕ Cancel</button>'
        )
    action_btns += '<button class="btn bdel bsm delete-sc-btn" data-id="' + str(s.id) + '">🗑</button>'

    badge_label = 'CANCELLED' if s.cancelled else ('ENDED' if is_past else 'UPCOMING')

    return (
        '<div class="sc-card ' + status + '" id="sc-' + str(s.id) + '">'
        '<div class="sc-head">'
        '<div style="min-width:0;flex:1">'
        '<div class="sc-title">' + s.title + '</div>'
        '<div class="sc-time">📅 ' + dt_fmt + '</div>'
        '</div>'
        '<span class="sc-badge ' + status + '">' + badge_label + '</span>'
        '</div>'
        + desc_html + link_html +
        '<div class="sc-foot">'
        '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">'
        '<span class="sc-joined">👥 0 students joined</span>'
        + invite_html +
        '</div>'
        '<div style="display:flex;gap:7px;flex-shrink:0">'
        + action_btns +
        '</div>'
        '</div>'
        '</div>'
    )
