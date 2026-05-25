import os
import secrets
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    WTF_CSRF_SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    WTF_CSRF_TIME_LIMIT = 3600
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///attendance.db")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # test connection before use, discard if stale
        "pool_recycle": 300,         # recycle every 5 min
        "pool_size": 5,
        "max_overflow": 2,
        "connect_args": {
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    LOGIN_MAX_ATTEMPTS = 10
    LOGIN_LOCKOUT_SECONDS = 300
    CLASSES_PER_CYCLE = 8
