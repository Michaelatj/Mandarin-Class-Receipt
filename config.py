"""
config.py — Application configuration.

For local development, defaults are used automatically.
For production, set environment variables:
    SECRET_KEY=<long-random-string>
    HTTPS=1
    FLASK_DEBUG=false
"""
import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "attendance.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {"connect_args": {"check_same_thread": False}}
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.environ.get("HTTPS", "") == "1"
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=8)
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_LOCKOUT_SECONDS: int = 300
    CLASSES_PER_CYCLE: int = 8


class DevelopmentConfig(Config):
    DEBUG: bool = True
    SESSION_COOKIE_SECURE: bool = False


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
