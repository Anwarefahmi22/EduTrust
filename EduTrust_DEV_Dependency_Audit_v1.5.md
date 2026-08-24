# EduTrust — DEV Dependency Audit v1.5

**Scope:** Frontend + backend dependency audit after DEV Vertical Slice #6 (Review Moderation) implementation
**Commands:** `npm audit --json` in `frontend/`; `pip check` in the backend venv (Python 3.11.2)
**Status:** FINDINGS — ACCEPT TEMPORARILY IN DEV; FIX BEFORE STAGING/PRODUCTION

---

# 1. Summary

Frontend (`npm audit --json`):

```text
info: 0
low: 0
moderate: 0
high: 2
critical: 0
total: 2
```

Affected packages:

```text
next@14.2.35            (direct dependency, package.json "next": "^14.2.0")
postcss@8.4.31 via next (transitive)
```

**VS6 introduced zero new dependencies** — the moderation console reuses the existing Next.js 14 + React 18 stack and the existing `lib/api.ts` client (`requirements.txt`, `package.json`, `package-lock.json` are byte-identical to pre-VS6, verified by diff). The finding set is identical to Dependency Audit v1.2/v1.3/v1.4.

Backend (`pip check`):

```text
No broken requirements found.
```

Pinned ranges (unchanged): Django >=5.2,<5.3 · djangorestframework >=3.16,<3.17 · psycopg[binary] >=3.2,<3.3 · PyJWT >=2.10,<3.0 · python-dotenv >=1.0,<2.0 · pytest >=8.3,<9.0 · pytest-django >=4.9,<5.0 · requests >=2.32,<3.0.

No dependency remediation was applied. `npm audit fix --force` was **not** run (not authorized).

---

# 2. DEP-001 — Next.js advisory set (carried from v1.2–v1.4, unchanged)

| Field | Finding |
|---|---|
| Package | `next` |
| Installed version | 14.2.35 |
| Direct dependency | Yes |
| Severity | high (aggregate) |
| Dependency chain | `frontend/package.json → next` |
| Advisories observed | Image Optimizer DoS via remotePatterns (moderate, GHSA-9g9p-9gw9-jx7f); RSC HTTP deserialization DoS (high, GHSA-h25m-26qc-wcjf); HTTP request smuggling in rewrites (moderate, GHSA-ggv3-7p47-pfv8); unbounded next/image disk cache (moderate, GHSA-3x4c-7xq6-v6v3); Server Components DoS advisories (high, GHSA-q4gf-8mx6-v5v3, GHSA-8h8q-6873-q5fj, and related) |
| Fixed versions | audit fix path is `next@16.3.2` (semver-major breaking change) |
| Breaking changes? | Yes |
| Runtime impact | Relevant only if a public Next server is exposed; current exposure is local DEV sandbox only |
| Development impact | Acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING / FIX BEFORE PRODUCTION |

Decision:

```text
DEV: acceptable temporarily
STAGING: must be remediated
PRODUCTION: must be remediated
```

# 3. DEP-002 — PostCSS advisories via next (carried from v1.2–v1.4, unchanged)

| Field | Finding |
|---|---|
| Package | `postcss` |
| Installed version | 8.4.31 (transitive via `next`) |
| Direct dependency | No |
| Severity | high (aggregate) |
| Dependency chain | `frontend/package.json → next → postcss` |
| Advisories observed | XSS via unescaped `</style>` in stringify output (GHSA-qx2v-qp2m-jg93); arbitrary file read via attacker-controlled `sourceMappingURL` (GHSA-6g55-p6wh-862q); incomplete fix reading arbitrary `.map` files when `from` unset (GHSA-fxqj-rqcc-2cmp); path traversal in previous source-map auto-loading (GHSA-r28c-9q8g-f849) |
| Fixed versions | postcss < 8.5.23 (pulled transitively by a Next upgrade path) |
| Breaking changes? | Only via the Next semver-major upgrade |
| Runtime impact | CSS processing surface of the Next build/serve pipeline; not reachable in the current local-DEV-only exposure |
| Development impact | Acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING / FIX BEFORE PRODUCTION |

Decision:

```text
DEV: acceptable temporarily
STAGING: must be remediated
PRODUCTION: must be remediated
```

---

# 4. Remediation path (unchanged, for a future approved work item)

```text
1. Evaluate upgrade next ^14.2.0 → 15.x (first) or 16.x with the DEV UI as the regression net.
2. Re-run the VS1–VS6 automated suite + E2E after the upgrade.
3. Verify postcss is resolved transitively to a fixed range.
4. Only then clear the STAGING/PRODUCTION dependency gate.
```

No part of this remediation was executed in VS6.

---

# 5. Result

```text
VS6_INTRODUCED_NEW_FINDINGS: NO
NPM_AUDIT_FIX_FORCE_RUN: NO
DEV: allowed (findings accepted temporarily)
STAGING: BLOCKED pending remediation (unchanged)
PRODUCTION: BLOCKED pending remediation (unchanged)
```
