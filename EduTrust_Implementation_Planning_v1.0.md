# EduTrust Algeria — Implementation Planning v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Implementation planning / engineering work breakdown  
**Status:** READY FOR IMPLEMENTATION PLANNING REVIEW  
**Implementation status:** NOT STARTED  
**Architecture status:** LOCKED  
**MVP scope:** LOCKED

---

# 1. Executive Summary

EduTrust has now passed the major product, architecture, database, UX, visual, and prototype gates.

Approved baseline:

```text
PRD / Product Definition             APPROVED
Database / DDL                       HARDENED
API Architecture                     APPROVED
State Machines                       APPROVED
UX Flows                             APPROVED
Low-Fidelity                         APPROVED
High-Fidelity UI                     APPROVED
Visual Mockups                       APPROVED
Clickable Prototype                  APPROVED
Clickable Prototype Final Audit      PASS
```

Implementation is still **not approved**.

This document defines how to move from approved prototype to implementation readiness without writing code yet.

The next intended sequence is:

```text
APPROVED CLICKABLE PROTOTYPE
        ↓
IMPLEMENTATION PLANNING v1.0
        ↓
Implementation Architecture / Work Breakdown Review
        ↓
Implementation Gate
        ↓
Backend + Frontend implementation
```

---

# 2. Non-Negotiable Rules

This planning document does **not**:

- start backend implementation,
- start frontend implementation,
- write production UI code,
- modify database schema,
- modify API architecture,
- modify state machines,
- expand MVP scope,
- resolve open policy decisions silently,
- reopen the architecture baseline.

Any future change to architecture, schema, API, UX, or state machines must be handled as a formal change request.

---

# 3. Authoritative Baseline

Implementation must follow these approved artifacts:

```text
EduTrust_MVP_PRD_v1.0.md
EduTrust_PostgreSQL_Database_Schema_v1.0.md
edutrust_schema_v1.sql
EduTrust_Schema_Patch_v1.1.md
edutrust_schema_patch_v1_1.sql
Schema Patch v1.2, required artifact before implementation
EduTrust_DDL_Hardening_v1.3.md
edutrust_schema_patch_v1_3.sql
EduTrust_API_Architecture_v1.0.md
EduTrust_State_Machines_v1.0.md
EduTrust_State_Machines_v1.1_Addendum.md
EduTrust_UX_Flows_v1.0.md
EduTrust_UX_Flows_v1.1_Patch.md
EduTrust_Low_Fidelity_Wireframes_v1.0.md
EduTrust_Low_Fidelity_Wireframes_v1.1_Patch.md
EduTrust_High_Fidelity_UI_Design_v1.0.md
EduTrust_High_Fidelity_Visual_Mockups_v1.0.md
EduTrust_Clickable_Prototype_Specification_v1.0.md
EduTrust_Clickable_Prototype_Patch_v1.1.md
EduTrust_Clickable_Prototype_Final_Audit_v1.0.md
```

## 3.1 Important artifact preflight

Before implementation begins, the engineering repository must include every database migration artifact in the approved chain.

Required DDL order:

```text
1. edutrust_schema_v1.sql
2. edutrust_schema_patch_v1_1.sql
3. edutrust_schema_patch_v1_2.sql
4. edutrust_schema_patch_v1_3.sql
```

If `edutrust_schema_patch_v1_2.sql` is missing from the repository, implementation must not begin until the artifact is supplied and migration order is verified.

---

# 4. Implementation Strategy

## 4.1 Architecture style

Approved implementation style:

```text
Modular Monolith + PostgreSQL
```

Do not introduce microservices in MVP.

## 4.2 Product surface

MVP implementation surface:

```text
Mobile-first web app for Parent and Teacher
Desktop-first Admin/OPS dashboard
API-first backend
PostgreSQL database
Background workers for jobs
Internal marketplace ledger
Event ledger / audit trail
```

## 4.3 Recommended technical direction

This is a recommended implementation plan, not code.

Recommended stack for review:

```text
Backend: Django + Django REST Framework or equivalent modular backend
Database: PostgreSQL 14+
Background jobs: Celery/RQ or equivalent worker system
Cache/broker: Redis
Frontend: Next.js / React / TypeScript mobile-first web
Admin UI: Next.js/React protected admin routes, with optional internal Django admin only for emergency back-office during early pilot
Testing: Pytest + integration DB tests + Playwright for E2E
CI/CD: GitHub Actions or equivalent
Containers: Docker for local/staging/prod parity
```

Alternative stacks are allowed only if they preserve:

- PostgreSQL constraints and migration discipline,
- strong transaction boundaries,
- modular monolith structure,
- RBAC and object-ownership enforcement,
- event ledger integration,
- decimal-safe money handling,
- idempotent financial/payment workflows.

## 4.4 Recommended repository structure

Preferred monorepo:

```text
edutrust/
  apps/
    backend/
    web/
    admin/
  packages/
    shared-types/
    design-tokens/
  database/
    migrations/
    seeds/
    ddl-audits/
  docs/
    architecture/
    ux/
    implementation/
  infra/
    docker/
    ci/
    deployment/
  tests/
    e2e/
    load/
    security/
```

If using a single frontend app with role-based routes:

```text
apps/web/
  parent/
  teacher/
  admin/
```

is acceptable, provided admin access is strongly protected.

---

# 5. Backend Module Plan

Backend must be a modular monolith with clear internal boundaries.

Recommended modules:

```text
AuthModule
UserModule
ParentStudentModule
TeacherModule
VerificationModule
SearchMatchingModule
AvailabilityModule
BookingModule
PaymentModule
RefundModule
LedgerModule
PayoutModule
SessionModule
ReportModule
ReviewModule
DisputeModule
NotificationModule
EventLedgerModule
AdminModule
SecurityAuditModule
MetricsModule
```

## 5.1 Module ownership rules

Each module owns its state transitions through service methods.

Forbidden:

```text
direct controller status mutation
direct frontend status updates
admin blind status edits
manual SQL changes in production for business transitions
```

Required pattern:

```text
Controller / API endpoint
   ↓
Request validation
   ↓
Authorization + ownership check
   ↓
Domain service method
   ↓
Database transaction
   ↓
Business changes + event ledger
   ↓
Commit
```

---

# 6. Service Contract Plan

## 6.1 Core services

Required services:

```text
AuthService
StudentService
TeacherService
VerificationService
MatchingService
AvailabilityService
BookingService
PaymentService
PaymentWebhookService
RefundService
LedgerService
PayoutService
SessionService
ReportService
ReviewService
DisputeService
NotificationService
EventLedgerService
AdminActionService
SecurityEventService
```

## 6.2 State transition services

All important state transitions must be centralized.

Examples:

```text
BookingService.holdSlot()
PaymentService.initiatePayment()
PaymentWebhookService.processProviderEvent()
SessionService.startSession()
SessionService.completeSession()
ReportService.createReport()
ReviewService.createVerifiedReview()
DisputeService.openDispute()
RefundService.approveRefund()
RefundService.submitRefundToProvider()
RefundService.reconcileRefund()
PayoutService.calculateEligibility()
PayoutService.processPayout()
```

No controller should directly set:

```text
booking.status
payment.status
session.status
refund.status
payout.status
```

outside these services.

---

# 7. Database and Migration Plan

## 7.1 Migration chain

Implementation must start from the approved SQL chain:

```text
edutrust_schema_v1.sql
edutrust_schema_patch_v1_1.sql
edutrust_schema_patch_v1_2.sql
edutrust_schema_patch_v1_3.sql
```

## 7.2 Migration requirements

Every migration must be:

- version-controlled,
- executable on clean database,
- executable on staging clone,
- included in CI migration test,
- reversible where practical or accompanied by rollback plan,
- validated against DDL audit expectations.

## 7.3 Seed data

MVP seed data:

```text
Subjects:
- Mathematics
- Physics

Academic levels:
- Secondary 1AS
- Secondary 2AS
- Secondary 3AS
- BAC

Roles:
- PARENT
- TEACHER
- ADMIN
- OPS
- SUPPORT
```

## 7.4 Database safety tests

Before application code is considered ready, test:

- parent cannot book another parent’s student,
- double booking same slot fails,
- overlapping active teacher slots fail,
- payment amount mismatch fails,
- duplicate confirmed payment fails,
- review before completed paid session fails,
- duplicate review fails,
- payout without report fails,
- payout with open dispute fails,
- over-refund fails,
- refund reconciliation proof requirements fail when missing,
- idempotency identity mutation fails,
- event ledger mutation fails,
- ledger entry mutation fails.

---

# 8. API Implementation Plan

## 8.1 API conventions

Use approved conventions:

```text
Base path: /api/v1
JSON request/response
Bearer access token
X-Request-ID
Idempotency-Key where required
Standard error envelope
Cursor pagination
Allowlisted filtering/sorting
```

## 8.2 Required endpoint groups

```text
/auth
/parents
/students
/students/:id/permissions
/teachers
/teachers/search
/teachers/match
/teachers/subjects
/teachers/availability
/bookings
/payments
/refunds or embedded refund responses
/sessions
/reports
/reviews
/disputes
/notifications
/admin
/admin/refunds
/admin/payouts
/admin/events
/admin/security-events
```

## 8.3 API contract patch list before implementation

From UX/prototype phases, the following implementation-level API contracts must be formalized:

```text
GET /notifications
POST /notifications/:id/read
GET /auth/sessions
GET /account/security-events
GET /bookings?scope=teacher
POST /teachers/availability/slots/:id/block
POST /teachers/availability/slots/:id/unblock
GET /admin/refunds
GET /admin/refunds/:id
POST /admin/refunds/:id/reconcile
Refund summaries embedded in GET /payments/:id, GET /bookings/:id, GET /disputes/:id
Recovery/adjustment read summaries in payout/refund/admin finance responses
```

These are not architecture changes; they are implementation contract completion items.

---

# 9. Authentication and Authorization Plan

## 9.1 Authentication

Required:

- access tokens,
- refresh-token rotation,
- hashed refresh tokens only,
- session revocation,
- failed-login security events,
- rate limiting.

## 9.2 RBAC

Roles:

```text
PARENT
TEACHER
SUPPORT
OPS
ADMIN
```

## 9.3 Object ownership checks

Mandatory ownership checks:

```text
Parent → own students/bookings/payments/reports/refunds/disputes
Teacher → own profile/bookings/sessions/reports/payouts
OPS/Admin → scoped operational access
Support → limited/redacted access
```

## 9.4 Permission checks for minors

Student context access must require:

```text
parent ownership
or teacher assigned session context
or explicit student_permission scope
or audited admin/OPS authority
```

Teacher must not receive unrestricted Student Passport access.

---

# 10. Payment, Refund, Ledger, and Payout Plan

## 10.1 Payment provider abstraction

Implement a provider interface:

```text
create_payment_intent()
verify_webhook_signature()
parse_provider_event()
submit_refund()
parse_refund_event()
```

Initial provider may be:

```text
CIB / Edahabia / CASH_PILOT / BANK_TRANSFER / OTHER
```

Actual provider decision remains dependent on legal/payment-provider readiness.

## 10.2 Payment webhook transaction

Must implement exactly:

```text
verify webhook outside DB transaction
BEGIN
  insert/lock payment_provider_events(provider, provider_event_id)
  lock payment
  lock booking
  verify amount/currency
  branch fulfillable vs unfulfillable late payment
  update payment
  update booking if fulfillable
  create session if fulfillable
  create ledger transaction
  create event ledger rows
  mark provider event processed
COMMIT
```

## 10.3 Late payment branch

If booking expired/cancelled/unfulfillable:

```text
payment = CONFIRMED
booking remains EXPIRED/CANCELLED
session not created
slot not reassigned
teacher payable not created
refund/reconciliation workflow created
```

## 10.4 Refund lifecycle

Implement refund states:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

Do not emit:

```text
PAYMENT_REFUNDED
PAYMENT_PARTIALLY_REFUNDED
```

before refund success.

## 10.5 Payout calculation

Before payout processing, calculate from backend:

```text
gross_teacher_payable
- refund exposure from APPROVED / PROVIDER_PENDING / SUCCEEDED
- other deductions
= net_teacher_payable
```

Frontend must not calculate final payout.

## 10.6 Post-payout recovery

If refund occurs after payout paid:

```text
old payout remains PAID
old payout_items unchanged
new adjustment/recovery ledger transaction created
```

A-59 remains read-only in MVP until a formal manual adjustment command is approved.

---

# 11. Background Jobs Plan

Required background jobs:

| Job | Purpose | Critical rules |
|---|---|---|
| Hold expiry job | Expire stale booking holds | Idempotent; lock booking/slot |
| Payment timeout/reconciliation job | Detect stale payment pending states | Do not auto-confirm without provider proof |
| Slot generation job | Generate concrete slots from availability rules | Do not alter booked slots silently |
| Notification dispatch job | Send pending notifications | External providers not source of truth |
| Metrics worker | Recalculate teacher trust metrics | Only worker can update derived metrics |
| Payout eligibility job | Identify eligible payouts | Include refund exposure and disputes |
| Provider reconciliation job | Reconcile payment/refund/payout provider states | Must be auditable |
| Cleanup job | Expire idempotency keys / sessions per policy | Preserve audit/ledger history |

All jobs must be idempotent and safe to retry.

---

# 12. Frontend Implementation Planning

No frontend implementation starts yet. This section defines future work packages.

## 12.1 Frontend apps/routes

Recommended route groups:

```text
/parent
/teacher
/admin
/auth
```

## 12.2 Parent frontend work packages

```text
Auth + account
Student profiles
Student Passport
Permissions
Teacher search/match
Trust Profile
Availability/booking hold
Checkout/payment status
Session/report/review
Dispute/refund timeline
Notifications
```

## 12.3 Teacher frontend work packages

```text
Onboarding
Subjects & Pricing
Verification
Availability
Bookings/sessions
Attendance
Reports
Reviews
Earnings/payouts
Student context boundary
Notifications
```

## 12.4 Admin frontend work packages

```text
Admin dashboard
Verification queue/detail
Booking monitoring
Payment monitoring
Refund queue/detail/reconciliation
Dispute queue/detail
Payout queue/processing/failure
Recovery read view
Event ledger
Security events
Sensitive access modal
User suspension
```

## 12.5 Frontend state rules

Frontend must not be state authority.

Frontend must:

- render backend states,
- hide/disable actions based on backend eligibility,
- use idempotency keys for required actions,
- re-fetch after timeout,
- never assume success after network failure,
- never calculate final financial amounts.

---

# 13. Event Ledger and Audit Plan

## 13.1 Event writing pattern

Critical business action must insert event ledger in same transaction where possible.

Examples:

```text
BOOKING_CREATED
BOOKING_HELD
PAYMENT_INITIATED
PAYMENT_CONFIRMED
BOOKING_CONFIRMED
SESSION_STARTED
SESSION_COMPLETED
REPORT_CREATED
REVIEW_CREATED
DISPUTE_OPENED
DISPUTE_RESOLVED
REFUND_APPROVED
REFUND_PROVIDER_SUBMITTED
REFUND_SUCCEEDED
PAYMENT_PARTIALLY_REFUNDED
PAYOUT_PROCESSED
ADMIN_ACTION
SECURITY_EVENT
```

## 13.2 Sensitive admin access

Sensitive access must generate:

```text
ADMIN_ACTION and/or SECURITY_EVENT
```

for:

```text
verification documents
provider payloads
refund reconciliation proof
minor/student sensitive context
security events
audit details
ledger/recovery details
```

---

# 14. Testing Strategy

## 14.1 Unit tests

Required for:

- state transition services,
- permission checks,
- money calculations,
- refund allocation,
- payout calculation,
- idempotency logic,
- provider event parsing.

## 14.2 Integration tests

Required with real PostgreSQL:

- booking hold concurrency,
- double-booking prevention,
- payment webhook idempotency,
- late payment after expiry,
- refund lifecycle,
- over-refund prevention,
- payout blocked by dispute,
- post-payout recovery,
- event ledger writes,
- audit/security event writes.

## 14.3 E2E tests

Use Playwright or equivalent.

Critical E2E scenarios:

```text
Parent happy path
Payment pending
Payment failure
Late payment after expiry
Refund success/failure/rejected/cancelled
Dispute
No-show
Teacher report
Verified review
Payout blocked
Payout processed
Post-payout recovery display
Sensitive admin access
Permission revoked/expired
Duplicate tap
Network timeout
Operational incident
```

## 14.4 Security tests

Must include:

- parent cannot access another parent’s student,
- teacher cannot access unrelated student passport,
- teacher cannot edit trust metrics,
- support cannot approve refunds/payouts,
- admin sensitive access is logged,
- raw provider payload not exposed to parent/teacher,
- refresh tokens not stored raw.

## 14.5 Financial tests

Must include:

- decimal-safe calculations,
- no over-refund,
- partial refund allocation,
- payout net calculation with approved/provider-pending/succeeded exposure,
- post-payout refund recovery,
- ledger entries balanced,
- ledger immutable.

---

# 15. Environment Configuration

## 15.1 Environments

Recommended environments:

```text
local
integration/CI
staging
pilot-production
production
```

## 15.2 Configuration

Required configuration categories:

```text
DATABASE_URL
REDIS_URL
SECRET_KEY / token signing keys
PAYMENT_PROVIDER settings
WEBHOOK_SECRET(s)
OBJECT_STORAGE settings
SMS/EMAIL provider settings
CORS/allowed origins
RATE_LIMIT settings
AUDIT_LOG settings
FEATURE_FLAGS for pilot-only flows
```

Secrets must never be committed.

## 15.3 Feature flags

Use feature flags for:

```text
payment provider mode
cash pilot mode
refund provider integration
notifications provider
admin-sensitive payload access
```

Feature flags must not bypass audit or state machines.

---

# 16. Deployment and CI/CD Plan

## 16.1 CI pipeline

Minimum CI steps:

```text
lint backend
lint frontend
type check
unit tests
PostgreSQL migration test on clean database
integration tests
security/dependency scan
frontend build
E2E smoke tests on staging-like environment
```

## 16.2 Deployment stages

```text
merge to main
run CI
build images
deploy to staging
run migrations
run smoke tests
manual approval
pilot deployment
monitor logs/events
```

## 16.3 Migration safety

Migrations must run before app version requiring them.

For payment/financial migrations:

```text
manual approval required
backup required
rollback plan required
```

---

# 17. Observability and Operations

## 17.1 Logging

Use structured logs with:

```text
request_id
actor_user_id when available
role
entity_type
entity_id
operation
status
error_code
```

Do not log raw payment provider payloads or sensitive documents.

## 17.2 Metrics

Track:

```text
booking holds
hold expiry rate
payment initiation rate
payment confirmation latency
webhook duplicate count
late payment count
refund lifecycle counts
payout eligible/blocked/failed
dispute rate
session completion rate
report completion rate
review rate
teacher trust metrics recalculation
```

## 17.3 Alerts

Alert on:

```text
payment webhook failures
ledger imbalance attempt
late payment after expiry
refund provider failures
payout provider failures
high dispute/safety events
sensitive access anomalies
admin override spikes
```

---

# 18. Product/Ops Policy Dependencies

The following remain open and should be resolved before production behavior is finalized:

1. Booking hold duration
2. Payment checkout timeout
3. Late-payment auto-refund vs OPS review
4. No-show grace periods
5. Parent dispute window
6. Payout delay
7. Refund allocation teacher/platform
8. Review eligibility after partial refund
9. Notification channels
10. Arabic/French terminology

## 18.1 Implementation handling before policy is finalized

Implementation may use configuration placeholders in staging, but production launch cannot proceed until these are approved.

No hardcoded arbitrary values should be introduced without a Product/Ops Policy decision.

---

# 19. Work Breakdown Structure

## Phase 0 — Implementation Gate Preparation

Deliverables:

```text
Stack decision
Repository setup plan
Migration artifact verification
API contract completion notes
Product/Ops policy decision plan
Security model review
Payment provider legal/ops decision plan
```

Exit criteria:

```text
Implementation Gate approval
```

## Phase 1 — Engineering Foundation

Work packages:

```text
Repository setup
Docker/local environment
PostgreSQL setup
Migration chain
Base backend app
Base frontend app
Auth foundation
RBAC foundation
Request ID/error model
Event ledger service
Idempotency service
CI pipeline skeleton
```

## Phase 2 — Identity, Profiles, Taxonomy

Work packages:

```text
Users/roles
Parent profiles
Student profiles
Student permissions
Teacher profiles
Subjects/academic levels
Teacher subjects/pricing
Verification submission/admin review
```

## Phase 3 — Availability, Search, Matching

Work packages:

```text
Availability rules
Concrete slots
Block/unblock
Teacher search
Rule-based matching
Trust profile read model
```

## Phase 4 — Booking and Payment Core

Work packages:

```text
Booking hold
Hold expiry job
Payment initiation
Payment provider adapter
Payment webhook processing
Fulfillable payment branch
Late payment after expiry branch
Ledger creation
Session synchronous creation
```

## Phase 5 — Sessions, Reports, Reviews, Passport

Work packages:

```text
Session start/complete/no-show
Session reports
Student progress events
Student Passport v0
Verified reviews
Review moderation basics
```

## Phase 6 — Disputes, Refunds, Payouts

Work packages:

```text
Dispute open/review/resolve
Refund lifecycle
Refund reconciliation
Partial refund allocation
Payout eligibility
Payout processing
Payout failure handling
Post-payout recovery read model
```

## Phase 7 — Notifications and Admin Operations

Work packages:

```text
Notification model
Notification delivery worker
Admin dashboard
Verification queue
Booking/payment monitoring
Refund queue/detail
Dispute queue/detail
Payout queue/detail
Event ledger views
Security event views
Sensitive access modal/audit
User suspension
```

## Phase 8 — Frontend Completion and E2E

Work packages:

```text
Parent flows
Teacher flows
Admin flows
Responsive behavior
RTL placeholders
Accessibility pass
Error/loading/empty states
E2E tests
Clickable prototype parity check
```

## Phase 9 — Staging, Pilot Readiness, Launch Gate

Work packages:

```text
Staging deployment
Payment provider sandbox testing
Security review
Privacy review
Data retention review
Legal/payment review
Operational runbooks
Support scripts
Pilot teacher/parent onboarding
Launch readiness review
```

---

# 20. Definition of Done

A feature is not done unless:

- API endpoint implemented and documented,
- authorization and ownership tests pass,
- state transition tests pass,
- Event Ledger event generated where required,
- idempotency implemented where required,
- database constraints respected,
- frontend handles loading/error/empty/permission states,
- sensitive data not leaked,
- audit/security event generated when required,
- E2E path passes if user-facing,
- no out-of-scope MVP feature added.

---

# 21. Implementation Gate Checklist

Before starting implementation, confirm:

```text
[ ] Technical stack approved
[ ] Repository structure approved
[ ] All DDL artifacts available, including v1.2
[ ] Migration chain tested on clean PostgreSQL
[ ] API contract clarifications approved
[ ] Product/Ops policy decision plan created
[ ] Payment provider/legal path defined for MVP/pilot
[ ] Security/privacy requirements accepted
[ ] Testing strategy accepted
[ ] CI/CD plan accepted
[ ] Implementation phases accepted
[ ] Team roles/responsibilities assigned
[ ] Change request process accepted
```

Only then may the project move to backend/frontend implementation.

---

# 22. Risks Before Implementation

| Risk | Severity | Mitigation |
|---|---:|---|
| Missing v1.2 migration artifact | High | Collect and verify all migration files before implementation |
| Payment provider legal/compliance uncertainty | Critical | Legal/payment provider decision before production payment launch |
| Overbuilding admin/analytics | High | Follow MVP work breakdown only |
| Frontend bypassing state authority | Critical | Backend eligibility-driven UI and tests |
| Refund/payout financial bugs | Critical | Integration tests and ledger validation |
| Student data overexposure | Critical | Permission checks and audit/security tests |
| Sensitive admin access not logged | High | Mandatory audit tests |
| Open policy values hardcoded arbitrarily | Medium/High | Product/Ops Policy v1.0 before production |

---

# 23. Recommended Next Step

Recommended next document:

```text
EduTrust_Implementation_Planning_Audit_v1.0.md
```

Purpose:

- verify this implementation plan against locked architecture,
- identify missing work packages,
- confirm no implementation begins prematurely,
- prepare the Implementation Gate.

Alternative next document:

```text
EduTrust_Product_Ops_Policy_Decisions_v1.0.md
```

Purpose:

- close the ten open policy decisions before production-level behavior.

---

# 24. Final Status

```text
EduTrust Implementation Planning v1.0 Status: READY FOR REVIEW
```

Implementation remains:

```text
NOT APPROVED
```

Approved next activity:

```text
Implementation Planning Review / Audit
```

Not approved:

```text
Backend implementation
Frontend implementation
Production UI code
Database changes
API changes
State-machine changes
MVP expansion
```
