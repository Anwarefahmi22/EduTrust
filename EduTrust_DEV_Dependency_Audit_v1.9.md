# EduTrust — DEV Dependency Audit v1.9

**Scope:** Frontend + backend dependency audit after DEV Vertical Slice #10 (R6 Auth Completion) implementation
**Commands:** `npm audit --json` in `frontend/`; `pip check` in the backend venv (Python 3.11.2)
**Status:** FINDINGS — ACCEPT TEMPORARILY IN DEV; FIX BEFORE STAGING/PRODUCTION (finding set unchanged from v1.8)
**Chain:** v1.8 (after VS9) → **v1.9 (after VS10)**

---

# 1. Summary

Frontend (`npm audit --json`, auditReportVersion 2):

```text
affected packages: 2
  next@14.2.35            (direct dependency, package.json "next": "^14.2.0")
  postcss@8.4.31          (transitive via next)
advisories observed: 25 (high: 10, moderate: 13, low: 2)
```

**VS10 introduced zero new dependencies** — the R6 slice adds two API routes, a service section, and a client-side refresh hook in `frontend/lib/api.ts` that uses only the existing `fetch`/`Headers` web APIs (no library). `backend/requirements.txt`, `frontend/package.json`, and `frontend/package-lock.json` are byte-identical to the pre-VS10 baseline `af8f818` (verified by `git diff af8f818 --stat` = empty for all three). The finding set is identical to Dependency Audits v1.2–v1.8.

Backend (`pip check`):

```text
No broken requirements found.
```

Pinned ranges (unchanged): Django >=5.2,<5.3 · djangorestframework >=3.16,<3.17 · psycopg[binary] >=3.2,<3.3 · PyJWT >=2.10,<3.0 · python-dotenv >=1.0,<2.0 · pytest >=8.3,<9.0 · pytest-django >=4.9,<5.0 · requests >=2.32,<3.0.

No dependency remediation was applied. `npm audit fix --force` was **not** run (not authorized; would force breaking major upgrades in a DEV slice).

Secrets scan (tracked files + the VS10 diff): no private keys, cloud key material, or hardcoded credential patterns found. Raw refresh tokens are never logged or stored (hash-only storage, verified by the Phase-16 direct-SQL audit). No runtime/generated artifacts (`node_modules`, `.next`) tracked or staged (both gitignored; verified).

---

# 2. DEP-001 — Next.js advisory set (carried from v1.2–v1.8, unchanged)

| Field | Finding |
|---|---|
| Package | `next` |
| Installed version | 14.2.35 |
| Direct dependency | Yes |
| Severity | high (aggregate) |
| Dependency chain | `frontend/package.json → next` |
| Advisories observed | Image Optimizer DoS via remotePatterns (GHSA-9g9p-9gw9-jx7f); RSC HTTP deserialization DoS (GHSA-h25m-26qc-wcjf); HTTP request smuggling in rewrites (GHSA-ggv3-7p47-pfv8); unbounded next/image disk cache (GHSA-3x4c-7xq6-v6v3); Server Components DoS advisories (GHSA-q4gf-8mx6-v5v3, GHSA-8h8q-6873-q5fj, and related) |
| Fixed versions | audit fix path is a semver-major Next upgrade |
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

# 3. DEP-002 — PostCSS advisories via next (carried from v1.2–v1.8, unchanged)

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
2. Re-run the VS1–VS10 automated suite + E2E after the upgrade.
3. Verify postcss is resolved transitively to a fixed range.
4. Only then clear the STAGING/PRODUCTION dependency gate.
```

No part of this remediation was executed in VS10.

---

# 5. Result

```text
VS10_INTRODUCED_NEW_FINDINGS: NO
NPM_AUDIT_FIX_FORCE_RUN: NO
SECRET_SCAN: CLEAN (tracked files + VS10 diff; hash-only token storage verified)
GENERATED_ARTIFACTS_TRACKED: NO (node_modules/.next gitignored)
DEPENDENCY_SET: BYTE-IDENTICAL TO PRE-VS10 (= af8f818)
```
