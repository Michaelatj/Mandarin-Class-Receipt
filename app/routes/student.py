"""
routes/student.py — Student Blueprint
"""
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from .. import db
from ..models import User, Attendance, Receipt, Schedule, ScheduleJoin, ScheduleInvite
from ..services.attendance import add_attendance
from ..services.i18n import tr, fmt_date, random_quote

logger = logging.getLogger(__name__)
student_bp = Blueprint("student", __name__)

def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def _get_current_user():
    return db.session.get(User, session.get("user_id"))


@student_bp.route("/dashboard")
@login_required
def dashboard():
    user = _get_current_user()
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))
    if user.role == "teacher":
        return redirect(url_for("teacher.dashboard"))

    teachers       = User.query.filter_by(role="teacher").all()
    receipts       = Receipt.query.filter_by(student_id=user.id)\
                        .order_by(Receipt.issue_date.desc()).all()
    unbilled       = Attendance.query.filter_by(student_id=user.id, billed=False)\
                        .order_by(Attendance.date.asc()).all()
    total_sessions = Attendance.query.filter_by(student_id=user.id).count()

    for a in unbilled:
        t = db.session.get(User, a.teacher_id)
        a.teacher_name = t.name() if t else "?"

    from datetime import datetime as _dt
    all_schedules = (Schedule.query
                     .order_by(Schedule.scheduled_at.asc()).all())

    schedules = []
    for s in all_schedules:
        # Check if this student is invited (empty invite list = open to all)
        invites = ScheduleInvite.query.filter_by(schedule_id=s.id).all()
        invited_ids = {inv.student_id for inv in invites}
        if invited_ids and user.id not in invited_ids:
            continue  # not invited, skip

        joins = ScheduleJoin.query.filter_by(schedule_id=s.id).all()
        s.joined_by      = {j.student_id for j in joins}
        s.join_count     = len(s.joined_by)
        s.already_joined = user.id in s.joined_by
        teacher = db.session.get(User, s.teacher_id)
        s.teacher_name = teacher.name() if teacher else "?"
        schedules.append(s)

    upcoming = [s for s in schedules
                if not s.cancelled and s.scheduled_at > _dt.utcnow()
                and not s.already_joined]
    new_count = len(upcoming)
    unpaid_count = sum(1 for r in receipts if not r.paid)
    unbilled_count = len(unbilled)

    # ── Pip visibility: only show if count changed since user last saw it ──
    seen = session.get("seen_pips", {})
    show_classes_pip  = new_count      > 0 and new_count      != seen.get("classes",  -1)
    show_progress_pip = unbilled_count > 0 and unbilled_count != seen.get("progress", -1)
    show_receipts_pip = unpaid_count   > 0 and unpaid_count   != seen.get("receipts", -1)

    from flask import make_response
    fresh = session.pop("fresh_login", False)
    resp = make_response(render_template("student/dashboard.html",
        user=user, teachers=teachers, receipts=receipts,
        unbilled=unbilled, total_sessions=total_sessions,
        schedules=schedules, new_count=new_count,
        unpaid_count=unpaid_count, unbilled_count=unbilled_count,
        show_classes_pip=show_classes_pip,
        show_progress_pip=show_progress_pip,
        show_receipts_pip=show_receipts_pip,
        fresh_login=fresh,
        quote=random_quote()))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@student_bp.route("/set_tz", methods=["POST"])
def set_tz():
    """Called from JS on page load to persist the user's UTC offset in their session."""
    from flask import request as _req, jsonify as _j
    data = _req.get_json(silent=True) or {}
    offset = data.get("tz_offset", 0)
    try:
        session["tz_offset"] = int(offset)
    except (TypeError, ValueError):
        pass
    return _j(ok=True)


@student_bp.route("/mark_attendance", methods=["POST"])
@login_required
def mark_attendance():
    user = _get_current_user()
    if not user or user.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Not a student")
        return redirect(url_for("student.dashboard"))

    teacher_id = request.form.get("teacher_id", type=int)
    teacher    = db.session.get(User, teacher_id) if teacher_id else None
    if not teacher or teacher.role != "teacher":
        if _is_ajax(): return jsonify(ok=False, msg=tr("err_user"))
        flash(tr("err_user"), "err")
        return redirect(url_for("student.dashboard"))

    # Save tz_offset in session so Jinja templates can display local time
    tz_offset = request.form.get("tz_offset", type=int, default=0)
    session["tz_offset"] = tz_offset

    # 90-minute cooldown — block if student already submitted or joined a class recently.
    # Only check source='student' or source='join' records (not teacher manual adds).
    COOLDOWN_SECONDS = 90 * 60
    last_att = (Attendance.query
                .filter(Attendance.student_id==user.id,
                        Attendance.source.in_(['student','join']))
                .order_by(Attendance.date.desc())
                .first())
    if last_att:
        elapsed_sec = (datetime.utcnow() - last_att.date).total_seconds()
        if 0 < elapsed_sec < COOLDOWN_SECONDS:
            wait = max(1, int((COOLDOWN_SECONDS - elapsed_sec) / 60))
            msg = f"Please wait {wait} more minute{'s' if wait != 1 else ''} before submitting again."
            if _is_ajax(): return jsonify(ok=False, msg=msg)
            flash(msg, "err")
            return redirect(url_for("student.dashboard"))

    # Store UTC in DB — display offset is applied at render time via local_dt()
    now_utc = datetime.utcnow()
    add_attendance(student_id=user.id, teacher_id=teacher.id, date=now_utc, source='student')


    if _is_ajax():
        unbilled       = Attendance.query.filter_by(student_id=user.id, billed=False)\
                            .order_by(Attendance.date.asc()).all()
        total_sessions = Attendance.query.filter_by(student_id=user.id).count()
        for a in unbilled:
            t = db.session.get(User, a.teacher_id)
            a.teacher_name = t.name() if t else "?"

        cnt  = len(unbilled)
        pct  = min(int(cnt / 8 * 100), 100)
        rem  = 8 - cnt
        lang = session.get('lang', 'en')
        rem_txt = f'还需 {rem} 节课后生成收据' if lang == 'zh' \
                  else f"{rem} more {'class' if rem==1 else 'classes'} until next receipt"

        # Apply WIB (UTC+7) for all time display
        from ..services.i18n import to_wib as _to_wib

        # Build cycle-grid HTML with WIB time applied
        cells = ""
        for i in range(8):
            if i < len(unbilled):
                a    = unbilled[i]
                ldt  = _to_wib(a.date)
                cells += (
                    f'<div class="cycle-cell done">'
                    f'<div class="cell-num">#{i+1}</div>'
                    f'<div class="cell-day">{ldt.strftime("%a")}</div>'
                    f'<div class="cell-date">{ldt.strftime("%d %b")}</div>'
                    f'<div class="cell-time">{ldt.strftime("%H:%M")}</div>'
                    f'</div>'
                )
            else:
                cells += (
                    f'<div class="cycle-cell empty-cell">'
                    f'<div class="cell-num">#{i+1}</div>'
                    f'<div class="cell-empty">—</div>'
                    f'</div>'
                )

        if cnt > 0:
            progress_html = (
                f'<div class="cycle-card">'
                f'<div class="cycle-header">'
                f'<div>'
                f'<div class="cycle-title">{cnt} / 8 {tr("classes_done")}</div>'
                f'<div class="cycle-sub">{tr("with_teacher")} {teacher.name()} · {rem_txt}</div>'
                f'</div>'
                f'<div class="cycle-pct">{pct}%</div>'
                f'</div>'
                f'<div class="cycle-bar"><div class="cycle-fill" style="width:{pct}%"></div></div>'
                f'<div class="cycle-grid">{cells}</div>'
                f'</div>'
            )
        else:
            progress_html = f'<div class="empty-state"><div class="empty-icon">📊</div><div class="empty-title">{tr("no_progress")}</div></div>'

        # Check if a new receipt was just generated (cycle completed)
        new_receipts = Receipt.query.filter_by(student_id=user.id)\
                           .order_by(Receipt.issue_date.desc()).all()
        receipt_count = len(new_receipts)

        # Build receipt card HTML only when a new receipt was just created (cnt reset to 0)
        new_receipt_html = None
        if cnt == 0 and new_receipts:
            r = new_receipts[0]
            from ..services.i18n import fmt_idr, parse_raw_dates
            parsed     = parse_raw_dates(r.raw_dates)
            paid_cls   = 'bpd' if r.paid else 'bup'
            paid_label = tr('paid_lbl') if r.paid else tr('unpaid_lbl')
            paid_val   = '1' if r.paid else '0'
            date_stamp = r.issue_date.strftime('%Y%m%d%H%M%S')
            num_sessions = len(parsed)
            fee_fmt    = fmt_idr(r.total_fee)
            issue_fmt  = fmt_date(r.issue_date)

            new_receipt_html = (
                f'<div class="rc-card"'
                f' data-rid="{r.id}"'
                f' data-paid="{paid_val}"'
                f' data-date="{date_stamp}"'
                f' data-student=""'
                f' data-teacher="{r.teacher_name}"'
                f' data-fee="{r.total_fee}"'
                f' data-issue="{issue_fmt}"'
                f' data-dates="{r.raw_dates or ""}"'
                f' data-show-paid="0" data-paid-url=""'
                f' tabindex="0" role="button">'
                f'<div class="rc-mid">'
                f'<div class="rc-top"><span class="rc-id">#{r.id}</span>'
                f'<span class="rc-name">{r.teacher_name}</span></div>'
                f'<div class="rc-bottom"><span class="rc-date">{issue_fmt}</span>'
                f'<span class="rc-sessions">{num_sessions} sessions</span></div>'
                f'</div>'
                f'<div class="rc-right">'
                f'<div class="rc-fee">Rp {fee_fmt}</div>'
                f'<span class="{paid_cls}">{paid_label}</span>'
                f'</div>'
                f'<div class="rc-arrow">›</div>'
                f'</div>'
            )

        return jsonify(ok=True, msg=tr("ok_attn"),
                       progress_html=progress_html,
                       cycle_count=cnt,
                       total_sessions=total_sessions,
                       receipt_count=receipt_count,
                       new_receipt_html=new_receipt_html)

    flash(tr("ok_attn"), "ok")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    from flask import jsonify as _j
    user = _get_current_user()
    if not user:
        return _j(ok=False, msg="Not logged in"), 401

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    user.display_name = request.form.get("display_name", "").strip()[:100]
    user.email        = request.form.get("email", "").strip()[:200]
    db.session.commit()

    if is_ajax:
        return _j(ok=True, msg="Profile saved.")
    flash("Profile saved.", "ok")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/mark_seen", methods=["POST"])
@login_required
def mark_seen():
    """Called when student clicks a nav tab — saves that they've seen the current count."""
    from flask import request as _req, jsonify as _j
    data = _req.get_json(silent=True) or {}
    tab  = data.get("tab", "")
    count = data.get("count", 0)
    if tab in ("classes", "progress", "receipts"):
        seen = session.get("seen_pips", {})
        seen[tab] = count
        session["seen_pips"] = seen
    return _j(ok=True)
