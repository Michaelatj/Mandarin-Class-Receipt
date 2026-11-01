"""
routes/auth.py — Authentication Blueprint (login, register, logout, language).
"""
import re
import logging
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, current_app, make_response)
from .. import db
from ..models import User
from ..services.security import (
    hash_password, verify_password, is_legacy_hash,
    migrate_legacy_password, is_rate_limited,
    record_failed_attempt, clear_attempts,
)
from ..services.i18n import tr, random_quote

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.+-]{3,40}$")

def _finish_login(user, ip, remember):
    # tanpa remember, cookie sesi hilang begitu browser ditutup
    session.permanent = remember
    session["user_id"] = user.id
    session["fresh_login"] = True
    clear_attempts(ip)

    endpoint = "teacher.dashboard" if user.role == "teacher" else "student.dashboard"
    # redirect (bukan JSON) supaya browser menawarkan simpan password
    return redirect(url_for(endpoint))


@auth_bp.route("/lang/<code>")
def set_lang(code: str):
    if code in ("en", "zh"):
        session["lang"] = code
    # The page switches language on its own; it only needs the choice saved.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return ("", 204)
    return redirect(request.referrer or url_for("auth.index"))


@auth_bp.route("/i18n-data.js")
def i18n_data():
    from ..services.i18n_live import data_js
    resp = make_response(data_js())
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=86400"   # the URL carries a version, so a new dictionary busts it
    return resp


@auth_bp.route("/")
def index():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user:
            return redirect(url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # kalau sudah login, langsung ke dashboard
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user:
            return redirect(url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard"))

    if request.method == "POST":
        ip       = request.remote_addr
        uname    = request.form.get("username", "").strip()
        pw       = request.form.get("password", "")
        remember = request.form.get("remember") == "1"

        if is_rate_limited(ip):
            flash(tr("err_locked"), "err")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=uname).first()

        if not user:
            record_failed_attempt(ip)
            flash(tr("err_user"), "err")
        elif is_legacy_hash(user.password) and migrate_legacy_password(user, pw):
            # hash lama cocok, password sudah di-upgrade di tempat
            db.session.commit()
            logger.info("User %s logged in (legacy hash migrated)", uname)
            return _finish_login(user, ip, remember)
        elif not verify_password(user.password, pw):
            record_failed_attempt(ip)
            flash(tr("err_pw"), "err")
            logger.warning("Failed login for user %r from %s", uname, ip)
        else:
            logger.info("User %s logged in successfully", uname)
            return _finish_login(user, ip, remember)

    resp = make_response(render_template("auth/login.html", quote=random_quote()))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # If already logged in, redirect to appropriate dashboard
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user:
            return redirect(url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard"))

    if request.method == "POST":
        uname  = request.form.get("username", "").strip()
        pw     = request.form.get("password", "").strip()
        dname  = request.form.get("display_name", "").strip()[:100]
        phone  = request.form.get("phone", "").strip()[:30]
        role   = request.form.get("role", "student")

        if not USERNAME_RE.match(uname):
            flash(tr("err_username_fmt"), "err")
            return redirect(url_for("auth.register"))
        if len(pw) < 6:
            flash(tr("pw_short"), "err")
            return redirect(url_for("auth.register"))
        if role not in ("student", "teacher"):
            role = "student"
        if User.query.filter_by(username=uname).first():
            flash(tr("err_taken"), "err")
            return redirect(url_for("auth.register"))

        db.session.add(User(
            username=uname, password=hash_password(pw),
            display_name=dname, phone=phone, role=role,
        ))
        db.session.commit()
        logger.info("New user registered: %s (%s)", uname, role)
        flash(tr("ok_created"), "ok")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    logger.info("User %s logged out", user_id)
    return redirect(url_for("auth.login"))


@auth_bp.route("/delete_account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    pw = request.form.get("confirm_password", "")
    if not verify_password(user.password, pw):
        flash(tr("err_delete_pw"), "err")
        return redirect(url_for("student.dashboard"))

    from ..models import (Attendance, Receipt, StudentFee, Schedule, ScheduleJoin,
                          ScheduleInvite, Quiz, QuizAssign, QuizAttempt)
    # Quizzes first: attempts and assignments point at both quizzes and users
    my_quiz_ids = [q.id for q in Quiz.query.filter_by(teacher_id=user.id).all()]
    if my_quiz_ids:
        QuizAttempt.query.filter(QuizAttempt.quiz_id.in_(my_quiz_ids)).delete(synchronize_session=False)
        QuizAssign.query.filter(QuizAssign.quiz_id.in_(my_quiz_ids)).delete(synchronize_session=False)
        Quiz.query.filter(Quiz.id.in_(my_quiz_ids)).delete(synchronize_session=False)
    QuizAttempt.query.filter_by(student_id=user.id).delete(synchronize_session=False)
    QuizAssign.query.filter_by(student_id=user.id).delete(synchronize_session=False)

    # Schedule rows reference attendance rows and users
    my_schedule_ids = [s.id for s in Schedule.query.filter_by(teacher_id=user.id).all()]
    if my_schedule_ids:
        ScheduleJoin.query.filter(ScheduleJoin.schedule_id.in_(my_schedule_ids)).delete(synchronize_session=False)
        ScheduleInvite.query.filter(ScheduleInvite.schedule_id.in_(my_schedule_ids)).delete(synchronize_session=False)
        Schedule.query.filter(Schedule.id.in_(my_schedule_ids)).delete(synchronize_session=False)
    ScheduleJoin.query.filter_by(student_id=user.id).delete(synchronize_session=False)
    ScheduleInvite.query.filter_by(student_id=user.id).delete(synchronize_session=False)

    # Delete all related data first (no cascade set up, so manual)
    Attendance.query.filter(
        (Attendance.student_id == user.id) | (Attendance.teacher_id == user.id)
    ).delete(synchronize_session=False)
    Receipt.query.filter(
        (Receipt.student_id == user.id) | (Receipt.teacher_id == user.id)
    ).delete(synchronize_session=False)
    StudentFee.query.filter(
        (StudentFee.student_id == user.id) | (StudentFee.teacher_id == user.id)
    ).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()

    session.clear()
    logger.info("Account deleted for user_id=%d", user.id)
    flash(tr("ok_deleted_account"), "ok")
    return redirect(url_for("auth.login"))

@auth_bp.route("/change_password", methods=["POST"])
def change_password():
    from flask import jsonify
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if not user:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(ok=False, msg="Not logged in"), 401
        return redirect(url_for("auth.login"))

    current_pw = request.form.get("current_password", "").strip()
    new_pw     = request.form.get("new_password", "").strip()
    confirm_pw = request.form.get("confirm_password", "").strip()
    is_ajax    = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not current_pw or not new_pw or not confirm_pw:
        msg = "All fields are required."
        if is_ajax: return jsonify(ok=False, msg=msg)
        flash(msg, "err"); return redirect(url_for("auth.login"))

    if not verify_password(user.password, current_pw):
        msg = "Current password is incorrect."
        if is_ajax: return jsonify(ok=False, msg=msg)
        flash(msg, "err"); return redirect(url_for("auth.login"))

    if new_pw != confirm_pw:
        msg = "New passwords do not match."
        if is_ajax: return jsonify(ok=False, msg=msg)
        flash(msg, "err"); return redirect(url_for("auth.login"))

    if len(new_pw) < 6:
        msg = "New password must be at least 6 characters."
        if is_ajax: return jsonify(ok=False, msg=msg)
        flash(msg, "err"); return redirect(url_for("auth.login"))

    user.password = hash_password(new_pw)
    db.session.commit()
    logger.info("Password changed for user_id=%d", user.id)

    msg = "Password changed successfully."
    if is_ajax: return jsonify(ok=True, msg=msg)
    flash(msg, "ok")
    redir = url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard")
    return redirect(redir)
