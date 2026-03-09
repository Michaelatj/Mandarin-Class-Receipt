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
from ..models import User, Schedule, ScheduleJoin, Attendance
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
    """Attach .joined_by (set of student_ids) and .already_joined to each schedule."""
    for s in schedules:
        joins = ScheduleJoin.query.filter_by(schedule_id=s.id).all()
        s.joined_by   = {j.student_id for j in joins}
        s.join_count  = len(s.joined_by)
        s.already_joined = viewer_id in s.joined_by if viewer_id else False
        teacher = db.session.get(User, s.teacher_id)
        s.teacher_name = teacher.name() if teacher else "?"
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
    db.session.commit()
    logger.info("Schedule #%d created by teacher %s", s.id, teacher.name())

    if _is_ajax():
        card_html = _render_schedule_card_teacher(s, teacher)
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

    db.session.commit()
    if _is_ajax(): return jsonify(ok=True, msg=tr("ok_saved"))
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
        return jsonify(ok=True, already=False,
                       meet_link=s.meet_link,
                       msg="Attendance marked! Opening Meet…")
    if s.meet_link:
        return redirect(s.meet_link)
    flash("Attendance marked!", "ok")
    return redirect(url_for("student.dashboard"))


# ── Internal HTML renderer (for AJAX card injection) ─────
def _render_schedule_card_teacher(s, teacher):
    dt  = s.scheduled_at
    now = datetime.utcnow()
    is_past = dt < now
    status  = "cancelled" if s.cancelled else ("past" if is_past else "upcoming")
    dt_fmt  = dt.strftime("%a, %d %b %Y · %H:%M")
    return f"""
<div class="sc-card {status}" id="sc-{s.id}" data-id="{s.id}">
  <div class="sc-head">
    <div>
      <div class="sc-title">{s.title}</div>
      <div class="sc-time">📅 {dt_fmt}</div>
    </div>
    <span class="sc-badge {status}">{status.upper()}</span>
  </div>
  {f'<div class="sc-desc">{s.description}</div>' if s.description else ''}
  {f'<div class="sc-link">🔗 <a href="{s.meet_link}" target="_blank">{s.meet_link}</a></div>' if s.meet_link else ''}
  <div class="sc-foot">
    <span class="sc-joined">👥 0 joined</span>
    <div style="display:flex;gap:7px">
      {"" if s.cancelled or is_past else f'<button class="btn bdel-outline bsm cancel-sc-btn" data-id="{s.id}">Cancel</button>'}
      <button class="btn bdel bsm delete-sc-btn" data-id="{s.id}">Delete</button>
    </div>
  </div>
</div>"""
