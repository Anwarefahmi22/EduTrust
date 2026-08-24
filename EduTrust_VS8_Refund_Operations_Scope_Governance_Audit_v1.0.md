# EduTrust — VS8 Refund Operations Scope & Governance Audit v1.0

**Audit type:** Strict READ-ONLY scope & governance audit for the VS8 candidate "Refund Operations" (R1). No implementation, no code, no SQL, no architecture, no API contract, no state-machine change, no commits, no pushes.
**Audited state:** `Anwarefahmi22/EduTrust` @ branch `arena/01a03280-edutrust`
**Classification legend:** `AUTHORITATIVE` = stated in an approved baseline document · `INFERRED` = derivable from approved documents, not explicitly stated · `UNKNOWN` = no approved document covers it; a decision is required — this audit does **not** invent it · `OUT OF SCOPE` = excluded by an approved boundary.

**Decision-ID cross-reference (used throughout):**

| This audit / user ID | VS6 Candidate Scope Definition ID | Subject |
|---|---|---|
| D1 | D1 | DEV/mock refund initiation mechanism |
| D2 | D2 + D3 | Mock provider success / failure mechanics |
| D3 | D4 | Provider refund event / replay model |
| D4 | D5 | Reconciliation command / workflow |
| D5 | D6 | Late-refund progression |
| D9 | D9 | Refund allocation / legal / accounting policy |
| (context) | D7, D8 | Full / partial refund mechanics (AUTHORITATIVE) |
| (context) | D10 | Refund ledger entry set (INFERRED → plan-time lock) |
| (context) | D11 | Refund audit/event behavior (AUTHORITATIVE) |

---

# 1. Git state verification (read-only)

| Check | Result | Class |
|---|---|---|
| Current branch | `arena/01a03280-edutrust` | verified |
| Local HEAD | `157a54da48329319deafc8c52a1f065a2b20cc5f` | verified |
| Remote `refs/heads/arena/01a03280-edutrust` | `157a54da48329319deafc8c52a1f065a2b20cc5f` — exact match with local HEAD | verified |
| Remote `main` | `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` — unchanged from all prior audits | verified |
| Working tree | CLEAN (0 modified, 0 untracked) | verified |
| VS7 presence | Commit `157a54d` "Implement DEV Vertical Slice 7 teacher verification" on top of VS6 `e0e3d89`; VS7 plan + implementation/test/E2E reports and `tests/test_vertical_slice_7.py` in HEAD; README documents VS7 (118 tests = 98 baseline + 20 VS7) | verified — **VS7: COMPLETE and pushed** |
| VS8 implementation | No VS8 files, routes, services, tests, or docs anywhere in HEAD or the working tree (case-insensitive scan for `vs8`/`slice 8`/`slice_8`: 0 hits) | verified — **VS8: NOT STARTED** |
| Lineage | `b245aae` (baseline, VS1–VS3) → `83c7bc5` (restore VS4+VS5) → `e0e3d89` (VS6) → `157a54d` (VS7) | verified |

Note on `dc5a18f`: the SHA referenced in some session-level instructions was destroyed by a prior environment reset and was rebuilt content-identically as `157a54d` (same parent `e0e3d89`, same 13 files, +1969/−1, same message). This audit verifies against the canonical `157a54d`.

---

# 2. Authoritative sources governing refunds (and their approval status)

Per `EduTrust_Implementation_Baseline_v1.0.md` (CONDITIONAL DEV/STAGING BASELINE; gate YELLOW → "DEV implementation may begin with mock payment and no production deployment"):

| Source | Baseline status | Refund content (verified in this audit) |
|---|---|---|
| `EduTrust_MVP_PRD_v1.0.md` | APPROVED | Parent "Refund/dispute status can be tracked" / "View refund status"; admin "Reconcile provider transaction IDs", "Trigger refund/adjustment process if applicable" (§10.4 P1); booking `DISPUTED → REFUNDED / RESOLVED`; payment states incl. `REFUND_PENDING/REFUNDED/PARTIALLY_REFUNDED`; rules: "Refunds must create ledger entries. Manual adjustments require admin reason and event log." Refunds are explicit MVP content |
| `EduTrust_API_Architecture_v1.0.md` | APPROVED | **§12.6 full refund endpoint contract** (`POST /payments/:id/refund`, OPS-under-policy / ADMIN-elevated, two-transaction boundary); §21.3 admin refunds/disputes catalogue; §14 ledger rules (`Refund → REFUND` tx type; balance; immutable entries); §2.6/§24 idempotency (required; `refund-<uuid>`; replay/conflict semantics); §4.1 + role matrix (SUPPORT "Cannot process refunds/payouts"; "Process refund: OPS policy-limited / ADMIN yes"); §19.4 ("Refund action must call refund service and create ledger/event entries"); §29.7 refund transaction sequence; §11.6 cancellation `requested_refund` ("cancellation may create refund eligibility or dispute") |
| `EduTrust_API_Contract_Addendum_v1.1.md` | **APPROVED WITH CONDITIONS** (condition: convert to OpenAPI/shared schemas during implementation — an integration-hardening obligation, not a DEV scope blocker) | **§7.1 `GET /admin/refunds`**, **§7.2 `GET /admin/refunds/:id`**, **§7.3 `POST /admin/refunds/:id/reconcile`** (full request schema, rules, error catalogue, idempotency, events, state restrictions); **§8 refund summaries** in `GET /payments/:id` (`refunds[]`), `GET /bookings/:id` (`refund_summary`), `GET /disputes/:id` (`linked_refunds`); "No `POST /admin/recoveries` in MVP" |
| `EduTrust_State_Machines_v1.0.md` | APPROVED | §7 payment state machine (states, transition matrix incl. `CONFIRMED/DISPUTED → REFUND_PENDING → REFUNDED/PARTIALLY_REFUNDED`, forbidden transitions, webhook replay semantics, "reconciliation must detect provider refund and complete internal refund state"); §14 refund lifecycle (7 states, types, transition matrix with authorities, partial/full behavior); §17.6 over-refund rule; §19.5 refund provider failure behavior; §11.4 the 11 dispute resolution actions (incl. `FULL_REFUND`/`PARTIAL_REFUND`) |
| `EduTrust_State_Machines_v1.1_Addendum.md` | APPROVED (supersedes conflicting v1.0 wording; explicit authority hierarchy §2) | **§7 authoritative refund states + correct event semantics + forbidden semantics**; §8 provider identity model (incl. **§8.4 `provider_refund_id` must link to `refunds.id`**); §9.3 late-payment branch B; §10 partial-refund → payout calculation; §11 refund after payout paid (adjustment/recovery, `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE`); **§13.1 event list, §13.2 `REFUND_ISSUED` deprecation, §13.3 event timing table**; §14.3 forbidden payment/refund transitions; §15.4 over-refund prevention formula; §16 admin override rules (no `payment.status = REFUNDED` before success); §17 open operational parameters |
| `edutrust_schema_v1.sql` → `..._v1_4.sql` (migrations 001–005) | v1 APPROVED · v1.1 APPROVED · v1.2 **CONDITIONAL — operational baseline approved with provenance warning** (reconstructed; historical equivalence UNVERIFIED) · v1.3 APPROVED · v1.4 APPROVED remediation · Migration Dry Run v1.4 APPROVED evidence | Complete refund object set (see §5 below): `refunds`, `refund_status`/`refund_type` enums, allocation + reconciliation columns, `payment_provider_events` (with refund linkage), `api_idempotency_keys`, `REFUND`/`ADJUSTMENT` ledger tx types, `REFUND_PAYABLE`/`TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` accounts, integrity/lifecycle/proof/idempotency triggers, PAID-payout immutability |
| UX `v1.0` + `v1.1 Patch` | APPROVED | Flow 32 — Admin Refund Handling (lifecycle, allocation visibility, events); **v1.1 Patch 1 closes UX-AUD-001** (refund read/status expectations, per-state labels, "Do not display 'Refunded' unless SUCCEEDED"); **v1.1 Patch 2 closes UX-AUD-002** (explicit reconciliation flow → `POST /admin/refunds/:id/reconcile`) |
| `EduTrust_UX_Audit_v1.0.md` | (audit input; findings closed by the approved v1.1 patch) | UX-AUD-001 (refund read API, HIGH), UX-AUD-002 (reconciliation command, HIGH), UX-AUD-005 (payout exposure from APPROVED/PROVIDER_PENDING) |
| `EduTrust_Product_Ops_Policy_Decisions_v1.0.md` | READY FOR REVIEW — **not approved production policy**; all 10 policies OPEN (pilot defaults only) | OPS-POL-003 (late-payment auto-refund vs OPS review) incl. "What happens if unset: … block auto-refund"; **OPS-POL-007 (refund allocation)** incl. "What happens if unset: Refund approval requires manual allocation fields; auto-approval disabled" |
| `EduTrust_Payment_Provider_Readiness_v1.0.md` | READY FOR REVIEW — **NOT LEGAL APPROVAL**; implementation NOT STARTED | Refund support / refund webhook / partial refund = `REQUIRES PROVIDER CONFIRMATION`; bank transfer = manual refund process; settlement/legal not approved |
| `EduTrust_Payment_Provider_Gate_Assessment_v1.0.md` | Baseline §6: **DEV/STAGING MOCK APPROVED; REAL MONEY BLOCKED** | DEV approved mode `MOCK_PAYMENT_PROVIDER`; **allowed: "test refunds/reconciliation using mock provider events"**; not allowed: real money, real credentials, real teacher payouts; refund capability "Architecturally supported, provider-specific capability unconfirmed" |
| `EduTrust_Feature_Flag_Governance_v1.0.md` | APPROVED | `PAYMENT_PROVIDER_MODE` (default `DISABLED`), **`REFUND_PROVIDER_MODE` (default `MANUAL_RECONCILIATION`; values `DISABLED`/`MANUAL_RECONCILIATION`/`PROVIDER_API`; forbidden behavior: "Cannot mark refunded before success proof")**, `PAYOUT_PROVIDER_MODE` (default `MANUAL_OPS`); "Flags … must not weaken safety controls" |
| `EduTrust_Implementation_Planning_v1.0.md` | APPROVED (baseline engineering set) | §10.4 refund lifecycle (7 states; "Do not emit `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` before refund success"); §10.5 payout calculation; §10.6 post-payout recovery |
| `EduTrust_Test_Traceability_Matrix_v1.0.md` | APPROVED | Refund rows: "Refund lifecycle valid", "Over-refund blocked", "Partial refund allocation", "Post-payout recovery separate", "Provider payload redaction"; planned artifacts `test_refund_service.py`, `test_refund_concurrency.py`, `e2e_refund_lifecycle.spec.ts`, `e2e_admin_refund_reconciliation.spec.ts` (none exist yet) |
| Implemented VS2/VS5 code + reports | verified in-repo | VS2 late-payment branch (creates `REQUESTED` FULL refund, tested); mock provider with unused `initiate_refund` primitive; VS5 payout refund-exposure calculation (consumes APPROVED/PROVIDER_PENDING/SUCCEEDED partial refunds; FULL refund row blocks payout) |

**Document-precedence note (AUTHORITATIVE):** SM v1.1 Addendum §2 defines the conflict order (Addendum > Schema v1.1 > SM v1.0 > API Arch v1.0 > DB Schema v1.0 > PRD). Concretely for refunds: API §12.6's `insert event_ledger REFUND_ISSUED` line is superseded by Addendum §13.2/§13.3 (do not use `REFUND_ISSUED` in new logic; `REFUND_REQUESTED` at row creation; money events only after success). SM v1.0 §14.3's "ADMIN_ACTION metadata failure" for the `PROVIDER_PENDING → FAILED` row is superseded by Addendum §7.3's `REFUND_FAILED` event.

---

# 3. Authoritative refund lifecycle map

Lifecycle: **eligibility → creation/request → (approval | rejection) → provider pending → (success | failure) → reconciliation/retry/recovery**, with payment-state shadowing.

| # | Stage | What is AUTHORITATIVE | INFERRED | UNKNOWN | OUT OF SCOPE |
|---|---|---|---|---|---|
| 1 | **Eligibility** | Payment must be `CONFIRMED`/`DISPUTED` (API §12.6; v1.1 integrity trigger additionally accepts `REFUND_PENDING`/`PARTIALLY_REFUNDED`, enabling follow-up partial refunds); over-refund bound `sum(APPROVED, PROVIDER_PENDING, SUCCEEDED) + new ≤ payment.amount` under payment/refund locks (SM §17.6, Addendum §15.4, v1.1 trigger); refund requires `reason` (≥3 chars), optional `reason_code`, optional `dispute_id`, `currency = DZD` (schema) | Refund eligibility created by cancellation of a paid booking (API §11.6 "may create refund eligibility or dispute" — cancellation endpoint itself unimplemented, R4) | — | Parent/teacher self-service refund request UI (no such contract exists; request path is OPS/ADMIN or dispute-mediated) |
| 2 | **Creation/request** | `POST /payments/:id/refund` (OPS under policy / ADMIN elevated), request `{amount, currency, reason, dispute_id}`, idempotency required ("Prevent duplicate refunds", `refund-<uuid>`) — API §12.6 + §24; refund row created `REQUESTED`; `REFUND_REQUESTED` emitted immediately at row creation (Addendum §13.3); SM §14.3 row "No refund → REQUESTED … Parent/Teacher **via dispute** or OPS/Admin"; dispute resolution actions `FULL_REFUND`/`PARTIAL_REFUND` "must call refund service and create ledger/event entries" (API §19.4) | Exact mapping of one §12.6 call onto the `REQUESTED → APPROVED → PROVIDER_PENDING` sequence (whether the creating call also records approval, or approval is a separate command) — see §7, D1 | **D9**: no allocation-split input field in the approved §12.6 request while approval requires one (see §7) | Real provider checkout for refunds |
| 3 | **Approval / rejection / cancellation** | States + authorities + events: `REQUESTED → APPROVED` (OPS/Admin; `approved_amount` + `approved_at` + approver required; allocation `teacher + platform = approved_amount` enforced by v1.1 trigger) event `REFUND_APPROVED`; `REQUESTED → REJECTED` event `REFUND_REJECTED`; `REQUESTED`/`APPROVED → CANCELLED` ("No provider refund completed"; "No financial movement") event `REFUND_CANCELLED` — SM §14.3 + Addendum §7.3; v1.3 state-data cleanliness (REQUESTED/REJECTED rows carry no allocation/approval/provider data) | **No approved endpoint contract for approve/reject/cancel commands** exists in API Arch or Addendum (state-machine + UX Flow 32 only) — plan-time contract item (see §7, D1) | — | Auto-approval of any refund (OPS-POL-007 unset behavior: "auto-approval disabled") |
| 4 | **Provider pending** | `APPROVED → PROVIDER_PENDING` via RefundService provider call (SM §14.3); payment → `REFUND_PENDING` (SM §7.6 row: "Refund approved; refund row created … Provider refund call after internal approval"); `provider_submitted_at` + `provider_refund_id` (Addendum §8.4 links it to `refunds.id`); event `REFUND_PROVIDER_SUBMITTED`; **outside the DB transaction** per API §12.6/§29.7 | — | **D1/D3**: how DEV performs/records the provider call (mock initiation contract, event identity) | Real provider refund API |
| 5 | **Provider success** | `PROVIDER_PENDING → SUCCEEDED` via "Provider webhook/reconciliation" (SM §14.3; Addendum §7.3); proof = valid `provider_refund_id` **or** full reconciliation proof (`reconciliation_source/reference/reconciled_at`, `reconciled_by_user_id` for `MANUAL_RECONCILIATION`/`ADMIN_OVERRIDE`) — v1.2/v1.3 constraints + Addendum §7.4; then payment → `REFUNDED` (full: `approved_amount = payment.amount`, trigger-enforced) or `PARTIALLY_REFUNDED` (partial), and **only then** `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` (Addendum §7.4/§14.3; Planning §10.4); balanced reversal/settlement ledger entries (API §12.6 TX2; §14.3); refund-after-PAID-payout → new adjustment/recovery ledger tx (`TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE`), old payout untouched (Addendum §11; v1.4 PAID immutability) | Exact normal-flow ledger entry set (D10 — INFERRED from VS2 late-branch precedent; locked at plan time, balanced by DB constraint) | **D2**: DEV mock success mechanics | Real money movement |
| 6 | **Provider failure** | `PROVIDER_PENDING → FAILED` with `failed_at` + `failure_code`/`failure_message` (schema; v1.2 guard); event `REFUND_FAILED` (Addendum §7.3); "Payment returns to previous financial state or remains `DISPUTED` if dispute still open; Ledger reversal is not posted unless money movement occurred; Admin/OPS notified" (SM §19.5) | — | **D2**: DEV mock failure mechanics (mock failure control? none?) | — |
| 7 | **Reconciliation / retry / recovery** | `POST /admin/refunds/:id/reconcile` — **approved contract** (Addendum §7.3: request `{result, reconciliation_source, reconciliation_reference, reconciled_at, reason, supporting_evidence[]}`, rules, errors, `ADMIN_ACTION` + `REFUND_SUCCEEDED`/`REFUND_FAILED`, payment events only on success, idempotency required, "terminal states cannot be reopened") + approved UX (v1.1 Patch 2) + proof constraints (v1.2/v1.3) + `REFUND_PROVIDER_MODE` default `MANUAL_RECONCILIATION` (Feature Flag Governance); "Reconciliation must detect provider refund and complete internal refund state. This is why `provider_refund_id` and `payment_provider_events` are required" (SM §7.9); provider-event retry `FAILED → PROCESSING` allowed (v1.2 lifecycle) | Reconcile allowed-from state set beyond "Refund must require reconciliation; terminal states cannot be reopened" (plan-time lock) | — | Refund-row retry after `FAILED` (terminal per v1.2 lifecycle; no approved reopen path; recovery would be a new refund row + audit — not specified) |

**Payment-state shadowing (AUTHORITATIVE):** `CONFIRMED → REFUND_PENDING → PARTIALLY_REFUNDED / REFUNDED` (SM §7.3/§7.6; API §23.2); `REFUND_PENDING → CONFIRMED/DISPUTED` on refund failure (SM §7.6); forbidden: `INITIATED → REFUNDED`, `REFUNDED → CONFIRMED`, `CONFIRMED → FAILED` (SM §7.7/§14.3); admin may never set `payment.status = REFUNDED` before refund success (Addendum §16).

**UX display rule (AUTHORITATIVE, v1.1 Patch 1):** "Do not display 'Refunded' unless `refund.status = SUCCEEDED`"; all 7 states have approved parent/admin-facing labels.

---

# 4. Complete refund lifecycle verification (stage-by-stage existence check)

Requirement: verify each stage exists in approved documents; do not assume existence from logic.

| Stage | Exists in approved docs? | Evidence |
|---|---|---|
| Refund eligibility | **YES** | API §12.6 precondition `payment.status in (CONFIRMED, DISPUTED)`; v1.1 trigger payment-state allowlist; SM §17.6 + Addendum §15.4 over-refund bound; UX-AUD-005/Flow 32 |
| Refund creation/request | **YES** | API §12.6 (full contract); Addendum §13.3 (`REFUND_REQUESTED` at row creation); SM §14.3 first row; API §24.1 idempotency |
| Refund approval (internal) | **YES (semantics) / PARTIAL (API contract)** | SM §14.3 + Addendum §7.3 (state, authority, event, data requirements, allocation integrity); **no approve endpoint contract** — plan-time item |
| Refund pending / provider processing | **YES (semantics) / NO (DEV execution)** | SM §14.3 + API §12.6 "Outside DB transaction: call provider refund API"; DEV mock execution mechanism = **UNKNOWN (D1)** |
| Provider success | **YES (semantics + proof rules) / NO (DEV execution)** | SM §14.3, Addendum §7.4, v1.3 `chk_refunds_v1_3_succeeded_proof`; DEV mock success mechanism = **UNKNOWN (D2)** |
| Refund succeeded/issued → payment effect | **YES** | Payment `REFUNDED`/`PARTIALLY_REFUNDED` + `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only after success (Addendum §7.4/§13.3/§14.3); ledger reversal/settlement (API §12.6 TX2); post-payout adjustment/recovery (Addendum §11) |
| Provider failure | **YES (semantics) / NO (DEV execution)** | SM §14.3 + §19.5, Addendum §7.3 (`REFUND_FAILED`), schema failure fields; DEV mock failure mechanism = **UNKNOWN (D2)** |
| Reconciliation | **YES (full approved contract)** | Addendum §7.3 `POST /admin/refunds/:id/reconcile` + UX v1.1 Patch 2 + v1.2/v1.3 proof constraints + `REFUND_PROVIDER_MODE` default `MANUAL_RECONCILIATION` + SM §7.9 |
| Retry (provider-event level) | **YES** | v1.2 provider-event lifecycle `FAILED → PROCESSING`; webhook duplicate/replay rules (SM §7.8, Addendum §8.2/§14.5) |
| Retry (refund-row level after FAILED) | **NO — not specified** | `FAILED` is terminal (v1.2 lifecycle guard); no approved reopen/retry command. Any recovery path is UNKNOWN and must not be invented |
| Recovery (post-paid payout) | **YES (representation + rule) / NO (workflow implemented)** | Addendum §11 + v1.1 accounts + v1.4 PAID immutability ("this patch does not create recovery rows"); workflow is part of refund operations scope |

Conclusion: every lifecycle stage the approved documents define is present and mutually consistent; the only missing pieces are (a) the **DEV mock execution mechanics** (D1–D3) and (b) **plan-time contract/entry locks** (approval/reject/cancel endpoint shape, D10 entry set, reconcile state preconditions). No stage is "assumed to exist merely because it would be logical."

---

# 5. Exact refund-related database objects (v1 → v1.4)

| Object | Layer | Contents (verified in migrations) |
|---|---|---|
| `refunds` table | v1.1 | `payment_id`/`booking_id` (RESTRICT), `dispute_id`, `provider` (`payment_provider`), `refund_type` (`FULL`/`PARTIAL`), `status` (`REQUESTED/APPROVED/PROVIDER_PENDING/SUCCEEDED/FAILED/REJECTED/CANCELLED`, default `REQUESTED`), `requested_amount` (>0), `approved_amount` (≤ requested), `currency` (DZD), **allocation** `teacher_adjustment_amount`/`platform_adjustment_amount` (≥0), `reason` (≥3 chars), `reason_code`, `provider_refund_id` (unique partial index `ux_refunds_provider_refund_id` on `(provider, provider_refund_id)`), **`idempotency_key` NOT NULL UNIQUE (≥16 chars)**, `requested_by_user_id/role`, `approved_by_user_id/role`, `approved_at`/`provider_submitted_at`/`completed_at`/`failed_at`/`rejected_at`/`cancelled_at`, `failure_code`/`failure_message`, `normalized_provider_payload`, `metadata`; CHECKs: status↔timestamp pairings |
| Reconciliation columns | v1.2 (reconstructed) | `reconciliation_source TEXT`, `reconciliation_reference TEXT`, `reconciled_at TIMESTAMPTZ`, `reconciled_by_user_id UUID` + partial index `idx_refunds_reconciliation_source` |
| `validate_refund_integrity()` trigger | v1.1 | Payment found + locked; `booking_id`/`provider`/`currency` match; payment status ∈ (`CONFIRMED`,`DISPUTED`,`REFUND_PENDING`,`PARTIALLY_REFUNDED`); `approved_amount ≤ payment.amount`; for APPROVED/PROVIDER_PENDING/SUCCEEDED: `approved_amount` present, **allocation sum = approved_amount**, `FULL ⇒ approved = payment amount`, `PARTIAL ⇒ approved < payment amount`, **reserved(APPROVED+PROVIDER_PENDING+SUCCEEDED) + new ≤ payment amount** |
| `validate_refund_lifecycle_v1_2()` trigger | v1.2 | Allowed transitions only: `REQUESTED → {APPROVED, REJECTED, CANCELLED}`; `APPROVED → {PROVIDER_PENDING, CANCELLED}`; `PROVIDER_PENDING → {SUCCEEDED, FAILED}`; terminal states cannot be reopened |
| Reconciliation/success-proof guards | v1.2 base + **v1.3 final hardening** | v1.3 constraints (`NOT VALID`) + `validate_refund_hardening_v1_3()`: `provider_refund_id` non-whitespace; reconciliation fields all-or-nothing with non-empty reference + `reconciled_at`; `MANUAL_RECONCILIATION`/`ADMIN_OVERRIDE` ⇒ `reconciled_by_user_id` required; REQUESTED/REJECTED/CANCELLED data cleanliness; **`SUCCEEDED` requires valid `provider_refund_id` OR full reconciliation proof** |
| `payment_provider_events` table | v1.1 | `UNIQUE(provider, provider_event_id)`; `provider_transaction_id`; **`provider_refund_id`**; `event_type TEXT`; `status` (`RECEIVED/PROCESSING/PROCESSED/IGNORED/FAILED/REJECTED`); `payment_id` FK; **`refund_id` FK + partial index `idx_payment_provider_events_refund`**; payload redaction default TRUE; lifecycle guard (v1.2: insert as RECEIVED; `FAILED → PROCESSING` retry allowed; terminal states final) |
| `api_idempotency_keys` table | v1.1 + v1.3 | `UNIQUE(scope, actor_key, idempotency_key)`, `request_hash`, `status PROCESSING/COMPLETED/FAILED`, stored `response_status`/`response_body`, `expires_at` (default +24h); v1.3: insert as PROCESSING, identity fields immutable, `PROCESSING → COMPLETED/FAILED` only, terminal records immutable except retention metadata, terminal requires `response_status` |
| Ledger objects | v1 (+ v1.1 accounts) | `ledger_transactions.transaction_type` incl. **`REFUND`**, `ADJUSTMENT`; `status DRAFT/POSTED/VOIDED`; `ledger_entries` (account types incl. **`REFUND_PAYABLE`**, **`TEACHER_RECOVERABLE`**, **`PLATFORM_REFUND_EXPENSE`**, `PAYMENT_PROVIDER_CLEARING`, …); balanced-tx deferred constraint trigger; entries append-only (no UPDATE/DELETE) |
| Payment-side objects | v1 | `payments.idempotency_key UNIQUE`, `refunded_at`, `UNIQUE(provider, provider_transaction_id)`, one-CONFIRMED-payment-per-booking partial index; `payment_status` enum incl. `REFUND_PENDING/REFUNDED/PARTIALLY_REFUNDED` |
| Event enum | v1 + v1.1 | `REFUND_ISSUED` (v1, **deprecated for new logic** — see §8), `PAYMENT_REFUNDED` (v1); v1.1 adds `REFUND_REQUESTED/APPROVED/PROVIDER_SUBMITTED/SUCCEEDED/FAILED/REJECTED/CANCELLED`, `PAYMENT_PARTIALLY_REFUNDED`, `PAYMENT_RECONCILIATION_REQUIRED` |
| Payout protection | v1.4 | PAID payout rows immutable at DB level; "Post-payout correction remains a separate adjustment/recovery ledger transaction; this patch does not create recovery rows" |

**Refund allocation tables:** no separate allocation table exists — allocation is column-level on `refunds` (verified; nothing else). **Provider event tables:** `payment_provider_events` is the only provider-event store and it carries refund linkage (verified).

**Is the existing v1→v1.4 schema sufficient?** **YES** — AUTHORITATIVE-supported conclusion: the VS6 Candidate Scope Definition dimension 4 and the Post-VS6 audit both verify "No schema change needed"; this audit re-verified every required object/constraint/trigger directly in migrations 001–005. The sole caveat is the reconstructed-v1.2 provenance warning (historical equivalence UNVERIFIED) — a governance-record item, not a functional gap. **REFUND_SCHEMA_READY: YES.**

---

# 6 & 7. Decision items D1–D5, D9 (+ OPS-POL-007 blocking analysis)

For each: exact question · authoritative evidence · current supported behavior · UNKNOWN gap · can implementation proceed without deciding it · recommended decision (only where documents support one). Nothing below invents behavior; recommendations are explicitly flagged `REQUIRES APPROVAL`.

## D1 — DEV/mock refund initiation mechanism (doc D1)

- **Exact question:** In DEV, how is the §12.6 step "Outside DB transaction: call provider refund API" executed and recorded, and how does one `POST /payments/:id/refund` call map onto the `REQUESTED → APPROVED → PROVIDER_PENDING` sequence (incl. approve/reject/cancel command shape)?
- **Authoritative evidence:** API §12.6 (two-transaction boundary; provider call outside tx; roles); Gate Assessment DEV "allowed: test refunds/reconciliation using mock provider events"; Feature Flag Governance `REFUND_PROVIDER_MODE` (default `MANUAL_RECONCILIATION`, values incl. `PROVIDER_API`); mock precedents — VS2 payment mock (`/mock/succeed`/`/mock/fail`, `mock_tx_`/`mock_evt_` identities, DEV-only 403 guard) and VS5 U1 (deterministic MANUAL_OPS/MOCK execution outside tx, DRAFT→POSTED/VOIDED ledger); **code fact:** `MockPaymentProvider.initiate_refund()` is declared and implemented in VS2's `backend/edutrust_api/payments.py` (returns `{"provider_refund_id": "mock_ref_<uuid>", "status": "PROVIDER_PENDING", …}`) but **is not called anywhere** (verified by full-repo grep).
- **Current supported behavior:** None end-to-end. No refund routes exist (`urls.py` verified: 0 refund endpoints); `process_mock_provider_event` accepts only `payment.confirmed`/`payment.failed` (400 otherwise). The only refund rows that can exist in DEV today come from the VS2 late-payment branch (`REQUESTED` FULL only).
- **UNKNOWN gap:** The approved DEV mock-refund contract: (a) whether the §12.6 creating call also records approval (actor = approver) or approval is a separate command; (b) the approve/reject/cancel endpoint contract (absent from API Arch and Addendum; SM §14.3 + UX Flow 32 only); (c) how `REFUND_PROVIDER_MODE` gates the DEV path (under default `MANUAL_RECONCILIATION`, is the row still driven through `PROVIDER_PENDING` before reconciliation — the v1.2 lifecycle guard permits **no** `APPROVED → SUCCEEDED` shortcut, so `PROVIDER_PENDING` must be traversed in all paths); (d) `provider_refund_id` identity for DEV (the `mock_ref_` pattern exists in code only, not in any approved document).
- **Can implementation proceed without deciding it?** **NO** for the provider-processing path. A create-only + read + reconcile slice is mechanically possible, but a refund that is created and never approvable/submittable is not a coherent VS8, and approval (which the slice must include) depends on the same command-mapping decision.
- **Recommended decision (document-supported, REQUIRES APPROVAL):** adopt the established mock pattern — (a) `POST /payments/:id/refund` performs the approved two-transaction §12.6 flow with the actor recorded as approver (`approved_by_* = actor`, `REFUND_APPROVED` in-flow) or via a separate approve command — **choose one at approval**; (b) provider submission via `MockPaymentProvider.initiate_refund` outside the DB transaction with `provider_refund_id = mock_ref_<uuid>`, refund → `PROVIDER_PENDING` + `REFUND_PROVIDER_SUBMITTED`, payment → `REFUND_PENDING`; (c) reject/cancel as audited OPS/ADMIN commands per SM §14.3/UX Flow 32. All elements are drawn only from approved documents/precedents; the combination itself requires approval.

## D2 — Mock provider success/failure mechanics (doc D2 + D3)

- **Exact question:** In DEV, what produces a compliant `SUCCEEDED` row and a compliant `FAILED` row?
- **Authoritative evidence:** v1.3 `SUCCEEDED` proof = `provider_refund_id` OR full reconciliation proof; Addendum §7.3/§7.4 event + payment semantics; SM §19.5 failure behavior; UX Flow 32 ("submit to provider, reconcile provider result"); Gate DEV allowance for mock provider events; `REFUND_PROVIDER_MODE` default `MANUAL_RECONCILIATION` ("Cannot mark refunded before success proof").
- **Current supported behavior:** The **manual reconciliation path is fully contract-approved** (`POST /admin/refunds/:id/reconcile` can lawfully produce both `SUCCEEDED` and `FAILED` with proof — Addendum §7.3 emits `REFUND_SUCCEEDED` **or** `REFUND_FAILED`). The **mock provider-event path exists for nothing refund-related**: the mock provider has no refund success/failure events and no route to deliver them (verified).
- **UNKNOWN gap:** Whether DEV adds mock refund result controls (analogous to `/payments/:id/mock/succeed|fail`, e.g. refund-scoped mock events driving `PROVIDER_PENDING → SUCCEEDED/FAILED` with `provider_refund_id`), uses reconciliation-only (default flag semantics), or both; and which `event_type` strings identify mock refund events (no refund event-type catalogue exists in any document).
- **Can implementation proceed without deciding it?** **Partially.** Reconciliation-only already closes the DEV lifecycle lawfully (row traverses `PROVIDER_PENDING`, then reconcile marks SUCCEEDED/FAILED with proof — no provider event needed). But the approved UX (Flow 32) and the Gate's DEV allowance describe the provider-event path too; choosing "reconciliation only" is itself a scope decision.
- **Recommended decision (document-supported, REQUIRES APPROVAL):** **both** — (a) reconciliation as the default proof path (matches `REFUND_PROVIDER_MODE = MANUAL_RECONCILIATION` default), (b) optional DEV-only mock refund result controls for the provider path, mirroring VS2's mock event discipline (DEV-only guard, duplicate-event replay → 200, conflict → 409). The mock refund `event_type` values (INFERRED-minor, e.g. `refund.succeeded`/`refund.failed` mirroring `payment.confirmed`/`payment.failed` naming) are locked at plan time.

## D3 — Provider refund event/replay model (doc D4)

- **Exact question:** Where are DEV mock refund events recorded, with what identity/uniqueness, and what are replay/conflict semantics?
- **Authoritative evidence:** Addendum §8.1/§8.2/§8.4 (identity separation; `UNIQUE(provider, provider_event_id)`; `provider_refund_id` linked to `refunds.id`); **schema fact:** `payment_provider_events` already carries `provider_refund_id`, `refund_id` FK and the refund partial index (v1.1) — the approved event store is refund-capable; v1.2 event lifecycle guard (insert RECEIVED; terminal states final; FAILED→PROCESSING retry); SM §7.8 replay/conflict semantics for provider events; SM §7.9 ("This is why `provider_refund_id` and `payment_provider_events` are required").
- **Current supported behavior:** Payment-scoped mock events only (`provider='OTHER'`, `mock_evt_<uuid>`, `mock_tx_<payment_id>`). No refund-scoped event is ever written by code.
- **UNKNOWN gap:** The DEV refund-event record model: `event_type` values for refund events; whether mock refund events use the same `payment_provider_events` table (schema says yes-by-capability, no document says yes-by-decision); replay/conflict behavior for refund events (direct analog of §7.8).
- **Can implementation proceed without deciding it?** **Partially** — reconciliation-only needs no refund events; the mock provider path (if approved under D2) needs this.
- **Recommended decision (document-supported, REQUIRES APPROVAL):** record mock refund events in `payment_provider_events` (the only approved provider-event store; refund linkage already present) with `UNIQUE(provider, provider_event_id)` identity, `refund_id` + `provider_refund_id` populated; replay of an already-`PROCESSED` event → 200 with previous result and no state change; conflicting identity/amount → 409 + security/ops event — exactly the §7.8 analog.

## D4 — Reconciliation command/workflow (doc D5)

- **Exact question:** What is the reconciliation command, its semantics, and what may it set?
- **Authoritative evidence — NEW FINDING F1:** the earlier "UNKNOWN — not an approved contract" classification (VS6 Candidate Scope Definition, dimension 13/D5) **does not hold against the current approved baseline**: that document's evidence base predated its use of the Addendum, while **API Contract Addendum v1.1 §7.3 (APPROVED WITH CONDITIONS per Implementation Baseline §3) fully specifies `POST /admin/refunds/:id/reconcile`** — request schema (`result`, `reconciliation_source`, `reconciliation_reference`, `reconciled_at`, `reason`, `supporting_evidence[]`), rules (source required; reference non-empty; `reconciled_at` required; `MANUAL_RECONCILIATION`/`ADMIN_OVERRIDE` require authenticated `reconciled_by_user_id`), error catalogue (`REFUND_NOT_FOUND`, `REFUND_INVALID_STATE`, `REFUND_RECONCILIATION_PROOF_REQUIRED`, `FORBIDDEN`, `IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_KEY_CONFLICT`), events (`ADMIN_ACTION` + `REFUND_SUCCEEDED`/`REFUND_FAILED`; payment refunded events only on success), state restrictions ("Refund must require reconciliation; terminal states cannot be reopened"), idempotency required. Corroborated by approved UX v1.1 Patch 2 (closes UX-AUD-002) and the v1.2/v1.3 proof constraints.
- **Current supported behavior:** Nothing implemented (no route; VS2 late refunds are stranded at `REQUESTED` with no approved DEV path to progress — a real operational gap the Post-VS6 audit flagged).
- **UNKNOWN gap (residual, minor):** the exact allowed-from state set for reconcile ("must require reconciliation" — plausibly `PROVIDER_PENDING` for both results, and pre-submission states only under `MANUAL_RECONCILIATION` mode); whether `result: FAILED` is used for observed provider failures or only reconciliation rejections. These are implementation-level clarifications, not governance unknowns.
- **Can implementation proceed without deciding it?** **YES** — the contract exists; residual semantics are locked at plan time (same treatment as VS5 U1/U2 and VS6 U-items).
- **Recommended decision:** implement Addendum §7.3 verbatim; lock the allowed-from set at plan time. **D4 is RECLASSIFIED from UNKNOWN to RESOLVED (approved contract) by this audit.**

## D5 — Late-refund progression (doc D6)

- **Exact question:** Does VS8 progress the `REQUESTED` FULL refunds seeded by the VS2 late-payment branch, and under what policy?
- **Authoritative evidence:** VS2 branch (implemented/tested): late success → payment `CONFIRMED`, booking stays `EXPIRED`/`CANCELLED`, `PARENT_PAYMENT` ledger (DEBIT `PAYMENT_PROVIDER_CLEARING` / CREDIT `REFUND_PAYABLE`), refund `FULL`/`REQUESTED` (`LATE_PAYMENT_AFTER_EXPIRY`, `idempotency_key = late-refund-<payment_id>`), events `PAYMENT_CONFIRMED` + `PAYMENT_RECONCILIATION_REQUIRED` + `REFUND_REQUESTED`; Addendum §9.3 events list ends "REFUND_REQUESTED or REFUND_APPROVED **depending policy**"; **OPS-POL-003 (OPEN)** — recommended pilot default "Create refund request + OPS review before provider submission"; "What happens if unset: Late payment branch must create reconciliation alert and **block auto-refund**."
- **Current supported behavior:** Late refunds exist and are tested, but **cannot progress** — approve/reject/reconcile do not exist yet.
- **UNKNOWN gap:** None for the slice mechanics: once the D1–D4 refund commands exist, late refunds progress through the **same** commands (OPS review → approve → provider/reconciliation → success). The OPEN question is the *policy value* (auto-approve vs review vs manual-only) — which is OPS-POL-003's, not VS8's; and the current VS2 behavior (request-only, no auto-approve) is exactly the documented "unset" safe behavior.
- **Can implementation proceed without deciding it?** **YES** — with the binding condition that VS8 **must not auto-approve** late refunds (respecting OPS-POL-003 unset behavior). Progression of seeded late refunds should be an explicit VS8 E2E scenario (the natural E2E loop for the reconciliation command).
- **Recommended decision:** include late-refund progression in VS8 scope via the generic commands; no auto-approval; OPS-POL-003 remains OPEN for production.

## D9 — Refund allocation / legal / accounting policy (doc D9)

- **Exact question:** Where does the teacher/platform split enter the refund flow, and who decides the split?
- **Authoritative evidence:** v1.1 trigger: for APPROVED/PROVIDER_PENDING/SUCCEEDED, `teacher_adjustment_amount + platform_adjustment_amount = approved_amount` (hard DB rule); Addendum §10.3 (allocation fields; payout exposure consumes `teacher_adjustment_amount`); UX Flow 32 ("Admin must see allocation … Total allocation equals approved amount"); Addendum §7.2 response carries both allocation fields; **OPS-POL-007 (OPEN POLICY)** — pilot default "OPS/Admin manual allocation with reason codes; **no automatic formula in pilot**"; "What happens if unset: **Refund approval requires manual allocation fields; auto-approval disabled**"; approvers include Legal/Compliance; §12.6 request has **no** allocation field (gap noted in VS6 scope definition dimension 2).
- **Current supported behavior:** Allocation columns are enforced at DB level but **no API input path exists** — an approval with `approved_amount > 0` cannot be lawfully created today through any approved contract.
- **UNKNOWN gap:** the input mechanism: (a) extend `POST /payments/:id/refund` with allocation fields (minor contract addition via the Addendum vehicle), (b) a separate approval command carrying the split, or (c) a fixed DEV default split. Option (c) is **not document-supported** (it would be an allocation formula/policy value, which OPS-POL-007 reserves to its approvers).
- **Can implementation proceed without deciding it?** **NO for the approval step** (and therefore for any refund beyond `REQUESTED`, including the late refunds). Creation, reads, rejection, and cancellation are unaffected (REQUESTED/REJECTED rows carry zero allocation per v1.3).
- **Recommended decision (mechanism only — document-supported, REQUIRES APPROVAL):** the approval action accepts an **actor-specified allocation** (`teacher_adjustment_amount` + `platform_adjustment_amount`, with reason/reason code) supplied by the approving OPS/ADMIN — matching the OPS-POL-007 pilot default ("manual allocation with reason codes") and its unset behavior ("approval requires manual allocation fields; auto-approval disabled"). **The split value itself is a per-transaction operator decision; no default formula is implemented; OPS-POL-007 remains OPEN for production.** The contract vehicle (extend §12.6 request vs separate approval command) is fixed by the D1 choice.

## OPS-POL-007 — is it actually blocking VS8?

**Determination: NOT a hard blocker for the DEV slice; a blocker for production refund allocation behavior.**

- It is OPEN (all 10 policies OPEN; document status READY FOR REVIEW; production policy NOT APPROVED) — AUTHORITATIVE.
- But the policy document itself defines the system's **unset behavior**: "Refund approval requires manual allocation fields; auto-approval disabled." Implementing a DEV slice under that documented fallback requires **no policy approval**: the slice simply (i) provides manual allocation input at approval, (ii) implements no automatic split/auto-approval, (iii) leaves the `REFUND_ALLOCATION_MODE` config decision to the policy approvers.
- What OPS-POL-007 does block: any automatic/default allocation formula, any production allocation semantics, and any relaxation of the manual-allocation requirement. Those are OUT OF SCOPE for a DEV slice.
- The earlier audits' "blocked on OPS-POL-007" framing conflated the **policy value** (OPEN, correctly) with the **DEV slice's ability to proceed** (not actually blocked, given the documented unset behavior). This audit reclassifies accordingly; the genuinely open item inside D9 is the **input mechanism**, which is a contract decision, not a policy approval.

---

# 8. Exact meaning and lifecycle of the six named events

Verified against the `event_type` enum (v1 + v1.1 ALTERs) and the Addendum's event rules. **Two of the six names in the audit brief do not exist as events — flagged, not papered over.**

| Name | Status | Exact meaning / lifecycle |
|---|---|---|
| `REFUND_REQUESTED` | **EXISTS — current, authoritative** | Emitted **immediately when the refund row is created as `REQUESTED`** (Addendum §13.3; v1.1 enum; used by the implemented VS2 late branch). One per refund creation. |
| `REFUND_PROVIDER_PENDING` | **DOES NOT EXIST as an event** | `PROVIDER_PENDING` is a **`refund_status` value** (v1.1 enum), not an event. The event for the `APPROVED → PROVIDER_PENDING` transition is **`REFUND_PROVIDER_SUBMITTED`** (Addendum §7.3: "Refund request sent to provider"). Any implementation or test referencing a `REFUND_PROVIDER_PENDING` event would violate the approved enum. |
| `REFUND_SUCCEEDED` | **EXISTS — current, authoritative** | Emitted on `PROVIDER_PENDING → SUCCEEDED` (Addendum §7.3) when provider or reconciliation confirms money returned; requires the v1.3 proof (`provider_refund_id` OR full reconciliation proof). Only after it may `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` be emitted (Addendum §7.4). |
| `REFUND_FAILED` | **EXISTS — current, authoritative** | Emitted on `PROVIDER_PENDING → FAILED` (Addendum §7.3); row carries `failed_at` + `failure_code/message`; payment returns to previous financial state or remains `DISPUTED`; no ledger reversal posted unless money moved; Admin/OPS notified (SM §19.5). Supersedes SM v1.0 §14.3's "ADMIN_ACTION metadata failure" wording. |
| `REFUND_RECONCILIATION_REQUIRED` | **DOES NOT EXIST anywhere in the repository** (verified by full-repo grep: 0 occurrences) | The actual event is **`PAYMENT_RECONCILIATION_REQUIRED`** (v1.1 enum; Addendum §13.1). Meaning: a **payment-level** fact — money movement requires reconciliation; in the approved baseline it is emitted by the late-payment branch B (Addendum §9.3: with `PAYMENT_CONFIRMED`, when payment success cannot create fulfillment) — the implemented VS2 branch emits it with the new `refund_id` in metadata. It is **not** a refund-status event and does not belong to the 7-state refund lifecycle. |
| `REFUND_ISSUED` | **EXISTS in the enum — DEPRECATED for new logic** | v1.0-era event (API §12.1/§12.6/§22.3/§29.7 and PRD event catalogue predate the Addendum). **Addendum §13.2: "Do not use `REFUND_ISSUED` in new service logic to mean: requested, approved, provider submitted, or succeeded. If old compatibility references exist, treat them as deprecated."** The enum value remains in the DB (v1.1's migration comment records the deprecation; no removal). A VS8 implementation **must not emit** it; API §12.6's "insert event_ledger REFUND_ISSUED" line is overridden by Addendum §13.2/§13.3 per the Addendum's own authority hierarchy (§2) — the same precedence already documented in the VS6 Candidate Scope Definition. |

Full current refund-related event set (11): `REFUND_REQUESTED`, `REFUND_APPROVED`, `REFUND_PROVIDER_SUBMITTED`, `REFUND_SUCCEEDED`, `REFUND_FAILED`, `REFUND_REJECTED`, `REFUND_CANCELLED`, `PAYMENT_REFUNDED`, `PAYMENT_PARTIALLY_REFUNDED`, `PAYMENT_RECONCILIATION_REQUIRED`, plus deprecated `REFUND_ISSUED` (no new use).

---

# 9. Ledger requirements

- **When refund ledger entries are created (approved rules):**
  - Payment confirmation (implemented in VS2 late branch): `PARENT_PAYMENT` tx, POSTED, DEBIT `PAYMENT_PROVIDER_CLEARING` / CREDIT `REFUND_PAYABLE` (refund liability), reference `late-payment-refund-liability` — verified in `services.py`.
  - Normal refund flow (unimplemented): API §12.6 TX1 "create refund intent record **or** `ledger_transaction REFUND` according to approved schema approach"; TX2 "create reversal/settlement ledger entries as needed"; PRD rule "Refunds must create ledger entries."
  - Payout interaction (implemented in VS5): DRAFT `TEACHER_PAYOUT` → POSTED on success / VOIDED on failure (draft-never-posted ⇒ no reversal needed, SM §12.6).
  - Refund after payout PAID (unimplemented workflow): **new** adjustment/recovery ledger transaction with `TEACHER_RECOVERABLE` / `PLATFORM_REFUND_EXPENSE` per allocation; old payout/entries untouched (Addendum §11; v1.4 DB immutability; v1.4: "this patch does not create recovery rows").
- **DRAFT/POSTED/VOIDED semantics (AUTHORITATIVE):** `DRAFT` = created, not yet effective (may be VOIDED without reversal); `POSTED` = effective and immutable; `VOIDED` = cancelled draft. Enforced by `ledger_transaction_status` enum + append-only entries + deferred balance trigger (v1).
- **Allocation:** column-level on `refunds`; `teacher + platform = approved_amount` for APPROVED+ (v1.1 trigger); payout net-payable deducts `teacher_adjustment_amount` of PARTIAL refunds in APPROVED/PROVIDER_PENDING/SUCCEEDED (Addendum §10.1; implemented in VS5).
- **Accounting identity:** every transaction balances `sum(DEBIT) = sum(CREDIT)` — DB deferred constraint trigger (v1); API §14.3.
- **What VS2 already implemented:** only the late-payment liability entry (DEBIT clearing / CREDIT refund payable) — i.e., the *liability representation* for unfulfillable late money. AUTHORITATIVE (verified code + tests).
- **What remains for a complete refund operation (D10 — INFERRED, lock at plan time; balance enforced by DB constraint):** (a) the normal-flow `REFUND` tx entry set on success (analogous to the late-branch liability settlement — exact accounts to be itemized in the plan); (b) the post-paid `ADJUSTMENT` recovery tx using `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` (Addendum §11 example: 300 teacher recoverable / 100 platform expense); (c) DRAFT→POSTED/VOIDED handling mirroring the VS5 payout pattern. None of this is a governance decision — it is a plan-time design lock, consistent with the VS6 scope definition's own D10 treatment.
- **REFUND_LEDGER_READY: YES** (objects, accounts, guards, and immutability all in place; entry set = plan-time lock D10; recovery workflow = in-scope implementation, representation already in place).

---

# 10. Authorization

| Actor | Refund authority (AUTHORITATIVE) |
|---|---|
| PARENT | **No refund processing** (role matrix "Process refund: No"; API §4.1). Tracks status only: PRD "Refund/dispute status can be tracked" / "View refund status" via Addendum §8.1 `refunds[]` on own payments, §8.2 `refund_summary` on own bookings, §8.3 `linked_refunds` on own disputes. Parent may *initiate a request via dispute* (SM §14.3 first row "Parent/Teacher via dispute") — the dispute-open path is implemented (VS4); the refund effect arrives via OPS/ADMIN resolution (§19.4). |
| TEACHER | **No refund processing** (matrix "No"). Sees only economic impact (UX v1.1 Patch 1: "Refund adjustment pending/applied; Recovery balance created" in earnings/payout context; never parent payment details). |
| SUPPORT | **Cannot process refunds/payouts** (API §4.1); may see limited/redacted refund data in `GET /admin/refunds` "if policy allows" (Addendum §7.1); cannot reconcile by default (UX Patch 2). |
| OPS | **Policy-limited processing** (role matrix); `POST /payments/:id/refund` "OPS under policy" (§12.6); approve/reject/cancel per SM §14.3 ("OPS/Admin", "Admin/OPS"); reconcile routine provider records "if policy allows" (UX Patch 2); every action audited (`ADMIN_ACTION`). |
| ADMIN | **Elevated financial override** (§12.6 "ADMIN for elevated financial override"); required for `ADMIN_OVERRIDE` reconciliation, safety/exceptional refund/override (§19.4, UX Patch 2); full refund reads with audited sensitive detail (Addendum §7.2). |
| Provider/System | Refund results arrive via "Provider refund result/System" (SM §7.6/§14.3) — real webhooks OUT OF SCOPE for DEV (gated); DEV equivalent = mock provider events (D1–D3) or manual reconciliation (approved default mode). |

All sensitive admin refund actions/reads generate `ADMIN_ACTION` and/or `SECURITY_EVENT` (API §4.1 global rule; Addendum §7.2; VS5 admin-read audit pattern). **Authorization readiness: YES** — fully specified; no open decisions.

---

# 11. Idempotency and concurrency

**Infrastructure (AUTHORITATIVE, in place):** `api_idempotency_keys` (v1.1) with v1.3 lifecycle (insert `PROCESSING`; identity fields immutable; `PROCESSING → COMPLETED/FAILED` only; terminal records immutable except retention; terminal requires stored `response_status`); `refunds.idempotency_key` NOT NULL UNIQUE; `payments.idempotency_key`; `UNIQUE(provider, provider_event_id)`.

**Expected exact behavior (all AUTHORITATIVE unless noted):**

| Scenario | Required behavior | Source |
|---|---|---|
| Duplicate refund request, **same actor + same idempotency key + same body** | Return the original stored response (replay); no second refund row | API §24.3; Addendum §7.3 error list; VS2/VS5 established pattern |
| **Same key, different body** | `409 IDEMPOTENCY_KEY_CONFLICT` (terminal idempotency record keeps original) | API §24.3; Addendum §7.3 |
| **Missing key** on refund/reconcile | `IDEMPOTENCY_KEY_REQUIRED` | API §24.1 ("Required"); Addendum §7.3 |
| Duplicate refund attempts with **different keys** on the same payment | Serialized by `FOR UPDATE` on payment (and refunds) — "Lock payment + refund + booking" (SM §7.6); the second proceeds only within remaining refundable balance, else rejected by the over-refund guard (`reserved + new ≤ payment.amount`, v1.1 trigger + service check per Addendum §15.4) — "Prevent duplicate refunds" (API §24.1) | SM §7.6/§17.6; Addendum §15.4; v1.1 trigger |
| **Concurrent provider events** (same refund/payment) | Lock/insert `payment_provider_events(provider, provider_event_id)` **before** mutating state (Addendum §15.1); already-`PROCESSED` duplicate event → HTTP 200 with previous result, no re-mutation (SM §7.8); in-flight event → 409 (VS2 pattern); conflicting identity/amount → `409 PAYMENT_PROVIDER_CONFLICT` + security/ops event, event stored rejected/failed for audit (SM §7.8); identity fields never mixed (§14.5) | Addendum §15.1/§14.5; SM §7.8; v1.2 event lifecycle |
| Crash between TX1 and provider call / TX2 | Idempotency record stays `PROCESSING` (replays hit the 409 in-flight guard, never a stale claim — VS5 documented pattern); no partial business state persists | VS5 report pattern; SM §7.9 |
| Retention/expiry | `expires_at` default +24h (schema); **retention periods are OPEN operational parameters** (Addendum §17 #11/#12) — non-blocking for DEV | schema; Addendum §17 |

**Idempotency readiness: YES** (infrastructure + rules complete; retention OPEN but explicitly non-structural per Addendum §17).

---

# 12. Real refund in DEV — forbidden, with the exact approved DEV/mock boundary

**REAL REFUND: FORBIDDEN IN DEV** — exact documented status:

- Gate Assessment (baseline §6: "DEV/STAGING MOCK APPROVED; REAL MONEY BLOCKED"): DEV approved mode `MOCK_PAYMENT_PROVIDER`; allowed list includes "test refunds/reconciliation using mock provider events"; **not allowed: real money, real customer payment credentials, real teacher payouts** (a real refund is a real-money operation). PILOT/PRODUCTION: NOT APPROVED.
- Payment Provider Readiness: provider refund support/refund webhook/partial refund = `REQUIRES PROVIDER CONFIRMATION`; settlement = `REQUIRES LEGAL REVIEW`; implementation status NOT STARTED. No legal approval claimed anywhere.
- Feature Flag Governance: `REFUND_PROVIDER_MODE` default **`MANUAL_RECONCILIATION`** (values `DISABLED`/`MANUAL_RECONCILIATION`/`PROVIDER_API`; `PROVIDER_API` implies a confirmed provider — none exists; "Cannot mark refunded before success proof"); `PAYMENT_PROVIDER_MODE` default `DISABLED`.
- Implemented boundary (VS2/VS5, verified): mock controls are DEV-only (403 unless `MOCK_PAYMENT_PROVIDER_ENABLED` and not `REAL_PAYMENT_ENABLED`); settings `REAL_PAYMENT_ENABLED=false`, `REAL_PAYOUT_ENABLED=false` defaults; slice reports consistently state "Real payment: forbidden / Real payout: forbidden".
- No document defines a separate `REAL_REFUND_ENABLED` flag; the prohibition is carried by the gate boundary + `REAL_PAYMENT_ENABLED` + `REFUND_PROVIDER_MODE` + the not-approved provider/legal status. (This audit records the exact mechanism; it does not invent a new flag.)

**Approved DEV/mock boundary for refunds:** refunds may be created, approved, rejected, cancelled, and reconciled in DEV; provider interaction may only be (a) the mock provider (initiation/result per the D1–D3 decision, mirroring the VS2 payment-mock discipline: DEV-only guard, synthetic identities, no money) or (b) manual/admin reconciliation with proof; success may only be recorded after provider-confirmed or reconciliation-confirmed success (Addendum §7.4; flag forbidden behavior); no real provider credentials, no real money, no real payout interaction.

---

# 13. Can a coherent VS8 be defined now?

## VS8_SCOPE_READY = **NO**

**Reason:** the DEV mock-refund **execution contract** — D1 (initiation/command mapping), D2 (mock success/failure mechanics), D3 (mock refund event identity/replay) — remains genuinely `UNKNOWN`: no approved document contains a mock-refund contract, and the approved documents (Gate Assessment, Feature Flag Governance, Addendum §7.3, SM §7.9, UX Flow 32/Patch 2) require one to exist before the lifecycle can be operated in DEV. Per the project's standing rule (VS6 Candidate Scope Definition: "this plan does not invent"; Post-VS6: "proceeding would force inventing a DEV mock-refund contract, which the approved documents do not contain"), this audit does not invent it.

**Importantly, the open set is materially smaller than previously recorded:**

| Previously recorded blocker | This audit's determination |
|---|---|
| D4/doc D5 reconciliation command = "not an approved contract" | **RESOLVED** — approved contract exists: Addendum v1.1 §7.3 (APPROVED WITH CONDITIONS) + UX v1.1 Patch 2 + v1.2/v1.3 proof rules. Residual allowed-from-state set = plan-time lock |
| OPS-POL-007 = blocking | **NOT a DEV blocker** under the policy doc's own documented unset behavior (manual allocation required; auto-approval disabled). Policy value stays OPEN (legal/accounting) — it blocks production allocation semantics, not the DEV slice |
| D5/doc D6 late-refund progression = open scope decision | **NOT separately blocking** — progression flows through the generic D1–D4 commands; binding condition: no auto-approval (OPS-POL-003 unset behavior); include as a VS8 E2E scenario |
| D9 allocation = OPEN policy blocking | Split into: (a) **input mechanism** — small contract decision, document-supported recommendation available (actor-specified allocation at approval, no formula); (b) **policy value** — remains OPEN, operator-decided per transaction in DEV |
| D10 ledger entry set | Plan-time design lock (INFERRED, DB-balance-enforced) — not a governance decision |

**Minimum decisions required before VS8 can be approved for planning/coding (all `REQUIRES APPROVAL`; document-supported recommendations provided in §7):**

1. **D1** — Approve the DEV mock-refund initiation contract: §12.6 two-transaction execution with `MockPaymentProvider.initiate_refund` outside tx (`mock_ref_<uuid>`), and the create/approve/reject/cancel command mapping (incl. which command carries the D9 allocation input).
2. **D2** — Approve the DEV refund-result mechanics: reconciliation as the default proof path (`REFUND_PROVIDER_MODE = MANUAL_RECONCILIATION`) plus optional DEV-only mock refund success/failure controls mirroring the VS2 payment-mock discipline (or an explicit decision to ship reconciliation-only).
3. **D3** — Approve the DEV mock-refund event record model: `payment_provider_events` with `refund_id`/`provider_refund_id` linkage, `UNIQUE(provider, provider_event_id)`, §7.8-analog replay (200) / conflict (409 + security event), and the mock refund `event_type` values (plan-locked naming).
4. **D9 (mechanism)** — Approve the allocation input mechanism: actor-specified `teacher_adjustment_amount` + `platform_adjustment_amount` + reason code at the approval action; **no automatic split, no auto-approval**; OPS-POL-007 remains OPEN for production.

Plan-time locks (not governance decisions): D10 ledger entry set; reconcile allowed-from state set; reject/cancel endpoint shape (derivable from SM §14.3 + UX Flow 32); mock `event_type` naming.

**If the four decisions are approved, the exact VS8 scope would be** (proposed, conditional, NOT implemented, NOT approved):

```text
VS8 — Refund Operations (DEV)
  1. POST /payments/:id/refund            (OPS policy-limited / ADMIN elevated; §12.6 two-transaction;
                                           idempotency required; creates REQUESTED (+ approval mapping per D1))
  2. Approve / reject / cancel commands    (per D1 mapping; allocation input per D9; events REFUND_APPROVED /
                                           REFUND_REJECTED / REFUND_CANCELLED; payment → REFUND_PENDING on approval)
  3. Mock provider submission + result     (per D1–D3; DEV-only guard; PROVIDER_PENDING; SUCCEEDED/FAILED with
                                           provider_refund_id or — per D2 — reconciliation proof)
  4. POST /admin/refunds/:id/reconcile     (Addendum §7.3 verbatim; ADMIN_ACTION + REFUND_SUCCEEDED/FAILED)
  5. Reads: GET /admin/refunds, GET /admin/refunds/:id (Addendum §7.1/7.2, audited, redacted)
           GET /payments/:id +refunds[], GET /bookings/:id +refund_summary, GET /disputes/:id +linked_refunds
           (Addendum §8; parent own-data scoping)
  6. Ledger: REFUND tx on success (D10 entry set); post-paid ADJUSTMENT recovery tx
           (TEACHER_RECOVERABLE / PLATFORM_REFUND_EXPENSE per allocation); DRAFT/POSTED/VOIDED per VS5 pattern
  7. Events strictly per Addendum §13.1/§13.3 (REFUND_ISSUED never emitted)
  8. Late-refund progression: VS2-seeded REQUESTED late refunds progressed through the same commands
           (E2E scenario; no auto-approval per OPS-POL-003 unset behavior)
  9. DEV console: admin refund list/detail/reconcile + allocation display (UX Flow 32 + Patch 1/2 labels;
           "no 'Refunded' label unless SUCCEEDED")
  10. Tests per Traceability rows: refund lifecycle valid, over-refund blocked (concurrency), partial refund
           allocation, post-payout recovery separate, provider payload redaction; planned artifacts
           test_refund_service.py, test_refund_concurrency.py, e2e_refund_lifecycle.spec.ts,
           e2e_admin_refund_reconciliation.spec.ts
  Boundaries: schema unchanged; state machine unchanged; real refund/payment/payout FORBIDDEN;
  REAL REFUND boundary per §12; no POST /admin/recoveries (Addendum §9.3)
```

No implementation was started by this audit.

---

# 14. Sequencing comparison: Refund Operations vs remaining candidates

Comparison only — no candidate is started or recommended-for-start by this audit. Criteria per the Post-VS6 audit's candidate analysis.

| Candidate (Post-VS6 ID) | Spec completeness | Blocking decisions | DB/API/SM readiness | Financial risk | Standalone? | Sequencing note |
|---|---|---|---|---|---|---|
| **R1 Refund Operations (VS8 candidate)** | H (this audit: §12.6 + Addendum §7/§8 + SM §14 + Addendum §7/§13 + full schema) | **D1, D2, D3 (mock execution contract) + D9 mechanism** — all small, document-supported, approvable in one decision pass | H / H (D9 input item) / H | **H** (ledger money movement even in DEV; mitigated by v1.1–v1.4 guards) | YES | The Post-VS6 proposed sequence places it as VS8 immediately after VS7; it is the dependency for R2's full action list and for R4's paid-cancellation path |
| R2 Dispute Resolution | H for non-financial core (§11.3–11.7, §19.4) | Scope decision (non-financial core vs full list); **full list requires R1** (AUTHORITATIVE: "Refund action must call refund service") + R10 suspension spec (thin/UNKNOWN) | H / H / H | L (core) / H (full) | Core only | Deliverable **without** the D1–D3 decisions — the main decision-light alternative; declared-partial relative to the 11-action list |
| R4 Cancellation (+R5 Reschedule) | M (endpoint + SM §6.3; reschedule rules thin) | Reschedule detail at plan time; paid path couples to R1 | H / M / M | M (refund-eligibility edge) | Pre-payment path only | Pre-payment path is a small standalone slice; paid path waits for R1 |
| R6 Auth completion / R7 Student Passport v0 + CRUD completion / R8 Parent completion / R9 Teacher completion | H (API §3.5/3.7, §7.3–7.5, §6.2–6.3, §8.1–8.4) | None blocking ( Passport v0 = read-only aggregation over existing VS3 data) | H / H / L-M | L | YES | Small, decision-light, no financial risk — alternative next slices if D1–D3 approval is deferred |
| R10 User suspend/reactivate / R11 Ledger admin / R12 Notifications (in-app) / R13 Admin monitoring completion | H (API §21.6, §21.4-area, §20, §21.3/21.5) | R10 operational effects INFERRED; R12 channels OPEN (OPS-POL-009) | H / H / L-M | L | YES (R11 supports R1/R2 post-paid recovery reads) | Fill-in slices; R11's reversal endpoint is ADMIN-only and audit-heavy |
| R15/R16 Background jobs + trust-metrics worker | M (Planning §11; worker spec partly INFERRED) | Worker spec detail at plan time | H | L | YES | Operationally important; spec gap is INFERRED, not governance-OPEN |
| R17 Production UI | H (64 screens approved) | — | — | L | No — a phase | Not a slice candidate |
| R18/R19 Real payment/payout | Spec exists, gated | Legal NOT APPROVED; provider unconfirmed | — | H-H | OUT OF SCOPE until gates | Refund provider capability is inside R18's provider confirmation — cannot unblock D1–D3 on real-provider terms |

**Sequencing conclusion (comparison only):** Refund Operations remains the proposed VS8 in the documented proposed sequence and is the enabling dependency for R2-full and R4-paid. It is currently the **only major financial workstream blocked on decisions**, and those decisions (D1–D3 + D9-mechanism) are small, document-supported, and mutually dependent — approvable in a single decision pass, after which VS8 is scope-ready with **no** schema/state-machine/architecture changes. If the decision pass is deferred, the decision-light candidates (R2 non-financial core; R6/R7/R8/R9; R10/R11/R12/R13) rank ahead of it on the same criteria the Post-VS6 audit applied — that re-ranking is a sequencing decision for the project, not a recommendation made by this audit.

---

# 15. Final decision table

| Item | Status | Classification / note |
|---|---|---|
| **D1** (doc D1) — DEV/mock refund initiation mechanism | **OPEN — BLOCKING** | UNKNOWN. `initiate_refund` primitive exists in code (unused); mock precedents + Gate allowance support a recommendation (REQUIRES APPROVAL). Includes approve/reject/cancel command-mapping |
| **D2** (doc D2+D3) — mock provider success/failure mechanics | **OPEN — BLOCKING** | UNKNOWN. Reconciliation-only can close the lifecycle lawfully today (approved §7.3); mock result controls unspecified; `event_type` naming plan-lock. Recommendation: both (REQUIRES APPROVAL) |
| **D3** (doc D4) — provider refund event/replay model | **OPEN — BLOCKING (minor)** | UNKNOWN. Store is schema-ready (`payment_provider_events` refund linkage verified); identity/replay semantics need the §7.8-analog decision (REQUIRES APPROVAL) |
| **D4** (doc D5) — reconciliation command/workflow | **RESOLVED** | **NEW FINDING F1:** approved contract Addendum v1.1 §7.3 + UX v1.1 Patch 2 + v1.2/v1.3 proof rules. Residual allowed-from-state set = plan-time lock. Previously recorded as UNKNOWN — corrected |
| **D5** (doc D6) — late-refund progression | **NOT BLOCKING** | Covered by generic commands; condition: no auto-approval (OPS-POL-003 unset behavior); include as VS8 E2E scenario. Policy value stays OPEN |
| **D9** (doc D9) — refund allocation / legal / accounting | **PARTIALLY OPEN — BLOCKING (mechanism only)** | Input mechanism: document-supported recommendation (actor-specified allocation at approval; no formula; REQUIRES APPROVAL). Policy value: OPEN via OPS-POL-007 (legal/accounting) — operator-decided per transaction in DEV |
| **OPS-POL-007** | **OPEN POLICY — NOT a DEV blocker** | Unset behavior is documented and DEV-safe: "Refund approval requires manual allocation fields; auto-approval disabled". Blocks production allocation semantics and any automatic split; does not block the DEV slice |
| **Schema readiness** | **YES** | v1→v1.4 verified object-by-object (§5); no change needed; v1.2 provenance caveat non-functional |
| **API readiness** | **YES** | Approved contracts: §12.6 create, Addendum §7.1/7.2/7.3 reads + reconcile, §8 summaries. Contingent items: D9 allocation input (D1-vehicle) + reject/cancel command shape (plan-time, derivable from SM §14.3 + UX Flow 32). No redesign needed |
| **State-machine readiness** | **YES** | Addendum §7 (states/events/forbidden) + §13 + SM §14 + v1.2 lifecycle guard; complete and consistent |
| **Ledger readiness** | **YES** | Types/accounts/immutability/balance in place; VS2 liability entry implemented; D10 entry set = plan-time lock; post-paid recovery workflow = in-scope implementation (representation in place, v1.4) |
| **Provider/mock readiness** | **NO** | D1–D3 open; `initiate_refund` unused; no refund mock events; reconciliation path is the only lawfully operable result path today |
| **Authorization readiness** | **YES** | Fully specified (§10): PARENT/TEACHER none, SUPPORT view-limited, OPS policy-limited, ADMIN elevated, provider/system via events/reconciliation; audit rules explicit |
| **Idempotency readiness** | **YES** | Infrastructure + exact replay/conflict/concurrency behavior specified (§11); retention periods OPEN but non-structural (Addendum §17) |
| **E2E readiness** | **NO** | No refund E2E exists; planned artifacts named in the approved Traceability Matrix (`e2e_refund_lifecycle.spec.ts`, `e2e_admin_refund_reconciliation.spec.ts`, plus `test_refund_service.py`, `test_refund_concurrency.py`) — a VS8 delivery obligation, not a decision blocker |

---

# 16. Document record

This audit created exactly one file: `EduTrust_VS8_Refund_Operations_Scope_Governance_Audit_v1.0.md` (this document). No other file was created or modified. No database, API, code, state machine, or architecture was touched. No commit was created. No push was performed. `main` was not touched.

Key findings register:

- **F1:** The reconciliation command is fully contract-approved (Addendum v1.1 §7.3 + UX v1.1 Patch 2) — correcting the earlier "not an approved contract" record.
- **F2:** OPS-POL-007 is not a DEV-slice blocker under its own documented unset behavior; only the allocation **input mechanism** (D9) needs a contract decision; the policy value stays OPEN.
- **F3:** The DEV mock-refund execution contract (D1–D3) remains the genuine UNKNOWN set blocking VS8 scope-readiness; the code's unused `MockPaymentProvider.initiate_refund` and the VS2/VS5 mock precedents document-supported-recommend a decision but do not approve one.
- **F4:** Event-name verification: `REFUND_PROVIDER_PENDING` is a state (event = `REFUND_PROVIDER_SUBMITTED`); `REFUND_RECONCILIATION_REQUIRED` does not exist (actual = `PAYMENT_RECONCILIATION_REQUIRED`); `REFUND_ISSUED` is deprecated for new logic per Addendum §13.2 and must not be emitted by VS8.
- **F5:** Schema is 100% sufficient (no change needed); the API surface is contract-ready apart from the D9 allocation input and reject/cancel command shape; state machines, ledger, authorization, and idempotency are ready; provider/mock and E2E are not.

---

# 17. Final status

```text
VS7:                          COMPLETE
VS8_IMPLEMENTATION:           NOT STARTED
VS8_SCOPE_READY:              NO
REFUND_SCHEMA_READY:          YES
REFUND_API_READY:             YES   (contingent items: D9 allocation input; reject/cancel command shape — plan-time)
REFUND_STATE_MACHINE_READY:   YES
REFUND_LEDGER_READY:          YES   (D10 entry set = plan-time lock; post-paid recovery workflow = in-scope implementation)
REFUND_PROVIDER_DEV_READY:    NO    (D1–D3 open)
OPEN_DECISIONS:               D1 (DEV mock refund initiation + create/approve/reject/cancel command mapping) ·
                              D2 (DEV mock refund success/failure mechanics — or explicit reconciliation-only decision) ·
                              D3 (DEV mock refund event identity/replay model in payment_provider_events) ·
                              D9-mechanism (allocation input at approval — actor-specified, no formula) ·
                              (plan-time locks, not governance decisions: D10 ledger entry set; reconcile allowed-from
                              state set; reject/cancel endpoint shape; mock refund event_type naming) ·
                              (OPEN policies, not DEV blockers: OPS-POL-007 allocation value; OPS-POL-003 late-payment
                              mode)
REAL_REFUND:                  FORBIDDEN IN DEV (Gate: DEV = mock provider only, "real money" not allowed;
                              REFUND_PROVIDER_MODE default MANUAL_RECONCILIATION; provider refund capability
                              REQUIRES PROVIDER CONFIRMATION; no legal approval)
REAL_PAYMENT:                 FORBIDDEN
REAL_PAYOUT:                  FORBIDDEN
DATABASE_MODIFIED:            NO
API_MODIFIED:                 NO
CODE_MODIFIED:                NO
COMMIT_CREATED:               NO
PUSH_PERFORMED:               NO
```

**STOP after the audit. VS8 is NOT started. No implementation is recommended until the OPEN_DECISIONS above are explicitly decided and approved.**
