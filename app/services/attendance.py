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

def generate_receipts(student_id: int, teacher_id: int, force: bool = False) -> list[Receipt]:
    new_receipts = []
    unbilled = Attendance.query.filter_by(
        student_id=student_id, teacher_id=teacher_id, billed=False
    ).order_by(Attendance.date.asc()).all()
    
    if not unbilled:
        return new_receipts
    
    fee_obj = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    teacher = User.query.get(teacher_id)
    student = User.query.get(student_id)
    
    base_fee = fee_obj.fee_idr if fee_obj else 0
    packet_type = fee_obj.packet_type if fee_obj else 'session'
    
    t_bank_acc = teacher.bank_account if teacher and teacher.bank_account else "N/A"
    t_bank_name = teacher.bank_name if teacher and teacher.bank_name else "N/A"

    first_date = unbilled[0].date
    days_since_start = (datetime.utcnow() - first_date).days

    should_bill = False
    total_fee = 0
    
    # FIX: Tambahkan kondisi `or force` di setiap pilihan 💥
    if packet_type == 'monthly':
        if days_since_start >= 30 or force:
            should_bill = True
            total_fee = base_fee
    elif packet_type == 'per_session':
        if days_since_start >= 30 or force:
            should_bill = True
            total_fee = len(unbilled) * base_fee
    else: 
        if len(unbilled) >= 8 or force:
            should_bill = True
            total_fee = len(unbilled) * base_fee

    if should_bill:
        receipt = Receipt(
            student_id=student_id, student_name=student.name(),
            teacher_id=teacher_id, teacher_name=teacher.name(),
            total_fee=total_fee, bank_account=t_bank_acc, bank_name=t_bank_name,
            raw_dates="|".join([cls.date.isoformat() for cls in unbilled]),
            issue_date=datetime.utcnow(), paid=False,
            packet_type=packet_type, custom_qty=len(unbilled) # Simpan qty aktual saat diregenerate
        )
        db.session.add(receipt)
        for cls in unbilled: cls.billed = True
        db.session.commit()
        new_receipts.append(receipt)
            
    return new_receipts

def add_attendance(student_id: int, teacher_id: int, date: datetime, note: str = "", source: str = "teacher") -> Attendance:
    start_time = date - timedelta(seconds=30)
    end_time = date + timedelta(seconds=30)
    
    existing = Attendance.query.filter(
        Attendance.student_id == student_id,
        Attendance.teacher_id == teacher_id,
        Attendance.date >= start_time,
        Attendance.date <= end_time
    ).first()
    
    if existing:
        return existing
    
    attn = Attendance(
        student_id=student_id, teacher_id=teacher_id,
        date=date, note=note, source=source, billed=False
    )
    db.session.add(attn)
    db.session.commit()
    
    generate_receipts(student_id, teacher_id)
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
