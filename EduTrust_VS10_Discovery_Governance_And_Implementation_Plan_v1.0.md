# EduTrust — VS10 Discovery, Governance & Implementation Plan v1.0

**Document type:** READ-ONLY discovery + governance audit + implementation plan for the next vertical slice (VS10). No implementation performed; no code, tests, migrations, frontend, dependencies, README, or prior documents modified. No commit, no push.
**Audited state (verified 2026-08-25):** `Anwarefahmi22/EduTrust` @ branch `arena/01a03280-edutrust` @ HEAD `af8f8185911af871fb1832e02fe9e5588bf228c0` (VS9) — local = remote.
**Authorities used:** repository documents only (PRD v1.0, API Architecture v1.0, API Contract Addendum v1.1, State Machines v1.0 + v1.1 Addendum, schema/migrations v1→v1.4, Implementation Baseline, Engineering Governance, Security/Privacy Plan, Feature Flag Governance, Product/Ops Policy Decisions, Payment Provider Readiness/Gate, Planning, Test Traceability Matrix, UX/visual specs, VS1–VS9 plans/reports, dependency audits v1.2–v1.8, Post-VS4/Post-VS6/Post-VS8 audits, VS8/VS9 scope audits) + verified code/schema state.
**Classification legend:** `AUTHORITATIVE` · `INFERRED` · `UNKNOWN` · `CONTRACT GAP` · `HISTORICAL` · `OUT OF SCOPE`

---

# A. Executive summary

VS9 (Dispute Resolution CORE) is complete, committed, and protected on the remote (`af8f818`, parent `b73d8ce`); VS1–VS8 remain intact; `main` untouched. This audit discovered and investigated **all documented next-slice candidates** repository-wide (Post-VS6 proposed sequence, Post-VS8 current roadmap, VS9 plan X11 deferrals, API/SM/PRD/UX/OPS sources) and deep-dived the six candidates the task names: **R10 (user suspend/reactivate), R11 (ledger administration), R4 (cancellation), R7 (student passport/completion), R6 (auth completion)**, plus the remaining documented fill-ins (R5, R8/R9, R12, R13, R14, R15/R16; N1 is contract-blocked).

Headline findings:

1. **R10 is NOT scope-ready.** The endpoint contract is APPROVED but thin (API §21.6: two ADMIN-only endpoints, "insert ADMIN_ACTION"); **no document specifies any operational effect of suspension** — no user-status state machine exists in SM v1.0 or the Addendum; SM §11.5 has no effects row for `ACCOUNT_SUSPENDED`; PRD states only that account status "can be active, suspended, or deleted". Verified code facts: login already rejects non-`ACTIVE` users (indistinguishable 401 `AUTH_INVALID_CREDENTIALS`); JWTs are bound to `auth_sessions` rows and checked per request (a revocation mechanism exists but nothing sets it on suspension); **no** booking/payout/refund/dispute/visibility path checks `users.status`. Everything beyond login is `UNKNOWN` — preserved as such, not invented.
2. **R11 is NOT scope-ready.** API §14.5 endpoints are explicitly **"Suggested"** (not approved contract); the reversal operation has no request/response contract, no authorized reversal semantics (which statuses are reversible; DRAFT-only vs offsetting ADJUSTMENT tx for POSTED), no OPS policy, and no dedicated event type. The schema is ready (ADJUSTMENT transaction/account types exist; ledger entries are DB-immutable; balance is a deferred constraint; PAID payouts are immutable with the trigger message directing corrections to "a separate adjustment/recovery transaction"). Addendum §9 constrains adjustment creation to approved services, not manual UI.
3. **R4 (cancellation) is PARTIALLY ready.** `POST /bookings/:id/cancel` is an APPROVED contract (§11.6: actors, request `{reason, requested_refund}`, rules, `BOOKING_CANCELLED` event) and the transitions exist (SM §6.3: HELD/PAYMENT_PENDING/BOOKED → CANCELLED), but the **cancellation deadline is unspecified (no OPS policy exists for it)**, the paid-path consequence ("may create refund eligibility or dispute") is deliberately ambiguous, and teacher-policy/session-cascade/slot-release mechanics are plan-time decisions. The pre-payment path is small and nearly standalone; the paid path now has its refund dependency (VS8) satisfied.
4. **R6 (auth completion) is scope-ready** and is the strongest VS10 candidate: `POST /auth/refresh` (§3.5: verify hash → rotate → store new hash → revoke old in the same transaction; replay → revoke + `SECURITY_EVENT`) and `POST /auth/revoke-sessions` (§3.7: current / all other / all) are APPROVED contracts; the supporting schema (`auth_sessions.refresh_token_hash` UNIQUE, `revoked_at`, `expires_at`), security events (`TOKEN_REVOKED`, `SUSPICIOUS_ACTIVITY`), rate-limit scope (§27.1 explicitly lists "Refresh token"), and hardening requirements (§27.2: hash-only storage, rotation, revoke-on-suspicious-replay) all already exist; zero financial effect; zero schema change. The prior "decision-free" classification is **slightly stale**: three small plan-time contract locks are needed (refresh request/response shape, revoke-sessions request shape, replay/"session family" semantics) — none is a governance decision, none blocks.
5. **R7 (student passport + completion) is scope-ready** (second-ranked): passport v0 response is fully specified (§7.4, read-only aggregation over existing VS3 data, "No AI-generated claims in MVP"), permissions contract + table exist (§7.5), ownership rule is §7.2.

**Recommendation (evidence-based, Phase U):** TOP_VS10 = **R6 Auth completion** · SECOND = **R7 Student Passport/Student completion** · THIRD = **R4 Cancellation** (with its plan-time decision set). R10 and R11 remain documented candidates but are **not** scope-ready (spec/contract gaps preserved as UNKNOWN — no behavior invented).

**Nothing was implemented, modified, committed, or pushed.** The only artifact created by this task is this document.

---

# B. Current Git state (verified read-only, 2026-08-25)

| Check | Result |
|---|---|
| Branch | `arena/01a03280-edutrust` |
| Local HEAD | `af8f8185911af871fb1832e02fe9e5588bf228c0` (VS9) |
| Remote `arena/01a03280-edutrust` | `af8f8185911af871fb1832e02fe9e5588bf228c0` — **matches local; VS9 protected** |
| Remote `main` (= `origin/HEAD`) | `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` — unchanged |
| VS9 parent | `b73d8cec22779bed222727eae10107a951ecdee8` (VS8) — verified `HEAD^` |
| Working tree | CLEAN (0 modified, 0 untracked) |

Ancestry (verified `git log`): `45dc020` (Initial) → `b245aae` (migrate/VS1–3) → `83c7bc5` (restore VS4+VS5) → `e0e3d89` (VS6) → `157a54d` (VS7) → `b73d8ce` (VS8) → `af8f818` (VS9).

# C. VS1–VS9 status

| Slice | Commit | Evidence (historical, verified in prior audits) | Status |
|---|---|---|---|
| VS1 core flows | `b245aae` | 10 tests; runtime E2E PASS (report-only) | COMPLETE |
| VS2 payment lifecycle | `b245aae` | 17 tests; 4 E2E scenarios (report-only) | COMPLETE |
| VS3 sessions/reports | `b245aae` | 26 tests; 7 E2E scenarios (report-only) | COMPLETE |
| VS4 reviews/disputes foundation | `83c7bc5` | 54 tests; 49/49 E2E (report-only) | COMPLETE |
| VS5 payouts | `83c7bc5` | 83 tests; 29/29 E2E (report-only) | COMPLETE |
| VS6 review moderation | `e0e3d89` | 98 tests; 32/32 E2E (report-only) | COMPLETE |
| VS7 teacher verification | `157a54d` | 118 tests; 29/29 E2E (report-only) | COMPLETE |
| VS8 refund operations | `b73d8ce` | 160 tests; 53/53 E2E (re-runnable suite); 32/32 direct-SQL | COMPLETE |
| VS9 dispute resolution (CORE) | `af8f818` | 197 tests (160+37); 75/75 E2E; 30/30 direct-SQL; §30 gate RATIFIED (recorded) | COMPLETE (pushed/protected) |

Suite growth is cumulative and consistent (10→17→26→54→83→98→118→160→197).

# D. Candidate inventory (Phase 1 — repository-wide discovery)

Search performed across all roadmap documents, implementation baseline, PRD, API architecture, state machines + addendum, UX documents, traceability matrix, OPS policies, feature-flag governance, dependency audits, VS reports, post-slice audits, and README. Explicit "VS10" mentions found: Post-VS6 proposed sequence (line 173: "VS10 Booking lifecycle completion: Cancellation (R4) + Reschedule (R5) + Report edit (R14)" — PROPOSED, never approved) and VS9 plan X11 ("VS10+ work (cancellation/reschedule, R10, R11, etc.) — Out of slice").

| # | Candidate | Source(s) | Exact documented requirement | Current status | Dependencies | Unknowns | Risk | Scope readiness |
|---|---|---|---|---|---|---|---|---|
| A | **R10 User suspend/reactivate** | API §21.6 (ADMIN-only `POST /admin/users/:id/suspend`, `/reactivate` + "Every admin operation … insert ADMIN_ACTION"); API role matrix (ADMIN only); PRD §8.1 ("Parent account status can be active, suspended, or deleted"); schema `user_status` ('PENDING','ACTIVE','SUSPENDED','DELETED') + `users.status`; SM §11.4 action names; A-63 wireframe (purpose/CTAs/events "ADMIN_ACTION, possibly SECURITY_EVENT"/idempotency "recommended"/reason required); Security/Privacy Plan ("must audit: admin user suspension"); Feature Flag Governance (listing fallback: "Cannot show unverified/suspended teacher as listed") | NOT IMPLEMENTED; endpoint contract APPROVED-thin; operational effects **UNKNOWN** (no state machine, no effects spec) | approved operational-effect spec (missing); dispute `ACCOUNT_SUSPENDED*` actions (VS9-deferred P6) | ~15 (see §F: token/booking/payout/refund/dispute/visibility/reactivation/concurrency effects) | H (account lifecycle + financial ripple) | **NO** |
| B | **R11 Ledger administration** | API §14.5 **Suggested** endpoints (`GET /admin/ledger/transactions` OPS/ADMIN; `GET /admin/ledger/transactions/:id` OPS/ADMIN; `POST /admin/ledger/reversals` ADMIN "Create reversal with reason"; "All admin ledger access/actions are audited"); Addendum §9 (adjustment creation = controlled side effect of approved services, not manual UI); schema ADJUSTMENT tx/account types + immutability triggers | NOT IMPLEMENTED; no service has ever written an ADJUSTMENT tx; contract SUGGESTED (not approved); reversal semantics unspecified | approved reversal contract + OPS/accounting policy + financial-workflow approval | which statuses reversible (DRAFT/POSTED/VOIDED); period locking; dedicated event type; manual-journal authorization | M-H (direct financial mutation) | **NO** |
| C | **R4 Cancellation** (+R5 reschedule) | API §11.6 (actors: PARENT own-before-deadline / TEACHER own-under-policy / OPS/ADMIN override-with-reason; request `{reason, requested_refund}`; rules: no COMPLETED, "If payment confirmed, cancellation may create refund eligibility or dispute", reason+actor stored, event ledger required); SM §6.3 (HELD/PAYMENT_PENDING/BOOKED → CANCELLED); `BOOKING_CANCELLED` event; API §11.7 reschedule (endpoint + events; rules "under rules" — not itemized) | NOT IMPLEMENTED; pre-payment path nearly standalone; paid path couples to VS8 refund (now available) | cancellation-deadline policy (no OPS policy exists); requested_refund trigger semantics; teacher policy; session cascade; slot release | 4–5 (plan-time) | M | **PARTIAL** |
| D | **R7 Student Passport + Student completion** | API §7.4 (passport v0 response fully specified; sources: sessions/session_reports/student_progress_events; "No AI-generated claims are returned in MVP"); §7.1 list/PATCH/DELETE (events STUDENT_PROFILE_*); §7.5 permissions (grant/revoke, scope SESSION_CONTEXT, granted_for_booking_id); §7.2 ownership rule; schema `student_permissions` (exists) | NOT IMPLEMENTED; passport = read-only aggregation over existing VS3 data | none blocking | 0–1 (list shape; DELETE archive-vs-delete nuance) | L (privacy-sensitive, minimized by design) | **YES** |
| E | **R6 Auth completion** | API §3.5 refresh (verify hash vs active session; rotate; store new hash; revoke old in same tx; replay → revoke session family "where supported" + `SECURITY_EVENT`); §3.7 revoke-sessions (current / all other / all); §27.1 rate limiting explicitly includes "Refresh token"; §27.2 hardening (hash-only, rotate, revoke on suspicious replay); schema `auth_sessions` (refresh_token_hash UNIQUE, revoked_at, expires_at); existing events TOKEN_REVOKED/SUSPICIOUS_ACTIVITY | NOT IMPLEMENTED (endpoints absent; login already issues+stores refresh tokens; logout revokes via `revoked_at`) | none | 0 governance; 3 plan-time contract locks (D1–D3, §V) | L | **YES** |
| F1 | R8/R9 Parent/Teacher completion | API §6.2–6.3 (parent profile read/update + dashboard), §8.1–8.4 (subject PATCH/DELETE, availability rules CRUD); schema `availability_rules` (exists) | NOT IMPLEMENTED | none | 1–2 small locks | L-M | YES (small) |
| F2 | R12 Notifications (in-app core) | API §20 (in-app source of truth); schema notifications + enums (exist); OPS-POL-009 channels **OPEN** | NOT IMPLEMENTED | channel policy OPEN (in-app core does not need it) | 1 (channel policy — deferrable) | L-M | PARTIAL (in-app core) |
| F3 | R13 Admin monitoring completion | API §21.3 (`GET /admin/bookings`), §21.5 (redacted `GET /admin/payments/:id`) | NOT IMPLEMENTED | none | 0 | L | YES (small) |
| F4 | R14 Report editing | API catalogue ("edit report under policy") — policy not itemized | NOT IMPLEMENTED | edit policy unspecified | 1–2 | L-M | PARTIAL |
| F5 | R15/R16 Background jobs + trust-metrics worker | Planning §11 (8 jobs); worker spec partly INFERRED | NOT IMPLEMENTED | worker spec detail at plan time | several (INFERRED) | M | PARTIAL |
| F6 | R20/R21/R22 (OpenAPI condition, CI/deploy, monitoring baseline) | Baseline §3; Gate; Security/Privacy Plan | NOT IMPLEMENTED; R21/R22 BLOCKED on spec decisions | spec decisions first | — | — | Not slice candidates |
| F7 | N1 Refund follow-up partials | VS8 plan O7 (DB trigger permits; §12.6 creation contract does not) | **BLOCKED** on Addendum contract patch | contract amendment approval | — | M | BLOCKED |
| F8 | R17 Production UI / R18/R19 real money | 64-screen approved baseline; Payment Provider Gate | R17 = PHASE (not a slice); R18/R19 OUT OF SCOPE (gates NOT APPROVED) | — | — | — | Excluded |

No candidate was invented; every row traces to a cited document. N1 and R17–R19 are listed for completeness, not as VS10 candidates.

# E. Authority hierarchy (Phase 2)

Per Implementation Baseline v1.0 (document statuses) + SM v1.1 Addendum §2 conflict order: **Addendum v1.1 > Schema v1.1 > SM v1.0 > API Architecture v1.0 > DB Schema v1.0 > PRD v1.0**. Roadmap precedence: **Post-VS8 Final Audit & Roadmap v1.0 is the current roadmap** (explicitly supersedes Post-VS6 roadmap sections); Post-VS6/Post-VS4 sequences are HISTORICAL proposals (never approved); VS8/VS9 scope audits are historical point-in-time records. UX documents (wireframes/HF/flows) are APPROVED for UI behavior but do not create API/SM/ledger obligations. OPS policies (10, all OPEN) are READY FOR REVIEW — their OPEN status means "unset behavior preserved", not "choose a default".

Contradictions touching VS10 candidates, classified (none silently reconciled):

| # | Tension | Documents | Classification |
|---|---|---|---|
| C1 | `ACCOUNT_SUSPENDED` listed as an allowed dispute action (SM §11.4) but no effects specified (§11.5 has no row) and no suspension capability spec anywhere | SM v1.0 vs (absence) | **OPEN** — VS9 deferred it (P6); remains the gating gap for R10 |
| C2 | API §14.5 "Suggested endpoints" (incl. manual `POST /admin/ledger/reversals`) vs Addendum §9 "Recovery/adjustment creation is a controlled side effect of approved … services, not a manual UI command" | API v1.0 (suggestion) vs Addendum v1.1 (constraint) | **OPEN** — by precedence the Addendum constrains: any reversal implementation must be an audited approved *service* (ADMIN-only, reason, audited), not a free-form manual journal UI; the "suggested" authority level still requires approval before implementation |
| C3 | "VS10 = R4+R5+R14" (Post-VS6 line 173) vs Post-VS8 roadmap ranking (auth/passport ahead of cancellation) | Post-VS6 (HISTORICAL proposal) vs Post-VS8 (current roadmap) | **RESOLVED by precedence** — Post-VS6 sequence was PROPOSED, never approved; Post-VS8 audit governs sequencing |
| C4 | PRD "Parent account status can be active, suspended, or deleted" vs schema `user_status` = PENDING/ACTIVE/SUSPENDED/DELETED (parent + all users) | PRD vs schema v1 | **RESOLVED by precedence** — schema v1 is the implementation of record; PRD statement is consistent (subset for parents), not contradictory |
| C5 | A-63 "Idempotency requirement: Recommended" vs repo convention (Idempotency-Key on state-changing POSTs — but existing logout is NOT idempotency-keyed, session-bound instead) | UX spec vs convention | **OPEN (minor)** — plan-time lock for R6 follows the existing logout convention (session-bound, no key header); for R10 the "recommended" is noted but the suspension contract is unapproved anyway |
| C6 | SM §16.2 booking→DISPUTED vs Addendum §4.1 overlay (v1.1 DB CHECK forbids DISPUTED on bookings/sessions) | SM v1.0 vs Addendum v1.1 | **RESOLVED** (Addendum wins; DB-enforced; relevant to R4's DISPUTED-adjacent states) |
| C7 | API §12.6 `REFUND_ISSUED` row vs Addendum §13.2 deprecation | API v1.0 vs Addendum v1.1 | **RESOLVED** (Addendum wins; 0 rows emitted — verified) |

Point-in-time historical statements (not contradictions): VS7 report "SUSPENDED untouched (owned by the user-suspension workstream R10)"; VS8 audit D-6 (Post-VS6 sequence "PROPOSED, never approved"); VS9 plan §32 (superseded by its §33 execution addendum).

# F. R10 investigation (Phase 3 — full trace)

**Documents searched:** all `.md` (suspend/suspended/reactivate/account suspension/user status/login guards/payout-booking-refund-dispute eligibility/teacher-parent-admin visibility/token/session invalidation/hidden accounts/active-inactive). **Code traced:** `auth.py`, `services.py` (login/logout/hold/booking/payment/refund/dispute/payout/eligibility paths), schema enums + columns + triggers.

Facts established (each verified against code or cited document):

1. **`user_status` enum** ('PENDING','ACTIVE','SUSPENDED','DELETED') + `users.status` (default 'ACTIVE') exist in schema v1. No CHECK beyond the enum; no trigger touches `users.status`.
2. **No user-status state machine** exists in SM v1.0 or the Addendum (verified: zero transition spec for PENDING/ACTIVE/SUSPENDED/DELETED).
3. **Login while suspended — implemented by existing code (not documented):** `login()` selects `status` and rejects unless `status = 'ACTIVE'`, raising `AUTH_INVALID_CREDENTIALS` 401 — indistinguishable from a wrong password (no dedicated "suspended" error exists).
4. **Existing tokens while suspended — mechanism exists, nothing uses it for suspension:** JWTs carry `auth_sessions.id`; every request's auth check verifies the session row (`revoked_at IS NULL` AND `expires_at` in future) — i.e., server-side invalidation is possible per-session, but no suspension path (none exists) would set it.
5. **Refresh tokens — endpoint unimplemented (R6):** refresh tokens are issued at login and stored as `refresh_token_hash` (UNIQUE); no `/auth/refresh` endpoint exists; behavior while suspended: **UNKNOWN** (no refresh path exists to block).
6. **Booking creation — no `users.status` check anywhere in the booking path** (traced `hold_booking`): a SUSPENDED parent could hold/confirm bookings under current code. Spec: **UNKNOWN** (not specified to be blocked or allowed).
7. **Booking participation / sessions** — no user-status check in session start/complete/no-show paths: **UNKNOWN**.
8. **Payout eligibility — no user-status check** in `_payout_ineligibility_reasons` (checks: session COMPLETED, report exists, CONFIRMED payment, no open dispute, no FULL refund): **UNKNOWN** whether suspension must block payouts (not specified).
9. **Refund creation/approval — no user-status check** in VS8 refund services (actors are OPS/ADMIN anyway; parent cannot create refunds): **UNKNOWN** for the edge of suspended-admin? (admin suspension not specified at all — §21.6 says "users"; the admin self-suspension edge is unspecified).
10. **Dispute creation — no user-status check** in `open_dispute`: **UNKNOWN**.
11. **Dispute resolution — OPS/ADMIN only** (VS9); a suspended parent already cannot resolve; admin suspension effects: **UNKNOWN**.
12. **Teacher visibility — no automatic hiding:** teacher search filters `teacher_subjects.is_active` + slot availability only (not `users.status`); `teacher_listing_status` has its own SUSPENDED value (set by nothing); Feature Flag Governance states the listing fallback "Cannot show unverified/suspended teacher as listed" (policy note tied to `TEACHER_PUBLIC_LISTING_ENABLED`). Automatic hiding on user suspension: **UNKNOWN** (not specified; a flag policy exists but is not a suspension effect spec).
13. **Parent visibility** — no parent-listing surface exists; **UNKNOWN** (n/a).
14. **Admin visibility — spec'd in UX:** A-63 screen (state badges Active/Suspended/Deleted; user summary; reason; impact warning; related disputes/security events; ADMIN only; "Action disabled without reason; SUPPORT/OPS disabled unless policy allows special case").
15. **Reactivation semantics — endpoint spec'd (POST /admin/users/:id/reactivate, ADMIN), effect unspecified** (presumably → ACTIVE; details UNKNOWN — e.g., no spec on session/token restoration, which cannot exist since suspension has no token semantics).
16. **Audit/security events — partially spec'd:** API §21.6 "Every admin operation … insert event_ledger ADMIN_ACTION"; A-63 "ADMIN_ACTION, possibly SECURITY_EVENT"; Security/Privacy Plan lists "admin user suspension" under must-audit. Dedicated security event type for suspension: **does not exist** in `security_event_type` enum (values: LOGIN_FAILED, TOKEN_REVOKED, PASSWORD_CHANGED, SUSPICIOUS_ACTIVITY, RATE_LIMITED, ADMIN_ACCESS, DOCUMENT_ACCESS) — `SUSPICIOUS_ACTIVITY` or `ADMIN_ACCESS` would be the only existing carriers (choice = spec decision).
17. **Idempotency — A-63 "Recommended"** (not mandated); request contract (reason field? format?) unspecified: **CONTRACT GAP**.
18. **Concurrency — unspecified:** **UNKNOWN**.
19. **Reversibility — YES by design** (reactivate endpoint exists; DELETED is a distinct status).
20. **Effect on existing sessions / financial obligations — NOT specified:** **UNKNOWN** (critical: does suspending a parent void their held/booked sessions? Does suspending a teacher freeze TEACHER_PAYABLE? No document answers).

**CRITICAL RULE honored:** no effect was inferred. The only suspension behavior that exists in the repository is the pre-existing login-ACTIVE guard (which predates R10 and is not documented as suspension policy).

**R10 verdict:** endpoint + UI + audit intent are documented; **operational effect spec is entirely missing** (no state machine, no effects table, no policy, no contract details). R10 cannot be scoped without a new approved spec document defining the effects matrix — that is a governance decision, not an implementation detail.

# G. R11 investigation (Phase 4 — full audit)

- **Proposed operations (API §14.5, "Suggested"):** `GET /admin/ledger/transactions` (OPS/ADMIN, search), `GET /admin/ledger/transactions/:id` (OPS/ADMIN, tx + entries), `POST /admin/ledger/reversals` (ADMIN, "Create reversal with reason"). "All admin ledger access/actions are audited."
- **Authority level:** SUGGESTED — not an approved contract (no request/response bodies anywhere; no error catalogue; no idempotency statement).
- **Accounts affected (existing enum):** PARENT_CASH, PAYMENT_PROVIDER_CLEARING, PLATFORM_CASH, PLATFORM_REVENUE, TEACHER_PAYABLE, TEACHER_CASH, REFUND_PAYABLE, **ADJUSTMENT**. Transaction types: PARENT_PAYMENT, PLATFORM_COMMISSION, TEACHER_PAYOUT, REFUND, **ADJUSTMENT** (the only type permitted without booking/payment/payout FK — CHECK at schema line 563).
- **Transaction lifecycle (existing):** DRAFT → POSTED (VS8 refund flow; VS2/VS5 post directly) ; DRAFT → VOIDED (VS8 failure/cancel); **POSTED is terminal in every implemented path** — no implemented transition reverses a POSTED tx.
- **Correction/reversal semantics — how the schema itself answers:** ledger entries are **immutable** (`prevent_ledger_entry_mutation` trigger on UPDATE OR DELETE — append-only); the balance is a DEFERRABLE INITIALLY DEFERRED constraint trigger (every tx with entries must debit=credit); **PAID payout rows are immutable (v1.4)** with the trigger message: *"create a separate adjustment/recovery transaction instead of updating payout"*. → The approved correction model is **offsetting entries, never mutation**. A reversal therefore = a new balanced ADJUSTMENT (or REFUND) transaction referencing the original, plus audit — or, for DRAFT-only, a VOID (already implemented for refund DRAFTs).
- **No service has ever written an ADJUSTMENT transaction** (verified: zero code references) — R11's reversal would be the first.
- **Authorization:** ADMIN only for reversals; OPS/ADMIN for reads (per §14.5).
- **Audit trail:** "All admin ledger access/actions are audited" (§14.5); existing pattern = ADMIN_ACTION event + (for sensitive reads) ADMIN_ACCESS security event (VS8 convention).
- **Idempotency/concurrency:** unspecified for reversals; repo convention available (scope + canonical hash + FOR UPDATE on the target tx).
- **Balance enforcement:** DB-deferred (existing) — any reversal must insert a balanced set of entries.
- **Period locking:** **no such mechanism exists** in schema or code — unspecified (UNKNOWN; likely a production concern, not DEV).
- **Financial approval requirements:** Engineering Governance §5 (financial-workflow change approval) applies to any service that moves ledger state — the five-owner gate would be required for the reversal service (not for read-only admin listing).
- **OPS/accounting policy dependencies:** no OPS policy covers ledger corrections/reversals (verified: only OPS-POL-007 touches LedgerService, for allocation). Policy gap.
- **Manual journal entry:** Addendum §9 — adjustment creation is "a controlled side effect of approved refund/payout/ledger services, **not a manual UI command**" → an ADMIN reversal endpoint is permissible only as a tightly-constrained audited service (reason required per §14.5), not a free-form journal.
- **Ledger mutation model:** entries append-only (DB-enforced); posted entries **cannot be edited** (DB-enforced); **voiding** is implemented only for refund DRAFTs (VS8) — voiding a POSTED tx is not an implemented transition (offsetting ADJUSTMENT is the approved alternative per the v1.4 trigger message).
- **New ledger accounts required:** NO (ADJUSTMENT exists). **Schema changes required:** NO (for reads + minimal balanced-ADJUSTMENT reversal). **Production-only controls (period locking):** unspecified.
- **Event types:** no dedicated ledger/reversal event exists in `event_type` — the action would audit via existing `ADMIN_ACTION` (+ existing security events); introducing a new event enum value would be a schema change (not required for a minimal slice).

**R11 verdict:** DB-ready, contract-weak (SUGGESTED, no reversal contract), policy-weak (no correction policy), financially sensitive (five-owner gate required). Two viable sub-scopes: (a) **reads only** (admin ledger list/detail — ADMIN/OPS, audited) — low risk, decision-light; (b) **reversal service** — requires approved reversal semantics + policy + financial gate. (a) alone is a legitimate small slice; (b) is not scope-ready.

# H. R4 investigation (Phase 5)

- **Contract (APPROVED, API §11.6):** `POST /bookings/:id/cancel` — PARENT (own booking, before cancellation deadline), TEACHER (own booking, under policy; affects cancellation metrics), OPS/ADMIN (operational override with reason). Request `{reason, requested_refund}`. Rules: cannot cancel COMPLETED; "If payment confirmed, cancellation may create refund eligibility or dispute"; reason + actor stored; Event Ledger required. Event: `BOOKING_CANCELLED` (exists in enum).
- **State machine (APPROVED, SM §6.3):** HELD → CANCELLED; PAYMENT_PENDING → CANCELLED (or EXPIRED); BOOKED → CANCELLED. CANCELLED is terminal (no CANCELLED → other transitions in §6.3).
- **Payment interaction:** pre-payment (HELD/PAYMENT_PENDING): no confirmed payment — PAYMENT_PENDING has an INITIATED/PENDING payment row (abandoned on cancel; no ledger tx exists at that point — payments post at CONFIRMED); **confirmed (BOOKED):** "may create refund eligibility or dispute" — deliberately open; with VS8 now implemented, the refund path is a VS8 `create_refund` (FULL, operator-initiated or auto — **trigger semantics unspecified**).
- **Payout interaction:** no payout exists before session completion; cancelling a BOOKED booking with a SCHEDULED session prevents payout (session never completes) — no special mechanism needed; no documented conflict.
- **Refund interaction:** see payment; late-payment branch (VS2: HELD→EXPIRED with late payment auto-creates a REQUESTED FULL refund) is a distinct EXPIRED path — cancellation does not use it; interaction edge: a PAYMENT_PENDING booking that is late-paid after cancel — unspecified (UNKNOWN; the late branch is expiry-driven, not cancel-driven).
- **Dispute interaction:** cancel vs open-dispute ordering unspecified (SM §6.3 allows DISPUTED → CANCELLED "depending resolution"; booking DISPUTED is overlay-forbidden on the status column by v1.1 — the dispute overlay lives in `disputes.status`).
- **Slot release:** slots have status transitions (block/unblock exist in code); slot release on cancel is **not spec'd** (plan-time decision; mechanism exists).
- **Session cascade:** sessions have a CANCELLED state (enum); booking-cancel → session-cancel is **not explicitly spec'd** (plan-time decision; state exists).
- **Authorization/idempotency/concurrency:** actors per §11.6; idempotency/concurrency unspecified (repo convention applies: Idempotency-Key on state-changing POST + booking-row `FOR UPDATE` — existing hold/confirm pattern).
- **Terminality:** CANCELLED terminal per §6.3.
- **Missing contracts (exact list):** (1) cancellation-deadline policy — **no OPS policy exists** (searched: zero cancellation mentions in the policy document); (2) `requested_refund=true` consequence on confirmed payment (auto-create REQUESTED FULL refund via VS8? create dispute? operator choice?) — **ambiguous by spec text**; (3) teacher cancellation policy (what "under policy" means; metric effect is named but not defined); (4) session cascade rule; (5) slot-release rule; (6) PAYMENT_PENDING late-edge.

**R4 verdict:** pre-payment path = small, nearly standalone (HELD→CANCELLED + slot release + event + reason/actor). Paid path = dependency satisfied (VS8) but 4–6 plan-time decisions required; R5 reschedule is thinner still (rules "under rules" — not itemized). PARTIALLY scope-ready.

# I. Student Passport / completion investigation (Phase 6)

- **Product scope (APPROVED, API §7.4):** `GET /students/:id/passport` (PARENT) returns Student Passport v0 from structured data — sources: `sessions`, `session_reports`, `student_progress_events` (all implemented in VS3); response shape fully specified (`subjects[]` with completed_sessions / recent_topics / recurring_weaknesses / recent_progress_notes); "**No AI-generated claims are returned in MVP**".
- **Completion surface (§7.1):** `GET /students` (list own), `PATCH /students/:id`, `DELETE /students/:id` ("Archive/delete own student"; event STUDENT_PROFILE_UPDATED), `POST/DELETE /students/:id/permissions` (grant/revoke teacher access; events STUDENT_PROFILE_UPDATED or ADMIN_ACTION if admin).
- **Permissions (§7.5 + schema):** `student_permissions` table exists (student+parent composite FK, teacher FK CASCADE, scope default 'SESSION_CONTEXT', granted_for_booking_id, starts_at/expires_at/revoked_at, CHECK expires>starts) — table ready; service absent.
- **Database requirements:** NONE (all tables/enums exist). **State model:** none new. **Authorization:** §7.2 ownership rule (`student_profiles.parent_id = authenticated_parent.id` → else 403) — the exact pattern already implemented for GET /students/:id (VS1).
- **Privacy implications:** minimized-minor-data design is the spec (no full legal name, birth_year plausibility check, consent GRANTED to activate); passport returns only derived structured aggregates; teacher access only via explicit permission grant (scope SESSION_CONTEXT). No new PII surface.
- **Evidence requirements:** none beyond existing VS3 data. **Dependencies:** VS3 data only (satisfied). **Completion criteria:** endpoint behavior per §7.1/§7.4/§7.5 + ownership 403 tests + event assertions.
- **Scope-creep guard:** passport v0 is read-only; no AI claims (explicit); permissions are grants (no impersonation); DELETE is archive/delete of own student (VS1-style), not cascading financial mutation (bookings/payments are RESTRICT-FK — behavior on delete with history = plan-time decision, likely archive-only per "minimized" design).

**R7 verdict:** scope-ready (read-only core is decision-free; CRUD completion adds 1–2 minor locks).

# J. Auth completion investigation (Phase 7)

- **What remains incomplete:** `POST /api/v1/auth/refresh` (§3.5) and `POST /api/v1/auth/revoke-sessions` (§3.7) — both APPROVED contracts, neither implemented. (Logout exists and is the established convention: session-bound `revoked_at` update + TOKEN_REVOKED security event + event_ledger SECURITY_EVENT entry, no Idempotency-Key header.)
- **Current architecture (verified code):** HS256 JWT with `exp = now + JWT_ACCESS_TTL_SECONDS`, payload bound to `auth_sessions.id`; every request verifies the session row (`revoked_at IS NULL`, `expires_at` future) — i.e., server-side per-session invalidation already exists; login stores `refresh_token_hash` (UNIQUE) + device/ip/ua; refresh tokens are currently issued-but-unusable.
- **RBAC:** refresh/revoke are self-service (any authenticated user, own sessions only); no admin surface is spec'd for sessions (none invented).
- **Account lifecycle:** `users.status` is orthogonal (see §F); refresh must respect session expiry/revocation (spec'd: "Verify refresh token hash against **active** auth_sessions row").
- **Password/security behavior:** password change/reset is **not spec'd** (API has no such endpoint; §27.1 mentions "Password reset **if implemented**" — not implemented → OUT OF SCOPE, not a gap).
- **Ownership:** own-sessions-only (§3.7 "user can revoke" — the user's sessions); cross-user revocation must be denied (plan assertion).
- **Audit events:** replay of a rotated token → `SECURITY_EVENT` (§3.5 explicit) — existing enum carriers: SUSPICIOUS_ACTIVITY; revocations → TOKEN_REVOKED (existing; used by logout). Event ledger `SECURITY_EVENT` row pattern already exists (logout).
- **Rate limiting:** §27.1 explicitly includes "Refresh token" in the rate-limited list; Sprint 1 report: DRF throttling foundation present, per-scope policies "not yet tuned" → apply existing foundation; no new infra.
- **Dependency status:** none new. **Production blockers:** none DEV-specific (this is security hygiene; real production hardening = secure transport etc. per §27.2 — out of DEV scope).
- **"Decision-free" classification — verdict: slightly stale.** Governance decisions: zero. Plan-time contract locks: **three** — (D1) refresh request/response shape (spec defines behavior, not bodies; login response shape is the in-repo precedent), (D2) revoke-sessions request shape (§3.7 names the three scopes, not the body/selector), (D3) replay "session family" semantics (schema has per-session rows, no family concept; §3.5 hedges "where supported" → lock: revoke the replaying session only, documented INFERRED). None blocks scope-readiness.

**R6 verdict:** scope-ready at declared scope; strongest evidence-based VS10 candidate.

# K. Database audit (Phase 8)

| Candidate | Existing support (verified in v1→v1.4) | SCHEMA_CHANGE_REQUIRED | Missing (if any) |
|---|---|---|---|
| R6 Auth | `auth_sessions` (refresh_token_hash UNIQUE, revoked_at, expires_at, CHECK), JWT-session check in auth.py, TOKEN_REVOKED/SUSPICIOUS_ACTIVITY events | **NO** | none |
| R7 Passport | `student_progress_events`, `session_reports`, `sessions` (VS3 data), `student_permissions` (full), events STUDENT_PROFILE_* | **NO** | none |
| R4 Cancel | `booking_status` incl. CANCELLED (+v1.1 overlay CHECK), `session_status` incl. CANCELLED, slot status transitions, `BOOKING_CANCELLED` event, booking-row lock convention | **NO** | none (deadline policy is a policy, not schema) |
| R10 Suspend | `user_status` enum + `users.status` + `deleted_at`; login-ACTIVE guard; session invalidation mechanism; A-63 UI | **NO** (for the endpoints + status change + audit) | **effect spec is missing (governance, not schema)**; optional: dedicated security event type would be a change — not required (existing carriers suffice) |
| R11 Ledger admin | ledger tables/constraints/triggers (balance deferred, entry immutability, PAID-payout immutability), ADJUSTMENT tx+account types, `idx_ledger_transactions_refs` | **NO** (for reads + minimal balanced-ADJUSTMENT reversal) | none in schema; contract + policy + financial gate missing |
| R12/R13/R14/R15/R16 | notifications + enums (R12); admin tables (R13); reports table (R14); raw source tables for metrics (R16) | **NO** | none in schema |

FK integrity / unique / check / triggers / enums / indexes / idempotency structures: all verified present and exercised by the 197-test suite + 30/30 direct-SQL audit (Post-VS8/VS9 records). No migration file was created or proposed by this task.

# L. API audit (Phase 9)

Current surface (Post-VS8 inventory, re-verified): 52 implemented unique operations + 2 VS9 (54 in-tree) + `/health` + `/ready`; ≈80 approved unique endpoints overall.

VS10 candidate operations, classified:

| Candidate | Endpoint | Method | Authorization (approved) | Request contract | Response contract | Error contract | Idempotency | State transition | Audit event | Classification |
|---|---|---|---|---|---|---|---|---|---|---|
| R6 | `/api/v1/auth/refresh` | POST | any authenticated (own session) | **GAP** (behavior spec'd, body not — D1 lock; login response shape is precedent) | **GAP** (D1; precedent: login's access/refresh/expires_in) | 401 invalid/expired/replayed (precedent TOKEN_INVALID/TOKEN_EXPIRED + 401 class) | session-bound (logout convention) | rotate refresh hash; revoke old; (replay → revoke session) | SECURITY_EVENT (replay, §3.5 explicit); existing TOKEN_REVOKED pattern | **APPROVED (behavior) / CONTRACT GAP (bodies → D1)** |
| R6 | `/api/v1/auth/revoke-sessions` | POST | any authenticated (own sessions) | **GAP** (scopes named: current/all other/all — body not — D2 lock) | standard envelope | 401/404 class | session-bound | set revoked_at on target sessions | TOKEN_REVOKED (logout convention) | **APPROVED (behavior) / CONTRACT GAP (body → D2)** |
| R7 | `GET /students/:id/passport` | GET | PARENT own (§7.2) | none | **specified** (§7.4) | 403/404 (precedent) | n/a | none | none (read) | **APPROVED** |
| R7 | `GET /students`, `PATCH/DELETE /students/:id`, `POST/DELETE /students/:id/permissions` | — | PARENT own | specified (§7.1/§7.5) | standard envelope | 403/404/400 class | repo convention | profile/permission rows | STUDENT_PROFILE_UPDATED (ADMIN_ACTION if admin) | **APPROVED** |
| R4 | `POST /bookings/:id/cancel` | POST | PARENT/TEACHER/OPS/ADMIN (role-specific rules) | **specified** `{reason, requested_refund}` | standard envelope | 403/409-class (precedent) | repo convention | → CANCELLED (§6.3) | BOOKING_CANCELLED (required) | **APPROVED** (deadline/refund-trigger = plan-time decisions) |
| R4 | `POST /bookings/:id/reschedule` | POST | (per §11.7) | partial (endpoint + events; rules "under rules") | — | — | — | — | — | **CONTRACT GAP** (R5) |
| R10 | `POST /admin/users/:id/suspend`, `/reactivate` | POST | ADMIN | **GAP** (A-63: reason required; body not spec'd) | standard envelope | 403/409-class (A-63 "Invalid state, insufficient permission") | "Recommended" (A-63) | users.status change (transitions UNDEFINED) | ADMIN_ACTION (required); SECURITY_EVENT "possibly" (A-63) | **APPROVED-thin / CONTRACT GAP (effects undefined)** |
| R11 | `GET /admin/ledger/transactions(+/id)` | GET | OPS/ADMIN | filters unspecified (VS8 list convention precedent) | tx + entries | 404 class | n/a | none | audited reads (§14.5) | **SUGGESTED (not approved)** |
| R11 | `POST /admin/ledger/reversals` | POST | ADMIN | **GAP** ("with reason" only) | **GAP** | **GAP** | unspecified | new balanced ADJUSTMENT tx (or DRAFT VOID) | ADMIN_ACTION (required) | **SUGGESTED / CONTRACT GAP (semantics undefined)** |

No endpoint, request field, or response field was invented; gaps are labeled as such.

# M. State-machine audit (Phase 10)

| Candidate | Current state → Action | Role | Preconditions | New state | Event | Financial effect | Terminality | Idempotency | Lock order | Conflict check vs VS8/VS9 |
|---|---|---|---|---|---|---|---|---|---|---|
| R6 | active auth_session → refresh | owner | hash matches, session not revoked/expired | same session, rotated hash (old token dead) | SECURITY_EVENT only on replay (TOKEN_REVOKED pattern on explicit revoke) | none | session terminal on revoke/expiry | replay of rotated hash → 401 + revoke + SECURITY_EVENT | `auth_sessions` row FOR UPDATE (single row; no cross-object order) | none (isolated from payment/refund/dispute/booking/payout objects) |
| R6 | active auth_session(s) → revoke (current/other/all) | owner | own sessions | revoked_at set | TOKEN_REVOKED | none | revoked is terminal (no reactivation of a session) | session-bound (logout convention) | row(s) FOR UPDATE | none |
| R7 | (read-only passport) | parent | ownership | — | none | none | — | n/a | — | none |
| R7 | permission grant/revoke | parent | ownership; teacher exists | permission row active/revoked_at | STUDENT_PROFILE_UPDATED | none | revocation terminal per row | repo convention | student row → permission row (new, leaf) | none |
| R4 | HELD → CANCEL | parent/teacher/ops/admin (role rules) | booking state HELD; deadline (policy — UNDEFINED); reason stored | CANCELLED (terminal) | BOOKING_CANCELLED | none (no confirmed payment) | terminal | repo convention | booking row FOR UPDATE (existing) | none |
| R4 | PAYMENT_PENDING → CANCEL | same | as above | CANCELLED | BOOKING_CANCELLED | abandons PENDING payment (no ledger tx exists pre-CONFIRMED) | terminal | repo convention | booking → payment (existing VS2 order) | none |
| R4 | BOOKED → CANCEL | same | not COMPLETED; reason; `requested_refund` semantics (UNDEFINED) | CANCELLED | BOOKING_CANCELLED (+VS8 refund flow if triggered) | possible VS8 FULL refund (operator/trigger UNDEFINED) | terminal | repo convention | booking → payment → refund (existing VS8 order) | none (uses VS8 service, same order) |
| R10 | (UNDEFINED transition table) | ADMIN | (UNDEFINED) | (UNDEFINED: →SUSPENDED; →ACTIVE) | ADMIN_ACTION (required); SECURITY_EVENT (possibly) | (UNDEFINED — see §F items 6–11,19–20) | (UNDEFINED) | (A-63: recommended) | (UNDEFINED) | **cannot be constructed — spec absent (C1 OPEN)** |
| R11 | POSTED tx → reversal (UNDEFINED) | ADMIN | (UNDEFINED: which statuses; reason required) | (UNDEFINED: offsetting ADJUSTMENT tx; original untouched — entries immutable by DB) | ADMIN_ACTION | balanced ADJUSTMENT entries (no new accounts) | original tx terminal | unspecified | target tx FOR UPDATE (new, leaf on ledger) | none (ledger is append-only; no cycle with payment/refund/payout) |

No new machine conflicts VS8/VS9: R6 and R7 touch objects disjoint from the refund/dispute/payout machines; R4 reuses the existing booking→payment→refund lock chain; R10/R11 have no defined transitions to conflict (spec gaps, labeled).

# N. Financial audit (Phase 11)

| Candidate | Money trace (payment→refund→dispute→payout→ledger) | Existing mechanisms sufficient? | New ledger form needed? | Payout triggers remain valid? | Refund interactions safe? | New accounting policy approval? | Classification |
|---|---|---|---|---|---|---|---|
| R6 Auth | none (session objects only) | n/a | NO | unaffected | unaffected | NO | **FINANCIAL_READY** (no financial surface) |
| R7 Passport | none (read-only aggregates + access grants) | n/a | NO | unaffected | unaffected | NO | **FINANCIAL_READY** |
| R4 Cancel | pre-payment: none; paid: BOOKED+CONFIRMED → possible VS8 FULL refund (VS8 forms L/D/A unchanged; DRAFT→POSTED/VOIDED intact) | YES for the refund leg (VS8 service) — the *trigger* is the open decision | NO (reuse VS8 forms) | valid (cancel prevents completion → no payout; no new path) | safe (VS8 over-refund/status guards unchanged; cancel does not mutate existing refunds) | NO (no new accounting; OPS-POL-007 untouched) | **FINANCIAL_CONDITIONALLY_READY** (condition = requested_refund trigger decision, plan-time) |
| R10 Suspend | **UNKNOWN** — no document defines suspension's effect on TEACHER_PAYABLE/payouts/refunds/booking obligations (§F items 6–11, 20) | UNKNOWN | UNKNOWN (depends on effects spec) | UNKNOWN | UNKNOWN | REQUIRED once effects defined (if any financial effect exists → Engineering Governance §5) | **UNKNOWN** (preserved; not FINANCIAL_BLOCKED by assertion — blocked by absence of spec) |
| R11 Ledger admin | reads: none; reversal: creates balanced ADJUSTMENT tx (offsetting model per v1.4 trigger message; entries immutable) | YES for the mechanics (balance constraint, immutability triggers, ADJUSTMENT types exist) — semantics undefined | NO new accounts/forms (ADJUSTMENT exists) | reversal must not touch PAID payouts directly (v1.4 immutability) — offsetting only | reversal of a refund-related tx interacts with refund state — semantics undefined | YES (financial-workflow five-owner gate + correction policy) | **FINANCIAL_BLOCKED** (until reversal contract + policy + gate) — reads-only sub-scope: FINANCIAL_READY |

No accounting entry was invented; every traceable effect cites an approved source (VS8 forms, v1.4 trigger message, Addendum §9).

# O. Security audit (Phase 12)

Roles (verified `role_name` enum): **PARENT, TEACHER, SUPPORT, OPS, ADMIN** — five roles. **Note: there is no SAFETY role in the schema or any role matrix; "SAFETY" appears only as a dispute category (priority 1) and as the UX "safety dispute" concept. Any matrix below therefore lists the five real roles + SYSTEM (server-side processes) — the task's SAFETY row is satisfied by the category-based rules where they exist.**

| Action | PARENT | TEACHER | SUPPORT | OPS | ADMIN | SYSTEM |
|---|---|---|---|---|---|---|
| R6 refresh (own session) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) | n/a |
| R6 revoke-sessions (own) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) | n/a |
| R6 revoke *another user's* session | DENY | DENY | DENY | DENY | DENY (no admin surface spec'd) | n/a |
| R7 passport / permissions (own student) | ALLOW (owner, §7.2) | DENY (unless granted permission row, read-scoped) | DENY | DENY | ALLOW (admin reads per existing admin surfaces; ADMIN_ACTION if mutating) | n/a |
| R7 student CRUD (own) | ALLOW (owner) | DENY | DENY | DENY | n/a (no admin student-mutation spec) | n/a |
| R4 cancel (own booking) | ALLOW (before deadline — policy UNDEFINED) | ALLOW (under policy — UNDEFINED; metric effect named) | DENY | ALLOW (override + reason) | ALLOW (override + reason) | n/a (hold-expiry job is R15, not implemented) |
| R10 suspend/reactivate | DENY | DENY | DENY (A-63: "disabled unless policy allows special case") | DENY (same) | ALLOW (ADMIN only, reason required, audited) | n/a |
| R11 ledger reads | DENY | DENY | DENY | ALLOW (§14.5) | ALLOW (§14.5) | n/a |
| R11 reversal | DENY | DENY | DENY | DENY | ALLOW (§14.5 — semantics UNDEFINED) | n/a |

Cross-cutting verified properties (no inference): ownership enforced by §7.2 pattern (implemented for students; same for sessions-own in R6); self-action: refresh/revoke are self-service and cross-user denied by design (session lookup scoped by user_id — logout precedent); privilege escalation: none introduced (no new role grants); client-supplied state: none (all state server-derived; refresh body carries only the opaque token; revoke carries only a scope selector); audit: R6 replay → SECURITY_EVENT (spec'd), revokes → TOKEN_REVOKED (convention); R10 → ADMIN_ACTION required + security event "possibly" (A-63); R11 → all access/actions audited (§14.5); PII: passport is minimized-minor-data by design; destructive ops: none beyond session revocation (reversible? no — session revocation terminal by design) and R10 suspension (reversible via reactivate — spec'd direction, details UNKNOWN).

# P. Idempotency / concurrency audit (Phase 13)

Existing conventions (VS5/VS8/VS9, verified): `api_idempotency_keys` (scope, actor_key, idempotency_key, request_hash, status PROCESSING/COMPLETED, response replay; v1.3 lifecycle guards: identity immutable, terminal immutable), `_idempotency_begin/_complete` helpers, canonical = `sha256(json(sorted explicit-strings))`, row locking `FOR UPDATE` in documented acyclic orders (VS5: session→payment; VS8: payment→refund→booking; VS9: dispute→session(no-show)→payment→booking).

| Candidate | Scope | Request hash | Replay | Conflict | In-flight | Terminal | Lock order | Acyclic check |
|---|---|---|---|---|---|---|---|---|
| R6 refresh | `auth_refresh` | canonical {refresh_token_hash} (server-identified session) — or session-bound no-key per logout convention (**D1/D-lock**) | rotated-token replay → 401 + session revoked + SUSPICIOUS_ACTIVITY (§3.5) | same hash, different context → 409 class (convention) | PROCESSING guard (convention) | session revoked/expired | single `auth_sessions` row FOR UPDATE | trivially acyclic (leaf object) |
| R6 revoke-sessions | session-bound (logout convention) | n/a (guarded UPDATE `revoked_at IS NULL`) | no-op on already-revoked (guarded UPDATE) | n/a | n/a | revoked terminal | row(s) FOR UPDATE | acyclic |
| R7 permissions | `student_permission` (convention) | canonical {student_id, teacher_id, scope, booking} | 200 stored (convention) | 409 (convention) | guard | revocation terminal | student → permission (leaf) | acyclic |
| R4 cancel | `booking_cancel` (convention) | canonical {booking_id, reason, requested_refund, actor_role-class} | 200 stored | 409 (convention) | guard | CANCELLED terminal | booking → payment → refund (existing VS8 chain; VS9 dispute chain not touched) | acyclic (subset of existing orders) |
| R10 suspend | (UNDEFINED — A-63 "recommended") | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | (UNDEFINED — user row; no known cycle) | **cannot verify — spec absent** |
| R11 reversal | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | (UNDEFINED) | original tx terminal (DB) | target tx FOR UPDATE (leaf on ledger) | acyclic if so (ledger not in any existing cycle) — **plan lock** |

No reverse lock order is introduced by any ready candidate (R6/R7/R4 reuse or extend existing chains only).

# Q. Frontend audit (Phase 14)

Implemented today (DEV consoles only — 5 pages: admin, parent, teacher, plus 2 app routes; **Production UI = 0/64 screens** — R17 remains a phase):

| Candidate | DEV UI (exists?) | DEV UI (needed for slice?) | Production UI | New screens (spec'd?) |
|---|---|---|---|---|
| R6 Auth | NO session UI (login/logout are in `lib/api.ts` + existing login forms) | NO new screen required — refresh is client-library behavior (token refresh on 401/expiry in `lib/api.ts`); optional: session-revoke control is **not spec'd** in any wireframe → not built (no invention) | NO (production auth UX is R17) | 0 spec'd |
| R7 Passport | NO passport UI | Parent console gains a passport view **only if** a wireframe specifies one — none does for passport v0 → API-only slice is compliant (DEV console additions optional, not required by spec) | NO | 0 spec'd |
| R4 Cancel | NO cancel UI in DEV consoles | cancellation is spec'd as an API operation; no wireframe CTA found for cancel in DEV scope → API-first (console buttons optional) | NO | 0 spec'd for DEV slice |
| R10 Suspend | — | A-63 screen EXISTS in the approved wireframes (production-screen ID) — building it is R17 scope; the slice is API + DEV-console-testable | A-63 belongs to R17 (64-screen phase) | A-63 (R17, not VS10) |
| R11 Ledger admin | NO | admin console list/detail view — no wireframe spec'd for ledger screens → API-first | R17 | 0 spec'd |

Rule honored: DEV console functionality is never treated as production UI; no screen counts invented (the only spec'd screen is A-63, and it is explicitly R17-phase material).

# R. Testing audit (Phase 15)

Existing conventions (verified in VS1–VS9 suites): per-slice `tests/test_<domain>.py` (service tests using Django test client + direct SQL assertions; uuid-based unique fixtures; per-entity event counts; before/after deltas for shared-DB counts), `tests/test_<domain>_concurrency.py` (threading.Barrier races; exactly-one-winner assertions; DB-level post-race checks), standalone `tests/e2e_<domain>.py` (own PG cluster + migrations + dev server [+ Next.js production server for console checks]; numbered scenarios S1…Sn; financial-integrity gates; non-zero exit on failure), slice reports + dependency-audit chain + README section. Baseline: 197 tests green (Post-VS9).

Proposed VS10 test inventory (R6 auth completion, specified behavior only — no tests written):

| Category | Est. count | Covers (approved behavior) |
|---|---|---|
| Service | 14–18 | refresh: happy path rotation (new hash stored, old dead, new valid); expired session 401; unknown/wrong hash 401 (indistinguishable, no enumeration); another-user's hash 401/404-class; replay of rotated token → 401 + session revoked + SUSPICIOUS_ACTIVITY written (DB); revoke current (revoked_at set, TOKEN_REVOKED, token dead); revoke all-others (count + owner scope); revoke all; already-revoked no-op; ownership guard (cross-user 403/404-class); audit rows present; login-issued refresh token usable (integration); expiry boundary |
| Authorization | 3–4 | anonymous 401 (both endpoints); own-only scoping; no admin surface exists (404/405 for admin-style calls — no invention, just absence) |
| Idempotency/replay | 3–4 | rotated-token replay (above) + guarded-UPDATE idempotency of revoke (no double TOKEN_REVOKED for no-op revoke — convention decision D-lock) |
| Concurrency | 2–3 | two concurrent refreshes of the same session → exactly one rotation wins (single hash, one winner 200, other 401/409-class); concurrent revoke + refresh ordering safe (row lock) |
| Security | 2–3 | no user enumeration (uniform error + no timing oracle claim beyond uniform 401); security events severity/actor correct; rate-limit scope present (foundation — §27.1) |
| E2E (standalone) | 6–8 scenarios | login → refresh → old token 401 → new token works → second rotation → revoke current → 401 → fresh login (2 sessions) → revoke all → both 401; replay detection → SUSPICIOUS_ACTIVITY visible in security events; full-suite coexistence (no regression of 197) |

Estimated total: ~25–32 new tests + 6–8 E2E scenarios → suite ≈ 222–229. (Estimate only; no tests were written or modified by this task.)

# S. Dependency / infrastructure audit (Phase 16)

| Item | Status | VS10 (R6) needs? |
|---|---|---|
| Backend deps | Django 5.2.17, DRF, psycopg 3.2.13, PyJWT, dotenv, pytest, pytest-django, requests (pinned ranges; byte-identical manifests) | **NO new dependency** (JWT/session mechanics already in place) |
| Frontend deps | Next 14.2.35 + React 18 (npm audit: 2 known high packages — carried, FIX-BEFORE-STAGING) | **NO** (no new screens; `lib/api.ts` refresh hook uses existing client) |
| Node | v22 (verified in prior sessions; build green) | NO |
| PostgreSQL | 16.2 (pgserver) + pgcrypto/citext/btree_gist (PGXS-built) | NO change |
| Migration runner | `scripts/run_migrations.py` + `run_backend_tests.sh` | NO change; **NO new migration** |
| CI | none (R21, BLOCKED on spec) | NO |
| New service/infra/tooling | — | **NO** |

# T. Production-boundary audit (Phase 17)

All VS10 candidates are **DEV-scope** under the Implementation Gate (DEV APPROVED WITH STRICT LIMITS; STAGING mock/sandbox only after CI/migration setup; PRODUCTION NOT APPROVED):

| Candidate | DEV | STAGING | PILOT | PRODUCTION |
|---|---|---|---|---|
| R6 Auth | IN SCOPE (slice) | inherits (token security matters earlier — no extra gate beyond STAGING's) | inherits | real auth hardening (§27.2) is a production control, not this slice |
| R7 Passport | IN SCOPE (if chosen) | inherits | inherits | inherits (privacy review per Security/Privacy Plan) |
| R4 Cancel | IN SCOPE (if chosen) | inherits | inherits | inherits |
| R10 / R11 | NOT scope-ready (see §F/§G) | — | — | — |

Confirmed for every candidate: **REAL PAYMENT = FORBIDDEN**, **REAL REFUND = FORBIDDEN**, **REAL PAYOUT = FORBIDDEN** (no gate approved; `REAL_*` flags false; mock-only boundary re-verified in the VS9 commit). No DEV mock behavior is presented as production capability anywhere in this plan.

# U. Candidate ranking (Phase 18)

Criteria (established convention — Post-VS6 candidate analysis, applied by Post-VS8/VS8-audits): scope completeness, contract completeness, financial readiness, security readiness, database readiness, test readiness, dependency risk, implementation risk, unknown count, required decisions.

| Candidate | Scope | Contract | Financial | Security | Database | Test | Dep risk | Impl risk | Unknowns | Required decisions | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **R6 Auth completion** | H | H (3 plan-time body locks) | READY (none) | H (security hygiene; events pre-exist) | H (no change) | H (convention maps 1:1) | none | L | 1 (family semantics) | 3 (all contract locks, non-blocking) | **TOP — scope-ready now** |
| **R7 Passport + completion** | H | H (passport response fully spec'd) | READY (none) | H (ownership + minimized PII) | H (no change) | H | none | L | 0–1 | 1–2 (minor) | **SECOND — scope-ready now** |
| **R4 Cancellation** | M | M (approved endpoint; 4–6 open mechanics) | CONDITIONALLY READY (paid-path trigger decision) | H (role rules spec'd) | H (no change) | M-H | none | M | 4–6 | 4–6 (incl. OPS cancellation-deadline policy — a policy decision) | **THIRD — ready after plan-time decision pass** |
| R8/R9 completion | H | H | READY | H | H | H | none | L | 0–2 | 1–2 | Viable small fill-in (bundle) |
| R13 Admin monitoring completion | H | H (2 reads) | READY | H | H | H | none | L | 0 | 0 | Viable small fill-in |
| R12 Notifications (in-app core) | H (in-app) | H (in-app); channels OPEN | READY | H | H | M-H | none | L-M | 1 (channels — deferrable) | 1 | Viable after/without channel policy (in-app core) |
| R14 Report editing | L-M | GAP (edit policy not itemized) | READY | H | H | M | none | L-M | 1–2 | 1–2 | Not ready (policy first) |
| **R10 Suspend/reactivate** | GAP (effects undefined) | GAP (thin) | **UNKNOWN** | H intent (ADMIN-only, audited) | H (enum exists) | M | none | H | ~15 | **1 major: approved operational-effect spec** (then more) | **NOT scope-ready — spec first** |
| **R11 Ledger admin** | M (reads clear; reversal undefined) | SUGGESTED (not approved) + reversal GAP | reads READY / reversal **BLOCKED** (five-owner gate + policy) | H (audited, ADMIN-only) | H (ADJUSTMENT types + immutability exist) | M | none | reads L / reversal H | 4–6 (reversal semantics, period lock, event choice, policy) | reads: 1 (approve the "suggested" list); reversal: 3+ incl. financial gate | **NOT scope-ready (reversal); reads-only sub-scope viable** |
| R15/R16 jobs + worker | M | GAP (worker spec INFERRED) | L-M (payout-eligibility job financial-adjacent) | M | H | M | none | M | several | worker spec | Not ready (spec detail) |
| R5 Reschedule (alone) | L | GAP ("under rules") | M | M | H | M | none | M | several | rules | Not ready (rules first) |
| N1 follow-up partials | — | BLOCKED (O7 Addendum patch) | M | H | H | H | none | M | 1 (patch text) | contract amendment | BLOCKED |
| R17/R18/R19/R20/R21/R22 | phase/gated | — | — | — | — | — | — | — | — | — | Excluded (not VS10 slice candidates) |

**TOP_VS10_CANDIDATE: R6 — Auth completion** (session refresh + revoke-sessions).
**SECOND_VS10_CANDIDATE: R7 — Student Passport / Student completion.**
**THIRD_VS10_CANDIDATE: R4 — Cancellation** (core; with its plan-time decision pass; R5 not bundled until rules are itemized).

Rationale: R6 is the only candidate with a fully approved behavioral contract, pre-existing schema + events + rate-limit scope, zero financial surface, zero schema change, and a 1:1 mapping onto the established test/E2E conventions — it is the lowest-risk, highest-certainty slice and closes a spec'd security-hardening requirement (§27.2). R7 is next (fully specified read-only core, privacy-positive). R4 carries the most product value of the remainder but 4–6 genuinely open mechanics, one of which (cancellation deadline) is an OPS-policy decision, not a plan-time lock. R10/R11 are deliberately ranked out of "ready" — their gaps are spec/contract gaps that this plan refuses to fill by invention.

# V. Decision register (Phase 19 — for TOP candidate R6)

| ID | Question | Why it matters | Evidence | Current state | Recommended decision | Blocking? | Owner |
|---|---|---|---|---|---|---|---|
| D1 | Refresh request/response contract: request `{refresh_token}` (body) and response `{access_token, refresh_token, expires_in}` (matching login's response shape)? | §3.5 specifies behavior, not bodies; the client library needs a stable contract | §3.5 behavior; login response shape (code); §27.2 hash-only/rotate | CONTRACT GAP (bodies) | Lock to the login-shape precedent; refresh token transported in body (not header) for log-redaction simplicity; response omits user_id/roles (not needed by client) | NO (plan lock) | Architecture Owner (record in VS10 plan) |
| D2 | Revoke-sessions request contract: body `{scope: "CURRENT" \| "OTHERS" \| "ALL"}`? | §3.7 names the three revocable sets, not the request shape | §3.7; logout (current-session) precedent | CONTRACT GAP (body) | Lock `{scope}` enum of the three named sets; default `CURRENT` (safest); unknown scope → 400 | NO (plan lock) | Architecture Owner |
| D3 | Replay-detection semantics: §3.5 says "revoke session family **where supported**"; the schema has per-session rows and no family concept — revoke exactly the session whose hash was replayed, and log SUSPICIOUS_ACTIVITY? | Determines how much access a stolen rotated token revokes; must not invent a family mechanism the schema lacks | schema (auth_sessions per-session; no family column); §3.5 hedge | UNKNOWN (spec hedge) | Lock: single-session revocation (the replaying session only) + SUSPICIOUS_ACTIVITY (existing enum, severity 2) + event_ledger SECURITY_EVENT row (logout pattern); document that "family" is unsupported by v1 schema (no change proposed) | NO (plan lock, INFERRED — flagged) | Security Owner |
| D4 (informational) | Rate limiting on /auth/refresh: §27.1 lists "Refresh token" but Sprint 1 notes per-scope policies "not yet tuned" — apply the existing DRF foundation as-is, or tune? | Security posture; tuning is a policy act | §27.1; Sprint 1 report | PARTIAL (foundation exists, untuned) | Apply existing foundation unchanged; record tuning as a STAGING work item (do not invent thresholds in the slice) | NO (record only) | Ops Lead (later) |

No governance decision in D1–D3 is assumed approved; all are plan-time locks to be recorded in the approved VS10 plan. No UNKNOWN was resolved by assumption — D3's "family" question is explicitly left as a documented INFERRED lock with the schema limitation stated.

# W. Proposed VS10 CORE scope (Phase 20 — candidate definition, not an approval)

**IN-SCOPE (R6 Auth completion):**
1. `POST /api/v1/auth/refresh` — per §3.5: verify presented refresh token's hash against the caller's **active** `auth_sessions` row (not revoked, not expired); rotate: store new hash + revoke the old token **in the same transaction**; issue a new access token (same session id) + new refresh token + `expires_in`; on **replay** of a rotated (already-replaced) hash → 401 + revoke that session (D3 lock) + SUSPICIOUS_ACTIVITY security event + event_ledger SECURITY_EVENT row.
2. `POST /api/v1/auth/revoke-sessions` — per §3.7 + D2 lock: `{scope: CURRENT|OTHERS|ALL}` over the caller's own sessions; set `revoked_at` (guarded, idempotent no-op on already-revoked); TOKEN_REVOKED security event per revocation (logout convention) + event_ledger rows.
3. Client library (`frontend/lib/api.ts`): refresh-on-expiry using the new endpoint; token storage unchanged; no new UI.
4. Tests + standalone E2E per §R; slice reports; dependency audit v1.9; README section.

**OUT-OF-SCOPE (explicit anti-creep list):** password change/reset (not spec'd — §27.1 "if implemented" = not implemented); MFA/2FA (not spec'd); admin session management endpoints (none spec'd — not invented); "session family" mechanism (schema-limited — D3); any `users.status`/suspension behavior (R10); any ledger/payout/refund/dispute/booking interaction (none exists for sessions — verified); rate-limit threshold tuning (D4); production auth infrastructure (STAGING/PRODUCTION gates); new event enum values (existing TOKEN_REVOKED/SUSPICIOUS_ACTIVITY suffice); new security_event types; device management UI (device_label is stored by login but no device endpoints are spec'd).

**DEFERRED (to later slices, with their gating items):** R7 (second candidate — ready but sequenced after), R4 (after its decision pass), R10 (after an approved operational-effect spec), R11 (after contract/policy/financial gate), R12/R13/R14/R15/R16 (per their own gates).

**UNKNOWN (preserved, not resolved):** D3 family semantics (locked as single-session, flagged INFERRED); nothing else.

**Scope-creep prevention:** the slice is exactly two endpoints + client hook + tests/docs. Any request beyond this list returns to this decision register first. No VS11 feature (including any R7/R4/R10/R11 item) may enter under this scope.

# X. Proposed implementation plan (Phase 21 — draft for approval; NOT an implementation start)

1. **Objective:** complete the approved auth-session surface (§3.5/§3.7) so refresh tokens issued at login become usable, sessions can be revoked by their owner, and rotated-token replay is detected and revoked — closing the §27.2 hardening items "Store refresh token hashes only / Rotate refresh tokens / Revoke sessions on suspicious replay".
2. **Scope:** §W IN-SCOPE list, verbatim.
3. **Non-goals:** §W OUT-OF-SCOPE list, verbatim.
4. **Authoritative sources:** API Architecture §3.5/§3.6/§3.7/§27.1/§27.2 (APPROVED); schema v1 `auth_sessions` + `security_event_type` (APPROVED); Security/Privacy Plan (APPROVED WITH CONDITIONS — session events must audit); Engineering Governance (slice approval convention); VS1 login/logout code (evidence — convention source); Post-VS9 state (this plan's §B/§C). Superseded/none conflicting: no addendum touches auth; SM documents contain no session machine (session lifecycle is code-convention, documented here as the plan lock).
5. **Dependency map:** none external. Internal: login (issues refresh token + session row — unchanged), logout (convention source — unchanged), JWT decode in `auth.py` (session check — unchanged).
6. **API changes (additive only):** `POST /auth/refresh` (D1 contract), `POST /auth/revoke-sessions` (D2 contract). No existing endpoint changes. Errors: 401 classes (invalid/expired/replayed — uniform, no enumeration), 400 (bad scope/body), standard envelope + request_id.
7. **State machine (auth_session, code-convention machine — plan lock):** `ACTIVE (revoked_at NULL, expires_at future) → REFRESHED (same row, new hash — old token dead) → REVOKED (revoked_at set, terminal) | EXPIRED (expires_at passed, terminal on use)`. No new schema states.
8. **Authorization:** owner-only (session rows scoped by `user_id` in every query — the logout pattern); anonymous → 401; cross-user → 404-class (uniform; no existence oracle). No role matrix change (all five roles self-service).
9. **Idempotency:** logout convention (session-bound guarded UPDATEs; no Idempotency-Key header for session ops — consistent with existing logout; refresh is naturally once-per-old-token because rotation invalidates the presented hash; a second presentation of the same rotated hash is a *replay*, handled as security detection, not idempotent replay). D-lock: already-revoked revoke = silent no-op (single TOKEN_REVOKED per actual revocation).
10. **Concurrency:** single `auth_sessions` row `FOR UPDATE` inside the rotation transaction (one writer wins; loser sees replaced hash → replay path or 401). Concurrent revoke vs refresh serialized on the same row lock. No cross-object locking; acyclic by construction (leaf object).
11. **Database impact:** NONE (no migration; `auth_sessions.refresh_token_hash` UNIQUE + revoked_at/expires_at + CHECK already exist; no new index needed — session lookups are PK + user_id, existing `idx` pattern).
12. **Financial impact:** NONE (verified: no ledger/payout/refund/payment object touched; no event with financial meaning).
13. **Audit/security events:** refresh rotation: no event on happy path (convention — logout events on revocation); replay: SUSPICIOUS_ACTIVITY (severity 2) + event_ledger SECURITY_EVENT row (logout pattern, actor = victim user id, metadata: session_id, request_id); revokes: TOKEN_REVOKED (severity 1) + SECURITY_EVENT row per actually-revoked session. All via existing enum values.
14. **Frontend scope:** `lib/api.ts` refresh-on-expiry hook (client-side 401/expiry → single in-flight refresh → retry once; second failure → logout state). No new screens, no console changes (no wireframe specifies session-management UI).
15. **Tests:** §R inventory (~25–32 service/authorization/idempotency/concurrency/security tests + 6–8 E2E scenarios), all conventions per §R; DB assertions for hash rotation, revoked_at, security-event rows, uniform 401s.
16. **E2E scenarios (standalone suite, own cluster + dev server + Next.js server):** S1 login→refresh→old-dead/new-live; S2 double rotation; S3 replay detection (rotated token reused → 401 + session revoked + SUSPICIOUS_ACTIVITY visible via admin security-events); S4 revoke CURRENT; S5 revoke OTHERS (2 sessions); S6 revoke ALL; S7 expired-session refresh 401; S8 cross-user 404-class + anonymous 401; S9 no full-suite regression (coexistence). Financial gates: n/a (no financial surface) — suite still runs the standard boundary assertions (REAL_* flags false, no provider events).
17. **Failure handling:** uniform 401 (no oracle); DB error → 500 + request_id (convention); partial rotation failure → transaction rollback (atomic by `tx()`); refresh storm protection → existing DRF throttling foundation (D4).
18. **Rollback strategy:** revert the single VS10 commit (additive endpoints + client hook; no schema → nothing to migrate back; issued-but-unrotated refresh tokens remain unusable as before the slice — no state stranded).
19. **Dependency audit:** v1.9 — expected: no new dependencies; manifests byte-identical; npm/pip findings unchanged (next/postcss carried); secrets scan clean.
20. **Production boundary:** DEV slice; mock boundaries untouched; real auth hardening (§27.2 transport etc.) stays in STAGING/PRODUCTION gate scope.
21. **Decision register:** D1–D3 (blocking: NO; record in approved plan) + D4 informational.
22. **Acceptance criteria:** see §Z.
23. **Implementation sequence:** (1) record D1–D3 in approved plan; (2) `refresh` service + view + url (+ tests to green); (3) `revoke-sessions` service + view + url (+ tests); (4) concurrency tests; (5) `lib/api.ts` hook (+ build green); (6) standalone E2E to 75-class green; (7) full suite green; (8) scope audit (diff vs HEAD); (9) reports + dep audit v1.9 + README; (10) single commit, parent = VS10-base, no push until instructed.
24. **Risk register:** see §Y.
25. **Explicit unknowns:** D3 family semantics (locked single-session, INFERRED-flagged); rate-limit tuning (D4 — deferred to STAGING); nothing else.
26. **Governance gate:** standard slice approval (operator approval of scope + D1–D3 locks + this plan). **No Engineering Governance §5 five-owner financial gate required** — the slice has zero financial surface (verified §X.12); the gate applies to financial-workflow changes, and this is not one.
27. **Final readiness verdict:** **SCOPE-READY at declared scope** — all blocking items are contract locks (D1–D3), each with a recommended default, each recordable in the approved plan without new governance; zero schema/financial/dependency blockers; all mechanics trace to approved sources or documented conventions.

# Y. Risk register

| ID | Risk | Likelihood | Impact | Mitigation (approved-source-traceable) |
|---|---|---|---|---|
| RISK-1 | Stolen refresh token used before rotation window closes | M | M | §3.5-mandated same-transaction rotation + replay revocation (D3) — spec'd behavior, implemented as specified |
| RISK-2 | "Session family" expectation (from §3.5 hedge) unmet → perceived spec deviation | L | L | D3 documents the schema limitation explicitly; no family mechanism invented; addendum note records the interpretation |
| RISK-3 | Refresh endpoint unthrottled if DRF foundation misconfigured | L | M | §27.1 includes refresh; apply existing foundation; D4 records tuning as STAGING item (no invented thresholds) |
| RISK-4 | Scope creep toward password change/reset/device UI (all unapproved) | M | M | §W OUT-OF-SCOPE list enforced at plan-review and scope-audit gates |
| RISK-5 | Concurrency race on the auth_sessions row under load | L | M | single-row FOR UPDATE inside atomic rotation; C-class tests (exactly-one-winner) in §R |
| RISK-6 | Uniform-401 requirement regresses into error oracles | L | M | tests assert identical error codes/paths for unknown vs expired vs revoked vs foreign (enumeration test) |
| RISK-7 | Client retry storm on repeated 401 (refresh loop) | L | L | single in-flight refresh + one retry (X.14 lock); no token refresh on 403-class |

# Z. Acceptance criteria (VS10 R6, for the approval gate)

1. `POST /auth/refresh` and `POST /auth/revoke-sessions` implemented per §3.5/§3.7 + D1–D3 locks; additive routes only.
2. Rotation is atomic (same transaction: new hash stored, old token dead); replay of a rotated hash → 401 + session revoked + SUSPICIOUS_ACTIVITY (DB-verified).
3. Owner-only scoping verified (cross-user/anonymous 401/404-class, uniform — no oracle).
4. TOKEN_REVOKED events written per actually-revoked session (no event for no-op revoke).
5. No schema change (migration chain byte-identical); no dependency change (manifests byte-identical); no other endpoint modified.
6. Full suite: 197 baseline + ~25–32 VS10 green, 0 failed/skipped; standalone VS10 E2E all scenarios PASS.
7. Boundary assertions: REAL PAYMENT/REFUND/PAYOUT FORBIDDEN; REFUND_ISSUED = 0 rows (still); mock-only provider boundary intact.
8. Scope audit (git diff): only VS10 files; no VS8/VS9 surface touched; no DDL; no secrets; no generated artifacts.
9. Reports: VS10 implementation/test/E2E reports + Dependency Audit v1.9 + README section; this plan's D1–D3 recorded in the approved plan.
10. Single commit, parent = current HEAD (`af8f818`), no push until instructed.

# AA. Governance gate

- **Slice approval:** operator approval of the VS10 scope (§W) + plan (this document §X) + D1–D3 locks — the established post-VS9 convention (ratify-before-implement; VS9's §30 gate record is the model).
- **Financial-workflow gate (Engineering Governance §5):** **NOT REQUIRED** — zero financial surface (X.12/N). If any in-slice change is later proposed that touches ledger/payout/refund/payment objects, the five-owner gate applies before implementation (anti-creep guard).
- **Security review:** Security/Privacy Plan obligation honored by design (session events audited; replay detection; hash-only storage) — no new approval needed beyond the slice gate.
- **Policy dependencies:** none OPEN are touched (all 10 OPS policies untouched; D4 defers tuning, inventing nothing).
- **Production gates:** unaffected (STAGING/PILOT/PRODUCTION blocker lists unchanged by this plan).

# AB. Self-audit (Phase 22 — verified before document creation)

- No UNKNOWN silently resolved — D3's only interpretive lock is explicitly flagged INFERRED with the schema limitation stated; R10/R11 gaps remain OPEN/UNKNOWN in §F/§G.
- No endpoint invented — every endpoint cited exists in API Architecture (§3.5/§3.7/§7.x/§11.6/§14.5/§21.6) or is labeled a contract lock on an existing contract.
- No state invented — auth_session states are the code-convention row states (revoked_at/expires_at); "REFRESHED" is a row-value condition, not a new schema state; user-status and reversal states are left UNDEFINED (spec gaps).
- No event invented — only existing enum values referenced (TOKEN_REVOKED, SUSPICIOUS_ACTIVITY, SECURITY_EVENT, ADMIN_ACTION, BOOKING_CANCELLED, STUDENT_PROFILE_UPDATED); absence of a ledger-adjustment or suspension event type is noted, not filled.
- No ledger entry invented — the offsetting-ADJUSTMENT model is cited from the v1.4 trigger message + existing ADJUSTMENT types; no entry shapes proposed.
- No account behavior invented — R10 effects are reported as UNKNOWN item-by-item (§F); the only asserted behavior is the pre-existing login-ACTIVE guard, cited as code, not spec.
- No production behavior invented — all candidates DEV-scoped; real money FORBIDDEN (T).
- No migration created (none exists from this task; none proposed — K).
- No dependency added (S).
- No code modified (verified: working tree clean before document creation; only this file added).
- No tests modified; no frontend modified.
- No commit; no push (verified in §AC).
- No VS11 references as scope — later candidates listed only as DEFERRED with their gates (W); no VS11 feature included in scope.

# AC. Final status

```text
VS10_STATUS:                  PLANNED (not started; no implementation of any kind performed)
TOP_VS10_CANDIDATE:           R6 — Auth completion (POST /auth/refresh + POST /auth/revoke-sessions; D1–D3 plan-time locks, none blocking)
SECOND_VS10_CANDIDATE:        R7 — Student Passport / Student completion
THIRD_VS10_CANDIDATE:         R4 — Cancellation (core; 4–6 plan-time decisions incl. OPS cancellation-deadline policy)
VS10_SCOPE_READY:             YES — for R6 at declared scope (all blockers are recordable contract locks)
DECISION_COUNT:               3 blocking-none (D1–D3) + 1 informational (D4)
BLOCKING_DECISIONS:           0 (D1–D3 are plan-time locks; no governance approval assumed)
SCHEMA_CHANGE_REQUIRED:       NO (R6; also NO for R7/R4/R10-minimal/R11-minimal — §K)
FINANCIAL_READINESS:          R6 READY (none) · R7 READY (none) · R4 CONDITIONALLY_READY (paid-path trigger decision) · R10 UNKNOWN (spec absent) · R11 reads READY / reversal BLOCKED (gate + policy)
SECURITY_READINESS:           R6 READY (owner-only, uniform 401s, replay detection, TOKEN_REVOKED/SUSPICIOUS_ACTIVITY pre-existing; §27.1/§27.2 satisfied) · role matrix verified (5 roles; no SAFETY role exists — SAFETY is a dispute category)
TEST_READINESS:               R6 READY (convention maps 1:1; ~25–32 tests + 6–8 E2E scenarios estimated, none written)
R10_SCOPE_READY:              NO — operational-effect spec missing (C1 OPEN; §F 20-item trace; ~15 UNKNOWNs preserved)
R11_SCOPE_READY:              NO (reversal) / YES (reads-only sub-scope, after approving the §14.5 "suggested" list)
CONTRADICTIONS_OPEN:          C1 (R10 effects), C2 (R11 suggested-vs-addendum), C5 (idempotency "recommended" vs convention) — all classified, none silently reconciled
NEW_DOCUMENTS_CREATED:        1 (this file)
CODE_MODIFIED:                NO
TESTS_MODIFIED:               NO
MIGRATIONS:                   UNCHANGED (v1→v1.4 byte-identical; none created)
DEPENDENCIES:                 UNCHANGED (manifests byte-identical)
FRONTEND_CODE:                UNCHANGED
COMMIT_CREATED:               NO
PUSH_PERFORMED:               NO
VS9_REMOTE:                   af8f8185911af871fb1832e02fe9e5588bf228c0 (protected, verified)
MAIN:                         b245aaeb5cd308f6fd6dd01a4eae25412e0146bb (untouched)
WORKING_TREE:                 clean before document creation; after: ONLY this document untracked
VS11_STARTED:                 NO
```

**STOP after this plan. VS10 is NOT started. No implementation of any kind was performed; no document, code, test, migration, config, or README was modified; nothing was committed or pushed.**
