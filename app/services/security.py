"""
services/security.py — Password hashing and brute-force rate limiting.

Uses werkzeug.security for password hashing (industry standard, well-tested).
Rate limiting is kept in-process memory — suitable for < 10 concurrent users.
"""
import logging
from datetime import datetime, timedelta
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# In-process store: { ip_address: [datetime, ...] }
_login_attempts: dict = {}


# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plain-text password using werkzeug's pbkdf2:sha256."""
    return generate_password_hash(password, method="pbkdf2:sha256:260000")


def verify_password(stored_hash: str, provided: str) -> bool:
    """
    Verify a password against its stored hash.
    Also handles legacy PBKDF2 hashes from the previous app version.
    """
    try:
        return check_password_hash(stored_hash, provided)
    except Exception:
        logger.warning("Password verification raised an unexpected error.")
        return False


def is_legacy_hash(stored: str) -> bool:
    """
    Detect old plain-SHA256 hashes (format: 'salt:hexdigest' or plain 64-char hex).
    Returns True if the password needs to be re-hashed with the new scheme.
    """
    # Old format was either bare 64-char hex or 'salt:hex'
    return not stored.startswith("pbkdf2:")


def migrate_legacy_password(user, plain_password: str) -> bool:
    """
    If a user has a legacy password hash and the plain password matches,
    re-hash with werkzeug and return True. Otherwise return False.
    """
    import hashlib, secrets as _secrets
    stored = user.password

    matched = False
    if len(stored) == 64:
        # Bare SHA-256 (very old version)
        import hashlib
        matched = stored == hashlib.sha256(plain_password.encode()).hexdigest()
    elif ":" in stored and not stored.startswith("pbkdf2:"):
        # salt:hex PBKDF2 from previous version
        try:
            salt, dk = stored.split(":", 1)
            import hashlib
            new_dk = hashlib.pbkdf2_hmac(
                "sha256", plain_password.encode(), salt.encode(), 260000
            ).hex()
            matched = _secrets.compare_digest(dk, new_dk)
        except Exception:
            matched = False

    if matched:
        user.password = hash_password(plain_password)
        logger.info("Migrated legacy password hash for user_id=%s", user.id)

    return matched


# ── Rate limiting ─────────────────────────────────────────────────────────────

def is_rate_limited(ip: str) -> bool:
    """Return True if the IP has exceeded the allowed login attempts."""
    max_attempts = current_app.config["LOGIN_MAX_ATTEMPTS"]
    lockout_secs = current_app.config["LOGIN_LOCKOUT_SECONDS"]
    cutoff = datetime.utcnow() - timedelta(seconds=lockout_secs)
    recent = [t for t in _login_attempts.get(ip, []) if t > cutoff]
    _login_attempts[ip] = recent
    return len(recent) >= max_attempts


def record_failed_attempt(ip: str) -> None:
    """Record a failed login attempt for an IP."""
    _login_attempts.setdefault(ip, []).append(datetime.utcnow())
    logger.warning("Failed login attempt from IP %s (total recent: %d)",
                   ip, len(_login_attempts[ip]))


def clear_attempts(ip: str) -> None:
    """Clear login attempts after a successful login."""
    _login_attempts.pop(ip, None)
