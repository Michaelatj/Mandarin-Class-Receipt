"""
config.py — Application configuration.

Local dev  : uses SQLite automatically (no setup needed)
Production : set these environment variables in Vercel dashboard:
    SECRET_KEY   = <long random string>
    DATABASE_URL = <your Neon/Supabase PostgreSQL connection string>
    HTTPS        = 1
"""
import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _db_uri():
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # Neon/Heroku use 'postgres://' but SQLAlchemy needs 'postgresql://'
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return "sqlite:///" + os.path.join(BASE_DIR, "instance", "attendance.db")


def _engine_options():
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return {"pool_pre_ping": True, "pool_recycle": 300}
    return {"connect_args": {"check_same_thread": False}}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI = _db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    LOGIN_MAX_ATTEMPTS = 10
    LOGIN_LOCKOUT_SECONDS = 300
    CLASSES_PER_CYCLE = 8


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
