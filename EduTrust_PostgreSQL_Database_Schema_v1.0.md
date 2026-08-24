# EduTrust Algeria — PostgreSQL Database Schema v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** PostgreSQL Database Schema v1.0  
**Depends on:** EduTrust MVP PRD v1.0  
**DDL file:** `edutrust_schema_v1.sql`  
**Architecture decision:** Modular Monolith + PostgreSQL first, not microservices.

---

## 1. Schema Objective

This schema is designed to support the exact MVP transaction loop:

```text
Parent
   ↓
Student Profile
   ↓
Search / Match
   ↓
Teacher Trust Profile
   ↓
Available Slot
   ↓
Booking
   ↓
Payment
   ↓
Session
   ↓
Session Report
   ↓
Verified Review
   ↓
Repeat Booking
```

The database is not a passive storage layer. It must actively protect core marketplace invariants:

- A parent cannot book for a student they do not own.
- The same availability slot cannot be booked twice.
- Payment amount must match the booking amount.
- Booking, Payment, and Session states are separate.
- Reviews require a completed, paid, verified session.
- Duplicate reviews for the same session are impossible.
- Teachers cannot review themselves.
- Payouts require eligible completed sessions.
- Event Ledger and financial Ledger are append-only.
- Trust Profile metrics are derived data, not teacher-editable fields.
- Student Passport data is built from structured educational events, not AI guesses.

---

## 2. Schema Layers

The schema is organized into 8 product-engineering layers.

```text
1. Identity & Access
   ├── users
   ├── roles
   ├── user_roles
   ├── auth_sessions
   └── security_events

2. Parent & Student
   ├── parent_profiles
   ├── student_profiles
   └── student_permissions

3. Teacher
   ├── teacher_profiles
   ├── teacher_verifications
   ├── verification_documents
   ├── subjects
   ├── academic_levels
   ├── teacher_subjects
   └── teacher_trust_metrics

4. Availability & Marketplace
   ├── availability_rules
   ├── availability_slots
   └── bookings

5. Transaction
   ├── payments
   ├── payouts
   ├── payout_items
   ├── ledger_transactions
   └── ledger_entries

6. Education
   ├── sessions
   ├── session_reports
   └── student_progress_events

7. Trust & Operations
   ├── reviews
   ├── disputes
   └── notifications

8. Audit & Security
   ├── event_ledger
   ├── security_events
   └── verification document metadata
```

> Note: The DDL creation order differs slightly from the conceptual layer order because PostgreSQL foreign keys require referenced tables to exist first.

---

## 3. Core Design Decisions

### 3.1 Modular Monolith, not microservices

All MVP modules share one PostgreSQL database:

```text
Auth / Users / Teachers / Students / Availability / Booking / Payment / Session / Reports / Reviews / Admin
```

Reason:

- Faster MVP delivery
- Fewer distributed consistency problems
- Easier auditability
- Strong transaction integrity around booking/payment/session
- Lower operational complexity

Microservices can be considered later only after the marketplace loop is validated.

---

### 3.2 Booking, Payment, and Session are separate entities

The schema intentionally separates:

```text
bookings.status
payments.status
sessions.status
```

Example:

```text
Booking status: BOOKED
Payment status: CONFIRMED
Session status: SCHEDULED
```

This prevents ambiguous states and makes disputes, refunds, no-shows, and reconciliation much easier.

---

### 3.3 Verified Session Graph is the core asset

Every completed session connects:

```text
Parent → Student → Teacher → Subject → Slot → Booking → Payment → Session → Report → Review
```

This graph later feeds:

- Teacher Trust Profile
- Matching Engine
- Student Passport
- Fraud detection
- Review integrity
- Teacher ranking
- AI learning intelligence

---

### 3.4 Event Ledger from day one

The schema includes an append-only `event_ledger` table for important product events:

```text
USER_REGISTERED
TEACHER_VERIFIED
SLOT_CREATED
BOOKING_CREATED
PAYMENT_INITIATED
PAYMENT_CONFIRMED
SESSION_STARTED
SESSION_COMPLETED
REPORT_CREATED
REVIEW_CREATED
REFUND_ISSUED
DISPUTE_OPENED
DISPUTE_RESOLVED
```

This supports:

- Auditability
- Fraud detection
- Analytics
- Debugging
- Trust engine computation
- AI context later
- Dispute evidence

---

### 3.5 Student Passport is structured-data-first

The schema does **not** make Student Passport dependent on AI.

Correct flow:

```text
Session
   ↓
Session Report
   ↓
Student Progress Events
   ↓
Student Passport
   ↓
AI Insights later
```

The table `student_progress_events` is the structured raw material for the Student Passport.

AI may later summarize and interpret this data, but it should not be the source of truth.

---

## 4. PostgreSQL Extensions

The DDL uses:

```sql
pgcrypto   -- UUID generation via gen_random_uuid()
citext     -- case-insensitive email/phone uniqueness
btree_gist -- exclusion constraint for overlapping availability slots
```

---

## 5. Key Tables by Layer

## 5.1 Identity & Access

### `users`

Stores platform users across all roles.

Important fields:

```text
id
full_name
phone_e164
email
password_hash
status
preferred_locale
last_login_at
deleted_at
created_at
updated_at
```

Important constraints:

- At least phone or email is required.
- Phone and email are unique.
- User status is controlled by enum.

---

### `roles` and `user_roles`

Supports RBAC:

```text
PARENT
TEACHER
ADMIN
OPS
SUPPORT
```

A single user may theoretically have more than one role, but profile creation is guarded:

- `parent_profiles` requires user role `PARENT`.
- `teacher_profiles` requires user role `TEACHER`.

This is enforced by trigger:

```text
require_user_role()
```

---

### `auth_sessions`

Stores authentication session metadata.

Important principle:

> Store hashed refresh tokens only, never raw tokens.

---

### `security_events`

Structured security event table for:

```text
LOGIN_FAILED
TOKEN_REVOKED
PASSWORD_CHANGED
SUSPICIOUS_ACTIVITY
RATE_LIMITED
ADMIN_ACCESS
DOCUMENT_ACCESS
```

Sensitive events should also be mirrored into `event_ledger` when relevant.

---

## 5.2 Parent & Student

### `parent_profiles`

One parent profile per user.

Important constraint:

```text
user_id UNIQUE
```

---

### `student_profiles`

Stores minimized student data.

Important fields:

```text
parent_id
display_name
birth_year
academic_level_id
school_year
primary_goal
preferred_mode
consent_status
status
```

Privacy principle:

> Do not store unnecessary minor data such as national ID, full address, school details, or sensitive information unless legally justified and operationally necessary.

Important constraint:

```sql
UNIQUE (id, parent_id)
```

This allows other tables to enforce that a student belongs to the parent creating the booking.

---

### `student_permissions`

Controls teacher access to student context.

Used for:

- Session-specific student access
- Parent-granted teacher visibility
- Future Student Passport sharing

Important fields:

```text
student_id
parent_id
teacher_id
granted_for_booking_id
scope
starts_at
expires_at
revoked_at
```

Important constraint:

```text
(student_id, parent_id) must exist in student_profiles
```

This prevents permissions from being created for a parent/student mismatch.

---

## 5.3 Teacher

### `teacher_profiles`

Stores teacher profile data, but not trust metrics as manually editable fields.

Important fields:

```text
user_id
public_name
profile_photo_storage_key
bio
methodology
experience_years
languages
teaching_modes
base_wilaya_code
base_commune
service_area
verification_status
listing_status
```

Important principle:

> Teacher cannot directly edit completed sessions, rating, attendance rate, cancellation rate, or Trust Profile metrics.

---

### `teacher_verifications`

Stores teacher verification workflow.

Verification types:

```text
IDENTITY
QUALIFICATION
EXPERIENCE
BACKGROUND_CHECK
```

Statuses:

```text
SUBMITTED
APPROVED
REJECTED
EXPIRED
```

Admin review is auditable through:

```text
reviewed_by_user_id
reviewed_at
reviewer_note
rejection_reason
metadata
```

---

### `verification_documents`

Stores metadata only, not raw files.

Important fields:

```text
storage_key
sha256_hash
file_mime_type
file_size_bytes
encrypted
status
```

Security principle:

> Verification files should be stored in encrypted object storage. PostgreSQL stores references and hashes only.

---

### `subjects` and `academic_levels`

Taxonomy tables used by search, teacher profiles, bookings, sessions, and reports.

Initial seed examples:

```text
subjects:
- MATHEMATICS
- PHYSICS

academic_levels:
- SECONDARY_1AS
- SECONDARY_2AS
- SECONDARY_3AS
- BAC
```

---

### `teacher_subjects`

Defines what a teacher offers.

Important fields:

```text
teacher_id
subject_id
academic_level_id
price_amount
currency
session_duration_minutes
is_active
```

Important constraint:

```sql
UNIQUE (teacher_id, subject_id, academic_level_id)
```

This prevents duplicate offerings for the same teacher/subject/level combination in MVP.

---

### `teacher_trust_metrics`

Derived current metrics used by Teacher Trust Profile and Matching Engine.

Fields:

```text
completed_sessions_count
attendance_rate
cancellation_rate
avg_response_seconds
verified_rating
review_count
dispute_rate
repeat_booking_rate
calculated_at
```

Important principle:

```text
Raw source of truth ≠ teacher_trust_metrics
```

Raw source tables are:

```text
sessions
bookings
payments
reviews
disputes
session_reports
```

`teacher_trust_metrics` is a derived performance table for fast reads.

The DDL includes an operational guard trigger:

```text
protect_teacher_trust_metrics()
```

In production, this should be combined with database GRANTs:

```text
app_runtime: SELECT only
metrics_worker: INSERT/UPDATE
admin: audited controlled access
```

---

## 5.4 Availability & Marketplace

### `availability_rules`

Recurring availability definition.

Important fields:

```text
teacher_id
day_of_week
start_time
end_time
mode
timezone
effective_from
effective_to
is_active
```

---

### `availability_slots`

Concrete bookable slots generated from rules or manually created.

Important fields:

```text
teacher_id
starts_at
ends_at
mode
status
held_until
held_by_parent_id
```

Important statuses:

```text
AVAILABLE
HELD
BOOKED
BLOCKED
EXPIRED
CANCELLED
```

Critical database guard:

```sql
EXCLUDE USING gist (
  teacher_id WITH =,
  tstzrange(starts_at, ends_at, '[)') WITH &&
)
WHERE (status IN ('AVAILABLE', 'HELD', 'BOOKED'));
```

This prevents overlapping active slots for the same teacher.

---

### `bookings`

Booking is the marketplace transaction intent.

Important fields:

```text
parent_id
student_id
teacher_id
teacher_subject_id
subject_id
academic_level_id
availability_slot_id
scheduled_start
scheduled_end
mode
price_amount
platform_commission_bps
status
hold_expires_at
```

Important booking states:

```text
HELD
PAYMENT_PENDING
BOOKED
COMPLETED
CANCELLED
DISPUTED
REFUNDED
EXPIRED
```

Critical constraints:

### Parent can only book for own student

```sql
FOREIGN KEY (student_id, parent_id)
REFERENCES student_profiles(id, parent_id)
```

### Teacher offering must match teacher, subject, and academic level

```sql
FOREIGN KEY (teacher_subject_id, teacher_id, subject_id, academic_level_id)
REFERENCES teacher_subjects(id, teacher_id, subject_id, academic_level_id)
```

### Booking slot must match teacher/time/mode

```sql
FOREIGN KEY (availability_slot_id, teacher_id, scheduled_start, scheduled_end, mode)
REFERENCES availability_slots(id, teacher_id, starts_at, ends_at, mode)
```

### One active booking per slot

```sql
CREATE UNIQUE INDEX ux_one_active_booking_per_slot
ON bookings(availability_slot_id)
WHERE status IN ('HELD', 'PAYMENT_PENDING', 'BOOKED', 'COMPLETED', 'DISPUTED');
```

---

## 5.5 Transaction Layer

### `payments`

Payment is separate from booking.

Important fields:

```text
booking_id
parent_id
provider
provider_transaction_id
idempotency_key
amount
currency
provider_fee_amount
status
raw_provider_payload
```

Payment statuses:

```text
NOT_STARTED
INITIATED
PENDING
CONFIRMED
FAILED
REFUND_PENDING
REFUNDED
PARTIALLY_REFUNDED
DISPUTED
```

Critical guards:

### Payment amount must match booking amount

Trigger:

```text
validate_payment_amount_matches_booking()
```

This blocks payment rows where:

```text
payment.amount != booking.price_amount
payment.currency != booking.currency
```

### Idempotency

```text
idempotency_key UNIQUE
```

### Provider transaction uniqueness

```sql
UNIQUE (provider, provider_transaction_id)
WHERE provider_transaction_id IS NOT NULL
```

### One confirmed payment per booking

```sql
UNIQUE (booking_id)
WHERE status = 'CONFIRMED'
```

---

### `ledger_transactions` and `ledger_entries`

Financial ledger is append-only.

Structure:

```text
ledger_transactions
   └── ledger_entries
```

A ledger transaction groups debit/credit entries.

Example:

```text
ledger_transaction: PARENT_PAYMENT

DEBIT   PAYMENT_PROVIDER_CLEARING   2000 DZD
CREDIT  TEACHER_PAYABLE             1700 DZD
CREDIT  PLATFORM_REVENUE             300 DZD
```

Critical guards:

- `ledger_entries` are append-only.
- Updates/deletes are blocked.
- Corrections should be reversal entries.
- A deferred constraint trigger checks that debit total equals credit total per ledger transaction.

Trigger:

```text
enforce_ledger_transaction_balance()
```

---

### `payouts` and `payout_items`

Payouts may aggregate multiple eligible sessions.

`payout_items` links payout to completed sessions.

Critical eligibility trigger:

```text
validate_payout_item_eligibility()
```

A payout item is blocked unless:

```text
session.status = COMPLETED
session_report exists
confirmed payment exists
teacher matches session teacher
no open dispute exists for booking/session
```

This prevents payouts for non-eligible sessions.

---

## 5.6 Education Layer

### `sessions`

A tutoring session is created from a confirmed booking.

Important fields:

```text
booking_id
parent_id
student_id
teacher_id
subject_id
academic_level_id
scheduled_start
scheduled_end
actual_start
actual_end
status
attendance_status
invitation_code
```

Session states:

```text
SCHEDULED
STARTED
COMPLETED
NO_SHOW_STUDENT
NO_SHOW_TEACHER
CANCELLED
DISPUTED
```

Critical trigger:

```text
validate_session_creation()
```

A session cannot be created unless:

```text
booking.status = BOOKED
payment.status = CONFIRMED
```

Completion guard:

```text
status = COMPLETED requires:
- actual_start
- actual_end
- attendance_status = PRESENT
```

---

### `session_reports`

Structured teacher report.

Important fields:

```text
session_id
teacher_id
student_id
subject_id
topics_covered
skills_practiced
participation
teacher_observations
homework
recommended_revision
next_objectives
progress_indicator
```

Critical trigger:

```text
validate_report_for_completed_session()
```

Report is allowed only for completed sessions and must match the session teacher/student.

---

### `student_progress_events`

This is the foundation of Student Passport.

Important fields:

```text
student_id
session_id
report_id
subject_id
event_type
source_type
topic
value_numeric
note
created_by_user_id
```

Event types:

```text
TOPIC_COVERED
SKILL_PRACTICED
WEAKNESS_OBSERVED
STRENGTH_OBSERVED
HOMEWORK_ASSIGNED
HOMEWORK_COMPLETED
PROGRESS_NOTE
PARTICIPATION_NOTE
```

Source types:

```text
TEACHER_REPORT
TEACHER_OBSERVATION
HOMEWORK
ADMIN_CORRECTION
```

No AI source type is included in MVP v0.1 because AI should not be the source of truth.

---

## 5.7 Trust & Operations

### `reviews`

Verified review table.

Important fields:

```text
session_id
booking_id
parent_id
student_id
teacher_id
rating
comment
status
is_verified
```

Critical constraints:

### One review per session

```sql
session_id UNIQUE
```

### Rating range

```sql
rating BETWEEN 1 AND 5
```

### Always verified

```sql
is_verified = TRUE
```

### Eligibility trigger

```text
validate_review_eligibility()
```

Review is blocked unless:

```text
session.status = COMPLETED
booking.status = COMPLETED
payment.status = CONFIRMED
review parent/student/teacher matches session
parent user != teacher user
```

This prevents:

- Arbitrary reviews
- Duplicate reviews
- Reviews before completed sessions
- Teacher self-reviews
- Reviews for unpaid/cancelled sessions

---

### `disputes`

Dispute workflow table.

Categories:

```text
TEACHER_NO_SHOW
STUDENT_NO_SHOW
SESSION_QUALITY
PAYMENT_REFUND
SAFETY
REPORT_ISSUE
OTHER
```

Statuses:

```text
OPEN
UNDER_REVIEW
RESOLVED
REJECTED
CANCELLED
```

Disputes can link to:

```text
booking_id
session_id
payment_id
```

At least one must be present.

---

### `notifications`

Tracks notification attempts and delivery state.

Channels:

```text
IN_APP
SMS
EMAIL
PUSH
```

Statuses:

```text
PENDING
SENT
DELIVERED
FAILED
READ
```

Important principle:

> Critical parent-facing events should be tracked, not only sent through external providers.

---

## 5.8 Audit & Security

### `event_ledger`

Append-only product event ledger.

Important fields:

```text
actor_user_id
actor_role
event_type
entity_type
entity_id
request_id
idempotency_key
ip_address
user_agent
metadata
created_at
```

Critical guard:

```text
prevent_event_ledger_mutation()
```

Updates and deletes are blocked.

Important principle:

> Application services should insert event_ledger rows in the same transaction as the business action where possible.

Example:

```text
Create booking transaction:
1. Insert booking
2. Update slot to HELD
3. Insert event_ledger: BOOKING_CREATED
4. Commit
```

---

## 6. Critical Invariants Enforced by Database

| Invariant | Enforcement |
|---|---|
| Same slot cannot be booked twice | Partial unique index on `bookings(availability_slot_id)` + slot trigger |
| Teacher cannot have overlapping active slots | Exclusion constraint on `availability_slots` |
| Parent cannot book for another parent’s student | Composite FK `(student_id, parent_id)` |
| Booking offering must match teacher/subject/level | Composite FK to `teacher_subjects` |
| Booking slot must match teacher/time/mode | Composite FK to `availability_slots` |
| Payment amount must equal booking amount | Trigger `validate_payment_amount_matches_booking()` |
| Duplicate confirmed payment blocked | Partial unique index on `payments(booking_id)` where confirmed |
| Session requires booked + paid booking | Trigger `validate_session_creation()` |
| Completed session needs actual start/end + attendance | Check + trigger |
| Report requires completed session | Trigger `validate_report_for_completed_session()` |
| Duplicate review blocked | `reviews.session_id UNIQUE` |
| Review requires completed paid session | Trigger `validate_review_eligibility()` |
| Teacher self-review blocked | Trigger compares parent user and teacher user |
| Payout requires eligible session | Trigger `validate_payout_item_eligibility()` |
| Event Ledger cannot be edited | Trigger blocks UPDATE/DELETE |
| Ledger entries cannot be edited | Trigger blocks UPDATE/DELETE |
| Ledger must balance | Deferred constraint trigger |
| Trust metrics not teacher-editable | Protected derived table + production GRANTs |

---

## 7. Index Strategy

The schema includes indexes for the most important MVP queries.

### Teacher search / matching

```text
teacher_profiles(listing_status, verification_status)
teacher_profiles GIN(teaching_modes)
teacher_profiles GIN(languages)
teacher_subjects(subject_id, academic_level_id, is_active, price_amount)
availability_slots(status, starts_at, mode)
```

### Parent dashboard

```text
bookings(parent_id, status, scheduled_start DESC)
payments(parent_id, created_at DESC)
sessions(student_id, status, scheduled_start DESC)
student_progress_events(student_id, created_at DESC)
```

### Teacher dashboard

```text
bookings(teacher_id, status, scheduled_start DESC)
sessions(teacher_id, status, scheduled_start DESC)
payouts(teacher_id, status, created_at DESC)
```

### Trust and operations

```text
reviews(teacher_id, created_at DESC)
disputes(status, priority, created_at)
event_ledger(entity_type, entity_id, created_at DESC)
event_ledger(event_type, created_at DESC)
event_ledger GIN(metadata)
```

---

## 8. Recommended Initial Seed Data

### Subjects

```sql
INSERT INTO subjects (code, name_ar, name_fr, name_en) VALUES
('MATHEMATICS', 'الرياضيات', 'Mathématiques', 'Mathematics'),
('PHYSICS', 'الفيزياء', 'Physique', 'Physics');
```

### Academic levels

```sql
INSERT INTO academic_levels (code, name_ar, name_fr, sort_order) VALUES
('SECONDARY_1AS', 'الأولى ثانوي', '1ère année secondaire', 10),
('SECONDARY_2AS', 'الثانية ثانوي', '2ème année secondaire', 20),
('SECONDARY_3AS', 'الثالثة ثانوي', '3ème année secondaire', 30),
('BAC', 'البكالوريا', 'Baccalauréat', 40);
```

---

## 9. RBAC and Minor Data Protection

The schema enforces ownership at write-time through foreign keys, especially in `bookings` and `student_permissions`.

For read access, the backend must enforce RBAC consistently.

Recommended access rules:

### Parent

Can read:

```text
own parent_profile
own student_profiles
own bookings
own payments
own sessions
own session_reports
own student_progress_events
own reviews
own disputes
```

### Teacher

Can read:

```text
own teacher_profile
own availability
own bookings
own sessions
student context only when permission exists
reports they created
reviews about them
own payout/income records
```

### Admin/Ops

Can read operational data based on permission level, with admin access logged.

### Recommended future RLS pattern

For high-sensitivity tables such as `student_profiles`, `session_reports`, and `student_progress_events`, PostgreSQL Row-Level Security can be added using session variables:

```text
edutrust.current_user_id
edutrust.current_parent_id
edutrust.current_teacher_id
edutrust.current_role
```

MVP backend must still enforce authorization in the service layer.

---

## 10. What the Database Does Not Try to Solve Alone

Some controls require backend + operations + policy, not only schema:

| Concern | Required Layer |
|---|---|
| Full RBAC read authorization | Backend + optional RLS |
| Payment provider compliance | Payment provider + legal/accounting review |
| Teacher document validation | Admin workflow + secure storage |
| Fraud scoring | Event ledger + analytics jobs |
| Trust metric recalculation | Background job / metrics worker |
| Student Passport summaries | Structured reports + progress aggregation |
| AI insights | Future AI service on top of structured data |
| Safety investigations | Admin workflow + audit logs + policy |

---

## 11. State Machine Mapping

### Booking state lives in `bookings.status`

```text
HELD → PAYMENT_PENDING → BOOKED → COMPLETED

Side states:
CANCELLED / DISPUTED / REFUNDED / EXPIRED
```

### Payment state lives in `payments.status`

```text
INITIATED → PENDING → CONFIRMED
FAILED
REFUND_PENDING → REFUNDED
DISPUTED
```

### Session state lives in `sessions.status`

```text
SCHEDULED → STARTED → COMPLETED
NO_SHOW_STUDENT
NO_SHOW_TEACHER
CANCELLED
DISPUTED
```

### Review eligibility is enforced by `reviews` trigger

```text
Only after:
booking = COMPLETED
payment = CONFIRMED
session = COMPLETED
```

---

## 12. Files Produced

Two files were produced:

```text
EduTrust_PostgreSQL_Database_Schema_v1.0.md
edutrust_schema_v1.sql
```

The SQL file contains:

- PostgreSQL extensions
- Enums
- Tables
- Foreign keys
- Composite constraints
- Partial unique indexes
- Exclusion constraints
- Trigger functions
- Database guards
- Event ledger immutability
- Ledger immutability and balancing

---

## 13. Next Step

After approving this schema, the next engineering document should be:

> **EduTrust API Architecture v1.0**

It should define:

- Endpoint groups
- Request/response bodies
- Validation rules
- Authorization rules
- Error responses
- Idempotency rules
- Payment webhook handling
- Event Ledger insertion points
- State transition rules per endpoint

Recommended sequence:

```text
PRD v1.0
   ↓
PostgreSQL Schema v1.0
   ↓
API Architecture v1.0
   ↓
State Machines v1.0
   ↓
UX Flows
   ↓
MVP Build
```
