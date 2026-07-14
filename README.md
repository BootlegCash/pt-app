# PT Portal — private coaching & workout tracking

A mobile-responsive Django application for a personal-training practice:
**the coach/administrator prescribes and controls the plan; the client records
execution, performance, readiness, and feedback.**

- Admin-only account creation (no public registration), forced password change
  at first login, username-or-email login, DB-backed login rate limiting
- Roles: administrator, coach, athlete (a user can be both coach and athlete)
- Coach access is granted only through an **active** `CoachClientRelationship`
- Athlete pages: dashboard, profile, measurements, maxes & PRs, weekly/monthly
  calendar, current program, mobile-first workout logger with autosave,
  workout/exercise history, progress charts (Chart.js), nutrition targets,
  supplements, private file uploads, data export, self-deactivation
- Coach pages: dashboard (adherence, pain flags, PRs, pending approvals),
  client detail hub, program builder (weeks/days/exercises/supersets/copying),
  calendar management, measurement & max entry, nutrition calculator
  (Mifflin-St Jeor / Katch-McArdle + configurable macro rules + overrides +
  weight-trend recommendations), supplement assignment, progression approvals,
  Excel-import approvals, private notes
- Progressive overload: double / fixed-load / percentage / rep / RIR-RPE /
  manual / performance-based. Recommendations are **never applied silently** —
  a coach approves, modifies, or rejects each one, and applied changes are audited
- Excel (.xlsx/.csv) upload → worksheet choice → column mapping → parsed
  preview → coach approval → **draft** program (never overwrites a live program)
- PDF reference uploads with page count, stored privately
- All private files served only through authenticated views; stored filenames
  are randomized; uploads validated by extension, magic bytes, and size
- Audit trail for profile/measurement/max/program/nutrition/supplement/
  progression/relationship changes

**Stack:** Python 3.11+ · Django 5.2 · SQLite (PostgreSQL-ready via
`DATABASE_URL`) · Django templates · vanilla JS · Chart.js (vendored) ·
openpyxl · pypdf · Pillow · WhiteNoise. No Redis/Celery/Docker/paid services.

---

## Local setup

```bash
git clone <your-repo-url> pt-app && cd pt-app

# Virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt

# Environment (optional for local dev — sane defaults exist)
copy .env.example .env           # cp on macOS/Linux

# Database
python manage.py migrate

# Demo data: admin/coach/athlete users, exercise library, 4-day program,
# calendar, one logged workout, nutrition targets, supplements
python manage.py seed_demo

# Run
python manage.py runserver
```

Log in at http://127.0.0.1:8000 — demo logins are printed by `seed_demo`
(`admin`, `coach`, `athlete`; coach/athlete must change password at first login).

### Tests & checks

```bash
python manage.py test            # full suite
python manage.py check           # system checks
python manage.py check --deploy --settings=config.settings.prod
```

### Static & media files

- `python manage.py collectstatic` gathers static files into `staticfiles/`
  (WhiteNoise serves them in production; hashed + compressed).
- Public media (`media/`) is unused for anything sensitive.
- **Private uploads** live in `private_media/` (configurable via
  `PRIVATE_MEDIA_ROOT`) and are only reachable through authenticated download
  views — never map this directory to a public URL.

### Management commands

| Command | Purpose |
|---|---|
| `seed_demo [--flush-demo]` | Create demo users + sample data |
| `backup_db [--output DIR]` | Safe SQLite online backup to `backups/` |
| `cleanup_files [--apply] [--days N] [--purge-imported]` | Remove abandoned/rejected/orphaned uploads and stale previews (dry-run by default). `--purge-imported` also deletes source spreadsheets whose data is already imported |

---

## Deploying on PythonAnywhere (free tier)

1. **Create the account** at pythonanywhere.com (free "Beginner" plan; no card).
2. **Get the code** (Bash console):
   ```bash
   git clone https://github.com/YOURUSER/pt-app.git
   cd pt-app
   python3.11 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure environment**: `cp .env.example .env`, then edit:
   - `SECRET_KEY` — long random string (`python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `DEBUG=False`
   - `ALLOWED_HOSTS=YOURUSER.pythonanywhere.com`
   - `CSRF_TRUSTED_ORIGINS=https://YOURUSER.pythonanywhere.com`
4. **Initialize**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser        # or seed_demo for a demo
   ```
5. **Web app**: Web tab → *Add a new web app* → *Manual configuration* →
   Python 3.11.
   - **Virtualenv**: `/home/YOURUSER/pt-app/venv`
   - **WSGI file**: replace contents with `deploy/pythonanywhere_wsgi.py`
     (adjust `USERNAME`).
   - **Static files mapping**: URL `/static/` → directory
     `/home/YOURUSER/pt-app/staticfiles` (WhiteNoise also works without this,
     but the mapping is faster).
   - Do **not** map `/media/` or `private_media/` — private files must go
     through Django's authenticated views.
6. **Reload** the web app from the Web tab.

> **Monthly renewal note:** free PythonAnywhere web apps are disabled after
> ~3 months unless you press the **"Run until 3 months from today"** button on
> the Web tab. Set a calendar reminder — visiting the button monthly keeps the
> app alive indefinitely.

### GitHub workflow (code backup & deploys)

```bash
# local machine
git add -A && git commit -m "change" && git push origin main

# PythonAnywhere console
cd ~/pt-app && git pull
source venv/bin/activate
pip install -r requirements.txt      # if dependencies changed
python manage.py migrate             # if migrations changed
python manage.py collectstatic --noinput
# then reload from the Web tab
```

Never commit `.env`, `db.sqlite3`, `private_media/` (already in `.gitignore`).

---

## Backups

### SQLite backup

```bash
python manage.py backup_db          # writes backups/db-<timestamp>.sqlite3
```

Copy the backup **and** the `private_media/` directory somewhere off the
server (e.g. download via the PythonAnywhere Files tab). On the free tier a
simple scheduled task can run `backup_db` daily (Tasks tab).

### SQLite restore

```bash
# stop the web app first (Web tab → disable), then:
cp backups/db-YYYYmmdd-HHMMSS.sqlite3 db.sqlite3
# re-enable / reload the web app
```

---

## Migrating to PostgreSQL later

The code avoids SQLite-specific SQL and migrations are PostgreSQL-compatible.

1. Provision PostgreSQL (any host).
2. `pip install "psycopg[binary]"` (uncomment in `requirements.txt`).
3. Dump from SQLite:
   ```bash
   python manage.py dumpdata --natural-foreign --natural-primary \
       -e contenttypes -e auth.permission -e admin.logentry -e sessions \
       -o dump.json
   ```
4. Point `DATABASE_URL=postgres://user:pass@host:5432/dbname` in `.env`.
5. `python manage.py migrate && python manage.py loaddata dump.json`
6. Verify, then retire the SQLite file. Future backups: `pg_dump`.

## Migrating file storage later

All private-file access goes through `core/services/storage.py`
(`get_private_storage()`) and authenticated download views. To move to
S3-compatible storage:

1. Implement an S3 backend in `core/services/storage.py` (e.g. with
   `django-storages`), returning it when `MEDIA_STORAGE_BACKEND=s3`.
2. Copy existing files from `private_media/` to the bucket (keep paths).
3. Set `MEDIA_STORAGE_BACKEND=s3` plus bucket credentials in the environment.

Keep the bucket **private**; downloads should stay behind the authenticated
views (serve via signed URLs or streaming).

## Moving hosts / future mobile app

- All configuration is environment-based; any WSGI host works
  (`config/settings/prod.py` + `config/wsgi.py`).
- Business logic lives in service modules (`*/services/`), separate from
  views, so a future REST API (e.g. Django REST Framework) for a mobile app
  can reuse the same services and authorization helpers
  (`core/services/access.py`).
- Google Calendar export is stubbed by design: `GOOGLE_CALENDAR_ENABLED`
  stays `False` until OAuth credentials are configured; only workout name,
  date, time, duration, a short exercise summary, and a link back may ever be
  sent — never measurements, injuries, or supplement data.

---

## User data export & deletion

- **Self-service export**: Account Settings → "Download my data (JSON)"
  (excludes coach-private notes).
- **Deactivation**: Account Settings → deactivate (password-confirmed);
  an administrator can reactivate.
- **Deletion**: administrator deletes the user in Django Admin
  (`Accounts → Users`); related data cascades. Export first if the user wants
  a copy.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `DisallowedHost` | Add the exact domain to `ALLOWED_HOSTS` in `.env`, reload |
| CSRF failure on login | Add `https://yourdomain` to `CSRF_TRUSTED_ORIGINS` |
| Static files 404 in production | Run `collectstatic`; check the Web-tab static mapping |
| Login always redirects to password change | Expected for new accounts — complete the change form |
| Uploads rejected | Check size limits (`MAX_*_UPLOAD_MB`) and that the file is a real .xlsx/.csv/.pdf |
| `SECRET_KEY environment variable is required` | Production settings refuse to boot without it — set it in `.env` |
| Free app went to sleep | Web tab → "Run until 3 months from today" |
| Locked SQLite during backup | Use `manage.py backup_db` (online backup API), not `cp` |

## Project layout

```
config/            settings (base/dev/prod), urls, wsgi
accounts/          custom user, auth, middleware, provisioning
profiles/          athlete profiles, measurements
exercises/         exercise library
programs/          programs, weeks, days, prescriptions, builder, copying
calendar_app/      scheduled sessions, generation, week/month grids
workouts/          sessions, set logs, autosave, pain reports, history
progress/          lift maxes, PRs, 1RM formulas, chart data, volume
nutrition/         macro rules, calculators, targets, weight trends
supplements/       library, defaults, assignments
coaching/          relationships, coach dashboard, progression engine
imports/           Excel/PDF uploads, validation, parsing, approvals
core/              access control, audit, storage, export, dashboards,
                   management commands (seed_demo, backup_db, cleanup_files)
templates/ static/ dark athletic UI, vanilla JS (autosave, charts)
deploy/            sample PythonAnywhere WSGI file
```

## Disclaimers baked into the product

- Calorie/body-fat numbers are always labelled estimates; circumference data
  never claims exact muscle mass.
- Pain reports are flagged to the coach and never framed as diagnosis; the UI
  directs red-flag symptoms to licensed professionals.
- Supplement content is educational, conservative, and never presented as
  disease treatment.
