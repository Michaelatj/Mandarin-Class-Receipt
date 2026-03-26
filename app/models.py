"""
models.py — SQLAlchemy database models.

All models live here so they are imported once and shared across
blueprints without circular imports.
"""
from datetime import datetime
from . import db


class User(db.Model):
    __tablename__ = "user"

    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password     = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100), default="")
    role         = db.Column(db.String(10), nullable=False)   # 'teacher' | 'student'
    bank_account = db.Column(db.String(100), default="")
    bank_name    = db.Column(db.String(100), default="")
    fee_idr      = db.Column(db.Integer, default=0)           # teacher default fee
    phone        = db.Column(db.String(30), default="")
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def name(self) -> str:
        """Return display_name if set, otherwise username."""
        return self.display_name or self.username

    def __repr__(self) -> str:
        return f"<User {self.username!r} ({self.role})>"


class StudentFee(db.Model):
    """Per-student tuition fee override set by a specific teacher."""
    __tablename__ = "student_fee"

    id         = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    fee_idr    = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "student_id", name="uq_teacher_student_fee"),
    )

    def __repr__(self) -> str:
        return f"<StudentFee teacher={self.teacher_id} student={self.student_id} fee={self.fee_idr}>"


class Attendance(db.Model):
    __tablename__ = "attendance"

    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    date       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    billed     = db.Column(db.Boolean, default=False, nullable=False)
    note       = db.Column(db.String(200), default="")

    def __repr__(self) -> str:
        return f"<Attendance student={self.student_id} date={self.date:%Y-%m-%d}>"


class Receipt(db.Model):
    __tablename__ = "receipt"

    id           = db.Column(db.Integer, primary_key=True)
    student_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=False)
    teacher_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    teacher_name = db.Column(db.String(100), nullable=False)
    bank_account = db.Column(db.String(100), nullable=False)
    bank_name    = db.Column(db.String(100), default="")
    total_fee    = db.Column(db.Integer, nullable=False)
    # Pipe-separated ISO-8601 timestamps: "2025-01-15T14:30:00|2025-01-22T14:30:00|..."
    # Stored language-independently; rendered into the current UI language on every request.
    raw_dates    = db.Column(db.String(2000), nullable=False, default="")
    issue_date   = db.Column(db.DateTime, default=datetime.utcnow)
    paid         = db.Column(db.Boolean, default=False)

    def get_dates(self):
        """Return a list of datetime objects parsed from raw_dates."""
        from ..services.i18n import parse_raw_dates
        return parse_raw_dates(self.raw_dates)

    def __repr__(self) -> str:
        return f"<Receipt #{self.id} student={self.student_name!r} fee={self.total_fee}>"


class Schedule(db.Model):
    """A class session scheduled by a teacher, with an optional Meet link."""
    __tablename__ = "schedule"

    id          = db.Column(db.Integer, primary_key=True)
    teacher_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), default="")
    meet_link   = db.Column(db.String(500), default="")
    scheduled_at = db.Column(db.DateTime, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled   = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Schedule #{self.id} '{self.title}' at {self.scheduled_at:%Y-%m-%d %H:%M}>"


class ScheduleJoin(db.Model):
    """Records which students have joined a scheduled class (auto-attendance)."""
    __tablename__ = "schedule_join"

    id          = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=False, index=True)
    student_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at   = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_id = db.Column(db.Integer, db.ForeignKey("attendance.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("schedule_id", "student_id", name="uq_schedule_student"),
    )


class ScheduleInvite(db.Model):
    """Maps which students are invited to a specific schedule."""
    __tablename__ = "schedule_invite"

    id          = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=False, index=True)
    student_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("schedule_id", "student_id", name="uq_schedule_invite"),
    )
