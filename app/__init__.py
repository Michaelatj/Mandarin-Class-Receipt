import os
from flask import Flask, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from .services.i18n import get_lang, get_translations

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=None):
    flask_app = Flask(__name__)

    # Load configuration
    if config_class is None:
        from .config import DevelopmentConfig
        config_class = DevelopmentConfig
    
    flask_app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)

    # Login Manager Setup
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    # Language Context Processor
    @flask_app.before_request
    def load_language():
        lang = request.cookies.get('lang', 'en')
        g.lang = lang
        g.translations = get_translations(lang)

	@flask_app.context_processor
    def inject_globals():
        from datetime import datetime, timedelta  # Added timedelta here!
        from flask import session                 # Added session here!
        from .services.i18n import random_quote, to_wib
        return {
            'lang': getattr(g, 'lang', 'en'),
            'get_lang': get_lang,
            'tr': lambda key, default=None: get_translations(getattr(g, 'lang', 'en')).get(key, default or key),
            'fmt_date': lambda dt: __import__('app.services.i18n', fromlist=['fmt_date']).fmt_date(dt),
            'fmt_idr': lambda amt: __import__('app.services.i18n', fromlist=['fmt_idr']).fmt_idr(amt),
            'to_wib': lambda dt: to_wib(dt),
            'now_dt': lambda: datetime.now(),
            'random_quote': random_quote,
            'parse_raw_dates': lambda dates: __import__('app.services.i18n', fromlist=['parse_raw_dates']).parse_raw_dates(dates),
            
            # 👇 Your brand new timezone calculator! 👇
            'local_dt': lambda dt: dt - timedelta(minutes=session.get('tz_offset', -420)),
        }

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.student import student_bp
    from .routes.teacher import teacher_bp
    from .routes.schedule import schedule_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(student_bp)
    flask_app.register_blueprint(teacher_bp)
    flask_app.register_blueprint(schedule_bp)

    return flask_app
