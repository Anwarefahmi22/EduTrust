# EduTrust Algeria — Technical Stack Decision v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Technical stack decision  
**Status:** RECOMMENDED FOR APPROVAL  
**Architecture constraint:** Modular Monolith + PostgreSQL. No microservices.

---

# 1. Selected Stack

| Layer | Selected technology | Version policy |
|---|---|---|
| Backend | Django + Django REST Framework | Python 3.12+; Django 5.2 LTS or current LTS at implementation gate; DRF current stable compatible with Django LTS |
| Frontend | Next.js + React + TypeScript | Next.js current stable major at implementation gate; React current stable; TypeScript 5.x |
| Database | PostgreSQL | PostgreSQL 16 recommended; SQL remains compatible with PostgreSQL 14+ baseline |
| Workers | Celery | Celery 5.x stable |
| Broker/cache | Redis | Redis 7.x stable |
| Testing | Pytest + Playwright | Pytest 8.x; Playwright current stable |
| Containers | Docker + Docker Compose | Current stable Docker engine; compose spec |
| CI/CD | GitHub Actions | Hosted or self-hosted runners |
| Package manager | Backend: `uv` or Poetry; Frontend: `pnpm` | Pin lockfiles in repo |
| API schema | OpenAPI generated from DRF or maintained manually | Versioned with `/api/v1` |

---

# 2. Rationale

## 2.1 Django + DRF

Reasons:

- strong fit for modular monolith,
- mature auth/session/security ecosystem,
- strong PostgreSQL integration,
- transaction management for payment/booking/session flows,
- admin/back-office acceleration for internal ops where safe,
- good testability with Pytest,
- maintainable for a small startup team.

## 2.2 Next.js + React + TypeScript

Reasons:

- mobile-first parent/teacher web app,
- admin desktop dashboard possible in same stack,
- TypeScript improves API contract safety,
- strong design-system ecosystem,
- deployable as web MVP before native mobile.

## 2.3 PostgreSQL

Reasons:

- already approved,
- required for constraints/triggers/ledger integrity,
- strong transactional semantics,
- supports exclusion constraints and JSONB metadata.

## 2.4 Celery + Redis

Reasons:

- background jobs needed for hold expiry, notifications, metrics, payout eligibility, provider reconciliation,
- mature Django integration,
- retry semantics and scheduling support.

---

# 3. Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Microservices | Rejected | Too much operational complexity for MVP; risks distributed consistency |
| Node/NestJS backend | Not selected | Viable but less direct fit for PostgreSQL-heavy transactional monolith in current plan |
| FastAPI backend | Not selected | Viable but more custom work for admin/auth/RBAC/document workflows |
| Native mobile first | Rejected for MVP | Slower iteration; web MVP sufficient for validation |
| Firebase/Supabase-only backend | Rejected | Insufficient control over financial state machines and ledger constraints |
| NoSQL primary DB | Rejected | Financial/session constraints require relational integrity |

---

# 4. Local Development Approach

Recommended:

```text
Docker Compose for PostgreSQL, Redis, workers
Backend runs locally or in container
Frontend runs via pnpm dev
Seed scripts for subjects/levels/roles
```

Local services:

```text
backend API
web frontend
admin routes
postgres
redis
celery worker
celery beat/scheduler, if needed
mail/SMS mock provider
payment provider mock
```

---

# 5. Staging Approach

Staging must include:

- real PostgreSQL instance,
- Redis,
- worker processes,
- payment provider sandbox/mock,
- object storage sandbox,
- notification sandbox,
- migration dry-run before deploy,
- E2E smoke tests.

---

# 6. Production Approach

Production must include:

- managed PostgreSQL with backups,
- Redis/broker with persistence strategy appropriate for jobs,
- separate web/API/worker processes,
- secrets manager,
- structured logs,
- monitoring/alerts,
- object storage with encryption,
- payment provider integration approved legally/operationally.

---

# 7. Security Implications

Required:

- Django security settings hardened,
- secure cookies/token handling,
- refresh token hashes only,
- rate limiting,
- RBAC/object ownership middleware/service checks,
- payment webhook signature verification,
- raw provider payload redaction,
- secure document storage,
- audit/security event generation.

---

# 8. Maintainability Implications

- Modular apps within backend monolith.
- Service layer for state transitions.
- OpenAPI/spec-driven frontend integration.
- Shared TypeScript types generated where feasible.
- Strict test matrix for state machines.

---

# 9. Termux / Lightweight Development Compatibility

Termux can be useful for lightweight code review or frontend prototyping, but it is not recommended as the authoritative local environment for full stack because Docker/PostgreSQL/workers may be constrained.

Recommended compatibility policy:

- frontend can run with Node/pnpm where supported,
- backend unit tests may run if Python/Postgres available,
- full integration tests require Docker/Linux/macOS/CI environment,
- do not rely on Termux for migration validation.

---

# 10. Migration Implications

- Use SQL migrations for approved DDL chain.
- Django migrations must not silently diverge from approved SQL.
- If ORM models are used, they must be generated/verified against DDL.
- Clean database migration test must run in CI.

---

# 11. Final Decision

```text
EduTrust Technical Stack Decision v1.0 Status: RECOMMENDED FOR APPROVAL
```

Implementation cannot start until this stack is approved by Engineering Lead / Architecture Owner.
