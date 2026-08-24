# EduTrust — Vertical Slice #5 Implementation Plan v1.0

**Slice:** DEV Vertical Slice #5 — Payout Lifecycle (MANUAL_OPS / MOCK execution)
**Status:** APPROVED SCOPE — IMPLEMENTATION PLANNED, NOT STARTED
**Environment:** DEV only · Real payout FORBIDDEN · Real payment FORBIDDEN · Production NOT APPROVED
**Approved decisions:** U1 = MANUAL_OPS/MOCK execution only · U2 = Admin/Ops-initiated PENDING batch creation (no scheduled jobs, no Celery, no automation)

**Class legend:** `AUTHORITATIVE` = stated in approved baseline docs · `INFERRED` = derived from approved docs · `PLAN-DECISION` = plan-level interpretation made explicit here, within the approved envelope (no new business rule, no structural change).

---

# 1. Exact VS5 boundaries

**In scope (the approved chain):**

```text
Eligibility → Calculation → Payout Item → PENDING → Admin/Ops Processing →
PAID / FAILED → Ledger → Event Ledger → Audit → Visibility →
Paid Payout Immutability → Recovery/Adjustment representation
```

**Out of scope — explicit exclusions (governance item 10 and boundary docs):**

```text
1.  Real payout providers, real money movement, live credentials, production payout
2.  Scheduled/automatic payout batching, Celery or any background payout automation (U2)
3.  New state transitions or any modification of the approved payout state machine (SM v1.0 §12)
4.  Refund Operations (initiate/approve/refund endpoints) — separate workstream
5.  Full Dispute Resolution (/admin/disputes/:id/resolve) — separate workstream
6.  Review Moderation — separate workstream
7.  User suspension / account actions
8.  Trust-metrics worker (derived metrics stay DB-protected, uncalculated)
9.  Payout CANCELLED transition — authority drivers (dispute/refund/account block, SM §12.3)
    are all out of VS5 scope; no cancel endpoint exists in VS5 (transition remains defined, unused)
10. Parent or student visibility of payouts (approved §15 contract grants none)
11. Notifications on payout events (Notifications workstream)
12. Any production UI (DEV console only)
13. Architecture, database, migration, API-architecture, state-machine, UX business-rule changes
14. Schema changes — none planned; none expected (see §21)
```

**Locked baselines (verification gate before/after implementation):** migrations `001–005` byte-identical; root SQL provenance copies untouched; v1.2 provenance warning intact (`RECONSTRUCTED v1.2 ≠ ORIGINAL v1.2`); all 54 existing tests unmodified and green; `requirements.txt` / `package.json` / `package-lock.json` unchanged (no new dependencies).

---

# 2. Endpoint inventory (exact approved contract, API Arch §15)

| # | Method | URL | Roles | Auth result | Purpose | Events |
|---|---|---|---|---|---|---|
| E1 | GET | `/api/v1/teacher/payouts` | TEACHER (own) | 401 anon / 403 other roles | List own payouts | — |
| E2 | GET | `/api/v1/teacher/payouts/<uuid>` | TEACHER (own) | 401 / 403 / 404 | Own payout detail (+ items) | — |
| E3 | POST | `/api/v1/admin/payouts/process` | OPS or ADMIN | 401 / 403 | Create + process one payout batch (mock execution) | `PAYOUT_ELIGIBLE`, `PAYOUT_PROCESSED` (on paid), `ADMIN_ACTION` |
| E4 | GET | `/api/v1/admin/payouts` | OPS or ADMIN (audited) | 401 / 403 | Operational payout monitoring | `ADMIN_ACTION` + `ADMIN_ACCESS` security event |

Notes:
- Paths follow the approved contract verbatim (teacher singular `teacher/payouts`, admin `admin/payouts[/process]`) — `AUTHORITATIVE`.
- E3 requires `Idempotency-Key` header (pattern `payout-<uuid>`) — `AUTHORITATIVE` (SM §12.3 "Required for batch"; API §15.3 header).
- E3 request body: `{ "teacher_id": "<uuid>", "session_ids": ["<uuid>", ...] }` — `AUTHORITATIVE` (API §15.3). `idempotency_scope` from the contract example is **not** a separate field: the approved `Idempotency-Key` header is the idempotency identity (PLAN-DECISION, consistent with the existing idempotency infrastructure which keys on scope+actor+header-key).
- E3 optional DEV-only body flag: `{ "force_mock_failure": true }` — PLAN-DECISION, DEV-only control mirroring the established VS2 mock boundary (`mock/succeed` + `mock/fail`); never used in any non-DEV path; used to exercise the approved `PROCESSING→FAILED` + recovery representation.
- New views: `teacher_payouts_list`, `teacher_payouts_detail`, `admin_payouts_process`, `admin_payouts` (one `require_roles` gate per the established pattern; 401 anonymous, 403 non-role — consistent with VS4 convention).

---

# 3. Service-layer workflow (single new VS5 section in `backend/edutrust_api/services.py`)

New service functions (reusing existing helpers `tx`, `fetchone/fetchall/execute`, `_idempotency_begin/_idempotency_complete`, `write_event`, `write_security_event`, `_serialize_row`, `get_roles`):

```text
S1  _payout_session_row(session_id)                    — session + booking + payment + teacher/parent joins
S2  _payout_eligibility_check(teacher_id, session_id)  — full service-level eligibility (see §5); returns (eligible, reason, net, gross)
S3  _calculate_session_net(session_row, refunds_rows)  — Addendum §10 calculation (see §6)
S4  create_and_process_payout(actor_user_id, roles, data, idempotency_key, request_id)
S5  get_payout_for_teacher(user_id, payout_id)         — own-row enforcement
S6  list_payouts_for_teacher(user_id)
S7  list_admin_payouts(actor_user_id, roles, request_id) — audited
```

### S4 — `create_and_process_payout` (E3) — two-transaction flow per API §15.3

```text
PRE-FLIGHT (no DB writes)
  - roles contain OPS or ADMIN (view gate)
  - Idempotency-Key present (400 IDEMPOTENCY_KEY_REQUIRED if absent — established pattern)
  - teacher_id + non-empty session_ids present (400 VALIDATION_ERROR)
  - sort session_ids ascending (deterministic lock order; deadlock avoidance — PLAN-DECISION)

TX1 — creation + eligibility (one atomic unit, per API §15.3 transaction boundary)
  1. _idempotency_begin("payout_process", actor, key, hash(canonical{teacher_id, session_ids, force_mock_failure}), "/api/v1/admin/payouts/process")
     → replay: return stored response_body; conflict: 409 IDEMPOTENCY_KEY_CONFLICT
  2. SELECT teacher_profile FOR UPDATE (teacher must exist → 404 RESOURCE_NOT_FOUND)
  3. FOR each session_id (sorted): SELECT sessions s JOIN bookings b JOIN parent/teacher profiles
     WHERE s.id = %s FOR UPDATE
     → session exists (404) and s.teacher_id = teacher (422 PAYOUT_SESSION_NOT_OWNED)
  4. Eligibility per session (§5) — ANY failure ⇒ 422 PAYOUT_INELIGIBLE with
     details: [{session_id, reason}] (all-or-nothing: nothing created — PLAN-DECISION,
     auditable; admin resubmits corrected list)
  5. Check session not already in payout_items → 409 PAYOUT_SESSION_ALREADY_PAYOUT (concurrency final guard; DB UNIQUE is backstop)
  6. INSERT payouts (teacher_id, amount=Σnets, currency='DZD', status='PENDING')      [U2: Admin/Ops-initiated]
  7. INSERT payout_items (per session: session_id, teacher_id, amount=net, currency)
  8. UPDATE payouts SET status='ELIGIBLE', eligible_at=now()                            [SM §12.3 PENDING→ELIGIBLE, authority OPS/admin process]
  9. INSERT ledger_transactions (transaction_type='TEACHER_PAYOUT', status='DRAFT',
        teacher? — no teacher column exists; reference carries payout id) (reference='payout:<id>', booking_id/payment_id NULL-allowed per schema)
  10. INSERT balanced ledger_entries (DRAFT stage):
        DEBIT  TEACHER_PAYABLE   Σnets   memo 'payout payout:<id>'
        CREDIT TEACHER_CASH      Σnets   memo 'payout payout:<id>'
        (entries balanced per the approved balance constraint — see §11)
  11. write_event('PAYOUT_ELIGIBLE', 'payout', payout_id, actor, role, metadata={session_ids, item_count, total, dev_mock:true})
  12. UPDATE payouts SET status='PROCESSING'                                              [SM §12.3 ELIGIBLE→PROCESSING]
  13. _idempotency_complete("payout_process", actor, key, 201, response, "payout", payout_id)
  COMMIT

MOCK EXECUTION (outside DB transaction — per API §15.3 "Outside DB transaction")
  - MANUAL_OPS/MOCK per U1: no provider call, no credentials, no money.
  - result = FAILED if force_mock_failure else PAID
  - provider_reference = "mock_payout_<payout_id>" on PAID (mock identity, DEV-only — PLAN-DECISION; no provider-specific behavior invented)

TX2 — outcome (per API §15.3 second boundary)
  14. SELECT payout FOR UPDATE
  15. PAID path:      UPDATE payouts SET status='PAID', paid_at=now(), provider_reference='mock_payout_<id>'
                      UPDATE ledger_transactions SET status='POSTED' (final TEACHER_PAYOUT posted only on success — SM §12.5.3)
                      write_event('PAYOUT_PROCESSED', 'payout', payout_id, actor, role, metadata={provider_reference, dev_mock:true})
  16. FAILED path:    UPDATE payouts SET status='FAILED'
                      UPDATE ledger_transactions SET status='VOIDED'   (DRAFT never posted → no money moved; no reversal required — §12.6; VOIDED is an approved ledger status)
                      write_event('ADMIN_ACTION', 'payout', payout_id, actor, role, metadata={action:'PAYOUT_PROCESS_FAILED', dev_mock:true, reason:'mock_failure_forced'})
  17. COMMIT
  18. Return {payout: {…status, amount, eligible_at, paid_at, provider_reference?}, items: […], ledger: {transaction_id, status}, result: 'PAID'|'FAILED'}
```

Deadlock/serialization notes: session locks acquired in sorted id order; idempotency row locked first (existing mechanism); payout row locked in TX2. Concurrent E3 calls on overlapping sessions: one wins, the other gets 409 (step 5) — deterministic.

---

# 4. Authorization matrix

| Endpoint | Anonymous | PARENT | TEACHER | OPS | ADMIN | Foreign TEACHER |
|---|---|---|---|---|---|---|
| E3 process | 401 | 403 | 403 | **200/201** (mock) | **200/201** (mock) | 403 |
| E4 admin list | 401 | 403 | 403 | **200 audited** | **200 audited** | 403 |
| E1 teacher list | 401 | 403 | **200 (own only)** | 403 | 403 | 403 |
| E2 teacher detail | 401 | 403 | **200 (own only)** | 403 | 403 | 404/403 (not own → 403) |

- Teacher "own only" enforced by `teacher_profiles.user_id` join, per the established ownership pattern — `AUTHORITATIVE` (API §15 roles; §4.2 object ownership).
- OPS/ADMIN operational reads write `ADMIN_ACTION` (entity `payouts`) + `ADMIN_ACCESS` security event (severity 2) — `AUTHORITATIVE` (API §15 + established VS2–VS4 admin-audit pattern).
- OPS-POL alignment (governance, not new rules): OPS-POL-005 unset → "Payout eligibility must remain blocked or require manual OPS release" — admin-initiated processing **is** the manual OPS release path; OPS-POL-006 unset → "Payout processing disabled except admin test environment" — DEV is the admin test environment. `AUTHORITATIVE` unset-behaviors.

---

# 5. Payout eligibility rules (service-level, per session)

`AUTHORITATIVE` sources: SM v1.0 §12.2, v1.1 Addendum §10.5, API Arch §15.2, DB trigger `validate_payout_item_eligibility` (final consistency guard, already live and VS4-tested).

| # | Rule | Source | Failure code/reason |
|---|---|---|---|
| 1 | `session.status = 'COMPLETED'` | §12.2 / trigger | `SESSION_NOT_COMPLETED` |
| 2 | Session belongs to the payout teacher (`s.teacher_id = teacher`) | §12.2 / trigger | `SESSION_NOT_OWNED` |
| 3 | Session report exists | §12.2 / trigger | `NO_SESSION_REPORT` |
| 4 | Confirmed payment exists for the booking | §12.2 / trigger | `NO_CONFIRMED_PAYMENT` |
| 5 | No open dispute (`status IN ('OPEN','UNDER_REVIEW')`) on session or booking | §12.2 / trigger (overlay model) | `OPEN_DISPUTE` |
| 6 | No full refund for the booking — PLAN-DECISION (strict): any `refunds` row with `refund_type='FULL'` blocks, regardless of refund status (strictest reading of "no full refund exists"; the alternative — blocking only at specific refund statuses — is not documented, and strictness is the financially safe side) | §10.5 / trigger-free (service-enforced per §12.2 "service layer must enforce … refund adjustments") | `FULL_REFUND_EXISTS` |
| 7 | `net_teacher_payable > 0` (see §6) | §10.5 | `NET_PAYABLE_ZERO` |
| 8 | Session not already included in `payout_items` | §10.5 / `payout_items.session_id UNIQUE` | `ALREADY_IN_PAYOUT` (409 under concurrency) |
| 9 | Payout delay / dispute window — OPS-POL-005/006 OPEN and unset; unset behaviors are defined (see §4) and satisfied by the admin-initiated DEV path | OPS docs | (documented, not a code check) |

Rule 6 is the only PLAN-DECISION in eligibility; it is flagged here for the record and does not alter any approved rule (it only selects the strict reading of an approved condition that the DB trigger does not itself check).

---

# 6. Calculation rules (authoritative Addendum §10)

Per eligible session `s` (booking `b`, confirmed payment `p`):

```text
commission            = p.amount × b.platform_commission_bps / 10000          (matches VS2 payment-confirmation ledger — AUTHORITATIVE pattern)
gross_teacher_payable = p.amount − commission                                 (AUTHORITATIVE: "gross teacher payable" per §10.4 example: 2000 − 300 = 1700)
refund_exposure       = Σ r.teacher_adjustment_amount
                        over refunds r where r.booking_id = b.id
                        AND r.refund_type = 'PARTIAL'
                        AND r.status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')   (AUTHORITATIVE: §10.1/§10.2 — approved & provider-pending refunds reduce exposure before provider success)
other_deductions      = 0  (no other approved deductions defined for DEV — nothing invented)
net_teacher_payable   = gross_teacher_payable − refund_exposure − other_deductions   (§10.1 formula)

Payout-level:  payout.amount = Σ net over all batch sessions;  item.amount = net per session
Rounding: quantize to 0.01 (schema NUMERIC(12,2), currency DZD — INFERRED-minor, U7)
```

Addendum §10.4 worked example (used verbatim as a test vector): price 2000, commission 300 → gross 1700; approved partial refund 400 (teacher adjustment 300, platform adjustment 100) → **net 1400**.

---

# 7. Blocked payout behavior

- **Pre-creation (service):** rules 5/6/7/8 → 422 `PAYOUT_INELIGIBLE` with per-session reasons; nothing created (all-or-nothing, §3).
- **DB backstop:** `validate_payout_item_eligibility` trigger rejects direct/accidental item inserts (dispute, no report, no confirmed payment, teacher mismatch) — live, VS4-tested.
- **Concurrency:** overlapping batches on the same session → one 201, one 409 `PAYOUT_SESSION_ALREADY_PAYOUT` (lock + check + `payout_items.session_id UNIQUE`).
- **Policy-unset blocking:** OPS-POL-005/006 unset behaviors remain in force (§4) — no code path bypasses eligibility/dispute checks (Feature Flag Governance constraint).

# 8. Failure behavior (`PROCESSING→FAILED`)

- DEV-only entry: `force_mock_failure: true` (E3 body) — no real provider failure is possible or attempted (U1).
- Effects (TX2): payout `FAILED`; DRAFT ledger transaction `VOIDED` (never posted → no funds moved → no reversal needed, per §12.6); `ADMIN_ACTION` event with failure metadata; **no** `PAYOUT_PROCESSED` (event is "if paid" — §12.3).
- Recovery posture: session is NOT re-eligible via retry within VS5 (retry = new batch with the same sessions; §12.3 `FAILED→PROCESSING` retry row exists in the approved matrix but its DEV trigger is a new admin process call with a new idempotency key — supported by design, not by a new endpoint; documented, not invented).
- `PAID→FAILED` remains forbidden (SM §12.4) — enforced by the v1.4 immutability trigger.

# 9. Paid behavior (`PROCESSING→PAID`)

- Effects (TX2): payout `PAID`, `paid_at=now()`, `provider_reference='mock_payout_<id>'` (mock identity, DEV-only); ledger transaction `DRAFT→POSTED` (final `TEACHER_PAYOUT` posted only on success — §12.5.3); `PAYOUT_PROCESSED` event.
- Teacher visibility updates immediately (E1/E2).
- Post-paid correction is **not** a VS5 feature (belongs to Refund Operations / recovery workstream); the representation exists (§12).

# 10. Immutability behavior

- **Paid payout rows:** DB-enforced by v1.4 `trg_00_payouts_paid_immutable_v1_4` — any `UPDATE` on a PAID row raises "PAID payout rows are immutable; create a separate adjustment/recovery transaction". VS5 code never updates PAID rows; tests assert the DB rejects it (read-only verification of the existing guard).
- **Ledger:** `ledger_entries` append-only (existing trigger); `ledger_transactions.status` transitions are DRAFT→POSTED/VOIDED only in VS5 (no mutation of posted entries).
- **No deletion anywhere** ("Never delete payout records" — API §15.3).

# 11. Ledger entries

| Stage | `ledger_transactions` | `ledger_entries` (balanced — constraint trigger, deferrable) |
|---|---|---|
| TX1 (PENDING→ELIGIBLE→PROCESSING) | INSERT `transaction_type='TEACHER_PAYOUT'`, `status='DRAFT'`, `reference='payout:<payout_id>'` | DEBIT `TEACHER_PAYABLE` Σnets · CREDIT `TEACHER_CASH` Σnets (memo `payout <id>`) |
| TX2 PAID | UPDATE `status='POSTED'` | none (entries unchanged — posting, not mutation) |
| TX2 FAILED | UPDATE `status='VOIDED'` | none (draft voided; no funds moved; no reversal needed per §12.6) |
| Post-paid recovery (future workstream — representation only) | separate `ADJUSTMENT` transaction with reversal entries; accounts `TEACHER_RECOVERABLE` / `PLATFORM_REFUND_EXPENSE` exist (v1.1) | not implemented in VS5 |

Balance invariant: every transaction's debits = credits (existing deferred constraint trigger enforces; both VS5 stages are balanced by construction).

# 12. Event Ledger events

| Event | When | Entity | Metadata (no secrets) |
|---|---|---|---|
| `PAYOUT_ELIGIBLE` | TX1 step 8 | payout | session_ids, item_count, total, dev_mock |
| `PAYOUT_PROCESSED` | TX2 on PAID only | payout | provider_reference, dev_mock |
| `ADMIN_ACTION` | E3 invocation (processing); E4 reads; failure path | payout / payouts | action names, dev_mock |

All three types exist in the enum — **no missing event types, none invented**. `event_ledger` append-only trigger untouched.

# 13. Audit events (security)

- E4 (admin/ops list read): `ADMIN_ACCESS` security event, severity 2, entity `payouts` (established pattern, identical to VS2–VS4 admin reads).
- E2/E1 teacher reads: no security event (non-sensitive own data — consistent with existing teacher reads).
- No logging of credentials, tokens, or provider secrets (U1); mock provider reference is a synthetic DEV string.

# 14. Recovery/adjustment representation (approved scope line: "representation", not full flow)

VS5 delivers the **representation and its guards**, not the recovery flow (which requires Refund Operations):

1. PAID rows immutable at DB level (v1.4 trigger) — VS5 tests verify a direct UPDATE is rejected with the adjustment/recovery message.
2. Ledger reversal-only correction path documented: post-paid correction = new `ADJUSTMENT` ledger transaction with reversal entries (never UPDATE/DELETE) — accounts `TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE` reserved (v1.1), used by the future refund workstream per Addendum §11.
3. FAILED path demonstrates the in-DEV correction: DRAFT→VOIDED with no funds moved (§12.6).
4. No recovery endpoints in VS5.

# 15. Visibility

- **Admin/Ops (E4):** operational list — payout id, teacher (public name), status, amount, currency, item_count, eligible_at, paid_at, provider_reference, created_at; audited. (Field set: INFERRED from §15 "Monitor payouts" + established admin-list patterns.)
- **Teacher (E1/E2):** own payouts — id, status, amount, currency, eligible_at, paid_at, created_at; detail adds items (session_id, amount) — **provider_reference omitted from teacher views** (internal mock identity — PLAN-DECISION, conservative).
- **Parent/Student:** none (approved contract grants no payout endpoints to parents — explicit non-scope).

# 16. Concurrency / idempotency strategy

- **Idempotency (E3):** mandatory `Idempotency-Key` (`payout-<uuid>`), scope `payout_process`, actor = invoking admin/ops user, hash over canonical `{teacher_id, session_ids, force_mock_failure}` — replay returns stored 201 response; conflicting payload → 409 `IDEMPOTENCY_KEY_CONFLICT` (established v1.1/v1.3 mechanism, untouched).
- **Locking:** idempotency row (existing `FOR UPDATE` in `_idempotency_begin`) → teacher row → session rows in sorted-id order (deadlock-free) → payout row (TX2).
- **Uniqueness backstop:** `payout_items.session_id UNIQUE` (DB) — a session can appear in exactly one payout item ever.
- **Expected outcomes (tested):** two concurrent identical E3 (same key) → one 201 + one 201-replay (same payout id); two concurrent E3 (different keys, overlapping sessions) → one 201 + one 409; no duplicate items ever.

# 17. Tests (new file `tests/test_vertical_slice_5.py`; all 54 existing tests unchanged)

**Eligibility & calculation (8):**
1. Eligible completed+reported session with confirmed payment → 201 PAID, payout + 1 item, correct net (Addendum §10.4 vector: 2000/300 commission → 1700 gross)
2. Partial refund (APPROVED) reduces net per §10.1 (vector: −300 teacher adjustment → 1400); PROVIDER_PENDING and SUCCEEDED exposures counted
3. Session not completed → 422 `SESSION_NOT_COMPLETED`
4. No session report → 422 `NO_SESSION_REPORT`
5. Open dispute blocks → 422 `OPEN_DISPUTE` (overlay; booking/session stay COMPLETED)
6. Full refund on booking → 422 `FULL_REFUND_EXISTS` (strict rule)
7. Net = 0 (refund exposure ≥ gross) → 422 `NET_PAYABLE_ZERO`; no payout/item rows
8. Multi-session batch: payout.amount = Σ nets, per-item nets correct, teacher ownership enforced (foreign session in list → 422)

**Lifecycle, ledger, events (7):**
9. PAID path: payout PAID + paid_at + mock provider_reference; ledger tx POSTED, balanced DEBIT TEACHER_PAYABLE / CREDIT TEACHER_CASH; `PAYOUT_ELIGIBLE` + `PAYOUT_PROCESSED` events present
10. FAILED path (`force_mock_failure`): payout FAILED; ledger tx VOIDED; no `PAYOUT_PROCESSED`; `ADMIN_ACTION` failure metadata
11. Ledger balance invariant holds across both paths (query-level debit=credit assertion)
12. PENDING is never the final status of a processed batch (atomic PENDING→ELIGIBLE→PROCESSING within E3)
13. PAID payout row UPDATE rejected by v1.4 trigger (direct DB attempt, expect exception naming adjustment/recovery)
14. ledger_entries append-only: direct UPDATE on posted entry rejected (existing trigger)
15. `payout_items.session_id UNIQUE`: session from a PAID batch cannot be re-payouted (409 `ALREADY_IN_PAYOUT`)

**Idempotency & concurrency (5):**
16. Same key + same payload replay → 201, same payout id, exactly one payout
17. Same key + different payload → 409 `IDEMPOTENCY_KEY_CONFLICT`
18. Missing Idempotency-Key → 400
19. Concurrent E3, same key → [201, 201-replay]
20. Concurrent E3, different keys, overlapping sessions → [201, 409], exactly one item

**Authorization & visibility (7):**
21. Teacher lists own payouts (200, own only); teacher detail 200; foreign teacher 403/404
22. Teacher views exclude `provider_reference`
23. Parent cannot list/read payouts (403); anonymous 401 on all four endpoints
24. OPS can process + list (200/201); ADMIN likewise
25. Admin/ops list read audited: `ADMIN_ACTION` (entity `payouts`) + `ADMIN_ACCESS` security event
26. E3 by PARENT/TEACHER role → 403
27. Admin process of empty `session_ids` / missing teacher → 400/404 validation

**Regression (1):**
28. Full existing suite (foundation 5 + VS1 5 + VS2 7 + VS3 9 + VS4 28) unmodified and green — executed in the same run

Target: **≥ 27 new tests; total ≥ 81 passing.**

# 18. E2E scenarios (isolated temp PostgreSQL + full v1→v1.4 chain + Django + Next.js; `bash`-driven against live servers)

```text
E2E_MAIN:
  teacher register/login (existing helpers) → admin process NOT yet possible (no eligible session)
  → 2nd cycle: parent student → hold → mock payment → session start/complete → teacher report
  → admin POST /admin/payouts/process {teacher_id, session_ids:[s]} + Idempotency-Key: payout-<uuid>
  → 201 PAID; payout + item amounts match expected net (computed from DB: price − commission)
  → GET /api/v1/admin/payouts (audited) shows the payout
  → GET /api/v1/teacher/payouts (teacher) shows own PAID payout with item
E2E_E2E_REPLAY: same key + payload → 201 same payout id
E2E_UNAUTHORIZED: parent/foreign-teacher reads 403; anonymous 401; teacher process 403
E2E_BLOCKED: open dispute on a fresh completed+reported session → process → 422 OPEN_DISPUTE, booking/session still COMPLETED
E2E_FAILURE: force_mock_failure batch on another eligible session → 201 FAILED, ledger VOIDED, no PAYOUT_PROCESSED
E2E_CONCURRENCY: two parallel process calls (different keys, same session) → one 201 + one 409, one item
E2E_IMMUTABILITY: psql UPDATE on the PAID payout row → rejected with v1.4 message (read-only proof, run from test harness psql)
E2E_FRONTEND: /teacher and /admin pages serve; teacher page shows payout console; admin page shows payout process console
E2E_ADMIN_AUDIT: admin/events contains PAYOUT_ELIGIBLE + PAYOUT_PROCESSED + ADMIN_ACTION; security-events count grew
Expected: E2E_MAIN / E2E_REPLAY / E2E_UNAUTHORIZED / E2E_BLOCKED / E2E_FAILURE / E2E_CONCURRENCY / E2E_IMMUTABILITY / E2E_FRONTEND / E2E_ADMIN_AUDIT = PASS
```

# 19. Frontend DEV scope (minimal console, existing pattern + tokens; no production UI)

- **Teacher page** — "Payouts" section: `Load my payouts` (list: status badge, amount DZD, eligible/paid dates), `View payout` (detail with items: session + amount). Uses existing `apiGet`; no provider reference shown (matches E1/E2 contract).
- **Admin page** — "Payouts (DEV mock)" section: `Load payouts` (operational list incl. provider_reference), process console: teacher_id + session_ids inputs (comma-separated) + `Process payout (mock)` button sending `Idempotency-Key: payout-<randomUUID>` and optional `force_mock_failure` checkbox; result state line (PAID/FAILED + payout id). Activity log records audit notes.
- **Parent page:** no changes (no parent payout visibility — approved).
- `npm run build` must pass; no new npm dependencies.

# 20. Documentation deliverables (post-implementation)

```text
EduTrust_DEV_Vertical_Slice_5_Implementation_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_5_Test_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_5_E2E_Report_v1.0.md
EduTrust_DEV_Dependency_Audit_v1.4.md (re-run; no --force)
README.md: VS5 section (endpoints, boundaries, test count) — same style as VS1–VS4
```

# 21. Schema / structural change assessment

| Change class | Required? | Note |
|---|---|---|
| Architecture | NO | new service section + 4 views + 4 routes in existing monolith |
| Database / migrations | NO | `payouts`, `payout_items`, `ledger_*`, `refunds` (adjustment fields), triggers, v1.4 immutability, event enum all already in v1→v1.4 (verified against live schema 2026-08-24) |
| API architecture | NO | additive endpoints exactly per approved §15 contract |
| State machines | NO | payout states/transitions per SM §12; CANCELLED transition defined but unused (drivers out of scope) |
| UX business rules | NO | DEV console only |
| MVP scope | NO | payouts are explicit PRD MVP content |

**Contingency (governance item 4):** if implementation discovers an actual approved blocker requiring schema change, STOP that portion and report `SCHEMA_CHANGE_REQUIRED: YES` with reason/table/column/minimal change/state-machine impact/migration proposal before applying anything. Not anticipated.

# 22. Definition of done (VS5)

```text
- All §5 eligibility rules enforced at service level + DB backstop intact
- §6 calculation exact (Addendum §10.4 vector test green)
- PENDING→ELIGIBLE→PROCESSING→PAID/FAILED per SM §12.3 (mock execution per U1)
- Ledger DRAFT→POSTED (paid) / DRAFT→VOIDED (failed), always balanced; no posted-entry mutation
- PAYOUT_ELIGIBLE / PAYOUT_PROCESSED / ADMIN_ACTION events recorded; admin reads audited
- PAID immutability verified (v1.4 trigger); recovery representation documented
- Idempotency replay/conflict + concurrency one-winner behavior proven (tests + E2E)
- Teacher own-only visibility (no provider_reference); admin operational visibility audited; parent none
- 54 pre-existing tests green + ≥27 new VS5 tests green (total ≥81)
- E2E scenarios all PASS on isolated runtime with full unmodified migration chain
- Frontend build passes; DEV consoles functional
- requirements/package files byte-identical; migrations byte-identical; v1.2 provenance intact
- Dependency audit re-run without --force; findings reported (expected: same 2 high, DEV-accepted)
- No real payout, no real payment, no provider credentials, no production exposure
- VS6 NOT started; no review moderation / refund operations / dispute resolution code introduced
```

# 23. Plan governance statement

```text
VS5_SCOPE_APPROVED: YES (per user approval, 2026-08-24)
U1: APPROVED — MANUAL_OPS / MOCK
U2: APPROVED — ADMIN/OPS INITIATED
IMPLEMENTATION_STARTED: NO
DATABASE_MODIFIED: NO
ARCHITECTURE_MODIFIED: NO
STATE_MACHINE_MODIFIED: NO
COMMIT_CREATED: NO
```
