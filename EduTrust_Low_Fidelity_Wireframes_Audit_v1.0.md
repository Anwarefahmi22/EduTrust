# EduTrust Algeria — Low-Fidelity Wireframes Audit v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Audited document:** `EduTrust_Low_Fidelity_Wireframes_v1.0.md`  
**Audit type:** Full UX wireframe architecture audit  
**Implementation status:** Not started  
**Architecture baseline:** LOCKED  
**Audit result:** **PASS WITH REQUIRED PATCHES**

---

# 1. Executive Summary

The low-fidelity wireframes document is strong and covers the required 64 screens across Parent, Teacher, and Admin/OPS experiences.

It correctly preserves the major architectural rules:

- No backend implementation is started.
- No high-fidelity UI is started.
- No architecture, database, API, or state-machine redesign is introduced.
- Reschedule is hidden from MVP public UX and replaced by cancel + new booking.
- Refund states remain distinct.
- Payout UI shows gross, refund exposure, deductions, and net teacher payable.
- Student permission boundaries are represented.
- Dispute appears as overlay rather than replacing factual booking/session state.
- Paid payout immutability is reflected.
- No AI tutor, AI matching, recording, subscriptions, group classes, gamification, or scope expansion appears.

However, the audit found several required corrections before moving to high-fidelity UI. The findings are mostly wireframe/API-contract precision issues, not architecture redesign issues.

Most important:

1. Late payment after booking expiry needs a clearer explicit screen/state variant.
2. Sensitive admin access still uses “may audit” wording in several places; it must be corrected to “must audit” when access is sensitive.
3. Admin recovery/adjustment CTA needs explicit backend command authority or must be represented as an implementation-level API contract dependency before UI design.
4. Several endpoints used in wireframes are implementation-level contract dependencies and should be normalized before frontend work.

No CRITICAL finding was found.

---

# 2. Final Audit Decision

```text
Low-Fidelity Wireframes Audit Status: PASS WITH REQUIRED PATCHES
```

Do **not** proceed to high-fidelity UI yet.

Do **not** proceed to frontend implementation.

Do **not** proceed to backend implementation.

Recommended next step:

```text
EduTrust_Low_Fidelity_Wireframes_v1.1_Patch.md
```

---

# 3. Audit Scope

Audited against:

1. EduTrust PRD v1.0
2. Database Schema v1.0
3. API Architecture v1.0
4. State Machines v1.0
5. Schema Patch v1.1
6. State Machines v1.1 Addendum
7. Schema Patch v1.2
8. DDL Hardening v1.3
9. `edutrust_schema_patch_v1_3.sql`
10. UX Flows v1.0
11. UX Flows v1.1 Patch
12. UX Audit v1.0

---

# 4. Screen Coverage Result

## 4.1 Parent screens

**Result:** PASS

All requested 28 Parent screens are present:

```text
P-01 to P-28
```

## 4.2 Teacher screens

**Result:** PASS

All requested 17 Teacher screens are present:

```text
T-29 to T-45
```

## 4.3 Admin/OPS screens

**Result:** PASS

All requested 19 Admin/OPS screens are present:

```text
A-46 to A-64
```

## 4.4 Total screen count

```text
28 Parent + 17 Teacher + 19 Admin/OPS = 64 screens
```

Coverage is complete at index level.

---

# 5. Findings Summary

| ID | Severity | Area | Finding |
|---|---|---|---|
| LFW-AUD-001 | HIGH | Late payment | Late payment after expiry lacks an explicit dedicated screen/state variant |
| LFW-AUD-002 | HIGH | Admin audit | Sensitive admin access still uses “may audit” wording in several screens |
| LFW-AUD-003 | HIGH | Recovery/adjustment | Admin recovery/adjustment CTA lacks explicit backend command authority |
| LFW-AUD-004 | MEDIUM | API contract | Refund/admin/refund-read endpoints remain partly implementation-dependent |
| LFW-AUD-005 | MEDIUM | Endpoint consistency | `GET /teacher/bookings` should be normalized to scoped `GET /bookings` or formally defined |
| LFW-AUD-006 | MEDIUM | Availability API | Availability block/unblock endpoints are not named explicitly in wireframes |
| LFW-AUD-007 | MEDIUM | Notifications API | Notification endpoints need API contract confirmation before frontend implementation |
| LFW-AUD-008 | MEDIUM | Account/security | Account security screens depend on incomplete session/security read APIs |
| LFW-AUD-009 | LOW | Payment success error copy | P-15 uses “support/retry” wording for impossible state; should avoid implying retriable mutation |
| LFW-AUD-010 | OPEN POLICY DECISION | Policy values | Open policy placeholders remain correctly unresolved |

---

# 6. Detailed Findings

---

## LFW-AUD-001 — Late payment after expiry lacks explicit dedicated screen/state variant

**Severity:** HIGH

### Exact wireframe screen(s)

- P-14 — Payment Pending
- P-16 — Payment Failure / Retry
- P-17 — Booking Detail
- P-22 — Refund Timeline
- P-21 — Payment / Invoice History

### Exact problematic behavior

The wireframes correctly mention late payment in navigation and financial rules, but there is no explicit parent-facing screen or state variant that clearly shows the dangerous branch:

```text
payment = CONFIRMED
booking remains EXPIRED/CANCELLED
session NOT created
slot NOT reassigned
refund/reconciliation created
```

P-14 says navigation may go to “Late Payment/Reconciliation if applicable,” but no concrete low-fidelity screen defines what the parent sees.

### Related architecture rule

State Machines v1.1 Addendum and Schema Patch v1.1 require:

```text
Expired booking + late provider success
=
Payment CONFIRMED
Booking remains EXPIRED/CANCELLED
Session NOT created
Slot NOT reassigned
Refund/Reconciliation workflow created
```

### Why it is a problem

This is one of the highest-risk financial/fulfillment cases. If not represented explicitly, high-fidelity UI or frontend implementation could accidentally show:

```text
Payment success = booking confirmed
```

which is false in the late-payment branch.

### Recommended correction

Add a dedicated state variant or sub-screen:

```text
P-14A / P-22A — Late Payment After Expiry / Reconciliation
```

Required content:

```text
Payment received
Reservation expired before confirmation
Booking was not confirmed
No session was scheduled
Refund/reconciliation started
Choose another slot
View refund timeline
Contact support
```

Required disabled actions:

```text
View session disabled
Review disabled
Teacher payout not shown
Rebook expired slot disabled
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes. Required before high-fidelity UI.

---

## LFW-AUD-002 — Sensitive admin access still uses “may audit” wording

**Severity:** HIGH

### Exact wireframe screen(s)

The following lines/screens contain wording such as “may audit” or “may generate” for sensitive access:

- P-06 — Student Passport v0
- T-43 — Student Session Context / Permission Boundary
- A-49 — Booking Monitoring
- A-51 — Refund Queue
- A-60 — Event Ledger
- A-61 — Security Events
- A-64 — Audit Trail

Examples:

```text
sensitive teacher/admin access may audit
sensitive drilldown may audit based on scope
sensitive access may audit
sensitive viewing may audit depending policy
sensitive audit access may audit depending policy
```

### Related architecture rule

UX Flows v1.1 Patch closed UX-AUD-010 by replacing “may audit” with:

```text
must generate ADMIN_ACTION and/or SECURITY_EVENT according to access type
```

Sensitive access must be audited.

### Why it is a problem

The low-fidelity wireframes partially reintroduced the weaker language. This can lead designers or implementers to treat audit logging as optional.

### Recommended correction

Replace all sensitive-access “may audit” wording with:

```text
Sensitive access must generate ADMIN_ACTION and/or SECURITY_EVENT according to access type.
```

For non-sensitive ordinary reads, say:

```text
No Event Ledger entry required for ordinary read.
```

For mixed screens, say:

```text
Ordinary list read does not require Event Ledger. Opening sensitive details must be audited.
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes. Required before high-fidelity UI.

---

## LFW-AUD-003 — Admin recovery/adjustment CTA lacks explicit backend command authority

**Severity:** HIGH

### Exact wireframe screen(s)

- A-59 — Recovery / Adjustment

### Exact problematic behavior

A-59 includes:

```text
[Create adjustment]
```

and lists:

```text
Admin payout/refund/ledger adjustment endpoints as implementation-level commands
```

but the API Architecture does not yet define a concrete endpoint such as:

```text
POST /admin/recoveries
POST /admin/ledger/adjustments
POST /admin/payouts/:id/recovery
```

### Related architecture rule

State Machines v1.1 Addendum and UX Patch v1.1 require:

```text
Paid payout + later refund
= new financial adjustment / recovery transaction
old payout remains immutable
```

Every CTA must correspond to approved backend authority.

### Why it is a problem

The product needs the recovery/adjustment UX, but the CTA is financially sensitive. Without a named backend command authority, implementation could accidentally:

- edit old payout,
- create non-idempotent adjustment,
- bypass ledger reversal/adjustment rules,
- fail to audit admin action.

### Recommended correction

Before high-fidelity UI, either:

Option A — Keep A-59 as read-only for low-fidelity and mark:

```text
[Create adjustment] hidden until backend command is specified
```

or Option B — Add API contract clarification:

```text
POST /admin/recoveries
```

or equivalent internal command, with:

```text
idempotency required
ADMIN/OPS authority
ledger adjustment transaction
ADMIN_ACTION event
no old payout mutation
```

### Requires architecture change?

No database/state-machine redesign. Requires API command clarification before implementation.

### Can be fixed at UX/API implementation level?

Yes. Required before high-fidelity UI for admin finance screens.

---

## LFW-AUD-004 — Refund/admin refund-read endpoints remain partly implementation-dependent

**Severity:** MEDIUM

### Exact wireframe screen(s)

- P-22 — Refund Timeline
- A-51 — Refund Queue
- A-52 — Refund Detail
- A-53 — Refund Reconciliation

### Exact problematic behavior

The wireframes reference:

```text
GET /admin/refunds
GET /admin/refunds/:id
refund read endpoint if implemented
refund read through payment/dispute response
```

UX Patch v1.1 allowed either embedded refund summaries or explicit refund read endpoints. The wireframes still leave this partly unresolved.

### Related architecture rule

Refund lifecycle exists in the database and must be visible in UX. However, API read contract must be explicit before frontend work.

### Why it is a problem

Frontend cannot reliably build refund timelines unless the API contract decides where refund data comes from.

### Recommended correction

Before frontend implementation, define one canonical approach:

Option A:

```text
GET /payments/:id includes refunds[]
GET /bookings/:id includes active_refund/refunds[]
GET /disputes/:id includes linked_refunds[]
GET /admin/payments and GET /admin/disputes include refund filters
```

Option B:

```text
GET /refunds/:id
GET /payments/:id/refunds
GET /admin/refunds
GET /admin/refunds/:id
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-005 — `GET /teacher/bookings` should be normalized or formally defined

**Severity:** MEDIUM

### Exact wireframe screen(s)

- T-31 — Teacher Dashboard

### Exact problematic behavior

T-31 references:

```text
GET /teacher/bookings or GET /bookings scoped
```

API Architecture primarily supports scoped booking list behavior through booking APIs.

### Related architecture rule

Teacher can view own bookings, but endpoint naming should be consistent.

### Why it is a problem

If designers/developers treat `GET /teacher/bookings` as canonical without API approval, it creates endpoint drift.

### Recommended correction

Use canonical scoped endpoint in wireframes:

```text
GET /bookings?scope=teacher
```

or explicitly define:

```text
GET /teacher/bookings
```

as an alias in API contract before implementation.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-006 — Availability block/unblock endpoints are not named explicitly

**Severity:** MEDIUM

### Exact wireframe screen(s)

- T-33 — Availability Management

### Exact problematic behavior

T-33 references:

```text
block/unblock endpoints
```

but does not name them.

### Related architecture rule

API Architecture defined availability management including block/unblock operations.

### Why it is a problem

Wireframes should map actions to concrete endpoint names where available.

### Recommended correction

Use explicit endpoint references:

```text
POST /teachers/availability/slots/:id/block
POST /teachers/availability/slots/:id/unblock
```

if these are the canonical API contract.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-007 — Notification endpoints need API contract confirmation

**Severity:** MEDIUM

### Exact wireframe screen(s)

- P-27 — Notifications
- T-44 — Notifications

### Exact problematic behavior

Wireframes reference:

```text
GET /notifications
POST /notifications/:id/read
```

These are consistent with the notification model, but the endpoint contract should be confirmed before frontend implementation.

### Related architecture rule

Notifications are tracked internally and external providers are not the source of truth.

### Why it is a problem

Notification UI depends on list/read behavior, unread counts, and target navigation.

### Recommended correction

Confirm API response fields:

```text
notification_id
event_type
entity_type
entity_id
title
body
status
created_at
read_at
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-008 — Account/security screens depend on incomplete session/security read APIs

**Severity:** MEDIUM

### Exact wireframe screen(s)

- P-28 — Account / Security
- T-45 — Account / Security

### Exact problematic behavior

The screens show active sessions/security events but only list auth mutation endpoints clearly:

```text
POST /auth/logout
POST /auth/revoke-sessions
```

They do not define how active sessions are read.

### Related architecture rule

Auth architecture includes `auth_sessions`, refresh token rotation, revocation, and security events.

### Why it is a problem

Frontend cannot display session management without read endpoint or embedded account security response.

### Recommended correction

Before frontend implementation, define one:

```text
GET /auth/sessions
GET /account/security
```

or embed active sessions in account settings response.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-009 — P-15 “support/retry” wording should avoid implying retriable mutation

**Severity:** LOW

### Exact wireframe screen(s)

- P-15 — Payment Success

### Exact problematic behavior

P-15 error state says:

```text
Payment confirmed but session missing should not occur; show support/retry status if detected
```

### Related architecture rule

Payment confirmation transaction must synchronously create session. Stable `CONFIRMED + BOOKED + no session` should not occur.

### Why it is a problem

“Retry” might imply the parent can retry payment/session creation. This should be an operational incident, not a user action.

### Recommended correction

Change to:

```text
If payment confirmed but session missing is detected, show support escalation and automatic status refresh. Do not show retry payment or retry booking.
```

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Yes.

---

## LFW-AUD-010 — Open policy placeholders remain correctly unresolved

**Severity:** OPEN POLICY DECISION

### Exact wireframe screen(s)

- P-12 Booking Hold
- P-14 Payment Pending
- P-16 Payment Failure
- T-36 Attendance
- A-55 Dispute Detail
- T-39 Earnings
- A-56 Payout Eligible Queue
- P-20 Review
- P-27/T-44 Notifications
- All final copy/terminology screens

### Exact behavior

The document correctly uses:

```text
[POLICY DECISION REQUIRED]
```

for unresolved values such as:

- Booking hold duration
- Payment checkout timeout
- Late-payment auto-refund vs OPS review
- No-show grace periods
- Parent dispute window
- Payout delay
- Refund allocation teacher/platform
- Review eligibility after partial refund
- Notification channels
- Arabic/French terminology

### Related architecture rule

These are operational/product policy decisions, not structural architecture decisions.

### Why it is not a blocker

Low-fidelity review can proceed with placeholders, but high-fidelity copy and production behavior cannot be finalized until policy values are chosen.

### Recommended correction

Keep placeholders. Create a separate Product/Ops Policy v1.0 before high-fidelity copy and production implementation.

### Requires architecture change?

No.

### Can be fixed at UX/API implementation level?

Partially, but should be decided before production.

---

# 7. Required Low-Fidelity Patch Scope

Recommended next document:

```text
EduTrust_Low_Fidelity_Wireframes_v1.1_Patch.md
```

Patch only the following:

1. Add explicit late-payment-after-expiry screen/state variant.
2. Replace all sensitive “may audit” wording with mandatory audit wording.
3. Resolve A-59 recovery/adjustment backend authority:
   - either make it read-only until API command is specified,
   - or define the API contract dependency explicitly.
4. Normalize or mark implementation-dependent refund read/admin refund endpoints.
5. Normalize `GET /teacher/bookings` to scoped `GET /bookings` or formally define alias.
6. Name availability block/unblock endpoints explicitly.
7. Confirm notification read/list endpoint expectations.
8. Clarify account/security read endpoint dependency.
9. Change P-15 error copy to support escalation/status refresh, not user retry.

Do not redesign wireframes.

Do not add new MVP features.

---

# 8. Audit Areas Requested by Gate

## 8.1 Do the 64 screens cover UX Flows v1.1?

**Result:** PASS WITH PATCHES

Coverage is complete at index level. Late-payment branch needs explicit screen/state variant.

## 8.2 Does every CTA have backend authority/state transition?

**Result:** PASS WITH PATCHES

Most CTAs map correctly. A-59 “Create adjustment” needs explicit backend command authority or must be read-only until defined.

## 8.3 Are any screens using APIs not defined in architecture?

**Result:** PASS WITH PATCHES

Most are consistent with architecture or UX Patch dependencies. Some endpoint names need normalization/contract clarification.

## 8.4 Are states missing or contradictory?

**Result:** PASS WITH PATCHES

Main states are present. Late payment branch needs explicit UI. Refund states are otherwise well represented.

## 8.5 Refund/Payout v1.1 consistency

**Result:** PASS

Refund exposure from `APPROVED`, `PROVIDER_PENDING`, and `SUCCEEDED` is represented in payout screens.

Paid payout immutability is represented.

## 8.6 Permissions

**Result:** PASS WITH PATCHES

Role/ownership is mostly correct. Sensitive audit wording must be strengthened.

## 8.7 MVP scope

**Result:** PASS

No out-of-scope MVP features were introduced.

## 8.8 Cross-screen consistency

**Result:** PASS WITH PATCHES

Most consistency is strong. Audit wording and late-payment screen variant require patch.

## 8.9 Reschedule hidden?

**Result:** PASS

Reschedule is hidden in MVP and replaced by cancel + new booking.

## 8.10 Are the 64 screens enough before high-fidelity?

**Result:** PASS WITH PATCHES

The screen set is sufficient after a small v1.1 low-fidelity patch.

---

# 9. Final Decision

```text
Low-Fidelity Wireframes Audit Status: PASS WITH REQUIRED PATCHES
```

No CRITICAL findings.

There are HIGH findings, so do not proceed to high-fidelity UI until a low-fidelity patch is produced and reviewed.

Recommended next step:

```text
EduTrust_Low_Fidelity_Wireframes_v1.1_Patch.md
```

Do not proceed to frontend implementation.

Do not proceed to backend implementation.
