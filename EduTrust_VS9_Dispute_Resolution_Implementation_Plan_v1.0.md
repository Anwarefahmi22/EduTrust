# EduTrust — VS9 Dispute Resolution Implementation Plan v1.0

**Document type:** Implementation plan (PLANNING ONLY — no implementation performed)
**Slice:** DEV Vertical Slice #9 — Dispute Resolution (CORE scope, Option B)
**Audited lineage:** `b245aae → 83c7bc5 → e0e3d89 → 157a54d → b73d8ce (VS8, now pushed)`
**Verified at planning time:** 160/160 tests PASS (fresh isolated PG 16.2, 330.79s) · 53/53 VS8 E2E PASS (re-run) · 32/32 direct-SQL VS8 financial checks PASS · migrations byte-identical · deps unchanged · no CRITICAL/HIGH findings
**Classification legend:** `AUTHORITATIVE` (approved document) · `INFERRED` (derived, flagged) · `UNKNOWN` (preserved; decision required) · `CONFLICTING` (document conflict, precedence applied) · `CONTRACT GAP` (approved spec incomplete; plan-time governance item)

---

# 1. Executive summary

VS9 implements the **dispute resolution core** on the existing approved baseline with **no schema, state-machine, architecture, or dependency changes**:

- `POST /api/v1/admin/disputes/:id/resolve` (OPS/ADMIN; SAFETY disputes ADMIN-only) — the approved contract from API §19.4 — resolves a dispute (OPEN or UNDER_REVIEW) to RESOLVED with one of the **nine contract-expressible actions** (NO_ACTION, WARNING, FULL_REFUND, PARTIAL_REFUND, PAYOUT_BLOCKED, PAYOUT_RELEASED, TEACHER_NO_SHOW_CONFIRMED, STUDENT_NO_SHOW_CONFIRMED, REPORT_CORRECTION_REQUIRED).
- `GET /api/v1/admin/disputes` — the approved admin monitoring list (API §21.3).
- Refund actions (FULL_REFUND / PARTIAL_REFUND) **call the VS8 refund service** (AUTHORITATIVE: §19.4 "Refund action must call refund service and create ledger/event entries") by creating the linked `REQUESTED` refund inside the resolve transaction; the operator then completes it through the **existing VS8 endpoints** (approve with actor-supplied allocation → mock provider result or reconciliation). No new refund behavior is invented.
- Payout blocking/release needs **no new mechanism**: the existing v1 DB trigger + VS5 service checks react to dispute status (AUTHORITATIVE: v1 `validate_payout_item_eligibility`; SM §13.5).
- **Explicitly excluded** (documented gaps, preserved as UNKNOWN/CONTRACT GAP — not invented): the two account actions (ACCOUNT_SUSPENSION_RECOMMENDED / ACCOUNT_SUSPENDED — R10 operational spec is UNKNOWN), the REJECTED and CANCELLED outcomes and the UNDER_REVIEW assignment mechanism (SM §11.3 names them but API §19.4's request cannot express them without invented fields), and all suspension effects (login/hiding/payout/booking/refund — UNKNOWN).

Scope-readiness: **VS9_SCOPE_READY = YES** for the CORE scope above, subject to the plan-time governance items in §29 (none blocks scope definition; P1 — the refund allocation input path — must be decided before coding the refund actions).

# 2. Scope

| # | In scope | Source |
|---|---|---|
| S1 | `POST /admin/disputes/:id/resolve` — RESOLVED outcome, 9 actions, OPS/ADMIN (SAFETY→ADMIN), idempotency required | API §19.4; SM §11.3 (RESOLVED row), §11.4 (actions), §11.7 (audit) |
| S2 | Refund actions call the VS8 refund service: dispute-linked refund created `REQUESTED` in the resolve transaction; completion via existing VS8 endpoints | API §19.4; VS8 approved service (b73d8ce) |
| S3 | `GET /admin/disputes` — admin monitoring list with status/category/priority filters | API §21.3 |
| S4 | Payout block/release semantics via existing dispute-status reactivity (no new mechanism) | v1 trigger; VS5 service check; SM §13.5 |
| S5 | Audit: `DISPUTE_RESOLVED` + `ADMIN_ACTION` (+ refund lifecycle events via VS8) | SM §11.7; API §19.1; Addendum §13 |
| S6 | DEV console: admin dispute list/detail/resolve; parent/teacher own-dispute detail | UX Flows (5.7, patch 1); DEV-console convention (VS1–VS8) |
| S7 | Test matrix (§22) + E2E suite (§23) + financial-integrity gates | Traceability Matrix; VS8 E2E convention |

# 3. Explicit exclusions (with source for each)

| # | Excluded | Source / reason |
|---|---|---|
| X1 | `ACCOUNT_SUSPENSION_RECOMMENDED`, `ACCOUNT_SUSPENDED` actions | R10 operational spec UNKNOWN (no effects/state-machine/auth behavior specified — Phase 10 investigation); §21.6 is endpoint-only. Decision P6 |
| X2 | `REJECTED` outcome | CONFLICTING/CONTRACT GAP: SM §11.3 assigns it to "Admin resolve endpoint" but §19.4's request (`{resolution, action, refund_amount, account_action}`) has no reject semantics; no REJECT action in the §11.4 list. Decision P5 |
| X3 | `CANCELLED` outcome | CONTRACT GAP: SM §11.3 "Cancel endpoint/admin action" — no cancel endpoint in §19.1's approved four. Decision P5 |
| X4 | `OPEN → UNDER_REVIEW` assignment mechanism | CONTRACT GAP: SM §11.3 "Admin review action / Dispute assigned" — no endpoint contract in §19.1. The RESOLVED path is reachable directly from OPEN (§11.3 row), so the core flow does not require UNDER_REVIEW. Decision P5 |
| X5 | All suspension effects (login block, content hiding, payout/booking/refund effects, reactivation effects) | UNKNOWN — no document specifies them; not invented |
| X6 | Real provider integration, real money, real payout | Gate: REAL REFUND/PAYMENT/PAYOUT FORBIDDEN (Feature Flag Governance; Payment Provider Gate Assessment) |
| X7 | Production 64-screen UI (incl. A-63 User Suspension screen) | R17 phase — not a slice; DEV console only (established convention) |
| X8 | `evidence[]` persistence (API §19.3 field) | CONTRACT GAP: no column in the approved `disputes` table; VS4 already ignores the field. Decision P7 (keep VS4 behavior: accept-and-ignore, documented) |
| X9 | Dispute window enforcement (when a parent may dispute a completed session) | OPS-POL-005 OPEN (unset behavior: payout eligibility stays blocked or manual OPS release — already satisfied by the existing trigger); window itself not implemented (VS4 behavior preserved) |
| X10 | New ledger accounts/entries for dispute resolution itself | None authorized — all financial effects flow through VS8 refund ledger forms (§15) |
| X11 | VS10+ work (cancellation/reschedule, R10, R11, etc.) | Out of slice |

# 4. Source authority (applied precedence)

Per Implementation Baseline v1.0 (statuses) + SM v1.1 Addendum §2 (conflict order: Addendum > Schema v1.1 > SM v1.0 > API Arch > DB Schema v1.0 > PRD):

| Source | Version | Status (Baseline) | Role in VS9 |
|---|---|---|---|
| State Machines v1.1 Addendum | v1.1 | APPROVED | Wins on conflict; overlay model (§4.1) governs dispute effects; refund event semantics (§7/§13) |
| State Machines v1.0 §11, §13.5, §18.2 | v1.0 | APPROVED | Dispute state machine, actions, effects, forbidden transitions, audit; payout-blocking map; ADMIN-only override list |
| API Architecture v1.0 §19, §21.3, §4.1, role matrix | v1.0 | APPROVED | Endpoint contracts, roles, admin catalogue |
| API Contract Addendum v1.1 | v1.1 | APPROVED WITH CONDITIONS | Refund-read surfaces (linked_refunds — already in VS8); the only vehicle for future contract additions (OpenAPI condition pending) |
| PostgreSQL schema v1→v1.4 (migrations 001–005) | — | APPROVED (v1.2 CONDITIONAL-provenance) | `disputes` table, enums, payout-blocking trigger, refund/payout objects |
| PRD v1.0 §10.4, §17, KPIs | v1.0 | APPROVED | P1 dispute management; dispute flow v0; dispute-rate KPI |
| UX Flows v1.0 + v1.1 Patch (APPROVED) | — | APPROVED | Dispute-as-overlay UX (2.4); 5.7 dispute open; refund timeline visibility in dispute detail |
| Product/Ops Policy Decisions v1.0 | v1.0 | READY FOR REVIEW (10 policies OPEN) | OPS-POL-005 dispute window (OPEN — not implemented, X9) |
| Engineering Governance v1.0 | v1.0 | APPROVED WITH CONDITIONS | §5 financial-workflow change approval (governs VS9's final gate); §7 gate ownership |
| Security/Privacy Plan | v1.0 | APPROVED WITH CONDITIONS | §9 "Must audit: … admin user suspension, … admin overrides" — admin overrides audited (VS9 resolve = admin override-class action) |
| Test Traceability Matrix | v1.0 | APPROVED | "Dispute blocks payout" row (already green via VS4/VS5); refund rows (green via VS8) |
| VS4 implementation report + tests | — | evidence | Dispute foundation (open/read/duplicate/audit/overlay); no mutation path (verified by test) |
| VS8 implementation plan/report + code | — | evidence | The refund service VS9 will call (verified in b73d8ce) |
| Post-VS8 Final Audit & Roadmap v1.0 | — | current roadmap | Supersedes Post-VS6 roadmap sections |

**Known conflicts resolved by precedence (none affect VS9 core beyond the documented ones):** API §12.6 `REFUND_ISSUED` line vs Addendum §13.2 (Addendum wins — VS8 emits no REFUND_ISSUED); SM v1.0 §16.2 booking→DISPUTED vs Addendum §4.1 overlay (Addendum wins — v1.1 DB CHECK enforces; VS9 never sets booking/session DISPUTED).

# 5. Traceability matrix (dispute domain — full)

| ID | Requirement | Source | Section | Authority | API | State | DB | Service | Event | Ledger | Authorization | Test (existing / planned) | E2E | Frontend | Status | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TR-01 | Open dispute (participant; 1+ target; category; SAFETY→priority 1; duplicate protection; overlay-only) | SM §11.3 row 1; API §19.3; PRD §17 | 19.3/11.3 | AUTHORITATIVE | `POST /disputes` | → OPEN | disputes insert | `open_dispute` (VS4) | `DISPUTE_OPENED` | none | PARENT/TEACHER participant; OPS/ADMIN may open (role matrix "Open dispute: Yes") | existing: 11 VS4 dispute tests | VS4 E2E (report-only) | parent/teacher console (VS4) | IMPLEMENTED | AUTHORITATIVE |
| TR-02 | List scoped disputes | API §19.1 | 19.1 | AUTHORITATIVE | `GET /disputes` | — | — | `list_disputes_for_user` (VS4) | none | none | participant scope; OPS/ADMIN all | existing: read tests | VS4 E2E | console | IMPLEMENTED | AUTHORITATIVE |
| TR-03 | View scoped dispute | API §19.1 | 19.1 | AUTHORITATIVE | `GET /disputes/:id` | — | — | `get_dispute_for_user` (VS4) | admin reads audited | none | participant/OPS/ADMIN | existing: read tests + audit test | VS4 E2E | console | IMPLEMENTED | AUTHORITATIVE |
| TR-04 | Linked refund summaries in dispute detail | Addendum-era UX patch 1; implemented in VS8 | UX patch 1 | AUTHORITATIVE | `GET /disputes/:id` field | — | — | VS8 `linked_refunds[]` | — | — | as dispute read | existing: VS8 tests | VS8 E2E | console | IMPLEMENTED (VS8) | AUTHORITATIVE |
| TR-05 | Resolve dispute → RESOLVED with action; resolution/resolved_at/resolver recorded | SM §11.3 row 3; §11.7; API §19.4 | 11.3/11.7/19.4 | AUTHORITATIVE | `POST /admin/disputes/:id/resolve` | OPEN/UNDER_REVIEW → RESOLVED | resolution, resolved_at, assigned_admin_user_id | NEW `resolve_dispute` (VS9) | `DISPUTE_RESOLVED` + `ADMIN_ACTION` | only via refund actions (TR-06) | OPS policy-limited; ADMIN for safety/exceptional/override (§19.4) | planned: VS9 test matrix §22 | planned: E2E S1 | admin console (VS9) | SPEC_ONLY | AUTHORITATIVE |
| TR-06 | FULL_REFUND action calls refund service + ledger/event entries | SM §11.4/§11.5; API §19.4 | 11.4/19.4 | AUTHORITATIVE | resolve request `action=FULL_REFUND`, `refund_amount` | refund → REQUESTED (then VS8 lifecycle) | refunds row (dispute_id linked) | NEW: calls VS8 `create_refund`; completion via VS8 `approve_refund`/`process_mock_refund_result`/`reconcile_refund` | `REFUND_REQUESTED` (+VS8 lifecycle events) | VS8 refund tx forms L/D/A | OPS/ADMIN (§19.4; §18.2: full refund after completed session = ADMIN override class) | planned | E2E S4 | admin console | SPEC_ONLY | AUTHORITATIVE (integration via VS8 approved service) |
| TR-07 | PARTIAL_REFUND action (same mechanics; amount < payment) | SM §11.4/§11.5; API §19.4; Addendum §10 (exposure) | 11.4/19.4 | AUTHORITATIVE | as TR-06 with `refund_amount` < payment | as TR-06 (PARTIAL) | as TR-06 | as TR-06 | as TR-06 | as TR-06; payout exposure from approval (Addendum §10.1) | as TR-06 | planned | E2E S5 | admin console | SPEC_ONLY | AUTHORITATIVE |
| TR-08 | NO_ACTION / WARNING / REPORT_CORRECTION_REQUIRED | SM §11.4 | 11.4 | AUTHORITATIVE (names) / INFERRED (effect = resolution record only) | resolve request action | → RESOLVED | resolution text | `resolve_dispute` | `DISPUTE_RESOLVED` + `ADMIN_ACTION` | none (no money movement specified) | OPS/ADMIN | planned | E2E S1 (NO_ACTION) | admin console | SPEC_ONLY | AUTHORITATIVE names; REPORT_CORRECTION_REQUIRED effect = decision P2 (record-only default) |
| TR-09 | TEACHER_NO_SHOW_CONFIRMED / STUDENT_NO_SHOW_CONFIRMED | SM §11.4 + §11.5 rows; SM §8 (no-show transitions exist) | 11.4/11.5 | AUTHORITATIVE | resolve request action | session → NO_SHOW_TEACHER/NO_SHOW_STUDENT **only if session is SCHEDULED** (existing VS3 no-show authority); no session state change if already terminal | — | `resolve_dispute` calls the existing session no-show path (server-derived) | existing `SESSION_NO_SHOW` (VS3) | none | OPS/ADMIN | planned | E2E (no-show confirmation) | admin console | SPEC_ONLY | AUTHORITATIVE (effect target exists; plan decision: apply only when session still SCHEDULED — the only state VS3's no-show transition allows) |
| TR-10 | PAYOUT_BLOCKED / PAYOUT_RELEASED actions | SM §11.4; §13.5; v1 trigger | 11.4/13.5 | AUTHORITATIVE (names) / INFERRED (mechanism = dispute-status reactivity; no independent financial effect specified) | resolve request action | dispute status drives block/release; RESOLVED/REJECTED unblocks by status | v1 `validate_payout_item_eligibility` (existing) | `resolve_dispute` (records action; no payout mutation) | `DISPUTE_RESOLVED` + `ADMIN_ACTION` | none at action time (payout ledger entries occur at payout time) | OPS/ADMIN | planned (block-before/after) | E2E S6/S7 | admin console | SPEC_ONLY | INFERRED mechanism (no document specifies an independent block/release operation — the trigger is the approved mechanism) |
| TR-11 | REJECTED outcome | SM §11.3 row 4 | 11.3 | CONFLICTING (SM says "Admin resolve endpoint"; §19.4 request cannot express it) | not expressible in §19.4 contract | OPEN/UNDER_REVIEW → REJECTED | columns exist | — | `DISPUTE_RESOLVED` or `ADMIN_ACTION` (§11.3) | may unblock payout | OPS/ADMIN | — | — | — | CONTRACT GAP | Decision P5 (deferred) |
| TR-12 | CANCELLED outcome (opener or admin; safety exception) | SM §11.3 row 5 | 11.3 | CONTRACT GAP (no endpoint contract) | not in §19.1 | OPEN → CANCELLED | columns exist | — | `ADMIN_ACTION`/metadata | may unblock payout | Opener or Admin (safety rules) | — | — | — | CONTRACT GAP | Decision P5 (deferred) |
| TR-13 | OPEN → UNDER_REVIEW (assignment) | SM §11.3 row 2 | 11.3 | CONTRACT GAP (no endpoint contract) | not in §19.1 | OPEN → UNDER_REVIEW | assigned_admin_user_id exists | — | `ADMIN_ACTION` | — | OPS/ADMIN | — | — | — | CONTRACT GAP | Decision P5 (deferred; core resolves directly from OPEN) |
| TR-14 | ACCOUNT_SUSPENSION_RECOMMENDED / ACCOUNT_SUSPENDED | SM §11.4; API §21.6 (endpoint-only); SM §18.2 (ADMIN-only override) | 11.4/21.6/18.2 | AUTHORITATIVE (names/endpoint) / UNKNOWN (operational effects) | §21.6 endpoints (not in VS9) | — | user_status enum exists | — | — | — | ADMIN only (matrix + §18.2) | — | — | — | UNKNOWN (effects) | Decision P6 (R10 workstream) |
| TR-15 | Payout blocked while dispute OPEN/UNDER_REVIEW | v1 trigger; SM §13.5; Traceability | v1/13.5 | AUTHORITATIVE | — (DB + service) | — | trigger + VS5 service check | existing (VS4/VS5) | — | — | — | existing: `test_open_dispute_blocks_payout_item_at_database_level` + VS5 tests | VS5 E2E (report-only) | — | IMPLEMENTED | AUTHORITATIVE |
| TR-16 | Dispute overlay: booking/session factual state never DISPUTED | Addendum §4.1; v1.1 CHECKs | 4.1 | AUTHORITATIVE | — | — | v1.1 CHECK constraints | enforced by DB | — | — | — | existing: VS4 overlay test | VS4 E2E | — | IMPLEMENTED | AUTHORITATIVE |
| TR-17 | Safety dispute priority 1 | SM §11.2; API §19.3 | 11.2/19.3 | AUTHORITATIVE | create | — | priority column | VS4 (server-derived) | — | — | — | existing: `test_dispute_safety_priority_and_teacher_open` | — | — | IMPLEMENTED | AUTHORITATIVE |
| TR-18 | Duplicate dispute protection (service-level) | VS4 report decision (approved slice convention) | VS4 report | AUTHORITATIVE (slice decision) | create | — | — | VS4 (booking-row-serialized) | — | — | — | existing: duplicate + concurrency tests | VS4 E2E | — | IMPLEMENTED | AUTHORITATIVE |
| TR-19 | Audit: resolution + resolved_at + resolver + admin action event + refund/account references | SM §11.7 | 11.7 | AUTHORITATIVE | resolve | — | columns | VS9 `resolve_dispute` | `ADMIN_ACTION` (metadata: action, refund_id) | — | OPS/ADMIN | planned | E2E S13 | admin console | SPEC_ONLY | AUTHORITATIVE |
| TR-20 | Admin dispute monitoring list | API §21.3 (incl. SUPPORT role nuance) | 21.3 | AUTHORITATIVE | `GET /admin/disputes` | — | — | NEW `list_admin_disputes` (VS9) | sensitive reads audited | — | SUPPORT/OPS/ADMIN per §21.3 (role nuance = decision P3) | planned | E2E (read) | admin console | SPEC_ONLY | AUTHORITATIVE (role nuance flagged) |
| TR-21 | `evidence[]` on create | API §19.3 | 19.3 | CONTRACT GAP (no column; VS4 ignores) | create | — | — | VS4 (ignored) | — | — | — | — | — | — | CONTRACT GAP | Decision P7 |

# 6. Endpoint inventory

| # | Endpoint | Approved source | Current state | VS9 action |
|---|---|---|---|---|
| E1 | `POST /api/v1/disputes` | API §19.3 | EXISTS (VS4) | unchanged |
| E2 | `GET /api/v1/disputes` | API §19.1 | EXISTS (VS4) | unchanged |
| E3 | `GET /api/v1/disputes/:id` | API §19.1 + UX patch 1 | EXISTS (VS4 + VS8 `linked_refunds[]`) | unchanged |
| E4 | `POST /api/v1/admin/disputes/:id/resolve` | API §19.4 | **MISSING** | **NEW (VS9)** — the core endpoint |
| E5 | `GET /api/v1/admin/disputes` | API §21.3 | **MISSING as a route** (admin view currently via E2 with role scoping) | **NEW (VS9)** — decision P3 (dedicated route + filters; SUPPORT nuance) |
| E6 | VS8 refund endpoints (create/approve/reject/cancel/mock×2/reconcile/reads) | API §12.6 + Addendum §7 | EXISTS (VS8) | **reused, unchanged** |
| E7 | `POST /admin/users/:id/suspend|reactivate` | API §21.6 | MISSING | **EXCLUDED (X1/P6)** |
| E8 | dispute cancel / reject / review-assign endpoints | not in §19.1 | — | **EXCLUDED (X2–X4/P5)** — no contract exists; not invented |

No endpoint is invented. E4/E5 are the only additions, both present in approved contracts.

# 7. Request/response contracts (E4 resolve + E5 list)

**E4 request (approved shape — API §19.4, verbatim fields):**

```json
{
  "resolution": "Partial refund approved due to shortened session.",
  "action": "PARTIAL_REFUND",
  "refund_amount": "1000.00",
  "account_action": null
}
```

Server-side interpretation (every rule cited; nothing invented):
- `resolution`: required non-empty string (≥3 chars, per project validation convention — INFERRED-minor, same convention as VS4 dispute description/VS8 reasons); stored in `disputes.resolution` (SM §11.7 "resolution").
- `action`: required; must be one of the **nine** scope actions (§3 X1/X2/X3 exclusions enforced as `VALIDATION_ERROR` with the approved action list for this slice). `FULL_REFUND`/`PARTIAL_REFUND` require `refund_amount`; all others require `refund_amount` absent or null (fail-fast; INFERRED-minor strictness consistent with VS5's strict body handling).
- `refund_amount`: required for refund actions; positive decimal string, `DZD` implied by schema (currency column fixed DZD — AUTHORITATIVE); for FULL_REFUND must equal the linked payment amount (VS8/SM §14.2 type rule applied at request time — INFERRED-minor fail-fast); for PARTIAL_REFUND must be < payment amount (same rule).
- `account_action`: accepted (field exists in the approved contract); in VS9 **must be null** (account actions excluded — X1). Non-null → `VALIDATION_ERROR` (documented limitation, decision P6). UNKNOWN value semantics preserved — not interpreted.
- **Allocation is NOT in the approved request** — the operator supplies the teacher/platform split at the VS8 approve step (decision P1, default option (i) two-step).

**E4 response (INFERRED from the project's standard envelope convention — §5.2; no approved response schema exists for §19.4 — flagged, not invented):**

```json
{
  "data": {
    "dispute": { "…dispute row incl. status=RESOLVED, resolution, resolved_at…", "linked_refunds": [ … ] },
    "refund": { "refund_id": "…", "status": "REQUESTED" }   // present only for refund actions
  },
  "request_id": "…"
}
```

Status 200. (The dispute detail shape reuses the existing VS4/VS8 read serializer — no new fields.)

**E5 list response:** standard list envelope `{"data": […], "pagination": {limit, next_cursor, has_more}, "request_id"}` — INFERRED from the established list convention (VS8 admin lists). Item fields = dispute row (id, category, status, priority, description, booking/session/payment refs, opened_by, assigned_admin_user_id, resolution, resolved_at, timestamps) — no new fields. Filters: `status`, `category`, `priority`, `from`, `to`, `limit`, `cursor` (same allowlist convention as VS8 `GET /admin/refunds`). The UX-patch `resolution_action` filter is **not supported** (no action column in the approved schema — CONTRACT GAP noted; decision P3).

# 8. Error catalogue (E4/E5 — derived from the established convention; no new categories invented)

| Code | HTTP | When | Source of convention |
|---|---|---|---|
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | missing key on E4 | VS5/VS6/VS8 idempotency helper (API §24) |
| `IDEMPOTENCY_KEY_CONFLICT` | 409 | same key, different body | same |
| `IDEMPOTENCY_REQUEST_PROCESSING` | 409 | same key in-flight | same |
| `VALIDATION_ERROR` | 400 | bad action (incl. excluded actions), missing/short resolution, missing/invalid refund_amount, FULL amount ≠ payment, PARTIAL ≥ payment, non-null account_action | project validation convention |
| `RESOURCE_NOT_FOUND` | 404 | unknown dispute id | project convention |
| `FORBIDDEN` | 403 | non-OPS/ADMIN actor; OPS on SAFETY dispute; OPS on "exceptional" refund (P4 policy detail) | API §19.4 rules; §11.6; role matrix |
| `DISPUTE_INVALID_STATE` | 409 | dispute not OPEN/UNDER_REVIEW (terminal) — "terminal states cannot be reopened" (SM §11.6 + §11.3; same naming style as VS8 `REFUND_INVALID_STATE`) | SM §11.6 |
| `OVER_REFUND` | 409 | refund action would exceed the payment's refundable bound | VS8 (Addendum §15.4) |
| `REFUND_INVALID_STATE` / `PAYMENT_PROVIDER_*` | 409 | propagated from the VS8 refund service when the linked refund cannot be created | VS8 catalogue |
| `DUPLICATE_DISPUTE` | 409 | (existing, E1 only) | VS4 |

# 9. State machine (dispute — as implemented in VS9)

States (schema `dispute_status`, unchanged): `OPEN, UNDER_REVIEW, RESOLVED, REJECTED, CANCELLED`.

VS9 implements the RESOLVED path only (TR-05–TR-10); REJECTED/CANCELLED/UNDER_REVIEW mechanisms are contract gaps (X2–X4). Terminality: RESOLVED/REJECTED/CANCELLED are terminal (SM §11.6 "do not reopen silently"; enforced by service state check — there is **no** dispute transition DB trigger in the approved schema, so service enforcement is the approved mechanism, consistent with VS4's service-level dispute invariants).

Payment/refund/payout interactions per §11.5 (AUTHORITATIVE), implemented as:
- Resolution with FULL_REFUND/PARTIAL_REFUND: refund created REQUESTED (payment still CONFIRMED/DISPUTED) → on later VS8 approval payment → REFUND_PENDING → on success REFUNDED/PARTIALLY_REFUNDED (VS8 semantics).
- No-show confirmations: session → NO_SHOW_* only when SCHEDULED (VS3 authority), otherwise no state change (documented plan decision; the §11.5 row says session "NO_SHOW_TEACHER" — applying it to a non-SCHEDULED session has no approved VS3 transition, so the action is recorded in the resolution and no session mutation occurs — INFERRED, flagged).
- PAYOUT_BLOCKED/RELEASED: no independent mechanism — status reactivity (TR-10).
- Overlay invariants: booking/session status never touched by VS9 (Addendum §4.1; v1.1 CHECKs).

# 10. Transition table (implemented in VS9)

| From | To | Actor | Preconditions | DB writes | Side effects | Events | Idempotency | Locking | Source |
|---|---|---|---|---|---|---|---|---|---|
| OPEN | RESOLVED | OPS/ADMIN (SAFETY→ADMIN) | dispute OPEN; action ∈ 9 scope actions; resolution ≥3 chars; refund actions: refund_amount valid + within bound; account_action null | `resolution`, `resolved_at`, `assigned_admin_user_id` (resolver) | refund actions: refund row REQUESTED (dispute-linked) via VS8 `create_refund` | `DISPUTE_RESOLVED` + `ADMIN_ACTION` (+ `REFUND_REQUESTED` via VS8) | required (scope `dispute_resolve`) | dispute `FOR UPDATE` first; refund creation locks payment→refund (VS8 order) — global order dispute→payment→refund→booking, acyclic | SM §11.3 row 3; API §19.4; §11.7 |
| UNDER_REVIEW | RESOLVED | same | same, dispute UNDER_REVIEW | same | same | same | same | same | SM §11.3 row 3 (from set includes UNDER_REVIEW) |
| OPEN/UNDER_REVIEW | (terminal re-entry) | any | — | — | 409 `DISPUTE_INVALID_STATE` | none | — | — | SM §11.6 |

No other transitions implemented. No reopen, no silent state change, no client-supplied status (all state writes server-derived from the validated action).

# 11. Authorization matrix (VS9 surface)

Sources: API §19.1/§19.4/role matrix/§4.1; SM §11.3/§11.6/§18.2; VS4/VS8 implemented role checks.

| Operation | anonymous | student* | teacher | parent | support | ops | admin |
|---|---|---|---|---|---|---|---|
| Read dispute (own/participant) | DENY (401) | n/a | ALLOW (own, VS4) | ALLOW (own, VS4) | CONDITIONAL (VS4: not granted; §21.3 lists SUPPORT for the admin list — P3) | ALLOW (all, VS4) | ALLOW (all, VS4; audited) |
| Create dispute | DENY | n/a | ALLOW (own, VS4) | ALLOW (own, VS4) | DENY (role matrix "Assist only") | ALLOW | ALLOW |
| View foreign dispute | DENY | n/a | DENY | DENY | CONDITIONAL (P3) | ALLOW | ALLOW (audited) |
| Review/assign (UNDER_REVIEW) | DENY | n/a | DENY | DENY | DENY | SPEC ONLY (P5) | SPEC ONLY (P5) |
| Resolve dispute (non-SAFETY, non-refund actions) | DENY | n/a | DENY | DENY | DENY (§11.6) | ALLOW (policy-limited, §19.4) | ALLOW |
| Resolve dispute — SAFETY category | DENY | n/a | DENY | DENY | DENY | DENY (ADMIN required, §19.4) | ALLOW |
| Resolve — FULL_REFUND / PARTIAL_REFUND | DENY | n/a | DENY | DENY | DENY | CONDITIONAL (OPS "within policy" — P4 detail; §18.2: "Full refund after completed session" is ADMIN-override class — plan lock: OPS may resolve refund actions on non-SAFETY disputes; ADMIN for SAFETY and for full refund of a COMPLETED session per §18.2) | ALLOW |
| Approve refund (with allocation) | DENY | n/a | DENY | DENY | DENY | ALLOW (VS8, policy-limited) | ALLOW |
| Reject / cancel refund | DENY | n/a | DENY | DENY | DENY | ALLOW (VS8) | ALLOW |
| Block payout (action) | DENY | n/a | DENY | DENY | DENY | ALLOW (action = resolution record; mechanism = status trigger) | ALLOW |
| Release payout (action) | same | same | same | same | DENY | ALLOW | ALLOW |
| Suspend user | DENY | n/a | DENY | DENY | DENY | DENY (matrix "No") | SPEC ONLY (P6/R10 — excluded) |

\* "student" has no user account in this system (students are profiles under a parent) — the column is n/a by architecture (AUTHORITATIVE: schema/users model).

Self-action boundaries (server-derived): a teacher can never resolve (role-gated); a parent's dispute can only be resolved by OPS/ADMIN; refund amounts come from the operator's request and are validated against the payment (a client cannot inflate via any other field — `requested_amount` is server-set from `refund_amount` with the FULL/PARTIAL bounds); ledger accounts are never client-selectable (VS8 service computes the form); payout release cannot be forced (status-driven trigger).

# 12. Service architecture

New code (all additive, following the VS5/VS8 function patterns; no existing function modified):

```text
services.py (VS9 section):
  DISPUTE_RESOLVE_ACTIONS = {9 scope actions}
  _dispute_resolve_row_for_update(dispute_id) -> dict      # FOR UPDATE
  _linked_payment_for_dispute(dispute) -> dict | None      # payment via dispute.payment_id or booking's confirmed payment
  resolve_dispute(user_id, roles, dispute_id, data, idempotency_key, request_id) -> dict
  list_admin_disputes(user_id, roles, params, request_id) -> dict
views.py:
  admin_disputes_resolve(request, dispute_id)   @require_roles("OPS","ADMIN")
  admin_disputes(request)                       @require_roles("SUPPORT","OPS","ADMIN")  (P3 role nuance; audited)
urls.py:
  admin/disputes/<uuid:dispute_id>/resolve      -> admin_disputes_resolve
  admin/disputes                                -> admin_disputes
```

`resolve_dispute` algorithm (single transaction, VS8-style):
1. Role/SAFETY check (ADMIN-only for SAFETY category; P4 policy locks for "exceptional refund").
2. Validate body (§7 rules).
3. `with tx():`
   a. `_idempotency_begin("dispute_resolve", user, key, sha256(canonical), path)` — replay → return stored body; conflict → 409.
   b. Lock dispute row `FOR UPDATE`; verify state ∈ {OPEN, UNDER_REVIEW} else 409.
   c. If refund action: identify the payment (dispute.payment_id else the booking's confirmed payment — the VS4 dispute always carries a derived booking_id); call the **existing VS8 `create_refund`** (nested savepoint) with `amount=refund_amount`, `reason=<resolution-derived per §7>`, `dispute_id=<id>`; propagate its errors (OVER_REFUND etc.) → full rollback.
   d. No-show confirmations: if session SCHEDULED, reuse the existing VS3 no-show service path (server-derived session state write) — otherwise record only (flagged INFERRED in §9).
   e. Write `resolution`, `resolved_at=now()`, `assigned_admin_user_id=<resolver>`; events `DISPUTE_RESOLVED` (dispute entity; metadata: action, refund_id, account_action=null) + `ADMIN_ACTION` (metadata: action, dispute_id, refund_id, request_id) — SM §11.7 fields all stored.
   f. `_idempotency_complete(...)` atomically with the tx (VS5/VS8 crash-safe pattern).
4. Response (§7).

No new helper is invented where an approved convention exists: idempotency (`_idempotency_begin/_complete`), errors (`ApiError`), transactions (`tx()`), events (`write_event`/`write_security_event`), serialization (`_serialize_row`), locking (payment→refund order inherited from the VS8 call).

# 13. Refund integration (VS9 → VS8)

**Integration mode: service invocation, synchronous, top-level VS8 commands (AUTHORITATIVE basis: §19.4 "Refund action must call refund service and create ledger/event entries"; the approved VS8 service surface is the implementation of "the refund service").**

Sequence (two-step, decision P1 default — contract-pure, uses only approved fields/endpoints):

```text
1. OPS/ADMIN resolves the dispute (E4, action=PARTIAL_REFUND, refund_amount=1000.00)
   TX: dispute → RESOLVED + resolution + DISPUTE_REFUNDED? no: DISPUTE_RESOLVED + ADMIN_ACTION
       + refund row REQUESTED (dispute_id linked) + REFUND_REQUESTED          [VS8 create_refund]
2. Operator completes the refund through the EXISTING VS8 console/endpoint:
   POST /admin/refunds/:id/approve  {approved_amount, teacher_adjustment_amount, platform_adjustment_amount}
   → APPROVED → PROVIDER_PENDING (mock submit, outside tx) + REFUND_APPROVED/REFUND_PROVIDER_SUBMITTED
3. Result: POST /admin/refunds/:id/mock/succeed|fail  (or /reconcile with proof)
   → SUCCEEDED/FAILED + payment REFUNDED/PARTIALLY_REFUNDED (or restore) + ledger POSTED/VOIDED
```

Why not one-step (resolve performs approval+submission): the approved §19.4 request has **no allocation fields**, and VS8 approval requires them (D9, approved for VS8). Inventing allocation fields on the resolve request is a contract addition — decision P1 option (ii) (Addendum patch, requires approval). Until decided, the two-step path is the only fully contract-pure integration. (Option (ii) is documented for the decision record; if approved later, it is a VS9.x enhancement, not scope creep.)

Guarantees inherited from VS8 (all tested): over-refund bound under payment lock; FULL/PARTIAL amount rules; allocation integrity; provider-event identity; ledger forms; terminality; REFUND_ISSUED never emitted.

Failure semantics: if refund creation fails inside resolve (e.g., over-refund), the **entire resolve rolls back** (dispute stays OPEN; no partial resolution) — the operator sees the VS8 error and may retry with a corrected amount or a different action. No half-resolved state exists.

# 14. Payout interaction (verified against v1 trigger + VS5 service + Addendum §10/§11)

| Situation | Behavior | Class |
|---|---|---|
| Dispute OPEN/UNDER_REVIEW before payout processing | Payout item insert blocked (v1 trigger `Payout item blocked by open dispute` + VS5 service `OPEN_DISPUTE` reason) | AUTHORITATIVE (implemented VS4/VS5; tested) |
| Dispute resolved (RESOLVED) without refund | Block lifts by status (trigger re-evaluates on next payout attempt) — SM §11.3 "Payout may unblock" | AUTHORITATIVE |
| Resolve with FULL_REFUND → refund approved | Payment → REFUND_PENDING → payout items additionally blocked by `NO_CONFIRMED_PAYMENT` (VS5 check) until refund completes | AUTHORITATIVE (VS5/VS8 checks) |
| FULL/PARTIAL refund SUCCEEDED (payment REFUNDED/PARTIALLY_REFUNDED) | No new payout item for that session (NO_CONFIRMED_PAYMENT) — documented VS8 semantic | AUTHORITATIVE (VS8, verified) |
| Refund after payout already PAID | VS8 Form A: new ADJUSTMENT-class ledger (TEACHER_RECOVERABLE + PLATFORM_REFUND_EXPENSE per allocation) / CREDIT PAYMENT_PROVIDER_CLEARING; old PAID payout byte-identical (v1.4 immutability trigger) | AUTHORITATIVE (Addendum §11; VS8) |
| Refund FAILED after resolution | Dispute already RESOLVED → trigger no longer blocks; **no re-block mechanism is specified** | UNKNOWN (governance note G1 — operator may open a new dispute; no reopen) |
| Refund RECONCILED (manual success) | Same as SUCCEEDED (Form A if post-paid; payment PARTIALLY_REFUNDED/REFUNDED) | AUTHORITATIVE (VS8) |

VS9 adds **no** payout mechanism — it records the PAYOUT_BLOCKED/PAYOUT_RELEASED actions in the resolution (TR-10) and relies on the approved status reactivity.

# 15. Ledger behavior (no new accounts; all effects via VS8 forms)

| VS9 action | Ledger effect | Source | Debit | Credit | When | Reversibility | Posting condition |
|---|---|---|---|---|---|---|---|
| NO_ACTION / WARNING / REPORT_CORRECTION_REQUIRED / no-show confirmations (without refund) | none — no money movement specified | SM §11.4/§11.5 (no ledger side effect listed) | — | — | — | — | — |
| FULL_REFUND / PARTIAL_REFUND (no PAID payout for booking) | VS8 **Form D** refund tx: DRAFT at VS8 approve → POSTED on success / VOIDED on failure | VS8 approved (Addendum §10.4 vector; v1 balance trigger) | TEACHER_PAYABLE (teacher share) + PLATFORM_REVENUE (platform share) | PAYMENT_PROVIDER_CLEARING (approved amount) | at VS8 approve (DRAFT) / success (POSTED) | VOIDED if failed/cancelled pre-success (draft never posted → no reversal needed — VS5 precedent) | VS8 proof rules (provider_refund_id or reconciliation proof) |
| FULL_REFUND / PARTIAL_REFUND (PAID payout exists) | VS8 **Form A**: DEBIT TEACHER_RECOVERABLE (teacher share) + DEBIT PLATFORM_REFUND_EXPENSE (platform share) / CREDIT PAYMENT_PROVIDER_CLEARING | VS8 approved (Addendum §11.3) | as left | as right | same as Form D | same | same |
| PAYOUT_BLOCKED / PAYOUT_RELEASED | none at action time (payout ledger entries occur at payout time, VS5) | v1 trigger; VS5 | — | — | — | — | — |

No account, no entry, no account selection is client-reachable. Balance enforced by the v1 deferred constraint trigger on every insert (existing, tested). **Ledger decision: none required — all financial behavior is VS8-approved.**

# 16. Event model (only existing approved enum values)

| Operation | Events (exact) | Source |
|---|---|---|
| E4 resolve (any action) | `ADMIN_ACTION` (dispute entity; metadata: action, dispute_id, refund_id?, request_id) + `DISPUTE_RESOLVED` (dispute entity; metadata: action, resolution summary refs) | SM §11.3 row 3; §11.7; API §19.1/§22.3 |
| E4 resolve (refund action) | + VS8 events from the nested `create_refund`: `REFUND_REQUESTED` (refund entity) + `ADMIN_ACTION` (refund entity, VS8 action) | VS8 (Addendum §13.1) |
| E4 resolve (no-show confirmation, SCHEDULED session) | existing VS3 `SESSION_NO_SHOW` (via the existing no-show path) | SM §8; VS3 |
| E5 list | none (ordinary list read — VS8 list convention; §21.3 monitoring read) | VS8 convention |
| E9 detail read (sensitive fields) | `ADMIN_ACTION` + `SECURITY_EVENT` `ADMIN_ACCESS` (severity 2) — VS8 admin-read convention | VS5/VS8 convention; Security Plan §9 |

Forbidden: `REFUND_ISSUED` (deprecated — Addendum §13.2; asserted in tests), any new enum value (none exist, none added), `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` outside the VS8 success path. No new event names are invented — the full set above exists in the approved `event_type` enum (v1 + v1.1).

# 17. Audit / security model

- Every resolve: `ADMIN_ACTION` + `DISPUTE_RESOLVED` in the same transaction as the state change (API §22.1 same-transaction rule; SM §11.7 all fields stored: resolution, resolved_at, resolver (assigned_admin_user_id), admin action event, refund reference (refund_id in metadata + refunds.dispute_id link), account action reference (account_action=null in VS9)).
- Sensitive admin reads (E9 detail): `ADMIN_ACTION` + `ADMIN_ACCESS` security event (severity 2) — VS5/VS8 pattern.
- Security events: none new beyond the established set (no new `security_event_type` values).
- PII/sensitive data: dispute descriptions may contain sensitive context — read access strictly role/participant-gated (server-derived); no student PII fields added to any response; provider payloads never exposed (VS8 redaction inherited).
- Auditability of the two-step refund flow: the dispute's `linked_refunds[]` (VS8) + `refunds.dispute_id` + event metadata (refund_id in the DISPUTE_RESOLVED event) give a complete audit chain: dispute → resolution → refund → provider event → ledger (all server-derived, append-only).

# 18. Idempotency (existing approved convention — no new mechanism)

- Endpoint E4: `Idempotency-Key` **required** (superset of SM §11.3 "Required if refund action" — plan lock; consistent with VS5/VS6/VS8 where every admin state-changing command requires the key).
- Scope: `dispute_resolve`; canonical body for hashing: `{dispute_id, resolution, action, refund_amount, account_action}` (sorted-keys sha256 — exact VS5/VS8 pattern).
- Replay: same actor + key + hash → stored response returned (200). Conflict: same key, different hash → 409 `IDEMPOTENCY_KEY_CONFLICT`. In-flight: 409 `IDEMPOTENCY_REQUEST_PROCESSING`. Terminal records immutable (v1.3 guards — existing).
- E5 (list): no idempotency (read).
- The nested VS8 `create_refund` call inside resolve uses its own idempotency scope (`refund_create`) with a **derived, deterministic key** (`dispute-resolve-<dispute_id>` — INFERRED-minor; prevents a resolve retry from creating a second refund row; the outer `dispute_resolve` idempotency already guarantees single execution, so the derived key is defense-in-depth only).

# 19. Concurrency (existing lock conventions applied)

- Global lock order (acyclic, extended from VS8): **dispute → payment → refund → booking**. Resolve locks the dispute first (SM §11.3 "Lock dispute + related rows"), then the nested VS8 create locks payment→refund (VS8 order). No VS8 path locks a dispute, so no cycle is possible.
- Concurrent resolves of the same dispute: serialize on the dispute `FOR UPDATE`; the second sees RESOLVED → 409 `DISPUTE_INVALID_STATE` (terminality).
- Concurrent resolve (refund action) + direct VS8 refund create on the same payment: serialize on the payment lock; the over-refund bound (Addendum §15.4) re-evaluated under the lock in both paths — a race cannot over-refund (VS8-tested property, now shared).
- Concurrent resolve + payout processing: payout locks session/payment (VS5 order) and re-checks the dispute status inside its transaction — an OPEN dispute blocks; a concurrent resolve commits first or after, and the trigger/service re-evaluation on the payout item insert sees the final status (v1 trigger is the final guard — tested in VS4/VS5).
- Provider-event concurrency: unchanged (VS8 — event identity unique, replay 200, conflict 409 + security event).

# 20. Database assessment

**SCHEMA_CHANGE_REQUIRED = NO.** Verified against migrations 001–005:

- `disputes`: `resolution TEXT`, `resolved_at TIMESTAMPTZ`, `assigned_admin_user_id UUID`, `status dispute_status` (5 values incl. RESOLVED), `priority`, `category`, FKs to booking/session/payment, `idx_disputes_status_priority` — everything TR-05/TR-19 needs exists.
- The chosen `action` is stored in `resolution` text + event metadata (no action column exists; adding one would be a schema change — not required: the UX-patch `resolution_action` filter is the only consumer and is deferred, P3).
- `refunds.dispute_id` FK exists (VS8 uses it); payout-blocking trigger exists (v1); refund/payout integrity triggers exist (v1.1–v1.4).
- No new table, column, index, enum value, constraint, or trigger is needed or created. (If P5/P6 decisions later require REJECTED/CANCELLED/suspension surfaces, those contract/schema questions are re-opened at that time — nothing is pre-built.)

# 21. Frontend DEV scope (DEV console only — R17 production UI excluded)

Following the VS1–VS8 console convention (5 pages; no production screens):

1. **Admin console** (`frontend/app/admin/page.tsx`): "Disputes (operational)" section —
   - list via E5 (status/category/priority filter selects; priority badge; SAFETY highlighted);
   - detail drawer: category, priority, status, description, linked booking/payment/session refs, opened-by, `linked_refunds[]` (VS8 field) with refund status labels (UX patch 1 label table), audit fields (resolution/resolved_at/resolver) once resolved;
   - resolve form: resolution text (required), action select (9 scope actions), refund_amount input (enabled + validated for FULL/PARTIAL_REFUND), account_action shown as disabled "not available in DEV core (R10 pending)" — server rejects non-null;
   - after a refund-action resolve: link/hint to the existing VS8 Refunds section (approve with allocation → mock result/reconcile) — the two-step flow is operator-visible.
2. **Parent console**: own-dispute detail (status labels per UX patch 1; "Do not display refunded unless SUCCEEDED" rule; linked refund statuses via the VS8 field).
3. **Teacher console**: own-dispute status visibility (read-only; teacher cannot resolve — server-enforced).
No new dependencies; `lib/api.ts` client reused.

# 22. Test architecture (planned — NOT implemented; ~44 tests)

File: `tests/test_dispute_resolve.py` (+ `tests/test_dispute_resolve_concurrency.py`) following VS4/VS5/VS8 patterns.

| ID | Purpose | Setup | Action | Expected | Source |
|---|---|---|---|---|---|
| T-01 | resolve NO_ACTION from OPEN | completed session + OPEN dispute (VS4 open) | resolve (OPS, NO_ACTION) | 200; dispute RESOLVED; resolution/resolved_at/resolver set; DISPUTE_RESOLVED + ADMIN_ACTION; no refund row; no ledger tx; payment unchanged | SM §11.3/§11.7 |
| T-02 | resolve from UNDER_REVIEW | dispute set UNDER_REVIEW via raw DB (state exists; mechanism deferred P5) | resolve | 200 RESOLVED | SM §11.3 from-set |
| T-03 | resolve terminal dispute | RESOLVED dispute | resolve | 409 DISPUTE_INVALID_STATE; row unchanged | SM §11.6 |
| T-04 | authorization matrix | all roles | resolve attempts | parent/teacher/support 403; OPS 200 (non-SAFETY); OPS on SAFETY 403; ADMIN 200 incl. SAFETY | §19.4; §11.6; matrix |
| T-05 | SAFETY priority + ADMIN-only | SAFETY dispute (VS4 priority 1) | OPS resolve / ADMIN resolve | 403 / 200 | §11.2; §19.4 |
| T-06 | excluded actions rejected | OPEN dispute | action=ACCOUNT_SUSPENDED / ACCOUNT_SUSPENSION_RECOMMENDED / arbitrary | 400 VALIDATION_ERROR; dispute unchanged | §3 X1 |
| T-07 | PARTIAL_REFUND creates linked REQUESTED refund | confirmed payment (1700 net scenario), OPEN dispute | resolve PARTIAL_REFUND 400.00 | 200; dispute RESOLVED; refund REQUESTED with dispute_id, requested 400.00, PARTIAL; REFUND_REQUESTED + DISPUTE_RESOLVED + 2×ADMIN_ACTION; payment still CONFIRMED; DRAFT ledger NOT yet created (creation step only) | §19.4; VS8 |
| T-08 | FULL_REFUND amount must equal payment | confirmed payment 2000 | resolve FULL_REFUND 1500.00 | 400 VALIDATION_ERROR; dispute OPEN | VS8/SM §14.2 rule |
| T-09 | PARTIAL_REFUND ≥ payment rejected | payment 2000 | PARTIAL_REFUND 2000.00 | 400 | same |
| T-10 | over-refund at resolve | payment 2000; existing SUCCEEDED 1500 refund | resolve PARTIAL_REFUND 600.00 | 409 OVER_REFUND; dispute stays OPEN (rolled back); no refund row | Addendum §15.4; VS8 |
| T-11 | refund completion via VS8 (two-step) | T-07 state | approve (300/100) → mock succeed | refund SUCCEEDED; payment PARTIALLY_REFUNDED; Form D ledger POSTED; PAYMENT_PARTIALLY_REFUNDED once; dispute linked_refunds shows SUCCEEDED | VS8; Addendum §7.4/§10.4 |
| T-12 | post-paid Form A | payout PAID (VS5 flow) then dispute + PARTIAL_REFUND + approve (300/100) + success | resolve→approve→succeed | Form A entries (TEACHER_RECOVERABLE 300 / PLATFORM_REFUND_EXPENSE 100 / CREDIT clearing 400) POSTED; old payout byte-identical | Addendum §11; VS8 |
| T-13 | refund failure after resolution | T-07 state | approve → mock fail | refund FAILED; payment restored CONFIRMED; ledger VOIDED; dispute stays RESOLVED (G1 note); no PAYMENT_* event | VS8; SM §19.5 |
| T-14 | reconciliation path | T-07 state | approve → reconcile SUCCEEDED (MANUAL_RECONCILIATION proof) | SUCCEEDED + proof fields + payment updated | VS8; Addendum §7.3 |
| T-15 | no payout while dispute OPEN | completed session + report + confirmed payment; OPEN dispute | payout process | 422 OPEN_DISPUTE (service) — regression of VS4/VS5 property through the new code path | v1 trigger; VS5 |
| T-16 | payout unblocks after RESOLVED (no refund) | T-15 state | resolve NO_ACTION → payout process | 201 (paid) | SM §11.3 "may unblock" |
| T-17 | PAYOUT_BLOCKED/RELEASED actions recorded | OPEN dispute | resolve PAYOUT_BLOCKED / PAYOUT_RELEASED | 200 RESOLVED; action in resolution+metadata; no payout mutation; no ledger tx | TR-10 (INFERRED mechanism) |
| T-18 | no-show confirmation (SCHEDULED session) | OPEN dispute on a SCHEDULED-session booking | resolve TEACHER_NO_SHOW_CONFIRMED | session → NO_SHOW_TEACHER (VS3 path) + SESSION_NO_SHOW event; dispute RESOLVED | SM §11.5; VS3 |
| T-19 | no-show confirmation (terminal session) | dispute on COMPLETED session | STUDENT_NO_SHOW_CONFIRMED | dispute RESOLVED; session unchanged (flagged INFERRED in §9) | §11.5 (no approved transition to terminal) |
| T-20 | REPORT_CORRECTION_REQUIRED record-only | OPEN dispute | resolve | 200 RESOLVED; no state side effects (P2 default) | TR-08 |
| T-21 | account_action non-null rejected | OPEN dispute | resolve NO_ACTION with account_action="SUSPEND" | 400 VALIDATION_ERROR | §3 X1/P6 |
| T-22 | idempotency replay | OPEN dispute | resolve twice, same key+body | 200 both; dispute RESOLVED once; one DISPUTE_RESOLVED; refund row ≤1 | VS5/VS8 idempotency |
| T-23 | idempotency conflict | same | same key different body | 409 IDEMPOTENCY_KEY_CONFLICT | same |
| T-24 | missing key | OPEN dispute | resolve without key | 400 IDEMPOTENCY_KEY_REQUIRED | API §24 |
| T-25 | E5 list + filters + audit | N disputes | list (ADMIN) with status/category filters | correct items/pagination; ADMIN_ACTION + ADMIN_ACCESS audit increments | §21.3; VS8 convention |
| T-26 | E5 role access | disputes | parent/teacher list admin route | 403 | §21.3 (P3 nuance for SUPPORT) |
| T-27 | unknown dispute id | — | resolve str(uuid4()) | 404 RESOURCE_NOT_FOUND | convention |
| T-28 | resolution length validation | OPEN dispute | resolve with short/missing resolution | 400 | convention |
| T-29 | refund_amount absent on non-refund actions tolerated; present rejected | OPEN dispute | WARNING with refund_amount | 400 (strict body — INFERRED-minor) | §7 |
| T-30 | audit fields complete (SM §11.7) | T-07 | inspect row + events | resolution, resolved_at, assigned_admin_user_id, ADMIN_ACTION event, refund reference in metadata + refunds.dispute_id | §11.7 |
| T-31 | overlay invariant | T-07 | booking/session status after resolve+refund | unchanged (no DISPUTED ever) | Addendum §4.1; v1.1 CHECKs |
| T-32 | REFUND_ISSUED never emitted | full T-07→T-11 flow | global event scan | 0 rows | Addendum §13.2 |
| T-33 | financial integrity snapshot (post-flow) | all flows run | direct SQL (same gates as VS8 audit) | all 32-style checks pass incl. new dispute-linked rows | Phase 5 audit method |
| T-34 | terminal refund + dispute consistency | T-13 | re-resolve attempt / new dispute allowed | old dispute terminal; new dispute openable (no reopen) | SM §11.6 |
| C-01 | concurrent resolves same dispute | OPEN dispute; 2 threads | both resolve (NO_ACTION) | [200, 409]; one RESOLVED | §19 |
| C-02 | concurrent resolve (refund 600) + direct VS8 create (1500) on 2000 payment | confirmed payment | both create refunds concurrently | at most one combination within bound survives; over-refund 409 for the loser; no over-refund at rest | §15.4 |
| C-03 | concurrent resolve + payout processing | OPEN dispute; eligible session | resolve NO_ACTION + payout process race | payout either blocked (422) or succeeds after resolve; never paid while OPEN at check time | v1 trigger |
| C-04 | idempotency in-flight guard | OPEN dispute | two threads same key | one 200, other 409 PROCESSING or 200 replay (no double resolution) | v1.3 |

Expected count: **~34–44 new tests** (T-01…T-34 + C-01…C-04 + a few split/edge variants per the VS8 file convention). Full suite after VS9: **~195–205** (160 baseline unchanged — VS1–VS8 tests byte-identical; `test_dispute_has_no_status_mutation_path_in_vs4` remains green: it asserts parent PATCH/PUT on `/disputes/:id` stays 404/405, which VS9 does not change).

# 23. E2E architecture (isolated runtime, VS8 suite convention)

Standalone `tests/e2e_dispute_resolution.py`: own PG 16.2 cluster + migrations + dev server; scenario PASS/FAIL with non-zero exit on failure (exactly the VS8 `e2e_refund_lifecycle.py` pattern).

| # | Scenario | Spec support | Key assertions |
|---|---|---|---|
| S1 | normal dispute lifecycle (NO_ACTION) | TR-01/TR-05 (AUTHORITATIVE) | open (VS4 API) → resolve → RESOLVED + audit events + parent detail shows resolution |
| S2 | unauthorized users | TR-04/TR-05 matrix | parent/teacher/support resolve → 403; anonymous 401 |
| S3 | invalid transition | TR-03 | resolve of RESOLVED dispute → 409; excluded actions 400 |
| S4 | FULL_REFUND | TR-06 (AUTHORITATIVE) | resolve → REQUESTED linked refund → VS8 approve (allocation) → mock success → payment REFUNDED; ledger Form D POSTED; parent sees refund completed |
| S5 | PARTIAL_REFUND + payout exposure | TR-07 + Addendum §10 | resolve → approve (300/100) → success → PARTIALLY_REFUNDED; payout for session blocked (NO_CONFIRMED_PAYMENT); exposure honored if a payout race occurs |
| S6 | payout blocked by open dispute | TR-15 (AUTHORITATIVE) | open dispute → payout process 422 OPEN_DISPUTE; DB trigger direct-insert also blocked |
| S7 | payout already paid + refund | TR-12/Addendum §11 | payout PAID 1700 → dispute → PARTIAL_REFUND 400 (300/100) → success → Form A recovery entries; old payout byte-identical |
| S8 | refund failure | TR-13/SM §19.5 | resolve → approve → mock fail → FAILED + restore + VOIDED; dispute RESOLVED; G1 note observed (no re-block) |
| S9 | refund reconciliation | TR-14 | resolve → approve → reconcile SUCCEEDED (proof) → SUCCEEDED + payment updated |
| S10 | idempotent replay | §18 | resolve replay same key → 200 original; single resolution; single refund row |
| S11 | idempotency conflict | §18 | same key different body → 409 |
| S12 | concurrent resolution | §19 | two admin resolves race → [200, 409]; one RESOLVED |
| S13 | audit/security events | §17 | every resolve produces ADMIN_ACTION + DISPUTE_RESOLVED; detail read produces ADMIN_ACCESS security event; counts asserted |
| S14 | ledger integrity (direct SQL) | §15/Phase 5 | all VS8 financial gates + dispute-linked refund checks (POSTED↔SUCCEEDED, balance, no premature POSTED, allocation, no DRAFT residue, no duplicates) |
| S15 | frontend console | §21 (DEV console) | admin list/detail/resolve exercised over HTTP + rendered console actions (admin page section) — API-level E2E of the console endpoints; no browser automation (repo has none) |

All 15 scenarios are supported by the authoritative specifications for the CORE scope (none requires X1–X5 behavior). Scenario 15 is API-level (the repository has no browser-test infrastructure — INFERRED limitation, not a new dependency).

# 24. Dependency audit (planning verification — no changes)

- `backend/requirements.txt`, `frontend/package.json`, `package-lock.json`: byte-identical to HEAD (verified by diff at planning time).
- VS9 uses only existing stack: Django/DRF/psycopg (backend), Next 14/React 18 + existing `lib/api.ts` (frontend). **NO NEW DEPENDENCIES** (expected outcome verified).
- `npm audit` (no --force): 4 advisories (2 high: next 14.2.35, postcss 8.4.31) — UNCHANGED from VS8 baseline (Dependency Audit v1.7); STAGING/PRODUCTION blocked pending remediation (future work item). `pip check`: clean.
- CI/staging/deployment: still absent (R21/R22) — VS9 does not implement them; staging remains blocked on the same gates as the Post-VS8 audit.

# 25. Rollback strategy

- VS9 is **purely additive**: 2 new routes, 2 new service functions (1 list), 1 new test file (+concurrency), console sections. No existing line modified (the only exception pattern across slices: none needed here — even the parent/teacher console additions are additive JSX).
- Rollback = revert the VS9 commit: routes disappear (404), dispute data remains valid (resolution fields are existing columns), any VS8 refunds created through the resolve flow are ordinary VS8 refunds (no cleanup; they remain resolvable via the VS8 console).
- No migration to roll back (none created). No dependency to roll back (none added). No data migration.
- Forward-compat: disputes resolved by VS9 are readable by post-VS9 code without migration.

# 26. Financial risk model (Phase 23)

| Risk | Level | Analysis |
|---|---|---|
| Operational | MEDIUM | Two-step operator flow (resolve → approve with allocation) has more steps than one-step; mitigated by console hints + E2E S4/S5. Reconciliation fallback exists (VS8). |
| Financial | HIGH (mitigated to LOW residual) | Refund actions move ledger money — but exclusively through the VS8-approved, trigger-guarded flow (over-refund bound, FULL/PARTIAL rules, allocation integrity, Form A post-paid). No new financial path exists in VS9 itself. Residual: G1 (refund failure after resolution lifts the payout block with no re-block — UNKNOWN, operator-visible via events/console). |
| Accounting | MEDIUM (mitigated) | Form A recovery entries (TEACHER_RECOVERABLE/PLATFORM_REFUND_EXPENSE) are VS8-approved; balance DB-enforced; no new accounts; OPS-POL-007 allocation value remains OPEN (operator supplies the split per transaction — no formula, per approved D9). |
| Security | LOW-MEDIUM | All mutations OPS/ADMIN-gated with SAFETY→ADMIN; all state server-derived; audit on every action + sensitive read; no new secrets/PII surfaces. |
| Concurrency | MEDIUM (mitigated) | New dispute→payment→refund lock chain; acyclic with VS8/VS5 orders; races covered by C-01…C-04; v1 payout trigger is the final guard. |
| Data integrity | LOW | Append-only events; dispute terminality service-enforced; no schema change; no reopen path. |
| Provider integration | LOW | Mock only; real refund FORBIDDEN; DEV-only guard on mock controls (VS8). |

**Refund + dispute + payout interaction (the critical triangle):** verified in T-10/T-11/T-12/T-15/T-16 and E2E S4–S7/S8/S9/S14 — the only financial coupling is via the existing VS8/VS5/v1 mechanisms; VS9 adds no independent money movement.

# 27. Security risk (Phase 22 — verified boundaries, all server-derived)

| Question | Answer | Basis |
|---|---|---|
| Can an operator resolve someone else's dispute? | OPS/ADMIN may resolve **any** dispute (role matrix "Resolve dispute: OPS policy-limited / ADMIN yes"); a **non-operator** cannot resolve any dispute (403) | §19.4; matrix; T-04 |
| Can a teacher resolve their own dispute? | DENY (403) — resolve is OPS/ADMIN only | matrix; T-04 |
| Can a student manipulate refund amount? | Students have no account (n/a); parents/teachers cannot call resolve at all; the refund amount is set by the operator and bounded by the FULL/PARTIAL rules + over-refund guard | schema; T-08/T-09/T-10 |
| Can a client supply a privileged status? | No — no status field in the request; state is server-derived from the validated action; client cannot reach REJECTED/CANCELLED/UNDER_REVIEW (not implemented) | §7/§10 |
| Can a client select ledger accounts? | No — accounts are computed by the VS8 service (Form L/D/A); no account field anywhere in the contract | §15 |
| Can a client force payout release? | No — release is dispute-status reactivity (trigger + service); no payout endpoint in the resolve contract | §14 |
| Can a client bypass idempotency? | No — server-side `api_idempotency_keys` enforcement (v1.3 guards); missing key 400 | §18 |
| Self-approval / self-suspension? | No self-approval path (resolve is role-gated); suspension not implemented (X1) | §11 |

# 28. Definition of Done (VS9)

1. 160/160 baseline suite green with VS9 files added (expected ~195–205 total, 0 failures).
2. ~34–44 new VS9 tests green (T-01…T-34, C-01…C-04 + variants).
3. E2E `tests/e2e_dispute_resolution.py`: 15/15 scenarios PASS on a fresh isolated runtime, incl. S14 financial gates.
4. Direct-SQL financial audit (Phase 5 method, extended for dispute-linked rows): all checks PASS.
5. Frontend `npm run build` green; console sections render (admin/parent/teacher).
6. `npm audit` unchanged from v1.7 baseline; `pip check` clean; dependency files byte-identical.
7. Migrations byte-identical (no migration created); schema unchanged (verified by diff).
8. REFUND_ISSUED never emitted (global test assertion).
9. Boundary assertions: REAL REFUND/PAYMENT/PAYOUT FORBIDDEN; mock controls DEV-only; no suspension behavior implemented.
10. Reports: VS9 implementation/test/E2E reports + dependency audit v1.8 + README section (established slice-report convention).
11. No file outside the VS9 artifact set modified (scope audit: additive-only diff).

# 29. Open governance items (decisions required before/during implementation — none silently resolved)

| ID | Item | Options | Default if undecided | Class |
|---|---|---|---|---|
| P1 | Allocation input for dispute-triggered refunds | (i) two-step: resolve creates REQUESTED; operator approves via existing VS8 endpoint with allocation (contract-pure) · (ii) one-step: Addendum contract addition of allocation fields on the §19.4 request (requires approval) | (i) — no contract invention | CONTRACT decision (governance) |
| P2 | REPORT_CORRECTION_REQUIRED effect | (i) record-only (resolution text; correction workflow = R14) · (ii) excluded from slice | (i) | INFERRED effect — confirmation |
| P3 | `GET /admin/disputes` shape | dedicated route + status/category/priority filters (this plan) · `resolution_action` filter deferred (no action column) · SUPPORT role per §21.3 (vs VS4 non-grant) — resolve the nuance | as planned; SUPPORT allowed per §21.3 with audit | CONTRACT nuance |
| P4 | OPS "within policy" detail for refund actions | §19.4 says OPS "within policy" without itemizing; plan lock: OPS may resolve non-SAFETY refund actions; ADMIN for SAFETY + "Full refund after completed session" (SM §18.2 ADMIN-override class) | plan lock | INFERRED policy detail |
| P5 | REJECTED / CANCELLED / UNDER_REVIEW mechanisms | (i) Addendum contract patch (new outcome field / cancel endpoint / assign action) · (ii) deferred slice | (ii) deferred — not implemented in VS9 | CONTRACT GAP |
| P6 | Account suspension (R10) | Spec the operational effects (login/content/payout/booking/refund) via an approved spec, then implement suspend/reactivate | deferred — UNKNOWN preserved | UNKNOWN (spec) |
| P7 | `evidence[]` field (API §19.3) | (i) keep VS4 behavior (accept-and-ignore; document) · (ii) schema patch adding storage | (i) | CONTRACT GAP |
| G1 | Refund failure after RESOLVED (payout block lifted, no re-block specified) | operator may open a new dispute (no reopen); formal re-block mechanism = future spec | documented as UNKNOWN; no mechanism invented | UNKNOWN (governance note) |

# 30. Final implementation gate

Per Engineering Governance §5 (financial workflow change approval) — VS9 touches refund/payout-adjacent workflows and requires, **before implementation starts**:

```text
Payment Owner · Database Owner · Security Owner · Architecture Owner · Ops Lead
(+ Legal/Compliance Advisor where applicable — refund allocation policy is OPEN)
```

Gate checklist (all must be YES):
1. P1–P5 decisions recorded (P6/P7/G1 may remain deferred with the §29 defaults).
2. Scope declared: CORE (9 actions; RESOLVED path only) — §2/§3.
3. Baseline verified at implementation start: full suite green on a fresh isolated runtime; migrations byte-identical.
4. Financial-workflow approval (§5) recorded; boundary assertions (REAL REFUND/PAYMENT/PAYOUT FORBIDDEN) accepted.
5. Rollback strategy (§25) accepted.
6. Definition of Done (§28) accepted as the completion gate.

Only after this gate may implementation begin. **This plan does not start it.**

---

# 31. Plan self-audit (Phase 30 cross-checks)

- No UNKNOWN silently resolved: P1–P7, G1 explicitly preserved with defaults labeled.
- No unsupported endpoint: only E4 (§19.4) + E5 (§21.3) added; E6 reused (VS8); E7/E8 explicitly excluded.
- No unsupported state: only OPEN/UNDER_REVIEW → RESOLVED implemented (§11.3 row 3); REJECTED/CANCELLED/UNDER_REVIEW mechanisms flagged as contract gaps, not implemented.
- No unsupported ledger entry: all ledger effects = VS8 approved forms (§15 table cites sources).
- No unsupported event: only existing enum values (§16 table cites sources); REFUND_ISSUED forbidden.
- No invented suspension behavior: X1/X5/P6 — nothing specified, nothing implemented.
- No production payment/refund, no real payout: X6; boundaries in §26/§28/§30.
- No migration: §20 (SCHEMA_CHANGE_REQUIRED = NO).
- No new dependency: §24 (verified byte-identical).
- No VS10 content: X11; roadmap in §29 deferrals only.
- No scope creep: §2 scope list is the complete implementation surface; §3 exclusions closed; §28 DoD matches §2.

# 32. Final status

```text
VS9_IMPLEMENTATION:         NOT STARTED (plan only)
VS9_SCOPE:                  CORE — dispute RESOLVED path, 9 actions, E4+E5, VS8 refund integration (two-step default),
                            payout reactivity (existing), DEV console, tests, E2E
VS9_SCOPE_READY:            YES (subject to P1–P5 plan-time decisions; P1 gates the refund-action coding)
ACCOUNT_SUSPENSION:         EXCLUDED — R10 spec UNKNOWN (P6)
REFUND_DEPENDENCY:          SATISFIED — VS8 committed b73d8ce (pushed) and verified (32/32 financial checks)
PAYOUT_DEPENDENCY:          SATISFIED — VS5 + v1 trigger (verified)
LEDGER_STATUS:              NO NEW ACCOUNTS/ENTRIES — all effects via VS8 approved forms
SCHEMA_CHANGE_REQUIRED:     NO
NEW_DEPENDENCIES:           NO
MIGRATIONS_CREATED:         NO
```

**STOP after this plan. VS9 is NOT implemented. No code, tests, migrations, or frontend changes were made for VS9.**

---

# 33. Execution-Status Addendum — 2026-08-25 (appended after execution; no earlier section of this plan was altered)

This addendum is the current-status record. The §32 final status above ("VS9_IMPLEMENTATION: NOT STARTED (plan only)") remains the **historical record of the planning moment** — it was true when written. It is superseded as current status **only**, by this addendum.

1. **§30 implementation gate: RATIFIED.** The §30 five-owner financial-workflow approval (Payment · Database · Security · Architecture · Ops) was closed by the operator's explicit ratification directive (2026-08-25), using this plan's already-approved scope (§2/§3) and P1–P5 decisions (§29). Full gate record: VS9 Implementation Report v1.0, §8. (The prior Post-VS8 audit had flagged this gate as unrecorded — finding R-3 — while WIP already existed; the ratification directive closed it. No earlier document was rewritten.)
2. **Implementation: COMPLETE** as a single VS9 implementation commit on top of `b73d8ce` (message "Implement DEV Vertical Slice 9 dispute resolution"); scope exactly as §2/§3 (CORE: RESOLVED path, nine actions, E4+E5, VS8 two-step refund per P1); P6/P7/G1 remain deferred with the §29 defaults (UNKNOWNs preserved — nothing invented); REJECTED/CANCELLED/UNDER_REVIEW and account actions were NOT implemented (P5/P6 contract gaps).
3. **Defects found and fixed during execution:** R-1 (stale test import `create_held_booking` → existing `make_held_booking`) and R-2 (raw `uuid.UUID` from the `<uuid:...>` URL converter placed unstringified into the idempotency canonical hash — fixed by normalizing to `str` at the service boundary, exactly the VS8 `create_refund`/`approve_refund` convention; regression-tested). Full record: VS9 Implementation Report v1.0, §4.
4. **Verification (fresh clean-room runs, 2026-08-25):** full suite **197/197** (160 baseline + 37 VS9; 0 failed, 0 skipped) · VS8 E2E **53/53** (VS8 protected, unregressed) · VS9 E2E **75/75** (15 scenarios incl. 11 DB-level financial gates + Next.js production console) · direct-SQL financial audit **30/30 checks PASS** over real suite data (75 refunds / 57 disputes / 239 ledger tx / 3757 events / 650 idempotency records / 24 payout items; every violation count = 0) · frontend production build PASS · `npm audit`/`pip check`/secrets/scope audits clean. Details: VS9 Test Report + E2E Report + Implementation Report §8.1.
5. **Commit discipline:** exactly one VS9 commit; parent `b73d8ce`; **not pushed** (per directive); `main` untouched.
