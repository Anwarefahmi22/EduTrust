# EduTrust Algeria — DDL v1.2 Missing Artifact Report

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Missing migration artifact report  
**Status:** BLOCKING IMPLEMENTATION

---

# 1. Executive Summary

The required DDL artifact is missing from the current workspace:

```text
edutrust_schema_patch_v1_2.sql
```

Workspace search found only:

```text
/home/user/edutrust_schema_v1.sql
/home/user/edutrust_schema_patch_v1_1.sql
/home/user/edutrust_schema_patch_v1_3.sql
```

Because v1.3 explicitly applies on top of v1.2, a migration dry-run must not be claimed or attempted as complete until v1.2 is supplied.

---

# 2. Exact Missing Artifact

```text
edutrust_schema_patch_v1_2.sql
```

Required migration chain:

```text
edutrust_schema_v1.sql
→ edutrust_schema_patch_v1_1.sql
→ edutrust_schema_patch_v1_2.sql
→ edutrust_schema_patch_v1_3.sql
```

---

# 3. Why v1.3 Depends on v1.2

`edutrust_schema_patch_v1_3.sql` references refund reconciliation fields that are not present in v1.1.

Examples referenced by v1.3:

```text
refunds.reconciliation_source
refunds.reconciliation_reference
refunds.reconciled_at
refunds.reconciled_by_user_id
```

These fields are expected to have been introduced by v1.2.

v1.3 also appears to harden behavior that the v1.2 audit described, including:

- reconciliation integrity,
- refund lifecycle hardening,
- provider event lifecycle protection,
- idempotency actor identity handling,
- payout/net payable authority clarification.

Without v1.2, v1.3 cannot be reliably applied.

---

# 4. Objects Expected from the Baseline

Based on the approved audits and v1.3 dependencies, v1.2 is expected to contain or modify at least:

```text
refunds.reconciliation_source
refunds.reconciliation_reference
refunds.reconciled_at
refunds.reconciled_by_user_id
possibly reconciliation source enum or text/domain constraints
provider event lifecycle constraints/triggers
api_idempotency actor identity hardening
refund lifecycle transition protection
additional payout/net-payable documentation or constraints if present
```

This report does not fabricate those definitions. The original v1.2 file must be supplied.

---

# 5. Migration Dependency Analysis

## Available files

```text
edutrust_schema_v1.sql
edutrust_schema_patch_v1_1.sql
edutrust_schema_patch_v1_3.sql
```

## Missing file

```text
edutrust_schema_patch_v1_2.sql
```

## Static dependency issue

If v1.3 is applied after v1.1 without v1.2, PostgreSQL is expected to fail with missing-column errors for reconciliation fields.

Therefore:

```text
Migration dry-run status: NOT EXECUTED / BLOCKED
```

---

# 6. Exact Action Required

Before implementation:

1. Locate or regenerate from approved source history the exact original:

```text
edutrust_schema_patch_v1_2.sql
```

2. Place it in the migration chain repository path.
3. Verify checksum/review provenance if possible.
4. Run clean PostgreSQL dry-run:

```text
v1 → v1.1 → v1.2 → v1.3
```

5. Produce:

```text
EduTrust_Migration_Dry_Run_Report_v1.0.md
```

Only after a successful dry-run may the DDL artifact blocker be marked closed.

---

# 7. Final Status

```text
DDL v1.2 Artifact Status: MISSING — BLOCKS IMPLEMENTATION
```
