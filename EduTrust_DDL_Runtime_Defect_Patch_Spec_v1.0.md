# EduTrust Algeria — DDL Runtime Defect Patch Specification v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Runtime DDL defect patch specification  
**SQL patch:** `edutrust_schema_patch_v1_4.sql`  
**Status:** READY FOR VALIDATION

---

# 1. Purpose

This specification defines a forward remediation patch for two confirmed PostgreSQL runtime defects discovered during actual migration/runtime validation.

The patch does not modify prior migrations and does not change business semantics.

---

# 2. DEF-001 — Booking enum cast bug

| Field | Value |
|---|---|
| Root cause | `validate_booking_slot()` assigned a `CASE` expression returning `text` into `availability_slots.status`, an `availability_slot_status` enum column |
| Affected object | `edutrust.validate_booking_slot()` |
| Observed evidence | Booking insert failed with `column "status" is of type availability_slot_status but expression is of type text` |
| Severity | HIGH / implementation blocker |
| Intended behavior | Booking insert updates slot status to `BOOKED` or `HELD` as `availability_slot_status` enum |
| Exact patch | Replace function with schema-qualified enum casts in CASE expression |
| Regression risk | Low; business logic unchanged, only enum typing corrected |
| Compatibility impact | Existing trigger continues using same function name/signature |
| Rollback considerations | Restore previous function body, but that reintroduces runtime defect |

---

# 3. DEF-002 — PAID payout mutation allowed

| Field | Value |
|---|---|
| Root cause | `payouts` table had no DB-level immutability trigger for rows after `status='PAID'` |
| Affected object | `edutrust.payouts` |
| Observed evidence | `UPDATE payouts SET amount=... WHERE status='PAID'` succeeded |
| Severity | HIGH / financial history integrity risk |
| Intended behavior | Once payout is `PAID`, any update to the row fails |
| Exact patch | Add `prevent_paid_payout_mutation_v1_4()` and `trg_00_payouts_paid_immutable_v1_4` BEFORE UPDATE trigger |
| Regression risk | Medium; any legitimate post-paid metadata update would be blocked, but no non-financial metadata exists in current schema |
| Compatibility impact | Non-PAID payout rows remain mutable; transition to PAID remains allowed while OLD.status is not PAID |
| Rollback considerations | Drop trigger/function; would remove DB-level immutability and must require financial approval |

---

# 4. Non-goals

This patch does not:

- redesign booking logic,
- change booking state machine,
- change API semantics,
- create recovery records,
- rewrite ledger entries,
- modify historical payouts,
- modify v1/v1.1/reconstructed v1.2/v1.3,
- expand MVP scope.

---

# 5. Final Status

```text
DDL Runtime Defect Patch Specification v1.0 Status: READY FOR VALIDATION
```
