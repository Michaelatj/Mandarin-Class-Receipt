"""
routes/hsk.py - HSK study material (HSK 1: 300 words, HSK 2: 200 new words) for enrolled students.

Only logged-in accounts that belong to the class can open it: teachers, and
students the teacher has actually enrolled (a fee set, an attendance, a receipt
or a schedule invite). Someone who just registered an account and is not part of
the class yet sees a short "ask your teacher" page. Nothing here is public.

URLs: /hsk1/, /hsk2/ (theme list) - /hsk<level>/<theme> - /hsk<level>/data.json
"""
import json
import logging
from functools import lru_cache, wraps
from pathlib import Path

from flask import (Blueprint, abort, jsonify, make_response, redirect,
                   render_template, session, url_for)

from .. import db
from ..models import Attendance, Receipt, ScheduleInvite, StudentFee, User

logger = logging.getLogger(__name__)
hsk_bp = Blueprint("hsk", __name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

LEVELS = {
    1: {"name": "HSK 1", "zh": "汉语水平考试一级",
        "intro": "300 words grouped by theme. Open a theme, read the explanations, then practise with flashcards."},
    2: {"name": "HSK 2", "zh": "汉语水平考试二级",
        "intro": "200 new words that continue HSK 1, grouped by theme. Example sentences only use HSK 1 and HSK 2 words."},
    3: {"name": "HSK 3", "zh": "汉语水平考试三级",
        "intro": "500 new words that continue HSK 2, grouped by theme. Example sentences only use HSK 1, 2 and 3 words."},
}

# (id, icon, label) - the order students see them in
THEMES = {
    1: [
        ("sapaan",     "🙏", "Greetings & manners"),
        ("orang",      "🧑", "Pronouns & people"),
        ("keluarga",   "👨‍👩‍👧", "Family"),
        ("angka",      "🔢", "Numbers & counting"),
        ("waktu",      "🕒", "Time & dates"),
        ("makanan",    "🍜", "Food & drink"),
        ("belanja",    "🛍️", "Shopping & money"),
        ("tempat",     "📍", "Places & directions"),
        ("transport",  "🚆", "Transport"),
        ("sekolah",    "🎓", "School & study"),
        ("kerja",      "🏃", "Everyday verbs"),
        ("sifat",      "🌡️", "Adjectives & states"),
        ("tanya",      "❓", "Question & pointing words"),
        ("tatabahasa", "🧩", "Grammar & particles"),
        ("benda",      "📦", "Things, animals & nature"),
    ],
    2: [
        ("tatabahasa", "🧩", "Particles, conjunctions & measure words"),
        ("gerak",      "🧭", "Directional verbs"),
        ("tempat",     "🚇", "Places & travel"),
        ("sekolah",    "🎓", "School & study"),
        ("orang",      "👵", "Family & people"),
        ("tubuh",      "🩺", "Body & health"),
        ("makanan",    "☕", "Food & drink"),
        ("benda",      "🎨", "Colors, objects & weather"),
        ("olahraga",   "⚽", "Sports & hobbies"),
        ("waktu",      "🕒", "Time & frequency"),
        ("kerja",      "🏃", "Everyday verbs"),
        ("sifat",      "🌡️", "Adjectives & feelings"),
    ],
    3: [
        ("tatabahasa", "🧩", "Grammar words & patterns"),
        ("kerja",      "🏃", "Everyday verbs"),
        ("sifat",      "🌡️", "Adjectives & feelings"),
        ("tempat",     "📍", "Places, travel & directions"),
        ("sekolah",    "🎓", "School & language"),
        ("kantor",     "💼", "Work, business & tech"),
        ("benda",      "🏠", "Things, clothes & home"),
        ("waktu",      "🕒", "Time & frequency"),
        ("alam",       "🌳", "Nature, weather & animals"),
        ("orang",      "🧑", "People & relationships"),
        ("hobi",       "🎨", "Hobbies, sport & arts"),
        ("tubuh",      "🫀", "Body & health"),
        ("makanan",    "🍲", "Food & cooking"),
    ],
}
LEVEL_LIST = [(lv, LEVELS[lv]["name"]) for lv in sorted(LEVELS)]


@lru_cache(maxsize=4)
def _entries(level):
    with open(DATA_DIR / f"hsk{level}.json", encoding="utf-8") as f:
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
        def wrapper(level, *args, **kwargs):
            if level not in LEVELS:
                abort(404)
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
            return fn(user, level, *args, **kwargs)
        return wrapper
    return decorator


def _page(template, user, level, back=None, **ctx):
    resp = make_response(render_template(
        template, home=back or _home(user), uid=user.id, level=level,
        level_name=LEVELS[level]["name"], levels=LEVEL_LIST, **ctx))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@hsk_bp.route("/hsk<int:level>/")
@guard()
def index(user, level):
    entries = _entries(level)
    themes = []
    for tid, icon, label in THEMES[level]:
        items = [e for e in entries if e["theme"] == tid]
        themes.append({
            "id": tid, "icon": icon, "label": label, "count": len(items),
            "preview": " ".join(e["hanzi"] for e in items[:5]),
            "ns": [e["n"] for e in items],
        })
    return _page("hsk/index.html", user, level, themes=themes, total=len(entries),
                 all_ns=[e["n"] for e in entries], level_zh=LEVELS[level]["zh"],
                 intro=LEVELS[level]["intro"])


@hsk_bp.route("/hsk<int:level>/<theme_id>")
@guard()
def theme(user, level, theme_id):
    entries = _entries(level)
    known = {t[0]: t for t in THEMES[level]}
    if theme_id == "semua":
        meta = ("semua", "📚", f"All {len(entries)} words")
        items = entries
    elif theme_id in known:
        meta = known[theme_id]
        items = [e for e in entries if e["theme"] == theme_id]
    else:
        abort(404)
    # the "back" link of this page goes to the theme list, not the dashboard
    return _page("hsk/theme.html", user, level, back=url_for("hsk.index", level=level),
                 theme_id=meta[0], icon=meta[1], label=meta[2], items=items)


@hsk_bp.route("/hsk<int:level>/data.json")
@guard(json_response=True)
def data(user, level):
    slim = [{"n": e["n"], "hanzi": e["hanzi"], "pinyin": e["pinyin"],
             "arti": e["arti"], "theme": e["theme"]} for e in _entries(level)]
    resp = jsonify(slim)
    resp.headers["Cache-Control"] = "no-store"
    return resp
