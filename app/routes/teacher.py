"""
routes/teacher.py — Teacher Blueprint
"""
import logging
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify, g, make_response)
from .. import db
from ..models import User, Receipt, Attendance, StudentFee, Schedule, ScheduleJoin, ScheduleInvite
from ..services.attendance import (
    add_attendance, delete_attendance,
    mark_receipt_paid, get_student_progress, set_custom_fee,
)
from ..services.i18n import tr, fmt_date, random_quote, to_wib, parse_raw_dates, fmt_idr
from ..services.security import hash_password

logger = logging.getLogger(__name__)
teacher_bp = Blueprint("teacher", __name__)

def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session: return redirect(url_for("auth.login"))
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "teacher": return redirect(url_for("student.dashboard"))
        return f(*args, **kwargs)
    return decorated

def _get_teacher():
    return db.session.get(User, session.get("user_id"))

@teacher_bp.route("/teacher/dashboard")
@teacher_required
def dashboard():
    teacher = _get_teacher()
    receipts = Receipt.query.filter_by(teacher_id=teacher.id).order_by(Receipt.issue_date.desc()).all()
    all_students = User.query.filter_by(role="student").all()
    progress = get_student_progress(teacher.id)
    
    custom_fees = {sf.student_id: sf.fee_idr for sf in StudentFee.query.filter_by(teacher_id=teacher.id).all()}
    custom_fee_types = {sf.student_id: sf.packet_type for sf in StudentFee.query.filter_by(teacher_id=teacher.id).all()}
    
    unbilled_records = Attendance.query.filter_by(teacher_id=teacher.id, billed=False).order_by(Attendance.date.desc()).all()
    unpaid_cnt = sum(1 for r in receipts if not r.paid)
    
    schedules = Schedule.query.filter_by(teacher_id=teacher.id).order_by(Schedule.scheduled_at.desc()).all()
    up_count = sum(1 for s in schedules if not s.cancelled)

    return render_template("teacher/dashboard.html",
        user=teacher, receipts=receipts, all_students=all_students,
        progress=progress, custom_fees=custom_fees, custom_fee_types=custom_fee_types,
        unbilled_records=unbilled_records, unpaid_cnt=unpaid_cnt, 
        schedules=schedules, up_count=up_count, now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
        quote=random_quote())

@teacher_bp.route("/teacher/update_settings", methods=["POST"])
@teacher_required
def update_settings():
    teacher = _get_teacher()
    teacher.bank_account = request.form.get("bank", "").strip()[:100]
    teacher.bank_name = request.form.get("bank_name", "").strip()[:100]
    teacher.fee_idr = int(request.form.get("fee") or 0)
    teacher.email = request.form.get("email", "").strip()[:200]
    dn = request.form.get("display_name", "").strip()[:100]
    if dn: teacher.display_name = dn
    db.session.commit()
    return jsonify(ok=True, msg=tr("ok_saved")) if _is_ajax() else redirect(url_for("teacher.dashboard"))

@teacher_bp.route("/teacher/set_fee", methods=["POST"])
@teacher_required
def set_fee():
    teacher = _get_teacher()
    student_id = request.form.get("student_id", type=int)
    fee_val = request.form.get("fee", type=int)
    packet_type = request.form.get("packet_type", "session")
    if student_id and fee_val is not None:
        set_custom_fee(teacher.id, student_id, fee_val, packet_type)
        return jsonify(ok=True, msg=tr("ok_saved"), fee_fmt=fmt_idr(fee_val))
    return jsonify(ok=False, msg="Invalid input"), 400

@teacher_bp.route("/teacher/add_attendance", methods=["POST"])
@teacher_required
def manual_add_attendance():
    teacher = _get_teacher()
    student_id = request.form.get("student_id", type=int)
    note = request.form.get("note", "").strip()
    date_str = request.form.get("date", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        dt = datetime.utcnow()
    
    add_attendance(student_id=student_id, teacher_id=teacher.id, date=dt, note=note, source='teacher')
    return jsonify(ok=True, msg=tr("ok_attn")) if _is_ajax() else redirect(url_for("teacher.dashboard"))

@teacher_bp.route("/teacher/delete_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def remove_attendance(att_id):
    teacher = _get_teacher()
    if delete_attendance(att_id, teacher.id):
        return jsonify(ok=True, msg=tr("ok_deleted")) if _is_ajax() else redirect(url_for("teacher.dashboard"))
    return jsonify(ok=False, msg="Not found"), 404

@teacher_bp.route("/teacher/edit_attendance/<int:att_id>", methods=["POST"])
@teacher_required
def edit_attendance(att_id):
    teacher = _get_teacher()
    record = db.session.get(Attendance, att_id)
    if not record or record.teacher_id != teacher.id:
        return jsonify(ok=False, msg="Not found"), 404
    
    date_str = request.form.get("new_date", "")
    try:
        dt_local = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
        record.date = dt_local - timedelta(hours=7)
        db.session.commit()
        return jsonify(ok=True, msg=tr("ok_saved"), att_id=att_id, new_date_fmt=fmt_date(to_wib(record.date)))
    except ValueError:
        return jsonify(ok=False, msg="Invalid date"), 400

@teacher_bp.route("/teacher/edit_receipt_time/<int:receipt_id>", methods=["POST"])
@teacher_required
def edit_receipt_time(receipt_id):
    receipt = db.session.get(Receipt, receipt_id)
    teacher = _get_teacher()
    if not receipt or receipt.teacher_id != teacher.id:
        return jsonify(ok=False, msg="Not found"), 404
    
    new_issue_date_str = request.form.get("issue_date")
    try:
        new_date = datetime.strptime(new_issue_date_str, "%Y-%m-%dT%H:%M")
        receipt.issue_date = new_date
        db.session.commit()
        return jsonify(ok=True, msg="Time updated", new_date=fmt_date(new_date))
    except ValueError:
        return jsonify(ok=False, msg="Invalid date"), 400

@teacher_bp.route("/teacher/reset_student_password/<int:student_id>", methods=["POST"])
@teacher_required
def reset_student_password(student_id):
    student = db.session.get(User, student_id)
    new_pw = request.form.get("new_password", "").strip()
    if student and len(new_pw) >= 6:
        student.password = hash_password(new_pw)
        db.session.commit()
        return jsonify(ok=True, msg=f"Password reset for {student.name()}")
    return jsonify(ok=False, msg="Invalid password"), 400

@teacher_bp.route("/teacher/mark_seen", methods=["POST"])
@teacher_required
def mark_seen():
    import json as _json
    teacher = _get_teacher()
    data = request.get_json() or {}
    seen = _json.loads(teacher.seen_pips or "{}")
    seen[data.get("tab")] = data.get("count", 0)
    teacher.seen_pips = _json.dumps(seen)
    db.session.commit()
    return jsonify(ok=True)
