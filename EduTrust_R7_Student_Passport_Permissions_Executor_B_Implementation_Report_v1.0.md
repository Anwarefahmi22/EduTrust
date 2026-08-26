# EduTrust — R7 Student Passport + Permissions — Executor B Implementation Report v1.0

**Agent:** ARENA 2 (Executor B)
**Date:** 2026-08-26
**Baseline:** `e706c7707458426496d3c730fe36d9d214d9a034` (Executor A — R7 Student Management), parent `709cfb395d3b4aff0135a904b2a6fbf5a0195dc7` (R6 protected baseline)
**Governing document:** `EduTrust_VS10_R7_Implementation_Authorization_v1.0.md` — SHA256 `12f3d53fd250eabeaf803dc8d8339951cef8ea61d319b08ecd3cf7ff7e84ea04` (verified before and after implementation; unchanged)

---

## 1. Implemented endpoints

| # | Endpoint | Handler | Service | Contract |
|---|---|---|---|---|
| B1 | `GET /api/v1/students/:id/passport` | `views.students_passport` | `services.get_student_passport` | API §7.4 + authorization D3, D9 |
| B2 | `POST /api/v1/students/:id/permissions` | `views.students_permissions` | `services.grant_student_permission` | API §7.5 + authorization D4, D7, §10, D9 |
| B3 | `DELETE /api/v1/students/:id/permissions/:permission_id` | `views.students_permission_item` | `services.revoke_student_permission` | API §7.1 + authorization D5, D9 |

All edits are **strictly additive**: three new service functions (+2 private helpers), three new view handlers appended after Executor A's block, one distinct URL block after Executor A's routes. No existing function, route, or behavior was modified. Executor A's `list_students` / `update_student` / `archive_student` and their routes are untouched.

## 2. Passport aggregation (B1 — D3 exact mapping)

- `completed_sessions` = `COUNT(sessions WHERE status='COMPLETED')` grouped by `sessions.subject_id`.
- `recent_topics` = distinct `TOPIC_COVERED` topic values (latest occurrence per topic via `DISTINCT ON`), latest 10 per subject, recency order (`created_at DESC, id DESC` tie-break).
- `recurring_weaknesses` = topics with ≥ 2 `WEAKNESS_OBSERVED` events per subject.
- `recent_progress_notes` = latest 5 notes from `PROGRESS_NOTE` + `PARTICIPATION_NOTE` events per subject, recency order.
- `subject_name` = `subjects.name_en` with `name_ar` fallback (`COALESCE(NULLIF(name_en,''), name_ar)`).
- Subject universe = subjects referenced by the student's COMPLETED sessions ∪ session_reports ∪ student_progress_events (the three §7.4/D3 sources; deterministic order `subject_name, id`).
- Response = exact §7.4 shape inside the standard `{data, request_id}` envelope. No extra fields. No AI-generated claims — every value is a structured DB aggregation.
- MVCC read: no locks, no events (D9). Ownership per §7.2: parent-scoped lookup, uniform `403 STUDENT_ACCESS_DENIED` for foreign and unknown ids (no existence oracle).

## 3. Permission lifecycle (B2/B3)

**Grant (D4+D7):** Idempotency-Key REQUIRED (400 `IDEMPOTENCY_KEY_REQUIRED`), reusing the established `_idempotency_begin`/`_idempotency_complete` mechanism verbatim with scope `student_permission_grant`; canonical identity `{student_id, teacher_id, scope, granted_for_booking_id, expires_at}` (stringified, nulls as null) hashed per the repo convention. Replay → 200 stored body; same key + different canonical → 409 `IDEMPOTENCY_KEY_CONFLICT`. Validations (all server-side): scope allowlist `{SESSION_CONTEXT}` (400 `VALIDATION_ERROR`); teacher exists (400); uuid-format guards on body ids (400, prevents 500s on malformed input); `expires_at` ISO-8601 and in the future (400; mirrors the DB CHECK `expires_at > starts_at`); booking triple per D7 — missing booking → 400, foreign-parent booking → uniform 403 `STUDENT_ACCESS_DENIED`, booking-student/teacher mismatch → 400. Duplicate ACTIVE permission (same student+teacher+scope+booking under the D5 active predicate, different key) → 409 `DUPLICATE_PERMISSION` (D4 class), no row created. Success → 201 with the created permission object (`{"permission": {...}}`, envelope) and one `STUDENT_PROFILE_UPDATED` event (entity `student`, actor PARENT, metadata `action=PERMISSION_GRANTED`). Timestamps are pre-serialized in the exact API format so an idempotent replay is byte-identical to the original 201.

**Revoke (D5):** No Idempotency-Key (R6 guarded-transition precedent). Lock order per §11: student row → permission row. Unknown / foreign / wrong-student permission → uniform 403 `STUDENT_ACCESS_DENIED` (no oracle). First transition: `UPDATE … SET revoked_at = now()` guarded by `revoked_at IS NULL`; row never deleted; exactly one event (metadata `action=PERMISSION_REVOKED`). Already revoked → 200 no-op returning the unchanged row, no second event. Terminal per row: re-grant inserts a NEW row; the old row is never reactivated.

**Active predicate (D5, shared shape):** `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`.

## 4. Concurrency strategy (no schema change, no unique index)

Authorization §11 lock order implemented: inside the grant/revoke transaction the **owning `student_profiles` row is locked `FOR UPDATE` first** (with the ownership check under the lock); `student_permissions` rows are leaves. Grants additionally run the idempotency insert *after* acquiring the student lock, so:

- **C-1** (same key+body, concurrent): both requests serialize on the student row; the second observes the COMPLETED idempotency row → 200 replay. Exactly one row, one event.
- **C-2** (different keys, same canonical, concurrent): both serialize on the student row; the duplicate-active check of the second runs after the first commits (READ COMMITTED re-snapshot under lock) → 409, loser rolls back. Verified at N=2 and N=4.
- **C-3** (grant vs revoke): serialized on the student row; both orderings (revoke-first → 201 new row; grant-first → 409 duplicate then revoke) leave consistent state; the revoked row stays revoked; at most one active grant.
- **C-3b** (revoke vs revoke): both 200; exactly one transition + one event.

Acyclicity: `student_profiles`/`student_permissions` appear in no existing lock chain (§11 proof; `hold_booking` reads the student row without locking), so student→permission adds no cycle. No migration, no unique index, no new status enum.

## 5. Tests (all evidence from actual runs)

| Suite | File | Result |
|---|---|---|
| Passport + permissions functional | `tests/test_student_completion_passport_permissions.py` (36 tests) | 36/36 PASS |
| Concurrency (real threaded DB races) | `tests/test_student_completion_passport_permissions_concurrency.py` (5 tests: C-1, C-2, C-2b N=4, C-3, C-3b) | 5/5 PASS |
| Executor-B E2E (temp PG + migrations 001–005 + live server + HTTP + direct SQL) | `tests/e2e_student_completion_passport_permissions.py` (S1–S8, 26 checks) | 26/26 PASS |
| **Full regression** (246 pre-B + 41 B-tests) | `pytest tests` | **287/287 PASS** (9m11s) |
| Protected-slice E2E re-verification on B code | Executor A management E2E (24/24), R6 auth E2E (33/33) | PASS |

Coverage map (per the assignment): passport — own access, cross-parent, no-oracle, empty, multiple subjects, completed-session counting (incl. SCHEDULED exclusion), TOPIC_COVERED aggregation, distinct topics, latest-10, weakness ≥2 threshold, PROGRESS_NOTE, PARTICIPATION_NOTE, latest-5, subject naming, Arabic fallback, no event on read, VS3 compatibility; grant — authorized parent, unknown teacher, malformed ids, ownership/no-oracle, valid booking triple, foreign-parent booking, wrong-teacher booking, unknown booking, wrong-student booking, scope validation, required key, canonical replay (200 + identical body), same-key-different-body (409), duplicate-active (409), expired-row re-grant, expires_at validation, no financial side effects, admin role forbidden; revoke — success, terminal, idempotent no-op, no second event, ownership/no-oracle, wrong student, role gate, re-grant-new-row.

## 6. Security / no-oracle behavior

Uniform `403 STUDENT_ACCESS_DENIED` for foreign AND unknown students and permissions (identical status+code — no existence oracle), verified by paired assertions in tests and E2E S4. All ownership from the server-derived JWT user → `parent_profiles`; booking relationships validated server-side (D7); no client-supplied trust. PARENT-only role gate on all three endpoints (admin/teacher → 403 `FORBIDDEN`); no admin mutation path, no teacher consumption endpoint, no security events invented (D9).

## 7. Protected-surface verification

- Migrations 001–005: byte-identical (diff vs e706c77 = ZERO).
- `backend/requirements.txt`, `frontend/package.json`, `frontend/package-lock.json`: unchanged (diff = ZERO); no new dependency.
- Payments/refunds/payouts/ledger/disputes/auth-refresh code paths: untouched (diff = ZERO); E2E S8 asserts refunds/payouts/payout_items = 0 and payments limited to the single VS3-flow fixture payment.
- VS8/VS9/R6/Executor-A behavior: preserved — proven by the 287/287 regression (incl. Executor A's 21 tests) plus Executor A and R6 E2E suites re-run green on the B-modified tree.
- Authorization document SHA256 unchanged: `12f3d53f…e84ea04` (verified post-implementation).
- No D3b/R10/R11/R4/VS11 implementation markers; no teacher-context endpoint; no production UI.

## 8. Environment note (non-repo)

The sandbox lacked PostgreSQL extensions required by migration 001 (`pgcrypto`, `citext`, `btree_gist`). They were built from the official PostgreSQL 16.2 source into the sandbox-local `pgserver` installation (test infrastructure only — nothing in the repository was changed; no dependency files modified).
