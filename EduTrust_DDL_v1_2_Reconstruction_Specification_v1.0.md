# EduTrust Algeria — DDL v1.2 Reconstruction Specification v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Reconstruction specification  
**Status:** RECONSTRUCTED DRAFT SPECIFICATION — NOT APPROVED  
**Related SQL draft:** `edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql`

---

# 1. Purpose

The original `edutrust_schema_patch_v1_2.sql` was not recovered from the workspace. This specification defines the minimum evidenced objects believed necessary to bridge:

```text
edutrust_schema_patch_v1_1.sql
→ reconstructed v1.2 draft
→ edutrust_schema_patch_v1_3.sql
```

This document does not claim historical equivalence.

```text
RECONSTRUCTED ≠ ORIGINAL
```

---

# 2. Evidence Ranking Used

Evidence sources ranked:

1. Existing v1.1 SQL
2. Existing v1.3 SQL
3. v1.2 audit statements embedded in DDL Hardening v1.3 and user review history
4. State Machines v1.1 Addendum
5. API Architecture / API Contract Addendum
6. Implementation planning artifacts
7. Other approved architecture documents

No unavailable original v1.2 file was used.

---

# 3. Classification Legend

| Classification | Meaning |
|---|---|
| EXACTLY EVIDENCED | Directly required by existing SQL or exact documented statement |
| STRONGLY IMPLIED | Clearly required by v1.3 references and v1.2 audit text |
| INFERRED | Plausible bridge behavior needed for consistency, but exact historical SQL unknown |
| UNKNOWN | Evidence insufficient; must not be silently implemented |

---

# 4. Reconstructed Object Specification

## 4.1 `refunds.reconciliation_source`

| Field | Value |
|---|---|
| Object name | `refunds.reconciliation_source` |
| Object type | Column |
| Evidence source | v1.3 SQL references `NEW.reconciliation_source`; v1.2 audit discusses `reconciliation_source IN ('MANUAL_RECONCILIATION','ADMIN_OVERRIDE')` |
| Evidence strength | EXACTLY EVIDENCED for existence; UNKNOWN for exact type |
| Dependency | `refunds` table from v1.1 |
| Purpose | Identify source of refund reconciliation proof |
| Expected SQL behavior | Add nullable column before v1.3 hardening constraints reference it |
| Exact SQL reconstructable? | Partially. Existence yes; exact type no |
| Uncertainty | Original may have used enum/domain/text. Draft uses `TEXT` to avoid inventing undocumented enum values |
| Classification | EXISTENCE: EXACTLY EVIDENCED; TYPE: INFERRED |

## 4.2 `refunds.reconciliation_reference`

| Field | Value |
|---|---|
| Object name | `refunds.reconciliation_reference` |
| Object type | Column |
| Evidence source | v1.3 SQL and audit requirements |
| Evidence strength | EXACTLY EVIDENCED |
| Dependency | `refunds` |
| Purpose | Store manual/provider reconciliation reference |
| Expected SQL behavior | Nullable text; v1.3 hardens non-whitespace requirement |
| Exact SQL reconstructable? | Mostly yes |
| Uncertainty | Exact length/type unknown |
| Classification | STRONGLY IMPLIED |

## 4.3 `refunds.reconciled_at`

| Field | Value |
|---|---|
| Object name | `refunds.reconciled_at` |
| Object type | Column |
| Evidence source | v1.3 SQL and audit requirements |
| Evidence strength | EXACTLY EVIDENCED |
| Dependency | `refunds` |
| Purpose | Timestamp reconciliation proof was recorded |
| Expected SQL behavior | Nullable `TIMESTAMPTZ` |
| Exact SQL reconstructable? | Yes |
| Uncertainty | None material |
| Classification | EXACTLY EVIDENCED |

## 4.4 `refunds.reconciled_by_user_id`

| Field | Value |
|---|---|
| Object name | `refunds.reconciled_by_user_id` |
| Object type | Column + FK |
| Evidence source | v1.3 SQL and audit requirement for manual/admin reconciliation |
| Evidence strength | EXACTLY EVIDENCED for existence; STRONGLY IMPLIED for FK to users |
| Dependency | `users` table; `refunds` table |
| Purpose | Identify OPS/Admin user recording manual/admin reconciliation |
| Expected SQL behavior | Nullable UUID FK to `users(id)` |
| Exact SQL reconstructable? | Mostly yes |
| Uncertainty | Original FK `ON DELETE` behavior unknown; draft uses `ON DELETE SET NULL` matching nearby user references |
| Classification | STRONGLY IMPLIED |

## 4.5 `idx_refunds_reconciliation_source`

| Field | Value |
|---|---|
| Object name | `idx_refunds_reconciliation_source` |
| Object type | Index |
| Evidence source | Operational need; not directly evidenced by v1.3 |
| Evidence strength | INFERRED |
| Dependency | Reconciliation columns |
| Purpose | Aid admin refund/reconciliation filtering |
| Expected SQL behavior | Partial index where reconciliation source exists |
| Exact SQL reconstructable? | No |
| Uncertainty | Original may not have had this index |
| Classification | INFERRED |

## 4.6 `validate_refund_lifecycle_v1_2()`

| Field | Value |
|---|---|
| Object name | `validate_refund_lifecycle_v1_2()` |
| Object type | Trigger function |
| Evidence source | v1.2 audit says refund lifecycle transitions became `REQUESTED → APPROVED → PROVIDER_PENDING → SUCCEEDED/FAILED`, terminal states cannot reopen |
| Evidence strength | STRONGLY IMPLIED |
| Dependency | `refund_status` enum from v1.1; `refunds.status` |
| Purpose | Enforce base refund status transitions |
| Expected SQL behavior | Prevent impossible backwards/terminal transitions |
| Exact SQL reconstructable? | Semantics yes; exact function name/body no |
| Uncertainty | Whether `FAILED` was terminal or retryable; draft treats it terminal based on audit text |
| Classification | STRONGLY IMPLIED |

## 4.7 `trg_refunds_lifecycle_v1_2`

| Field | Value |
|---|---|
| Object name | `trg_refunds_lifecycle_v1_2` |
| Object type | Trigger |
| Evidence source | Lifecycle function requirement |
| Evidence strength | STRONGLY IMPLIED |
| Dependency | `validate_refund_lifecycle_v1_2()` |
| Purpose | Attach lifecycle guard to `refunds` |
| Expected SQL behavior | `BEFORE UPDATE OF status` |
| Exact SQL reconstructable? | Functionally yes; original name unknown |
| Uncertainty | Original trigger name unknown |
| Classification | INFERRED name, STRONGLY IMPLIED behavior |

## 4.8 `validate_refund_reconciliation_v1_2()`

| Field | Value |
|---|---|
| Object name | `validate_refund_reconciliation_v1_2()` |
| Object type | Trigger function |
| Evidence source | v1.2 audit identifies a bug in manual/admin reconciliation logic and says REQUESTED was cleaned of provider/reconciliation data |
| Evidence strength | STRONGLY IMPLIED |
| Dependency | Reconciliation fields; `refund_status` |
| Purpose | Base success proof / reconciliation guard before v1.3 hardening |
| Expected SQL behavior | For `SUCCEEDED` require provider ID OR reconciliation proof; for `REQUESTED` prohibit provider/reconciliation data |
| Exact SQL reconstructable? | Partially. Known limitations intentionally preserved for v1.3 to harden |
| Uncertainty | Exact original function name and full state cleanliness rules |
| Classification | STRONGLY IMPLIED behavior, INFERRED implementation |

## 4.9 `validate_provider_event_lifecycle_v1_2()`

| Field | Value |
|---|---|
| Object name | `validate_provider_event_lifecycle_v1_2()` |
| Object type | Trigger function |
| Evidence source | v1.2 audit says provider events became `RECEIVED → PROCESSING → PROCESSED` or `FAILED → PROCESSING`, terminal states protected |
| Evidence strength | STRONGLY IMPLIED |
| Dependency | `payment_provider_events`; `provider_event_processing_status` |
| Purpose | Prevent duplicate/invalid provider event lifecycle transitions |
| Expected SQL behavior | Terminal states cannot reopen; failed can retry to processing |
| Exact SQL reconstructable? | Semantics mostly yes; exact original SQL no |
| Uncertainty | Whether `IGNORED` terminal and whether direct `RECEIVED → REJECTED` allowed |
| Classification | STRONGLY IMPLIED with minor INFERRED details |

## 4.10 `validate_api_idempotency_actor_v1_2()`

| Field | Value |
|---|---|
| Object name | `validate_api_idempotency_actor_v1_2()` |
| Object type | Trigger function |
| Evidence source | v1.2 audit says actor identity became linked to `actor_user_id` |
| Evidence strength | STRONGLY IMPLIED |
| Dependency | `api_idempotency_keys.actor_user_id`, `actor_key` from v1.1 |
| Purpose | Prevent mismatched user actor identity in idempotency records |
| Expected SQL behavior | If actor_user_id present, actor_key must be `user:<uuid>`; system actors cannot use `user:` prefix |
| Exact SQL reconstructable? | No; rule is inferred from audit wording |
| Uncertainty | Original exact actor_key format unknown |
| Classification | INFERRED |

---

# 5. UNKNOWN Items Not Implemented

The following remain unknown and are not silently implemented:

1. Exact original type/enum for `reconciliation_source`.
2. Exact original enum values for reconciliation source.
3. Exact original trigger/function names.
4. Whether refund `FAILED` was retryable or terminal in original v1.2.
5. Exact original provider event lifecycle around `IGNORED`.
6. Whether v1.2 included data migrations.
7. Whether v1.2 added comments, grants, or additional indexes.
8. Whether v1.2 validated previous `NOT VALID` constraints.

---

# 6. Reconstruction Decision

Evidence is sufficient to create a **minimum technically complete reconstructed draft** that satisfies v1.3 dependencies and implements documented behavior at a conservative level.

However:

```text
The draft is NOT the original historical artifact.
It requires static audit, dry-run, semantic audit, and human approval.
```

---

# 7. Final Status

```text
DDL v1.2 Reconstruction Specification v1.0 Status: RECONSTRUCTED DRAFT SPEC READY — NOT APPROVED
```
