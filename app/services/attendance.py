"""
services/attendance.py — Business logic for attendance & receipts.
"""
from datetime import datetime, timedelta
from app.models import db, Attendance, Receipt, StudentFee, User
from typing import Optional

CYCLE_SIZE = 8

def generate_receipts(student_id: int, teacher_id: int) -> list[Receipt]:
    new_receipts = []
    
    # 1. Ambil HANYA absensi yang belum ditagih (billed=False)
    unbilled = Attendance.query.filter_by(
        student_id=student_id, teacher_id=teacher_id, billed=False
    ).order_by(Attendance.date.asc()).all()
    
    # Debug: Cek apakah ada data yang terbaca
    print(f"DEBUG: Found {len(unbilled)} unbilled attendances for student {student_id}")

    if not unbilled:
        return new_receipts

    # 2. Ambil data tarif dan info guru
    fee_obj = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    teacher = User.query.get(teacher_id)
    student = User.query.get(student_id)
    
    # Ambil tarif (override atau default)
    base_fee = fee_obj.fee_idr if fee_obj else (teacher.fee_idr if teacher else 70000)
    packet_type = fee_obj.packet_type if fee_obj else 'session'
    
    # Ambil data bank guru (PENTING: Jangan sampai kosong agar tidak error NotNull)
    t_bank_acc = teacher.bank_account if teacher and teacher.bank_account else "N/A"
    t_bank_name = teacher.bank_name if teacher and teacher.bank_name else "N/A"

    # 3. Logika Billing
    if packet_type == 'session':
        while len(unbilled) >= CYCLE_SIZE:
            cycle = unbilled[:CYCLE_SIZE]
            total = len(cycle) * base_fee 
            
            receipt = Receipt(
                student_id=student_id, student_name=student.name() if student else "Unknown",
                teacher_id=teacher_id, teacher_name=teacher.name() if teacher else "Unknown",
                total_fee=total,
                bank_account=t_bank_acc,
                bank_name=t_bank_name,
                raw_dates="|".join([cls.date.isoformat() for cls in cycle]),
                issue_date=datetime.utcnow(), paid=False
            )
            db.session.add(receipt)
            for cls in cycle: cls.billed = True
            db.session.commit() # Commit setiap pembuatan struk
            new_receipts.append(receipt)
            unbilled = unbilled[CYCLE_SIZE:]
            print("DEBUG: Receipt generated for session packet.")

    elif packet_type == 'monthly':
        first_date = unbilled[0].date
        # Jika sudah lewat 30 hari, tagih
        if (datetime.utcnow() - first_date).days >= 30:
            receipt = Receipt(
                student_id=student_id, student_name=student.name() if student else "Unknown",
                teacher_id=teacher_id, teacher_name=teacher.name() if teacher else "Unknown",
                total_fee=base_fee, # Flat fee per bulan
                bank_account=t_bank_acc,
                bank_name=t_bank_name,
                raw_dates="|".join([cls.date.isoformat() for cls in unbilled]),
                issue_date=datetime.utcnow(), paid=False
            )
            db.session.add(receipt)
            for cls in unbilled: cls.billed = True
            db.session.commit()
            new_receipts.append(receipt)
            print("DEBUG: Receipt generated for monthly packet.")

    return new_receipts

def add_attendance(student_id: int, teacher_id: int, date: datetime, note: str = "", source: str = "teacher") -> Attendance:
    # Cek duplikat (toleransi 30 detik)
    start = date - timedelta(seconds=30)
    end = date + timedelta(seconds=30)
    existing = Attendance.query.filter(
        Attendance.student_id == student_id, Attendance.teacher_id == teacher_id,
        Attendance.date >= start, Attendance.date <= end
    ).first()
    
    if existing: return existing
    
    attn = Attendance(student_id=student_id, teacher_id=teacher_id, date=date, note=note, source=source, billed=False)
    db.session.add(attn)
    db.session.commit()
    
    # Memicu logic generate
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
    if not record or record.teacher_id != teacher_id or record.billed: return False
    db.session.delete(record)
    db.session.commit()
    return True

def mark_receipt_paid(receipt_id: int, teacher_id: int) -> bool:
    receipt = Receipt.query.get(receipt_id)
    if not receipt or receipt.teacher_id != teacher_id: return False
    receipt.paid = True
    db.session.commit()
    return True
