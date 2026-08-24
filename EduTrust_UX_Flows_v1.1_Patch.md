# EduTrust Algeria — UX Flows v1.1 Patch

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Patch to `EduTrust_UX_Flows_v1.0.md`  
**Source audit:** `EduTrust_UX_Audit_v1.0.md`  
**Status:** UX patch only — no frontend/backend implementation  
**Architecture baseline:** LOCKED

---

# 1. Purpose

This document patches `EduTrust_UX_Flows_v1.0.md` by closing the 10 findings identified in `EduTrust_UX_Audit_v1.0.md`.

This patch does **not**:

- rewrite UX Flows v1.0,
- redesign architecture,
- modify database schema,
- modify state machines,
- start frontend implementation,
- start backend implementation,
- introduce new MVP features.

The locked architecture baseline remains authoritative.

---

# 2. Patch Authority

If this patch conflicts with `EduTrust_UX_Flows_v1.0.md`, this patch wins for the specific UX topics it covers.

It does not override:

- PRD v1.0,
- Database Schema v1.0,
- API Architecture v1.0,
- State Machines v1.0,
- Schema Patch v1.1,
- State Machines v1.1 Addendum,
- Schema Patch v1.2,
- DDL Hardening v1.3,
- `edutrust_schema_patch_v1_3.sql`.

UX remains a reflection of business logic, not a source of business logic.

---

# 3. Findings Closed

| Finding | Status in this patch |
|---|---|
| UX-AUD-001 — Refund read/status API expectations | Closed |
| UX-AUD-002 — Admin/OPS refund reconciliation UX | Closed |
| UX-AUD-003 — Student Data Sharing Permission Flow | Closed |
| UX-AUD-004 — Admin Payout Processing Flow | Closed |
| UX-AUD-005 — Partial Refund/Payout UX exposure | Closed |
| UX-AUD-011 — Post-payout recovery/adjustment UX | Closed |
| UX-AUD-007 — Teacher Subjects & Pricing Flow | Closed |
| UX-AUD-006 — Reschedule ambiguity | Closed: hidden from MVP |
| UX-AUD-008 — Refund rejected/cancelled treatment | Closed |
| UX-AUD-010 — Sensitive admin access must audit | Closed |

---

# 4. Patch 1 — Refund Read/Status API Expectations

## Audit finding closed

`UX-AUD-001 — Refund status/timeline UX lacks explicit read API contract`

## Exact UX correction

Refund timeline must be visible wherever refund state affects the user:

- Parent payment detail
- Parent booking detail
- Parent dispute detail
- Admin refund handling
- Admin dispute handling
- Teacher earnings/payout detail when refund affects teacher payable

The UX must clearly distinguish all refund states:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

## Required refund timeline component

Display as a timeline:

```text
Refund requested
   ↓
Refund approved
   ↓
Refund submitted to payment provider
   ↓
Refund completed / failed / rejected / cancelled
```

User-facing labels:

| Refund state | Parent-facing label | Admin-facing label |
|---|---|---|
| `REQUESTED` | Refund requested | Requested |
| `APPROVED` | Refund approved | Approved internally |
| `PROVIDER_PENDING` | Refund processing | Submitted to provider |
| `SUCCEEDED` | Refund completed | Provider/reconciliation success |
| `FAILED` | Refund failed | Provider/reconciliation failed |
| `REJECTED` | Refund rejected | Rejected by platform |
| `CANCELLED` | Refund cancelled | Cancelled before completion |

Important UX rule:

```text
Do not display “Refunded” unless refund.status = SUCCEEDED.
```

## API contract dependency

No new product feature is introduced. The approved refund lifecycle must be exposed by API responses.

Minimum implementation expectation:

### Parent-scoped responses

`GET /payments/:id` should include refund summary/timeline when refunds exist:

```json
{
  "data": {
    "payment_id": "pay_123",
    "status": "PARTIALLY_REFUNDED",
    "amount": "2000.00",
    "currency": "DZD",
    "refunds": [
      {
        "refund_id": "refund_123",
        "status": "SUCCEEDED",
        "refund_type": "PARTIAL",
        "requested_amount": "400.00",
        "approved_amount": "400.00",
        "currency": "DZD",
        "reason": "Partial refund approved after dispute resolution.",
        "created_at": "2026-09-05T15:00:00Z",
        "approved_at": "2026-09-05T15:10:00Z",
        "provider_submitted_at": "2026-09-05T15:12:00Z",
        "completed_at": "2026-09-05T15:20:00Z"
      }
    ]
  }
}
```

`GET /bookings/:id` should include an `active_refund` or `refunds[]` summary if the booking has refund activity.

`GET /disputes/:id` should include linked refund summaries when dispute resolution involved refund.

### Admin-scoped responses

Admin refund monitoring may be implemented through existing admin payment/dispute views with refund filters, or through explicit admin refund read endpoints if the backend team adds them as an API contract clarification:

```text
GET /admin/payments?refund_status=PROVIDER_PENDING
GET /admin/disputes?resolution_action=REFUND
GET /admin/refunds
GET /admin/refunds/:id
```

If explicit `/admin/refunds` endpoints are added, they are an implementation-level exposure of the already-approved `refunds` table, not a new product feature.

## Backend authority

Refund read access is controlled by:

- Parent: own payments/bookings/disputes only.
- Teacher: only refund impact relevant to own earnings/payouts, not parent payment details beyond necessary adjustment context.
- OPS/Admin: operational refund monitoring with audited sensitive access.

## User-facing state

Parent sees:

```text
Refund requested / approved / processing / completed / failed / rejected / cancelled
```

Teacher sees only economic impact when relevant:

```text
Refund adjustment pending
Refund adjustment applied
Recovery balance created
```

## Idempotency requirement

Read endpoints do not require idempotency.

Refund creation/submission/reconciliation commands remain idempotent.

## Audit/event requirement

Read access by parent/teacher normally does not create Event Ledger records.

Sensitive admin refund/payment detail access must generate appropriate audit/security logging when it exposes provider payloads, reconciliation proof, or sensitive financial details.

---

# 5. Patch 2 — Admin/OPS Refund Reconciliation UX

## Audit finding closed

`UX-AUD-002 — Manual/admin refund reconciliation endpoint/action is ambiguous`

## Exact UX correction

Replace ambiguous wording:

```text
refund reconciliation endpoint if implemented
```

with explicit admin reconciliation flow.

## New patched UX flow — Admin Refund Reconciliation

| Field | Specification |
|---|---|
| Actor | OPS/Admin; ADMIN required for exceptional/manual override policies |
| Entry point | Admin → Refunds → Refund detail → Reconcile |
| Preconditions | Refund exists; refund requires manual/provider reconciliation; actor has permission |
| UI state | Reconciliation form with source, reference, timestamp, reason, supporting evidence |
| User action | Admin records reconciliation result |
| API call | `POST /admin/refunds/:id/reconcile` or equivalent `RefundService.reconcileRefund()` command |
| Backend state transition | Refund moves to `SUCCEEDED` or `FAILED` according to reconciliation result; payment updates only after success |
| Success state | Refund timeline shows reconciliation proof and final status |
| Failure state | Missing reference, missing reconciled_at, missing reconciled_by_user_id for manual/admin reconciliation, invalid state |
| Loading state | “Saving reconciliation…” |
| Empty state | Not applicable |
| Permission failure | SUPPORT cannot perform financial reconciliation unless explicitly authorized |
| Idempotency behavior | Required for reconciliation command |
| Notification | Parent notified if refund succeeds or fails |
| Audit/event generated | `ADMIN_ACTION`; `REFUND_SUCCEEDED` or `REFUND_FAILED`; `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only on success |
| Next allowed action | Resolve dispute, update payout eligibility, or review recovery/adjustment impact |

## Required fields represented in UX

The reconciliation form must capture or represent:

```text
reconciliation_source
reconciliation_reference
reconciled_at
reconciled_by_user_id
reason
supporting evidence
```

Rules:

```text
reconciliation_source IS NOT NULL
→ reconciliation_reference required
→ reconciled_at required

MANUAL_RECONCILIATION / ADMIN_OVERRIDE
→ reconciled_by_user_id required
```

`reconciled_by_user_id` is usually derived from authenticated admin/OPS user, not manually typed.

## API contract dependency

The backend must provide a command authority for reconciliation.

Recommended endpoint:

```text
POST /admin/refunds/:id/reconcile
```

This is not a new feature. It is the admin command required to operate the approved refund reconciliation lifecycle.

## Backend authority

- OPS may reconcile routine provider records if policy allows.
- ADMIN required for `ADMIN_OVERRIDE` and exceptional/manual financial corrections.
- SUPPORT cannot reconcile refunds by default.

## User-facing state

Parent sees:

```text
Refund completed
```

or:

```text
Refund failed — support is reviewing
```

Parent does not see raw provider payload or internal reconciliation mechanics.

## Idempotency requirement

Required.

Same reconciliation command with same idempotency key and same request body returns same result.

## Audit/event requirement

Must generate:

```text
ADMIN_ACTION
REFUND_SUCCEEDED or REFUND_FAILED
PAYMENT_REFUNDED or PAYMENT_PARTIALLY_REFUNDED, only if refund succeeded
```

If sensitive provider/payment data is accessed during reconciliation, also generate appropriate security/audit event.

---

# 6. Patch 3 — Student Data Sharing Permission Flow

## Audit finding closed

`UX-AUD-003 — Student permission/data-sharing UX flow is missing`

## Exact UX correction

Add a dedicated Student Data Sharing Permission Flow.

## New patched UX flow — Student Data Sharing Permission

| Field | Specification |
|---|---|
| Actor | Parent grants/revokes; teacher receives limited access |
| Entry point | Student Passport, booking confirmation, session preparation, parent settings |
| Preconditions | Parent owns student; teacher exists; permission scope is valid |
| UI state | Permission panel showing teacher, scope, expiry, linked booking/session if any |
| User action | Parent grants, views, or revokes teacher access |
| API call | `POST /students/:id/permissions`; `DELETE /students/:id/permissions/:permission_id`; read permission list via student detail/passport API if implemented |
| Backend state transition | `student_permissions` row created or revoked |
| Success state | Teacher can access only permitted student/session context |
| Failure state | Student not owned, teacher invalid, permission expired, booking mismatch |
| Loading state | “Updating access…” |
| Empty state | “No teachers currently have access to this student profile.” |
| Permission failure | Teacher cannot access student context without permission or relevant session context |
| Idempotency behavior | Recommended for grant/revoke commands |
| Notification | Optional: parent confirmation; teacher notification if access granted for session preparation |
| Audit/event generated | Student profile update event; sensitive access may generate security/audit event |
| Next allowed action | Teacher views limited context; parent may revoke anytime |

## Permission scopes

MVP default:

```text
SESSION_CONTEXT
```

Displayed copy:

```text
This teacher can see only the information needed for the booked session, such as academic level, subject, learning goal, and relevant previous session notes you choose to share.
```

## Expiry behavior

Permission UX must show:

```text
Starts at
Expires at
Revoked at, if revoked
Linked booking/session, if applicable
```

If permission expires:

```text
Teacher access automatically ends.
```

## API contract dependency

The write endpoints already exist architecturally.

UX requires the ability to display active permissions. This may be returned through:

```text
GET /students/:id
GET /students/:id/passport
```

or a future implementation-level read endpoint:

```text
GET /students/:id/permissions
```

This is not a new feature; it is read visibility for approved permission records.

## Backend authority

- Parent owns grant/revoke authority.
- Teacher can only read within granted scope.
- Admin access to student data must be audited.

## User-facing state

Parent sees:

```text
Access active
Access expired
Access revoked
```

Teacher sees:

```text
Limited student context available for this session
```

## Idempotency requirement

Recommended for grant/revoke to avoid duplicate permissions or repeated revocation attempts.

## Audit/event requirement

- Grant/revoke should create a student profile/update event or equivalent audit event.
- Teacher access to sensitive Student Passport context should be auditable where appropriate.

---

# 7. Patch 4 — Admin Payout Processing Flow

## Audit finding closed

`UX-AUD-004 — Admin payout processing UX flow is missing`

## Exact UX correction

Add complete Admin Payout Processing Flow.

## New patched UX flow — Admin Payout Processing

| Field | Specification |
|---|---|
| Actor | OPS/Admin |
| Entry point | Admin → Payouts → Eligible queue |
| Preconditions | Sessions completed; reports exist; confirmed payments exist; no open disputes; refund exposure calculated; net teacher payable > 0 |
| UI state | Eligible payout queue with blocked reasons and payable breakdown |
| User action | OPS/Admin reviews batch and processes payout |
| API call | `POST /admin/payouts/process` |
| Backend state transition | Payout `ELIGIBLE` → `PROCESSING` → `PAID` or `FAILED` |
| Success state | Teacher sees payout processed/paid |
| Failure state | Provider payout failure, no longer eligible, open dispute, refund exposure changed, duplicate payout item |
| Loading state | “Processing payout…” |
| Empty state | “No eligible payouts.” |
| Permission failure | SUPPORT cannot process payouts; OPS/Admin only |
| Idempotency behavior | Required |
| Notification | Teacher payout processing/paid/failed notification |
| Audit/event generated | `PAYOUT_ELIGIBLE`, `PAYOUT_PROCESSED`, `ADMIN_ACTION`; provider failure audit metadata if failed |
| Next allowed action | Reconcile failed payout, retry safely, or view paid payout record |

## Eligible payout queue must show

```text
Teacher
Completed sessions
Report status
Payment status
Dispute status
Refund exposure
Gross teacher payable
Approved/provider-pending/succeeded refund adjustments
Other deductions
Net teacher payable
Blocked reason, if blocked
```

## Blocked reasons

Display explicit reasons:

```text
Session report missing
Open dispute
Refund approved/pending
Full refund
Net payable is zero
Payout waiting period not passed
Session already included in payout
```

## API contract dependency

Existing architecture defines:

```text
POST /admin/payouts/process
GET /admin/payouts
GET /teacher/payouts
GET /teacher/payouts/:id
```

Admin payout queue response must include payout eligibility and blocked reasons.

## Backend authority

- OPS/Admin can process payout.
- SUPPORT cannot process payout.
- PayoutService is the authority for net payable calculation.

## User-facing state

Teacher sees:

```text
Eligible
Processing
Paid
Failed
Blocked
Adjusted
```

## Idempotency requirement

Required for payout processing.

## Audit/event requirement

Must generate:

```text
ADMIN_ACTION
PAYOUT_ELIGIBLE, where applicable
PAYOUT_PROCESSED, when paid
```

Provider failure must be recorded and visible to OPS/Admin.

---

# 8. Patch 5 — Partial Refund / Payout Exposure UX

## Audit finding closed

`UX-AUD-005 — Refund exposure must affect payout before refund success`

## Exact UX correction

Payout UX must account for refund exposure from:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

Do not wait until `SUCCEEDED`.

## Required payout calculation display

Before payout processing, admin and teacher-facing payout breakdown must represent:

```text
gross_teacher_payable
- approved refund adjustment
- provider-pending refund adjustment
- succeeded refund adjustment
- other approved deductions
= net_teacher_payable
```

## User-facing distinctions

| Refund/payout condition | UX label |
|---|---|
| Refund `APPROVED` | Approved refund adjustment reserved |
| Refund `PROVIDER_PENDING` | Refund processing — payout adjusted |
| Refund `SUCCEEDED` | Refund completed — adjustment applied |
| Payout not yet paid | Net payout adjusted before payment |
| Payout already paid | Recovery/adjustment created separately |

## API contract dependency

Payout-related API responses must include enough fields to display:

```text
gross_teacher_payable
refund_exposure_total
refund_exposure_by_status
teacher_adjustment_amount
platform_adjustment_amount
other_deductions
net_teacher_payable
```

This can be returned through:

```text
GET /teacher/payouts
GET /teacher/payouts/:id
GET /admin/payouts
```

## Backend authority

PayoutService is the sole authority for net payable calculation.

Frontend must not calculate final payout from raw values alone.

## User-facing state

Teacher copy:

```text
Your estimated payout has been adjusted because a refund was approved or is being processed for this session.
```

Admin copy:

```text
This payout includes approved/provider-pending refund exposure. Net payable has been recalculated.
```

## Idempotency requirement

Payout processing remains idempotent.

Read-only payout display does not require idempotency.

## Audit/event requirement

Refund approval/submission/success creates refund events.

Payout processing creates payout/admin events.

---

# 9. Patch 6 — Post-Payout Recovery / Adjustment UX

## Audit finding closed

`UX-AUD-011 — Teacher recovery/adjustment UX after paid payout is under-specified`

## Exact UX correction

If refund occurs after payout is already `PAID`, UX must never imply the old payout was edited.

## Required UX behavior

Show a separate adjustment/recovery entry.

Teacher payout history:

```text
Payout #P-1001 — Paid — 1700 DZD
Adjustment #A-2001 — Recovery due to refund — -300 DZD
```

Admin ledger/recovery view:

```text
Original payout: PAID
Refund: SUCCEEDED
Teacher responsible share: 300 DZD
Platform absorbed share: 100 DZD
Recovery method: future payout offset / manual recovery / platform absorbed
Reference: dispute_id, refund_id
```

## Required fields in UX

```text
recovery_balance
adjustment_entry_id
future_payout_recovery_amount
platform_absorbed_amount
refund_reference
dispute_reference
created_at
status
```

## API contract dependency

Teacher payout/earnings responses must expose adjustment/recovery summaries if they exist.

Possible response fields:

```text
adjustments[]
recovery_balance
future_recovery_pending
platform_absorbed_amount
```

This is a representation of already-approved ledger adjustment/recovery behavior, not a new feature.

## Backend authority

LedgerService/PayoutService creates adjustment/recovery records.

Teacher cannot alter recovery records.

Admin cannot edit old paid payout; admin can only initiate approved adjustment/recovery workflows.

## User-facing state

Teacher labels:

```text
Adjustment applied
Recovery pending
Recovered from future payout
Platform absorbed
```

## Idempotency requirement

Adjustment/recovery creation must be idempotent if command-based.

Read-only display does not require idempotency.

## Audit/event requirement

Must generate:

```text
ADMIN_ACTION, if admin initiated
ledger adjustment/reversal event through Event Ledger metadata where applicable
```

Old payout remains immutable.

---

# 10. Patch 7 — Teacher Subjects & Pricing Flow

## Audit finding closed

`UX-AUD-007 — Teacher subjects/pricing flow is incomplete`

## Exact UX correction

Add Teacher Subjects & Pricing Flow.

## New patched UX flow — Teacher Subjects & Pricing

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Teacher dashboard → Subjects & Pricing |
| Preconditions | Teacher profile exists |
| UI state | Subject offering form/list |
| User action | Teacher creates, updates, deactivates subject offering |
| API call | `POST /teachers/subjects`, `PATCH /teachers/subjects/:id`, `DELETE /teachers/subjects/:id` or deactivate equivalent |
| Backend state transition | `teacher_subjects` created/updated/deactivated |
| Success state | Offering appears in teacher profile/search once listing rules are met |
| Failure state | Duplicate subject/level, invalid price, inactive subject/level, permission denied |
| Loading state | “Saving subject offering…” |
| Empty state | “Add at least one subject and level so parents can find you.” |
| Permission failure | Teacher can manage only own offerings |
| Idempotency behavior | Recommended for create/update/deactivate |
| Notification | None by default |
| Audit/event generated | `TEACHER_PROFILE_UPDATED` |
| Next allowed action | Add availability, submit verification, become listed if requirements met |

## Required fields

```text
subject
academic level
price per session
currency = DZD
session duration
active/inactive
```

## Duplicate offering validation

UX error:

```text
You already offer this subject for this academic level. Edit the existing offer instead.
```

## Update/delete behavior

MVP recommendation:

- Update future availability/search display.
- Do not alter historical bookings/session prices.
- Deactivation hides offering from new booking but preserves history.

## API contract dependency

Teacher subject endpoints are already in the API Architecture.

## Backend authority

Teacher owns their own offerings.

Admin may override only through audited admin path.

## User-facing state

```text
Active
Inactive
Draft profile requirement incomplete
```

---

# 11. Patch 8 — Reschedule Decision

## Audit finding closed

`UX-AUD-006 — Reschedule endpoint exists but UX does not define or explicitly exclude it`

## Decision

For MVP v0.1, reschedule is hidden from the user-facing UX.

Users must cancel and create a new booking.

## Exact UX correction

Do not show:

```text
Reschedule booking
```

as a normal parent/teacher action in MVP.

Instead show:

```text
Cancel this booking and book a new slot
```

## Rationale

Reschedule touches multiple sensitive states:

```text
booking
payment
slot
refund policy
teacher availability
notifications
audit trail
```

The architecture already supports a controlled reschedule endpoint, but MVP UX will not expose it until operational policies are mature.

## API contract dependency

`POST /bookings/:id/reschedule` may remain in backend architecture for future/controlled OPS use, but MVP public UX does not expose it.

## Backend authority

- Parent/teacher public UX: no reschedule.
- OPS/Admin may use controlled operational reschedule only if implementation explicitly permits it and creates audit events.

## User-facing state

Parent/teacher copy:

```text
To change the time, cancel this booking and select a new slot. Refund or cancellation rules may apply.
```

## Idempotency requirement

Cancellation remains recommended-idempotent.

New booking hold requires idempotency.

## Audit/event requirement

Cancel + new booking produces normal events:

```text
BOOKING_CANCELLED
BOOKING_CREATED
BOOKING_HELD
PAYMENT_INITIATED, if payment required
```

---

# 12. Patch 9 — Refund Rejected / Cancelled UX Treatment

## Audit finding closed

`UX-AUD-008 — Refund REJECTED and CANCELLED states lack complete user-facing treatment`

## Exact UX correction

Add labels, timeline behavior, and notification/copy for:

```text
REFUND_REJECTED
REFUND_CANCELLED
```

## State labels

| Refund state | Parent label | Admin label |
|---|---|---|
| `REJECTED` | Refund rejected | Rejected |
| `CANCELLED` | Refund cancelled | Cancelled before completion |

## Timeline behavior

### Rejected

```text
Refund requested
   ↓
Refund rejected
```

Do not show provider submission or refund completion steps.

### Cancelled

```text
Refund requested / approved
   ↓
Refund cancelled
```

Do not show provider success or payment refunded.

## User-facing copy

### Parent copy — rejected

```text
Your refund request was reviewed and rejected. You can view the reason in the dispute or contact support if you believe this is incorrect.
```

### Parent copy — cancelled

```text
This refund process was cancelled before completion. No refund was issued.
```

### Admin copy

```text
Rejected/cancelled refunds must include a reason. Provider evidence, if any, belongs in provider events or event ledger, not as refund success proof.
```

## API contract dependency

Refund read/status responses must include:

```text
status
reason
reason_code
rejected_at
cancelled_at
```

where applicable.

## Backend authority

OPS/Admin can reject/cancel according to policy.

Parent/teacher cannot self-approve/reject/cancel a refund after admin review has begun unless policy defines request withdrawal before review.

## Idempotency requirement

Refund reject/cancel commands should be idempotent if exposed as commands.

## Audit/event requirement

Must generate:

```text
REFUND_REJECTED
```

or:

```text
REFUND_CANCELLED
```

plus `ADMIN_ACTION` when admin/OPS performs the decision.

Notifications should be sent to affected parent.

---

# 13. Patch 10 — Sensitive Admin Access Must Audit

## Audit finding closed

`UX-AUD-010 — Sensitive admin access should say “must audit,” not “may audit”`

## Exact UX correction

Replace all ambiguous sensitive-access wording:

```text
may generate ADMIN_ACTION/SECURITY_EVENT
```

with:

```text
must generate ADMIN_ACTION and/or SECURITY_EVENT according to access type
```

## Sensitive access examples

Sensitive access includes:

```text
verification documents
raw/normalized payment provider payload
refund reconciliation proof
minor/student sensitive context
security events
admin override actions
ledger/reversal/adjustment detail
```

## API contract dependency

Admin endpoints that expose sensitive information must write audit/security records.

This is already required by architecture; UX copy must not weaken it.

## Backend authority

- ADMIN full audited access according to policy.
- OPS limited audited access.
- SUPPORT restricted view by default.

## User-facing/admin state

Admin UI should show:

```text
This access will be logged.
```

for sensitive views.

## Idempotency requirement

Read access does not require idempotency.

State-changing admin actions require idempotency where financial or operationally sensitive.

## Audit/event requirement

Mandatory:

```text
ADMIN_ACTION
SECURITY_EVENT
```

depending on action/access type.

---

# 14. Cross-Flow Corrections Introduced by This Patch

## 14.1 Refund visibility correction

Any screen showing payment/refund status must distinguish:

```text
Refund requested
Refund approved
Refund processing
Refund completed
Refund failed
Refund rejected
Refund cancelled
```

## 14.2 Payout exposure correction

Any payout screen must include refund exposure from:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

not only `SUCCEEDED`.

## 14.3 Dispute/refund/payout interaction correction

If dispute opens:

```text
payout blocked
```

If refund is approved/provider-pending:

```text
payout net payable adjusted or payout remains blocked depending policy
```

If refund succeeds after payout paid:

```text
recovery/adjustment entry created
old payout remains unchanged
```

## 14.4 Student privacy correction

Teacher access to student context must always be explained in UI through:

```text
scope
reason
expiry
revocation option
```

---

# 15. Updated Button Rules

## 15.1 Parent buttons

Add:

| Button | Show only when |
|---|---|
| Grant teacher access | Parent owns student; valid teacher/session context exists |
| Revoke teacher access | Active permission exists |
| View refund status | Refund exists for parent’s payment/booking/dispute |

Remove/hide for MVP:

| Button | Rule |
|---|---|
| Reschedule | Hidden from MVP public UX; use cancel + new booking |

## 15.2 Teacher buttons

Add:

| Button | Show only when |
|---|---|
| Add subject/pricing | Teacher owns profile |
| Edit subject/pricing | Teacher owns offering; offering not locked by historical booking |
| Deactivate offering | Teacher owns offering; deactivation preserves history |

## 15.3 Admin buttons

Add:

| Button | Show only when |
|---|---|
| Reconcile refund | Refund requires reconciliation; OPS/Admin permission |
| Process payout | Payout eligible; net payable > 0; no open dispute; refund exposure accounted for |
| View sensitive payload/document | ADMIN/authorized OPS; audited access |

---

# 16. Updated Notification Requirements

Add or clarify notifications:

| Event | Recipient | UX message |
|---|---|---|
| `REFUND_REJECTED` | Parent | Refund request rejected |
| `REFUND_CANCELLED` | Parent | Refund process cancelled |
| `PAYOUT_FAILED` or payout failure metadata | Teacher + OPS/Admin | Payout failed; support/ops reviewing |
| `TEACHER_VERIFIED` | Teacher | Verification approved |
| `TEACHER_REJECTED` | Teacher | Verification rejected |
| `SECURITY_EVENT` for sensitive account action | Affected user/admin depending policy | Security/account event recorded |

External notification failure does not roll back business state.

---

# 17. Updated UX Testing Checklist

Add these tests to UX validation.

## Refund tests

- [ ] Refund timeline shows all states distinctly.
- [ ] Refund `APPROVED` does not display as refunded.
- [ ] Refund `PROVIDER_PENDING` does not display as refunded.
- [ ] Refund `SUCCEEDED` displays as completed/refunded.
- [ ] Refund `FAILED` displays failure and support/admin next step.
- [ ] Refund `REJECTED` displays rejection reason.
- [ ] Refund `CANCELLED` displays cancellation state.

## Reconciliation tests

- [ ] Admin cannot reconcile without source.
- [ ] Admin cannot reconcile without reference.
- [ ] Admin cannot reconcile without reconciled timestamp.
- [ ] Manual/admin reconciliation uses authenticated admin as reconciled_by_user_id.
- [ ] Reconciliation access/action is audited.

## Student permission tests

- [ ] Parent can grant teacher limited access.
- [ ] Parent can view active teacher access.
- [ ] Parent can revoke access.
- [ ] Teacher cannot access Student Passport without permission/context.
- [ ] Expired permission blocks access.

## Payout tests

- [ ] Admin payout queue shows blocked reasons.
- [ ] Approved refund exposure reduces net teacher payable.
- [ ] Provider-pending refund exposure reduces net teacher payable.
- [ ] Succeeded refund adjustment is applied.
- [ ] Payout cannot process with open dispute.
- [ ] Paid payout is not edited after later refund.
- [ ] Recovery/adjustment entry appears separately.

## Teacher setup tests

- [ ] Teacher can add subject/level/price/duration.
- [ ] Duplicate offering is blocked with clear message.
- [ ] Deactivated offering disappears from new booking search but history remains.

## Reschedule tests

- [ ] Public reschedule button is not visible in MVP.
- [ ] User is guided to cancel and book a new slot.

## Admin audit tests

- [ ] Sensitive document access is audited.
- [ ] Payment/refund provider payload access is audited.
- [ ] Admin override is audited.

---

# 18. API Contract Dependencies Before Implementation

These are not architecture redesigns. They are implementation-level API contract clarifications required by the patched UX.

## Required before frontend implementation

1. Refund timeline visibility in payment/booking/dispute/admin responses.
2. Explicit admin refund reconciliation command authority.
3. Student permission read visibility for parent.
4. Admin payout eligibility/blocked-reason response fields.
5. Teacher payout adjustment/recovery response fields.
6. Teacher subject/pricing create/update/deactivate responses.
7. Refund rejected/cancelled status/copy fields.
8. Sensitive admin access audit enforcement.

If these are not defined in endpoint specs before frontend implementation, frontend may hardcode assumptions and violate architecture.

---

# 19. Remaining Open Policy Decisions

These remain open from UX Flows v1.0 and are not closed by this patch:

1. Exact booking hold duration.
2. Payment checkout timeout.
3. Late-payment policy: auto-refund vs OPS review.
4. No-show grace periods.
5. Parent dispute window.
6. Payout delay after report completion.
7. Refund allocation policy between teacher and platform.
8. Review eligibility after partial refund.
9. Notification channels.
10. Arabic/French final terminology.

These are not structural blockers for architecture, but they must be decided before high-fidelity UI copy and production rules.

---

# 20. Final Patch Status

All 10 required audit findings are closed at UX specification level.

No HIGH finding remains open in this patch.

No architecture redesign was introduced.

No implementation was started.

```text
UX Flows v1.1 Patch Status: PASS
```

Recommended next gate:

```text
UX Patch Review
```

If accepted, the project may proceed to:

```text
Low-fidelity wireframes
```

Do not proceed to frontend/backend implementation until UX Patch Review is complete.
