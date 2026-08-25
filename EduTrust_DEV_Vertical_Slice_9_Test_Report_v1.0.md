# EduTrust — DEV Vertical Slice #9 Test Report v1.0

**Sprint:** DEV Vertical Slice #9 — Dispute Resolution (R2), CORE scope
**Environment:** Python 3.11.2 venv (`/home/user/.venv-edutrust`; Django 5.2.17, psycopg 3.2.13, pytest 8.4.2, pytest-django 4.14.0) · PostgreSQL 16.2 (pgserver wheel, PGXS-built `pgcrypto`/`citext`/`btree_gist`) · fresh isolated cluster per run (trust auth, `scripts/run_migrations.py` chain v1→v1.4)
**Status:** PASS — 197/197 (full repository suite, fresh run) · 37/37 VS9 tests

---

# 1. Results

| Run | Scope | Result |
|---|---|---|
| Full repository suite (`pytest -q tests`, fresh isolated PG 16.2 + migrations) | 160 committed (VS1–VS8) + 37 VS9 | **197 passed in 430.40s — 0 failed, 0 skipped** |
| VS9 alone (`pytest -q tests/test_dispute_resolve.py tests/test_dispute_resolve_concurrency.py`, fresh cluster) | 33 unit + 4 concurrency | **37 passed in 119.22s** |
| VS8 E2E re-run on the VS9 tree (`tests/e2e_refund_lifecycle.py`) | 7 scenarios + 8 financial gates | **53/53 PASS** (VS8 protection — see E2E report) |

Historical baseline (unchanged): 160 committed tests = 118 (VS1–VS7) + 42 (VS8: 38 service + 4 concurrency). VS9 adds 37 (33 service + 4 concurrency). No committed test was modified or weakened — all VS1–VS8 test files byte-identical to `b73d8ce` (verified by diff); VS9 only adds new test files.

# 2. Coverage map (VS9 — 37 tests)

`tests/test_dispute_resolve.py` (33; plan test IDs T-01…T-34 + regression):

| Area | Tests | What is verified (incl. direct DB assertions) |
|---|---|---|
| Record-only resolution | T-01, T-02, T-17, T-18, T-19, T-20 | NO_ACTION/WARNING/PAYOUT_BLOCKED/PAYOUT_RELEASED/REPORT_CORRECTION_REQUIRED → RESOLVED + `DISPUTE_RESOLVED` + `ADMIN_ACTION`; no refund row, no ledger tx, payment untouched; UNDER_REVIEW from-set honored; no-show confirmations mutate the session only when SCHEDULED (VS3 authority), record-only otherwise |
| Authorization | T-04, T-05 | parent/teacher/SUPPORT 403, anonymous 401, OPS 200; SAFETY → OPS 403 / ADMIN 200 (priority 1 intact) |
| Invalid states / exclusions | T-03, T-06, T-21, T-27, T-28, T-29 | terminal re-resolve 409 `DISPUTE_INVALID_STATE`; excluded actions (incl. both account actions) 400; `account_action` non-null 400; unknown dispute 404; resolution validation 400; `refund_amount` on non-refund action 400 — each with dispute-stays-OPEN DB check |
| Refund integration (P1 two-step) | T-07, T-08, T-09, T-10, T-11 | PARTIAL/FULL create linked `REQUESTED` refund (no ledger tx yet; payment CONFIRMED at creation); FULL must equal payment amount; PARTIAL strictly below; **T-10:** follow-up partial on `PARTIALLY_REFUNDED` → 409 `REFUND_INVALID_STATE` (approved VS8 contract — O7 gap; plan T-10 correction, proven on the pure VS8 direct path) with full rollback (dispute OPEN, no refund row); **T-11:** VS8 approve (300/100) → mock succeed → `PARTIALLY_REFUNDED`, Form D entries POSTED at DB level (TEACHER_PAYABLE 300 / PLATFORM_REVENUE 100 / CLEARING 400), `PAYMENT_PARTIALLY_REFUNDED` exactly once, `REFUND_ISSUED` globally 0, `linked_refunds[]` visible |
| Payout interaction | T-12, T-15, T-16 | open dispute → 422 `OPEN_DISPUTE`, 0 payout items; resolve → payout 201 PAID 1700 (2000 − 15% commission, VS5 behavior unchanged); **T-12 post-paid:** Form A entries POSTED (TEACHER_RECOVERABLE 300 / PLATFORM_REFUND_EXPENSE 100 / CLEARING 400) with the old PAID payout byte-identical (v1.4) |
| Ledger integrity (failure/reconciliation) | T-13, T-14 | mock failure → `FAILED` + payment restored CONFIRMED + DRAFT **VOIDED** (no premature POSTED) + no `PAYMENT_*` event; reconciliation (MANUAL_RECONCILIATION) → SUCCEEDED/REFUNDED with proof + actor attribution; dispute stays RESOLVED through the refund lifecycle (G1 documented) |
| Idempotency | T-22, T-23, T-24 + **R-2 regression** | replay same key+body → 200 original, single refund row, single `DISPUTE_RESOLVED`; same key different body → 409 `IDEMPOTENCY_KEY_CONFLICT`; missing key → 400 `IDEMPOTENCY_KEY_REQUIRED`; **R-2 regression:** successful resolve response and its stored idempotency body are plain-JSON serializable (the UUID-canonical defect class), replay returns the identical refund |
| Admin list + audit | T-25, T-26, T-30 | list (200 + pagination + status/category/priority filters, cross-interaction), reads audited (`ADMIN_ACCESS` + `ADMIN_ACTION` READ_DISPUTE_LIST deltas at DB level), SUPPORT allowed / parent+teacher 403; SM §11.7 fields stored (resolution/resolved_at/resolver) + `ADMIN_ACTION` carries the refund reference |
| Terminality + overlay | T-31, T-34 | booking/session never DISPUTED (Addendum §4.1); terminal dispute no-reopen (409) but a fresh dispute for the same interaction is allowed |

`tests/test_dispute_resolve_concurrency.py` (4; plan C-01…C-04 — threading.Barrier races, all DB-asserted):

| Test | Race | Verified at DB level |
|---|---|---|
| C-01 | two concurrent RESOLVE, different keys, different actors | exactly [200, 409]; status RESOLVED, exactly one `DISPUTE_RESOLVED` event — one authoritative transition |
| C-02 | concurrent APPROVE of two REQUESTED refunds (one dispute-linked, one direct VS8) over a 2000 payment | exactly [200, 409] (over-refund under lock, Addendum §15.4); reserved ≤ payment amount; 0 POSTED txs (neither is SUCCEEDED yet — no double posting) |
| C-03 | resolve NO_ACTION vs payout processing | resolve 200; payout 422 (0 items) or 201 (exactly 1 item) — never paid-while-open, never double |
| C-04 | same idempotency key concurrent | [200, 200] (replay) or [200, 409] (in-flight); exactly one resolution + one event |

# 3. Financial invariants asserted directly in SQL (not via HTTP only)

Every POSTED refund tx ↔ SUCCEEDED refund; all ledger transactions balanced (VS8 E2E S-gates + unit assertions); no premature POSTED (DRAFT VOIDED on failure); allocation integrity (teacher + platform = approved); no duplicate refund per dispute/payment-key; no duplicate payout item per session; no duplicate provider-event identity; terminal-state timestamps complete; `REFUND_ISSUED` = 0 rows globally; no real provider events.

# 4. Test-infrastructure repairs made during this slice (record, with cause)

All repairs were made to **VS9's own test files only** (no VS1–VS8 test file touched), each verified against approved behavior before being made:

1. `test_dispute_resolve.py:31` — import `create_held_booking` → `make_held_booking` (the existing VS2 helper; the VS8 `test_refund_service.py` uses the identical import). Fixed the canonical-suite collection abort (audit finding R-1).
2. T-06/T-28 — the loops re-opened a dispute per iteration while the previous one stayed OPEN; VS4's service invariant allows one active dispute per interaction, so the second open is a legitimate `DUPLICATE_DISPUTE` 409. Fixed by closing the dispute between iterations (the 400-under-test is unaffected).
3. T-10 — plan T-10 expected `OVER_REFUND`; the approved VS8 creation contract (byte-identical, protected) status-gates first — proven on the pure VS8 direct path that both 600.00 and the exact 500.00 remainder return `REFUND_INVALID_STATE`. Test now asserts the approved-contract error + the plan's rollback guarantee. (O7 contract gap unchanged.)
4. T-12/T-16 — switched to the VS5 `completed_with_report()` fixture: payout eligibility requires a session report (`NO_SESSION_REPORT`), which the plain completed-session fixture does not write.
5. T-25 — the second SAFETY dispute now opens on a different interaction (VS4 one-active-dispute-per-interaction); filter assertions made order-independent (the shared test DB accumulates disputes across tests); LIKE patterns parameterized (psycopg3 rejects `%D` as a placeholder).
6. T-30 — LIKE pattern parameterized (same psycopg placeholder class).
7. C-01/C-04 — `SELECT status::text, count(*) … WHERE id=…` is invalid SQL (non-aggregated column without GROUP BY); split into status + count queries (PK uniqueness makes the count assertion intact).

# 5. Result

```text
VS9_TESTS:            37 (33 service + 4 concurrency)
VS9_TEST_RESULT:      37/37 PASSED (fresh isolated PG 16.2, 119.22s)
FULL_SUITE:           197/197 PASSED (430.40s; 160 committed + 37 VS9; 0 failed, 0 skipped)
COMMITTED_BASELINE:   160/160 — unregressed (VS1–VS8 test files byte-identical to b73d8ce)
DB_LEVEL_ASSERTIONS:  present in all 37 VS9 tests (status/ledger/events/refund/payout rows)
HISTORICAL_EVIDENCE:  baseline counts from the VS8 test report (160 = 118 + 42) — unchanged
LIMITATION:           concurrency tests use 2-thread barrier races on a single-node runtime (repo convention; no distributed-DB simulation)
```
