# EduTrust Algeria — Product/Ops Policy Decisions v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Product/Ops policy matrix  
**Status:** READY FOR REVIEW  
**Important:** Recommended pilot defaults are **not** approved production policy.

---

# 1. Purpose

This document tracks the ten policy decisions that remained unresolved throughout UX, visual, and prototype gates.

The goal is to distinguish:

```text
RECOMMENDED PILOT DEFAULT
```

from:

```text
APPROVED PRODUCTION POLICY
```

No recommendation in this document is automatically approved for production.

---

# 2. Approval Roles

| Role | Approval scope |
|---|---|
| Product Lead | User-facing policy and UX copy |
| Ops Lead | Operational workflows, support handling, dispute windows |
| Payment/Finance Lead | refunds, payouts, payment timeouts, settlement rules |
| Legal/Compliance Advisor | payment/legal/privacy/child data constraints |
| Security/Privacy Lead | notification channels, sensitive data, retention |
| Engineering Lead | configuration implementation and testability |

If actual people are unknown, use role-based approval only.

---

# 3. Policy Matrix

## OPS-POL-001 — Booking hold duration

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Determines how long a slot is reserved before payment; affects double-booking, UX urgency, and payment latency |
| Recommended pilot default | 10 minutes |
| Approved production policy | NOT APPROVED |
| Configuration key | `BOOKING_HOLD_DURATION_SECONDS` |
| Allowed range/enum | 300–1800 seconds |
| Approver | Product Lead + Ops Lead + Engineering Lead |
| Modules consuming it | BookingService, HoldExpiryJob, Parent UI, Notifications |
| What happens if unset | Booking hold endpoint must fail closed or use staging-only config; production launch blocked |
| Test cases affected | hold expiry, payment after expiry, duplicate hold, countdown UI |

## OPS-POL-002 — Payment checkout timeout

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Defines when payment pending becomes stale and whether slot is released |
| Recommended pilot default | 15 minutes |
| Approved production policy | NOT APPROVED |
| Configuration key | `PAYMENT_CHECKOUT_TIMEOUT_SECONDS` |
| Allowed range/enum | 300–3600 seconds |
| Approver | Payment/Finance Lead + Ops Lead + Engineering Lead |
| Modules consuming it | PaymentService, PaymentTimeoutJob, BookingService, Parent UI |
| What happens if unset | Payment timeout job disabled in production; launch blocked |
| Test cases affected | payment pending timeout, late provider success, retry eligibility |

## OPS-POL-003 — Late-payment auto-refund vs OPS review

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Late payment after expiry is financially real but unfulfillable; must decide auto-refund or review queue |
| Recommended pilot default | Create refund request + OPS review before provider submission |
| Approved production policy | NOT APPROVED |
| Configuration key | `LATE_PAYMENT_RESOLUTION_MODE` |
| Allowed range/enum | `OPS_REVIEW`, `AUTO_APPROVE_REFUND`, `MANUAL_RECONCILIATION_ONLY` |
| Approver | Payment/Finance Lead + Ops Lead + Legal/Compliance Advisor |
| Modules consuming it | PaymentWebhookService, RefundService, AdminRefundQueue, Notifications |
| What happens if unset | Late payment branch must create reconciliation alert and block auto-refund; launch blocked for payment flow |
| Test cases affected | late payment after expiry, refund timeline, admin reconciliation |

## OPS-POL-004 — No-show grace period

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Determines when teacher/student can be marked no-show and affects refund/payout/disputes |
| Recommended pilot default | 10 minutes online, 15 minutes in-person |
| Approved production policy | NOT APPROVED |
| Configuration key | `NO_SHOW_GRACE_SECONDS_ONLINE`, `NO_SHOW_GRACE_SECONDS_IN_PERSON` |
| Allowed range/enum | 0–3600 seconds per mode |
| Approver | Product Lead + Ops Lead |
| Modules consuming it | SessionService, DisputeService, Notifications, Teacher UI |
| What happens if unset | No-show action disabled; OPS manual handling required |
| Test cases affected | student no-show, teacher no-show claim, dispute opening, payout block |

## OPS-POL-005 — Parent dispute window

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Determines when payout can be released and when parent can dispute a completed session |
| Recommended pilot default | 24 hours after report availability or session completion, whichever is later |
| Approved production policy | NOT APPROVED |
| Configuration key | `PARENT_DISPUTE_WINDOW_SECONDS` |
| Allowed range/enum | 0–604800 seconds |
| Approver | Product Lead + Ops Lead + Payment/Finance Lead |
| Modules consuming it | DisputeService, PayoutService, Notifications, Parent UI |
| What happens if unset | Payout eligibility must remain blocked or require manual OPS release |
| Test cases affected | payout eligibility, dispute after completion, parent dispute flow |

## OPS-POL-006 — Payout delay

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Protects against immediate payout before report/dispute/refund exposure is known |
| Recommended pilot default | 48 hours after report completion and no open dispute |
| Approved production policy | NOT APPROVED |
| Configuration key | `PAYOUT_DELAY_SECONDS` |
| Allowed range/enum | 0–1209600 seconds |
| Approver | Payment/Finance Lead + Ops Lead |
| Modules consuming it | PayoutService, PayoutEligibilityJob, Teacher UI |
| What happens if unset | Payout processing disabled except admin test environment |
| Test cases affected | payout eligible, payout blocked, refund before payout |

## OPS-POL-007 — Refund allocation teacher/platform

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Determines economic burden of partial refunds and affects net teacher payable |
| Recommended pilot default | OPS/Admin manual allocation with reason codes; no automatic formula in pilot |
| Approved production policy | NOT APPROVED |
| Configuration key | `REFUND_ALLOCATION_MODE` |
| Allowed range/enum | `MANUAL_OPS`, `TEACHER_FULL`, `PLATFORM_FULL`, `RULE_BASED_V1` |
| Approver | Payment/Finance Lead + Ops Lead + Legal/Compliance Advisor |
| Modules consuming it | RefundService, PayoutService, LedgerService, Admin UI |
| What happens if unset | Refund approval requires manual allocation fields; auto-approval disabled |
| Test cases affected | partial refund allocation, payout net, post-payout recovery |

## OPS-POL-008 — Review eligibility after partial refund

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Determines whether partially refunded completed sessions can still produce verified reviews |
| Recommended pilot default | Allow review if session was completed, but block review for full refund/no-show; show no special public label initially |
| Approved production policy | NOT APPROVED |
| Configuration key | `REVIEW_AFTER_PARTIAL_REFUND_POLICY` |
| Allowed range/enum | `ALLOW`, `BLOCK`, `ALLOW_WITH_INTERNAL_FLAG` |
| Approver | Product Lead + Ops Lead + Legal/Compliance Advisor |
| Modules consuming it | ReviewService, Parent UI, TrustMetricsWorker |
| What happens if unset | Backend should default to conservative block in production until approved |
| Test cases affected | review eligibility, partial refund, trust metrics |

## OPS-POL-009 — Notification channels

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Affects reliability of parent visibility and operational cost/compliance |
| Recommended pilot default | In-app + email; SMS only for critical safety/payment events if provider ready |
| Approved production policy | NOT APPROVED |
| Configuration key | `NOTIFICATION_CHANNELS_ENABLED`, `CRITICAL_NOTIFICATION_CHANNELS` |
| Allowed range/enum | Subset of `IN_APP`, `EMAIL`, `SMS`, `PUSH` |
| Approver | Product Lead + Ops Lead + Security/Privacy Lead |
| Modules consuming it | NotificationService, NotificationWorker, Parent/Teacher/Admin UI |
| What happens if unset | In-app only in non-production; production launch requires approved channels |
| Test cases affected | notification creation, delivery failure, read status |

## OPS-POL-010 — Arabic/French terminology

| Field | Decision |
|---|---|
| Current status | OPEN POLICY |
| Why it matters | Affects trust, clarity, and legal/financial wording in Algeria |
| Recommended pilot default | Use Arabic-first with French secondary labels in pilot; final terminology reviewed by Product/Ops/legal |
| Approved production policy | NOT APPROVED |
| Configuration key | `DEFAULT_LOCALE`, translation files, terminology glossary version |
| Allowed range/enum | `ar-DZ`, `fr-DZ`, bilingual display policy |
| Approver | Product Lead + Ops Lead + Legal/Compliance Advisor |
| Modules consuming it | All frontend apps, notifications, invoices/receipts, support scripts |
| What happens if unset | Use placeholders in prototypes; production copy blocked |
| Test cases affected | RTL, mixed-language layout, notification copy, invoice/receipt copy |

---

# 4. Production Approval Rule

No recommended pilot default is production-approved until recorded as:

```text
APPROVED PRODUCTION POLICY
```

with approver roles and date/version.

---

# 5. Final Status

```text
EduTrust Product/Ops Policy Decisions v1.0 Status: READY FOR REVIEW
```
