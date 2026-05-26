"""
services/attendance.py — Business logic for attendance & receipts.
"""
from datetime import datetime, timedelta
from app.models import db, Attendance, Receipt, StudentFee, User
from typing import Optional

# Constants
CYCLE_SIZE = 8

def get_student_progress(teacher_id: int) -> list[dict]:
    active = Attendance.query.filter_by(teacher_id=teacher_id, billed=False).order_by(Attendance.date.asc()).all()
    progress: dict[int, dict] = {}
    for record in active:
        if record.student_id not in progress:
            student = db.session.get(User, record.student_id)
            progress[record.student_id] = {
                "student_id": record.student_id,
                "name": student.name() if student else "?",
                "count": 0,
                "dates": [],
            }
        progress[record.student_id]["count"] += 1
        progress[record.student_id]["dates"].append(record.date)
    return list(progress.values())

def generate_receipts(student_id: int, teacher_id: int) -> list[Receipt]:
    new_receipts = []
    fee_override = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    teacher = User.query.get(teacher_id)
    fee_amount = fee_override.fee_idr if fee_override else (teacher.fee_idr if teacher else 0)
    
    attendances = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher_id).order_by(Attendance.date).all()
    total_classes = len(attendances)
    existing_receipts = Receipt.query.filter_by(student_id=student_id, teacher_id=teacher.id).count()
    expected_receipts = total_classes // CYCLE_SIZE
    
    while existing_receipts < expected_receipts:
        cycle_start_idx = existing_receipts * CYCLE_SIZE
        cycle_classes = attendances[cycle_start_idx:cycle_start_idx + CYCLE_SIZE]
        if len(cycle_classes) == CYCLE_SIZE:
            student = User.query.get(student_id)
            receipt = Receipt(
                student_id=student_id,
                student_name=student.name() if student else "Unknown",
                teacher_id=teacher_id,
                teacher_name=teacher.name() if teacher else "Unknown",
                total_fee=fee_amount,
                raw_dates="|".join([cls.date.isoformat() for cls in cycle_classes]),
                issue_date=datetime.utcnow()
            )
            db.session.add(receipt)
            new_receipts.append(receipt)
            existing_receipts += 1
    return new_receipts

def add_attendance(student_id: int, teacher_id: int, date: datetime, note: str = "", source: str = "teacher") -> Attendance:
    """
    Menambahkan kehadiran. Argumen sudah disesuaikan agar sesuai dengan teacher.py
    """
    existing = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher_id, date=date).first()
    if existing:
        raise ValueError("Kehadiran sudah tercatat untuk waktu ini")
    
    attn = Attendance(
        student_id=student_id,
        teacher_id=teacher_id,
        date=date,
        note=note,
        source=source
    )
    db.session.add(attn)
    db.session.commit() # Penting: Commit di sini agar data tersimpan
    
    generate_receipts(student_id, teacher_id)
    db.session.commit() # Commit receipt jika ada
    
    return attn

def set_custom_fee(teacher_id: int, student_id: int, fee_idr: int, packet_type: str = 'session') -> StudentFee:
    fee = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if fee:
        fee.fee_idr = fee_idr
        fee.packet_type = packet_type
    else:
        fee = StudentFee(teacher_id=teacher_id, student_id=student_id, fee_idr=fee_idr, packet_type=packet_type)
        db.session.add(fee)
    db.session.commit()
    return fee

def delete_attendance(att_id: int, teacher_id: int) -> bool:
    record = Attendance.query.get(att_id)
    if not record or record.teacher_id != teacher_id or record.billed:
        return False
    db.session.delete(record)
    db.session.commit()
    return True

def mark_receipt_paid(receipt_id: int, teacher_id: int) -> bool:
    receipt = Receipt.query.get(receipt_id)
    if not receipt or receipt.teacher_id != teacher_id:
        return False
    receipt.paid = True
    db.session.commit()
    return True
