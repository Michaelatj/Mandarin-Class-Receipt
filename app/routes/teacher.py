"""
routes/teacher.py — Teacher Blueprint
All POST routes return JSON when called via AJAX (X-Requested-With header).
"""
import logging
from datetime import datetime
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify, g)
from .. import db
from ..models import User, Receipt, Attendance, StudentFee, Schedule, ScheduleJoin
from ..services.attendance import (
    add_attendance, delete_attendance,
    mark_receipt_paid, get_student_progress, set_custom_fee,
)
from ..services.i18n import tr, fmt_date, random_quote, to_wib
from ..services.security import verify_password, hash_password

logger = logging.getLogger(__name__)
teacher_bp = Blueprint("teacher", __name__)

def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "teacher":
            return redirect(url_for("student.dashboard"))
        return f(*args, **kwargs)
    return decorated

def _get_teacher():
    return db.session.get(User, session.get("user_id"))


@teacher_bp.route("/teacher/dashboard")
@teacher_required
def dashboard():
    teacher      = _get_teacher()
    receipts     = Receipt.query.filter_by(teacher_id=teacher.id)\
                       .order_by(Receipt.issue_date.desc()).all()
    all_students = User.query.filter_by(role="student").all()
    progress     = get_student_progress(teacher.id)
    
    custom_fees  = {sf.student_id: sf.fee_idr
                    for sf in StudentFee.query.filter_by(teacher_id=teacher.id).all()}
    custom_fee_types = {sf.student_id: sf.packet_type
                        for sf in StudentFee.query.filter_by(teacher_id=teacher.id).all()}
    
    unbilled_records = (
        Attendance.query.filter_by(teacher_id=teacher.id, billed=False)
        .order_by(Attendance.date.desc()).all()
    )
    for a in unbilled_records:
        s = db.session.get(User, a.student_id)
        a.student_name = s.name() if s else "?"

    r_count      = len(receipts)
    unpaid_cnt   = sum(1 for r in receipts if not r.paid)
    student_count = User.query.filter_by(role='student').count()

    from datetime import datetime as _dt
    schedules = (Schedule.query
                 .filter_by(teacher_id=teacher.id)
                 .order_by(Schedule.scheduled_at.desc()).all())
    for s in schedules:
        joins = ScheduleJoin.query.filter_by(schedule_id=s.id).all()
        s.joined_by  = {j.student_id for j in joins}
        s.join_count = len(s.joined_by)
        from ..models import ScheduleInvite
        invites = ScheduleInvite.query.filter_by(schedule_id=s.id).all()
        s.invited_ids = {inv.student_id for inv in invites}

    student_sessions = {}
    student_unbilled = {}
    for s in all_students:
        total = Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id).count()
        unbilled = Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id, billed=False).count()
        student_sessions[s.id] = total
        student_unbilled[s.id] = unbilled

    # Pip visibility logic
    import json as _json
    try:
        seen = _json.loads(teacher.seen_pips or "{}")
    except Exception:
        seen = {}

    up_count   = sum(1 for s in schedules if not s.cancelled)
    attn_count = len(unbilled_records)

    if not seen:
        seen = {
            "classes":    up_count,
            "attendance": attn_count,
            "receipts":   unpaid_cnt,
        }
        try:
            teacher.seen_pips = _json.dumps(seen)
            db.session.commit()
        except Exception:
            pass

    def _pip(tab, current):
        last = seen.get(tab, None)
        if last is None:
            return False
        return current > int(last)

    show_classes_pip  = up_count   > 0 and _pip("classes",    up_count)
    show_attn_pip     = attn_count > 0 and _pip("attendance", attn_count)
    show_receipts_pip = unpaid_cnt > 0 and _pip("receipts",   unpaid_cnt)

    fresh = session.pop("fresh_login", False)

    from flask import make_response
    resp = make_response(render_template("teacher/dashboard.html",
        user=teacher, receipts=receipts, all_students=all_students,
        progress=progress, custom_fees=custom_fees,
        custom_fee_types=custom_fee_types,
        unbilled_records=unbilled_records, r_count=r_count,
        unpaid_cnt=unpaid_cnt, student_count=student_count,
        student_sessions=student_sessions, student_unbilled=student_unbilled,
        now=_dt.now().strftime("%Y-%m-%dT%H:%M"),
        schedules=schedules,
        up_count=up_count, attn_count=attn_count,
        show_classes_pip=show_classes_pip,
        show_attn_pip=show_attn_pip,
        show_receipts_pip=show_receipts_pip,
        fresh_login=fresh,
        quote=random_quote()))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@teacher_bp.route("/teacher/update_settings", methods=["POST"])
@teacher_required
def update_settings():
    teacher = _get_teacher()
    teacher.bank_account = request.form.get("bank", "").strip()[:100]
    teacher.bank_name    = request.form.get("bank_name", "").strip()[:100]
    teacher.fee_idr      = int(request.form.get("fee") or 0)
    teacher.email        = request.form.get("email", "").strip()[:200]
    dn = request.form.get("display_name", "").strip()[:100]
    if dn: teacher.display_name = dn
    db.session.commit()
    if _is_ajax():
        return jsonify(ok=True, msg=tr("ok_saved"))
    flash(tr("ok_saved"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/set_fee", methods=["POST"])
@teacher_required
def set_fee():
    teacher     = _get_teacher()
    student_id  = request.form.get("student_id", type=int)
    fee_str     = request.form.get("fee", "").strip()
    packet_type = request.form.get("packet_type", "session")
    if student_id and fee_str and db.session.get(User, student_id):
        fee_val = int(fee_str)
        set_custom_fee(teacher.id, student_id, fee_val, packet_type)
        if _is_ajax():
            from ..services.i18n import fmt_idr
            return jsonify(ok=True, msg=tr("ok_saved"), fee_fmt=fmt_idr(fee_val))
        flash(tr("ok_saved"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/add_attendance", methods=["POST"])
@teacher_required
def manual_add_attendance():
    teacher    = _get_teacher()
    student_id = request.form.get("student_id", type=int)
    note       = request.form.get("note", "").strip()
    student    = db.session.get(User, student_id) if student_id else None
    if not student:
        if _is_ajax(): return jsonify(ok=False, msg="Student not found")
        return redirect(url_for("teacher.dashboard"))

    date_str = request.form.get("date", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        dt = datetime.utcnow()

    record = add_attendance(student_id=student_id, teacher_id=teacher.id,
                            date=dt, note=note, source='teacher')

    if _is_ajax():
        from ..services.attendance import get_student_progress
        from ..services.i18n import fmt_date as _fmt_date, to_wib as _to_wib

        record_html = (
            f'<div class="attn-row" id="attn-{record.id}" data-billed="0">'
            f'<div>'
            f'<div class="attn-name">{student.name()}</div>'
            f'<div class="attn-date">{fmt_date(_to_wib(record.date))}</div>'
            f'{"<div class=attn-note>" + note + "</div>" if note else ""}'
            f'</div>'
            f'<form class="del-attn-form" method="POST" '
            f'action="/teacher/delete_attendance/{record.id}" '
            f'data-id="{record.id}" style="margin:0;flex-shrink:0">'
            f'<button class="btn bdel bsm" type="submit">{tr("delete_btn")}</button>'
            f'</form></div>'
        )

        progress     = get_student_progress(teacher.id)
        unbilled_count = Attendance.query.filter_by(
            teacher_id=teacher.id, billed=False
        ).count()

        # Build progress HTML (table rows)
        progress_html = _build_progress_html(progress)

        s_total    = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id).count()
        s_unbilled = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id, billed=False).count()

        # Check for newly generated receipts
        new_receipts_data = _get_new_receipts_data(teacher)

        return jsonify(
            ok=True,
            msg=tr("ok_attn"),
            record_html=record_html,
            progress_html=progress_html,
            unbilled_count=unbilled_count,
            student_id=student_id,
            s_total=s_total,
            s_unbilled=s_unbilled,
            new_receipts=new_receipts_data,
        )

    flash(tr("ok_attn"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def remove_attendance(att_id):
    teacher = _get_teacher()
    record  = db.session.get(Attendance, att_id)
    student_id = record.student_id if record else None

    if delete_attendance(att_id, teacher.id):
        if _is_ajax():
            from ..services.attendance import get_student_progress
            progress = get_student_progress(teacher.id)
            progress_html = _build_progress_html(progress)
            s_total    = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id).count() if student_id else 0
            s_unbilled = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id, billed=False).count() if student_id else 0
            return jsonify(ok=True, msg=tr("ok_deleted"),
                           progress_html=progress_html,
                           student_id=student_id,
                           s_total=s_total, s_unbilled=s_unbilled)
        flash(tr("ok_deleted"), "ok")
    else:
        if _is_ajax(): return jsonify(ok=False, msg="Not found or already billed")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/mark_paid/<int:receipt_id>", methods=["POST"])
@teacher_required
def paid(receipt_id):
    teacher = _get_teacher()
    if mark_receipt_paid(receipt_id, teacher.id):
        if _is_ajax():
            return jsonify(ok=True, msg=tr("ok_paid"), paid_label=tr("paid_lbl"))
        flash(tr("ok_paid"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_receipt/<int:receipt_id>", methods=["POST"])
@teacher_required
def delete_receipt(receipt_id):
    teacher = _get_teacher()
    receipt = db.session.get(Receipt, receipt_id)
    if not receipt or receipt.teacher_id != teacher.id:
        if _is_ajax(): return jsonify(ok=False, msg="Not found")
        return redirect(url_for("teacher.dashboard"))
    db.session.delete(receipt)
    db.session.commit()
    if _is_ajax(): return jsonify(ok=True, msg="Receipt deleted")
    flash(tr("ok_deleted"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_student/<int:student_id>", methods=["POST"])
@teacher_required
def delete_student(student_id):
    teacher = _get_teacher()
    student = db.session.get(User, student_id)
    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Student not found")
        return redirect(url_for("teacher.dashboard"))

    Attendance.query.filter(
        (Attendance.student_id == student_id) | (Attendance.teacher_id == student_id)
    ).delete(synchronize_session=False)
    Receipt.query.filter(
        (Receipt.student_id == student_id) | (Receipt.teacher_id == student_id)
    ).delete(synchronize_session=False)
    StudentFee.query.filter(
        (StudentFee.student_id == student_id) | (StudentFee.teacher_id == student_id)
    ).delete(synchronize_session=False)
    db.session.delete(student)
    db.session.commit()

    logger.info("Teacher %s deleted student_id=%d", teacher.name(), student_id)
    if _is_ajax(): return jsonify(ok=True, msg="Student deleted")
    flash(tr("ok_deleted"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/student_records/<int:student_id>")
@teacher_required
def student_records(student_id):
    teacher = _get_teacher()
    records = (Attendance.query
               .filter_by(student_id=student_id, teacher_id=teacher.id)
               .order_by(Attendance.date.desc()).all())
    student = db.session.get(User, student_id)

    rows_html = ""
    for a in records:
        wib = to_wib(a.date)
        rows_html += (
            f'<div class="attn-row" id="attn-{a.id}" data-billed="{"1" if a.billed else "0"}">'
            f'<div>'
            f'<div class="attn-name">{student.name() if student else "?"}</div>'
            f'<div class="attn-date">{fmt_date(wib)}</div>'
            f'{"<div class=attn-note>" + a.note + "</div>" if a.note else ""}'
            f'</div>'
        )
        if not a.billed:
            rows_html += (
                f'<div style="display:flex;gap:6px;flex-shrink:0">'
                f'<button class="btn bgh bsm" onclick="openEditAttn({a.id},\'{wib.strftime("%Y-%m-%dT%H:%M")}\',\'{fmt_date(wib)}\')">✏️</button>'
                f'<form class="del-attn-form" method="POST" action="/teacher/delete_attendance/{a.id}" data-id="{a.id}" style="margin:0">'
                f'<button class="btn bdel bsm" type="submit">{tr("delete_btn")}</button>'
                f'</form>'
                f'</div>'
            )
        rows_html += '</div>'

    if not rows_html:
        rows_html = '<div class="empty-inline">No attendance records yet.</div>'

    total    = len(records)
    unbilled = sum(1 for a in records if not a.billed)
    return jsonify(ok=True, html=rows_html, total=total, unbilled=unbilled)


@teacher_bp.route("/teacher/edit_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def edit_attendance(att_id):
    teacher = _get_teacher()
    record  = db.session.get(Attendance, att_id)
    if not record or record.teacher_id != teacher.id:
        if _is_ajax(): return jsonify(ok=False, msg="Not found")
        return redirect(url_for("teacher.dashboard"))

    date_str = request.form.get("new_date", "")
    try:
        # Input is WIB — convert back to UTC for storage
        dt_wib = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
        from datetime import timedelta
        record.date = dt_wib - timedelta(hours=7)
        db.session.commit()
    except ValueError:
        if _is_ajax(): return jsonify(ok=False, msg="Invalid date")
        return redirect(url_for("teacher.dashboard"))

    if _is_ajax():
        from ..services.attendance import get_student_progress
        progress      = get_student_progress(teacher.id)
        progress_html = _build_progress_html(progress)
        return jsonify(ok=True, msg=tr("ok_saved"),
                       att_id=att_id,
                       new_date_fmt=fmt_date(to_wib(record.date)),
                       progress_html=progress_html)
    flash(tr("ok_saved"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/reset_student_password/<int:student_id>", methods=["POST"])
@teacher_required
def reset_student_password(student_id):
    teacher = _get_teacher()
    student = db.session.get(User, student_id)
    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Student not found")
        return redirect(url_for("teacher.dashboard"))
    new_pw = request.form.get("new_password", "").strip()
    if len(new_pw) < 6:
        if _is_ajax(): return jsonify(ok=False, msg="Password must be at least 6 characters")
        flash("Password too short", "err")
        return redirect(url_for("teacher.dashboard"))
    student.password = hash_password(new_pw)
    db.session.commit()
    logger.info("Teacher %s reset password for student_id=%d", teacher.name(), student_id)
    if _is_ajax(): return jsonify(ok=True, msg=f"Password reset for {student.name()}")
    flash("Password reset successfully", "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/mark_seen", methods=["POST"])
@teacher_required
def mark_seen():
    import json as _json
    teacher = _get_teacher()
    data    = request.get_json(silent=True) or {}
    tab     = data.get("tab", "")
    count   = data.get("count", 0)
    if tab in ("classes", "attendance", "receipts"):
        try:
            seen = _json.loads(teacher.seen_pips or "{}")
        except Exception:
            seen = {}
        seen[tab] = count
        teacher.seen_pips = _json.dumps(seen)
        db.session.commit()
    return jsonify(ok=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_progress_html(progress):
    from ..services.i18n import fmt_date as _fmt_date, to_wib as _to_wib
    if not progress:
        return ''
    rows = ''
    for sp in progress:
        pct     = min(int(sp["count"] / 8 * 100), 100)
        is_zero = sp["count"] == 0
        last    = f'Last: {_fmt_date(_to_wib(sp["dates"][-1]))}' if sp["dates"] else \
                  '<span style="color:var(--text3);font-style:italic">No unbilled sessions</span>'
        rows += (
            f'<div class="dt-row prog-row" id="prog-{sp["student_id"]}"'
            f' style="grid-template-columns:1fr 80px 120px 44px;cursor:pointer{"opacity:.65" if is_zero else ""}"'
            f' data-id="{sp["student_id"]}" data-name="{sp["name"]}">'
            f'<div><div class="dt-name">{sp["name"]}</div><div class="dt-meta">{last}</div></div>'
            f'<div style="font-weight:700;font-size:.92rem;color:{"var(--text3)" if is_zero else "var(--text)"}">{sp["count"]}/8</div>'
            f'<div style="padding-right:8px"><div class="progress-bar" style="margin:0">'
            f'<div class="progress-fill" style="width:{pct}%"></div></div></div>'
            f'<button class="btn bg bsm view-attn-btn" data-id="{sp["student_id"]}" data-name="{sp["name"]}">📋</button>'
            f'</div>'
        )
    return f'<div class="data-table"><div class="dt-head" style="grid-template-columns:1fr 80px 120px 44px"><span>Student</span><span>Unbilled</span><span>Progress</span><span></span></div>{rows}</div>'


def _get_new_receipts_data(teacher):
    from ..services.i18n import fmt_idr, fmt_date as _fmt_date, to_wib as _to_wib
    recent = (Receipt.query
              .filter_by(teacher_id=teacher.id)
              .order_by(Receipt.issue_date.desc())
              .limit(5).all())
    # Only return receipts created in the last 10 seconds (just generated)
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(seconds=10)
    new_ones = [r for r in recent if r.issue_date >= cutoff]
    result = []
    for r in new_ones:
        issue_wib = _to_wib(r.issue_date)
        from ..services.i18n import parse_raw_dates
        sessions = len(parse_raw_dates(r.raw_dates))
        result.append({
            "id":           r.id,
            "receipt_no":   r.receipt_no or r.id,
            "student_name": r.student_name,
            "teacher_name": r.teacher_name,
            "total_fee":    r.total_fee,
            "fee_fmt":      fmt_idr(r.total_fee),
            "issue_date":   _fmt_date(issue_wib),
            "raw_dates":    r.raw_dates,
            "bank_account": r.bank_account,
            "bank_name":    r.bank_name,
            "sessions":     sessions,
            "paid_url":     url_for("teacher.paid", receipt_id=r.id),
        })
    return result
