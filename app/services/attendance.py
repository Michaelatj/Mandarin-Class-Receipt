"""
services/attendance.py — Business logic for attendance & receipts.
"""
from datetime import datetime, timedelta
from typing import Optional
from app.models import db, Attendance, Receipt, StudentFee, User

# Constants
CYCLE_SIZE = 8  # Jumlah pertemuan per siklus untuk paket session


def get_student_progress(teacher_id: int) -> list[dict]:
    active = (
        Attendance.query.filter_by(teacher_id=teacher_id, billed=False)
        .order_by(Attendance.date.asc())
        .all()
    )
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
    unbilled = (
        Attendance.query.filter_by(
            student_id=student_id, teacher_id=teacher_id, billed=False
        )
        .order_by(Attendance.date.asc())
        .all()
    )

    if not unbilled:
        return new_receipts

    fee_obj = StudentFee.query.filter_by(
        teacher_id=teacher_id, student_id=student_id
    ).first()
    teacher = User.query.get(teacher_id)
    student = User.query.get(student_id)

    base_fee = fee_obj.fee_idr if fee_obj else 0
    packet_type = fee_obj.packet_type if fee_obj else "session"

    t_bank_acc = (
        teacher.bank_account if teacher and teacher.bank_account else "N/A"
    )
    t_bank_name = (
        teacher.bank_name if teacher and teacher.bank_name else "N/A"
    )

    first_date = unbilled[0].date
    today = datetime.utcnow()
    days_since_start = (today - first_date).days

    # Hitung selisih bulan kalender antara sesi pertama unbilled dan hari ini
    months_elapsed = (today.year - first_date.year) * 12 + (
        today.month - first_date.month
    )

    should_bill = False
    total_fee = 0

    
    # ✅ KODE YANG BENAR:
    if packet_type == 'monthly':
        if months_elapsed >= 1 or force:
            should_bill = True
            total_fee = base_fee
    elif packet_type == 'per_session':
        if days_since_start >= 30 or force:
            should_bill = True
            total_fee = len(unbilled) * base_fee
    else:
        # Default paket 'session' (tiap 8 pertemuan)
        if len(unbilled) >= CYCLE_SIZE or force:
            should_bill = True
            total_fee = len(unbilled) * base_fee

    if should_bill:
        receipt = Receipt(
            student_id=student_id,
            student_name=student.name() if student else "?",
            teacher_id=teacher_id,
            teacher_name=teacher.name() if teacher else "?",
            total_fee=total_fee,
            bank_account=t_bank_acc,
            bank_name=t_bank_name,
            raw_dates="|".join([cls.date.isoformat() for cls in unbilled]),
            issue_date=today,
            paid=False,
            packet_type=packet_type,
            custom_qty=len(unbilled),
        )
        db.session.add(receipt)
        for cls in unbilled:
            cls.billed = True
        db.session.commit()
        new_receipts.append(receipt)

    return new_receipts


def add_attendance(
    student_id: int,
    teacher_id: int,
    date: datetime,
    note: str = "",
    source: str = "teacher",
) -> Attendance:
    # 90-MINUTE GLOBAL DB COOLDOWN
    if source in ["student", "join"]:
        start_time = date - timedelta(minutes=90)
        existing = Attendance.query.filter(
            Attendance.student_id == student_id,
            Attendance.teacher_id == teacher_id,
            Attendance.date >= start_time,
            Attendance.date <= date,
            Attendance.source.in_(["student", "join"]),
        ).first()
    else:
        # Teacher manual input check (30 seconds)
        start_time = date - timedelta(seconds=30)
        end_time = date + timedelta(seconds=30)
        existing = Attendance.query.filter(
            Attendance.student_id == student_id,
            Attendance.teacher_id == teacher_id,
            Attendance.date >= start_time,
            Attendance.date <= end_time,
        ).first()

    if existing:
        return existing

    attn = Attendance(
        student_id=student_id,
        teacher_id=teacher_id,
        date=date,
        note=note,
        source=source,
        billed=False,
    )
    db.session.add(attn)
    db.session.commit()

    generate_receipts(student_id, teacher_id)
    return attn


def set_custom_fee(
    teacher_id: int, student_id: int, fee_idr: int, packet_type: str = "session"
) -> StudentFee:
    fee = StudentFee.query.filter_by(
        teacher_id=teacher_id, student_id=student_id
    ).first()
    if fee:
        fee.fee_idr = fee_idr
        fee.packet_type = packet_type
    else:
        fee = StudentFee(
            teacher_id=teacher_id,
            student_id=student_id,
            fee_idr=fee_idr,
            packet_type=packet_type,
        )
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

def cancel_receipt(receipt_id: int, teacher_id: int) -> bool:
    """Membatalkan receipt dan mengembalikan status kehadiran menjadi billed=False (unbilled)."""
    receipt = (
        db.session.get(Receipt, receipt_id)
        if hasattr(db.session, 'get')
        else Receipt.query.get(receipt_id)
    )
    if not receipt or receipt.teacher_id != teacher_id:
        return False

    # 1. Kembalikan semua sesi absensi di raw_dates menjadi billed = False
    if receipt.raw_dates:
        date_strs = receipt.raw_dates.split("|")
        for d_str in date_strs:
            if not d_str.strip():
                continue
            try:
                dt = datetime.fromisoformat(d_str.strip())
                attn = Attendance.query.filter_by(
                    student_id=receipt.student_id,
                    teacher_id=teacher_id,
                    date=dt,
                ).first()
                if attn:
                    attn.billed = False
            except Exception:
                continue

    # 2. Hapus receipt yang salah terbit
    db.session.delete(receipt)
    db.session.commit()
    return True
