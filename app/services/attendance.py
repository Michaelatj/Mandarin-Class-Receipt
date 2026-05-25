"""
services/attendance.py — Business logic for attendance & receipts.
"""
from datetime import datetime, timedelta
from app.models import db, Attendance, Receipt, StudentFee, User
from typing import Optional, Dict, Any

# Constants
CYCLE_SIZE = 8

def get_student_progress(student_id: int, teacher_id: int) -> Dict[str, Any]:
    """
    Calculate current cycle progress for a student with a specific teacher.
    Returns dict with: current_cycle_count, cycle_number, total_classes, next_receipt_date
    """
    # Get all attendances for this student-teacher pair
    attendances = Attendance.query.filter_by(
        student_id=student_id, 
        teacher_id=teacher_id
    ).order_by(Attendance.date).all()
    
    if not attendances:
        return {
            'current_cycle_count': 0,
            'cycle_number': 1,
            'total_classes': 0,
            'next_receipt_date': None
        }
    
    total_classes = len(attendances)
    
    # Calculate completed cycles and current progress
    completed_cycles = total_classes // CYCLE_SIZE
    current_cycle_count = total_classes % CYCLE_SIZE
    cycle_number = completed_cycles + 1
    
    # Find date of next class (for next receipt estimation)
    next_class = None
    if current_cycle_count == 0:
        # Just completed a cycle, next class starts new cycle
        # Look for future scheduled classes or use last class + 1 week estimate
        last_class = attendances[-1].date
        next_class = last_class + timedelta(days=7) # Estimate
    else:
        # In middle of cycle
        next_class = attendances[-1].date + timedelta(days=7) # Estimate

    return {
        'current_cycle_count': current_cycle_count,
        'cycle_number': cycle_number,
        'total_classes': total_classes,
        'next_receipt_date': next_class
    }

def generate_receipts(student_id: int, teacher_id: int) -> list[Receipt]:
    """
    Check if student completed a cycle (8 classes) and generate receipt if needed.
    Returns list of newly created receipts.
    """
    new_receipts = []
    
    # Get fee for this student
    fee_override = StudentFee.query.filter_by(
        teacher_id=teacher_id, 
        student_id=student_id
    ).first()
    
    # Get teacher to access default fee
    teacher = User.query.get(teacher_id)
    fee_amount = fee_override.fee_idr if fee_override else (teacher.fee_idr if teacher else 0)
    
    # Get all attendances
    attendances = Attendance.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id
    ).order_by(Attendance.date).all()
    
    total_classes = len(attendances)
    
    # Check how many receipts already exist
    existing_receipts = Receipt.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id
    ).count()
    
    # Calculate how many receipts should exist
    expected_receipts = total_classes // CYCLE_SIZE
    
    # Generate missing receipts
    while existing_receipts < expected_receipts:
        cycle_start_idx = existing_receipts * CYCLE_SIZE
        cycle_end_idx = cycle_start_idx + CYCLE_SIZE
        
        cycle_classes = attendances[cycle_start_idx:cycle_end_idx]
        if len(cycle_classes) == CYCLE_SIZE:
            # Get student info
            student = User.query.get(student_id)
            receipt = Receipt(
                student_id=student_id,
                student_name=student.name() if student else "Unknown",
                teacher_id=teacher_id,
                teacher_name=teacher.name() if teacher else "Unknown",
                bank_account=teacher.bank_account if teacher else "",
                bank_name=teacher.bank_name if teacher else "",
                total_fee=fee_amount,
                raw_dates="|".join([cls.date.isoformat() for cls in cycle_classes]),
                issue_date=datetime.utcnow()
            )
            db.session.add(receipt)
            new_receipts.append(receipt)
            existing_receipts += 1
    
    return new_receipts

def add_attendance(student_id: int, teacher_id: int, class_date: datetime, note: str = "", is_manual: bool = False) -> Attendance:
    """
    Add a single attendance record.
    """
    # Check for duplicates
    existing = Attendance.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id,
        date=class_date
    ).first()
    
    if existing:
        raise ValueError("Attendance already exists for this date/time")
    
    attn = Attendance(
        student_id=student_id,
        teacher_id=teacher_id,
        date=class_date,
        note=note,
        source="teacher" if not is_manual else "manual"
    )
    db.session.add(attn)
    
    # Try to generate receipts if cycle completes
    generate_receipts(student_id, teacher_id)
    
    return attn

def set_custom_fee(teacher_id: int, student_id: int, fee_idr: int, packet_type: str = 'session') -> StudentFee:
    """
    Set or update custom fee for a student.
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
    
    return fee

def can_student_mark_attendance(student_id: int, teacher_id: int) -> tuple[bool, str]:
    """
    Check if student can mark attendance (90 min cooldown).
    Returns (can_mark, reason_message)
    """
    last_attendance = Attendance.query.filter_by(
        student_id=student_id,
        teacher_id=teacher_id
    ).order_by(Attendance.date.desc()).first()
    
    if not last_attendance:
        return True, "OK"
    
    now = datetime.utcnow()
    time_since_last = now - last_attendance.date
    
    if time_since_last < timedelta(minutes=90):
        remaining = 90 - int(time_since_last.total_seconds() / 60)
        return False, f"Please wait {remaining} minutes before marking again."
    
    return True, "OK"
