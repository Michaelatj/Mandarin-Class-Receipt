"""
models.py — SQLAlchemy database models.

All models live here so they are imported once and shared across
blueprints without circular imports.
"""
from datetime import datetime, timedelta
from . import db

WIB_OFFSET = timedelta(hours=7)   # Indonesia (WIB) is UTC+7, no daylight saving


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
    email        = db.Column(db.String(200), default="")
    seen_pips    = db.Column(db.String(500), default="{}")    # JSON: {tab: last_seen_count}
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    # a student added by a teacher who has no login yet (set to that teacher's id). Their
    # records are linked to a real account once they register.
    managed_by   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

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
    packet_type = db.Column(db.String(20), default="session")  # 'session' | 'monthly'
    # True = the student pays first, then has class (an unpaid prepaid receipt is issued up front)
    pay_first   = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "student_id", name="uq_teacher_student_fee"),
    )

    def __repr__(self) -> str:
        return f"<StudentFee teacher={self.teacher_id} student={self.student_id} fee={self.fee_idr} type={self.packet_type}>"


class Attendance(db.Model):
    __tablename__ = "attendance"

    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    date       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    billed     = db.Column(db.Boolean, default=False, nullable=False)
    note       = db.Column(db.String(200), default="")
    source     = db.Column(db.String(10), default="teacher")  # 'student' | 'teacher'

    def __repr__(self) -> str:
        return f"<Attendance student={self.student_id} date={self.date:%Y-%m-%d}>"


class Receipt(db.Model):
    __tablename__ = "receipt"

    id           = db.Column(db.Integer, primary_key=True)
    receipt_no   = db.Column(db.Integer, nullable=False, default=0)  # sequential per teacher
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
    paid_at      = db.Column(db.DateTime)   # when the teacher marked it paid (older receipts have none)
    packet_type  = db.Column(db.String(20), nullable=True) # Override tipe paket: 'session' atau 'monthly'
    custom_qty   = db.Column(db.Integer, nullable=True)    # Override jumlah quantity

    # 'billing' = issued after classes happened, 'prepaid' = paid up front before the classes
    kind         = db.Column(db.String(10), default="billing")
    covers       = db.Column(db.String(200), default="")   # what a prepaid receipt pays for
    method       = db.Column(db.String(30), default="")    # cash, transfer, ...
    period_start = db.Column(db.DateTime)                  # prepaid coverage starts here (UTC)
    period_end   = db.Column(db.DateTime)                  # monthly prepaid coverage ends here (UTC)

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

    # in-person classes: where it is held, and the code students type for the roll call (点名)
    mode           = db.Column(db.String(10), default="online")
    location       = db.Column(db.String(200), default="")
    rollcall_code  = db.Column(db.String(8))
    rollcall_until = db.Column(db.DateTime)

    @property
    def is_offline(self):
        return (self.mode or "online") == "offline"

    @property
    def start_utc(self):
        """When the class starts, in UTC. The teacher types the time as WIB wall-clock time and it is
        stored as typed, while attendance and every "now" in the app are UTC, so any comparison
        between a class time and a moment must go through this."""
        return self.scheduled_at - WIB_OFFSET

    def rollcall_open(self, now=None):
        now = now or datetime.utcnow()
        return bool(self.rollcall_code and self.rollcall_until and self.rollcall_until > now)

    def in_rollcall_window(self, now=None):
        """Roll call only makes sense around the class: 3 hours before to 8 hours after it starts."""
        now = now or datetime.utcnow()
        return self.is_offline and not self.cancelled \
            and self.start_utc - timedelta(hours=3) <= now <= self.start_utc + timedelta(hours=8)

    def in_attend_window(self, now=None):
        """Students can submit attendance from 3 hours before the class to 8 hours after it starts."""
        now = now or datetime.utcnow()
        return not self.cancelled \
            and self.start_utc - timedelta(hours=3) <= now <= self.start_utc + timedelta(hours=8)

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


class ScheduleAbsent(db.Model):
    """The teacher set this student as absent for a class. It overrides any attendance record,
    so the streak breaks even when the student submitted something near the class time."""
    __tablename__ = "schedule_absent"

    id          = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=False, index=True)
    student_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("schedule_id", "student_id", name="uq_schedule_absent"),
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



class Quiz(db.Model):
    """A quiz made by a teacher. Questions live in one JSON column."""
    __tablename__ = "quiz"

    id                 = db.Column(db.Integer, primary_key=True)
    teacher_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title              = db.Column(db.String(200), nullable=False)
    description        = db.Column(db.String(500), default="")
    questions          = db.Column(db.JSON, nullable=False, default=list)
    hide_pinyin        = db.Column(db.Boolean, default=False)
    time_limit_seconds = db.Column(db.Integer, default=0)       # 0 = no timer
    allow_retakes      = db.Column(db.Boolean, default=True)
    assign_all         = db.Column(db.Boolean, default=False)   # visible to every student
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)


class QuizAssign(db.Model):
    """A quiz given to one specific student."""
    __tablename__ = "quiz_assign"
    __table_args__ = (db.UniqueConstraint("quiz_id", "student_id", name="uq_quiz_assign"),)

    id          = db.Column(db.Integer, primary_key=True)
    quiz_id     = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False, index=True)
    student_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempt"

    id             = db.Column(db.Integer, primary_key=True)
    quiz_id        = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False, index=True)
    student_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    answers        = db.Column(db.JSON, nullable=False, default=dict)   # {question_id: {value, usedMeaning, answeredAtMs}}
    answer_order   = db.Column(db.JSON, nullable=False, default=list)
    accuracy_score = db.Column(db.Float)
    xp_score       = db.Column(db.Float)
    longest_streak = db.Column(db.Integer, default=0)
    title          = db.Column(db.String(50))
    started_at     = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at   = db.Column(db.DateTime)
