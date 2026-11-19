# EduManage SaaS

A commercial, multi-tenant **Coaching Institute Management SaaS** built with
Django. The implemented foundation includes email-based role authentication,
tenant isolation, institute registration/approval, subscription plans, Razorpay
payments, invoices/receipts, licenses and a live Super Admin console.

> **Deployment:** See [`DEPLOYMENT.md`](DEPLOYMENT.md) for local installation,
> Windows/PythonAnywhere/Linux VPS instructions, production configuration,
> backups, Razorpay, DNS and scheduled jobs. See
> [`QA_AUDIT_REPORT.md`](QA_AUDIT_REPORT.md) for the security audit results.

## Technology

| Layer | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Framework | Django 6.1 |
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js |
| Database | SQLite (development), MySQL (production) |
| Configuration | `django-environ` + `.env` |
| Server | `runserver` (dev), Gunicorn (prod) |

## Architecture

- **Split settings** — `CoachingApp/settings/base.py` holds shared config;
  `development.py` and `production.py` hold environment-specific overrides.
- **19 first-class apps** — each app owns its models, views, URLs, templates and
  static files. All are registered and mounted under their own URL prefix.
- **Dedicated Super Admin console** — `/superadmin/` is the platform-owner area,
  separate from the role dashboards under `/accounts/dashboard/`.
- **Custom user model** — `accounts.User` is defined before the first migration,
  so `AUTH_USER_MODEL` never has to be swapped. It includes a platform-wide
  `role` field and an institute foreign key.
- **Multi-tenant isolation** — every institute-owned model inherits
  `core.tenant.TenantModel`. Its default manager filters by the active tenant,
  `all_objects` is reserved for Super Admin/platform work, and middleware binds
  the tenant from the authenticated user on every request.
- **Reusable model bases** — `core.models.TimeStampedModel` provides timestamps
  and `core.tenant.TenantModel` adds the institute FK, scoped manager, queryset
  and cross-tenant write protection.
- **Shared templates** — `templates/base.html` plus navbar/sidebar/footer
  partials, a landing page, and custom 400/403/404/500 error pages.
- **Logging** — console + rotating file handlers (`logs/django.log`,
  `logs/errors.log`).
- **Timezone** — `Asia/Kolkata`, with timezone-aware datetimes enabled.

## Folder structure

```text
CoachingApp/                         # repository root
├── CoachingApp/                     # Django project package
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                  # shared settings
│   │   ├── development.py           # DEBUG=True + SQLite
│   │   └── production.py            # HTTPS hardening + MySQL
│   ├── asgi.py
│   ├── urls.py                      # root URLconf + error handlers
│   └── wsgi.py
├── accounts/                        # auth, users, invitations, permissions
│   ├── backends.py                  # email authentication backend
│   ├── decorators.py                # @role_required helpers
│   ├── forms.py                     # login, profile, creation, invitation forms
│   ├── mixins.py                    # CBV role mixins
│   ├── models.py                    # User + Invitation
│   ├── urls.py / views.py / admin.py / tests.py
│   └── migrations/0001_initial.py
├── activity_logs/                   # audit trail + auth signals
│   ├── models.py                    #   ActivityLog, log_activity(), redaction
│   ├── signals.py                   #   login/logout audit hooks
│   ├── views.py / urls.py / admin.py / tests.py
├── assignments/                     # teacher-created assignments
│   ├── models.py / forms.py
│   └── views.py / urls.py / admin.py
├── attendance/                      # marking, summaries, charts and exports
│   ├── models.py / services.py / exports.py
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
├── batches/                         # batch CRUD, enrollment and timetables
│   ├── models.py                    #   Batch, schedule, students, subjects
│   ├── services.py                  #   plan limits, enrollment, assignments
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
├── core/                            # base templates, tenant layer, errors
│   ├── api.py                       # tenant-scoped JSON APIs
│   ├── context_processors.py
│   ├── forms.py                     # TenantFormMixin (server-side ownership)
│   ├── middleware.py                # binds the active tenant per request
│   ├── mixins.py                    # tenant-aware view mixins
│   ├── models.py                    # TimeStampedModel
│   ├── tenant.py                    # TenantModel, managers, scoped search
│   ├── urls.py
│   └── views.py                     # tenant search + secure downloads
├── courses/                         # course and subject administration
│   ├── models.py                    #   Course, Subject + canonical/status fields
│   ├── services.py                  #   scoped search and code uniqueness
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
├── examinations/                    # exams and teacher-entered marks
│   ├── models.py / forms.py
│   └── views.py / urls.py / admin.py
├── fees/
├── institutes/                      # tenant model, public registration,
│   ├── forms.py                     #   Super Admin approval workflow
│   ├── models.py                    # Institute + RegistrationStatus
│   ├── views.py / urls.py / admin.py / tests.py
├── licenses/                        # secure software license lifecycle
│   ├── models.py                    #   License + append-only LicenseHistory
│   ├── services.py                  #   issue/validate/activate/suspend/revoke
│   ├── views.py / urls.py / forms.py
│   └── tests.py
├── notifications/                   # in-app inbox, admin/teacher composers
│   ├── models.py                    #   Notification, NotificationRead, BatchAnnouncement
│   ├── services.py                  #   audience matching + read state
│   ├── context_processors.py        #   navbar bell count
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
├── payments/                        # Razorpay checkout, verification, invoices
│   ├── gateway.py                   #   signed requests + HMAC verification
│   ├── services.py                  #   payment state transitions + invoice data
│   ├── pdf.py                       #   dependency-free PDF writer
│   ├── views.py / urls.py / forms.py
│   └── tests.py
├── reports/                         # role-scoped Reports & Analytics
│   ├── forms.py                     #   shared date/batch/course/search filters
│   ├── services.py                  #   report registry + live DB query builders
│   ├── views.py / urls.py / tests.py
│   └── templates/reports/           #   hub + report page with Chart.js
├── students/                        # full student administration module
│   ├── models.py                    #   Student + status/gender choices
│   ├── services.py                  #   enrollment IDs, plan limits, accounts
│   ├── views.py / urls.py / forms.py
│   └── tests.py
├── study_material/                  # notes, reading history and student alerts
│   ├── models.py                    #   StudyMaterial, MaterialView, MaterialNotification
│   ├── services.py                  #   validation, access, tracking, reports
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
├── subscriptions/                   # plan catalog, subscriptions, renewals, reminders
│   ├── models.py                    #   Subscription, SubscriptionRenewal, SubscriptionReminder
│   ├── services.py                  #   monitoring, reminders, proration, renewal
│   ├── management/commands/
│   │   └── monitor_subscriptions.py #   scheduled daily monitor command
│   ├── forms.py / views.py / urls.py / admin.py / tests.py
│   └── migrations/
├── superadmin/                      # platform console: views, services, forms,
│   ├── views.py / urls.py           #   stats, navigation and settings
│   ├── services.py                  # approval/extension/invoice side effects
│   └── tests.py
├── teachers/                        # full teacher administration + workspace
│   ├── models.py                    #   Teacher, subjects/batches, activity log
│   ├── services.py                  #   IDs, accounts, plan limits, scoped data
│   ├── views.py / urls.py / forms.py / admin.py
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── includes/                    # navbar, sidebar, footer
│   ├── errors/                      # 400, 403, 404, 500
│   ├── accounts/                    # login, reset, profile, dashboards,
│   │   ├── auth_base.html           #   user/invitation management pages
│   │   └── email/                   # reset + invitation emails
│   ├── payments/                    # checkout, proof upload, history, invoices
│   ├── subscriptions/               # plans, status, renewal, history
│   ├── reports/                     # report hub + generated reports
│   └── superadmin/                  # console shell, tables, forms, Chart.js
├── static/
│   ├── css/app.css                  # shared navy/sky design system
│   └── js/app.js                    # toasts, confirms, loaders, tables
├── logs/                            # rotating log files (git-ignored)
├── media/                           # user uploads (git-ignored)
├── .env.example
├── .gitignore
├── manage.py
├── README.md
└── requirements.txt
```

## Quick start

### 1. Create and activate a virtual environment

An existing venv is located at `C:\Users\Rupam\OneDrive\Desktop\Coaching\venv`.
To create a fresh one in the project folder:

```powershell
# Windows (PowerShell) - from the repository root
python -m venv venv
.\venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

If PowerShell blocks activation, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the environment

```powershell
copy .env.example .env
```

Edit `.env` and replace `SECRET_KEY` with a long random value. Leave
`DATABASE_URL` empty to use SQLite during development.

### 4. Run migrations

```bash
python manage.py migrate
```

Whenever models change later:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Start the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The admin is at
<http://127.0.0.1:8000/admin/>; create a superuser with
`python manage.py createsuperuser`.

### 6. Verify the setup

```bash
python manage.py check
python manage.py check --deploy --settings=CoachingApp.settings.production
```

## Authentication and authorization

The custom `accounts.User` model replaces Django's username with a unique email
address (`USERNAME_FIELD = "email"`). It is the first migration in `accounts`,
so no user-model swap will ever be needed. Passwords are hashed with Django's
PBKDF2 hasher and validated against a 10-character minimum plus the built-in
common/numeric/similarity validators.

### Roles and dashboards

| Role | Dashboard URL | Allowed actions |
| --- | --- | --- |
| `SUPER_ADMIN` | `/accounts/dashboard/super-admin/` | Create institutes and institute admins, manage accounts |
| `INSTITUTE_ADMIN` | `/accounts/dashboard/institute-admin/` | Create teachers/students in **their own** institute, invite by email, manage those accounts |
| `TEACHER` | `/accounts/dashboard/teacher/` | Own profile and password only |
| `STUDENT` | `/accounts/dashboard/student/` | Own profile and password only |

Every dashboard is guarded by `@role_required(...)` (or `RoleRequiredMixin` for
class-based views). Cross-role access returns **403** and renders the custom
error page. `/accounts/dashboard/` redirects each verified role to its own
dashboard.

### Institute Admin Dashboard

`/accounts/dashboard/institute-admin/` is a live command centre rendered by
`accounts/dashboard_data.py`. All counters and chart series are built from the
requesting tenant's own records via `Model.objects.for_institute(...)`; a
Super Admin session still cannot read another institute's numbers. The sidebar
lists every module area the administrator can reach (the original 18-item set
plus the attendance, assignment and examination workspaces added later).

- **Stat cards** — students, active students, teachers, courses, batches,
  assignments, examinations, study materials and overall attendance percentage.
- **Subscription widget** — current plan, status, expiry date, days remaining
  and seat usage bars for students, teachers and batches. Actions link to
  **Renew** (renewal/change-plan page), **Upgrade** (same page, with proration
  preview), **View Invoice** (latest tenant invoice PDF, otherwise the invoice
  list) and **Download Receipt** (latest paid payment, otherwise payment history).
- **Expiry warning** — an amber alert appears within seven days of expiry and
  a red alert after expiry. Expired subscriptions are restricted to renewal and
  billing pages by the tenant middleware, with optional configurable grace
  access to dashboards.
- **Charts** — Chart.js bar (students per course), line (present percentage for
  the last six months) and doughnut (exam Pass/Fail) series, injected with
  Django's `json_script` filter so no template-side data is hard-coded.
- **Quick actions** — direct links to user management, students, teachers,
  batches, attendance reports and examination results.

The layout uses responsive Bootstrap grids and the shared navbar/sidebar;
Chart.js is loaded once in `templates/base.html`.

### Flows

- **Login / logout** — email-based login at `/accounts/login/`; logout is a
  CSRF-protected POST at `/accounts/logout/` and flushes the session.
- **Forgot / reset password** — `/accounts/password-reset/` sends a single-use,
  short-lived reset link using Django's signed token framework.
- **Change password** — `/accounts/password-change/` requires the current
  password and applies the same strength validators.
- **Profile** — `/accounts/profile/` updates name, email, phone and profile
  image (uploads go to `media/profiles/`).
- **Account status** — managers activate/deactivate users from
  `/accounts/users/`; deactivated accounts cannot authenticate. Super Admin
  and Institute Admin cannot deactivate themselves.
- **Invitations** — there is **no public teacher/student self-registration**.
  An Institute Admin creates a single-use invitation (7-day expiry) at
  `/accounts/invitations/create/`; the invitee completes registration at the
  emailed link, where role and institute are taken from the invitation.
- **Institute scoping** — an Institute Admin sees and can modify only
  teacher/student accounts in their own institute. Other institutes return 404.

### Session security

Sessions use HTTP-only, SameSite=Lax cookies with an 8-hour lifetime and
expire when the browser closes. Production settings additionally enforce
secure cookies, HTTPS redirects and HSTS.

### Auth tests

```bash
python manage.py test accounts -v 2
```

The suite covers all four dashboards (including negative cross-role checks),
email login, logout, password reset/change, profile uploads, management
permissions, institute scoping, deactivation and the full invitation flow.

## Multi-tenant architecture and institute registration

The same application instance can be sold to many coaching institutes. Each
institute is a tenant with a generated public `institute_id` (`INST-...`), its
own administrator account, subscription and isolated records.

### Registration lifecycle

1. **Public registration** — `/institutes/register/` collects institute name,
   owner name, email, mobile, address, city, state, pincode, password and
   confirmation.
2. **Tenant + admin creation** — a pending, inactive `Institute` and a linked
   `INSTITUTE_ADMIN` user are created in one transaction. The new admin is
   signed in automatically.
3. **Plan selection** — `/subscriptions/plans/select/` creates a **pending**
   subscription and an unpaid `Payment`. Four standard plans are seeded by
   migration `subscriptions/0004_subscription_plan_module.py` and can be changed
   by the platform owner at any time.
4. **Payment** — the admin is routed to Razorpay checkout for online payment or
   can submit a bank-transfer/cash proof. Only a verified gateway response or a
   Super Admin manual approval can mark the payment paid.
5. **Pending gate** — until payment verification, middleware redirects the
   institute admin away from dashboards and feature pages to checkout/status.
6. **Super Admin approval** — `/institutes/pending/` lists registrations.
   Approval requires a paid payment record; it then activates the institute,
   subscription, license and admin account. Rejection marks the institute and
   subscription rejected and deactivates the admin.

### Tenant isolation layers

- **Models** — `core.tenant.TenantModel` gives every institute-owned model an
  `institute` FK, a scoped default manager, an unscoped `all_objects` manager,
  and a save guard that rejects cross-tenant writes while a tenant is active.
  Concrete examples: `students.Student`, `teachers.Teacher`, `courses.Course`,
  `study_material.StudyMaterial`, `reports.SavedReport` and
  `subscriptions.Subscription`.
- **Querysets** — `TenantQuerySet.for_institute()` is explicit; the default
  manager additionally filters using a request-scoped `ContextVar`.
- **Middleware** — `TenantIsolationMiddleware` pins every non-Super-Admin
  request to its own institute and enforces the pending-subscription gate.
- **Views / mixins** — `TenantRequiredMixin`, `TenantObjectMixin` and helpers
  such as `scoped_queryset()` force server-side filtering. Object IDs from
  another institute resolve to 404, not merely a hidden menu item.
- **Forms** — `TenantFormMixin` assigns `instance.institute` from
  `request.user`; a forged `institute` field in POST data is ignored.
- **APIs** — `/core/api/search/` and
  `/core/api/records/<app_label>/<model_name>/` derive the tenant from the
  session and ignore `?institute_id=` query parameters.
- **File downloads** — `/core/download/<app>/<model>/<pk>/<field>/` verifies the
  object through the scoped queryset and only then streams the file. Uploads
  are physically partitioned under `media/tenants/<institute_id>/`.
- **Reports / search** — generated CSVs and `/core/search/` only read
  tenant-scoped querysets, so Institute A can never include Institute B data.

### Tenant security tests

```bash
python manage.py test -v 2
```

The suite includes 332 tests, including a dedicated security audit suite
(`core/test_security_audit.py`) covering role authorization, CSRF, SQL injection,
XSS, upload validation, webhook authenticity, payment idempotency, password
policy, login throttling, session cookies and cross-tenant IDOR. Tenant-specific
coverage proves that cross-institute object downloads, report downloads, search
results, record APIs, payment documents, license pages and forged form
submissions are blocked, while Super Admin retains intentional platform-wide
visibility. See `QA_AUDIT_REPORT.md` for the full audit results.

## Super Admin platform console

Only `SUPER_ADMIN` users can access `/superadmin/`. Login now redirects the
platform owner there; the old `accounts:super_admin_dashboard` URL redirects to
the same console.

The console has its own dark, responsive sidebar with all 13 requested sections:
Dashboard, Institute Management, Subscription Plans, Subscriptions, Payment
Management, License Management, Invoices, Renewals, Revenue Reports, Activity
Logs, Notifications, System Settings and Logout.

### Live statistics

Every number is aggregated from database rows:

- Institute totals by status (active, pending, suspended)
- Subscription totals (active, expired, pending approval)
- Payment totals and pending payment count
- Total, monthly and yearly revenue from paid `Payment` rows
- Monthly revenue series rendered with Chart.js

### Platform workflows

- Search institutes by name, email or generated `INST-...` ID and filter by
  active, pending, expired or suspended status.
- Open an institute profile with its admin, subscription history, payments,
  invoices, licenses and platform activity.
- Activate or suspend an institute; activation is blocked until a verified paid
  payment exists, and both actions update the subscription/license state and
  write an audit entry.
- Create/edit plans and enable or disable them in the selection catalog.
- Extend subscriptions, change plans and record cash/manual payments.
- Search/filter payments by institute, transaction, status and method; approve
  or reject manual proof, record refunds and download PDF receipts.
- Generate printable invoices with configurable tax from System Settings and
  download them as PDFs from both tenant and platform views.
- Generate, activate, suspend, revoke and extend licenses, inspect their full
  history and see live server-side validation status from the console.
- Review renewals, revenue charts, activity logs and notifications.
- Maintain platform settings such as platform name, support email, currency,
  revenue goal and the configurable subscription grace period.

Selecting a plan automatically raises a pending `Payment` and an inactive
`License`; activation only happens after payment verification, so the console
starts with real operational data rather than hardcoded figures.

## Subscription Plan Management

`subscriptions.SubscriptionPlan` is the global catalog maintained by the
platform owner. Four standard plans are seeded by migration:

| Slug | Plan | Duration | Price |
| --- | --- | --- | --- |
| `monthly` | Monthly Plan | 1 month / 30 days | ₹999 |
| `quarterly` | Quarterly Plan | 3 months / 90 days | ₹2499 |
| `half-yearly` | Half-Yearly Plan | 6 months / 180 days | ₹4499 |
| `yearly` | Yearly Plan | 12 months / 365 days | ₹7999 |

The model stores `plan_name`, `slug`, `description`, `duration_in_days`,
`duration_in_months`, `price`, `discount_price`, `max_students`,
`max_teachers`, `max_batches`, `max_storage_mb`, `features`, `is_popular`,
`is_active`, `created_at` and `updated_at`. Super Admins can add, edit,
deactivate or safely delete plans from `/superadmin/plans/`, including all
prices, durations, limits and feature lines. Deletion is blocked while a tenant
subscription still references the plan; deactivation is the safe alternative.

The public `/subscriptions/pricing/` page renders four attractive cards and a
comparison table directly from this catalog. No price, duration or limit is
hardcoded in a template. A card's **Select Plan** button stores the choice in
the session and routes the visitor to registration or plan confirmation.

Automated coverage includes default-plan seeding, discount/duration helpers,
database-driven pricing output, inactive-plan hiding, and Super Admin plan
creation and editing with all limits, durations, prices and features.

## Payments, invoices and receipts

### Data model

- `payments.Payment` stores the tenant, subscription, `transaction_id`, amount,
  currency, payment method/date/status, gateway order/payment IDs, receipt
  number, proof upload, verifier, refund fields and failure details.
- `payments.Invoice` stores `invoice_number`, tenant, subscription, linked
  payment, subtotal, tax, total, invoice date/status and billing details.
- Statuses: `pending`, `authorized`, `paid`, `failed`, `refunded`; refunds are
  tracked separately as `none`, `requested`, `processed` or `failed`.
- Methods: UPI, debit card, credit card, net banking, manual bank transfer and
  cash recorded by the Super Admin. **Card numbers, CVV and UPI PINs are never
  accepted or stored.**
- Compatibility aliases (`Payment.status/method/paid_at` and
  `Invoice.amount/status/issued_at`) remain as read-only Python properties; use
  the canonical fields in ORM queries.

### Tenant routes

| URL | Purpose |
| --- | --- |
| `/payments/history/` | Searchable/filterable payment history |
| `/payments/checkout/<id>/` | Create/reuse a Razorpay order and render checkout |
| `/payments/verify/` | Server-side checkout signature and gateway verification |
| `/payments/webhook/razorpay/` | Signed Razorpay webhook receiver |
| `/payments/proof/<id>/` | Upload manual bank-transfer/cash proof |
| `/payments/invoices/` | Tenant invoice list |
| `/payments/invoices/<id>/pdf/` | Download a tax invoice PDF |
| `/payments/receipt/<id>/` | Download a payment receipt PDF |

### Platform routes

`/superadmin/payments/` provides search/filter, manual approval/rejection,
refund recording and PDF receipt downloads. `/superadmin/invoices/` lists all
invoices, with detail and PDF views, and invoices can also be generated from a
subscription once a paid payment exists.

### Workflows

1. **Online** — plan selection opens checkout. The browser receives only the
   Razorpay order ID/public key. The callback verifies the
   `order_id|payment_id` HMAC signature, fetches authoritative payment state from
   Razorpay and checks amount/order/status before marking the payment paid.
2. **Webhook** — `payment.captured` and `payment.failed` events are accepted only
   with a valid `X-Razorpay-Signature`; captured events are re-fetched from the
   gateway before activation.
3. **Manual** — proof uploads stay pending until the Super Admin approves or
   rejects them. Rejection records a reason and never activates the subscription.
4. **Activation** — every transition runs through `payments.services`, which is
   idempotent, duplicate-safe and transactional. A subscription, license and
   institute account become active only after a verified paid payment.
5. **Invoice/receipt** — payment verification generates a tax invoice using the
   configurable tax percent and a unique receipt number. PDFs use the local
   dependency-free writer in `payments/pdf.py`; no ReportLab binary is needed.
6. **Refunds** — refund status is recorded locally, sets the payment to
   `refunded` and voids the related invoice. `gateway.create_refund()` is
   available when gateway-initiated refunds are enabled.

Signature checks use `hmac.compare_digest`, gateway IDs have unique constraints,
and payment state is never taken from POST data or frontend callbacks.

## Student management

Student administration is available only to `INSTITUTE_ADMIN` users. Teachers,
students, anonymous visitors and Super Admins are denied all `/students/`
administration pages by `@institute_admin_required`, and every lookup is
additionally narrowed with `Student.objects.for_institute(request.user.institute)`.

### Routes

| URL | Ability |
| --- | --- |
| `/students/` | Searchable/filterable student directory |
| `/students/create/` | Add a student, enrollment number and login account |
| `/students/<id>/` | Read-only profile and lifecycle actions |
| `/students/<id>/edit/` | Edit every student field and upload a profile picture |
| `/students/<id>/activate/`, `/students/<id>/deactivate/` | Toggle record and login |
| `/students/<id>/delete/` | Delete the student and its dedicated login |
| `/students/export/` | CSV export of the filtered, tenant-scoped directory |

### Data model and account creation

- `Student` stores `student_id`, `full_name`, `email`, `mobile`, `date_of_birth`,
  `gender`, `address`, `parent_name`, `parent_mobile`, `qualification`, `course`,
  `batch`, `admission_date`, `profile_picture` and `status`. The earlier
  `first_name`, `last_name`, `phone` and `is_active` columns remain as
  synchronized compatibility fields.
- Enrollment numbers use the format `STU-XXXX-YYYY-NNNNNN`, are generated
  server-side with `secrets.randbelow`, and retry on collisions within the
  institute. They are never accepted from a POST body.
- Creating a student also creates an `accounts.User` with role `STUDENT` and the
  **same institute**. A one-time password-reset link is emailed through Django's
  mail backend; no password is stored or rendered in the browser.
- `batches.Batch` is a tenant model linked to a course. Course/batch choices in
  forms are scoped to the request's institute, and a batch from a different
  course is rejected.
- Profile pictures are stored under `media/tenants/<institute_pk>/students/` and
  served only through `core:secure_download` after a scoped object lookup.

### Plan restrictions

`students.services.active_subscription()` requires an `active` subscription that
has not expired. `student_limit_context()` counts active students against
`SubscriptionPlan.max_students` (`0` means unlimited) and is checked again
inside the creation transaction. When no plan is active or all seats are used,
creation is blocked and the directory/form display an **Upgrade plan** message
with a link to the pricing page.

## Teacher management

Teacher administration is restricted to `INSTITUTE_ADMIN` users by
`@institute_admin_required`; teachers, students, anonymous visitors and Super
Admins cannot reach `/teachers/` administration pages. Every admin lookup is
narrowed with `Teacher.objects.for_institute(request.user.institute)`.

### Administration routes

| URL | Ability |
| --- | --- |
| `/teachers/` | Searchable/filterable teacher directory |
| `/teachers/create/` | Add a teacher, teacher ID and login account |
| `/teachers/<id>/` | Profile, assignments, recent activity and lifecycle actions |
| `/teachers/<id>/edit/` | Edit every field, subjects, batches and profile picture |
| `/teachers/<id>/activate/`, `/teachers/<id>/deactivate/` | Toggle record and login |
| `/teachers/<id>/delete/` | Delete the teacher and its dedicated login |
| `/teachers/activity/` | Institute-wide teacher activity audit trail |

Teacher fields are `teacher_id`, `institute`, `full_name`, `email`, `mobile`,
`qualification`, `experience`, `specialization`, `joining_date`,
`profile_picture` and `status`. Legacy `employee_id`, `first_name`, `last_name`,
`phone` and `is_active` columns remain synchronized for compatibility.
`TeacherActivity` records creation, updates, activation, deactivation and every
workspace action with actor, institute and timestamp.

IDs use `TCH-XXXX-YYYY-NNNNNN`, are generated server-side with
`secrets.randbelow`, and retry on collisions within the institute. Creating a
teacher creates an `accounts.User` with role `TEACHER` in the **same institute**
and emails a one-time password-reset link; no temporary password is displayed.

### Teacher workspace routes

| URL | Ability |
| --- | --- |
| `/teachers/my-batches/` | View only assigned batches and subjects |
| `/teachers/my-students/` | View students in assigned batches only |
| `/study-material/` | List and upload files for assigned courses only |
| `/assignments/` | List and create assignments for assigned batches/subjects |
| `/attendance/` | Filter attendance history, mark students, edit own rows |
| `/examinations/` | Create examinations, enter marks and view results |
| `/notifications/teacher/` | Send and review notifications for assigned batches |
| `/notifications/teacher/create/` | Compose a category notification for one assigned batch |

Every workspace form loads choices from `teachers.services.assigned_batches()`,
`assigned_subjects()` or `assigned_courses()`, and every queryset starts from
`.for_institute(teacher.institute)`. A forged cross-institute or unassigned
subject/batch is rejected by form validation or returns HTTP 404. Uploads remain
under `media/tenants/<institute_pk>/teachers/` and are served through
`core:secure_download`.

### Plan restrictions

`teacher_limit_context()` counts active teachers against
`SubscriptionPlan.max_teachers` (`0` means unlimited). The same check runs again
inside the creation transaction via `enforce_teacher_limit()`, so concurrent
requests cannot exceed the plan. Missing/expired subscriptions and full plans
block creation and show an **Upgrade plan required** message with a pricing link.

## Course, subject and batch management

All administration pages in `courses` and `batches` are restricted to
`INSTITUTE_ADMIN` users and start their lookups from
`Model.objects.for_institute(request.user.institute)`. Cross-institute IDs return
HTTP 404, and forged foreign keys in POST data are rejected by form validation.
The old `name`, `code` and `is_active` columns remain synchronized with the new
canonical fields so student, teacher, attendance and examination code continues
to work.

### Data model

- `courses.Course` — `course_name`, `institute`, `description`, `duration`,
  `course_fee`, `status` plus an optional institute-unique `code`.
- `courses.Subject` — `subject_name`, `subject_code`, `course`, `institute`,
  `description`.
- `batches.Batch` — `batch_name`, `institute`, `course`, `start_date`,
  `end_date`, `start_time`, `end_time`, `assigned_teacher`, `maximum_students`,
  `status`, an optional `code`, M2M `subjects` and M2M `enrolled_students`.

`Batch.student_queryset()` unions students enrolled through the new M2M with
students still linked by the legacy `Student.batch` foreign key, so `student_count`,
`available_seats` and `is_full` are always accurate.

### Routes

| URL | Ability |
| --- | --- |
| `/courses/` | Searchable/filterable course directory |
| `/courses/create/`, `/courses/<id>/edit/`, `/courses/<id>/delete/` | Course CRUD |
| `/courses/<id>/` | Course profile with its subjects and batches |
| `/courses/subjects/` | Searchable/filterable subject directory |
| `/courses/subjects/create/`, `/courses/subjects/<id>/edit/`, `/courses/subjects/<id>/delete/` | Subject CRUD |
| `/batches/` | Searchable/filterable batch directory with seat counts |
| `/batches/create/`, `/batches/<id>/edit/`, `/batches/<id>/delete/` | Batch CRUD |
| `/batches/<id>/` | Batch profile, students, subjects and teachers |
| `/batches/<id>/students/` | Batch-wise students, multi-enroll and remove |
| `/batches/timetable/` | Institute timetable with course/teacher filters |

### Enrollment and assignments

`StudentEnrollmentForm` limits choices to the batch institute and to students
not already enrolled, then checks the number of free seats. `enroll_students()`
performs a second, atomic check, ignores duplicate submissions, rejects students
from another institute or a different course, and mirrors the assignment onto the
legacy `Student.batch` column when it is empty. `unenroll_student()` clears both
the M2M link and the legacy foreign key.

`BatchForm` can assign a primary `assigned_teacher` and any number of additional
teachers. `sync_batch_assignments()` keeps `Teacher.batches` and `Teacher.subjects`
aligned so those teachers immediately see the batch and its subjects in their
workspace. Subjects must belong to the batch's course.

### Plan restrictions

`batch_limit_context()` counts active batches against
`SubscriptionPlan.max_batches` (`0` means unlimited) and `enforce_batch_limit()`
re-checks inside the create view. Missing/expired subscriptions or a full plan
block creation and display an **Upgrade plan required** alert with a pricing link.

## Study material and notes management

Study material is the central content library. Teachers publish notes for their
assigned batches and subjects; students only ever see material released to their
own batch or course. Every related view requires the matching role
(`teacher_required`, `student_required` or `institute_admin_required`) and starts
from a `.for_institute()` queryset, so forged cross-institute IDs return 404.

### Data model

- `StudyMaterial` — `title`, `description`, `course`, `batch`, `subject`,
  `chapter`, `topic`, `file`, `uploaded_by`, `is_published`, `published_at`.
  The original `is_active` flag is kept in sync with publication state, and
  migration `0003` backfilled existing files as published so nothing vanished.
- `MaterialView` — `material`, `student`, `first_viewed_at`, `last_viewed_at`,
  `view_count`, unique per material/student pair.
- `MaterialNotification` — one unread alert per eligible student when a file is
  published, unique per material/student pair.

### File validation and storage

`validate_material_file()` allows PDF, DOC, DOCX, PPT, PPTX, PNG, JPG, JPEG, GIF,
WEBP and legacy TXT uploads. Anything else is rejected with a field error, and
files above `STUDY_MATERIAL_MAX_UPLOAD_SIZE` (25 MB by default) are refused.
`material_upload_path()` writes to
`media/tenants/<institute_pk>/study-material/<uuid>/<filename>`; the random
subdirectory prevents filename collisions and cross-tenant path guessing. Files
are only reachable through authenticated views that re-check tenant and batch
access — never through a public media URL.

### Viewing versus downloading

Opening a note calls `record_material_view()`, which creates the first
`MaterialView` row and then updates `last_viewed_at` and increments `view_count`
on each subsequent visit. The response uses `Content-Disposition: inline` with
the correct MIME type, so PDFs open directly in the browser. Downloading uses
`Content-Disposition: attachment` and deliberately does **not** create a view —
a download is not proof that material was read.

### Routes

| URL | Ability |
| --- | --- |
| `/study-material/` | Teacher material directory, filters and View Report buttons |
| `/study-material/upload/`, `/study-material/<id>/edit/`, `/study-material/<id>/delete/` | Teacher CRUD |
| `/study-material/<id>/open/` | Teacher preview of an owned file |
| `/study-material/<id>/report/` | Teacher reading report for one material |
| `/study-material/student/` | Student notes with search and subject/chapter filters |
| `/study-material/student/<id>/open/` | Student inline view (records a view) |
| `/study-material/student/<id>/download/` | Student secure download (no view recorded) |
| `/study-material/student/notifications/` | New material alerts and mark-read |
| `/study-material/admin/` | Institute-wide directory with teacher/batch/subject filters |
| `/study-material/admin/stats/` | Publishing and reading statistics |
| `/study-material/admin/<id>/report/` | Admin reading report |

### Reading report

`material_reading_report()` lists the total students assigned to a material, how
many have and have not opened it, and each student's name, enrollment number,
first viewed date, last viewed date and view count. Teachers reach it with the
**View Report** button on their own material rows; admins reach the same report
for every institute file. Downloads never appear as views in this report.

## Attendance management

Attendance records live in `attendance.AttendanceRecord` with `institute`,
`student`, `batch`, `teacher`, `date`, `status`, `remarks` and `created_at` from
the shared tenant base model. Statuses are `present`, `absent` and `late`. A
database `UniqueConstraint` on `(institute, student, batch, date)` prevents
duplicate records, while the marking view uses `update_or_create()` so re-saving
a date edits the existing rows rather than failing. Migration `0002` backfills
the new `teacher` field from the legacy `marked_by` field.

### Teacher workflow

`/attendance/mark/` loads only `assigned_batches(teacher)`. Choosing a batch and
date lists students from that batch only, including students enrolled through
the batch M2M. Teachers select Present, Absent or Late for each student and save
all rows atomically; forged batch IDs are rejected by the scoped form. A row can
later be edited at `/attendance/<id>/edit/` only if the teacher originally
marked it **and** is still assigned to that batch. `/attendance/` is the filtered
history with View Report-style search by student, batch, status and date. Every
mark or edit writes a `TeacherActivityAction.ATTENDANCE_MARKED` entry.

### Student workflow

`/attendance/student/` shows personal working days, present days, absent days,
late days and an automatically calculated percentage
(`(present + late) / working_days × 100`). Students can restrict the summary and
history by batch, month and year. All querysets start from the student's institute
and their own enrollment records.

### Admin workflow

| URL | Ability |
| --- | --- |
| `/attendance/admin/` | Institute-wide records, search by student, batch, teacher and date |
| `/attendance/admin/daily/` | Attendance for one date with status totals |
| `/attendance/admin/monthly/` | Chart.js daily grouped bar chart for a month and optional batch |
| `/attendance/admin/activity/` | Teacher attendance activity and edits |
| `/attendance/admin/report/` | Filtered report with Excel and PDF download buttons |
| `/attendance/admin/export/excel/`, `/attendance/admin/export/pdf/` | Exports honouring the active filters |

`monthly_chart_data()` produces one label per day of the selected month with
separate Present, Absent and Late series; Chart.js is already included in
`templates/base.html`. Excel is written as a real `.xlsx` package with the
standard library, and PDF uses the existing dependency-free PDF writer. Both
exports apply the same tenant and filter rules as the on-screen report.

## Assignment management

`assignments.Assignment` extends the original teacher-created model with an
`issue_date` and an optional document attachment. The historical `due_date`
field remains the canonical submission deadline, and `deadline`/`is_published`
are read-only aliases. New `AssignmentSubmission` rows are created in `Pending`
state for every student in the batch when an assignment is issued (and lazily
for students enrolled later). Statuses are `Pending`, `Submitted`, `Late` and
`Evaluated`; submitting after the deadline automatically records `Late` and a
late flag, while evaluation moves the row to `Evaluated` with marks and feedback.

### Teacher workflow

| URL | Ability |
| --- | --- |
| `/assignments/` | Assignments created by the teacher |
| `/assignments/create/`, `/assignments/<id>/edit/` | Create/edit with batch, subject, issue date, deadline and document |
| `/assignments/<id>/` | Submission list with status counts and evaluate/download actions |
| `/assignments/<id>/file/` | Download the teacher's own assignment document |
| `/assignments/submissions/<id>/download/` | Download a student's answer file |
| `/assignments/submissions/<id>/evaluate/` | Enter marks and feedback |

Batch and subject choices come from `assigned_batches()` and
`assigned_subjects()`, and every queryset starts from the teacher's institute.
Teachers cannot download or evaluate submissions for another teacher's work.

### Student workflow

`/assignments/student/` lists only published assignments for batches the student
belongs to (legacy `Student.batch` and current M2M enrollment are both honoured).
Students download the task file, upload an answer at
`/assignments/student/<id>/submit/`, and see the live status, marks and feedback.
Uploads are validated with the shared document rules and stored in a tenant and
UUID-scoped media path. The generic `core:secure_download` endpoint refuses
students for assignment and submission files, so all access goes through the
workspace endpoints that re-check publication and batch membership.

## Examination management

`examinations.Examination` keeps the teacher's existing fields and adds
`pass_percentage` (default 40) and `is_active`. `examinations.Mark` gains
`remarks`. Percentage and result are derived automatically on the model:
`percentage = marks / max_marks × 100` and `Pass` when marks meet
`max_marks × pass_percentage / 100`, otherwise `Fail`.

### Teacher workflow

`/examinations/` and `/examinations/create/` remain the teacher workspace.
`/examinations/<id>/marks/` accepts one mark and one remark per student in the
exam's batch, ignores out-of-range values, and writes a `MARKS_ENTERED`
activity entry. `/examinations/<id>/` displays percentage, result and remarks.

### Student workflow

`/examinations/student/` shows the exam schedule with obtained marks, total
marks, percentage, automatic Pass/Fail/Not declared status and teacher remarks.
Hidden, foreign and other-batch examinations are excluded.

### Admin workflow

| URL | Ability |
| --- | --- |
| `/examinations/admin/` | Create, edit, publish/hide and delete any institute exam |
| `/examinations/admin/performance/` | Batch-wise aggregate performance |
| `/examinations/admin/report-card/<student_id>/` | Individual report card |
| `/examinations/admin/results/` | Filtered result table with export buttons |
| `/examinations/admin/export/excel/`, `/examinations/admin/export/pdf/` | Result exports honouring filters |

`report_card()` totals declared marks and their maximums across the student's
exams, calculates the aggregate percentage and derives an overall status. Excel
and PDF exports reuse the dependency-free writers from the attendance module and
apply the same tenant, batch, exam, student and date filters as the results page.

## Notifications and activity logs

### Notification module

`notifications.Notification` carries `institute`, `title`, `message`,
`notification_type`, `target_role`, `target_batch`, `target_course`,
`created_by` and `created_at`. Categories are New Notes Uploaded, New
Assignment, Examination Notice, Class Schedule Change, Fee Reminder, General
Announcement and Subscription Expiry Reminder. Audiences are all students, all
teachers, all institute admins (used by automated subscription reminders), a
specific batch or a specific course.

- Institute Admins compose broadcasts at `/notifications/admin/create/` and
  review institute history at `/notifications/admin/`.
- Teachers may only send batch notifications to batches returned by
  `teachers.services.assigned_batches()`; forged unassigned batches are rejected
  by form validation.
- `notifications.services.visible_notifications()` resolves the audience from
  the user's role and profile, so a student never sees another institute's or
  another batch's notification.
- Every signed-in user has an inbox at `/notifications/` with all/unread/read
  filters. `NotificationRead` stores one `(notification, user)` receipt;
  "mark as read" is idempotent and "mark all as read" only touches visible rows.
- The navbar bell is fed by `notifications.context_processors.notification_badge`,
  which also keeps the Super Admin platform notice count intact.

### Activity log module

`activity_logs.ActivityLog` records `institute`, `user`, `action`, `description`,
`timestamp` and `ip_address`. `ActivityAction` supplies canonical names for
login/logout, student/teacher creation, notes upload/deletion, assignment
creation, attendance updates, fee payments, subscription changes, license
activation and payment approval.

- `log_activity()` always redacts password/token/secret/API-key/card patterns
  from descriptions. Never pass raw request bodies to it.
- `log_fee_payment()` is the ready audit hook for the student-fee module; it
  writes the `fee_payment` action without coupling billing apps together.
- Django's `user_logged_in` / `user_logged_out` signals are wired in
  `activity_logs/apps.py`; the remaining hooks live in the relevant services and
  views so each module owns its own audit calls.
- Super Admin keeps platform-wide visibility at `/superadmin/activity-logs/`.
- Institute Admins see only their own tenant at
  `/activity-logs/`, with search and action filters. Teachers and students
  receive HTTP 403.

## Software license management

Every tenant has at most one active software license. Migration
`licenses/0002_license_lifecycle.py` renames the original timestamp fields to
the canonical schema and backfills statuses without dropping license rows.

### Data model

- `licenses.License` stores `license_key`, `institute`, `subscription`,
  `issued_date`, `expiry_date`, `license_status`, `activated_at`,
  `suspended_at`, plan seat limits and `created_at`.
- Statuses are `active`, `expired`, `suspended` and `revoked`.
- `licenses.LicenseHistory` is an append-only, tenant-scoped audit table. Every
  issue, activation, suspension, expiry, revocation, extension and subscription
  sync writes an entry with actor, previous/new status and expiry.
- Keys are generated with `secrets.token_hex(10)` in the `EDM-XXXX-XXXX-XXXX-XXXX-XXXX`
  format. A `unique` key constraint, a generation collision retry and a partial
  unique constraint on `license_status='active'` per institute prevent duplicates.
- `issued_at`, `expires_at` and `is_active` remain Python compatibility shims;
  use `issued_date`, `expiry_date` and `license_status` in ORM queries.

### Routes

| URL | Ability |
| --- | --- |
| `/licenses/` | Institute Admin: view their key, status and expiry date |
| `/superadmin/licenses/` | Super Admin: searchable/filterable license list |
| `/superadmin/licenses/generate/` | Generate a fresh key and revoke the previous active one |
| `/superadmin/licenses/<id>/` | License details, validation result and history |
| `/superadmin/licenses/<id>/activate/` | Activate after subscription/tenant checks |
| `/superadmin/licenses/<id>/suspend/` | Suspend with a recorded reason |
| `/superadmin/licenses/<id>/extend/` | Extend license and subscription validity |
| `/superadmin/licenses/<id>/revoke/` | Permanently revoke a license |

### Server-side validation

`licenses.services.validate_license()` is the only access decision point. It
canonicalizes the key, verifies the tenant and subscription, rejects revoked,
suspended, expired and manually expired licenses, and confirms that the
institute and subscription are active. `validate_institute_license()` is called
by tenant middleware before feature pages are served; a revoked or suspended
license redirects the user to the read-only license status page. No validation
secret, signature or decision logic is rendered into frontend JavaScript.

All lifecycle changes go through `licenses.services`, which is transactional.
Subscription approval, payment verification, renewal and plan changes call
`sync_license()`, so expiry date and status always follow the authoritative
subscription. Suspending an institute cascades to its active licenses, and a
revoked license can never be silently reactivated.

## Frontend design system

All pages use a shared Bootstrap 5 design system with a navy primary colour,
white secondary surfaces, sky-blue accents and a light-gray page background.
`static/css/app.css` and `static/js/app.js` provide the common cards, tables,
forms, badges, buttons, toasts, styled confirm dialogs, loading overlays, empty
states and responsive utilities. Font Awesome icons and Chart.js are loaded once
in `templates/base.html`.

Dedicated layout wrappers keep each area visually consistent while preserving
role separation:

| Layout | Area |
| --- | --- |
| `layouts/public_base.html` | Public marketing website and login |
| `layouts/super_admin_base.html` | Super Admin console |
| `layouts/institute_admin_base.html` | Institute Admin dashboard |
| `layouts/teacher_base.html` | Teacher workspace |
| `layouts/student_base.html` | Student workspace |

Public marketing pages (Home, About, Features, Pricing, FAQ, Contact, Login and
Institute Registration) are responsive and SEO-friendly: each has a unique
title, meta description, Open Graph/Twitter tags and canonical URL, and the
Home/FAQ pages include JSON-LD structured data. The Home page features the
nine core capabilities and a lead-capture form that emails the support inbox;
the Pricing page renders the four billing plans (Monthly, Quarterly,
Half-Yearly, Yearly) directly from the database with a **Purchase Now** button
on every card — prices are never hardcoded. Clicking Purchase Now remembers the
plan, sends anonymous visitors to institute registration, and routes signed-in
Institute Admins to plan selection; a verified Razorpay payment activates the
subscription and licence and redirects to the Institute Admin Dashboard.

There are no placeholder links or dead buttons. The authenticated navbar is
role-aware, with profile dropdown, notification bell and a collapsible sidebar.
All forms, tables and modals are keyboard accessible with visible focus states
and ARIA labels.

## Reports and analytics

`reports/` provides live, role-scoped reports with no hardcoded data:

- **Super Admin** — total institutes, active/expired subscriptions, monthly and
  yearly revenue, plan-wise sales, payment history, registration reports and
  renewal reports.
- **Institute Admin** — admission, teacher, course-wise, batch-wise,
  attendance, fee collection, pending fee, assignment submission, exam
  performance and notes-view reports.

Every report is built by `reports.services.build_report()` from live ORM data.
Tenant reports start from `.objects`/`.for_institute()`, while platform reports
explicitly use `.all_objects()`; no client-supplied institute id is trusted.
Shared `ReportFilterForm` supports date range, batch, course and student search.
Charts use Chart.js; Excel/PDF/print/download use the existing dependency-free
writers and honour the same filters. Fee reports are liability-only because the
`fees/` app is scaffold-only and no student fee-payment model exists.

Routes: `/reports/` (hub) and `/reports/<slug>/` (individual report). Sidebar
links point Institute Admin, Teacher and Super Admin users to the hub.

## Subscription monitoring and renewal

Subscriptions use **calendar-month arithmetic** (`add_calendar_months`) for plan
durations: 1/3/6/12 months clamp short months correctly (31 Jan + 1 month =
28 Feb, or 29 Feb in a leap year). The management command

```bash
python manage.py monitor_subscriptions
```

expires overdue subscriptions, updates the tenant and license status, and sends
reminders. Schedule it daily with cron or Windows Task Scheduler. It is safe to
run repeatedly: reminders are unique per `(subscription, kind, expiry)`, so
overlapping or repeated runs never deliver duplicates, while a renewal starts a
fresh expiry cycle.

Reminders fire at 7, 3 and 1 days before expiry, on the expiry date, and (when
configured) when the grace period ends. Each reminder is delivered by email to
active Institute Admins and as an in-app notification targeted at
`ALL_ADMINS`. The Super Admin can configure the grace period (0–365 days) in
System Settings.

On expiry the subscription and institute are marked `EXPIRED`, the license is
reconciled, and protected operations are blocked on the server. Renewal and
billing pages remain reachable, and dashboards remain readable during the grace
period. All institute data is preserved — nothing is deleted.

Institute Admins can renew, upgrade or downgrade at `/subscriptions/renewal/choose/`.
`proration_preview()` computes the unused-time credit and exact charge on the
server; the browser never supplies an amount. Downgrades never issue a cash
refund. Confirmed renewals create a pending `Payment`, and payment verification
applies the new plan, extends expiry with calendar months, reactivates the
license and records the change in `/subscriptions/renewal/history/`.
`SubscriptionRenewal` and `SubscriptionReminder` provide the audit trail.

## Production security checklist

The application enforces tenant isolation, role permissions and CSRF in code,
but a correct deployment is still required:

- **Never run production with development settings.** Set
  `DJANGO_SETTINGS_MODULE=CoachingApp.settings.production` and supply
  `SECRET_KEY`, `ALLOWED_HOSTS` and `DATABASE_URL`. The default `wsgi.py`
  setting is development; explicitly override it in the process manager.
- **Never expose `/media/` publicly.** In development Django serves uploads
  from `MEDIA_ROOT` for convenience. In production, configure the web server or
  object storage so uploaded files are **not** reachable by guessed direct
  URLs. All application file access goes through authenticated views that
  re-check tenant, role and batch membership. Add signed URLs or an
  auth-enforcing media handler if direct access is required.
- **Use a shared cache in production.** Login throttling uses Django's cache
  framework. Configure Redis/Memcached via `CACHES` so failed-login counters
  are shared across all worker processes.
- **Configure Razorpay webhook secret.** Set `RAZORPAY_WEBHOOK_SECRET` to the
  secret shown in the Razorpay dashboard. Do not rely on the fallback to the
  key secret. Set `RAZORPAY_SANDBOX=False` for live payments.
- **Trusted proxy header.** `SECURE_PROXY_SSL_HEADER` trusts
  `X-Forwarded-Proto`. Only expose the app behind a proxy that overwrites this
  header; otherwise suppress the SSL redirect setting appropriately.
- **Keep `DEBUG=False`.** Production settings force it off. Error pages are
  custom and do not expose stack traces.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `DEBUG` | Debug mode | `False` (dev settings force `True`) |
| `SECRET_KEY` | Django signing key | insecure dev default; **required in production** |
| `ALLOWED_HOSTS` | Comma-separated hostnames | empty (dev adds localhost) |
| `DATABASE_URL` | DB connection URL | empty → SQLite in dev, **required in production** |
| `DATABASE_SSL_CA` | MySQL TLS CA certificate path | empty |
| `STATIC_ROOT` | `collectstatic` destination | `staticfiles/` |
| `MEDIA_ROOT` | Upload storage directory | `media/` (keep outside web root) |
| `LOG_DIR` | Log directory | `logs/` |
| `BACKUP_DIR` | Default backup directory | `backups/` |
| `EMAIL_BACKEND` | Email delivery backend | console in dev, **SMTP in production** |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP server | empty, `587` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials | empty |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | SMTP encryption | `True`, `False` |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Sender addresses | `no-reply@edumanage.local` |
| `ADMIN_EMAIL` | Receives 500-error emails | empty |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins | empty |
| `SECURE_SSL_REDIRECT` | Force HTTPS | `True` in production |
| `TRUST_X_FORWARDED_PROTO` | Trust proxy TLS header | `True` in production |
| `SESSION_COOKIE_DOMAIN`, `CSRF_COOKIE_DOMAIN` | Shared cookie domains | empty |
| `SECURE_HSTS_SECONDS` | HSTS max-age | `31536000` |
| `RAZORPAY_KEY_ID` | Razorpay public key ID | empty (required for live checkout) |
| `RAZORPAY_KEY_SECRET` | Razorpay secret key (server only) | empty |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook HMAC secret | empty (required in production) |
| `RAZORPAY_SANDBOX` | Force sandbox/test mode | `True` in dev, **`False` in production** |
| `RAZORPAY_CURRENCY` | Gateway currency | `INR` |

The full reference, including required/optional status and deployment notes, is
in `DEPLOYMENT.md` §5.

Never place Razorpay secrets in source code or templates. Test keys starting
with `rzp_test_` are detected as sandbox automatically. Configure the webhook
URL as `/payments/webhook/razorpay/` and select `payment.captured`,
`payment.failed` and `refund.*` events.

Example MySQL URL:
`mysql://edumanage:strong-password@127.0.0.1:3306/edumanage`

## Static files, media and error pages

- `STATIC_URL = /static/`, source files in `static/`, collected into
  `staticfiles/` by `python manage.py collectstatic`.
- `MEDIA_URL = /media/`, uploads go to `media/`; Django serves them only when
  `DEBUG=True`. Production must configure the web server or object storage.
- Bootstrap 5 and Chart.js are loaded from CDN in `templates/base.html`.
- Custom error templates live in `templates/errors/` and are wired through
  `handler400`, `handler403`, `handler404` and `handler500` in the root URLconf.

## GitHub repository and upload

The repository root is this `CoachingApp/` folder. Upload the **whole source
project**, not a single file. `.gitignore` excludes `.env`, `db.sqlite3`,
`media/`, `logs/`, `backups/`, `staticfiles/`, virtualenvs and Python caches;
only `media/.gitkeep` and `logs/.gitkeep` are kept so those directories exist
after cloning.

```powershell
git status --short
git add -A
git commit -m "Prepare EduManage for deployment"
git remote add origin https://github.com/<account>/<repository>.git
git branch -M main
git push -u origin main
```

If the remote already exists, replace `git remote add` with:

```powershell
git remote set-url origin https://github.com/<account>/<repository>.git
```

**Upload:** all Python source, migrations, `templates/`, `static/`,
`requirements.txt`, `manage.py`, `.env.example`, `.gitignore`, `.gitattributes`,
`README.md`, `DEPLOYMENT.md`, `QA_AUDIT_REPORT.md` and `deploy/`.

**Never upload:** `.env`, a real `SECRET_KEY`, Razorpay credentials,
`db.sqlite3`, user uploads from `media/`, logs, backups, `.venv/` or
`__pycache__/`.

A Linux VPS or PythonAnywhere host needs no extra PaaS build file — use the
examples in `deploy/` and the WSGI entry point. Render/Railway/Heroku-style
platforms need a platform-specific file such as `render.yaml` or `Procfile`;
confirm the target platform before adding one.

Pushing source to GitHub is **not** a deployment. Follow `DEPLOYMENT.md` and
verify the live host before calling the app deployed.

## Production notes

See `DEPLOYMENT.md` for the complete procedure. In short:

1. Set `DJANGO_SETTINGS_MODULE=CoachingApp.settings.production` (WSGI/ASGI now
   default to it) and supply `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`,
   `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, SMTP
   settings and `CSRF_TRUSTED_ORIGINS`.
2. Set `RAZORPAY_SANDBOX=False` only with live `rzp_live_...` keys and a distinct
   webhook signing secret.
3. Run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
4. Run `python manage.py check --deploy --settings=CoachingApp.settings.production`
   and resolve every error. Extra production checks live in
   `CoachingApp/checks.py`. `manage.py` defaults to development settings, so the
   `--settings` flag (or an explicit `DJANGO_SETTINGS_MODULE`) is required.
5. Serve with Gunicorn behind a TLS-terminating reverse proxy, e.g.
   `gunicorn CoachingApp.wsgi:application --bind 127.0.0.1:8000`.
6. Serve static files from `staticfiles/` via the proxy/CDN. Never expose
   `/media/` directly — all uploads are read through authenticated views.
7. Schedule `python manage.py monitor_subscriptions` daily and
   `python manage.py backup_database` with off-server retention.

## Application inventory

| # | App | URL prefix | Status |
| --- | --- | --- | --- |
| 1 | `core` | `/` | Foundation + tenant isolation implemented |
| 2 | `accounts` | `/accounts/` | Auth, roles, invitations and dashboards implemented |
| 3 | `institutes` | `/institutes/` | Tenant registration and approval implemented |
| 4 | `subscriptions` | `/subscriptions/` | Plan catalog, public pricing and tenant subscriptions implemented |
| 5 | `payments` | `/payments/` | Razorpay checkout, verification, refunds, invoices and receipts implemented |
| 6 | `licenses` | `/licenses/` | Secure key generation, validation, lifecycle and history implemented |
| 7 | `students` | `/students/` | Admin-only CRUD, accounts, limits, export implemented |
| 8 | `teachers` | `/teachers/` | Full CRUD, activity log and scoped workspace implemented |
| 9 | `courses` | `/courses/` | Full course/subject CRUD, filters and uniqueness implemented |
| 10 | `batches` | `/batches/` | Full CRUD, enrollment, seats, assignments, timetable implemented |
| 11 | `study_material` | `/study-material/` | Teacher CRUD, student notes, view tracking, reports implemented |
| 12 | `attendance` | `/attendance/` | Teacher marking, student summary, admin charts/exports implemented |
| 13 | `assignments` | `/assignments/` | Teacher assignment creation implemented |
| 14 | `examinations` | `/examinations/` | Exams and teacher-entered marks implemented |
| 15 | `fees` | `/fees/` | Scaffold only |
| 16 | `notifications` | `/notifications/` | Inbox, admin/teacher composers, read receipts implemented |
| 17 | `reports` | `/reports/` | Tenant-scoped reports implemented |
| 18 | `activity_logs` | `/activity-logs/` | Institute audit trail + platform-wide Super Admin logs implemented |
| 19 | `superadmin` | `/superadmin/` | Platform-owner console implemented |
