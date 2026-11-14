"""
routes/hsk.py - HSK 1 study material (300 words) for enrolled students.

Only logged-in accounts that belong to the class can open it: teachers, and
students the teacher has actually enrolled (a fee set, an attendance, a receipt
or a schedule invite). Someone who just registered an account and is not part of
the class yet sees a short "ask your teacher" page. Nothing here is public.
"""
import json
import logging
from functools import lru_cache, wraps
from pathlib import Path

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   session, url_for)

from .. import db
from ..models import Attendance, Receipt, ScheduleInvite, StudentFee, User

logger = logging.getLogger(__name__)
hsk_bp = Blueprint("hsk", __name__, url_prefix="/hsk1")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "hsk1.json"

# (id, icon, label) - the order students see them in
THEMES = [
    ("sapaan",     "🙏", "Sapaan & sopan santun"),
    ("orang",      "🧑", "Kata ganti & orang"),
    ("keluarga",   "👨‍👩‍👧", "Keluarga"),
    ("angka",      "🔢", "Angka & hitungan"),
    ("waktu",      "🕒", "Waktu & tanggal"),
    ("makanan",    "🍜", "Makanan & minuman"),
    ("belanja",    "🛍️", "Belanja & uang"),
    ("tempat",     "📍", "Tempat & arah"),
    ("transport",  "🚆", "Transportasi"),
    ("sekolah",    "🎓", "Sekolah & belajar"),
    ("kerja",      "🏃", "Kata kerja sehari-hari"),
    ("sifat",      "🌡️", "Sifat & keadaan"),
    ("tanya",      "❓", "Kata tanya & penunjuk"),
    ("tatabahasa", "🧩", "Tata bahasa & partikel"),
    ("benda",      "📦", "Benda, hewan & alam"),
]
THEME_MAP = {t[0]: t for t in THEMES}


@lru_cache(maxsize=1)
def _entries():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


@hsk_bp.context_processor
def _shell_user():
    uid = session.get("user_id")
    return {"shell_user": db.session.get(User, uid) if uid else None,
            "active_nav": "hsk"}


def _home(user):
    return url_for("teacher.dashboard" if user.role == "teacher" else "student.dashboard")


def _is_enrolled(user):
    if user.role == "teacher":
        return True
    for model in (StudentFee, Attendance, Receipt, ScheduleInvite):
        if model.query.filter_by(student_id=user.id).first():
            return True
    return False


def guard(json_response=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            uid = session.get("user_id")
            user = db.session.get(User, uid) if uid else None
            if not user:
                if json_response:
                    return jsonify(ok=False, msg="login required"), 401
                return redirect(url_for("auth.login"))
            if not _is_enrolled(user):
                if json_response:
                    return jsonify(ok=False, msg="not enrolled"), 403
                return render_template("hsk/locked.html", home=_home(user)), 403
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator


def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@hsk_bp.route("/")
@guard()
def index(user):
    entries = _entries()
    themes = []
    for tid, icon, label in THEMES:
        items = [e for e in entries if e["theme"] == tid]
        themes.append({
            "id": tid, "icon": icon, "label": label, "count": len(items),
            "preview": " ".join(e["hanzi"] for e in items[:5]),
            "ns": [e["n"] for e in items],
        })
    return _no_store(app_render("hsk/index.html", user, themes=themes, total=len(entries),
                                all_ns=[e["n"] for e in entries]))


@hsk_bp.route("/<theme_id>")
@guard()
def theme(user, theme_id):
    entries = _entries()
    if theme_id == "semua":
        meta = ("semua", "📚", "Semua 300 kata")
        items = entries
    elif theme_id in THEME_MAP:
        meta = THEME_MAP[theme_id]
        items = [e for e in entries if e["theme"] == theme_id]
    else:
        abort(404)
    return _no_store(app_render("hsk/theme.html", user, theme_id=meta[0], icon=meta[1],
                                label=meta[2], items=items))


@hsk_bp.route("/data.json")
@guard(json_response=True)
def data(user):
    slim = [{"n": e["n"], "hanzi": e["hanzi"], "pinyin": e["pinyin"],
             "arti": e["arti"], "theme": e["theme"]} for e in _entries()]
    return _no_store(jsonify(slim))


def app_render(template, user, **ctx):
    from flask import make_response
    return make_response(render_template(template, home=_home(user), uid=user.id, **ctx))
