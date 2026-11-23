"""Erase a student account together with everything that points at it."""
from .. import db
from ..models import (Attendance, BonusAccess, HskActivity, HskGame, HskKnown, Quiz, QuizAssign, QuizAttempt, Receipt,
                      ScheduleAbsent, ScheduleInvite, ScheduleJoin, StreakEntry, StudentFee, User)


def erase_student(student):
    """Delete one student and all of their rows. Does not commit: the caller does, so a failure
    rolls everything back. Rows are removed child-first so no foreign key is left dangling."""
    sid = student.id
    for model in (QuizAttempt, QuizAssign, ScheduleJoin, ScheduleAbsent, ScheduleInvite,
                  StreakEntry, BonusAccess, Attendance, Receipt, StudentFee):
        model.query.filter_by(student_id=sid).delete(synchronize_session=False)
    for model in (HskKnown, HskActivity, HskGame):
        model.query.filter_by(user_id=sid).delete(synchronize_session=False)
    db.session.delete(student)
