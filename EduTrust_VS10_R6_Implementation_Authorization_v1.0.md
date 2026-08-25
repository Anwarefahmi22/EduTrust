# EduTrust — VS10 R6 (Auth Completion) Implementation Authorization v1.0

**Document type:** READ-ONLY governance lock + implementation authorization package for VS10 candidate R6 (Auth completion: `POST /api/v1/auth/refresh` + `POST /api/v1/auth/revoke-sessions`). Converts the completed VS10 discovery (EduTrust_VS10_Discovery_Governance_And_Implementation_Plan_v1.0.md, sections D/J/L/M/N/O/P/V/W/X/Z) into an explicit, item-by-item authorized contract.
**No implementation performed.** No code, tests, migrations, frontend, dependencies, or prior documents modified. No commit, no push.
**Classification legend:** `APPROVED` (explicit in an approved document) · `CONVENTION` (established in-repo pattern, cited) · `CONTRACT GAP → LOCK` (spec silent; locked here with evidence + owner) · `UNKNOWN` (no source support — preserved)

---

# 1. Current protected Git state (verified 2026-08-25)

| Check | Result |
|---|---|
| Branch | `arena/01a03280-edutrust` |
| Local HEAD | `af8f8185911af871fb1832e02fe9e5588bf228c0` (VS9) |
| VS9 parent | `b73d8cec22779bed222727eae10107a951ecdee8` (VS8) — verified `HEAD^` |
| Remote `arena/01a03280-edutrust` | `af8f8185911af871fb1832e02fe9e5588bf228c0` — **VS9 protected (local = remote)** |
| Remote `main` | `b245aaeb5cd308f6fd6dd01a4eae25412e0146bb` — untouched |
| Working tree | ONLY `EduTrust_VS10_Discovery_Governance_And_Implementation_Plan_v1.0.md` untracked; 0 tracked modifications |

No unexpected modification existed; Phase 0 passed without STOP.

# 2. R6 source hierarchy

Applied precedence (Implementation Baseline + SM v1.1 Addendum §2 order), for the R6 surface:

| Source | Status | Role for R6 |
|---|---|---|
| API Architecture v1.0 §3.5 (Refresh) | APPROVED | The only approved refresh behavior contract (5 behavior bullets, quoted in §3 below) |
| API Architecture v1.0 §3.6 (Logout) | APPROVED | Existing convention source (session revocation + events) — already implemented in VS1 |
| API Architecture v1.0 §3.7 (Revoke sessions) | APPROVED | The only approved revoke-sessions contract (three revocable sets) |
| API Architecture v1.0 §27.1 (Rate limiting) | APPROVED | Explicitly lists "Refresh token" in the rate-limited scope |
| API Architecture v1.0 §27.2 (Auth hardening) | APPROVED | "Store refresh token hashes only. Rotate refresh tokens. Revoke sessions on suspicious replay." — the three R6 hardening mandates |
| Schema v1 `auth_sessions` + `security_event_type` + `idx_auth_sessions_user` | APPROVED | The data structure R6 operates on (verified column list, §8) |
| Security/Privacy Plan §9 ("Must audit: …") | APPROVED WITH CONDITIONS | Session-revocation security events must audit (logout pattern satisfies) |
| Engineering Governance | APPROVED WITH CONDITIONS | Slice-approval convention; §5 financial gate NOT triggered (zero financial surface, verified) |
| VS1 login/logout code (`services.py`, `auth.py`, `security.py`) | evidence (implemented, approved-slice) | The in-repo convention for tokens, hashing, session checks, events, response shapes |
| Sprint 1 report (rate-limiting note) | evidence | "DRF throttling foundation … per-scope policies not yet tuned" |
| VS10 Discovery & Governance & Implementation Plan (sections D/J/L/M/N/O/P/V/W/X/Z) | current planning record | Source of the R6 candidate definition, D1–D4 register, scope, and test estimates — extracted, not reinterpreted |

Superseded/irrelevant: no addendum touches auth; no state-machine document covers auth sessions (session lifecycle is a code-convention machine — recorded here as plan lock, §10); Post-VS6/Post-VS8 roadmap rows classify R6 as decision-light (HISTORICAL context only).

# 3. D1 — Refresh contract (`POST /api/v1/auth/refresh`)

Approved source text (API §3.5, verbatim):
> "POST /api/v1/auth/refresh — Behavior: Verify refresh token hash against active `auth_sessions` row. Rotate token. Store new hash. Revoke old token in the same transaction. If replay of old token is detected, revoke session family where supported and log `SECURITY_EVENT`."

Item-by-item classification:

| Item | Classification | Locked contract |
|---|---|---|
| Authentication requirement | CONVENTION (login_view pattern: `@authentication_classes([]) @permission_classes([])`) | Unauthenticated endpoint — it IS the re-authentication; the actor is derived from the session row found via the presented token's hash (the token identifies the session; the session identifies the user). No Authorization header required or accepted for identity (one may be present and ignored). |
| Request body | CONTRACT GAP → **LOCK D1.1** | `{ "refresh_token": "<string>" }` — single required field; field name matches the login response field that issues it (code precedent, `login()` returns `refresh_token`). |
| Required fields / validation | CONTRACT GAP → **LOCK D1.2** | Missing/empty/non-string `refresh_token` → **401** with the uniform refresh-failure code (LOCK D1.5) — matching the login precedent (`login()` maps an empty identifier to `AUTH_INVALID_CREDENTIALS` 401, not 400: no 400/401 distinction leak). Extra fields ignored. |
| Verification | APPROVED (§3.5 bullet 1) + CONVENTION (code) | `sha256(utf8(token))` (exactly `security.py hash_token`) → `SELECT … FROM auth_sessions WHERE refresh_token_hash = %s` (unique-indexed) → the row must be **active**: `revoked_at IS NULL` AND `expires_at > now()`. No other predicate (no device/IP binding — none exists in schema or spec; NOT invented). |
| Token rotation | APPROVED (§3.5 bullets 2–3) | Issue a new refresh token via `secrets.token_urlsafe(48)` (`generate_token`, code) and store its hash. |
| Refresh-token invalidation of the old token | APPROVED (§3.5 bullet 4: "Revoke old token in the same transaction") | The old token is invalidated **by hash replacement within the single rotation transaction** — after commit, the old hash matches no session row and is permanently inert. No separate "old token" record exists or is created (v1 schema has one hash per session — verified). |
| Session TTL on rotation | CONTRACT GAP → **LOCK D1.3** | Rotation **preserves the session's existing `expires_at`** (does NOT extend it). Rationale: §3.5 is silent on expiry; login sets `expires_at = now + REFRESH_TOKEN_TTL_DAYS` (30d, settings) at creation only; the conservative reading bounds total session lifetime to the original login + 30d regardless of refresh frequency (no indefinite extension by refresh). Documented as a lock, approvable. |
| New access token | CONVENTION (code: `make_access_token`) | New HS256 JWT `{sub, roles, sid, iat, exp}` — **same session id** (`sid`), `exp = now + JWT_ACCESS_TTL_SECONDS` (900s default). |
| Roles on rotation | CONVENTION (code: login re-reads `get_roles`) | Roles are **re-read from the database** at rotation (never copied from the prior token) — server-derived; a role change made between refreshes is picked up. |
| Response | CONTRACT GAP → **LOCK D1.4** | Standard envelope: `{ "data": { "access_token": str, "refresh_token": str, "expires_in": int }, "request_id": str }`. Fields mirror the login response **minus** `user_id`/`roles` (the client retains its local identity from login; minimal surface). `expires_in` = `JWT_ACCESS_TTL_SECONDS` (login precedent). |
| Error responses | CONTRACT GAP → **LOCK D1.5** | **One uniform 401** for every token-validation outcome: unknown hash (no row), revoked session, expired session, rotated-out (old) token, malformed token. Code: `AUTH_INVALID_REFRESH_TOKEN` (new error code — a contract detail of this lock, named for client handling; behavior is uniform 401 regardless). Message generic ("Invalid or expired refresh token.") — **no oracle**: the client cannot distinguish which class failed (anti-enumeration). No 400 for token problems (see D1.2); no 403/404 (no existence leak). |
| Session ownership | APPROVED (§3.5 "active auth_sessions row" — the row found IS the owner's; the lookup is by hash only) + CONVENTION (auth.py binds `id AND user_id` for JWTs) | The endpoint acts only on the session whose current hash matches; there is no user parameter in the contract, so cross-user targeting is structurally impossible. |
| Replay behavior | APPROVED intent (§3.5 bullet 5) — **detection limited by v1 schema; see §5 (D3) in full** | Under the authorized D3a baseline: a rotated-out token is undetectable *as the session's old token* (only the current hash is stored) → it fails verification like any unknown token → uniform 401; the session remains active on its current token; **no revocation and no security event is triggerable for rotation-replay under the v1 schema** (the spec's own "where supported" clause licenses this limitation; the D3b enhancement that makes it detectable is fully specified in §5 and requires a separate schema decision). |
| Audit / security events | APPROVED for replay (conditional — §5); CONVENTION for the rest (logout pattern) | Successful rotation: **no event** (LOCK D1.6 — spec silent; rotation is not a revocation; event noise would also leak refresh cadence). Revocation via revoke-sessions: per §4. Replay-detection event: only under D3b (§5). |
| Idempotency | CONVENTION (auth protocol) — see §9 | No `Idempotency-Key` header. Replay prevention is the rotation itself (the presented token is one-use) + the uniform-401 path. A second use of a rotated token is a *replay*, handled per §5 — not an idempotent 200-replay. This deliberately differs from the VS5/VS8/VS9 admin-mutation idempotency convention (documented, not automatic). |
| Concurrency | CONVENTION (row-lock pattern) → **LOCK D1.7** | The rotation transaction takes the `auth_sessions` row `FOR UPDATE` (single row; acyclic — a leaf object). Two concurrent refreshes with the same current token: exactly one 200 (rotates), the other 401 (its token is now rotated-out). No double rotation; the session ends active with exactly one live token. |
| Terminal behavior | CONVENTION (code: logout/`expires_at`) + APPROVED (§3.5 "active" predicate) | A session is terminal when `revoked_at IS NOT NULL` or `expires_at <= now()`: its current refresh token 401s, its access tokens 401 (`SESSION_REVOKED` via the existing per-request check), and there is **no un-revocation path** (none spec'd — not invented). |

**D1: CLOSED** (8 locks D1.1–D1.7 + the error-code naming; every lock cites its evidence; owner: Architecture Owner, recorded at slice approval).

# 4. D2 — Revoke-sessions contract (`POST /api/v1/auth/revoke-sessions`)

Approved source text (API §3.7, verbatim):
> "POST /api/v1/auth/revoke-sessions — Allows user to revoke: Current session / All other sessions / All sessions."

Item-by-item classification:

| Item | Classification | Locked contract |
|---|---|---|
| Actor | APPROVED ("Allows **user** to revoke") + CONVENTION (logout: authenticated, own session) | Any authenticated user (all 5 roles; the contract is user-scoped, not role-scoped — no role differentiation exists in §3.7 and none is invented). |
| Ownership | APPROVED (self-implied) + CONVENTION (auth.py `id AND user_id` binding; logout scopes by `user_id`) | The endpoint acts **only on the caller's own sessions** (`WHERE user_id = caller`). The request carries no user/session-id target fields, so cross-user revocation is structurally impossible. |
| Scope | APPROVED (§3.7 names exactly three sets) | `CURRENT` = the caller's current session (the `sid` from the access token). `OTHERS` = all of the caller's sessions except the current one. `ALL` = all of the caller's sessions, including the current one. |
| Request body | CONTRACT GAP → **LOCK D2.1** | `{ "scope": "CURRENT" \| "OTHERS" \| "ALL" }` — required, no default (a deliberate revocation should be explicit; the spec lists options without a default — NOT defaulted by invention). Unknown/missing/non-string `scope` → **400 VALIDATION_ERROR** (input validation, unlike token problems which are 401 — a scope error says nothing about any token/session). |
| Response | CONTRACT GAP → **LOCK D2.2** | `{ "data": { "revoked": <int> }, "request_id": str }` — `revoked` = number of sessions **actually** revoked by this call (0 for a no-op re-revocation). A count (not a list of session details): self-information only (the caller's own sessions), no detail leak. |
| Effect on current session | APPROVED (set 1) + CONVENTION (mechanism = logout's `UPDATE … SET revoked_at = now()` guarded by `revoked_at IS NULL`) | `revoked_at = now()` set for the target row(s) in one transaction. For `CURRENT`/`ALL`: the caller's access token stops working at the next request (existing per-request session check → 401 `SESSION_REVOKED`); the response to the in-flight request is still delivered (commit precedes response; natural consequence, no spec conflict). |
| Effect on other sessions | APPROVED (sets 2–3) | Same mechanism for the selected rows (`OTHERS` = `user_id = caller AND id <> current_sid`; `ALL` = `user_id = caller`). |
| Access-token invalidation | CONVENTION (existing `auth.py` per-request check — code-verified) | Automatic and immediate at next use: any access token whose session has `revoked_at IS NOT NULL` → 401 `SESSION_REVOKED`. No token blacklisting mechanism exists or is needed (the session row IS the authority). |
| Refresh-token invalidation | APPROVED (§3.5 "active" predicate applied to future refreshes) + CONVENTION (mechanism) | A revoked session is not **active** → any refresh attempt with its current token fails the active-row check → uniform 401 (D1.5). Automatic. |
| Replay behavior | CONVENTION (guarded UPDATE — logout pattern) | Re-revoking an already-revoked session is a **no-op** (guarded `UPDATE … WHERE revoked_at IS NULL`); no error, no double event (LOCK D2.3: security events are written **only for sessions actually revoked** — i.e., per row whose `revoked_at` transitioned from NULL. This refines the pre-existing logout behavior, which writes its event unconditionally; the existing logout is NOT modified by R6 — out of scope). |
| Authorization | APPROVED (self-service) | As actor row above. No admin session-management surface is spec'd anywhere → none is created (absence is a scope fact, not a test target). |
| Audit events | CONVENTION (logout pattern: `write_event("SECURITY_EVENT", "auth_session", session_id, …)`) | One `SECURITY_EVENT` event_ledger row per actually-revoked session (entity_type `auth_session`, entity = session id, metadata includes `event: TOKEN_REVOKED` + request_id — logout shape). |
| Security events | CONVENTION (logout pattern: `write_security_event("TOKEN_REVOKED", user_id=…, severity=1, metadata={request_id, session_id})`) | One `TOKEN_REVOKED` security event (existing enum value) per actually-revoked session, severity 1, actor = caller. Satisfies the Security/Privacy Plan "must audit" obligation for session revocation. |
| Idempotency | CONVENTION (auth protocol) — see §9 | No `Idempotency-Key` header; the guarded UPDATE is naturally idempotent at the DB level (second call flips 0 rows, returns `revoked: 0`, emits no events). |
| Concurrency | CONVENTION (single-statement guarded UPDATE; row locks) → **LOCK D2.4** | Two concurrent revoke calls: the guarded UPDATEs are each atomic; rows flip exactly once (first writer wins per row); the loser flips 0 → reports the smaller/zero count; no double events; no deadlock (single relation, no cross-object ordering). |

**D2: CLOSED** (4 locks D2.1–D2.4; owner: Architecture Owner).

# 5. D3 — Replay / session-family semantics (the core governance lock)

Trace of the existing implementation (every item code- or schema-verified in this session):

1. **What constitutes a refresh-token replay?** A presentation of a refresh token whose hash no longer matches the current `refresh_token_hash` of its session because a newer rotation replaced it — i.e., a **rotated-out ("old") token** re-presented. (§3.5: "If replay of old token is detected …" — APPROVED term "old token"; the rest is this lock.)
2. **How is a refresh token identified?** By its **SHA-256 hex hash** (`hash_token`, `security.py:22`) against `auth_sessions.refresh_token_hash` (`UNIQUE` → unique index). The raw token (`secrets.token_urlsafe(48)`, `security.py:18`) is returned only at issuance and never stored. (CONVENTION/code; §27.2 "Store refresh token hashes only" already satisfied by login.)
3. **Is there a session identifier?** Yes — `auth_sessions.id` (UUID PK); it is embedded in every access token as the `sid` claim (`make_access_token`, `auth.py:22`) and is what the per-request check binds (`WHERE id = %s AND user_id = %s`, `auth.py:66-70`).
4. **Is there a session family identifier?** **No — verified absence.** No column on `auth_sessions` (full column list verified §8), no JWT claim, no code reference, no index; repository-wide scan for family/previous-token constructs: zero hits. Each login creates an independent session row; sessions are related only by `user_id`.
5. **Is token rotation already implemented?** **No.** No `/auth/refresh` route exists (urls scan: zero refresh/revoke hits); no hash-replacement code exists; refresh tokens issued at login are currently stored-but-unusable (VS10 plan §J, re-verified).
6. **What happens when an old refresh token is reused (today)?** Nothing is possible — the refresh endpoint does not exist; there is no code path that consumes a refresh token at all. (Verified.)
7. **Does replay revoke one token or the entire session family?** Spec: "revoke session family **where supported**" (§3.5, verbatim). Schema-supported extent: **a single session only** (family unsupported — item 4; single-session revocation supported via `revoked_at`). **LOCK D3.1: revocation scope on detected replay = the single session whose token was replayed; no family mechanism is created.**
8. **What security event is emitted on detected replay?** **LOCK D3.2: `SUSPICIOUS_ACTIVITY`** (existing `security_event_type` value — the only existing value whose semantics fit a detected credential replay; no new enum value is invented) + one `SECURITY_EVENT` event_ledger row (logout pattern, entity = the revoked session, metadata: `event: SUSPICIOUS_ACTIVITY`, request_id, session_id). **Caveat (the crux):** under the v1 schema this branch is **triggerable only if a replay is detectable** — see items 9/12 and the D3a/D3b fork below.
9. **What HTTP status is returned (replay and all invalid cases)?** **LOCK D3.3: uniform 401** (`AUTH_INVALID_REFRESH_TOKEN`, D1.5) — identical for unknown, rotated-out, revoked-session, and expired-session tokens. No status differentiation (anti-oracle, consistent with D1.5).
10. **What information is exposed to the client?** LOCK D3.4: the error code + generic message only. Never: which session, that a session exists for that user, whether the token was "rotated" vs "unknown" vs "revoked", any session id, any user attribute. (Enforced by the uniform-401 design; testable, §11.)
11. **Can replay be detected concurrently?** Two concurrent presentations of the same **current** token (double-tab): serialized by the row `FOR UPDATE` (D1.7) — first rotates (200), second presents the now-rotated-out token → uniform 401; session stays active on the new token. A stolen **old** token racing the legitimate current token: the legitimate refresh succeeds; the old token 401s — and under the D3a baseline it is **not identifiable as that session's old token** (item 12), so no forced revocation/event occurs; under D3b it IS identifiable → the specified revocation + `SUSPICIOUS_ACTIVITY` fires (killing the session per §3.5 — the legitimate client re-authenticates; that is the approved behavior).
12. **What database structures enforce this?** `auth_sessions` as built in v1: PK `id`; `refresh_token_hash TEXT NOT NULL UNIQUE` (the lookup + one-hash-per-session fact); `revoked_at` (revocation); `expires_at` + `CHECK (expires_at > created_at)` (expiry); `user_id` FK CASCADE (ownership/cleanup); `idx_auth_sessions_user (user_id, expires_at)` (revoke-sessions scans). **No trigger enforces rotation** (service-level transaction); the per-request JWT→session check (`auth.py`) enforces access-token death on revocation. **The single structural limitation: there is exactly one hash column per session — a rotated-out hash is overwritten, not retained — so "this hash WAS this session's current hash" is unrecoverable after rotation.**

### The D3 fork (surfaced, not silently resolved)

The approved spec (§3.5 bullet 5 + §27.2 "Revoke sessions on suspicious replay") assumes replay is **detectable**; the approved v1 schema makes rotated-out-token detection **impossible** without retaining the previous hash. Two fully-specified dispositions:

- **D3a — authorized baseline (NO schema change):** strict one-use rotation; the old token dies by hash replacement; a rotated-out presentation is observationally identical to an unknown token → uniform 401, session unaffected, no event. §3.5 bullet 5 is implemented **to the extent the v1 schema supports** — precisely the extent its own "where supported" clause grants (family: unsupported → single session; rotated-out detection: unsupported → no distinguishable detection). **Compliance note (recorded in the slice report, not hidden):** the forced-revocation + `SECURITY_EVENT` branch is not triggerable under v1; the security delta vs full detection is bounded — a stolen rotated-out token is already inert (it 401s and gains nothing); what D3a forgoes is the forensic event and the defensive whole-session revocation on a replay sighting.
- **D3b — spec-completing enhancement (ONE nullable column; separate schema decision required):** add `auth_sessions.previous_refresh_token_hash TEXT NULL` (one small, backward-compatible migration; no data migration; no trigger changes). Rotation then: `previous := current; current := new`. Verification: hash == current → rotate (as D3a); **hash == previous AND session active → DETECTED REPLAY → revoke that session (`revoked_at = now()`) + `SUSPICIOUS_ACTIVITY` + uniform 401** (the §3.5 branch, single-session per D3.1); else → uniform 401. This makes §3.5 bullet 5 + §27.2 fully implementable (family still "not supported" — unchanged, licensed by the same clause).

**LOCK D3.5 (the governance decision itself):** **D3a is the authorized baseline for R6** (keeps the slice migration-free, consistent with every slice to date and with the VS10 plan's `SCHEMA_CHANGE_REQUIRED: NO`). **D3b is recorded as the approved-scope-completing alternative**: if the approver judges §3.5 bullet 5 unconditionally mandatory, R6 proceeds with exactly the D3b migration (spec complete in this document; Database Owner + operator sign the schema decision **before** implementation). No third option exists within the no-invention constraint.

**D3: CLOSED as a lock** — disposition: D3a baseline authorized; D3b specified + owned (Database Owner + operator) as the escalation path; replay semantics are fully known under both options; nothing is left as a silent UNKNOWN. (If the approver rejects D3a, the decision flips to D3b — a one-line change, no other contract in this document moves.)

# 6. Rate-limit status (D4 — informational)

| Question | Finding (source-verified) |
|---|---|
| Does R6 require rate limiting in DEV? | §27.1 (APPROVED) explicitly lists "Refresh token" among rate-limited operations → **yes, by approval** — no new decision needed; the endpoint is in scope of the approved list. |
| Existing mechanism? | **Yes** — DRF global defaults are configured in `settings.py`: `DEFAULT_THROTTLE_CLASSES = [AnonRateThrottle, UserRateThrottle]`, `DEFAULT_THROTTLE_RATES = {anon: 10000/min, user: 10000/min}` (verified, `settings.py:69-70`). No per-view throttle classes exist anywhere (views scan: zero) — the Sprint 1 report's "DRF throttling foundation … per-scope policies not yet tuned" is confirmed. The new endpoints inherit the global throttle automatically (framework default). |
| Explicitly deferred to staging? | Per-scope tuning is deferred (Sprint 1 evidence); the approval to rate-limit refresh exists now (§27.1); no staging-only gate is documented for it. |
| New dependency required? | **No** — DRF throttling is part of the installed DRF (no new package). |
| Disposition | **D4 = INFORMATIONAL, non-blocking.** R6 applies the existing global foundation unchanged and records per-scope tuning as a STAGING work item (inventing thresholds in-slice is forbidden — none are approved). No test asserts specific 429 behavior (thresholds are untuned — §11). |

# 7. Security matrix (exact; only roles that exist)

Verified `role_name` enum (schema v1, line 19): **PARENT, TEACHER, ADMIN, OPS, SUPPORT** — five roles. **There is no SAFETY role** in the schema, the API role matrix, or the code (SAFETY exists only as a dispute *category*); no SAFY row is invented below.

| Endpoint | anonymous | PARENT | TEACHER | SUPPORT | OPS | ADMIN |
|---|---|---|---|---|---|---|
| `POST /auth/refresh` | DENY → 401 (uniform refresh-failure; no header/token present = unknown-token class) | ALLOW (self; own session via token) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) |
| `POST /auth/revoke-sessions` | DENY → 401 `AUTH_REQUIRED` (logout-view convention for unauthenticated) | ALLOW (self; own sessions only) | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) |

The contract is **user-scoped, not role-scoped** (§3.7 "Allows user to revoke"; §3.5's verification is token-based) — all five roles have identical self-service rights; no role gains a privilege over another's sessions (structurally impossible: no user/session-id parameters exist in either contract).

Cross-cutting verifications (all source-traceable, none inferred):

- **Ownership:** refresh — the token's hash identifies exactly one session row; the actor IS that row's user (no parameter to point elsewhere). Revoke — `WHERE user_id = caller` (D2); `idx_auth_sessions_user` supports it. Cross-user targeting: structurally impossible in both contracts.
- **Privilege escalation:** none introduced — no role grants, no elevation path; roles are re-read server-side at rotation (D1), never client-supplied (the refresh request carries no roles claim; the access token's `roles` are re-issued from the DB).
- **Uniform error behavior:** token problems → one 401 code/class across all five token-failure classes (D1.5/D3.3/D3.4); scope problems → 400 (input only); unauthenticated revoke → 401 `AUTH_REQUIRED` (logout convention). No existence oracle (no 404 on unknown session/token; no "session not found" vs "token expired" distinction).
- **Token leakage:** raw refresh tokens appear only in issuance responses (login/refresh) — never in logs, events, or error bodies (events carry session ids + request ids only — logout pattern). Access tokens: standard bearer handling; rotation supersedes, revocation kills.
- **Refresh-token leakage:** hash-only storage (existing, §27.2-satisfied); the presented token is hashed in-memory for lookup and discarded; not persisted (no new storage).
- **Session enumeration:** a user can only ever act on their own sessions; the revoke response is a **count** (D2.2), not a list — no session metadata, device, or IP exposure (those columns exist but are never returned by R6).
- **Replay information leakage:** uniform 401 — a replier learns only "not accepted", never "this was a rotated token" (under D3a nothing distinguishes it; under D3b the 401 is likewise uniform — the revocation + event are server-side).
- **Audit coverage:** revocations → `TOKEN_REVOKED` security event + `SECURITY_EVENT` ledger row per session (D2); replay (D3b) → `SUSPICIOUS_ACTIVITY` + row (D3.2); successful rotation → no event (D1.6, documented); failures → no event under D3a (uniform 401 class; LOGIN_FAILED is a login-specific event and is NOT repurposed for refresh — no invention).

# 8. Database impact

**SCHEMA_CHANGE_REQUIRED = NO** (D3a authorized baseline) — **or exactly one nullable column under the D3b option** (`auth_sessions.previous_refresh_token_hash TEXT NULL`; no data migration, no trigger, no index beyond what a future lookup would use — D3b detection reuses the existing hash-unique lookup pattern against the previous column; that index question is part of the D3b schema decision, not pre-built).

Existing structures supporting R6 (all verified in `database/migrations/001_edutrust_schema_v1.sql` + code):

| Structure | Exact definition | R6 use |
|---|---|---|
| `auth_sessions.id` | `UUID PRIMARY KEY DEFAULT gen_random_uuid()` | session identity; JWT `sid` binding |
| `auth_sessions.user_id` | `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE` | ownership scoping (revoke `WHERE user_id = caller`) |
| `auth_sessions.refresh_token_hash` | `TEXT NOT NULL UNIQUE` | refresh verification lookup (unique → unique index) |
| `auth_sessions.expires_at` | `TIMESTAMPTZ NOT NULL` + `CHECK (expires_at > created_at)` | "active" predicate; TTL preservation on rotation (D1.3) |
| `auth_sessions.revoked_at` | `TIMESTAMPTZ` (nullable) | revocation (revoke-sessions; D3b replay revocation); per-request JWT check |
| `auth_sessions.device_label / ip_address / user_agent` | nullable metadata | written at login (existing); **never returned or filtered by R6** (no binding invented) |
| `idx_auth_sessions_user` | `ON auth_sessions(user_id, expires_at)` | revoke-sessions scans (`user_id` equality + optional active filter) |
| `security_event_type` | enum incl. `TOKEN_REVOKED`, `SUSPICIOUS_ACTIVITY`, `LOGIN_FAILED`, … | D2/D3 events — existing values only |
| `event_ledger` | existing append-only audit table + `SECURITY_EVENT` event_type | per-revocation / per-replay ledger rows (logout pattern) |

No migration file was created by this task; none is required under D3a. FK integrity: `users` CASCADE already covers user deletion; no new FKs. No new constraint, trigger, or index under D3a.

# 9. Idempotency model

Compared against the VS5/VS8/VS9 convention (`api_idempotency_keys` + `_idempotency_begin/_complete` on state-changing **admin** mutations: create/approve/reject/cancel/reconcile/resolve):

- The approved R6 contract contains **no idempotency requirement** (§3.5/§3.7 are silent; A-63-style "recommended" notes exist only for the unapproved R10 screen — not for R6).
- The existing **auth** surface (login/logout — VS1, approved and implemented) does **not** use `Idempotency-Key`: logout is a session-bound guarded UPDATE (naturally idempotent); login mints a new session per call (inherently non-replayable — a "replayed" login just creates another session, which the revoke-sessions surface then governs).
- **R6 follows the auth protocol, not the admin-mutation convention** (per the governance instruction: do not add idempotency merely because other mutations use it). The replay-prevention mechanisms are: (a) **rotation** — each refresh token is one-use; replacement in the same transaction is the invalidation; (b) **guarded UPDATE** — revocation flips each row at most once; (c) **uniform 401** — a replayed/old token is rejected without side effects (D3a) or with the specified detection+revocation (D3b); (d) D3b-only: **previous-hash detection** (the only state-based replay detector, and it requires the D3b column).
- Consequence documented (not a gap): a network retry of a **successful** refresh does NOT return the original 200 — the first attempt already rotated; the retry's token is rotated-out → 401. The client library (X.14 of the VS10 plan) handles this by treating post-rotation 401s as "re-login or use the stored new token"; a single in-flight refresh guard (per client) prevents the common double-send. This is the standard one-use-token trade-off, fully specified here, and is why the client hook — not an idempotency key — is the authorized replay defense.

# 10. Concurrency model

Race conditions R6 must survive, with locked expected outcomes (derived from the row-lock convention + §3; no invented states):

| # | Race | Locked outcome | Basis |
|---|---|---|---|
| CR-1 | Two simultaneous refreshes presenting the **same current token** T1 | Serialized on the session row (`FOR UPDATE` in the rotation tx, D1.7). Exactly **one 200** (rotates T1→T2); the other **401** (T1 now rotated-out). Final state: session active, exactly one live token (T2), one `USER_…`-free rotation (no events, D1.6). No double rotation, no split-brain hashes. | D1.7 + §3.5 bullets 2–4 |
| CR-2 | Refresh vs `revoke-sessions CURRENT` on the same session | Serialized on the same row. If refresh wins: rotation commits, then revoke flips `revoked_at` → session dead, both T1 and T2 inert (next uses 401). If revoke wins: refresh's "active row" check fails → 401. Either order: a single consistent terminal-or-active state; no state where a revoked session holds a live token (access check + active-row predicate both read `revoked_at`). | D1/D2 + auth.py check |
| CR-3 | Stolen **old** token T0 vs legitimate current T1 (replay race) | Legitimate refresh rotates T1→T2 (200). T0 presentation → 401 (uniform). **D3a:** nothing further (T0 undetectable as session's old token; session stays active on T2 — the attacker's T0 is inert). **D3b:** T0 == `previous_refresh_token_hash` → DETECTED REPLAY → session revoked + `SUSPICIOUS_ACTIVITY` + 401 (legitimate client re-authenticates — the specified behavior). | §3.5 bullet 5 + D3a/D3b |
| CR-4 | Concurrent `revoke-sessions ALL` ×2 (same user) | Each call's guarded UPDATE is atomic; each row flips exactly once (first writer wins per row); the second call flips 0 (or fewer) → `revoked` count reflects actual flips; **no duplicate events** (events per actually-revoked row, D2.3). | D2.3/D2.4 + guarded UPDATE |
| CR-5 | Cross-user interleaving (user A's ops vs user B's ops) | No shared rows except none (all queries scoped by user_id or by unique hash — a hash belongs to exactly one session of one user); no cross-user lock contention beyond normal DB behavior; no cross-user effect possible. | D2 ownership + unique hash |
| — | Deadlock potential | **None:** every R6 transaction locks a single relation's row(s) owned by one user; no cross-object ordering exists (auth_sessions is a leaf — it locks no booking/payment/refund/dispute/payout row), so it cannot form a cycle with the VS5/VS8/VS9 orders (session→payment; payment→refund→booking; dispute→payment→booking). | lock-order audit (VS10 plan §P, re-verified) |

# 11. Test authorization matrix (review of the VS10 plan §R inventory — no tests written)

Rule applied: a test is **VALID** iff every assertion maps to an APPROVED behavior or a LOCK in this document; **TESTS_REQUIRING_DECISION** = tests whose assertions exist only under the D3b option; **TESTS_NOT_SUPPORTED_BY_SOURCE** = assertions with no source support (removed from the authorized inventory).

| Authorized test (category — count) | Maps to | Status |
|---|---|---|
| Service — refresh happy path: new hash stored, old token 401s after, new token rotates again, same session id in both access tokens, roles re-read from DB | D1 (APPROVED bullets 2–4 + D1 locks) | VALID |
| Service — rotation preserves `expires_at` (no extension) | D1.3 lock | VALID |
| Service — uniform 401 class: unknown hash / revoked session / expired session / rotated-out token / malformed token all → same 401 code; message carries no distinguishing detail | D1.5, D3.3, D3.4 | VALID |
| Service — cross-user token (user A's token, presented by B's context) → uniform 401 (no existence leak, no 404/403 variant) | D1.5 + ownership (token identifies its own session) | VALID |
| Service — missing/empty `refresh_token` → 401 (not 400) | D1.2 lock | VALID |
| Service — no event written on successful rotation (event_ledger + security_events unchanged) | D1.6 lock | VALID |
| Service — revoke CURRENT: `revoked_at` set, `revoked: 1`, access token 401s next request, refresh 401s, TOKEN_REVOKED + SECURITY_EVENT rows present | D2 (APPROVED set 1 + convention events) | VALID |
| Service — revoke OTHERS (2 sessions): current survives, other revoked, `revoked: 1` | D2 (set 2) | VALID |
| Service — revoke ALL: both revoked, `revoked: 2`, two event pairs | D2 (set 3) | VALID |
| Service — revoke no-op (re-revocation): `revoked: 0`, no new events, 200 | D2.3 lock | VALID |
| Service — bad scope (unknown/missing/non-string) → 400 VALIDATION_ERROR | D2.1 lock | VALID |
| Service — terminality: a revoked session cannot be "un-revoked" by any R6 call; expiry path 401s | D1 terminal + code convention | VALID |
| Service — login integration: a login-issued refresh token is usable exactly once | D1 + login (code) | VALID |
| Authorization — anonymous refresh → 401 uniform; anonymous revoke → 401 AUTH_REQUIRED | §7 matrix (logout convention) | VALID |
| Authorization — ownership: no request shape can target another user's sessions (contract-absence assertion: endpoint operates solely on caller's rows) | D2 ownership | VALID |
| Idempotency/replay — rotated token's second use → 401 (not a 200-replay); no `Idempotency-Key` header has any effect on either endpoint | §9 model | VALID |
| Concurrency — CR-1 double-refresh same token: exactly one 200 + one 401, one live token (DB-asserted) | CR-1 lock | VALID |
| Concurrency — CR-2 refresh vs revoke race: consistent final state in both interleavings (DB-asserted) | CR-2 lock | VALID |
| Concurrency — CR-4 double revoke-ALL: each row flipped once, no duplicate events (DB-asserted) | CR-4 lock | VALID |
| Security — enumeration: responses contain no session id / user attribute / existence signal beyond the uniform code + self-count | D3.4 + D2.2 | VALID |
| Security — events carry session id + request id, never the token (DB-asserted on event rows) | §7 token-leakage | VALID |
| **D3b-ONLY:** detected replay (previous-hash match, active session) → session revoked + SUSPICIOUS_ACTIVITY + 401 | D3b spec (§5) | **TESTS_REQUIRING_DECISION** (2 tests; authorized iff D3b is chosen with its schema decision) |
| **D3b-ONLY:** CR-3 under D3b (stolen old token vs legitimate current → session revoked, event written) | D3b + CR-3 | **TESTS_REQUIRING_DECISION** (1 test) |
| ~~Rate-limit: refresh endpoint returns 429 above a threshold~~ | §27.1 approves the scope; thresholds untuned (Sprint 1) — no approved threshold to assert | **NOT_SUPPORTED_BY_SOURCE — REMOVED** (framework-level throttling is inherited automatically; asserting it is optional smoke at most, not a gate test) |
| ~~Absence of admin session-management endpoints (404 probes)~~ | No approved admin surface exists; testing absence of unapproved routes asserts nothing about the contract | **NOT_SUPPORTED_BY_SOURCE — REMOVED** |
| ~~Exact error-message string matching~~ | Messages are implementation text; the contract locks the code + uniformity, not wording | **NOT_SUPPORTED_BY_SOURCE — REMOVED** (uniformity IS tested — code/class level) |

Authorized inventory: **~22 VALID service/authorization/idempotency/concurrency/security tests** (within the plan's 25–32 band once E2E-level service assertions are counted) + **3 TESTS_REQUIRING_DECISION (D3b-gated)** + **3 categories REMOVED as unsupported**. The plan's "~25–32" estimate stands with the D3b variants included; under D3a the authorized count is ~22–25 + E2E.

# 12. E2E authorization matrix (review of the VS10 plan §X.16 scenarios — none executed or modified)

| Scenario | Contract basis | Classification |
|---|---|---|
| S1 login → refresh → old token dead (401) / new token live (200) → second rotation | §3.5 bullets 1–4 + D1 | **READY** |
| S2 double rotation chain (T0→T1→T2; each predecessor 401s) | D1 + §3.5 | **READY** |
| S3 replay detection (rotated token re-presented → **session revoked + SUSPICIOUS_ACTIVITY visible via admin security-events surface**) | §3.5 bullet 5 — detectable **only under D3b** | **CONDITIONAL** — under the D3a baseline this scenario runs in its baseline form (rotated token → uniform 401, session stays active, **no** event — asserting the documented limitation); the revocation+event variant is authorized iff D3b is chosen |
| S4 revoke CURRENT (token dies; refresh 401s; events present) | §3.7 set 1 + D2 | **READY** |
| S5 revoke OTHERS with two live sessions | §3.7 set 2 + D2 | **READY** |
| S6 revoke ALL | §3.7 set 3 + D2 | **READY** |
| S7 expired-session refresh → 401 (test sets `expires_at` in the past via direct DB — a test-harness privilege, not an app path) | §3.5 "active" predicate | **READY** |
| S8 anonymous + cross-user contexts → 401s, uniform, no oracle | §7 matrix + D3.4 | **READY** |
| S9 full-suite coexistence (no regression of the 197-test baseline alongside the new tests) | acceptance gate | **READY** |

Result: **7 READY, 1 CONDITIONAL (S3, D3-dependent — both its forms are specified), 0 BLOCKED.**

# 13. Exact implementation scope (IN SCOPE)

Only explicitly approved R6 functionality:

1. `POST /api/v1/auth/refresh` — service + view + route, exactly per §3 (D1 locks D1.1–D1.7): token-verified rotation (same session, roles re-read, `expires_at` preserved), uniform-401 handling, no events on success, row-locked transaction.
2. `POST /api/v1/auth/revoke-sessions` — service + view + route, exactly per §4 (D2 locks D2.1–D2.4): `scope` ∈ {CURRENT, OTHERS, ALL} over the caller's sessions; guarded revocation; per-actually-revoked `TOKEN_REVOKED` + `SECURITY_EVENT`; `revoked` count response.
3. D3a baseline replay handling: uniform 401 for all non-current tokens (no detection state, no extra revocation) — with the §5 compliance note recorded in the slice report. (If D3b is chosen by the approver: the one-column migration + previous-hash detection + revocation + `SUSPICIOUS_ACTIVITY`, per §5 D3b — and nothing more.)
4. Frontend client hook: `frontend/lib/api.ts` refresh-on-expiry (single in-flight refresh; one retry; second failure → logged-out state) — no new screens, no console changes (no wireframe specifies session UI; none invented).
5. Authorized tests (§11 VALID set) in new files + standalone E2E (§12 READY scenarios + S3 in its baseline form) in a new file — per the slice test convention.
6. Slice deliverables per established convention: VS10 implementation/test/E2E reports, Dependency Audit v1.9, README VS10 section, this authorization document carried in the commit.

# 14. Explicit exclusions (OUT OF SCOPE — anything not in §13)

- **Real payment / real refund / real payout** — FORBIDDEN (gates not approved; `REAL_*` flags stay false; no R6 surface touches any money object — verified zero financial surface, §2/§16).
- **R10 suspension semantics** — any `users.status` behavior, suspend/reactivate endpoints, or suspension effects (spec UNKNOWN — VS10 plan §F; untouched).
- **R11 ledger administration** — no ledger reads/reversals/adjustments (contract "Suggested"-only — VS10 plan §G).
- **R4 cancellation / R5 reschedule / R14 report edit** — no booking/session mutation of any kind.
- **Production UI** — no screen (R17 phase; the only spec'd screen in this domain, A-63, is R10/R17 material and is not built).
- **New infrastructure / services / queues** — none (no cron, no worker, no cache layer; DRF throttling is existing framework config).
- **New dependencies** — none (DRF/JWT/psycopg already installed; no package added).
- **Password change/reset, MFA/2FA, device management, account deletion flows** — not spec'd (§27.1 "if implemented" = not implemented; none invented).
- **Admin session-management endpoints** — none spec'd; none created.
- **Session "family" mechanisms** — D3.1 lock: unsupported by schema, not invented.
- **New event or security-event enum values** — existing values only (`TOKEN_REVOKED`, `SUSPICIOUS_ACTIVITY`, `SECURITY_EVENT`).
- **Modifying any pre-existing behavior** — including the existing logout's unconditional event (noted in D2.3 as a refinement that applies to the NEW endpoint only; logout is untouched), login, JWT decoding, or any VS1–VS9 code region.
- **Migrations** — none under D3a; the single D3b column migration exists ONLY if the approver elects D3b with the signed schema decision.
- **Rate-limit threshold tuning** — D4: STAGING work item, not in-slice.

# 15. Decision register (final)

| ID | Decision | Evidence | Current status | Recommended disposition | Blocking? | Owner |
|---|---|---|---|---|---|---|
| D1 | Refresh contract (8 sub-locks D1.1–D1.7 + error-code naming) | §3.5 (APPROVED behavior) + login/logout code conventions + uniform-401 security practice | **CLOSED** — fully specified in §3 | Implement as locked; approver may amend sub-locks at slice approval (all are contract-shape, not behavior-invention) | NO | Architecture Owner |
| D2 | Revoke-sessions contract (4 sub-locks D2.1–D2.4) | §3.7 (APPROVED three sets) + logout code convention (guarded UPDATE, TOKEN_REVOKED, SECURITY_EVENT) | **CLOSED** — fully specified in §4 | Implement as locked | NO | Architecture Owner |
| D3 | Replay / session-family semantics (locks D3.1–D3.5) | §3.5 bullet 5 verbatim ("where supported" clause) + §27.2 + verified schema absence of family/previous-hash (item 4/12, §5) + code trace (no rotation exists) | **CLOSED as a lock** — D3a baseline authorized; D3b fully specified as the alternative | **D3a** (migration-free; §3.5 implemented to schema-supported extent; compliance note recorded). If the approver deems bullet 5 unconditional → flip to **D3b** (one nullable column + detection + revocation + SUSPICIOUS_ACTIVITY; no other contract changes) | NO for the D3a baseline (the flip to D3b requires the Database Owner + operator schema sign-off — a separate, named decision, not a silent one) | Database Owner + operator (flip decision); Security Owner (D3.2 event choice) |
| D4 | Rate limiting | §27.1 (APPROVED scope incl. "Refresh token") + settings.py global DRF throttle (verified) + Sprint 1 (untuned per-scope) | **INFORMATIONAL** — non-blocking | Apply existing global foundation unchanged; record per-scope tuning as STAGING work item; no thresholds invented | NO | Ops Lead (later, STAGING) |

Open UNKNOWNs remaining after this lock: **none within R6's declared scope** (the D3a/D3b choice is a recorded decision fork with both sides fully specified — not an UNKNOWN; R10's ~15 suspension UNKNOWNs remain outside R6, untouched, per §14).

# 16. Acceptance gates (R6)

1. `POST /auth/refresh` + `POST /auth/revoke-sessions` implemented exactly per §§3–4 (locks D1.1–D2.4; D3a baseline per §5) — additive routes only.
2. Rotation atomicity: hash replacement + access-token re-issue in one transaction; old token inert after commit (DB-asserted).
3. Uniform-401 class: all token failures indistinguishable (code + shape); no oracle (DB/API-asserted).
4. Revocation: per-scope correctness (CURRENT/OTHERS/ALL), guarded no-op, per-actually-revoked events, self-count response (DB-asserted).
5. Race outcomes CR-1/CR-2/CR-4 hold (concurrency tests, DB-asserted).
6. **No schema change** (migration chain v1→v1.4 byte-identical) under D3a — or, iff D3b is elected, exactly the one authorized column and the D3b behavior, nothing more.
7. Full suite: 197 baseline + authorized R6 tests (§11) green; 0 failed / 0 skipped; standalone R6 E2E (§12 READY + S3-baseline) all PASS.
8. Boundary assertions: REAL PAYMENT/REFUND/PAYOUT FORBIDDEN; REFUND_ISSUED = 0 rows (unchanged); provider boundary `OTHER`-only (unchanged); `users.status` untouched (R10 boundary); no ledger object touched.
9. Scope audit by `git diff` against the VS10 base: only §13 files; §14 exclusions absent; no DDL (D3a); no secrets; no generated artifacts tracked.
10. Deliverables: VS10 implementation/test/E2E reports + Dependency Audit v1.9 (no new findings expected; manifests byte-identical) + README section + this document; D1–D3 dispositions recorded verbatim in the slice report (including the §5 compliance note under D3a).
11. Single commit, parent = current HEAD (`af8f818`), **no push until instructed**.

# 17. Stop conditions

- Any financial invariant failure or any touch of a ledger/payout/refund/payment object → STOP (zero financial surface is a gate, not a hope).
- Any need beyond the declared scope (including any `users.status`/suspension behavior, any ledger surface, any booking/session mutation) → STOP and return to governance (that is R10/R11/R4, not R6).
- D3b elected without the Database Owner + operator schema sign-off → STOP (migration without the signed decision is forbidden).
- Any regression in the 197-test baseline or in VS8/VS9 surfaces (refund E2E 53/53, dispute E2E 75/75) → STOP.
- Any discovery that an R6 assertion rests on a source this document did not cite → STOP and classify (do not silently adopt).
- Any approved-source conflict discovered during implementation → STOP and report (do not reconcile silently).
- Any red full-suite or E2E result → do not commit.

# 18. Final authorization verdict

Readiness check against the required criteria:

| Criterion | Verdict | Basis |
|---|---|---|
| D1 resolved | YES | §3 — 8 sub-locks, each cited; CLOSED |
| D2 resolved | YES | §4 — 4 sub-locks, each cited; CLOSED |
| D3 resolved | YES (as a lock) | §5 — D3a baseline authorized + D3b fully specified alternative; replay semantics known under both; the only fork is a named, owned, non-silent decision |
| No blocking UNKNOWN remains | YES | §15 — zero open UNKNOWNs within declared scope |
| Schema impact known | YES | §8 — NO (D3a) / exactly one nullable column (D3b) |
| Security behavior known | YES | §7 — matrix + six cross-cutting verifications, all source-traceable |
| Replay semantics known | YES | §5 — 12-item trace + locked outcomes + the detection-limitation stated with its spec license ("where supported") |
| Test contract sufficient | YES | §11 — every authorized test maps to an APPROVED behavior or a lock; unsupported categories removed; D3b variants gated |
| No financial ambiguity | YES | zero financial surface — no ledger/payout/refund/payment object in scope or in any R6 code path (§13/§14/§16.8) |

```text
R6_IMPLEMENTATION_READY:  YES — at the declared scope (D3a baseline). One named decision fork (D3a→D3b) is recorded, owned, and non-silent; choosing D3b requires the Database Owner + operator schema sign-off before implementation. No other decision, UNKNOWN, or gate stands between this authorization and implementation.

R6_AUTHORIZED_SCOPE:      POST /api/v1/auth/refresh (D1-locked) + POST /api/v1/auth/revoke-sessions (D2-locked) + D3a replay handling (uniform 401; §5 compliance note recorded) + lib/api.ts refresh-on-expiry hook + authorized tests/E2E (§11/§12) + slice deliverables (§13.6). Under an elected D3b: + the single previous-hash column + detection/revocation/SUSPICIOUS_ACTIVITY per §5 D3b — and nothing else.

R6_ALLOWED_FILES:         backend/edutrust_api/services.py (ADDITIVE: refresh + revoke-sessions service functions; no pre-existing line modified)
                          backend/edutrust_api/views.py (ADDITIVE: refresh_view + revoke_sessions_view)
                          backend/edutrust_api/urls.py (ADDITIVE: 2 route lines)
                          frontend/lib/api.ts (refresh-on-expiry hook; no UI)
                          tests/test_auth_completion.py (NEW)
                          tests/test_auth_completion_concurrency.py (NEW)
                          tests/e2e_auth_completion.py (NEW)
                          EduTrust_DEV_Vertical_Slice_10_Implementation_Report_v1.0.md (NEW)
                          EduTrust_DEV_Vertical_Slice_10_Test_Report_v1.0.md (NEW)
                          EduTrust_DEV_Vertical_Slice_10_E2E_Report_v1.0.md (NEW)
                          EduTrust_DEV_Dependency_Audit_v1.9.md (NEW)
                          README.md (VS10 section, additive)
                          EduTrust_VS10_R6_Implementation_Authorization_v1.0.md (this document, carried)
                          [D3b ONLY, if elected + signed] database/migrations/006_edutrust_auth_sessions_previous_hash.sql (NEW, single nullable column)

R6_FORBIDDEN_FILES:       every file not listed above — in particular: migrations 001–005 (byte-identical), all VS1–VS9 test files, backend/edutrust_api/{payments,auth,security,errors,permissions}.py, requirements.txt, package.json, package-lock.json, all state-machine/addendum/PRD/API documents, frontend/app/** (no screens), the VS10 discovery plan, and any pre-existing line in services.py/views.py/urls.py/lib/api.ts outside the additive regions.

R6_ACCEPTANCE_GATES:      §16 (11 gates), verbatim.

R6_STOP_CONDITIONS:       §17 (7 conditions), verbatim.
```

**No implementation has been started by this document.** It authorizes; it does not execute.

# 19. Self-audit

- No UNKNOWN silently resolved — the D3 detection limitation is stated with its source license (§3.5 "where supported"), the D3a/D3b fork is visible, owned, and decisionable; R10's UNKNOWNs are untouched and out of scope (§14).
- No endpoint invented — only §3.5's and §3.7's two endpoints; no admin session surface, no password/device/MFA routes (explicitly excluded, §14).
- No state invented — the auth_session lifecycle (active/rotated/revoked/expired) is the row-value behavior of existing columns; "rotated" is a hash-replacement condition, not a new schema state; no user-status behavior appears anywhere.
- No event invented — `TOKEN_REVOKED`, `SUSPICIOUS_ACTIVITY`, `SECURITY_EVENT` are existing enum values; no new value proposed; "no event on successful rotation" is a locked absence (D1.6), not a new event.
- No ledger entry invented — zero ledger surface in scope or in any R6 path.
- No account behavior invented — `users.status` is explicitly out of scope; the login-ACTIVE guard is pre-existing and untouched.
- No production behavior invented — DEV scope only; real money FORBIDDEN; STAGING tuning deferred, not designed.
- No migration created — none in the repository from this task; the D3b migration is specified-on-paper only and gated behind a signed decision.
- No dependency added — verified against installed packages; DRF throttling is existing framework config.
- No code modified — working tree contained only the VS10 discovery document before this file; 0 tracked modifications.
- No tests modified/written; no frontend modified.
- No commit; no push (verified in the final safety check below and in §1).
- No VS11 references as scope — later candidates appear only in §14 exclusions with their own gates.
- The VS10 plan was extracted, not reinterpreted — every R6 fact in this document was re-verified against primary sources (API text quoted verbatim; code lines traced this session; schema columns listed from the migration file) rather than copied from the plan.
