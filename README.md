# EduTrust Algeria — DEV Foundation

This repository is the Sprint 1 DEV implementation foundation for EduTrust Algeria.

## Current authorization

- DEV implementation: approved
- STAGING: approved with mock/sandbox only
- PILOT: not approved
- PRODUCTION: not approved
- Real-money payments: forbidden
- Real teacher payouts: forbidden

## Structure

```text
backend/        Django + DRF modular monolith foundation
database/       Approved SQL migration chain
frontend/       Next.js + React + TypeScript shell
tests/          Backend foundation tests
scripts/        Migration/test/dev helper scripts
infra/          Future deployment/container assets
docs/           Future implementation docs
```

## Database migration chain

```text
001_edutrust_schema_v1.sql
002_edutrust_schema_patch_v1_1.sql
003_edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql
004_edutrust_schema_patch_v1_3.sql
005_edutrust_schema_patch_v1_4.sql
```

Important: v1.2 is reconstructed and must never be described as the original historical artifact.

## Setup

```bash
pip install -r backend/requirements.txt
cd frontend && npm install
```

PostgreSQL 14+ with `psql` is required for migrations/tests. The validation environment used PostgreSQL 17.11.

## Run backend tests

```bash
./scripts/run_backend_tests.sh
```

This script starts an isolated temporary PostgreSQL cluster, runs the approved migration chain, and runs pytest.

## Run migrations manually

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/edutrust_dev
python scripts/run_migrations.py
```

## Start backend

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/edutrust_dev
export SECRET_KEY=dev-only
export JWT_SECRET=dev-only-jwt-secret-with-at-least-32-bytes
python backend/manage.py runserver 0.0.0.0:8000
```

Endpoints implemented in Sprint 1:

```text
GET  /health
GET  /ready
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/students
GET  /api/v1/students/:id
GET  /api/v1/admin/security-events
```

## Start frontend

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Implemented frontend screens are placeholder shells only:

```text
/
/parent
/teacher
/admin
```

## Mock payment

`backend/edutrust_api/payments.py` defines a `PaymentProvider` interface and `MockPaymentProvider`. It does not process real money and must not bypass approved state machines.

## DEV Vertical Slice #1

Implemented in this repository:

```text
Parent → Student → Teacher → Subject/Pricing → Availability → Search → Booking Hold → DEV Mock Booking Confirmation
```

Additional Sprint 2 endpoints:

```text
GET/PATCH /api/v1/teachers/me
GET/POST /api/v1/teachers/subjects
GET/POST /api/v1/teachers/availability/slots
POST /api/v1/teachers/availability/slots/:id/block
POST /api/v1/teachers/availability/slots/:id/unblock
GET /api/v1/teachers/search
POST /api/v1/teachers/match
GET /api/v1/teachers/:id
GET /api/v1/teachers/:id/trust-profile
POST /api/v1/bookings/hold
POST /api/v1/bookings/:id/confirm   # DEV mock only, no real money
GET /api/v1/bookings
GET /api/v1/bookings/:id
```

Booking confirmation in this slice is DEV-only and uses the mock payment boundary. It creates mock `OTHER` provider payment records only to preserve the approved database invariants. It is not real payment processing.

## Current test status

```bash
./scripts/run_backend_tests.sh
# 10 passed

cd frontend && npm run build
# compiled successfully
```

## Dependency audit note

`npm audit` currently reports high severity issues in `next` / transitive `postcss`. These are accepted temporarily for local DEV only and must be remediated before staging/production exposure.

## DEV Vertical Slice #2

Implemented payment lifecycle using `MockPaymentProvider` only:

```text
Booking Hold → Payment Initiation → Payment Pending → Mock Provider Event → Payment Confirmed/Failed → Booking/Session outcome
```

Additional Sprint 3 endpoints:

```text
POST /api/v1/payments/initiate
GET  /api/v1/payments/:id
POST /api/v1/payments/:id/mock/succeed   # DEV-only
POST /api/v1/payments/:id/mock/fail      # DEV-only
GET  /api/v1/admin/payments
GET  /api/v1/admin/events
```

Strict boundaries:

```text
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```

Automated backend tests at end of VS2:

```bash
./scripts/run_backend_tests.sh
# 17 passed
```

## DEV Vertical Slice #3

Implemented session execution lifecycle using the existing approved schema/state model (no schema changes):

```text
Booking → Payment Confirmed → Session Scheduled → Session Execution → Attendance/No-show → Completion → Teacher Report → Parent Report → Student Progress Events
```

Additional Sprint 4 endpoints:

```text
GET  /api/v1/sessions
GET  /api/v1/sessions/:id
POST /api/v1/sessions/:id/start
POST /api/v1/sessions/:id/complete
POST /api/v1/sessions/:id/no-show
GET  /api/v1/sessions/:id/report
POST /api/v1/sessions/:id/report
```

Automated backend tests at end of VS3:

```bash
./scripts/run_backend_tests.sh
# 26 passed
```

## DEV Vertical Slice #4

Implemented verified review + basic dispute foundation on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
Completed Session → Review Eligibility → Verified Review → Review Read → Dispute Open → Dispute Read → Admin/OPS Review → Audit/Security Events
```

- Reviews are **verified by construction**: eligibility = completed session + completed booking + confirmed payment + parent ownership (DB trigger as final guard). The client cannot set `is_verified` (schema enforces `is_verified = TRUE`).
- Disputes follow the approved **overlay model**: opening a dispute never sets `DISPUTED` on bookings/sessions; payout blocking is enforced by the existing database trigger.
- `SAFETY` disputes automatically receive priority 1. Dispute resolution/moderation is **not** part of VS4.
- Duplicate/concurrent protection: one review per session (DB unique), one active dispute per (actor, interaction); idempotency via the established `Idempotency-Key` pattern (replay/conflict semantics).

VS4 endpoints:

```text
POST /api/v1/sessions/:id/review          # PARENT only
GET  /api/v1/sessions/:id/review          # PARENT/TEACHER/ADMIN/OPS (admin/ops audited)
GET  /api/v1/reviews                      # own scope; ADMIN/OPS operational (audited)
GET  /api/v1/teachers/:id/reviews         # public: visible verified reviews, no student data
POST /api/v1/disputes                     # PARENT/TEACHER participants
GET  /api/v1/disputes                     # own scope; ADMIN/OPS operational (audited)
GET  /api/v1/disputes/:id                 # participant scope; ADMIN/OPS audited
```

Strict boundaries (unchanged):

```text
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```

Current automated backend tests:

```bash
./scripts/run_backend_tests.sh
# 98 passed (83 baseline regression + 15 VS6)
```

## DEV Vertical Slice #6

Implemented manual review moderation on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
Operational review list → FLAG / HIDE / RESTORE / REMOVE → public visibility update → audit trail
```

- Transitions exactly per State Machines v1.0 §10.3: FLAG (VISIBLE→FLAGGED), HIDE (FLAGGED→HIDDEN), RESTORE (FLAGGED|HIDDEN→VISIBLE), REMOVE (→REMOVED, **ADMIN-only**; OPS gets 403).
- No physical deletion: the review row, rating, and comment are always preserved (auditability per §10.4).
- Public visibility continues to use the existing VS4 filter (`VISIBLE` + `is_verified`); moderation takes effect automatically.
- Verified-review model fully preserved (server-derived verification, eligibility, ownership, privacy boundaries).
- Automatic/system flagging is NOT implemented (no approved detection specification; out of scope).
- Every moderation and operational read is audited (`ADMIN_ACTION` + `ADMIN_ACCESS`); Idempotency-Key mandatory on moderation (replay/conflict semantics).

VS6 endpoints:

```text
GET  /api/v1/admin/reviews                  # SUPPORT/OPS/ADMIN (audited)
POST /api/v1/admin/reviews/:id/moderate     # OPS/ADMIN; REMOVE ADMIN-only
```

Strict boundaries (unchanged):

```text
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```

## DEV Vertical Slice #5

Implemented the payout lifecycle on the existing approved baseline (MANUAL_OPS / MOCK execution only; no schema, state-machine, or architecture changes):

```text
Completed eligible session → Eligibility → Calculation → Payout Item → PENDING →
Admin/Ops Processing → PROCESSING → mock execution → PAID / FAILED →
Ledger → Event Ledger → Audit → Visibility → PAID immutability (DB-enforced)
```

- Payouts are processed exclusively by OPS/ADMIN through `POST /api/v1/admin/payouts/process` (mandatory `Idempotency-Key: payout-<uuid>`); DEV execution is mock/manual-ops — no real payout provider, no real money, no credentials (approved decision U1). PENDING batches are Admin/Ops-initiated — no scheduled jobs (approved decision U2).
- Net-payable calculation per the authoritative Addendum: gross (price − booking commission) minus APPROVED/PROVIDER_PENDING/SUCCEEDED partial-refund teacher adjustments; net = 0 blocks the session.
- Blocked path: open dispute blocks payout at service level and via the existing DB trigger; the dispute overlay never changes booking/session status.
- PAID payout rows are DB-immutable (v1.4 trigger); failed batches void the DRAFT ledger transaction (never posted → no funds moved). Post-paid correction is represented by the existing adjustment/recovery ledger model only — no recovery workflow in VS5.

VS5 endpoints:

```text
GET  /api/v1/teacher/payouts           # TEACHER own payouts
GET  /api/v1/teacher/payouts/:id       # TEACHER own payout detail (no provider reference)
POST /api/v1/admin/payouts/process     # OPS/ADMIN, Idempotency-Key required, mock execution
GET  /api/v1/admin/payouts             # OPS/ADMIN operational (audited)
```

Strict boundaries (unchanged):

```text
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```
