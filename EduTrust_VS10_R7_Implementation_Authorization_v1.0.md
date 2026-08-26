# EduTrust — R7 (Student Passport / Student Completion) Implementation Authorization v1.0

**Document type:** READ-ONLY discovery, governance lock & implementation authorization. **No R7 code, tests, migrations, frontend, dependencies, commits, or pushes were performed.**
**Protected baseline (verified at document creation):** `arena/01a03280-edutrust` @ `709cfb395d3b4aff0135a904b2a6fbf5a0195dc7` (R6), parent `af8f818` (VS9); remote arena = `709cfb3`; `main` = `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb`; working tree clean.
**Classification legend:** `APPROVED` · `CONVENTION` (established in-repo, cited) · `CONTRACT GAP` (spec silent) · `INFERRED LOCK` (plan-time lock on a contract gap — flagged, not invention of approved behavior) · `UNKNOWN` (preserved)

---

# 1. Executive Summary

R7 = **Student Passport + Student completion**, the SECOND-ranked next-slice candidate in the committed VS10 discovery plan (`EduTrust_VS10_Discovery_Governance_And_Implementation_Plan_v1.0.md`, §U/§AC). Full discovery was performed against the primary sources (API Architecture §7/§4, PRD §8.2/§12, wireframes P-05/P-06/P-07, HF design, UX flows, traceability matrix, schema v1, migrations v1→v1.4, existing code).

**Verdict: `R7_SCOPE_READY = YES`** — with **9 plan-time locks (D1–D9)** and **0 blocking governance decisions, 0 schema changes, 0 financial surface, 0 new dependencies**. The approved contract surface is six PARENT endpoints: `GET /students` (list), `PATCH /students/:id`, `DELETE /students/:id`, `GET /students/:id/passport`, `POST /students/:id/permissions`, `DELETE /students/:id/permissions/:permission_id` (`POST /students` and `GET /students/:id` already exist from VS1 — unchanged by R7). The passport v0 response shape is fully specified (API §7.4); the passport data sources already exist and are already written by VS3 (structured session reports + `student_progress_events`); the `student_permissions` table exists and is unused; the ownership rule (§7.2, 403 `STUDENT_ACCESS_DENIED`, no existence oracle) is already the implemented VS1 pattern.

Two honest findings require the approver's attention (neither blocks scope-readiness):

1. **Teacher-side student-context consumption has NO approved API endpoint.** PRD §12.3 ("Teacher access requires parent permission and only for relevant student/session context") and the traceability matrix ("Teacher Passport restriction — StudentContextService") express the product intent, and wireframe P-07 describes the parent-side grant UI — but the approved API (§7) defines **no teacher-facing student endpoint**. R7 therefore implements the **parent side only** (grant/revoke + parent passport); the teacher-side read endpoint is a recorded **CONTRACT GAP**, not invented, and is OUT OF SCOPE for R7 (a later approved endpoint spec is required).
2. **The VS10 plan's frontend statement is corrected:** the plan asserted "no wireframe specifies a passport screen". That is **inaccurate** — wireframes **P-06 (Student Passport v0)** and **P-07 (Student Data Sharing Permissions)** ARE specified (LF + HF, both APPROVED). They belong to the **64-screen production UI set (R17 phase)**; R7's DEV-slice frontend scope remains **API-only, with an optional parent-console DEV view** (production P-06/P-07 screens stay deferred to R17 — no production UI in R7).

**No UNKNOWN was converted to YES.** Every contract gap is listed in §17 (UNKNOWN/BLOCKING) or locked as an explicit `INFERRED LOCK` in §19 with its source and rationale.

# 2. Current Protected Baseline (verified read-only at creation)

| Check | Value |
|---|---|
| Branch | `arena/01a03280-edutrust` |
| Local HEAD | `709cfb395d3b4aff0135a904b2a6fbf5a0195dc7` (R6 Auth Completion) |
| HEAD parent | `af8f8185911af871fb1832e02fe9e5588bf228c0` (VS9) |
| Remote arena | `709cfb395d3b4aff0135a904b2a6fbf5a0195dc7` — **matches local (R6 protected)** |
| Remote main | `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` — untouched |
| Working tree | CLEAN (0 modified, 0 untracked at verification) |
| Ancestry | `709cfb3` (R6) → `af8f818` (VS9) → `b73d8ce` (VS8) → `157a54d` (VS7) → `e0e3d89` (VS6) → `83c7bc5` (restore VS4+VS5) → `b245aae` (migrate) → `45dc020` (root) |

VS8 (`b73d8ce`), VS9 (`af8f818`), and R6 (`709cfb3`) are all PROTECTED: none is modified by this document or by any R7 action authorized here.

# 3. Authority Hierarchy (R7-relevant sources)

Precedence per Implementation Baseline v1.0 + SM v1.1 Addendum §2 (Addendum > Schema v1.1 > SM v1.0 > API Arch > DB Schema v1.0 > PRD); UX documents are APPROVED for UI behavior but do not create API/ledger obligations; roadmap precedence: VS10 discovery plan (committed, current) > Post-VS8 audit (roadmap) > Post-VS6 (HISTORICAL proposal).

| SOURCE | VERSION | SECTION | STATUS | AUTHORITY LEVEL | R7 RELEVANCE |
|---|---|---|---|---|---|
| API Architecture | v1.0 | §7.1–7.5 (Student APIs), §4.2–4.3 (ownership + sensitive data), §4 error catalog (403 `STUDENT_ACCESS_DENIED`), §27.1 (rate-limit scope) | APPROVED | **Primary contract** | Endpoint set, roles, events, ownership rule, no-oracle rule, passport response shape, permission rules |
| PRD | v1.0 | §8.2 (Student Profile P0), §12 (Student Passport v0: principle, fields, behavior, future-AI exclusion) | APPROVED | Product spec | MVP fields, minimized-data principle, "structured data, not AI", parent-viewable, permission-gated teacher context |
| State Machines v1.0 + Addendum v1.1 | v1.0/v1.1 | — (no student state machine section) | APPROVED | — | **No student status state machine is spec'd** — `student_status` transitions are a CONTRACT GAP (see §7) |
| Schema v1 (migration 001) | v1 | `student_profiles`, `student_permissions`, `student_progress_events`, `session_reports`, `subjects`, `academic_levels`, enums `student_status`/`consent_status`/`progress_event_type` | APPROVED | Implementation of record | All R7 tables exist; FK delete rules define archive-vs-delete reality |
| Wireframes (LF) + HF UI Design | v1.0 | P-05 (Student Profile), P-06 (Student Passport v0), P-07 (Data Sharing Permissions) | APPROVED | UI behavior spec (R17 production set) | Screen specs: states, CTAs, empty/error/denied states, "no AI-derived claims", endpoints referenced |
| UX Flows | v1.0 | passport-in-main-flow; report flow ("Report contributes to Student Passport v0") | APPROVED | UX flow | Passport updated from session reports (already implemented by VS3 progress-event writes) |
| Test Traceability Matrix | v1.0 | rows 42 (Student ownership privacy — Security Gate), 43 (Teacher Passport restriction — Security Gate), 64/89 (planned test file names) | APPROVED | Test obligation | Ownership + permission-check test obligations; planned names `test_student_permissions.py` / `e2e_student_permissions.spec.ts` (planning-era names — the established executed convention is standalone Python E2E; names are informational) |
| Feature Flag Governance | v1.0 | `TEACHER_PUBLIC_LISTING_ENABLED` fallback note | READY FOR REVIEW | Policy (OPEN) | Not R7-relevant (teacher listing, not student context) |
| Product/Ops Policy Decisions | v1.0 | — (no student/permission policy among the 10) | READY FOR REVIEW | Policy (OPEN) | **No OPS policy governs R7** — no policy dependency |
| VS10 Discovery & Governance & Implementation Plan | v1.0 (committed in `709cfb3`) | §I, §K–§U, §AC | CURRENT roadmap | Sequencing source | R7 = SECOND candidate; scope-ready verdict; one statement corrected (§1 finding 2) |
| VS1 implementation (code + report) | — | `create_student`/`get_student` | EVIDENCE (implemented) | Convention source | Ownership pattern (403 `STUDENT_ACCESS_DENIED`), event `STUDENT_PROFILE_CREATED`, no-idempotency for student create (pre-convention) |
| R6 (VS10) implementation (code + authorization doc) | v1.0 (committed in `709cfb3`) | guarded-transition revoke events; uniform 401; no-oracle | EVIDENCE (implemented) | Convention source | "Only actually-transitioned rows emit events"; uniform-error convention |

**Conflicts recorded (none silently resolved):**
- C1: VS10 plan ("no wireframe specifies a passport screen") vs wireframes P-06/P-07 (specified). **Governing source: the wireframes** (APPROVED primary UI spec; the plan's sentence is an inference error). Resolution recorded in §13: production screens = R17 phase; R7 = API + optional DEV console view.
- C2: API §7.5 permission rules (grant/revoke exist) vs no permission-read endpoint anywhere in §7 while wireframe P-07 shows an access list. **Governing source: the API** (no endpoint → no endpoint). Resolution: read-list is a CONTRACT GAP, OUT OF SCOPE (recorded §17, not invented).
- C3: API §7.3 "academic_level_id must exist and be active" vs VS1 `create_student` (enforces existence via FK only; `is_active` unchecked) — pre-existing VS1 gap. **Not an R7 conflict** (R7 does not touch create); recorded as a pre-existing finding (F-1, §17) — R7 does not fix it (out of scope; fix is a separate decision).

# 4. R7 Contract (complete extraction — nothing invented)

APPROVED surface (API §7.1, all PARENT; events per the §7.1 Event column):

| # | METHOD | PATH | ACTOR | INPUT (approved) | OUTPUT (approved) | SUCCESS | ERROR (approved/precedent) | IDEMPOTENCY (approved?) | AUTHORIZATION | AUDIT EVENT | SECURITY EVENT | STATE TRANSITION | DB EFFECT | FINANCIAL EFFECT | CONCURRENCY (spec?) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 | GET | `/students` | PARENT | none | own-students list (shape: standard envelope — **GAP**: item shape unspecified) | 200 | 401 (anon) | n/a (read) | §7.2 ownership (self-listing) | None (§7.1) | none | none | read `student_profiles` | NONE | n/a |
| E2 | PATCH | `/students/:id` | PARENT | updatable profile fields (**GAP**: field set unspecified — lock D1) | updated student (shape: envelope — convention) | 200 | 403 `STUDENT_ACCESS_DENIED` (§7.2), 400 validation (precedent), 401 | not spec'd (P-05 UX: "recommended for update" — advisory; lock D1b) | §7.2 ownership | `STUDENT_PROFILE_UPDATED` (§7.1) | none | field update (status NOT client-settable — lock D1c) | update `student_profiles` row | NONE | last-writer-wins under row lock (lock D1d — INFERRED) |
| E3 | DELETE | `/students/:id` | PARENT | none | archive confirmation (shape: envelope — convention) | 200 | 403 `STUDENT_ACCESS_DENIED` (uniform, §7.2) | idempotent by semantics (lock D2) | §7.2 ownership | `STUDENT_PROFILE_UPDATED` (§7.1) | none | active → archived (lock D2; `DELETED` semantics UNKNOWN) | soft archive (row retained; bookings RESTRICT-FK makes hard delete impossible with history) | NONE | student-row lock (lock D2) |
| E4 | GET | `/students/:id/passport` | PARENT | none | **fully specified** (§7.4): `{student_id, subjects[]:{subject_id, subject_name, completed_sessions, recent_topics[], recurring_weaknesses[], recent_progress_notes[]}}` | 200 | 403 `STUDENT_ACCESS_DENIED` (uniform, §7.2), 401 | n/a (read) | §7.2 ownership | **None** for parent read (§7.1; P-06 "None for parent read") | none ("sensitive teacher/admin access may audit" — no teacher/admin read endpoint exists in R7) | none | read `sessions`, `session_reports`, `student_progress_events` (+`subjects` names) | NONE | MVCC read, no locks |
| E5 | POST | `/students/:id/permissions` | PARENT | `{teacher_id, scope, granted_for_booking_id, expires_at}` (§7.5) | created permission (shape: envelope — **GAP**: unspecified; lock D4) | 201 (creation precedent) | 403 `STUDENT_ACCESS_DENIED` (student ownership, §7.2), 400 (teacher must exist / booking must belong — §7.5 rules 2–3; error classes INFERRED lock D4), 409 (duplicate active grant — INFERRED lock D4) | **not spec'd** → dominant convention (VS4 `dispute_open`/`review_create`: key required) — lock D4 | §7.2 + §7.5 rules | `STUDENT_PROFILE_UPDATED` (§7.1; "or ADMIN_ACTION if admin" — no admin path exists in R7 → parent events only) | none | new permission row (active) | insert `student_permissions` | NONE | student-row lock (lock D4) |
| E6 | DELETE | `/students/:id/permissions/:permission_id` | PARENT | path param | revoke confirmation (envelope — convention) | 200 | 403 `STUDENT_ACCESS_DENIED` (uniform — foreign/unknown permission indistinguishable, §7.2 no-oracle) | idempotent (guarded transition, R6 revoke precedent — lock D5) | §7.2 ownership (permission's student must be owned) | `STUDENT_PROFILE_UPDATED` (§7.1) | none | active → revoked (terminal per row) | `revoked_at = now()` guarded | NONE | permission-row lock (lock D5) |

**Explicitly non-approved (recorded, not implemented):**
- `GET /students/:id/permissions` (or any permission-read endpoint) — **does not exist in §7** despite P-07's access-list UI (C2). CONTRACT GAP.
- Any **teacher-facing** student-context/passport endpoint — **does not exist in §7/§8** despite PRD §12.3 and traceability row 43 (finding 1). CONTRACT GAP.
- Any **admin** student-mutation path — §7.1 lists PARENT only; "or ADMIN_ACTION if admin" in E5's event cell is conditional on an admin path that is not spec'd. No admin student endpoints are invented.
- `POST /students` and `GET /students/:id` — **already implemented (VS1); R7 does not modify them** (behavioral preservation is a gate, §20).

**§7.5 permission rules (APPROVED, all four):** (1) Parent must own student; (2) Teacher must exist; (3) If `granted_for_booking_id` exists, booking must belong to parent/student/teacher; (4) Teacher access expires or can be revoked.

**§7.2 (APPROVED):** `student_profiles.parent_id = authenticated_parent.id` else `403 STUDENT_ACCESS_DENIED`; "Never reveal whether another parent's student exists." (Uniform 403 for foreign AND unknown ids — implemented VS1 pattern, extended to all six endpoints.)

**§4.3 sensitive student data (APPROVED):** minimized set — student display name/nickname only; no full legal name (PRD §8.2 "Student data must be minimized").

# 5. Existing Code (baseline investigation — nothing modified)

**Exists (VS1, unchanged by R7):**
- `services.create_student(parent_user_id, data, request_id)` — inserts `student_profiles` (display_name required, birth_year/academic_level_id/school_year/primary_goal/preferred_mode/consent_status; consent defaults 'GRANTED' via `COALESCE`); event `STUDENT_PROFILE_CREATED` (entity `student`, actor PARENT); **no Idempotency-Key** (pre-convention era); parent-profile required (403 `FORBIDDEN` if absent).
- `services.get_student(parent_user_id, student_id)` — ownership-scoped SELECT (`WHERE id=%s AND parent_id=%s`); 403 `STUDENT_ACCESS_DENIED` on miss (uniform, no oracle); returns `{id, display_name, status, parent_id}`.
- `views.students_create` (`@require_roles("PARENT")`), `views.students_detail` (PARENT) — routes `POST /students`, `GET /students/:id`.
- **VS3 passport data writers (already populated by existing behavior):** report creation writes `student_progress_events` rows `TOPIC_COVERED` (per topic) and `SKILL_PRACTICED` (per skill) with `source_type='TEACHER_REPORT'` (services.py report-create path) — PRD/UX "Report contributes to Student Passport v0" is already realized at the data layer.

**Partially implemented:** nothing (no R7 endpoint exists beyond VS1's two).

**Documented only (no code):** E1–E6 of §4 (verified: zero code references to `passport`, `student_permissions`, or `STUDENT_PROFILE_UPDATED` in `backend/`).

**Explicitly absent (verified by scan):** no list/PATCH/DELETE/passport/permission service, view, or route; no permission-check helper for teacher reads (none needed in R7 — no teacher endpoint); no `DELETED`-status handling anywhere.

**Reusable (do NOT duplicate):**
- Ownership pattern: `get_student`'s parent-scoped SELECT + 403 `STUDENT_ACCESS_DENIED` (extend, don't re-implement differently).
- Idempotency helpers: `_idempotency_begin`/`_idempotency_complete` + `api_idempotency_keys` (v1.3 lifecycle guards) — for E5 (lock D4).
- Guarded-transition + per-actually-transitioned-event pattern (R6 revoke; VS8 transitions) — for E3/E6 (locks D2/D5).
- `write_event`/`write_security_event` + existing event values `STUDENT_PROFILE_CREATED`/`STUDENT_PROFILE_UPDATED` (both already in the `event_type` enum — verified in schema line 47–53 block: `STUDENT_PROFILE_CREATED`, `STUDENT_PROFILE_UPDATED` exist).
- Envelope + `request_id` response convention; `VALIDATION_ERROR`/`FORBIDDEN`/404-class error conventions.

**Must NOT be duplicated:** VS1 create/get behavior (gate: behavior-preservation test, §14 T-30); the no-oracle uniform-403 semantics (one pattern, all six endpoints).

**Pre-existing finding (F-1, out of R7 scope):** VS1 `create_student` does not enforce §7.3's "academic_level_id must … be active" (`academic_levels.is_active` exists in the schema but is unchecked; `birth_year` plausibility IS enforced by the DB CHECK 1990–2035). R7 neither fixes nor depends on this; a fix would be a separate, explicitly approved change.

# 6. Database Readiness (SCHEMA_CHANGE_REQUIRED = NO — proved object-by-object)

| Object | Exists? | R7 use | Change needed |
|---|---|---|---|
| `student_profiles` (id PK, parent_id FK RESTRICT, display_name CHECK≥1, birth_year CHECK 1990–2035, academic_level_id FK SET NULL, school_year, primary_goal, preferred_mode, consent_status DEFAULT GRANTED, status DEFAULT ACTIVE, UNIQUE(id,parent_id)) | YES (v1) | E1–E4, E5/E6 student validation | **NO** |
| `student_status` enum (ACTIVE, ARCHIVED, DELETED) | YES (v1) | E3 archive target = ARCHIVED (lock D2) | **NO** (DELETED semantics UNKNOWN — unused by R7) |
| `consent_status` enum (PENDING, GRANTED, REVOKED) | YES (v1) | PATCH-able field (D1) | **NO** |
| `student_permissions` (student_id+parent_id composite FK CASCADE, teacher_id FK CASCADE, granted_for_booking_id (no FK — lock D4 validates server-side), scope TEXT DEFAULT 'SESSION_CONTEXT', starts_at, expires_at, revoked_at, CHECK expires>starts) | YES (v1) | E5/E6 | **NO** |
| `student_progress_events` (student_id FK CASCADE, session_id/report_id/subject_id FK SET NULL, event_type `progress_event_type`, source_type, topic, value_numeric, note, created_by, created_at) | YES (v1) | E4 sources | **NO** |
| `progress_event_type` enum (TOPIC_COVERED, SKILL_PRACTICED, WEAKNESS_OBSERVED, STRENGTH_OBSERVED, HOMEWORK_ASSIGNED, HOMEWORK_COMPLETED, PROGRESS_NOTE, PARTICIPATION_NOTE) | YES (v1) | E4 aggregation | **NO** |
| `session_reports` (session_id UNIQUE, topics_covered[], skills_practiced[], participation, teacher_observations, homework, recommended_revision, next_objectives[], progress_indicator) | YES (v1) | E4 sources | **NO** |
| `sessions` / `bookings` / `subjects` (name_en, is_active) / `academic_levels` (is_active) | YES (v1) | E4 grouping (session.student_id, session.subject_id), E5 booking validation | **NO** |
| `event_type` enum incl. `STUDENT_PROFILE_CREATED`, `STUDENT_PROFILE_UPDATED` | YES (v1) | E2/E3/E5/E6 events | **NO** |
| Indexes | existing (students by parent via FK; permissions by student) | read paths | **NO** (a parent's students/permissions are small sets; no new index justified or spec'd) |

**Delete-behavior proof (drives lock D2):** `bookings (student_id, parent_id) → student_profiles ON DELETE RESTRICT` (migration 001 line 344) — a student with any booking **cannot be hard-deleted** (DB blocks it); `student_permissions` and `student_progress_events` cascade; `parent_profiles ← student_profiles` is RESTRICT (parent delete blocked by students, unchanged). Hence the only DB-legal interpretation of "Archive/delete own student" for students with history is a **soft archive**; hard delete is impossible by design and not implemented (finding recorded, not a gap to close — it is the schema's data-retention posture).

**Migrations v1→v1.4:** byte-identical to the protected baseline; R7 creates **none** (gate §20).

# 7. State Machine (mapped — nothing invented)

**Student profile status** (`student_status`: ACTIVE/ARCHIVED/DELETED): **no state machine is spec'd anywhere** (SM v1.0 and Addendum v1.1 contain no student-status section) — the transitions below are the lock-set, not approved transitions:

| Current | Action | Next | Terminal? | Reversible? | Actor | Guard | Event | Side effect |
|---|---|---|---|---|---|---|---|---|
| (absent) | create (VS1, unchanged) | ACTIVE (default) | no | — | PARENT | parent profile exists; display_name; (DB: birth_year range) | STUDENT_PROFILE_CREATED | row insert |
| ACTIVE | PATCH (E2) | ACTIVE | no | field-level | PARENT owner | ownership (§7.2); field validation (D1) | STUDENT_PROFILE_UPDATED | row update (status untouched — D1c) |
| ACTIVE | DELETE (E3) | **ARCHIVED** (lock D2) | quasi (re-activation path NOT spec'd — UNKNOWN) | UNKNOWN (no spec'd reactivate) | PARENT owner | ownership | STUDENT_PROFILE_UPDATED (first transition only — D2) | soft archive; bookings/payments untouched (RESTRICT bypassed by not deleting) |
| ARCHIVED | DELETE again (E3) | ARCHIVED (no-op) | — | — | PARENT owner | ownership | **none** (guarded no-op — D2, R6 convention) | none |
| ARCHIVED | PATCH (E2) | ARCHIVED | — | — | PARENT owner | ownership | STUDENT_PROFILE_UPDATED | field update allowed (lock D1d-adjacent INFERRED: archive is orthogonal to field edits; P-05 disables *Find teacher* for archived students, not editing) |
| ACTIVE/ARCHIVED | → DELETED | — | **UNKNOWN — no spec'd action writes DELETED; not implemented** (hard delete DB-blocked with history; no soft-DELETE action spec'd) | — | — | — | — | — |

**Permission row lifecycle** (`student_permissions`):

| Current | Action | Next | Terminal? | Actor | Guard | Event |
|---|---|---|---|---|---|---|
| (absent) | grant (E5) | active (revoked_at NULL, starts_at now) | no | PARENT owner | §7.5 rules 1–3; duplicate-active check (D4) | STUDENT_PROFILE_UPDATED |
| active | revoke (E6) | revoked (revoked_at now) | **yes per row** (no re-activation spec'd; re-grant = new row — D5) | PARENT owner | ownership via the permission's student | STUDENT_PROFILE_UPDATED (first flip only — D5) |
| active | time passes expires_at | **passively inactive** (predicate `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())` — §7.5 rule 4 "expires") | — | n/a (no job — no background jobs in scope) | predicate used by any future consumer | none (passive) |

**Illegal transitions / races (checked):** no client path writes `status` (D1c) — so ACTIVE↔DELETED, ARCHIVED→ACTIVE, etc. are unreachable (no invented transitions); revoke-after-revoke is a guarded no-op (not a transition); grant-after-revoke = new row (no row reuse); concurrent transitions are serialized by row locks (§11) — no stale-state race beyond the INFERRED last-writer-wins PATCH lock (D1d).

# 8. Authorization (five real roles — no SAFETY role exists or is invented)

Actual `role_name` enum: **PARENT, TEACHER, SUPPORT, OPS, ADMIN** (verified, schema v1 line 19). §7.1's Role column for all six endpoints: **PARENT**.

| Operation | PARENT (owner) | PARENT (non-owner) | TEACHER | SUPPORT | OPS | ADMIN | anonymous |
|---|---|---|---|---|---|---|---|
| E1 list own students | ALLOW | n/a (list is self-scoped by JWT user) | DENY 403 | DENY 403 | DENY 403 | DENY 403 (no admin student surface spec'd) | 401 |
| E2 PATCH own student | ALLOW | DENY 403 `STUDENT_ACCESS_DENIED` (uniform w/ unknown id — §7.2) | DENY 403 | DENY 403 | DENY 403 | DENY 403 (no admin path spec'd) | 401 |
| E3 DELETE own student | ALLOW | DENY 403 (uniform) | DENY 403 | DENY 403 | DENY 403 | DENY 403 | 401 |
| E4 passport (own student) | ALLOW | DENY 403 (uniform) | DENY 403 (no teacher read endpoint exists — finding 1) | DENY 403 | DENY 403 | DENY 403 | 401 |
| E5 grant permission (own student) | ALLOW | DENY 403 (uniform) | DENY 403 | DENY 403 | DENY 403 | DENY 403 (E5's "or ADMIN_ACTION if admin" is conditional on an admin path that is not spec'd — not implemented) | 401 |
| E6 revoke permission (own student's permission) | ALLOW | DENY 403 (uniform — foreign/unknown permission indistinguishable) | DENY 403 | DENY 403 | DENY 403 | DENY 403 | 401 |

Rationale for the non-PARENT DENYs: §7.1 assigns each endpoint to PARENT only; no other role's student-surface is spec'd anywhere (teacher student-context is a contract gap, finding 1; no admin student surface exists in the API). DENY = the `require_roles("PARENT")` decorator convention (VS1 `students_create` precedent). **Self-action:** all six are owner-self actions; there is no cross-owner path (ownership is the authorization). **Client-supplied identity:** none — the acting parent comes from the JWT (`request.user.id` → parent profile); the student/teacher/booking identifiers are validated against ownership/existence server-side, never trusted as identity. **Client-supplied state:** none — `status`, `parent_id`, `revoked_at`, `starts_at` are server-set.

# 9. Security (compared with R6's established conventions)

- **Ownership / no-oracle:** §7.2 uniform `403 STUDENT_ACCESS_DENIED` for foreign AND unknown ids on all six endpoints (VS1 `get_student` pattern extended; R6's uniform-401 no-oracle convention is the direct analogue). Test obligation: traceability row 42 (Security Gate).
- **PII:** minimized-minor-data by spec (PRD §8.2; API §4.3: display name/nickname only; no full legal name field exists in the schema — `display_name` is the only name column). Passport (E4) returns structured aggregates (topics/notes/counts) — no free-text PII beyond report-derived notes, parent-only read (no teacher read endpoint in R7). Wireframe P-06 rule enforced at the contract level: "No AI-derived claims; structured data only".
- **Secret exposure:** none — no token/credential material in any R7 response; no provider data.
- **Token/session implications:** none (R7 does not touch auth).
- **Rate limiting:** §27.1's explicit list (login, register, refresh token, password reset, teacher search/match, booking hold, payment initiation, webhooks) does **not** include student endpoints → **no new rate-limit scope is spec'd or created**; the existing global DRF throttle (R6 convention: inherit global, tune at STAGING) applies unchanged.
- **Audit:** `STUDENT_PROFILE_UPDATED` (event_ledger, entity `student`, actor PARENT) on E2/E3(first)/E5/E6(first); `STUDENT_PROFILE_CREATED` (VS1, unchanged) on create; **no events for reads** (E1/E4 — §7.1 + P-06 "None for parent read"); no security events are spec'd for R7 (none invented).
- **Enumeration/oracle risks:** closed by the uniform-403 rule (no existence signal); E1 exposes only the caller's own students (self-scoped query); E5/E6 responses carry no other-parent data.
- **Destructive operations:** E3 is soft-archive only (row retained; data intact; bookings/payments/progress events untouched — proven by FK rules §6); E6 is per-row revocation (terminal, intended). No hard delete exists or is authorized.
- **Privilege escalation:** none introduced (no role grants; PARENT-only decorator; no admin surface invented).

# 10. Idempotency (reuse of the established convention — no new convention)

Convention map (verified in code): actor-owned state-changing POSTs from VS2 onward use `_idempotency_begin/_complete` on `api_idempotency_keys` (scopes: `booking_hold`, `payment_initiate`, `review_create`, `dispute_open`, `payout_process`, `review_moderate`, `verification_submit`, `refund_*`, …); the key is required (400 `IDEMPOTENCY_KEY_REQUIRED`), replay of same key+hash → 200 stored body, same key different hash → 409 `IDEMPOTENCY_KEY_CONFLICT`, in-flight → 409 `IDEMPOTENCY_REQUEST_PROCESSING`; canonical = `sha256(json(sorted explicit-strings))`. Pre-convention exceptions: VS1 `POST /students` (no key — unchanged by R7) and slot block/unblock.

| Operation | Required? | Scope | Canonical | Replay | Conflict | In-flight | Completion | TTL | Lock |
|---|---|---|---|---|---|---|---|---|---|
| E1/E4 (reads) | n/a | — | — | n/a | n/a | n/a | n/a | — | — |
| E2 PATCH | **NO** (lock D1b — INFERRED: PATCH is idempotent by HTTP semantics; no PATCH-with-key precedent exists in the codebase; P-05's "recommended for update" is advisory UX text, treated as non-normative consistently with A-63's "recommended" handling) | — | — | n/a | n/a | n/a | n/a | — | student-row lock (D1d) |
| E3 DELETE | **NO** (lock D2 — guarded transition, R6 revoke precedent: idempotent by construction) | — | — | no-op 200 (no second event) | n/a | n/a | n/a | — | student-row lock |
| E5 grant | **YES** (lock D4 — dominant convention for actor-owned state-changing POSTs; `review_create`/`dispute_open` are the nearest analogues: non-financial, actor-owned, row-creating) | `student_permission_grant` (lock D4 — scope name INFERRED per the `_<domain>_<action>` naming convention) | `{student_id, teacher_id, scope, granted_for_booking_id, expires_at}` (all stringified; nulls as null — convention) | 200 stored body (single row) | 409 `IDEMPOTENCY_KEY_CONFLICT` (same key, different canonical) | 409 `IDEMPOTENCY_REQUEST_PROCESSING` | response = created permission (envelope) | v1.3 retention rules (existing) | student row `FOR UPDATE` inside the idempotency tx |
| E6 revoke | **NO** (lock D5 — guarded per-row transition, R6 revoke precedent; DELETE has no key precedent) | — | — | no-op 200 (no second event) | n/a | n/a | n/a | — | permission-row lock |

**No new convention is created:** every lock either reuses the VS4+ idempotency mechanism verbatim (E5) or the R6 guarded-transition pattern (E3/E6), or follows HTTP idempotency semantics (E2). No TTL invention (existing v1.3 retention applies to E5 records).

# 11. Concurrency (races, lock order, acyclicity)

**Lock order (locked):** `student_profiles` row (`FOR UPDATE`) → `student_permissions` rows (leaf). E5/E6 first lock the owning student row (ownership check under lock), then the permission row. E2/E3 lock the student row only. E1/E4 take no locks (MVCC reads).

**Acyclicity proof (checked against all existing chains):** VS5 payout chain = session→payment (row locks inside payout processing); VS8 refund chain = payment→refund→booking; VS9 dispute chain = dispute→session(no-show)→payment→booking; R6 auth chain = `auth_sessions` row (leaf). **`student_profiles` and `student_permissions` appear in none of these chains** (verified: `hold_booking` reads the student row without a lock; no financial/dispute service locks a student row) → adding student→permission introduces no cycle with any existing or each other (student is never locked by a chain that permission could lock back). **The lock graph remains acyclic.**

**Required races (locked outcomes; where the spec is silent, the lock is INFERRED and flagged):**

| Race | Winner | Loser | HTTP result | DB result | Event result | Idempotency result |
|---|---|---|---|---|---|---|
| C-1 two concurrent E5 grants, same key+body | first to lock | second | 201 / 200 (replay of stored body) | exactly 1 permission row | 1 `STUDENT_PROFILE_UPDATED` | replay per convention |
| C-2 two concurrent E5 grants, different keys, same teacher+scope+booking | first to lock | second | 201 / 409 (duplicate-active — lock D4, INFERRED) | 1 row (loser rolls back) | 1 event | n/a (different keys) |
| C-3 E5 grant vs E6 revoke (same permission target: grant row A + revoke of A mid-flight) | serialized on student row | — | 201 then 200 (or 409-dup then 200, order-dependent) | final state consistent (row revoked if revoke's row exists; grant row absent if dup-409) | events per actual transitions only | per-convention |
| C-4 two concurrent E2 PATCHes, same student | last committer | — (both succeed) | 200 / 200 | last-write-wins on the locked row (lock D1d, INFERRED — spec silent; no versioning spec'd) | 2 events (one per successful update) | n/a |
| C-5 E3 archive vs E2 PATCH (same student) | serialized on student row | — | 200/200 in either order | final: archived (if archive last) with possibly updated fields (if PATCH last — allowed per §7 ARCHIVED+PATCH row) | events per actual transitions | n/a |
| C-6 two concurrent E3 DELETEs | first flip | second | 200 / 200 (no-op) | 1 archive flip | **1 event** (guarded no-op — D2) | n/a |
| E4 reads vs any writer | n/a (MVCC) | — | 200 | consistent snapshot | — | — |

**UNKNOWNs preserved (not locked):** none new — every race has a lock or an INFERRED lock; the only spec silences (PATCH ordering, duplicate-grant) are explicitly flagged INFERRED in §19 (D1d/D4).

# 12. Financial Impact (FINANCIAL_SURFACE = NONE — proven by absence)

R7's six endpoints touch, in total: `student_profiles` (read/update/status-archive), `student_permissions` (insert/revoke), and **reads** of `sessions`, `session_reports`, `student_progress_events`, `subjects`, `bookings` (E5 booking-validation read), `academic_levels` (D1 validation read).

Proof of absence (object-by-object): no endpoint reads or writes `payments`, `refunds`, `payouts`, `payout_items`, `ledger_transactions`, or `ledger_entries`; no endpoint writes any financial status field; E5's booking access is a **read-only ownership validation** (booking belongs to parent/student/teacher — §7.5 rule 3); E4 is read-only aggregation; E3's archive leaves `bookings`/`payments` rows untouched (RESTRICT FK proves the row is retained). **No ledger form is invented; no accounting entry is created; no financial behavior is unspecified-and-needed** (there is no financial behavior at all). No financial-workflow gate (Engineering Governance §5) is triggered — there is no financial workflow change.

# 13. Frontend Scope (no expansion; production UI stays R17)

- **DEV console (optional, not contractually required):** a minimal parent-console view (passport data + permission grant/revoke controls) MAY be built as a DEV console section — consistent with the VS8/VS9/R6 convention of a DEV console per slice. It is **optional** because the approved API contract (§7) is fully satisfiable with API-only delivery.
- **Production UI (P-06/P-07): OUT OF SCOPE for R7** — the wireframe-specified P-06/P-07 screens belong to the approved 64-screen production set, which is the **R17 phase** ("a phase, not a slice" — Post-VS8 audit §14/R17). No production screen is built in R7.
- **Correction recorded (C1):** the VS10 plan's "no wireframe specifies one" for passport is inaccurate (P-06/P-07 exist, LF+HF). The correction changes the *citation*, not the *scope*: R7 remains API-first; the production screens remain R17's.
- **Teacher-side UI:** none (no teacher endpoint exists — finding 1).
- **New screens (R7 DEV-slice count):** 0 required; 0–1 optional DEV-console sections (no new production screens).

# 14. Test Readiness (inventory designed — no test written)

Convention: `tests/test_student_completion.py` (service/authorization/validation) + `tests/test_student_completion_concurrency.py` (C-races) per the slice convention (VS5–VS10 pattern; traceability's planned name `test_student_permissions.py` is superseded in naming by the slice convention — informational). Every test cites its source. **VALID** = proves an APPROVED behavior or a locked (D/INFERRED-flagged) behavior; **REQUIRING DECISION** / **UNSUPPORTED** = contract does not support it.

| ID | Test | Source/contract | Class |
|---|---|---|---|
| T-01 | passport happy path: student with completed sessions + reports → `subjects[]` populated from the three source tables; `student_id` correct | API §7.4 (shape + sources); PRD §12.2 | VALID |
| T-02 | passport aggregation mapping: `recent_topics` from TOPIC_COVERED; `recent_progress_notes` from PROGRESS_NOTE/PARTICIPATION_NOTE; `recurring_weaknesses` from WEAKNESS_OBSERVED (≥2, lock D3b); `completed_sessions` = COMPLETED session count per subject | §7.4 sources + `progress_event_type` enum; D3b INFERRED lock | VALID (against D3 locks) |
| T-03 | passport empty: student with no sessions/reports → `subjects: []` (shape preserved) | §7.4 shape; P-06 empty state ("Progress appears after completed sessions…") | VALID |
| T-04 | passport no-AI-claims: response contains exactly the §7.4 fields (structured data only) | §7.4 "No AI-generated claims are returned in MVP"; P-06 | VALID |
| T-05 | passport ownership: foreign student id → 403 `STUDENT_ACCESS_DENIED`, identical body-class to unknown id (no oracle) | §7.2 | VALID |
| T-06 | passport anonymous → 401 | RBAC convention (§7.1 PARENT row) | VALID |
| T-07 | list own students: 200, own students only, `status` present, created_at desc (D3a INFERRED order) | §7.1; D3a | VALID |
| T-08 | list cross-parent isolation: other parent's students never appear | §7.2; PRD §8.2; traceability row 42 | VALID |
| T-09 | PATCH updates each allowed field (D1 set); `updated_at` advances; `STUDENT_PROFILE_UPDATED` written (entity `student`, actor PARENT) | §7.1 (event); D1 | VALID |
| T-10 | PATCH `status`/`parent_id` in body are ignored (server-set — D1c) | D1c INFERRED lock (no client state) | VALID (against D1c) |
| T-11 | PATCH validation: implausible `birth_year` (e.g. 1950) → 400 `VALIDATION_ERROR` (pre-validated, DB CHECK 1990–2035 as backstop); inactive `academic_level_id` handling per D1e | §7.3 validation parity (D1e INFERRED); schema CHECK | VALID (against D1) |
| T-12 | PATCH foreign/unknown student → 403 uniform | §7.2 | VALID |
| T-13 | DELETE archives: `status` ACTIVE→ARCHIVED, row retained, bookings/payments untouched (DB-asserted), event written | §7.1 (event); D2; §6 RESTRICT proof | VALID |
| T-14 | DELETE idempotent: second DELETE → 200 no-op, no second event | D2 (R6 guarded-transition convention) | VALID (against D2) |
| T-15 | DELETE with booking history succeeds (soft archive; hard delete would be DB-blocked — proven) | D2; §6 | VALID |
| T-16 | DELETE foreign/unknown → 403 uniform | §7.2 | VALID |
| T-17 | grant happy: row created (active, starts_at, scope SESSION_CONTEXT, booking ref), response envelope, event written | §7.5; D4 | VALID |
| T-18 | grant unknown `teacher_id` → 400 (D4c INFERRED error class) | §7.5 rule 2; D4c | VALID (against D4c) |
| T-19 | grant booking validation: booking of another parent → 403 uniform (no oracle); booking without the teacher → 400 (D4c); valid triple → 201 | §7.5 rule 3; §7.2; D4c | VALID (against D4) |
| T-20 | grant idempotency: replay same key+body → 200 stored body, 1 row, 1 event; same key different body → 409 `IDEMPOTENCY_KEY_CONFLICT` | §10 (VS4+ convention) | VALID |
| T-21 | grant duplicate active (different key, same teacher+scope+booking) → 409 (D4b INFERRED) | D4b INFERRED lock | VALID (against D4b) |
| T-22 | grant scope allowlist: `SESSION_CONTEXT` accepted; unknown scope → 400 (D4d INFERRED) | §7.5 (only scope named); D4d | VALID (against D4d) |
| T-23 | revoke happy: `revoked_at` set, 200, event written (first flip) | §7.1 (event); D5 | VALID |
| T-24 | revoke idempotent: revoke already-revoked → 200 no-op, no second event | D5 (R6 convention) | VALID (against D5) |
| T-25 | revoke foreign/unknown permission → 403 uniform (no oracle) | §7.2; D5 | VALID (against D5) |
| T-26 | permission passive expiry: expired permission is inactive per the §7.5 rule-4 predicate | §7.5 rule 4 | **UNSUPPORTED in R7** — no R7 endpoint consumes the predicate (no permission-read endpoint, no teacher read endpoint — finding 1/C2); predicate exists in code for future consumers but is unobservable in R7's API → **test removed; gap recorded** |
| T-27 | C-1/C-2 grant races (concurrency file): 201+200-replay (same key); 201+409 (dup, different keys); 1 row; 1 event | §11; D4 | VALID |
| T-28 | C-3 grant-vs-revoke race: consistent final state; events per actual transitions | §11 | VALID |
| T-29 | C-4/C-5/C-6 PATCH×2 (last-write-wins, 2 events), archive-vs-PATCH, DELETE×2 (1 event) | §11; D1d/D2 INFERRED | VALID (against D1d/D2) |
| T-30 | regression: VS1 `create_student`/`get_student` behavior byte/behaviorally preserved (create 201 + `STUDENT_PROFILE_CREATED`; get 200/403) | VS1 contract (gate §20) | VALID |
| T-31 | role denial matrix: TEACHER/SUPPORT/OPS/ADMIN on all six endpoints → 403; anonymous → 401 | §8 matrix (from §7.1 PARENT-only) | VALID |
| T-32 | no-oracle sweep: on E2–E6, foreign-id and unknown-id responses are code-identical (403 `STUDENT_ACCESS_DENIED`) | §7.2 "Never reveal…" | VALID |

**Totals: 31 VALID (22 service + 3 concurrency + 6 regression/matrix), 0 REQUIRING DECISION (all D-locked behaviors are explicitly flagged INFERRED in §19), 1 UNSUPPORTED (T-26 — removed, gap recorded).** No test asserts behavior the contract does not support; D-locked assertions cite their lock id.

# 15. E2E Readiness (scenarios designed — none executed, no file created)

Convention: standalone `tests/e2e_student_completion.py` (VS2–VS10 pattern: own PG cluster + migrations + Django dev server; API-level; `check()` gates; non-zero exit on failure). Production-browser automation is not the repo convention (R6/VS8/VS9 precedent: API + SSR serving at most).

| ID | Setup | Actor | Request(s) | Expected response | DB assertion | Event assertion | Security assertion | Financial assertion | Cleanup |
|---|---|---|---|---|---|---|---|---|---|
| S1 | full booking cycle + completed session + report (VS2/VS3 flow) | PARENT (owner) | `GET /students/:id/passport` | 200; `subjects[]` with completed_sessions≥1, recent_topics ⊇ report topics, notes present | passport values match `student_progress_events`/`session_reports` rows (direct SQL cross-check) | none (parent read — §7.1/P-06) | no event rows created; response has no PII beyond structured aggregates | none (read-only) | scenario-scoped rows |
| S2 | fresh student, no sessions | PARENT (owner) | passport | 200; `subjects: []` | 0 progress events for the student | none | — | — | — |
| S3 | student + 2 teachers (1 with a booking) | PARENT (owner) | grant (valid triple) → revoke | 201 then 200 | permission row created then `revoked_at` set; no other rows touched | 2 `STUDENT_PROFILE_UPDATED` (one per transition) | grant body never echoes other-parent data; revoke of unknown id → 403 | none | — |
| S4 | two parents, each with a student | PARENT B | all six endpoints against A's student ids | uniform 403 `STUDENT_ACCESS_DENIED` on E2–E6; E1 returns only B's student | A's rows unchanged (0 writes) | no events for B's denied attempts | foreign-vs-unknown id responses code-identical (no oracle) | none | — |
| S5 | student WITH booking history (booked, paid-mock, completed) | PARENT (owner) | `DELETE /students/:id` twice | 200, then 200 no-op | `status='ARCHIVED'`, row retained; bookings/payments/sessions rows byte-unchanged (direct SQL before/after) | exactly 1 `STUDENT_PROFILE_UPDATED` | — | **financial tables untouched (direct SQL)** | — |
| S6 | student + teacher + booking | 2× PARENT (owner, parallel HTTP) | concurrent grants: same key (×1 pair) and dup-active different keys (×1 pair) | 201+200-replay; 201+409 | 2 rows total (1+1); no orphans; idempotency rows COMPLETED | 2 events total | — | none | — |
| S7 | all five roles + anonymous | each | each of the six endpoints | 403 (TEACHER/SUPPORT/OPS/ADMIN), 401 (anonymous), 200 (own PARENT on own resources) | no writes by denied actors | no events from denied attempts | no data leakage in denied responses | none | — |
| S8 | full-slice coexistence | mixed | R6 refresh/revoke + VS9 dispute open + VS8 refund create (smoke) alongside R7 calls | all 200-class per their contracts | cross-slice rows consistent; no cross-writes | per-slice events intact | — | refund smoke keeps ledger balanced (direct SQL) | — |

**E2E_READINESS = READY** (8 scenarios; all assertions map to §4/§11/§12; no scenario requires an unapproved endpoint or invented behavior).

# 16. Dependency Audit (new dependencies = NONE — proven)

- **Python packages:** R7 uses only the existing stack (Django/DRF views, `psycopg` via the existing `db` helpers, `hashlib`/`secrets` already imported for idempotency). No new package. `requirements.txt` unchanged (gate: byte-identical, §20).
- **npm packages / frontend:** optional DEV-console view uses only the existing `lib/api.ts` client; no package. `package.json`/`package-lock.json` unchanged (gate).
- **New services / external APIs / providers / workers / cron / queues:** NONE — passport is an SQL aggregation over existing tables; permission expiry is passive (predicate, no job); no provider of any kind. **Proven by absence:** no R7 operation requires any external call (every input is a local DB read or a JWT-derived identity).
- Any future dependency would be a governance decision, not an implementation assumption (none is anticipated).

# 17. Scope Boundary

**IN SCOPE (the complete R7 slice):**
- E1 `GET /students` · E2 `PATCH /students/:id` · E3 `DELETE /students/:id` · E4 `GET /students/:id/passport` · E5 `POST /students/:id/permissions` · E6 `DELETE /students/:id/permissions/:permission_id` — services, views, routes per §4 (PARENT-only, §7.2 ownership, §7.1 events).
- Locks D1–D9 as recorded (§19) — recorded in the approved slice plan before implementation.
- Tests (§14: 31 VALID) + concurrency file + standalone E2E (§15: S1–S8).
- Optional parent-console DEV view (13).
- Slice deliverables: implementation/test/E2E reports, Dependency Audit v1.9→v1.10 chain, README section.

**OUT OF SCOPE (explicit, including accidental-expansion guards):**
- **Teacher-side student-context/passport read endpoint** — no approved API (finding 1; PRD §12.3/traceability row 43 intent noted; not invented).
- **Permission-read endpoint** (P-07's list has no approved API — C2).
- **Admin student-mutation surface** (not spec'd; "or ADMIN_ACTION if admin" conditional not triggered).
- **Production UI P-06/P-07 screens** — R17 phase (64-screen set); no production UI in R7.
- **`DELETED` status semantics / hard delete / reactivate-from-archive** — no spec'd action; hard delete DB-blocked with history (data-retention posture, not a gap).
- **Background jobs / cron / workers** (expiry is passive; no jobs in scope).
- **VS1 create-validation fix (F-1: `academic_levels.is_active` unchecked)** — pre-existing finding; separate decision.
- **R10 (suspension) / R11 (ledger admin) / R4 (cancellation) / VS11 items** — none enter R7.
- **Notifications** (none spec'd for R7), **AI of any kind** (§7.4/PRD §12.4 future-AI exclusion), **new providers**, **real payment/refund/payout** (FORBIDDEN at all times in DEV), **schema changes** (none required — §6), **financial behavior** (none exists — §12).

**DEFERRED (with gating items):** teacher-side context read (needs an approved endpoint spec + its authorization/audit design); permission-read endpoint (needs an approved contract); DELETED/reactivation semantics (needs a spec decision); F-1 create-validation fix (needs an approval decision); P-06/P-07 production screens (R17 phase).

**UNKNOWN (preserved, not converted):** (U1) `DELETED` vs `ARCHIVED` distinction and any reactivate path; (U2) whether ARCHIVED students may be edited after archive (locked as allowed, INFERRED — D1d-adjacent, flagged); (U3) exact duplicate-grant semantics (locked 409, INFERRED — D4b, flagged); (U4) passport aggregation thresholds/limits (locked, INFERRED — D3, flagged); (U5) PATCH field-set and ordering semantics (locked, INFERRED — D1, flagged).

**BLOCKING:** **none** (zero blocking decisions; all UNKNOWNs are either preserved (U1) or explicitly locked as INFERRED with citation (U2–U5) — the approver can override any lock at approval time).

# 18. Risk Register

| Class | Nominal risk | Residual risk | Mitigation | Remaining UNKNOWN |
|---|---|---|---|---|
| FINANCIAL | none (no financial surface — §12 proven) | none | S5/S8 financial-touched assertions (direct SQL) | none |
| SECURITY | PII exposure via passport/permissions (minor data) | LOW | minimized-data schema (no legal-name column); uniform 403 no-oracle (§7.2, T-05/T-12/T-16/T-19/T-25/T-32); no teacher read endpoint in R7 (no consumer of shared context exists → shared data is currently readable by no one but the parent); P-06 "no AI-derived claims" contractually asserted (T-04) | U2–U4 (locked, flagged) |
| OPERATIONAL | none (no jobs, no new surfaces for failure) | LOW | passive expiry (no job to fail); idempotency via existing v1.3-guarded table | none |
| IMPLEMENTATION | aggregation mapping ambiguity (passport) | LOW | D3 locks + T-01/T-02 assert exact mapping; shape asserted (T-04) | U4 (locked) |
| DATA-INTEGRITY | accidental hard delete / cascade surprise | LOW | soft-archive only (D2); RESTRICT FK makes hard delete impossible with history (DB-enforced); S5 before/after DB proof; T-13/T-14/T-15 | U1 (DELETED unused) |
| SCOPE | creep into teacher-context / permission-read / admin surface | LOW | §17 OUT list is a gate (§20); scope audit by `git diff` at pre-commit (VS10/R6 precedent) | none |

# 19. Decision Register (plan-time locks — all cited; INFERRED flags explicit; none silently resolved)

| ID | Decision | Why it matters | Evidence (source) | Current state | Recommended decision (lock) | Blocking? | Owner |
|---|---|---|---|---|---|---|---|
| D1 | PATCH field set + semantics: updatable = `display_name, birth_year, academic_level_id, school_year, primary_goal, preferred_mode, consent_status`; `status`/`parent_id`/`id`/timestamps server-set (ignored if sent); response = updated student object (envelope); validation parity with §7.3 (birth_year plausibility pre-checked; academic_level existence via FK; `is_active` check per D1e); last-writer-wins under student-row lock, no versioning | §7.1 names PATCH but not its fields | API §7.1 (event only); schema columns; P-05 "Edit profile" CTA; VS1 create field set | CONTRACT GAP | as stated (INFERRED lock); D1e `is_active` on PATCH: validate like §7.3 says for create (consistency) — INFERRED | NO | Architecture Owner |
| D2 | DELETE = soft archive `status → 'ARCHIVED'`; idempotent (re-DELETE = 200 no-op, no second event); event `STUDENT_PROFILE_UPDATED` on first transition only; no hard delete (DB RESTRICT with history; minimized-data retention); `DELETED` unused (UNKNOWN U1) | §7.1 "Archive/delete" is ambiguous; DB makes hard delete impossible with history | API §7.1; schema FK rules (§6 proof); R6 guarded-transition convention; P-05 "State badges: Active, Archived" | CONTRACT GAP | as stated (archive portion INFERRED lock — the only DB-legal reading; "deleted" portion recorded as UNKNOWN, not implemented) | NO | Architecture Owner + Database Owner (acknowledge FK posture) |
| D3 | Passport aggregation mapping (response shape is APPROVED §7.4; mapping internals are not): `completed_sessions` = COUNT(sessions status COMPLETED) per subject (via session.subject_id); `recent_topics` = distinct topic values from TOPIC_COVERED events, most recent 10 per subject (created_at desc); `recurring_weaknesses` = subjects/topics with ≥2 WEAKNESS_OBSERVED events (threshold INFERRED); `recent_progress_notes` = note values from PROGRESS_NOTE + PARTICIPATION_NOTE events, most recent 5 per subject; subject_name from `subjects.name_en` (fallback name_ar) | §7.4 gives shape + sources + "no AI", not thresholds/windows | API §7.4; `progress_event_type` enum; `session_reports`/`student_progress_events` schemas; P-06/HF layout | CONTRACT GAP (shape APPROVED, mapping INFERRED) | as stated; limits/thresholds are implementation constants, documented in the slice plan; overridable at approval | NO | Architecture Owner |
| D4 | E5 grant: Idempotency-Key **required**, scope `student_permission_grant` (naming per convention), canonical `{student_id, teacher_id, scope, granted_for_booking_id, expires_at}`; response = created permission object (envelope) — INFERRED shape (spec silent); error classes: unknown teacher → 400 `VALIDATION_ERROR`; invalid booking triple (foreign parent → 403 `STUDENT_ACCESS_DENIED` uniform; wrong teacher/no booking → 400 `VALIDATION_ERROR`); duplicate ACTIVE permission (same teacher+scope+booking, different key) → 409 `VALIDATION_ERROR`-class duplicate (INFERRED); scope allowlist = {`SESSION_CONTEXT`} (only scope named in §7.5) → unknown scope 400 (INFERRED); `granted_for_booking_id` validated server-side against (parent, student, teacher) triple; no FK exists for it (schema) so validation is service-side | §7.5 gives request + 4 rules, not response/errors/idempotency | API §7.5; §10 convention map (review_create/dispute_open precedent); §7.2 no-oracle; schema (no booking FK on permissions) | CONTRACT GAP | as stated (idempotency = CONVENTION reuse; response/error/dup/scope items = INFERRED locks) | NO | Architecture Owner |
| D5 | E6 revoke: no idempotency key (DELETE; guarded transition, R6 revoke precedent); idempotent no-op on already-revoked (200, no second event); foreign/unknown permission → 403 `STUDENT_ACCESS_DENIED` uniform (permission's student ownership); revocation terminal per row (re-grant = new row); passive expiry predicate `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())` implemented as the shared "active" predicate for future consumers (unobservable in R7 — T-26 removed) | §7.1/§7.5 rule 4; no DELETE-key precedent in codebase | API §7.1/§7.5; R6 revoke implementation (committed `709cfb3`); §7.2 | CONTRACT GAP (mechanics) | as stated (INFERRED locks on mechanics; the predicate is the direct reading of §7.5 rule 4) | NO | Architecture Owner |
| D6 | E1 list response: standard envelope `{data: [student objects], request_id}`; item = same field set as `get_student` response + `created_at`; order `created_at desc`; **no pagination** (spec silent; a parent's students are a small bounded set; cursor convention introduced only if a spec adds it — INFERRED) | §7.1 names the endpoint only | API §7.1; `get_student` response shape (VS1); list-convention precedent (VS8 admin lists have pagination — but the spec names none here) | CONTRACT GAP | as stated (INFERRED lock) | NO | Architecture Owner |
| D7 | E5 booking-triple validation details: "booking must belong to parent/student/teacher" (§7.5 rule 3) = booking.student_id = the student AND booking's parent chain = the acting parent AND booking.teacher_id = the presented teacher_id; all server-side; any mismatch → the error classes locked in D4 | §7.5 rule 3 wording | API §7.5; bookings schema (student_id, parent chain via bookings→parent_profiles) | APPROVED rule; mechanics INFERRED | as stated | NO | Architecture Owner |
| D8 | Teacher-side student-context consumption: **NOT IMPLEMENTED** (no approved endpoint — finding 1). The permission "active" predicate (D5) is the only shared-context artifact R7 ships; no teacher read path exists in R7. | PRD §12.3/traceability row 43 intent vs absent API | API §7/§8 (absence); PRD §12.3; traceability row 43 | CONTRACT GAP (recorded) | keep OUT (no endpoint invented); defer to an approved endpoint spec | NO (records a gap; does not block R7) | Architecture Owner + Product (future spec) |
| D9 | Events: `STUDENT_PROFILE_UPDATED` on E2/E3(first)/E5/E6(first) with entity `student`, actor = acting PARENT (VS1 `STUDENT_PROFILE_CREATED` event shape: entity `student`, actor_user_id, actor_role PARENT); **no events for E1/E4 reads** (P-06 "None for parent read"); no security events (none spec'd — none invented); E5's "or ADMIN_ACTION if admin" clause is inert in R7 (no admin path — D8/§8) | §7.1 Event column; P-06; VS1 event precedent | API §7.1; wireframe P-06; VS1 `create_student` code | APPROVED (events) + INFERRED (no-read-events confirmation is spec-supported by P-06) | as stated | NO | Architecture Owner |

**Decision counts: 9 decisions (D1–D9); 0 blocking.** All INFERRED-locked items are individually flagged and overridable at approval; no UNKNOWN was converted to YES silently (U1 remains UNKNOWN; U2–U5 are explicit locks with citation).

# 20. Implementation Gates (the slice may start only when)

1. **Scope + locks approved:** D1–D9 recorded verbatim (or overridden) in the approved VS10/R7 slice plan; the §17 IN/OUT boundary accepted.
2. **No financial-workflow gate** — none required (zero financial surface, §12 proven).
3. **No schema gate** — no migration (SCHEMA_CHANGE_REQUIRED = NO, §6 proven).
4. **Behavior-preservation gate:** VS1 `create_student`/`get_student` behavior unchanged (T-30 in the suite).
5. **Standard slice gate** (Engineering Governance convention; VS5–VS10 precedent): plan approved → implement → gates green (full suite + E2E + scope audit + dependency audit) → single commit → push only when instructed.
6. **Pre-commit scope audit:** `git diff` limited to the §13 IN list; protected surfaces (migrations, manifests, VS1–R6 files outside the additive regions) byte-identical.

# 21. Rollback Strategy

- R7 is **purely additive** (new service functions appended, new views, new routes, new test files, docs) — **no schema change, no migration, no modification of existing endpoint behavior** (VS1 student endpoints untouched; T-30 gate).
- Rollback = revert the single R7 commit. No data migration back exists or is needed: archived students (if any) remain archived rows (business state, fully restorable by a future explicit decision — no migration coupling); granted/revoked permission rows are inert without the R7 endpoints (no other consumer exists — D8).
- No lock or index to remove; no dependency to retract; no event-enum removal (no new values).

# 22. Final Readiness Decision

**`R7_SCOPE_READY = YES`** — at the declared scope (§13 IN list), with the 9 recorded plan-time locks (D1–D9), **zero blocking decisions**, **zero schema changes** (proved object-by-object, §6), **zero financial surface** (proved by absence, §12), **zero new dependencies** (proved, §16), a fully specified passport contract (API §7.4) over already-populated data sources, an already-implemented ownership/no-oracle pattern (VS1), reuse of the established idempotency (VS4+) and guarded-transition (R6) conventions, a complete 31-test + 8-scenario E2E design with every assertion source-cited (§14/§15), and a purely-additive rollback (§21).

R7 is **not** called ready because it looks easy: it is ready because every contract item is either APPROVED (cited), CONVENTION-reuse (cited), or an explicit INFERRED lock (flagged, overridable, cited) — and every gap that cannot be locked (teacher-side context, permission read, DELETED semantics) is recorded OUT/DEFERRED rather than invented.

# 23. Self-Audit (Phase 19 verification of this document)

- No invented endpoint: E1–E6 are the §7.1 set verbatim; teacher-context/permission-read/admin surfaces are explicitly NOT created (findings 1/C2/§8).
- No invented state: student status transitions are a lock-set on an UNSPECIFIED machine (flagged); `DELETED` untouched (UNKNOWN U1).
- No invented event: only `STUDENT_PROFILE_UPDATED`/`STUDENT_PROFILE_CREATED` (both pre-existing enum values, verified in schema); no security events (none spec'd).
- No invented ledger entry / financial behavior: §12 proves absence; nothing created.
- No invented schema: §6 proves sufficiency object-by-object; no migration designed.
- No invented role: five-role matrix from the actual `role_name` enum; SAFETY not invented.
- No invented dependency: §16 proves none.
- No R10/R11/R4/VS11 implementation content: §17 OUT list; none appears in any design.
- No D3b (R6) implementation content: R6 untouched; rollback/rollout references only R7's own additive commit.
- No contradiction with protected R6/VS9/VS8: R7's lock order (student→permission) is disjoint from all existing chains (§11 acyclicity proof); no protected file is modified.
- All UNKNOWNs preserved: U1 (DELETED/reactivation) preserved as UNKNOWN; U2–U5 explicit INFERRED locks with citations (flagged, overridable) — none silently converted.
- All blocking decisions explicitly listed: §17 BLOCKING = none (count: 0); §19 all 9 decisions non-blocking with owners.

# 24. Final Status

```text
R7_DISCOVERY:               COMPLETE (all 20 phases executed; sources cited per item)
R7_SCOPE_READY:             YES (at declared scope; 9 plan-time locks; 0 blocking decisions)
BLOCKING_DECISIONS:         0
DECISION_COUNT:             9 (D1-D9; INFERRED-locked: D1, D2-archive, D3, D4, D5, D6, D7-mechanics, D9-read-events; APPROVED-anchored: D8 gap record + D7 rule)
SCHEMA_CHANGE_REQUIRED:     NO (proved object-by-object, section 6)
FINANCIAL_SURFACE:          NONE (proved by absence, section 12)
SECURITY_READINESS:         READY (uniform no-oracle 403s, minimized PII, no new consumer of shared data, no new secrets; 5-role matrix from the real enum)
TEST_READINESS:             READY (31 VALID tests designed + source-cited; 1 unsupported test removed and gap recorded; 0 tests require decisions beyond the recorded locks)
E2E_READINESS:              READY (8 scenarios designed, all assertions source-cited; none executed; no file created)
IMPLEMENTATION_STARTED:     NO
CODE_MODIFIED:              NO
DATABASE_MODIFIED:          NO
TESTS_MODIFIED:             NO
FRONTEND_MODIFIED:          NO
DEPENDENCIES_MODIFIED:      NO
COMMIT_CREATED:             NO
PUSH_PERFORMED:             NO
DOCUMENT:                   EduTrust_VS10_R7_Implementation_Authorization_v1.0.md (this file — the only file created)
VS8:                        PROTECTED (b73d8ce; untouched)
VS9:                        PROTECTED (af8f818; untouched)
R6:                         PROTECTED (709cfb3; untouched)
R10:                        NOT_STARTED
R11:                        NOT_STARTED
R4:                         NOT_STARTED
VS11:                       NOT_STARTED
STOP_AFTER_PLAN:            YES
```

**STOP after this plan. R7 is authorized-in-draft pending the gate pass of §20; it was NOT implemented. Nothing was committed or pushed. No feature work of any kind was performed.**
