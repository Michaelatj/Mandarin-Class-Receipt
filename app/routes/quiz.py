"""
routes/quiz.py - Quiz feature (placeholder, coming soon).
"""
from flask import Blueprint, render_template, redirect, url_for, session
from .. import db
from ..models import User

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/quiz")
def coming_soon():
    user = db.session.get(User, session["user_id"]) if "user_id" in session else None
    if not user:
        return redirect(url_for("auth.login"))

    home = url_for("teacher.dashboard") if user.role == "teacher" else url_for("student.dashboard")
    return render_template("quiz/coming_soon.html", role=user.role, home=home)
