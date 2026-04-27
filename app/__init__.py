"""
app/__init__.py — Application factory.
"""
import logging
import os
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import config_map

logger = logging.getLogger(__name__)

db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(config_name=None):
    
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    flask_app = Flask(__name__, instance_relative_config=True)

    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    cfg = config_map.get(config_name, config_map["default"])
    flask_app.config.from_object(cfg)

    # ── Set database URI at runtime (AFTER env vars are available) ──
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        # Neon/Heroku use 'postgres://' but SQLAlchemy needs 'postgresql://'
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        flask_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    else:
        # Local dev: use SQLite
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
            "sqlite:///" + os.path.join(base_dir, "instance", "attendance.db")
        )
        flask_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False}
        }
        try:
            os.makedirs(flask_app.instance_path, exist_ok=True)
        except OSError:
            pass

    db.init_app(flask_app)
    csrf.init_app(flask_app)
    # Accept CSRF token from header (for AJAX requests that can't easily use form fields)
    flask_app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken']

    _configure_logging(flask_app)

    # Import blueprints AFTER app initialization (avoids circular imports)
    from .routes.auth import auth_bp
    from .routes.student import student_bp
    from .routes.teacher import teacher_bp
    from .routes.schedule import schedule_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(student_bp)
    flask_app.register_blueprint(teacher_bp)
    flask_app.register_blueprint(schedule_bp)

    _register_template_globals(flask_app)

    with flask_app.app_context():
        from . import models  # noqa
        db.create_all()
        _auto_migrate(flask_app)

    logger.info("App started in %s mode.", config_name)
    return flask_app


def _auto_migrate(flask_app):
    """
    Safely add any missing columns to existing tables.
    Works with both SQLite (local) and PostgreSQL (production).
    """
    db_url = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")

    migrations = [
        # (table, column, sql_type_and_default)
        ("user",       "email",      "VARCHAR(200) DEFAULT ''"),
        ("user",       "seen_pips",  "VARCHAR(500) DEFAULT '{}'"),
        ("attendance", "source",     "VARCHAR(10)  DEFAULT 'teacher'"),
        ("receipt",    "receipt_no", "INTEGER DEFAULT 0"),
    ]

    try:
        if db_url.startswith("sqlite:///"):
            # ── SQLite ──
            import sqlite3 as _sql
            db_path = db_url.replace("sqlite:///", "")
            conn = _sql.connect(db_path)
            cur  = conn.cursor()
            for table, col, defn in migrations:
                cur.execute(f"PRAGMA table_info({table})")
                existing = {row[1] for row in cur.fetchall()}
                if col not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
                    logger.info("Auto-migration: added column '%s' to '%s'", col, table)
            conn.commit()
            conn.close()

        elif db_url.startswith("postgresql"):
            # ── PostgreSQL ──
            from sqlalchemy import text
            with db.engine.connect() as conn:
                for table, col, defn in migrations:
                    result = conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t AND column_name=:c"
                    ), {"t": table, "c": col})
                    if result.fetchone() is None:
                        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {col} {defn}'))
                        logger.info("Auto-migration: added column '%s' to '%s'", col, table)
                conn.commit()

    except Exception as e:
        logger.warning("Auto-migration warning: %s", e)


def _configure_logging(flask_app):
    level = logging.DEBUG if flask_app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not flask_app.config.get("DEBUG"):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _register_template_globals(flask_app):
    from .services.i18n import tr, fmt_date, fmt_idr, get_lang, parse_raw_dates, random_quote, to_wib
    from datetime import timedelta as _td

    def now_dt():
        return datetime.utcnow()

    def local_dt(utc_dt):
        """Convert UTC to WIB (UTC+7) for display in templates."""
        return to_wib(utc_dt)

    flask_app.jinja_env.globals.update(
        tr=tr,
        fmt_date=fmt_date,
        fmt_idr=fmt_idr,
        get_lang=get_lang,
        parse_raw_dates=parse_raw_dates,
        now_dt=now_dt,
        local_dt=local_dt,
        to_wib=to_wib,
        random_quote=random_quote,
    )