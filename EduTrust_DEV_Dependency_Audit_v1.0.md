# EduTrust — DEV Dependency Audit v1.0

**Scope:** Frontend dependency audit before Vertical Slice #1 implementation  
**Command run:** `npm audit --json` in `frontend/`  
**Status:** FINDINGS — ACCEPT TEMPORARILY IN DEV; FIX BEFORE STAGING

---

# 1. Summary

`npm audit` reported:

```text
high: 2
critical: 0
total: 2 vulnerable dependency nodes
```

Affected packages:

```text
next
postcss, transitive through next
```

No automatic dependency changes were applied.

`npm audit fix --force` was **not** run.

---

# 2. Finding DEP-001 — Next.js vulnerabilities

| Field | Assessment |
|---|---|
| Package | `next` |
| Current version | `14.2.35` installed from `^14.2.0` |
| Direct dependency | Yes |
| Severity | High aggregate due multiple advisories |
| Vulnerability names | DoS in Server Components, SSRF in Server Actions/custom servers, middleware/proxy issues, cache poisoning, image optimizer DoS and related advisories |
| Dependency chain | direct `frontend/package.json → next` |
| Available safe versions | Audit indicates fix via `next@16.3.2` with semver-major upgrade; many ranges also imply `>=15.5.21` for several advisories |
| Breaking changes? | Yes, recommended audit fix is semver major |
| Runtime impact | Potential production/staging runtime exposure if public Next server is deployed |
| DEV impact | Acceptable temporarily for local DEV shell only, not public internet exposure |
| Classification | FIX BEFORE STAGING |

Decision:

```text
ACCEPT TEMPORARILY IN DEV
FIX BEFORE STAGING
FIX BEFORE PRODUCTION
```

Required action before staging:

- Decide whether to upgrade to Next 15.5.21+ or 16.x.
- Run compatibility build/tests.
- Re-run `npm audit`.
- Confirm no production/staging exposure with vulnerable Next version.

---

# 3. Finding DEP-002 — PostCSS vulnerabilities via Next

| Field | Assessment |
|---|---|
| Package | `postcss` |
| Current source | Transitive dependency via `next` |
| Direct dependency | No |
| Severity | High aggregate due arbitrary file read / path traversal source map advisories and XSS advisory |
| Dependency chain | `next → postcss` |
| Available safe versions | Fix available through Next upgrade according to npm audit output |
| Breaking changes? | Likely tied to Next major upgrade path |
| Runtime impact | Could affect build/server processing if exposed to attacker-controlled CSS/source maps; staging/prod must not ship vulnerable chain |
| DEV impact | Acceptable temporarily in local DEV only |
| Classification | FIX BEFORE STAGING |

Decision:

```text
ACCEPT TEMPORARILY IN DEV
FIX BEFORE STAGING
FIX BEFORE PRODUCTION
```

---

# 4. Overall Decision

```text
Dependency Audit: FINDINGS
DEV: Allowed temporarily
STAGING: Blocked until remediated or formally risk-accepted
PRODUCTION: Blocked until remediated
```

No dependency modifications were made in this sprint.
