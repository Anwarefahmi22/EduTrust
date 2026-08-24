# EduTrust Algeria — Clickable Prototype Patch v1.1

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Patch to `EduTrust_Clickable_Prototype_Specification_v1.0.md`  
**Source audit:** `EduTrust_Clickable_Prototype_Audit_v1.0.md`  
**Status:** READY FOR RE-AUDIT  
**Implementation status:** No frontend/backend implementation started  
**Architecture baseline:** LOCKED

---

# 1. Purpose

This patch closes the required findings from `EduTrust_Clickable_Prototype_Audit_v1.0.md`.

This patch does **not**:

- modify architecture,
- modify database,
- modify API architecture,
- modify state machines,
- modify UX business logic,
- expand MVP,
- invent policy values,
- start frontend implementation,
- start backend implementation,
- write production UI code.

---

# 2. Findings Closed

| Finding | Severity | Patch action | Status |
|---|---:|---|---|
| CP-AUD-001 — Visible “Simulate ...” labels | HIGH | Move all simulation controls to tester-only prototype controls / hidden hotspots | Closed |
| CP-AUD-002 — Network timeout and duplicate tap need explicit frames | MEDIUM | Add explicit state frames/variants | Closed |
| CP-AUD-003 — Frame naming crosswalk needed | LOW | Add frame ID crosswalk table | Closed |
| CP-AUD-004 — Open policy decisions | OPEN POLICY | Keep placeholders | Accepted |

---

# 3. Patch 1 — Prototype-Only Simulation Controls

## Finding closed

`CP-AUD-001 — Visible “Simulate ...” labels could imply unauthorized state changes`

## Patch decision

All simulation controls are moved out of role-facing UI.

They must be implemented as either:

1. hidden Figma hotspots,
2. a separate facilitator-only prototype controls page,
3. or clearly marked testing controls outside user-visible frames.

## New prototype-only frame

Add:

```text
CP-TEST-00 — Prototype Test Controls
```

Purpose:

```text
Facilitator-only branch control frame.
Not visible to parent, teacher, admin, or normal prototype participants.
```

Visible warning at top:

```text
Prototype facilitator controls only — not part of product UI.
```

## Controls moved to CP-TEST-00

The following labels must not appear as user-facing UI:

```text
Simulate confirmed payment
Simulate late payment
Simulate refund completed
Simulate refund failed
Simulate refund rejected
Simulate refund cancelled
Simulate payment failed
Simulate verification issue
Simulate provider payout failure
```

## User-facing replacements

Where users need an action, use legitimate labels:

| Previous test label | User-facing replacement |
|---|---|
| Simulate confirmed payment | Refresh status |
| Simulate late payment | Refresh status |
| Simulate payment failed | Refresh status / View payment status |
| Simulate refund completed | View refund status |
| Simulate refund failed | View refund status |
| Simulate refund rejected | View refund status |
| Simulate refund cancelled | View refund status |
| Simulate verification issue | Automatic status refresh / Contact support |
| Simulate provider payout failure | Not user-facing; facilitator-only branch |

## Updated interaction pattern

Example for payment pending:

```text
CP-P-13 Payment Pending
User-facing button: Refresh status
Destination by prototype variant:
  - CP-P-14 Payment Success
  - CP-P-15 Payment Failure
  - CP-P-16 Late Payment After Expiry
  - CP-P-31 Operational Incident
```

The branch choice is controlled by the facilitator/tester in prototype mode, not by a visible product CTA.

## Backend authority preserved

Provider/system-driven transitions remain represented as backend-driven results, not user-triggered commands.

---

# 4. Patch 2 — Explicit Network Timeout / Duplicate Tap / Disabled Frames

## Finding closed

`CP-AUD-002 — Network timeout and duplicate tap scenarios need explicit frame/variant IDs`

## New reusable state frames

Add:

| Frame ID | Name | Purpose |
|---|---|---|
| `CP-STATE-01` | Network Timeout / Checking Latest Status | Used when a request times out but final backend state is unknown |
| `CP-STATE-02` | Duplicate Tap / Action Already Processing | Used when user taps twice on idempotent action |
| `CP-STATE-03` | Disabled Action With Reason | Used when action is visible but not allowed by state/authorization |
| `CP-STATE-04` | Permission Denied | Used for ownership/RBAC denial |
| `CP-STATE-05` | Generic Loading / Processing | Used for long-running processing states |

## CP-STATE-01 — Network Timeout / Checking Latest Status

Visual content:

```text
We are checking the latest status.
Your request may still be processing.
Please wait or refresh safely.
```

Allowed CTAs:

```text
Refresh status
Return to dashboard
Contact support, for sensitive/payment cases
```

Forbidden:

```text
Assume success
Assume failure
Create duplicate booking/payment/refund/payout
```

Use in:

```text
booking hold
payment initiation
payment pending
refund submission
payout processing
operational incident
```

## CP-STATE-02 — Duplicate Tap / Action Already Processing

Visual content:

```text
This action is already being processed.
Please wait while we confirm the result.
```

Allowed CTAs:

```text
View current status
```

Forbidden:

```text
Create another booking
Start another payment
Submit another refund
Process payout again
```

Use in idempotent actions:

```text
POST /bookings/hold
POST /payments/initiate
POST /sessions/:id/review
refund commands
payout processing
```

## CP-STATE-03 — Disabled Action With Reason

Visual pattern:

```text
Disabled CTA
Reason text below action
```

Examples:

```text
Review disabled — Available after a verified completed session.
Pay disabled — Reservation expired.
Process payout disabled — Open dispute or refund exposure exists.
View Student Passport disabled — Parent permission required.
```

## CP-STATE-04 — Permission Denied

Visual content:

```text
You do not have access to this resource.
```

Rules:

- Do not reveal whether another user’s resource exists.
- Provide safe navigation back.

## CP-STATE-05 — Generic Loading / Processing

Use for:

```text
Reserving session
Starting payment
Submitting report
Submitting review
Processing refund
Processing payout
Opening secure access
```

---

# 5. Patch 3 — Updated Interaction Tables for Risky Branches

## Payment pending branch

Replace user-facing simulation labels with:

| Source frame | User-facing element | Destination behavior |
|---|---|---|
| `CP-P-13` | Refresh status | Facilitator routes to `CP-P-14`, `CP-P-15`, `CP-P-16`, or `CP-P-31` depending test scenario |
| `CP-P-13` | Return to dashboard | Navigate to `CP-P-02` |

Prototype facilitator controls live in:

```text
CP-TEST-00
```

## Refund outcome branch

Replace visible simulation outcome buttons with:

| Source frame | User-facing element | Destination behavior |
|---|---|---|
| `CP-P-23` | Refresh refund status | Facilitator routes to completed/failed/rejected/cancelled outcome |
| `CP-P-23` | Contact support | Support overlay |

Outcome branch controls remain prototype-only.

## Admin payout provider failure branch

Admin user-facing flow:

```text
Confirm process
→ Processing state
→ Paid or Failed result shown by prototype scenario
```

Do not show:

```text
Simulate provider payout failure
```

as a visible admin CTA.

## Operational incident branch

User-facing flow:

```text
Refresh status
→ Operational incident frame if issue persists
```

Do not show:

```text
Simulate verification issue
```

as a visible parent CTA.

---

# 6. Patch 4 — Frame ID Crosswalk

## Finding closed

`CP-AUD-003 — Frame naming crosswalk needed between low-fidelity and prototype IDs`

## Crosswalk table

| Clickable prototype frame | Low-fidelity screen(s) | High-fidelity design section |
|---|---|---|
| `CP-P-01` | P-01 Authentication / Login | P-01 |
| `CP-P-02` | P-02 Parent Dashboard | P-02 |
| `CP-P-03` | P-04 Create Student | P-04 |
| `CP-P-04` | P-05 Student Profile | P-05 |
| `CP-P-05` | P-06 Student Passport v0 | P-06 |
| `CP-P-06` | P-07 Student Data Sharing Permissions | P-07 |
| `CP-P-07` | P-08 Teacher Search | P-08 |
| `CP-P-08` | P-09 Matching Results | P-09 |
| `CP-P-09` | P-10 Teacher Trust Profile | P-10 |
| `CP-P-10` | P-11 Teacher Availability | P-11 |
| `CP-P-11` | P-12 Booking Hold | P-12 |
| `CP-P-12` | P-13 Checkout / Payment Initiation | P-13 |
| `CP-P-13` | P-14 Payment Pending | P-14 |
| `CP-P-14` | P-15 Payment Success | P-15 |
| `CP-P-15` | P-16 Payment Failure / Retry | P-16 |
| `CP-P-16` | P-14A / P-22A Late Payment After Expiry | P-14A / P-22A |
| `CP-P-17` | P-17 Booking Detail | P-17 |
| `CP-P-18` | P-18 Session Detail | P-18 |
| `CP-P-19` | P-19 Session Report | P-19 |
| `CP-P-20` | P-20 Review | P-20 |
| `CP-P-21` | P-23 Dispute create state | P-23 |
| `CP-P-22` | P-23 Dispute status state | P-23 |
| `CP-P-23` | P-22 Refund Timeline | P-22 |
| `CP-P-24` | P-26 Refund Completed | P-26 |
| `CP-P-25` | Refund Failed state from P-22 | P-22 / Refund failure variant |
| `CP-P-26` | P-24 Refund Rejected | P-24 |
| `CP-P-27` | P-25 Refund Cancelled | P-25 |
| `CP-P-28` | P-21 Payment / Invoice History | P-21 |
| `CP-P-29` | P-27 Notifications | P-27 |
| `CP-P-30` | P-28 Account / Security | P-28 |
| `CP-P-31` | P-15 operational incident variant | P-15 incident variant |

Teacher and Admin prototype frame IDs map one-to-one with their low-fidelity screen labels by screen name.

---

# 7. Updated Prototype Review Checklist

Before approving the clickable prototype, verify:

- [ ] No role-facing screen contains “Simulate ...” labels.
- [ ] All simulation controls are hidden or in `CP-TEST-00`.
- [ ] User-facing payment pending action is “Refresh status,” not “Simulate confirmed payment.”
- [ ] User-facing refund action is “Refresh refund status,” not “Simulate refund completed/failed/etc.”
- [ ] Provider failure branches are facilitator-controlled, not product CTAs.
- [ ] `CP-STATE-01` Network Timeout exists.
- [ ] `CP-STATE-02` Duplicate Tap exists.
- [ ] `CP-STATE-03` Disabled Action With Reason exists.
- [ ] `CP-STATE-04` Permission Denied exists.
- [ ] `CP-STATE-05` Generic Loading/Processing exists.
- [ ] Frame ID crosswalk is included in prototype handoff.
- [ ] No architecture/state-machine/API changes were introduced.
- [ ] Open policy placeholders remain unresolved.

---

# 8. Final Patch Status

All clickable prototype audit findings are addressed at specification level.

No architecture change was introduced.

No implementation was started.

```text
Clickable Prototype Patch v1.1: READY FOR FINAL AUDIT
```

Recommended next step:

```text
Clickable Prototype Final Audit
```

Do not proceed to implementation.
