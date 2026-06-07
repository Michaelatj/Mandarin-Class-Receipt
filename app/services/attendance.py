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
    
    # Ambil semua data absensi murid ini yang belum ditagih
    unbilled = Attendance.query.filter_by(
        student_id=student_id, teacher_id=teacher_id, billed=False
    ).order_by(Attendance.date.asc()).all()
    
    if not unbilled:
        return new_receipts

    # Tarik data biaya dan tipe paket
    fee_override = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    teacher = User.query.get(teacher_id)
    fee_amount = fee_override.fee_idr if fee_override else (teacher.fee_idr if teacher else 0)
    packet_type = getattr(fee_override, 'packet_type', 'session') if fee_override else 'session'
    
    def _create_receipt(cycle_classes):
        student = User.query.get(student_id)
        receipt = Receipt(
            student_id=student_id,
            student_name=student.name() if student else "Unknown",
            teacher_id=teacher_id,
            teacher_name=teacher.name() if teacher else "Unknown",
            total_fee=fee_amount,
            raw_dates="|".join([cls.date.isoformat() for cls in cycle_classes]),
            issue_date=datetime.utcnow(),
            paid=False
        )
        db.session.add(receipt)
        # Tandai semua absen dalam putaran ini sebagai sudah ditagih
        for cls in cycle_classes:
            cls.billed = True
        return receipt

    # ==== LOGIKA BILLING ====
    if packet_type == 'session':
        # Tiap 8 pertemuan, jadikan 1 struk
        while len(unbilled) >= CYCLE_SIZE:
            cycle_classes = unbilled[:CYCLE_SIZE]
            unbilled = unbilled[CYCLE_SIZE:]
            new_receipts.append(_create_receipt(cycle_classes))

    elif packet_type == 'monthly':
        # Hitung jarak 30 hari dari absen pertama yang belum ditagih
        while unbilled:
            first_date = unbilled[0].date
            last_date = unbilled[-1].date
            
            # Jika sudah mencapai 30 hari atau lebih
            if (last_date - first_date).days >= 30:
                # Kumpulkan semua absen yang masuk dalam rentang kurang dari 30 hari
                cycle_classes = [a for a in unbilled if (a.date - first_date).days < 30]
                
                # Sisa absen yang ada di hari ke-30 atau lebih (termasuk last_date), jadi cycle bulan depan
                unbilled = [a for a in unbilled if a not in cycle_classes]
                
                # Buat struk untuk satu bulan tersebut
                new_receipts.append(_create_receipt(cycle_classes))
            else:
                # Jika hari ini belum mencapai 30 hari, keluar dari loop (jangan buat struk dulu)
                break
                
    return new_receipts

def add_attendance(student_id: int, teacher_id: int, date: datetime, note: str = "", source: str = "teacher") -> Attendance:
    """
    Menambahkan kehadiran dan otomatis memicu logic struk/tagihan.
    """
    existing = Attendance.query.filter_by(student_id=student_id, teacher_id=teacher_id, date=date).first()
    if existing:
        raise ValueError("Kehadiran sudah tercatat untuk waktu ini")
    
    attn = Attendance(
        student_id=student_id,
        teacher_id=teacher_id,
        date=date,
        note=note,
        source=source,
        billed=False
    )
    db.session.add(attn)
    db.session.commit() # Penting: Commit absen dulu biar masuk daftar `unbilled`
    
    generate_receipts(student_id, teacher_id)
    db.session.commit() # Commit struk jika fungsi di atas berhasil buat struk baru
    
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
