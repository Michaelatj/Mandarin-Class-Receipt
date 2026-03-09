# 中文课堂 · Chinese Class Attendance System

A Flask web app for managing student attendance and automated tuition billing.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run locally
python run.py

# 3. Open in browser
http://localhost:5000
```

The SQLite database is created automatically at `instance/attendance.db`.

## Project Structure

```
project/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── models.py            # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py          # Login, register, logout, language
│   │   ├── student.py       # Student dashboard, mark attendance
│   │   └── teacher.py       # Teacher dashboard, fees, receipts
│   ├── services/
│   │   ├── attendance.py    # Business logic (receipt generation etc.)
│   │   ├── i18n.py          # Translations, date formatting
│   │   └── security.py      # Password hashing, rate limiting
│   ├── templates/
│   │   ├── base.html        # Shared layout
│   │   ├── auth/            # login.html, register.html
│   │   ├── student/         # dashboard.html
│   │   ├── teacher/         # dashboard.html
│   │   └── partials/        # flashes, quote, receipt_card macro
│   └── static/
│       └── css/main.css     # All styles
├── instance/
│   └── attendance.db        # SQLite DB (auto-created, gitignored)
├── config.py                # DevelopmentConfig / ProductionConfig
├── run.py                   # Entry point
└── requirements.txt
```

## Production Deployment

```bash
# Set environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export FLASK_ENV=production
export HTTPS=1

# Run with gunicorn
gunicorn "run:app" --workers 2 --bind 0.0.0.0:8000
```

### Platforms
| Platform | Command |
|---|---|
| **Railway** | Push to GitHub, set env vars in dashboard |
| **Render** | Connect repo, start command: `gunicorn "run:app"` |
| **PythonAnywhere** | Upload files, point WSGI to `run:app` |

## Migrating from the single-file version

If you have an existing `attendance.db` run the migration script first:

```bash
python migrate.py
```
