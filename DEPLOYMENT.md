# EduManage SaaS — Installation & Production Deployment Guide

This document covers local setup, production configuration, backups, scheduled
jobs, Razorpay, DNS, and step-by-step instructions for a Linux VPS and
PythonAnywhere.

> **Important:** This guide prepares the project for deployment. It is **not**
> evidence that the application has been deployed. You must perform the
> verification steps in §14 on your own host and confirm them before going live.

---

## Table of contents

1. [Architecture and settings modules](#1-architecture-and-settings-modules)
2. [Prerequisites](#2-prerequisites)
3. [Local installation (Windows)](#3-local-installation-windows)
4. [Local installation (macOS / Linux)](#4-local-installation-macos--linux)
5. [Environment variable reference](#5-environment-variable-reference)
6. [Database setup and migrations](#6-database-setup-and-migrations)
7. [Creating the Super Admin](#7-creating-the-super-admin)
8. [Static files](#8-static-files)
9. [Media storage and access control](#9-media-storage-and-access-control)
10. [Logging and error reporting](#10-logging-and-error-reporting)
11. [Email backend](#11-email-backend)
12. [HTTPS, cookies, hosts and CSRF](#12-https-cookies-hosts-and-csrf)
13. [MySQL in production](#13-mysql-in-production)
14. [Production deployment — Linux VPS](#14-production-deployment--linux-vps)
15. [Production deployment — PythonAnywhere](#15-production-deployment--pythonanywhere)
16. [Domain and DNS](#16-domain-and-dns)
17. [Database backup and restore](#17-database-backup-and-restore)
18. [Razorpay configuration](#18-razorpay-configuration)
19. [Subscription scheduled jobs](#19-subscription-scheduled-jobs)
20. [Deployment verification checklist](#20-deployment-verification-checklist)
21. [Troubleshooting and rollback](#21-troubleshooting-and-rollback)

---

## 1. Architecture and settings modules

| Module | Purpose |
| --- | --- |
| `CoachingApp/settings/base.py` | Shared settings, apps, middleware, auth, static/media paths, email, logging. |
| `CoachingApp/settings/development.py` | `DEBUG=True`, SQLite, localhost hosts, console email. Default for `manage.py`. |
| `CoachingApp/settings/production.py` | `DEBUG=False`, MySQL, HTTPS, secure cookies, live Razorpay, production logging. Default for `wsgi.py`/`asgi.py`. |
| `CoachingApp/checks.py` | Extra `check --deploy` rules for production configuration. |

`manage.py` defaults to **development** so local commands are convenient.
`wsgi.py` and `asgi.py` default to **production** so an application server can
never silently start with `DEBUG=True`. Always set
`DJANGO_SETTINGS_MODULE=CoachingApp.settings.production` explicitly in your
process manager as well.

---

## 2. Prerequisites

| Component | Development | Production |
| --- | --- | --- |
| Python | 3.11+ (3.12/3.13 recommended) | 3.11+ |
| Database | SQLite (included) | MySQL 8.0+ |
| Web server | Django dev server | Nginx (or Apache) + Gunicorn |
| TLS | Not required | Required (Let's Encrypt or commercial CA) |
| Email | Console backend | SMTP account |
| Payments | Razorpay test keys | Razorpay live keys + webhook |
| Scheduler | Manual | cron or systemd timer |
| Client tools | — | `mysqldump`, `mysql` for backups |

Installed Python packages are listed in `requirements.txt` (Django 6.1,
django-environ, PyMySQL, Pillow, Gunicorn, Razorpay).

---

## 3. Local installation (Windows)

### 3.1 Clone / open the project

```powershell
cd C:\Users\You\Projects
# If using git: git clone <repository-url> CoachingApp
cd CoachingApp
```

### 3.2 Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternative (Command Prompt):

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

Your prompt should show `(.venv)`. Deactivate with `deactivate`.

### 3.3 Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3.4 Configure the environment

```powershell
copy .env.example .env
notepad .env
```

For local development set at least:

```ini
DEBUG=True
SECRET_KEY=<a long random key>
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
DATABASE_URL=
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
RAZORPAY_SANDBOX=True
```

Generate a key with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`.env` is git-ignored. Never commit it.

### 3.5 Migrate and create the Super Admin

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py check
```

### 3.6 Start the development server

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The Super Admin console is at
<http://127.0.0.1:8000/superadmin/>.

### 3.7 Windows scheduled job (subscription monitor)

Use Task Scheduler → *Create Basic Task*:

- **Program:** `C:\Users\You\Projects\CoachingApp\.venv\Scripts\python.exe`
- **Arguments:** `manage.py monitor_subscriptions`
- **Start in:** `C:\Users\You\Projects\CoachingApp`
- **Trigger:** Daily

Or register it with PowerShell (run as Administrator, adjust paths):

```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\You\Projects\CoachingApp\.venv\Scripts\python.exe" -Argument "manage.py monitor_subscriptions" -WorkingDirectory "C:\Users\You\Projects\CoachingApp"
$trigger = New-ScheduledTaskTrigger -Daily -At "01:15"
Register-ScheduledTask -TaskName "EduManageSubscriptionMonitor" -Action $action -Trigger $trigger
```

---

## 4. Local installation (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp .env.example .env
nano .env

python manage.py migrate
python manage.py createsuperuser
python manage.py check
python manage.py runserver
```

---

## 5. Environment variable reference

| Variable | Required | Purpose |
| --- | --- | --- |
| `DEBUG` | No | `False` in production; dev settings force `True`. |
| `SECRET_KEY` | **Yes** | Django signing key. ≥50 random characters, unique per install. |
| `ALLOWED_HOSTS` | **Yes** | Comma-separated hostnames, e.g. `app.example.com`. No wildcards. |
| `CSRF_TRUSTED_ORIGINS` | Recommended | `https://app.example.com` (include scheme). |
| `DATABASE_URL` | **Yes (prod)** | `mysql://user:pass@host:3306/edumanage`. Empty → SQLite locally. |
| `DATABASE_SSL_CA` | No | CA certificate path for MySQL TLS. |
| `STATIC_ROOT` | No | Where `collectstatic` writes. |
| `MEDIA_ROOT` | No | Where uploads are stored. Keep outside the web root. |
| `LOG_DIR` | No | Directory for `django.log` and `errors.log`. |
| `BACKUP_DIR` | No | Default directory for `backup_database`. |
| `EMAIL_BACKEND` | **Yes (prod)** | Must be a real SMTP backend in production. |
| `EMAIL_HOST` / `EMAIL_PORT` | **Yes (prod)** | SMTP server and port (usually 587). |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | **Yes (prod)** | SMTP credentials. |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | No | TLS on 587 (default) or SSL on 465. |
| `DEFAULT_FROM_EMAIL` / `SERVER_EMAIL` | Recommended | Sender and error sender addresses. |
| `ADMIN_EMAIL` | Recommended | Receives 500-error emails. |
| `RAZORPAY_KEY_ID` | **Yes (prod)** | Live key ID (`rzp_live_...`). |
| `RAZORPAY_KEY_SECRET` | **Yes (prod)** | Live key secret (server only). |
| `RAZORPAY_WEBHOOK_SECRET` | **Yes (prod)** | Distinct webhook signing secret. |
| `RAZORPAY_SANDBOX` | **Yes (prod)** | Must be `False` with live keys. |
| `RAZORPAY_CURRENCY` | No | `INR` by default. |
| `SECURE_SSL_REDIRECT` | No | `True` by default in production. |
| `SECURE_HSTS_SECONDS` | No | `31536000` by default. |
| `TRUST_X_FORWARDED_PROTO` | No | `True` only behind a proxy that **overwrites** this header. |
| `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN` | No | Set for shared parent domains. |

Protect these values: use a root-readable env file (Linux: `chmod 600`), a
secret manager, or the host's environment dashboard. Never put credentials in
source code, templates, JavaScript, or the repository.

---

## 6. Database setup and migrations

**Development:** leave `DATABASE_URL` empty. SQLite file: `db.sqlite3`.

**Production (MySQL):**

```sql
CREATE DATABASE edumanage CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'edumanage'@'localhost' IDENTIFIED BY 'use-a-long-random-password';
GRANT ALL PRIVILEGES ON edumanage.* TO 'edumanage'@'localhost';
FLUSH PRIVILEGES;
```

For a remote DB host, use `'edumanage'@'<app-host-ip>'` and enable TLS via
`DATABASE_SSL_CA`.

```ini
DATABASE_URL=mysql://edumanage:use-a-long-random-password@127.0.0.1:3306/edumanage
```

Apply migrations (run as the deployment user):

```bash
export DJANGO_SETTINGS_MODULE=CoachingApp.settings.production
python manage.py migrate
python manage.py makemigrations --check --dry-run
python manage.py check --deploy
```

Migrations are additive and preserve tenant data. Never delete migration files
or run `migrate --fake` without a verified backup.

---

## 7. Creating the Super Admin

```bash
python manage.py createsuperuser
# Email: ops@example.com
# Password: (use a long, unique password)
```

The custom user model logs in with email only. `create_superuser` assigns the
`super_admin` role automatically. After signing in, create subscription plans
and approve the first institute from the Super Admin console.

For a second Super Admin, use Django admin at `/admin/` or the console's user
management screen. Never share the Super Admin account.

---

## 8. Static files

Source files live in `static/`; `collectstatic` copies them to `STATIC_ROOT`
(default `staticfiles/`):

```bash
python manage.py collectstatic --noinput
```

Serve `/static/` from the web server (see `deploy/nginx-edumanage.conf.example`).
Bootstrap 5, Font Awesome and Chart.js are loaded from CDN in the base
templates, so those assets require outbound internet access from the browser.

`STATICFILES_DIRS` must not overlap `STATIC_ROOT`.

---

## 9. Media storage and access control

Uploads (payment proofs, study material, assignment submissions, photos,
generated reports) are written to `MEDIA_ROOT` (default `media/`).

**Django serves media only when `DEBUG=True`.** In production:

1. Mount `MEDIA_ROOT` on a durable volume outside the web root, e.g.
   `/var/lib/edumanage/media`.
2. Deny direct HTTP access to `/media/` in the web server (the Nginx example
   contains `location /media/ { deny all; }`).
3. Let the application read files through its authenticated views
   (`core:secure_download` and the study-material/assignment endpoints), which
   re-check tenant, role, batch membership and object ownership on every read.

If you use object storage (S3-compatible), configure `STORAGES["default"]` in a
small environment-specific settings module and keep the same view-level
authorization. Never grant public bucket read access to uploaded files.

`DATA_UPLOAD_MAX_MEMORY_SIZE` and `FILE_UPLOAD_MAX_MEMORY_SIZE` are 26 MB;
module-specific validators are stricter. Keep `client_max_body_size` in Nginx
at or above 26 MB.

---

## 10. Logging and error reporting

Logs are written to `LOG_DIR` (default `logs/`):

- `django.log` — general application/django messages, rotated at 5 MB × 5.
- `errors.log` — 4xx/5xx request errors, rotated at 5 MB × 5.
- Gunicorn access/error logs are configured in the systemd example.

Production lowers console verbosity to `WARNING` but keeps `errors.log` at
`ERROR`. Setting `ADMIN_EMAIL` adds Django's `AdminEmailHandler` to
`django.request`, so 500 errors are emailed as well. Ensure SMTP is configured
before enabling this, and restrict log directory permissions:

```bash
sudo chmod 750 /var/log/edumanage
sudo chown edumanage:www-data /var/log/edumanage
```

Logs may contain IPs and usernames but not passwords — audit descriptions are
passed through `redact_sensitive()`.

---

## 11. Email backend

Development uses the console backend. Production defaults to SMTP:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=edumanage@example.com
EMAIL_HOST_PASSWORD=<smtp-password>
DEFAULT_FROM_EMAIL=EduManage <no-reply@example.com>
SERVER_EMAIL=no-reply@example.com
ADMIN_EMAIL=ops@example.com
```

For port 465 set `EMAIL_USE_TLS=False` and `EMAIL_USE_SSL=True`. Subscription
expiry reminders and password-reset links depend on working email
configuration; the production deploy check rejects console/dummy backends.

---

## 12. HTTPS, cookies, hosts and CSRF

Production settings enforce:

- `DEBUG=False`
- `SECURE_SSL_REDIRECT=True`
- `SECURE_HSTS_SECONDS=31536000`, include subdomains, preload
- `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
- `SESSION_COOKIE_HTTPONLY=True`, `SameSite=Lax`
- `SECURE_CONTENT_TYPE_NOSNIFF=True`, `SECURE_REFERRER_POLICY=same-origin`
- `X_FRAME_OPTIONS=DENY`
- `SECURE_PROXY_SSL_HEADER` from `X-Forwarded-Proto` (enable only behind a
  trusted proxy that **overwrites** the header)

Configure:

```ini
ALLOWED_HOSTS=app.example.com,www.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com,https://www.example.com
```

`check --deploy` fails if hosts are missing/wildcarded, cookies are not Secure,
SSL redirect is off, or secrets/payment credentials are unsafe.

For CI or local checks on a machine with no MySQL server, set
`EDUMANAGE_SKIP_DB_ENGINE_CHECK=1` to downgrade the MySQL-engine check to a
warning. **Never set this variable on the production host** — the production
check must confirm the MySQL engine normally.

---

## 13. MySQL in production

- Use MySQL 8.0+ with `utf8mb4`.
- Create a dedicated database and user with only the privileges the app needs.
- Never use `root` in `DATABASE_URL`.
- Enable TLS for remote connections (`DATABASE_SSL_CA`).
- Keep `DATABASE_URL` out of shell history where possible (use an env file or
  secret manager with mode `600`).
- Install `mysqldump`/`mysql` client tools for the backup commands.

PyMySQL is included in `requirements.txt` and installed as `MySQLdb`; if
`mysqlclient` is present it is used instead.

---

## 14. Production deployment — Linux VPS

The following is a reference procedure for Ubuntu 22.04/24.04. Adjust package
manager commands for your distribution.

### 14.1 Prepare the host

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential nginx mysql-client certbot python3-certbot-nginx
sudo adduser --system --group --home /srv/edumanage edumanage
sudo mkdir -p /srv/edumanage /var/log/edumanage /var/backups/edumanage /var/lib/edumanage/media
sudo chown -R edumanage:www-data /srv/edumanage /var/log/edumanage /var/backups/edumanage /var/lib/edumanage/media
```

Set up MySQL as shown in §6.

### 14.2 Install the application

```bash
sudo -u edumanage bash
cd /srv/edumanage
# copy/clone the project here
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
exit
```

### 14.3 Create the environment file

```bash
sudo install -o edumanage -g edumanage -m 600 /dev/null /etc/edumanage/edumanage.env
sudo nano /etc/edumanage/edumanage.env
```

Example contents (no quotes needed; no spaces around `=`):

```ini
DJANGO_SETTINGS_MODULE=CoachingApp.settings.production
DEBUG=False
SECRET_KEY=<generate-a-new-one>
ALLOWED_HOSTS=app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com
DATABASE_URL=mysql://edumanage:password@127.0.0.1:3306/edumanage
MEDIA_ROOT=/var/lib/edumanage/media
LOG_DIR=/var/log/edumanage
BACKUP_DIR=/var/backups/edumanage
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=edumanage@example.com
EMAIL_HOST_PASSWORD=<smtp-password>
DEFAULT_FROM_EMAIL=EduManage <no-reply@example.com>
ADMIN_EMAIL=ops@example.com
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=<live-secret>
RAZORPAY_WEBHOOK_SECRET=<webhook-secret>
RAZORPAY_SANDBOX=False
```

Django-environ reads a project `.env` automatically, but a separate
root-protected env file with `EnvironmentFile=` in systemd is preferable on a
VPS. Keep the two mechanisms distinct; do not duplicate secrets.

### 14.4 Migrate, collect static, check

```bash
cd /srv/edumanage
set -a; source /etc/edumanage/edumanage.env; set +a
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py createsuperuser
```

Fix every error emitted by `check --deploy` before continuing.

### 14.5 Gunicorn service

Copy `deploy/systemd-edumanage.service.example` to
`/etc/systemd/system/edumanage.service`, adjust paths, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now edumanage
sudo systemctl status edumanage
```

### 14.6 Nginx and TLS

Copy `deploy/nginx-edumanage.conf.example` to
`/etc/nginx/sites-available/edumanage`, edit the domain and paths, then:

```bash
sudo ln -s /etc/nginx/sites-available/edumanage /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d app.example.com
sudo certbot renew --dry-run
```

### 14.7 Scheduled jobs

Copy `deploy/systemd-edumanage-monitor.service.example` and
`deploy/systemd-edumanage-monitor.timer.example` into `/etc/systemd/system/`,
then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now edumanage-monitor.timer
systemctl list-timers edumanage-monitor.timer
```

Alternatively use the cron lines in `deploy/crontab.example`.

---

## 15. Production deployment — PythonAnywhere

PythonAnywhere does not allow systemd units or arbitrary ports on free accounts.
Use a paid plan for a custom domain and always-on HTTPS.

1. Create a Bash console and clone/upload the project to
   `/home/<username>/edumanage`.
2. Create a virtual environment:

   ```bash
   cd ~/edumanage
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create a private `.env` in the project directory (mode `600`) with the
   production values from §14.3. On PythonAnywhere, `django-environ` reads it
   automatically. Use a MySQL database from the *Databases* tab and copy its
   connection URL into `DATABASE_URL`.
4. Run migrations and static collection:

   ```bash
   DJANGO_SETTINGS_MODULE=CoachingApp.settings.production python manage.py migrate
   DJANGO_SETTINGS_MODULE=CoachingApp.settings.production python manage.py collectstatic --noinput
   DJANGO_SETTINGS_MODULE=CoachingApp.settings.production python manage.py createsuperuser
   DJANGO_SETTINGS_MODULE=CoachingApp.settings.production python manage.py check --deploy
   ```

5. In the **Web** tab create a web app using Python 3.12, set the source code
   directory to `/home/<username>/edumanage`, and replace the WSGI file with
   `deploy/pythonanywhere-wsgi.py.example` (adjust the username).
6. Add static file mappings:

   | URL | Directory |
   | --- | --- |
   | `/static/` | `/home/<username>/edumanage/staticfiles` |
   | `/media/` | **do not map** — uploads are served by authenticated views |

7. Reload the web app. Add a scheduled task under the **Tasks** tab running
   `python manage.py monitor_subscriptions` daily, and another for
   `python manage.py backup_database` (download backups off-platform; platform
   backups are not a substitute for application-level dumps).
8. Enable HTTPS for your domain in the Web tab. `SECURE_SSL_REDIRECT=True` is
   appropriate when the platform terminates TLS and sets
   `X-Forwarded-Proto: https`.

> PythonAnywhere's free subdomain uses plain HTTP. If you cannot terminate TLS,
> do not use a free subdomain for a commercial deployment.

---

## 16. Domain and DNS

1. Point the application hostname at your host:
   - **A record:** `app` → VPS IPv4 address
   - **AAAA record:** `app` → VPS IPv6 address (if available)
   - **CNAME:** `www` → `app.example.com` (optional)
2. Do not publish the raw IP or a staging hostname in `ALLOWED_HOSTS`.
3. Issue a TLS certificate (Let's Encrypt via Certbot on a VPS, or the
   platform's HTTPS feature on PythonAnywhere).
4. Add the Razorpay webhook URL:
   `https://app.example.com/payments/webhook/razorpay/`
5. After TLS is active, confirm:
   - `http://app.example.com` redirects to `https://`
   - the certificate covers all names in `ALLOWED_HOSTS`
   - `CSRF_TRUSTED_ORIGINS` matches the final HTTPS origins exactly
6. HSTS preload is a long-term commitment: only submit your domain to the
   preload list once you are certain HTTPS will always be available.

---

## 17. Database backup and restore

Application-level commands are provided:

```bash
# SQLite backup (safe while running) or MySQL dump via mysqldump
python manage.py backup_database
python manage.py backup_database --dir /var/backups/edumanage
python manage.py backup_database --output /tmp/edumanage.sqlite3

# Restore — destructive, requires explicit confirmation
python manage.py restore_database /var/backups/edumanage/edumanage_....sql --force
```

Behavior:

- Timestamped files named `edumanage_YYYYMMDD_HHMMSS.sqlite3` or `.sql`.
- MySQL credentials are written to a temporary option file, never to argv.
- Restore refuses to run without `--force` and validates SQLite integrity.
- Stop the application before restoring; take a fresh backup first.

Automate daily backups and retention (see `deploy/crontab.example`):

```cron
0 2 * * * cd /srv/edumanage && .venv/bin/python manage.py backup_database --dir /var/backups/edumanage && find /var/backups/edumanage -type f -mtime +14 -delete
```

Also take a snapshot **before** schema migrations and store at least one backup
off-server. Test restores periodically — an untested backup is not a backup.

Do not rely only on host-provider snapshots for application data consistency;
combine both.

---

## 18. Razorpay configuration

1. Create a Razorpay account, complete KYC, and switch to **Live** mode.
2. Generate a live API key pair. Copy the key ID and secret into
   `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`.
3. In Razorpay Dashboard → **Webhooks**, add:
   - URL: `https://app.example.com/payments/webhook/razorpay/`
   - Secret: a distinct random value → `RAZORPAY_WEBHOOK_SECRET`
   - Events: `payment.captured`, `payment.failed`, `refund.*`
4. Set `RAZORPAY_SANDBOX=False`. The gateway also detects `rzp_test_` keys and
   treats them as sandbox automatically; `check --deploy` rejects them.
5. Confirm the webhook secret differs from the key secret — the code falls back
   to the key secret only as a convenience for development.
6. Test the full flow on a staging deployment: order creation, checkout,
   signature verification, webhook delivery, invoice, activation, and renewal.

The application never handles card numbers, CVV or UPI PINs. All payment state
changes are verified server-side with HMAC signatures and an authoritative
gateway fetch before a subscription is activated or extended.

---

## 19. Subscription scheduled jobs

The command `python manage.py monitor_subscriptions` performs expiry and the
7/3/1 day reminder bands. It is idempotent: reminders are unique per
subscription, kind and expiry cycle.

- **Linux systemd:** use the timer example in §14.7 (daily 01:15).
- **cron:** use `deploy/crontab.example`.
- **Windows:** Task Scheduler instructions in §3.7.
- **PythonAnywhere:** scheduled task calling the same command daily.

For backfills or testing a specific instant:

```bash
python manage.py monitor_subscriptions --now 2026-01-31T09:00:00
```

Never run multiple schedulers against the same database (duplicate reminders
are prevented, but duplicate load is wasted). Monitor the log output and alert
if the job has not run in 48 hours.

---

## 20. Deployment verification checklist

Run these **on your host**, with production env vars loaded:

```bash
cd /srv/edumanage
source .venv/bin/activate
set -a; source /etc/edumanage/edumanage.env; set +a

python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test -v 1
python manage.py backup_database --output /tmp/verify-backup.sqlite3  # or .sql with MySQL
curl -I https://app.example.com/
curl -I https://app.example.com/static/css/app.css
```

Acceptance criteria:

- [ ] `check --deploy` reports **no errors**; warnings are understood.
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` and CSRF origins match the live domain.
- [ ] HTTPS redirects work and cookies carry `Secure`, `HttpOnly`, `SameSite=Lax`.
- [ ] `/media/` is denied by the web server; direct guessed URLs return 403/404.
- [ ] Static files load (no 404 for `/static/css/app.css`).
- [ ] Login works for each role and each role sees only its own dashboard.
- [ ] A paid test payment activates a subscription and produces an invoice.
- [ ] The webhook is delivered and verified; replaying it does not double-charge.
- [ ] Reminders are sent once per band and expiry restricts protected views.
- [ ] A backup file is created and a restore was tested in staging.
- [ ] Logs and error emails are generated (trigger a 404/500 in staging).

**Do not announce a successful deployment until every applicable item above has
been verified on the target host.**

---

## 21. Troubleshooting and rollback

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `ImproperlyConfigured: Set the SECRET_KEY environment variable` | Production settings loaded without env file | Load `/etc/edumanage/edumanage.env` and restart the service. |
| `DisallowedHost` | `ALLOWED_HOSTS` missing the requested hostname | Add the exact host (no scheme, no wildcard) and reload. |
| CSRF 403 on forms | `CSRF_TRUSTED_ORIGINS` missing scheme or wrong proxy header | Set `https://<domain>` and verify `TRUST_X_FORWARDED_PROTO`. |
| Redirect loop | HTTPS terminated upstream but `SECURE_SSL_REDIRECT=True` with no proxy header | Ensure the proxy overwrites `X-Forwarded-Proto: https`. |
| Static 404 | `collectstatic` not run or Nginx alias wrong | Run `collectstatic`, check `nginx -t` and alias path. |
| Upload 404 | `/media/` denied or `MEDIA_ROOT` wrong | Use application download links; verify mount and permissions. |
| Emails not sent | Console backend or SMTP auth failure | Check `EMAIL_BACKEND`, credentials, and `errors.log`. |
| Payment not activated | Webhook secret mismatch or wrong events | Check Razorpay webhook logs and `errors.log`. |
| Subscription not expiring | Scheduler not running | Check `systemctl list-timers` or cron logs. |

**Rollback:** stop Gunicorn, restore the previous database backup (§17), restore
the previous code release, re-run `collectstatic` if static assets changed,
then start Gunicorn and re-run §20 checks. Never roll back data without a
fresh backup of the current state.

---

## Related documents

- `README.md` — feature and architecture overview.
- `QA_AUDIT_REPORT.md` — QA/security audit results and fix history.
- `.env.example` — environment variable template.
- `deploy/` — Nginx, systemd, cron and PythonAnywhere configuration examples.
