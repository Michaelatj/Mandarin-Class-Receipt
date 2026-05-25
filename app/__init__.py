import os
from flask import Flask, g, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=Config):
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)

    # Login Manager Configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # Set language before each request
    @flask_app.before_request
    def load_locale():
        if not request.path.startswith('/static'):
            lang = request.cookies.get('lang', 'en')
            if lang not in ['en', 'zh']:
                lang = 'en'
            g.lang = lang
            g.current_url = request.path

    # Context processor to make tr() available in templates
    @flask_app.context_processor
    def inject_globals():
        from app.services.i18n import tr, fmt_date, to_wib, fmt_idr
        return dict(tr=tr, fmt_date=fmt_date, to_wib=to_wib, fmt_idr=fmt_idr)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.teacher import teacher_bp
    from app.routes.schedule import schedule_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(student_bp)
    flask_app.register_blueprint(teacher_bp)
    flask_app.register_blueprint(schedule_bp)

    return flask_app
