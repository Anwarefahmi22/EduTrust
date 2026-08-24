# EduTrust — Vertical Slice #6 Implementation Plan v1.0

**Slice:** DEV Vertical Slice #6 — Review Moderation
**Status:** APPROVED SCOPE — PLANNED, NOT STARTED
**Environment:** DEV only · Real payment FORBIDDEN · Real payout FORBIDDEN · Production NOT APPROVED
**Approved scope basis:** `EduTrust_VS6_Candidate_Scope_Definition_v1.0.md` (Candidate C) + authoritative documents listed in §2
**Classification legend (applied to every non-explicit detail):** `AUTHORITATIVE` = stated in an approved baseline document · `INFERRED` = derivable from approved documents, not explicitly stated · `UNKNOWN` = no approved document covers it — this plan does not invent it · `REQUIRES APPROVAL` = plan-time decision that must be explicitly confirmed before implementation

---

# 1. Pre-planning state verification (read-only, performed this sprint)

```text
Branch:            arena/01a03280-edutrust
HEAD:              f271b9a12dc79f4e11786ca64354e62b5801d98a (VS5)
Lineage:           b245aae (baseline) → 2799018 (VS4) → f271b9a (VS5) — verified
Working tree:      clean except two untracked planning documents (VS5 final audit,
                   VS6 candidate scope definition) — no code changes
VS1–VS5:           COMPLETE / PASS WITH LIMITATIONS each; 83/83 tests; 29/29 VS5 E2E
Migration chain:   v1 → v1.1 → v1.2 (RECONSTRUCTED) → v1.3 → v1.4 — 0-line diff vs baseline
v1.2 provenance:   intact ("RECONSTRUCTED DRAFT — NOT YET APPROVED" header;
                   manifest "RECONSTRUCTED v1.2 ≠ ORIGINAL v1.2")
VS6 code:          none exists (grep for moderation code across backend/frontend/tests:
                   zero implementation hits)
```

---

# 2. Authoritative specifications read (evidence base)

| Document | Sections used |
|---|---|
| `EduTrust_MVP_PRD_v1.0.md` | §10.5 "Review Moderation — P1" (view reviews, flag abusive content, hide policy-violating content, **preserve rating if review is verified and not fraudulent**); "Review text may be moderated"; "Suspicious review behavior can be flagged" |
| `EduTrust_State_Machines_v1.0.md` | §10.1 states (VISIBLE/FLAGGED/HIDDEN/REMOVED); §10.3 allowed transition matrix (authorities, preconditions, invariants, events, idempotency, locking); §10.4 forbidden transitions (**"Delete review physically — Preserve auditability; use status"**) |
| `EduTrust_State_Machines_v1.1_Addendum.md` | §4.1 overlay precedent (factual records preserved); §13 event-ledger discipline (no invented events; ADMIN_ACTION for admin operations) |
| `EduTrust_API_Architecture_v1.0.md` | §18.1 endpoint table (`POST /admin/reviews/:id/moderate` OPS/ADMIN, event `ADMIN_ACTION`; `GET /teachers/:id/reviews` = "List **visible** verified reviews"); §18.4 moderation behavior ("hide abusive comment text, but verified rating should not be silently deleted unless review is fraudulent or policy-violating; **Moderation must be audited**"); §21.4 (`GET /admin/reviews` SUPPORT/OPS/ADMIN list; `POST /admin/reviews/:id/moderate` OPS/ADMIN "Hide/flag/remove content"); §4.2 object ownership; §5 error categories |
| Schema / migrations | `review_status` enum (VISIBLE/FLAGGED/HIDDEN/REMOVED), `reviews.status` column (default VISIBLE); `reviews.session_id UNIQUE`; `is_verified CHECK (is_verified = TRUE)`; `event_ledger` (append-only, `metadata JSONB`); `api_idempotency_keys` (v1.1) |
| `EduTrust_UX_Flows_v1.0.md` | Review flow: "Review visible on teacher profile **after moderation rules**"; creation preconditions (VS4) |
| `EduTrust_Product_Ops_Policy_Decisions_v1.0.md` | OPS-POL-008 (review eligibility after partial refund — tangential; concerns *eligibility*, not moderation; current strict default is policy-safe) |
| `EduTrust_Feature_Flag_Governance_v1.0.md` | §5 forbidden flags list includes **`ALLOW_UNVERIFIED_REVIEWS`** — no flag may weaken the verified-review model |
| VS4 implementation/audit documents | Verified-review model (server-derived verification, eligibility, public VISIBLE+verified filter, ownership boundaries, audit pattern) — preserved, not weakened |

---

# 3. Scope definition

## 3.1 In scope (exact)

| # | Item | Basis | Class |
|---|---|---|---|
| S1 | `GET /api/v1/admin/reviews` — operational review list (all statuses) for SUPPORT/OPS/ADMIN; audited | API §21.4 | AUTHORITATIVE |
| S2 | `POST /api/v1/admin/reviews/:id/moderate` — OPS/ADMIN moderation command | API §18.1/§21.4 | AUTHORITATIVE |
| S3 | Actions: **FLAG** (VISIBLE→FLAGGED), **HIDE** (FLAGGED→HIDDEN), **RESTORE** (FLAGGED\|HIDDEN→VISIBLE), **REMOVE** (any of VISIBLE/FLAGGED/HIDDEN → REMOVED) | SM §10.3 matrix | AUTHORITATIVE |
| S4 | **REMOVE is ADMIN-only** (OPS may flag/hide/restore but not remove) | SM §10.3 ("Admin only") | AUTHORITATIVE |
| S5 | **No physical deletion** — the review row is always preserved; moderation is status-based; auditability preserved | SM §10.4 forbidden list | AUTHORITATIVE |
| S6 | **Public visibility interaction**: VS4 public list filter (`status = 'VISIBLE' AND is_verified`) unchanged → FLAGGED/HIDDEN/REMOVED are excluded from `GET /teachers/:id/reviews` immediately and automatically (no public-list code change required) | API §18.1 + VS4 implementation | AUTHORITATIVE |
| S7 | **Verified-review invariants preserved**: moderation never touches `is_verified` (DB CHECK keeps it TRUE), `session_id`, `rating`, comment data, eligibility, or ownership; `ALLOW_UNVERIFIED_REVIEWS` is a forbidden flag and no flag is introduced | SM §10.3 invariants + Feature Flag §5 + VS4 model | AUTHORITATIVE |
| S8 | **Audit**: every moderation writes `ADMIN_ACTION` (entity `review`, metadata: action, reason, from_status, to_status); the list read writes `ADMIN_ACTION` (entity `reviews`) + `ADMIN_ACCESS` security event (severity 2) — established VS2–VS5 admin-audit pattern | SM §10.3 event column + API §18.4 "must be audited" + established pattern | AUTHORITATIVE |
| S9 | **Preconditions**: FLAG on abuse/fraud signal (operator-supplied); HIDE on policy violation in text/content; RESTORE when review cleared; REMOVE on fraud/legal/safety policy | SM §10.3 preconditions + PRD §10.5 | AUTHORITATIVE |
| S10 | **Locking**: "Lock review" (SM §10.3) — `SELECT ... FOR UPDATE` on the review row inside the transaction; concurrent modulations serialize | SM §10.3 | AUTHORITATIVE |
| S11 | **Idempotency**: via the existing `api_idempotency_keys` mechanism (replay returns stored response; conflicting payload → 409) | SM §10.3 idempotency column (REMOVE "Required"; others "Recommended") + established v1.1/v1.3 infrastructure | AUTHORITATIVE (mechanism) + REQUIRES APPROVAL U2 (uniform mandatory key) |
| S12 | **Rating preservation**: moderation changes status only; the rating value is never deleted or altered (row preserved; public exposure governed by the status filter) — "verified rating should not be silently deleted" | API §18.4 + PRD §10.5 | AUTHORITATIVE |
| S13 | **Frontend DEV console**: admin "Review Moderation" section (operational list incl. non-visible statuses + moderate action with reason + outcome line) | PRD §10.5 (admin "can") + established DEV-console posture | AUTHORITATIVE (requirement) / INFERRED (console shape, per VS1–VS5 pattern) |

## 3.2 Explicit scope exclusions (do not implement)

| # | Exclusion | Basis | Class |
|---|---|---|---|
| X1 | **Automatic / System review flagging** (abuse/fraud detection engine) — the SM §10.3 matrix lists "System" as an authority for VISIBLE→FLAGGED, but **no approved detection specification exists anywhere in the repository**; only the manual OPS/Admin path is implemented; the "System" authority remains defined-but-unused | User instruction + absence of any approved detection spec | AUTHORITATIVE (exclusion basis) / UNKNOWN (detection — never invented) |
| X2 | Notifications on moderation (matrix: "Optional"; Notifications workstream not implemented) | SM §10.3 | AUTHORITATIVE |
| X3 | Trust-metrics recalculation (worker unimplemented; DB protection trigger in place; matrix: "updated later by metrics worker") | SM §10.3 side-effects column | AUTHORITATIVE |
| X4 | Any review-eligibility change (OPS-POL-008 remains OPEN; VS4 strict `CONFIRMED`-only default stands) | Product-Ops docs | AUTHORITATIVE |
| X5 | Refund operations, dispute resolution, payout changes, any financial state transition | Candidate scope definition | AUTHORITATIVE |
| X6 | Physical deletion of review rows (forbidden) | SM §10.4 | AUTHORITATIVE |
| X7 | Full production UI (DEV console only) | Established DEV posture | AUTHORITATIVE |
| X8 | Any schema, migration, state-machine, architecture, or API-redesign change | Governance envelope | AUTHORITATIVE |
| X9 | VS7 or any other slice | Governance envelope | AUTHORITATIVE |

---

# 4. Endpoint design (exact)

### E1 — `GET /api/v1/admin/reviews`
- **Roles:** SUPPORT, OPS, ADMIN (API §21.4). Anonymous → 401; PARENT/TEACHER → 403. `AUTHORITATIVE`.
- **Response:** standard envelope; list (LIMIT 100, newest first) of: `id`, `session_id`, `booking_id`, `teacher_id`, `teacher_public_name`, `student_display_name`, `rating`, `comment`, `status`, `is_verified`, `created_at`. Field set INFERRED from the established admin-list patterns (VS2–VS5) and the moderation console's needs (S13) — includes non-VISIBLE statuses (that is the operational point of this endpoint).
- **Audit:** `ADMIN_ACTION` (entity `reviews`, action `READ_REVIEW_LIST`) + `ADMIN_ACCESS` security event (severity 2) on every read — established pattern. `AUTHORITATIVE` (pattern) / INFERRED (metadata names).

### E2 — `POST /api/v1/admin/reviews/:id/moderate`
- **Roles:** OPS, ADMIN (API §18.1/§21.4). Anonymous → 401; other roles → 403; **OPS attempting REMOVE → 403** (matrix "Admin only"). `AUTHORITATIVE`.
- **Request body:** see §5 (U1 — REQUIRES APPROVAL).
- **Response:** standard envelope with the updated review (same field set as E1 row). INFERRED from convention.
- **Transaction:** single atomic tx — idempotency begin → `SELECT review FOR UPDATE` → role/transition validation → `UPDATE reviews SET status=... WHERE id=...` (status column only) → `ADMIN_ACTION` event → idempotency complete. No other row is written. `AUTHORITATIVE` (lock + event) / INFERRED (exact step order per established service pattern).

## 5. Moderation request contract — specification status and minimum decision

**Verification (required check): the request body is NOT fully specified by the approved documents.** API §18.1/§18.4/§21.4 name the endpoint, roles, purpose ("Hide/flag/remove content"), and event, but itemize no request fields. SM §10.3 defines the four transitions and preconditions but not a wire format.

**Minimum plan-time decision (U1 — REQUIRES APPROVAL, nothing more):**

```json
{
  "action": "FLAG | HIDE | RESTORE | REMOVE",
  "reason": "<non-empty operator-supplied text>"
}
```

- `action` enum values derive 1:1 from the approved transitions (FLAG=VISIBLE→FLAGGED, HIDE=FLAGGED→HIDDEN, RESTORE=FLAGGED|HIDDEN→VISIBLE, REMOVE=any→REMOVED) — `INFERRED` from SM §10.3 + PRD §10.5; the values themselves require the single confirmation in U1.
- `reason` (non-empty text) is required by "Moderation must be audited" (§18.4) and the §10.3 preconditions (policy/fraud/safety justification); stored **only** in the `ADMIN_ACTION` event metadata (no schema column exists on `reviews`, none is needed — `event_ledger.metadata JSONB` is the approved audit store). `INFERRED`.
- **No other fields** are added (no notify flag, no severity, no policy code). Anything further is out of the approved envelope. `UNKNOWN` territory is not touched.

## 6. Transition, error, and concurrency semantics

### 6.1 Allowed transitions (exact, per SM §10.3) — AUTHORITATIVE

| Action | From | To | Authority |
|---|---|---|---|
| FLAG | VISIBLE | FLAGGED | OPS, ADMIN |
| HIDE | FLAGGED | HIDDEN | OPS, ADMIN |
| RESTORE | FLAGGED, HIDDEN | VISIBLE | OPS, ADMIN |
| REMOVE | VISIBLE, FLAGGED, HIDDEN | REMOVED | **ADMIN only** |

### 6.2 Invalid transitions and error semantics

Established error model (VS1–VS5 codes): `AUTHORITATIVE` (code set) / INFERRED (mapping details, locked by U3 where ambiguous).

| Case | Status / code | Basis |
|---|---|---|
| Unknown review id | 404 `RESOURCE_NOT_FOUND` | convention |
| Unknown `action` value | 400 `VALIDATION_ERROR` | convention |
| Missing/empty `reason` | 400 `VALIDATION_ERROR` | §18.4 audit requirement (INFERRED) |
| Invalid transition (e.g., HIDE from VISIBLE; RESTORE from VISIBLE or REMOVED; REMOVE of REMOVED; HIDE of REMOVED) | 422 `INVALID_STATE_TRANSITION` with `details.current_status` | established 422 state-violation code (VS1–VS5) — INFERRED mapping, part of U3 |
| RESTORE of an already-VISIBLE review (target-state repeat) | **U3 decision** — recommended: 422 `INVALID_STATE_TRANSITION` (strict matrix reading: RESTORE is defined only from FLAGGED/HIDDEN); alternative: 200 idempotent no-op (VS3 session start/complete precedent) | REQUIRES APPROVAL (U3) |
| OPS action = REMOVE | 403 `FORBIDDEN` | matrix "Admin only" — AUTHORITATIVE |
| Non-OPS/ADMIN role | 403 `FORBIDDEN`; anonymous 401 `AUTH_REQUIRED` | `require_roles` convention |
| Idempotency key missing (if U2 confirmed) | 400 `IDEMPOTENCY_KEY_REQUIRED` | established helper |
| Same key, different payload | 409 `IDEMPOTENCY_KEY_CONFLICT` | established helper |
| In-flight same-key | 409 processing guard | established helper |

### 6.3 Concurrency

- The review row is locked `FOR UPDATE` inside the single moderation transaction (SM §10.3 "Lock review") — concurrent modulations on the same review **serialize**; each re-reads status after acquiring the lock, so exactly one of N conflicting transitions succeeds and the rest get 422 (or 409 on idempotency conflict for same-key).
- No schema backstop is needed (transitions are service-guarded under the row lock; the status column admits only the 4 enum values).
- Expected test outcome (locked by U3): two parallel modulations, different keys, conflicting actions → one success + one 422; final status consistent; exactly one review row.

## 7. Authorization matrix (exact)

| Endpoint | Anonymous | PARENT | TEACHER (incl. review owner/teacher) | SUPPORT | OPS | ADMIN |
|---|---|---|---|---|---|---|
| GET /admin/reviews | 401 | 403 | 403 | **200 (audited)** | **200 (audited)** | **200 (audited)** |
| POST /admin/reviews/:id/moderate (FLAG/HIDE/RESTORE) | 401 | 403 | 403 | 403 | **200/404/422** | **200/404/422** |
| POST /admin/reviews/:id/moderate (REMOVE) | 401 | 403 | 403 | 403 | **403** | **200/404/422** |

Notes: the review's parent and the reviewed teacher have **no** moderation rights (matrix authorities are System/OPS/Admin and OPS/Admin only — `AUTHORITATIVE`); a teacher/parent reading a review uses the unchanged VS4 endpoints. SUPPORT list access is per API §21.4 (SUPPORT users, like ADMIN/OPS, are seeded outside public registration — established test convention).

## 8. Verified-review model preservation (required check)

VS4 invariants are **preserved, not weakened** — `AUTHORITATIVE` throughout:
- `is_verified` stays server-derived; DB `CHECK (is_verified = TRUE)` untouched; moderation UPDATE touches `status` only.
- Creation eligibility (completed session + completed booking + confirmed payment + ownership + no teacher self-review) untouched.
- Ownership/privacy boundaries untouched (VS4 scoped reads unchanged).
- Public visibility filtering unchanged (VS4 `VISIBLE + is_verified` filter; moderation simply changes which rows qualify).
- Audit/security controls preserved (admin reads/moderations audited; no secrets logged).
- No flag introduced; `ALLOW_UNVERIFIED_REVIEWS` remains on the forbidden list (Feature Flag §5).

## 9. Ledger / financial notes

No ledger interaction. No financial state transitions. No money movement. `AUTHORITATIVE` (moderation is a content/visibility operation per all cited sections).

## 10. Frontend DEV console (exact)

Admin page new section "Review Moderation" (existing console pattern, existing tokens; no new npm dependency):
- `Load reviews` (operational list: teacher, student, rating, comment, status badge incl. FLAGGED/HIDDEN/REMOVED, verified flag)
- Per-row action control: action select (FLAG/HIDE/RESTORE/REMOVE) + reason text input + `Moderate` button
- Automatic `Idempotency-Key: moderate-<randomUUID>` (if U2 confirmed)
- Outcome line (201/200 new status / 403 / 404 / 409 / 422 with current_status)
- Activity log entries; visible note: "Moderation is audited. Reviews are never physically deleted."
- Teacher/parent pages: **unchanged** (public list already reflects moderation state).

## 11. Test plan (exact, before implementation)

New file `tests/test_vertical_slice_6.py`; all 83 existing tests unchanged. Minimum tests:

| # | Test | Asserts |
|---|---|---|
| 1 | `test_moderate_flag_visible_to_flagged` | 200/201; status FLAGGED; `ADMIN_ACTION` event with action/reason/from/to metadata; rating/comment/is_verified unchanged |
| 2 | `test_moderate_hide_flagged_to_hidden` | FLAGGED→HIDDEN 200; event recorded |
| 3 | `test_moderate_restore_flagged_to_visible` | FLAGGED→VISIBLE 200 |
| 4 | `test_moderate_restore_hidden_to_visible` | HIDDEN→VISIBLE 200 |
| 5 | `test_moderate_remove_admin_only_success` | ADMIN: VISIBLE→REMOVED 200; **row still exists in DB** (no physical delete); rating preserved |
| 6 | `test_moderate_remove_from_flagged_and_hidden` | both → REMOVED allowed |
| 7 | `test_ops_cannot_remove` | OPS REMOVE → 403 |
| 8 | `test_moderation_denied_for_parent_teacher_anonymous` | parent owner 403; teacher 403; anonymous 401; PARENT-role on list 403 |
| 9 | `test_invalid_transitions_rejected` | HIDE from VISIBLE → 422 (`current_status` detail); RESTORE from VISIBLE → 422 (per U3); RESTORE from REMOVED → 422; REMOVE of REMOVED → 422; HIDE of REMOVED → 422 |
| 10 | `test_validation_errors` | unknown action → 400; empty reason → 400; unknown review id → 404 |
| 11 | `test_public_visibility_reflects_moderation` | VISIBLE appears in `GET /teachers/:id/reviews`; after FLAG/HIDE/REMOVE the public list excludes it; after RESTORE it reappears; no public-list code change needed |
| 12 | `test_verified_review_invariants_preserved` | after any moderation: `is_verified=True`, `session_id` unchanged, `rating`/`comment` intact, `session_id UNIQUE` intact (second creation for same session still 409 `DUPLICATE_REVIEW`), eligibility rules unchanged |
| 13 | `test_admin_list_audited_and_support_access` | SUPPORT list 200 + `ADMIN_ACTION`/`ADMIN_ACCESS` events; OPS/ADMIN list 200 audited; list shows non-VISIBLE statuses |
| 14 | `test_moderation_idempotency_replay_and_conflict` | same key+payload → same result, status applied once; same key different payload → 409 `IDEMPOTENCY_KEY_CONFLICT`; missing key → 400 (if U2 confirmed) |
| 15 | `test_concurrent_moderation_serialized` | two parallel modulations (different keys, conflicting actions, e.g. FLAG + REMOVE) → one success + one 422/409; exactly one review row; final status consistent with the winner |
| 16 | `test_regression_full_suite` | all 83 pre-existing tests green in the same run |

Target: **≥ 15 new tests; total ≥ 98 passing** (final count may exceed; all listed behaviors must be covered).

## 12. Runtime E2E plan (exact)

Isolated temporary PostgreSQL (UTF8) + full unmodified v1→v1.4 chain + Django + Next.js, same harness pattern as VS4/VS5:

```text
E2E_MAIN:
  full VS1 cycle → verified review created (VS4 flow)
  admin GET /admin/reviews → review listed (VISIBLE)
  moderate FLAG (reason) → 200; public teacher list no longer shows the review
  moderate HIDE → 200; public list still excludes it
  moderate RESTORE → 200; public list shows it again
E2E_REMOVE:
  second review (second full cycle) → ADMIN REMOVE → 200;
  public list excludes it permanently; DB row still present (psql check)
E2E_UNAUTHORIZED:
  parent/teacher moderate → 403; anonymous → 401; OPS REMOVE → 403;
  parent GET /admin/reviews → 403; anonymous → 401
E2E_INVALID:
  HIDE from VISIBLE → 422 with current_status; REMOVE of REMOVED → 422
E2E_CONCURRENCY:
  two parallel modulations, different keys, same review → one 200 + one 422/409; one row
E2E_IDEMPOTENCY:
  same key+payload repeat → same outcome, single status change
E2E_AUDIT:
  /admin/events contains ADMIN_ACTION entries with action+reason metadata;
  /admin/security-events count grew (ADMIN_ACCESS)
E2E_FRONTEND:
  /admin → 200, moderation console present; actions functional through the API
Expected: all eight scenario groups PASS
```

## 13. Dependency audit

- No new npm or pip dependencies (service/views/urls/console only; existing `lib/api.ts` client).
- Re-run `npm audit` + `pip check` after implementation; expected result: identical to pre-VS6 (2 high: next 14.2.35 / postcss 8.4.31 — DEV-accepted, STAGING/PROD blocked). **Do not run `npm audit fix --force`.**
- Deliver `EduTrust_DEV_Dependency_Audit_v1.5.md`.

## 14. Rollback / safety considerations

- **Additive-only change set**: new routes, new views, new service functions, new test file, admin-page section, reports. No existing function, route, schema object, or test is modified.
- **No schema/migration/state-machine changes** → rollback = revert the single VS6 commit; no data migration to reverse.
- **Data safety**: moderation is a status UPDATE on an existing row (never a delete); RESTORE reverses FLAG/HIDE; REMOVE is a status change with the row and rating preserved and the operation fully audited in `event_ledger` (append-only). No irrecoverable data path exists.
- **No financial, provider, or provider-credential surface** — nothing in this slice touches money, payments, or external systems.
- Idempotency rows for moderation live in the existing `api_idempotency_keys` table (24h expiry per existing design) — no new state store.
- Dev server reloads are file-additive; no config/env changes required.

## 15. Plan-time decisions requiring explicit approval (minimum set)

| ID | Decision | Options | Recommendation | Class |
|---|---|---|---|---|
| U1 | Moderation request contract = `{action: FLAG\|HIDE\|RESTORE\|REMOVE, reason: non-empty string}`, response = updated review in standard envelope; no other fields | confirm as stated, or amend | confirm as stated (minimum derivable from SM §10.3/§18.4) | REQUIRES APPROVAL (INFERRED basis) |
| U2 | Idempotency-Key mandatory on **all four** moderation actions (matrix: REMOVE "Required", others "Recommended"; uniform enforcement matches VS2–VS5 POST conventions) | mandatory-all (recommended) vs required-only-REMOVE | mandatory-all | REQUIRES APPROVAL |
| U3 | Invalid-transition error semantics: 422 `INVALID_STATE_TRANSITION` (+`current_status` detail) for all invalid transitions, including RESTORE-of-already-VISIBLE (strict matrix reading) | strict 422 (recommended) vs 200 idempotent no-op for target-state repeats (VS3 precedent) | strict 422 | REQUIRES APPROVAL |

Everything else in this plan is AUTHORITATIVE or INFERRED-with-cited-basis. **No UNKNOWN item has been silently resolved.**

## 16. Schema change assessment (required check)

**SCHEMA_CHANGE_REQUIRED: NO**

Reasons:
1. `review_status` enum already contains all four moderation states; `reviews.status` column (default VISIBLE) is the status carrier — the entire state machine runs on existing objects.
2. The moderation reason needs no new column: the approved audit path is `event_ledger.metadata` (JSONB), which already stores operator context for `ADMIN_ACTION` events (VS2–VS5 pattern).
3. Concurrency needs no new constraint: the "Lock review" (SM §10.3) is a row lock, and the enum admits only the four states.
4. Idempotency reuses `api_idempotency_keys` (v1.1) — no new table.
5. Public visibility needs no change: the VS4 public query already filters `status = 'VISIBLE' AND is_verified`.
6. Immutability of verification is already DB-enforced (`CHECK (is_verified = TRUE)`) and untouched.

Contingency (governance envelope): if implementation discovers a genuine blocker requiring schema change, STOP and report `SCHEMA_CHANGE_REQUIRED: YES` with reason/column/minimal change/state-machine impact/migration proposal before applying anything. Not anticipated.

## 17. Definition of Done (VS6)

```text
- FLAG/HIDE/RESTORE/REMOVE implemented exactly per SM §10.3 (manual OPS/Admin path; System flagging out of scope)
- REMOVE enforced ADMIN-only (OPS 403)
- No physical deletion anywhere; review row + rating always preserved
- Public visibility reflects moderation state automatically (VS4 filter unchanged)
- Verified-review model fully preserved (is_verified/eligibility/ownership/public filter/audit; no new flags)
- Every moderation audited: ADMIN_ACTION with action+reason+from/to; list reads audited with ADMIN_ACCESS
- Invalid transitions → 422 with current_status (per U3); validation → 400; roles → 401/403; unknown id → 404
- Idempotency: replay safe, conflict 409, missing key 400 (per U2); in-flight processing guard
- Concurrency: row-locked serialization; conflicting parallel modulations → one winner
- Frontend DEV moderation console functional; teacher/parent pages unchanged
- ≥ 15 new tests + all 83 pre-existing tests green (total ≥ 98)
- E2E: all 8 scenario groups PASS on isolated runtime with unmodified migration chain
- Dependency audit re-run without --force; no new dependencies
- Reports: Implementation / Test / E2E / Dependency Audit v1.5 + README update
- No schema, state-machine, architecture, or API-redesign changes; v1.2 provenance intact
- VS7 NOT started
```

## 18. Deliverables (post-implementation)

```text
EduTrust_DEV_Vertical_Slice_6_Implementation_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_6_Test_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_6_E2E_Report_v1.0.md
EduTrust_DEV_Dependency_Audit_v1.5.md
README.md (VS6 section + test count)
```

---

# 19. Formal gate

```text
VS6_SCOPE_APPROVED: YES
VS6_IMPLEMENTATION_STARTED: NO
DATABASE_MODIFIED: NO
ARCHITECTURE_MODIFIED: NO
API_MODIFIED: NO
STATE_MACHINE_MODIFIED: NO
COMMIT_CREATED: NO
```

**Implementation is explicitly NOT started.** The three plan-time decisions (U1, U2, U3) are recorded above and require explicit confirmation; until the implementation sprint is authorized, no code, test, migration, or commit will be created.
