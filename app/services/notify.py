"""In-app notifications (the bell). Rows are only added to the session: the caller commits, so a
notification exists if and only if the thing it announces was saved."""
from datetime import datetime, timedelta

from .. import db
from ..models import Notification, User

KEEP_DAYS = 45      # older ones are removed the next time someone is notified, so the table stays small


def notify(user_ids, kind, title, body="", url=""):
    ids = {int(i) for i in user_ids if i}
    for uid in ids:
        db.session.add(Notification(user_id=uid, kind=kind, title=title[:200], body=(body or "")[:300], url=url[:300]))
    if ids:
        Notification.query.filter(Notification.created_at < datetime.utcnow() - timedelta(days=KEEP_DAYS)).delete(
            synchronize_session=False)


def teacher_ids():
    return [u.id for u in User.query.filter_by(role="teacher").all()]


def student_ids():
    return [u.id for u in User.query.filter(User.role == "student", User.managed_by.is_(None)).all()]


def unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, read_at=None).count()
