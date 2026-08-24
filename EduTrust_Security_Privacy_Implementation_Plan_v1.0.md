# EduTrust Algeria — Security & Privacy Implementation Plan v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Security/privacy implementation controls  
**Status:** READY FOR REVIEW

---

# 1. Principles

- Privacy by design
- Minor data minimization
- Parent control over student data
- RBAC + object ownership
- Auditability
- Secure payment/document handling
- Sensitive admin access logging
- No raw provider payload exposure to Parent/Teacher

---

# 2. Access Matrix

| Resource/action | Parent | Teacher | Support | OPS | Admin |
|---|---|---|---|---|---|
| Own parent profile | Read/update own | No | Limited support view | Operational | Admin scoped |
| Student profile | Own only | No, except permitted context | Limited/redacted | Limited audited | Audited |
| Student Passport | Own only | Permission-scoped only | No by default | Limited audited | Audited |
| Student permissions | Grant/revoke own | View effect only | No | Assist audited | Audited |
| Teacher profile | Public/listed view | Own edit | View | Operational | Admin override |
| Verification documents | No | Own metadata only | No | Audited limited | Audited full |
| Booking | Own | Assigned teacher only | Limited | Operational | Full scoped |
| Payment | Own redacted | No, only earnings impact | Limited redacted | Operational | Audited full |
| Raw provider payload | No | No | No | Restricted audited | Audited admin only |
| Refund | Own payment/refund timeline | Earnings impact only | Limited | Operational | Full scoped |
| Payout | No | Own only | No | Process/monitor | Process/monitor |
| Event ledger | No | No | No | Scoped | Full scoped |
| Security events | Own user-visible only | Own user-visible only | No | Limited | Full scoped |
| Sensitive access override | No | No | No | Limited audited | Audited |

---

# 3. RBAC Implementation

Required layers:

1. API authentication middleware.
2. Role check per endpoint.
3. Object ownership check per resource.
4. State-transition authority check per command.
5. Sensitive-data access policy check.
6. Event/security audit for sensitive admin access.

Forbidden:

```text
role-only authorization without object ownership
frontend-only permission enforcement
admin blind mutation without audit
```

---

# 4. Parent / Student Isolation

Controls:

- All student queries filtered by `parent_id`.
- Composite FK already protects booking ownership.
- API must return generic `FORBIDDEN` without revealing another student exists.
- Student display name/nickname preferred over full legal identity.
- Do not collect national ID, full address, school details, or sensitive data unless later approved.

Tests:

```text
Parent A cannot GET/PATCH/book for Parent B student.
Parent A cannot view Parent B passport/report/payment.
```

---

# 5. Teacher Student Passport Boundaries

Teacher may see only:

```text
assigned session context
or explicit student_permission scope
```

Teacher must not see unrestricted Student Passport.

Permission UX/API must expose:

```text
scope
expiry
linked booking/session
revoked_at
```

Teacher access to sensitive student context should be auditable where policy requires.

---

# 6. Verification Documents

Implementation controls:

- Store files in encrypted object storage.
- Database stores metadata and storage key only.
- Signed URLs short-lived.
- Document access only through audited admin/OPS flow.
- Teacher sees own document metadata/status, not unrestricted storage URL after upload.
- Public never sees documents.

Required audit:

```text
SECURITY_EVENT DOCUMENT_ACCESS
ADMIN_ACTION where admin/OPS opened sensitive document
```

---

# 7. Provider Payload Protection

Controls:

- Store normalized provider payload subset.
- Redact full payload; if retained, store encrypted outside normal API response.
- Never expose raw provider payload to Parent/Teacher.
- Admin access requires sensitive access modal and reason.
- Logs must exclude raw payload and sensitive payment/auth data.

---

# 8. Payment Data Minimization

Parent sees:

```text
amount
currency
status
receipt/reference
refund timeline
```

Teacher sees:

```text
earnings impact
refund adjustment effect
payout status
```

Teacher does not see:

```text
parent payment provider payload
parent payment method sensitive details
```

---

# 9. Audit Logging

Sensitive actions must generate:

```text
ADMIN_ACTION
SECURITY_EVENT
```

as appropriate.

Must audit:

- verification document access,
- provider payload access,
- refund reconciliation proof access/change,
- admin user suspension,
- sensitive student context access by admin/OPS,
- ledger/recovery sensitive detail access,
- admin overrides.

---

# 10. Authentication / Session Security

Controls:

- Passwords hashed with strong adaptive algorithm.
- Refresh tokens stored hashed only.
- Refresh token rotation on refresh.
- Session revocation supported.
- Failed login rate limiting.
- Security events for login anomalies and token replay.
- HTTPS required in production.
- Secrets in secrets manager, not repo.

---

# 11. Rate Limiting

Required rate limits:

```text
login/register/refresh
password reset if implemented
teacher search/match
booking hold
payment initiation
refund requests
admin sensitive access attempts
payment webhooks by provider/source
```

Rate-limit events may generate `SECURITY_EVENT` for suspicious patterns.

---

# 12. Retention / Deletion

Policy remains to be finalized, but implementation must support:

- account deletion/soft delete where required,
- student profile archive/delete workflow,
- verification document retention limits,
- provider payload retention limit,
- audit/ledger retention according to legal/financial requirements,
- idempotency key expiry/cleanup.

Do not delete ledger/event history casually.

---

# 13. Backup Security

Controls:

- Encrypted database backups.
- Restricted backup access.
- Restore tests.
- Backup retention policy.
- No raw secrets in backups outside encrypted stores.

---

# 14. Incident Response

Minimum runbook:

1. Identify incident type.
2. Freeze affected accounts/flows if needed.
3. Preserve event/security logs.
4. Notify internal owners.
5. Assess child/payment data impact.
6. Execute containment.
7. Document resolution.
8. Post-incident review.

Incident classes:

```text
payment mismatch
provider payload leak
student data access violation
admin account compromise
teacher verification document leak
ledger inconsistency attempt
```

---

# 15. Security Testing Checklist

- Parent ownership bypass tests.
- Teacher student context boundary tests.
- Admin sensitive access audit tests.
- Raw payload redaction tests.
- Refresh token storage tests.
- Rate limit tests.
- Document access expiry tests.
- Payment webhook signature tests.
- Refund reconciliation permission tests.
- Payout processing permission tests.

---

# 16. Final Status

```text
EduTrust Security & Privacy Implementation Plan v1.0 Status: READY FOR REVIEW
```
