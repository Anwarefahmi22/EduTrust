# EduTrust Algeria — UX Audit v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** UX Audit v1.0  
**Audited document:** `EduTrust_UX_Flows_v1.0.md`  
**Implementation status:** Not started  
**Audit result:** **PASS WITH REQUIRED PATCHES**

---

# 1. Executive Summary

`EduTrust_UX_Flows_v1.0.md` correctly follows the locked architecture baseline in its most important areas:

- UX does not redefine the business logic.
- Dispute is treated as overlay.
- Late payment after expiry is represented correctly.
- Verified review eligibility is respected.
- Booking/payment/session separation is preserved.
- Refund lifecycle is not collapsed into a single “refunded” label.
- Payout after dispute/refund exposure is acknowledged.
- No AI, subscriptions, group classes, gamification, or scope expansion were introduced.

However, the audit found several gaps that must be patched before UI design or implementation. The main issues are not architecture-breaking; they are UX/API-contract completeness issues.

Most important required patches:

1. Refund status/timeline UX depends on refund read APIs or response fields that are not explicitly defined.
2. Manual/admin refund reconciliation is mentioned but lacks a concrete UX/API authority path.
3. Student data sharing permissions exist architecturally but have no complete UX flow.
4. Admin payout processing exists architecturally but has no complete UX flow.
5. Partial refund exposure must affect payout UX as soon as refund is `APPROVED` or `PROVIDER_PENDING`, not only after `SUCCEEDED`.

No critical architecture contradiction was found. The architecture baseline remains safe and locked, but UX Flows v1.0 should not proceed to UI design until required UX/API patches are made.

---

# 2. Audit Scope

The UX document was audited against the locked baseline:

1. PRD v1.0
2. Database Schema v1.0
3. API Architecture v1.0
4. State Machines v1.0
5. Schema Patch v1.1
6. State Machines v1.1 Addendum
7. Schema Patch v1.2
8. DDL Hardening v1.3
9. `edutrust_schema_patch_v1_3.sql`

The audit did **not** redesign the architecture and does **not** start implementation.

---

# 3. Severity Definitions

| Severity | Meaning |
|---|---|
| CRITICAL | UX contradicts locked architecture or could enable unsafe financial/session state |
| HIGH | UX/API gap could cause incorrect implementation of sensitive workflow |
| MEDIUM | Important completeness or consistency issue, but not unsafe if backend follows architecture |
| LOW | Copy, clarity, or minor completeness issue |
| OPEN POLICY DECISION | Product/ops parameter intentionally still undecided |

---

# 4. Overall Audit Result

```text
UX Audit Status: PASS WITH REQUIRED PATCHES
```

Reason:

- No CRITICAL findings.
- Several HIGH findings must be corrected before UI design or implementation.
- Architecture remains safe and locked.
- Required patches are mostly UX/API-contract clarifications, not database or state-machine redesigns.

---

# 5. Findings Summary

| ID | Severity | Area | Finding |
|---|---|---|---|
| UX-AUD-001 | HIGH | Refund APIs | Refund status/timeline UX lacks explicit read API contract |
| UX-AUD-002 | HIGH | Refund reconciliation | Manual/admin refund reconciliation endpoint/action is ambiguous |
| UX-AUD-003 | HIGH | Child privacy | Student permission/data-sharing UX flow is missing |
| UX-AUD-004 | HIGH | Payout | Admin payout processing UX flow is missing |
| UX-AUD-005 | HIGH | Partial refund / payout | Refund exposure must affect payout before refund success, not only after success |
| UX-AUD-006 | MEDIUM | Reschedule | Reschedule endpoint exists architecturally but UX does not define or explicitly exclude it |
| UX-AUD-007 | MEDIUM | Teacher marketplace setup | Teacher subjects/pricing flow is incomplete |
| UX-AUD-008 | MEDIUM | Refund lifecycle UI | Refund `REJECTED` and `CANCELLED` states lack complete user-facing treatment |
| UX-AUD-009 | MEDIUM | Payment initiation failure | Provider checkout failure/retry UX is under-specified |
| UX-AUD-010 | MEDIUM | Audit access | Sensitive admin audit/payment/document access should say “must audit,” not “may audit” |
| UX-AUD-011 | MEDIUM | Recovery after payout | Teacher recovery/adjustment UX after paid payout is under-specified |
| UX-AUD-012 | LOW | Auth UX | Login/logout/session-management UX is not fully described |
| UX-AUD-013 | LOW | Notifications | Some lifecycle notifications are missing from notification matrix |
| UX-AUD-014 | OPEN POLICY DECISION | Review eligibility | Review after partial refund remains policy-dependent |
| UX-AUD-015 | OPEN POLICY DECISION | Operational timing | Hold duration, grace periods, dispute window, payout delay remain open |

---

# 6. Detailed Findings

---

## UX-AUD-001 — Refund status/timeline UX lacks explicit read API contract

**Severity:** HIGH

### Exact UX flow

- Flow 20 — Refund Request
- Flow 21 — Partial Refund
- Flow 22 — Late Payment After Booking Expiry
- Flow 32 — Admin Refund Handling

### Exact problematic behavior

The UX expects users/admins to view a refund timeline:

```text
REQUESTED → APPROVED → PROVIDER_PENDING → SUCCEEDED / FAILED / REJECTED / CANCELLED
```

But the current API Architecture v1.0 explicitly defines:

```text
POST /payments/:id/refund
GET /payments/:id
GET /payments
```

It does not clearly define whether refund objects are returned through:

```text
GET /payments/:id
GET /bookings/:id
GET /disputes/:id
GET /admin/refunds
GET /refunds/:id
```

### Related architecture rule

Schema Patch v1.1/v1.3 introduced a dedicated `refunds` lifecycle. UX must not infer refund state only from `payments.status`.

### Why it is a problem

If frontend only sees payment status, it may collapse important states:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

into vague labels like “refund pending” or “refunded.” That would contradict refund lifecycle semantics.

### Recommended correction

Before implementation, define one of these API approaches:

Option A — Embed refund summaries in existing endpoints:

```text
GET /payments/:id includes refunds[]
GET /bookings/:id includes active_refund / refunds[]
GET /disputes/:id includes linked_refunds[]
```

Option B — Add explicit refund read endpoints:

```text
GET /refunds/:id
GET /payments/:id/refunds
GET /admin/refunds
GET /admin/refunds/:id
```

This is not a new feature; it is exposing the already-approved refund lifecycle.

### Requires architecture change?

No database/state-machine redesign. Requires API contract patch or implementation-level API clarification.

### Can be fixed at UX/API implementation level?

Yes, but must be fixed before frontend implementation.

---

## UX-AUD-002 — Manual/admin refund reconciliation endpoint/action is ambiguous

**Severity:** HIGH

### Exact UX flow

- Flow 32 — Admin Refund Handling

### Exact problematic behavior

Flow 32 says:

```text
POST /payments/:id/refund, refund reconciliation endpoint if implemented
```

This creates ambiguity. Schema/DDL v1.3 supports explicit reconciliation fields:

```text
reconciliation_source
reconciliation_reference
reconciled_at
reconciled_by_user_id
```

But the UX does not define the admin action that writes them.

### Related architecture rule

DDL Hardening v1.3 requires valid reconciliation proof for manual/admin reconciliation, especially for `SUCCEEDED` refunds without provider proof.

### Why it is a problem

Without a defined admin reconciliation action, implementers may:

- Overload `POST /payments/:id/refund` inconsistently.
- Mark refund `SUCCEEDED` without proper reconciliation proof.
- Create an admin UI with no clear backend authority.

### Recommended correction

Define an explicit admin reconciliation UX/API path, such as:

```text
POST /admin/refunds/:id/reconcile
```

or explicitly specify that reconciliation is performed by an internal refund reconciliation service with admin-controlled input.

Required UX fields:

```text
reconciliation_source
reconciliation_reference
reconciled_at
reconciled_by_user_id, implicit from admin auth for manual/admin reconciliation
reason
supporting evidence
```

### Requires architecture change?

No architecture redesign. Requires API contract patch to expose an already-approved lifecycle authority.

### Can be fixed at UX/API implementation level?

Yes, but should be fixed before implementation.

---

## UX-AUD-003 — Student permission/data-sharing UX flow is missing

**Severity:** HIGH

### Exact UX flow

- Flow 14 — Student Passport v0
- Teacher flows where teacher sees student/session context
- Missing dedicated flow for student permissions

### Exact problematic behavior

The UX says:

```text
Teacher can access student context only with permission/session context.
```

But it does not define how the parent grants, reviews, or revokes that permission.

API Architecture defines:

```text
POST /students/:id/permissions
DELETE /students/:id/permissions/:permission_id
```

Schema defines `student_permissions`.

### Related architecture rule

Child/minor data protection requires parental control, data minimization, and auditable access.

### Why it is a problem

Without a parent-facing permission UX, engineers may implement teacher access implicitly or too broadly.

That would weaken:

- Child privacy
- Parental control
- Teacher access boundaries
- Student Passport sharing rules

### Recommended correction

Add a dedicated UX flow:

```text
Flow — Student Data Sharing Permission
```

Include:

- Parent grants access during booking or from Student Passport.
- Scope displayed clearly, e.g. `SESSION_CONTEXT`.
- Expiry date shown.
- Teacher name/profile shown.
- Parent can revoke permission.
- Teacher sees only permitted context.
- Sensitive access may generate audit/security event.

### Requires architecture change?

No. The architecture already supports it.

### Can be fixed at UX/API implementation level?

Yes. Required before UI design involving Student Passport sharing.

---

## UX-AUD-004 — Admin payout processing UX flow is missing

**Severity:** HIGH

### Exact UX flow

- Flow 23 — Payout Visibility
- State-based admin buttons section
- Missing complete admin payout processing flow

### Exact problematic behavior

The UX mentions:

```text
Process payout
```

and teacher payout visibility, but does not provide a complete flow for:

```text
POST /admin/payouts/process
```

API Architecture and State Machines include payout processing:

```text
ELIGIBLE → PROCESSING → PAID / FAILED
```

### Related architecture rule

Payout eligibility requires:

```text
session COMPLETED
report exists
confirmed payment
no open dispute
no full refund
net_teacher_payable > 0
no duplicate payout item
```

### Why it is a problem

Payout is a financial transition. Without a complete admin UX flow, implementation may create an unsafe or incomplete payout screen.

### Recommended correction

Add:

```text
Flow — Admin Payout Processing
```

Include:

- Eligible payout queue
- Blocked reasons
- Net teacher payable calculation
- Approved/provider-pending/succeeded refund exposure
- Idempotency key
- Processing state
- Provider failure handling
- Ledger event/audit requirements
- `PAYOUT_ELIGIBLE`, `PAYOUT_PROCESSED`, `ADMIN_ACTION`

### Requires architecture change?

No. Existing API/state machine supports it.

### Can be fixed at UX/API implementation level?

Yes, but required before financial admin UI design.

---

## UX-AUD-005 — Refund exposure must affect payout before refund success

**Severity:** HIGH

### Exact UX flow

- Flow 21 — Partial Refund
- Flow 23 — Payout Visibility
- Flow 29 — Teacher Earnings/Payout View
- Flow 32 — Admin Refund Handling

### Exact problematic behavior

Flow 21 says teacher payout is adjusted when partial refund is completed/succeeded. It does mention adjustment, but it does not clearly state that payout must also account for refunds in:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

State Machines v1.1 Addendum requires payout exposure calculation before payout processing.

### Related architecture rule

Before payout processing:

```text
gross_teacher_payable
- reserved_or_succeeded_teacher_refund_adjustments
- other approved deductions
= net_teacher_payable
```

Refund exposure includes:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

### Why it is a problem

If UX/admin payout UI only adjusts after refund success, an admin might process payout while refund is already approved or provider-pending, creating overpayment risk.

### Recommended correction

Update payout-related UX copy and admin payout flow to show:

```text
Pending refund adjustment
Approved refund adjustment
Provider-pending refund adjustment
Succeeded refund adjustment
```

Teacher-facing copy should distinguish:

```text
Estimated net payout after approved refund adjustment
```

from:

```text
Final paid payout
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes. Required before payout UI design.

---

## UX-AUD-006 — Reschedule endpoint exists but UX does not define or explicitly exclude it

**Severity:** MEDIUM

### Exact UX flow

- Booking/cancellation flows
- Missing reschedule UX

### Exact problematic behavior

API Architecture defines:

```text
POST /bookings/:id/reschedule
```

UX Flows v1.0 does not define a reschedule flow or explicitly state that reschedule is disabled for MVP UI.

### Related architecture rule

API Architecture recommends reschedule as cancel old booking + create new booking when payment already confirmed.

### Why it is a problem

Designers may add a reschedule button without knowing whether it should:

- Mutate the booking,
- Cancel and recreate booking,
- Trigger refund/reconciliation,
- Require new payment,
- Preserve old audit trail.

### Recommended correction

Choose one UX rule before UI design:

Option A — MVP hides reschedule:

```text
Users cancel and book a new slot.
```

Option B — Define reschedule flow using approved backend rule:

```text
cancel old booking + create new booking, with audit metadata
```

### Requires architecture change?

No, but requires UX/API decision.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-007 — Teacher subjects/pricing flow is incomplete

**Severity:** MEDIUM

### Exact UX flow

- Flow 24 — Teacher Onboarding
- Teacher navigation includes Subjects & Pricing
- Missing complete subject/pricing management flow

### Exact problematic behavior

Flow 24 lists “add subjects/pricing” as next action, but no complete UX flow defines:

```text
POST /teachers/subjects
PATCH /teachers/subjects/:id
DELETE /teachers/subjects/:id
```

### Related architecture rule

Teacher offerings are required for matching and booking:

```text
teacher_subjects
subject
academic_level
price
session_duration
```

### Why it is a problem

Without subject/pricing UX, teacher onboarding cannot produce bookable supply.

### Recommended correction

Add:

```text
Flow — Teacher Subjects & Pricing
```

Include:

- Subject selection
- Academic level selection
- Price per session
- Duration
- Active/inactive state
- Duplicate offering conflict
- Validation
- Event `TEACHER_PROFILE_UPDATED`

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-008 — Refund `REJECTED` and `CANCELLED` states lack complete user-facing treatment

**Severity:** MEDIUM

### Exact UX flow

- State badges
- Flow 20 — Refund Request
- Flow 32 — Admin Refund Handling

### Exact problematic behavior

State badges include:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
```

but do not clearly label:

```text
REJECTED
CANCELLED
```

### Related architecture rule

Refund lifecycle includes:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

### Why it is a problem

Users/admins need clear final-state labels for rejected/cancelled refund workflows.

### Recommended correction

Add state labels:

| Refund state | Label |
|---|---|
| `REJECTED` | Refund rejected |
| `CANCELLED` | Refund cancelled |

Also define notification/copy if applicable.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-009 — Payment provider checkout failure/retry UX is under-specified

**Severity:** MEDIUM

### Exact UX flow

- Flow 8 — Payment Initiation
- Flow 9 — Payment Pending / Success / Failure

### Exact problematic behavior

Flow 8 says provider unavailable is a failure state, but does not define recovery if:

1. EduTrust created internal payment row.
2. Booking became `PAYMENT_PENDING`.
3. External provider checkout creation failed after DB commit.

### Related architecture rule

External provider calls must occur outside DB transactions. Therefore internal intent may exist before provider checkout succeeds.

### Why it is a problem

UX must not leave parent stuck in unclear state.

### Recommended correction

Define recovery states:

```text
Payment setup failed. Try again.
Payment pending but checkout unavailable. We are checking status.
Booking still reserved until hold/payment timeout.
```

Backend should expose enough payment status to allow retry safely using idempotency rules.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-010 — Sensitive admin access should say “must audit,” not “may audit”

**Severity:** MEDIUM

### Exact UX flow

- Flow 33 — Admin Audit/Event Views
- Admin verification/payment/refund flows

### Exact problematic behavior

Flow 33 says:

```text
Sensitive access may generate ADMIN_ACTION/SECURITY_EVENT
```

### Related architecture rule

Sensitive admin actions and access to verification documents/payment payloads must be auditable.

### Why it is a problem

“May” weakens the security/audit requirement.

### Recommended correction

Change wording to:

```text
Sensitive access must generate ADMIN_ACTION and/or SECURITY_EVENT according to access type.
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-011 — Teacher recovery/adjustment UX after paid payout is under-specified

**Severity:** MEDIUM

### Exact UX flow

- Flow 21 — Partial Refund
- Flow 23 — Payout Visibility
- Flow 29 — Teacher Earnings/Payout View

### Exact problematic behavior

UX correctly states that old paid payout is not edited, but does not define how teacher sees:

```text
TEACHER_RECOVERABLE
future recovery
negative adjustment
platform-absorbed refund
```

### Related architecture rule

Post-payout refund requires new adjustment/recovery ledger transaction, not old payout mutation.

### Why it is a problem

Teacher earnings UI may become confusing if later refunds appear without clear explanation.

### Recommended correction

Add UX treatment for:

```text
Recovery balance
Adjustment entry
Applied to future payout
Platform absorbed amount
Dispute/refund reference
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-012 — Login/logout/session-management UX is not fully described

**Severity:** LOW

### Exact UX flow

- Flow 1 — Parent Onboarding
- Flow 24 — Teacher Onboarding
- Missing explicit login/logout/session management UX

### Exact problematic behavior

Auth API includes:

```text
POST /auth/login
POST /auth/refresh
POST /auth/logout
POST /auth/revoke-sessions
```

UX focuses mostly on registration.

### Related architecture rule

Authentication model includes refresh-token rotation and session revocation.

### Why it is a problem

Not an MVP blocker, but account/security UX should eventually show:

- Login
- Logout
- Active sessions
- Revoke sessions

### Recommended correction

Add lightweight Account/Security UX flow.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-013 — Some lifecycle notifications are missing

**Severity:** LOW

### Exact UX flow

- Notifications matrix

### Exact problematic behavior

Notification matrix omits or under-specifies some lifecycle events:

```text
REFUND_REJECTED
REFUND_CANCELLED
PAYOUT_FAILED
TEACHER_VERIFIED
TEACHER_REJECTED
SECURITY_EVENT for sensitive account actions
```

### Related architecture rule

Notifications are not source of truth but should reflect critical state changes.

### Why it is a problem

Users may not receive clear updates for negative terminal states.

### Recommended correction

Add notification rows for these states or explicitly mark them as in-app/admin-only.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-014 — Review after partial refund remains policy-dependent

**Severity:** OPEN POLICY DECISION

### Exact UX flow

- Flow 15 — Verified Review
- Flow 21 — Partial Refund

### Exact problematic behavior

The UX correctly says review eligibility is backend-controlled, but the baseline still leaves open whether a parent can review after partial refund if no review was created before refund.

### Related architecture rule

State Machines v1.1 Addendum explicitly listed this as an open decision.

### Why it is a problem

The UI cannot finalize button visibility copy until policy is decided.

### Recommended correction

Choose a policy before high-fidelity UI:

Option A:

```text
Partial refund before review blocks review.
```

Option B:

```text
Partial refund before review still allows review but displays verified context.
```

### Requires architecture change?

No, unless review eligibility rules are changed in backend contract.

### Can be fixed at UX/API implementation level?

Yes.

---

## UX-AUD-015 — Operational timing parameters remain open

**Severity:** OPEN POLICY DECISION

### Exact UX flow

Multiple flows:

- Booking hold
- Payment timeout
- No-show
- Dispute
- Payout
- Notifications

### Exact problematic behavior

The UX correctly lists open decisions:

```text
hold duration
payment checkout timeout
late-payment auto-refund vs OPS review
no-show grace periods
dispute window
payout delay
notification channels
```

### Related architecture rule

These were intentionally not locked as structural architecture decisions.

### Why it is a problem

High-fidelity UI copy, countdowns, notification timing, and admin SLA displays need exact values.

### Recommended correction

Create a short Product/Ops Policy v1.0 before final UI copy.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Partially, but values should be decided before production.

---

# 7. Specific Audit Areas A–T

## A. State transition correctness

**Result:** PASS WITH REQUIRED PATCHES

The main state transitions are correct. Required patches relate to missing payout/admin/refund read flows, not invalid state transitions.

## B. API endpoint consistency

**Result:** PASS WITH REQUIRED PATCHES

Most UX endpoints exist in API Architecture. Ambiguous or missing contracts:

```text
refund read/status endpoints
manual/admin refund reconciliation endpoint
action for admin payout processing UX flow absent from flow section
student permission flow missing despite API support
```

## C. Authorization

**Result:** PASS WITH REQUIRED PATCHES

Role/ownership logic is generally respected. Required patch: student permission UX must make parental control explicit.

## D. Idempotency

**Result:** PASS

Duplicate taps, payment initiation, booking hold, refund, and payout are acknowledged. UX should ensure generated idempotency keys are reused on retry for same user action.

## E. Booking hold expiry

**Result:** PASS

Expired hold behavior is correctly represented.

## F. Payment/webhook behavior

**Result:** PASS WITH MEDIUM PATCH

Webhook delay and payment pending states are correct. Provider checkout setup failure needs more detailed UX recovery.

## G. Late payment after expiry

**Result:** PASS

The UX correctly states:

```text
payment confirmed
booking remains expired/cancelled
session not created
refund/reconciliation created
```

## H. Refund lifecycle

**Result:** PASS WITH REQUIRED PATCHES

Lifecycle is correct, but read/reconciliation endpoints and rejected/cancelled display need completion.

## I. Partial refund

**Result:** PASS WITH REQUIRED PATCH

Needs clearer treatment of approved/provider-pending refund exposure before payout success.

## J. Refund after payout

**Result:** PASS WITH MEDIUM PATCH

Correctly avoids old payout mutation. Needs clearer teacher-facing recovery/adjustment UX.

## K. Dispute overlay

**Result:** PASS

UX correctly keeps booking/session factual state separate from dispute overlay.

## L. No-show

**Result:** PASS

Teacher/student no-show distinctions are correct. Teacher no-show via parent report correctly requires review/dispute.

## M. Review eligibility

**Result:** PASS WITH OPEN POLICY DECISION

Verified-review principles are respected. Partial-refund review policy remains open.

## N. Payout eligibility

**Result:** PASS WITH REQUIRED PATCHES

Payout blocked/dispute logic is correct. Admin payout processing flow and refund-exposure treatment must be added.

## O. Student/child privacy

**Result:** PASS WITH REQUIRED PATCH

Privacy principle is respected, but the explicit permission-management UX is missing.

## P. Admin/SUPPORT privilege separation

**Result:** PASS

UX generally separates SUPPORT/OPS/ADMIN. Sensitive access wording should be strengthened from “may audit” to “must audit.”

## Q. Event Ledger requirements

**Result:** PASS WITH MEDIUM PATCH

Most flows list events. Sensitive admin access should explicitly require event/security logging.

## R. Notification correctness

**Result:** PASS WITH LOW PATCH

Main notifications included. Some terminal/negative lifecycle events should be added.

## S. Empty/loading/error states

**Result:** PASS

The UX document consistently includes loading/empty/failure states.

## T. Cross-flow consistency

**Result:** PASS WITH REQUIRED PATCHES

Main cross-flow consistency is strong. Required improvements center on refund visibility, payout processing, and data-sharing permissions.

---

# 8. Invented Endpoints

Potentially invented or ambiguous endpoint references:

| UX reference | Status | Recommendation |
|---|---|---|
| “refund reconciliation endpoint if implemented” | Ambiguous / not defined | Define explicit admin reconciliation endpoint or internal service authority before implementation |

No other clearly invented endpoint was found.

---

# 9. Missing Endpoints or Missing API Response Contracts Required by UX

| UX need | Missing/ambiguous API contract | Severity |
|---|---|---|
| Parent/admin refund timeline | Refund read endpoints or embedded refund response fields | HIGH |
| Admin manual refund reconciliation | Explicit reconciliation command endpoint/action | HIGH |
| Student permission management UX | API exists, UX missing | HIGH |
| Admin payout processing | API exists, UX flow missing | HIGH |
| Teacher subject/pricing management | API exists, UX flow incomplete | MEDIUM |
| Reschedule | API exists, UX missing/unspecified | MEDIUM |

---

# 10. UX Actions That Lack Clear Backend Authority

| UX action | Issue | Fix |
|---|---|---|
| Admin refund reconciliation | No explicit endpoint/action authority | Define endpoint/service |
| Admin payout processing | Button mentioned but no full flow | Add full flow tied to `/admin/payouts/process` |
| Parent grants teacher student context | Permission concept exists but no UX flow | Add data-sharing permission flow |
| Reschedule | Endpoint exists but UX not defined | Hide or define cancel+new-booking flow |

---

# 11. Backend States With No Complete UX Representation

| Backend state | UX gap |
|---|---|
| Refund `REJECTED` | Missing state badge/copy/notification |
| Refund `CANCELLED` | Missing state badge/copy/notification |
| Refund reconciliation proof | Admin UX ambiguous |
| API idempotency `FAILED` internal state | No user issue if translated to retry/error; okay |
| Provider event `FAILED/REJECTED` | Admin audit/reconciliation view should expose it |
| Payout `FAILED` | Notification exists partly, needs admin/teacher treatment |
| Teacher recovery balance | Under-specified |

---

# 12. UX States With No Backend Representation

No major unsafe UX-only states found.

Potential ambiguity:

```text
“Refund processing”
```

must map clearly to:

```text
REFUND_PROVIDER_SUBMITTED / PROVIDER_PENDING
```

and not to `APPROVED` or `SUCCEEDED`.

---

# 13. Required UX Patch Scope

Recommended next document:

```text
EduTrust_UX_Flows_v1.1_Patch.md
```

It should patch only:

1. Refund read/status response expectations.
2. Admin refund reconciliation flow.
3. Student data-sharing permission flow.
4. Admin payout processing flow.
5. Partial refund exposure before payout.
6. Teacher recovery/adjustment UX after paid payout.
7. Teacher subjects/pricing flow.
8. Reschedule decision: hidden or explicitly defined.
9. Refund rejected/cancelled state labels.
10. Sensitive admin access “must audit.”

Do not redesign the architecture.

---

# 14. Final Decision

```text
UX Audit Status: PASS WITH REQUIRED PATCHES
```

There are no CRITICAL findings.

There are HIGH findings, so do **not** proceed to UI design or implementation yet.

Required next step:

```text
EduTrust_UX_Flows_v1.1_Patch.md
```

After the UX patch is reviewed, if no HIGH issues remain, the project can proceed to low-fidelity wireframes.
