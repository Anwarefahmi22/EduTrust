# EduTrust — DEV Dependency Audit v1.1

**Scope:** Frontend dependency audit before DEV Vertical Slice #2  
**Command:** `npm audit --json` in `frontend/`  
**Status:** FINDINGS — ACCEPT TEMPORARILY IN DEV; FIX BEFORE STAGING

---

# 1. Summary

`npm audit` reports:

```text
2 vulnerable dependency nodes
high: 2
critical: 0
```

Affected dependency nodes:

```text
next
postcss, transitive through next
```

No dependency modifications were made during this sprint.

`npm audit fix --force` was not run.

---

# 2. Finding DEP-001 — Next.js advisory set

| Field | Assessment |
|---|---|
| Package | `next` |
| Installed major | Next.js 14 line, build output `14.2.35` |
| Direct dependency | Yes |
| Severity | High aggregate |
| Vulnerability names | Multiple Next.js advisories, including Server Components DoS, SSRF in Server Actions/custom servers, middleware/proxy issues, cache poisoning, image optimizer DoS |
| Dependency chain | `frontend/package.json → next` |
| Fixed versions | `npm audit` indicates `next@16.3.2` via semver-major upgrade; many advisories also fixed in later Next 15.x ranges |
| Breaking change? | Yes, audit-recommended fix is semver-major |
| Runtime vs dev | Runtime risk if publicly deployed; acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING |

Decision:

```text
ACCEPT TEMPORARILY IN DEV
FIX BEFORE STAGING
FIX BEFORE PRODUCTION
```

---

# 3. Finding DEP-002 — PostCSS via Next

| Field | Assessment |
|---|---|
| Package | `postcss` |
| Direct dependency | No |
| Dependency chain | `next → postcss` |
| Severity | High aggregate |
| Vulnerability names | Source map path traversal/arbitrary file read, CSS stringify XSS-related advisories |
| Fixed versions | Resolved through Next dependency upgrade according to audit output |
| Breaking change? | Likely tied to Next major upgrade path |
| Runtime vs dev | Potential build/runtime risk depending exposure; acceptable temporarily for local DEV only |
| Classification | FIX BEFORE STAGING |

---

# 4. Final Decision

```text
Dependency Audit v1.1: FINDINGS
DEV: ACCEPT TEMPORARILY
STAGING: BLOCKED UNTIL REMEDIATED OR FORMALLY RISK-ACCEPTED
PRODUCTION: BLOCKED UNTIL REMEDIATED
```
