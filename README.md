# 中文课堂 · Mandarin Class Receipt

A web app for running a private Mandarin class: students check in to each lesson, the app counts the sessions and issues a tuition receipt automatically, the teacher schedules online classes with a Meet link, and can give quizzes built from the lesson material.

It was built for a small tutoring practice where attendance and payments used to be tracked by hand. The goal is to replace that with one place that both the teacher and the students can open from a phone.

Live deployment: https://mandarin-class-receipt.vercel.app

## What it does

The app has two roles, chosen when registering: **teacher** and **student**. Each role gets its own dashboard.

### Attendance and billing

- A student marks attendance for a class with a chosen teacher. The teacher can also add, edit, or delete attendance manually.
- Each student has a tuition fee set by the teacher, with one of two packet types:
  - **Session packet**: billed after every 8 classes, total = number of classes x fee per class.
  - **Monthly packet**: a fixed fee, billed once a calendar month has passed since the first unbilled class, no matter how many classes were attended. This protects the teacher's income when classes get rescheduled often.
- When a billing condition is met, a receipt is generated with the teacher's bank details, the list of class dates, and a sequential receipt number. The teacher can also force a receipt early.
- Receipts can be edited, marked as paid, cancelled (the sessions go back to unbilled), or deleted.
- The teacher can open a per-student record page with their full attendance and receipt history.

### Schedule

- The teacher creates a class schedule with a title, description, time, and Meet link, and chooses which students are invited.
- Students see their upcoming classes. Pressing Join opens the link and marks attendance automatically.
- Schedules can be edited, cancelled, deleted, or deleted in bulk.

### Quiz

- The teacher pastes quiz JSON produced by a chatbot from the lesson material, then assigns the quiz to all students or to chosen ones.
- Supported question types: multiple choice, multiple select (checkboxes), and sentence reorder (several valid word orders are accepted).
- The teacher can edit questions and answers, set a time limit, hide pinyin, and allow or block retakes.
- Students answer one question at a time. Grading happens on the server, and correct answers are never sent to the student's browser before they answer.
- Each attempt gets an accuracy score, an XP score, a longest streak, and a title based on the result (童生 up to 状元).
- The teacher sees per-question statistics.

### Accounts and interface

- Register, log in, log out, change password, delete account. Teachers can reset a student's password.
- Login can remember the user for 30 days. The login form is a normal HTML form, so the browser's password manager can save the password and autofill it on the next visit.
- Passwords are hashed with PBKDF2-SHA256. Old hashes from earlier versions are upgraded automatically on the next login.
- Failed logins are rate limited per IP address. All forms use CSRF protection.
- The whole interface switches between English and 中文 instantly, without reloading the page.
- Light and dark theme, mobile-friendly layout with a bottom navigation bar, and times shown in WIB (UTC+7).

## Tools and technologies

| Area | What is used |
|---|---|
| Language | Python 3.11+, JavaScript (no framework), HTML, CSS |
| Web framework | Flask 3 with blueprints and an app factory |
| Database access | Flask-SQLAlchemy / SQLAlchemy 2.0 |
| Database | SQLite for local development, PostgreSQL ([Neon](https://neon.tech)) in production, through `psycopg2-binary` |
| Security | Werkzeug password hashing, Flask-WTF CSRF protection, secure session cookies |
| Templating | Jinja2 |
| Hosting | [Vercel](https://vercel.com) (Python serverless function in `api/index.py`) |
| Production server option | gunicorn |

## Project structure

```
Mandarin-Class-Receipt/
├── api/
│   └── index.py             # Vercel entry point; creates tables and adds missing columns on startup
├── app/
│   ├── __init__.py          # App factory (create_app), template helpers, blueprint registration
│   ├── config.py            # DevelopmentConfig / ProductionConfig, config_map
│   ├── models.py            # User, StudentFee, Attendance, Receipt, Schedule*, Quiz*
│   ├── routes/
│   │   ├── auth.py          # Login, register, logout, language, change/delete account
│   │   ├── student.py       # Student dashboard, mark attendance, profile
│   │   ├── teacher.py       # Teacher dashboard, fees, attendance and receipt management
│   │   ├── schedule.py      # Create / edit / cancel schedules, student join
│   │   └── quiz.py          # Quiz creation, assignment, play, grading
│   ├── services/
│   │   ├── attendance.py    # Receipt generation and billing rules
│   │   ├── quiz_logic.py    # Quiz validation, shuffling, scoring, titles
│   │   ├── security.py      # Password hashing, login rate limiting
│   │   ├── i18n.py          # English / Chinese strings, date and currency formatting
│   │   ├── i18n_live.py     # Serves the dictionary for instant language switching
│   │   ├── ui_strings.py    # Extra UI strings for live translation
│   │   └── email_otp.py     # Email OTP helper (not connected to a route yet)
│   ├── static/
│   │   ├── css/             # main.css, quiz.css
│   │   └── js/              # i18n-live.js, quiz-play.js, quiz-edit.js, quiz-teacher.js
│   └── templates/
│       ├── base.html        # Shared layout, theme toggle, toast, CSRF helper
│       ├── auth/            # login, register
│       ├── student/         # dashboard
│       ├── teacher/         # dashboard
│       ├── quiz/            # teacher and student quiz pages
│       └── partials/        # flashes, quote, receipt card, schedule cards, password toggle
├── instance/                # Local SQLite database (created automatically, not committed)
├── migrate_db.py            # One-off migration for old SQLite databases
├── migrate_packet_type.py   # One-off migration: adds packet_type to student_fee
├── run.py                   # Local entry point
├── requirements.txt
└── vercel.json
```

## Running locally

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the app
python run.py
```

Open http://localhost:5000. With no `DATABASE_URL` set, the app uses SQLite and creates `instance/attendance.db` automatically.

## Environment variables

| Variable | Needed | Purpose |
|---|---|---|
| `SECRET_KEY` | production | Signs sessions and CSRF tokens. Use a long random value, for example `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_URL` | production | PostgreSQL connection string (Neon). When missing, SQLite is used. |
| `FLASK_ENV` | optional | `development` (default) or `production` for `run.py`. |
| `HTTPS` | optional | Set to `1` to mark session cookies as secure when running outside `ProductionConfig`. |

## Deploying to Vercel

1. Push the repository to GitHub and import it in Vercel.
2. In the project settings, add `SECRET_KEY` and `DATABASE_URL` (the Neon connection string).
3. Deploy. `vercel.json` sends every request to `api/index.py`, which uses `ProductionConfig`.

On every cold start, `api/index.py` creates any missing tables and adds the `packet_type` and `custom_qty` columns to existing tables, so the production database does not need a manual migration step.

To run on another host with gunicorn instead:

```bash
export SECRET_KEY=...
export DATABASE_URL=...
export FLASK_ENV=production
gunicorn "run:app" --workers 2 --bind 0.0.0.0:8000
```

## Database migrations

- Production (PostgreSQL): handled automatically by `api/index.py` as described above.
- Local SQLite created by an older version: run `python migrate_db.py` and `python migrate_packet_type.py` once. Both can be run more than once safely.

## Known limitations

- Login rate limiting is kept in process memory. On a serverless host it is per instance and resets on a cold start, so it slows down guessing but is not a strict limit.
- Password recovery is handled by the teacher (reset a student's password). Self-service reset by email OTP is not wired up yet, although `services/email_otp.py` exists.
- There are no automated tests yet.
