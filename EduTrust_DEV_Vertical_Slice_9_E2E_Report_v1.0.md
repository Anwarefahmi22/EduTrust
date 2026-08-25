# EduTrust — DEV Vertical Slice #9 E2E Report v1.0

**Sprint:** DEV Vertical Slice #9 — Dispute Resolution (R2), CORE scope
**Suite:** `tests/e2e_dispute_resolution.py` (standalone; not pytest-collected — repo convention)
**Environment (fresh, isolated):** temporary PostgreSQL 16.2 cluster (pgserver wheel, port 55481, trust auth) + full migration chain v1→v1.4 + Django dev server (port 8101) + **Next.js production server** (`npm run build` → `next start`, port 3101) + scripted scenario checks over live HTTP + direct-SQL checks via `psql`
**Status:** PASS — **75/75 checks, 15/15 scenarios** (`E2E_DISPUTE_RESOLUTION=PASS`)

---

# 1. Scenario results (all PASS)

| # | Scenario | Checks | What was verified (HTTP + DB) |
|---|---|---|---|
| S1 | Normal resolution | 4 | OPS resolve NO_ACTION → 200 RESOLVED; no refund for record-only; `DISPUTE_RESOLVED` event = 1; parent sees the resolution in dispute detail |
| S2 | Unauthorized roles | 5 | parent (opener) 403, teacher (participant) 403, anonymous 401; admin list 403 for parent and teacher |
| S3 | Invalid transitions | 4 | first resolve 200; re-resolve of RESOLVED → 409 `DISPUTE_INVALID_STATE`; both account actions → 400 `VALIDATION_ERROR` (excluded) |
| S4 | Full refund (two-step) | 5 | FULL_REFUND → refund REQUESTED/FULL; VS8 approve (1400/600) → PROVIDER_PENDING; mock success → SUCCEEDED / payment REFUNDED; ledger tx POSTED; parent payment detail shows the SUCCEEDED refund (SUCCEEDED-only rule) |
| S5 | Partial refund + authority | 5 | **OPS** FULL_REFUND after a COMPLETED session → 403 (P4 / SM §18.2); **OPS** PARTIAL_REFUND 400 → REQUESTED/PARTIAL; approve (300/100) → PROVIDER_PENDING; success → PARTIALLY_REFUNDED; payout → 422 (payment not CONFIRMED — VS5 `NO_CONFIRMED_PAYMENT` guard) |
| S6 | Payout blocking / release | 4 | payout while dispute OPEN → 422 `OPEN_DISPUTE`, 0 payout items; resolve → 200; payout after resolution → 201 PAID **1700.00** (2000 − 15%) |
| S7 | Post-paid refund (Form A) | 5 | payout PAID first; dispute PARTIAL_REFUND 400 → approve → success; Form A entries at DB level (TEACHER_RECOVERABLE:DEBIT:300 / PLATFORM_REFUND_EXPENSE:DEBIT:100 / PAYMENT_PROVIDER_CLEARING:CREDIT:400); **old PAID payout byte-identical** (v1.4 immutability) |
| S8 | Refund failure | 6 | PARTIAL_REFUND → approve → mock fail → FAILED / payment restored CONFIRMED; ledger tx **VOIDED** (no premature POSTED); terminal FAILED cannot reopen (409); dispute stays RESOLVED (G1: operator may open a new dispute) |
| S9 | Reconciliation | 5 | FULL_REFUND → approve → reconcile SUCCEEDED (MANUAL_RECONCILIATION) → SUCCEEDED / REFUNDED; proof recorded **with actor attribution**; reconcile of terminal refund → 409 |
| S10 | Idempotent replay | 4 | same key+body → 200 original twice; identical refund id; exactly 1 refund row; exactly 1 `DISPUTE_RESOLVED` event |
| S11 | Idempotency conflict | 3 | same key different body → 409 `IDEMPOTENCY_KEY_CONFLICT`; missing key → 400 `IDEMPOTENCY_KEY_REQUIRED` |
| S12 | Concurrent resolution | 3 | two operators, barrier race → exactly one 200 + one 409; exactly one authoritative `DISPUTE_RESOLVED`; dispute RESOLVED |
| S13 | Audit / security | 6 | SM §11.7 fields stored (resolution/resolved_at/resolver); `ADMIN_ACTION` carries the refund reference; admin list read audited (`ADMIN_ACCESS` +1); detail read 200; **`REFUND_ISSUED` = 0 rows globally** |
| S14 | DB-level financial integrity | 11 | every ledger tx balanced; no unauthorized POSTED refund tx (POSTED ⇒ SUCCEEDED); no FAILED refund with a POSTED tx; allocation integrity (teacher+platform=approved); no duplicate provider-event identity; no duplicate refund (payment+key); no duplicate payout item per session; terminal states carry terminal timestamps; refunded payments have SUCCEEDED refunds; no over-refund at rest; no real provider events (mock-only boundary) |
| S15 | Frontend console | 5 | admin console list API (status filter) 200 + dispute present; parent console list 200 + own dispute; teacher console list 200 (participant visibility); **Next.js production server** serves `/admin` (200, SSR HTML contains the Disputes section) and `/parent` (200) |

Total: **75 checks, 75 PASS, 0 FAIL.**

# 2. Financial-integrity gates (S14) — direct SQL over the resulting database

All eleven gates asserted against the live `edutrust_e2e` database after the full scenario run (not per-scenario snapshots): balance, POSTED↔SUCCEEDED correspondence, no premature POSTED, allocation integrity, provider-event identity uniqueness, refund uniqueness (payment+key), payout-item uniqueness per session, terminal-timestamp completeness, refund/payment state consistency, no over-refund at rest, mock-only provider boundary.

# 3. Harness defects found and repaired during this slice (record, with proof)

The suite had never been executed before this slice (it was authored with the WIP). Five harness defects were found — each proven against approved/existing behavior before the harness (never the application) was changed:

1. **S3 sequencing:** the excluded-action loop re-opened a dispute per iteration while the previous one stayed OPEN (the 400 leaves it OPEN). VS4's service invariant is one *active* dispute per interaction, so the second open is a legitimate `DUPLICATE_DISPUTE` 409 — proven in the VS4 suite/plan TR-18. Fix: close between iterations.
2. **S5 token + sequencing:** the "OPS full refund after COMPLETED session → 403" check passed the **ADMIN** token (ADMIN is allowed to do exactly that by P4, so it returns 200); and a second dispute was opened on the same session while the first (after a 403) stayed OPEN (→ legitimate `DUPLICATE_DISPUTE`). Fix: OPS token for the 403 check; the partial-refund dispute moves to a fresh interaction. No application change — the 403/200 behavior matches the plan P4 lock.
3. **S13 syntax:** an invalid walrus expression (`st == 200 and after2 := psql(...) and …`) — a syntax error, provably never-runnable code. Fix: compute the count before the check.
4. **S14 duplicate line:** a stray duplicate of the over-refund query with a typo'd enum (`PROVIDED_PENDING`), immediately overwritten by the corrected line. Fix: removed the duplicate.
5. **Runtime PATH:** the migration subprocess env omitted `PG_BIN` from `PATH` (so `psql` was not found) — the committed VS8 harness includes the identical line; the VS9 harness simply lacked it. Fix: added the VS8 convention line.

None of these repairs masks an application failure: every expected value (403/409/422/201, amounts, ledger forms, events) was asserted against the application as-is and passed.

# 4. Limitations

- No browser automation (repo convention — same as VS1–VS8): S15 verifies the console APIs and the Next.js **production** server's SSR output (the Disputes section markup is present), not click-through interaction.
- Concurrency is a 2-thread barrier race on a single-node runtime (repo convention).
- DEV mock provider only; real provider paths are out of scope by gate.

# 5. Result

```text
VS9_E2E:                75/75 checks PASS — 15/15 scenarios (E2E_DISPUTE_RESOLUTION=PASS)
RUNTIME:                fresh isolated PG 16.2 + migrations + Django dev server + Next.js production server
FINANCIAL_GATES:        11/11 DB-level integrity gates PASS (S14)
AUTHORIZATION:          S2 matrix PASS (403/401) + S5 P4 ADMIN-override PASS
IDEMPOTENCY/CONCURRENCY: S10/S11/S12 PASS (single resolution, single refund, single event)
HISTORICAL_EVIDENCE:    VS8 E2E 53/53 (VS8 report) — re-run this slice: 53/53 PASS on the VS9 tree (VS8 protected)
HARNESS_REPAIRS:        5 (documented in §3; each proven before changing)
```
