# EduTrust Algeria — Clickable Prototype Audit v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Audited document:** `EduTrust_Clickable_Prototype_Specification_v1.0.md`  
**Audit type:** Prototype / interaction consistency audit  
**Architecture baseline:** LOCKED  
**Implementation status:** Not started  
**Audit status:** PASS WITH REQUIRED PATCHES

---

# 1. Executive Audit Decision

```text
Clickable Prototype Audit Status: PASS WITH REQUIRED PATCHES
```

The prototype specification is structurally strong and covers the required parent, teacher, and admin/OPS flows, including critical edge cases:

- Parent happy path
- Payment pending
- Payment failure
- Late payment after expiry
- Refund success/failure/rejected/cancelled
- Dispute
- No-show
- Payout blocked
- Payout failure
- Post-payout recovery
- Sensitive admin access
- Student data permissions
- Network timeout
- Duplicate tap
- Operational incident

However, the audit found one HIGH issue and two smaller issues that must be patched before the clickable prototype is considered approved for user testing or stakeholder review.

The architecture baseline remains locked. No architecture, database, API, or state-machine changes are required.

Frontend/backend implementation remains not approved.

---

# 2. Finding Classification Summary

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |
| OPEN POLICY | 1 |

---

# 3. Finding Table

| ID | Severity | Area | Finding | Patch required |
|---|---:|---|---|---|
| CP-AUD-001 | HIGH | CTA / action safety | Several prototype branch controls use visible labels such as “Simulate confirmed payment,” which could imply unauthorized user-triggered state changes if placed in role flows | Yes |
| CP-AUD-002 | MEDIUM | Error/network states | Network timeout and duplicate tap behavior are listed as scenarios but need explicit frame/variant IDs for the prototype | Yes |
| CP-AUD-003 | LOW | Frame naming | Clickable prototype frame IDs differ from low-fidelity screen IDs in a few places and need a crosswalk to avoid handoff confusion | Yes |
| CP-AUD-004 | OPEN POLICY | Product/ops policy | Ten policy decisions remain unresolved by design | No, keep placeholders |

---

# 4. Audit Findings

---

## CP-AUD-001 — Visible “Simulate …” labels could imply unauthorized state changes

**Severity:** HIGH

## Prototype frame(s)

Examples found in:

- `CP-P-13` Payment Pending
- `CP-P-23` Refund Timeline
- `CP-P-14` Payment Success / operational incident branch
- `CP-A-15` Payout Processing
- Admin refund and payout branch interactions

## Exact issue

The prototype interaction tables include visible labels such as:

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

These are useful for prototype testing, but if implemented as visible role-facing UI labels, they could imply that users can trigger backend/provider/system state transitions.

For example, a parent must not appear able to click:

```text
Simulate confirmed payment
```

because payment confirmation is provider/system authority, not parent authority.

## Violated baseline/rule

Approved rules:

- Every CTA must map to approved backend authority.
- Parent cannot confirm payment.
- Parent cannot force booking confirmation.
- Provider/system drives webhook result.
- Admin/OPS cannot bypass state machines.

## Why it matters

Clickable prototypes are often tested by non-technical stakeholders. If test-only controls appear as user-facing UI, the prototype may teach the wrong product behavior and later leak into implementation.

This is especially dangerous for:

- payment confirmation,
- late payment branch,
- refund lifecycle,
- payout provider failure,
- operational incident handling.

## Required correction

Move all simulation controls into one of these safe patterns:

### Option A — Prototype-only facilitator controls

Create a separate non-user-facing frame/page:

```text
CP-TEST-00 — Prototype Test Controls
```

with branch controls for testing.

These controls must be marked:

```text
Prototype facilitator only — not visible to users
```

### Option B — Hidden hotspots / keyboard shortcuts

Use hidden Figma hotspots for testers, not visible UI buttons.

### Option C — User-facing labels only for user actions

Replace visible user labels with legitimate user actions:

```text
Refresh status
View refund timeline
Contact support
Choose another slot
```

Backend-driven state changes can still be simulated in the prototype, but not as visible user authority.

## Whether architecture change is required

No.

## Whether prototype patch is required

Yes.

---

## CP-AUD-002 — Network timeout and duplicate tap scenarios need explicit frame/variant IDs

**Severity:** MEDIUM

## Prototype frame(s)

- Global scenario table
- Critical mutation flows:
  - booking hold
  - payment initiation
  - review submit
  - refund command
  - payout processing

## Exact issue

The specification includes scenarios for:

```text
Network timeout
Duplicate tap
```

but does not define explicit prototype frames or reusable variants for them.

It says expected behavior should be status refresh / replay-safe state, but designers need concrete frames/variants to wire into Figma.

## Violated baseline/rule

Approved UX requirements require the clickable prototype to demonstrate:

- loading
- network timeout
- duplicate tap behavior
- disabled action behavior
- status refresh behavior

## Why it matters

Duplicate taps and network timeouts are critical in booking/payment/refund/payout flows. If not prototyped, usability testing may miss whether users understand:

```text
Do not tap again
We are checking the latest status
No duplicate booking/payment/payout was created
```

## Required correction

Add reusable prototype frames/variants:

```text
CP-STATE-01 — Network Timeout / Checking Latest Status
CP-STATE-02 — Duplicate Tap / Action Already Processing
CP-STATE-03 — Disabled Action With Reason
```

Map them to critical flows:

- `POST /bookings/hold`
- `POST /payments/initiate`
- `POST /sessions/:id/review`
- refund commands
- payout processing

## Whether architecture change is required

No.

## Whether prototype patch is required

Yes.

---

## CP-AUD-003 — Frame naming crosswalk needed between low-fidelity and prototype IDs

**Severity:** LOW

## Prototype frame(s)

- Parent frames around payment/refund outcomes

## Exact issue

The clickable prototype uses its own frame IDs, for example:

```text
CP-P-15 = Payment Failure
CP-P-16 = Late Payment After Expiry
```

while low-fidelity screen IDs used:

```text
P-16 = Payment Failure / Retry
P-14A / P-22A = Late Payment After Expiry
```

This is not wrong, but it can cause handoff confusion.

## Violated baseline/rule

No business rule violation.

## Why it matters

Designers, reviewers, and engineers may cross-reference frame IDs during review. A crosswalk prevents miscommunication.

## Required correction

Add a frame ID crosswalk table:

```text
Clickable prototype frame → Low-fidelity screen(s) → High-fidelity screen(s)
```

## Whether architecture change is required

No.

## Whether prototype patch is required

Yes, minor documentation patch.

---

## CP-AUD-004 — Open policy decisions remain unresolved

**Severity:** OPEN POLICY

## Prototype frame(s)

Multiple.

## Exact issue

The ten operational/product policy decisions remain open:

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

## Violated baseline/rule

None. The baseline explicitly requires these to remain unresolved.

## Why it matters

The prototype can proceed with placeholders, but production copy and implementation cannot finalize these values.

## Required correction

No prototype correction required. Keep:

```text
[POLICY DECISION REQUIRED]
```

## Whether architecture change is required

No.

## Whether prototype patch is required

No.

---

# 5. Verification Areas

## 5.1 Parent happy path

**Result:** PASS

The prototype path is complete:

```text
Login
→ Dashboard
→ Create Student
→ Search
→ Matching Results
→ Trust Profile
→ Availability
→ Booking Hold
→ Checkout
→ Payment Pending
→ Payment Success
→ Session Detail
→ Session Report
→ Verified Review
```

Required patch: only ensure provider/system-driven transitions are not visible as user CTAs.

---

## 5.2 Parent payment/refund/dispute branches

**Result:** PASS WITH PATCH

Branches exist for:

- payment pending
- payment failure
- late payment
- refund success/failure/rejected/cancelled
- dispute

Patch required only for test-only simulation controls.

---

## 5.3 Late Payment After Expiry

**Result:** PASS WITH PATCH

The branch correctly shows:

```text
Payment received
Booking expired
No session
Refund/reconciliation started
```

Patch required: branch trigger must not appear as user-facing “Simulate late payment.”

---

## 5.4 Payment failure and retry eligibility

**Result:** PASS

Retry is allowed only when backend says booking is still payable/fulfillable.

No patch required beyond global simulation-control cleanup.

---

## 5.5 Operational incident handling

**Result:** PASS WITH PATCH

The operational incident branch exists and forbids retry payment/booking/session creation.

Patch required: “Simulate verification issue” must be test-only, not user-facing.

---

## 5.6 Student Data Sharing Permissions

**Result:** PASS

Grant/revoke/expired states are represented.

Teacher permission-scoped context is represented.

No architecture issue.

---

## 5.7 Teacher onboarding → session → report → payout

**Result:** PASS

Teacher path is coherent and respects teacher authority.

No teacher payment confirmation or payout processing authority appears.

---

## 5.8 Teacher student-context permissions

**Result:** PASS

Teacher context is permission-scoped and can show denied/expired states.

---

## 5.9 Admin verification and sensitive access

**Result:** PASS

Sensitive Access Modal exists and requires:

```text
This access will be logged.
Reason required.
```

---

## 5.10 Refund/reconciliation flow

**Result:** PASS WITH PATCH

Admin refund/reconciliation flow is structurally correct.

Patch required only to ensure test/prototype branch controls are not mistaken for production admin CTAs.

---

## 5.11 Payout processing/failure/recovery

**Result:** PASS WITH PATCH

Payout path exists and recovery remains separate/read-only.

Patch required for provider failure simulation control placement.

---

## 5.12 Event Ledger / Audit Trail

**Result:** PASS

Admin event/audit paths exist.

Sensitive event detail access is acknowledged.

---

## 5.13 RTL prototype variants

**Result:** PASS

Representative RTL frames are listed and rules are clear.

---

## 5.14 Loading/error/empty/permission states

**Result:** PASS WITH PATCH

Most states are covered. Add explicit frame/variant IDs for network timeout and duplicate tap.

---

## 5.15 Duplicate tap / network timeout behavior

**Result:** PASS WITH REQUIRED PATCH

Concept exists, but explicit prototype frames/variants are required.

---

## 5.16 Unauthorized CTA prevention

**Result:** PASS WITH REQUIRED PATCH

Business CTAs are generally safe, but visible “Simulate ...” labels must be moved to prototype-only controls.

---

## 5.17 Financial state semantics

**Result:** PASS

Refund states and payout states are semantically correct.

---

## 5.18 Paid payout immutability

**Result:** PASS

Paid payout remains unchanged and recovery appears separately.

---

## 5.19 Post-payout recovery separation

**Result:** PASS

Recovery is separate from historical paid payout.

---

## 5.20 MVP scope compliance

**Result:** PASS

No out-of-scope MVP features are introduced.

---

## 5.21 Open policy placeholders

**Result:** PASS / OPEN POLICY

Placeholders remain unresolved correctly.

---

# 6. Required Patch

Because findings exist, the required patch document is:

```text
EduTrust_Clickable_Prototype_Patch_v1.1.md
```

The patch must address:

1. Move/mark all simulation controls as prototype-only and non-user-facing.
2. Add explicit frame/variant IDs for network timeout, duplicate tap, and disabled action with reason.
3. Add frame ID crosswalk table.

No architecture change is required.

---

# 7. Implementation Restriction

Do not proceed to implementation.

Still prohibited:

- frontend implementation
- backend implementation
- production UI code
- database changes
- API changes
- state-machine changes
- UX business logic changes
- MVP expansion

---

# 8. Final Status

```text
Clickable Prototype Audit Status: PASS WITH REQUIRED PATCHES
```

Required next document:

```text
EduTrust_Clickable_Prototype_Patch_v1.1.md
```
