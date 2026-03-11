"""
routes/teacher.py — Teacher Blueprint
All POST routes return JSON when called via AJAX (X-Requested-With header).
"""
import logging
from datetime import datetime
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from .. import db
from ..models import User, Receipt, Attendance, StudentFee, Schedule, ScheduleJoin
from ..services.attendance import (
    add_attendance, delete_attendance,
    mark_receipt_paid, get_student_progress, set_custom_fee,
)
from ..services.i18n import tr, fmt_date, random_quote
from ..services.security import verify_password

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



def _build_progress_html(teacher_id):
    """Build the progress data-table HTML for AJAX responses."""
    from ..services.attendance import get_student_progress
    from ..services.i18n import fmt_date, to_wib
    progress = get_student_progress(teacher_id)
    if not progress:
        return ""
    rows = ""
    for sp in progress:
        pct = min(int(sp["count"] / 8 * 100), 100)
        last_date = fmt_date(to_wib(sp["dates"][-1])) if sp["dates"] else ""
        last_html = f'<div class="dt-meta">Last: {last_date}</div>' if last_date else ""
        rows += (
            f'<div class="dt-row prog-row" id="prog-{sp["student_id"]}" '
            f'style="grid-template-columns:1fr 80px 120px 44px;cursor:pointer" '
            f'data-id="{sp["student_id"]}" data-name="{sp["name"]}">' 
            f'<div><div class="dt-name">{sp["name"]}</div>'
            f'{last_html}</div>'
            f'<div style="font-weight:700;font-size:.92rem;color:var(--text)">{sp["count"]}/8</div>'
            f'<div style="padding-right:8px"><div class="progress-bar" style="margin:0">'
            f'<div class="progress-fill" style="width:{pct}%"></div></div></div>'
            f'<button class="btn bg bsm view-attn-btn" data-id="{sp["student_id"]}" data-name="{sp["name"]}">📋</button>'
            f'</div>'
        )
    return (
        '<div class="data-table">'
        '<div class="dt-head" style="grid-template-columns:1fr 80px 120px 44px">'
        '<span>Student</span><span>Unbilled</span><span>Progress</span><span></span>'
        '</div>' + rows + '</div>'
    )


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

    # Per-student session & unbilled counts for the registered students table
    student_sessions = {}
    student_unbilled = {}
    for s in all_students:
        total = Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id).count()
        unbilled = Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id, billed=False).count()
        student_sessions[s.id] = total
        student_unbilled[s.id] = unbilled

    from flask import make_response
    fresh = session.pop("fresh_login", False)

    # Pip persistence — show pip only if count changed since teacher last viewed that tab
    # seen[tab] = last count teacher saw. -1 = never seen. -2 = seen with 0 items.
    seen      = session.get("teacher_seen_pips", {})
    up_count  = sum(1 for s in schedules if not s.cancelled)
    attn_count = len(unbilled_records)
    # Show pip only when count is > 0 AND different from last seen count
    show_classes_pip  = up_count   > 0 and seen.get("classes",   -1) != up_count
    show_attn_pip     = attn_count > 0 and seen.get("attendance", -1) != attn_count
    show_receipts_pip = unpaid_cnt > 0 and seen.get("receipts",   -1) != unpaid_cnt

    resp = make_response(render_template("teacher/dashboard.html",
        user=teacher, receipts=receipts, all_students=all_students,
        progress=progress, custom_fees=custom_fees,
        unbilled_records=unbilled_records, r_count=r_count,
        unpaid_cnt=unpaid_cnt, student_count=student_count,
        student_sessions=student_sessions, student_unbilled=student_unbilled,
        now=_dt.now().strftime("%Y-%m-%dT%H:%M"),
        schedules=schedules,
        fresh_login=fresh,
        quote=random_quote(),
        show_classes_pip=show_classes_pip,
        show_attn_pip=show_attn_pip,
        show_receipts_pip=show_receipts_pip,
        up_count=up_count, attn_count=attn_count,
        ))
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


@teacher_bp.route("/teacher/mark_seen", methods=["POST"])
@teacher_required
def mark_seen():
    """Store how many items teacher has seen per tab — prevents stale pips on refresh."""
    tab   = request.json.get("tab") if request.is_json else request.form.get("tab")
    count = request.json.get("count") if request.is_json else request.form.get("count", type=int)
    if tab is not None and count is not None:
        seen = session.get("teacher_seen_pips", {})
        seen[tab] = int(count)
        session["teacher_seen_pips"] = seen
    return jsonify(ok=True)


@teacher_bp.route("/teacher/set_fee", methods=["POST"])
@teacher_required
def set_fee():
    from ..services.i18n import fmt_idr
    teacher    = _get_teacher()
    student_id = request.form.get("student_id", type=int)
    fee_str    = request.form.get("fee", "").strip()
    if student_id and fee_str and db.session.get(User, student_id):
        fee = int(fee_str)
        set_custom_fee(teacher.id, student_id, fee)
        if _is_ajax():
            return jsonify(ok=True, msg=tr("ok_saved"),
                           student_id=student_id,
                           fee=fee,
                           fee_fmt=fmt_idr(fee))
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

    # Snapshot receipts before adding — so we can detect newly generated ones
    receipt_ids_before = {r.id for r in Receipt.query.filter_by(teacher_id=teacher.id).all()}

    record = add_attendance(student_id=student_id, teacher_id=teacher.id, date=dt, note=note, source='teacher')

    if _is_ajax():
        from ..services.attendance import get_student_progress
        from ..services.i18n import fmt_date, to_wib
        from flask import current_app
        from .. import db as _db

        # Build HTML for the new attendance row
        note_html = f'<div class="attn-note">{note}</div>' if note else ''
        record_html = (
            f'<div class="attn-row" id="attn-{record.id}">'
            f'<div>'
            f'<div class="attn-name">{student.name()}</div>'
            f'<div class="attn-date">{fmt_date(to_wib(record.date))}</div>'
            f'{note_html}'
            f'</div>'
            f'<form class="del-attn-form" method="POST" '
            f'action="/teacher/delete_attendance/{record.id}" '
            f'data-id="{record.id}" style="margin:0;flex-shrink:0">'
            f'<button class="btn bdel bsm" type="submit">{tr("delete_btn")}</button>'
            f'</form>'
            f'</div>'
        )

        # Check if a new receipt was generated
        new_receipts = Receipt.query.filter_by(teacher_id=teacher.id).filter(
            ~Receipt.id.in_(receipt_ids_before)
        ).all()
        new_receipt_data = []
        for nr in new_receipts:
            from ..services.i18n import fmt_idr, parse_raw_dates
            dates = parse_raw_dates(nr.raw_dates) if nr.raw_dates else []
            new_receipt_data.append({
                "id":           nr.id,
                "student_name": nr.student_name,
                "total_fee":    nr.total_fee,
                "fee_fmt":      fmt_idr(nr.total_fee),
                "issue_date":   fmt_date(nr.issue_date),
                "sessions":     len(dates),
                "paid":         nr.paid,
                "paid_url":     f"/teacher/paid/{nr.id}",
                "raw_dates":    nr.raw_dates or "",
                "teacher_name": nr.teacher_name,
                "bank_account": nr.bank_account or "",
                "bank_name":    nr.bank_name or "",
            })

        # Build updated progress HTML
        progress_html = _build_progress_html(teacher.id)

        # Count remaining unbilled records
        unbilled_count = Attendance.query.filter_by(
            teacher_id=teacher.id, billed=False
        ).count()

        # Updated counts for this student's row in the Students table
        s_total    = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id).count()
        s_unbilled = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher.id, billed=False).count()

        return jsonify(
            ok=True,
            msg=tr("ok_attn"),
            record_html=record_html,
            progress_html=progress_html,
            unbilled_count=unbilled_count,
            student_id=student_id,
            s_total=s_total,
            s_unbilled=s_unbilled,
            new_receipts=new_receipt_data,
        )

    flash(tr("ok_attn"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def remove_attendance(att_id):
    teacher = _get_teacher()
    # Grab student_id before deleting
    record = db.session.get(Attendance, att_id)
    student_id_del = record.student_id if record else None

    if delete_attendance(att_id, teacher.id):
        if _is_ajax():
            progress_html = _build_progress_html(teacher.id)
            unbilled_count = Attendance.query.filter_by(
                teacher_id=teacher.id, billed=False
            ).count()
            s_total = s_unbilled = 0
            if student_id_del:
                s_total    = Attendance.query.filter_by(student_id=student_id_del, teacher_id=teacher.id).count()
                s_unbilled = Attendance.query.filter_by(student_id=student_id_del, teacher_id=teacher.id, billed=False).count()
            return jsonify(
                ok=True,
                msg=tr("ok_deleted"),
                progress_html=progress_html,
                unbilled_count=unbilled_count,
                student_id=student_id_del,
                s_total=s_total,
                s_unbilled=s_unbilled,
            )
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
    """Teacher can delete a receipt (only if already paid)."""
    teacher = _get_teacher()
    receipt = db.session.get(Receipt, receipt_id)
    if not receipt or receipt.teacher_id != teacher.id:
        if _is_ajax(): return jsonify(ok=False, msg="Receipt not found")
        return redirect(url_for("teacher.dashboard"))
    if not receipt.paid:
        if _is_ajax(): return jsonify(ok=False, msg="Can only delete paid receipts")
        flash("Can only delete paid receipts", "err")
        return redirect(url_for("teacher.dashboard"))
    db.session.delete(receipt)
    db.session.commit()
    if _is_ajax():
        return jsonify(ok=True, msg="Receipt deleted")
    flash("Receipt deleted", "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_student/<int:student_id>", methods=["POST"])
@teacher_required
def delete_student(student_id):
    """
    RBAC: Only teachers can delete student accounts.
    This is the elevated privilege (kekuasaan) — teachers have authority
    over their students' accounts.
    """
    teacher = _get_teacher()
    student = db.session.get(User, student_id)

    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Student not found")
        return redirect(url_for("teacher.dashboard"))

    # Delete all related data
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

    if _is_ajax(): return jsonify(ok=True, msg=f"Student deleted")
    flash(tr("ok_deleted"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/reset_student_password/<int:student_id>", methods=["POST"])
@teacher_required
def reset_student_password(student_id):
    """Teacher resets a student's password."""
    teacher  = _get_teacher()
    student  = db.session.get(User, student_id)

    if not student or student.role != "student":
        if _is_ajax(): return jsonify(ok=False, msg="Student not found")
        return redirect(url_for("teacher.dashboard"))

    new_pw = request.form.get("new_password", "").strip()
    if len(new_pw) < 6:
        if _is_ajax(): return jsonify(ok=False, msg="Password must be at least 6 characters")
        flash("Password too short.", "err")
        return redirect(url_for("teacher.dashboard"))

    from ..services.security import hash_password
    student.password = hash_password(new_pw)
    db.session.commit()
    logger.info("Teacher %s reset password for student_id=%d", teacher.name(), student_id)

    if _is_ajax(): return jsonify(ok=True, msg="Password reset successfully")
    flash("Password reset successfully.", "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/student_records/<int:student_id>", methods=["GET", "POST"])
@teacher_required
def student_records(student_id):
    """Return all attendance records for a specific student (AJAX)."""
    from ..services.i18n import fmt_date, to_wib

    teacher = _get_teacher()
    student = db.session.get(User, student_id)
    if not student:
        return jsonify(ok=False, msg="Student not found")

    records = (
        Attendance.query
        .filter_by(student_id=student_id, teacher_id=teacher.id)
        .order_by(Attendance.date.desc())
        .all()
    )

    total = len(records)
    unbilled = sum(1 for r in records if not r.billed)

    rows_html = ""
    for a in records:
        local = to_wib(a.date)
        wib_iso = local.strftime("%Y-%m-%dT%H:%M")
        date_fmt = fmt_date(local)
        note_html = f'<div class="attn-note">{a.note}</div>' if a.note else ""
        if not a.billed:
            del_btn = (
                f'<form class="del-attn-form" method="POST" '
                f'action="/teacher/delete_attendance/{a.id}" '
                f'data-id="{a.id}" style="margin:0">'
                f'<button class="btn bdel bsm" type="submit">{tr("delete_btn")}</button>'
                f'</form>'
            )
            edit_btn = (
                f'<button class="btn bgh bsm" style="flex-shrink:0" '
                f'onclick="openEditAttn({a.id}, \'{wib_iso}\', \'{date_fmt}\')">✏️</button>'
            )
            action_html = f'<div style="display:flex;gap:6px;flex-shrink:0">{edit_btn}{del_btn}</div>'
        else:
            action_html = '<span style="font-size:.75rem;color:var(--text3);flex-shrink:0">billed</span>'

        rows_html += (
            f'<div class="attn-row" id="attn-{a.id}">'
            f'<div>'
            f'<div class="attn-date">{date_fmt}</div>'
            f'{note_html}'
            f'</div>'
            f'{action_html}'
            f'</div>'
        )

    if not rows_html:
        rows_html = '<div class="empty-inline">No attendance records yet.</div>'

    return jsonify(
        ok=True,
        html=rows_html,
        total=total,
        unbilled=unbilled,
    )


@teacher_bp.route("/teacher/edit_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def edit_attendance(att_id):
    """Teacher edits the datetime of an attendance record (input is WIB, stored as UTC)."""
    from ..services.i18n import fmt_date, to_wib
    from datetime import timedelta as _td
    teacher = _get_teacher()
    record  = db.session.get(Attendance, att_id)
    if not record or record.teacher_id != teacher.id or record.billed:
        return jsonify(ok=False, msg="Not found, wrong owner, or already billed")

    date_str = request.form.get("new_date", "").strip()
    try:
        # Input is WIB → convert to UTC for storage
        wib_dt  = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
        utc_dt  = wib_dt - _td(hours=7)
    except ValueError:
        return jsonify(ok=False, msg="Invalid date format")

    record.date = utc_dt
    db.session.commit()
    logger.info("Teacher %s edited attendance %d to %s", teacher.name(), att_id, utc_dt)

    new_wib = to_wib(record.date)
    progress_html = _build_progress_html(teacher.id)
    return jsonify(
        ok=True,
        att_id=att_id,
        new_date_fmt=fmt_date(new_wib),
        progress_html=progress_html,
    )
