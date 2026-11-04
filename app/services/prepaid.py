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
from ..models import (Attendance, QuizAttempt, Receipt, ScheduleAbsent, ScheduleInvite, ScheduleJoin,
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


SESSIONS_PER_INVOICE = 8      # a pay-first session packet is invoiced 8 classes at a time
INVOICE_AHEAD_DAYS = 7        # a monthly packet is invoiced this many days before the month ends
ACTIVE_DAYS = 60              # a student with no class for this long is not invoiced again by itself


def ensure_upfront_invoice(student_id, teacher_id, force_first=False, now=None):
    """For a pay-first student, issue the next unpaid prepaid receipt when the paid coverage
    has run out (or, for a monthly packet, is about to). Returns the new receipt or None.

    The very first invoice is only made on request (force_first, when the teacher turns on pay
    first); after that invoices follow the student's classes, and stop for a student who has
    gone quiet, so a deleted invoice does not come back for someone who left."""
    fee = StudentFee.query.filter_by(teacher_id=teacher_id, student_id=student_id).first()
    if not fee or not fee.pay_first or not fee.fee_idr or fee.fee_idr <= 0:
        return None
    now = now or datetime.utcnow()

    q = Receipt.query.filter_by(student_id=student_id, teacher_id=teacher_id, kind="prepaid")
    if q.filter_by(paid=False).first():
        return None                                   # one is already waiting for payment
    paid = q.filter_by(paid=True).order_by(Receipt.period_start.asc(), Receipt.id.asc()).all()
    if not paid and not force_first:
        return None
    if paid and not force_first:
        last_class = (db.session.query(db.func.max(Attendance.date))
                      .filter(Attendance.student_id == student_id, Attendance.teacher_id == teacher_id).scalar())
        if not last_class or last_class < now - timedelta(days=ACTIVE_DAYS):
            return None

    student = db.session.get(User, student_id)
    teacher = db.session.get(User, teacher_id)
    if not student or not teacher:
        return None

    if fee.packet_type == "monthly":
        monthly = [r for r in paid if r.packet_type == "monthly" and r.period_end]
        latest_end = max((r.period_end for r in monthly), default=None)
        if latest_end and latest_end > now:
            if latest_end - now > timedelta(days=INVOICE_AHEAD_DAYS):
                return None                           # this month is still paid for
            local = latest_end + WIB                  # the month after the paid one
        else:
            local = now + WIB                         # nothing paid for the current month
        year, month = local.year, local.month
        start = month_start_utc(year, month)
        ey, em = _add_months(year, month, 1)
        end = month_start_utc(ey, em)
        covers = "Paket bulanan: " + _label(year, month, 1)
        packet, qty, amount = "monthly", None, fee.fee_idr
    else:
        sessions = [r for r in paid if r.packet_type != "monthly"]
        left = sum(max(0, (r.custom_qty or 0) - len([d for d in (r.raw_dates or "").split("|") if d.strip()]))
                   for r in sessions)
        if left > 0:
            return None                               # paid sessions are still left
        w = now + WIB
        start = datetime(w.year, w.month, w.day) - WIB
        # classes attended before the invoice was paid should be covered by it too
        first_open = (Attendance.query.filter_by(student_id=student_id, teacher_id=teacher_id, billed=False)
                      .order_by(Attendance.date.asc()).first())
        if first_open and first_open.date < start:
            start = first_open.date
        end = None
        covers = f"{SESSIONS_PER_INVOICE} sesi dibayar di muka"
        packet, qty, amount = "session", SESSIONS_PER_INVOICE, fee.fee_idr * SESSIONS_PER_INVOICE

    invoice = Receipt(
        student_id=student.id, student_name=student.name(),
        teacher_id=teacher.id, teacher_name=teacher.name(),
        bank_account=teacher.bank_account or "N/A", bank_name=teacher.bank_name or "N/A",
        total_fee=amount, raw_dates="", issue_date=now, paid=False, paid_at=None,
        packet_type=packet, custom_qty=qty, kind="prepaid", covers=covers, method="",
        period_start=start, period_end=end,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


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


def last_month_attendance(receipt):
    """(label, [attendance datetimes in UTC]) for the calendar month (WIB) before the month this
    prepaid receipt starts in. A pay-first student is billed ahead, so the receipt also shows what
    they actually attended the month before. It is read from the attendance records, so no
    schedule has to exist for that month."""
    ref = receipt.period_start if (receipt.packet_type == "monthly" and receipt.period_start) \
        else (receipt.issue_date or datetime.utcnow())
    local = ref + WIB
    py, pm = _add_months(local.year, local.month, -1)
    rows = (Attendance.query
            .filter(Attendance.student_id == receipt.student_id, Attendance.teacher_id == receipt.teacher_id,
                    Attendance.date >= month_start_utc(py, pm),
                    Attendance.date < month_start_utc(local.year, local.month))
            .order_by(Attendance.date.asc()).all())
    return f"{MONTHS_ID[pm - 1]} {py}", [a.date for a in rows]


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
    for model in (ScheduleJoin, ScheduleInvite, ScheduleAbsent):
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
