# EduTrust Algeria — API Contract Addendum v1.1

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Implementation-level API contract addendum  
**Status:** READY FOR REVIEW  
**Architecture baseline:** LOCKED

---

# 1. Purpose

This addendum formalizes API contracts introduced by the approved UX, visual, prototype, and implementation-planning gates.

It does **not** redesign the API architecture. It completes implementation-level contracts needed before frontend/backend work begins.

---

# 2. Global API Rules

| Rule | Requirement |
|---|---|
| Base path | `/api/v1` |
| Auth | Bearer access token unless public/read-reduced endpoint explicitly allowed |
| Request ID | `X-Request-ID` accepted/generated and returned |
| Error format | Approved standard error envelope |
| Pagination | Cursor pagination for list endpoints |
| Money | String decimal amount + `DZD` currency |
| Sensitive data | Never expose raw provider payloads to Parent/Teacher |
| Audit | Sensitive admin access must generate `ADMIN_ACTION` and/or `SECURITY_EVENT` |
| State changes | Must go through approved service authority |
| Recovery creation | **No `POST /admin/recoveries` in MVP** |

Standard error envelope:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found.",
    "request_id": "req_uuid",
    "details": {}
  }
}
```

---

# 3. Notifications API

## 3.1 `GET /notifications`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/notifications` |
| Actor | Parent, Teacher, Admin/OPS/SUPPORT for own notifications; admin notification views may be separate |
| Authorization | Authenticated user |
| Ownership | Return only notifications where `notifications.user_id = current_user.id` |
| Request schema | Query params: `status`, `event_type`, `limit`, `cursor` |
| Pagination | Required, cursor-based |
| Filtering | `status=PENDING|SENT|DELIVERED|FAILED|READ`, `event_type` allowlist |
| Idempotency | Not required |
| State restrictions | Read-only |
| Event Ledger | None for ordinary read |
| Sensitive-data rules | Body/title must not expose sensitive minor/payment payload details |

Response:

```json
{
  "data": [
    {
      "notification_id": "notif_123",
      "event_type": "BOOKING_CONFIRMED",
      "entity_type": "booking",
      "entity_id": "booking_123",
      "title": "Booking confirmed",
      "body": "Your tutoring session has been confirmed.",
      "status": "DELIVERED",
      "created_at": "2026-09-05T10:00:00Z",
      "read_at": null
    }
  ],
  "pagination": { "limit": 20, "next_cursor": null, "has_more": false },
  "request_id": "req_uuid"
}
```

Errors:

```text
AUTH_REQUIRED
FORBIDDEN
VALIDATION_ERROR
RATE_LIMITED
```

## 3.2 `POST /notifications/:id/read`

| Field | Contract |
|---|---|
| Method | `POST` |
| Path | `/api/v1/notifications/:id/read` |
| Actor | Notification owner |
| Authorization | Authenticated user |
| Ownership | Notification must belong to current user |
| Request schema | `{}` |
| Response schema | Notification summary with `status=READ` and `read_at` |
| Idempotency | Recommended; repeated calls return read state |
| State restrictions | Only own notification; already-read is safe replay |
| Event Ledger | Not required by default |
| Sensitive-data rules | Does not expose sensitive target content |

---

# 4. Account / Security APIs

## 4.1 `GET /auth/sessions`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/auth/sessions` |
| Actor | Authenticated user |
| Authorization | Authenticated user |
| Ownership | Own sessions only |
| Request schema | Query: `include_revoked=false`, `limit`, `cursor` |
| Pagination | Required if many sessions |
| Idempotency | Not required |
| State restrictions | Read-only |
| Event Ledger | None for ordinary read |
| Sensitive-data rules | Never expose raw refresh tokens or token hashes |

Response:

```json
{
  "data": [
    {
      "session_id": "session_123",
      "device_label": "Chrome on Android",
      "created_at": "2026-09-01T10:00:00Z",
      "expires_at": "2026-09-30T10:00:00Z",
      "last_used_at": "2026-09-05T09:00:00Z",
      "is_current_session": true,
      "revoked_at": null,
      "approximate_ip_or_region": "Algiers, DZ"
    }
  ],
  "request_id": "req_uuid"
}
```

## 4.2 `GET /account/security-events`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/account/security-events` |
| Actor | Authenticated user |
| Authorization | Authenticated user |
| Ownership | Own user-visible security events only |
| Request schema | Query: `limit`, `cursor`, `severity` |
| Pagination | Required |
| Idempotency | Not required |
| Event Ledger | None for ordinary own read |
| Sensitive-data rules | Admin-only details remain excluded |

Response:

```json
{
  "data": [
    {
      "security_event_id": "sec_123",
      "event_type": "PASSWORD_CHANGED",
      "severity": 2,
      "message": "Your password was changed.",
      "created_at": "2026-09-03T12:00:00Z"
    }
  ],
  "pagination": { "limit": 20, "next_cursor": null, "has_more": false },
  "request_id": "req_uuid"
}
```

---

# 5. Teacher Bookings API

## 5.1 `GET /bookings?scope=teacher`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/bookings?scope=teacher` |
| Actor | Teacher |
| Authorization | Role `TEACHER` |
| Ownership | `booking.teacher_id = authenticated_teacher.id` |
| Request schema | Query: `scope=teacher`, `status`, `from`, `to`, `subject_id`, `limit`, `cursor` |
| Pagination | Required |
| Filtering | Status/date/subject filters allowlisted |
| Idempotency | Not required |
| State restrictions | Read-only |
| Event Ledger | None for ordinary read |
| Sensitive-data rules | Student context minimized; no parent payment provider payload |

Response:

```json
{
  "data": [
    {
      "booking_id": "booking_123",
      "status": "BOOKED",
      "payment_status": "CONFIRMED",
      "session_status": "SCHEDULED",
      "student": { "display_name": "Ahmed", "academic_level_id": "level_2as" },
      "subject_id": "sub_math",
      "scheduled_start": "2026-09-05T13:00:00Z",
      "scheduled_end": "2026-09-05T14:00:00Z"
    }
  ],
  "pagination": { "limit": 20, "next_cursor": null, "has_more": false },
  "request_id": "req_uuid"
}
```

Errors:

```text
AUTH_REQUIRED
FORBIDDEN
VALIDATION_ERROR
```

---

# 6. Availability Block / Unblock APIs

## 6.1 `POST /teachers/availability/slots/:id/block`

| Field | Contract |
|---|---|
| Method | `POST` |
| Path | `/api/v1/teachers/availability/slots/:id/block` |
| Actor | Teacher, OPS/Admin override |
| Authorization | Teacher owns slot or OPS/Admin with reason |
| Ownership | `availability_slots.teacher_id = authenticated_teacher.id` |
| Request schema | `{ "reason": "Personal appointment" }` |
| Response schema | Slot with `status=BLOCKED` |
| Idempotency | Recommended |
| State restrictions | Only `AVAILABLE` slots normally blockable; booked slots cannot be silently blocked |
| Event Ledger | `SLOT_BLOCKED`; admin override also `ADMIN_ACTION` |
| Sensitive-data rules | No parent/student data exposed for unrelated slots |

Errors:

```text
AVAILABILITY_SLOT_NOT_FOUND
FORBIDDEN
INVALID_STATE_TRANSITION
AVAILABILITY_SLOT_ALREADY_BOOKED
```

## 6.2 `POST /teachers/availability/slots/:id/unblock`

| Field | Contract |
|---|---|
| Method | `POST` |
| Path | `/api/v1/teachers/availability/slots/:id/unblock` |
| Actor | Teacher, OPS/Admin override |
| Authorization | Teacher owns slot or OPS/Admin with reason |
| Request schema | `{ "reason": "Available again" }` |
| Response schema | Slot with `status=AVAILABLE` if no conflict |
| Idempotency | Recommended |
| State restrictions | Only `BLOCKED` slots normally unblockable; overlap constraints still apply |
| Event Ledger | `SLOT_UPDATED`; admin override also `ADMIN_ACTION` |
| Sensitive-data rules | No unrelated booking details |

Errors:

```text
INVALID_STATE_TRANSITION
AVAILABILITY_OVERLAP
FORBIDDEN
```

---

# 7. Admin Refund APIs

## 7.1 `GET /admin/refunds`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/admin/refunds` |
| Actor | OPS/Admin; SUPPORT limited/redacted if policy allows |
| Authorization | OPS/Admin for full view |
| Ownership | Operational scope; role-filtered |
| Request schema | Query: `status`, `provider`, `dispute_id`, `payment_id`, `from`, `to`, `limit`, `cursor` |
| Pagination | Required |
| Filtering | Status/provider/date/dispute/payment allowlisted |
| Idempotency | Not required |
| State restrictions | Read-only |
| Event Ledger | Ordinary list read none; sensitive drilldown audited in detail endpoint if sensitive fields exposed |
| Sensitive-data rules | No raw provider payload in list |

Response:

```json
{
  "data": [
    {
      "refund_id": "refund_123",
      "payment_id": "pay_123",
      "booking_id": "booking_123",
      "dispute_id": "dispute_123",
      "provider": "CIB",
      "refund_type": "PARTIAL",
      "status": "PROVIDER_PENDING",
      "requested_amount": "400.00",
      "approved_amount": "400.00",
      "currency": "DZD",
      "reason_code": "SESSION_QUALITY",
      "created_at": "2026-09-05T15:00:00Z"
    }
  ],
  "pagination": { "limit": 20, "next_cursor": null, "has_more": false },
  "request_id": "req_uuid"
}
```

## 7.2 `GET /admin/refunds/:id`

| Field | Contract |
|---|---|
| Method | `GET` |
| Path | `/api/v1/admin/refunds/:id` |
| Actor | OPS/Admin |
| Authorization | OPS/Admin; ADMIN for sensitive/override details |
| Request schema | Optional query: `include_provider_summary=true`, not raw payload |
| Response schema | Full refund detail with redacted provider/reconciliation summary |
| Idempotency | Not required |
| State restrictions | Read-only |
| Event Ledger | Sensitive detail access must generate `ADMIN_ACTION` and/or `SECURITY_EVENT` according to fields exposed |
| Sensitive-data rules | Raw payload not returned; provider summary redacted |

Response:

```json
{
  "data": {
    "refund_id": "refund_123",
    "status": "PROVIDER_PENDING",
    "refund_type": "PARTIAL",
    "payment_id": "pay_123",
    "booking_id": "booking_123",
    "dispute_id": "dispute_123",
    "requested_amount": "400.00",
    "approved_amount": "400.00",
    "currency": "DZD",
    "teacher_adjustment_amount": "300.00",
    "platform_adjustment_amount": "100.00",
    "reason": "Partial refund approved after dispute resolution.",
    "reason_code": "SESSION_QUALITY",
    "provider_refund_id": null,
    "reconciliation": null,
    "timeline": {
      "created_at": "2026-09-05T15:00:00Z",
      "approved_at": "2026-09-05T15:10:00Z",
      "provider_submitted_at": "2026-09-05T15:12:00Z",
      "completed_at": null,
      "failed_at": null,
      "rejected_at": null,
      "cancelled_at": null
    },
    "provider_event_summary": []
  },
  "request_id": "req_uuid"
}
```

## 7.3 `POST /admin/refunds/:id/reconcile`

| Field | Contract |
|---|---|
| Method | `POST` |
| Path | `/api/v1/admin/refunds/:id/reconcile` |
| Actor | OPS/Admin; ADMIN required for `ADMIN_OVERRIDE` |
| Authorization | OPS/Admin with financial authority |
| Request schema | See below |
| Response schema | Refund detail after reconciliation |
| Idempotency | Required |
| State restrictions | Refund must require reconciliation; terminal states cannot be reopened |
| Event Ledger | `ADMIN_ACTION` plus `REFUND_SUCCEEDED` or `REFUND_FAILED`; payment refunded events only on success |
| Sensitive-data rules | Supporting evidence references only; no raw payload exposure |

Request:

```json
{
  "result": "SUCCEEDED",
  "reconciliation_source": "MANUAL_RECONCILIATION",
  "reconciliation_reference": "BANK-REF-12345",
  "reconciled_at": "2026-09-05T16:00:00Z",
  "reason": "Manual bank confirmation received.",
  "supporting_evidence": [
    { "type": "document_reference", "id": "evidence_123" }
  ]
}
```

Rules:

```text
reconciliation_source required
reconciliation_reference non-empty
reconciled_at required
MANUAL_RECONCILIATION / ADMIN_OVERRIDE require authenticated reconciled_by_user_id
```

Errors:

```text
REFUND_NOT_FOUND
REFUND_INVALID_STATE
REFUND_RECONCILIATION_PROOF_REQUIRED
FORBIDDEN
IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_KEY_CONFLICT
```

---

# 8. Refund Summaries in Existing Endpoints

## 8.1 `GET /payments/:id`

Add `refunds[]` summary when refund activity exists.

```json
{
  "data": {
    "payment_id": "pay_123",
    "status": "PARTIALLY_REFUNDED",
    "amount": "2000.00",
    "currency": "DZD",
    "refunds": [
      {
        "refund_id": "refund_123",
        "status": "SUCCEEDED",
        "refund_type": "PARTIAL",
        "requested_amount": "400.00",
        "approved_amount": "400.00",
        "currency": "DZD",
        "reason": "Partial refund after dispute resolution.",
        "created_at": "2026-09-05T15:00:00Z",
        "approved_at": "2026-09-05T15:10:00Z",
        "provider_submitted_at": "2026-09-05T15:12:00Z",
        "completed_at": "2026-09-05T15:20:00Z"
      }
    ]
  }
}
```

Parent sees only own payments. Teacher does not receive parent payment details.

## 8.2 `GET /bookings/:id`

Add `refund_summary` when applicable:

```json
{
  "refund_summary": {
    "has_refund_activity": true,
    "active_refund_status": "PROVIDER_PENDING",
    "total_approved_refund_amount": "400.00",
    "currency": "DZD"
  }
}
```

## 8.3 `GET /disputes/:id`

Add linked refund summaries:

```json
{
  "linked_refunds": [
    {
      "refund_id": "refund_123",
      "status": "APPROVED",
      "approved_amount": "400.00",
      "currency": "DZD"
    }
  ]
}
```

---

# 9. Payout Recovery / Adjustment Read Summaries

## 9.1 Teacher payout responses

`GET /teacher/payouts` and `GET /teacher/payouts/:id` must include read-only adjustment summaries if present.

```json
{
  "data": {
    "payout_id": "payout_123",
    "status": "PAID",
    "gross_teacher_payable": "1700.00",
    "refund_exposure_total": "300.00",
    "other_deductions": "0.00",
    "net_teacher_payable": "1400.00",
    "adjustments": [
      {
        "adjustment_id": "adj_123",
        "type": "POST_PAYOUT_RECOVERY",
        "amount": "300.00",
        "currency": "DZD",
        "status": "RECOVERY_PENDING",
        "refund_id": "refund_123",
        "dispute_id": "dispute_123"
      }
    ]
  }
}
```

## 9.2 Admin payout / finance responses

Admin payout responses may include recovery details:

```json
{
  "recovery_summary": {
    "teacher_recoverable_amount": "300.00",
    "platform_absorbed_amount": "100.00",
    "future_payout_offset_amount": "300.00",
    "original_payout_id": "payout_123",
    "refund_id": "refund_123"
  }
}
```

## 9.3 Explicit MVP restriction

```text
No POST /admin/recoveries in MVP.
```

Recovery/adjustment creation is a controlled side effect of approved refund/payout/ledger services, not a manual UI command.

---

# 10. Implementation Checklist for This Addendum

Before frontend/backend implementation:

```text
[ ] Add these endpoint contracts to API spec backlog
[ ] Add response schemas to shared API contract package
[ ] Add authorization tests for each endpoint
[ ] Add sensitive-data redaction tests
[ ] Add Event Ledger / SECURITY_EVENT tests where required
[ ] Add frontend mock API fixtures for these responses
[ ] Confirm no POST /admin/recoveries exists in MVP routes
```

---

# 11. Final Status

```text
EduTrust API Contract Addendum v1.1 Status: READY FOR REVIEW
```
