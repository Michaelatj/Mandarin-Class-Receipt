"""
services/email_otp.py — Email OTP for forgot-password flow.

CARA SETUP EMAIL (pilih salah satu):

OPSI 1 — Edit langsung di file ini (untuk local dev):
  Ganti SMTP_USER dan SMTP_PASSWORD di bawah.

OPSI 2 — Environment variable (untuk production):
  set SMTP_USER=emailkamu@gmail.com
  set SMTP_PASS=xxxx xxxx xxxx xxxx

CARA DAPAT GMAIL APP PASSWORD (gratis):
  1. Buka myaccount.google.com → Security
  2. Aktifkan 2-Step Verification
  3. Cari "App passwords" → buat baru → pilih Mail
  4. Copy 16 karakter yang muncul → paste ke SMTP_PASSWORD
"""
import random
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════
#  EDIT DI SINI untuk local dev (tanpa env vars)
# ════════════════════════════════════════════════
_HARDCODED_USER = ""        # contoh: "emailkamu@gmail.com"
_HARDCODED_PASS = ""        # contoh: "abcd efgh ijkl mnop"
# ════════════════════════════════════════════════

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = os.environ.get("SMTP_USER", _HARDCODED_USER).strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASS", _HARDCODED_PASS).strip()
FROM_NAME     = "中文课堂"


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp_code: str, username: str) -> bool:
    """
    Send OTP email. Returns True on success, False on failure.
    If SMTP_USER is not configured, prints OTP to terminal (dev mode).
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        # Dev mode — OTP muncul di terminal, bukan dikirim via email
        print(f"\n{'='*50}")
        print(f"📧 [DEV MODE] OTP untuk {username} ({to_email}): {otp_code}")
        print(f"{'='*50}\n")
        logger.warning("DEV MODE: OTP for %s: %s", to_email, otp_code)
        return True

    subject = "中文课堂 — Kode Reset Password"
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;background:#f5f4f1;padding:32px 0;margin:0">
<div style="max-width:440px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="background:#19160f;padding:24px 28px">
    <div style="font-family:Georgia,serif;font-size:1.2rem;color:#e8c87a;font-weight:700">&#20013;&#25991;&#35838;&#22530;</div>
    <div style="font-size:.72rem;color:rgba(255,255,255,.4);margin-top:4px;letter-spacing:1.5px;text-transform:uppercase">Password Reset</div>
  </div>
  <div style="padding:28px">
    <p style="color:#4a4540;font-size:.95rem;margin:0 0 12px">Hi <strong>{username}</strong>,</p>
    <p style="color:#4a4540;font-size:.88rem;margin:0 0 20px;line-height:1.6">Kami menerima permintaan reset password. Gunakan kode di bawah &mdash; berlaku selama <strong>10 menit</strong>.</p>
    <div style="background:#fdf6e3;border:1.5px solid rgba(176,125,46,.3);border-radius:10px;padding:20px;text-align:center;margin:0 0 20px">
      <div style="font-size:2.4rem;font-weight:700;letter-spacing:12px;color:#b07d2e;font-family:monospace">{otp_code}</div>
    </div>
    <p style="color:#aaa;font-size:.78rem;margin:0">Jika kamu tidak meminta reset password, abaikan email ini.</p>
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        logger.info("OTP email sent to %s", to_email)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail auth failed — pastikan App Password benar (bukan password biasa)")
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending to %s: %s", to_email, e)
        return False
    except Exception as e:
        logger.error("Unexpected error sending OTP to %s: %s", to_email, e)
        return False
