"""
routes/auth.py — Authentication Blueprint (login, register, logout, language).
"""
import re
import logging
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash)
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


@auth_bp.route("/lang/<code>")
def set_lang(code: str):
    if code in ("en", "zh"):
        session["lang"] = code
    return redirect(request.referrer or url_for("student.dashboard"))


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        ip    = request.remote_addr
        uname = request.form.get("username", "").strip()
        pw    = request.form.get("password", "")

        if is_rate_limited(ip):
            flash(tr("err_locked"), "err")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=uname).first()

        if not user:
            record_failed_attempt(ip)
            flash(tr("err_user"), "err")
        elif is_legacy_hash(user.password) and migrate_legacy_password(user, pw):
            # Legacy hash matched — password was upgraded in-place
            db.session.commit()
            session.permanent = True
            session["user_id"] = user.id
            clear_attempts(ip)
            logger.info("User %s logged in (legacy hash migrated)", uname)
            return redirect(url_for("student.dashboard"))
        elif not verify_password(user.password, pw):
            record_failed_attempt(ip)
            flash(tr("err_pw"), "err")
            logger.warning("Failed login for user %r from %s", uname, ip)
        else:
            session.permanent = True
            session["user_id"] = user.id
            clear_attempts(ip)
            logger.info("User %s logged in successfully", uname)
            return redirect(url_for("student.dashboard"))

    from flask import make_response
    resp = make_response(render_template("auth/login.html", quote=random_quote()))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("student.dashboard"))

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

    from ..models import Attendance, Receipt, StudentFee
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
