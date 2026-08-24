# EduTrust Algeria — State Machines v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** State Machines v1.0  
**Depends on:**
1. EduTrust MVP PRD v1.0
2. EduTrust PostgreSQL Database Schema v1.0
3. EduTrust API Architecture v1.0

**Architecture status:** API Architecture Gate #3 approved.  
**Architecture model:** Modular Monolith + PostgreSQL.  
**Implementation status:** Specification only. Do **not** begin backend implementation from this document alone.

---

# 1. Executive Summary

This document formally defines the core EduTrust MVP state machines:

1. Booking State Machine
2. Payment State Machine
3. Session State Machine
4. Review State Machine
5. Dispute State Machine
6. Payout State Machine

It also defines the cross-domain transition map:

```text
Booking → Payment → Session → Report → Review → Payout
```

The purpose is to prevent EduTrust from entering inconsistent or financially unsafe states such as:

```text
BOOKED booking without confirmed payment
CONFIRMED payment without scheduled session
COMPLETED booking without completed session
Review without verified completed session
Payout while dispute is open
Partial refund with no refund lifecycle record
Duplicate payment webhook processing
Duplicate payout for same session
```

---

# 2. Authoritative Architecture Decisions

The following decisions are now authoritative and must be carried into implementation and Schema Patch v1.1.

## 2.1 Approved decisions

| Decision | Status |
|---|---|
| Modular Monolith + PostgreSQL | Approved |
| REST-style `/api/v1` | Approved |
| RBAC + ownership + state-transition authority | Approved |
| No arbitrary public status updates | Approved |
| Payment webhook as atomic transaction boundary | Approved |
| Internal Marketplace Transaction Ledger, not full SCF accounting | Approved |
| Teacher Trust Metrics are derived, not teacher-editable | Approved |
| Student Passport built from structured data, not AI | Approved |
| No AI in MVP state transitions | Approved |
| No microservices in MVP | Approved |

## 2.2 Decisions requiring Schema Patch v1.1 before implementation

These are not database redesigns. They are schema patches required to safely implement the approved API/state-machine behavior.

### A. Add `api_idempotency_keys`

Required because:

- `event_ledger` is not a response replay store.
- Idempotency is needed beyond payments.
- Booking hold, refund, payout, and other retryable operations need durable replay behavior.

Used by:

```text
POST /bookings/hold
POST /payments/initiate
POST /payments/:id/refund
POST /admin/payouts/process
other retryable POST operations
```

### B. Add `payment_provider_events`

Required because:

```text
provider_event_id ≠ provider_transaction_id
```

A provider may resend the same event, or send multiple events for one financial transaction.

Required identity:

```text
UNIQUE(provider, provider_event_id)
```

### C. Add `refunds`

Required because MVP supports:

- Refund lifecycle
- Partial refunds
- Provider refund status
- Refund approval
- Refund idempotency
- Dispute-linked refunds

Minimum fields:

```text
refund_id
payment_id
booking_id
dispute_id
requested_amount
approved_amount
currency
reason
status
provider_refund_id
idempotency_key
requested_by
approved_by
created_at
completed_at
```

### D. Synchronous session creation

A `sessions` row must be created synchronously inside the same database transaction that confirms payment and books the booking.

Approved flow:

```text
PAYMENT CONFIRMED
   ↓
BOOKING BOOKED
   ↓
SESSION CREATED as SCHEDULED
   ↓
LEDGER CREATED
   ↓
EVENT LEDGER WRITTEN
   ↓
COMMIT
```

This prevents:

```text
payment = CONFIRMED
booking = BOOKED
session = missing
```

---

# 3. Global State Machine Principles

## 3.1 No arbitrary status updates

The API must never allow generic status updates such as:

```http
PATCH /bookings/:id
{
  "status": "BOOKED"
}
```

All state transitions must happen through explicit commands/endpoints/services.

Examples:

```text
POST /bookings/hold
POST /payments/initiate
POST /payments/webhooks/:provider
POST /sessions/:id/start
POST /sessions/:id/complete
POST /sessions/:id/review
POST /admin/payouts/process
```

## 3.2 State-transition authority is separate from RBAC

Having a role is not enough.

Each transition requires:

```text
Role authorization
+ Object ownership
+ Current state validity
+ Transition authority
+ Business preconditions
```

Example:

A parent may own a booking, but still cannot transition it directly from `PAYMENT_PENDING` to `BOOKED`. Only a verified payment confirmation or approved OPS manual pilot rule can do that.

## 3.3 PostgreSQL is the final consistency guard

The service layer must validate rules, but PostgreSQL constraints/triggers must remain the final guard against:

- Double booking
- Duplicate reviews
- Payment amount mismatch
- Payout for ineligible session
- Ledger mutation
- Event Ledger mutation

## 3.4 Business change + event ledger in same transaction

For critical state transitions:

```text
BEGIN
  business state change
  event_ledger insert
COMMIT
```

If the business change commits, the audit event should commit with it.

## 3.5 External provider calls outside DB transactions

Never keep a PostgreSQL transaction open while waiting for:

- Payment provider checkout creation
- Payment provider refund API
- Bank/payout provider
- SMS/email provider

Pattern:

```text
DB transaction to create internal intent
COMMIT
External provider call
DB transaction to record result
COMMIT
```

Webhook confirmation is different: provider already called EduTrust. The webhook handler verifies the incoming event first, then performs one internal DB transaction.

## 3.6 Idempotency is mandatory for retryable commands

At minimum:

```text
booking hold
payment initiation
payment webhook processing
refund request/approval
payout processing
```

Duplicate retry with same key and same body returns the original response.

Duplicate retry with same key and different body returns:

```text
409 IDEMPOTENCY_KEY_CONFLICT
```

## 3.7 Separate financial truth from educational truth

A session may have happened even if a refund is later issued.

Therefore:

```text
session.status
booking.status
payment.status
refund.status
```

must not be collapsed into one field.

Example:

```text
session.status = COMPLETED
payment.status = PARTIALLY_REFUNDED
dispute.status = RESOLVED
booking.status = COMPLETED
```

This is valid if the session occurred but a partial refund was granted.

---

# 4. Global Actors and Authorities

| Actor | Meaning |
|---|---|
| PARENT | Parent/guardian who owns student profile and booking |
| TEACHER | Teacher assigned to session/booking |
| PAYMENT_PROVIDER | External payment provider calling webhook |
| SYSTEM_JOB | Internal scheduled job, e.g. hold expiry, notification dispatch |
| METRICS_WORKER | Internal derived-metrics worker |
| SUPPORT | Limited operational support |
| OPS | Operations user with policy-limited authority |
| ADMIN | Elevated platform administrator |

## 4.1 Authority hierarchy

Admin override is not a normal transition. It must require:

- Explicit endpoint
- Reason
- Actor identity
- Event Ledger `ADMIN_ACTION`
- Security event when sensitive
- No silent mutation

---

# 5. State Machine Notation

Each state machine section includes:

- States
- Allowed transitions
- Forbidden transitions
- Transition authority
- Triggering endpoint/service
- Preconditions
- Database invariants
- Side effects
- Event Ledger event
- Notification event
- Idempotency requirements
- Concurrency/locking requirements
- Failure behavior
- Compensation/reversal behavior
- Timeout/expiry behavior
- Admin override rules
- Audit requirements

---

# 6. Booking State Machine

## 6.1 Booking states

From approved schema:

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

Important note:

`AVAILABLE` is not a booking state. It is an `availability_slots.status` state. A booking begins when a parent holds an available slot.

## 6.2 Normal booking flow

```text
AVAILABLE SLOT
   ↓ POST /bookings/hold
HELD
   ↓ POST /payments/initiate
PAYMENT_PENDING
   ↓ payment webhook confirms
BOOKED
   ↓ session completed
COMPLETED
```

## 6.3 Side flows

```text
HELD → EXPIRED
HELD → CANCELLED
PAYMENT_PENDING → CANCELLED / EXPIRED
BOOKED → CANCELLED
BOOKED → DISPUTED
COMPLETED → DISPUTED
DISPUTED → REFUNDED / COMPLETED / CANCELLED depending resolution
```

## 6.4 Allowed transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| No booking + slot `AVAILABLE` | `HELD` | Parent via BookingService | `POST /bookings/hold` | Parent owns student; teacher offering valid; slot available | One active booking per slot; FK student-parent | Slot becomes `HELD`; hold expiry set | `BOOKING_CREATED`, `BOOKING_HELD` | Optional hold notification | Required | Lock slot `FOR UPDATE` |
| `HELD` | `PAYMENT_PENDING` | Parent via PaymentService | `POST /payments/initiate` | Parent owns booking; hold not expired | Payment amount equals booking price | Payment row created; payment provider checkout initiated after commit | `PAYMENT_INITIATED` | Payment pending | Required | Lock booking `FOR UPDATE` |
| `PAYMENT_PENDING` | `BOOKED` | Payment webhook or approved OPS pilot | `POST /payments/webhooks/:provider` or controlled OPS endpoint | Authenticated webhook; payment confirmed; amount/currency valid | One confirmed payment per booking | Session row created `SCHEDULED`; ledger entries created; slot becomes `BOOKED` | `PAYMENT_CONFIRMED`, `BOOKING_CONFIRMED` | Booking confirmed | Webhook idempotency required | Lock payment + booking |
| `BOOKED` | `COMPLETED` | SessionService after session completion | `POST /sessions/:id/complete` | Session completed with attendance `PRESENT` | Session belongs to booking | Booking marked completed | `SESSION_COMPLETED` with booking metadata | Session completed/report requested | Command idempotency recommended | Lock session + booking |
| `HELD` | `EXPIRED` | System job | Hold expiry job | `hold_expires_at < now()` and no confirmed payment | Slot can be released | Slot returns `AVAILABLE` | `BOOKING_CANCELLED` with reason `HOLD_EXPIRED` or expiry metadata | Optional | Job idempotent | Lock booking + slot |
| `PAYMENT_PENDING` | `EXPIRED` | System job | Payment timeout job | Payment not confirmed before expiry window | No confirmed payment exists | Slot returns `AVAILABLE`; payment may remain `FAILED`/expired by policy | `BOOKING_CANCELLED` metadata `PAYMENT_TIMEOUT` | Payment timeout | Job idempotent | Lock booking + payment + slot |
| `HELD`/`PAYMENT_PENDING`/`BOOKED` | `CANCELLED` | Parent/Teacher/OPS/Admin under policy | `POST /bookings/:id/cancel` | Actor authorized; deadline/policy allows | No completed session | Slot released if not already consumed; refund flow may start if paid | `BOOKING_CANCELLED` | Booking cancelled | Recommended | Lock booking + slot + payment if paid |
| `BOOKED`/`COMPLETED` | `DISPUTED` | Parent/Teacher via DisputeService | `POST /disputes` | Actor participates in booking/session | Dispute linked to booking/session/payment | Payout blocked; payment may become `DISPUTED` | `DISPUTE_OPENED` | Dispute update | Recommended | Lock dispute target rows |
| `DISPUTED` | `REFUNDED` | OPS/Admin via RefundService | `POST /payments/:id/refund` | Full refund approved | Refund record + ledger reversal | Payment `REFUNDED`; booking financial status `REFUNDED` | `REFUND_ISSUED`, `PAYMENT_REFUNDED`, `DISPUTE_RESOLVED` | Refund issued | Required | Lock payment + booking + dispute |
| `DISPUTED` | previous operational state | OPS/Admin via DisputeService | `POST /admin/disputes/:id/resolve` | Dispute resolved without full refund | Dispute resolved | Payout may unblock if eligible | `DISPUTE_RESOLVED` | Dispute resolved | Recommended | Lock dispute + booking |

## 6.5 Booking forbidden transitions

The API must reject these transitions:

| Forbidden transition | Reason |
|---|---|
| `HELD → BOOKED` directly by parent | Requires payment confirmation or approved manual pilot authority |
| `HELD → COMPLETED` | No payment/session lifecycle |
| `PAYMENT_PENDING → COMPLETED` | Missing confirmed booking/session |
| `CANCELLED → BOOKED` | Must create new booking |
| `EXPIRED → BOOKED` | Must create new hold/booking |
| `REFUNDED → BOOKED` | Financially closed |
| `COMPLETED → BOOKED` | Completed is terminal except dispute/refund metadata |
| Any public `PATCH status` | Violates state-transition authority |

## 6.6 Booking timeout/expiry behavior

### Hold expiry

Default decision before implementation:

```text
10 or 15 minutes; final value remains open decision
```

Behavior:

```text
HELD + hold_expires_at < now()
   ↓
EXPIRED
   ↓
slot AVAILABLE
```

### Payment pending timeout

If checkout is initiated but not confirmed:

```text
PAYMENT_PENDING + payment timeout
   ↓
EXPIRED or CANCELLED depending policy
   ↓
slot AVAILABLE
```

Payment provider late confirmations must be handled carefully:

- If booking expired and slot was rebooked, late webhook must not create inconsistent booking.
- Payment should be flagged for reconciliation/refund, not auto-booked.

## 6.7 Booking compensation/reversal

Booking has no financial reversal by itself. Financial reversal must happen through:

```text
refunds
ledger reversal transactions
payment status updates
```

If a booking was wrongly confirmed due to provider/payment mismatch, the system must:

1. Stop further session/payout actions.
2. Open admin/security event.
3. Use refund/reversal workflow if money moved.
4. Never silently delete booking/payment/ledger records.

---

# 7. Payment State Machine

## 7.1 Payment states

From approved schema:

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

`NOT_STARTED` is conceptual before a payment row exists.

## 7.2 Payment provider event identity

State Machines v1.0 requires Schema Patch v1.1:

```text
payment_provider_events
```

Minimum identity:

```text
UNIQUE(provider, provider_event_id)
```

Do not confuse:

```text
provider_event_id        = webhook event identity
provider_transaction_id  = financial transaction identity
```

## 7.3 Refund lifecycle requirement

State Machines v1.0 requires Schema Patch v1.1:

```text
refunds
```

Recommended refund statuses:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

The payment state summarizes cumulative refund state:

```text
CONFIRMED → REFUND_PENDING → PARTIALLY_REFUNDED / REFUNDED
```

## 7.4 Normal payment flow

```text
NOT_STARTED
   ↓ POST /payments/initiate
INITIATED
   ↓ provider pending/checkout state
PENDING
   ↓ verified provider webhook
CONFIRMED
```

## 7.5 Payment webhook confirmation flow

This is the highest-risk state transition in the MVP.

Required exact transaction flow:

```text
Before DB transaction:
  1. Authenticate/verify webhook signature
  2. Parse and validate provider event shape
  3. Extract provider_event_id and provider_transaction_id

Inside one PostgreSQL transaction:
  4. Insert or lock payment_provider_events(provider, provider_event_id)
  5. If duplicate processed event: return replay/duplicate response
  6. Lock payment row FOR UPDATE
  7. Lock booking row FOR UPDATE
  8. Verify payment belongs to booking
  9. Verify amount
  10. Verify currency
  11. Update payment state to CONFIRMED
  12. Update booking state to BOOKED
  13. Create sessions row as SCHEDULED
  14. Create ledger transaction and balanced ledger entries
  15. Insert event_ledger PAYMENT_CONFIRMED
  16. Insert event_ledger BOOKING_CONFIRMED with session_id metadata
  17. Mark payment_provider_events as PROCESSED
COMMIT
```

If any critical step fails, business state must remain consistent.

## 7.6 Allowed payment transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| `NOT_STARTED` | `INITIATED` | Parent via PaymentService | `POST /payments/initiate` | Booking `HELD`; parent owns booking; amount known | Payment amount equals booking amount | Booking `PAYMENT_PENDING`; provider checkout created after commit | `PAYMENT_INITIATED` | Payment pending | Required | Lock booking |
| `INITIATED` | `PENDING` | Provider/System | Provider callback/webhook | Valid provider state | Provider event unique | Payment pending recorded | Optional `PAYMENT_INITIATED` metadata | None or pending | Provider event idempotency | Lock payment |
| `INITIATED`/`PENDING` | `CONFIRMED` | Payment provider webhook | `POST /payments/webhooks/:provider` | Authenticated event; amount/currency match; booking valid | Unique confirmed payment per booking | Booking `BOOKED`; session `SCHEDULED`; ledger created | `PAYMENT_CONFIRMED`, `BOOKING_CONFIRMED` | Booking/payment confirmed | Required provider event identity | Lock payment + booking |
| `INITIATED`/`PENDING` | `FAILED` | Provider webhook/System | Webhook or timeout reconciliation | Provider says failed or checkout expired | No confirmed payment | Booking may expire/cancel depending policy | `PAYMENT_FAILED` | Payment failed | Provider event idempotency | Lock payment + booking |
| `CONFIRMED` | `DISPUTED` | DisputeService | `POST /disputes` | Valid participant dispute | Dispute linked | Payout blocked | `DISPUTE_OPENED` | Dispute update | Recommended | Lock payment + dispute |
| `CONFIRMED`/`DISPUTED` | `REFUND_PENDING` | OPS/Admin via RefundService | `POST /payments/:id/refund` | Refund approved; refund row created | Refund amount <= remaining refundable amount | Provider refund call after internal approval | `REFUND_ISSUED` | Refund initiated | Required | Lock payment + refund + booking |
| `REFUND_PENDING` | `PARTIALLY_REFUNDED` | Provider refund result/System | Provider refund webhook or reconciliation | Refund succeeded; cumulative refund < payment amount | Refund row succeeded; ledger reversal balanced | Payment partially refunded | `PAYMENT_REFUNDED` metadata partial | Refund processed | Provider refund event idempotency | Lock payment + refund |
| `REFUND_PENDING` | `REFUNDED` | Provider refund result/System | Provider refund webhook or reconciliation | Refund succeeded; cumulative refund = payment amount | Refund row succeeded; ledger reversal balanced | Booking may become `REFUNDED` when full refund | `PAYMENT_REFUNDED` | Refund processed | Provider refund event idempotency | Lock payment + refund + booking |
| `REFUND_PENDING` | `CONFIRMED`/`DISPUTED` | System/Admin | Refund failure handling | Provider refund failed | Refund row `FAILED` | Payment restored to prior financial state | `ADMIN_ACTION` or refund failure event metadata | Refund failed | Required | Lock payment + refund |

## 7.7 Payment forbidden transitions

| Forbidden transition | Reason |
|---|---|
| `NOT_STARTED → CONFIRMED` | Must have payment row and provider verification |
| `INITIATED → REFUNDED` | Cannot refund unconfirmed payment |
| `FAILED → CONFIRMED` without verified provider event | Unsafe late mutation |
| `CONFIRMED → FAILED` | Use refund/dispute/reversal, not failure |
| `REFUNDED → CONFIRMED` | Financially reversed; create new booking/payment |
| Public API direct status mutation | Violates payment authority |

## 7.8 Duplicate/replayed webhook behavior

### Same provider event replay

If:

```text
provider + provider_event_id already PROCESSED
```

Return HTTP 200 with duplicate response. Do not mutate state again.

### Same financial transaction, new event

If provider sends different events for same transaction:

- Process only if event type is valid for current state.
- Enforce `provider_transaction_id` uniqueness where applicable.
- Do not create duplicate confirmed payment.

### Conflicting duplicate

If same provider transaction arrives with different amount/currency:

```text
409 PAYMENT_PROVIDER_CONFLICT
```

Actions:

- Do not confirm payment.
- Store provider event as rejected/failed for audit.
- Log security/ops event.
- Notify OPS/Admin.

## 7.9 Payment failure/compensation behavior

If webhook processing fails before commit:

- No partial business state should persist.
- Provider may retry.

If provider confirms payment but internal processing repeatedly fails:

- Payment provider event remains unprocessed or failed depending schema patch behavior.
- OPS reconciliation queue must surface issue.
- Do not mark booking `BOOKED` unless transaction fully succeeds.

If refund provider succeeds but internal update fails:

- Reconciliation must detect provider refund and complete internal refund state.
- This is why `provider_refund_id` and `payment_provider_events` are required.

---

# 8. Session State Machine

## 8.1 Session states

From approved schema:

```text
SCHEDULED
STARTED
COMPLETED
NO_SHOW_STUDENT
NO_SHOW_TEACHER
CANCELLED
DISPUTED
```

## 8.2 Session materialization rule

A session is created synchronously inside payment-confirmation transaction.

```text
Payment CONFIRMED
Booking BOOKED
Session SCHEDULED
```

There must be no stable production state where:

```text
booking.status = BOOKED
payment.status = CONFIRMED
session row missing
```

## 8.3 Normal session flow

```text
SCHEDULED
   ↓ teacher starts
STARTED
   ↓ teacher completes
COMPLETED
```

## 8.4 Allowed session transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| No session | `SCHEDULED` | PaymentWebhookService | Payment confirmation transaction | Payment confirmed; booking booked | One session per booking | Session available to teacher/parent dashboards | `BOOKING_CONFIRMED` metadata `session_id` | Booking/session scheduled | Webhook idempotency | Lock payment + booking |
| `SCHEDULED` | `STARTED` | Assigned teacher or OPS | `POST /sessions/:id/start` | Actor is assigned teacher; within allowed time window | Session belongs to booking/teacher | actual_start set | `SESSION_STARTED` | Parent notified session started | Recommended | Lock session |
| `STARTED` | `COMPLETED` | Assigned teacher or OPS | `POST /sessions/:id/complete` | actual_start exists; actual_end valid; attendance `PRESENT` | Completion check constraints | Booking becomes `COMPLETED`; report can be created | `SESSION_COMPLETED` | Parent notified; report requested | Recommended | Lock session + booking |
| `SCHEDULED` | `NO_SHOW_STUDENT` | Teacher report, OPS confirmation if disputed | `POST /sessions/:id/no-show` | Grace period elapsed; student absent | Session belongs to teacher | Attendance metric candidate; parent notified | `SESSION_NO_SHOW` | No-show notification | Recommended | Lock session |
| `SCHEDULED` | `NO_SHOW_TEACHER` | OPS/Admin after parent report or evidence | `POST /sessions/:id/no-show` + dispute review | Parent reports teacher absent; OPS confirms | Session belongs to booking | Refund/dispute likely; teacher metric impact | `SESSION_NO_SHOW`, `DISPUTE_OPENED` if needed | Parent/teacher notified | Recommended | Lock session + dispute |
| `SCHEDULED`/`STARTED` | `CANCELLED` | BookingService/OPS | Booking cancellation flow | Booking cancellation allowed | Booking/session linked | Booking cancelled; refund policy may apply | `BOOKING_CANCELLED` | Cancellation notification | Recommended | Lock booking + session |
| `SCHEDULED`/`STARTED`/`COMPLETED`/no-show | `DISPUTED` | DisputeService | `POST /disputes` | Participant opens dispute | Dispute linked | Payout blocked | `DISPUTE_OPENED` | Dispute update | Recommended | Lock session + dispute |

## 8.5 Session forbidden transitions

| Forbidden transition | Reason |
|---|---|
| `SCHEDULED → COMPLETED` by teacher without start | MVP requires start first; OPS override only with reason |
| `COMPLETED → STARTED` | Completed is terminal except dispute annotation |
| `NO_SHOW_TEACHER → COMPLETED` | Must resolve through admin/dispute; do not pretend session happened |
| `NO_SHOW_STUDENT → COMPLETED` | Must create new session if later delivered |
| `CANCELLED → STARTED` | Cancelled sessions cannot be started |
| Parent directly marking session completed | Parent has dispute/confirmation feedback, not completion authority |

## 8.6 No-show handling

### Student no-show

Teacher may report `NO_SHOW_STUDENT` after defined grace period.

Rules:

- Parent is notified.
- Parent may dispute.
- Payout eligibility depends on cancellation/no-show policy.
- Attendance and trust metrics update only after dispute window or admin confirmation where needed.

### Teacher no-show

Parent report should not directly and finally mark teacher absent without review.

Recommended flow:

```text
Parent reports teacher no-show
   ↓
Dispute opened or no-show claim recorded
   ↓
OPS/Admin reviews evidence
   ↓
Session marked NO_SHOW_TEACHER if confirmed
   ↓
Refund flow may start
```

## 8.7 Session completion side effects

When session becomes `COMPLETED`:

- Booking becomes `COMPLETED`.
- Parent receives session completed notification.
- Teacher is prompted to create report.
- Review is not yet necessarily created, but eligibility becomes possible after report/notification policy.
- Payout is not yet eligible until report exists and no open dispute.

---

# 9. Report Lifecycle

Report is not requested as a standalone state machine, but it is required in the cross-domain lifecycle.

## 9.1 Report states

The current schema has one report row per session and no explicit report status. MVP lifecycle is:

```text
NOT_CREATED
   ↓
CREATED
   ↓ optional limited edit window
LOCKED/FINAL by policy, if implemented later
```

## 9.2 Report creation authority

| Action | Authority | Endpoint | Preconditions | Event |
|---|---|---|---|---|
| Create report | Assigned teacher | `POST /sessions/:id/report` | Session `COMPLETED`; teacher owns session | `REPORT_CREATED` |
| View report | Parent/teacher/OPS/Admin scoped | `GET /sessions/:id/report` | Ownership or operational permission | None |
| Patch report | Teacher in edit window or OPS/Admin | `PATCH /sessions/:id/report` | Policy allows edit | `ADMIN_ACTION` or report update metadata |

## 9.3 Report side effects

Creating a report must create structured `student_progress_events`.

Mapping:

| Report field | Progress event |
|---|---|
| topics_covered | `TOPIC_COVERED` |
| skills_practiced | `SKILL_PRACTICED` |
| homework | `HOMEWORK_ASSIGNED` |
| teacher_observations | `PROGRESS_NOTE` or manual structured weakness/strength fields |
| progress_indicator | `PROGRESS_NOTE` with numeric value |

No AI-generated Student Passport source of truth in MVP.

---

# 10. Review State Machine

## 10.1 Review states

From approved schema:

```text
VISIBLE
FLAGGED
HIDDEN
REMOVED
```

Additionally, eligibility states exist conceptually before the review row:

```text
NOT_ELIGIBLE
ELIGIBLE
SUBMITTED
```

## 10.2 Review eligibility

A parent may create a review only if:

```text
booking.status = COMPLETED
payment.status = CONFIRMED
session.status = COMPLETED
review does not already exist
reviewer is parent/guardian of the student
reviewer is not the teacher
```

Important refund note:

- If a full refund occurred before review, review creation is not allowed in MVP.
- If a partial refund occurs after a review, the existing verified review remains unless moderated for policy/fraud.
- If partial refund occurs before review, product/legal decision is required; MVP default is strict `payment.status = CONFIRMED` at review creation.

## 10.3 Allowed review transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| No review + `ELIGIBLE` | `VISIBLE` | Parent owner | `POST /sessions/:id/review` | Eligibility rules satisfied | `reviews.session_id UNIQUE`; teacher self-review blocked | Teacher rating source data updated later by metrics worker | `REVIEW_CREATED` | Teacher may be notified | Recommended | Lock session/review eligibility or rely on unique constraint |
| `VISIBLE` | `FLAGGED` | System/OPS/Admin | Admin moderation | Abuse/fraud signal | Review exists | Hidden from ranking decisions only if policy says | `ADMIN_ACTION` | Optional | Recommended | Lock review |
| `FLAGGED` | `HIDDEN` | OPS/Admin | `POST /admin/reviews/:id/moderate` | Policy violation in text/content | Review record preserved | Comment hidden; rating handling per policy | `ADMIN_ACTION` | Optional | Recommended | Lock review |
| `FLAGGED`/`HIDDEN` | `VISIBLE` | OPS/Admin | Moderation endpoint | Review cleared | Review exists | Restored visibility | `ADMIN_ACTION` | Optional | Recommended | Lock review |
| `VISIBLE`/`FLAGGED`/`HIDDEN` | `REMOVED` | Admin only | Moderation endpoint | Fraud/legal/safety policy | Review record preserved | Excluded from public display and metrics if policy | `ADMIN_ACTION` | Optional | Required for admin operation | Lock review |

## 10.4 Forbidden review transitions

| Forbidden transition | Reason |
|---|---|
| Create review before session completed | Fake/unverified review risk |
| Create review for cancelled/no-show session | Not a completed tutoring session |
| Create duplicate review for same session | One verified review per completed session |
| Teacher creates review for self | Conflict of interest |
| Arbitrary user reviews teacher | Violates verified review principle |
| Delete review physically | Preserve auditability; use status |

## 10.5 Review failure behavior

If review creation fails due duplicate insert:

- Return `409 DUPLICATE_REVIEW`.
- Do not create second review.

If eligibility changed during request:

- Return `422 REVIEW_NOT_ELIGIBLE`.

---

# 11. Dispute State Machine

## 11.1 Dispute states

From approved schema:

```text
OPEN
UNDER_REVIEW
RESOLVED
REJECTED
CANCELLED
```

## 11.2 Dispute categories

```text
TEACHER_NO_SHOW
STUDENT_NO_SHOW
SESSION_QUALITY
PAYMENT_REFUND
SAFETY
REPORT_ISSUE
OTHER
```

Safety disputes always receive highest priority.

```text
category = SAFETY → priority = 1
```

## 11.3 Allowed dispute transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| No dispute | `OPEN` | Parent/Teacher participant | `POST /disputes` | Actor participates in booking/session/payment | At least one target exists | Booking/session/payment may become `DISPUTED`; payout blocked | `DISPUTE_OPENED` | Dispute opened | Recommended | Lock target rows |
| `OPEN` | `UNDER_REVIEW` | OPS/Admin | Admin review action | Dispute assigned | Dispute exists | Admin review starts | `ADMIN_ACTION` | Status update | Recommended | Lock dispute |
| `OPEN`/`UNDER_REVIEW` | `RESOLVED` | OPS/Admin | `POST /admin/disputes/:id/resolve` | Resolution selected | Resolution recorded | May trigger refund, account action, payout release/block | `DISPUTE_RESOLVED` | Resolution notification | Required if refund action | Lock dispute + related rows |
| `OPEN`/`UNDER_REVIEW` | `REJECTED` | OPS/Admin | Admin resolve endpoint | Claim invalid or insufficient evidence | Resolution reason required | Payout may unblock | `DISPUTE_RESOLVED` or `ADMIN_ACTION` | Resolution notification | Recommended | Lock dispute |
| `OPEN` | `CANCELLED` | Opener or Admin, except safety rules | Cancel endpoint/admin action | No critical safety concern requiring review | Cancellation reason | Payout may unblock | `ADMIN_ACTION` or dispute cancelled metadata | Optional | Recommended | Lock dispute |

## 11.4 Dispute resolution actions

Allowed resolution actions:

```text
NO_ACTION
WARNING
FULL_REFUND
PARTIAL_REFUND
PAYOUT_BLOCKED
PAYOUT_RELEASED
TEACHER_NO_SHOW_CONFIRMED
STUDENT_NO_SHOW_CONFIRMED
ACCOUNT_SUSPENSION_RECOMMENDED
ACCOUNT_SUSPENDED
REPORT_CORRECTION_REQUIRED
```

## 11.5 Dispute effects on related state machines

| Dispute type/action | Booking effect | Payment effect | Session effect | Payout effect |
|---|---|---|---|---|
| Open dispute after booked/completed session | Booking may become `DISPUTED` | Payment may become `DISPUTED` | Session may become `DISPUTED` | Block payout |
| Teacher no-show confirmed | Booking likely `REFUNDED` after full refund | Refund flow | Session `NO_SHOW_TEACHER` | No payout |
| Student no-show confirmed | Booking may remain completed/cancelled per policy | Usually no refund or partial per policy | Session `NO_SHOW_STUDENT` | Payout policy-dependent |
| Quality issue partial refund | Booking returns `COMPLETED` after resolution | Payment `PARTIALLY_REFUNDED` | Session may remain `COMPLETED` | Payout reduced or adjusted |
| Safety issue | Admin escalation | Refund likely/manual | Session `DISPUTED` or final factual state | Payout blocked until resolved |

## 11.6 Dispute forbidden transitions

| Forbidden transition | Reason |
|---|---|
| `RESOLVED → OPEN` | Create new dispute or admin appeal record, do not reopen silently |
| `REJECTED → RESOLVED` without admin override | Requires audited admin action |
| Safety dispute cancellation without review | Safety must be handled carefully |
| Support resolving high-risk financial/safety dispute | Requires OPS/Admin or Admin only |

## 11.7 Dispute audit requirements

Every dispute resolution must store:

```text
resolution
resolved_at
assigned_admin_user_id or resolver
admin action event
refund reference if applicable
account action reference if applicable
```

---

# 12. Payout State Machine

## 12.1 Payout states

From approved schema:

```text
PENDING
ELIGIBLE
PROCESSING
PAID
FAILED
CANCELLED
```

## 12.2 Payout eligibility

A session is payout-eligible only if:

```text
session.status = COMPLETED
session report exists
confirmed payment exists
teacher matches session teacher
no open dispute exists
no full refund exists
session not already included in payout_items
payout waiting/dispute window has passed, if configured
```

Database already enforces core eligibility through `validate_payout_item_eligibility()`.

The service layer must enforce policy windows and refund adjustments.

## 12.3 Allowed payout transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | DB invariants | Side effects | Event Ledger | Notification | Idempotency | Locking |
|---|---|---|---|---|---|---|---|---|---|---|
| No payout row | `PENDING` | PayoutService/System | Payout batch creation | Candidate completed sessions exist | Teacher exists | Payout draft created | Optional `PAYOUT_ELIGIBLE` only when eligible | None | Required for batch | Lock selected sessions |
| `PENDING` | `ELIGIBLE` | PayoutService/OPS | Eligibility job/admin process | Eligibility rules satisfied | `payout_items.session_id UNIQUE` | Payout can be processed | `PAYOUT_ELIGIBLE` | Teacher may see eligible payout | Required | Lock payout + sessions |
| `ELIGIBLE` | `PROCESSING` | OPS/Admin | `POST /admin/payouts/process` | Approved payout batch | No duplicate payout item | Provider payout call prepared after commit | `ADMIN_ACTION` or payout processing metadata | Processing notice optional | Required | Lock payout |
| `PROCESSING` | `PAID` | Provider result/OPS reconciliation | Provider success | Provider reference valid | Ledger payout transaction balanced | Teacher payout marked paid | `PAYOUT_PROCESSED` | Teacher payout processed | Provider idempotency | Lock payout |
| `PROCESSING` | `FAILED` | Provider result/OPS | Provider failed | Failure reason captured | No deletion | Retry possible; reversal if ledger was posted prematurely | `ADMIN_ACTION` metadata failure | Teacher/admin notified if needed | Provider idempotency | Lock payout |
| `PENDING`/`ELIGIBLE` | `CANCELLED` | OPS/Admin/System | Dispute/refund/account block | Reason required | Payout items handled safely | Payout not processed | `ADMIN_ACTION` | Optional | Recommended | Lock payout |
| `FAILED` | `PROCESSING` | OPS/Admin | Retry payout | Failure resolved; idempotency key new or replay-safe | Same sessions not duplicated | Retry provider call | `ADMIN_ACTION` | Optional | Required | Lock payout |

## 12.4 Payout forbidden transitions

| Forbidden transition | Reason |
|---|---|
| `PENDING → PAID` | Must pass eligibility and processing |
| `ELIGIBLE → PAID` without provider/process step | No payout execution record |
| `PAID → FAILED` | If correction needed, use adjustment/reversal, not mutation |
| `CANCELLED → PAID` | Create new payout if later eligible |
| Duplicate payout item for same session | Blocked by `payout_items.session_id UNIQUE` |
| Payout while open dispute exists | Violates payout eligibility |

## 12.5 Payout ledger behavior

Recommended safe approach:

1. At payment confirmation, ledger records teacher payable.
2. At payout success, ledger records teacher payable reduction and teacher cash/payout settlement.
3. Do not post final `TEACHER_PAYOUT` ledger as paid until provider payout succeeds.
4. If ledger is posted before provider success for operational reasons, failure requires reversal transaction, never UPDATE/DELETE.

## 12.6 Payout failure/compensation

If provider payout fails:

- Payout status becomes `FAILED`.
- No session becomes eligible for another payout unless retry uses the same payout or safe cancellation/recreation policy.
- If funds did not move, no final paid ledger should exist.
- If ledger entry was created, create reversal entry.
- Event Ledger captures failure metadata.

---

# 13. Cross-Domain Transition Map

## 13.1 Happy path

```text
1. Parent holds slot
   availability_slot: AVAILABLE → HELD
   booking: none → HELD
   events: BOOKING_CREATED, BOOKING_HELD

2. Parent initiates payment
   booking: HELD → PAYMENT_PENDING
   payment: NOT_STARTED → INITIATED/PENDING
   event: PAYMENT_INITIATED

3. Provider confirms payment via webhook
   payment: INITIATED/PENDING → CONFIRMED
   booking: PAYMENT_PENDING → BOOKED
   session: none → SCHEDULED
   ledger: parent payment + commission + teacher payable
   events: PAYMENT_CONFIRMED, BOOKING_CONFIRMED

4. Teacher starts session
   session: SCHEDULED → STARTED
   event: SESSION_STARTED

5. Teacher completes session
   session: STARTED → COMPLETED
   booking: BOOKED → COMPLETED
   event: SESSION_COMPLETED

6. Teacher submits report
   report: NOT_CREATED → CREATED
   student_progress_events created
   event: REPORT_CREATED

7. Parent reviews teacher
   review: none/eligible → VISIBLE
   event: REVIEW_CREATED

8. Payout becomes eligible and processed
   payout: PENDING → ELIGIBLE → PROCESSING → PAID
   ledger: teacher payout settlement
   events: PAYOUT_ELIGIBLE, PAYOUT_PROCESSED
```

## 13.2 Payment confirmation transaction map

Authoritative transaction:

```text
Provider webhook received
   ↓
Verify webhook signature outside DB transaction
   ↓
BEGIN
   ↓
Insert/lock payment_provider_events(provider, provider_event_id)
   ↓
Lock payment
   ↓
Lock booking
   ↓
Verify amount/currency
   ↓
Update payment CONFIRMED
   ↓
Update booking BOOKED
   ↓
Create session SCHEDULED
   ↓
Create ledger transaction + entries
   ↓
Insert event ledger PAYMENT_CONFIRMED
   ↓
Insert event ledger BOOKING_CONFIRMED with session_id metadata
   ↓
Mark provider event PROCESSED
   ↓
COMMIT
```

This avoids:

```text
Payment confirmed but booking not booked
Booking booked but session missing
Ledger missing for confirmed payment
Event missing for business state change
```

## 13.3 Report to Student Passport map

```text
session_reports
   ↓
student_progress_events
   ↓
Student Passport v0 query/aggregation
```

No AI is involved in MVP state transition or source of truth.

## 13.4 Review to Trust Profile map

```text
reviews + sessions + bookings + disputes
   ↓
Metrics Worker
   ↓
teacher_trust_metrics
   ↓
Teacher Trust Profile API
```

Teacher cannot directly mutate trust metrics.

## 13.5 Dispute blocking payout map

```text
DISPUTE_OPENED
   ↓
disputes.status = OPEN / UNDER_REVIEW
   ↓
payout eligibility blocked
   ↓
resolution determines refund/payout/account action
```

Payout can proceed only after:

```text
no open dispute exists
refund impact handled
session remains eligible
```

---

# 14. Refund Lifecycle

Refund is part of the Payment domain but requires a dedicated `refunds` table.

## 14.1 Refund states

Recommended for Schema Patch v1.1:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

## 14.2 Refund types

```text
FULL_REFUND
PARTIAL_REFUND
```

## 14.3 Refund transition matrix

| From | To | Authority | Endpoint/Service | Preconditions | Side effects | Event Ledger | Idempotency |
|---|---|---|---|---|---|---|---|
| No refund | `REQUESTED` | Parent/Teacher via dispute or OPS/Admin | `POST /disputes` or refund request | Payment confirmed; reason exists | Dispute may open | `DISPUTE_OPENED` if dispute-based | Recommended |
| `REQUESTED` | `APPROVED` | OPS/Admin | Dispute resolution/refund endpoint | Policy allows refund | Payment may become `REFUND_PENDING` | `REFUND_ISSUED` | Required |
| `APPROVED` | `PROVIDER_PENDING` | RefundService | Provider refund call | Approved amount <= refundable balance | Provider request sent | `REFUND_ISSUED` metadata | Required |
| `PROVIDER_PENDING` | `SUCCEEDED` | Provider webhook/reconciliation | Provider confirms refund | Provider refund ID valid | Payment `REFUNDED` or `PARTIALLY_REFUNDED`; ledger reversal | `PAYMENT_REFUNDED` | Provider event idempotency |
| `PROVIDER_PENDING` | `FAILED` | Provider webhook/reconciliation | Provider rejects/fails | Failure reason captured | Payment restored to previous state | `ADMIN_ACTION` metadata failure | Provider event idempotency |
| `REQUESTED` | `REJECTED` | OPS/Admin | Dispute/refund resolution | Refund not approved | Dispute may resolve rejected | `DISPUTE_RESOLVED` | Recommended |
| `REQUESTED`/`APPROVED` | `CANCELLED` | Admin/OPS | Operational cancellation | No provider refund completed | No financial movement | `ADMIN_ACTION` | Required |

## 14.4 Partial refund behavior

If cumulative successful refund amount is less than original confirmed payment amount:

```text
payment.status = PARTIALLY_REFUNDED
booking.status = COMPLETED or BOOKED depending operational state
session.status remains factual state
```

Examples:

```text
Session completed but quality issue → partial refund:
session = COMPLETED
booking = COMPLETED
payment = PARTIALLY_REFUNDED
dispute = RESOLVED
```

## 14.5 Full refund behavior

If cumulative successful refund amount equals original payment amount:

```text
payment.status = REFUNDED
booking.status = REFUNDED when full financial reversal applies
```

Session remains factual:

- If teacher no-show: `session.status = NO_SHOW_TEACHER`
- If session happened but full refund granted: `session.status` may remain `COMPLETED` or `DISPUTED` depending resolution policy, but must not be deleted.

---

# 15. Timeout and Expiry Rules

## 15.1 Booking hold expiry

```text
HELD + hold_expires_at < now()
   ↓
EXPIRED
   ↓
slot AVAILABLE
```

Handled by system job.

## 15.2 Payment checkout expiry

If provider checkout expires before confirmation:

```text
payment INITIATED/PENDING → FAILED
booking PAYMENT_PENDING → EXPIRED/CANCELLED
slot AVAILABLE
```

Late provider success must be reconciled, not blindly booked.

## 15.3 Session start grace period

Before marking no-show:

- Define teacher grace period.
- Define student grace period.
- Parent teacher-no-show report should usually create dispute or OPS review.

Exact durations remain open decisions.

## 15.4 Report due window

Report should be created soon after session completion.

Recommended policy:

```text
Teacher report due before payout eligibility
```

## 15.5 Dispute window

Payout should not become final until:

```text
report exists
no open dispute
minimum dispute window passed, if configured
```

Exact dispute window remains open decision.

---

# 16. Idempotency Requirements by State Machine

| Operation | Required? | Storage | Replay behavior |
|---|---|---|---|
| Booking hold | Yes | `api_idempotency_keys` | Return original booking/hold response |
| Payment initiation | Yes | `payments.idempotency_key` + `api_idempotency_keys` | Return existing payment checkout state |
| Payment webhook | Yes | `payment_provider_events(provider, provider_event_id)` | Return duplicate processed response |
| Refund request/approval | Yes | `refunds.idempotency_key` + `api_idempotency_keys` | Return existing refund state |
| Payout processing | Yes | `api_idempotency_keys` + payout batch reference | Return existing payout batch |
| Review creation | Recommended | `api_idempotency_keys` optional; DB unique required | Return existing review or duplicate conflict |
| Session start/complete | Recommended | `api_idempotency_keys` optional | Return current state if already applied safely |

---

# 17. Concurrency Requirements by Risk

## 17.1 Double booking

Protection:

```text
SELECT availability_slot FOR UPDATE
+ booking insert in same transaction
+ partial unique index on active booking per slot
+ slot status trigger
```

## 17.2 Duplicate payment confirmation

Protection:

```text
payment_provider_events unique(provider, provider_event_id)
+ unique provider_transaction_id where applicable
+ unique confirmed payment per booking
+ payment row lock
+ booking row lock
```

## 17.3 Duplicate session creation

Protection:

```text
sessions.booking_id UNIQUE
+ creation inside payment confirmation transaction
```

If duplicate webhook tries to create a second session, transaction should return duplicate webhook response and not insert.

## 17.4 Duplicate review

Protection:

```text
reviews.session_id UNIQUE
+ eligibility check
```

## 17.5 Duplicate payout

Protection:

```text
payout_items.session_id UNIQUE
+ payout idempotency key
+ session/payment locks during payout batch
```

## 17.6 Refund over-refund

Protection required in Schema Patch/Service:

```text
sum(successful refunds) + new approved refund <= payment.amount
```

Must be checked under payment/refund lock.

---

# 18. Admin Override Rules

Admin override is allowed only when explicitly defined.

## 18.1 Admin override requirements

Every override must include:

```text
admin_user_id
role
reason
before_state
after_state
entity_type
entity_id
request_id
created_at
event_ledger.ADMIN_ACTION
```

## 18.2 Overrides that require ADMIN, not SUPPORT

```text
Payment confirmation override
Refund approval outside policy
Full refund after completed session
Teacher verification approval/rejection
User suspension
Safety dispute resolution
Ledger reversal
Payout cancellation after processing
Raw payment payload access
Verification document access
```

## 18.3 Overrides that may be OPS under policy

```text
Manual pilot payment confirmation
Booking cancellation assistance
Operational dispute resolution
Payout batch processing
Review moderation for non-sensitive abuse
```

## 18.4 Forbidden even for normal admin UI

Admin UI should not allow direct blind mutation of:

```text
ledger_entries
ledger_transactions without reversal
payments.status without payment/refund service
bookings.status without transition service
sessions.status without transition service
teacher_trust_metrics without metrics worker/admin recalculation path
```

---

# 19. Failure and Compensation Patterns

## 19.1 General principle

Never fix financial or trust inconsistencies by deleting records.

Use:

```text
reversal ledger entries
refund records
admin action events
security events
new corrective events
```

## 19.2 Payment confirmed but internal transaction fails

If webhook transaction fails before commit:

- No internal state should show confirmed.
- Provider event may retry.
- Reconciliation must detect provider-side success if retries stop.

## 19.3 Booking booked but session creation fails

This must not persist.

Because session creation is inside same transaction:

```text
booking BOOKED and session insert either both commit or both rollback
```

## 19.4 Ledger imbalance

Ledger transaction must not commit if debit/credit totals do not balance.

If correction needed after commit:

- Create reversal transaction.
- Create new correct transaction.
- Do not update/delete ledger entries.

## 19.5 Refund provider failure

If provider refund fails:

- Refund row `FAILED`.
- Payment returns to previous financial state or remains `DISPUTED` if dispute still open.
- Ledger reversal is not posted unless money movement occurred.
- Admin/OPS notified.

## 19.6 Payout provider failure

If payout fails:

- Payout `FAILED`.
- No duplicate payout item.
- Retry via same payout or audited cancellation/recreation.
- Reversal only if ledger/funds moved.

---

# 20. Notification Events

Notifications are not source of truth. State tables and event ledger are source of truth.

| State transition | Notification |
|---|---|
| Booking confirmed | Parent + teacher booking confirmation |
| Booking cancelled | Parent + teacher cancellation |
| Payment confirmed | Parent payment success |
| Payment failed | Parent payment failure |
| Session started | Parent session started visibility |
| Session completed | Parent session completed |
| Report created | Parent report available |
| Review eligible/requested | Parent review request |
| Dispute opened | Relevant party dispute opened |
| Dispute resolved | Relevant party dispute outcome |
| Refund issued/processed | Parent refund status |
| Payout processed | Teacher payout status |

Notification failures must not roll back core business state. They should be retried separately while tracking notification status.

---

# 21. Database Invariants Summary

| Invariant | Enforced by |
|---|---|
| Parent can book only own student | Composite FK `(student_id, parent_id)` |
| One active booking per slot | Partial unique index |
| No overlapping active teacher slots | Exclusion constraint |
| Payment amount equals booking amount | Payment trigger |
| One confirmed payment per booking | Partial unique index |
| Session created only from booked/paid booking | Session trigger + service flow |
| One session per booking | `sessions.booking_id UNIQUE` |
| Report only for completed session | Report trigger |
| One review per session | `reviews.session_id UNIQUE` |
| Review requires completed paid session | Review trigger |
| Teacher self-review blocked | Review trigger |
| Payout requires completed session/report/payment/no dispute | Payout trigger + service checks |
| Event Ledger append-only | Trigger |
| Ledger entries append-only and balanced | Trigger |

Additional Schema Patch v1.1 invariants required:

| New invariant | Required table |
|---|---|
| General command idempotency | `api_idempotency_keys` |
| Provider webhook event uniqueness | `payment_provider_events(provider, provider_event_id)` |
| Refund lifecycle and partial refund tracking | `refunds` |
| Prevent over-refund | `refunds` + service/database check |

---

# 22. State Transition Authority Summary

## 22.1 Booking

| Transition | Authority |
|---|---|
| Slot available → Booking held | Parent via BookingService |
| Held → Payment pending | Parent via PaymentService |
| Payment pending → Booked | Payment webhook / approved OPS pilot |
| Booked → Completed | SessionService after session completion |
| Active → Cancelled | Parent/Teacher/OPS/Admin under policy |
| Active/Completed → Disputed | Parent/Teacher via DisputeService |
| Disputed → Refunded | OPS/Admin via RefundService |

## 22.2 Payment

| Transition | Authority |
|---|---|
| Not started → Initiated | Parent via PaymentService |
| Initiated/Pending → Confirmed | Verified provider webhook |
| Initiated/Pending → Failed | Provider/System timeout |
| Confirmed → Disputed | DisputeService |
| Confirmed/Disputed → Refund pending | OPS/Admin refund approval |
| Refund pending → Refunded/Partially refunded | Provider refund result/Reconciliation |

## 22.3 Session

| Transition | Authority |
|---|---|
| None → Scheduled | PaymentWebhookService |
| Scheduled → Started | Assigned teacher/OPS |
| Started → Completed | Assigned teacher/OPS |
| Scheduled → No-show student | Teacher/OPS, disputeable |
| Scheduled → No-show teacher | OPS/Admin after parent report/evidence |
| Active → Disputed | DisputeService |

## 22.4 Review

| Transition | Authority |
|---|---|
| Eligible → Visible review | Parent owner |
| Visible → Flagged/Hidden/Removed | OPS/Admin moderation |

## 22.5 Dispute

| Transition | Authority |
|---|---|
| None → Open | Parent/Teacher participant |
| Open → Under review | OPS/Admin |
| Under review → Resolved/Rejected | OPS/Admin, Admin for safety/high-risk |
| Open → Cancelled | Opener/Admin, safety restrictions apply |

## 22.6 Payout

| Transition | Authority |
|---|---|
| Pending → Eligible | PayoutService/OPS |
| Eligible → Processing | OPS/Admin |
| Processing → Paid | Provider success/Reconciliation |
| Processing → Failed | Provider failure/Reconciliation |
| Pending/Eligible → Cancelled | OPS/Admin/System due dispute/refund |

---

# 23. Critical Unsafe States and Prevention

| Unsafe state | Prevention |
|---|---|
| Booking `BOOKED` without payment `CONFIRMED` | Payment webhook transaction authority |
| Payment `CONFIRMED` without booking `BOOKED` | Same transaction updates both |
| Booking `BOOKED` without session `SCHEDULED` | Synchronous session creation |
| Session `COMPLETED` without booking `COMPLETED` | Session completion syncs booking |
| Review without completed paid session | Review eligibility trigger/service |
| Payout while dispute open | Payout eligibility trigger/service |
| Duplicate payment webhook mutation | `payment_provider_events` + locks |
| Duplicate payout for same session | `payout_items.session_id UNIQUE` |
| Partial refund without lifecycle | Dedicated `refunds` table |
| Trust metrics manually changed by teacher | Derived metrics protected |
| Student passport based on AI hallucination | Structured progress events only |

---

# 24. Open Decisions Before Implementation

These decisions remain open and should be closed before coding.

1. Exact booking hold duration: 10 or 15 minutes.
2. Payment checkout timeout duration.
3. Late payment confirmation handling after booking expiry.
4. Session no-show grace periods for teacher and student.
5. Parent dispute window after session completion.
6. Payout eligibility delay after report completion.
7. Exact refund statuses and fields in Schema Patch v1.1.
8. Exact `api_idempotency_keys` schema and retention policy.
9. Exact `payment_provider_events` schema and retention policy.
10. Whether review remains creatable after partial refund if no review was created before refund.
11. Whether resolved disputes restore previous booking/session/payment status or keep final factual/financial status with resolution metadata.
12. Which payment provider is first and what webhook fields are guaranteed.
13. Which provider supports refund webhooks vs manual reconciliation.
14. Which roles may perform manual pilot payment confirmation.
15. Whether PostgreSQL Row-Level Security is added in MVP or deferred.

---

# 25. Explicit Non-Goals

This document does not introduce:

- AI tutor
- AI state decisions
- Session recording
- Microservices
- Subscriptions
- Group classes
- Predictive analytics
- Advanced referral engine
- Public teacher leaderboard
- Paid ranking
- Full SCF accounting system

---

# 26. Final State Machine Decision

EduTrust MVP state machines are approved for Architecture Gate #4 review if implementation preserves these rules:

```text
No arbitrary status mutation.
No payment confirmation outside verified webhook/manual approved pilot path.
No booking BOOKED without payment CONFIRMED.
No booking BOOKED without session SCHEDULED.
No session COMPLETED without valid attendance and timing.
No report before completed session.
No review before verified completed paid session.
No payout while dispute is open.
No partial refund without refund lifecycle record.
No duplicate webhook processing.
No frontend-only concurrency protection.
No mutable ledger entries.
No mutable event ledger.
No AI as source of truth for state transitions or Student Passport.
```

The next phase after Architecture Gate #4 should be:

```text
UX Flows v1.0
```

or, if desired before UX:

```text
Schema Patch v1.1 Specification
```

for:

```text
api_idempotency_keys
payment_provider_events
refunds
```
