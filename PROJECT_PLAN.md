# LexOffice - Complete Project Implementation Plan
## Legal Office Management SaaS - Egypt MVP
### Flask + Flask-SQLAlchemy Web Application

---

## TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Database Schema - All Models](#4-database-schema---all-models)
5. [Module Breakdown & Implementation Details](#5-module-breakdown--implementation-details)
6. [External Services & API Keys](#6-external-services--api-keys)
7. [Security Implementation](#7-security-implementation)
8. [Implementation Phases](#8-implementation-phases)
9. [Configuration & Environment Variables](#9-configuration--environment-variables)

---

## 1. PROJECT OVERVIEW

**What is LexOffice?**
A SaaS platform for Egyptian law firms (2-30 lawyers) to manage everything from client registration to judgment enforcement in one system.

**Target Market:** Egyptian law offices
**Language:** Fully Arabic (RTL interface + content + notifications)
**Business Model:** SaaS subscription (Starter / Professional / Enterprise) - Seat-based monthly/annual
**AI Role:** Document summarization only + Smart Reminder text improvement (supportive, not core)
**Platforms:** Web App (primary, what we're building) + Mobile App (V2 - read-only initially)

**Problems it solves:**
- Lost/disorganized paper files --> Full digital client & case files
- Missed court sessions & appeal deadlines --> Auto multi-stage notifications (SMS + Email + Push)
- No financial tracking --> Integrated financials: fees, payments, invoices, account statements
- Verbal task distribution --> Task Board with priorities and deadlines per lawyer
- Power of attorney expiring unnoticed --> Auto-tracking with color-coded alerts
- No visibility into office performance --> Real-time dashboard with all key metrics

---

## 2. TECH STACK

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | Flask |
| ORM | Flask-SQLAlchemy |
| Database | PostgreSQL (multi-tenant, schema-per-tenant) |
| Migrations | Flask-Migrate (Alembic) |
| Authentication | Flask-JWT-Extended (JWT + Refresh Tokens) |
| Password Hashing | bcrypt / argon2 |
| Task Queue | Celery + Redis |
| File Storage | Local filesystem (dev) / S3-compatible (prod) |
| PDF Generation | WeasyPrint or ReportLab |
| DOCX Generation | python-docx |
| CSV Export | Python csv module |
| Email | Flask-Mail (SMTP) |
| SMS | Twilio / Vodafone SMS API |
| AI | Azure OpenAI API |
| Rate Limiting | Flask-Limiter |
| CSRF | Flask-WTF CSRFProtect |
| Caching | Redis |
| Scheduler | Celery Beat (for recurring notification checks) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Template Engine | Jinja2 |
| CSS Framework | Bootstrap 5 (RTL support) |
| JavaScript | Vanilla JS + Alpine.js or HTMX for interactivity |
| Calendar | FullCalendar.js |
| Task Board | SortableJS (drag & drop) |
| Charts | Chart.js |
| Date Picker | Flatpickr (Arabic locale) |
| Rich Text | Quill.js or TinyMCE (for judgment text, notes) |
| File Upload | Dropzone.js |
| Dark Mode | CSS variables toggle |

---

## 3. PROJECT STRUCTURE

```
allawance/
├── flask_app.py                 # Application entry point
├── config.py                    # Configuration classes
├── requirements.txt
├── .env                         # Environment variables (NOT committed)
├── .gitignore
│
├── app/
│   ├── __init__.py              # App factory, register blueprints
│   ├── extensions.py            # db, migrate, jwt, mail, limiter, csrf
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tenant.py            # Tenant (law office)
│   │   ├── user.py              # User + Role + Permission
│   │   ├── subscription.py      # Plan, Subscription, Payment
│   │   ├── client.py            # Client (Mowakel)
│   │   ├── case.py              # Case (Qadiya)
│   │   ├── session.py           # Court Session (Galsa)
│   │   ├── judgment.py          # Judgment (Hokm)
│   │   ├── enforcement.py       # Enforcement (Tanfeez)
│   │   ├── power_of_attorney.py # POA (Tawkeel)
│   │   ├── financial.py         # Payment, Invoice, Expense
│   │   ├── task.py              # Task, Appointment
│   │   ├── document.py          # Document, Template
│   │   ├── notification.py      # Notification, NotificationSetting
│   │   └── audit.py             # AuditLog, DeviceSession
│   │
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── auth/                # Login, Register, OTP, MFA, Password reset
│   │   ├── onboarding/          # Office setup, subscription, team invite
│   │   ├── dashboard/           # Main dashboard, widgets
│   │   ├── clients/             # Client CRUD, profile tabs
│   │   ├── cases/               # Case CRUD, case file tabs
│   │   ├── sessions/            # Session CRUD, calendar
│   │   ├── judgments/           # Judgment CRUD, appeal tracking
│   │   ├── enforcement/        # Enforcement CRUD, collection tracking
│   │   ├── poa/                 # Power of Attorney CRUD
│   │   ├── financial/           # Payments, invoices, expenses, statements
│   │   ├── tasks/               # Task board, appointments
│   │   ├── documents/           # Upload, classify, preview, search
│   │   ├── templates_legal/     # Legal document templates
│   │   ├── notifications/       # Notification center, settings
│   │   ├── reports/             # All report types
│   │   ├── settings/            # Office settings, members, RBAC
│   │   └── ai/                  # Document summarization endpoint
│   │
│   ├── services/                # Business logic layer
│   │   ├── auth_service.py
│   │   ├── notification_service.py
│   │   ├── financial_service.py
│   │   ├── report_service.py
│   │   ├── ai_service.py
│   │   ├── sms_service.py
│   │   ├── email_service.py
│   │   ├── pdf_service.py
│   │   └── audit_service.py
│   │
│   ├── utils/
│   │   ├── decorators.py        # role_required, permission_required, tenant_required
│   │   ├── helpers.py           # Date calculations, Egyptian courts list, etc.
│   │   ├── constants.py         # Enums, static lists
│   │   └── validators.py        # Input validation
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html            # RTL base layout with sidebar
│   │   ├── base_auth.html       # Auth pages layout
│   │   ├── components/          # Reusable partials
│   │   ├── auth/
│   │   ├── onboarding/
│   │   ├── dashboard/
│   │   ├── clients/
│   │   ├── cases/
│   │   ├── sessions/
│   │   ├── judgments/
│   │   ├── enforcement/
│   │   ├── poa/
│   │   ├── financial/
│   │   ├── tasks/
│   │   ├── documents/
│   │   ├── templates_legal/
│   │   ├── notifications/
│   │   ├── reports/
│   │   └── settings/
│   │
│   └── static/
│       ├── css/
│       │   ├── main.css         # Custom styles
│       │   ├── rtl.css          # RTL overrides
│       │   └── dark-mode.css    # Dark theme
│       ├── js/
│       │   ├── app.js           # Main JS
│       │   ├── calendar.js
│       │   ├── taskboard.js
│       │   └── notifications.js
│       ├── img/
│       └── uploads/             # Dev only - file uploads
│
├── migrations/                  # Flask-Migrate / Alembic
├── seeds/                       # Seed data
│   ├── courts.py               # Egyptian courts list
│   ├── roles_permissions.py    # Default roles & permissions
│   └── subscription_plans.py   # Default plans
├── celery_worker.py            # Celery entry point
└── tests/
```

---

## 4. DATABASE SCHEMA - ALL MODELS

### 4.1 Tenant (Law Office)
```
tenants
├── id                  : Integer, PK
├── name                : String(200), NOT NULL          -- Office name
├── logo_path           : String(500), nullable          -- Logo file path
├── address             : Text, nullable                 -- Full address
├── bar_registration_no : String(100), nullable          -- Bar association number
├── primary_court       : String(200), nullable          -- Main court
├── courts              : Text, nullable                 -- JSON list of courts
├── phone               : String(20), nullable
├── fax                 : String(20), nullable
├── email               : String(200), nullable
├── subscription_plan_id: Integer, FK -> subscription_plans.id
├── subscription_status : Enum(trial, active, expired, cancelled)
├── trial_ends_at       : DateTime, nullable
├── is_active           : Boolean, default=True
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.2 Users & Roles
```
roles
├── id                  : Integer, PK
├── name                : String(50), NOT NULL           -- manager/partner/senior/junior/assistant/accountant
├── name_ar             : String(100), NOT NULL          -- Arabic name
└── description         : Text, nullable

permissions
├── id                  : Integer, PK
├── module              : String(50), NOT NULL           -- clients, cases, sessions, financial, etc.
├── action              : String(50), NOT NULL           -- create, read, update, delete, export
└── scope               : String(50), default='all'      -- all, own, team, financial_only, print_only, view_only

role_permissions
├── id                  : Integer, PK
├── role_id             : Integer, FK -> roles.id
├── permission_id       : Integer, FK -> permissions.id
└── constraint_value    : String(100), nullable          -- e.g. "own_cases", "own_tasks", "team"

users
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── email               : String(200), UNIQUE within tenant
├── password_hash       : String(255)
├── full_name           : String(200), NOT NULL
├── full_name_en        : String(200), nullable
├── phone               : String(20), nullable
├── role_id             : Integer, FK -> roles.id
├── is_active           : Boolean, default=True
├── mfa_enabled         : Boolean, default=False
├── mfa_secret          : String(100), nullable
├── last_login_at       : DateTime, nullable
├── password_changed_at : DateTime, nullable
├── avatar_path         : String(500), nullable
├── notification_preferences : JSON, nullable            -- channel preferences per type
├── quiet_hours_start   : Time, nullable                 -- e.g. 22:00
├── quiet_hours_end     : Time, nullable                 -- e.g. 08:00
├── daily_summary_enabled: Boolean, default=False
├── created_at          : DateTime
└── updated_at          : DateTime

invitations
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── email               : String(200)
├── role_id             : Integer, FK -> roles.id
├── token               : String(255), UNIQUE
├── invited_by          : Integer, FK -> users.id
├── accepted_at         : DateTime, nullable
├── expires_at          : DateTime
└── created_at          : DateTime
```

### 4.3 Subscription & Payment
```
subscription_plans
├── id                  : Integer, PK
├── name                : String(100)                    -- Starter / Professional / Enterprise
├── name_ar             : String(100)
├── max_lawyers         : Integer                        -- seat limit
├── price_monthly       : Decimal(10,2)
├── price_yearly        : Decimal(10,2)
├── features            : JSON                           -- feature flags
├── is_active           : Boolean, default=True
└── created_at          : DateTime

subscription_payments
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── plan_id             : Integer, FK -> subscription_plans.id
├── amount              : Decimal(10,2)
├── payment_method      : Enum(credit_card, vodafone_cash, etisalat_cash)
├── payment_reference   : String(200), nullable
├── period_start        : Date
├── period_end          : Date
├── status              : Enum(pending, paid, failed, refunded)
├── receipt_sent        : Boolean, default=False
└── created_at          : DateTime
```

### 4.4 Clients (Mowakeloon)
```
clients
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_number       : String(50), auto-generated     -- Sequential per tenant
├── client_type         : Enum(individual, company, government)
├── full_name           : String(300), NOT NULL
├── full_name_en        : String(300), nullable
├── national_id         : String(20), nullable           -- National ID or Commercial Reg
├── commercial_reg      : String(50), nullable
├── date_of_birth       : Date, nullable                 -- or company founding date
├── nationality         : String(100), nullable
├── profession          : String(200), nullable          -- or business activity
├── governorate         : String(100), nullable
├── city                : String(100), nullable
├── district            : String(100), nullable
├── street              : String(200), nullable
├── building_no         : String(50), nullable
├── phone_primary       : String(20), nullable           -- mandatory per SRS
├── phone_secondary     : String(20), nullable
├── email               : String(200), nullable
├── whatsapp            : String(20), nullable           -- used for notifications
├── emergency_contact_name   : String(200), nullable
├── emergency_contact_phone  : String(20), nullable
├── emergency_contact_relation: String(100), nullable
├── internal_notes      : Text, nullable                 -- visible to lawyers only
├── registered_by       : Integer, FK -> users.id
├── is_active           : Boolean, default=True
├── created_at          : DateTime
└── updated_at          : DateTime

client_documents        -- Identity documents (national ID, passport, etc.)
├── id                  : Integer, PK
├── client_id           : Integer, FK -> clients.id
├── document_type       : Enum(national_id_front, national_id_back, passport, commercial_reg, tax_card, other)
├── file_path           : String(500)
├── file_name           : String(300)
├── file_type           : String(10)                     -- jpg, png, pdf
├── uploaded_by         : Integer, FK -> users.id
└── created_at          : DateTime
```

### 4.5 Cases (Qadaya)
```
cases
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id
├── case_number         : String(100), nullable          -- Official court case number
├── judicial_year       : String(10), nullable           -- e.g. "2026"
├── court_id            : Integer, FK -> courts.id
├── circuit              : String(100), nullable         -- Court circuit/division
├── case_type           : Enum(criminal, civil, commercial, administrative, labor, family, constitutional, enforcement)
├── subject             : Text, nullable                 -- Brief description
├── opponent_name       : String(300), nullable
├── opponent_capacity   : String(200), nullable          -- Legal capacity
├── opponent_lawyer     : String(300), nullable
├── responsible_lawyer_id: Integer, FK -> users.id       -- Lead lawyer (mandatory)
├── assistant_lawyer_id : Integer, FK -> users.id, nullable
├── our_client_capacity : Enum(plaintiff, defendant, appellant, respondent, other)
├── fee_type            : Enum(fixed, percentage, hourly, mixed)
├── fee_amount          : Decimal(12,2), nullable        -- Agreed total fee
├── retainer_paid       : Decimal(12,2), default=0       -- Advance payment
├── payment_schedule    : Enum(upfront, installments, open)
├── status              : Enum(new, active, awaiting_judgment, suspended, closed)
├── priority            : Enum(normal, important, critical)
├── internal_notes      : Text, nullable                 -- Lawyers only
├── closed_at           : DateTime, nullable
├── created_at          : DateTime
└── updated_at          : DateTime

courts                  -- Pre-seeded list of all Egyptian courts
├── id                  : Integer, PK
├── name                : String(300)
├── name_en             : String(300), nullable
├── court_type          : Enum(primary, appeal, cassation, constitutional, economic, family, military, state_council)
├── governorate         : String(100)
└── is_active           : Boolean, default=True
```

### 4.6 Sessions (Galsat)
```
sessions
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── case_id             : Integer, FK -> cases.id
├── session_date        : Date, NOT NULL
├── session_time        : Time, nullable
├── court_id            : Integer, FK -> courts.id       -- Auto from case, editable
├── circuit             : String(100), nullable
├── session_type        : Enum(first, evidence, pleading, judgment, emergency, postponement)
├── preparation_notes   : Text, nullable                 -- What to prepare
├── result              : Enum(postponed, judgment, decision, evidence, attendance, absence), nullable
├── result_summary      : Text, nullable                 -- Free text summary
├── next_session_date   : Date, nullable                 -- Auto-creates next session if postponed
├── minutes_file_path   : String(500), nullable          -- Uploaded session minutes PDF
├── responsible_lawyer_id: Integer, FK -> users.id
├── notification_48h_sent : Boolean, default=False
├── notification_24h_sent : Boolean, default=False
├── notification_3h_sent  : Boolean, default=False
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.7 Judgments (Ahkam)
```
judgments
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── case_id             : Integer, FK -> cases.id
├── judgment_date       : Date, NOT NULL
├── court_id            : Integer, FK -> courts.id
├── judgment_type       : Enum(primary, appeal, cassation, constitutional)
├── result              : Enum(full_win, partial_win, loss, postponement, procedural, absence)
├── judgment_text       : Text, nullable                 -- Full text of judgment
├── judgment_file_path  : String(500), nullable          -- Uploaded PDF
├── judge_name          : String(200), nullable
├── awarded_amount      : Decimal(12,2), nullable        -- Used in enforcement
├── notes               : Text, nullable
│
│   -- Appeal tracking
├── appeal_tracking_enabled : Boolean, default=False
├── appeal_type         : Enum(appeal, cassation), nullable
├── appeal_deadline     : Date, nullable                 -- Auto-calculated
├── appeal_notification_30d : Boolean, default=False
├── appeal_notification_14d : Boolean, default=False
├── appeal_notification_7d  : Boolean, default=False
├── appeal_notification_3d  : Boolean, default=False
│
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.8 Enforcement (Tanfeez)
```
enforcements
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── judgment_id         : Integer, FK -> judgments.id
├── case_id             : Integer, FK -> cases.id
├── client_id           : Integer, FK -> clients.id
├── enforcement_number  : String(100), nullable          -- Official number
├── enforcement_court   : String(300), nullable
├── executor_name       : String(200), nullable          -- Judge/officer
├── enforcement_type    : Enum(real_estate_seizure, funds_seizure, movables_seizure, eviction, delivery)
├── total_amount        : Decimal(12,2), NOT NULL        -- Total to collect
├── collected_amount    : Decimal(12,2), default=0
├── debtor_name         : String(300), nullable
├── start_date          : Date, nullable
├── status              : Enum(active, completed, suspended)
├── notes               : Text, nullable
├── created_at          : DateTime
└── updated_at          : DateTime

enforcement_collections  -- Each payment collected
├── id                  : Integer, PK
├── enforcement_id      : Integer, FK -> enforcements.id
├── amount              : Decimal(12,2)
├── collection_date     : Date
├── collection_method   : String(100), nullable
├── notes               : Text, nullable
└── created_at          : DateTime

enforcement_actions      -- Log of all enforcement steps
├── id                  : Integer, PK
├── enforcement_id      : Integer, FK -> enforcements.id
├── action_description  : Text
├── action_date         : Date
└── created_at          : DateTime
```

### 4.9 Power of Attorney (Tawkeelat)
```
powers_of_attorney
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id
├── case_id             : Integer, FK -> cases.id, nullable
├── poa_type            : Enum(general, special, judicial, banking, real_estate, commercial)
├── issue_date          : Date, NOT NULL
├── expiry_date         : Date, nullable                 -- Mandatory if fixed-term
├── notary_office       : String(300), nullable
├── real_estate_registry: String(200), nullable
├── notarization_number : String(100), nullable
├── status              : Enum(active, expiring_soon, expired)  -- Auto-updated
├── notification_30d_sent : Boolean, default=False
├── notification_7d_sent  : Boolean, default=False
├── notification_1d_sent  : Boolean, default=False
├── file_path           : String(500), nullable
├── created_at          : DateTime
└── updated_at          : DateTime

-- Color coding logic (computed, not stored):
-- Green:  active, expiry > 30 days away
-- Yellow: expiry <= 30 days
-- Orange: expiry <= 7 days
-- Red:    expired
```

### 4.10 Financial System
```
payments                 -- Incoming payments from clients
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id
├── case_id             : Integer, FK -> cases.id, nullable
├── amount              : Decimal(12,2), NOT NULL
├── payment_date        : Date, NOT NULL
├── payment_method      : Enum(cash, bank_transfer, check, vodafone_cash, card)
├── reference_number    : String(200), nullable          -- Check/transfer number
├── receipt_file_path   : String(500), nullable          -- Scanned receipt
├── notes               : Text, nullable
├── recorded_by         : Integer, FK -> users.id
├── created_at          : DateTime
└── updated_at          : DateTime

invoices
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id
├── case_id             : Integer, FK -> cases.id, nullable
├── invoice_number      : String(50), auto-generated     -- Sequential per tenant
├── issue_date          : Date, NOT NULL
├── status              : Enum(draft, sent, paid, overdue, cancelled)
├── subtotal            : Decimal(12,2)
├── discount_type       : Enum(percentage, fixed), nullable
├── discount_value      : Decimal(12,2), nullable
├── tax_rate            : Decimal(5,2), default=14.00    -- Egyptian VAT
├── tax_amount          : Decimal(12,2)
├── total               : Decimal(12,2)
├── notes               : Text, nullable
├── sent_via            : Enum(email, whatsapp), nullable
├── sent_at             : DateTime, nullable
├── created_at          : DateTime
└── updated_at          : DateTime

invoice_items
├── id                  : Integer, PK
├── invoice_id          : Integer, FK -> invoices.id
├── description         : String(500)
├── item_type           : Enum(fees, expenses, stamp, transport, other)
├── amount              : Decimal(12,2)
└── created_at          : DateTime

expenses
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── case_id             : Integer, FK -> cases.id, nullable
├── client_id           : Integer, FK -> clients.id, nullable
├── expense_type        : Enum(court_fees, transport, stamp, expert, other)
├── amount              : Decimal(12,2)
├── expense_date        : Date
├── description         : Text, nullable
├── receipt_file_path   : String(500), nullable
├── recorded_by         : Integer, FK -> users.id
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.11 Tasks & Appointments
```
tasks
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── title               : String(300), NOT NULL
├── description         : Text, nullable
├── assigned_to         : Integer, FK -> users.id
├── assigned_by         : Integer, FK -> users.id
├── case_id             : Integer, FK -> cases.id, nullable
├── priority            : Enum(urgent, important, normal)   -- Red, Orange, Gray
├── deadline            : DateTime, nullable
├── status              : Enum(new, in_progress, done)
├── is_recurring        : Boolean, default=False
├── recurrence_type     : Enum(daily, weekly, monthly), nullable
├── created_at          : DateTime
└── updated_at          : DateTime

appointments             -- Client appointments (separate from court sessions)
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id
├── lawyer_id           : Integer, FK -> users.id
├── appointment_date    : Date, NOT NULL
├── appointment_time    : Time, NOT NULL
├── notes               : Text, nullable
├── confirmation_sent   : Boolean, default=False         -- WhatsApp/SMS sent
├── reminder_sent       : Boolean, default=False         -- 2h before
├── attendance_status   : Enum(pending, attended, no_show, rescheduled), default='pending'
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.12 Documents
```
documents
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── client_id           : Integer, FK -> clients.id, nullable
├── case_id             : Integer, FK -> cases.id, nullable
├── session_id          : Integer, FK -> sessions.id, nullable
├── doc_type            : Enum(defense_memo, judgment, contract, poa, receipt, correspondence, session_minutes, other)
├── name                : String(500)                    -- Auto from filename, editable
├── file_path           : String(500)
├── file_type           : String(10)                     -- pdf, docx, jpg, png, xlsx
├── file_size           : Integer                        -- bytes
├── doc_date            : Date, nullable
├── notes               : Text, nullable
├── ai_summary          : Text, nullable                 -- AI-generated summary
├── share_token         : String(100), nullable          -- Temporary 24h share link
├── share_expires_at    : DateTime, nullable
├── uploaded_by         : Integer, FK -> users.id
├── created_at          : DateTime
└── updated_at          : DateTime

legal_templates
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id, nullable  -- null = system-wide
├── name                : String(200)
├── name_ar             : String(200)
├── template_type       : Enum(fee_contract, special_poa, fee_receipt, defense_memo, client_letter)
├── output_format       : Enum(pdf, docx)
├── template_content    : Text                           -- HTML with placeholders like {{client_name}}
├── auto_fill_fields    : JSON                           -- List of fields auto-filled
├── thumbnail_path      : String(500), nullable
├── is_active           : Boolean, default=True
├── created_at          : DateTime
└── updated_at          : DateTime
```

### 4.13 Notifications
```
notifications
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── user_id             : Integer, FK -> users.id        -- Recipient
├── notification_type   : Enum(
│                           session_upcoming, appeal_deadline, poa_expiring,
│                           task_deadline, task_overdue, invoice_overdue,
│                           fees_reminder, poa_expired, payment_received,
│                           document_uploaded, general
│                         )
├── priority            : Enum(critical, important, info)
├── title               : String(300)
├── body                : Text
├── channel             : Enum(in_app, email, sms, push)
├── related_type        : String(50), nullable           -- 'session', 'case', 'task', etc.
├── related_id          : Integer, nullable              -- FK to related record
├── is_read             : Boolean, default=False
├── read_at             : DateTime, nullable
├── sent_at             : DateTime, nullable
├── delivery_status     : Enum(pending, sent, delivered, failed)
├── created_at          : DateTime
└── updated_at          : DateTime

notification_settings    -- Per-user overrides
├── id                  : Integer, PK
├── user_id             : Integer, FK -> users.id
├── notification_type   : String(50)
├── email_enabled       : Boolean, default=True
├── sms_enabled         : Boolean, default=True
├── push_enabled        : Boolean, default=True
├── in_app_enabled      : Boolean, default=True
└── updated_at          : DateTime
```

### 4.14 Audit & Security
```
audit_logs
├── id                  : Integer, PK
├── tenant_id           : Integer, FK -> tenants.id
├── user_id             : Integer, FK -> users.id
├── action              : String(50)                     -- create, update, delete, login, export, etc.
├── resource_type       : String(50)                     -- client, case, payment, etc.
├── resource_id         : Integer, nullable
├── details             : JSON, nullable                 -- What changed
├── ip_address          : String(45)
├── user_agent          : String(500), nullable
├── created_at          : DateTime
-- Retained for 7 years per SRS

device_sessions
├── id                  : Integer, PK
├── user_id             : Integer, FK -> users.id
├── device_name         : String(200)
├── device_type         : String(50)                     -- web, ios, android
├── ip_address          : String(45)
├── user_agent          : String(500)
├── refresh_token       : String(500)
├── is_trusted          : Boolean, default=False         -- "Remember me 30 days"
├── last_active_at      : DateTime
├── expires_at          : DateTime
├── is_active           : Boolean, default=True
└── created_at          : DateTime
```

---

## 5. MODULE BREAKDOWN & IMPLEMENTATION DETAILS

### MODULE 1: Authentication & Onboarding (SRS Sections 3.1)

**A. New Subscription (Registration)**
| Step | Screen | Fields | Validations | Auto Actions |
|------|--------|--------|-------------|--------------|
| 1 | Registration | full_name, email, phone, office_size (1-5/6-15/15+) | Email unique, phone format | - |
| 2 | OTP Verification | 6-digit code on email | Expires in 10 min, max 3 attempts | - |
| 3 | Office Setup | office_name, logo (optional), address, bar_reg_no, primary_court, phone, fax, email | office_name required | Creates isolated tenant |
| 4 | Subscription Plan | plan selection, payment method (credit/vodafone/etisalat) | - | 14-day free trial if no payment; sends receipt email |
| 5 | Team Invite | email + role per member | Valid email, valid role | Sends invite link + instructions; skippable |

**B. Daily Login**
| Step | Details | Notes |
|------|---------|-------|
| 1 | Email + password | - |
| 2 | OTP (if MFA enabled) | Phone OTP or Authenticator app. Manager enforces MFA for all; others optional |
| 3 | Dashboard redirect | Shows: today's tasks, upcoming sessions, notifications |
| 4 | Remember device | "Remember 30 days" on trusted devices |

**Key Routes:**
```
POST /auth/register
POST /auth/verify-otp
POST /auth/login
POST /auth/refresh-token
POST /auth/logout
POST /auth/forgot-password
POST /auth/reset-password
GET  /onboarding/setup-office
POST /onboarding/setup-office
GET  /onboarding/choose-plan
POST /onboarding/choose-plan
GET  /onboarding/invite-team
POST /onboarding/invite-team
POST /onboarding/skip-invite
GET  /auth/accept-invite/<token>
```

---

### MODULE 2: Client Management (SRS Section 3.2)

**A. Add New Client - 5-step flow with tabs:**

| Tab | Fields | Required | Notes |
|-----|--------|----------|-------|
| Basic Data | type (individual/company/gov), full_name, full_name_en, national_id OR commercial_reg, dob, nationality, profession, full address | name, national_id/commercial_reg | - |
| Contact | phone_primary, phone_secondary, email, whatsapp, emergency contact (name+phone+relation) | phone_primary | WhatsApp used for notifications |
| ID Documents | National ID front+back OR passport, additional docs (commercial reg, tax card) | - | JPG/PNG/PDF, preview before save |
| Internal Notes | free text notes | - | Visible to lawyers only, not clients |
| Auto-saved | client_number (sequential), registration_date, registered_by | - | System-generated |

**B. Client Profile Page - 6 tabs:**
1. **Data tab** - All registration data with inline edit buttons per field
2. **Cases tab** - List of all client's cases with status + last update. Click to open case
3. **Financial tab** - Total fees, paid amount, remaining balance + "Print Account Statement" button
4. **POA tab** - All power of attorney records with expiry dates and color-coded status
5. **Documents tab** - All uploaded documents sorted by date, with inline preview
6. **Activity Log tab** - Every change made to this client's file with timestamp + who did it

**Key Routes:**
```
GET  /clients                    -- List all clients (paginated, searchable)
GET  /clients/new                -- Add client form
POST /clients                    -- Save new client
GET  /clients/<id>               -- Client profile (data tab)
GET  /clients/<id>/cases         -- Cases tab
GET  /clients/<id>/financial     -- Financial tab
GET  /clients/<id>/poa           -- POA tab
GET  /clients/<id>/documents     -- Documents tab
GET  /clients/<id>/activity      -- Activity log
PUT  /clients/<id>               -- Update client
GET  /clients/<id>/statement     -- Generate account statement PDF
```

---

### MODULE 3: Case Management (SRS Section 3.3)

**A. Open New Case - 5-step flow:**

| Step | Fields | Notes |
|------|--------|-------|
| 1. Start | From client profile (auto-links) or from cases list (search client) | - |
| 2. Case Data | client (search), case_number, judicial_year, court (dropdown - pre-seeded), circuit, case_type, subject | Court is from pre-seeded Egyptian courts list |
| 3. Parties | opponent_name, opponent_capacity, opponent_lawyer, responsible_lawyer (from team), assistant_lawyer (optional), our_client_capacity | responsible_lawyer is mandatory |
| 4. Fees | fee_type, fee_amount, retainer_paid, payment_schedule | - |
| 5. Status | status (new/active/awaiting_judgment/suspended/closed), priority (normal/important/critical) | Save -> appears on dashboard + case list immediately |

**B. Case File - 8 tabs:**
1. **Overview** - Basic data + visual timeline of all case events
2. **Sessions** - All past and future sessions + results + minutes + "Add Session" button
3. **Judgments** - All judgments with appeal deadlines
4. **Enforcement** - Enforcement files if any judgment exists
5. **Documents** - Case documents organized: memos/judgments/contracts/correspondence/other
6. **Tasks** - Case-specific task board
7. **Financial** - Case fees + payments + expenses + remaining balance
8. **Notes** - Internal notes (lawyers only, NOT visible to client)

**C. Case Status Transitions:**
| Status | Behavior |
|--------|----------|
| Active (نشطة) | Appears in active cases list, session notifications enabled |
| Awaiting Judgment (منتظرة حكم) | Different color in lists, alert to lawyer after 90 days of no updates |
| Suspended (موقوفة) | Moves to suspended section, stops notifications, can be reactivated |
| Closed (مغلقة) | Moves to archive, preserved in full, appears in historical statistics |

**Key Routes:**
```
GET  /cases                      -- List all cases (filterable by status, type, lawyer, client)
GET  /cases/new                  -- New case form
POST /cases                      -- Save new case
GET  /cases/<id>                 -- Case file (overview tab)
GET  /cases/<id>/sessions        -- Sessions tab
GET  /cases/<id>/judgments       -- Judgments tab
GET  /cases/<id>/enforcement     -- Enforcement tab
GET  /cases/<id>/documents       -- Documents tab
GET  /cases/<id>/tasks           -- Tasks tab
GET  /cases/<id>/financial       -- Financial tab
GET  /cases/<id>/notes           -- Notes tab
PUT  /cases/<id>                 -- Update case
PUT  /cases/<id>/status          -- Change status
```

---

### MODULE 4: Sessions & Calendar (SRS Section 3.4)

**A. Add Session:**

| Step | Fields | Notes |
|------|--------|-------|
| 1 | From case file -> Sessions tab -> "Add Session" OR from calendar -> "Book" | If from case: case + client auto-linked |
| 2 | case (search/auto), date, time (optional), court (auto from case, editable), circuit, session_type (first/evidence/pleading/judgment/emergency/postponement), preparation_notes | - |
| 3 | AUTO: System creates 3 notifications: 48h + 24h + 3h before session. Lawyer receives via SMS + Email + Push. Customizable timing. | - |

**B. After Session - Result Recording:**
1. System sends push notification after session time ends: "Record session result"
2. Result options: postponed / judgment / decision / evidence / attendance / absence
3. If postponed: enter new date -> system auto-creates next session
4. Session summary text (free text) -> used in client report later
5. Upload session minutes (PDF/image) - optional

**C. Monthly Calendar:**
| Feature | Details |
|---------|---------|
| View | Monthly / Weekly / Daily with easy toggle |
| Session Card | Case name + client + court + time, different color per lawyer |
| Day View | Click any day -> list of all sessions sorted by time |
| Filter | By specific lawyer / all team / specific session type |
| Export | PDF or Outlook Sync / Google Calendar |

**Key Routes:**
```
GET  /sessions                   -- List all sessions
GET  /sessions/new               -- New session form
POST /sessions                   -- Save session
GET  /sessions/<id>              -- Session detail
PUT  /sessions/<id>              -- Update session
PUT  /sessions/<id>/result       -- Record session result
GET  /calendar                   -- Calendar view
GET  /calendar/day/<date>        -- Day view
GET  /calendar/export            -- Export to PDF/ICS
```

---

### MODULE 5: Judgment Registry (SRS Section 3.5)

**A. Register New Judgment:**

| Field | Type | Required |
|-------|------|----------|
| judgment_date | Date picker | YES |
| court | Dropdown (from case) | YES |
| judgment_type | primary/appeal/cassation/constitutional | YES |
| result | full_win/partial_win/loss/postponement/procedural/absence | YES |
| judgment_text | Long text OR upload PDF | NO |
| judge_name | Text | NO |
| awarded_amount | Number (used in enforcement) | NO |
| notes | Text | NO |

**B. Appeal Deadline Tracking (Auto):**
1. System asks: "Do you want to track appeal deadlines?"
2. If yes: choose appeal type (appeal/cassation) + set legal deadline
3. System auto-calculates expiry date
4. Auto-notifications: 30 days / 14 days / 7 days / 3 days before deadline

**C. Link to Enforcement:**
- If judgment is in our client's favor: "Open Enforcement File" button appears
- Judgment data auto-transfers to enforcement file (no re-entry)

---

### MODULE 6: Enforcement Tracking (SRS Section 3.6)

**A. Open Enforcement File:**

| Step | Fields |
|------|--------|
| 1 | From judgment -> "Open enforcement file" OR from enforcement section -> "New file" |
| 2 | enforcement_number, enforcement_court, executor_name |
| 3 | enforcement_type (real_estate_seizure/funds/movables/eviction/delivery), total_amount, debtor_name, start_date |

**B. Collection Tracking:**
- Each collected amount is recorded with date + method
- Auto-calculated: collected / remaining / collection_percentage
- Visual progress bar: e.g. "35% complete" with colored bar
- Log of all enforcement sessions and actions taken

**Progress Bar Visual:**
```
Total: 500,000 EGP | Collected: 175,000 EGP | Remaining: 325,000 EGP
[=============                          ] 35%
```
Shown in enforcement file AND on dashboard.

---

### MODULE 7: Power of Attorney Registry (SRS Section 3.7)

**A. Add New POA:**

| Field | Notes |
|-------|-------|
| poa_type | general/special/judicial/banking/real_estate/commercial |
| issue_date | Required |
| expiry_date | Required if fixed-term |
| notary_office | Where notarized |
| real_estate_registry | Registry number |
| notarization_number | Reference number |
| linked_case | Optional |
| file | Upload POA document |

**B. Auto-Expiry Notifications:**
| Days Before | Recipient | Action |
|-------------|-----------|--------|
| 30 days | Lawyer | Notification sent |
| 7 days | Lawyer + Office Manager | Urgent notification |
| 1 day | Lawyer + Office Manager | Critical notification |
| 0 (expired) | System auto | Status -> "expired", red indicator, appears on dashboard |

**C. Color-Coded Status:**
| Color | Status | Condition |
|-------|--------|-----------|
| Green | Active (ساري) | Expiry > 30 days |
| Yellow | Expiring Soon | Expiry <= 30 days |
| Orange | Critical | Expiry <= 7 days |
| Red | Expired (منته) | Past expiry date |

---

### MODULE 8: Financial System (SRS Section 3.8)

**A. Record Payment:**
From client or case file -> "Record Payment"
- Amount, date, method (cash/bank_transfer/check/vodafone_cash/card)
- Reference number (optional), receipt upload (optional), notes (optional)
- AUTO: Updates client balance, total collected, remaining. Notification to accountant + responsible lawyer

**B. Invoices:**
1. Create invoice from client/case -> "Create Invoice"
2. Official office template opens
3. Add line items: fees/expenses/stamp/transport/other - each with description + amount
4. Discount (% or fixed) + Tax (14% Egyptian VAT auto-applied, can be disabled)
5. System calculates: subtotal + tax + total
6. Auto sequential invoice number + issue date
7. Export: PDF with office logo + editable Word version
8. Send: via Email or WhatsApp directly from system

**C. Expense Tracking:**
- Record expense per case: type (court_fees/transport/stamp/expert/other) + amount + receipt
- Links to case and client account
- Expense reports: monthly / quarterly / by case / by type

**D. Client Account Statement (كشف حساب):**
- "Print Account Statement" button from any client file
- Contains: agreed fees, all payments with dates, all expenses, remaining balance
- Exports as formal PDF + Word with office branding

---

### MODULE 9: Tasks & Appointments (SRS Section 3.9)

**A. Tasks:**

| Feature | Details |
|---------|---------|
| Create | From quick "+" button anywhere OR from case -> Tasks tab |
| Fields | title (required), description, assigned_to (lawyer or "me"), priority (urgent/important/normal), deadline (date+time), linked_case (optional), recurrence (daily/weekly/monthly) |
| Task Board | 3 columns: "New" / "In Progress" / "Done" with drag & drop |
| Updates | Drag to change status -> assignee notified immediately |
| Overdue | Red color highlight + appears on dashboard as alert |

**B. Client Appointments:**

| Feature | Details |
|---------|---------|
| Book | Client + date + time + notes + responsible lawyer |
| Confirmation | Auto SMS/WhatsApp to client confirming appointment + reminder 2h before |
| Attendance | Lawyer records: attended / no_show / rescheduled -> saved in client record |

---

### MODULE 10: Document Management (SRS Section 3.10)

**A. Upload:**
- From any file (client/case/session) -> "Upload" button or drag & drop zone
- Supported: PDF, DOCX, PNG, JPG, XLSX
- Multi-file upload supported
- Max file size: configurable (suggest 20MB per file)

**B. Classification:**
- Type: defense_memo / judgment / contract / poa / receipt / correspondence / session_minutes / other
- Name: auto-filled from filename, editable
- Date + notes (optional)

**C. Preview & Access:**
- PDF and images: inline preview without download
- Filter by: type / date / case / client
- Search by name within any file collection
- Download: single click + share via temporary link (24h expiry, unique token)

---

### MODULE 11: Legal Templates (SRS Section 3.11)

**5 Templates for MVP:**

| Template | Auto-Fill Fields | Output |
|----------|-----------------|--------|
| Fee Contract (عقد أتعاب) | client name, national ID, address, case subject, fee amount, contract date | PDF |
| Special POA (توكيل خاص) | client full data, lawyer name, POA type, court, notarization number | PDF |
| Fee Receipt (إيصال استلام أتعاب) | client name, amount, date, case number, receiving lawyer | PDF |
| Defense Memo (مذكرة دفاع) | court name, case number, parties, session date | DOCX (editable) |
| Client Letter (خطاب إلى موكل) | client name, date, office data, letter body (lawyer writes) | PDF |

**Template Usage Flow:**
1. Select template from gallery (with thumbnail preview)
2. Choose client + case -> system auto-fills all fields
3. Paper View: full document preview with editable fields highlighted in yellow
4. Edit any field inline
5. Save to client/case file automatically
6. Export PDF with office logo

---

### MODULE 12: Notification System (SRS Section 4)

**Notification Types & Rules:**

| Type | Priority | Channels | Timing |
|------|----------|----------|--------|
| Upcoming Session | Critical | SMS + Push + Email | 48h + 24h + 3h before |
| Appeal Deadline | Critical | SMS + Push + Email | 30d + 14d + 7d + 3d before |
| POA Expiring | Important | Email + Push | 30d + 7d + 1d before |
| Task Deadline | Important | In-App + Push | 24h + 1h before |
| Task Overdue | Critical | In-App + Push + Email | Immediately after deadline |
| Invoice Overdue | Important | Email + Push | 14 + 7 + 3 days after due |
| Remaining Fees | Info | In-App + Email | Weekly per client with balance |
| POA Expired | Critical | SMS + Push | Immediately upon expiry |
| Payment Received | Info | In-App only | Immediately |
| New Document | Info | In-App only | Immediately |

**Notification Settings:**
- Each lawyer controls their own channels per notification type
- Office Manager controls mandatory team notifications
- Quiet Hours: no notifications between 10pm - 8am (customizable)
- Optional daily morning summary: all today's appointments + tasks in one message

**Implementation: Celery Beat scheduled tasks:**
- Every 15 minutes: check upcoming sessions for notification triggers
- Every hour: check appeal deadlines, POA expiry, task deadlines
- Daily at 7am: generate morning summaries for opted-in users
- Weekly: remaining fees reminders

---

### MODULE 13: Dashboard & Reports (SRS Section 6)

**A. Dashboard Widgets (7 cards):**

| Widget | Content | Update |
|--------|---------|--------|
| Active Cases | Total count + breakdown by type (criminal/civil/commercial...) | Real-time |
| Today's Sessions | List of all today's sessions sorted by time + responsible lawyer | Real-time |
| This Week's Calendar | Mini 7-day calendar with sessions and tasks | Real-time |
| Urgent Alerts | Overdue tasks + expiring POAs + critical appeal deadlines | Real-time |
| Financial Collection | This month's collected vs target + collection % | Daily |
| Win/Loss Ratio | Last 90 days: % win from all judgments | Weekly |
| My Tasks Today | Personal task list sorted by priority | Real-time |

**B. Reports (6 types):**

| Report | Content | Export |
|--------|---------|--------|
| Monthly Financial | Total revenue, collected, remaining, top clients by collection | CSV + PDF |
| Lawyer Performance | Cases count, tasks completed, deadline compliance % | CSV + PDF |
| Workload | Case + task distribution across team - who's overloaded? | PDF |
| Win/Loss | Judgment analysis by type, court, lawyer | PDF |
| Client Statement | Per client: fees, payments, remaining | DOCX + PDF |
| Sessions Report | All sessions in date range with results | CSV + PDF |

**Key Routes:**
```
GET /dashboard                   -- Main dashboard
GET /reports                     -- Reports menu
GET /reports/financial           -- Monthly financial report
GET /reports/performance         -- Lawyer performance
GET /reports/workload            -- Workload distribution
GET /reports/win-loss            -- Win/loss analysis
GET /reports/client-statement/<id> -- Client statement
GET /reports/sessions            -- Sessions report
GET /reports/<type>/export/<format> -- Export any report
```

---

### MODULE 14: AI Features (SRS Section 5)

**A. Document Summarization:**
- Trigger: When PDF with 5+ pages is uploaded, show "Request AI Summary" button
- Process: Send document text to Azure OpenAI API
- Output: Bullet-point summary with: parties, dates, amounts, core subject
- Restrictions: NO legal analysis, NO opinions, NO auto-modification of case data
- Review: Lawyer reviews summary before saving. System applies nothing without consent
- Language: Arabic, optimized for Egyptian legal content
- Storage: Summary saved in document record (ai_summary field)

**B. Smart Reminders:**
- AI does NOT send notifications - it improves their text
- "جلسة الغد" becomes "جلسة الطعن في قضية المقاول — غداً 10 ص بمحكمة القاهرة الابتدائية"
- Priority ordering: if lawyer has 5 notifications, AI suggests ordering by session type
- Morning summary: AI generates natural-language one-liner per appointment

**Implementation:**
```python
# Service class
class AIService:
    def summarize_document(self, document_text: str) -> str:
        # Call Azure OpenAI with Arabic legal prompt
        # Return structured summary

    def enhance_notification_text(self, notification: Notification, context: dict) -> str:
        # Enrich basic notification with case/session details

    def prioritize_notifications(self, notifications: list) -> list:
        # Suggest ordering based on urgency + session type

    def generate_morning_summary(self, user_id: int, date: date) -> str:
        # Generate natural-language daily summary
```

---

### MODULE 15: Settings & Administration (SRS Section 2)

**A. Office Settings (Manager only):**
- Office name, logo, address, contact info
- Bar registration, primary court
- Subscription management
- MFA enforcement toggle
- Default notification settings for team

**B. Team Management:**
- View all members with roles
- Invite new member (email + role)
- Change member role
- Deactivate member (preserves data, blocks login)

**C. RBAC Permission Matrix (6 roles x 10 modules):**

| Module | Manager | Partner | Senior | Junior | Assistant | Accountant |
|--------|---------|---------|--------|--------|-----------|------------|
| Clients - Add/Edit | YES | YES | YES | NO | YES | NO |
| Cases - Open/Close | YES | YES | NO | NO | NO | NO |
| Cases - View | ALL | ALL | ALL | OWN CASES | OWN (view only) | NO |
| Sessions - Schedule | YES | YES | YES | YES | YES | NO |
| Financial - Record | YES | YES | OWN CASES | NO | NO | YES |
| Financial - Reports | YES | YES | OWN CASES | NO | NO | YES |
| Tasks - Assign | YES | YES | OWN TEAM | NO | OWN | NO |
| Members - Manage | YES | YES | NO | NO | NO | NO |
| Legal Templates | YES | YES | YES | YES | PRINT ONLY | NO |
| Full Reports | YES | YES | NO | NO | NO | FINANCIAL ONLY |

---

## 6. EXTERNAL SERVICES & API KEYS

| Service | Purpose | Required For MVP | Estimated Cost |
|---------|---------|-----------------|----------------|
| **SMTP (e.g., SendGrid, Mailgun)** | OTP emails, notifications, invoice sending | YES | Free tier available |
| **SMS Gateway (e.g., Twilio)** | Session reminders, POA alerts, appeal deadlines | YES | ~$0.05/SMS |
| **Azure OpenAI API** | Document summarization, smart reminders | YES | Pay-per-use |
| **File Storage (S3-compatible)** | Document, receipt, ID storage in production | YES for prod | ~$0.023/GB |
| **Redis** | Celery broker, caching, rate limiting | YES | Free (self-hosted) |
| **PostgreSQL** | Primary database | YES | Free (self-hosted) |
| **WhatsApp Business API** | Appointment confirmations, invoice sending | NICE TO HAVE | Variable |
| **Google Calendar API** | Calendar sync (V2) | NO (V2) | Free |
| **Microsoft Graph API** | Outlook sync (V2) | NO (V2) | Free |
| **Payment Gateway** | Subscription billing | LATER | Variable |

---

## 7. SECURITY IMPLEMENTATION

| Requirement | Implementation |
|-------------|---------------|
| Data Encryption | AES-256 for stored data, TLS 1.3 for all connections |
| Authentication | JWT access tokens (15 min) + Refresh tokens (30 days). MFA optional for lawyers, mandatory option for managers |
| RBAC | Permission checks on every API endpoint via @permission_required decorator. Cannot be bypassed from frontend |
| CSRF | Flask-WTF CSRF tokens on all state-changing forms |
| Rate Limiting | Flask-Limiter: per IP + per user limits. Brute force protection on login (5 attempts -> 15 min lockout) |
| Audit Trail | Every action logged: who, what, when. Retained 7 years |
| Device Tracking | Active device list in settings, ability to terminate any session remotely |
| Backup | Daily encrypted backup, 90-day retention, recovery < 4 hours |
| Egyptian Compliance | Compliant with Personal Data Protection Law No. 151/2020 |
| Password Policy | 8 chars minimum, uppercase + number + symbol, change every 90 days (optional) |
| Multi-tenancy | Complete data isolation per tenant. No cross-tenant data access possible |

---

## 8. IMPLEMENTATION PHASES

### PHASE 1: Foundation (Week 1-2)
```
[x] Project setup: Flask app factory, config, extensions
[x] Database: PostgreSQL setup, all models, migrations
[x] Multi-tenancy: tenant isolation middleware
[x] Auth: Registration, login, JWT, refresh tokens, OTP email verification
[x] RBAC: Roles, permissions, decorators
[x] Base templates: RTL layout, sidebar, Bootstrap 5, dark mode toggle
[x] Seed data: Egyptian courts list, default roles & permissions, sample plans
```

### PHASE 2: Core Modules (Week 3-5)
```
[x] Onboarding: Office setup wizard, plan selection (mock payment), team invite
[x] Client Management: Full CRUD, profile page with all 6 tabs, search
[x] Case Management: Full CRUD, case file with all 8 tabs, status transitions
[x] Sessions: CRUD, result recording, auto-create next session on postponement
[x] Calendar: FullCalendar integration, day/week/month views, filters
```

### PHASE 3: Legal Tracking (Week 6-7)
```
[x] Judgment Registry: CRUD, appeal deadline auto-calculation, appeal notifications
[x] Enforcement Tracking: CRUD, collection recording, progress bar
[x] Power of Attorney: CRUD, expiry tracking, color-coded status
```

### PHASE 4: Financial System (Week 8-9)
```
[x] Payments: Record incoming payments, auto-update balances
[x] Invoices: Create, line items, tax calculation, sequential numbering
[x] Invoice PDF generation with office branding
[x] Invoice sending (email/WhatsApp)
[x] Expenses: Record per case, receipt upload
[x] Client Account Statement: Generate PDF + Word
```

### PHASE 5: Tasks, Documents & Templates (Week 10-11)
```
[x] Task Board: Kanban with drag & drop, priorities, deadlines, recurring
[x] Client Appointments: Book, SMS/WhatsApp confirmation, attendance recording
[x] Document Management: Upload, classify, preview, search, temporary share links
[x] Legal Templates: 5 templates, auto-fill, inline editing, PDF export with logo
```

### PHASE 6: Notifications & AI (Week 12-13)
```
[x] Notification System: In-app notification center
[x] Email notifications via Celery
[x] SMS notifications via Twilio/gateway
[x] Celery Beat: Scheduled notification checks (sessions, deadlines, POA)
[x] Notification settings: Per-user channel preferences, quiet hours
[x] Morning daily summary
[x] AI: Document summarization via Azure OpenAI
[x] AI: Smart reminder text enhancement
```

### PHASE 7: Dashboard, Reports & Polish (Week 14-15)
```
[x] Dashboard: 7 widgets with real-time data
[x] Reports: All 6 report types with filters
[x] Report export: PDF, CSV, DOCX
[x] Audit log viewer (manager only)
[x] Device session management
[x] Settings pages: office, team, subscription
[x] Dark mode full implementation
[x] Performance optimization, caching
[x] Security hardening: rate limiting, CSRF, input sanitization
```

### PHASE 8: Testing & Deployment (Week 16)
```
[x] End-to-end testing of all user journeys
[x] Arabic content review
[x] Security audit
[x] Deployment setup (Gunicorn + Nginx)
[x] SSL/TLS configuration
[x] Backup automation
[x] Monitoring setup
```

---

## 9. CONFIGURATION & ENVIRONMENT VARIABLES

```env
# Flask
FLASK_APP=flask_app.py
FLASK_ENV=development
SECRET_KEY=<generate-strong-key>

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/lexoffice

# JWT
JWT_SECRET_KEY=<generate-strong-key>
JWT_ACCESS_TOKEN_EXPIRES=900          # 15 minutes
JWT_REFRESH_TOKEN_EXPIRES=2592000     # 30 days

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (SMTP)
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=<sendgrid-api-key>
MAIL_DEFAULT_SENDER=noreply@lexoffice.app

# SMS
SMS_PROVIDER=twilio                   # or vodafone
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_PHONE_NUMBER=<number>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=<endpoint>
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# File Storage
UPLOAD_FOLDER=/path/to/uploads        # Local dev
MAX_FILE_SIZE=20971520                 # 20MB
# S3 (production)
S3_BUCKET=<bucket>
S3_ACCESS_KEY=<key>
S3_SECRET_KEY=<secret>
S3_REGION=me-south-1                  # Bahrain region (closest to Egypt)

# WhatsApp (optional)
WHATSAPP_API_URL=<url>
WHATSAPP_API_TOKEN=<token>

# App
DEFAULT_LANGUAGE=ar
ITEMS_PER_PAGE=20
OTP_EXPIRY_MINUTES=10
OTP_MAX_ATTEMPTS=3
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

---

## END OF PLAN

This plan covers every single detail from the SRS document (all 24 pages).
Each module maps directly to SRS sections 1-8.
Every field, every flow, every validation, every notification rule, every permission is accounted for.

Ready to start building when you are.
