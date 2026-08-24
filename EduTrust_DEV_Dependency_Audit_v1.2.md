# EduTrust — DEV Dependency Audit v1.2

**Scope:** Frontend dependency audit before completing DEV Vertical Slice #3  
**Command:** `npm audit --json` in `frontend/`  
**Status:** FINDINGS — ACCEPT TEMPORARILY IN DEV; FIX BEFORE STAGING/PRODUCTION

---

# 1. Summary

Current audit result:

```text
high: 2
critical: 0
total vulnerable dependency nodes: 2
```

Affected packages:

```text
next
postcss via next
```

No dependency remediation was applied.

`npm audit fix --force` was not run.

---

# 2. DEP-001 — Next.js advisory set

| Field | Finding |
|---|---|
| Package | `next` |
| Installed line | Next.js 14, build output `14.2.35` |
| Direct dependency | Yes |
| Severity | High aggregate |
| Dependency chain | `frontend/package.json → next` |
| Advisories observed | Server Components DoS, SSRF in Server Actions/custom servers, middleware/proxy issues, cache poisoning, image optimizer DoS, and related advisories |
| Fixed versions | `npm audit` recommends `next@16.3.2` via semver-major upgrade; multiple advisories indicate later Next 15.x/16.x fixed ranges |
| Breaking changes? | Yes, audit fix path is semver-major |
| Runtime impact | Relevant if public Next server is exposed |
| Development impact | Acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING / FIX BEFORE PRODUCTION |

Decision:

```text
DEV: ACCEPT TEMPORARILY
STAGING: MUST REMEDIATE OR FORMALLY RISK-ACCEPT
PRODUCTION: MUST REMEDIATE
```

---

# 3. DEP-002 — PostCSS via Next

| Field | Finding |
|---|---|
| Package | `postcss` |
| Direct dependency | No |
| Dependency chain | `next → postcss` |
| Severity | High aggregate |
| Advisories observed | Source map path traversal/arbitrary file read and CSS stringify XSS-related advisories |
| Fixed versions | Resolved through Next dependency upgrade according to audit output |
| Breaking changes? | Likely tied to Next major upgrade path |
| Runtime impact | Relevant for staging/production build/server exposure |
| Development impact | Acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING / FIX BEFORE PRODUCTION |

---

# 4. Final Decision

```text
Dependency Audit v1.2: FINDINGS
DEV: ACCEPT TEMPORARILY
STAGING: BLOCKED UNTIL REMEDIATED OR FORMALLY RISK-ACCEPTED
PRODUCTION: BLOCKED UNTIL REMEDIATED
```
