# EduTrust Algeria — Migration Dry Run Actual v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Actual PostgreSQL migration dry-run report  
**Migration chain tested:**

```text
edutrust_schema_v1.sql
→ edutrust_schema_patch_v1_1.sql
→ edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql
→ edutrust_schema_patch_v1_3.sql
```

**Status:** MIGRATION EXECUTION PASS; POST-MIGRATION VALIDATION FOUND BLOCKERS  
**Implementation status:** NOT APPROVED

---

# 1. Environment

| Item | Value |
|---|---|
| Environment method | Local isolated PostgreSQL cluster initialized with `initdb` in `/home/user/pg_validation_20260824T004704Z` |
| Container | Not used; Docker/Podman unavailable, local PostgreSQL package installed for validation |
| Database name | `edutrust_validation` |
| Schema name | `edutrust` |
| Client version | `psql (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)` |
| Server version | `PostgreSQL 17.11 (Debian 17.11-0+deb13u1)` |
| Baseline target | PostgreSQL 14+ |
| Validation timestamp | `2026-08-24 00:47:04 UTC` |

Clean database pre-check:

```text
edutrust_schema_exists=false
edutrust_tables=0
edutrust_enums=0
```

---

# 2. Migration Files

| Order | File | Status |
|---:|---|---|
| 1 | `edutrust_schema_v1.sql` | Present |
| 2 | `edutrust_schema_patch_v1_1.sql` | Present |
| 3 | `edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql` | Present; reconstructed draft, not original |
| 4 | `edutrust_schema_patch_v1_3.sql` | Present |

Important:

```text
The v1.2 file tested is RECONSTRUCTED DRAFT, not the original historical artifact.
```

---

# 3. Per-Migration Result

| Migration | Exit code | Duration | Result | Object counts after migration |
|---|---:|---:|---|---|
| v1 | 0 | 117 ms | PASS | schemas=1, tables=30, enums=31, functions=15, triggers=30 |
| v1.1 | 0 | 26 ms | PASS | schemas=1, tables=33, enums=35, functions=17, triggers=35 |
| reconstructed v1.2 | 0 | 11 ms | PASS | schemas=1, tables=33, enums=35, functions=21, triggers=39 |
| v1.3 | 0 | 12 ms | PASS | schemas=1, tables=33, enums=35, functions=23, triggers=41 |

Migration execution result:

```text
PASS — all four SQL files executed successfully on clean PostgreSQL 17.11.
```

This proves technical SQL execution only. It does not prove historical equivalence of reconstructed v1.2.

---

# 4. Schema Inventory Summary

After full migration chain:

| Object type | Count |
|---|---:|
| Schemas | 1 |
| Tables | 33 |
| Columns | 404 |
| Enums | 35 |
| Constraints | 222 |
| Indexes | 110 |
| Triggers | 41 |
| Functions | 23 |

Important reconstructed/hardened objects verified:

```text
refunds.reconciliation_source:text:YES
refunds.reconciliation_reference:text:YES
refunds.reconciled_at:timestamp with time zone:YES
refunds.reconciled_by_user_id:uuid:YES
```

v1.2 functions present:

```text
validate_api_idempotency_actor_v1_2
validate_provider_event_lifecycle_v1_2
validate_refund_lifecycle_v1_2
validate_refund_reconciliation_v1_2
```

v1.3 functions present:

```text
validate_api_idempotency_lifecycle_v1_3
validate_refund_hardening_v1_3
```

v1.2 triggers present:

```text
trg_api_idempotency_actor_v1_2
trg_payment_provider_events_lifecycle_v1_2
trg_refunds_lifecycle_v1_2
trg_refunds_reconciliation_v1_2
```

v1.3 triggers present:

```text
trg_api_idempotency_lifecycle_v1_3
trg_refunds_hardening_v1_3
```

v1.3 refund constraints present:

```text
chk_refunds_v1_3_provider_refund_id_trim
chk_refunds_v1_3_reconciliation_consistency
chk_refunds_v1_3_reconciliation_reference_trim
chk_refunds_v1_3_state_data_cleanliness
chk_refunds_v1_3_succeeded_proof
```

Provider event identity verified structurally:

```text
provider_event_unique=1
```

Append-only triggers verified structurally:

```text
ledger_no_update_trigger=1
event_ledger_no_update_trigger=1
```

---

# 5. Constraint / Trigger / Function Validation

## 5.1 Schema creation

Status: PASS

`edutrust` schema created.

## 5.2 Tables and enums

Status: PASS

33 tables and 35 enums created.

## 5.3 FKs / CHECK / UNIQUE / indexes

Status: PASS for creation.

222 constraints and 110 indexes created.

## 5.4 Triggers/functions

Status: PASS for creation.

41 non-internal triggers and 23 functions created.

---

# 6. Runtime Validation — Normal Application-Like Fixture Setup

Status: FAIL

A normal booking insert failed due to an existing v1 trigger bug in `validate_booking_slot()`.

PostgreSQL error:

```text
ERROR:  column "status" is of type availability_slot_status but expression is of type text
LINE 2:   SET status = CASE WHEN NEW.status = 'BOOKED' THEN 'BOOKED'...
                       ^
HINT:  You will need to rewrite or cast the expression.
QUERY:  UPDATE availability_slots
  SET status = CASE WHEN NEW.status = 'BOOKED' THEN 'BOOKED' ELSE 'HELD' END,
      held_until = NEW.hold_expires_at,
      held_by_parent_id = NEW.parent_id,
      updated_at = now()
  WHERE id = NEW.availability_slot_id
CONTEXT:  PL/pgSQL function validate_booking_slot() line 21 at SQL statement
```

Interpretation:

- This is not caused by reconstructed v1.2.
- It exists in the v1 baseline function `validate_booking_slot()`.
- It blocks normal booking creation at DB runtime.
- It must be handled as a separate DDL defect/change request before implementation.

Severity:

```text
HIGH / IMPLEMENTATION BLOCKER
```

---

# 7. Domain Validation With Controlled Fixture Bypass

Because the booking trigger bug prevented dependent refund/payout fixtures, a separate validation run used a controlled test-fixture-only bypass:

```text
ALTER TABLE bookings DISABLE TRIGGER trg_bookings_validate_slot;
insert booking fixture;
ALTER TABLE bookings ENABLE TRIGGER trg_bookings_validate_slot;
```

This bypass was used only to seed dependent data and does **not** validate booking creation.

Domain validation output directory:

```text
/home/user/pg_validation_domain_20260824T004802Z
```

## 7.1 Refund lifecycle validation

| Test | Status |
|---|---|
| `REQUESTED → APPROVED → PROVIDER_PENDING → SUCCEEDED` | PASS |
| terminal refund transition blocked | PASS |
| over-refund blocked | PASS |
| whitespace-only `provider_refund_id` blocked | PASS |
| manual reconciliation requires user | PASS |
| `SUCCEEDED` requires provider identity or reconciliation proof | PASS via tested hardening paths |

## 7.2 Idempotency validation

| Test | Status |
|---|---|
| Insert starts at `PROCESSING` | PASS |
| `PROCESSING → COMPLETED` | PASS |
| `COMPLETED → PROCESSING` blocked | PASS |
| actor identity mismatch blocked | PASS |
| request identity fields protected by v1.3 trigger | PASS structurally and partially tested |

## 7.3 Provider event validation

| Test | Status |
|---|---|
| insert `RECEIVED` | PASS |
| `RECEIVED → PROCESSING → PROCESSED` | PASS |
| `PROCESSED → RECEIVED` blocked | PASS |
| provider event identity uniqueness exists | PASS structurally |

## 7.4 Ledger / Event Ledger validation

| Test | Status |
|---|---|
| ledger entries append-only | PASS |
| event ledger append-only | PASS |
| ledger balancing trigger exists | PASS structurally; balanced insert passed |

## 7.5 Payout validation

| Test | Status |
|---|---|
| payout item blocked when open dispute exists | PASS |
| paid payout amount immutable at DB level | FAIL |

Paid payout mutation test result:

```text
FAIL_PAYOUT_MUTATION_ALLOWED
```

Interpretation:

- The database currently allows updating a `payouts` row with `status='PAID'`.
- This violates the desired financial UX/business rule if DB-level immutability is required.
- Previous architecture positioned paid payout immutability mainly as service/ledger/UI discipline, but this validation request explicitly asked to validate payout historical immutability.
- Therefore this is a DB-level enforcement gap or must be explicitly documented as service-layer-only.

Severity:

```text
MEDIUM/HIGH — requires Architecture/Database decision
```

---

# 8. Financial Integrity Validation Summary

| Requirement | Result | Notes |
|---|---|---|
| Ledger append-only | PASS | Update blocked by trigger |
| Event Ledger append-only | PASS | Delete blocked by trigger |
| Refund allocation protection | PASS | Allocation and over-refund tests passed |
| Payment/refund identities separated | PASS | Payment/refund/provider event structures exist |
| Provider event identity separate from transaction identity | PASS | `provider_event_id` and `provider_transaction_id` both present; unique provider event index exists |
| Payout blocked by open dispute | PASS | `payout_items` insert blocked |
| Paid payout historical immutability | FAIL | `payouts.amount` update allowed for `PAID` payout |
| Post-payout correction as new adjustment/recovery | UNVERIFIED | Requires service/ledger implementation; no DB-level adjustment table/trigger beyond ledger accounts |

---

# 9. Session Synchronous Creation Validation

Status: UNVERIFIED

Reason:

Synchronous session creation is a PaymentWebhookService transaction behavior, not a standalone DDL-only behavior. The database can enforce some prerequisites for session creation, but it does not itself create the session on payment confirmation.

This must be validated during service/integration implementation.

---

# 10. Failed Tests

## FAIL-001 — Booking insert trigger enum-cast bug

Area:

```text
validate_booking_slot()
```

Failure:

```text
CASE expression returns text where availability_slot_status enum is required.
```

Impact:

```text
Normal booking creation fails.
```

Likely fix direction, not applied:

```text
Cast CASE branches to availability_slot_status or rewrite assignment with enum-typed values.
```

No migration was modified in this sprint.

## FAIL-002 — Paid payout mutation allowed at DB level

Area:

```text
payouts
```

Failure:

```text
UPDATE payouts SET amount=1600 WHERE status='PAID'
```

succeeded in a transaction.

Impact:

```text
DB does not enforce historical paid payout immutability.
```

Possible decision:

- Add DB trigger in future approved patch, or
- explicitly classify paid payout immutability as service-layer + audit/ledger policy only.

No migration was modified in this sprint.

---

# 11. Unverified Tests

| Area | Status | Reason |
|---|---|---|
| Historical equivalence of reconstructed v1.2 | UNVERIFIED | Original v1.2 not recovered |
| Full normal booking lifecycle | FAIL before completion | Booking trigger bug |
| Session synchronous creation | UNVERIFIED | Requires PaymentWebhookService implementation |
| Post-payout recovery creation | UNVERIFIED | Requires service/ledger implementation |
| Provider-specific webhook signature | UNVERIFIED | Provider not selected |
| Legal/payment readiness | UNVERIFIED | Requires legal/provider review |

---

# 12. Actual Execution Evidence

Validation directories:

```text
Migration + initial validation:
/home/user/pg_validation_20260824T004704Z

Domain validation with fixture bypass:
/home/user/pg_validation_domain_20260824T004802Z
```

Key logs:

```text
output/01_v1.log
output/02_v1_1.log
output/03_v1_2_reconstructed.log
output/04_v1_3.log
output/validation_tests.log
output/domain_validation.log
output/schema_inventory_corrected.txt
output/important_object_checks.txt
```

---

# 13. Technical Conclusion

## Migration execution

```text
PASS — full SQL chain executed successfully on clean PostgreSQL 17.11.
```

## Runtime validation

```text
FAIL/PARTIAL — core refund/idempotency/provider/ledger tests passed, but booking trigger and paid payout immutability issues remain.
```

## Reconstructed v1.2 technical status

```text
TECHNICALLY EXECUTABLE
```

## Historical equivalence

```text
UNVERIFIED
```

---

# 14. Final Status

```text
Migration Dry Run Actual v1.0 Status: MIGRATION PASS; VALIDATION FAILURES REMAIN
```

Implementation Gate must remain RED.
