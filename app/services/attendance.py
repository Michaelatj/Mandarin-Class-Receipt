"""
services/attendance.py — Business logic for attendance and receipt generation.

All database-touching logic that isn't a simple query lives here,
keeping routes thin and this layer independently testable.
"""
import logging
from datetime import datetime
from .. import db
from ..models import Attendance, Receipt, StudentFee, User

logger = logging.getLogger(__name__)


def get_custom_fee(teacher_id: int, student_id: int, default_fee: int) -> int:
    """
    Return the teacher's custom fee for this student, or the default if none set.
    """
    override = StudentFee.query.filter_by(
        teacher_id=teacher_id, student_id=student_id
    ).first()
    return override.fee_idr if override else default_fee


def set_custom_fee(teacher_id: int, student_id: int, fee: int) -> None:
    """Create or update a per-student fee override."""
    existing = StudentFee.query.filter_by(
        teacher_id=teacher_id, student_id=student_id
    ).first()
    if existing:
        existing.fee_idr = fee
    else:
        db.session.add(StudentFee(
            teacher_id=teacher_id, student_id=student_id, fee_idr=fee
        ))
    db.session.commit()
    logger.info("Custom fee set: teacher=%d student=%d fee=%d", teacher_id, student_id, fee)


def add_attendance(student_id: int, teacher_id: int,
                   date: datetime | None = None, note: str = "",
                   source: str = "teacher") -> Attendance | None:
    """
    Add one attendance record and check whether a receipt should be generated.
    Returns the new Attendance object, or None if blocked by 90-min cooldown.

    Cooldown applies to student-initiated submissions (source='student' or 'join').
    Teacher manual entries (source='teacher') bypass cooldown.
    """
    from datetime import timedelta
    now = date or datetime.utcnow()

    # 90-minute cooldown — only for student/join sources, not teacher manual
    if source in ("student", "join"):
        cutoff = now - timedelta(minutes=90)
        recent = (
            Attendance.query
            .filter(
                Attendance.student_id == student_id,
                Attendance.teacher_id == teacher_id,
                Attendance.date >= cutoff,
                Attendance.source.in_(["student", "join"]),
            )
            .first()
        )
        if recent:
            logger.info(
                "Cooldown blocked attendance: student=%d teacher=%d "
                "(last was %s, within 90 min)",
                student_id, teacher_id, recent.date.isoformat(),
            )
            return None

    record = Attendance(
        student_id=student_id,
        teacher_id=teacher_id,
        date=now,
        note=note[:200],
        source=source,
    )
    db.session.add(record)
    db.session.commit()
    logger.info("Attendance added: student=%d teacher=%d date=%s source=%s",
                student_id, teacher_id, record.date.isoformat(), source)

    student = db.session.get(User, student_id)
    teacher = db.session.get(User, teacher_id)
    _maybe_generate_receipt(student, teacher)
    return record


def delete_attendance(attendance_id: int, teacher_id: int) -> bool:
    """
    Delete an unbilled attendance record that belongs to teacher_id.
    Returns True if deleted, False if not found / already billed / wrong owner.
    """
    record = db.session.get(Attendance, attendance_id)
    if not record:
        return False
    if record.teacher_id != teacher_id:
        logger.warning("Teacher %d tried to delete attendance %d owned by teacher %d",
                       teacher_id, attendance_id, record.teacher_id)
        return False
    if record.billed:
        logger.warning("Attempted to delete already-billed attendance %d", attendance_id)
        return False
    db.session.delete(record)
    db.session.commit()
    logger.info("Attendance %d deleted by teacher %d", attendance_id, teacher_id)
    return True


def mark_receipt_paid(receipt_id: int, teacher_id: int) -> bool:
    """
    Mark a receipt as paid. Only the owning teacher may do this.
    Returns True on success.
    """
    receipt = db.session.get(Receipt, receipt_id)
    if not receipt or receipt.teacher_id != teacher_id:
        return False
    receipt.paid = True
    db.session.commit()
    logger.info("Receipt %d marked paid by teacher %d", receipt_id, teacher_id)
    return True


def get_student_progress(teacher_id: int) -> list[dict]:
    """
    Return a list of dicts summarising each student's current unbilled progress
    under this teacher:  [{name, count, dates, student_id}, ...]

    Always includes ALL students who have ever had attendance with this teacher,
    even if they currently have 0 unbilled (shows 0/8).
    """
    # All students who ever had ANY attendance with this teacher
    all_records = (
        Attendance.query
        .filter_by(teacher_id=teacher_id)
        .order_by(Attendance.date.asc())
        .all()
    )

    # Build set of all student_ids who have ever attended
    seen_students: dict[int, dict] = {}
    for record in all_records:
        if record.student_id not in seen_students:
            student = db.session.get(User, record.student_id)
            seen_students[record.student_id] = {
                "student_id": record.student_id,
                "name": student.name() if student else "?",
                "count": 0,        # unbilled count
                "dates": [],       # unbilled dates only
            }

    # Now fill in unbilled counts
    unbilled = (
        Attendance.query
        .filter_by(teacher_id=teacher_id, billed=False)
        .order_by(Attendance.date.asc())
        .all()
    )
    for record in unbilled:
        if record.student_id in seen_students:
            seen_students[record.student_id]["count"] += 1
            seen_students[record.student_id]["dates"].append(record.date)

    return list(seen_students.values())


# ── Internal ──────────────────────────────────────────────────────────────────

def _maybe_generate_receipt(student: User | None, teacher: User | None) -> None:
    """
    Check if student has reached CLASSES_PER_CYCLE unbilled sessions with this
    teacher. If so, create a Receipt and mark those sessions as billed.
    """
    if not student or not teacher:
        return

    from flask import current_app
    cycle_size = current_app.config.get("CLASSES_PER_CYCLE", 8)

    unbilled = (
        Attendance.query
        .filter_by(student_id=student.id, teacher_id=teacher.id, billed=False)
        .order_by(Attendance.date.asc())
        .all()
    )

    if len(unbilled) < cycle_size:
        return

    batch     = unbilled[:cycle_size]
    raw_dates = "|".join(a.date.strftime("%Y-%m-%dT%H:%M:%S") for a in batch)
    fee       = get_custom_fee(teacher.id, student.id, teacher.fee_idr)

    # Sequential receipt number per teacher (survives deletions)
    last = (Receipt.query
            .filter_by(teacher_id=teacher.id)
            .order_by(Receipt.receipt_no.desc())
            .first())
    next_no = (last.receipt_no or 0) + 1 if last else 1

    receipt = Receipt(
        receipt_no   = next_no,
        student_id   = student.id,
        student_name = student.name(),
        teacher_id   = teacher.id,
        teacher_name = teacher.name(),
        bank_account = teacher.bank_account,
        bank_name    = teacher.bank_name,
        total_fee    = fee,
        raw_dates    = raw_dates,
    )
    db.session.add(receipt)

    for record in batch:
        record.billed = True

    db.session.commit()
    logger.info(
        "Receipt generated: student=%s teacher=%s fee=%d",
        student.name(), teacher.name(), fee,
    )
