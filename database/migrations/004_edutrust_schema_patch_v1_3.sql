-- EduTrust Algeria — Schema Patch v1.3 FINAL HARDENING
-- Applies on top of:
--   edutrust_schema_v1.sql
--   edutrust_schema_patch_v1_1.sql
--   edutrust_schema_patch_v1_2.sql
-- Target: PostgreSQL 14+
-- Purpose:
--   1. Refund reconciliation integrity hardening
--   2. Refund state data cleanliness hardening
--   3. Provider refund identity non-whitespace validation
--   4. API idempotency lifecycle/immutability validation
--   5. Relation-scoped constraint existence checks

BEGIN;

SET search_path TO edutrust, public;

-- =========================================================
-- 1. REFUND HARDENING CHECK CONSTRAINTS
--    Added as NOT VALID to preserve existing v1.1/v1.2 data while
--    enforcing the rules for new/updated rows.
-- =========================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_refunds_v1_3_provider_refund_id_trim'
      AND conrelid = 'edutrust.refunds'::regclass
  ) THEN
    ALTER TABLE edutrust.refunds
    ADD CONSTRAINT chk_refunds_v1_3_provider_refund_id_trim
    CHECK (
      provider_refund_id IS NULL
      OR length(trim(provider_refund_id)) > 0
    ) NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_refunds_v1_3_reconciliation_reference_trim'
      AND conrelid = 'edutrust.refunds'::regclass
  ) THEN
    ALTER TABLE edutrust.refunds
    ADD CONSTRAINT chk_refunds_v1_3_reconciliation_reference_trim
    CHECK (
      reconciliation_reference IS NULL
      OR length(trim(reconciliation_reference)) > 0
    ) NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_refunds_v1_3_reconciliation_consistency'
      AND conrelid = 'edutrust.refunds'::regclass
  ) THEN
    ALTER TABLE edutrust.refunds
    ADD CONSTRAINT chk_refunds_v1_3_reconciliation_consistency
    CHECK (
      (
        reconciliation_source IS NULL
        AND reconciliation_reference IS NULL
        AND reconciled_at IS NULL
        AND reconciled_by_user_id IS NULL
      )
      OR
      (
        reconciliation_source IS NOT NULL
        AND reconciliation_reference IS NOT NULL
        AND length(trim(reconciliation_reference)) > 0
        AND reconciled_at IS NOT NULL
        AND (
          reconciliation_source::text NOT IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE')
          OR reconciled_by_user_id IS NOT NULL
        )
      )
    ) NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_refunds_v1_3_state_data_cleanliness'
      AND conrelid = 'edutrust.refunds'::regclass
  ) THEN
    ALTER TABLE edutrust.refunds
    ADD CONSTRAINT chk_refunds_v1_3_state_data_cleanliness
    CHECK (
      CASE status::text
        WHEN 'REQUESTED' THEN
          provider_refund_id IS NULL
          AND reconciliation_source IS NULL
          AND reconciliation_reference IS NULL
          AND reconciled_at IS NULL
          AND reconciled_by_user_id IS NULL
          AND approved_amount IS NULL
          AND approved_by_user_id IS NULL
          AND approved_by_role IS NULL
          AND approved_at IS NULL
          AND COALESCE(teacher_adjustment_amount, 0) = 0
          AND COALESCE(platform_adjustment_amount, 0) = 0
          AND provider_submitted_at IS NULL
          AND completed_at IS NULL
          AND failed_at IS NULL
          AND rejected_at IS NULL
          AND cancelled_at IS NULL
        WHEN 'REJECTED' THEN
          provider_refund_id IS NULL
          AND reconciliation_source IS NULL
          AND reconciliation_reference IS NULL
          AND reconciled_at IS NULL
          AND reconciled_by_user_id IS NULL
          AND approved_amount IS NULL
          AND approved_by_user_id IS NULL
          AND approved_by_role IS NULL
          AND approved_at IS NULL
          AND COALESCE(teacher_adjustment_amount, 0) = 0
          AND COALESCE(platform_adjustment_amount, 0) = 0
          AND provider_submitted_at IS NULL
          AND completed_at IS NULL
          AND failed_at IS NULL
          AND cancelled_at IS NULL
        WHEN 'CANCELLED' THEN
          provider_refund_id IS NULL
          AND reconciliation_source IS NULL
          AND reconciliation_reference IS NULL
          AND reconciled_at IS NULL
          AND reconciled_by_user_id IS NULL
          AND provider_submitted_at IS NULL
          AND completed_at IS NULL
          AND failed_at IS NULL
          AND rejected_at IS NULL
        ELSE TRUE
      END
    ) NOT VALID;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_refunds_v1_3_succeeded_proof'
      AND conrelid = 'edutrust.refunds'::regclass
  ) THEN
    ALTER TABLE edutrust.refunds
    ADD CONSTRAINT chk_refunds_v1_3_succeeded_proof
    CHECK (
      status::text <> 'SUCCEEDED'
      OR
      (
        provider_refund_id IS NOT NULL
        AND length(trim(provider_refund_id)) > 0
      )
      OR
      (
        reconciliation_source IS NOT NULL
        AND reconciliation_reference IS NOT NULL
        AND length(trim(reconciliation_reference)) > 0
        AND reconciled_at IS NOT NULL
        AND (
          reconciliation_source::text NOT IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE')
          OR reconciled_by_user_id IS NOT NULL
        )
      )
    ) NOT VALID;
  END IF;
END $$;

-- =========================================================
-- 2. REFUND HARDENING TRIGGER
--    This trigger provides clear error messages and enforces the
--    same rules for new/updated rows. It intentionally does not
--    replace validate_refund_integrity() from v1.1/v1.2; it layers
--    final hardening on top.
-- =========================================================

CREATE OR REPLACE FUNCTION validate_refund_hardening_v1_3()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  status_text TEXT;
  source_text TEXT;
  provider_refund_id_valid BOOLEAN;
  reconciliation_valid BOOLEAN;
BEGIN
  status_text := NEW.status::text;
  source_text := CASE
    WHEN NEW.reconciliation_source IS NULL THEN NULL
    ELSE NEW.reconciliation_source::text
  END;

  -- Provider refund identity must not be whitespace-only.
  IF NEW.provider_refund_id IS NOT NULL AND length(trim(NEW.provider_refund_id)) = 0 THEN
    RAISE EXCEPTION 'provider_refund_id must contain non-whitespace content when present';
  END IF;

  -- Reconciliation reference must not be whitespace-only.
  IF NEW.reconciliation_reference IS NOT NULL AND length(trim(NEW.reconciliation_reference)) = 0 THEN
    RAISE EXCEPTION 'reconciliation_reference must contain non-whitespace content when present';
  END IF;

  -- Reconciliation source/metadata consistency.
  IF NEW.reconciliation_source IS NOT NULL THEN
    IF NEW.reconciliation_reference IS NULL OR length(trim(NEW.reconciliation_reference)) = 0 THEN
      RAISE EXCEPTION 'reconciliation_source requires non-empty reconciliation_reference';
    END IF;

    IF NEW.reconciled_at IS NULL THEN
      RAISE EXCEPTION 'reconciliation_source requires reconciled_at';
    END IF;

    IF source_text IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE')
       AND NEW.reconciled_by_user_id IS NULL THEN
      RAISE EXCEPTION 'Manual/admin reconciliation requires reconciled_by_user_id';
    END IF;
  ELSE
    IF NEW.reconciliation_reference IS NOT NULL
       OR NEW.reconciled_at IS NOT NULL
       OR NEW.reconciled_by_user_id IS NOT NULL THEN
      RAISE EXCEPTION 'reconciliation_reference, reconciled_at, and reconciled_by_user_id must be NULL when reconciliation_source is NULL';
    END IF;
  END IF;

  -- REQUESTED must contain no provider, reconciliation, approval, or terminal-state data.
  IF status_text = 'REQUESTED' THEN
    IF NEW.provider_refund_id IS NOT NULL
       OR NEW.reconciliation_source IS NOT NULL
       OR NEW.reconciliation_reference IS NOT NULL
       OR NEW.reconciled_at IS NOT NULL
       OR NEW.reconciled_by_user_id IS NOT NULL
       OR NEW.approved_amount IS NOT NULL
       OR NEW.approved_by_user_id IS NOT NULL
       OR NEW.approved_by_role IS NOT NULL
       OR NEW.approved_at IS NOT NULL
       OR COALESCE(NEW.teacher_adjustment_amount, 0) <> 0
       OR COALESCE(NEW.platform_adjustment_amount, 0) <> 0
       OR NEW.provider_submitted_at IS NOT NULL
       OR NEW.completed_at IS NOT NULL
       OR NEW.failed_at IS NOT NULL
       OR NEW.rejected_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL THEN
      RAISE EXCEPTION 'REQUESTED refund cannot contain provider, reconciliation, approval, allocation, or terminal-state data';
    END IF;
  END IF;

  -- REJECTED must contain no provider, reconciliation, provider submission, success/failure/cancel, or approval data.
  IF status_text = 'REJECTED' THEN
    IF NEW.provider_refund_id IS NOT NULL
       OR NEW.reconciliation_source IS NOT NULL
       OR NEW.reconciliation_reference IS NOT NULL
       OR NEW.reconciled_at IS NOT NULL
       OR NEW.reconciled_by_user_id IS NOT NULL
       OR NEW.approved_amount IS NOT NULL
       OR NEW.approved_by_user_id IS NOT NULL
       OR NEW.approved_by_role IS NOT NULL
       OR NEW.approved_at IS NOT NULL
       OR COALESCE(NEW.teacher_adjustment_amount, 0) <> 0
       OR COALESCE(NEW.platform_adjustment_amount, 0) <> 0
       OR NEW.provider_submitted_at IS NOT NULL
       OR NEW.completed_at IS NOT NULL
       OR NEW.failed_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL THEN
      RAISE EXCEPTION 'REJECTED refund cannot contain provider, reconciliation, provider submission, approval, allocation, or success/failure/cancel data';
    END IF;
  END IF;

  -- CANCELLED is a pre-provider-submission cancellation in MVP v1.3.
  -- Historical provider evidence belongs in payment_provider_events/event_ledger, not refunds.
  IF status_text = 'CANCELLED' THEN
    IF NEW.provider_refund_id IS NOT NULL
       OR NEW.reconciliation_source IS NOT NULL
       OR NEW.reconciliation_reference IS NOT NULL
       OR NEW.reconciled_at IS NOT NULL
       OR NEW.reconciled_by_user_id IS NOT NULL
       OR NEW.provider_submitted_at IS NOT NULL
       OR NEW.completed_at IS NOT NULL
       OR NEW.failed_at IS NOT NULL
       OR NEW.rejected_at IS NOT NULL THEN
      RAISE EXCEPTION 'CANCELLED refund cannot contain provider identity, reconciliation data, provider submission, success, failure, or rejection data';
    END IF;
  END IF;

  provider_refund_id_valid :=
    NEW.provider_refund_id IS NOT NULL
    AND length(trim(NEW.provider_refund_id)) > 0;

  reconciliation_valid :=
    NEW.reconciliation_source IS NOT NULL
    AND NEW.reconciliation_reference IS NOT NULL
    AND length(trim(NEW.reconciliation_reference)) > 0
    AND NEW.reconciled_at IS NOT NULL
    AND (
      source_text NOT IN ('MANUAL_RECONCILIATION', 'ADMIN_OVERRIDE')
      OR NEW.reconciled_by_user_id IS NOT NULL
    );

  IF status_text = 'SUCCEEDED' AND NOT (provider_refund_id_valid OR reconciliation_valid) THEN
    RAISE EXCEPTION 'SUCCEEDED refund requires valid provider_refund_id or explicit valid reconciliation proof';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_refunds_hardening_v1_3 ON edutrust.refunds;
CREATE TRIGGER trg_refunds_hardening_v1_3
BEFORE INSERT OR UPDATE OF
  status,
  provider_refund_id,
  reconciliation_source,
  reconciliation_reference,
  reconciled_at,
  reconciled_by_user_id,
  provider_submitted_at,
  completed_at,
  failed_at,
  rejected_at,
  cancelled_at,
  approved_amount,
  approved_by_user_id,
  approved_by_role,
  approved_at,
  teacher_adjustment_amount,
  platform_adjustment_amount
ON edutrust.refunds
FOR EACH ROW EXECUTE FUNCTION validate_refund_hardening_v1_3();

-- =========================================================
-- 3. API IDEMPOTENCY LIFECYCLE + IMMUTABILITY
-- =========================================================

CREATE OR REPLACE FUNCTION validate_api_idempotency_lifecycle_v1_3()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.status::text <> 'PROCESSING' THEN
      RAISE EXCEPTION 'api_idempotency_keys must be inserted with status PROCESSING';
    END IF;

    IF NEW.scope IS NULL OR length(trim(NEW.scope)) < 2 THEN
      RAISE EXCEPTION 'api_idempotency_keys.scope is required';
    END IF;

    IF NEW.actor_key IS NULL OR length(trim(NEW.actor_key)) < 3 THEN
      RAISE EXCEPTION 'api_idempotency_keys.actor_key is required';
    END IF;

    IF NEW.idempotency_key IS NULL OR length(trim(NEW.idempotency_key)) < 16 THEN
      RAISE EXCEPTION 'api_idempotency_keys.idempotency_key is required';
    END IF;

    IF NEW.request_hash IS NULL OR length(trim(NEW.request_hash)) < 32 THEN
      RAISE EXCEPTION 'api_idempotency_keys.request_hash is required';
    END IF;

    RETURN NEW;
  END IF;

  -- Identity fields are immutable. The same idempotency identity must never be reused
  -- or reshaped for a different request.
  IF NEW.scope IS DISTINCT FROM OLD.scope
     OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
     OR NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id
     OR NEW.actor_key IS DISTINCT FROM OLD.actor_key
     OR NEW.request_method IS DISTINCT FROM OLD.request_method
     OR NEW.request_path IS DISTINCT FROM OLD.request_path
     OR NEW.request_hash IS DISTINCT FROM OLD.request_hash THEN
    RAISE EXCEPTION 'api_idempotency_keys identity/request fields are immutable';
  END IF;

  -- Allowed lifecycle:
  --   PROCESSING -> COMPLETED
  --   PROCESSING -> FAILED
  -- Staying in the same state is allowed for metadata updates while PROCESSING,
  -- or retention-only updates for terminal states.
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    IF OLD.status::text = 'PROCESSING'
       AND NEW.status::text IN ('COMPLETED', 'FAILED') THEN
      -- allowed
    ELSE
      RAISE EXCEPTION 'Invalid api_idempotency_keys status transition: % -> %', OLD.status, NEW.status;
    END IF;
  END IF;

  -- Terminal records are immutable except retention metadata such as expires_at
  -- and automatic updated_at changes.
  IF OLD.status::text IN ('COMPLETED', 'FAILED') THEN
    IF NEW.response_status IS DISTINCT FROM OLD.response_status
       OR NEW.response_body IS DISTINCT FROM OLD.response_body
       OR NEW.resource_type IS DISTINCT FROM OLD.resource_type
       OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
       OR NEW.locked_until IS DISTINCT FROM OLD.locked_until THEN
      RAISE EXCEPTION 'Terminal api_idempotency_keys records are immutable except retention metadata';
    END IF;
  END IF;

  -- A completed/failed idempotency record should have a replayable response status.
  IF NEW.status::text IN ('COMPLETED', 'FAILED') AND NEW.response_status IS NULL THEN
    RAISE EXCEPTION 'Terminal api_idempotency_keys records require response_status';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_api_idempotency_lifecycle_v1_3 ON edutrust.api_idempotency_keys;
CREATE TRIGGER trg_api_idempotency_lifecycle_v1_3
BEFORE INSERT OR UPDATE OF
  scope,
  idempotency_key,
  actor_user_id,
  actor_key,
  request_method,
  request_path,
  request_hash,
  status,
  response_status,
  response_body,
  resource_type,
  resource_id,
  locked_until
ON edutrust.api_idempotency_keys
FOR EACH ROW EXECUTE FUNCTION validate_api_idempotency_lifecycle_v1_3();

COMMIT;
