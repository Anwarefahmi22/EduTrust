# EduTrust — VS8 Refund Operations Implementation Plan v1.0

**Document type:** Implementation plan only. NO implementation, no code, no migrations, no architecture/API/state-machine/UX change, no commits, no pushes.
**Audited lineage:** `Anwarefahmi22/EduTrust` @ `arena/01a03280-edutrust` @ `157a54da48329319deafc8c52a1f065a2b20cc5f` (VS7 complete and pushed; `main` = `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` untouched).
**Governing documents:** VS8 Scope & Governance Audit v1.0 (this repo) + approved baseline set per Implementation Baseline v1.0 (PRD, API Architecture v1.0, API Contract Addendum v1.1 (APPROVED WITH CONDITIONS), State Machines v1.0 + v1.1 Addendum, schema v1→v1.4 migrations, UX v1.0 + v1.1 Patch, Feature Flag Governance, Payment Provider Gate Assessment, Product/Ops Policy Decisions, Test Traceability Matrix).
**Classification legend:** `AUTHORITATIVE` = stated in an approved document · `INFERRED/PLAN-LOCK` = derived from approved documents and locked by this plan (no new behavior invented) · `OUT OF SCOPE` = excluded by an approved boundary or by this plan's explicit out-of-scope list.

---

# 1. Approved governance decisions (input to this plan) and closure verification

## 1.1 Approved decisions (verbatim summary of the governance approval)

| ID | Decision | Approved position |
|---|---|---|
| **D1** | DEV mock refund initiation | Admin/OPS-initiated DEV-only refund operation through the existing refund service boundary and the already-existing `MockPaymentProvider.initiate_refund()` primitive. No real refund providers, no real credentials, no real money, no new provider architecture |
| **D2** | Mock refund result mechanics | DEV mock provider supports deterministic **SUCCESS** and **FAILURE** only. No additional provider result states invented. The approved reconciliation endpoint/workflow remains available for the documented reconciliation cases |
| **D3** | Mock refund provider event model | Reuse the existing `payment_provider_events` infrastructure where supported by the schema. No new refund-event table unless the approved schema demonstrably cannot support the contract. **No new event enum values.** `REFUND_PROVIDER_PENDING` is a STATE (event = `REFUND_PROVIDER_SUBMITTED`). There is NO `REFUND_RECONCILIATION_REQUIRED` event (use `PAYMENT_RECONCILIATION_REQUIRED` where the approved contract requires it). `REFUND_ISSUED` is DEPRECATED for new logic and MUST NOT be emitted by VS8 |
| **D9** | Refund allocation mechanism | Allocation explicitly supplied by the authorized Admin/OPS actor at the applicable approval/reconciliation operation. No automatic allocation formula. No undocumented legal/accounting derivations. OPS-POL-007 policy value unmodified. Mechanism must preserve existing accounting/ledger constraints and reject invalid allocation per the approved schema/contract |

**Final governance boundaries:** REAL REFUND = FORBIDDEN · REAL PAYMENT = FORBIDDEN · REAL PAYOUT = FORBIDDEN · DEV MOCK ONLY = YES · AUTOMATIC REFUND ALLOCATION = NO · AUTOMATIC PROVIDER EXECUTION = NO · NEW REFUND EVENT ENUM = NO · NEW REFUND TABLE = NO (unless demonstrably required) · SCHEMA MIGRATION = FORBIDDEN (unless an approved contract demonstrably requires it) · VS9 = NOT STARTED.

## 1.2 Read-only closure verification (performed for this plan; no modifications)

| Decision | Verified evidence (read-only) | Closed? |
|---|---|---|
| D1 | `MockPaymentProvider.initiate_refund()` exists in `backend/edutrust_api/payments.py` (returns `{"provider_refund_id": "mock_ref_<uuid>", "status": "PROVIDER_PENDING", …}`); refund service boundary exists (`services.py`); DEV-only guard pattern exists (`settings.MOCK_PAYMENT_PROVIDER_ENABLED` / `settings.REAL_PAYMENT_ENABLED`, `services.py` line ~661); no real provider code exists | **YES** |
| D2 | Deterministic SUCCESS/FAILURE mechanics have an approved analog in the VS2 mock controls (`/payments/<id>/mock/succeed|fail`); reconciliation contract (Addendum §7.3) verified in the approved Addendum; no other result states exist or are needed | **YES** |
| D3 | `payment_provider_events` demonstrably supports refund events in the approved schema (v1.1): `refund_id UUID REFERENCES refunds(id)`, `provider_refund_id TEXT`, `UNIQUE(provider, provider_event_id)`, `event_type TEXT` (provider-event kind column — **not** an enum), partial index on `refund_id`; v1.2 lifecycle guard supports the record flow. All required `event_ledger` values already exist in the `event_type` enum (verified in migrations 001/002: `REFUND_REQUESTED/APPROVED/PROVIDER_SUBMITTED/SUCCEEDED/FAILED/REJECTED/CANCELLED`, `PAYMENT_REFUNDED`, `PAYMENT_PARTIALLY_REFUNDED`, `PAYMENT_RECONCILIATION_REQUIRED`, `ADMIN_ACTION`). **No new refund table and no new enum value is required** | **YES** |
| D9 | Allocation columns + integrity trigger verified in v1.1 (`teacher_adjustment_amount + platform_adjustment_amount = approved_amount` for APPROVED+; non-negative CHECKs); `OPS-POL-007` document byte-identical to HEAD (0-line diff — policy value unmodified); no automatic formula exists anywhere | **YES** |

**Result: D1, D2, D3, D9 are CLOSED. VS8_SCOPE_READY: YES.** All other audit preconditions held (schema/API/state-machine/ledger/authorization/idempotency readiness verified in the audit; no schema change is required, so the SCHEMA MIGRATION = FORBIDDEN boundary is satisfied by doing nothing).

## 1.3 Scope summary

VS8 implements the **Refund Operations** workstream (R1) in DEV: admin/OPS-initiated refund creation, approval (with actor-supplied allocation), rejection, cancellation, deterministic mock provider submission + result (success/failure), the approved reconciliation command, refund read endpoints (admin + embedded parent summaries), the refund ledger behavior (incl. post-paid adjustment/recovery representation), late-refund progression, and the DEV console surface — strictly on the existing schema, state machines, API baseline, and mock boundary. No real money. No migrations.

---

# 2. Exact endpoints

All paths under `/api/v1`. Response envelope and error format per API §5.2/§5.3 (existing). Auth = Bearer access token (existing). Request ID per §2.5 (existing).

## 2.1 New endpoints (7)

| # | Method & path | Actor(s) | Purpose | Idempotency |
|---|---|---|---|---|
| E1 | `POST /payments/<uuid:payment_id>/refund` | OPS, ADMIN | Create refund (`REQUESTED`) per API §12.6 | **Required** (`refund-<uuid-v4>`; scope `refund_create`) |
| E2 | `POST /admin/refunds/<uuid:refund_id>/approve` | OPS, ADMIN | `REQUESTED → APPROVED → PROVIDER_PENDING` (mock submission); payment → `REFUND_PENDING`; DRAFT ledger; allocation input (D9) | **Required** (scope `refund_approve`) |
| E3 | `POST /admin/refunds/<uuid:refund_id>/reject` | OPS, ADMIN | `REQUESTED → REJECTED` | **Required** (scope `refund_reject`; PLAN-LOCK: strengthened from "Recommended" in SM §14.3 for consistency) |
| E4 | `POST /admin/refunds/<uuid:refund_id>/cancel` | OPS, ADMIN | `REQUESTED`/`APPROVED → CANCELLED` (pre-provider only) | **Required** (scope `refund_cancel`; per SM §14.3 "Required") |
| E5 | `POST /admin/refunds/<uuid:refund_id>/mock/succeed` | OPS, ADMIN (**DEV-only** — 403 unless `MOCK_PAYMENT_PROVIDER_ENABLED` and `not REAL_PAYMENT_ENABLED`) | Deterministic mock provider **SUCCESS**: `PROVIDER_PENDING → SUCCEEDED` + payment update + ledger POST | Not via idempotency table — **provider-event identity** (`provider_event_id`) is the idempotency mechanism (VS2 pattern; Addendum §8.2) |
| E6 | `POST /admin/refunds/<uuid:refund_id>/mock/fail` | OPS, ADMIN (**DEV-only**) | Deterministic mock provider **FAILURE**: `PROVIDER_PENDING → FAILED` + payment restore + ledger VOID | Same as E5 |
| E7 | `POST /admin/refunds/<uuid:refund_id>/reconcile` | OPS, ADMIN (**ADMIN required when `reconciliation_source = ADMIN_OVERRIDE`**) | Manual/admin reconciliation per Addendum v1.1 §7.3 (SUCCEEDED or FAILED with proof) | **Required** (scope `refund_reconcile`) |
| E8 | `GET /admin/refunds` | OPS, ADMIN | Refund list per Addendum §7.1 (query: `status`, `provider`, `dispute_id`, `payment_id`, `from`, `to`, `limit`, `cursor`; cursor pagination; no raw provider payload in list; no event per ordinary list read per §7.1) | n/a (read) |
| E9 | `GET /admin/refunds/<uuid:refund_id>` | OPS, ADMIN | Full refund detail per Addendum §7.2 (redacted provider/reconciliation summary, timeline, `provider_event_summary[]`; optional `include_provider_summary=true` — never raw payload; **sensitive access audited**: `ADMIN_ACTION` + `SECURITY_EVENT` `ADMIN_ACCESS` severity 2, VS5 pattern) | n/a (read) |

(E8/E9 are the read half of "7 write + 2 read" — all nine rows above are new; E1–E7 state-changing, E8–E9 read.)

## 2.2 Extended endpoints (additive JSON fields only, per Addendum §8 — no behavior change)

| # | Method & path | Additive field(s) | Actor(s) (unchanged) |
|---|---|---|---|
| X1 | `GET /payments/<uuid:payment_id>` | `refunds[]` summary when refund activity exists (per §8.1: `refund_id`, `status`, `refund_type`, `requested_amount`, `approved_amount`, `currency`, `reason`, `created_at`, `approved_at`, `provider_submitted_at`, `completed_at`); parent sees only own payments; teacher never receives parent payment details (existing scoping) | PARENT (own), OPS, ADMIN (existing) |
| X2 | `GET /bookings/<uuid:booking_id>` | `refund_summary` when applicable (per §8.2: `has_refund_activity`, `active_refund_status`, `total_approved_refund_amount`, `currency`) | existing actors |
| X3 | `GET /disputes/<uuid:dispute_id>` | `linked_refunds[]` when applicable (per §8.3: `refund_id`, `status`, `approved_amount`, `currency`) | existing actors |

## 2.3 Request/response contracts (exact)

**E1 — create.** Request: `{ "amount": "2000.00", "currency": "DZD", "reason": "Teacher no-show confirmed", "dispute_id": "<uuid, optional>" }` — field semantics per §12.6 (amount string decimal, DZD; `reason` ≥3 chars; `dispute_id` must belong to the same booking if provided — PLAN-LOCK validation). Response 201: `{ "data": { "refund_id", "payment_id", "booking_id", "status": "REQUESTED", "requested_amount", "currency", "reason", "reason_code": null, "created_at" }, "request_id" }`.

**E2 — approve.** Request: `{ "approved_amount": "1000.00", "teacher_adjustment_amount": "700.00", "platform_adjustment_amount": "300.00", "reason_code": "SESSION_QUALITY (optional)" }`. **Allocation is actor-supplied here (D9) — there is no default, no pre-fill, no formula.** Response 200: refund detail incl. `status: "PROVIDER_PENDING"`, allocation fields, `provider_refund_id`, `payment_status: "REFUND_PENDING"`.

**E3 — reject.** Request: `{ "reason": "…" (≥3 chars) }`. Response 200: refund detail `status: "REJECTED"`.

**E4 — cancel.** Request: `{ "reason": "… (≥3 chars)" }`. Response 200: refund detail `status: "CANCELLED"` (+ `payment_status` if restored).

**E5/E6 — mock results.** Request: `{ "provider_event_id": "optional; defaults to mock_evt_<uuid>" }`. **No amount/currency in the body** — the event amount is derived from `refund.approved_amount` (PLAN-LOCK; mirrors VS2, where the mock event amount is derived from the payment row). Response 200: `{ "data": { "duplicate": bool, "provider_event_id", "refund_status", "payment_status", "refund_id" }, "request_id" }`.

**E7 — reconcile.** Request (Addendum §7.3, verbatim shape): `{ "result": "SUCCEEDED"|"FAILED", "reconciliation_source": "MANUAL_RECONCILIATION" (required, non-empty text; `ADMIN_OVERRIDE` ⇒ ADMIN only), "reconciliation_reference": "BANK-REF-12345" (required, non-whitespace), "reconciled_at": "2026-09-05T16:00:00Z" (required), "reason": "Manual bank confirmation received." (≥3 chars), "supporting_evidence": [ {"type": "document_reference", "id": "evidence_123"} ] (optional references only — never raw payloads) }`. `reconciled_by_user_id` is **derived from the authenticated actor, never client-supplied** (Addendum §7.3; UX Patch 2). Response 200: refund detail after reconciliation (incl. `reconciliation` block + `payment_status`).

**E8/E9.** Response shapes exactly per Addendum §7.1/§7.2 (list item fields; detail `timeline` block with the 7 timestamps; `provider_event_summary[]` from `payment_provider_events` rows linked by `refund_id`, redacted: `provider_event_id`, `event_type`, `status`, `received_at`, `processed_at` — no `normalized_payload`/raw payload).

## 2.4 Error catalogue (VS8)

| Code | HTTP | When |
|---|---|---|
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Missing `Idempotency-Key` on E1–E4, E7 (existing helper behavior) |
| `IDEMPOTENCY_KEY_CONFLICT` | 409 | Same key, different body hash (existing helper behavior; Addendum §7.3 catalogue) |
| `IDEMPOTENCY_REQUEST_PROCESSING` | 409 | Same key in-flight (existing helper behavior) |
| `VALIDATION_ERROR` | 400 | Bad amount/currency/reason shapes; key length <16 (schema CHECK, pre-validated); `approved_amount > requested_amount`; **allocation sum ≠ approved_amount or negative component (D9)**; reconcile proof fields missing/whitespace (`REFUND_RECONCILIATION_PROOF_REQUIRED` per Addendum §7.3 catalogue, 400) |
| `RESOURCE_NOT_FOUND` | 404 | Unknown payment/refund (`REFUND_NOT_FOUND` semantics per Addendum §7.3) |
| `FORBIDDEN` | 403 | Role not authorized (incl. SUPPORT/PARENT/TEACHER on any E1–E7); OPS on `ADMIN_OVERRIDE` reconcile; mock controls outside DEV guard |
| `REFUND_INVALID_STATE` | 409 | Transition precondition failed (wrong refund status; payment not in `CONFIRMED`/`DISPUTED` for E1; reconcile on non-`PROVIDER_PENDING`; mock result on non-`PROVIDER_PENDING`) — per Addendum §7.3 catalogue |
| `OVER_REFUND` | 409 | `reserved(APPROVED+PROVIDER_PENDING+SUCCEEDED) + approved_amount > payment.amount` (SM §17.6; Addendum §15.4; v1.1 trigger backstop) |
| `PAYMENT_PROVIDER_EVENT_IN_PROGRESS` | 409 | Event already being processed (VS2 pattern) |
| `PAYMENT_PROVIDER_CONFLICT` | 409 | Conflicting provider identity/amount (SM §7.8) + `SECURITY_EVENT` `SUSPICIOUS_ACTIVITY` |
| `DB constraint exceptions` | 409/422 (mapped) | `validate_refund_integrity` / lifecycle / v1.3 hardening triggers fire → mapped to `REFUND_INVALID_STATE` with the DB message (defense-in-depth; service pre-checks should make these unreachable in normal flow) |

---

# 3. Exact refund state transitions

Refund states (AUTHORITATIVE, Addendum §7.2 / v1.1 enum): `REQUESTED, APPROVED, PROVIDER_PENDING, SUCCEEDED, FAILED, REJECTED, CANCELLED`. Payment shadow states: `CONFIRMED/DISPUTED → REFUND_PENDING → REFUNDED | PARTIALLY_REFUNDED` (SM §7.3/§7.6); restore on failure/cancel (SM §7.6 row `REFUND_PENDING → CONFIRMED/DISPUTED`).

| From | To | Command (actor) | Preconditions (exact) | Payment effect | Ledger effect | Event(s) (exact set) |
|---|---|---|---|---|---|---|
| — | `REQUESTED` | E1 (OPS/ADMIN) | Payment status ∈ (`CONFIRMED`, `DISPUTED`) **per §12.6 contract** (PLAN-LOCK; the wider DB trigger allowlist remains as defense-in-depth only); `amount ≤ remaining refundable` under payment lock; `reason` valid; optional `dispute_id` belongs to same booking | none (stays `CONFIRMED`/`DISPUTED`) | none | `REFUND_REQUESTED` (refund entity) + `ADMIN_ACTION` (refund entity) |
| `REQUESTED` | `APPROVED` | E2 step 1 (OPS/ADMIN) | `approved_amount ≤ requested_amount`; `teacher ≥ 0`, `platform ≥ 0`, **`teacher + platform = approved_amount`** (service pre-check + v1.1 trigger); over-refund bound under lock; refund locked `FOR UPDATE` | payment → `REFUND_PENDING`; store `metadata.payment_status_before_refund` | DRAFT `REFUND` tx + balanced entries (form per §7) | `REFUND_APPROVED` + `ADMIN_ACTION` |
| `APPROVED` | `PROVIDER_PENDING` | E2 step 2 (RefundService, mock provider call **outside** the DB tx per §12.6/§29.7) | `initiate_refund()` returned `provider_refund_id` | none further | none (DRAFT tx already exists) | `REFUND_PROVIDER_SUBMITTED` (metadata: `provider_refund_id`, `dev_mock: true`) |
| `PROVIDER_PENDING` | `SUCCEEDED` | E5 mock success **or** E7 reconcile `result=SUCCEEDED` | Provider event identity valid (`provider_refund_id` linkage, Addendum §8.4) **or** full reconciliation proof (v1.3: source+reference+reconciled_at, user for MANUAL/ADMIN sources); amount/currency match | → `REFUNDED` if cumulative SUCCEEDED = `payment.amount` (full), else `PARTIALLY_REFUNDED` (partial); `refunded_at = now()` (SM §14.4/14.5) | DRAFT tx → `POSTED` | `REFUND_SUCCEEDED` + (`PAYMENT_REFUNDED` \| `PAYMENT_PARTIALLY_REFUNDED`) + `ADMIN_ACTION` (E7 adds its own `ADMIN_ACTION` per §7.3; E5 mock control: `ADMIN_ACTION` as an admin operation) |
| `PROVIDER_PENDING` | `FAILED` | E6 mock failure **or** E7 reconcile `result=FAILED` | Failure captured: `failed_at` (+ `failure_code`/`failure_message`; reconcile path: proof fields also recorded) | **Restore** to `metadata.payment_status_before_refund` (`CONFIRMED` or `DISPUTED`) (SM §19.5) | DRAFT tx → `VOIDED` ("Ledger reversal is not posted unless money movement occurred" — SM §19.5) | `REFUND_FAILED` + `ADMIN_ACTION` (no `PAYMENT_*` event — Addendum §7.4: payment events only on success) |
| `REQUESTED` | `REJECTED` | E3 (OPS/ADMIN) | Refund `REQUESTED`; rejection reason recorded in `metadata.rejection_reason` | none | none ("No financial movement" — SM §14.3) | `REFUND_REJECTED` + `ADMIN_ACTION` |
| `REQUESTED` \| `APPROVED` | `CANCELLED` | E4 (OPS/ADMIN) | "No provider refund completed" (SM §14.3) — i.e. refund not yet `PROVIDER_PENDING`/terminal; cancellation reason in `metadata.cancellation_reason` | if from `APPROVED` (payment is `REFUND_PENDING`): restore to `metadata.payment_status_before_refund`; else none | if DRAFT tx exists (from `APPROVED`): → `VOIDED`; else none | `REFUND_CANCELLED` + `ADMIN_ACTION` |

**Terminal states** (`SUCCEEDED/FAILED/REJECTED/CANCELLED`) cannot be reopened (v1.2 lifecycle guard; Addendum §7.3 "terminal states cannot be reopened"). **No retry/reopen of a `FAILED` refund exists** (not in any approved transition set) — recovery is a **new** refund request via E1 (see §13).
**Forbidden (enforced by v1.2 lifecycle trigger + service checks, AUTHORITATIVE):** any transition not in the table above; `payment.status = REFUNDED` before refund success (Addendum §16); emitting `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` before success (Addendum §7.4/§14.3; Planning §10.4).

---

# 4. Exact provider/mock flow

Provider object: `MockPaymentProvider` (existing, `backend/edutrust_api/payments.py`) — the **only** provider in VS8. No real provider, no real credentials, no real money (Gate Assessment DEV boundary; settings `REAL_PAYMENT_ENABLED=false`, `REAL_PAYOUT_ENABLED=false` defaults unchanged; no new provider architecture).

**Submission (inside E2, deterministic, in-process):**

```text
TX1 (COMMIT): [§3 approve step 1 — refund APPROVED, payment REFUND_PENDING, DRAFT ledger, events]
Outside any DB transaction:
    result = MockPaymentProvider().initiate_refund(payment_id, approved_amount, currency)
    → {"provider_refund_id": "mock_ref_<uuid>", "status": "PROVIDER_PENDING", ...}   (existing primitive, D1)
TX2 (COMMIT): lock refund FOR UPDATE (must still be APPROVED)
    → insert payment_provider_events (provider = payment.provider — 'OTHER' for mock, per VS2 identity
      convention; provider_event_id = "mock_evt_<uuid>"; provider_refund_id; refund_id;
      event_type = 'refund.initiated'  [provider-event kind in the TEXT column — NOT an event_ledger
      enum value; D3: no enum change]; status RECEIVED → PROCESSING (attempts 1) → PROCESSED
      [three-step per v1.2 lifecycle guard and VS2 pattern])
    → refund: status PROVIDER_PENDING, provider_refund_id, provider_submitted_at = now()
    → event_ledger REFUND_PROVIDER_SUBMITTED
    → _idempotency_complete('refund_approve', …, 200, response)   [atomic with TX2 — VS5 crash-safe pattern]
```

**Crash window (documented):** process death between TX1 and TX2 leaves the refund `APPROVED`, payment `REFUND_PENDING`, DRAFT ledger, idempotency `PROCESSING`. Same-key replays receive 409 `IDEMPOTENCY_REQUEST_PROCESSING` (never a stale claim). Operator recovery uses only approved transitions: E4 cancel (APPROVED→CANCELLED) + new E1 request. PLAN-LOCK: no re-drive endpoint is added (none is approved).

**Result (E5/E6, deterministic mock provider event — D2):**

```text
DEV guard: 403 FORBIDDEN unless MOCK_PAYMENT_PROVIDER_ENABLED and not REAL_PAYMENT_ENABLED (VS2 pattern)
TX (single):
  1. Lock/insert provider event by (provider='OTHER', provider_event_id) FOR UPDATE   [VS2 pattern;
     Addendum §15.1: event identity locked before any state mutation]
     - already PROCESSED  → return 200 {duplicate: true, final states} — no state change (SM §7.8)
     - RECEIVED/PROCESSING → 409 PAYMENT_PROVIDER_EVENT_IN_PROGRESS
     - FAILED              → reset to PROCESSING (retry, v1.2 lifecycle)
  2. Lock payment FOR UPDATE, then refund FOR UPDATE; refund must be PROVIDER_PENDING
     else 409 REFUND_INVALID_STATE
  3. Verify linkage: event.provider_refund_id = refund.provider_refund_id; amount/currency derived
     from refund.approved_amount/currency (PLAN-LOCK: no client-supplied amount) → mismatch ⇒
     409 PAYMENT_PROVIDER_CONFLICT + SECURITY_EVENT SUSPICIOUS_ACTIVITY + event row REJECTED
     (last_error_code) for audit (SM §7.8)
  4. Succeed: refund SUCCEEDED + completed_at; payment REFUNDED/PARTIALLY_REFUNDED (cumulative
     rule, §3); ledger DRAFT→POSTED; event row PROCESSED;
     events REFUND_SUCCEEDED + PAYMENT_REFUNDED|PAYMENT_PARTIALLY_REFUNDED + ADMIN_ACTION
     Fail:    refund FAILED + failed_at + failure_code 'PROVIDER_REFUND_FAILED' +
     failure_message 'Mock provider refund failure (DEV).'; payment restored; ledger DRAFT→VOIDED;
     event row PROCESSED; events REFUND_FAILED + ADMIN_ACTION
  COMMIT
```

Only two result states exist: **SUCCESS / FAILURE** (D2). The mock controls are the DEV stand-in for "provider refund webhook" delivery; a real webhook endpoint for refunds is OUT OF SCOPE (§20).

---

# 5. Exact event usage

Event source of truth: Addendum §13.1/§13.3 + v1.1 enum. **VS8 emits only these `event_ledger` values (all pre-existing — zero enum changes, D3):**

| Operation | `event_ledger` events (exact order) | Entity | Metadata (minimum) |
|---|---|---|---|
| E1 create | `REFUND_REQUESTED`, then `ADMIN_ACTION` | refund | `REFUND_REQUESTED`: `{requested_amount, dev_mock: provider=='OTHER'}`; `ADMIN_ACTION`: `{action: 'refund.created', actor_role}` |
| E2 approve | `REFUND_APPROVED`, `ADMIN_ACTION` (TX1); `REFUND_PROVIDER_SUBMITTED` (TX2) | refund | `REFUND_APPROVED`: `{approved_amount, teacher_adjustment_amount, platform_adjustment_amount}`; `REFUND_PROVIDER_SUBMITTED`: `{provider_refund_id, dev_mock: true}` |
| E3 reject | `REFUND_REJECTED`, `ADMIN_ACTION` | refund | `{rejection_reason}` |
| E4 cancel | `REFUND_CANCELLED`, `ADMIN_ACTION` | refund | `{cancellation_reason, payment_status_restored: bool}` |
| E5 mock success | `REFUND_SUCCEEDED`, then `PAYMENT_REFUNDED` \| `PAYMENT_PARTIALLY_REFUNDED`, then `ADMIN_ACTION` | refund, payment, refund | `PAYMENT_*`: `{refund_id, dev_mock: true}`; `ADMIN_ACTION`: `{action: 'refund.mock_succeeded', provider_event_id}` |
| E6 mock failure | `REFUND_FAILED`, then `ADMIN_ACTION` | refund, refund | `REFUND_FAILED`: `{failure_code, provider_event_id}`; `ADMIN_ACTION`: `{action: 'refund.mock_failed'}` |
| E7 reconcile | `ADMIN_ACTION`, then `REFUND_SUCCEEDED`/`REFUND_FAILED`, then (success only) `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` | per Addendum §7.3 | `ADMIN_ACTION`: `{action: 'refund.reconciled', reconciliation_source, reconciliation_reference}` |
| E9 detail read (sensitive fields) | none to `event_ledger` beyond `ADMIN_ACTION`; `SECURITY_EVENT` `ADMIN_ACCESS` (severity 2) in `security_events` | refund | `{entity: 'refund', entity_id, request_id}` (VS5 pattern) |
| E8 list read | **none** (Addendum §7.1: "Ordinary list read none") | — | — |

**Hard rules (asserted by tests):**
- `REFUND_ISSUED` is **never** emitted by VS8 (deprecated, Addendum §13.2). Tests assert zero `REFUND_ISSUED` rows produced by any VS8 code path.
- `REFUND_PROVIDER_PENDING` is a **state**, never an event; the submission event is `REFUND_PROVIDER_SUBMITTED`.
- There is no `REFUND_RECONCILIATION_REQUIRED` event; the only reconciliation event is the pre-existing `PAYMENT_RECONCILIATION_REQUIRED` (payment entity), which VS8 does **not** newly emit except via the unchanged VS2 late branch (already implemented).
- `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only after refund success (Addendum §7.4; Planning §10.4).
- Every state-changing refund operation writes its lifecycle event and `ADMIN_ACTION` in the same transaction as the state change (API §22.1; §21 global admin rule).
- `event_ledger` append-only (v1 guard) — no updates/deletes.

---

# 6. Exact ledger behavior

Ledger facts (AUTHORITATIVE): `ledger_transaction_type` ∈ {`PARENT_PAYMENT`, `PLATFORM_COMMISSION`, `TEACHER_PAYOUT`, `REFUND`, `ADJUSTMENT`}; tx `status` ∈ {`DRAFT`, `POSTED`, `VOIDED`}; entries append-only; every tx must balance `sum(DEBIT) = sum(CREDIT)` (v1 deferred constraint trigger); post-paid corrections are separate adjustment/recovery transactions (Addendum §11; v1.4 PAID-payout immutability).

**VS8 uses tx type `REFUND` for the refund itself and `ADJUSTMENT` for the post-paid recovery form** (both pre-existing; PRD rule "Refunds must create ledger entries"; §12.6 TX1 "create … ledger_transaction REFUND according to approved schema approach").

**Entry-set design — PLAN-LOCK (the audit's D10 plan-time lock; balanced by the DB constraint; DRAFT→POSTED/VOIDED lifecycle mirrors the approved VS5 U1 pattern):**

Let `A = approved_amount`, `T = teacher_adjustment_amount`, `P = platform_adjustment_amount` (`T + P = A` — D9, actor-supplied). The form is determined **at approve (TX1)** from the booking's financial state:

| Form | Condition (deterministic check at approve) | Entries (balanced) | Rationale (documented source) |
|---|---|---|---|
| **L — late/unfulfillable** | booking has **zero** `sessions` rows (the VS2 late branch is the only path that books `REFUND_PAYABLE` liability, and it never creates sessions) | DRAFT `REFUND` tx: DEBIT `REFUND_PAYABLE` A / CREDIT `PAYMENT_PROVIDER_CLEARING` A | Settles the exact liability recorded by the implemented VS2 late branch (DEBIT clearing / CREDIT `REFUND_PAYABLE`) |
| **D — direct (fulfilled, not yet paid out)** | sessions exist and **no** `PAID` payout for the booking | DRAFT `REFUND` tx: DEBIT `TEACHER_PAYABLE` T / DEBIT `PLATFORM_REVENUE` P / CREDIT `PAYMENT_PROVIDER_CLEARING` A | Reverses the original confirmation entry (VS2: CR `TEACHER_PAYABLE` net + CR `PLATFORM_REVENUE` commission) in proportion to the actor-specified allocation |
| **A — post-paid recovery** | a `PAID` payout exists for the booking | DRAFT `REFUND` tx: DEBIT `TEACHER_RECOVERABLE` T / DEBIT `PLATFORM_REFUND_EXPENSE` P / CREDIT `PAYMENT_PROVIDER_CLEARING` A | Addendum §11.3 exactly (teacher recoverable + platform refund expense; old payout remains `PAID`, untouched — v1.4) |

**Lifecycle:** tx created `DRAFT` with balanced entries in approve TX1 (VS5 pattern: "DRAFT … balanced … POSTED on success / VOIDED on failure; draft never posted → no reversal needed", SM §12.6 cited by VS5). On `SUCCEEDED`: tx → `POSTED`. On `FAILED`/`CANCELLED` (from `APPROVED`): tx → `VOIDED`. No entries are ever updated/deleted (append-only; corrections only via new transactions).

**Accounting identity:** enforced by the v1 deferred balance trigger on every entry insert (no new constraint needed). **Account-balance note (documented, not a rule):** the DB enforces per-transaction balance only (no per-account balance constraint exists in the approved schema); the economic meaning of a teacher share exceeding outstanding `TEACHER_PAYABLE` in Form D is the approving operator's responsibility under D9 (actor-supplied, reason-coded) — no formula is applied or checked beyond `T + P = A`, non-negativity, and the over-refund bound.

**Payout interaction (already implemented in VS5 — VS8 consumes it, does not change it):** `APPROVED`/`PROVIDER_PENDING`/`SUCCEEDED` partial refunds reduce `net_teacher_payable` via `teacher_adjustment_amount` (Addendum §10.1); any `FULL` refund row blocks payout eligibility (`FULL_REFUND_EXISTS`); payout net recalculation happens at payout processing.

---

# 7. Allocation validation (D9)

- **Where supplied:** E2 approve request (`teacher_adjustment_amount`, `platform_adjustment_amount`) — the "applicable approval" operation (D9). Reconciliation (E7) does **not** accept allocation: by the time a refund is `PROVIDER_PENDING`, allocation is already fixed at approve (schema: v1.3 keeps allocation data intact through the lifecycle). PLAN-LOCK.
- **Validation (service pre-checks, then DB backstops):**
  1. Both components present, non-negative, string-decimal DZD-consistent (else `VALIDATION_ERROR` 400).
  2. `teacher + platform = approved_amount` exactly (else `VALIDATION_ERROR` 400) — mirrors v1.1 `validate_refund_integrity` ("Refund allocation must equal approved_amount").
  3. `approved_amount ≤ requested_amount` and `≤ remaining refundable` (else `VALIDATION_ERROR` / `OVER_REFUND`).
  4. FULL refund: `approved_amount = payment.amount` (v1.1 trigger); PARTIAL: `< payment.amount` (trigger).
- **No automatic allocation formula exists or will be added** (D9; OPS-POL-007 pilot default "no automatic formula in pilot" and unset behavior "auto-approval disabled" respected — no auto-approval anywhere in VS8).
- **OPS-POL-007 policy value is unmodified** (verified byte-identical; no config key introduced).
- **Rejection of invalid values** occurs at the service (clean 400) and, as defense-in-depth, at the DB triggers (mapped to `REFUND_INVALID_STATE`).
- **Audit:** the approved allocation is recorded on the row (`teacher_adjustment_amount`, `platform_adjustment_amount`, `approved_by_*`, `approved_at`) and in the `REFUND_APPROVED` event metadata; UX Flow 32 "Admin must see allocation" satisfied by E9 detail + console display.

---

# 8. Authorization matrix

Role behavior (AUTHORITATIVE: API §4.1, role matrix "Process refund: PARENT No / TEACHER No / SUPPORT No / OPS policy-limited / ADMIN Yes"; Addendum §7.1–7.3; SM §14.3; UX Patch 2). Enforcement: existing `@require_roles` decorator + service-side role checks (established pattern).

| Operation | PARENT | TEACHER | SUPPORT | OPS | ADMIN |
|---|---|---|---|---|---|
| E1 create `POST /payments/:id/refund` | 403 | 403 | 403 | ✅ policy-limited | ✅ elevated financial override (§12.6) |
| E2 approve / E3 reject / E4 cancel | 403 | 403 | 403 | ✅ (SM §14.3 "OPS/Admin", "Admin/OPS") | ✅ |
| E5/E6 mock results | 403 | 403 | 403 | ✅ **DEV-only guard** (403 outside DEV) | ✅ **DEV-only guard** |
| E7 reconcile | 403 | 403 | 403 ("SUPPORT cannot perform financial reconciliation" — UX Patch 2) | ✅ **except** `ADMIN_OVERRIDE` source | ✅ incl. `ADMIN_OVERRIDE` |
| E8 list / E9 detail | 403 | 403 | 403 (SUPPORT view "if policy allows" — **no approved policy exists ⇒ out of scope, §20**) | ✅ (detail: audited) | ✅ (detail: audited, sensitive override fields) |
| X1 `GET /payments/:id` (+`refunds[]`) | ✅ own only | — (never parent payment details) | (existing rules) | ✅ | ✅ |
| X2/X3 (+`refund_summary` / `linked_refunds[]`) | existing actor rules, unchanged | existing | existing | ✅ | ✅ |

Parent/teacher request **initiation** exists only via the dispute path (SM §14.3 first row) — the dispute-open endpoint is implemented (VS4); dispute *resolution* with refund actions is R2 (out of scope). Every authorized E1–E7 operation writes `ADMIN_ACTION`; sensitive E9 reads write `ADMIN_ACTION` + `SECURITY_EVENT` `ADMIN_ACCESS` (severity 2).

---

# 9. Idempotency

Infrastructure (existing, v1.1 + v1.3): `api_idempotency_keys` with `UNIQUE(scope, actor_key, idempotency_key)`, `request_hash`, `PROCESSING → COMPLETED/FAILED` lifecycle, immutable identity, terminal records carry `response_status` + stored `response_body`. Helpers (existing, verified): `_idempotency_begin(scope, actor_user_id, key, request_hash, path)` (missing key → 400 `IDEMPOTENCY_KEY_REQUIRED`; hash mismatch → 409 `IDEMPOTENCY_KEY_CONFLICT`; COMPLETED → replay stored response; PROCESSING → 409 `IDEMPOTENCY_REQUEST_PROCESSING`) and `_idempotency_complete(…, 200, response_body, resource_type, resource_id)`; `request_hash = sha256(json.dumps(body, sort_keys=True))` (VS1–VS6 pattern).

| Command | Scope | Required? | Exact expected behavior |
|---|---|---|---|
| E1 create | `refund_create` | **Yes** (API §24.1 "Prevent duplicate refunds"; key format `refund-<uuid-v4>` per §24.2) | Duplicate refund request with same key+body → original 201 response replayed (no second row); same key, different body → 409 conflict; in-flight → 409 processing |
| E2 approve | `refund_approve` | **Yes** | Same as above; `_idempotency_complete` executed **atomically inside TX2** (VS5 crash-safe pattern) |
| E3 reject | `refund_reject` | **Yes** (PLAN-LOCK: "Recommended" in SM §14.3 → adopted as required) | Same as above |
| E4 cancel | `refund_cancel` | **Yes** (SM §14.3 "Required") | Same as above |
| E5/E6 mock results | — | Not table-based | **Provider-event identity is the idempotency mechanism** (Addendum §8.2; VS2 pattern): same `provider_event_id` already `PROCESSED` → 200 duplicate with final states, no re-mutation; in-flight → 409; conflicting identity → 409 `PAYMENT_PROVIDER_CONFLICT` + security event |
| E7 reconcile | `refund_reconcile` | **Yes** (Addendum §7.3: `IDEMPOTENCY_KEY_REQUIRED` / `IDEMPOTENCY_KEY_CONFLICT` in its error catalogue) | Same as above; `_idempotency_complete` atomic with the reconcile tx |

Key hygiene (PLAN-LOCK, per schema CHECKs): key length ≥16 pre-validated (400 `VALIDATION_ERROR` if shorter); `actor_key = "user:<actor_user_id>"` (v1.2 actor-identity guard); retention/expiry per existing schema default (+24h) — retention-period policy remains OPEN per Addendum §17 (non-structural).

**Duplicate refund requests with different keys** (no idempotency protection) are handled by the concurrency/over-refund rules (§10), not by idempotency.

---

# 10. Concurrency

Lock discipline (PLAN-LOCK, derived from SM §7.6 "Lock payment + refund + booking", Addendum §15.1/§15.3/§15.4, VS5 sorted-lock pattern):

1. **Global lock order (always):** payment row → refund row(s) → booking row. All VS8 commands follow it — no deadlocks between refund commands.
2. **E1 create:** `SELECT payment FOR UPDATE` + booking lock (per §12.6 "lock payment and booking"); over-refund reservation computed **under the payment lock**.
3. **E2/E3/E4/E7:** `SELECT payment FOR UPDATE`, then `SELECT refund FOR UPDATE` (by id; verify `refund.payment_id = payment.id`).
4. **E5/E6:** provider event row locked/inserted by `(provider, provider_event_id)` **before** payment/refund locks (Addendum §15.1 — event identity first, exactly the VS2 order).
5. **Over-refund race:** two concurrent approvals on the same payment serialize on the payment row; the second recomputes `reserved + new ≤ payment.amount` under the lock (Addendum §15.4) and fails with `OVER_REFUND` if the bound is exceeded — backed by the v1.1 trigger (which re-checks under its own `FOR UPDATE` on the payment).
6. **Concurrent success paths** (E5 mock success vs E7 reconcile vs a second E5 with a different event id) on the same refund: serialized by the refund row lock; the first commits; the others see the refund no longer `PROVIDER_PENDING` → 409 `REFUND_INVALID_STATE`. The already-`PROCESSED` same-event-id replay always returns 200 with the recorded outcome (SM §7.8).
7. **Concurrent provider events** on different refunds of the same payment: event-identity lock first (unique per event id), then payment/refund locks — no double-credit; ledger balance trigger remains the final integrity backstop.
8. **In-flight idempotency:** `PROCESSING` records block same-key replays with 409 (never a stale claim — VS5 pattern).
9. **Crash safety:** every multi-step command is a single transaction (TX1/TX2 for E2 as in §4); a crash leaves either the pre-state or a fully committed state, plus the documented E2 crash window and its approved recovery path (§4).

---

# 11. Reconciliation (E7 — exact)

Contract: Addendum v1.1 §7.3 (AUTHORITATIVE) + UX v1.1 Patch 2 + v1.2/v1.3 proof constraints + `REFUND_PROVIDER_MODE` default `MANUAL_RECONCILIATION` (Feature Flag Governance — the documented default refund processing mode).

- **Actor:** OPS/ADMIN; `ADMIN` required when `reconciliation_source = "ADMIN_OVERRIDE"` (else 403).
- **Idempotency:** required (scope `refund_reconcile`).
- **Allowed-from state (PLAN-LOCK of the audit's residual):** `PROVIDER_PENDING` only. Rationale: the v1.2 lifecycle permits `PROVIDER_PENDING → SUCCEEDED/FAILED`; no other non-terminal state can legally reach a terminal state via reconciliation (`REQUESTED` has no `approved_amount` to reconcile; terminal states "cannot be reopened"). In VS8's flow a refund is never left at `APPROVED` for operator action (approve+submit is one command), so `PROVIDER_PENDING` is the only reachable "requires reconciliation" state.
- **Request/fields:** exactly §2.3 E7. `reconciled_by_user_id` = authenticated actor (never client-supplied). `supporting_evidence` = references only (no raw payloads — Addendum §7.3 sensitive-data rule).
- **Proof rules (v1.2/v1.3, enforced at DB + pre-checked at service):** `reconciliation_source` non-empty ⇒ `reconciliation_reference` non-whitespace + `reconciled_at` present; sources `MANUAL_RECONCILIATION`/`ADMIN_OVERRIDE` ⇒ `reconciled_by_user_id` present (always true by construction).
- **Effects:** per §3 table rows for `SUCCEEDED`/`FAILED` (payment update only on success; ledger POSTED/VOIDED; events per §5).
- **Errors:** `REFUND_NOT_FOUND` (404) · `REFUND_INVALID_STATE` (409) · `REFUND_RECONCILIATION_PROOF_REQUIRED` (400) · `FORBIDDEN` (403) · `IDEMPOTENCY_KEY_REQUIRED` (400) · `IDEMPOTENCY_KEY_CONFLICT` (409) — the Addendum §7.3 catalogue, implemented verbatim.
- **Relationship to mock results:** E5/E6 (provider-event path) and E7 (manual path) are alternative result sources for the same `PROVIDER_PENDING` state; first committed wins (§10.6). Under the default `REFUND_PROVIDER_MODE = MANUAL_RECONCILIATION` semantics, operators may simply never invoke the mock controls and reconcile directly — both paths are lawful in DEV (D2: "the approved reconciliation endpoint/workflow remains available for the documented reconciliation cases").
- **PLAN-LOCK (flag wiring):** no new settings key is introduced by VS8; the DEV slice exposes both result paths under the existing DEV-only guard, which covers both governance-doc modes operationally. Wiring `REFUND_PROVIDER_MODE` config is recorded as an integration item (§22), not a VS8 deliverable.

---

# 12. Late-refund handling

Facts (AUTHORITATIVE/implemented): the VS2 late branch (unchanged by VS8) creates, on late/unfulfillable mock success: payment `CONFIRMED`, booking stays `EXPIRED`/`CANCELLED`, no session, `PARENT_PAYMENT` ledger (DEBIT `PAYMENT_PROVIDER_CLEARING` / CREDIT `REFUND_PAYABLE`), refund `FULL`/`REQUESTED` (`reason_code LATE_PAYMENT_AFTER_EXPIRY`, `idempotency_key late-refund-<payment_id>`, `requested_by_user_id NULL`), events `PAYMENT_CONFIRMED` + `PAYMENT_RECONCILIATION_REQUIRED` + `REFUND_REQUESTED`. OPS-POL-003 is OPEN; its documented **unset** behavior is "create reconciliation alert and block auto-refund" — which the VS2 behavior already satisfies (request only, no auto-approval).

**VS8 progression (no new late-specific code — the generic commands cover it, per the audit's D5 determination):**
1. OPS/ADMIN sees the `REQUESTED` late refund in E8 (status filter) / payment detail (`refunds[]`).
2. **Approve** via E2 with actor-supplied allocation. (Economically consistent values for a late refund are `teacher_adjustment = 0`, `platform_adjustment = A` — the teacher has no outstanding payable, since no session/payout was ever created; this is **guidance documented in the console help text only — not enforced, not auto-filled** (D9: no formula, no default). The ledger Form L (§6) settles from `REFUND_PAYABLE` regardless of the split, because no `TEACHER_PAYABLE` was ever credited for a late payment.)
3. **Result** via E5/E6 (mock) or E7 (reconciliation). E2E scenario 3 (§18) exercises the reconciliation path (the documented reconciliation case — "Late payment unfulfillable" timing row, Addendum §13.3).
4. **No auto-approval, no auto-refund** of late payments at any point (OPS-POL-003 unset behavior; D9 no-auto-allocation).
5. `PAYMENT_RECONCILIATION_REQUIRED` is emitted only by the unchanged VS2 branch; VS8 adds no new emitters of that event.

---

# 13. Failure handling

| Failure | Exact behavior (AUTHORITATIVE sources) |
|---|---|
| Mock provider failure (E6) | Refund `FAILED` + `failed_at` + `failure_code 'PROVIDER_REFUND_FAILED'` + message; **payment restored** to `metadata.payment_status_before_refund` (`CONFIRMED` or `DISPUTED`) (SM §7.6/§19.5); DRAFT ledger tx `VOIDED` ("Ledger reversal is not posted unless money movement occurred" — SM §19.5); `REFUND_FAILED` + `ADMIN_ACTION`; Admin/OPS notification in DEV = audited event ledger + refund visible in E8 `?status=FAILED` (real notification dispatch is R12 — OUT OF SCOPE; documented) |
| Reconciled failure (E7 `result=FAILED`) | Same terminal effects as E6 failure, with reconciliation proof fields recorded on the row |
| Invalid allocation (E2) | 400 `VALIDATION_ERROR` before any state change (tx not started); DB trigger as backstop |
| Over-refund (E1/E2) | 409 `OVER_REFUND` under lock; v1.1 trigger backstop raises → mapped 409 |
| Invalid state (any command) | 409 `REFUND_INVALID_STATE`; no partial state (single-transaction commands) |
| Provider identity conflict (E5/E6) | 409 `PAYMENT_PROVIDER_CONFLICT`; event row `REJECTED` with `last_error_code`; `SECURITY_EVENT` `SUSPICIOUS_ACTIVITY`; no business state mutated (SM §7.8) |
| Internal DB error mid-transaction | Full rollback (no partial business state — SM §7.9 principle); idempotency record left `PROCESSING` → replays get 409 processing guard; operator re-drives or cancels |
| E2 crash window (TX1 committed, TX2 lost) | Refund stuck `APPROVED`; documented recovery: E4 cancel + new E1 request (§4). No automatic retry (AUTOMATIC PROVIDER EXECUTION = NO) |
| Refund `FAILED` and a refund is still warranted | **No retry/reopen** (terminal — v1.2 lifecycle; no approved reopen transition). Recovery = a **new** refund request via E1 (new idempotency key), subject to the over-refund bound (the `FAILED` row's `approved_amount` does not count toward the bound — only `APPROVED/PROVIDER_PENDING/SUCCEEDED` reserve, per Addendum §15.4 and the v1.1 trigger). E2E scenario 4 covers this |
| Concurrency losses | First-writer-wins per §10; losers receive 409 with the recorded final state in the response metadata |

---

# 14. Audit / security events

- **`ADMIN_ACTION` (event_ledger):** every authorized E1–E7 operation (API §21 global admin rule: "Every admin operation: verify permission → perform action → insert event_ledger ADMIN_ACTION"); metadata carries the action name + key identifiers (§5 table). Actor identity (`actor_user_id`, `actor_role`) recorded on every refund event (API §22.2).
- **`SECURITY_EVENT` (`security_events`, existing enum values only):**
  - `ADMIN_ACCESS` (severity 2) on E9 sensitive detail reads (provider/reconciliation summary exposed) — VS5 admin-read pattern.
  - `SUSPICIOUS_ACTIVITY` on `PAYMENT_PROVIDER_CONFLICT` (SM §7.8 "Log security/ops event").
- **Event ledger integrity:** append-only (v1 trigger); business state + event in the same transaction (API §22.1).
- **Provider payload handling:** `normalized_provider_payload` on `refunds` stores mock metadata only; raw payloads are never stored in responses; `payload_redacted = TRUE` default on `payment_provider_events` (v1.1) preserved; E8 list never includes raw payload (Addendum §7.1); Traceability row "Provider payload redaction" covered by tests.
- **No new `security_event_type` values** (D3 analog for the security enum; existing values only).

---

# 15. Frontend DEV scope (approved DEV-console posture only — R17 production UI OUT OF SCOPE)

**Admin console — Refunds section (UX Flow 32 + UX v1.1 Patch 1/2):**
- **List** (E8): refund id, payment/booking refs, type, status (admin labels per Patch 1: Requested / Approved internally / Submitted to provider / Provider-reconciliation success / Provider-reconciliation failed / Rejected by platform / Cancelled before completion), amounts, reason code, created_at; filters: status/provider/dispute/payment.
- **Detail** (E9): full timeline component (requested → approved → submitted to provider → completed/failed/rejected/cancelled) with the 7 state timestamps; **allocation block (Flow 32: "Admin must see allocation")**: approved amount, teacher adjustment, platform adjustment, "Total allocation equals approved amount"; reconciliation block (source/reference/at/by) once set; `provider_event_summary` list (redacted).
- **Actions:** Approve (form: `approved_amount` pre-displayed = `requested_amount` as a *display hint only* — the value is actor-confirmed, and the two allocation fields are **empty inputs, never pre-filled** (D9); reason code optional), Reject (reason), Cancel (reason), Reconcile (result SUCCEEDED/FAILED, source, reference, timestamp auto-now, reason, evidence references), **Mock Succeed / Mock Fail** buttons (clearly labeled "DEV MOCK — provider result simulation", hidden when the DEV guard is off).
- **Display rule (Patch 1, enforced):** never render "Refunded" unless `status = SUCCEEDED`; `PARTIALLY_REFUNDED`/`REFUND_PENDING` shown with their distinct labels.

**Parent console (X1/X2 consumption):** payment detail shows `refunds[]` timeline (parent labels per Patch 1); booking detail shows `refund_summary`; dispute detail shows `linked_refunds[]` (X3). No new parent actions.

**Teacher console:** unchanged in VS8 (payout economic-impact display for refund adjustments is a recorded follow-up, §20 — the data already exists in VS5 payout detail responses).

**Engineering:** reuses the existing Next.js DEV console patterns/pages (admin page section + parent page additions); no new dependencies; `npm run build` must pass.

---

# 16. Tests (pytest, repo runner `scripts/run_backend_tests.sh`)

New test files (names per the approved Test Traceability Matrix):

**`tests/test_refund_service.py`** — covers Traceability rows "Refund lifecycle valid", "Over-refund blocked", "Partial refund allocation", "Post-payout recovery separate", "Provider payload redaction":
- **Create (E1):** eligible `CONFIRMED` payment; eligible `DISPUTED` payment; 404 unknown payment; 403 PARENT/TEACHER/SUPPORT; 400 bad amount/currency/short reason; 400 short idempotency key; `REFUND_INVALID_STATE` for `INITIATED`/`PENDING`/`FAILED`/`REFUNDED`/`REFUND_PENDING`/`PARTIALLY_REFUNDED` payments (contract precondition); over-refund at creation bound; `dispute_id` cross-booking rejection; events = exactly `REFUND_REQUESTED` + `ADMIN_ACTION`; payment state unchanged after create.
- **Approve (E2):** happy path (allocation valid) → `PROVIDER_PENDING`, payment `REFUND_PENDING`, DRAFT ledger balanced (form D), `provider_refund_id` set, provider event row `PROCESSED` (`refund.initiated`), events `REFUND_APPROVED` + `ADMIN_ACTION` + `REFUND_PROVIDER_SUBMITTED`; allocation sum mismatch → 400 (no state change); negative component → 400; `approved > requested` → 400; FULL with `approved ≠ payment.amount` → rejected (trigger); PARTIAL with `approved = payment.amount` → rejected (trigger); over-refund under reservation → 409; reject/cancel after approve → `VOIDED` ledger + payment restore; idempotency replay/conflict/in-flight; crash-window state assertion (TX1 only ⇒ replay 409 processing).
- **Reject (E3) / Cancel (E4):** transitions, metadata reasons, events, payment effects (none / restore), idempotency, terminal-state rejection.
- **Mock success (E5):** full → payment `REFUNDED` + `PAYMENT_REFUNDED`; partial → `PARTIALLY_REFUNDED` + `PAYMENT_PARTIALLY_REFUNDED`; cumulative rule (partial then remainder); ledger `POSTED` for Forms L/D/A (three separate bookings); `refunded_at` set; duplicate `provider_event_id` → 200 no re-mutation; in-flight event → 409; refund not `PROVIDER_PENDING` → 409; DEV guard 403 when `MOCK_PAYMENT_PROVIDER_ENABLED=false`; events exact set.
- **Mock failure (E6):** `FAILED` + `failed_at` + failure fields; payment restore for both prior states (`CONFIRMED`, `DISPUTED`); ledger `VOIDED`; events exact; no `PAYMENT_*` event emitted.
- **Reconcile (E7):** success with `MANUAL_RECONCILIATION` proof (no `provider_refund_id` reliance) → SUCCEEDED + payment + ledger POSTED + events incl. `ADMIN_ACTION` first; failure result; `ADMIN_OVERRIDE` by OPS → 403, by ADMIN → 200; missing reference/whitespace reference/missing `reconciled_at` → 400 `REFUND_RECONCILIATION_PROOF_REQUIRED`; non-`PROVIDER_PENDING` → 409; idempotency required/conflict; `reconciled_by_user_id` = actor (not client value).
- **Ledger (D10 forms):** Form L (late booking, zero sessions) entries exact; Form D entries exact; Form A (PAID payout exists) entries exact + old payout row byte-identical after refund (v1.4 immutability); balance trigger holds in every case (deferred constraint); no entry UPDATE/DELETE attempted.
- **Events negative tests:** zero `REFUND_ISSUED` rows created by any VS8 path; no event named `REFUND_PROVIDER_PENDING`; `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` never precede SUCCEEDED; `event_type` enum unchanged (no migration).
- **Reads:** E8 filters/pagination/redaction (no raw payload in list); E9 detail fields + `ADMIN_ACCESS` security event; X1 `refunds[]` on own payment (parent) and absence for others; X2 `refund_summary`; X3 `linked_refunds[]`; teacher never sees parent payment details.
- **Payout interaction regression (VS5):** APPROVED partial refund reduces net payable; FULL refund blocks eligibility; refund exposure counted from APPROVED (not only SUCCEEDED) — Traceability "Partial refund allocation" + UX-AUD-005.

**`tests/test_refund_concurrency.py`** — Traceability "Over-refund blocked … concurrent refunds <= payment":
- Two concurrent E2 approvals racing on one payment (second blocked by lock, then `OVER_REFUND` or success-within-bound deterministically);
- Concurrent E5 success vs E7 reconcile (first wins; second 409 `REFUND_INVALID_STATE`);
- Concurrent E5 same `provider_event_id` (one PROCESSED, other 200-duplicate);
- Concurrent E1 creates (serialization; reservation respected);
- Deadlock-freedom smoke (all lock orders per §10.1).

**Regression:** full existing suite (118 tests after VS7) must pass unmodified.

---

# 17. E2E scenarios (follow the VS2–VS6 embedded-E2E convention; planned traceability artifacts `e2e_refund_lifecycle.spec.ts`, `e2e_admin_refund_reconciliation.spec.ts` materialize as these scripted end-to-end checks in the DEV E2E run)

| # | Scenario | Steps (exact) | Expected end state (asserted) |
|---|---|---|---|
| E2E-1 | `E2E_FULL_REFUND_LIFECYCLE` | HELD booking → confirm → `POST /payments/initiate` → mock succeed (payment CONFIRMED, session SCHEDULED) → E1 create FULL → E2 approve (allocation T+P=A) → E5 mock succeed | refund `SUCCEEDED` (provider_refund_id `mock_ref_*`); payment `REFUNDED` + `refunded_at`; booking unchanged factually; ledger `REFUND` tx `POSTED` (Form D, balanced); events in order: `REFUND_REQUESTED`, `REFUND_APPROVED`, `REFUND_PROVIDER_SUBMITTED`, `REFUND_SUCCEEDED`, `PAYMENT_REFUNDED`, + `ADMIN_ACTION`s; **no** `REFUND_ISSUED`; parent `GET /payments/:id` shows `refunds[0].status = "SUCCEEDED"` |
| E2E-2 | `E2E_PARTIAL_REFUND_PAYOUT_EXPOSURE` | full paid loop → E1 create PARTIAL → E2 approve (allocation) → attempt payout (net reduced by T per VS5) → E5 mock succeed | refund `SUCCEEDED`; payment `PARTIALLY_REFUNDED`; `PAYMENT_PARTIALLY_REFUNDED` emitted; payout net = gross − T (or blocked if net ≤ 0); teacher view shows exposure; `PARTIALLY_REFUNDED` label in parent UI data |
| E2E-3 | `E2E_LATE_REFUND_RECONCILIATION` | VS2 late path (expired hold + mock succeed ⇒ `REQUESTED` FULL refund + `PAYMENT_RECONCILIATION_REQUIRED` + `REFUND_REQUESTED`) → E2 approve (allocation; e.g. 0/A) → **E7 reconcile SUCCEEDED** (`MANUAL_RECONCILIATION`, bank reference, actor-attributed) | refund `SUCCEEDED` with full proof fields (provider_refund_id may be `mock_ref_*` from submission); payment `REFUNDED`; ledger `REFUND` tx `POSTED` **Form L** (DEBIT `REFUND_PAYABLE` / CREDIT `PAYMENT_PROVIDER_CLEARING`); booking still `EXPIRED` (no revival); E9 detail shows reconciliation block |
| E2E-4 | `E2E_REFUND_FAILURE_AND_RECOVERY` | paid loop → E1 → E2 → E6 mock fail → (assert FAILED + payment restored + ledger VOIDED) → new E1 (new key) → E2 → E5 succeed | first refund `FAILED` (terminal; reopen attempt → 409); second refund `SUCCEEDED`; payment final `REFUNDED`; both rows auditable; over-refund bound respected across the two |
| E2E-5 | `E2E_POST_PAID_REFUND_RECOVERY` | full paid loop **including payout PAID** (VS5) → later E1 PARTIAL → E2 approve (allocation) → E5 succeed | refund `SUCCEEDED`; payment `PARTIALLY_REFUNDED`; **old payout row byte-identical** (`PAID` immutable, v1.4); **new** `REFUND` tx `POSTED` **Form A** (DEBIT `TEACHER_RECOVERABLE` T / DEBIT `PLATFORM_REFUND_EXPENSE` P / CREDIT `PAYMENT_PROVIDER_CLEARING` A); Addendum §11.3 example arithmetic verified (2000/300-commission/400-refund/300-teacher/100-platform ⇒ net 1400 pre-paid case) |
| E2E-6 | `E2E_IDEMPOTENCY_AND_REPLAY` | E1 replay same key+body (200/201 original, one row); E1 same key different body (409 `IDEMPOTENCY_KEY_CONFLICT`); E2 in-flight same key (409 processing); E5 duplicate `provider_event_id` (200 duplicate, no re-mutation); E7 replay (original response) | exactly one refund row; idempotency records `COMPLETED` with stored `response_status`; no double ledger tx |
| E2E-7 | `E2E_AUTHORIZATION_MATRIX` | PARENT/TEACHER/SUPPORT → 403 on E1–E7; OPS → E1/E2/E3/E4/E5/E6/E7(200); OPS + `ADMIN_OVERRIDE` reconcile → 403; ADMIN + `ADMIN_OVERRIDE` → 200; mock controls with DEV guard off → 403 | matrix in §8 asserted row-by-row; `ADMIN_ACTION`/`ADMIN_ACCESS` audit rows present for all authorized admin ops |

---

# 18. Dependency audit

- **Python (backend):** no new packages, no version changes — `backend/requirements.txt` diff = empty (VS8 uses Django/psycopg stack already present; `hashlib`, `uuid`, `json` are stdlib).
- **Node (frontend):** no new packages — `frontend/package.json` / `package-lock.json` diff = empty.
- **Vulnerability posture:** unchanged. The known high-severity findings (next 14.2.35 / postcss 8.4.31) remain the **staging dependency-gate items** (Dependency Audits v1.2–v1.6) — unaffected by VS8 and OUT OF SCOPE for it (no `--force` remediation in a DEV slice, per those audits).
- **Verification step (implementation time):** `diff` of `requirements.txt` + `package-lock.json` against the VS7 commit must be empty; `npm run build` passes; `bash scripts/run_backend_tests.sh` green (full suite + new VS8 files).

---

# 19. Rollback strategy

1. **Additive-only design:** VS8 adds new routes, new service functions, a new admin console section, new test files, and additive JSON fields on three existing GET responses (X1–X3). It changes no migration, no state machine, no existing endpoint's behavior, no existing table.
2. **Rollback = revert the single VS8 commit.** No forward/backward migrations exist to run. Reverting removes the routes (404 for refund endpoints) and the console section; nothing else is affected.
3. **Data residue:** refund rows/provider-event rows/ledger txs created during VS8 DEV testing remain valid schema data (they satisfy all v1.1–v1.4 constraints) — no destructive cleanup required; optional DEV-DB purge only. No production data can exist (DEV-only phase; gate).
4. **Guardrail residual:** even if the commit were left in place with flags flipped (`MOCK_PAYMENT_PROVIDER_ENABLED=false` or `REAL_PAYMENT_ENABLED=true`), the mock result controls 403 (VS2 guard) — the slice cannot leak into non-DEV behavior.
5. **API compatibility of rollback:** the X1–X3 additive fields simply disappear on revert — consumers (DEV console only) revert with the same commit.
6. **Verification after rollback:** full pre-VS8 suite (118) green; `git diff` vs `157a54d` empty for code paths.

---

# 20. Explicit out-of-scope items (VS8 does NOT do)

| # | Item | Reason (source) |
|---|---|---|
| O1 | Real refund provider integration / real credentials / real money | REAL REFUND = FORBIDDEN (governance boundary; Gate Assessment: DEV mock only; provider refund capability `REQUIRES PROVIDER CONFIRMATION`; legal NOT APPROVED) |
| O2 | Real refund **webhook** endpoint (`POST /payments/webhooks/:provider` is payment-scoped) | R18; OUT OF SCOPE for DEV slices; mock controls (E5/E6) are the DEV stand-in for result delivery |
| O3 | Parent/teacher self-service refund request endpoints | No approved contract; request initiation exists only via the dispute path (SM §14.3); dispute resolution is R2 |
| O4 | Dispute resolution (`POST /admin/disputes/:id/resolve`) incl. `FULL_REFUND`/`PARTIAL_REFUND` actions | R2 (VS9 candidate in the proposed sequence); its refund actions will call this slice's refund service (§19.4) |
| O5 | SUPPORT access to refund reads | "if policy allows" (Addendum §7.1) — no approved policy exists |
| O6 | Refund retry/reopen after terminal states; automatic provider execution; automatic approval | v1.2 terminality; AUTOMATIC PROVIDER EXECUTION = NO / AUTOMATIC ALLOCATION = NO (boundaries); OPS-POL-003 unset behavior (no auto-refund) |
| O7 | Refund creation on payments in `REFUND_PENDING`/`PARTIALLY_REFUNDED` (follow-up partials after a completed partial) | §12.6 contract precondition is `(CONFIRMED, DISPUTED)`; the wider DB trigger allowlist stays as defense-in-depth; follow-up partials = recorded minor contract gap for a future Addendum patch |
| O8 | Notification dispatch for refund outcomes | R12 (notifications unimplemented); DEV notification = event ledger + admin list visibility (documented, §13) |
| O9 | Manual recovery/adjustment **commands** (e.g. `POST /admin/recoveries`) | "No `POST /admin/recoveries` in MVP" (Addendum §2/§9.3) — recovery is a controlled side effect of the refund service only |
| O10 | Ledger admin endpoints (`/admin/ledger/*`) | R11 |
| O11 | Cancellation/reschedule endpoints (refund eligibility via cancellation) | R4/R5 |
| O12 | Production UI (64 screens) | R17 (phase, not a slice); DEV console posture only |
| O13 | Any schema migration / new table / new enum value | Boundaries: NEW REFUND TABLE = NO (schema demonstrably sufficient — verified), NEW REFUND EVENT ENUM = NO, SCHEMA MIGRATION = FORBIDDEN (no approved contract requires one) |
| O14 | OPS-POL-007 / OPS-POL-003 policy value decisions; `REFUND_ALLOCATION_MODE` / `LATE_PAYMENT_RESOLUTION_MODE` config wiring; `REFUND_PROVIDER_MODE` config wiring | OPEN policies (legal/accounting approvers); config wiring = recorded integration item (see O15 note) |
| O15 | Teacher payout-detail refund-adjustment display; OpenAPI conversion of the Addendum (R20); v1.2 provenance re-verification | Recorded follow-ups (UX display enhancement; integration-hardening condition; governance-record item) — none block VS8 |
| O16 | VS9 or any other slice | VS9 = NOT STARTED (boundary) |

---

# 21. Plan-time locks (this plan's decisions, all derived from approved documents — no invented behavior)

1. **Command set & mapping:** E1 creates `REQUESTED` only; E2 performs approval **and** mock submission as one approved two-transaction operation (§12.6 boundary; SM §14.3 authorities); E3/E4 are separate audited commands (SM §14.3 + UX Flow 32).
2. **Creation precondition** exactly §12.6: `payment.status ∈ (CONFIRMED, DISPUTED)` (O7 documents the contract gap for later partials).
3. **Payment `REFUND_PENDING` is set at approval** (SM §7.6 row precondition "Refund approved; refund row created"), not at creation; prior payment state stored in `metadata.payment_status_before_refund` for restore.
4. **Reconcile allowed-from:** `PROVIDER_PENDING` only (§11).
5. **Mock event kinds** `'refund.initiated'` / `'refund.succeeded'` / `'refund.failed'` are **TEXT values in `payment_provider_events.event_type`** (the provider-event kind column, `CHECK (length ≥ 2)`) — the same category as VS2's `'payment.confirmed'`/`'payment.failed'`. They are **not** `event_ledger` enum values; the `event_type` enum is untouched (D3).
6. **Mock result controls derive amount/currency from the refund row** (no client-supplied amount; mirrors VS2's payment-derived amount) — the conflict path is implemented defensively per SM §7.8 but unreachable via the mock body.
7. **Mock provider identity:** `provider = payment.provider` (`'OTHER'` for mock payments, per VS2 convention); `provider_event_id = mock_evt_<uuid>` (or operator-supplied); `provider_refund_id = mock_ref_<uuid>` from the existing `initiate_refund()` primitive (D1).
8. **Ledger forms L/D/A** and their form-determination rule (§6) — the D10 plan-time lock.
9. **E3 idempotency required** (strengthened from "Recommended").
10. **No new settings keys** in VS8 (existing `MOCK_PAYMENT_PROVIDER_ENABLED` / `REAL_PAYMENT_ENABLED` guards reused; flag wiring = O14 integration item).
11. **SUPPORT refund reads excluded** (O5).
12. **Console allocation inputs start empty** (no pre-fill, D9); display hints only.

---

# 22. Open items carried forward (NONE blocking VS8 scope or implementation)

| Item | Owner | Notes |
|---|---|---|
| OPS-POL-007 allocation policy value (production) | Payment/Finance + Ops + Legal/Compliance | Unchanged; DEV operates under documented unset behavior (manual allocation, no auto-approval) |
| OPS-POL-003 late-payment mode value | same approvers | Unchanged; VS8 respects unset behavior (no auto-refund) |
| Follow-up partials on `PARTIALLY_REFUNDED` payments (contract gap O7) | API Addendum patch (R20 vehicle) | Recorded; not needed for VS8 |
| `REFUND_PROVIDER_MODE` / `REFUND_ALLOCATION_MODE` config wiring (O14) | integration-hardening | VS8 is mode-agnostic in DEV (§11 PLAN-LOCK) |
| Idempotency/provider-event retention periods (Addendum §17 #11/#12) | Ops | Non-structural; schema defaults apply |
| Teacher payout-detail refund-adjustment display (O15) | UX follow-up | Data already present in VS5 responses |
| v1.2 reconstructed-draft provenance (governance record) | baseline owners | Unchanged by VS8 |

---

# 23. Governance statement / final status

```text
THIS DOCUMENT: implementation plan only (no implementation performed)

DECISIONS_CLOSED:  D1 (mock initiation via existing initiate_refund, Admin/OPS-initiated) ·
                   D2 (deterministic SUCCESS/FAILURE mock results + reconciliation retained) ·
                   D3 (payment_provider_events reuse; no new table; no new event enum values;
                       REFUND_PROVIDER_PENDING = state, event = REFUND_PROVIDER_SUBMITTED;
                       no REFUND_RECONCILIATION_REQUIRED (use PAYMENT_RECONCILIATION_REQUIRED);
                       REFUND_ISSUED deprecated — never emitted) ·
                   D9 (actor-supplied allocation at approval; no formula; OPS-POL-007 unmodified)

VS7:                        COMPLETE
VS8_SCOPE_READY:            YES
VS8_IMPLEMENTATION:         NOT STARTED
VS9:                        NOT STARTED

SCHEMA_CHANGE_REQUIRED:     NO   (v1→v1.4 verified sufficient; no migration created)
STATE_MACHINE_CHANGE:       NO
ARCHITECTURE_CHANGE:        NO
API_CHANGE:                 additive only, per approved contracts (§12.6; Addendum v1.1 §7/§8)
NEW_EVENT_ENUM_VALUES:      NO
NEW_TABLES:                 NO
NEW_DEPENDENCIES:           NO
NEW_SETTINGS_KEYS:          NO
MVP_SCOPE_EXPANDED:         NO   (refunds are explicit MVP content — PRD)

REAL_REFUND:                FORBIDDEN (DEV MOCK ONLY = YES)
REAL_PAYMENT:               FORBIDDEN
REAL_PAYOUT:                FORBIDDEN
AUTOMATIC_REFUND_ALLOCATION: NO
AUTOMATIC_PROVIDER_EXECUTION: NO

DATABASE_MODIFIED:          NO
CODE_MODIFIED:              NO
COMMIT_CREATED:             NO
PUSH_PERFORMED:             NO
```

**STOP after this plan. VS8 implementation is NOT started; it awaits explicit approval to proceed against this plan.**
