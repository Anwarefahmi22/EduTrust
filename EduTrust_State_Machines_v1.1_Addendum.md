# EduTrust Algeria — State Machines v1.1 Addendum

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** State Machines v1.1 Addendum  
**Type:** Authoritative patch to `EduTrust_State_Machines_v1.0.md`  
**Depends on:**
1. EduTrust MVP PRD v1.0
2. EduTrust PostgreSQL Database Schema v1.0
3. EduTrust API Architecture v1.0
4. EduTrust State Machines v1.0
5. EduTrust Schema Patch v1.1

**Gate status:** Architecture Gate #4 = PASS after v1.1 addendum alignment  
**Implementation status:** Specification only. Do not begin backend implementation yet.

---

# 1. Purpose

This addendum patches `EduTrust_State_Machines_v1.0.md` without rewriting it completely.

It makes the state-machine layer consistent with the approved `EduTrust_Schema_Patch_v1.1.md` and closes the five issues identified during Architecture Gate #4:

1. Dispute must be an overlay, not a factual Booking/Session state.
2. Refund lifecycle events must distinguish approval/submission from actual money returned.
3. Partial refunds must adjust teacher payable before payout.
4. Late payment after booking expiry must not revive the booking.
5. Refund after already-paid payout must use financial adjustment/recovery, not payout mutation.

This addendum supersedes any conflicting wording in State Machines v1.0.

---

# 2. Authority Hierarchy

If documents conflict, use this order:

```text
1. EduTrust State Machines v1.1 Addendum
2. EduTrust Schema Patch v1.1
3. EduTrust State Machines v1.0
4. EduTrust API Architecture v1.0
5. EduTrust PostgreSQL Database Schema v1.0
6. EduTrust MVP PRD v1.0
```

The addendum does not expand MVP scope and does not introduce implementation.

---

# 3. Summary of v1.1 State Machine Changes

| Area | v1.0 behavior | v1.1 authoritative behavior |
|---|---|---|
| Booking dispute | Could move to `DISPUTED` | Do not use `bookings.status = DISPUTED`; dispute lives in `disputes.status` |
| Session dispute | Could move to `DISPUTED` | Do not use `sessions.status = DISPUTED`; dispute lives in `disputes.status` |
| Refund events | `REFUND_ISSUED` ambiguous | Use precise lifecycle events: requested, approved, provider submitted, succeeded, failed |
| Payment refunded event | Could be confused with approval | Emit only after provider-confirmed refund success or reconciliation-confirmed success |
| Late payment | Mentioned as reconciliation case | Formal branch: payment confirmed, booking remains expired/cancelled, no session, refund/reconciliation |
| Partial refund before payout | “May adjust payout” | Must compute net teacher payable before payout processing |
| Refund after payout | Not fully formalized | Do not mutate old payout; use adjustment/recovery ledger transaction |
| Provider identity | Separated in principle | Authoritative: `provider_event_id` is webhook identity; `provider_transaction_id` is financial transaction identity |

---

# 4. Dispute Overlay Model

## 4.1 Authoritative rule

A dispute is a procedural overlay.

It must not overwrite factual Booking or Session state.

Use:

```text
disputes.status = OPEN / UNDER_REVIEW / RESOLVED / REJECTED / CANCELLED
```

Do not use ordinary API/service logic to set:

```text
bookings.status = DISPUTED
sessions.status = DISPUTED
```

## 4.2 Booking example

Correct:

```text
booking.status = COMPLETED
session.status = COMPLETED
payment.status = CONFIRMED
dispute.status = OPEN
payout eligibility = BLOCKED
```

After partial refund resolution:

```text
booking.status = COMPLETED
session.status = COMPLETED
payment.status = PARTIALLY_REFUNDED
dispute.status = RESOLVED
payout = adjusted/released according to net teacher payable
```

Incorrect:

```text
booking.status = DISPUTED
session.status = DISPUTED
```

## 4.3 Why this matters

A dispute does not erase facts.

Examples of factual truths:

- The booking was completed.
- The session occurred.
- A teacher no-show occurred.
- A student no-show occurred.
- A payment was confirmed.
- A refund later succeeded.

The dispute table carries the procedural review state.

---

# 5. Updated Booking State Machine

## 5.1 Booking states retained

From v1.0 schema:

```text
HELD
PAYMENT_PENDING
BOOKED
COMPLETED
CANCELLED
REFUNDED
EXPIRED
```

`DISPUTED` exists in the legacy enum but is deprecated/blocked for MVP v1.1 through Schema Patch v1.1 constraints.

## 5.2 Normal booking flow

```text
AVAILABLE SLOT
   ↓ POST /bookings/hold
booking = HELD
   ↓ POST /payments/initiate
booking = PAYMENT_PENDING
   ↓ payment webhook confirms fulfillable payment
booking = BOOKED
   ↓ session completed
booking = COMPLETED
```

## 5.3 Dispute overlay flow

```text
booking = COMPLETED
session = COMPLETED
payment = CONFIRMED
   ↓ parent/teacher opens dispute
booking remains COMPLETED
session remains COMPLETED
dispute = OPEN
payout = blocked
   ↓ dispute resolved with partial refund
booking remains COMPLETED
session remains COMPLETED
payment = PARTIALLY_REFUNDED
dispute = RESOLVED
payout = recalculated/released
```

## 5.4 When `booking.status = REFUNDED` is allowed

`booking.status = REFUNDED` should be used only when full financial reversal closes an unfulfilled booking flow, such as:

```text
teacher no-show confirmed before fulfilled session
late payment after expiry refunded
booking cancelled and fully refunded before session fulfillment
```

If a session factually occurred and was completed, then a later refund should generally not overwrite the factual booking completion.

Correct for completed but refunded session:

```text
booking.status = COMPLETED
session.status = COMPLETED
payment.status = REFUNDED or PARTIALLY_REFUNDED
refund.status = SUCCEEDED
dispute.status = RESOLVED
```

This preserves factual history and separates it from financial correction.

## 5.5 Updated forbidden booking transitions

| Forbidden transition | Reason |
|---|---|
| Any booking state → `DISPUTED` | Dispute is overlay in `disputes`, not booking factual state |
| `EXPIRED → BOOKED` after late payment | Expired booking cannot be revived by late provider success |
| `CANCELLED → BOOKED` after payment success | Must use reconciliation/refund or new booking, not revival |
| `COMPLETED → DISPUTED` | Use `disputes.status = OPEN`; booking remains completed |
| `COMPLETED → REFUNDED` when session factually occurred | Payment/refund state carries financial reversal; booking remains factual |
| Public direct status mutation | Violates state-transition authority |

---

# 6. Updated Session State Machine

## 6.1 Session states retained

```text
SCHEDULED
STARTED
COMPLETED
NO_SHOW_STUDENT
NO_SHOW_TEACHER
CANCELLED
```

`DISPUTED` exists in the legacy enum but is deprecated/blocked for MVP v1.1 through Schema Patch v1.1 constraints.

## 6.2 Normal session flow

```text
SCHEDULED
   ↓ teacher starts
STARTED
   ↓ teacher completes
COMPLETED
```

## 6.3 Dispute overlay flow

Correct:

```text
session.status = COMPLETED
dispute.status = OPEN
```

Incorrect:

```text
session.status = DISPUTED
```

## 6.4 Updated forbidden session transitions

| Forbidden transition | Reason |
|---|---|
| Any session state → `DISPUTED` | Dispute is procedural overlay, not educational/factual state |
| `COMPLETED → STARTED` | Completed is factual terminal state |
| `NO_SHOW_TEACHER → COMPLETED` | If session later occurs, create a new booking/session or admin-correct with audit if factual error |
| `NO_SHOW_STUDENT → COMPLETED` | No-show should not be converted into completed session without formal correction |
| `CANCELLED → STARTED` | Cancelled sessions cannot be started |
| Parent directly marking session completed | Parent may dispute or confirm feedback; teacher/OPS controls completion |

---

# 7. Updated Payment and Refund State Machines

## 7.1 Payment state remains separate from refund lifecycle

Payment states summarize financial state:

```text
INITIATED
PENDING
CONFIRMED
FAILED
REFUND_PENDING
REFUNDED
PARTIALLY_REFUNDED
DISPUTED, reserved for provider/financial dispute scenarios
```

Refund lifecycle lives in the new `refunds` table.

## 7.2 Refund states

Authoritative refund states:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

## 7.3 Correct refund event semantics

| Refund state transition | Event Ledger event | Meaning |
|---|---|---|
| No refund → `REQUESTED` | `REFUND_REQUESTED` | Refund request exists |
| `REQUESTED` → `APPROVED` | `REFUND_APPROVED` | Platform approved refund internally |
| `APPROVED` → `PROVIDER_PENDING` | `REFUND_PROVIDER_SUBMITTED` | Refund request sent to provider |
| `PROVIDER_PENDING` → `SUCCEEDED` | `REFUND_SUCCEEDED` | Provider/reconciliation confirms money returned |
| `PROVIDER_PENDING` → `FAILED` | `REFUND_FAILED` | Provider/reconciliation confirms refund failed |
| `REQUESTED` → `REJECTED` | `REFUND_REJECTED` | Platform rejected refund request |
| `REQUESTED`/`APPROVED` → `CANCELLED` | `REFUND_CANCELLED` | Refund workflow cancelled before success |

## 7.4 Payment refunded events

Only after refund success:

```text
refund.status = SUCCEEDED
```

may the system emit:

```text
PAYMENT_REFUNDED
```

or:

```text
PAYMENT_PARTIALLY_REFUNDED
```

## 7.5 Forbidden refund/payment semantics

| Forbidden behavior | Reason |
|---|---|
| Emitting `PAYMENT_REFUNDED` at refund approval | Approved refund is not money returned |
| Emitting `PAYMENT_PARTIALLY_REFUNDED` at provider submission | Provider submission is not success |
| Treating `REFUND_APPROVED` as financial settlement | Settlement occurs only after provider/reconciliation success |
| Updating old ledger entries for refund correction | Ledger is immutable; use reversal/adjustment |
| Hiding failed refunds by deleting refund rows | Refund lifecycle must remain auditable |

---

# 8. Provider Identity Model

## 8.1 Authoritative identity separation

```text
provider_event_id       = webhook event identity
provider_transaction_id = payment financial transaction identity
provider_refund_id      = refund transaction identity
```

These must not be mixed.

## 8.2 Webhook uniqueness

Webhook replay protection uses:

```text
UNIQUE(provider, provider_event_id)
```

This belongs in `payment_provider_events`.

## 8.3 Payment transaction uniqueness

Financial transaction identity remains:

```text
provider_transaction_id
```

This is not sufficient for webhook idempotency because one transaction can have multiple events.

## 8.4 Refund identity

Refund provider identity:

```text
provider_refund_id
```

This identifies provider-side refund operations and must be linked to EduTrust `refunds.id`.

---

# 9. Updated Payment Webhook Confirmation Branches

Payment webhook handling now has two formal branches.

## 9.1 Shared webhook preconditions

Before any business mutation:

```text
1. Verify provider signature/authenticity.
2. Parse event safely.
3. Extract provider_event_id.
4. Extract provider_transaction_id when present.
5. Insert/lock payment_provider_events(provider, provider_event_id).
6. Reject or replay duplicate events safely.
7. Lock payment row.
8. Lock booking row.
9. Verify amount and currency.
```

## 9.2 Branch A — Fulfillable payment success

Use when booking can still be fulfilled.

Preconditions:

```text
booking.status = PAYMENT_PENDING
slot still corresponds to booking
payment amount/currency valid
no expiry or cancellation preventing fulfillment
```

Transition:

```text
payment.status = CONFIRMED
booking.status = BOOKED
session.status = SCHEDULED
ledger = parent payment + platform commission + teacher payable
event_ledger = PAYMENT_CONFIRMED + BOOKING_CONFIRMED
provider_event.status = PROCESSED
COMMIT
```

Notifications:

```text
Payment confirmed
Booking confirmed
Session scheduled
```

## 9.3 Branch B — Late payment after expiry / unfulfillable payment

Use when provider reports success but booking cannot be fulfilled.

Examples:

```text
booking.status = EXPIRED
booking.status = CANCELLED
slot already released/rebooked
hold expired before payment success
```

Authoritative transition:

```text
payment.status = CONFIRMED
booking.status remains EXPIRED or CANCELLED
session is NOT created
slot is NOT reassigned
teacher payable is NOT created
refund/reconciliation workflow is created
provider_event.status = PROCESSED
COMMIT
```

Events:

```text
PAYMENT_CONFIRMED
PAYMENT_RECONCILIATION_REQUIRED
REFUND_REQUESTED or REFUND_APPROVED depending policy
```

Notifications:

```text
Payment received after booking expiry.
Booking was not confirmed.
Refund/reconciliation has started.
```

## 9.4 Forbidden late-payment behavior

| Forbidden behavior | Reason |
|---|---|
| Reviving expired booking to `BOOKED` | Can steal slot or violate marketplace integrity |
| Reassigning slot from another parent | Breaks booking trust and concurrency guarantees |
| Creating session for expired booking | Creates false fulfillment |
| Creating teacher payable | Teacher did not earn unfulfilled late payment |
| Ignoring payment | Money movement must be reconciled/refunded |

---

# 10. Partial Refund → Payout Calculation

## 10.1 Authoritative payout calculation before processing

Before payout moves from:

```text
ELIGIBLE → PROCESSING
```

PayoutService must compute:

```text
gross_teacher_payable
- reserved_or_succeeded_teacher_refund_adjustments
- other approved deductions
= net_teacher_payable
```

Where refund exposure includes refunds in statuses:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

## 10.2 Why approved/provider-pending refunds are included

If EduTrust ignores approved refunds that have not yet succeeded at provider level, it may overpay the teacher before the refund settles.

Therefore:

```text
approved refund exposure reduces payout eligibility before provider refund success
```

## 10.3 Refund allocation fields

Schema Patch v1.1 adds:

```text
teacher_adjustment_amount
platform_adjustment_amount
```

For approved/provider/succeeded refunds:

```text
teacher_adjustment_amount + platform_adjustment_amount = approved_amount
```

## 10.4 Example

```text
Session price: 2000 DZD
Platform commission: 300 DZD
Gross teacher payable: 1700 DZD
Approved partial refund: 400 DZD
Teacher adjustment: 300 DZD
Platform adjustment: 100 DZD

Net teacher payable:
1700 - 300 = 1400 DZD
```

## 10.5 Payout eligibility rule

A payout item may be created only if:

```text
session.status = COMPLETED
session report exists
confirmed payment exists
no open dispute exists
no full refund exists
net_teacher_payable > 0
session not already included in payout_items
payout waiting/dispute window passed, if configured
```

If:

```text
net_teacher_payable = 0
```

then no payout item should be created for that session.

---

# 11. Refund After Payout Already Paid

## 11.1 Authoritative rule

If payout already reached:

```text
payout.status = PAID
```

then a later refund must not modify:

```text
old payout row
old payout_items
old ledger entries
```

## 11.2 Correct behavior

Use new financial adjustment/recovery:

```text
new ledger transaction
new ledger entries
optional teacher recoverable balance
optional platform refund expense
```

Possible accounts:

```text
TEACHER_RECOVERABLE
PLATFORM_REFUND_EXPENSE
```

## 11.3 Example

```text
Teacher already paid: 1700 DZD
Later partial refund: 400 DZD
Teacher responsible share: 300 DZD
Platform responsible share: 100 DZD
```

Correct:

```text
old payout remains PAID
new adjustment ledger records 300 DZD teacher recoverable
new adjustment ledger records 100 DZD platform refund expense
```

Incorrect:

```text
update old payout amount from 1700 to 1400
update old payout_items
delete old ledger entries
```

---

# 12. Updated Cross-Domain Transition Maps

## 12.1 Happy path

```text
Parent holds slot
   ↓
booking = HELD
slot = HELD
   ↓
Parent initiates payment
   ↓
booking = PAYMENT_PENDING
payment = INITIATED/PENDING
   ↓
Provider confirms fulfillable payment
   ↓
payment = CONFIRMED
booking = BOOKED
session = SCHEDULED
ledger = payment/commission/teacher payable
   ↓
Teacher starts session
   ↓
session = STARTED
   ↓
Teacher completes session
   ↓
session = COMPLETED
booking = COMPLETED
   ↓
Teacher creates report
   ↓
session_report = CREATED
student_progress_events = CREATED
   ↓
Parent reviews
   ↓
review = VISIBLE
   ↓
Payout processing
   ↓
net_teacher_payable calculated
payout = PROCESSING → PAID
```

## 12.2 Completed session with dispute and partial refund before payout

```text
booking = COMPLETED
session = COMPLETED
payment = CONFIRMED
report = CREATED
   ↓
Parent opens dispute
   ↓
dispute = OPEN
booking remains COMPLETED
session remains COMPLETED
payout blocked
   ↓
OPS/Admin approves partial refund
   ↓
refund = APPROVED
teacher_adjustment_amount set
platform_adjustment_amount set
payment = REFUND_PENDING when submitted
   ↓
Provider confirms refund success
   ↓
refund = SUCCEEDED
payment = PARTIALLY_REFUNDED
dispute = RESOLVED
   ↓
Payout recalculates net teacher payable
   ↓
payout based on adjusted amount
```

## 12.3 Late payment after expiry

```text
booking = HELD
hold expires
booking = EXPIRED
slot = AVAILABLE
possibly another booking uses slot
   ↓
Old provider success webhook arrives
   ↓
payment = CONFIRMED
booking remains EXPIRED
session NOT created
teacher payable NOT created
refund/reconciliation created
   ↓
refund submitted and succeeds
   ↓
payment = REFUNDED
refund = SUCCEEDED
booking remains EXPIRED
```

## 12.4 Refund after payout paid

```text
session = COMPLETED
report = CREATED
payment = CONFIRMED
payout = PAID
   ↓
Later dispute/refund approved
   ↓
refund = APPROVED → PROVIDER_PENDING → SUCCEEDED
payment = PARTIALLY_REFUNDED or REFUNDED
   ↓
old payout remains PAID
new adjustment/recovery ledger transaction created
```

---

# 13. Updated Event Ledger Rules

## 13.1 Refund lifecycle events

Use:

```text
REFUND_REQUESTED
REFUND_APPROVED
REFUND_PROVIDER_SUBMITTED
REFUND_SUCCEEDED
REFUND_FAILED
REFUND_REJECTED
REFUND_CANCELLED
PAYMENT_REFUNDED
PAYMENT_PARTIALLY_REFUNDED
PAYMENT_RECONCILIATION_REQUIRED
```

## 13.2 Deprecated semantic use

Do not use `REFUND_ISSUED` in new service logic to mean:

- requested,
- approved,
- provider submitted,
- or succeeded.

If old compatibility references exist, treat them as deprecated.

## 13.3 Required event timing

| Business fact | Correct event timing |
|---|---|
| Refund requested | immediately when refund row is created as `REQUESTED` |
| Refund approved | when platform approves internally |
| Refund sent to provider | after provider submission is recorded |
| Money returned | only after provider/reconciliation confirms success |
| Partial payment refund | after successful partial refund only |
| Full payment refund | after successful full refund only |
| Late payment unfulfillable | when payment success cannot create fulfillment |

---

# 14. Updated Forbidden Transition Catalogue

## 14.1 Booking forbidden transitions

```text
Any → DISPUTED
EXPIRED → BOOKED because of late payment
CANCELLED → BOOKED because of late payment
COMPLETED → DISPUTED
COMPLETED → REFUNDED when session factually occurred
```

## 14.2 Session forbidden transitions

```text
Any → DISPUTED
COMPLETED → STARTED
NO_SHOW_TEACHER → COMPLETED without audited correction/new session
NO_SHOW_STUDENT → COMPLETED without audited correction/new session
CANCELLED → STARTED
```

## 14.3 Payment/refund forbidden transitions

```text
REFUND_APPROVED → PAYMENT_REFUNDED
REFUND_PROVIDER_SUBMITTED → PAYMENT_REFUNDED
REFUND_APPROVED → PAYMENT_PARTIALLY_REFUNDED
REFUND_PROVIDER_SUBMITTED → PAYMENT_PARTIALLY_REFUNDED
CONFIRMED → FAILED
REFUNDED → CONFIRMED
```

## 14.4 Payout forbidden transitions

```text
ELIGIBLE → PROCESSING without recalculating net_teacher_payable
Payout while open dispute exists
Payout while approved/provider-pending refund exposure is ignored
PAID → amount changed
PAID → payout_items changed
PAID → deleted
```

## 14.5 Provider identity forbidden behavior

```text
Using provider_transaction_id as webhook event idempotency identity
Ignoring provider_event_id
Treating provider_event_id and provider_transaction_id as interchangeable
Processing duplicate provider_event_id twice
```

---

# 15. Updated Concurrency and Locking Requirements

## 15.1 Payment webhook with provider event table

Webhook processing must lock or insert:

```text
payment_provider_events(provider, provider_event_id)
```

before mutating payment/booking/session/refund states.

## 15.2 Late payment branch locking

For late/unfulfillable payment:

```text
BEGIN
  lock provider event
  lock payment
  lock booking
  inspect booking status and slot status
  confirm payment truth
  do not create session
  create refund/reconciliation record
  create appropriate ledger/event rows
COMMIT
```

## 15.3 Payout calculation locking

Before creating payout items:

```text
lock session
lock payment
lock relevant refunds for payment/booking
lock open disputes query target or enforce with serializable/retry-safe transaction pattern
```

Then calculate:

```text
net_teacher_payable
```

and create payout item only if positive and still eligible.

## 15.4 Refund over-refund prevention

Before approving/provider-submitting refund:

```text
lock payment
lock existing refunds for payment
ensure sum(APPROVED, PROVIDER_PENDING, SUCCEEDED) + new approved_amount <= payment.amount
```

---

# 16. Updated Admin Override Rules

Admin override remains allowed only through explicit audited workflows.

Even ADMIN must not blindly set:

```text
bookings.status = DISPUTED
sessions.status = DISPUTED
ledger_entries = edited/deleted
payout.amount = changed after PAID
payment.status = REFUNDED before refund success
```

Admin corrections must use:

- Dispute resolution
- Refund lifecycle
- Ledger reversal/adjustment
- Admin action event
- Security event when sensitive

---

# 17. Operational Parameters Still Open

The following are not structural architecture blockers but must be decided before coding or production launch:

1. Booking hold duration: 10 or 15 minutes.
2. Payment checkout timeout.
3. Late-payment policy: auto-refund vs OPS reconciliation queue.
4. No-show grace periods.
5. Parent dispute window.
6. Payout delay after report completion.
7. Refund allocation policy between teacher and platform.
8. Review eligibility after partial refund.
9. Provider-specific webhook guarantees.
10. Refund webhook availability vs manual reconciliation.
11. Idempotency retention period.
12. Provider event retention period.
13. Whether PostgreSQL RLS is implemented in MVP or deferred.

These parameters may affect product policy and UX, but they do not reopen the architecture baseline.

---

# 18. Updated Authoritative Baseline

After this addendum, the architecture baseline is:

```text
EduTrust MVP PRD v1.0
   +
EduTrust PostgreSQL Database Schema v1.0
   +
EduTrust API Architecture v1.0
   +
EduTrust State Machines v1.0
   +
EduTrust Schema Patch v1.1
   +
EduTrust State Machines v1.1 Addendum
```

Together they define:

```text
AUTHORITATIVE ARCHITECTURE BASELINE
```

for UX Flows v1.0 and later implementation.

---

# 19. Final Gate #4 Decision

Architecture Gate #4 is considered passed if the team accepts this addendum and the Schema Patch v1.1 specification.

Key final rules:

```text
Dispute is overlay.
Booking/Session factual state is not overwritten by dispute.
Refund approval is not money returned.
Payment refunded events occur only after refund success.
Late payment after expiry does not revive booking.
Partial refunds reduce net teacher payable before payout.
Paid payouts are immutable after later refunds.
Post-payout refund uses adjustment/recovery ledger transaction.
Provider event identity is separate from payment transaction identity.
Webhook duplicate processing is prevented by provider_event_id.
API idempotency uses durable api_idempotency_keys.
```

Recommended next step after review:

```text
UX Flows v1.0
```

DDL audit of:

```text
edutrust_schema_patch_v1_1.sql
```

may be done before implementation, but UX can proceed using the approved architecture baseline if this addendum is accepted.
