"""
routes/quiz.py - quizzes: teachers create and assign them, students take them.

A teacher pastes the JSON a chatbot made from the lesson material, then gives
the quiz to all students or to chosen ones. A student answers one question at
a time (each answer is checked instantly), and gets a score and a fun title.

Everything a student receives is stripped of correct answers; grading always
happens here on the server.
"""
import logging
from datetime import datetime
from functools import wraps

from flask import (Blueprint, render_template, redirect, url_for, request,
                   session, jsonify, abort)
from sqlalchemy import func

from .. import db
from ..models import User, Quiz, QuizAssign, QuizAttempt
from ..services import quiz_logic as ql

logger = logging.getLogger(__name__)
quiz_bp = Blueprint("quiz", __name__)

MAX_PAYLOAD_BYTES = 400_000
MAX_TIME_LIMIT = 7200  # seconds

# ---------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------
def _is_api():
    return request.path.startswith("/quiz/api/")


def guard(role=None):
    """Require a logged-in user (optionally with a given role)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            uid = session.get("user_id")
            user = db.session.get(User, uid) if uid else None
            if not user:
                if _is_api():
                    return jsonify(ok=False, msg="Please log in again."), 401
                return redirect(url_for("auth.login"))
            if role and user.role != role:
                if _is_api():
                    return jsonify(ok=False, msg="You are not allowed to do that."), 403
                return redirect(url_for("quiz.index"))
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator


def _home(user):
    return url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard")


def _own_quiz(user, quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.teacher_id != user.id:
        return None
    return quiz


def _visible_to(user, quiz):
    if quiz.assign_all:
        return True
    return QuizAssign.query.filter_by(quiz_id=quiz.id, student_id=user.id).first() is not None


def _not_found():
    if _is_api():
        return jsonify(ok=False, msg="Quiz not found."), 404
    abort(404)


# ---------------------------------------------------------------------
# Quiz list (teacher and student see different things)
# ---------------------------------------------------------------------
@quiz_bp.route("/quiz")
@guard()
def index(user):
    if user.role == "teacher":
        quizzes = (Quiz.query.filter_by(teacher_id=user.id)
                   .order_by(Quiz.created_at.desc()).all())
        ids = [q.id for q in quizzes]
        assigned, submitted = {}, {}
        if ids:
            assigned = dict(db.session.query(QuizAssign.quiz_id, func.count(QuizAssign.id))
                            .filter(QuizAssign.quiz_id.in_(ids)).group_by(QuizAssign.quiz_id).all())
            submitted = dict(db.session.query(QuizAttempt.quiz_id, func.count(QuizAttempt.id))
                             .filter(QuizAttempt.quiz_id.in_(ids), QuizAttempt.submitted_at.isnot(None))
                             .group_by(QuizAttempt.quiz_id).all())
        return render_template("quiz/teacher_index.html", home=_home(user),
                               quizzes=quizzes, assigned=assigned, submitted=submitted)

    assigned_ids = [a.quiz_id for a in QuizAssign.query.filter_by(student_id=user.id).all()]
    quizzes = (Quiz.query
               .filter(db.or_(Quiz.assign_all.is_(True), Quiz.id.in_(assigned_ids or [-1])))
               .order_by(Quiz.created_at.desc()).all())
    best = {}
    if quizzes:
        attempts = (QuizAttempt.query
                    .filter(QuizAttempt.student_id == user.id,
                            QuizAttempt.quiz_id.in_([q.id for q in quizzes]),
                            QuizAttempt.submitted_at.isnot(None)).all())
        for a in attempts:
            cur = best.get(a.quiz_id)
            if cur is None or (a.accuracy_score or 0, a.xp_score or 0) > (cur.accuracy_score or 0, cur.xp_score or 0):
                best[a.quiz_id] = a
    titles = {qid: ql.title_by_name(a.title) for qid, a in best.items()}
    return render_template("quiz/student_index.html", home=_home(user),
                           quizzes=quizzes, best=best, titles=titles)


# ---------------------------------------------------------------------
# Teacher: create
# ---------------------------------------------------------------------
@quiz_bp.route("/quiz/new")
@guard("teacher")
def new(user):
    return render_template("quiz/new.html", home=url_for("quiz.index"))


@quiz_bp.route("/quiz/api/create", methods=["POST"])
@guard("teacher")
def api_create(user):
    if (request.content_length or 0) > MAX_PAYLOAD_BYTES:
        return jsonify(ok=False, msg="That quiz is too large."), 413
    data = request.get_json(silent=True) or {}
    payload = data.get("quiz")
    errors = ql.validate_quiz_payload(payload)
    if errors:
        return jsonify(ok=False, msg="This quiz has problems.", details=errors[:12]), 400

    norm = ql.normalize_quiz(payload)
    quiz = Quiz(teacher_id=user.id, title=norm["title"], description=norm["description"],
                questions=norm["questions"])
    db.session.add(quiz)
    db.session.commit()
    logger.info("Quiz %s created by teacher %s (%d questions)", quiz.id, user.id, len(quiz.questions))
    return jsonify(ok=True, id=quiz.id, url=url_for("quiz.edit", quiz_id=quiz.id, new=1)), 201


# ---------------------------------------------------------------------
# Teacher: one quiz (settings, who gets it, results)
# ---------------------------------------------------------------------
@quiz_bp.route("/quiz/<int:quiz_id>")
@guard("teacher")
def detail(user, quiz_id):
    quiz = _own_quiz(user, quiz_id)
    if not quiz:
        return _not_found()

    students = User.query.filter_by(role="student").order_by(User.username).all()
    names = {s.id: s.name() for s in students}
    assigned_ids = {a.student_id for a in QuizAssign.query.filter_by(quiz_id=quiz.id).all()}

    attempts = (QuizAttempt.query.filter_by(quiz_id=quiz.id)
                .filter(QuizAttempt.submitted_at.isnot(None))
                .order_by(QuizAttempt.submitted_at.desc()).all())
    rows = [{
        "attempt": a,
        "student": names.get(a.student_id, "?"),
        "title": ql.title_by_name(a.title),
        "review": ql.build_review(quiz.questions, a.answers or {}),
    } for a in attempts]

    return render_template("quiz/detail.html", home=url_for("quiz.index"), quiz=quiz,
                           students=students, assigned_ids=assigned_ids, rows=rows)


def _question_stats(quiz):
    """How many finished attempts answered each question, and how many got it right."""
    stats = {q["id"]: {"answered": 0, "correct": 0} for q in quiz.questions}
    by_id = {q["id"]: q for q in quiz.questions}
    for a in QuizAttempt.query.filter_by(quiz_id=quiz.id).filter(QuizAttempt.submitted_at.isnot(None)).all():
        for qid, given in (a.answers or {}).items():
            if qid in by_id:
                stats[qid]["answered"] += 1
                if ql.is_answer_correct(by_id[qid], given.get("value")):
                    stats[qid]["correct"] += 1
    return stats


@quiz_bp.route("/quiz/<int:quiz_id>/edit")
@guard("teacher")
def edit(user, quiz_id):
    quiz = _own_quiz(user, quiz_id)
    if not quiz:
        return _not_found()
    submitted = (QuizAttempt.query.filter_by(quiz_id=quiz.id)
                 .filter(QuizAttempt.submitted_at.isnot(None)).count())
    return render_template("quiz/edit.html", home=url_for("quiz.detail", quiz_id=quiz.id), quiz=quiz,
                           stats=_question_stats(quiz), submitted=submitted,
                           is_new=request.args.get("new") == "1")


@quiz_bp.route("/quiz/api/<int:quiz_id>/questions", methods=["POST"])
@guard("teacher")
def api_questions(user, quiz_id):
    quiz = _own_quiz(user, quiz_id)
    if not quiz:
        return _not_found()
    if (request.content_length or 0) > MAX_PAYLOAD_BYTES:
        return jsonify(ok=False, msg="That quiz is too large."), 413
    data = request.get_json(silent=True) or {}
    questions = data.get("questions")
    errors = ql.validate_quiz_payload({"title": quiz.title, "questions": questions})
    if errors:
        return jsonify(ok=False, msg="This quiz has problems.", details=errors[:12]), 400

    norm = ql.normalize_quiz({"title": quiz.title, "questions": questions},
                             existing_ids=[q["id"] for q in quiz.questions])
    quiz.questions = norm["questions"]          # assign a new list so the JSON column is saved

    # A corrected answer key should fix everyone's score, so grade finished attempts again
    attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).filter(QuizAttempt.submitted_at.isnot(None)).all()
    for a in attempts:
        ql.regrade_attempt(a, quiz.questions, quiz.time_limit_seconds)
    db.session.commit()
    logger.info("Quiz %s edited by teacher %s (%d questions, %d results re-graded)",
                quiz.id, user.id, len(quiz.questions), len(attempts))
    return jsonify(ok=True, count=len(quiz.questions), regraded=len(attempts))


@quiz_bp.route("/quiz/api/<int:quiz_id>/update", methods=["POST"])
@guard("teacher")
def api_update(user, quiz_id):
    quiz = _own_quiz(user, quiz_id)
    if not quiz:
        return _not_found()
    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = str(data["title"]).strip()[:200]
        if not title:
            return jsonify(ok=False, msg="The title cannot be empty."), 400
        quiz.title = title
    if "hide_pinyin" in data:
        quiz.hide_pinyin = bool(data["hide_pinyin"])
    if "allow_retakes" in data:
        quiz.allow_retakes = bool(data["allow_retakes"])
    if "assign_all" in data:
        quiz.assign_all = bool(data["assign_all"])
    if "time_limit_seconds" in data:
        try:
            seconds = int(data["time_limit_seconds"])
        except (TypeError, ValueError):
            return jsonify(ok=False, msg="The time limit must be a whole number of seconds."), 400
        quiz.time_limit_seconds = max(0, min(MAX_TIME_LIMIT, seconds))

    if "student_ids" in data:
        raw = data["student_ids"] if isinstance(data["student_ids"], list) else []
        wanted = {int(x) for x in raw if str(x).isdigit()}
        valid = {u.id for u in User.query.filter(User.id.in_(wanted or [-1]), User.role == "student").all()}
        existing = {a.student_id: a for a in QuizAssign.query.filter_by(quiz_id=quiz.id).all()}
        for sid, row in existing.items():
            if sid not in valid:
                db.session.delete(row)
        for sid in valid - set(existing):
            db.session.add(QuizAssign(quiz_id=quiz.id, student_id=sid))

    db.session.commit()
    return jsonify(ok=True, msg="Saved")


@quiz_bp.route("/quiz/api/<int:quiz_id>/delete", methods=["POST"])
@guard("teacher")
def api_delete(user, quiz_id):
    quiz = _own_quiz(user, quiz_id)
    if not quiz:
        return _not_found()
    QuizAttempt.query.filter_by(quiz_id=quiz.id).delete(synchronize_session=False)
    QuizAssign.query.filter_by(quiz_id=quiz.id).delete(synchronize_session=False)
    db.session.delete(quiz)
    db.session.commit()
    return jsonify(ok=True, url=url_for("quiz.index"))


# ---------------------------------------------------------------------
# Student: take a quiz
# ---------------------------------------------------------------------
def _has_submitted(user, quiz):
    return (QuizAttempt.query.filter_by(quiz_id=quiz.id, student_id=user.id)
            .filter(QuizAttempt.submitted_at.isnot(None)).first() is not None)


@quiz_bp.route("/quiz/<int:quiz_id>/play")
@guard("student")
def play(user, quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or not _visible_to(user, quiz):
        return _not_found()
    blocked = (not quiz.allow_retakes) and _has_submitted(user, quiz)
    return render_template("quiz/play.html", home=url_for("quiz.index"), quiz=quiz,
                           question_count=len(quiz.questions), blocked=blocked)


@quiz_bp.route("/quiz/api/<int:quiz_id>/start", methods=["POST"])
@guard("student")
def api_start(user, quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or not _visible_to(user, quiz):
        return _not_found()
    if not quiz.questions:
        return jsonify(ok=False, msg="This quiz has no questions yet."), 400
    if not quiz.allow_retakes and _has_submitted(user, quiz):
        return jsonify(ok=False, msg="Retakes are turned off for this quiz."), 403

    # Reuse an unfinished attempt instead of piling up empty rows
    attempt = (QuizAttempt.query.filter_by(quiz_id=quiz.id, student_id=user.id, submitted_at=None)
               .order_by(QuizAttempt.id.desc()).first())
    if attempt:
        attempt.answers = {}
        attempt.answer_order = []
        attempt.started_at = datetime.utcnow()
    else:
        attempt = QuizAttempt(quiz_id=quiz.id, student_id=user.id, answers={}, answer_order=[])
        db.session.add(attempt)
    db.session.commit()
    return jsonify(ok=True, attemptId=attempt.id, quiz=ql.to_student_view(quiz))


def _open_attempt(user, attempt_id):
    attempt = db.session.get(QuizAttempt, attempt_id)
    if not attempt or attempt.student_id != user.id:
        return None
    return attempt


@quiz_bp.route("/quiz/api/attempt/<int:attempt_id>/answer", methods=["POST"])
@guard("student")
def api_answer(user, attempt_id):
    attempt = _open_attempt(user, attempt_id)
    if not attempt or attempt.submitted_at:
        return jsonify(ok=False, msg="This attempt is closed."), 404
    data = request.get_json(silent=True) or {}
    # read fresh every time: a teacher may have just corrected the answer key
    quiz = db.session.get(Quiz, attempt.quiz_id)
    q = next((x for x in (quiz.questions if quiz else []) if x["id"] == data.get("questionId")), None)
    if not q:
        return jsonify(ok=False, msg="Question not found."), 404
    return jsonify(ok=True, correct=ql.is_answer_correct(q, data.get("value")))


def _clean_answers(questions, raw):
    """Keep only well-formed answers for questions that really exist."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for q in questions:
        given = raw.get(q["id"])
        if not isinstance(given, dict):
            continue
        value = given.get("value")
        if q["type"] == "sentence_reorder":
            if not (isinstance(value, list) and len(value) <= ql.MAX_CHUNKS
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
                continue
        elif q["type"] == "multiple_select":
            if not (isinstance(value, list) and len(value) <= ql.MAX_OPTIONS
                    and all(isinstance(v, str) and len(v) <= ql.MAX_TEXT for v in value)):
                continue
        elif not (isinstance(value, str) and len(value) <= ql.MAX_TEXT):
            continue
        at = given.get("answeredAtMs")
        clean[q["id"]] = {
            "value": value,
            "usedMeaning": given.get("usedMeaning") is True,
            "answeredAtMs": at if isinstance(at, (int, float)) and not isinstance(at, bool) and 0 <= at < 86_400_000 else None,
        }
    return clean


def _result_payload(quiz_questions, attempt):
    title = ql.title_by_name(attempt.title) or ql.TITLES[0]
    return {
        "ok": True,
        "accuracyScore": attempt.accuracy_score,
        "xpScore": attempt.xp_score,
        "longestStreak": attempt.longest_streak,
        "title": title,
        "totalQuestions": len(quiz_questions),
        "review": ql.build_review(quiz_questions, attempt.answers or {}),
    }


@quiz_bp.route("/quiz/api/attempt/<int:attempt_id>/submit", methods=["POST"])
@guard("student")
def api_submit(user, attempt_id):
    attempt = _open_attempt(user, attempt_id)
    if not attempt:
        return jsonify(ok=False, msg="Attempt not found."), 404
    quiz = db.session.get(Quiz, attempt.quiz_id)
    if not quiz:
        return jsonify(ok=False, msg="Quiz not found."), 404

    # A double submit (timer + button) just returns the saved result
    if attempt.submitted_at:
        return jsonify(_result_payload(quiz.questions, attempt))

    data = request.get_json(silent=True) or {}
    answers = _clean_answers(quiz.questions, data.get("answers"))
    known = {q["id"] for q in quiz.questions}
    order = []
    for qid in (data.get("answerOrder") if isinstance(data.get("answerOrder"), list) else []):
        if qid in known and qid in answers and qid not in order:
            order.append(qid)
    for q in quiz.questions:          # anything answered but not listed
        if q["id"] in answers and q["id"] not in order:
            order.append(q["id"])

    scored = ql.recompute_score(answers, order, quiz.questions, quiz.time_limit_seconds)
    title = ql.compute_title(scored["accuracy"], scored["longest_streak"], len(quiz.questions))

    attempt.answers = answers
    attempt.answer_order = order
    attempt.accuracy_score = scored["accuracy"]
    attempt.xp_score = scored["xp"]
    attempt.longest_streak = scored["longest_streak"]
    attempt.title = title["name"]
    attempt.submitted_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_result_payload(quiz.questions, attempt))
