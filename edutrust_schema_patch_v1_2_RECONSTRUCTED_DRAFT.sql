-- EduTrust Algeria — Schema Patch v1.2 RECONSTRUCTED DRAFT
-- RECONSTRUCTED DRAFT — NOT YET APPROVED
-- This file is NOT the original historical edutrust_schema_patch_v1_2.sql.
-- It is a controlled reconstruction based only on available workspace evidence.
-- Applies on top of:
--   edutrust_schema_v1.sql
--   edutrust_schema_patch_v1_1.sql
-- and before:
--   edutrust_schema_patch_v1_3.sql
-- Target: PostgreSQL 14+
-- Purpose:
--   1. Add refund reconciliation fields required by v1.3.
--   2. Add base refund lifecycle transition guard evidenced by v1.2 audit notes.
--   3. Add base refund success/reconciliation proof guard with known limitations hardened by v1.3.
--   4. Add provider event lifecycle guard evidenced by v1.2 audit notes.
--   5. Add api_idempotency actor identity guard evidenced by v1.2 audit notes.
--
-- PROVENANCE WARNING:
--   Reconstructed != Original.
--   This SQL must undergo DDL audit and clean PostgreSQL dry-run before adoption.

BEGIN;

SET search_path TO edutrust, public;

-- =========================================================
-- 1. REFUND RECONCILIATION FIELDS
-- =========================================================

ALTER TABLE edutrust.refunds
  ADD COLUMN IF NOT EXISTS reconciliation_source TEXT,
  ADD COLUMN IF NOT EXISTS reconciliation_reference TEXT,
  ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS reconciled_by_user_id UUID REFERENCES edutrust.users(id) ON DELETE SET NULL;

COMMENT ON COLUMN edutrust.refunds.reconciliation_source IS
  'RECONSTRUCTED v1.2 DRAFT: source of manual/provider/admin refund reconciliation. Exact original type/enum was not recovered.';
COMMENT ON COLUMN edutrust.refunds.reconciliation_reference IS
  'RECONSTRUCTED v1.2 DRAFT: external/manual reconciliation reference. Hardened by v1.3.';
COMMENT ON COLUMN edutrust.refunds.reconciled_at IS
  'RECONSTRUCTED v1.2 DRAFT: timestamp when reconciliation proof was recorded.';
COMMENT ON COLUMN edutrust.refunds.reconciled_by_user_id IS
  'RECONSTRUCTED v1.2 DRAFT: admin/ops user who recorded manual/admin reconciliation where applicable.';

CREATE INDEX IF NOT EXISTS idx_refunds_reconciliation_source
ON edutrust.refunds(reconciliation_source, reconciled_at DESC)
WHERE reconciliation_source IS NOT NULL;

-- =========================================================
-- 2. REFUND LIFECYCLE TRANSITION GUARD
-- =========================================================

CREATE OR REPLACE FUNCTION edutrust.validate_refund_lifecycle_v1_2()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  -- Preserve v1.1 insert semantics. v1.3 later hardens state data cleanliness.
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;

  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
    RETURN NEW;
  END IF;

  -- Terminal states cannot be reopened in the reconstructed v1.2 evidence model.
  IF OLD.status IN (
    'SUCCEEDED'::edutrust.refund_status,
    'FAILED'::edutrust.refund_status,
    'REJECTED'::edutrust.refund_status,
    'CANCELLED'::edutrust.refund_status
  ) THEN
    RAISE EXCEPTION 'Invalid refund status transition from terminal state: % -> %', OLD.status, NEW.status;
  END IF;

  IF OLD.status = 'REQUESTED'::edutrust.refund_status
     AND NEW.status IN ('APPROVED'::edutrust.refund_status, 'REJECTED'::edutrust.refund_status, 'CANCELLED'::edutrust.refund_status) THEN
    RETURN NEW;
  END IF;

  IF OLD.status = 'APPROVED'::edutrust.refund_status
     AND NEW.status IN ('PROVIDER_PENDING'::edutrust.refund_status, 'CANCELLED'::edutrust.refund_status) THEN
    RETURN NEW;
  END IF;

  IF OLD.status = 'PROVIDER_PENDING'::edutrust.refund_status
     AND NEW.status IN ('SUCCEEDED'::edutrust.refund_status, 'FAILED'::edutrust.refund_status) THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION 'Invalid refund status transition: % -> %', OLD.status, NEW.status;
END;
$$;

DROP TRIGGER IF EXISTS trg_refunds_lifecycle_v1_2 ON edutrust.refunds;
CREATE TRIGGER trg_refunds_lifecycle_v1_2
BEFORE UPDATE OF status ON edutrust.refunds
FOR EACH ROW EXECUTE FUNCTION edutrust.validate_refund_lifecycle_v1_2();

-- =========================================================
-- 3. BASE REFUND RECONCILIATION / SUCCESS PROOF GUARD
-- =========================================================
-- Evidence from v1.2 audit indicated this guard existed but had limitations:
-- - Manual/admin reconciler requirement was tied to provider_refund_id IS NULL.
-- - REJECTED/CANCELLED data cleanliness was incomplete.
-- - Whitespace provider_refund_id was not fully rejected.
-- v1.3 is the authoritative final hardening layer.

CREATE OR REPLACE FUNCTION edutrust.validate_refund_reconciliation_v1_2()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  -- v1.2 evidence: REQUESTED was kept clean of provider/reconciliation data.
  IF NEW.status = 'REQUESTED'::edutrust.refund_status THEN
    IF NEW.provider_refund_id IS NOT NULL
       OR NEW.reconciliation_source IS NOT NULL
       OR NEW.reconciliation_reference IS NOT NULL
       OR NEW.reconciled_at IS NOT NULL THEN
      RAISE EXCEPTION 'REQUESTED refund cannot contain provider or reconciliation data';
    END IF;
  END IF;

  -- v1.2 evidence: successful refund needed provider_refund_id OR reconciliation proof.
  -- Known limitation: manual/admin reconciled_by_user_id is only required in the reconciliation branch
  -- where provider_refund_id IS NULL. v1.3 hardens this to apply whenever reconciliation_source exists.
  IF NEW.status = 'SUCCEEDED'::edutrust.refund_status AND NEW.provider_refund_id IS NULL THEN
    IF NEW.reconciliation_source IS NULL
       OR NEW.reconciliation_reference IS NULL
       OR NEW.reconciled_at IS NULL THEN
      RAISE EXCEPTION 'SUCCEEDED refund requires provider_refund_id or reconciliation proof';
    END IF;

    IF NEW.reconciliation_source IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE')
       AND NEW.reconciled_by_user_id IS NULL THEN
      RAISE EXCEPTION 'Manual/admin reconciliation requires reconciled_by_user_id';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_refunds_reconciliation_v1_2 ON edutrust.refunds;
CREATE TRIGGER trg_refunds_reconciliation_v1_2
BEFORE INSERT OR UPDATE OF status, provider_refund_id, reconciliation_source, reconciliation_reference, reconciled_at, reconciled_by_user_id
ON edutrust.refunds
FOR EACH ROW EXECUTE FUNCTION edutrust.validate_refund_reconciliation_v1_2();

-- =========================================================
-- 4. PROVIDER EVENT LIFECYCLE GUARD
-- =========================================================

CREATE OR REPLACE FUNCTION edutrust.validate_provider_event_lifecycle_v1_2()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.status <> 'RECEIVED'::edutrust.provider_event_processing_status THEN
      RAISE EXCEPTION 'payment_provider_events must be inserted with status RECEIVED';
    END IF;
    RETURN NEW;
  END IF;

  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
    RETURN NEW;
  END IF;

  IF OLD.status IN (
    'PROCESSED'::edutrust.provider_event_processing_status,
    'REJECTED'::edutrust.provider_event_processing_status,
    'IGNORED'::edutrust.provider_event_processing_status
  ) THEN
    RAISE EXCEPTION 'Invalid provider event transition from terminal state: % -> %', OLD.status, NEW.status;
  END IF;

  IF OLD.status = 'RECEIVED'::edutrust.provider_event_processing_status
     AND NEW.status IN ('PROCESSING'::edutrust.provider_event_processing_status, 'IGNORED'::edutrust.provider_event_processing_status, 'REJECTED'::edutrust.provider_event_processing_status) THEN
    RETURN NEW;
  END IF;

  IF OLD.status = 'PROCESSING'::edutrust.provider_event_processing_status
     AND NEW.status IN ('PROCESSED'::edutrust.provider_event_processing_status, 'FAILED'::edutrust.provider_event_processing_status, 'REJECTED'::edutrust.provider_event_processing_status, 'IGNORED'::edutrust.provider_event_processing_status) THEN
    RETURN NEW;
  END IF;

  IF OLD.status = 'FAILED'::edutrust.provider_event_processing_status
     AND NEW.status = 'PROCESSING'::edutrust.provider_event_processing_status THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION 'Invalid provider event status transition: % -> %', OLD.status, NEW.status;
END;
$$;

DROP TRIGGER IF EXISTS trg_payment_provider_events_lifecycle_v1_2 ON edutrust.payment_provider_events;
CREATE TRIGGER trg_payment_provider_events_lifecycle_v1_2
BEFORE INSERT OR UPDATE OF status ON edutrust.payment_provider_events
FOR EACH ROW EXECUTE FUNCTION edutrust.validate_provider_event_lifecycle_v1_2();

-- =========================================================
-- 5. API IDEMPOTENCY ACTOR IDENTITY GUARD
-- =========================================================

CREATE OR REPLACE FUNCTION edutrust.validate_api_idempotency_actor_v1_2()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.actor_user_id IS NOT NULL THEN
    IF NEW.actor_key IS DISTINCT FROM ('user:' || NEW.actor_user_id::text) THEN
      RAISE EXCEPTION 'api_idempotency_keys.actor_key must equal user:<actor_user_id> when actor_user_id is present';
    END IF;
  ELSE
    IF NEW.actor_key LIKE 'user:%' THEN
      RAISE EXCEPTION 'api_idempotency_keys.actor_key cannot use user: prefix when actor_user_id is NULL';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_api_idempotency_actor_v1_2 ON edutrust.api_idempotency_keys;
CREATE TRIGGER trg_api_idempotency_actor_v1_2
BEFORE INSERT OR UPDATE OF actor_user_id, actor_key ON edutrust.api_idempotency_keys
FOR EACH ROW EXECUTE FUNCTION edutrust.validate_api_idempotency_actor_v1_2();

COMMIT;
