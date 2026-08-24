# EduTrust Algeria — Schema Runtime Defect Patch v1.4

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Runtime defect remediation patch summary  
**SQL patch:** `edutrust_schema_patch_v1_4.sql`  
**Status:** READY FOR EXECUTION VALIDATION

---

# 1. Summary

Patch v1.4 remediates two confirmed runtime defects:

1. Booking insertion enum-cast failure in `validate_booking_slot()`.
2. Missing DB-level immutability for `PAID` payout rows.

It is a forward remediation patch over the tested reconstructed migration chain.

---

# 2. Patch Scope

Migration chain after this patch:

```text
v1
→ v1.1
→ reconstructed v1.2 draft
→ v1.3
→ v1.4
```

Patch v1.4 does not modify prior files.

---

# 3. DEF-001 Fix

The function `edutrust.validate_booking_slot()` is replaced with equivalent business logic but explicit enum casts:

```text
'BOOKED'::edutrust.availability_slot_status
'HELD'::edutrust.availability_slot_status
```

Expected result:

```text
Normal booking creation succeeds.
Slot status updates correctly.
```

---

# 4. DEF-002 Fix

The patch adds:

```text
edutrust.prevent_paid_payout_mutation_v1_4()
trg_00_payouts_paid_immutable_v1_4
```

Expected result:

```text
Any UPDATE against a row where OLD.status = 'PAID' fails.
```

Post-payout correction remains:

```text
new adjustment/recovery transaction
```

not historical payout mutation.

---

# 5. Final Status

```text
Schema Runtime Defect Patch v1.4 Status: READY FOR VALIDATION
```
