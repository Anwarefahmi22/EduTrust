# EduTrust — Vertical Slice #7 Implementation Plan v1.0

**Slice:** DEV Vertical Slice #7 — Teacher Verification
**Status:** APPROVED SCOPE — PLANNED, NOT STARTED
**Basis:** `EduTrust_Post_VS6_Continuation_And_Roadmap_Audit_v1.0.md` (candidate R3, ranked #1)
**Environment:** DEV only · Real payment FORBIDDEN · Real payout FORBIDDEN · Production NOT APPROVED
**Classification legend:** `AUTHORITATIVE` = stated in an approved baseline document · `INFERRED` = derivable from approved documents, not explicitly stated · `UNKNOWN` = no approved document covers it · `REQUIRES APPROVAL` = decision must be confirmed at sprint start

---

# 1. Pre-planning state verification (read-only, performed this sprint)

| Check | Result |
|---|---|
| Branch | `arena/01a03280-edutrust` |
| Local HEAD | `e0e3d89c786e790abd6b7c4a9d69af7499280f34` |
| Remote branch HEAD | `e0e3d89c786e790abd6b7c4a9d69af7499280f34` — exact match |
| `main` | `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` — unchanged |
| Working tree | clean except the untracked Post-VS6 audit document |
| VS1–VS6 presence | all deliverables present (commits `b245aae`/`83c7bc5`/`e0e3d89`) |
| VS7 implementation absence | verified — no verification endpoints in `urls.py`; zero VS7 code in backend/frontend/tests |
| Existing verification surface (VS1) | `verification_status` + `listing_status` exposed in: `GET/PATCH /teachers/me`, `GET /teachers/:id`, `GET /teachers/search`, `GET /teachers/:id/trust-profile` (4 service queries); every new teacher is `UNVERIFIED` / `DRAFT` (schema defaults); no mechanism exists to change `verification_status` |

---

# 2. Authoritative sources read

| Document | Used for |
|---|---|
| PRD §9.2 (P0/P1), §10.1 (P0), §8.4 (P0) | Verification levels 0–3 (Level 3 = future, excluded); MVP requirements (submit, admin review, status on profile, events logged); acceptance criteria (auditable approval/rejection, parents distinguish verified, document access restricted); trust-profile fields `verified_identity`/`verified_qualification` |
| API Architecture §8.1/§8.4/§8.5, §21.1 | The 6 approved endpoints (exact); submission request shape (type + documents + metadata; "API stores metadata and storage key only"; "Teacher cannot self-approve verification"); trust-profile response shape (`identity.verified`, `qualifications.verified`); "verification_status/listing_status not freely editable"; admin table (verify/reject events; "Document access is audited separately") |
| State Machines v1.0 + v1.1 Addendum | **No dedicated verification state machine exists** (verified by search) — the lifecycle is specified by the schema enums + API §8.4 rules + PRD. SM §3.6 (idempotency mandatory for retryable commands) informs V5 |
| Schema (v1 migration, live-verified) | `teacher_verification_status` enum (6 values), `verification_type` enum (4 values), `verification_review_status` enum (4 values), `document_status` enum (4 values); `teacher_verifications` table (status default SUBMITTED, reviewed_by/at, reviewer_note, rejection_reason, metadata); `verification_documents` table (document_type, storage_key UNIQUE, sha256, mime, size, encrypted, status); event enum already contains `TEACHER_VERIFICATION_SUBMITTED`, `TEACHER_VERIFIED`, `TEACHER_REJECTED`, `ADMIN_ACTION`; security event enum already contains `DOCUMENT_ACCESS` |
| Product/Ops policies | **No verification-related policy exists** (verified) — no OPEN policy blocks this slice |
| Security/Privacy Plan §6 + data matrix | "Document access only through audited admin/OPS flow"; matrix: teacher=own metadata only, support=No, OPS=audited limited, admin=audited full; `SECURITY_EVENT DOCUMENT_ACCESS` |
| Feature Flag Governance | `DOCUMENT_ACCESS_ENABLED` (staging/prod, Security Owner) and `TEACHER_PUBLIC_LISTING_ENABLED` (staging/prod, **default false before pilot**, "Cannot show unverified/suspended teacher as listed") — both staging/prod-scoped; VS7 does not implement or alter them (see §9) |
| UX / prototype specification | DEV console targets: CP-T-03 (teacher verification submission/status), CP-A-02 (verification queue), CP-A-03 (verification detail) |
| Test Traceability Matrix | **No verification rows exist** — VS7 test plan derives from PRD acceptance criteria + API §8.4 rules (noted, not a gap in approved coverage) |
| Implementation Baseline | API Architecture APPROVED (verification endpoints part of the approved API baseline); schema chain APPROVED (tables present) |

---

# 3. Verification model (as it exists — verified, not re-invented)

**Enums (all pre-existing, `AUTHORITATIVE`):**
```text
teacher_verification_status: UNVERIFIED (default), SUBMITTED, IDENTITY_VERIFIED, QUALIFICATION_REVIEWED, REJECTED, SUSPENDED
verification_type:           IDENTITY, QUALIFICATION, EXPERIENCE, BACKGROUND_CHECK
verification_review_status:  SUBMITTED (default), APPROVED, REJECTED, EXPIRED
document_status:             UPLOADED (default), APPROVED, REJECTED, DELETED
```

**PRD levels (AUTHORITATIVE):** Level 0 profile submitted (= `UNVERIFIED`) · Level 1 identity verified (= `IDENTITY_VERIFIED`) · Level 2 qualifications reviewed (= `QUALIFICATION_REVIEWED`) · Level 3 advanced — **future, explicitly OUT OF SCOPE**.

**Entities:**
- `teacher_verifications` — one row per submission (teacher_id, verification_type, status, submitted_at, reviewed_by_user_id, reviewed_at, reviewer_note, rejection_reason, metadata JSONB). No unique constraint on (teacher, type) — multiple submissions per type are schema-legal.
- `verification_documents` — metadata rows (document_type TEXT free-form, storage_key UNIQUE, sha256_hash, mime, size, encrypted, status). **No content/blob storage exists in the schema** — DEV stores metadata with a synthetic storage key only (API §8.4: "API stores metadata and storage key only").
- `teacher_profiles.verification_status` — the public trust signal (currently always `UNVERIFIED`).

**What is NOT specified anywhere (hence the decisions in §12):** the exact mapping from per-type verification results to `teacher_profiles.verification_status`; the verify/reject request payloads; who sets `EXPIRED`; what sets `SUSPENDED` (belongs to the user-suspension workstream — excluded here); document_type allowlists (none approved — none invented); listing/search filtering by verification (see §9).

---

# 4. Slice scope (in / out)

**IN (all AUTHORITATIVE unless noted):**
- Teacher submits verification (type + metadata + document metadata) → `teacher_verifications` row `SUBMITTED`; profile → `SUBMITTED`; event `TEACHER_VERIFICATION_SUBMITTED`
- Teacher lists own verifications (+ document metadata)
- Admin/OPS: pending list, verification detail (audited), verify (approve), reject (with reason); events `TEACHER_VERIFIED` / `TEACHER_REJECTED` + `ADMIN_ACTION`
- Profile `verification_status` updated per the approved mapping decision (V1/V2)
- Trust-profile response gains the approved per-type booleans `identity.verified` / `qualifications.verified` (additive; V4)
- DEV consoles: teacher verification submission/status (CP-T-03), admin queue + detail (CP-A-02/CP-A-03)
- Idempotency on submission (V5), row-lock concurrency on verify/reject, full audit

**OUT (explicit, with basis):**
- Automatic/AI/KYC/provider verification — no approved spec; API §8.4 is admin-review-based; PRD Level 3 = future
- New document types, KYC requirements, legal requirements, trust scores, ranking logic — none approved (explicitly not invented)
- Real document upload/storage — no storage exists in schema; DEV = metadata + synthetic storage key (API §8.4 rule)
- `EXPIRED` mechanics — no approved trigger/owner (UNKNOWN; the enum value stays unused)
- `SUSPENDED` transitions — user-suspension workstream (R10), not approved for VS7
- Search/listing **filtering** by verification or `listing_status` — no approved DEV rule; `TEACHER_PUBLIC_LISTING_ENABLED` is staging/prod (default false pre-pilot); search continues to **expose** `verification_status` only (INFERRED boundary, §9)
- `listing_status` management (DRAFT→LISTED etc.) — no approved admin workflow specified; unchanged
- Notifications on verification — Notifications workstream (R12); API §8.4 defines no notification
- `PATCH /teachers/me` gaining verification fields — API §8.1: "verification_status, listing_status … not freely editable" (already enforced; remains so)

---

# 5. API endpoints (exact — all from the approved contract, none invented)

| # | Method | URL | Roles | Request | Response | Events |
|---|---|---|---|---|---|---|
| E1 | POST | `/api/v1/teachers/verifications` | TEACHER (own) | `{"verification_type": "IDENTITY"|"QUALIFICATION"|…, "documents": [{"document_type": "<string>", "upload_token": "<synthetic DEV token>"}], "metadata": {…}}` (shape per API §8.4) + mandatory `Idempotency-Key` (V5) | 201 envelope: verification row + documents + new profile `verification_status` | `TEACHER_VERIFICATION_SUBMITTED` |
| E2 | GET | `/api/v1/teachers/verifications` | TEACHER (own) | — | 200: own verification rows (newest first) with document metadata | — |
| E3 | GET | `/api/v1/admin/teachers/pending-verification` | OPS, ADMIN (audited) | — | 200: teachers with ≥1 `SUBMITTED` verification (teacher identity + pending type(s)) | `ADMIN_ACTION` + `ADMIN_ACCESS` (admin-read pattern) |
| E4 | GET | `/api/v1/admin/teachers/:id/verifications` | OPS, ADMIN (audited) | — | 200: verification rows + document **metadata only** (no content; no storage URL exposure) | `ADMIN_ACTION` + `ADMIN_ACCESS`; `DOCUMENT_ACCESS` security event reserved for real document access (V6) |
| E5 | POST | `/api/v1/admin/teachers/:id/verify` | OPS, ADMIN (V2 policy) | `{"verification_id": "<uuid>", "reviewer_note": "<string>"}` (V1-payload decision) | 200: updated verification + profile status | `TEACHER_VERIFIED` + `ADMIN_ACTION` |
| E6 | POST | `/api/v1/admin/teachers/:id/reject` | OPS, ADMIN (V2 policy) | `{"verification_id": "<uuid>", "rejection_reason": "<non-empty string>"}` | 200: updated verification + profile status | `TEACHER_REJECTED` + `ADMIN_ACTION` |

**Error semantics (established model):** 400 `VALIDATION_ERROR` (unknown type, missing/blank reason, bad payload) · 401 `AUTH_REQUIRED` · 403 `FORBIDDEN` (role/ownership; includes teacher self-approval attempt) · 404 `RESOURCE_NOT_FOUND` (unknown teacher/verification) · 422 `INVALID_STATE_TRANSITION` + `details.current_status` (verify/reject on an already-reviewed or EXPIRED row) · 400 `IDEMPOTENCY_KEY_REQUIRED` / 409 `IDEMPOTENCY_KEY_CONFLICT` (E1, per established mechanism).

**Authorization matrix (exact):**

| Endpoint | Teacher | Parent | Student* | Support | OPS | Admin | Anonymous |
|---|---|---|---|---|---|---|---|
| E1 submit | **201 (own)** | 403 | 403 | 403 | 403 | 403 | 401 |
| E2 own list | **200 (own)** | 403 | 403 | 403 | 403 | 403 | 401 |
| E3 pending list | 403 | 403 | 403 | 403 | **200 (audited)** | **200 (audited)** | 401 |
| E4 detail | 403 (own via E2) | 403 | 403 | 403 | **200 (audited, metadata-limited)** | **200 (audited, full metadata)** | 401 |
| E5 verify | 403 (no self-approve) | 403 | 403 | 403 | **200** (V2) | **200** | 401 |
| E6 reject | 403 | 403 | 403 | 403 | **200** (V2) | **200** | 401 |

\* No `STUDENT` role exists in the `role_name` enum — students act through parent accounts; parent-account access is 403 on all verification admin/teacher endpoints (as shown).

Data-access nuance per Security Plan §6 matrix: OPS = "audited limited", Admin = "audited full" (metadata-only in DEV both; the limited/full distinction activates with real document storage — V6).

---

# 6. State transitions (approved lifecycle, exactly)

```text
teacher_verifications.status:   SUBMITTED (default on create)
                                  → APPROVED  (E5; reviewed_by/at, reviewer_note set)
                                  → REJECTED  (E6; reviewed_by/at, rejection_reason set)
                                  → EXPIRED   (no approved mechanic — UNIMPLEMENTED, value unused)
  Re-submission after REJECTED: new row (schema-legal; no approved unique constraint —
  no duplicate rule invented). A teacher may hold multiple rows (one per submission).

teacher_profiles.verification_status (mapping = REQUIRES APPROVAL V1/V2, recommended):
  submission of any type            → SUBMITTED (from UNVERIFIED/REJECTED)
  IDENTITY APPROVED                 → IDENTITY_VERIFIED (unless already QUALIFICATION_REVIEWED)
  QUALIFICATION APPROVED            → QUALIFICATION_REVIEWED
  REJECTED with no other APPROVED   → REJECTED
  REJECTED with a higher APPROVED   → keep the higher level (no demotion)
  SUSPENDED                         → NOT TOUCHED in VS7 (R10 workstream)
  EXPERIENCE / BACKGROUND_CHECK     → tracked as rows only, no profile-level change (V3)
```

Consequences: "Parents can distinguish verified vs unverified claims" (PRD acceptance) is satisfied by `verification_status` (already exposed in profile/search/trust-profile) plus the new per-type booleans.

---

# 7. Idempotency / concurrency

- **E1 submission:** `Idempotency-Key` mandatory (V5 — recommended; basis: SM §3.6 "idempotency is mandatory for retryable commands" + VS4/VS5/VS6 convention). Scope `verification_submit`, canonical hash over `{verification_type, documents, metadata}`; replay returns stored response; conflict → 409. **No duplicate-submission business rule is invented** (none approved): distinct submissions create distinct rows.
- **E5/E6:** `SELECT verification … FOR UPDATE` (row lock) → re-read status after lock → transition only from `SUBMITTED`, else 422 with `current_status`. Two concurrent reviewers: exactly one winner; the other gets 422.
- **No DB uniqueness constraint is added** (none approved; schema unchanged).

---

# 8. Service layer design (new VS7 section in `services.py`)

```text
verification_transitions (module constant, mirrors §6)
submit_verification(teacher_user_id, data, idempotency_key, request_id)
  - role check (view gate) + own-profile lookup
  - validate verification_type in enum; documents: list of {document_type non-empty string,
    upload_token non-empty string} (DEV synthetic; no content); metadata: JSON object
  - idempotency begin → tx:
      INSERT teacher_verifications (status SUBMITTED) + verification_documents rows
      (storage_key = synthetic 'dev-synthetic-<uuid>' — UNIQUE-safe)
      UPDATE teacher_profiles SET verification_status per V1 mapping (if upgrading)
      write_event TEACHER_VERIFICATION_SUBMITTED
      idempotency complete (201)
list_verifications_for_teacher(user_id)
  - own rows (newest first) + document metadata; profile status
list_pending_verifications(actor_user_id, roles, request_id)
  - audited; teachers with ≥1 SUBMITTED row (teacher identity + pending types + counts)
get_verifications_for_admin(actor_user_id, roles, teacher_id, request_id)
  - audited; 404 unknown teacher; rows + document metadata (metadata only, V6)
review_verification(actor_user_id, roles, teacher_id, verification_id, decision, reason, request_id)
  - decision = APPROVED|REJECTED (E5/E6 share the core; reason required for REJECTED,
    optional note for APPROVED)
  - tx: row FOR UPDATE → status must be SUBMITTED (else 422 current_status)
    → UPDATE status/reviewed_by/at/reviewer_note|rejection_reason
    → UPDATE teacher_profiles.verification_status per V1/V2 mapping
    → write_event TEACHER_VERIFIED | TEACHER_REJECTED + ADMIN_ACTION
```

Trust-profile additive alignment (V4): `teacher_public_profile` gains `identity_verified` + `qualifications_verified` booleans (derived: latest `APPROVED` row per type exists) — existing fields (`verification_status`, metrics, etc.) retained unchanged (backward compatible; aligns implementation with the approved §8.5/PRD §8.4 shape without removing anything).

---

# 9. Visibility behavior (exactly what changes / does not)

- **Trust profile:** adds per-type booleans (V4). Metric fields remain worker-derived (currently default/zero — unchanged; metrics worker is R16, out of scope).
- **Search:** **unchanged** — continues to expose `verification_status`; **no filtering added** (no approved DEV listing rule; `TEACHER_PUBLIC_LISTING_ENABLED` is staging/prod, default false pre-pilot, and "cannot show unverified/suspended teacher as listed" activates with that flag at pilot — flagged here as a pilot-readiness note, not a VS7 change). `INFERRED` boundary, documented.
- **Public teacher profile:** `verification_status` already exposed — unchanged.
- **Documents:** never exposed publicly; teacher sees own metadata (E2); admin/OPS audited metadata view (E4); no storage URLs/content anywhere (schema has no content column; `DOCUMENT_ACCESS_ENABLED` remains staging/prod-scoped).

---

# 10. Frontend DEV scope (consoles per CP-T-03 / CP-A-02 / CP-A-03)

- **Teacher page** — "Verification" section: type select (`IDENTITY`, `QUALIFICATION` — the two PRD MVP levels; EXPERIENCE/BACKGROUND_CHECK selectable per V3 if approved), metadata fields matching the API §8.4 example (`institution`, `graduation_year` for QUALIFICATION; generic key-value otherwise — no fixed KYC fields invented), document add (type + synthetic upload token placeholder), submit (auto `Idempotency-Key: verif-<uuid>`), own verifications list with status badges.
- **Admin page** — "Verification Queue" section: pending list (teacher, type(s), submitted_at), detail (verification rows + document metadata + teacher profile), verify (note) / reject (reason, required) actions, outcome line, audit note ("All actions are logged").
- No production UI; no new dependencies; parent page unchanged.

---

# 11. Test plan (exact; new file `tests/test_vertical_slice_7.py`)

| # | Test | Asserts |
|---|---|---|
| 1 | `test_verification_submission_identity` | 201; row SUBMITTED; profile → SUBMITTED; `TEACHER_VERIFICATION_SUBMITTED` event; documents stored with synthetic storage_key |
| 2 | `test_verification_submission_qualification_metadata` | metadata JSON round-trip (institution/graduation_year per §8.4 example); no content fields exist/leaked |
| 3 | `test_verification_list_own` | own rows newest-first with document metadata; other teacher's rows absent |
| 4 | `test_submission_denied_for_non_teacher` | parent 403; anonymous 401; (teacher self-path works) |
| 5 | `test_verify_approves_identity` | OPS verify → row APPROVED (reviewed_by/at set, note stored); profile → IDENTITY_VERIFIED; `TEACHER_VERIFIED` + `ADMIN_ACTION` events |
| 6 | `test_verify_approves_qualification` | profile → QUALIFICATION_REVIEWED |
| 7 | `test_reject_sets_rejection` | row REJECTED + rejection_reason; profile → REJECTED (no other approved); `TEACHER_REJECTED` + `ADMIN_ACTION` |
| 8 | `test_reject_does_not_demote_approved_higher_level` | IDENTITY approved → submit QUALIFICATION → reject it → profile stays IDENTITY_VERIFIED (V2) |
| 9 | `test_invalid_transitions` | verify on APPROVED → 422 + current_status; reject on REJECTED → 422; verify unknown verification → 404; reject on unknown teacher → 404 |
| 10 | `test_admin_authorization_matrix` | parent/teacher/support/anonymous → 403/401 on E3–E6; OPS + ADMIN allowed; **teacher cannot self-approve** (403 on admin endpoints) |
| 11 | `test_admin_views_audited` | E3/E4 → `ADMIN_ACTION` + `ADMIN_ACCESS` security events; metadata-only payload (no content/URL fields) |
| 12 | `test_trust_profile_per_type_booleans` | UNVERIFIED → both false; after IDENTITY → identity true/qual false; after QUALIFICATION → both true (V4) |
| 13 | `test_trust_profile_backward_compatible` | pre-existing fields (verification_status, listing_status, metrics, subjects, slots) unchanged in shape |
| 14 | `test_search_exposes_status_no_filter_change` | unverified teacher still appears in search with `verification_status=UNVERIFIED`; verified teacher shows updated status (no filtering behavior invented) |
| 15 | `test_idempotency_replay_conflict_missing_key` | same key+payload → same row (1 row); same key different payload → 409 `IDEMPOTENCY_KEY_CONFLICT`; missing key → 400 `IDEMPOTENCY_KEY_REQUIRED` (V5) |
| 16 | `test_concurrent_verify_reject_one_wins` | parallel verify+reject on one SUBMITTED row → one 200 + one 422; final state exactly APPROVED or REJECTED; single reviewer fields |
| 17 | `test_resubmission_after_rejection_allowed` | new row after rejection (schema-legal; no invented duplicate block); profile mapping per V1/V2 |
| 18 | `test_regression_full_suite` | all 98 pre-existing tests green in the same run |

Target: **≥ 17 new tests; total ≥ 115 passing** (final count may exceed).

---

# 12. E2E plan (isolated PostgreSQL 16.2 + full v1→v1.4 chain + Django + Next.js)

```text
E2E_MAIN:  teacher register/login → submit IDENTITY (metadata + 1 synthetic document)
           → own list shows SUBMITTED → admin pending list shows teacher →
           admin detail (audited, metadata only) → verify → profile IDENTITY_VERIFIED →
           trust-profile identity.verified=true → search row shows IDENTITY_VERIFIED →
           submit QUALIFICATION → verify → QUALIFICATION_REVIEWED →
           trust-profile qualifications.verified=true
E2E_REJECT: second teacher submits → reject with reason → row REJECTED + reason visible
            in own list; profile REJECTED (no approved level)
E2E_UNAUTHORIZED: parent/teacher/anonymous attempts on E3–E6 → 401/403 (incl. self-approve)
E2E_INVALID: double-verify (second 422 + current_status); verify unknown → 404
E2E_IDEMPOTENCY: same key+payload resubmit → same row; key reuse different payload → 409
E2E_CONCURRENCY: parallel verify + reject → one 200 + one 422, single final state
E2E_AUDIT: /admin/events contains TEACHER_VERIFICATION_SUBMITTED, TEACHER_VERIFIED,
           TEACHER_REJECTED, ADMIN_ACTION; security-events count grew (ADMIN_ACCESS)
E2E_FRONTEND: /teacher + /admin → 200 with verification console markers
Expected: all eight groups PASS
```

---

# 13. Dependency & production implications

- **No new dependencies** (npm/pip) — console reuses the existing stack; `requirements.txt`/`package.json`/`package-lock.json` untouched.
- **No feature flags introduced or altered** in DEV. `DOCUMENT_ACCESS_ENABLED` and `TEACHER_PUBLIC_LISTING_ENABLED` remain staging/prod-scoped per Feature Flag Governance. **Pilot implications (documented, not implemented):** at pilot, (a) real document access must be audited per Security Plan §6 with the flag gate, and (b) the listing policy ("cannot show unverified/suspended teacher as listed") activates via `TEACHER_PUBLIC_LISTING_ENABLED` — search filtering would then be a separate approved work item.
- **Production implications:** verification is a PRD P0 trust prerequisite for pilot credibility; no provider/KYC integration is implied by any approved document (admin-review based); legal requirements: none in repository (none invented).
- **Dependency on other workstreams:** none (standalone, per audit ranking).

---

# 14. Rollback / safety

- Additive-only change set: 6 new routes, one VS7 service section, additive trust-profile fields, console UI, test file, reports. No existing function/route/schema object modified (trust-profile field set is extended, never shrunk).
- No schema/migration/state-machine changes → rollback = revert the single VS7 commit; no data migration to reverse.
- No money, no providers, no external calls; document rows are metadata with synthetic keys (no real storage referenced); audit events append-only.

---

# 15. Trust-objective alignment (PRD comparison)

The PRD core hypothesis is that parents "repeatedly book and complete paid tutoring sessions **with verified teachers**" and §8.4 defines the Trust Profile as "a data product, not a decorative profile section." Before VS7, `verification_status` was structurally frozen at `UNVERIFIED` (registration default, no write path) — the platform's central trust signal was non-functional. After VS7: (1) the full approved verification loop (submit → admin review → approve/reject) operates and is **auditable** (PRD acceptance: "Admin approval/rejection is auditable" — events + security events per decision); (2) **parents can distinguish verified vs unverified** (PRD acceptance — status in search/profile/trust-profile + per-type booleans); (3) **document access is restricted** (PRD acceptance — metadata-only, audited admin/OPS flow per Security Plan §6, no public exposure). Level 3 (advanced verification) remains explicitly future per the PRD.

---

# 16. Remaining decisions — every UNKNOWN / REQUIRES APPROVAL item (none silently resolved)

| ID | Decision | Class | Recommended default (for approval, not assumed) |
|---|---|---|---|
| V1 | Profile `verification_status` mapping rules (submit→SUBMITTED; IDENTITY approved→IDENTITY_VERIFIED; QUALIFICATION approved→QUALIFICATION_REVIEWED; reject with no other approved→REJECTED) | REQUIRES APPROVAL (INFERRED from PRD levels + enum) | as recommended |
| V2 | Rejection of a type while a higher level is APPROVED → keep the higher level (no demotion) | REQUIRES APPROVAL (INFERRED) | as recommended |
| V3 | EXPERIENCE / BACKGROUND_CHECK submissions in DEV: accepted as `teacher_verifications` rows with **no** profile-level mapping (no approved level exists for them) — vs restricting submission to IDENTITY/QUALIFICATION only | REQUIRES APPROVAL (INFERRED; no approved rule covers these types' profile effect) | accept-as-rows (schema-legal, no invented level) |
| V4 | Trust-profile additive per-type booleans (`identity_verified`/`qualifications_verified`), existing fields retained | REQUIRES APPROVAL (INFERRED from API §8.5 + PRD §8.4 shape) | as recommended |
| V5 | `Idempotency-Key` mandatory on `POST /teachers/verifications` | REQUIRES APPROVAL (INFERRED from SM §3.6 + VS4–VS6 convention) | mandatory |
| V6 | DEV document-access scoping: admin/OPS metadata view audited via `ADMIN_ACTION` + `ADMIN_ACCESS`; `DOCUMENT_ACCESS` security event reserved for real document storage (staging, `DOCUMENT_ACCESS_ENABLED`) | REQUIRES APPROVAL (INFERRED from Security Plan §6) | as recommended |
| U1 | `EXPIRED` status mechanics (who/when) | UNKNOWN — no approved mechanic | not implemented in VS7 (enum value stays unused) |
| U2 | `SUSPENDED` profile-status transitions | UNKNOWN for this slice — belongs to user-suspension workstream (R10) | excluded |
| U3 | document_type allowlist | UNKNOWN — no approved list exists | none invented; free-form non-empty string stored as metadata (API §8.4 stores metadata only) |
| U4 | Search/listing filtering by verification at DEV | UNKNOWN — no approved DEV rule; listing flag is staging/prod | no filtering in VS7 (exposure only); pilot note documented (§9) |

---

# 17. Schema change assessment (required check)

**SCHEMA_CHANGE_REQUIRED: NO**

Every object the slice needs already exists in the approved v1→v1.4 chain (live-verified): `teacher_profiles.verification_status` (+6-value enum), `teacher_verifications` (full column set incl. reviewer/note/reason/metadata), `verification_documents` (metadata columns + `storage_key UNIQUE`), `verification_type`/`verification_review_status`/`document_status` enums, `TEACHER_VERIFICATION_SUBMITTED`/`TEACHER_VERIFIED`/`TEACHER_REJECTED`/`ADMIN_ACTION` events, `DOCUMENT_ACCESS` security event. No new table, column, enum value, constraint, trigger, or event type is needed; no approved requirement forces a schema change. Contingency (governance envelope): if implementation discovers a genuine blocker, STOP and report `SCHEMA_CHANGE_REQUIRED: YES` with the exact reason before applying anything.

---

# 18. Definition of Done (VS7)

```text
- 6 approved endpoints implemented exactly (no invented endpoints/paths)
- Submission → SUBMITTED row + documents (metadata, synthetic keys) + profile mapping (V1)
- Verify/reject transitions only from SUBMITTED; 422 + current_status otherwise; row-locked
- Profile mapping incl. no-demotion rule (V2); EXPERIENCE/BACKGROUND_CHECK per V3
- Self-approval impossible (403); full authorization matrix enforced
- Trust-profile per-type booleans additive (V4); existing response fields intact
- Search unchanged (exposure only); no listing filtering invented
- Idempotency on submission (V5): replay/conflict/missing-key semantics
- Audit: TEACHER_VERIFICATION_SUBMITTED / TEACHER_VERIFIED / TEACHER_REJECTED +
  ADMIN_ACTION on every admin action; ADMIN_ACCESS on admin reads (V6 scoping)
- Documents: metadata-only everywhere; no content/URL exposure; restricted access
- Frontend DEV consoles (teacher submission/status; admin queue/detail) building
- ≥ 17 new tests + all 98 pre-existing tests green (total ≥ 115)
- E2E: all 8 scenario groups PASS on isolated PG with unmodified v1→v1.4 chain
- Dependency audit re-run without --force; no new dependencies
- No schema/state-machine/architecture changes; v1.2 provenance intact
- Reports: implementation / test / E2E + Dependency Audit v1.6 + README section
- VS8 NOT started
```

# 19. Deliverables (post-implementation)

```text
EduTrust_DEV_Vertical_Slice_7_Implementation_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_7_Test_Report_v1.0.md
EduTrust_DEV_Vertical_Slice_7_E2E_Report_v1.0.md
EduTrust_DEV_Dependency_Audit_v1.6.md
README.md (VS7 section + test count)
```

---

# 20. Formal gate

```text
VS7_SCOPE_APPROVED: YES
VS7_IMPLEMENTATION_STARTED: NO
DATABASE_MODIFIED: NO
ARCHITECTURE_MODIFIED: NO
API_MODIFIED: NO
STATE_MACHINE_MODIFIED: NO
COMMIT_CREATED: NO
PUSH_PERFORMED: NO
```

**STOP after the plan.** Implementation begins only on explicit authorization (with V1–V6 confirmations).
