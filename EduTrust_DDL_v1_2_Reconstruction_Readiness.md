# EduTrust Algeria — DDL v1.2 Reconstruction Readiness

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Reconstruction readiness analysis, not a migration  
**Status:** ORIGINAL v1.2 NOT RECOVERED — RECONSTRUCTION REQUIRES APPROVAL  
**Implementation status:** NOT APPROVED

---

# 1. Executive Summary

The original artifact:

```text
edutrust_schema_patch_v1_2.sql
```

was searched for across the available workspace and was **not recovered**.

This document does **not** reconstruct the SQL and does **not** create a replacement migration. It identifies what v1.2 appears to have introduced or modified based on approved evidence and v1.3 dependencies.

Reconstruction is unsafe without explicit approval because v1.3 was authored as a hardening patch on top of v1.2, and v1.2 may contain lifecycle constraints/triggers whose exact semantics must not be guessed.

---

# 2. Search Evidence

Workspace search covered:

```text
edutrust_schema_patch_v1_2.sql
*v1_2*.sql
*v1.2*.sql
Schema Patch v1.2 references
DDL Audit v1.2 references
reconciliation_source
provider_event lifecycle
api_idempotency lifecycle
refund lifecycle hardening
```

Files found:

```text
edutrust_schema_v1.sql
edutrust_schema_patch_v1_1.sql
edutrust_schema_patch_v1_3.sql
```

Missing:

```text
edutrust_schema_patch_v1_2.sql
```

---

# 3. Dependencies on v1.1

v1.1 created the main structures that v1.2/v1.3 harden:

```text
api_idempotency_keys
payment_provider_events
refunds
refund_status
refund_type
provider_event_processing_status
api_idempotency_status
```

v1.1 `refunds` table includes:

```text
payment_id
booking_id
dispute_id
provider
refund_type
status
requested_amount
approved_amount
currency
teacher_adjustment_amount
platform_adjustment_amount
reason
reason_code
provider_refund_id
idempotency_key
requested_by_user_id
requested_by_role
approved_by_user_id
approved_by_role
approved_at
provider_submitted_at
completed_at
failed_at
rejected_at
cancelled_at
failure_code
failure_message
normalized_provider_payload
metadata
created_at
updated_at
```

v1.1 does **not** include the reconciliation fields referenced by v1.3.

---

# 4. Exact Objects v1.3 Expects

`edutrust_schema_patch_v1_3.sql` references the following refund reconciliation columns:

```text
refunds.reconciliation_source
refunds.reconciliation_reference
refunds.reconciled_at
refunds.reconciled_by_user_id
```

Therefore, v1.2 must have introduced or altered at least these fields.

v1.3 also references lifecycle and hardening behavior described in the v1.2 audit:

```text
manual/admin reconciliation integrity
refund state transition protection
provider event state transition protection
api idempotency actor identity/lifecycle handling
refund success proof handling
payout/net payable authority documentation or guards
```

---

# 5. SQL Objects That Would Need Reconstruction

If reconstruction is explicitly approved, the reconstruction would need to determine and implement, at minimum:

## 5.1 Refund reconciliation fields

Likely additions to `refunds`:

```text
reconciliation_source
reconciliation_reference
reconciled_at
reconciled_by_user_id
```

Uncertainty:

- Is `reconciliation_source` an enum or text column?
- What exact enum values are allowed?
- Does it include `MANUAL_RECONCILIATION`, `ADMIN_OVERRIDE`, provider reconciliation values, or others?

## 5.2 Refund lifecycle transition guard

Likely trigger/function to prevent invalid transitions such as:

```text
SUCCEEDED → anything
FAILED → SUCCEEDED, unless explicit retry model
REJECTED/CANCELLED → reopened
```

Uncertainty:

- Exact allowed retry behavior from `FAILED`.
- Whether `FAILED → PROVIDER_PENDING` retry was allowed.

## 5.3 Provider event lifecycle guard

Likely trigger/function for `payment_provider_events` transitions:

```text
RECEIVED → PROCESSING → PROCESSED
PROCESSING → FAILED / REJECTED
FAILED → PROCESSING, if retryable
terminal states protected
```

Uncertainty:

- Exact terminal states.
- Whether `IGNORED` is terminal.
- Whether duplicate failed events can be retried automatically.

## 5.4 API idempotency actor identity hardening

The v1.2 audit stated actor identity was improved. v1.1 already has `actor_user_id` and `actor_key`, but v1.2 may have added guards linking them.

Uncertainty:

- Exact relationship required between `actor_user_id` and `actor_key`.
- Whether system actors are allowed with `actor_user_id IS NULL`.
- Whether actor_key format constraints were added.

## 5.5 Refund success proof and state cleanliness

v1.3 final hardening closes gaps found in v1.2, but v1.2 likely introduced base proof semantics.

Uncertainty:

- Exact proof rules before v1.3.
- Existing constraint names and whether v1.3 expects them.

## 5.6 PayoutService/net payable authority

v1.2 audit indicated PayoutService was documented as authority for `net_teacher_payable`.

Uncertainty:

- Whether v1.2 contains actual SQL changes or only documentation around payout authority.

---

# 6. Unresolved Uncertainties

Reconstruction cannot be safely applied until the following are answered:

1. Was `reconciliation_source` an enum, text, or domain?
2. What exact values were allowed for reconciliation source?
3. What exact refund status transition matrix did v1.2 enforce?
4. What exact provider event transition matrix did v1.2 enforce?
5. Did v1.2 add constraints, triggers, indexes, or comments that v1.3 assumes by name?
6. Did v1.2 modify `api_idempotency_keys` beyond actor identity?
7. Did v1.2 alter existing v1.1 triggers such as `validate_refund_integrity()`?
8. Did v1.2 add migration-safe `NOT VALID` constraints or validate existing constraints?
9. Did v1.2 include data migration steps that v1.3 assumes?
10. Did v1.2 introduce provider refund event handling changes not visible in v1.3?

---

# 7. Why Reconstruction Is Unsafe Without Approval

Reconstructing v1.2 from v1.3 references alone risks:

- introducing semantics that differ from the approved v1.2 audit,
- creating duplicate or conflicting constraint names,
- omitting required transition guards,
- breaking v1.3 assumptions,
- producing a database that appears to migrate but does not match the approved architecture,
- undermining financial/refund/audit safety.

Therefore:

```text
DO NOT apply a reconstructed v1.2 automatically.
```

---

# 8. Required Approval Before Reconstruction

Before reconstruction, obtain explicit approval for:

1. Reconstruction scope.
2. Exact column definitions.
3. Reconciliation source type and allowed values.
4. Refund lifecycle transition rules.
5. Provider event lifecycle transition rules.
6. Idempotency actor identity rules.
7. Constraint/trigger names.
8. Migration safety strategy.
9. DDL audit plan.
10. Clean PostgreSQL dry-run plan.

---

# 9. Recommended Next Step

Preferred:

```text
Recover original edutrust_schema_patch_v1_2.sql from source history.
```

If not possible:

```text
Approve reconstruction explicitly
→ create edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql
→ DDL audit
→ clean PostgreSQL dry-run
→ only then consider gate update
```

---

# 10. Final Status

```text
DDL v1.2 Recovery Status: ORIGINAL NOT RECOVERED
DDL v1.2 Reconstruction Status: NOT APPROVED
Implementation Impact: BLOCKS IMPLEMENTATION
```
