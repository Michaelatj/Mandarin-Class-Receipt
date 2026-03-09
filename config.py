"""
config.py — Application configuration.

Local dev  : uses SQLite automatically (no setup needed)
Production : set these environment variables in Vercel dashboard:
    SECRET_KEY   = <long random string>
    DATABASE_URL = <your Neon/Supabase PostgreSQL connection string>
"""
import os
import secrets
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
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
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}
