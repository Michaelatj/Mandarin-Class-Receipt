from app.models import db, Attendance, Receipt, StudentFee, User
from datetime import datetime, timedelta

def get_student_progress(student_id, teacher_id):
    """
    Calculate current cycle progress for a student.
    Returns: { 'current_cycle_count': int, 'cycle_number': int, 'total_sessions': int }
    """
    # Get all attendance records for this student with this teacher, ordered by date
    attendances = Attendance.query.filter_by(
        student_id=student_id, 
        teacher_id=teacher_id
    ).order_by(Attendance.class_date).all()
    
    total_sessions = len(attendances)
    if total_sessions == 0:
        return {'current_cycle_count': 0, 'cycle_number': 1, 'total_sessions': 0}
    
    # Calculate completed cycles (every 8 sessions)
    completed_cycles = total_sessions // 8
    current_cycle_count = total_sessions % 8
    cycle_number = completed_cycles + 1
    
    return {
        'current_cycle_count': current_cycle_count,
        'cycle_number': cycle_number,
        'total_sessions': total_sessions
    }

def generate_receipts(student_id, teacher_id):
    """
    Check if a student has completed 8 sessions in the current cycle.
    If so, generate a receipt for that cycle.
    """
    attendances = Attendance.query.filter_by(
        student_id=student_id, 
        teacher_id=teacher_id
    ).order_by(Attendance.class_date).all()
    
    total_sessions = len(attendances)
    
    # Only generate if we have a multiple of 8 sessions (8, 16, 24...)
    if total_sessions > 0 and total_sessions % 8 == 0:
        # Check if receipt already exists for this cycle to prevent duplicates
        cycle_number = total_sessions // 8
        
        existing_receipt = Receipt.query.filter_by(
            student_id=student_id,
            teacher_id=teacher_id,
            cycle_number=cycle_number
        ).first()
        
        if not existing_receipt:
            # Determine fee
            custom_fee = StudentFee.query.filter_by(
                teacher_id=teacher_id, 
                student_id=student_id
            ).first()
            
            fee_amount = custom_fee.fee_idr if custom_fee else teacher.default_fee
            
            # Get the date of the 8th class in this cycle (the last one)
            last_class_date = attendances[-1].class_date
            
            receipt = Receipt(
                student_id=student_id,
                teacher_id=teacher_id,
                cycle_number=cycle_number,
                sessions_count=8,
                total_fee=fee_amount,
                generated_at=datetime.utcnow(),
                period_start=attendances[-8].class_date,
                period_end=last_class_date
            )
            db.session.add(receipt)
            db.session.commit()
            return True
            
    return False

def set_custom_fee(teacher_id, student_id, fee_idr, packet_type='session'):
    """
    Set or update a custom fee for a specific student.
    """
    fee = StudentFee.query.filter_by(
        teacher_id=teacher_id, 
        student_id=student_id
    ).first()
    
    if fee:
        fee.fee_idr = fee_idr
        fee.packet_type = packet_type
    else:
        fee = StudentFee(
            teacher_id=teacher_id,
            student_id=student_id,
            fee_idr=fee_idr,
            packet_type=packet_type
        )
        db.session.add(fee)
    
    db.session.commit()
    return fee
