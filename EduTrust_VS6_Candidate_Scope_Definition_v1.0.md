# EduTrust — VS6 Candidate Scope Definition v1.0

**Document type:** Strict planning-only scope definition for the next vertical slice (no implementation, no commits)
**Audited lineage:** `b245aae` → `2799018` (VS4) → `f271b9a` (VS5, Final Audit: PASS)
**Verified baseline at planning time:** 83/83 tests PASS · 29/29 VS5 E2E PASS · VS1–VS4 regression PASS · financial/ledger/PAID-immutability integrity PASS
**Candidates evaluated:** A. Refund Operations · B. Dispute Resolution · C. Review Moderation
**Evidence base:** existing approved repository documents only. No requirements invented.

**Classification legend (applied to every conclusion):**
`AUTHORITATIVE` = stated in an approved baseline document (PRD, API Architecture, State Machines v1.0 + v1.1 Addendum, schema/migrations, Planning, Product-Ops, Feature-Flag, Payment-Provider documents) · `INFERRED` = derivable from approved documents but not explicitly stated · `UNKNOWN` = not covered by any approved document; a decision is required — this plan does **not** invent it.

---

# 1. Shared context (what VS1–VS5 already deliver)

| Asset | Status | Class |
|---|---|---|
| Refund schema: `refunds` table with full lifecycle columns, `refund_type`/`refund_status` enums, allocation fields, reconciliation fields, v1.1/v1.2/v1.3 integrity + hardening triggers (incl. over-refund prevention, REQUESTED-data restrictions, SUCCEEDED-proof requirement) | Complete, in-place, unmodified | AUTHORITATIVE (schema) |
| Refund events: `REFUND_REQUESTED/APPROVED/PROVIDER_SUBMITTED/SUCCEEDED/FAILED/REJECTED/CANCELLED`, `PAYMENT_PARTIALLY_REFUNDED`, `PAYMENT_RECONCILIATION_REQUIRED` (v1.1 enum extension) + `REFUND_ISSUED` (deprecated per Addendum §13.2) | Complete | AUTHORITATIVE |
| Late-payment refund path: VS2 mock-confirmation branch already creates a `REQUESTED` FULL refund + `PAYMENT_RECONCILIATION_REQUIRED`/`REFUND_REQUESTED` events (tested) | Partial implementation exists | AUTHORITATIVE (implemented per approved branch) |
| Payout refund exposure: VS5 net-payable calculation already consumes APPROVED/PROVIDER_PENDING/SUCCEEDED partial-refund `teacher_adjustment_amount` (tested) | In use | AUTHORITATIVE |
| Post-paid recovery representation: `ADJUSTMENT` tx type, `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` accounts, PAID-row immutability (v1.4) | Representation in place (no workflow) | AUTHORITATIVE |
| Dispute foundation: open/read/duplicate/audit (VS4); `disputes.resolution/resolved_at/assigned_admin_user_id`; `dispute_status` enum (5 states); `DISPUTE_RESOLVED` event | In place | AUTHORITATIVE |
| Review foundation: creation/read/visibility (VS4); `review_status` enum (VISIBLE/FLAGGED/HIDDEN/REMOVED); public list already filters `VISIBLE + is_verified` | In place | AUTHORITATIVE |
| `payment_provider_events` table | Payment-event scoped (`payment_id` FK); **no refund-event model exists** | AUTHORITATIVE (gap noted, not filled) |
| User suspension endpoint | `POST /admin/users/:id/suspend` (ADMIN) in API Arch §21.6 — endpoint-level contract only; no detailed operational spec anywhere | AUTHORITATIVE (thin) / operational detail UNKNOWN |

**Document-internal precedence notes (both resolved by the later Addendum, as before):**
- API Arch §12.6 first transaction says "insert event_ledger `REFUND_ISSUED`", but Addendum §13.2 (authoritative) forbids using `REFUND_ISSUED` in new service logic to mean requested/approved/submitted/succeeded, and §13.3 fixes event timing (`REFUND_REQUESTED` at row creation, money events only after success). A new refund implementation must follow the Addendum. (DOCUMENTATION note only.)
- SM v1.0 §16.2 "→ DISPUTED" row vs Addendum §4.1 overlay rule — Addendum governs; already implemented that way in VS4/VS5. (DOCUMENTATION note only.)

---

# 2. Candidate A — Refund Operations

## 14-dimension evaluation

| # | Dimension | Finding | Class |
|---|---|---|---|
| 1 | PRD authority | PRD: "Refund/dispute status can be tracked" (parent), "View refund status", "Trigger refund/adjustment process if applicable" (admin, §10.4 P1 context); refund states in the PRD state catalogue (`REFUNDED`, `REFUND_PENDING`, `DISPUTED → REFUNDED/RESOLVED`). Refunds are explicit MVP content | AUTHORITATIVE |
| 2 | API contract coverage | **Complete endpoint contract**: `POST /payments/:id/refund` (OPS under policy / ADMIN elevated) with request `{amount, currency, reason, dispute_id}` and a full two-transaction boundary (lock payment+booking; verify `payment.status in (CONFIRMED, DISPUTED)`; refund intent record or `ledger_transaction REFUND`; commit; provider call outside tx; second tx updates payment to `REFUNDED`/`PARTIALLY_REFUNDED` or `REFUND_PENDING`/`FAILED`, reversal/settlement ledger entries, `PAYMENT_REFUNDED` on success) — API Arch §12.6 + §21.3. Also `GET /admin/disputes` lists refunds' context. **Gap:** contract request has no allocation-split field while the schema carries allocation columns (see decision D9) | AUTHORITATIVE (contract) / UNKNOWN (allocation input) |
| 3 | State-machine coverage | **Complete**: Addendum §7 refund states + transition semantics; §7.3 correct event semantics; §7.4 `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only after success; §7.5 forbidden semantics (no settlement at approval, immutable ledger, no row deletion); §8.4 refund identity (`provider_refund_id` linked to `refunds.id`); §13.1 event list; §13.3 event timing table; Planning §10.4 (states + no premature events) | AUTHORITATIVE |
| 4 | Database/schema readiness | **Complete**: full `refunds` schema incl. allocation + reconciliation fields; v1.1 `validate_refund_integrity` (payment match, provider match, allocation=approved, FULL=payment amount, status timestamp rules); v1.2/v1.3 lifecycle + reconciliation guards; over-refund prevention; `REFUND` ledger tx type; `REFUND_PAYABLE`/`ADJUSTMENT`/`PLATFORM_REFUND_EXPENSE`/`TEACHER_RECOVERABLE` accounts. **No schema change needed** | AUTHORITATIVE |
| 5 | Existing implementation | **Partial**: VS2 late-payment branch creates `REQUESTED` FULL refunds + reconciliation-required event (tested). No admin refund endpoint, no approve/reject/cancel flow, no mock provider refund path, no reconciliation command | AUTHORITATIVE (what exists) |
| 6 | Existing tests | VS2 `test_late_payment_after_expiry_creates_refund_and_no_session`; VS1 DB regression smoke (refund guard); VS5 `seed_refund` fixtures (constraint-compliant) + exposure-calculation tests. **No** admin-endpoint/approval/rejection/refund-success tests | verified |
| 7 | Existing E2E coverage | VS2 embedded E2E `E2E_LATE_PAYMENT=PASS`. No admin-refund E2E | verified |
| 8 | Dependency on VS1–VS5 | Payment boundary + mock provider pattern (VS2) ✓; dispute linkage `refunds.dispute_id` (VS4) ✓; payout exposure + post-paid representation (VS5) ✓ | verified |
| 9 | Financial risk | **HIGH** even in DEV: ledger money movement (clearing/refund-payable/settlement), over-refund surface (mitigated by v1.3 guards), payout net-payable interaction (already wired in VS5), post-paid adjustment path | AUTHORITATIVE (constraints) / assessed (level) |
| 10 | Security/privacy risk | MEDIUM: OPS/ADMIN-only, audited; refund records reference bookings/payments (sensitive financial context); reconciliation is operator-attributed (`reconciled_by_user_id`) | assessed |
| 11 | Operational risk | MEDIUM-HIGH: reconciliation must be an explicit audited command (UX Audit: "Admin manual refund reconciliation — explicit reconciliation command endpoint/action — HIGH"); late-payment refund rows created by VS2 currently have no approved DEV path to progress; OPS-POL-007 OPEN | AUTHORITATIVE (UX audit gap, policy open) |
| 12 | Frontend requirements | DEV console: admin refund console (initiate under policy, status tracking, reconciliation action) + parent refund-status visibility (PRD "View refund status") — DEV-only per established posture | AUTHORITATIVE (PRD) / INFERRED (console shape) |
| 13 | Missing governance decisions | **D1–D11 below — all must be decided before implementation** (the DEV refund execution mechanism is entirely unspecified in approved docs; allocation policy is OPEN/legal) | UNKNOWN (by definition) |
| 14 | DEV without structural changes? | Architecture: NO change needed · Schema: NO change needed · State machine: NO change needed · API: additive per §12.6 (one INFERRED-minor addition if allocation input is approved — D9) · MVP: NO expansion (refunds are MVP content). **Feasible — but only after the D-decisions close** | assessed |

## Required decisions for Refund Operations (what each approved document says / what is missing)

| ID | Decision item | What approved documents provide | What is missing (must be decided — not invented) | Class |
|---|---|---|---|---|
| D1 | **Mock refund initiation** (DEV execution of the §12.6 "call provider refund API" step) | Two-transaction boundary + "Outside DB transaction: call provider refund API" (API §12.6); mock-provider precedent for payments (VS2) and payouts (VS5 U1) | No approved DEV mock-refund contract exists. A decision is required to define the DEV mock refund execution mechanism (analogous to U1). The VS2 mock provider contract covers only `payment.confirmed`/`payment.failed` | UNKNOWN |
| D2 | **Provider success** (→ `SUCCEEDED`) | `SUCCEEDED` requires `approved_amount`, `completed_at`, and valid `provider_refund_id` or reconciliation proof (schema triggers); `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only after success (Addendum §7.4); payment → `REFUNDED`/`PARTIALLY_REFUNDED` (API §12.6) | How a DEV mock produces a compliant `SUCCEEDED` row (provider_refund_id value/identity, timing) is unspecified | UNKNOWN |
| D3 | **Provider failure** (→ `FAILED`) | `FAILED` requires `failed_at`; failure fields exist; failure is auditable (Addendum §7) | The DEV mechanism producing `FAILED` (mock failure control? no auto-failure?) is unspecified | UNKNOWN |
| D4 | **Provider event replay** | Addendum §8.1/§8.2/§8.4: identity separation, webhook/event uniqueness, `provider_refund_id` linked to `refunds.id`; idempotency infrastructure (v1.1/v1.3) | No refund-event record model exists (`payment_provider_events` is payment-scoped); replay identity for DEV mock refund events is unspecified. Decide: record mock refund events where, and with what uniqueness key | UNKNOWN |
| D5 | **Reconciliation** (manual OPS) | Reconciliation fields + `reconciled_by_user_id` (v1.2/v1.3); `PAYMENT_RECONCILIATION_REQUIRED` event (used by VS2 late branch); UX Audit demands an explicit reconciliation command (HIGH) | The reconciliation command (endpoint/semantics/what it may set) is not an approved contract — decision required (or explicit deferral) | UNKNOWN |
| D6 | **Late-payment refund interaction** | VS2 branch (approved, implemented, tested) creates `REQUESTED` FULL refund + reconciliation-required event; Addendum §13.3 timing "Late payment unfulfillable" | Whether VS6 progresses those seeded late refunds (approve → mock success → `PAYMENT_REFUNDED` + settlement) is an in-scope decision; the mechanics are the same D1–D2 decisions | UNKNOWN (scope decision) |
| D7 | **Partial refund** | `PARTIAL` type; allocation fields; payout exposure already consumes them (VS5); `PARTIALLY_REFUNDED` payment status + event only on success (§7.4); over-refund prevention (v1.3) | Mechanics approved; execution subject to D1–D4. No separate decision beyond those | AUTHORITATIVE (mechanics) |
| D8 | **Full refund** | `FULL` requires `approved_amount = payment amount` (trigger); payment → `REFUNDED`; `PAYMENT_REFUNDED` on success only | Same as D7 | AUTHORITATIVE (mechanics) |
| D9 | **Refund allocation** (teacher/platform split) | Schema requires `teacher_adjustment + platform_adjustment = approved_amount` for approved+ statuses (v1.1 trigger); OPS-POL-007 (allocation) is **OPEN — requires legal/accounting approval**; §12.6 request has no allocation input field | The split rule for DEV must be decided: (a) actor-supplied split (requires a minor approved contract addition to the §12.6 request), or (b) a documented DEV default split. Until decided, approved-status refunds with non-zero allocation cannot be lawfully created | UNKNOWN + OPEN policy |
| D10 | **Refund ledger behavior** | `REFUND` ledger tx type exists; §12.6: "create refund intent record or ledger_transaction REFUND according to approved schema approach" + "reversal/settlement ledger entries as needed"; accounts exist; VS2 late-branch precedent (DEBIT `PAYMENT_PROVIDER_CLEARING` / CREDIT `REFUND_PAYABLE`) | The exact entry set for the normal (non-late) refund flow is INFERRED from the precedent, not itemized — decision to lock the entry design at plan time (balanced by constraint) | INFERRED → decision at plan time |
| D11 | **Refund audit/event behavior** | Addendum §13.1 event list; §13.2 deprecates `REFUND_ISSUED` in new logic; §13.3 timing table; §7.5 forbidden semantics; §12.6 events | **Sufficiently specified** — no decision needed beyond following the Addendum precedence over §12.6's `REFUND_ISSUED` line (DOCUMENTATION note) | AUTHORITATIVE |

**Verdict A:** highest specification density of the three (complete state machine, complete endpoint contract, complete schema, partial implementation in place) — **but not scope-ready**: D1–D5 (and D9) are genuine UNKNOWNs/Open-policy items that this plan must not invent. If the decisions are approved, implementation needs **no** architecture/schema/state-machine changes and no API redesign (additive per §12.6, subject to D9).

---

# 3. Candidate B — Dispute Resolution

## 14-dimension evaluation

| # | Dimension | Finding | Class |
|---|---|---|---|
| 1 | PRD authority | PRD §10.4 "Dispute Management — P1": admin can open dispute, assign category, review booking/payment/session/report context, **add resolution**, "trigger refund/adjustment process if applicable"; parent "Raise disputes if needed"; dispute rate is an MVP KPI | AUTHORITATIVE |
| 2 | API contract coverage | **Complete for the endpoint**: `POST /admin/disputes/:id/resolve` (OPS/ADMIN), request `{resolution, action, refund_amount, account_action}`, rules (OPS within policy; ADMIN for safety/suspension/exceptional refund/override; "Refund action must call refund service and create ledger/event entries"), event `DISPUTE_RESOLVED` (+maybe refund events) — API §19.4 + §21.3. Per-action request detail for all 11 actions and `account_action` semantics: partially specified | AUTHORITATIVE (endpoint) / INFERRED (per-action detail) |
| 3 | State-machine coverage | **Complete**: SM §11.1 states; §11.3 transition matrix (OPEN→UNDER_REVIEW→RESOLVED/REJECTED; OPEN→CANCELLED; authorities, preconditions, invariants, events); §11.4 the 11 resolution actions; §11.5 effects on related state machines; §11.6 forbidden transitions (no RESOLVED→OPEN, no safety-cancel without review); §11.7 audit requirements (resolution, resolved_at, resolver, admin action event, refund/account references); Addendum §4.1 overlay (resolution keeps factual booking/session states) | AUTHORITATIVE |
| 4 | Database/schema readiness | **Complete**: `disputes.resolution/resolved_at/assigned_admin_user_id`; 5-state `dispute_status` enum; `DISPUTE_RESOLVED` event; payout blocking already reactive to dispute status (VS4/VS5 trigger). No schema change needed | AUTHORITATIVE |
| 5 | Existing implementation | VS4: open + scoped reads + audit (complete foundation). **No** resolve/reject/cancel/assign implementation (explicitly out of VS4 scope) | verified |
| 6 | Existing tests | VS4: open/read/duplicate/concurrency/audit/overlay (28-test suite). No resolution tests | verified |
| 7 | Existing E2E coverage | VS4 E2E: dispute open, duplicate, concurrency, admin read. No resolution E2E | verified |
| 8 | Dependency on VS1–VS5 | Dispute foundation (VS4) ✓; payout release/block reactivity (VS5 trigger) ✓; **refund actions require Candidate A's refund service** (see §4 below); `ACCOUNT_SUSPENSION*` requires §21.6 suspension (thin contract, operational spec UNKNOWN) | verified + AUTHORITATIVE (dependency) |
| 9 | Financial risk | **HIGH for the full action list** (FULL_REFUND/PARTIAL_REFUND move ledger money); LOW for the non-financial subset (NO_ACTION/WARNING/REJECTED/CANCELLED/no-show confirmations) | assessed |
| 10 | Security/privacy risk | MEDIUM: OPS/ADMIN-only, audited (§11.7); resolution text may contain sensitive context; safety disputes carry elevated handling rules | AUTHORITATIVE (rules) / assessed |
| 11 | Operational risk | MEDIUM: policy matrix OPS-vs-ADMIN partially specified (§19.4 rules) but per-action policy detail open; safety-cancel protection must be enforced; OPS-POL-005 (dispute window) OPEN | AUTHORITATIVE (rules) / OPEN (policy) |
| 12 | Frontend requirements | DEV console: admin dispute detail with resolve action (per approved action list), status visibility for parent/teacher (PRD "Refund/dispute status can be tracked") — DEV-only | AUTHORITATIVE (PRD) / INFERRED (console shape) |
| 13 | Missing governance decisions | Per-action OPS/ADMIN policy matrix detail; suspension capability spec (if ACCOUNT_SUSPENDED in scope); whether the slice is "non-financial core" or "full action list" (the latter requires Candidate A + suspension) | UNKNOWN/OPEN |
| 14 | DEV without structural changes? | Non-financial core: NO structural changes needed. Full approved action list: **not deliverable** without Candidate A (refunds) and a suspension operational spec | assessed |

## Does Dispute Resolution genuinely depend on Refund Operations? (evidence-based determination)

**Yes — but only partially, and the documents say so explicitly:**

- API §19.4: *"Refund action must call refund service and create ledger/event entries."* → the `FULL_REFUND`/`PARTIAL_REFUND` actions **depend on a refund service that does not exist yet** (Candidate A). AUTHORITATIVE.
- API §19.1: resolve event = `DISPUTE_RESOLVED`, **"maybe `REFUND_ISSUED`"** → refund coupling is conditional on the chosen action. AUTHORITATIVE.
- PRD §10.4: *"Trigger refund/adjustment process **if applicable**"* → conditional. AUTHORITATIVE.
- SM §11.5: resolution *"may trigger refund, account action, payout release/block"* → "may", not "must". AUTHORITATIVE.
- Payout release/block needs **no refund service**: the DB trigger already blocks payouts while a dispute is OPEN/UNDER_REVIEW; resolving the dispute (status change) naturally unblocks (verified in VS4/VS5). AUTHORITATIVE.
- `ACCOUNT_SUSPENSION_RECOMMENDED`/`ACCOUNT_SUSPENDED` depend on `POST /admin/users/:id/suspend` (§21.6) — endpoint contract exists (AUTHORITATIVE, thin) but the operational spec (status transitions, effect on active sessions/bookings) is UNKNOWN.

**Conclusion:** the **non-financial resolution core** (OPEN→UNDER_REVIEW→RESOLVED/REJECTED, OPEN→CANCELLED with safety-cancel protection, no-show confirmations, audit per §11.7, overlay preservation, payout unblock-by-status) is deliverable **without** Candidate A. The **full approved action list** genuinely depends on Candidate A (refunds) and on a suspension operational spec. A "Dispute Resolution" slice that ships only the non-financial core is a partial slice relative to the approved §11.4 action list — that partiality must be an explicit, approved scope decision, not an assumption. INFERRED (scope-shaping) / AUTHORITATIVE (the dependency facts above).

**Verdict B:** spec-complete for the core, but the approved action list cannot be fully delivered in isolation. Weakest independence of the three.

---

# 4. Candidate C — Review Moderation

## 14-dimension evaluation

| # | Dimension | Finding | Class |
|---|---|---|---|
| 1 | PRD authority | PRD §10.5 "Review Moderation — P1": admin can view reviews, flag abusive content, hide policy-violating content, **preserve rating if review is verified and not fraudulent**; "Review text may be moderated"; "Suspicious review behavior can be flagged" | AUTHORITATIVE |
| 2 | API contract coverage | Endpoint contracts: `POST /admin/reviews/:id/moderate` (OPS/ADMIN, `ADMIN_ACTION` event) — API §18.1 + §21.4; `GET /admin/reviews` (SUPPORT/OPS/ADMIN list) — §21.4; moderation behavior rules: "hide abusive comment text, but verified rating should not be silently deleted unless review is fraudulent or policy-violating; moderation must be audited" — §18.4. **Gap:** request/response field schema for `/moderate` (action values, reason field) not itemized — derivable from the SM matrix (flag/hide/restore/remove) + §18.4 + audit requirement | AUTHORITATIVE (endpoints + behavior) / INFERRED-minor (request schema) |
| 3 | State-machine coverage | **Complete for the moderation transitions**: SM §10.3 rows — VISIBLE→FLAGGED (System/OPS/Admin, abuse/fraud signal), FLAGGED→HIDDEN (OPS/Admin, via the moderate endpoint, policy violation), FLAGGED/HIDDEN→VISIBLE (restore), any→REMOVED (Admin only, fraud/legal/safety); "review record preserved" invariant (no physical delete); §10.4 forbidden list (no delete, status-based only); events `ADMIN_ACTION` | AUTHORITATIVE |
| 4 | Database/schema readiness | **Complete**: `review_status` enum (VISIBLE/FLAGGED/HIDDEN/REMOVED), `reviews.status` column (default VISIBLE); VS4 public list already filters `VISIBLE + is_verified`, so moderation state immediately affects public display with no further change. No schema change needed | AUTHORITATIVE |
| 5 | Existing implementation | VS4: creation/read/visibility/audit (the consumption side). **No** moderation endpoint/service (none existed in VS1–VS5) | verified |
| 6 | Existing tests | VS4 `test_review_public_teacher_reviews_only_visible_no_student_data` pins the VISIBLE-only public behavior (moderation's effect surface is pre-verified). No moderation tests | verified |
| 7 | Existing E2E coverage | VS4 E2E covers review creation/public read. No moderation E2E | verified |
| 8 | Dependency on VS1–VS5 | Reviews (VS4) ✓. **No dependency on any other unimplemented workstream** (no financial coupling, no refund/dispute/payout involvement) | verified |
| 9 | Financial risk | **LOW**: no money movement. Trust-metrics impact is "per policy" and the metrics worker is unimplemented (DB protection trigger in place) | AUTHORITATIVE (constraints) |
| 10 | Security/privacy risk | MEDIUM: moderation exposes full comment text (potential student-sensitive content) to OPS/ADMIN → must be audited (auditing is already the approved pattern; public exposure already minimized by VS4) | assessed |
| 11 | Operational risk | LOW: single audited endpoint; "System" automatic flagging (abuse/fraud detection) has **no approved detection spec** → a manual-only moderation slice is the coherent scope (automatic flagging excluded, not invented) | AUTHORITATIVE (exclusion basis) |
| 12 | Frontend requirements | DEV console: admin review list (incl. non-visible states for OPS) + moderate action (flag/hide/restore/remove with reason); teacher/parent views unchanged (public list already reflects moderation). DEV-only | AUTHORITATIVE (PRD) / INFERRED (console shape) |
| 13 | Missing governance decisions | **None blocking.** OPS-POL-008 (review after partial refund) concerns *eligibility*, not moderation — and the current strict `CONFIRMED`-only default is policy-safe per the continuation audit. The only plan-time lock: the `/moderate` request schema (INFERRED-minor, derivable from the approved matrix) | INFERRED-minor (one item) |
| 14 | DEV without structural changes? | Architecture: NO · Schema: NO · State machine: NO (transitions exactly per §10.3) · API: additive per §18.1/§21.4 · MVP: NO expansion (moderation is P1 PRD content). **Feasible now** | assessed |

**Verdict C:** the only candidate that is **fully deliverable today** with no pending governance decisions, no cross-workstream dependency, no financial risk, and complete state-machine + schema + PRD coverage. The single INFERRED-minor item (request field schema) is derivable from the approved transition matrix and must be locked in the implementation plan (the same treatment as VS5's U1/U2).

---

# 5. Ranking (evidence-based)

| Rank | Candidate | Rationale (evidence) |
|---|---|---|
| **1** | **C — Review Moderation** | Only candidate with complete coverage on every load-bearing axis (PRD P1 §10.5; SM §10.3/§10.4 full matrix; API §18.4 + §21.4 endpoints; schema ready; consumption side pre-verified by VS4) **and zero pending decisions/UNKNOWNs**; no dependencies; lowest financial/operational risk. Coherent vertical loop: list → moderate (flag/hide/restore/remove) → public display changes → audit trail. |
| **2** | **A — Refund Operations** | Highest specification density (Addendum §7/§8.4/§13 + API §12.6 complete contract + full schema + VS2 partial implementation), and the natural future pairing for Candidate B — **but** D1–D5 and D9 are genuine UNKNOWNs/OPEN-policy items that must be decided first (DEV mock refund execution, success/failure/replay/reconciliation mechanics, allocation policy). Best "next major" candidate once the decisions close; not scope-ready today. |
| **3** | **B — Dispute Resolution** | Spec-complete for the non-financial core, but the approved §11.4 action list genuinely cannot be fully delivered in isolation: refund actions depend on Candidate A (AUTHORITATIVE, §19.4) and `ACCOUNT_SUSPENDED` needs a thin/unspecified suspension capability. A non-financial-core-only slice would be a partial slice relative to the approved action list — viable, but the weakest independence and the least complete relative to its own spec. |

**Sequencing note (INFERRED, not a recommendation to implement):** if the decisions for Candidate A are approved, the highest-value pairing is A → B (resolution's refund actions then become deliverable); C is independently deliverable at any point.

---

# 6. Scope-sufficiency determination

| Candidate | Sufficient authoritative specification coverage for a VS6 scope definition? | Condition |
|---|---|---|
| C — Review Moderation | **YES** — VS6_SCOPE_READY: YES (subject to formal approval) | One INFERRED-minor item (the `/moderate` request schema, derivable from SM §10.3) to be locked in the implementation plan |
| A — Refund Operations | **NO** — VS6_SCOPE_READY: NO | Decisions D1–D5, D9 required first (DEV mock refund execution contract; D10 ledger entry design to lock at plan time; OPS-POL-007 allocation policy) |
| B — Dispute Resolution | **NO** — VS6_SCOPE_READY: NO (full action list) / conditionally YES for a declared non-financial core only | Requires Candidate A for refund actions + suspension operational spec; core-only scope must be an explicit approved decision |

Per the planning instruction, **no implementation is recommended at this step** beyond noting that Candidate C meets the sufficiency bar and could be approved as VS6 if chosen.

---

# 7. Governance statement

```text
THIS DOCUMENT: scope definition and ranking only.
VS6_CANDIDATES_EVALUATED: A (Refund Operations), B (Dispute Resolution), C (Review Moderation)
BEST_CANDIDATE: C — Review Moderation (scope-ready; no pending decisions)
SECOND_CANDIDATE: A — Refund Operations (blocked on D1–D5 + D9 decisions)
THIRD_CANDIDATE: B — Dispute Resolution (partial without Candidate A + suspension spec)
REFUND_DEV_EXECUTION: NO mock refund behavior invented (D1–D4 = UNKNOWN, decision required)
DISPUTE_DEP_ON_REFUNDS: partial, AUTHORITATIVE (§19.4) — refund actions only
SCOPE_DEFINITION_ONLY
```

```text
VS6_IMPLEMENTATION_STARTED: NO
DATABASE_MODIFIED: NO
ARCHITECTURE_MODIFIED: NO
API_MODIFIED: NO
STATE_MACHINE_MODIFIED: NO
COMMIT_CREATED: NO
```
