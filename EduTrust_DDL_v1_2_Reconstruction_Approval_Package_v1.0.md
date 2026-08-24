# EduTrust Algeria — DDL v1.2 Reconstruction Approval Package v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Reconstruction approval package  
**Status:** REQUIRES HUMAN ARCHITECTURE / DATABASE APPROVAL  
**Reconstructed SQL:** `edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql`

---

# 1. Critical Statement

```text
RECONSTRUCTED ≠ ORIGINAL
```

The SQL draft created in this sprint is not the historical/original `edutrust_schema_patch_v1_2.sql`.

It is a controlled reconstructed draft based on available workspace evidence.

It must not be renamed or treated as the official v1.2 migration until approved through DDL audit and migration dry-run.

---

# 2. Why Original v1.2 Was Unavailable

Workspace search did not find:

```text
edutrust_schema_patch_v1_2.sql
```

Available SQL files:

```text
edutrust_schema_v1.sql
edutrust_schema_patch_v1_1.sql
edutrust_schema_patch_v1_3.sql
```

The original artifact is missing from the current workspace.

---

# 3. Evidence Used

Evidence sources:

1. Existing v1.1 SQL
2. Existing v1.3 SQL
3. v1.2 audit evidence captured in DDL Hardening v1.3
4. State Machines v1.1 Addendum
5. API Architecture / API Contract Addendum
6. Implementation planning and DDL missing/reconstruction reports

Key evidence:

- v1.3 references reconciliation fields not present in v1.1.
- v1.2 audit described refund lifecycle, provider event lifecycle, and idempotency actor identity improvements.
- v1.3 hardens specific v1.2 issues, implying v1.2 contained base behavior with known gaps.

---

# 4. Reconstructed Objects

| Object | Type | Evidence strength |
|---|---|---|
| `refunds.reconciliation_source` | Column | existence exactly evidenced; type inferred |
| `refunds.reconciliation_reference` | Column | strongly implied |
| `refunds.reconciled_at` | Column | exactly evidenced |
| `refunds.reconciled_by_user_id` | Column + FK | strongly implied |
| `idx_refunds_reconciliation_source` | Index | inferred |
| `validate_refund_lifecycle_v1_2()` | Function | strongly implied |
| `trg_refunds_lifecycle_v1_2` | Trigger | strongly implied behavior, inferred name |
| `validate_refund_reconciliation_v1_2()` | Function | strongly implied behavior |
| `trg_refunds_reconciliation_v1_2` | Trigger | strongly implied behavior, inferred name |
| `validate_provider_event_lifecycle_v1_2()` | Function | strongly implied |
| `trg_payment_provider_events_lifecycle_v1_2` | Trigger | strongly implied behavior, inferred name |
| `validate_api_idempotency_actor_v1_2()` | Function | inferred from audit evidence |
| `trg_api_idempotency_actor_v1_2` | Trigger | inferred |

---

# 5. Static Audit Result

Static audit document:

```text
EduTrust_DDL_v1_2_Reconstruction_Static_Audit_v1.0.md
```

Result:

```text
Static Audit Status: PASS WITH UNVERIFIED HISTORICAL EQUIVALENCE
```

Static audit confirms structural coherence but not execution.

---

# 6. PostgreSQL Dry-Run Result

Dry-run document:

```text
EduTrust_Migration_Dry_Run_Reconstructed_v1.0.md
```

Result:

```text
Migration Dry Run Reconstructed v1.0 Status: NOT EXECUTED — ENVIRONMENT BLOCKED
```

Reason:

```text
psql: command not found
```

No claim is made that SQL executes successfully.

---

# 7. Semantic Audit Result

Semantic audit document:

```text
EduTrust_DDL_Reconstructed_v1_2_Semantic_Audit_v1.0.md
```

Result:

```text
Semantic Audit Status: PASS WITH UNVERIFIED ITEMS
```

The draft aligns with known architecture and v1.3 dependencies, but exact historical equivalence remains unverified.

---

# 8. Differences from Documented v1.2

Because the original v1.2 document/file is unavailable, exact differences cannot be fully enumerated.

Known/likely differences:

1. `reconciliation_source` is implemented as `TEXT`, while original may have used an enum/domain.
2. Trigger and function names are reconstructed, not original.
3. Provider event `IGNORED` terminal behavior is inferred.
4. Refund `FAILED` is treated terminal based on audit text; original exact retry model unknown.
5. `idx_refunds_reconciliation_source` is inferred and may not have existed originally.
6. Comments are added for provenance and may not have existed originally.

---

# 9. Remaining Uncertainty

Remaining uncertainty:

- exact reconciliation source type and values,
- exact lifecycle transition edge cases,
- original trigger/function names,
- possible original data migration steps,
- original index/constraint naming,
- PostgreSQL execution success,
- historical equivalence.

---

# 10. Required Approval

Before adoption, require approval from:

```text
Architecture Owner
Database Owner
Payment Owner
Security Owner
QA Owner
```

Approval must explicitly accept:

1. Reconstructed status.
2. Known uncertainties.
3. Whether `TEXT` for `reconciliation_source` is acceptable.
4. Whether refund `FAILED` terminal behavior is acceptable.
5. Whether provider event lifecycle semantics are acceptable.
6. Whether migration dry-run must be performed externally before adoption.

---

# 11. Required Next Steps

1. Run full migration chain in PostgreSQL 14+ environment:

```text
v1 → v1.1 → reconstructed v1.2 draft → v1.3
```

2. Produce updated dry-run report with actual execution output.
3. Perform runtime trigger/constraint behavior tests.
4. Conduct human DDL approval review.
5. Only then decide whether to adopt reconstructed draft as official replacement.

---

# 12. Approval Package Final Status

```text
DDL v1.2 Reconstruction Approval Package Status: REQUIRES APPROVAL
Implementation Gate Impact: REMAINS RED
```
