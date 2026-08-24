# EduTrust Algeria — Feature Flag Governance v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Feature flag governance  
**Status:** READY FOR REVIEW

---

# 1. Principle

Feature flags must never bypass:

- state machines,
- authorization,
- payment verification,
- refund rules,
- audit logging,
- privacy permissions,
- ledger integrity.

Flags may select providers/modes or enable UI exposure, but must not weaken safety controls.

---

# 2. Governance Template

Every flag must define:

```text
flag name
purpose
owner
environments
default
allowed values
audit requirement
rollback
forbidden bypass behavior
```

---

# 3. Approved Flag Catalogue

| Flag | Purpose | Owner | Environments | Default | Allowed values | Audit requirement | Rollback | Forbidden bypass behavior |
|---|---|---|---|---|---|---|---|---|
| `PAYMENT_PROVIDER_MODE` | Select payment mode/provider | Payment Owner | local/staging/prod | `DISABLED` | `DISABLED`, `MOCK`, `CIB`, `EDAHABIA`, `CASH_PILOT`, `BANK_TRANSFER` | Changes audited in config history | Set to previous provider or DISABLED | Cannot bypass payment confirmation/webhook verification |
| `REFUND_PROVIDER_MODE` | Select refund processing mode | Payment Owner | local/staging/prod | `MANUAL_RECONCILIATION` | `DISABLED`, `MANUAL_RECONCILIATION`, `PROVIDER_API` | Config change audited | Revert to manual reconciliation | Cannot mark refunded before success proof |
| `PAYOUT_PROVIDER_MODE` | Select payout mechanism | Payment Owner | staging/prod | `MANUAL_OPS` | `DISABLED`, `MANUAL_OPS`, `PROVIDER_API` | Config change audited | Disable provider payout | Cannot bypass payout eligibility/dispute checks |
| `NOTIFICATION_CHANNELS_ENABLED` | Enabled channels | Product/Ops | all | `IN_APP` | subset of `IN_APP`, `EMAIL`, `SMS`, `PUSH` | Config change logged | Fall back to IN_APP | Cannot make provider delivery source of truth |
| `CASH_PILOT_ENABLED` | Allow cash/manual pilot workflows | Ops/Payment | local/staging/pilot only | `false` | `true`, `false` | All manual confirmations audited | Disable cash pilot | Cannot bypass ledger/event/audit recording |
| `SENSITIVE_PAYLOAD_ACCESS_ENABLED` | Allow admin provider payload secure access | Security Owner | staging/prod | `false` | `true`, `false` | Every access audited | Disable access | Cannot expose raw payload to Parent/Teacher |
| `DOCUMENT_ACCESS_ENABLED` | Allow secure verification document access | Security Owner | staging/prod | `true` | `true`, `false` | Every access audited | Disable document access | Cannot expose unrestricted document URLs |
| `TEACHER_PUBLIC_LISTING_ENABLED` | Allow listed teachers visible in marketplace | Product Lead | staging/prod | `false` before pilot | `true`, `false` | Listing policy changes logged | Disable listing | Cannot show unverified/suspended teacher as listed |
| `MATCHING_RULE_VERSION` | Select rule-based matching version | Product/Engineering | all | `v0` | `v0`, `v0_experiment` | Experiment config logged | Revert to v0 | Cannot become AI matching or bypass hard filters |
| `ADMIN_OVERRIDE_ENABLED` | Allow controlled admin override paths | Admin/Security | staging/prod | `false` until policy approved | `true`, `false` | Every override audited | Disable overrides | Cannot bypass audit/state services |
| `RLS_ENFORCEMENT_MODE` | Track optional DB row-level security rollout | Security/DB Owner | staging/prod | `SERVICE_LAYER_ONLY` | `SERVICE_LAYER_ONLY`, `RLS_SHADOW`, `RLS_ENFORCED` | Config change audited | Revert with security review | Cannot weaken service-layer ownership checks |

---

# 4. Flag Change Process

1. Submit flag change request.
2. Owner approves.
3. Security/payment review if sensitive.
4. Apply to staging first.
5. Run smoke tests.
6. Apply to production only after approval.
7. Record change in audit/config history.

---

# 5. Prohibited Flags

Do not create flags such as:

```text
BYPASS_PAYMENT_VERIFICATION
DISABLE_AUDIT_LOGGING
IGNORE_DISPUTE_FOR_PAYOUT
ALLOW_UNVERIFIED_REVIEWS
DISABLE_STUDENT_PERMISSION_CHECKS
MUTATE_LEDGER_DIRECTLY
```

---

# 6. Final Status

```text
EduTrust Feature Flag Governance v1.0 Status: READY FOR REVIEW
```
