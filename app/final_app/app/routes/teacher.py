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
    resp = make_response(render_template("teacher/dashboard.html",
        user=teacher, receipts=receipts, all_students=all_students,
        progress=progress, custom_fees=custom_fees,
        unbilled_records=unbilled_records, r_count=r_count,
        unpaid_cnt=unpaid_cnt, student_count=student_count,
        student_sessions=student_sessions, student_unbilled=student_unbilled,
        now=_dt.now().strftime("%Y-%m-%dT%H:%M"),
        schedules=schedules,
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
    teacher    = _get_teacher()
    student_id = request.form.get("student_id", type=int)
    fee_str    = request.form.get("fee", "").strip()
    if student_id and fee_str and db.session.get(User, student_id):
        set_custom_fee(teacher.id, student_id, int(fee_str))
        if _is_ajax():
            return jsonify(ok=True, msg=tr("ok_saved"))
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

    record = add_attendance(student_id=student_id, teacher_id=teacher.id, date=dt, note=note)

    if _is_ajax():
        from ..services.attendance import get_student_progress
        from ..services.i18n import fmt_date as _fmt_date
        from flask import current_app
        from .. import db as _db

        # Build HTML for the new attendance row
        record_html = (
            f'<div class="ai" id="attn-{record.id}">'
            f'<div><strong>{student.name()}</strong> &mdash; '
            f'<span class="ad">{fmt_date(record.date)}</span>'
            f'{"<div class=an>" + note + "</div>" if note else ""}'
            f'</div>'
            f'<form class="del-attn-form" method="POST" '
            f'action="/teacher/delete_attendance/{record.id}" '
            f'data-id="{record.id}" style="margin:0;flex-shrink:0">'
            f'<button class="btn bdel bsm" type="submit">{tr("delete_btn")}</button>'
            f'</form></div>'
        )

        # Build updated progress HTML
        progress = get_student_progress(teacher.id)
        progress_html = ""
        for sp in progress:
            pct = min(int(sp["count"] / 8 * 100), 100)
            dates_html = "".join(f'<span class="bdg">{fmt_date(d)}</span>' for d in sp["dates"])
            progress_html += (
                f'<div class="pc" id="prog-{sp["student_id"]}">'
                f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px">'
                f'<strong>{sp["name"]}</strong>'
                f'<span style="font-size:.85rem;color:var(--ink3)">{sp["count"]}/8</span>'
                f'</div>'
                f'<div class="pb"><div class="pbf" style="width:{pct}%"></div></div>'
                f'<div class="bdgs">{dates_html}</div>'
                f'</div>'
            )

        # Count remaining unbilled records
        unbilled_count = Attendance.query.filter_by(
            teacher_id=teacher.id, billed=False
        ).count()

        return jsonify(
            ok=True,
            msg=tr("ok_attn"),
            record_html=record_html,
            progress_html=progress_html,
            unbilled_count=unbilled_count,
        )

    flash(tr("ok_attn"), "ok")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/teacher/delete_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def remove_attendance(att_id):
    teacher = _get_teacher()
    if delete_attendance(att_id, teacher.id):
        if _is_ajax(): return jsonify(ok=True, msg=tr("ok_deleted"))
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
