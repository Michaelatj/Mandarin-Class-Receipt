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
from ..services.i18n import tr, fmt_date, random_quote, to_wib, fmt_idr
from ..services.security import hash_password

logger = logging.getLogger(__name__)
teacher_bp = Blueprint("teacher", __name__)

def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def teacher_required(f):
    from functools import wraps
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

    student_sessions = {s.id: Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id).count() for s in all_students}
    student_unbilled = {s.id: Attendance.query.filter_by(student_id=s.id, teacher_id=teacher.id, billed=False).count() for s in all_students}

    return render_template("teacher/dashboard.html",
        user=teacher, receipts=receipts, all_students=all_students,
        progress=progress, custom_fees=custom_fees, custom_fee_types=custom_fee_types,
        unbilled_records=unbilled_records, unpaid_cnt=unpaid_cnt, 
        schedules=schedules, up_count=up_count, attn_count=len(unbilled_records),
        student_sessions=student_sessions, student_unbilled=student_unbilled,
        student_count=len(all_students), now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
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
        return jsonify(ok=True, msg="Time updated", new_date=fmt_date(to_wib(new_date)))
    except ValueError:
        return jsonify(ok=False, msg="Invalid date format"), 400

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
    data = request.get_json(silent=True) or {}
    tab = data.get("tab", "")
    count = data.get("count", 0)
    if tab in ("classes", "attendance", "receipts"):
        seen = _json.loads(teacher.seen_pips or "{}")
        seen[tab] = count
        teacher.seen_pips = _json.dumps(seen)
        db.session.commit()
    return jsonify(ok=True)
@teacher_bp.route("/teacher/mark_paid/<int:receipt_id>", methods=["POST"])
@teacher_required
def paid(receipt_id): # <--- Pastikan nama fungsinya 'paid'
    teacher = _get_teacher()
    if mark_receipt_paid(receipt_id, teacher.id):
        if _is_ajax():
            return jsonify(ok=True, msg=tr("ok_paid"), paid_label=tr("paid_lbl"))
        flash(tr("ok_paid"), "ok")
    return redirect(url_for("teacher.dashboard"))

@teacher_bp.route("/teacher/student_records/<int:student_id>")
@teacher_required
def student_records(student_id):
    teacher = _get_teacher()
    
    records = Attendance.query.filter_by(
        student_id=student_id, teacher_id=teacher.id
    ).order_by(Attendance.date.desc()).all()
    
    unbilled_count = sum(1 for r in records if not r.billed)
    
    html = ""
    for r in records:
        ldt = to_wib(r.date)
        date_str = fmt_date(ldt)
        time_str = ldt.strftime("%H:%M")
        
        billed_val = "1" if r.billed else "0"
        status_lbl = "Billed" if r.billed else "Unbilled"
        status_cls = "bpd" if r.billed else "bup"
        note_html = f'<div style="font-size:0.85rem;color:var(--text3);margin-top:4px;">{r.note}</div>' if r.note else ''
        
        edit_btn = ""
        del_btn = ""
        if not r.billed:
            iso_str = r.date.isoformat() + "Z"
            edit_btn = f'<button type="button" class="btn bgh bsm edit-attn-btn" data-id="{r.id}" data-iso="{iso_str}" title="Edit Time">✏️ Edit</button>'
            del_btn = f'''
            <form class="del-attn-form" data-id="{r.id}" method="POST" action="{url_for('teacher.remove_attendance', att_id=r.id)}" style="margin:0">
                <button type="submit" class="btn bdel-outline bsm" title="Delete">🗑️</button>
            </form>
            '''

        html += f'''
        <div class="attn-row dt-row" id="attn-{r.id}" data-billed="{billed_val}" style="display:flex; justify-content:space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border);">
            <div>
                <div style="font-weight:600; color:var(--text);">{date_str} <span style="font-weight:400; color:var(--text2);">at {time_str} WIB</span></div>
                {note_html}
            </div>
            <div style="display:flex; gap: 6px; align-items:center;">
                <span class="{status_cls}" style="margin-right:6px;">{status_lbl}</span>
                {edit_btn}
                {del_btn}
            </div>
        </div>
        '''
        
    if not records:
        html = '<div class="empty-inline">No records found.</div>'

    return jsonify(ok=True, total=len(records), unbilled=unbilled_count, html=html)
