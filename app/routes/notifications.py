"""The notification bell: a small JSON API. The unread number is put in every page by a context
processor, and the list is only fetched when someone opens the bell."""
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from .. import db
from ..models import Notification

notif_bp = Blueprint("notif", __name__)


def _uid():
    return session.get("user_id")


@notif_bp.route("/notifications")
def listing():
    uid = _uid()
    if not uid:
        return jsonify(ok=False), 401
    rows = Notification.query.filter_by(user_id=uid).order_by(Notification.created_at.desc()).limit(30).all()
    out = [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "url": n.url,
            "at": n.created_at.isoformat() + "Z", "unread": n.read_at is None} for n in rows]
    return jsonify(ok=True, items=out)


@notif_bp.route("/notifications/read", methods=["POST"])
def mark_read():
    uid = _uid()
    if not uid:
        return jsonify(ok=False), 401
    q = Notification.query.filter_by(user_id=uid, read_at=None)
    nid = (request.get_json(silent=True) or {}).get("id")
    if nid:
        q = q.filter_by(id=int(nid))
    q.update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.session.commit()
    return jsonify(ok=True)


@notif_bp.route("/notifications/clear", methods=["POST"])
def clear():
    uid = _uid()
    if not uid:
        return jsonify(ok=False), 401
    Notification.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.commit()
    return jsonify(ok=True)
