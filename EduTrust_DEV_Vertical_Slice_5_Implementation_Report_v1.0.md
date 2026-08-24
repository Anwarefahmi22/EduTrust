# EduTrust — DEV Vertical Slice #5 Implementation Report v1.0

**Sprint:** DEV Vertical Slice #5 — Payout Lifecycle (MANUAL_OPS / MOCK execution)
**Status:** PASS WITH LIMITATIONS
**Environment:** DEV only
**Real payment:** NOT IMPLEMENTED
**Real payout:** NOT IMPLEMENTED
**Production:** NOT APPROVED
**Schema changes:** NONE
**Architecture changes:** NONE
**State-machine changes:** NONE
**API contract changes to existing endpoints:** NONE
**Approved plan:** `EduTrust_Vertical_Slice_5_Implementation_Plan_v1.0.md` (followed; governance decisions U1 = MANUAL_OPS/MOCK, U2 = Admin/Ops-initiated)

---

# 1. Executive Summary

Vertical Slice #5 implemented the approved payout lifecycle end-to-end on the existing baseline:

```text
Completed eligible session → eligibility → calculation → payout item → PENDING →
Admin/Ops processing → PROCESSING → mock execution → PAID / FAILED →
ledger treatment → Event Ledger → audit → teacher/admin visibility →
PAID immutability (DB-enforced) → recovery/adjustment representation
```

Plus the approved blocked path (open dispute → payout blocked) and the post-paid representation (PAID rows immutable at the DB level; recovery only via separate adjustment/recovery ledger transaction — no recovery workflow implemented, per scope).

No migration was created or modified. No state machine was modified. No existing endpoint was changed. Real money and real payout providers remain completely outside the slice (U1).

---

# 2. Database

**Changes: NONE.** Verified against the live schema before implementation:

- `payouts` (id, teacher_id, amount, currency, status, eligible_at, paid_at, provider_reference) — used as-is.
- `payout_items` (payout_id, session_id **UNIQUE**, teacher_id, amount, currency) — used as-is; the unique constraint is the final double-pay guard.
- `ledger_transactions` (incl. `payout_id` column, `TEACHER_PAYOUT` type, DRAFT/POSTED/VOIDED statuses) and `ledger_entries` (balance constraint trigger, `TEACHER_PAYABLE`/`TEACHER_CASH` accounts) — used as-is.
- `validate_payout_item_eligibility` trigger (completed session + report + confirmed payment + teacher match + no open dispute) — untouched, remains the final consistency guard (exercised by the VS4 regression test).
- v1.4 `trg_00_payouts_paid_immutable_v1_4` (PAID rows immutable) — untouched; E2E proves it rejects updates.
- Refund tables/triggers (v1.1/v1.2/v1.3) — untouched; read-only consumption for the §10 calculation (APPROVED/PROVIDER_PENDING/SUCCEEDED partial-refund `teacher_adjustment_amount`).

The full approved chain `v1 → v1.1 → reconstructed v1.2 → v1.3 → v1.4` executed unmodified in both the automated environment and the E2E runtime. v1.2 provenance preserved.

---

# 3. Service layer (backend/edutrust_api/services.py — new VS5 section)

| Function | Behavior |
|---|---|
| `create_and_process_payout(user_id, roles, data, idempotency_key, request_id)` | OPS/ADMIN only. Validates teacher + unique non-empty session list. Sorted session ids (deterministic lock order). **TX1** (per API Arch §15.3): idempotency begin (key mandatory; replay → stored response; conflict → 409) → teacher `FOR UPDATE` → per session `FOR UPDATE` + ownership + eligibility (422 `PAYOUT_INELIGIBLE` with per-session reasons; 409 `PAYOUT_SESSION_ALREADY_PAYOUT`) → payout `PENDING` (U2: Admin/Ops-initiated) → items → `ELIGIBLE` (eligible_at) → DRAFT `TEACHER_PAYOUT` ledger (balanced DEBIT TEACHER_PAYABLE / CREDIT TEACHER_CASH) → `PAYOUT_ELIGIBLE` event → `PROCESSING`. **Mock execution** (outside DB tx, per §15.3; U1: deterministic MANUAL_OPS/MOCK, no provider, no money): PAID or forced FAILED. **TX2**: payout `PAID` (paid_at, `mock_payout_<id>` reference) + ledger `POSTED` + `PAYOUT_PROCESSED`, or payout `FAILED` + ledger `VOIDED` (draft never posted → no reversal needed, SM §12.6) + `ADMIN_ACTION` failure metadata. Idempotency completed atomically with TX2 (established pattern; crash-safe: in-flight same-key replays get the 409 processing guard, never a stale claim). |
| `_payout_ineligibility_reasons(row)` | Service-level checks per SM §12.2 / Addendum §10.5: `SESSION_NOT_COMPLETED`, `NO_SESSION_REPORT`, `NO_CONFIRMED_PAYMENT`, `OPEN_DISPUTE` (session or booking), `FULL_REFUND_EXISTS` (strict reading: any FULL refund row blocks — the documented plan decision). |
| `_calculate_session_net(row, payment_amount)` | Addendum §10.1: commission = amount × booking.platform_commission_bps / 10000 (quantized, matches VS2 ledger); gross = amount − commission; exposure = Σ `teacher_adjustment_amount` over PARTIAL refunds with status APPROVED/PROVIDER_PENDING/SUCCEEDED; net = gross − exposure (quantized to 0.01). |
| `get_payout_for_teacher(user_id, payout_id)` / `list_payouts_for_teacher(user_id)` | Teacher own-row enforcement via `teacher_profiles` join; 404 for foreign/unknown; **provider_reference omitted** from teacher views (internal mock identity). |
| `list_admin_payouts(user_id, roles, request_id)` | Operational list with teacher public name + provider_reference + item counts; `ADMIN_ACTION` + `ADMIN_ACCESS` security event (severity 2) on every read. |

Eligibility/calculation are enforced at service level **and** backed by the existing DB trigger (defense in depth, per API Arch §15.2 "must also be checked by API service logic").

---

# 4. API (urls.py, views.py)

| Method | URL | Roles | Result codes |
|---|---|---|---|
| GET | `/api/v1/teacher/payouts` | TEACHER (own) | 200 / 401 / 403 |
| GET | `/api/v1/teacher/payouts/<uuid>` | TEACHER (own) | 200 / 401 / 403 / 404 |
| POST | `/api/v1/admin/payouts/process` | OPS or ADMIN | 201 / 400 / 401 / 403 / 404 / 409 / 422 |
| GET | `/api/v1/admin/payouts` | OPS or ADMIN (audited) | 200 / 401 / 403 |

Paths, roles, request shape, `Idempotency-Key` requirement, and transaction boundary follow the approved API Arch §15 contract exactly. `force_mock_failure` is the DEV-only mock control (plan-approved; mirrors the VS2 mock boundary; no provider-specific behavior).

---

# 5. Concurrency / idempotency (as planned)

- Mandatory `Idempotency-Key` (`payout-<uuid>`), scope `payout_process`, canonical hash over `{teacher_id, session_ids, force_mock_failure}`.
- Same-key replay → stored 201 response (same payout id); conflicting payload → 409 `IDEMPOTENCY_KEY_CONFLICT`; in-flight same-key → 409 processing guard (safe; proven in tests).
- Overlapping concurrent batches (different keys, same session) → one 201 + one 409 `PAYOUT_SESSION_ALREADY_PAYOUT`; `payout_items.session_id UNIQUE` is the DB backstop. No double pay is possible.

---

# 6. Frontend (DEV consoles, existing pattern + tokens)

- **Teacher page** — "My Payouts": list (status, amount, items) + detail (items with session + amount). No provider reference shown (matches API contract).
- **Admin page** — "Payouts (operational)": list (teacher, status, amount, items, mock ref) + process console (teacher_id, comma-separated session_ids, force-mock-failure checkbox, automatic `payout-<uuid>` idempotency key, outcome line). Explicit "no real payout provider, no real money" note.
- Parent page unchanged (no parent payout visibility — approved). No new npm dependencies; `npm run build` passes (all routes compiled).

---

# 7. Files changed

| File | Change |
|---|---|
| `backend/edutrust_api/services.py` | +VS5 section (7 service functions + helpers) |
| `backend/edutrust_api/views.py` | +4 views with `require_roles` gates |
| `backend/edutrust_api/urls.py` | +4 routes (approved §15 paths) |
| `tests/test_vertical_slice_5.py` | NEW — 29 automated tests |
| `frontend/app/teacher/page.tsx` | +My Payouts console section |
| `frontend/app/admin/page.tsx` | +Payouts operational console section |
| `README.md` | VS5 section + updated test count (54 → 83) |
| Reports | 4 new VS5 report documents |

Untouched (verified by diff): all 5 migration files, root SQL provenance copies, all pre-VS5 tests, settings/middleware/audit/errors/permissions/auth/payments, domains, `requirements.txt`, `package.json`, `package-lock.json`.

---

# 8. Known limitations

- **No recovery workflow** (scope line is "representation" only): post-paid corrections are a future refund/recovery workstream; the DB immutability trigger and the ADJUSTMENT/`TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` representation are in place.
- **Crash window**: a process death between TX1 and TX2 leaves a `PROCESSING` payout with a DRAFT (unposted) ledger and a completed idempotency key — no money moved, no double pay; the payout is visible to admin. DEV-only operational edge (mock execution is a no-op computation in DEV).
- `PENDING→CANCELLED` / `FAILED→PROCESSING` (retry) transitions remain defined in the approved matrix but have no VS5 endpoint (their drivers — dispute/refund/account actions, retry policy — are out of scope); a new admin process call with a fresh key is the natural retry path and is supported by design.
- Frontend is a DEV console, not production UI.
- OPS-POL-005/006 remain OPEN policies; their defined unset behaviors (manual OPS release / admin-test-environment exception) are the DEV semantics actually implemented.

---

# 9. Governance statement

```text
VS5 IMPLEMENTATION: PASS WITH LIMITATIONS
DEV: allowed
STAGING: subject to dependency remediation and existing gate conditions
REAL PAYMENT: FORBIDDEN (mock provider only, untouched)
REAL PAYOUT: FORBIDDEN (mock/manual-ops only per U1; no provider, no credentials, no money)
PRODUCTION: NOT APPROVED
SCHEMA_CHANGE_REQUIRED: NO
STATE_MACHINE_CHANGE: NO
ARCHITECTURE_CHANGE: NO
API_CONTRACT_CHANGE: NO (additive endpoints per approved §15 contract)
MVP_SCOPE_EXPANDED: NO (payouts are explicit PRD MVP content)
V1_2_PROVENANCE: PRESERVED (RECONSTRUCTED v1.2 ≠ ORIGINAL v1.2)
VS6: NOT STARTED
```
