# EduTrust Algeria — Product/Ops Final Readiness v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Product/Ops policy readiness assessment  
**Status:** READY FOR DEV/STAGING CONFIG; PRODUCTION POLICY NOT FINAL

---

# 1. Summary

The ten Product/Ops policies remain production-unapproved. Recommended pilot defaults exist and can be implemented as configuration placeholders for DEV/STAGING and controlled pilot planning.

Do not treat recommendations as approved production policy.

---

# 2. Policy Readiness Matrix

| ID | Policy | Classification | Exact question | Recommended pilot default | Config key | Downstream modules | Test impact | Approval role |
|---|---|---|---|---|---|---|---|---|
| OPS-POL-001 | Booking hold duration | READY FOR PILOT | How long is a slot reserved? | 10 minutes | `BOOKING_HOLD_DURATION_SECONDS` | Booking, HoldExpiryJob, UI | hold expiry, late payment | Product + Ops + Eng |
| OPS-POL-002 | Payment checkout timeout | READY FOR PILOT | When does payment pending become stale? | 15 minutes | `PAYMENT_CHECKOUT_TIMEOUT_SECONDS` | Payment, timeout job, UI | payment timeout, retry | Payment + Ops + Eng |
| OPS-POL-003 | Late-payment resolution | READY FOR PILOT | Auto-refund or OPS review? | OPS review | `LATE_PAYMENT_RESOLUTION_MODE` | PaymentWebhook, Refund, Admin | late payment branch | Payment + Ops + Legal |
| OPS-POL-004 | No-show grace period | READY FOR PILOT | When can no-show be recorded? | 10 min online / 15 min in-person | `NO_SHOW_GRACE_SECONDS_ONLINE`, `NO_SHOW_GRACE_SECONDS_IN_PERSON` | Session, Dispute | no-show/dispute | Product + Ops |
| OPS-POL-005 | Parent dispute window | READY FOR PILOT | How long can parent dispute? | 24 hours after report/session completion | `PARENT_DISPUTE_WINDOW_SECONDS` | Dispute, Payout | payout block/release | Product + Ops + Payment |
| OPS-POL-006 | Payout delay | READY FOR PILOT | When payout becomes eligible? | 48 hours after report and no dispute | `PAYOUT_DELAY_SECONDS` | Payout | payout eligibility | Payment + Ops |
| OPS-POL-007 | Refund allocation | READY FOR PILOT | Who bears partial refund? | Manual OPS allocation | `REFUND_ALLOCATION_MODE` | Refund, Payout, Ledger | allocation/net payout | Payment + Ops + Legal |
| OPS-POL-008 | Review after partial refund | REQUIRES DECISION | Can partially refunded completed sessions be reviewed? | Allow with internal flag | `REVIEW_AFTER_PARTIAL_REFUND_POLICY` | Review, Trust metrics | review eligibility | Product + Ops + Legal |
| OPS-POL-009 | Notification channels | READY FOR PILOT | Which channels are enabled? | In-app + email; SMS only critical if provider ready | `NOTIFICATION_CHANNELS_ENABLED` | Notification | notification delivery | Product + Ops + Security |
| OPS-POL-010 | Arabic/French terminology | REQUIRES DECISION | Final bilingual wording? | Arabic-first + French secondary draft | translation/glossary config | All UI/notifications | RTL/copy tests | Product + Ops + Legal |

---

# 3. Production Blockers

Production blockers:

```text
OPS-POL-007 refund allocation must be legally/accounting approved.
OPS-POL-008 review after partial refund must be product/legal approved.
OPS-POL-010 final terminology must be approved.
Payment/legal policies must be finalized for real-money workflows.
```

---

# 4. Dev/Staging Handling

DEV/STAGING may use recommended defaults as configuration values if clearly marked:

```text
NON-PRODUCTION DEFAULT — NOT PRODUCTION POLICY
```

Tests must assert configurability, not hardcoded values.

---

# 5. Final Status

```text
Product/Ops Final Readiness: READY FOR DEV/STAGING CONFIG; PRODUCTION POLICY NOT FINAL
```
