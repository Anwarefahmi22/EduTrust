# EduTrust Algeria — Clickable Prototype Specification v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Clickable prototype specification for Figma or equivalent tool  
**Status:** READY FOR REVIEW  
**Implementation status:** No frontend/backend implementation started  
**Architecture baseline:** LOCKED

---

# 1. Purpose

This document defines the clickable prototype structure for EduTrust MVP.

It is intended for designers preparing a Figma or equivalent clickable prototype that can be tested with parents, teachers, and admin/operations users before any production implementation.

This document does **not**:

- implement frontend
- implement backend
- write production UI code
- modify database schema
- modify API architecture
- modify state machines
- modify UX business logic
- add MVP features
- reopen the architecture baseline
- invent unresolved policy values

---

# 2. Approved Inputs

The prototype must be based strictly on:

1. PRD v1.0
2. Database / DDL baseline
3. API Architecture v1.0
4. State Machines v1.1 baseline
5. UX Flows v1.1
6. Approved Low-Fidelity Baseline
7. High-Fidelity UI Design v1.0
8. High-Fidelity UI Audit PASS
9. Visual Mockups v1.0
10. Visual Mockups Audit PASS

---

# 3. Prototype Structure

## 3.1 Figma page structure

Recommended pages:

```text
00 Prototype Cover
01 Parent Prototype — Happy Path
02 Parent Prototype — Payment / Refund / Dispute Edges
03 Teacher Prototype
04 Admin OPS Prototype
05 Privacy & Permissions Prototype
06 RTL Variants
07 Error Loading Empty States
08 Prototype Test Scenarios
09 Prototype Notes / Handoff
```

## 3.2 Role-based prototype starting points

| Role | Starting frame | Frame ID |
|---|---|---|
| Parent | Login | `CP-P-01` |
| Teacher | Teacher Onboarding | `CP-T-01` |
| Admin/OPS | Admin Dashboard | `CP-A-01` |

## 3.3 Prototype interaction types

Use the following interaction types:

| Type | Meaning |
|---|---|
| Navigate | Full frame navigation |
| Overlay | Modal or overlay opens above current frame |
| Bottom sheet | Mobile bottom sheet |
| Drawer | Admin side drawer/detail drawer |
| Swap variant | Same frame changes state variant |
| Back | Return to previous frame |
| Disabled | Element visible but not clickable; reason shown |
| Simulated mutation | Prototype moves to next state to simulate approved backend transition |
| Read-only | Click opens detail but implies no mutation |

## 3.4 Prototype branches

Required branches:

```text
Parent happy path
Parent payment pending branch
Parent payment failure branch
Parent late payment after expiry branch
Parent dispute/refund branch
Parent permission grant/revoke branch
Teacher onboarding/session/report/payout branch
Teacher post-payout recovery branch
Admin verification/sensitive access branch
Admin refund/reconciliation branch
Admin payout/failure branch
Admin event/audit branch
RTL representative branch
```

---

# 4. Global Prototype Rules

## 4.1 No unauthorized state transitions

A prototype click may simulate a backend transition only if that transition exists in the approved state machines.

Forbidden examples:

```text
Parent confirms booking manually
Parent confirms payment
Parent completes session
Teacher confirms payment
Teacher processes payout
Admin edits old paid payout
Admin directly mutates factual booking/session state
```

## 4.2 Loading behavior

For mutation-like interactions, include a loading frame or state variant when useful:

```text
Reserving slot
Starting payment
Waiting for payment confirmation
Submitting report
Submitting review
Opening dispute
Processing refund
Processing payout
```

## 4.3 Error behavior

Prototype must include explicit error branches for critical workflows:

```text
slot unavailable
payment failed
payment pending delay
late payment after expiry
refund failed
refund rejected
refund cancelled
payout blocked
payout failed
permission denied
operational incident
```

## 4.4 Disabled behavior

Disabled actions must show a reason.

Examples:

```text
Review disabled: Available after a verified completed session.
Pay disabled: Reservation expired.
Process payout disabled: Open dispute or refund exposure exists.
View Student Passport disabled: Parent permission required.
```

## 4.5 Open policy values

Do not invent final values. Use:

```text
[POLICY DECISION REQUIRED]
```

for unresolved policies.

---

# 5. Frame Inventory

## 5.1 Parent frames

| Frame ID | Frame name | Purpose |
|---|---|---|
| `CP-P-01` | Parent Login | Login/register entry |
| `CP-P-02` | Parent Dashboard | Parent home |
| `CP-P-03` | Create Student | Student profile creation |
| `CP-P-04` | Student Profile | Student summary |
| `CP-P-05` | Student Passport v0 | Structured progress view |
| `CP-P-06` | Data Sharing Permissions | Grant/view/revoke permissions |
| `CP-P-07` | Teacher Search | Search filters |
| `CP-P-08` | Matching Results | Rule-based recommendations |
| `CP-P-09` | Teacher Trust Profile | Teacher profile/trust evidence |
| `CP-P-10` | Teacher Availability | Slot selection |
| `CP-P-11` | Booking Hold | Temporary reservation |
| `CP-P-12` | Checkout | Payment initiation |
| `CP-P-13` | Payment Pending | Waiting for provider confirmation |
| `CP-P-14` | Payment Success | Payment/booking/session confirmed |
| `CP-P-15` | Payment Failure | Payment failure/retry eligibility |
| `CP-P-16` | Late Payment After Expiry | Payment received but booking expired |
| `CP-P-17` | Booking Detail | Booking/payment/session state detail |
| `CP-P-18` | Session Detail | Parent session detail |
| `CP-P-19` | Session Report | Structured report |
| `CP-P-20` | Verified Review | Review form |
| `CP-P-21` | Dispute Create | Report a problem |
| `CP-P-22` | Dispute Status | Dispute timeline/status |
| `CP-P-23` | Refund Timeline | Refund lifecycle |
| `CP-P-24` | Refund Completed | Refund succeeded |
| `CP-P-25` | Refund Failed | Refund failed |
| `CP-P-26` | Refund Rejected | Refund rejected |
| `CP-P-27` | Refund Cancelled | Refund cancelled |
| `CP-P-28` | Payment History | Payment/invoice list |
| `CP-P-29` | Notifications | Parent notifications |
| `CP-P-30` | Account Security | Parent account/security |
| `CP-P-31` | Operational Incident | Payment confirmed but session unavailable status refresh/support |

## 5.2 Teacher frames

| Frame ID | Frame name | Purpose |
|---|---|---|
| `CP-T-01` | Teacher Onboarding | Setup start |
| `CP-T-02` | Subjects & Pricing | Offerings setup |
| `CP-T-03` | Verification | Verification submission/status |
| `CP-T-04` | Availability Management | Calendar/slots |
| `CP-T-05` | Teacher Dashboard | Teacher home |
| `CP-T-06` | Bookings | Teacher bookings |
| `CP-T-07` | Session Detail | Assigned session |
| `CP-T-08` | Attendance | Attendance/no-show |
| `CP-T-09` | Session Report | Teacher report form |
| `CP-T-10` | Earnings | Earnings summary |
| `CP-T-11` | Payout Detail | Payout breakdown |
| `CP-T-12` | Refund Adjustment | Refund exposure impact |
| `CP-T-13` | Post-Payout Recovery | Separate recovery record |
| `CP-T-14` | Student Context | Permission-scoped context |
| `CP-T-15` | Reviews | Teacher reviews |
| `CP-T-16` | Notifications | Teacher notifications |
| `CP-T-17` | Account Security | Teacher account/security |

## 5.3 Admin/OPS frames

| Frame ID | Frame name | Purpose |
|---|---|---|
| `CP-A-01` | Admin Dashboard | Operational overview |
| `CP-A-02` | Verification Queue | Teacher verification queue |
| `CP-A-03` | Verification Detail | Teacher verification review |
| `CP-A-04` | Sensitive Access Modal | Logged sensitive access |
| `CP-A-05` | Secure Document View | Protected document/payload view |
| `CP-A-06` | Audit Trail | Entity audit timeline |
| `CP-A-07` | Booking Monitoring | Booking table |
| `CP-A-08` | Payment Monitoring | Payment table |
| `CP-A-09` | Refund Queue | Refund lifecycle queue |
| `CP-A-10` | Refund Detail | Refund detail/timeline |
| `CP-A-11` | Refund Reconciliation | Reconciliation form |
| `CP-A-12` | Dispute Queue | Dispute queue |
| `CP-A-13` | Dispute Detail | Dispute resolution detail |
| `CP-A-14` | Payout Eligible Queue | Eligible/blocked payouts |
| `CP-A-15` | Payout Processing | Process payout |
| `CP-A-16` | Payout Failure | Payout failure handling |
| `CP-A-17` | Recovery / Adjustment | Read-only recovery/adjustment |
| `CP-A-18` | Event Ledger | Event ledger table |
| `CP-A-19` | Event Detail Drawer | Event detail drawer |
| `CP-A-20` | Security Events | Security event list |
| `CP-A-21` | User Suspension | User suspension action |

## 5.4 RTL representative frames

| Frame ID | Frame name |
|---|---|
| `CP-RTL-01` | Parent Dashboard RTL |
| `CP-RTL-02` | Teacher Search RTL |
| `CP-RTL-03` | Teacher Trust Profile RTL |
| `CP-RTL-04` | Booking / Payment RTL |
| `CP-RTL-05` | Refund Timeline RTL |
| `CP-RTL-06` | Teacher Payout RTL |
| `CP-RTL-07` | Admin Refund Queue RTL |

---

# 6. Parent Prototype Path

## 6.1 Parent happy path overview

```text
CP-P-01 Login
→ CP-P-02 Dashboard
→ CP-P-03 Create Student
→ CP-P-07 Teacher Search
→ CP-P-08 Matching Results
→ CP-P-09 Teacher Trust Profile
→ CP-P-10 Teacher Availability
→ CP-P-11 Booking Hold
→ CP-P-12 Checkout
→ CP-P-13 Payment Pending
→ CP-P-14 Payment Success
→ CP-P-18 Session Detail
→ CP-P-19 Session Report
→ CP-P-20 Verified Review
```

## 6.2 Parent happy path interactions

| Source frame | Element ID | Visible label | Interaction type | Destination frame | Preconditions | Backend state represented | Mutation implied | Required authorization | Loading behavior | Error behavior | Disabled behavior | Back behavior |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-01` | `P01-login-primary` | Login | Navigate | `CP-P-02` | Valid credentials in prototype path | Authenticated parent | Simulated login | Public → Parent | Login spinner | Invalid credentials branch optional | Disabled if fields empty | N/A |
| `CP-P-02` | `P02-add-student` | Add student | Navigate | `CP-P-03` | Parent authenticated | Parent dashboard | No mutation until submit | Parent | None | N/A | N/A | Back to dashboard |
| `CP-P-03` | `P03-save-student` | Save student | Navigate | `CP-P-04` | Required fields + consent | Student profile created | Simulated `STUDENT_PROFILE_CREATED` | Parent owns account | Saving spinner | Validation error variant | Disabled until valid | Back to dashboard |
| `CP-P-04` | `P04-find-teacher` | Find teacher | Navigate | `CP-P-07` | Student active | Student profile | No | Parent owns student | None | N/A | Disabled if archived | Back to profile |
| `CP-P-07` | `P07-search` | Search | Navigate | `CP-P-08` | Subject/level selected | Search query | No | Parent | Search skeleton | No results variant | Disabled until required fields | Back to student/profile |
| `CP-P-07` | `P07-best-match` | Find best match | Navigate | `CP-P-08` | Student owned; filters valid | Rule-based matching | No | Parent | Matching skeleton | No results variant | Disabled until valid | Back to search |
| `CP-P-08` | `P08-view-profile` | View profile | Navigate | `CP-P-09` | Teacher listed | Teacher profile read | No | Parent/public reduced | Profile skeleton | Teacher unavailable | Disabled if unlisted | Back to results |
| `CP-P-08` | `P08-select-slot` | Select slot | Navigate | `CP-P-10` | Slot available in result | Availability read | No | Parent | Slot loading | Slot gone variant | Disabled if no slot | Back to results |
| `CP-P-09` | `P09-choose-slot` | Choose slot | Navigate | `CP-P-10` | Teacher has available slots | Availability read | No | Parent | Slot loading | No slots | Disabled if unavailable | Back to profile |
| `CP-P-10` | `P10-reserve-slot` | Reserve this slot | Navigate | `CP-P-11` | Slot `AVAILABLE` | Slot → held booking | Simulated booking hold | Parent owns student | Reserving spinner | Slot unavailable branch | Disabled if not available | Back to availability |
| `CP-P-11` | `P11-pay` | Proceed to payment | Navigate | `CP-P-12` | Booking `HELD`, unexpired | Booking held | No mutation until pay | Parent owns booking | None | Hold expired branch | Disabled if expired | Back to hold |
| `CP-P-12` | `P12-start-payment` | Pay | Navigate | `CP-P-13` | Booking `HELD`, provider available | Booking `PAYMENT_PENDING`; payment initiated | Simulated `PAYMENT_INITIATED` | Parent owns booking | Starting payment spinner | Provider unavailable / setup failed | Disabled if expired | Back to checkout |
| `CP-P-13` | `P13-refresh-success` | Simulate confirmed payment | Navigate | `CP-P-14` | Provider confirms fulfillable payment | Payment `CONFIRMED`, booking `BOOKED`, session `SCHEDULED` | Backend-driven simulation | Provider/system, parent observes | Checking status | Pending remains / failure branch | N/A | Back to dashboard |
| `CP-P-14` | `P14-view-session` | View session | Navigate | `CP-P-18` | Session `SCHEDULED` exists | Session detail | No | Parent owns session | Loading session | Operational incident branch | Disabled if session missing | Back to booking |
| `CP-P-18` | `P18-view-report` | View report | Navigate | `CP-P-19` | Report exists | Session report | No | Parent owns child/session | Report skeleton | Report not ready | Disabled if no report | Back to session |
| `CP-P-19` | `P19-review` | Review teacher | Navigate | `CP-P-20` | Review eligible | Verified review flow | No mutation until submit | Parent owner | None | Not eligible branch | Disabled if ineligible | Back to report |
| `CP-P-20` | `P20-submit-review` | Submit review | Navigate | `CP-P-09` | Eligible; no duplicate review | Review created | Simulated `REVIEW_CREATED` | Parent owner | Submitting spinner | Duplicate/not eligible | Disabled until rating valid | Back to report |

---

# 7. Parent Edge Branches

## 7.1 Payment pending → Late payment after expiry

```text
CP-P-13 Payment Pending
→ CP-P-16 Late Payment After Expiry
→ CP-P-23 Refund Timeline
→ CP-P-24/25/26/27 outcome
```

| Source frame | Element ID | Visible label | Interaction type | Destination frame | Preconditions | Backend state represented | Mutation implied | Authorization | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-13` | `P13-late-payment-branch` | Simulate late payment | Navigate | `CP-P-16` | Booking expired before provider success | Payment `CONFIRMED`; booking `EXPIRED`; no session; refund/reconciliation started | Backend-driven simulation | Provider/system, parent observes | Checking status | Reconciliation unavailable | N/A | Back to payment status |
| `CP-P-16` | `P16-view-refund` | View refund timeline | Navigate | `CP-P-23` | Refund/reconciliation exists | Refund lifecycle | No | Parent owns payment | Loading timeline | Could not load refund | N/A | Back to late payment screen |
| `CP-P-16` | `P16-choose-slot` | Choose another slot | Navigate | `CP-P-07` | Parent wants new valid booking | New search flow | No | Parent | None | N/A | N/A | Back to late payment |

Forbidden in this branch:

```text
Booking confirmed
Session scheduled
Teacher payout pending
Review teacher
Retry old booking confirmation
```

## 7.2 Refund outcome branches

| Source frame | Element ID | Visible label | Interaction type | Destination frame | Preconditions | State shown | Mutation implied | Authorization | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-23` | `P23-refund-succeeded` | Simulate refund completed | Navigate | `CP-P-24` | Refund `SUCCEEDED` | Refund completed / refunded | Backend-driven simulation | System/provider | Loading | N/A | N/A | Back to timeline |
| `CP-P-23` | `P23-refund-failed` | Simulate refund failed | Navigate | `CP-P-25` | Refund `FAILED` | Refund failed | Backend-driven simulation | System/provider | Loading | N/A | N/A | Back to timeline |
| `CP-P-23` | `P23-refund-rejected` | Simulate refund rejected | Navigate | `CP-P-26` | Refund `REJECTED` | Refund rejected | Admin/system simulation | Admin/OPS | Loading | N/A | N/A | Back to timeline |
| `CP-P-23` | `P23-refund-cancelled` | Simulate refund cancelled | Navigate | `CP-P-27` | Refund `CANCELLED` | Refund cancelled | Admin/system simulation | Admin/OPS | Loading | N/A | N/A | Back to timeline |

Refund visual rules:

```text
APPROVED = warning
PROVIDER_PENDING = warning
SUCCEEDED = success
FAILED/REJECTED = danger
CANCELLED = neutral/danger
```

## 7.3 Session → Dispute → Refund/resolution outcome

```text
CP-P-18 Session Detail
→ CP-P-21 Dispute Create
→ CP-P-22 Dispute Status
→ CP-P-23 Refund Timeline, if refund action
```

| Source frame | Element ID | Visible label | Interaction type | Destination frame | Preconditions | Backend state represented | Mutation implied | Authorization | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-18` | `P18-report-problem` | Report problem | Navigate | `CP-P-21` | Parent participates in session | Dispute creation | No until submit | Parent | None | N/A | Disabled if not allowed | Back to session |
| `CP-P-21` | `P21-submit-dispute` | Submit dispute | Navigate | `CP-P-22` | Category + description | Dispute `OPEN`; session remains factual | Simulated `DISPUTE_OPENED` | Parent participant | Opening dispute | Invalid target | Disabled until valid | Back to session |
| `CP-P-22` | `P22-view-refund` | View refund timeline | Navigate | `CP-P-23` | Dispute resolution includes refund | Refund lifecycle | No | Parent owner | Timeline loading | No refund linked | Hidden if no refund | Back to dispute |

Dispute overlay rule:

```text
Session and booking factual state remain visible.
Dispute status appears separately.
```

## 7.4 Payment failure branch

```text
CP-P-13 Payment Pending
→ CP-P-15 Payment Failure
→ Retry if backend allows
or
→ Search/choose another slot
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-13` | `P13-payment-failed` | Simulate payment failed | Navigate | `CP-P-15` | Provider failure | Payment `FAILED` | Backend-driven | Provider/system | Checking | N/A | N/A | Back to pending |
| `CP-P-15` | `P15-retry-payment` | Try again | Navigate | `CP-P-12` | Backend says booking still payable/fulfillable | New payment initiation | No until pay | Parent owner | Checking eligibility | Retry unavailable | Disabled if expired/cancelled | Back to failure |
| `CP-P-15` | `P15-new-slot` | Choose another slot | Navigate | `CP-P-07` | Booking expired/unfulfillable | New search | No | Parent | None | N/A | N/A | Back to failure |

## 7.5 Operational incident branch

```text
Payment confirmed but session unavailable
→ status refresh
→ support escalation
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-14` | `P14-operational-incident` | Simulate verification issue | Navigate | `CP-P-31` | Payment confirmed but session missing detected | Operational incident | No user mutation | Parent observes | Automatic refresh | Support escalation | Retry payment disabled | Back to payment status |
| `CP-P-31` | `P31-refresh` | Refresh status | Swap variant | `CP-P-31` | Incident unresolved | Status refresh | No | Parent | Refresh spinner | Still reviewing | N/A | N/A |
| `CP-P-31` | `P31-contact-support` | Contact support | Overlay | Support overlay | Incident unresolved | Support path | No | Parent | None | N/A | N/A | Close overlay |

Forbidden:

```text
Retry payment
Retry booking
Retry session creation
```

---

# 8. Parent Privacy Prototype

## 8.1 Student data sharing permissions

```text
CP-P-04 Student Profile
→ CP-P-06 Data Sharing Permissions
→ Grant permission confirmation overlay
→ Updated permission state
→ Revoke confirmation overlay
→ Updated revoked state
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State represented | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-P-04` | `P04-manage-permissions` | Manage permissions | Navigate | `CP-P-06` | Parent owns student | Permission list | No | Parent | Loading | Access denied | N/A | Back to profile |
| `CP-P-06` | `P06-grant` | Grant access | Overlay | Grant permission modal | Valid teacher/session selected | Draft permission | No until confirm | Parent | None | No teacher context | Disabled without target | Close modal |
| Permission modal | `PERM-confirm-grant` | Confirm grant | Swap variant | `CP-P-06` active state | Scope/expiry valid | Permission active | Simulated permission created | Parent | Updating | Validation error | Disabled until valid | Return to permissions |
| `CP-P-06` | `P06-revoke` | Revoke | Overlay | Revoke confirmation | Active permission exists | Permission active | No until confirm | Parent | None | N/A | Disabled if expired/revoked | Close modal |
| Revoke modal | `PERM-confirm-revoke` | Confirm revoke | Swap variant | `CP-P-06` revoked state | Active permission exists | Permission revoked | Simulated revoke | Parent | Updating | Failed revoke | N/A | Return to permissions |

Teacher access must be limited to:

```text
scope
expiry
linked booking/session
```

---

# 9. Teacher Prototype

## 9.1 Teacher path overview

```text
CP-T-01 Onboarding
→ CP-T-02 Subjects & Pricing
→ CP-T-03 Verification
→ CP-T-04 Availability
→ CP-T-05 Dashboard
→ CP-T-06 Bookings
→ CP-T-07 Session Detail
→ CP-T-08 Attendance
→ CP-T-09 Session Report
→ CP-T-10 Earnings
→ CP-T-11 Payout Detail
```

## 9.2 Teacher interactions

| Source frame | Element ID | Visible label | Interaction type | Destination frame | Preconditions | Backend state represented | Mutation implied | Authorization | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-T-01` | `T01-start-setup` | Continue setup | Navigate | `CP-T-02` | Teacher authenticated | Teacher profile draft | No | Teacher | None | N/A | N/A | N/A |
| `CP-T-02` | `T02-add-offering` | Add offering | Overlay | Offering modal | Teacher profile exists | Draft offering | No until save | Teacher | None | Duplicate validation | Disabled if invalid | Close modal |
| Offering modal | `T02-save-offering` | Save offering | Navigate | `CP-T-03` | Subject/level/price/duration valid | `teacher_subjects` created | Simulated profile update | Teacher | Saving | Duplicate/invalid price | Disabled until valid | Back to subjects |
| `CP-T-03` | `T03-submit-verification` | Submit verification | Navigate | `CP-T-04` | Required docs/metadata | Verification `SUBMITTED` | Simulated verification submitted | Teacher | Uploading | Upload failed | Disabled until valid | Back to subjects |
| `CP-T-04` | `T04-add-availability` | Add availability | Overlay | Availability modal | Teacher profile exists | Availability draft | No until save | Teacher | None | Overlap | Disabled if invalid | Close modal |
| Availability modal | `T04-save-slot` | Save slot | Navigate | `CP-T-05` | Valid slot/no overlap | Slot `AVAILABLE` | Simulated slot created | Teacher | Saving | Overlap error | Disabled until valid | Back to availability |
| `CP-T-05` | `T05-view-bookings` | View bookings | Navigate | `CP-T-06` | Teacher has booking list | Scoped bookings | No | Teacher | Loading | N/A | N/A | Back dashboard |
| `CP-T-06` | `T06-open-session` | Open session | Navigate | `CP-T-07` | Teacher assigned | Session detail | No | Teacher | Loading | Access denied | N/A | Back bookings |
| `CP-T-07` | `T07-start-session` | Start session | Swap variant | `CP-T-07` started state | Session `SCHEDULED`, assigned teacher | Session `STARTED` | Simulated `SESSION_STARTED` | Teacher | Starting | Too early/invalid | Disabled unless scheduled | N/A |
| `CP-T-07` | `T07-attendance` | Attendance | Navigate | `CP-T-08` | Session scheduled/started | Attendance decision | No | Teacher | None | N/A | Disabled after completed | Back session |
| `CP-T-08` | `T08-complete-present` | Complete session | Navigate | `CP-T-09` | Attendance present; session started | Session `COMPLETED` | Simulated `SESSION_COMPLETED` | Teacher | Completing | Invalid state | Disabled unless started | Back session |
| `CP-T-09` | `T09-submit-report` | Submit report | Navigate | `CP-T-10` | Session `COMPLETED`, report valid | Report created, progress events | Simulated `REPORT_CREATED` | Teacher | Saving | Validation/duplicate | Disabled until valid | Back report |
| `CP-T-10` | `T10-view-payout` | View payout detail | Navigate | `CP-T-11` | Payout exists or eligible | Payout breakdown | No | Teacher | Loading | No payout | N/A | Back earnings |

## 9.3 Teacher recovery branch

```text
CP-T-11 Payout Detail
→ CP-T-13 Post-Payout Recovery
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-T-11` | `T11-view-recovery` | View recovery | Navigate | `CP-T-13` | Post-payout recovery exists | Separate recovery entry | No | Teacher owner | Loading | No recovery | Hidden if none | Back payout |

Old paid payout remains unchanged.

## 9.4 Teacher student context branch

```text
CP-T-07 Session Detail
→ CP-T-14 Student Context
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-T-07` | `T07-student-context` | View student context | Navigate | `CP-T-14` | Assigned session and permission/session scope | Permission-scoped context | No | Assigned teacher | Loading | Permission expired/denied | Disabled if no permission/context | Back session |

Student Passport is not unrestricted.

---

# 10. Admin / OPS Prototype

## 10.1 Verification and sensitive access path

```text
CP-A-01 Dashboard
→ CP-A-02 Verification Queue
→ CP-A-03 Verification Detail
→ CP-A-04 Sensitive Access Modal
→ CP-A-05 Secure Document View
→ CP-A-06 Audit Trail
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State represented | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-A-01` | `A01-verification-queue` | Verification queue | Navigate | `CP-A-02` | Admin/OPS role | Pending verifications | No | OPS/Admin | Loading table | Permission denied | Hidden if no role | Dashboard |
| `CP-A-02` | `A02-review` | Review | Navigate | `CP-A-03` | Verification submitted | Verification detail | No | OPS/Admin | Loading | Already resolved | Disabled if not authorized | Queue |
| `CP-A-03` | `A03-open-doc` | Access document | Overlay | `CP-A-04` | Sensitive document exists | Protected access request | No | Authorized OPS/Admin | None | No document | Disabled if unauthorized | Detail |
| `CP-A-04` | `A04-open-secure` | Open secure view | Navigate | `CP-A-05` | Reason provided | Sensitive access logged | Simulated audit/security event | Authorized OPS/Admin | Opening | Access denied | Disabled without reason | Close modal |
| `CP-A-05` | `A05-view-audit` | View audit trail | Navigate | `CP-A-06` | Audit record exists | Audit trail | No | OPS/Admin | Loading | N/A | N/A | Back secure view |
| `CP-A-03` | `A03-approve` | Approve | Navigate | `CP-A-02` | Admin/OPS allowed; review complete | Teacher verification approved | Simulated `TEACHER_VERIFIED` | Authorized OPS/Admin | Saving | Invalid state | Disabled without authority | Back detail |
| `CP-A-03` | `A03-reject` | Reject | Navigate | `CP-A-02` | Reason provided | Teacher verification rejected | Simulated `TEACHER_REJECTED` | Authorized OPS/Admin | Saving | Missing reason | Disabled without reason | Back detail |

Sensitive access modal must display:

```text
This access will be logged.
Reason required.
```

## 10.2 Refund and reconciliation path

```text
CP-A-01 Dashboard
→ CP-A-09 Refund Queue
→ CP-A-10 Refund Detail
→ CP-A-11 Refund Reconciliation
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State represented | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-A-01` | `A01-refund-queue` | Refund queue | Navigate | `CP-A-09` | OPS/Admin | Refund list | No | OPS/Admin | Loading | Permission denied | N/A | Dashboard |
| `CP-A-09` | `A09-open-refund` | Open refund | Navigate | `CP-A-10` | Refund exists | Refund detail | No | OPS/Admin | Loading | Not found | N/A | Queue |
| `CP-A-10` | `A10-approve-refund` | Approve refund | Swap variant | `CP-A-10` approved state | Refund `REQUESTED`; allocation valid | Refund `APPROVED` | Simulated `REFUND_APPROVED` | OPS/Admin | Saving | Allocation invalid | Disabled if invalid | N/A |
| `CP-A-10` | `A10-submit-provider` | Submit to provider | Swap variant | `CP-A-10` provider-pending state | Refund `APPROVED` | Refund `PROVIDER_PENDING` | Simulated provider submission | OPS/Admin | Submitting | Provider error | Disabled if not approved | N/A |
| `CP-A-10` | `A10-reconcile` | Reconcile | Navigate | `CP-A-11` | Refund requires reconciliation | Reconciliation form | No until submit | OPS/Admin | None | N/A | Disabled if not applicable | Back detail |
| `CP-A-11` | `A11-mark-succeeded` | Mark succeeded | Navigate | `CP-A-10` succeeded state | Valid reconciliation proof | Refund `SUCCEEDED`, payment refunded/partial | Simulated reconciliation success | OPS/Admin | Saving | Missing proof | Disabled until valid | Back reconciliation |
| `CP-A-11` | `A11-mark-failed` | Mark failed | Navigate | `CP-A-10` failed state | Valid failure reason | Refund `FAILED` | Simulated reconciliation failure | OPS/Admin | Saving | Missing reason | Disabled until valid | Back reconciliation |

Refund visual semantics:

```text
APPROVED and PROVIDER_PENDING remain warning states.
Only SUCCEEDED is success.
```

## 10.3 Payout path

```text
CP-A-01 Dashboard
→ CP-A-14 Payout Eligible Queue
→ CP-A-15 Payout Processing
→ CP-A-16 Payout Failure, if failure
→ CP-A-17 Recovery / Adjustment, if post-payout refund
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State represented | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-A-01` | `A01-payout-queue` | Payouts | Navigate | `CP-A-14` | OPS/Admin | Payout queue | No | OPS/Admin | Loading | Permission denied | N/A | Dashboard |
| `CP-A-14` | `A14-process-payout` | Process payout | Navigate | `CP-A-15` | Eligible, no open dispute, net > 0, refund exposure accounted | Payout candidate | No until confirm | OPS/Admin | None | Eligibility changed | Disabled if blocked | Back queue |
| `CP-A-15` | `A15-confirm-process` | Confirm process | Swap variant | `CP-A-15` processing/paid state | Still eligible | Payout `PROCESSING` then `PAID` | Simulated payout process | OPS/Admin | Processing | Provider failure branch | Disabled if stale | Back queue |
| `CP-A-15` | `A15-provider-failure` | Simulate failure | Navigate | `CP-A-16` | Provider failure | Payout `FAILED` | Backend-driven simulation | OPS/Admin | Processing | N/A | N/A | Back processing |
| `CP-A-16` | `A16-retry` | Retry safely | Swap variant | `CP-A-16` retrying state | Retryable failed payout | Payout retry | Simulated retry if allowed | OPS/Admin | Retrying | Failed again | Disabled if non-retryable | Back failure |
| `CP-A-14` | `A14-view-recovery` | View recovery | Navigate | `CP-A-17` | Recovery exists | Read-only adjustment | No | OPS/Admin | Loading | Not found | Hidden if none | Back queue |

A-17/A-59 recovery view is read-only.

No manual create adjustment CTA in MVP.

## 10.4 Event ledger path

```text
CP-A-01 Dashboard
→ CP-A-18 Event Ledger
→ CP-A-19 Event Detail Drawer
```

| Source | Element ID | Label | Interaction | Destination | Preconditions | State represented | Mutation | Auth | Loading | Error | Disabled | Back |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CP-A-01` | `A01-events` | Event Ledger | Navigate | `CP-A-18` | OPS/Admin | Event list | No | OPS/Admin | Loading | Permission denied | Hidden if no role | Dashboard |
| `CP-A-18` | `A18-open-event` | Open event | Drawer | `CP-A-19` | Event exists | Event detail | No | OPS/Admin | Loading | Redacted/denied | Disabled if not authorized | Close drawer |
| `CP-A-19` | `A19-related-entity` | Open related entity | Navigate | Entity frame | Related entity allowed | Related detail | No | OPS/Admin | Loading | Access denied | Disabled if unauthorized | Back to event |

Sensitive event detail access must be audited where applicable.

---

# 11. RTL Prototype Variants

Representative RTL frames:

```text
CP-RTL-01 Parent Dashboard RTL
CP-RTL-02 Teacher Search RTL
CP-RTL-03 Teacher Trust Profile RTL
CP-RTL-04 Booking / Payment RTL
CP-RTL-05 Refund Timeline RTL
CP-RTL-06 Teacher Payout RTL
CP-RTL-07 Admin Refund Queue RTL
```

## RTL interaction rules

- Frame navigation remains semantically identical.
- Layout mirrors horizontally.
- Timelines may mirror direction, but state order must remain clear.
- Directional icons mirror.
- DZD amounts remain readable.
- Mixed Arabic/French content remains legible.
- CTA hierarchy remains clear.

Do not invent final Arabic/French terminology.

Use:

```text
[POLICY DECISION REQUIRED]
```

---

# 12. Error / Loading / Empty Prototype States

## 12.1 Required state frames or variants

| State type | Required prototype variant |
|---|---|
| Loading | Skeleton/card/table/button spinner variants |
| Success | Payment success, refund completed, payout paid |
| Warning | Payment pending, refund approved, provider-pending, late payment |
| Failure | Payment failure, refund failed, payout failed |
| Empty | No students, no teachers, no reports, no payouts, no refunds |
| Permission denied | Student access denied, admin restricted, teacher context denied |
| Disabled action | Review disabled, pay disabled, payout disabled, context access disabled |
| Expired hold | Booking hold expired |
| Payment pending | Waiting provider confirmation |
| Late payment | Payment received after reservation expired |
| Dispute | Dispute open/under review |
| Payout blocked | Open dispute/refund exposure/report missing |
| Operational incident | Payment confirmed but session unavailable |

## 12.2 Prototype state destinations

| Trigger | Destination frame/variant |
|---|---|
| Slot unavailable | `CP-P-10` error variant |
| Hold expired | `CP-P-11` expired variant |
| Payment failure | `CP-P-15` |
| Payment pending delay | `CP-P-13` pending variant |
| Late payment | `CP-P-16` |
| Refund failed | `CP-P-25` |
| Refund rejected | `CP-P-26` |
| Refund cancelled | `CP-P-27` |
| Payout blocked | `CP-A-14` blocked row / `CP-T-10` blocked card |
| Payout failed | `CP-A-16` |
| Permission revoked | `CP-P-06` revoked variant / `CP-T-14` denied variant |
| Operational incident | `CP-P-31` |

---

# 13. Prototype Testing Scenarios

## 13.1 Scenario table

| Scenario | Starting frame | User action | Expected prototype behavior | Expected state shown | Forbidden behavior |
|---|---|---|---|---|---|
| Happy path | `CP-P-01` | Parent follows booking/payment/session/report/review path | Ends at verified review submitted | Booking confirmed, session completed, report available, review created | Skipping payment/session/report eligibility |
| Payment pending | `CP-P-12` | Parent pays; provider delayed | Shows `CP-P-13` pending | Payment pending, booking waiting confirmation | Showing confirmed session |
| Payment failure | `CP-P-13` | Simulate payment failed | Shows `CP-P-15` | Payment failed; retry only if allowed | Retry when booking expired |
| Late payment after expiry | `CP-P-13` | Simulate late success | Shows `CP-P-16` | Payment received, booking expired, no session, refund started | Booking confirmed/session scheduled |
| Successful refund | `CP-P-23` | Simulate refund success | Shows `CP-P-24` | Refund completed/SUCCEEDED | Showing refunded before SUCCEEDED |
| Failed refund | `CP-P-23` | Simulate failed refund | Shows `CP-P-25` | Refund failed | Success-green treatment |
| Rejected refund | `CP-P-23` | Simulate rejected refund | Shows `CP-P-26` | Refund rejected | Refund completed label |
| Cancelled refund | `CP-P-23` | Simulate cancelled refund | Shows `CP-P-27` | Refund cancelled | Provider success visuals |
| Partial refund | `CP-A-10` | Approve/provider-pending/succeed partial refund | Payout exposure updates | Approved/provider-pending/succeeded adjustments visible | Waiting until SUCCEEDED to show exposure |
| Dispute | `CP-P-18` | Parent opens dispute | Shows dispute overlay/status | Factual session remains completed/scheduled as applicable | Replacing session state with disputed factual state |
| No-show | `CP-T-08` | Teacher marks student no-show | Shows no-show state | Student absent; parent notified path | Parent finalizing teacher no-show without review |
| Payout blocked | `CP-A-14` | View blocked payout | Shows blocked reason | Open dispute/refund/report blocker | Process enabled despite blocker |
| Payout failure | `CP-A-15` | Simulate provider payout failure | Shows `CP-A-16` | Payout failed, retry if allowed | Duplicate payout item implied |
| Post-payout recovery | `CP-T-11` | View recovery | Shows `CP-T-13` | Separate adjustment/recovery | Editing old paid payout |
| Sensitive admin access | `CP-A-03` | Open document | Shows sensitive modal then secure view | This access will be logged | Direct document opening without audit warning |
| Permission revoked | `CP-P-06` | Revoke teacher access | Teacher context denied variant | Permission revoked | Teacher retains unrestricted context |
| Permission expired | `CP-T-14` | View expired context | Permission denied/expired | Access expired | Student Passport unrestricted |
| Unauthorized action | Any protected action | Click with wrong role | Permission denied state | Role/ownership failure | Revealing private resource existence |
| Network timeout | Payment/refund/payout action | Simulate timeout | Status refresh/check state | Pending/unknown with safe retry/status check | Assuming success or failure incorrectly |
| Duplicate tap | Hold/payment/refund/payout action | Tap twice | Shows loading/replay-safe state | No duplicate entity implied | Duplicate booking/payment/payout |
| Operational incident | `CP-P-14` | Simulate confirmed payment but missing session | Shows `CP-P-31` | Automatic refresh/support escalation | User retry payment/booking/session creation |

---

# 14. Prototype Acceptance Criteria

The prototype must prove:

1. A parent can understand the complete transaction lifecycle.
2. A parent cannot accidentally interpret pending or expired state as confirmed.
3. Refund states are unambiguous.
4. Teacher payout calculations are understandable.
5. Paid payouts are visibly immutable.
6. Recovery is visibly separate from historical payout.
7. Student permissions are understandable.
8. Sensitive admin access is visibly audited.
9. All critical error paths are understandable.
10. No prototype interaction creates a business rule that does not exist in the architecture.

---

# 15. Open Policy Decisions

The following remain unresolved and must stay as placeholders:

1. Booking hold duration
2. Payment checkout timeout
3. Late-payment auto-refund vs OPS review
4. No-show grace periods
5. Parent dispute window
6. Payout delay
7. Refund allocation teacher/platform
8. Review eligibility after partial refund
9. Notification channels
10. Arabic/French terminology

Use:

```text
[POLICY DECISION REQUIRED]
```

Do not invent values.

---

# 16. Prototype Review Checklist

Before approving the clickable prototype, verify:

- [ ] Parent happy path is clickable end-to-end.
- [ ] Teacher path is clickable end-to-end.
- [ ] Admin refund/reconciliation path is clickable.
- [ ] Admin sensitive access path shows audit warning.
- [ ] Late payment branch is clickable.
- [ ] Refund success/failure/rejected/cancelled branches are clickable.
- [ ] Payout blocked/failure/recovery paths are clickable.
- [ ] Permission grant/revoke/expired states are clickable.
- [ ] Duplicate tap/network timeout states are represented.
- [ ] No unauthorized CTA appears.
- [ ] No excluded MVP features appear.
- [ ] Policy placeholders remain unresolved.

---

# 17. Final Status

```text
Clickable Prototype Specification v1.0: READY FOR REVIEW
```

Do not begin implementation.

Do not write production UI code.

Do not modify architecture, database, API architecture, or state machines.
