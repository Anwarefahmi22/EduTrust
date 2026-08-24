-- EduTrust Algeria — PostgreSQL Database Schema v1.0
-- MVP v0.1 foundation: trust marketplace + transaction + verified session graph
-- Target: PostgreSQL 14+

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS edutrust;
SET search_path TO edutrust, public;

-- =========================================================
-- 0. ENUMS
-- =========================================================

CREATE TYPE user_status AS ENUM ('PENDING', 'ACTIVE', 'SUSPENDED', 'DELETED');
CREATE TYPE role_name AS ENUM ('PARENT', 'TEACHER', 'ADMIN', 'OPS', 'SUPPORT');
CREATE TYPE teaching_mode AS ENUM ('ONLINE', 'IN_PERSON', 'HYBRID');
CREATE TYPE consent_status AS ENUM ('PENDING', 'GRANTED', 'REVOKED');
CREATE TYPE student_status AS ENUM ('ACTIVE', 'ARCHIVED', 'DELETED');
CREATE TYPE teacher_verification_status AS ENUM ('UNVERIFIED', 'SUBMITTED', 'IDENTITY_VERIFIED', 'QUALIFICATION_REVIEWED', 'REJECTED', 'SUSPENDED');
CREATE TYPE teacher_listing_status AS ENUM ('DRAFT', 'PENDING_REVIEW', 'LISTED', 'PAUSED', 'SUSPENDED');
CREATE TYPE verification_type AS ENUM ('IDENTITY', 'QUALIFICATION', 'EXPERIENCE', 'BACKGROUND_CHECK');
CREATE TYPE verification_review_status AS ENUM ('SUBMITTED', 'APPROVED', 'REJECTED', 'EXPIRED');
CREATE TYPE document_status AS ENUM ('UPLOADED', 'APPROVED', 'REJECTED', 'DELETED');
CREATE TYPE availability_slot_status AS ENUM ('AVAILABLE', 'HELD', 'BOOKED', 'BLOCKED', 'EXPIRED', 'CANCELLED');
CREATE TYPE booking_status AS ENUM ('HELD', 'PAYMENT_PENDING', 'BOOKED', 'COMPLETED', 'CANCELLED', 'DISPUTED', 'REFUNDED', 'EXPIRED');
CREATE TYPE payment_provider AS ENUM ('CIB', 'EDAHABIA', 'CASH_PILOT', 'BANK_TRANSFER', 'OTHER');
CREATE TYPE payment_status AS ENUM ('NOT_STARTED', 'INITIATED', 'PENDING', 'CONFIRMED', 'FAILED', 'REFUND_PENDING', 'REFUNDED', 'PARTIALLY_REFUNDED', 'DISPUTED');
CREATE TYPE session_status AS ENUM ('SCHEDULED', 'STARTED', 'COMPLETED', 'NO_SHOW_STUDENT', 'NO_SHOW_TEACHER', 'CANCELLED', 'DISPUTED');
CREATE TYPE attendance_status AS ENUM ('UNKNOWN', 'PRESENT', 'STUDENT_ABSENT', 'TEACHER_ABSENT', 'PARTIAL');
CREATE TYPE participation_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'EXCELLENT');
CREATE TYPE progress_event_type AS ENUM ('TOPIC_COVERED', 'SKILL_PRACTICED', 'WEAKNESS_OBSERVED', 'STRENGTH_OBSERVED', 'HOMEWORK_ASSIGNED', 'HOMEWORK_COMPLETED', 'PROGRESS_NOTE', 'PARTICIPATION_NOTE');
CREATE TYPE progress_source_type AS ENUM ('TEACHER_REPORT', 'TEACHER_OBSERVATION', 'HOMEWORK', 'ADMIN_CORRECTION');
CREATE TYPE review_status AS ENUM ('VISIBLE', 'FLAGGED', 'HIDDEN', 'REMOVED');
CREATE TYPE dispute_category AS ENUM ('TEACHER_NO_SHOW', 'STUDENT_NO_SHOW', 'SESSION_QUALITY', 'PAYMENT_REFUND', 'SAFETY', 'REPORT_ISSUE', 'OTHER');
CREATE TYPE dispute_status AS ENUM ('OPEN', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED', 'CANCELLED');
CREATE TYPE notification_channel AS ENUM ('IN_APP', 'SMS', 'EMAIL', 'PUSH');
CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'DELIVERED', 'FAILED', 'READ');
CREATE TYPE payout_status AS ENUM ('PENDING', 'ELIGIBLE', 'PROCESSING', 'PAID', 'FAILED', 'CANCELLED');
CREATE TYPE ledger_transaction_type AS ENUM ('PARENT_PAYMENT', 'PLATFORM_COMMISSION', 'TEACHER_PAYOUT', 'REFUND', 'ADJUSTMENT');
CREATE TYPE ledger_transaction_status AS ENUM ('DRAFT', 'POSTED', 'VOIDED');
CREATE TYPE ledger_direction AS ENUM ('DEBIT', 'CREDIT');
CREATE TYPE ledger_account_type AS ENUM ('PARENT_CASH', 'PAYMENT_PROVIDER_CLEARING', 'PLATFORM_CASH', 'PLATFORM_REVENUE', 'TEACHER_PAYABLE', 'TEACHER_CASH', 'REFUND_PAYABLE', 'ADJUSTMENT');
CREATE TYPE event_type AS ENUM (
  'USER_REGISTERED', 'USER_LOGIN', 'STUDENT_PROFILE_CREATED', 'STUDENT_PROFILE_UPDATED',
  'TEACHER_PROFILE_CREATED', 'TEACHER_PROFILE_UPDATED', 'TEACHER_VERIFICATION_SUBMITTED',
  'TEACHER_VERIFIED', 'TEACHER_REJECTED', 'SLOT_CREATED', 'SLOT_UPDATED', 'SLOT_BLOCKED',
  'BOOKING_CREATED', 'BOOKING_HELD', 'BOOKING_CONFIRMED', 'BOOKING_CANCELLED',
  'PAYMENT_INITIATED', 'PAYMENT_CONFIRMED', 'PAYMENT_FAILED', 'PAYMENT_REFUNDED',
  'SESSION_STARTED', 'SESSION_COMPLETED', 'SESSION_NO_SHOW', 'REPORT_CREATED',
  'REVIEW_CREATED', 'DISPUTE_OPENED', 'DISPUTE_RESOLVED', 'REFUND_ISSUED',
  'PAYOUT_ELIGIBLE', 'PAYOUT_PROCESSED', 'ADMIN_ACTION', 'SECURITY_EVENT'
);
CREATE TYPE security_event_type AS ENUM ('LOGIN_FAILED', 'TOKEN_REVOKED', 'PASSWORD_CHANGED', 'SUSPICIOUS_ACTIVITY', 'RATE_LIMITED', 'ADMIN_ACCESS', 'DOCUMENT_ACCESS');

-- =========================================================
-- 1. IDENTITY & ACCESS
-- =========================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name TEXT NOT NULL CHECK (length(trim(full_name)) >= 2),
  phone_e164 CITEXT UNIQUE,
  email CITEXT UNIQUE,
  password_hash TEXT,
  status user_status NOT NULL DEFAULT 'ACTIVE',
  preferred_locale TEXT NOT NULL DEFAULT 'ar-DZ',
  last_login_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (phone_e164 IS NOT NULL OR email IS NOT NULL)
);

CREATE TABLE roles (
  name role_name PRIMARY KEY,
  description TEXT
);

INSERT INTO roles (name, description) VALUES
  ('PARENT', 'Parent or legal guardian'),
  ('TEACHER', 'Verified or applicant teacher'),
  ('ADMIN', 'Platform administrator'),
  ('OPS', 'Operations user'),
  ('SUPPORT', 'Support agent')
ON CONFLICT DO NOTHING;

CREATE TABLE user_roles (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role role_name NOT NULL REFERENCES roles(name),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, role)
);

CREATE TABLE auth_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  refresh_token_hash TEXT NOT NULL UNIQUE,
  device_label TEXT,
  ip_address INET,
  user_agent TEXT,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (expires_at > created_at)
);

CREATE TABLE security_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type security_event_type NOT NULL,
  severity SMALLINT NOT NULL DEFAULT 1 CHECK (severity BETWEEN 1 AND 5),
  ip_address INET,
  user_agent TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 2. TAXONOMY
-- =========================================================

CREATE TABLE subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  name_ar TEXT NOT NULL,
  name_fr TEXT,
  name_en TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE academic_levels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  name_ar TEXT NOT NULL,
  name_fr TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 3. PARENT & STUDENT
-- =========================================================

CREATE TABLE parent_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
  preferred_language TEXT NOT NULL DEFAULT 'ar',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE student_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id UUID NOT NULL REFERENCES parent_profiles(id) ON DELETE RESTRICT,
  display_name TEXT NOT NULL CHECK (length(trim(display_name)) >= 1),
  birth_year SMALLINT CHECK (birth_year IS NULL OR birth_year BETWEEN 1990 AND 2035),
  academic_level_id UUID REFERENCES academic_levels(id) ON DELETE SET NULL,
  school_year TEXT,
  primary_goal TEXT,
  preferred_mode teaching_mode,
  consent_status consent_status NOT NULL DEFAULT 'GRANTED',
  status student_status NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (id, parent_id)
);

-- =========================================================
-- 4. TEACHER
-- =========================================================

CREATE TABLE teacher_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
  public_name TEXT NOT NULL CHECK (length(trim(public_name)) >= 2),
  profile_photo_storage_key TEXT,
  bio TEXT,
  methodology TEXT,
  experience_years NUMERIC(4,1) CHECK (experience_years IS NULL OR experience_years >= 0),
  languages TEXT[] NOT NULL DEFAULT ARRAY['ar'],
  teaching_modes teaching_mode[] NOT NULL DEFAULT ARRAY['ONLINE']::teaching_mode[],
  base_wilaya_code TEXT,
  base_commune TEXT,
  service_area TEXT,
  verification_status teacher_verification_status NOT NULL DEFAULT 'UNVERIFIED',
  listing_status teacher_listing_status NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (array_length(languages, 1) IS NULL OR array_length(languages, 1) > 0),
  CHECK (array_length(teaching_modes, 1) IS NULL OR array_length(teaching_modes, 1) > 0)
);

CREATE TABLE teacher_verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  verification_type verification_type NOT NULL,
  status verification_review_status NOT NULL DEFAULT 'SUBMITTED',
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  reviewer_note TEXT,
  rejection_reason TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE verification_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  verification_id UUID NOT NULL REFERENCES teacher_verifications(id) ON DELETE CASCADE,
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  document_type TEXT NOT NULL,
  storage_key TEXT NOT NULL UNIQUE,
  sha256_hash TEXT,
  file_mime_type TEXT,
  file_size_bytes BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes > 0),
  encrypted BOOLEAN NOT NULL DEFAULT TRUE,
  status document_status NOT NULL DEFAULT 'UPLOADED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE teacher_subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  academic_level_id UUID NOT NULL REFERENCES academic_levels(id) ON DELETE RESTRICT,
  price_amount NUMERIC(12,2) NOT NULL CHECK (price_amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  session_duration_minutes INTEGER NOT NULL DEFAULT 60 CHECK (session_duration_minutes BETWEEN 30 AND 240),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (teacher_id, subject_id, academic_level_id),
  UNIQUE (id, teacher_id, subject_id, academic_level_id)
);

CREATE TABLE student_permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL,
  parent_id UUID NOT NULL,
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  granted_for_booking_id UUID,
  scope TEXT NOT NULL DEFAULT 'SESSION_CONTEXT',
  starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (student_id, parent_id) REFERENCES student_profiles(id, parent_id) ON DELETE CASCADE,
  CHECK (expires_at IS NULL OR expires_at > starts_at)
);

-- Current metrics are derived, not user-editable source of truth.
-- Raw source tables remain: sessions, bookings, payments, reports, reviews, disputes.
CREATE TABLE teacher_trust_metrics (
  teacher_id UUID PRIMARY KEY REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  completed_sessions_count INTEGER NOT NULL DEFAULT 0 CHECK (completed_sessions_count >= 0),
  attendance_rate NUMERIC(5,2) CHECK (attendance_rate IS NULL OR attendance_rate BETWEEN 0 AND 100),
  cancellation_rate NUMERIC(5,2) CHECK (cancellation_rate IS NULL OR cancellation_rate BETWEEN 0 AND 100),
  avg_response_seconds INTEGER CHECK (avg_response_seconds IS NULL OR avg_response_seconds >= 0),
  verified_rating NUMERIC(3,2) CHECK (verified_rating IS NULL OR verified_rating BETWEEN 1 AND 5),
  review_count INTEGER NOT NULL DEFAULT 0 CHECK (review_count >= 0),
  dispute_rate NUMERIC(5,2) CHECK (dispute_rate IS NULL OR dispute_rate BETWEEN 0 AND 100),
  repeat_booking_rate NUMERIC(5,2) CHECK (repeat_booking_rate IS NULL OR repeat_booking_rate BETWEEN 0 AND 100),
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 5. AVAILABILITY & MARKETPLACE
-- =========================================================

CREATE TABLE availability_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  mode teaching_mode NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Africa/Algiers',
  effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
  effective_to DATE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_time > start_time),
  CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE availability_slots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
  rule_id UUID REFERENCES availability_rules(id) ON DELETE SET NULL,
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  mode teaching_mode NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Africa/Algiers',
  status availability_slot_status NOT NULL DEFAULT 'AVAILABLE',
  held_until TIMESTAMPTZ,
  held_by_parent_id UUID REFERENCES parent_profiles(id) ON DELETE SET NULL,
  blocked_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (ends_at > starts_at),
  UNIQUE (id, teacher_id, starts_at, ends_at, mode)
);

ALTER TABLE availability_slots
ADD CONSTRAINT ex_no_overlapping_active_teacher_slots
EXCLUDE USING gist (
  teacher_id WITH =,
  tstzrange(starts_at, ends_at, '[)') WITH &&
)
WHERE (status IN ('AVAILABLE', 'HELD', 'BOOKED'));

CREATE TABLE bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_number TEXT UNIQUE,
  parent_id UUID NOT NULL REFERENCES parent_profiles(id) ON DELETE RESTRICT,
  student_id UUID NOT NULL,
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE RESTRICT,
  teacher_subject_id UUID NOT NULL,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  academic_level_id UUID NOT NULL REFERENCES academic_levels(id) ON DELETE RESTRICT,
  availability_slot_id UUID NOT NULL,
  scheduled_start TIMESTAMPTZ NOT NULL,
  scheduled_end TIMESTAMPTZ NOT NULL,
  mode teaching_mode NOT NULL,
  price_amount NUMERIC(12,2) NOT NULL CHECK (price_amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  platform_commission_bps INTEGER NOT NULL DEFAULT 1500 CHECK (platform_commission_bps BETWEEN 0 AND 10000),
  status booking_status NOT NULL DEFAULT 'HELD',
  hold_expires_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  cancelled_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  cancelled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (scheduled_end > scheduled_start),
  FOREIGN KEY (student_id, parent_id) REFERENCES student_profiles(id, parent_id) ON DELETE RESTRICT,
  FOREIGN KEY (teacher_subject_id, teacher_id, subject_id, academic_level_id)
    REFERENCES teacher_subjects(id, teacher_id, subject_id, academic_level_id) ON DELETE RESTRICT,
  FOREIGN KEY (availability_slot_id, teacher_id, scheduled_start, scheduled_end, mode)
    REFERENCES availability_slots(id, teacher_id, starts_at, ends_at, mode) ON DELETE RESTRICT,
  UNIQUE (id, parent_id),
  UNIQUE (id, student_id),
  UNIQUE (id, teacher_id),
  UNIQUE (id, subject_id, academic_level_id)
);

CREATE UNIQUE INDEX ux_one_active_booking_per_slot
ON bookings(availability_slot_id)
WHERE status IN ('HELD', 'PAYMENT_PENDING', 'BOOKED', 'COMPLETED', 'DISPUTED');

ALTER TABLE student_permissions
ADD CONSTRAINT fk_student_permissions_booking
FOREIGN KEY (granted_for_booking_id) REFERENCES bookings(id) ON DELETE SET NULL;

-- =========================================================
-- 6. PAYMENTS
-- =========================================================

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL,
  parent_id UUID NOT NULL,
  provider payment_provider NOT NULL,
  provider_transaction_id TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  provider_fee_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (provider_fee_amount >= 0),
  status payment_status NOT NULL DEFAULT 'INITIATED',
  initiated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confirmed_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ,
  raw_provider_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (booking_id, parent_id) REFERENCES bookings(id, parent_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX ux_payments_provider_transaction
ON payments(provider, provider_transaction_id)
WHERE provider_transaction_id IS NOT NULL;

CREATE UNIQUE INDEX ux_one_confirmed_payment_per_booking
ON payments(booking_id)
WHERE status = 'CONFIRMED';

-- =========================================================
-- 7. EDUCATION: SESSIONS, REPORTS, PASSPORT DATA
-- =========================================================

CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE RESTRICT,
  parent_id UUID NOT NULL,
  student_id UUID NOT NULL,
  teacher_id UUID NOT NULL,
  subject_id UUID NOT NULL,
  academic_level_id UUID NOT NULL,
  scheduled_start TIMESTAMPTZ NOT NULL,
  scheduled_end TIMESTAMPTZ NOT NULL,
  actual_start TIMESTAMPTZ,
  actual_end TIMESTAMPTZ,
  status session_status NOT NULL DEFAULT 'SCHEDULED',
  attendance_status attendance_status NOT NULL DEFAULT 'UNKNOWN',
  invitation_code TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (scheduled_end > scheduled_start),
  CHECK (actual_end IS NULL OR actual_start IS NOT NULL),
  CHECK (actual_end IS NULL OR actual_end > actual_start),
  CHECK (status <> 'COMPLETED' OR (actual_start IS NOT NULL AND actual_end IS NOT NULL AND attendance_status = 'PRESENT')),
  FOREIGN KEY (booking_id, parent_id) REFERENCES bookings(id, parent_id) ON DELETE RESTRICT,
  FOREIGN KEY (booking_id, student_id) REFERENCES bookings(id, student_id) ON DELETE RESTRICT,
  FOREIGN KEY (booking_id, teacher_id) REFERENCES bookings(id, teacher_id) ON DELETE RESTRICT,
  FOREIGN KEY (booking_id, subject_id, academic_level_id) REFERENCES bookings(id, subject_id, academic_level_id) ON DELETE RESTRICT,
  UNIQUE (id, parent_id),
  UNIQUE (id, student_id),
  UNIQUE (id, teacher_id),
  UNIQUE (id, booking_id)
);

CREATE TABLE session_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL UNIQUE,
  teacher_id UUID NOT NULL,
  student_id UUID NOT NULL,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  topics_covered TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  skills_practiced TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  participation participation_level,
  teacher_observations TEXT,
  homework TEXT,
  recommended_revision TEXT,
  next_objectives TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  progress_indicator SMALLINT CHECK (progress_indicator IS NULL OR progress_indicator BETWEEN -5 AND 5),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (session_id, teacher_id) REFERENCES sessions(id, teacher_id) ON DELETE RESTRICT,
  FOREIGN KEY (session_id, student_id) REFERENCES sessions(id, student_id) ON DELETE RESTRICT
);

CREATE TABLE student_progress_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
  session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
  report_id UUID REFERENCES session_reports(id) ON DELETE SET NULL,
  subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
  event_type progress_event_type NOT NULL,
  source_type progress_source_type NOT NULL DEFAULT 'TEACHER_REPORT',
  topic TEXT,
  value_numeric NUMERIC(6,2),
  note TEXT,
  created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 8. TRUST & OPERATIONS
-- =========================================================

CREATE TABLE reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL UNIQUE,
  booking_id UUID NOT NULL,
  parent_id UUID NOT NULL,
  student_id UUID NOT NULL,
  teacher_id UUID NOT NULL,
  rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  status review_status NOT NULL DEFAULT 'VISIBLE',
  is_verified BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_verified = TRUE),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (session_id, booking_id) REFERENCES sessions(id, booking_id) ON DELETE RESTRICT,
  FOREIGN KEY (session_id, parent_id) REFERENCES sessions(id, parent_id) ON DELETE RESTRICT,
  FOREIGN KEY (session_id, student_id) REFERENCES sessions(id, student_id) ON DELETE RESTRICT,
  FOREIGN KEY (session_id, teacher_id) REFERENCES sessions(id, teacher_id) ON DELETE RESTRICT
);

CREATE TABLE disputes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID REFERENCES bookings(id) ON DELETE RESTRICT,
  session_id UUID REFERENCES sessions(id) ON DELETE RESTRICT,
  payment_id UUID REFERENCES payments(id) ON DELETE RESTRICT,
  opened_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  category dispute_category NOT NULL,
  status dispute_status NOT NULL DEFAULT 'OPEN',
  priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  description TEXT,
  assigned_admin_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  resolution TEXT,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (booking_id IS NOT NULL OR session_id IS NOT NULL OR payment_id IS NOT NULL)
);

CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel notification_channel NOT NULL,
  event_type event_type,
  entity_type TEXT,
  entity_id UUID,
  title TEXT,
  body TEXT,
  status notification_status NOT NULL DEFAULT 'PENDING',
  provider_message_id TEXT,
  scheduled_for TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  read_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 9. PAYOUTS & LEDGER
-- =========================================================

CREATE TABLE payouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE RESTRICT,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  status payout_status NOT NULL DEFAULT 'PENDING',
  eligible_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  provider_reference TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payout_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payout_id UUID NOT NULL REFERENCES payouts(id) ON DELETE CASCADE,
  session_id UUID NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE RESTRICT,
  teacher_id UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE RESTRICT,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ledger_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_type ledger_transaction_type NOT NULL,
  status ledger_transaction_status NOT NULL DEFAULT 'POSTED',
  booking_id UUID REFERENCES bookings(id) ON DELETE RESTRICT,
  payment_id UUID REFERENCES payments(id) ON DELETE RESTRICT,
  payout_id UUID REFERENCES payouts(id) ON DELETE RESTRICT,
  reference TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (booking_id IS NOT NULL OR payment_id IS NOT NULL OR payout_id IS NOT NULL OR transaction_type = 'ADJUSTMENT')
);

CREATE TABLE ledger_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ledger_transaction_id UUID NOT NULL REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
  account_type ledger_account_type NOT NULL,
  direction ledger_direction NOT NULL,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  currency CHAR(3) NOT NULL DEFAULT 'DZD' CHECK (currency = 'DZD'),
  memo TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 10. EVENT LEDGER / AUDIT
-- =========================================================

CREATE TABLE event_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  actor_role role_name,
  event_type event_type NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  request_id UUID,
  idempotency_key TEXT,
  ip_address INET,
  user_agent TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 11. INDEXES
-- =========================================================

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_user_roles_role ON user_roles(role);
CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id, expires_at);
CREATE INDEX idx_security_events_user_created ON security_events(user_id, created_at DESC);

CREATE INDEX idx_student_profiles_parent ON student_profiles(parent_id, status);
CREATE INDEX idx_student_profiles_level ON student_profiles(academic_level_id);

CREATE INDEX idx_teacher_profiles_listing ON teacher_profiles(listing_status, verification_status);
CREATE INDEX idx_teacher_profiles_modes ON teacher_profiles USING GIN(teaching_modes);
CREATE INDEX idx_teacher_profiles_languages ON teacher_profiles USING GIN(languages);
CREATE INDEX idx_teacher_subjects_search ON teacher_subjects(subject_id, academic_level_id, is_active, price_amount);
CREATE INDEX idx_teacher_subjects_teacher ON teacher_subjects(teacher_id, is_active);

CREATE INDEX idx_availability_slots_teacher_time ON availability_slots(teacher_id, starts_at, ends_at);
CREATE INDEX idx_availability_slots_search ON availability_slots(status, starts_at, mode);
CREATE INDEX idx_bookings_parent_status ON bookings(parent_id, status, scheduled_start DESC);
CREATE INDEX idx_bookings_teacher_status ON bookings(teacher_id, status, scheduled_start DESC);
CREATE INDEX idx_bookings_student ON bookings(student_id, scheduled_start DESC);

CREATE INDEX idx_payments_booking_status ON payments(booking_id, status);
CREATE INDEX idx_payments_parent_created ON payments(parent_id, created_at DESC);

CREATE INDEX idx_sessions_teacher_status ON sessions(teacher_id, status, scheduled_start DESC);
CREATE INDEX idx_sessions_student_status ON sessions(student_id, status, scheduled_start DESC);
CREATE INDEX idx_session_reports_student ON session_reports(student_id, created_at DESC);
CREATE INDEX idx_student_progress_events_student ON student_progress_events(student_id, created_at DESC);
CREATE INDEX idx_student_progress_events_subject ON student_progress_events(subject_id, event_type);

CREATE INDEX idx_reviews_teacher_created ON reviews(teacher_id, created_at DESC);
CREATE INDEX idx_disputes_status_priority ON disputes(status, priority, created_at);
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status, created_at DESC);

CREATE INDEX idx_payouts_teacher_status ON payouts(teacher_id, status, created_at DESC);
CREATE INDEX idx_ledger_transactions_refs ON ledger_transactions(booking_id, payment_id, payout_id);
CREATE INDEX idx_ledger_entries_tx ON ledger_entries(ledger_transaction_id);
CREATE INDEX idx_event_ledger_entity ON event_ledger(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_event_ledger_type_created ON event_ledger(event_type, created_at DESC);
CREATE INDEX idx_event_ledger_metadata ON event_ledger USING GIN(metadata);

-- =========================================================
-- 12. TRIGGERS & DATABASE GUARDS
-- =========================================================

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_parent_profiles_touch BEFORE UPDATE ON parent_profiles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_student_profiles_touch BEFORE UPDATE ON student_profiles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_teacher_profiles_touch BEFORE UPDATE ON teacher_profiles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_teacher_subjects_touch BEFORE UPDATE ON teacher_subjects FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_availability_rules_touch BEFORE UPDATE ON availability_rules FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_availability_slots_touch BEFORE UPDATE ON availability_slots FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_bookings_touch BEFORE UPDATE ON bookings FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_payments_touch BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_sessions_touch BEFORE UPDATE ON sessions FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_session_reports_touch BEFORE UPDATE ON session_reports FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_reviews_touch BEFORE UPDATE ON reviews FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_disputes_touch BEFORE UPDATE ON disputes FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_notifications_touch BEFORE UPDATE ON notifications FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_payouts_touch BEFORE UPDATE ON payouts FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE OR REPLACE FUNCTION require_user_role()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE required_role role_name;
BEGIN
  required_role := TG_ARGV[0]::role_name;
  IF NOT EXISTS (
    SELECT 1 FROM user_roles WHERE user_id = NEW.user_id AND role = required_role
  ) THEN
    RAISE EXCEPTION 'User % must have role % before creating this profile', NEW.user_id, required_role;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_parent_requires_role
BEFORE INSERT OR UPDATE OF user_id ON parent_profiles
FOR EACH ROW EXECUTE FUNCTION require_user_role('PARENT');

CREATE TRIGGER trg_teacher_requires_role
BEFORE INSERT OR UPDATE OF user_id ON teacher_profiles
FOR EACH ROW EXECUTE FUNCTION require_user_role('TEACHER');

CREATE OR REPLACE FUNCTION validate_booking_slot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE slot_record availability_slots%ROWTYPE;
BEGIN
  SELECT * INTO slot_record
  FROM availability_slots
  WHERE id = NEW.availability_slot_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Availability slot not found: %', NEW.availability_slot_id;
  END IF;

  IF slot_record.status <> 'AVAILABLE' THEN
    RAISE EXCEPTION 'Slot % is not available; current status is %', NEW.availability_slot_id, slot_record.status;
  END IF;

  IF NEW.status NOT IN ('HELD', 'PAYMENT_PENDING', 'BOOKED') THEN
    RAISE EXCEPTION 'New booking must start as HELD, PAYMENT_PENDING, or BOOKED';
  END IF;

  UPDATE availability_slots
  SET status = CASE WHEN NEW.status = 'BOOKED' THEN 'BOOKED' ELSE 'HELD' END,
      held_until = NEW.hold_expires_at,
      held_by_parent_id = NEW.parent_id,
      updated_at = now()
  WHERE id = NEW.availability_slot_id;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bookings_validate_slot
BEFORE INSERT ON bookings
FOR EACH ROW EXECUTE FUNCTION validate_booking_slot();

CREATE OR REPLACE FUNCTION sync_slot_from_booking_status()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;

  IF NEW.status = 'BOOKED' THEN
    UPDATE availability_slots SET status = 'BOOKED', updated_at = now()
    WHERE id = NEW.availability_slot_id;
  ELSIF NEW.status IN ('CANCELLED', 'EXPIRED', 'REFUNDED') THEN
    UPDATE availability_slots SET status = 'AVAILABLE', held_until = NULL, held_by_parent_id = NULL, updated_at = now()
    WHERE id = NEW.availability_slot_id;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bookings_sync_slot_status
AFTER UPDATE OF status ON bookings
FOR EACH ROW EXECUTE FUNCTION sync_slot_from_booking_status();

CREATE OR REPLACE FUNCTION validate_payment_amount_matches_booking()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE booking_amount NUMERIC(12,2); booking_currency CHAR(3);
BEGIN
  SELECT price_amount, currency INTO booking_amount, booking_currency
  FROM bookings
  WHERE id = NEW.booking_id;

  IF booking_amount IS NULL THEN
    RAISE EXCEPTION 'Booking not found for payment: %', NEW.booking_id;
  END IF;

  IF NEW.amount <> booking_amount OR NEW.currency <> booking_currency THEN
    RAISE EXCEPTION 'Payment amount/currency must match booking. Payment % %, Booking % %',
      NEW.amount, NEW.currency, booking_amount, booking_currency;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_payments_validate_amount
BEFORE INSERT OR UPDATE OF amount, currency, booking_id ON payments
FOR EACH ROW EXECUTE FUNCTION validate_payment_amount_matches_booking();

CREATE OR REPLACE FUNCTION validate_session_creation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE b_status booking_status;
BEGIN
  SELECT status INTO b_status FROM bookings WHERE id = NEW.booking_id;

  IF b_status IS NULL THEN
    RAISE EXCEPTION 'Booking not found for session: %', NEW.booking_id;
  END IF;

  IF b_status NOT IN ('BOOKED', 'COMPLETED') THEN
    RAISE EXCEPTION 'Session can only be created from BOOKED booking. Booking % status is %', NEW.booking_id, b_status;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM payments WHERE booking_id = NEW.booking_id AND status = 'CONFIRMED'
  ) THEN
    RAISE EXCEPTION 'Cannot create session without confirmed payment for booking %', NEW.booking_id;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sessions_validate_creation
BEFORE INSERT ON sessions
FOR EACH ROW EXECUTE FUNCTION validate_session_creation();

CREATE OR REPLACE FUNCTION validate_session_completion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'COMPLETED' AND OLD.status IS DISTINCT FROM 'COMPLETED' THEN
    IF NEW.actual_start IS NULL OR NEW.actual_end IS NULL THEN
      RAISE EXCEPTION 'Completed session requires actual_start and actual_end';
    END IF;
    IF NEW.attendance_status <> 'PRESENT' THEN
      RAISE EXCEPTION 'Completed session requires attendance_status = PRESENT';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sessions_validate_completion
BEFORE UPDATE OF status ON sessions
FOR EACH ROW EXECUTE FUNCTION validate_session_completion();

CREATE OR REPLACE FUNCTION sync_booking_after_session_completion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'COMPLETED' AND OLD.status IS DISTINCT FROM 'COMPLETED' THEN
    UPDATE bookings SET status = 'COMPLETED', updated_at = now()
    WHERE id = NEW.booking_id AND status = 'BOOKED';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sessions_sync_booking_completed
AFTER UPDATE OF status ON sessions
FOR EACH ROW EXECUTE FUNCTION sync_booking_after_session_completion();

CREATE OR REPLACE FUNCTION validate_report_for_completed_session()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE s_status session_status; s_teacher UUID; s_student UUID;
BEGIN
  SELECT status, teacher_id, student_id INTO s_status, s_teacher, s_student
  FROM sessions WHERE id = NEW.session_id;

  IF s_status IS NULL THEN
    RAISE EXCEPTION 'Session not found for report: %', NEW.session_id;
  END IF;
  IF s_status <> 'COMPLETED' THEN
    RAISE EXCEPTION 'Report can only be created for COMPLETED session. Current status: %', s_status;
  END IF;
  IF NEW.teacher_id <> s_teacher OR NEW.student_id <> s_student THEN
    RAISE EXCEPTION 'Report teacher/student must match session';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_reports_validate_session
BEFORE INSERT OR UPDATE OF session_id, teacher_id, student_id ON session_reports
FOR EACH ROW EXECUTE FUNCTION validate_report_for_completed_session();

CREATE OR REPLACE FUNCTION validate_review_eligibility()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  s_record sessions%ROWTYPE;
  b_status booking_status;
  parent_user UUID;
  teacher_user UUID;
BEGIN
  SELECT * INTO s_record FROM sessions WHERE id = NEW.session_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Session not found for review: %', NEW.session_id;
  END IF;

  IF s_record.status <> 'COMPLETED' THEN
    RAISE EXCEPTION 'Review requires completed session';
  END IF;

  SELECT status INTO b_status FROM bookings WHERE id = s_record.booking_id;
  IF b_status <> 'COMPLETED' THEN
    RAISE EXCEPTION 'Review requires completed booking. Current booking status: %', b_status;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM payments WHERE booking_id = s_record.booking_id AND status = 'CONFIRMED'
  ) THEN
    RAISE EXCEPTION 'Review requires confirmed payment';
  END IF;

  IF NEW.booking_id <> s_record.booking_id OR NEW.parent_id <> s_record.parent_id
     OR NEW.student_id <> s_record.student_id OR NEW.teacher_id <> s_record.teacher_id THEN
    RAISE EXCEPTION 'Review must match session booking, parent, student, and teacher';
  END IF;

  SELECT user_id INTO parent_user FROM parent_profiles WHERE id = NEW.parent_id;
  SELECT user_id INTO teacher_user FROM teacher_profiles WHERE id = NEW.teacher_id;
  IF parent_user = teacher_user THEN
    RAISE EXCEPTION 'Teacher cannot review themselves';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_reviews_validate_eligibility
BEFORE INSERT OR UPDATE OF session_id, booking_id, parent_id, student_id, teacher_id ON reviews
FOR EACH ROW EXECUTE FUNCTION validate_review_eligibility();

CREATE OR REPLACE FUNCTION validate_payout_item_eligibility()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE s_record sessions%ROWTYPE;
BEGIN
  SELECT * INTO s_record FROM sessions WHERE id = NEW.session_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Session not found for payout item: %', NEW.session_id;
  END IF;

  IF s_record.status <> 'COMPLETED' THEN
    RAISE EXCEPTION 'Payout item requires completed session';
  END IF;

  IF NEW.teacher_id <> s_record.teacher_id THEN
    RAISE EXCEPTION 'Payout teacher must match session teacher';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM session_reports WHERE session_id = NEW.session_id) THEN
    RAISE EXCEPTION 'Payout item requires session report';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM payments WHERE booking_id = s_record.booking_id AND status = 'CONFIRMED') THEN
    RAISE EXCEPTION 'Payout item requires confirmed payment';
  END IF;

  IF EXISTS (
    SELECT 1 FROM disputes
    WHERE status IN ('OPEN', 'UNDER_REVIEW')
      AND (session_id = NEW.session_id OR booking_id = s_record.booking_id)
  ) THEN
    RAISE EXCEPTION 'Payout item blocked by open dispute';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_payout_items_validate_eligibility
BEFORE INSERT OR UPDATE OF session_id, teacher_id ON payout_items
FOR EACH ROW EXECUTE FUNCTION validate_payout_item_eligibility();

CREATE OR REPLACE FUNCTION prevent_event_ledger_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'event_ledger is append-only; updates/deletes are not allowed';
END;
$$;

CREATE TRIGGER trg_event_ledger_no_update
BEFORE UPDATE OR DELETE ON event_ledger
FOR EACH ROW EXECUTE FUNCTION prevent_event_ledger_mutation();

CREATE OR REPLACE FUNCTION prevent_ledger_entry_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ledger_entries are append-only; use reversal entries instead of update/delete';
END;
$$;

CREATE TRIGGER trg_ledger_entries_no_update
BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION prevent_ledger_entry_mutation();

CREATE OR REPLACE FUNCTION enforce_ledger_transaction_balance()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  tx_id UUID;
  debit_total NUMERIC(12,2);
  credit_total NUMERIC(12,2);
  entry_count INTEGER;
BEGIN
  tx_id := COALESCE(NEW.ledger_transaction_id, OLD.ledger_transaction_id);

  SELECT COUNT(*),
         COALESCE(SUM(CASE WHEN direction = 'DEBIT' THEN amount ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE 0 END), 0)
  INTO entry_count, debit_total, credit_total
  FROM ledger_entries
  WHERE ledger_transaction_id = tx_id;

  IF entry_count > 0 AND debit_total <> credit_total THEN
    RAISE EXCEPTION 'Ledger transaction % is not balanced: debit %, credit %', tx_id, debit_total, credit_total;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE CONSTRAINT TRIGGER trg_ledger_entries_balanced
AFTER INSERT ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION enforce_ledger_transaction_balance();

-- Operational guard. In production, combine this with DB GRANTs so only a metrics worker can write.
CREATE OR REPLACE FUNCTION protect_teacher_trust_metrics()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF current_setting('edutrust.internal_metric_update', true) IS DISTINCT FROM 'on' THEN
    RAISE EXCEPTION 'teacher_trust_metrics is derived; direct writes are blocked';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER trg_teacher_trust_metrics_protect
BEFORE INSERT OR UPDATE OR DELETE ON teacher_trust_metrics
FOR EACH ROW EXECUTE FUNCTION protect_teacher_trust_metrics();

COMMIT;
