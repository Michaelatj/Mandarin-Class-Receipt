"""
routes/hsk.py - HSK study material (HSK 1: 300 words, HSK 2: 200 new words) for enrolled students.

Bonus Courses. Teachers can open every level; a student only the levels the teacher
unlocked for them (table bonus_access, set from the Students tab). Everything else
shows a lock page. Nothing here is public.

URLs: /bonus/ (start page) - /hsk1/, /hsk2/, /hsk3/ (theme list) - /hsk<level>/<theme> - /hsk<level>/data.json
"""
import json
import logging
from functools import lru_cache, wraps
from pathlib import Path

from flask import (Blueprint, abort, jsonify, make_response, redirect, request,
                   render_template, session, url_for)

from .. import db
from datetime import datetime

from ..models import BonusAccess, HskActivity, HskGame, HskKnown, User

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
def _riddles(level):
    """Hand-written Indonesian riddles (hanzi -> riddle). Only some levels have them."""
    try:
        with open(DATA_DIR / f"riddles{level}.json", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


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


def _allowed_levels(user):
    """Levels this account may open: a teacher all of them, a student only what the teacher unlocked."""
    if user.role == "teacher":
        return set(LEVELS)
    return {a.level for a in BonusAccess.query.filter_by(student_id=user.id).all()} & set(LEVELS)


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
            if level not in _allowed_levels(user):
                if json_response:
                    return jsonify(ok=False, msg="not unlocked"), 403
                return render_template("hsk/locked.html", home=url_for("hsk.lobby"),
                                       level_name=LEVELS[level]["name"]), 403
            return fn(user, level, *args, **kwargs)
        return wrapper
    return decorator


@hsk_bp.route("/bonus/")
def lobby():
    """Bonus Courses start page: every level, unlocked ones open, the others show a lock."""
    uid = session.get("user_id")
    user = db.session.get(User, uid) if uid else None
    if not user:
        return redirect(url_for("auth.login"))
    allowed = _allowed_levels(user)
    cards = [{"level": lv, "name": LEVELS[lv]["name"], "zh": LEVELS[lv]["zh"], "intro": LEVELS[lv]["intro"],
              "open": lv in allowed, "words": len(_entries(lv))} for lv in sorted(LEVELS)]
    resp = make_response(render_template("hsk/lobby.html", home=_home(user), cards=cards,
                                         any_open=bool(allowed)))
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _page(template, user, level, back=None, **ctx):
    resp = make_response(render_template(
        template, home=back or _home(user), uid=user.id, level=level,
        level_name=LEVELS[level]["name"], levels=LEVEL_LIST, allowed=_allowed_levels(user), **ctx))
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
    return _page("hsk/index.html", user, level, back=url_for("hsk.lobby"), themes=themes, total=len(entries),
                 all_ns=[e["n"] for e in entries], level_zh=LEVELS[level]["zh"],
                 intro=LEVELS[level]["intro"])


@hsk_bp.route("/hsk<int:level>/flashcards")
@guard()
def flashcards(user, level):
    """Flashcards for every word of the level (the level page only has a button to this page)."""
    return _page("hsk/flashcards.html", user, level, back=url_for("hsk.index", level=level), items=_entries(level))


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


@hsk_bp.route("/hsk<int:level>/progress", methods=["GET", "POST"])
@guard(json_response=True)
def progress(user, level):
    """The words this account marked as mastered, kept on the server so they follow the student
    to another phone and the teacher can see them.
    GET  -> {known: [n, ...]}
    POST -> {items: [{n, known}, ...]}  (max 400 per call); every item counts as one practice answer."""
    if request.method == "GET":
        rows = HskKnown.query.filter_by(user_id=user.id, level=level).all()
        resp = jsonify(ok=True, known=sorted(r.n for r in rows))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    body = request.get_json(silent=True) or {}
    items = body.get("items")
    total = len(_entries(level))
    if not isinstance(items, list) or not items or len(items) > 400:
        return jsonify(ok=False, msg="bad request"), 400
    wanted = {}
    for it in items:
        n, k = (it.get("n"), it.get("known")) if isinstance(it, dict) else (None, None)
        if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= total and isinstance(k, bool):
            wanted[n] = k
    if not wanted:
        return jsonify(ok=False, msg="bad request"), 400
    have = {r.n: r for r in HskKnown.query.filter(HskKnown.user_id == user.id, HskKnown.level == level,
                                                  HskKnown.n.in_(list(wanted))).all()}
    now = datetime.utcnow()
    for n, k in wanted.items():
        row = have.get(n)
        if k and not row:
            db.session.add(HskKnown(user_id=user.id, level=level, n=n, updated_at=now))
        elif not k and row:
            db.session.delete(row)
    act = HskActivity.query.filter_by(user_id=user.id, level=level).first()
    if not act:
        act = HskActivity(user_id=user.id, level=level, reviews=0)
        db.session.add(act)
    act.reviews = (act.reviews or 0) + len(wanted)
    act.last_at = now
    try:
        db.session.commit()
    except Exception:                      # two taps at once can race on the unique key
        db.session.rollback()
        logger.exception("hsk progress save failed")
        return jsonify(ok=False, msg="could not save"), 500
    return jsonify(ok=True)


GAMES = ("memory", "speed", "ladder", "match", "fill", "riddle", "race", "story")


@hsk_bp.route("/hsk<int:level>/games")
@guard()
def games(user, level):
    entries = _entries(level)
    themes = [{"id": tid, "icon": icon, "label": label,
               "count": sum(1 for e in entries if e["theme"] == tid)} for tid, icon, label in THEMES[level]]
    best = {g.game: {"best": g.best or 0, "plays": g.plays or 0}
            for g in HskGame.query.filter_by(user_id=user.id, level=level).all()}
    from .schedule import streak_view
    badge = streak_view(user.id) if user.role == "student" else None
    return _page("hsk/games.html", user, level, back=url_for("hsk.index", level=level), themes=themes,
                 total=len(entries), best=best, badge_key=(badge or {}).get("key", "gold"))


@hsk_bp.route("/hsk<int:level>/leaderboard/<game>")
@guard(json_response=True)
def leaderboard(user, level, game):
    """Top 10 best scores of one game in one level, students only (the teacher is not ranked)."""
    if game not in GAMES:
        return jsonify(ok=False, msg="bad request"), 400
    rows = (db.session.query(HskGame.best, HskGame.plays, User)
            .join(User, User.id == HskGame.user_id)
            .filter(HskGame.level == level, HskGame.game == game, HskGame.best > 0, User.role == "student")
            .order_by(HskGame.best.desc(), HskGame.last_at.asc()).limit(10).all())
    return jsonify(ok=True, rows=[{"name": u.name(), "best": b, "plays": p, "me": u.id == user.id} for b, p, u in rows])


@hsk_bp.route("/hsk<int:level>/game_score", methods=["POST"])
@guard(json_response=True)
def game_score(user, level):
    """Save a finished game. Only the best score is kept, plus how many times it was played."""
    body = request.get_json(silent=True) or {}
    game, score = body.get("game"), body.get("score")
    if game not in GAMES or not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5000:
        return jsonify(ok=False, msg="bad request"), 400
    row = HskGame.query.filter_by(user_id=user.id, level=level, game=game).first()
    if not row:
        row = HskGame(user_id=user.id, level=level, game=game, best=0, plays=0)
        db.session.add(row)
    record = score > (row.best or 0)
    if record:
        row.best = score
    row.plays = (row.plays or 0) + 1
    row.last_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("hsk game score failed")
        return jsonify(ok=False, msg="could not save"), 500
    return jsonify(ok=True, best=row.best, record=record, plays=row.plays)


@hsk_bp.route("/hsk<int:level>/data.json")
@guard(json_response=True)
def data(user, level):
    slim = [{"n": e["n"], "hanzi": e["hanzi"], "pinyin": e["pinyin"],
             "arti": e["arti"], "theme": e["theme"], "parts": e.get("parts", ""), "trick": e.get("trick", ""),
             "sentence": e.get("sentence") or [], "riddle": _riddles(level).get(e["hanzi"], "")}
            for e in _entries(level)]
    resp = jsonify(slim)
    resp.headers["Cache-Control"] = "private, max-age=3600"  # the word list never changes between deploys: the browser reuses it, no server call
    return resp
