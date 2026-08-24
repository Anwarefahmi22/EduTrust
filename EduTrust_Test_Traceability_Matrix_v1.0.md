# EduTrust Algeria — Test Traceability Matrix v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Architecture-to-test traceability matrix  
**Status:** READY FOR REVIEW

---

# 1. Purpose

This matrix maps critical architecture/state/database rules to required tests.

Format:

```text
Architecture/State rule → Database constraint → Service → API → Unit test → Integration test → E2E test → Gate
```

---

# 2. Traceability Matrix

| Rule | DB constraint/guard | Service | API | Unit test | Integration test | E2E test | Gate |
|---|---|---|---|---|---|---|---|
| Parent cannot book another parent’s student | Composite FK `(student_id,parent_id)` | BookingService | `POST /bookings/hold` | ownership check rejects | FK/service rejects | Parent B student inaccessible | Implementation Gate |
| No double booking | active booking unique index + slot lock | BookingService | `POST /bookings/hold` | unavailable slot check | concurrent hold test | two parents same slot | Implementation Gate |
| No overlapping active teacher slots | exclusion constraint | AvailabilityService | availability slot/rule endpoints | overlap validation | DB overlap insert fails | teacher overlap UI error | Implementation Gate |
| Payment amount mismatch blocked | payment amount trigger | PaymentService/Webhook | `POST /payments/initiate`, webhook | amount compare | mismatch webhook fails | provider mismatch admin alert | Payment Gate |
| Webhook idempotency | `payment_provider_events(provider,event_id)` | PaymentWebhookService | webhook endpoint | duplicate event logic | duplicate webhook no double mutation | payment pending → success once | Payment Gate |
| Late payment after expiry | service branch + refund workflow | PaymentWebhookService/RefundService | webhook + refund reads | branch selection | expired booking + late success no session | late payment screen | Payment Gate |
| Session synchronous creation | `sessions.booking_id UNIQUE`; service transaction | PaymentWebhookService | webhook | create session when fulfillable | confirmed payment creates booked+session | payment success shows session | Payment Gate |
| Refund lifecycle valid | refund triggers/checks | RefundService | admin refund/reconcile | transition validation | invalid transition fails | refund timeline states | Refund Gate |
| Over-refund blocked | refund integrity trigger with payment lock | RefundService | `POST /payments/:id/refund` | allocation sum | concurrent refunds <= payment | admin error on over-refund | Refund Gate |
| Partial refund allocation | allocation check | RefundService/PayoutService | admin refund | teacher+platform=sum | allocation mismatch fails | admin partial refund form | Refund Gate |
| Payout eligibility | payout item trigger + service checks | PayoutService | `POST /admin/payouts/process` | eligibility rules | open dispute/report missing blocks | payout queue blocked reason | Payout Gate |
| Dispute blocks payout | payout trigger/service checks | DisputeService/PayoutService | disputes + payout | dispute open flag | payout insert blocked | dispute → payout blocked | Payout Gate |
| Post-payout recovery separate | ledger immutable + service adjustment | Refund/Payout/LedgerService | payout/refund reads | no old payout mutation | recovery entry created | recovery shown separate | Payout Gate |
| Review eligibility | review trigger + unique session | ReviewService | `POST /sessions/:id/review` | eligibility check | before completion rejected | review button hidden/enabled | Review Gate |
| Duplicate review blocked | `reviews.session_id UNIQUE` | ReviewService | review endpoint | duplicate check | second insert fails | duplicate tap no second review | Review Gate |
| Teacher cannot self-review | review trigger | ReviewService | review endpoint | parent != teacher user | self-review rejected | no teacher review UI | Review Gate |
| Student ownership privacy | FK + service filters | StudentService | student endpoints | ownership service test | cross-parent query denied | permission denied screen | Security Gate |
| Teacher Passport restriction | `student_permissions` + service | StudentContextService | session/student context | permission check | expired/revoked denied | teacher denied/limited context | Security Gate |
| Sensitive admin access audited | event/security insert | AdminActionService | admin sensitive endpoints | audit required | access creates event | sensitive modal → audit trail | Security Gate |
| Provider payload redaction | response serializer | Payment/Admin services | admin payment/refund reads | serializer redacts | raw payload absent | admin sees secure modal | Security Gate |
| Idempotency mutation prevention | v1.3 idempotency trigger | IdempotencyService | idempotent POSTs | immutable fields | invalid status transition fails | duplicate tap safe state | Implementation Gate |
| Ledger immutability | ledger update/delete trigger | LedgerService | internal/admin reads | no update path | update/delete fails | no edit ledger UI | Finance Gate |
| Event ledger immutability | event update/delete trigger | EventLedgerService | admin events | no update path | update/delete fails | event detail read-only | Audit Gate |
| Notification source of truth | notifications table | NotificationService | `/notifications` | status update | mark read safe | notification read UI | UX/E2E Gate |
| Auth sessions secure | refresh hash/session table | AuthService | `/auth/sessions` | no raw token | token hash only | session revoke UI | Security Gate |

---

# 3. Required Test Suites

## Unit suites

```text
test_booking_service.py
test_payment_webhook_service.py
test_refund_service.py
test_payout_service.py
test_review_service.py
test_student_permissions.py
test_idempotency_service.py
test_authorization.py
test_serializers_redaction.py
```

## Integration suites

```text
test_db_constraints.py
test_concurrency_booking.py
test_webhook_idempotency.py
test_refund_concurrency.py
test_payout_eligibility.py
test_audit_logging.py
```

## E2E suites

```text
e2e_parent_happy_path.spec.ts
e2e_late_payment.spec.ts
e2e_refund_lifecycle.spec.ts
e2e_teacher_report_payout.spec.ts
e2e_admin_refund_reconciliation.spec.ts
e2e_student_permissions.spec.ts
e2e_sensitive_admin_access.spec.ts
```

---

# 4. Final Status

```text
EduTrust Test Traceability Matrix v1.0 Status: READY FOR REVIEW
```
