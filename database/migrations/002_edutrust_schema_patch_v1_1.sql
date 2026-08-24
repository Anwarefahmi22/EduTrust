-- EduTrust Algeria — Schema Patch v1.1
-- Applies on top of edutrust_schema_v1.sql
-- Purpose:
-- 1. Durable API idempotency storage
-- 2. Provider webhook event identity
-- 3. Dedicated refund lifecycle table
-- 4. Dispute-as-overlay guard for Booking/Session
-- 5. Refund/payout adjustment allocation support
-- Target: PostgreSQL 14+

BEGIN;

SET search_path TO edutrust, public;

-- =========================================================
-- 1. ENUM PATCHES
-- =========================================================

-- Refund lifecycle events. REFUND_ISSUED from v1.0 is deprecated for new refund workflow semantics.
-- PAYMENT_REFUNDED must only be emitted after provider-confirmed successful full refund.
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_REQUESTED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_APPROVED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_PROVIDER_SUBMITTED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_SUCCEEDED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_FAILED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_REJECTED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'REFUND_CANCELLED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'PAYMENT_PARTIALLY_REFUNDED';
ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'PAYMENT_RECONCILIATION_REQUIRED';

-- Additional internal ledger accounts for post-payout adjustments/recoveries.
-- This remains an internal marketplace ledger, not SCF statutory accounting.
ALTER TYPE ledger_account_type ADD VALUE IF NOT EXISTS 'TEACHER_RECOVERABLE';
ALTER TYPE ledger_account_type ADD VALUE IF NOT EXISTS 'PLATFORM_REFUND_EXPENSE';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'edutrust' AND t.typname = 'api_idempotency_status'
  ) THEN
    CREATE TYPE api_idempotency_status AS ENUM ('PROCESSING', 'COMPLETED', 'FAILED');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'edutrust' AND t.typname = 'provider_event_processing_status'
  ) THEN
    CREATE TYPE provider_event_processing_status AS ENUM ('RECEIVED', 'PROCESSING', 'PROCESSED', 'IGNORED', 'FAILED', 'REJECTED');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'edutrust' AND t.typname = 'refund_status'
  ) THEN
    CREATE TYPE refund_status AS ENUM ('REQUESTED', 'APPROVED', 'PROVIDER_PENDING', 'SUCCEEDED', 'FAILED', 'REJECTED', 'CANCELLED');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'edutrust' AND t.typname = 'refund_type'
  ) THEN
    CREATE TYPE refund_type AS ENUM ('FULL', 'PARTIAL');
  END IF;
END $$;

-- =========================================================
-- 2. DISPUTE-AS-OVERLAY GUARDS
-- =========================================================

-- DISPUTED remains in the v1.0 enum for compatibility, but the MVP v1.1 rule is:
-- Booking and Session factual/operational state must not be overwritten by dispute overlay.
-- Dispute state lives in the disputes table.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_bookings_dispute_overlay_no_status'
  ) THEN
    ALTER TABLE bookings
    ADD CONSTRAINT chk_bookings_dispute_overlay_no_status
    CHECK (status <> 'DISPUTED'::booking_status);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_sessions_dispute_overlay_no_status'
  ) THEN
    ALTER TABLE sessions
    ADD CONSTRAINT chk_sessions_dispute_overlay_no_status
    CHECK (status <> 'DISPUTED'::session_status);
  END IF;
END $$;

-- =========================================================
-- 3. API IDEMPOTENCY KEYS
-- =========================================================

CREATE TABLE IF NOT EXISTS api_idempotency_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scope TEXT NOT NULL CHECK (length(trim(scope)) >= 2),
  idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) >= 16),
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  -- Stable actor key used for uniqueness. Examples: 'user:<uuid>', 'admin:<uuid>', 'system:hold-expiry'.
  actor_key TEXT NOT NULL CHECK (length(trim(actor_key)) >= 3),
  request_method TEXT NOT NULL CHECK (request_method IN ('POST', 'PATCH', 'PUT', 'DELETE')),
  request_path TEXT NOT NULL,
  request_hash TEXT NOT NULL CHECK (length(request_hash) >= 32),
  status api_idempotency_status NOT NULL DEFAULT 'PROCESSING',
  response_status INTEGER CHECK (response_status IS NULL OR response_status BETWEEN 100 AND 599),
  response_body JSONB,
  resource_type TEXT,
  resource_id UUID,
  locked_until TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (expires_at > created_at),
  UNIQUE (scope, actor_key, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_api_idempotency_actor_created
ON api_idempotency_keys(actor_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_idempotency_expires
ON api_idempotency_keys(expires_at);

DROP TRIGGER IF EXISTS trg_api_idempotency_touch ON api_idempotency_keys;
CREATE TRIGGER trg_api_idempotency_touch
BEFORE UPDATE ON api_idempotency_keys
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- =========================================================
-- 4. REFUNDS TABLE
-- =========================================================

CREATE TABLE IF NOT EXISTS refunds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
  booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
  dispute_id UUID REFERENCES disputes(id) ON DELETE SET NULL,
  provider payment_provider NOT NULL,
  refund_type refund_type NOT NULL,
  status refund_status NOT NULL DEFAULT 'REQUESTED',
  requested_amount NUMERIC(12,2) NOT NULL CHECK (requested_amount > 0),
  approved_amount NUMERIC(12,2) CHECK (approved_amount IS NULL OR approved_amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  -- Allocation of refund burden. For approved/provider/succeeded refunds:
  -- teacher_adjustment_amount + platform_adjustment_amount must equal approved_amount.
  teacher_adjustment_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (teacher_adjustment_amount >= 0),
  platform_adjustment_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (platform_adjustment_amount >= 0),
  reason TEXT NOT NULL CHECK (length(trim(reason)) >= 3),
  reason_code TEXT,
  provider_refund_id TEXT,
  idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) >= 16),
  requested_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  requested_by_role role_name,
  approved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  approved_by_role role_name,
  approved_at TIMESTAMPTZ,
  provider_submitted_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  rejected_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  failure_code TEXT,
  failure_message TEXT,
  normalized_provider_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (approved_amount IS NULL OR approved_amount <= requested_amount),
  CHECK (status <> 'APPROVED'::refund_status OR (approved_amount IS NOT NULL AND approved_at IS NOT NULL)),
  CHECK (status <> 'PROVIDER_PENDING'::refund_status OR (approved_amount IS NOT NULL AND provider_submitted_at IS NOT NULL)),
  CHECK (status <> 'SUCCEEDED'::refund_status OR (approved_amount IS NOT NULL AND completed_at IS NOT NULL)),
  CHECK (status <> 'FAILED'::refund_status OR failed_at IS NOT NULL),
  CHECK (status <> 'REJECTED'::refund_status OR rejected_at IS NOT NULL),
  CHECK (status <> 'CANCELLED'::refund_status OR cancelled_at IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_refunds_provider_refund_id
ON refunds(provider, provider_refund_id)
WHERE provider_refund_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_refunds_payment_status
ON refunds(payment_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_refunds_booking
ON refunds(booking_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_refunds_dispute
ON refunds(dispute_id)
WHERE dispute_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_refunds_touch ON refunds;
CREATE TRIGGER trg_refunds_touch
BEFORE UPDATE ON refunds
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- =========================================================
-- 5. PROVIDER WEBHOOK EVENT IDENTITY
-- =========================================================

CREATE TABLE IF NOT EXISTS payment_provider_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider payment_provider NOT NULL,
  provider_event_id TEXT NOT NULL CHECK (length(trim(provider_event_id)) >= 3),
  -- Financial transaction identity. Not the same as provider_event_id.
  provider_transaction_id TEXT,
  provider_refund_id TEXT,
  event_type TEXT NOT NULL CHECK (length(trim(event_type)) >= 2),
  status provider_event_processing_status NOT NULL DEFAULT 'RECEIVED',
  payment_id UUID REFERENCES payments(id) ON DELETE SET NULL,
  refund_id UUID REFERENCES refunds(id) ON DELETE SET NULL,
  amount NUMERIC(12,2) CHECK (amount IS NULL OR amount > 0),
  currency CHAR(3) CHECK (currency IS NULL OR currency = 'DZD'),
  occurred_at TIMESTAMPTZ,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ,
  processing_attempts INTEGER NOT NULL DEFAULT 0 CHECK (processing_attempts >= 0),
  payload_hash TEXT,
  normalized_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- If full raw payload must be retained, store it outside this table in encrypted storage.
  raw_payload_storage_key TEXT,
  payload_redacted BOOLEAN NOT NULL DEFAULT TRUE,
  last_error_code TEXT,
  last_error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_payment_provider_events_payment
ON payment_provider_events(payment_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_provider_events_refund
ON payment_provider_events(refund_id, received_at DESC)
WHERE refund_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_provider_events_transaction
ON payment_provider_events(provider, provider_transaction_id, received_at DESC)
WHERE provider_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_provider_events_status
ON payment_provider_events(status, received_at DESC);

DROP TRIGGER IF EXISTS trg_payment_provider_events_touch ON payment_provider_events;
CREATE TRIGGER trg_payment_provider_events_touch
BEFORE UPDATE ON payment_provider_events
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- =========================================================
-- 6. REFUND INTEGRITY TRIGGER
-- =========================================================

CREATE OR REPLACE FUNCTION validate_refund_integrity()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  p RECORD;
  reserved_amount NUMERIC(12,2);
  allocation_total NUMERIC(12,2);
BEGIN
  SELECT id, booking_id, amount, currency, status, provider
  INTO p
  FROM payments
  WHERE id = NEW.payment_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Payment not found for refund: %', NEW.payment_id;
  END IF;

  IF NEW.booking_id <> p.booking_id THEN
    RAISE EXCEPTION 'Refund booking_id must match payment booking_id';
  END IF;

  IF NEW.provider <> p.provider THEN
    RAISE EXCEPTION 'Refund provider must match payment provider';
  END IF;

  IF NEW.currency <> p.currency THEN
    RAISE EXCEPTION 'Refund currency must match payment currency';
  END IF;

  IF p.status NOT IN ('CONFIRMED', 'DISPUTED', 'REFUND_PENDING', 'PARTIALLY_REFUNDED') THEN
    RAISE EXCEPTION 'Refund requires confirmed/refundable payment state. Current payment status: %', p.status;
  END IF;

  IF NEW.approved_amount IS NOT NULL AND NEW.approved_amount > p.amount THEN
    RAISE EXCEPTION 'Refund approved_amount cannot exceed payment amount';
  END IF;

  IF NEW.status IN ('APPROVED', 'PROVIDER_PENDING', 'SUCCEEDED') THEN
    IF NEW.approved_amount IS NULL THEN
      RAISE EXCEPTION 'Approved/provider/succeeded refund requires approved_amount';
    END IF;

    allocation_total := COALESCE(NEW.teacher_adjustment_amount, 0) + COALESCE(NEW.platform_adjustment_amount, 0);
    IF allocation_total <> NEW.approved_amount THEN
      RAISE EXCEPTION 'Refund allocation must equal approved_amount. allocation %, approved %', allocation_total, NEW.approved_amount;
    END IF;

    IF NEW.refund_type = 'FULL'::refund_type AND NEW.approved_amount <> p.amount THEN
      RAISE EXCEPTION 'FULL refund approved_amount must equal payment amount';
    END IF;

    IF NEW.refund_type = 'PARTIAL'::refund_type AND NEW.approved_amount >= p.amount THEN
      RAISE EXCEPTION 'PARTIAL refund approved_amount must be less than payment amount';
    END IF;

    SELECT COALESCE(SUM(approved_amount), 0)
    INTO reserved_amount
    FROM refunds
    WHERE payment_id = NEW.payment_id
      AND id <> NEW.id
      AND status IN ('APPROVED', 'PROVIDER_PENDING', 'SUCCEEDED');

    IF reserved_amount + NEW.approved_amount > p.amount THEN
      RAISE EXCEPTION 'Refund would exceed payment amount. Already reserved/succeeded %, new %, payment %',
        reserved_amount, NEW.approved_amount, p.amount;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_refunds_validate_integrity ON refunds;
CREATE TRIGGER trg_refunds_validate_integrity
BEFORE INSERT OR UPDATE OF payment_id, booking_id, provider, currency, requested_amount, approved_amount, status, refund_type, teacher_adjustment_amount, platform_adjustment_amount
ON refunds
FOR EACH ROW EXECUTE FUNCTION validate_refund_integrity();

-- =========================================================
-- 7. PROVIDER EVENT STATUS TIMESTAMP GUARD
-- =========================================================

CREATE OR REPLACE FUNCTION validate_provider_event_status_fields()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'PROCESSED'::provider_event_processing_status AND NEW.processed_at IS NULL THEN
    NEW.processed_at := now();
  END IF;

  IF NEW.status IN ('FAILED', 'REJECTED') AND NEW.last_error_code IS NULL THEN
    RAISE EXCEPTION 'Failed/rejected provider event requires last_error_code';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_payment_provider_events_validate_status ON payment_provider_events;
CREATE TRIGGER trg_payment_provider_events_validate_status
BEFORE INSERT OR UPDATE OF status, processed_at, last_error_code
ON payment_provider_events
FOR EACH ROW EXECUTE FUNCTION validate_provider_event_status_fields();

COMMIT;
