# EduTrust Migration Manifest v1.0

**Package creation timestamp:** 2026-08-24T07:21:37Z

## Source Workspace Inventory Summary

- Source workspace approximate size: 156 MB previously observed; current raw file inventory size may include runtime/generated artifacts.
- Source workspace file count observed before packaging: 5682
- Migration-safe payload target: source/config/docs only, excluding generated/dependency/runtime artifacts.

## Package Inventory

- Included file count before manifest: 156
- Included payload size before manifest: 1314207 bytes (1.25 MiB)
- Manifest included: YES

## Included Directories

```text
backend/
frontend/app/
frontend/lib/
frontend/styles/
database/migrations/
tests/
scripts/
```

## Included Configuration Files

```text
.env.example
.gitignore
pytest.ini
README.md
frontend/package.json
frontend/package-lock.json
frontend/next.config.mjs
frontend/tsconfig.json
frontend/next-env.d.ts
backend/requirements.txt
```

## Included Documentation

All `EduTrust_*.md` project documentation and implementation reports present in the source workspace are included, including architecture, database, API, UX, visual/prototype, implementation planning, and DEV vertical slice reports.

## Database Migration Chain

```text
v1
→ v1.1
→ reconstructed v1.2
→ v1.3
→ v1.4
```

Files:

```text
database/migrations/001_edutrust_schema_v1.sql
database/migrations/002_edutrust_schema_patch_v1_1.sql
database/migrations/003_edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql
database/migrations/004_edutrust_schema_patch_v1_3.sql
database/migrations/005_edutrust_schema_patch_v1_4.sql
```

Root SQL baseline copies are also included for provenance and audit continuity.

## v1.2 Provenance Warning

```text
Original v1.2: NOT RECOVERED
Reconstructed v1.2: OPERATIONAL DEV/STAGING BASELINE
Historical equivalence: UNVERIFIED
RECONSTRUCTED v1.2 ≠ ORIGINAL v1.2
```

Do not rename or describe `edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql` as the historical/original v1.2 artifact.

## Current Implementation Status

```text
DEV Foundation: COMPLETE / PASS WITH LIMITATIONS
DEV Vertical Slice #1: COMPLETE / PASS WITH LIMITATIONS
DEV Vertical Slice #2: COMPLETE / PASS WITH LIMITATIONS
DEV Vertical Slice #3: COMPLETE / PASS WITH LIMITATIONS
Vertical Slice #4: NOT STARTED
```

## Completed DEV Work

### DEV Foundation

Repository foundation, Django backend foundation, PostgreSQL migration runner, auth/RBAC/audit foundations, Next.js frontend shell, tests.

### DEV Vertical Slice #1

Parent → Student → Teacher → Subject/Pricing → Availability → Search → Trust Profile → Booking Hold → DEV Mock Booking Confirmation.

### DEV Vertical Slice #2

Booking → Payment Intent → Payment Pending → Mock Provider Event → Payment Confirmed/Failed → Booking/Session outcome.

### DEV Vertical Slice #3

Booking → Payment Confirmed → Session Scheduled → Session Execution → Attendance/No-show → Completion → Teacher Report → Parent Report → Student Progress Events.

## Known Limitations

```text
Real Payment: NOT IMPLEMENTED / FORBIDDEN
Real Payout: NOT IMPLEMENTED / FORBIDDEN
Production: NOT APPROVED
Frontend is minimal DEV UI, not full 64-screen production UI
Dependency vulnerabilities in Next/PostCSS remain accepted only for DEV
Staging/production require dependency remediation or formal risk acceptance
Payment/legal readiness remains unresolved for real-money workflows
```

## Dependency Findings

Latest dependency audits report high severity findings in:

```text
next
postcss via next
```

Classification:

```text
DEV: acceptable temporarily
STAGING: must be remediated
PRODUCTION: must be remediated
```

No `npm audit fix --force` was run.

## Excluded File Categories

```text
frontend/node_modules/
frontend/.next/
backend/**/__pycache__/
.venv/
.pytest_cache/
node_modules/
dist/
build/
coverage/
logs/
tmp/
pg_validation_*/
pg_validation_domain_*/
pg_validation_v14_*/
temporary PostgreSQL data
runtime-generated files
last-run state files
OS/editor temporary files
generated caches
large binary artifacts
.env files containing secrets
```

Only `.env.example` is included. No real payment credentials, API secrets, private keys, tokens, or production credentials should be present.

## Migration Use Instructions for New Arena Conversation

1. Extract the archive.
2. Install backend dependencies from `backend/requirements.txt`.
3. Install frontend dependencies from `frontend/package.json`.
4. Provision PostgreSQL 14+.
5. Run `scripts/run_backend_tests.sh` or `scripts/run_migrations.py` with `DATABASE_URL`.
6. Preserve the reconstructed v1.2 provenance warning.
7. Do not start Vertical Slice #4 without explicit instruction.

## Final Preservation Statement

```text
SOURCE_PROJECT_PRESERVED: YES
VERTICAL_SLICE_4_STARTED: NO
SECRETS_INCLUDED: NO, only .env.example included
```
