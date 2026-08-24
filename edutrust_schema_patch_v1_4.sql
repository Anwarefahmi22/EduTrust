-- EduTrust Algeria — Schema Runtime Defect Patch v1.4
-- Purpose:
--   DEF-001: Fix booking slot status enum-cast runtime bug in validate_booking_slot().
--   DEF-002: Enforce DB-level immutability for PAID payout rows.
-- Applies on top of:
--   edutrust_schema_v1.sql
--   edutrust_schema_patch_v1_1.sql
--   edutrust_schema_patch_v1_2_RECONSTRUCTED_DRAFT.sql
--   edutrust_schema_patch_v1_3.sql
-- Target: PostgreSQL 14+
-- No architecture, state-machine, API, or MVP-scope changes.

BEGIN;

SET search_path TO edutrust, public;

-- =========================================================
-- DEF-001 — BOOKING ENUM CAST BUG
-- =========================================================
-- Preserve existing booking/slot business semantics:
-- - newly inserted BOOKED booking makes the slot BOOKED
-- - newly inserted HELD or PAYMENT_PENDING booking makes the slot HELD
-- The only change is that CASE returns availability_slot_status, not text.

CREATE OR REPLACE FUNCTION edutrust.validate_booking_slot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  slot_record edutrust.availability_slots%ROWTYPE;
BEGIN
  SELECT * INTO slot_record
  FROM edutrust.availability_slots
  WHERE id = NEW.availability_slot_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Availability slot not found: %', NEW.availability_slot_id;
  END IF;

  IF slot_record.status <> 'AVAILABLE'::edutrust.availability_slot_status THEN
    RAISE EXCEPTION 'Slot % is not available; current status is %', NEW.availability_slot_id, slot_record.status;
  END IF;

  IF NEW.status NOT IN (
    'HELD'::edutrust.booking_status,
    'PAYMENT_PENDING'::edutrust.booking_status,
    'BOOKED'::edutrust.booking_status
  ) THEN
    RAISE EXCEPTION 'New booking must start as HELD, PAYMENT_PENDING, or BOOKED';
  END IF;

  UPDATE edutrust.availability_slots
  SET status = CASE
        WHEN NEW.status = 'BOOKED'::edutrust.booking_status
          THEN 'BOOKED'::edutrust.availability_slot_status
        ELSE 'HELD'::edutrust.availability_slot_status
      END,
      held_until = NEW.hold_expires_at,
      held_by_parent_id = NEW.parent_id,
      updated_at = now()
  WHERE id = NEW.availability_slot_id;

  RETURN NEW;
END;
$$;

-- =========================================================
-- DEF-002 — PAID PAYOUT IMMUTABILITY
-- =========================================================
-- Once a payout is PAID, the database must reject any UPDATE to that row.
-- This protects amount/currency/status/teacher_id/timestamps/provider reference and
-- all historical payout fields. Post-payout correction remains a separate
-- adjustment/recovery ledger transaction; this patch does not create recovery rows.

CREATE OR REPLACE FUNCTION edutrust.prevent_paid_payout_mutation_v1_4()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'PAID'::edutrust.payout_status THEN
    RAISE EXCEPTION 'PAID payout rows are immutable; create a separate adjustment/recovery transaction instead of updating payout %', OLD.id;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_00_payouts_paid_immutable_v1_4 ON edutrust.payouts;
CREATE TRIGGER trg_00_payouts_paid_immutable_v1_4
BEFORE UPDATE ON edutrust.payouts
FOR EACH ROW EXECUTE FUNCTION edutrust.prevent_paid_payout_mutation_v1_4();

COMMIT;
