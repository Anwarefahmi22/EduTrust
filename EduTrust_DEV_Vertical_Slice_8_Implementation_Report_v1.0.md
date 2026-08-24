# EduTrust — DEV Vertical Slice #8 Implementation Report v1.0

**Sprint:** DEV Vertical Slice #8 — Refund Operations (R1)
**Status:** PASS WITH LIMITATIONS (DEV mock only; strict boundaries preserved)
**Approved plan:** `EduTrust_VS8_Refund_Operations_Implementation_Plan_v1.0.md` (followed; no redesign, no scope expansion)
**Approved decisions:** D1 (DEV mock refund initiation via existing `MockPaymentProvider.initiate_refund()`), D2 (deterministic mock SUCCESS/FAILURE only), D3 (reuse `payment_provider_events`; no new refund-event table; no new event enum values; `REFUND_ISSUED` never emitted), D9 (allocation explicitly supplied by the authorized Admin/OPS actor at approval; no formula; OPS-POL-007 value unmodified)

**State-machine changes:** NONE
**Database/migration changes:** NONE (v1→v1.4 chain byte-identical, verified by diff)
**API contract changes to existing endpoints:** NONE (additive fields only, per approved Addendum v1.1 §8)
**New endpoints:** 9 (additive, per approved contracts API Arch §12.6 / Addendum §7)

---

# 1. What was implemented

The approved refund lifecycle, DEV mock only:

```text
Eligibility (payment CONFIRMED/DISPUTED, over-refund bound)
→ REQUESTED (POST /payments/:id/refund, OPS policy-limited / ADMIN elevated, idempotent)
→ APPROVED (actor-supplied allocation: teacher + platform = approved_amount)
→ PROVIDER_PENDING (mock provider call outside the DB transaction — D1)
→ SUCCEEDED (mock success — D2) or FAILED (mock failure — D2)
   or via POST /admin/refunds/:id/reconcile (Addendum v1.1 §7.3 verbatim)
Payment shadow: CONFIRMED/DISPUTED → REFUND_PENDING → REFUNDED / PARTIALLY_REFUNDED
               (restored to prior state on failure/cancel — SM 7.6)
```

Implemented service surface (all in `backend/edutrust_api/services.py`, VS8 section):
- `create_refund` — E1, two-part contract: `REQUESTED` row + `REFUND_REQUESTED` + `ADMIN_ACTION`; creation precondition exactly §12.6 (`CONFIRMED`/`DISPUTED`); `refund_type` derived from amount vs payment amount; idempotency scope `refund_create`.
- `approve_refund` — E2, approved two-transaction boundary: TX1 (idempotency `refund_approve`, payment+refund `FOR UPDATE` in plan lock order, allocation validation, over-refund re-check under lock per Addendum §15.4, refund→`APPROVED` + payment→`REFUND_PENDING` + balanced DRAFT `REFUND` ledger tx + `REFUND_APPROVED`/`ADMIN_ACTION`) → mock `initiate_refund()` **outside** any transaction (D1) → TX2 (provider event `refund.initiated` in `payment_provider_events` RECEIVED→PROCESSING→PROCESSED, refund→`PROVIDER_PENDING` + `provider_refund_id` + `provider_submitted_at`, `REFUND_PROVIDER_SUBMITTED`, idempotency completed atomically — VS5 crash-safe pattern).
- `reject_refund` / `cancel_refund` — E3/E4 (SM §14.3 authorities/events); cancel from `APPROVED` restores the prior payment state (from `metadata.payment_status_before_refund`) and `VOID`s the DRAFT ledger (documented crash-window recovery path, tested).
- `process_mock_refund_result` — E5/E6, deterministic SUCCESS/FAILURE only (D2): DEV-only guard (403 unless `MOCK_PAYMENT_PROVIDER_ENABLED` and `not REAL_PAYMENT_ENABLED`, VS2 pattern); provider-event identity locked first (Addendum §15.1); SM §7.8 replay (200 duplicate, no re-mutation) and conflict (409 `PAYMENT_PROVIDER_CONFLICT` + committed `SUSPICIOUS_ACTIVITY` security event, event row `REJECTED` only from non-terminal states per the v1.2 lifecycle guard); success → `SUCCEEDED` + payment `REFUNDED`/`PARTIALLY_REFUNDED` (cumulative rule) + ledger `POSTED` + `REFUND_SUCCEEDED` + `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` (only on success — Addendum §7.4); failure → `FAILED` + failure fields + payment restored + ledger `VOIDED` + `REFUND_FAILED` (no `PAYMENT_*` event).
- `reconcile_refund` — E7, Addendum §7.1/§7.3 verbatim: request `{result, reconciliation_source, reconciliation_reference, reconciled_at, reason, supporting_evidence[]}`; proof rules (source required; reference non-whitespace; `reconciled_at` required and parseable; `MANUAL_RECONCILIATION`/`ADMIN_OVERRIDE` ⇒ `reconciled_by_user_id` = authenticated actor, never client-supplied); `ADMIN_OVERRIDE` ⇒ ADMIN only; allowed-from state `PROVIDER_PENDING` (PLAN-LOCK; terminal states cannot reopen); idempotency required (`IDEMPOTENCY_KEY_REQUIRED`/`IDEMPOTENCY_KEY_CONFLICT` in the response catalogue).
- `list_admin_refunds` / `get_admin_refund` — E8/E9 per Addendum §7.1/§7.2: filters (`status`, `provider`, `dispute_id`, `payment_id`, `from`, `to`, `limit`, cursor `next_cursor`/`has_more`), no raw provider payload in list, detail with `timeline` + `reconciliation` + redacted `provider_event_summary[]`; ordinary list read generates no event (contract), sensitive detail read audited (`ADMIN_ACTION` + `ADMIN_ACCESS` security event, severity 2).
- Additive read fields (Addendum §8, fields appear only when activity exists — existing responses otherwise unchanged):
  - `GET /payments/:id` → `refunds[]` (parent own-data scoping unchanged)
  - `GET /bookings/:id` → `refund_summary` (`has_refund_activity`, `active_refund_status`, `total_approved_refund_amount`, `currency`)
  - `GET /disputes/:id` → `linked_refunds[]`

## Ledger behavior (D10 plan-lock; balanced by the v1 deferred constraint)

- Refund tx created `DRAFT` at approval; `POSTED` on success; `VOIDED` on failure/cancel (draft-never-posted ⇒ no reversal needed).
- Form determined at approval:
  - **L (late/unfulfillable, zero sessions):** DEBIT `REFUND_PAYABLE` A / CREDIT `PAYMENT_PROVIDER_CLEARING` A (settles the VS2 late-branch liability).
  - **D (fulfilled, no PAID payout):** DEBIT `TEACHER_PAYABLE` T / DEBIT `PLATFORM_REVENUE` P / CREDIT `PAYMENT_PROVIDER_CLEARING` A.
  - **A (PAID payout covering the booking):** DEBIT `TEACHER_RECOVERABLE` T / DEBIT `PLATFORM_REFUND_EXPENSE` P / CREDIT `PAYMENT_PROVIDER_CLEARING` A (Addendum §11; old PAID payout byte-identical — v1.4 immutability).
- Zero-valued allocation components are omitted (schema `amount > 0` CHECK).

## Allocation (D9)

- Supplied by the approving OPS/ADMIN as `teacher_adjustment_amount` + `platform_adjustment_amount` in the E2 request; validated `≥ 0` and `sum = approved_amount` (service pre-check; v1.1 `validate_refund_integrity` backstop). No automatic formula, no defaults, no pre-fill in the console. OPS-POL-007 policy value unmodified (document byte-identical).

## Late refunds

- VS2 branch unchanged (auto-creates `REQUESTED` FULL + `PAYMENT_RECONCILIATION_REQUIRED` + `REFUND_REQUESTED`; **no auto-approval** — OPS-POL-003 unset behavior). Progression through the same VS8 commands (approve → mock result or reconciliation). Form L ledger settles from `REFUND_PAYABLE`. Covered by E2E scenario 3.

## Payout interaction (verified, unchanged code)

- Approval moves the payment to `REFUND_PENDING`, so a payout for the session is blocked while the refund is in flight and after a partial settles (v1 `validate_payout_item_eligibility` requires a `CONFIRMED` payment — approved DB guard; service-level `NO_CONFIRMED_PAYMENT` reason matches it). The Addendum §10.4 net-reduction vector remains pinned by the VS5 suite (seeded `APPROVED` refund with payment still `CONFIRMED`). Post-paid refunds use Form A recovery. No payout code modified.

## Authorization (enforced)

| Operation | PARENT | TEACHER | SUPPORT | OPS | ADMIN |
|---|---|---|---|---|---|
| E1 create / E2 approve / E3 reject / E4 cancel | 403 | 403 | 403 | ✅ policy-limited | ✅ elevated |
| E5/E6 mock results | 403 | 403 | 403 | ✅ (DEV-only guard) | ✅ (DEV-only guard) |
| E7 reconcile | 403 | 403 | 403 | ✅ except `ADMIN_OVERRIDE` | ✅ incl. `ADMIN_OVERRIDE` |
| E8 list / E9 detail | 403 | 403 | 403 (no approved policy) | ✅ (detail audited) | ✅ (detail audited) |

## Frontend (DEV console only — no production UI)

- `frontend/app/admin/page.tsx` — "Refunds (operational)" section: list with status/type/amounts, detail with timeline, allocation display (approved = teacher + platform), Reconcile form (result/source/reference/reason), DEV-labeled Mock success/failure buttons, Approve/Reject/Cancel actions (allocation inputs start empty).
- `frontend/app/parent/page.tsx` — "Refund status" button on the booking card showing `refunds[]` with the UX v1.1 Patch 1 parent labels (Refund requested / approved / processing / completed / failed / rejected / cancelled); "completed" (refunded) shown only for `SUCCEEDED`.

# 2. Explicit out-of-scope (per approved plan)

Real refund/payment/payout providers and credentials; real refund webhook endpoint; parent/teacher self-service refund endpoints; SUPPORT refund reads; retry/reopen of terminal refunds; refund creation on `REFUND_PENDING`/`PARTIALLY_REFUNDED` payments (creation contract is §12.6 `CONFIRMED`/`DISPUTED` only — recorded as the plan's O7 contract gap for a future Addendum patch); notifications dispatch (R12); manual recovery commands (Addendum §9.3); dispute resolution (R2/VS9); production UI (R17); OPS-POL-007/003 policy values; `REFUND_PROVIDER_MODE` config wiring (integration item).

# 3. Boundary verification

```text
REAL REFUND:   FORBIDDEN — not implemented (provider classes = PaymentProvider + MockPaymentProvider only)
REAL PAYMENT:  FORBIDDEN — unchanged
REAL PAYOUT:   FORBIDDEN — unchanged
DEV MOCK ONLY: YES
Migrations v1→v1.4: byte-identical (verified by diff)
Root SQL provenance copies: byte-identical (verified by diff)
VS1–VS7 test files: unchanged (verified by diff)
requirements.txt / package.json / package-lock.json: unchanged (verified by diff)
REFUND_ISSUED: never emitted (unit + E2E assertions)
```

# 4. Artifacts

- `tests/test_refund_service.py` (38 tests), `tests/test_refund_concurrency.py` (4 tests), `tests/e2e_refund_lifecycle.py` (standalone E2E, 7 scenarios + financial-integrity gates)
- Reports: Implementation (this file), Test Report v1.0, E2E Report v1.0, Dependency Audit v1.7 (chain continues from v1.6/VS7)
- README "DEV Vertical Slice #8" section
