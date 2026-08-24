# EduTrust — Vertical Slice #5 Scope Proposal v1.0

**Document type:** Formal scope-definition proposal (candidate workstream evaluation; converts approved architecture/API/state-machine requirements into a candidate VS5 scope)
**Basis:** Existing repository and approved baseline documents only. No requirements invented.
**Governing rule:** Nothing in this document is an instruction to implement. VS5 scope is **proposed, not approved**.

**Classification legend used throughout:**

```text
AUTHORITATIVE  — stated in an approved baseline document (state machines, API architecture,
                 schema, PRD, planning, governance, product-ops, feature-flag documents)
INFERRED       — derivable from authoritative documents but not explicitly stated
UNKNOWN        — not derivable; no approved document covers it
```

---

# 1. Shared evidence base (applies to all candidates)

| Asset | Status | Reference |
|---|---|---|
| Migration chain v1 → v1.1 → v1.2 (RECONSTRUCTED) → v1.3 → v1.4 | In place, unmodified, executes clean; v1.2 provenance preserved | `database/migrations/`, `MIGRATION_MANIFEST.md` |
| Event ledger (append-only) | `event_type` enum = base 28 values **extended by v1.1** with `REFUND_REQUESTED/REFUND_APPROVED/REFUND_PROVIDER_SUBMITTED/REFUND_SUCCEEDED/REFUND_FAILED/REFUND_REJECTED/REFUND_CANCELLED/PAYMENT_PARTIALLY_REFUNDED/PAYMENT_RECONCILIATION_REQUIRED`; plus `DISPUTE_RESOLVED`, `REFUND_ISSUED`, `PAYOUT_ELIGIBLE`, `PAYOUT_PROCESSED`, `ADMIN_ACTION`, `SECURITY_EVENT` | schema v1 + `002` lines 21–29 |
| Idempotency infrastructure | `api_idempotency_keys` + v1.2/v1.3 lifecycle guards; proven replay/conflict semantics in VS1–VS4 | `002`, `003`, `004` |
| Ledger (double-entry, balanced, append-only) | `ledger_transactions`/`ledger_entries`, balance constraint trigger, `TEACHER_PAYOUT` tx type, v1.1 accounts `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` | schema v1 + `002` |
| Audit/security mechanisms | `write_event`/`write_security_event`, `ADMIN_ACTION` + `ADMIN_ACCESS` pattern, append-only `event_ledger`, `security_events` | VS1–VS4 code, Security Plan |
| RBAC/ownership conventions | `require_roles`, per-object ownership checks, 401/403 conventions | API Arch §4, existing endpoints |
| DEV boundaries | Real payment FORBIDDEN (mock only), real payout FORBIDDEN, production NOT APPROVED | README, all slice reports, Payment Gate |
| Existing tested guard relevant here | Payout-item eligibility DB trigger (completed session + report + confirmed payment + teacher match + **no open dispute**) — exercised by VS4 test `test_open_dispute_blocks_payout_item_at_database_level` | `001` trigger, `tests/test_vertical_slice_4.py` |

---

# 2. Candidate evaluations

## 2.1 Candidate A — Payout Lifecycle

**Lifecycle:** teacher payout eligibility → payout calculation → payout processing → blocked payout → payout failure → paid payout → immutability → audit/event ledger → recovery/adjustment interaction.

| Dimension | Finding | Class |
|---|---|---|
| Authoritative specification references | SM v1.0 §12 (full payout state machine: states, eligibility, allowed/forbidden transition matrix, ledger behavior, failure/compensation); v1.1 Addendum §10 (authoritative net-payable calculation incl. refund exposure and worked example), §11 (refund after payout paid → adjustment/recovery, never mutation); API Arch §15 (endpoint table, eligibility text, `POST /admin/payouts/process` request shape, Idempotency-Key, transaction boundary, failure handling, "never delete payout records"); Planning §10.5–10.6 (payout calculation, post-payout recovery), §11 (payout eligibility job with refund exposure + disputes rule); Feature Flag Governance (`PAYOUT_PROVIDER_MODE`, default `MANUAL_OPS`, staging/prod only, "cannot bypass payout eligibility/dispute checks"); Product-Ops OPS-POL-005 (parent dispute window; unset → "Payout eligibility must remain blocked or require manual OPS release") and OPS-POL-006 (payout delay; **unset → "Payout processing disabled except admin test environment"** — defines DEV behavior); PRD (teacher sees expected/paid/pending payouts, payout status; trust loop) | AUTHORITATIVE |
| State-machine coverage | Complete: 6 states, 7 allowed transitions with authority/preconditions/invariants/side-effects/events/idempotency/locking columns; 6 forbidden transitions; ledger behavior; failure/compensation | AUTHORITATIVE |
| API contract coverage | Complete: 4 endpoints (`GET /teacher/payouts`, `GET /teacher/payouts/:id`, `POST /admin/payouts/process`, `GET /admin/payouts`) with roles, request shape, header, transaction boundary, events; teacher list/detail response field lists not itemized | AUTHORITATIVE (field lists: INFERRED-minor) |
| Database/schema readiness | Complete: `payouts`, `payout_items` (`session_id UNIQUE`), `ledger_transactions/entries` (`TEACHER_PAYOUT`, balance trigger), `validate_payout_item_eligibility` trigger, v1.4 `trg_00_payouts_paid_immutable_v1_4` (PAID rows immutable; correction only via adjustment/recovery transaction), refund allocation fields (v1.3) feeding the calculation | AUTHORITATIVE — no schema change needed |
| Existing implementation status | Zero payout service/API code (verified: no payout routes/services). Adjacent foundations exist and are tested: payment-confirmation ledger entries crediting `TEACHER_PAYABLE` (VS2), session reports (VS3), dispute-based payout blocking (VS4, trigger-tested) | verified |
| Existing tests | `test_open_dispute_blocks_payout_item_at_database_level` (VS4) exercises the DB eligibility guard incl. control case; no payout service tests exist yet | verified |
| Frontend status | None. PRD defines teacher payout surfaces (completed sessions, expected/paid/pending amounts, payout status) — DEV console extension would follow existing pattern | AUTHORITATIVE (PRD), implementation absent |
| Dependencies on VS1–VS4 | Payment-confirmed ledger (VS2) ✓, session + report (VS3) ✓, disputes blocking payout (VS4) ✓ — all present | verified |
| Financial risk (DEV) | MEDIUM: no real funds (real payout FORBIDDEN; `MANUAL_OPS`); internal ledger entries only; overpayment risk governed by Addendum §10.1 (refund exposure reduces net before processing) | AUTHORITATIVE constraints |
| Security/privacy risk | LOW–MEDIUM: OPS/ADMIN-only processing, teacher self-scoped reads, `ADMIN_ACTION`/`PAYOUT_*` events; no student data in payout records | AUTHORITATIVE |
| Complexity | MEDIUM: one service cluster + 4 additive endpoints + ledger posting + idempotency + audit; no new tables, no new state machines, no provider integration in DEV | assessed |
| Coherent vertical slice | YES: entry (eligible completed+reported sessions with confirmed payment and no open dispute) → calculation → process → PAID/FAILED with balanced ledger + events → teacher/admin visibility | assessed |
| Still missing | U1 DEV payout execution mechanism (PROCESSING→PAID via OPS reconciliation — path approved in §12.3 but DEV mechanics undocumented); U2 PENDING row creation trigger (job vs admin-initiated batch — §12.3 "PayoutService/System", Planning §11 job); U3/U4 OPS-POL-006/005 values OPEN (unset-behavior defined); U6 batch aggregation (one payout per teacher batch is inferable from request shape); U7 rounding (NUMERIC(12,2) implied) | U1 UNKNOWN (path approved, mechanics undocumented) · U2 INFERRED · U3/U4 AUTHORITATIVE-open-policy · U6/U7 INFERRED-minor |
| Changes required | Architecture: NO · Database: NO · API: additive only (exact approved contract) · State machine: NO · UX business rules: NO · MVP scope expansion: NO (payouts are explicit PRD MVP content) | assessed |

## 2.2 Candidate B — Dispute Resolution

| Dimension | Finding | Class |
|---|---|---|
| Authoritative specification references | API Arch §19.4 (`POST /admin/disputes/:id/resolve` request `{resolution, action, refund_amount, account_action}`; OPS within policy, ADMIN for safety/suspension/exceptional refund/override; refund actions must call refund service + ledger/events); SM §11.3 (transition matrix incl. `OPEN→UNDER_REVIEW`, `→RESOLVED`, `→REJECTED`, `OPEN→CANCELLED`), §11.4 (11 resolution actions), §11.5 (effects on related state machines), §11.6 (forbidden transitions incl. safety-cancel protection), §11.7 (audit requirements); Addendum §4 (resolution keeps factual booking/session state intact) | AUTHORITATIVE |
| State-machine coverage | Complete for dispute status transitions; §11.5 effects reference refund/payout flows that are not yet implemented | AUTHORITATIVE |
| API contract coverage | Endpoint + request shape + authority rules specified; per-action request details (all 11 actions) and `account_action` semantics only partially specified (account actions reference user suspension, which is unimplemented and slice-unassigned) | AUTHORITATIVE (partial: account actions) |
| Database/schema readiness | `disputes.resolution/resolved_at/assigned_admin_user_id`, full `dispute_status` enum, `DISPUTE_RESOLVED` event — all present | AUTHORITATIVE |
| Existing implementation status | Zero (VS4 explicitly deferred resolution; no mutation endpoint exists — verified by VS4 test) | verified |
| Existing tests | None for resolution (VS4 covers open/read/duplicate/concurrency only) | verified |
| Frontend status | VS4 admin dispute list/detail (read-only) exists; resolution UI not specified (production UI out of DEV scope) | verified |
| Dependencies on VS1–VS4 | Dispute foundation (VS4) ✓; **refund service (Candidate C) required for refund actions; user suspension unimplemented for account actions** | verified gap |
| Financial risk | HIGH: approved action list includes `FULL_REFUND`/`PARTIAL_REFUND`/`PAYOUT_BLOCKED`/`PAYOUT_RELEASED` — executing the full approved action set moves ledger money in DEV | AUTHORITATIVE |
| Security/privacy risk | MEDIUM: OPS/ADMIN-only, audited; resolution text may contain sensitive context | AUTHORITATIVE |
| Complexity | HIGH: coupled to refund service, account actions, OPS-POL-007 (refund allocation, OPEN/legal) and policy gates | assessed |
| Coherent vertical slice | PARTIAL: the non-financial subset (`NO_ACTION`/`WARNING`, RESOLVED/REJECTED/CANCELLED transitions + audit) is self-contained and deliverable; the full approved action list is not deliverable without Candidate C | assessed |
| Still missing | Approved DEV execution for refund actions (depends on C); user suspension capability (no approved spec anywhere in repo — UNKNOWN); OPS-vs-ADMIN action matrix beyond §19.4 rules; cancellation policy detail (safety exception noted, window/owner not itemized) | mixed |
| Changes required | Non-financial subset: none. Full action set: requires refund service (separate workstream) — not resolvable within this candidate alone | assessed |

## 2.3 Candidate C — Refund Operations

| Dimension | Finding | Class |
|---|---|---|
| Authoritative specification references | Addendum §7 (refund states, provider identity, correct event semantics §7.3, forbidden semantics §7.5) + §13.1 (refund event list — all in v1.1-extended enum); v1.1 schema (refunds table, lifecycle); v1.2 RECONSTRUCTED (reconciliation fields + lifecycle/reconciliation guards); v1.3 (allocation fields `teacher_adjustment_amount`/`platform_adjustment_amount`, hardening trigger, over-refund prevention); API Arch §1264/§1391 (`POST /payments/:id/refund` OPS/ADMIN, transaction steps: refund intent record / ledger_transaction REFUND, provider refund API call outside transaction); SM cross-map line 1120 (`DISPUTED → REFUNDED` via refund flow); Planning §10.4 | AUTHORITATIVE |
| State-machine coverage | Complete refund lifecycle with event semantics and forbidden list | AUTHORITATIVE |
| API contract coverage | Endpoint + roles + transaction steps specified; request/response field detail thin | AUTHORITATIVE (detail: INFERRED-minor) |
| Database/schema readiness | Complete: refunds table + guards (v1.1/v1.2/v1.3), ledger accounts for refund expense/recoverable, over-refund prevention | AUTHORITATIVE |
| Existing implementation status | PARTIAL: VS2 late-payment branch already creates `REQUESTED` full refunds + `PAYMENT_RECONCILIATION_REQUIRED`/`REFUND_REQUESTED` events (a working DEV refund-creation path, tested). Admin refund endpoint/approval/rejection: not implemented | verified |
| Existing tests | VS2 `test_late_payment_after_expiry_creates_refund_and_no_session`; DB refund-guard regression smoke (VS1) | verified |
| Frontend status | None | verified |
| Dependencies on VS1–VS4 | Mock payment boundary (VS2) ✓ | verified |
| Financial risk | HIGH: refunds move ledger money (provider clearing ↔ refund payable/expense); over-refund guarded by v1.3 but allocation policy is OPEN (OPS-POL-007 requires legal/accounting approval) | AUTHORITATIVE |
| Security/privacy risk | MEDIUM: OPS/ADMIN-only, audited | AUTHORITATIVE |
| Complexity | HIGH: DEV provider-refund execution, ledger reversal, allocation calculation, payout net-payable interaction | assessed |
| Coherent vertical slice | PARTIAL: admin initiate/approve/reject/cancel path is deliverable; refund SUCCEEDED/FAILED requires a provider-side result, and the approved mock provider contract (VS2) covers only `payment.confirmed`/`payment.failed` — no approved DEV mock-refund event exists | assessed |
| Still missing | **DEV refund execution path (UNKNOWN — OPS reconciliation is the only plausible approved route but is not documented for refunds)**; OPS-POL-007 allocation split (OPEN, legal); refund reason-code set beyond existing codes | UNKNOWN / OPEN |
| Changes required | Schema: NO · State machine: NO · Architecture: NO · But the DEV execution-path gap (UNKNOWN) must be resolved by an explicit decision before implementation | assessed |

## 2.4 Candidate D — Review Moderation

| Dimension | Finding | Class |
|---|---|---|
| Authoritative specification references | SM §10.3 moderation rows (`VISIBLE→FLAGGED` System/OPS/Admin on abuse/fraud signal; `FLAGGED→HIDDEN` via `POST /admin/reviews/:id/moderate`; `FLAGGED/HIDDEN→VISIBLE` restore; `→REMOVED` Admin only, fraud/legal/safety; preconditions and "review record preserved"); §10.4 forbidden list (no physical delete; status-based only); API Arch lines 1809/2029 (`POST /admin/reviews/:id/moderate`, OPS/ADMIN, "Moderate review content" / "Hide/flag/remove content", event `ADMIN_ACTION`) | AUTHORITATIVE (endpoint contract thin) |
| State-machine coverage | Complete for the 4 moderation transitions incl. authority, preconditions, DB invariants, events | AUTHORITATIVE |
| API contract coverage | Endpoint, roles, purpose, event specified; request/response field contract (action values, reason field) not itemized — action set is derivable from the SM matrix (flag/hide/restore/remove) | AUTHORITATIVE (request schema: INFERRED-minor) |
| Database/schema readiness | Complete: `review_status` enum (VISIBLE/FLAGGED/HIDDEN/REMOVED) + `reviews.status`; VS4 public endpoint already filters `VISIBLE + is_verified`, so moderation immediately affects public display; no student data in public rows | AUTHORITATIVE |
| Existing implementation status | Zero moderation code; VS4 public-read filter provides the consumption side | verified |
| Existing tests | None for moderation; VS4 `test_review_public_teacher_reviews_only_visible_no_student_data` pins the VISIBLE-only public behavior | verified |
| Frontend status | VS4 admin operational review list exists (read-only); moderation UI unspecified (production UI out of DEV scope) | verified |
| Dependencies on VS1–VS4 | Reviews (VS4) ✓ — no dependency on any other unimplemented workstream | verified |
| Financial risk | LOW: no money movement; trust-metrics effect "per policy" and metrics worker unimplemented (DB protection trigger in place) | AUTHORITATIVE |
| Security/privacy risk | MEDIUM: moderation exposes full review comment text (potential student-sensitive content) to OPS/ADMIN → must be audited; public exposure already minimized by VS4 | assessed |
| Complexity | LOW: 1 additive endpoint + 4 status transitions + audit events; no new schema/events/services beyond the service method | assessed |
| Coherent vertical slice | YES: operational review list → moderate (flag/hide/restore/remove) → public display changes → audit trail | assessed |
| Still missing | Request/response field contract for `/moderate` (INFERRED-minor); automatic "System" flagging (abuse/fraud detection) — no approved detection spec (excluded, not invented); moderation notification — "Optional" in matrix (excluded) | INFERRED-minor / UNKNOWN-excluded |
| Changes required | Architecture: NO · Database: NO · API: additive only · State machine: NO · UX business rules: NO · MVP scope expansion: NO | assessed |

---

# 3. Ranking (evidence-based)

| Rank | Candidate | Why |
|---|---|---|
| 1 | **A — Payout Lifecycle** | Highest specification density: complete state machine **and** authoritative calculation rules **and** complete API contract **and** complete schema/triggers/events **and** explicit DEV gate behavior (OPS-POL-006 unset rule) **and** tested existing guard (VS4). Remaining gaps are narrow, bounded, and non-structural (U1–U7 below). Financially safe in DEV (mock/manual-ops, real payout forbidden). |
| 2 | D — Review Moderation | Fully coherent and lowest risk, but specification density is thinner (endpoint contract is one line + SM matrix; request schema INFERRED-minor) and product value is narrower; the "System flag" half of §10.3 has no approved detection spec. A good early candidate if payout is deferred. |
| 3 | B — Dispute Resolution | Strong spec, but the approved action list cannot be fully delivered without Candidate C (refund service) and an unimplemented suspension capability; highest coupling; financial actions are the riskiest to bring in without the refund foundation. Deliverable only as a non-financial subset (would leave the approved action list incomplete). |
| 4 | C — Refund Operations | Complete lifecycle spec and schema, and a partial DEV creation path already exists (VS2), but the DEV provider-refund **execution path is not approved anywhere** (mock contract covers only confirmed/failed; OPS reconciliation for refunds undocumented) and allocation policy is OPEN (legal). Bringing refunds in without a defined DEV success path would force an undocumented mechanism. |

**B vs C ordering note:** B ranks above C only because C contains an UNKNOWN execution path; a combined "Refund + Dispute-resolution" workstream is the natural future pairing, but each individually is less slice-complete than A or D.

---

# 4. Recommendation

```text
RECOMMENDED_VS5_CANDIDATE: Payout Lifecycle (Candidate A)

RECOMMENDATION_CONFIDENCE: HIGH (that the existing approved documents are sufficient to
                           define the slice scope; the slice itself still requires the
                           explicit approval decisions listed in §5 before implementation)

RATIONALE:
- Evidence density: only candidate with complete coverage on all four pillars —
  state machine (SM v1.0 §12), calculation rules (v1.1 Addendum §10, marked
  "authoritative"), API contract (API Arch §15 with endpoint table, request shape,
  Idempotency-Key, transaction boundary, failure handling), and database (payouts/
  payout_items/ledger/eligibility trigger/PAID-immutability trigger/event enum).
- No structural changes: zero schema, state-machine, architecture, or UX business-rule
  changes required; API additions follow the exact approved contract.
- Dependency closure: every upstream dependency (confirmed-payment ledger VS2,
  session+report VS3, dispute blocking VS4) is already implemented and tested.
- Financial safety in DEV: real payout is FORBIDDEN by every boundary document;
  PAYOUT_PROVIDER_MODE defaults to MANUAL_OPS; OPS-POL-006 defines DEV behavior when
  the delay policy is unset ("payout processing disabled except admin test environment").
- Existing guard: the payout-eligibility DB trigger (incl. dispute block) is already
  present and exercised by VS4 tests — the slice extends tested ground, not unknown ground.
- MVP position: teacher payouts are explicit PRD MVP content (not scope expansion).
- Runner-up (D, Review Moderation) is recommended only if the scope decision prioritizes
  lowest risk over specification density; it is fully specified enough to slice.
```

No candidate is declared VS5 automatically. This recommendation requires an explicit scope approval per the repository's governance (Engineering Governance release gates; slice reports' "Do not start automatically" convention).

---

# 5. Payout Lifecycle — nine-capability sufficiency verification (required)

| Capability | Defined by approved documents? | Evidence |
|---|---|---|
| Teacher payout eligibility | YES — AUTHORITATIVE | SM §12.2 (8 conditions) + Addendum §10.5 (incl. `net_teacher_payable > 0`, no full refund, not already in payout_items) + API §15.2 ("enforced by `validate_payout_item_eligibility()` and must also be checked by API service logic") + OPS-POL-005/006 (dispute window & payout delay, unset behaviors defined) |
| Payout calculation | YES — AUTHORITATIVE | Addendum §10.1 formula (gross − reserved/succeeded refund adjustments − deductions = net), §10.2 (approved/provider-pending refund exposure reduces eligibility), §10.3 (allocation fields sum rule), §10.4 worked example, §10.5 (net = 0 → no item) |
| Payout processing | YES — AUTHORITATIVE (DEV execution mechanics: see U1) | API §15.3 (endpoint, `{teacher_id, session_ids, idempotency_scope}`, `Idempotency-Key: payout-<uuid>`, transaction boundary: verify permission → lock → verify eligibility → payout row → items → `TEACHER_PAYOUT` ledger + balanced entries → `PAYOUT_ELIGIBLE`; provider call outside transaction; second tx: status PAID/FAILED + `PAYOUT_PROCESSED`) + SM §12.3 (`ELIGIBLE→PROCESSING` by OPS/Admin) |
| Blocked payout | YES — AUTHORITATIVE | SM §12.4 ("Payout while open dispute exists" forbidden; duplicate item forbidden) + DB trigger (dispute/report/payment/teacher checks, VS4-tested) + Addendum §10.5 + OPS-POL-005/006 unset behaviors |
| Payout failure | YES — AUTHORITATIVE | SM §12.3 (`PROCESSING→FAILED`, failure reason captured, no deletion, retry possible, reversal if ledger posted prematurely) + §12.6 (no re-eligibility without safe retry/cancel; no final paid ledger if funds didn't move) + API §15.3 failure handling |
| Paid payout | YES — AUTHORITATIVE | SM §12.3 (`PROCESSING→PAID` on provider success, valid provider reference, balanced ledger, `PAYOUT_PROCESSED`) + v1.4 PAID-immutability trigger |
| Immutability | YES — AUTHORITATIVE | API §15.3 "Never delete payout records" + v1.4 `trg_00_payouts_paid_immutable_v1_4` ("PAID payout rows are immutable; create a separate adjustment/recovery transaction") + SM §12.5.4 (no UPDATE/DELETE of ledger; reversals only) |
| Audit / event ledger | YES — AUTHORITATIVE | `PAYOUT_ELIGIBLE`, `PAYOUT_PROCESSED`, `ADMIN_ACTION` (all in enum); append-only `event_ledger` trigger; admin-processing audit pattern established in VS2–VS4 |
| Recovery / adjustment interaction | YES — AUTHORITATIVE | SM §12.5–12.6 (reversal transaction, never mutation) + Addendum §11 (refund after payout paid → adjustment/recovery ledger transaction) + v1.1 ledger accounts `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` |

**Result: 9/9 capabilities are defined by approved documents. VS5_SCOPE_READY: YES**
(scope is definable from the baseline — but per instruction, NOT implemented, and NOT approved).

## Still unspecified before implementation (decision items, none requiring structural change)

| ID | Item | Class | Blocking? |
|---|---|---|---|
| U1 | **DEV payout execution mechanism** — how `PROCESSING→PAID` occurs in DEV. SM §12.3 approves "Provider result / **OPS reconciliation**" as the PAID authority, and the feature-flag default is `MANUAL_OPS`, but no document specifies the DEV reconciliation step/semantics (e.g., an OPS/ADMIN reconciliation action recording a mock provider reference). Must be decided as an explicit DEV-only mechanism consistent with the mock-payment boundary. | UNKNOWN (path approved; mechanics undocumented) | Yes — decision required before coding |
| U2 | **PENDING row creation** — SM §12.3 attributes batch creation to "PayoutService/System"; Planning §11 defines a payout eligibility job. Whether DEV uses an admin-initiated batch command or a job is undocumented. Admin-initiated batch is INFERRED as the DEV-consistent choice (matches mock/sandbox posture). | INFERRED | Yes — decision required (low risk) |
| U3 | `PAYOUT_DELAY_SECONDS` (OPS-POL-006) — OPEN policy; unset → "Payout processing disabled except admin test environment" (DEV qualifies; pilot value 48h recommended but NOT APPROVED). DEV may proceed with the unset/admin-test semantics. | AUTHORITATIVE-open-policy | No (unset behavior is defined) |
| U4 | `PARENT_DISPUTE_WINDOW_SECONDS` (OPS-POL-005) — OPEN; unset → "Payout eligibility must remain blocked or require manual OPS release". Strictest safe default: remain blocked / manual OPS release in DEV. | AUTHORITATIVE-open-policy | No (unset behavior is defined; choice of strict default should be recorded) |
| U5 | Teacher payout list/detail response field lists — endpoints defined; field itemization follows the standard envelope conventions (minor). | INFERRED-minor | No |
| U6 | Batch aggregation — one payout row per process call containing N payout_items (inferable from the approved request shape `{teacher_id, session_ids}`); not explicitly stated. | INFERRED | No (record the inference) |
| U7 | Amount rounding — `NUMERIC(12,2)`/DZD implied by schema; Addendum example uses whole DZD. | INFERRED-minor | No |

None of U1–U7 requires architecture, database, API-contract, or state-machine changes; U1/U2 are governance decisions to lock at design time.

---

# 6. Governance statement

```text
THIS DOCUMENT: scope definition and ranking only.
VS5_SCOPE_READY: YES (for the recommended candidate, subject to U1/U2 decisions + explicit approval)
IMPLEMENTATION_STARTED: NO
CANDIDATES NOT RECOMMENDED: Dispute Resolution (needs Refund Operations + suspension capability),
                            Refund Operations (UNKNOWN DEV execution path + OPEN allocation policy),
                            Review Moderation (coherent runner-up; thinner contract)
REAL PAYOUT: FORBIDDEN        PRODUCTION: NOT APPROVED
```
