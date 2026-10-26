"""
config.py — Application configuration.

Local dev  : uses SQLite automatically (no setup needed)
Production : set these environment variables in Vercel dashboard:
    SECRET_KEY   = <long random string>
    DATABASE_URL = <your Neon/Supabase PostgreSQL connection string>
"""
import os
import hashlib
import secrets
from datetime import timedelta


def _secret_key():
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    # SECRET_KEY is missing. A random key per process logs people out (and
    # makes every POST fail CSRF) whenever a serverless request lands on a
    # different instance, so derive a stable key from the database URL when
    # there is one. Set a real SECRET_KEY in the environment settings.
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        print("WARNING: SECRET_KEY is not set, using a key derived from DATABASE_URL")
        return hashlib.sha256(("class-receipt:" + db_url).encode()).hexdigest()
    return secrets.token_hex(32)  # local development only


class Config:
    SECRET_KEY = _secret_key()
    WTF_CSRF_SECRET_KEY = SECRET_KEY
    WTF_CSRF_TIME_LIMIT = None   # 1 hour token validity
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///attendance.db")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
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
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}

def _database_url():
    url = os.environ.get("DATABASE_URL", "sqlite:///attendance.db")
    # beberapa penyedia memberi awalan lama atau khusus driver, samakan ke psycopg2
    for prefix in ("postgres://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
    return url
