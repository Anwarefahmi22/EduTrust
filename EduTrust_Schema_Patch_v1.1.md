# EduTrust Algeria — Schema Patch v1.1

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** Schema Patch v1.1  
**Depends on:**
1. EduTrust MVP PRD v1.0
2. EduTrust PostgreSQL Database Schema v1.0
3. EduTrust API Architecture v1.0
4. EduTrust State Machines v1.0

**Gate status:** Architecture Gate #4 = Conditional Pass  
**Patch file:** `edutrust_schema_patch_v1_1.sql`  
**Implementation status:** Specification + DDL patch only. No backend implementation yet.

---

# 1. Executive Summary

Schema Patch v1.1 closes the five decisions raised during Architecture Gate #4 before moving to UX or backend implementation.

The patch does **not** redesign the database and does **not** expand the MVP. It adds the minimum schema support required for safe implementation of the approved API/state-machine behavior.

The patch introduces:

1. `api_idempotency_keys`
2. `payment_provider_events`
3. `refunds`
4. Dispute-as-overlay guards for `bookings` and `sessions`
5. Refund/payout adjustment allocation support
6. New event semantics for refund lifecycle

---

# 2. Authoritative Decisions Closed by v1.1

## Decision 1 — Dispute is an overlay, not a factual Booking/Session state

A dispute is an operational/legal/support process around a booking/session/payment. It is not the factual state of the educational event.

Therefore:

```text
booking.status remains factual/operational
session.status remains factual/educational
dispute.status carries the dispute lifecycle
```

Example:

```text
booking.status = COMPLETED
session.status = COMPLETED
payment.status = CONFIRMED
dispute.status = OPEN
payout = blocked
```

After partial refund resolution:

```text
booking.status = COMPLETED
session.status = COMPLETED
payment.status = PARTIALLY_REFUNDED
dispute.status = RESOLVED
payout = adjusted/released
```

### Schema patch

The v1.0 enums still contain `DISPUTED`, but v1.1 forbids using it for Booking and Session factual states:

```sql
ALTER TABLE bookings
ADD CONSTRAINT chk_bookings_dispute_overlay_no_status
CHECK (status <> 'DISPUTED'::booking_status);

ALTER TABLE sessions
ADD CONSTRAINT chk_sessions_dispute_overlay_no_status
CHECK (status <> 'DISPUTED'::session_status);
```

### Important note

`payments.status = DISPUTED` may remain reserved for actual provider/financial dispute scenarios, not ordinary EduTrust service disputes.

---

## Decision 2 — Refund event semantics must be precise

The previous event name `REFUND_ISSUED` is ambiguous and must not be used for refund approval or provider submission in the new workflow.

The patch defines clear refund lifecycle events:

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
```

### Financial rule

```text
Approved refund ≠ money refunded
Provider-submitted refund ≠ money refunded
Only provider-confirmed success means money refunded
```

Therefore:

```text
PAYMENT_REFUNDED
```

or:

```text
PAYMENT_PARTIALLY_REFUNDED
```

must occur only after refund success is confirmed by provider webhook or reconciliation.

---

## Decision 3 — Partial refund affects teacher payable before payout

Before a payout moves from:

```text
ELIGIBLE → PROCESSING
```

EduTrust must calculate:

```text
gross_teacher_payable
- teacher_refund_adjustments
- other approved deductions
= net_teacher_payable
```

A payout must not rely only on `payment.status`. It must account for current refund exposure and approved/succeeded refund adjustments.

### Patch support

The `refunds` table includes allocation fields:

```text
teacher_adjustment_amount
platform_adjustment_amount
```

For approved/provider-pending/succeeded refunds:

```text
teacher_adjustment_amount + platform_adjustment_amount = approved_amount
```

This makes the economic effect explicit.

Example:

```text
Payment amount: 2000 DZD
Teacher gross payable: 1700 DZD
Platform commission: 300 DZD
Partial refund: 400 DZD
Teacher adjustment: 300 DZD
Platform adjustment: 100 DZD
Net teacher payable before payout: 1400 DZD
```

---

## Decision 4 — Late payment after booking expiry does not revive booking

Scenario:

```text
10:00 Booking HELD
10:10 Booking EXPIRED
10:11 Another parent books the slot
10:12 Old payment webhook arrives as successful
```

The late payment is financially real, but it must not create fulfillment.

Authoritative rule:

```text
Expired booking + late provider success
=
Payment CONFIRMED
Booking remains EXPIRED
Session NOT created
Slot NOT reassigned
Refund/reconciliation workflow created
```

This preserves the distinction between:

```text
payment truth
```

and:

```text
booking fulfillment truth
```

### Patch support

`payment_provider_events` records the webhook identity and processing result.

`refunds` supports the automatic refund/reconciliation flow:

```text
reason_code = LATE_PAYMENT_AFTER_EXPIRY
status = REQUESTED or APPROVED according to operational policy
```

Recommended MVP behavior:

```text
Create refund row as APPROVED after late successful payment on expired booking.
Submit refund to provider after commit.
Do not create session.
Do not set booking to BOOKED.
```

---

## Decision 5 — Refund after payout does not mutate old payout

If a teacher has already been paid and a refund is later granted:

```text
old payout remains PAID
old payout_items remain unchanged
old ledger entries remain immutable
```

Correction must happen through:

```text
new financial adjustment / recovery ledger transaction
```

not by modifying old payout records.

### Patch support

The patch adds internal ledger account types:

```text
TEACHER_RECOVERABLE
PLATFORM_REFUND_EXPENSE
```

This preserves the rule:

```text
No UPDATE/DELETE of financial history.
Use reversal or adjustment transactions.
```

---

# 3. New Table: `api_idempotency_keys`

## 3.1 Why this table is required

`event_ledger` is not a response replay store.

EduTrust needs durable idempotency for retryable commands such as:

```text
POST /bookings/hold
POST /payments/initiate
POST /payments/:id/refund
POST /admin/payouts/process
POST /sessions/:id/review, recommended
```

Redis/cache alone is not sufficient for financial or booking idempotency.

## 3.2 Table purpose

`api_idempotency_keys` stores:

- Operation scope
- Actor identity
- Idempotency key
- Request hash
- Processing status
- Final response snapshot
- Resource created/affected
- Expiry time

## 3.3 Main fields

```text
id
scope
idempotency_key
actor_user_id
actor_key
request_method
request_path
request_hash
status
response_status
response_body
resource_type
resource_id
locked_until
expires_at
created_at
updated_at
```

## 3.4 Uniqueness

```text
UNIQUE(scope, actor_key, idempotency_key)
```

Examples:

```text
scope = booking_hold
actor_key = user:<uuid>
idempotency_key = booking-hold-<uuid>
```

## 3.5 Replay behavior

| Case | Behavior |
|---|---|
| Same key, same request hash, completed | Return stored response |
| Same key, same request hash, still processing | Return 409/202 depending endpoint policy |
| Same key, different request hash | Return `409 IDEMPOTENCY_KEY_CONFLICT` |
| Expired key | May be purged after retention period |

## 3.6 Security note

Do not store sensitive access tokens, refresh tokens, raw payment payloads, or verification document data in `response_body`.

---

# 4. New Table: `payment_provider_events`

## 4.1 Why this table is required

A payment provider webhook event has a different identity from a payment transaction.

```text
provider_event_id ≠ provider_transaction_id
```

Examples:

- Same financial transaction may generate multiple events.
- Same webhook event may be resent multiple times.
- Refund event may reference both transaction and refund IDs.

Therefore, webhook idempotency requires durable provider event storage.

## 4.2 Unique identity

```text
UNIQUE(provider, provider_event_id)
```

This is the primary replay-protection identity for webhooks.

## 4.3 Main fields

```text
id
provider
provider_event_id
provider_transaction_id
provider_refund_id
event_type
status
payment_id
refund_id
amount
currency
occurred_at
received_at
processed_at
processing_attempts
payload_hash
normalized_payload
raw_payload_storage_key
payload_redacted
last_error_code
last_error_message
created_at
updated_at
```

## 4.4 Provider event statuses

```text
RECEIVED
PROCESSING
PROCESSED
IGNORED
FAILED
REJECTED
```

## 4.5 Webhook handling rule

On webhook receipt:

```text
Verify signature outside DB transaction
BEGIN
  insert/lock payment_provider_events(provider, provider_event_id)
  if already PROCESSED → return duplicate success response
  lock payment/refund/booking as needed
  validate amount/currency/state
  perform state transition
  create ledger entries
  create event_ledger rows
  mark provider event PROCESSED
COMMIT
```

## 4.6 Raw payload policy

The table is designed for normalized payload storage.

Do not blindly store full provider payload.

If full payload must be retained:

- Store it encrypted outside the table.
- Keep only `raw_payload_storage_key` in PostgreSQL.
- Redact PII.
- Restrict access to ADMIN/OPS with audit.

---

# 5. New Table: `refunds`

## 5.1 Why this table is required

The MVP supports refund lifecycle and partial refunds. Payment status alone is insufficient.

EduTrust must track:

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

Without a dedicated refund table, refund history would be scattered across:

- payment status
- ledger entries
- disputes
- event ledger
- provider payloads

That is unsafe for reconciliation and auditability.

## 5.2 Refund statuses

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

## 5.3 Refund types

```text
FULL
PARTIAL
```

## 5.4 Key fields

```text
payment_id
booking_id
dispute_id
provider
refund_type
status
requested_amount
approved_amount
currency
teacher_adjustment_amount
platform_adjustment_amount
reason
reason_code
provider_refund_id
idempotency_key
requested_by_user_id
requested_by_role
approved_by_user_id
approved_by_role
approved_at
provider_submitted_at
completed_at
failed_at
rejected_at
cancelled_at
failure_code
failure_message
normalized_provider_payload
metadata
```

## 5.5 Refund integrity constraints

The patch adds a trigger to enforce:

- Payment must exist.
- Refund booking must match payment booking.
- Refund provider must match payment provider.
- Refund currency must match payment currency.
- Refund requires a refundable payment state.
- Approved amount cannot exceed payment amount.
- Total reserved/succeeded refunds cannot exceed payment amount.
- Full refund approved amount must equal payment amount.
- Partial refund approved amount must be less than payment amount.
- Approved/provider/succeeded refund must allocate its burden:

```text
teacher_adjustment_amount + platform_adjustment_amount = approved_amount
```

## 5.6 Over-refund prevention

The trigger reserves refund exposure for statuses:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

This prevents approving multiple partial refunds whose total exceeds the original payment.

---

# 6. Dispute Overlay Model

## 6.1 Deprecated behavior

Do not use:

```text
bookings.status = DISPUTED
sessions.status = DISPUTED
```

for ordinary EduTrust disputes.

## 6.2 Approved behavior

Use:

```text
disputes.status = OPEN / UNDER_REVIEW / RESOLVED / REJECTED / CANCELLED
```

while leaving factual state unchanged.

Example:

```text
booking.status = COMPLETED
session.status = COMPLETED
dispute.status = OPEN
```

## 6.3 Why this matters

A dispute does not erase the fact that:

- a booking was completed,
- a session was completed,
- a no-show happened,
- a payment was confirmed,
- a refund later occurred.

Dispute is procedural overlay, not factual truth.

---

# 7. Refund Event Semantics v1.1

## 7.1 Correct event sequence

### Refund requested

```text
refund.status = REQUESTED
event_ledger = REFUND_REQUESTED
```

### Refund approved

```text
refund.status = APPROVED
event_ledger = REFUND_APPROVED
```

### Refund submitted to provider

```text
refund.status = PROVIDER_PENDING
event_ledger = REFUND_PROVIDER_SUBMITTED
```

### Refund succeeds

```text
refund.status = SUCCEEDED
payment.status = REFUNDED or PARTIALLY_REFUNDED
event_ledger = REFUND_SUCCEEDED
```

Then also:

```text
PAYMENT_REFUNDED
```

or:

```text
PAYMENT_PARTIALLY_REFUNDED
```

### Refund fails

```text
refund.status = FAILED
event_ledger = REFUND_FAILED
```

## 7.2 Deprecated semantic usage

Do not use `REFUND_ISSUED` to mean:

- refund requested,
- refund approved,
- refund submitted to provider.

If retained for compatibility, it should be treated as deprecated in new code.

---

# 8. Late Payment After Expiry — Formal Rule

## 8.1 Unsafe case

```text
Booking HELD
Booking EXPIRED
Slot released
Another parent books slot
Old payment provider sends success webhook
```

## 8.2 Formal transition

When provider confirms payment for an expired/unfulfillable booking:

```text
payment.status = CONFIRMED
booking.status remains EXPIRED or CANCELLED
session is NOT created
slot is NOT reassigned
refund/reconciliation workflow is created
```

## 8.3 Ledger behavior

Do not create teacher payable or platform revenue as if the session were booked.

Instead, payment ledger should reflect:

```text
funds received
refund liability / refund pending
```

The exact ledger entry pattern should be implemented by LedgerService, but it must not create teacher payout eligibility.

## 8.4 Event Ledger

Recommended events:

```text
PAYMENT_CONFIRMED
PAYMENT_RECONCILIATION_REQUIRED
REFUND_APPROVED or REFUND_REQUESTED depending policy
```

## 8.5 Notification

Parent should receive clear message:

```text
Payment was received after the booking expired. The booking was not confirmed. A refund/reconciliation process has been started.
```

---

# 9. Partial Refund → Payout Rule

## 9.1 Before payout processing

Before a payout moves to `PROCESSING`, PayoutService must compute:

```text
gross_teacher_payable
- sum(teacher_adjustment_amount for approved/provider_pending/succeeded refunds)
- other approved deductions
= net_teacher_payable
```

Only `net_teacher_payable` may be included in payout.

## 9.2 Refund statuses included in payout calculation

Include refund exposure for:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

Do not ignore approved refunds just because provider has not completed them yet.

Otherwise EduTrust may overpay the teacher.

## 9.3 After payout already paid

If payout is already `PAID`, do not mutate old payout.

Instead:

```text
create adjustment/recovery ledger transaction
use TEACHER_RECOVERABLE if teacher owes future recovery
use PLATFORM_REFUND_EXPENSE if platform absorbs refund
```

Old payout remains immutable.

---

# 10. Provider Event Identity Rule

## 10.1 Do not mix identities

```text
provider_event_id = webhook event identity
provider_transaction_id = financial transaction identity
provider_refund_id = refund transaction identity
```

## 10.2 Unique webhook processing key

```text
UNIQUE(provider, provider_event_id)
```

## 10.3 Duplicate event behavior

If same provider event arrives again:

- If already `PROCESSED`, return duplicate success response.
- If `PROCESSING`, return retry-later/processing response.
- If `FAILED`, allow controlled retry or reconciliation depending error class.
- If conflicting payload for same event ID, mark as `REJECTED` and alert OPS/Admin.

---

# 11. Updated Payment Confirmation Logic with Expiry Branch

## 11.1 Normal branch

If booking is still fulfillable:

```text
payment CONFIRMED
booking BOOKED
session SCHEDULED
ledger: payment/commission/teacher payable
events: PAYMENT_CONFIRMED, BOOKING_CONFIRMED
```

## 11.2 Expired/unfulfillable branch

If booking is expired/cancelled and cannot be fulfilled:

```text
payment CONFIRMED
booking remains EXPIRED/CANCELLED
session NOT created
ledger: refund liability, not teacher payable
refund workflow created
events: PAYMENT_CONFIRMED, PAYMENT_RECONCILIATION_REQUIRED, REFUND_REQUESTED/APPROVED
```

## 11.3 Forbidden behavior

Do not:

- Re-book expired slot.
- Steal slot from another parent.
- Create session for expired booking.
- Create teacher payable for unfulfilled late payment.
- Ignore the payment as if it did not happen.

---

# 12. Updated Payout Eligibility with Refund Exposure

A session is payout-eligible only if:

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

Where:

```text
net_teacher_payable = gross_teacher_payable - reserved/succeeded teacher refund adjustments - other approved deductions
```

If net teacher payable is zero:

```text
No payout item should be created.
```

If net teacher payable is negative due to post-payout refund:

```text
Create recovery/adjustment ledger transaction.
Do not mutate old payout.
```

---

# 13. DDL Summary

The SQL patch file creates or changes:

## 13.1 New tables

```text
api_idempotency_keys
payment_provider_events
refunds
```

## 13.2 New enums

```text
api_idempotency_status
provider_event_processing_status
refund_status
refund_type
```

## 13.3 New event enum values

```text
REFUND_REQUESTED
REFUND_APPROVED
REFUND_PROVIDER_SUBMITTED
REFUND_SUCCEEDED
REFUND_FAILED
REFUND_REJECTED
REFUND_CANCELLED
PAYMENT_PARTIALLY_REFUNDED
PAYMENT_RECONCILIATION_REQUIRED
```

## 13.4 New ledger account enum values

```text
TEACHER_RECOVERABLE
PLATFORM_REFUND_EXPENSE
```

## 13.5 New constraints

```text
bookings.status cannot be DISPUTED
sessions.status cannot be DISPUTED
```

## 13.6 New triggers

```text
validate_refund_integrity()
validate_provider_event_status_fields()
touch_updated_at triggers for new tables
```

---

# 14. Implementation Requirements for Services

## 14.1 BookingService

Must not set:

```text
bookings.status = DISPUTED
```

Use `disputes` table instead.

## 14.2 SessionService

Must not set:

```text
sessions.status = DISPUTED
```

Use `disputes` table instead.

## 14.3 PaymentWebhookService

Must use:

```text
payment_provider_events(provider, provider_event_id)
```

as webhook identity.

Must distinguish:

```text
provider_event_id
provider_transaction_id
provider_refund_id
```

Must branch between:

```text
normal fulfillable payment confirmation
```

and:

```text
late payment after expiry / unfulfillable payment
```

## 14.4 RefundService

Must use the `refunds` table for all refund lifecycle operations.

Must not emit `PAYMENT_REFUNDED` or `PAYMENT_PARTIALLY_REFUNDED` before provider-confirmed success.

## 14.5 PayoutService

Must calculate net teacher payable using refund adjustments before processing payout.

Must not mutate old payout after a later refund.

Use ledger adjustment/recovery.

---

# 15. Updated Critical Unsafe States and Prevention

| Unsafe state | v1.1 prevention |
|---|---|
| Booking/session factual state overwritten by dispute | Dispute overlay constraints |
| Refund approved but treated as money returned | Separate refund lifecycle events |
| Payment refunded event before provider success | `REFUND_SUCCEEDED` required first |
| Partial refund ignored before payout | Refund allocation fields + payout rule |
| Teacher overpaid after approved refund | Net teacher payable calculation |
| Old paid payout mutated after late refund | Adjustment/recovery ledger transaction |
| Late payment revives expired booking | Formal expiry branch in webhook flow |
| Duplicate webhook event processed twice | `payment_provider_events` unique identity |
| Multiple refunds exceed payment amount | Refund integrity trigger |
| Response replay stored in event ledger | Dedicated `api_idempotency_keys` |

---

# 16. Open Decisions Remaining After Patch

The patch closes Gate #4 structural issues. These operational parameters still require product/legal/ops decisions before coding:

1. Booking hold duration: 10 or 15 minutes.
2. Payment checkout timeout duration.
3. Exact automatic policy for late payment after expiry: auto-approve refund or send to OPS queue first.
4. No-show grace periods for teacher and student.
5. Parent dispute window after session completion.
6. Payout eligibility delay after report completion.
7. Exact refund allocation policy between teacher and platform.
8. Whether partial refund before review keeps review eligibility.
9. Payment provider-specific webhook fields and signature verification method.
10. Refund provider webhook availability vs manual reconciliation.
11. Retention policy for `api_idempotency_keys` and `payment_provider_events`.
12. Whether PostgreSQL RLS is added in MVP or service-layer authorization remains the first implementation layer.

---

# 17. Migration / Deployment Notes

## 17.1 Apply order

Apply after:

```text
edutrust_schema_v1.sql
```

Then apply:

```text
edutrust_schema_patch_v1_1.sql
```

## 17.2 Existing data note

If any existing rows already have:

```text
bookings.status = DISPUTED
sessions.status = DISPUTED
```

then the new check constraints will fail.

For MVP before production data, this should not be an issue.

If data exists, migrate disputes into the `disputes` table first and restore factual booking/session states before applying constraints.

## 17.3 Enum note

The patch adds enum values but does not remove old enum values, because removing PostgreSQL enum values is intrusive and unnecessary for MVP.

Deprecated enum values are blocked by constraints/service rules where needed.

---

# 18. Final Schema Patch Decision

Schema Patch v1.1 is ready for Architecture Gate review if it preserves these rules:

```text
Dispute is overlay, not Booking/Session factual state.
Refund lifecycle has precise semantics.
PAYMENT_REFUNDED/PARTIALLY_REFUNDED only after refund success.
Partial refunds adjust teacher payable before payout.
Late payment after expiry does not revive booking.
Paid payouts are never mutated after later refunds.
Provider event identity is durable and separate from provider transaction identity.
API idempotency is durable and not stored in Event Ledger.
```

After this patch is reviewed, the recommended next step is either:

```text
State Machines v1.1 Addendum
```

or:

```text
UX Flows v1.0
```

The safer sequence is:

```text
Schema Patch v1.1 review
   ↓
State Machines v1.1 Addendum, if required
   ↓
UX Flows v1.0
   ↓
Implementation
```
