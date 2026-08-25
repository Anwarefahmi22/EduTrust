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

## DEV Vertical Slice #7

Implemented teacher verification on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
Teacher submission (type + metadata + document metadata)
→ SUBMITTED → Admin/OPS review (audited) → APPROVED / REJECTED
→ trust-profile per-type booleans + public profile/search exposure
```

- Levels per PRD 9.2: IDENTITY approval → `IDENTITY_VERIFIED`; QUALIFICATION approval → `QUALIFICATION_REVIEWED` (Level 3 advanced verification = future, out of scope). EXPERIENCE/BACKGROUND_CHECK rows are tracked but have no profile-level mapping (no approved level exists).
- Approved profile mapping with the no-demotion rule: a rejected lower type never demotes an approved higher level; profile → `REJECTED` only when no approved level remains.
- Server-derived verification only: the API never accepts client-supplied status/verified flags. Automatic/AI/KYC/provider verification and real document storage are out of scope (DEV documents are metadata + synthetic storage key only).
- Self-approval is forbidden; admin/OPS reads and decisions are audited (`ADMIN_ACTION` + `ADMIN_ACCESS` security events).

VS7 endpoints:

```text
POST /api/v1/teachers/verifications                       # TEACHER (own), Idempotency-Key required
GET  /api/v1/teachers/verifications                       # TEACHER (own)
GET  /api/v1/admin/teachers/pending-verification          # OPS/ADMIN (audited)
GET  /api/v1/admin/teachers/:id/verifications             # OPS/ADMIN (audited, metadata only)
POST /api/v1/admin/teachers/:id/verify                    # OPS/ADMIN
POST /api/v1/admin/teachers/:id/reject                    # OPS/ADMIN (reason required)
```

Current automated backend tests:

```bash
./scripts/run_backend_tests.sh
# 118 passed (98 baseline regression + 20 VS7)
```

Strict boundaries (unchanged):

```text
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```
## DEV Vertical Slice #8

Implemented refund operations on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
Eligibility (payment CONFIRMED/DISPUTED, over-refund bound under lock)
→ REQUESTED → APPROVED (actor-supplied allocation: teacher + platform = approved)
→ PROVIDER_PENDING (DEV mock provider call outside the DB transaction)
→ SUCCEEDED / FAILED (deterministic mock result)
   or via the approved reconciliation command (Addendum v1.1 §7.3)
Payment shadow: CONFIRMED/DISPUTED → REFUND_PENDING → REFUNDED / PARTIALLY_REFUNDED
               (restored on failure/cancel; REFUND_ISSUED is never emitted)
```

- Approval is the only allocation entry point: the approving OPS/ADMIN supplies `teacher_adjustment_amount` + `platform_adjustment_amount` (sum = `approved_amount`, DB-enforced); no automatic formula, no defaults — OPS-POL-007 value remains OPEN and unmodified.
- Ledger per approved schema: DRAFT `REFUND` tx at approval → POSTED on success / VOIDED on failure; form L (late → `REFUND_PAYABLE` settlement), D (direct reversal of `TEACHER_PAYABLE`/`PLATFORM_REVENUE`), A (post-paid recovery via `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` — old PAID payout byte-identical, v1.4).
- Late refunds (VS2 branch, unchanged) progress through the same commands — no auto-approval (OPS-POL-003 unset behavior); reconciliation is the documented DEV proof path and also handles the manual/bank-confirmation case.
- Provider events reuse `payment_provider_events` (no new table, no new event enum values); replay → 200 duplicate, identity conflict → 409 + `SUSPICIOUS_ACTIVITY` security event (Addendum §8 / SM §7.8).
- Payout interaction: a refund in flight (`REFUND_PENDING`) blocks new payout items for the session via the existing v1 DB guard; the Addendum §10.4 net-reduction vector remains pinned by the VS5 suite. No payout code modified.
- Reads: admin refund list/detail (audited detail, redacted provider summary) + additive `refunds[]` / `refund_summary` / `linked_refunds[]` on payment/booking/dispute reads (Addendum §8; fields appear only when activity exists).

VS8 endpoints:

```text
POST /api/v1/payments/:id/refund                        # OPS/ADMIN, Idempotency-Key required
POST /api/v1/admin/refunds/:id/approve                  # OPS/ADMIN, Idempotency-Key required (allocation input)
POST /api/v1/admin/refunds/:id/reject                   # OPS/ADMIN, Idempotency-Key required
POST /api/v1/admin/refunds/:id/cancel                   # OPS/ADMIN, Idempotency-Key required
POST /api/v1/admin/refunds/:id/mock/succeed             # OPS/ADMIN, DEV-only (deterministic mock SUCCESS)
POST /api/v1/admin/refunds/:id/mock/fail                # OPS/ADMIN, DEV-only (deterministic mock FAILURE)
POST /api/v1/admin/refunds/:id/reconcile                # OPS/ADMIN (ADMIN_OVERRIDE ⇒ ADMIN), Idempotency-Key required
GET  /api/v1/admin/refunds                              # OPS/ADMIN (filters + cursor pagination)
GET  /api/v1/admin/refunds/:id                          # OPS/ADMIN (audited, redacted)
```

Current automated backend tests:

```bash
./scripts/run_backend_tests.sh
# 160 passed (118 baseline regression + 42 VS8: 38 service + 4 concurrency)
```

VS8 E2E (standalone, isolated runtime):

```bash
PG_BIN=<pg bin dir> python tests/e2e_refund_lifecycle.py
# 53/53 checks PASS (7 scenarios + 8 financial-integrity gates)
```

Strict boundaries (unchanged):

```text
Real refund: forbidden
Real payment: forbidden
Real payout: forbidden
Production: forbidden
```

## DEV Vertical Slice #9

Implemented dispute resolution (CORE: the RESOLVED path, nine actions) on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
Dispute OPEN / UNDER_REVIEW
→ resolve (OPS/ADMIN; SAFETY + full-refund-after-completed-session ⇒ ADMIN)
   NO_ACTION · WARNING · FULL_REFUND · PARTIAL_REFUND · PAYOUT_BLOCKED · PAYOUT_RELEASED
   TEACHER_NO_SHOW_CONFIRMED · STUDENT_NO_SHOW_CONFIRMED · REPORT_CORRECTION_REQUIRED
→ RESOLVED (resolution + resolved_at + resolver — SM §11.7; DISPUTE_RESOLVED + ADMIN_ACTION)
Refund actions are TWO-STEP (plan P1): resolve creates the linked REQUESTED refund via the
VS8 service; the operator approves it with allocation in the Refunds section (VS8 endpoint).
REJECTED / CANCELLED / UNDER_REVIEW mechanisms and account actions: deferred (contract gaps / R10 UNKNOWN).
```

- No ledger mechanism added — every financial effect flows through the VS8 refund forms (L/D/A); post-paid refunds settle via Form A with the old PAID payout byte-identical (v1.4).
- Open disputes block payout items via the existing v1/VS5 guards; resolution unblocks. No payout code modified.
- No-show confirmations reuse the VS3 session no-show path, only while the session is SCHEDULED (otherwise record-only).
- Idempotency + audit events per the existing conventions; reads audited (`ADMIN_ACCESS` + `ADMIN_ACTION`); `REFUND_ISSUED` never emitted.

VS9 endpoints:

```text
POST /api/v1/admin/disputes/:id/resolve   # OPS/ADMIN, Idempotency-Key required
GET  /api/v1/admin/disputes               # SUPPORT/OPS/ADMIN (filters + cursor pagination, audited)
```

Current automated backend tests:

```bash
./scripts/run_backend_tests.sh
# 197 passed (160 baseline regression + 37 VS9: 33 service + 4 concurrency)
```

VS9 E2E (standalone, isolated runtime incl. Next.js production server):

```bash
PG_BIN=<pg bin dir> python tests/e2e_dispute_resolution.py
# 75/75 checks PASS (15 scenarios + 11 DB-level financial-integrity gates)
```

## DEV Vertical Slice #10

Implemented R6 auth completion (session refresh + session revocation) on the existing approved baseline (no schema, state-machine, or architecture changes):

```text
POST /api/v1/auth/refresh
  Strict one-use rotation (D3a baseline): sha256(token) → active auth_sessions row
  (FOR UPDATE) → new token hash stored in the SAME transaction (the old token is
  dead by replacement) → access token re-issued for the SAME session (sid preserved,
  roles re-read from DB, existing TTL). Uniform 401 for unknown/revoked/expired/
  rotated-out tokens (no existence oracle). Session lifetime NOT extended.
  Rotated-token reuse = schema-limited (uniform 401, no detection event —
  D3a documented limitation; D3b previous-hash detection deferred, not implemented).

POST /api/v1/auth/revoke-sessions
  Self-service only (own sessions; scope from the verified JWT, never the body):
  { "scope": "CURRENT" | "OTHERS" | "ALL" } → guarded UPDATE revoked_at per row;
  one TOKEN_REVOKED security event + SECURITY_EVENT ledger row per actually-revoked
  session; response = the self-count only (no ids, no tokens).
```

- No new event values (existing `TOKEN_REVOKED`/`SECURITY_EVENT` only); no ledger/financial surface; no D3b marker; no admin session surface (none approved).
- Frontend: `lib/api.ts` refresh-on-expiry hook (single in-flight refresh, one retry, logged-out state) — opt-in; no console screens (none approved for R6).
- Concurrency: existing `auth_sessions` row-lock strategy (leaf object — acyclic); two simultaneous same-token refreshes → exactly one rotation.

VS10 endpoints:

```text
POST /api/v1/auth/refresh            # unauthenticated (token is the credential), uniform 401 class
POST /api/v1/auth/revoke-sessions    # authenticated, own sessions only, scope CURRENT/OTHERS/ALL
```

Current automated backend tests:

```bash
./scripts/run_backend_tests.sh
# 225 passed (197 baseline regression + 28 VS10: 23 service + 5 concurrency)
```

VS10 E2E (standalone, isolated runtime):

```bash
PG_BIN=<pg bin dir> python tests/e2e_auth_completion.py
# 33/33 checks PASS (8 scenarios, D3a replay semantics verified)
```

Strict boundaries (unchanged):

```text
Real payment: forbidden
Real refund: forbidden
Real payout: forbidden
D3b previous-hash detection: deferred (not implemented, no schema change)
Production: forbidden
```
