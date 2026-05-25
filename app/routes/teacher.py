from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from app.models import db, User, Attendance, Receipt, StudentFee, Schedule
from app.services.attendance import generate_receipts, get_student_progress
from app.services.i18n import tr, fmt_date, to_wib, fmt_idr
from datetime import datetime, timedelta

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def teacher_required(f):
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'teacher':
            flash(tr('err_teacher_only', 'Access denied. Teachers only.'), 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@teacher_bp.route('/dashboard')
@teacher_required
def dashboard():
    students = User.query.filter_by(role='student').all()
    fee_overrides = StudentFee.query.filter_by(teacher_id=current_user.id).all()
    
    # Create a map of student_id -> {fee, packet_type}
    fee_map = {}
    for fee in fee_overrides:
        fee_map[fee.student_id] = {
            'fee_idr': fee.fee_idr,
            'packet_type': fee.packet_type
        }
    
    schedules = Schedule.query.filter_by(teacher_id=current_user.id).order_by(Schedule.scheduled_at.desc()).all()
    
    student_data = []
    for student in students:
        progress = get_student_progress(student.id, current_user.id)
        fee_info = fee_map.get(student.id, {'fee_idr': current_user.default_fee, 'packet_type': 'session'})
        
        student_data.append({
            'id': student.id,
            'display_name': student.display_name,
            'progress': progress,
            'current_fee': fee_info['fee_idr'],
            'packet_type': fee_info['packet_type']
        })

    return render_template('teacher/dashboard.html', 
                         students=student_data, 
                         schedules=schedules,
                         current_time=datetime.utcnow())

@teacher_bp.route('/set_fee', methods=['POST'])
@teacher_required
def set_fee():
    # Handle both JSON and Form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    student_id = data.get('student_id')
    fee_idr = data.get('fee_idr')
    packet_type = data.get('packet_type', 'session')
    
    if not student_id or fee_idr is None:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Missing student_id or fee_idr'}), 400
        flash('Missing data', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    try:
        # Clean input (remove dots if Indonesian format used)
        fee_val = int(str(fee_idr).replace('.', ''))
    except ValueError:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Invalid fee amount'}), 400
        flash('Invalid fee amount', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    # Upsert logic
    fee = StudentFee.query.filter_by(teacher_id=current_user.id, student_id=student_id).first()
    if fee:
        fee.fee_idr = fee_val
        fee.packet_type = packet_type
    else:
        fee = StudentFee(
            teacher_id=current_user.id,
            student_id=student_id,
            fee_idr=fee_val,
            packet_type=packet_type
        )
        db.session.add(fee)
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Fee updated'})
    
    flash(tr('ok_saved', 'Settings saved.'), 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/add_attendance', methods=['POST'])
@teacher_required
def add_attendance():
    student_id = request.form.get('student_id')
    date_str = request.form.get('date')
    note = request.form.get('note', '')
    
    if not student_id or not date_str:
        flash('Missing data', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    try:
        class_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    existing = Attendance.query.filter_by(
        student_id=student_id,
        teacher_id=current_user.id,
        class_date=class_date
    ).first()
    
    if existing:
        flash('Attendance already recorded for this time', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    attn = Attendance(
        student_id=student_id,
        teacher_id=current_user.id,
        class_date=class_date,
        note=note,
        is_manual=True
    )
    db.session.add(attn)
    generate_receipts(student_id, current_user.id)
    db.session.commit()
    
    flash(tr('ok_attn', 'Attendance recorded!'), 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/delete_attendance/<int:attn_id>', methods=['POST'])
@teacher_required
def delete_attendance(attn_id):
    attn = Attendance.query.get_or_404(attn_id)
    if attn.teacher_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    db.session.delete(attn)
    db.session.commit()
    flash(tr('ok_deleted', 'Record deleted.'), 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/mark_paid/<int:receipt_id>', methods=['POST'])
@teacher_required
def mark_paid(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.student.teacher_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    receipt.is_paid = True
    receipt.paid_at = datetime.utcnow()
    db.session.commit()
    
    flash(tr('ok_paid', 'Marked as paid.'), 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/schedule_class', methods=['POST'])
@teacher_required
def schedule_class():
    date_str = request.form.get('scheduled_at')
    meet_link = request.form.get('meet_link', '')
    
    if not date_str:
        flash('Date required', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    try:
        scheduled_at = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    schedule = Schedule(
        teacher_id=current_user.id,
        scheduled_at=scheduled_at,
        meet_link=meet_link
    )
    db.session.add(schedule)
    db.session.commit()
    
    flash('Class scheduled!', 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/delete_schedule/<int:sched_id>', methods=['POST'])
@teacher_required
def delete_schedule(sched_id):
    sched = Schedule.query.get_or_404(sched_id)
    if sched.teacher_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    db.session.delete(sched)
    db.session.commit()
    flash('Schedule deleted', 'success')
    return redirect(url_for('teacher.dashboard'))
