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
    
    # Ambil HANYA absensi yang belum ditagih (billed=False)
    unbilled_attendances = Attendance.query.filter_by(
        student_id=student_id, 
        teacher_id=teacher_id, 
        billed=False
    ).order_by(Attendance.date.asc()).all()
    
    # --- DEBUG LOG ---
    print(f"DEBUG: Checking receipts for Student ID: {student_id}")
    print(f"DEBUG: Found {len(unbilled_attendances)} unbilled attendances.")
    # -----------------
    
    # Selama jumlah absen yang belum ditagih >= 8 (CYCLE_SIZE), buat struk!
    while len(unbilled_attendances) >= CYCLE_SIZE:
        print("DEBUG: Condition met (>=8 classes), generating receipt...")
        
        cycle_classes = unbilled_attendances[:CYCLE_SIZE]
        
        # Tarik data biaya
        fee_override = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
        teacher = User.query.get(teacher_id)
        fee_amount = fee_override.fee_idr if fee_override else (teacher.fee_idr if teacher else 0)
        student = User.query.get(student_id)
        
        # Ambil info bank guru
        t_bank_acc = teacher.bank_account if teacher and teacher.bank_account else "N/A"
        t_bank_name = teacher.bank_name if teacher and teacher.bank_name else "N/A"

        # Buat receipt
        receipt = Receipt(
            student_id=student_id,
            student_name=student.name() if student else "Unknown",
            teacher_id=teacher_id,
            teacher_name=teacher.name() if teacher else "Unknown",
            total_fee=fee_amount,
            bank_account=t_bank_acc,
            bank_name=t_bank_name,
            raw_dates="|".join([cls.date.isoformat() for cls in cycle_classes]),
            issue_date=datetime.utcnow(),
            paid=False
        )
        db.session.add(receipt)
        
        # Tandai absen sebagai sudah ditagih
        for cls in cycle_classes:
            cls.billed = True
        
        new_receipts.append(receipt)
        unbilled_attendances = unbilled_attendances[CYCLE_SIZE:]
            
    return new_receipts

def add_attendance(student_id: int, teacher_id: int, date: datetime, note: str = "", source: str = "teacher") -> Attendance:
    """
    Menambahkan kehadiran dengan toleransi waktu 60 detik.
    """
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
        student_id=student_id,
        teacher_id=teacher_id,
        date=date,
        note=note,
        source=source,
        billed=False
    )
    db.session.add(attn)
    db.session.commit()
    
    generate_receipts(student_id, teacher_id)
    db.session.commit()
    
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
