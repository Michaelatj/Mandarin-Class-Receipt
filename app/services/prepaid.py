"""
services/prepaid.py - paying up front, and students who do not have an account yet.

A prepaid receipt is issued the moment the money is received, before any class happens:
  * monthly packet: pays for one or more calendar months (WIB). Classes inside that period
    are covered, so no new bill is made for them.
  * session packet: pays for a number of sessions. The next classes (from the payment day on)
    use them up, one by one, until they run out.
Covered classes are marked billed and their dates are added to the prepaid receipt, so the
receipt shows how much of it has been used. When the coverage ends, normal billing resumes.
"""
import re
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from .. import db
from ..models import (Attendance, QuizAttempt, Receipt, ScheduleInvite, ScheduleJoin,
                      StudentFee, User)

WIB = timedelta(hours=7)
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]
METHODS = ("Cash", "Bank transfer", "QRIS", "E-wallet", "Other")
MAX_AMOUNT = 1_000_000_000


class PrepaidError(ValueError):
    """A problem the teacher can fix, with a message that is safe to show."""


def visible_students(teacher_id):
    """Students a teacher can see: everyone with an account, plus students that teacher added."""
    return User.query.filter(User.role == "student",
                             db.or_(User.managed_by.is_(None), User.managed_by == teacher_id))


def create_managed_student(teacher, name, phone=""):
    name = (name or "").strip()[:100]
    if len(name) < 2:
        raise PrepaidError("Enter the student's name.")
    phone = re.sub(r"[^\d+ ()-]", "", phone or "")[:30]
    user = User(username="walkin-" + secrets.token_hex(4), role="student", display_name=name,
                phone=phone, managed_by=teacher.id,
                password=generate_password_hash(secrets.token_urlsafe(24)))   # nobody knows it, so no login
    db.session.add(user)
    db.session.commit()
    return user


def month_start_utc(year, month):
    return datetime(year, month, 1) - WIB


def _add_months(year, month, n):
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


def _label(year, month, count):
    first = f"{MONTHS_ID[month - 1]} {year}"
    if count == 1:
        return first
    ey, em = _add_months(year, month, count - 1)
    return f"{first} - {MONTHS_ID[em - 1]} {ey}"


def record_prepayment(teacher, student, *, mode, amount, paid_on=None, method="", year=None, month=None,
                      months=1, sessions=None):
    """Create a paid receipt for money received before the classes."""
    if student.role != "student" or (student.managed_by and student.managed_by != teacher.id):
        raise PrepaidError("Student not found.")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise PrepaidError("Enter the amount in rupiah.")
    if amount <= 0 or amount > MAX_AMOUNT:
        raise PrepaidError("The amount must be more than zero.")
    paid_on = paid_on or datetime.utcnow()
    if paid_on > datetime.utcnow() + timedelta(days=1):
        raise PrepaidError("The payment date cannot be in the future.")
    method = method if method in METHODS else ""

    if mode == "monthly":
        try:
            year, month, months = int(year), int(month), int(months or 1)
        except (TypeError, ValueError):
            raise PrepaidError("Pick the month this payment covers.")
        if not (1 <= month <= 12 and 2000 <= year <= 2100 and 1 <= months <= 12):
            raise PrepaidError("Pick the month this payment covers.")
        start = month_start_utc(year, month)
        ey, em = _add_months(year, month, months)
        end = month_start_utc(ey, em)
        covers = "Paket bulanan: " + _label(year, month, months)
        packet, qty = "monthly", None
    elif mode == "sessions":
        try:
            sessions = int(sessions)
        except (TypeError, ValueError):
            raise PrepaidError("Enter how many sessions were paid for.")
        if not (1 <= sessions <= 200):
            raise PrepaidError("Sessions must be between 1 and 200.")
        w = paid_on + WIB
        start = datetime(w.year, w.month, w.day) - WIB      # from the start of the payment day (WIB)
        end = None
        covers = f"{sessions} sesi dibayar di muka"
        packet, qty = "session", sessions
    else:
        raise PrepaidError("Choose monthly or per-session.")

    receipt = Receipt(
        student_id=student.id, student_name=student.name(),
        teacher_id=teacher.id, teacher_name=teacher.name(),
        bank_account=teacher.bank_account or "N/A", bank_name=teacher.bank_name or "N/A",
        total_fee=amount, raw_dates="", issue_date=paid_on, paid=True, paid_at=paid_on,
        packet_type=packet, custom_qty=qty, kind="prepaid", covers=covers, method=method,
        period_start=start, period_end=end,
    )
    db.session.add(receipt)
    db.session.commit()
    apply_prepaid_coverage(student.id, teacher.id)
    return receipt


def apply_prepaid_coverage(student_id, teacher_id):
    """Mark unbilled classes covered by a prepaid receipt as billed, and list them on that receipt.
    Returns how many classes were covered."""
    prepaid = (Receipt.query.filter_by(student_id=student_id, teacher_id=teacher_id, kind="prepaid", paid=True)
               .order_by(Receipt.period_start.asc(), Receipt.id.asc()).all())
    if not prepaid:
        return 0
    covered = 0
    for r in prepaid:
        used = [d for d in (r.raw_dates or "").split("|") if d.strip()]
        q = Attendance.query.filter(Attendance.student_id == student_id, Attendance.teacher_id == teacher_id,
                                    Attendance.billed.is_(False))
        if r.packet_type == "monthly":
            q = q.filter(Attendance.date >= r.period_start, Attendance.date < r.period_end)
            rows = q.order_by(Attendance.date.asc()).all()
        else:
            room = (r.custom_qty or 0) - len(used)
            if room <= 0:
                continue
            rows = q.filter(Attendance.date >= r.period_start).order_by(Attendance.date.asc()).limit(room).all()
        for a in rows:
            a.billed = True
            used.append(a.date.isoformat())
            covered += 1
        if rows:
            r.raw_dates = "|".join(used)
    if covered:
        db.session.commit()
    return covered


def prepaid_usage(receipt):
    """(used, total) for a prepaid receipt; total is None for a monthly packet."""
    used = len([d for d in (receipt.raw_dates or "").split("|") if d.strip()])
    return used, (receipt.custom_qty if receipt.packet_type != "monthly" else None)


def link_managed_student(teacher, managed, account):
    """Move everything recorded under a student without an account onto their real account."""
    if managed.managed_by != teacher.id or managed.role != "student":
        raise PrepaidError("That student was not added by you.")
    if account.role != "student" or account.managed_by:
        raise PrepaidError("Pick a student who has registered an account.")
    moved = {"attendance": 0, "receipts": 0}
    moved["attendance"] = Attendance.query.filter_by(student_id=managed.id).update({"student_id": account.id})
    moved["receipts"] = Receipt.query.filter_by(student_id=managed.id).update({"student_id": account.id})

    mine = StudentFee.query.filter_by(student_id=managed.id).all()
    for fee in mine:
        if StudentFee.query.filter_by(teacher_id=fee.teacher_id, student_id=account.id).first():
            db.session.delete(fee)
        else:
            fee.student_id = account.id
    for model in (ScheduleJoin, ScheduleInvite):
        for row in model.query.filter_by(student_id=managed.id).all():
            if model.query.filter_by(schedule_id=row.schedule_id, student_id=account.id).first():
                db.session.delete(row)
            else:
                row.student_id = account.id
    QuizAttempt.query.filter_by(student_id=managed.id).update({"student_id": account.id})
    db.session.delete(managed)
    db.session.commit()
    apply_prepaid_coverage(account.id, teacher.id)
    return moved
