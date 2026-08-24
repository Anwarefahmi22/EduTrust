# EduTrust Algeria — DDL Hardening v1.3

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** DDL Hardening v1.3  
**SQL patch:** `edutrust_schema_patch_v1_3.sql`  
**Applies on top of:**

```text
edutrust_schema_v1.sql
+
edutrust_schema_patch_v1_1.sql
+
edutrust_schema_patch_v1_2.sql
```

**Gate:** DDL Audit v1.2 result = FAIL WITH PATCHES  
**Scope:** Final hardening only. No schema redesign. No UX. No backend implementation.

---

# 1. Executive Summary

DDL Hardening v1.3 fixes the remaining issues found during DDL Audit v1.2:

1. Reconciliation integrity when `provider_refund_id` is present.
2. Refund state data cleanliness for `REQUESTED`, `REJECTED`, and `CANCELLED`.
3. Whitespace-only `provider_refund_id` for successful refunds.
4. Missing DB-level lifecycle validation for `api_idempotency_keys`.
5. Migration robustness around relation-scoped constraint existence checks.

The patch is intentionally small. It does not redesign the schema, does not delete enum values, and does not modify previous architecture documents.

---

# 2. Patch Strategy

The SQL patch adds:

1. Relation-scoped `CHECK` constraints on `refunds`, added as `NOT VALID`.
2. A refund hardening trigger:

```text
validate_refund_hardening_v1_3()
```

3. An idempotency lifecycle/immutability trigger:

```text
validate_api_idempotency_lifecycle_v1_3()
```

The patch does **not** replace the existing v1.1/v1.2 refund integrity logic. It layers final hardening on top.

Using `NOT VALID` constraints preserves existing v1.1/v1.2 data while enforcing the rules for new or updated rows.

---

# 3. FIX 1 — Reconciliation Integrity

## Finding

Manual/admin reconciliation rules were only enforced under a branch where `provider_refund_id IS NULL`.

This allowed a logically invalid state:

```text
status = SUCCEEDED
provider_refund_id = 'PR-123'
reconciliation_source = MANUAL_RECONCILIATION
reconciled_by_user_id = NULL
```

## Root cause

The validation logic treated provider proof and reconciliation proof as mutually exclusive paths, but did not enforce reconciliation metadata consistently whenever `reconciliation_source` was present.

## Exact SQL fix

The v1.3 patch enforces:

```text
IF reconciliation_source IS NOT NULL:
  reconciliation_reference IS NOT NULL
  length(trim(reconciliation_reference)) > 0
  reconciled_at IS NOT NULL

IF reconciliation_source IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE'):
  reconciled_by_user_id IS NOT NULL

IF reconciliation_source IS NULL:
  reconciliation_reference IS NULL
  reconciled_at IS NULL
  reconciled_by_user_id IS NULL
```

Implemented through:

```sql
chk_refunds_v1_3_reconciliation_consistency
```

and:

```sql
validate_refund_hardening_v1_3()
```

## Why the fix is safe

The rule is independent of provider refund identity. It applies whenever reconciliation data exists.

This preserves valid provider-based success and valid reconciliation-based success while blocking incomplete reconciliation records.

## Migration impact

The check constraint is added as `NOT VALID`, so existing rows are not scanned during migration. New and updated rows must satisfy the rule.

---

# 4. FIX 2 — Refund State Data Cleanliness

## Finding

`REQUESTED` was clean, but `REJECTED` and `CANCELLED` could still carry provider or reconciliation metadata that did not belong to those states.

Examples of invalid data that could pass before hardening:

```text
status = REJECTED
provider_refund_id = 'xyz'
reconciliation_source = MANUAL_RECONCILIATION
```

or:

```text
status = CANCELLED
provider_refund_id = 'xyz'
reconciled_at = '...'
```

## Root cause

Refund state timestamp and metadata rules were not consistently defined for non-success terminal states.

## Exact SQL fix

The v1.3 patch enforces:

### REQUESTED

Must contain no:

```text
provider_refund_id
reconciliation data
approval data
allocation data
provider_submitted_at
completed_at
failed_at
rejected_at
cancelled_at
```

### REJECTED

Must contain no:

```text
provider_refund_id
reconciliation data
provider_submitted_at
completed_at
failed_at
cancelled_at
approval data
allocation data
```

`rejected_at` remains valid and is expected by the existing refund lifecycle rules.

### CANCELLED

In MVP v1.3, cancellation is treated as pre-provider-submission cancellation.

Must contain no:

```text
provider_refund_id
reconciliation data
provider_submitted_at
completed_at
failed_at
rejected_at
```

Historical provider evidence, if required, belongs in:

```text
payment_provider_events
event_ledger
```

not as success-like evidence inside `refunds`.

Implemented through:

```sql
chk_refunds_v1_3_state_data_cleanliness
```

and:

```sql
validate_refund_hardening_v1_3()
```

## Why the fix is safe

It keeps state rows semantically clean and avoids confusing cancelled/rejected refunds with provider-submitted or reconciled refunds.

## Migration impact

Constraint is `NOT VALID`; existing rows are preserved. Future inserts/updates must comply.

---

# 5. FIX 3 — Provider Refund Identity

## Finding

`SUCCEEDED` could accept whitespace-only `provider_refund_id` because checks used `IS NOT NULL` instead of trimmed content validation.

Invalid example:

```text
status = SUCCEEDED
provider_refund_id = '   '
```

## Root cause

Provider refund identity was checked for nullability, not meaningful content.

## Exact SQL fix

The v1.3 patch enforces:

```text
provider_refund_id IS NULL
OR length(trim(provider_refund_id)) > 0
```

For `SUCCEEDED`, success proof requires either:

```text
provider_refund_id IS NOT NULL
AND length(trim(provider_refund_id)) > 0
```

or valid explicit reconciliation proof:

```text
reconciliation_source IS NOT NULL
reconciliation_reference IS NOT NULL
length(trim(reconciliation_reference)) > 0
reconciled_at IS NOT NULL
manual/admin reconciliation requires reconciled_by_user_id
```

Implemented through:

```sql
chk_refunds_v1_3_provider_refund_id_trim
chk_refunds_v1_3_succeeded_proof
validate_refund_hardening_v1_3()
```

## Why the fix is safe

It blocks fake success identity while allowing two valid success paths:

1. Provider refund identity.
2. Explicit reconciliation proof.

## Migration impact

Constraints are `NOT VALID`; existing data is preserved while future writes are protected.

---

# 6. FIX 4 — Idempotency State Lifecycle

## Finding

`api_idempotency_keys` had durable identity fields but no DB-level lifecycle guard.

This left impossible transitions theoretically possible:

```text
COMPLETED → PROCESSING
COMPLETED → FAILED
FAILED → COMPLETED
FAILED → PROCESSING
```

It also left idempotency identity fields mutable unless protected by service logic only.

## Root cause

The idempotency table was designed for replay, but its own state machine was not enforced at the database level.

## Exact SQL fix

The v1.3 patch adds:

```sql
validate_api_idempotency_lifecycle_v1_3()
```

and trigger:

```sql
trg_api_idempotency_lifecycle_v1_3
```

Allowed lifecycle:

```text
INSERT → PROCESSING only
PROCESSING → COMPLETED
PROCESSING → FAILED
PROCESSING → PROCESSING, for metadata updates while still processing
COMPLETED → COMPLETED, retention-only updates
FAILED → FAILED, retention-only updates
```

Forbidden lifecycle:

```text
COMPLETED → PROCESSING
COMPLETED → FAILED
FAILED → COMPLETED
FAILED → PROCESSING
```

Immutable identity/request fields:

```text
scope
idempotency_key
actor_user_id
actor_key
request_method
request_path
request_hash
```

Terminal records also freeze replay-relevant fields:

```text
response_status
response_body
resource_type
resource_id
locked_until
```

`expires_at` remains retention/cleanup metadata and may be updated.

## Why the fix is safe

It prevents key reuse and response mutation while preserving the intended replay behavior.

The same idempotency identity can no longer be reshaped into a different request.

## Migration impact

No table rewrite is required. The trigger applies to future inserts/updates.

Existing completed/failed records are preserved.

---

# 7. FIX 5 — Constraint Existence Checks

## Finding

Migration checks that rely only on:

```sql
pg_constraint.conname
```

can theoretically skip a required constraint if another table has the same constraint name.

## Root cause

Constraint names are not a robust global identity for migration checks across all relations.

## Exact SQL fix

All new v1.3 constraint existence checks scope to the intended table:

```sql
conrelid = 'edutrust.refunds'::regclass
```

Example:

```sql
IF NOT EXISTS (
  SELECT 1
  FROM pg_constraint
  WHERE conname = 'chk_refunds_v1_3_succeeded_proof'
    AND conrelid = 'edutrust.refunds'::regclass
) THEN
  ALTER TABLE edutrust.refunds
  ADD CONSTRAINT ...
END IF;
```

## Why the fix is safe

It prevents false positives in migration detection and makes the patch safer in non-empty or long-lived databases.

## Migration impact

No data impact.

---

# 8. What v1.3 Does Not Change

The patch does **not** change:

- Booking/payment/session architecture.
- Dispute overlay model.
- Refund lifecycle design.
- Provider event identity model.
- Ledger immutability.
- PayoutService authority over `net_teacher_payable` calculation.
- Existing enum values.
- Existing v1.1/v1.2 tables.
- Existing historical rows.

The patch does **not** start UX or backend implementation.

---

# 9. Final Verification Checklist

Use this checklist for DDL Audit Final Pass.

## Refund reconciliation

- [ ] `reconciliation_source IS NOT NULL` requires non-empty `reconciliation_reference`.
- [ ] `reconciliation_source IS NOT NULL` requires `reconciled_at`.
- [ ] Manual/admin reconciliation requires `reconciled_by_user_id`.
- [ ] Reconciliation metadata cannot exist when `reconciliation_source IS NULL`.
- [ ] Rules apply even when `provider_refund_id` exists.

## Refund state cleanliness

- [ ] `REQUESTED` has no provider/reconciliation/approval/allocation/terminal data.
- [ ] `REJECTED` has no provider/reconciliation/provider-submission/approval/allocation/success/failure/cancel data.
- [ ] `CANCELLED` has no provider/reconciliation/provider-submission/success/failure/rejection data.
- [ ] Historical provider evidence remains in `payment_provider_events` or `event_ledger`.

## Provider refund identity

- [ ] Whitespace-only `provider_refund_id` is rejected.
- [ ] `SUCCEEDED` requires valid provider refund ID or valid reconciliation proof.
- [ ] Whitespace-only `reconciliation_reference` is rejected.

## Idempotency lifecycle

- [ ] New idempotency records must start as `PROCESSING`.
- [ ] `PROCESSING → COMPLETED` is allowed.
- [ ] `PROCESSING → FAILED` is allowed.
- [ ] `COMPLETED → PROCESSING` is blocked.
- [ ] `COMPLETED → FAILED` is blocked.
- [ ] `FAILED → COMPLETED` is blocked.
- [ ] `FAILED → PROCESSING` is blocked.
- [ ] Identity/request fields are immutable.
- [ ] Terminal replay-relevant fields are immutable.
- [ ] `expires_at` remains retention metadata.

## Migration robustness

- [ ] Constraint existence checks are scoped to the intended relation using `conrelid`.
- [ ] Migration is transaction-safe.
- [ ] Existing data is preserved.
- [ ] No enum values are deleted.
- [ ] No redesign is introduced.

---

# 10. Migration Impact Summary

| Area | Impact |
|---|---|
| Existing data | Preserved |
| Existing enum values | Preserved |
| New constraints | Added as `NOT VALID` where they could affect historical rows |
| New triggers | Apply to future inserts/updates |
| Transaction safety | Entire patch runs inside one transaction |
| Backward compatibility | Applies on top of v1.2 without table redesign |
| Operational behavior | Stricter invalid-state prevention |

---

# 11. Final Status

DDL Hardening v1.3 Status: **PASS**

Next gate:

```text
DDL Audit FINAL PASS
```

Do not proceed to UX until the v1.3 SQL patch is reviewed and accepted.
