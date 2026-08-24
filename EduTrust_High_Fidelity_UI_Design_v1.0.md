# EduTrust Algeria — High-Fidelity UI Design v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** High-fidelity UI design specification  
**Status:** Ready for High-Fidelity Review  
**Implementation status:** No frontend/backend implementation started  
**Derived from:** Approved Low-Fidelity Baseline

Approved design foundation:

```text
EduTrust_Low_Fidelity_Wireframes_v1.0.md
+
EduTrust_Low_Fidelity_Wireframes_v1.1_Patch.md
+
EduTrust_Low_Fidelity_Wireframes_Final_Audit_v1.0.md
```

Locked architecture foundation:

```text
PRD v1.0
Database Schema v1.0
API Architecture v1.0
State Machines v1.0
Schema Patch v1.1
State Machines v1.1 Addendum
Schema Patch v1.2
DDL Hardening v1.3
DDL Audit FINAL PASS
UX Flows v1.0
UX Flows v1.1 Patch
Low-Fidelity Wireframes Final Audit PASS
```

---

# 1. Executive Summary

This document converts the approved low-fidelity interaction architecture into a high-fidelity UI design specification.

It defines:

- Visual direction
- Layout system
- Component system
- Status badges
- Financial state presentation
- Privacy and audit presentation
- Parent, Teacher, and Admin screen-level UI design
- Critical edge-state UI design
- Accessibility and responsive behavior
- High-fidelity review checklist

This document does **not**:

- change architecture,
- change database schema,
- change API state machines,
- introduce new MVP features,
- start frontend implementation,
- start backend implementation,
- create production UI code.

---

# 2. High-Fidelity Design Principles

## 2.1 Trust before decoration

The UI must make trust evidence visible without overwhelming the user.

Examples:

```text
Verified identity
Verified qualifications
Verified sessions
Attendance rate
Cancellation rate
Review count
```

## 2.2 State clarity before visual polish

Financial and operational states must be unmistakable.

Especially:

```text
Payment pending ≠ Payment confirmed
Refund approved ≠ Refunded
Booking expired ≠ Booking confirmed
Dispute open ≠ Session not completed
Paid payout ≠ Editable payout
```

## 2.3 Parent-first simplicity

Parents should see simple, safe labels:

```text
Reserved temporarily
Payment pending
Session confirmed
Report available
Refund processing
Dispute under review
```

They should not see implementation terms like:

```text
webhook
ledger
provider_event_id
idempotency
row lock
```

## 2.4 Teacher operating clarity

Teachers need to know:

- what to do next,
- what is blocking payout,
- which reports are due,
- what earnings are adjusted by refund exposure,
- what student context they may access.

## 2.5 Admin operational precision

Admin/OPS screens may show more technical/operational details, but sensitive access must be controlled and visibly audited.

Mandatory text on sensitive access screens:

```text
This access will be logged.
```

## 2.6 Mobile-first, desktop-capable

Parent and teacher experiences are mobile-first.

Admin experience is desktop-first.

---

# 3. Brand and Visual Direction

## 3.1 Brand personality

EduTrust should feel:

```text
Safe
Professional
Educational
Transparent
Calm
Reliable
Local to Algeria
```

Avoid:

```text
Overly playful visuals
Gaming-style UI
Aggressive marketplace urgency
Luxury/elitist styling
AI-first branding
```

## 3.2 Visual metaphor

Use a visual language of:

- verified records,
- educational continuity,
- structured progress,
- secure transactions,
- parent visibility.

Recommended motifs:

```text
Checkmarks
Timelines
Cards
Progress notes
Verified badges
Document/report icons
Calendar/session markers
```

---

# 4. Design Tokens v1.0

These are design tokens for high-fidelity mockups. They are not implementation code.

## 4.1 Color palette

| Token | Hex | Purpose |
|---|---:|---|
| `trust-blue-700` | `#1D4ED8` | Primary actions, trusted links |
| `trust-blue-50` | `#EFF6FF` | Subtle primary backgrounds |
| `deep-navy-900` | `#0F172A` | Main text, admin headers |
| `slate-700` | `#334155` | Secondary text |
| `slate-500` | `#64748B` | Hints, metadata |
| `slate-200` | `#E2E8F0` | Borders |
| `surface-50` | `#F8FAFC` | App background |
| `white` | `#FFFFFF` | Cards/surfaces |
| `success-700` | `#15803D` | Success states |
| `success-50` | `#F0FDF4` | Success backgrounds |
| `warning-700` | `#B45309` | Warning/pending states |
| `warning-50` | `#FFFBEB` | Warning backgrounds |
| `danger-700` | `#B91C1C` | Error, rejected, failed |
| `danger-50` | `#FEF2F2` | Error backgrounds |
| `info-700` | `#0369A1` | Informational states |
| `info-50` | `#F0F9FF` | Informational backgrounds |
| `purple-700` | `#7E22CE` | Admin/audit/recovery markers |
| `purple-50` | `#FAF5FF` | Audit/recovery backgrounds |

## 4.2 Color usage rules

- Use blue for trusted primary navigation/action.
- Use green only for completed successful states.
- Use amber for pending, review, approved-but-not-final states.
- Use red for failed, rejected, cancelled, or dangerous actions.
- Use purple for admin/audit/recovery states.

Critical financial rule:

```text
REFUND_APPROVED and PROVIDER_PENDING must not use success green.
Only SUCCEEDED can use success green.
```

## 4.3 Typography

Recommended font pairing:

| Language/context | Font family |
|---|---|
| Arabic UI | `Noto Sans Arabic` or `IBM Plex Sans Arabic` |
| French/Latin UI | `Inter` or system sans |
| Admin dense tables | `Inter` or system sans |
| Numeric financial data | Tabular numeric variant where available |

Final Arabic/French terminology remains:

```text
[POLICY DECISION REQUIRED]
```

## 4.4 Type scale

| Token | Size | Use |
|---|---:|---|
| Display | 28–32px | Parent/teacher dashboard greeting |
| H1 | 24px | Screen title |
| H2 | 20px | Section title |
| Body | 16px | Main readable text |
| Body small | 14px | Metadata, helper copy |
| Caption | 12px | badges, timestamps |
| Table body | 13–14px | Admin dense tables |

## 4.5 Spacing

Use 8px grid:

```text
4 / 8 / 12 / 16 / 24 / 32 / 48
```

Recommended:

- Mobile page padding: 16px
- Desktop page padding: 24–32px
- Card padding: 16–24px
- Form field spacing: 12–16px

## 4.6 Radius and surfaces

| Token | Value | Use |
|---|---:|---|
| `radius-sm` | 6px | badges, small controls |
| `radius-md` | 10px | inputs, buttons |
| `radius-lg` | 16px | cards |
| `radius-xl` | 24px | large dashboard panels |

Cards:

```text
white background
1px slate-200 border
subtle shadow for elevated panels only
```

## 4.7 Accessibility

- Minimum contrast ratio: WCAG AA.
- Do not rely on color alone; pair color with icon/text.
- Touch target minimum: 44px.
- All state badges must have text labels.
- Error messages must be placed near the field and summarized at form level.
- RTL support must be considered from the beginning.

---

# 5. Component System v1.0

## 5.1 Buttons

### Primary button

Use for one main action per screen:

```text
Find teacher
Reserve slot
Pay
Submit report
Process payout
```

Visual:

```text
trust-blue-700 background
white text
radius-md
44–48px height mobile
```

### Secondary button

Use for navigation or alternative action:

```text
Back
View details
Contact support
Choose another slot
```

Visual:

```text
white background
slate-200 border
trust-blue-700 or deep-navy text
```

### Danger button

Use only for destructive/serious action:

```text
Cancel booking
Suspend user
Reject refund
```

Visual:

```text
danger-700 background or outline depending severity
confirmation required
```

### Disabled button

Must include explanation nearby.

Example:

```text
Review Teacher disabled
Reason: Review is available after the session is completed.
```

## 5.2 Status badges

All badges must include text and optional icon.

| Category | Visual treatment |
|---|---|
| Success | green text/background |
| Pending | amber text/background |
| Failed/rejected | red text/background |
| Informational | blue text/background |
| Audit/recovery | purple text/background |
| Neutral | slate text/background |

## 5.3 Timelines

Use timelines for:

- booking lifecycle,
- payment status,
- refund lifecycle,
- dispute handling,
- verification,
- payout processing.

Timeline step states:

```text
Completed
Current
Pending
Failed
Cancelled
Skipped
```

## 5.4 Trust cards

Teacher Trust Profile uses trust cards:

```text
Identity verified
Qualifications reviewed
Verified sessions
Rating + review count
Attendance rate
Cancellation rate
```

Trust cards must avoid unexplained algorithmic scores.

## 5.5 Financial breakdown cards

Use a clear stacked breakdown:

```text
Gross teacher payable
- Approved refund adjustment
- Provider-pending refund adjustment
- Succeeded refund adjustment
- Other deductions
= Net teacher payable
```

Frontend displays backend-calculated values. Frontend must not become financial calculation authority.

## 5.6 Sensitive access modal

Required for admin sensitive views.

```text
Title: Sensitive access
Message: This access will be logged.
Reason field
Entity summary
[Open secure view]
[Cancel]
```

## 5.7 Empty states

Empty states must suggest next valid action.

Example:

```text
No students yet → Add student
No slots available → Try another teacher or date
No reports yet → Reports appear after completed sessions
No eligible payouts → Completed reported sessions will appear here
```

---

# 6. Financial State Presentation

## 6.1 Refund visual states

| Refund backend state | UI label | Color | Notes |
|---|---|---|---|
| `REQUESTED` | Refund requested | info | Request exists |
| `APPROVED` | Refund approved | warning | Not money returned |
| `PROVIDER_PENDING` | Refund processing | warning | Sent to provider / awaiting confirmation |
| `SUCCEEDED` | Refund completed | success | Money returned/reconciled |
| `FAILED` | Refund failed | danger | Support/admin review needed |
| `REJECTED` | Refund rejected | danger | No refund issued |
| `CANCELLED` | Refund cancelled | neutral/danger | Cancelled before completion |

Hard rule:

```text
Only SUCCEEDED can use “Refund completed” or “Refunded.”
```

## 6.2 Late payment after expiry presentation

Use warning, not success.

Title:

```text
Payment received after reservation expired
```

Do not show:

```text
Booking confirmed
Session scheduled
Teacher payout pending
```

## 6.3 Payout visual states

| Payout state | UI label | Color |
|---|---|---|
| Eligible | Eligible | info |
| Processing | Processing | warning |
| Paid | Paid | success |
| Failed | Failed | danger |
| Blocked | Blocked | warning/danger depending reason |
| Recovery pending | Recovery pending | purple/warning |

## 6.4 Post-payout recovery presentation

Original payout card remains unchanged:

```text
Payout #P-1001 — Paid — 1700 DZD
```

Adjustment appears separately:

```text
Adjustment #A-2001 — Recovery due to refund — -300 DZD
```

---

# 7. Parent Experience — High-Fidelity Screen Design

## P-01 — Authentication / Login

Visual layout:

```text
Top: EduTrust wordmark
Middle: Login/Register card
Bottom: language/help links
```

High-fidelity details:

- Use calm trust-blue accent.
- Use segmented tabs for Login / Create account.
- Show password/OTP area based on auth method.
- Error messages are generic and non-enumerating.
- Mobile-first centered card.

Primary CTA:

```text
Login / Create account
```

Security note:

```text
Your account protects access to your child’s education records.
```

Final Arabic/French wording:

```text
[POLICY DECISION REQUIRED]
```

---

## P-02 — Parent Dashboard

Visual layout:

```text
Greeting header
Children summary cards
Upcoming session card
Pending actions card
Find teacher CTA
Notifications preview
```

High-fidelity details:

- Use a prominent “Find teacher” button.
- Pending actions are shown as cards with status badges.
- Disputes and refunds appear as alert rows, not hidden in payment history.
- Student names use display names only.

Critical UI logic:

```text
Review CTA only appears if backend says eligible.
Pay CTA only appears if booking is HELD and unexpired.
```

---

## P-03 — Student List

Visual layout:

```text
Page title: Children / Students
Student cards
Add student floating or top CTA
```

Card content:

```text
Display name
Academic level
Upcoming session count
Recent report/progress note
```

Privacy:

- Do not show unnecessary minor data.
- No full legal identity required in UI.

---

## P-04 — Create Student

Visual layout:

```text
Single-column form
Privacy note at top
Fields grouped into: Basic info / Learning goal / Preferences
```

High-fidelity details:

- Use helper text under each field.
- Consent checkbox must be clear and not prechecked.
- Use simple academic level dropdown.

Disabled state:

```text
Save disabled until required fields and consent are complete.
```

---

## P-05 — Student Profile

Visual layout:

```text
Student header card
Quick actions row
Recent sessions
Reports/progress preview
Data sharing summary
```

Primary actions:

```text
Find teacher
View Passport
Manage permissions
```

High-fidelity note:

- Permissions must be visible enough that parents understand who can access context.

---

## P-06 — Student Passport v0

Visual layout:

```text
Student Passport header
Subject tabs/cards
Completed sessions
Recent topics
Teacher observations
Homework/progress notes
```

Design style:

- Use education report cards, not analytics dashboards.
- Avoid AI-looking charts or predictive visuals.

State label:

```text
Based on verified session reports
```

No AI claims.

---

## P-07 — Student Data Sharing Permissions

Visual layout:

```text
Permission explanation banner
Active access list
Expired/revoked list collapsed
Grant access CTA
```

Permission card:

```text
Teacher name
Scope: SESSION_CONTEXT
Linked booking/session
Expires at
[Revoke]
```

High-fidelity rule:

- Use a privacy-shield icon.
- Show “Parent controlled” badge.
- Revoke action requires confirmation.

---

## P-08 — Teacher Search

Visual layout:

```text
Student selector
Filter form
Search CTA
Find best match CTA
```

Filters:

```text
Subject
Academic level
Mode
Budget
Availability
Language
Location if in-person
```

High-fidelity details:

- Use filter chips after search.
- Use mobile bottom sheet for filters.
- Do not show “AI matching.” Use “Find best match” / “Recommended matches.”

---

## P-09 — Matching Results

Visual layout:

```text
Results header
Teacher cards
Filter chips
Sort/filter controls
```

Teacher card:

```text
Name/photo
Subjects/level
Price
Next available slot
Trust summary row
Why recommended bullets
[View profile]
[Select slot]
```

Critical:

- Reasons must be explainable.
- Do not show unexplained 94% score as primary signal.

---

## P-10 — Teacher Trust Profile

Visual layout:

```text
Teacher hero card
Subject offerings
Trust Profile grid
Verified reviews
Availability preview
```

Trust grid:

```text
Identity verified
Qualifications reviewed
Verified sessions
Rating + review count
Attendance
Cancellation
```

Visual style:

- Use verified checkmarks.
- Display review count next to rating.
- Avoid paid ranking visuals.

---

## P-11 — Teacher Availability

Visual layout:

```text
Calendar/list hybrid
Date selector
Slot chips
Selected slot summary bottom sheet
```

Slot chip states:

```text
Available: blue/neutral
Held: amber/disabled
Booked: grey/disabled
Blocked: grey/disabled
```

Primary CTA:

```text
Reserve this slot
```

---

## P-12 — Booking Hold

Visual layout:

```text
Reservation summary card
Countdown area
Payment CTA
Cancel/choose another slot
```

Countdown:

```text
Reserved for [POLICY DECISION REQUIRED]
```

Warning state near expiry:

```text
Your reservation is about to expire.
```

No invented duration.

---

## P-13 — Checkout / Payment Initiation

Visual layout:

```text
Booking summary
Amount card
Payment method card
Security note
Pay CTA
```

Payment button disabled if:

```text
hold expired
booking not HELD
provider unavailable
```

No raw provider information shown.

---

## P-14 — Payment Pending

Visual layout:

```text
Status illustration/icon: pending
Payment submitted
Booking waiting for confirmation
Refresh/status polling area
```

Copy:

```text
Payment confirmation may take a few moments.
We will update your booking automatically.
```

Do not show confirmed session yet.

---

## P-14A / P-22A — Late Payment After Expiry / Reconciliation

Visual layout:

```text
Warning banner
Payment received card
Reservation expired card
Refund/reconciliation timeline
Actions
```

Primary message:

```text
Your payment was received after the reservation expired, so the session was not confirmed.
A refund/reconciliation process has been started.
```

State badges:

```text
Payment received
Reservation expired
Refund/reconciliation started
No session scheduled
```

Primary CTA:

```text
View refund timeline
```

Secondary CTAs:

```text
Choose another slot
Contact support
```

Disabled/hidden:

```text
View session
Review teacher
Retry old booking
Reassign slot
```

---

## P-15 — Payment Success

Visual layout:

```text
Success state
Payment confirmed
Booking confirmed
Session scheduled card
Receipt link
```

Show only when:

```text
payment = CONFIRMED
booking = BOOKED
session = SCHEDULED
```

Operational incident copy:

```text
We are verifying your booking confirmation. If this does not update shortly, support will review it.
```

Do not show retry payment or retry booking for missing-session incident.

---

## P-16 — Payment Failure / Retry

Visual layout:

```text
Error status
Payment failed or setup failed
Booking/hold status
Retry eligibility
```

Primary CTA:

```text
Try again
```

Only if backend says booking is still payable/fulfillable.

If expired:

```text
Choose another slot
```

---

## P-17 — Booking Detail

Visual layout:

```text
Booking status header
Teacher/student/session summary
Payment state
Session state
Dispute/refund overlays
Timeline
Actions
```

Critical:

- Dispute shown as overlay banner.
- No reschedule button.
- Use cancel + new booking.

---

## P-18 — Session Detail

Visual layout:

```text
Session header
Status badge
Teacher/student/subject/time
Attendance state
Report state
Dispute overlay if any
```

Parent cannot start or complete session.

---

## P-19 — Session Report

Visual layout:

```text
Report title
Topics covered
Skills practiced
Participation
Observations
Homework
Revision
Next objectives
```

Use readable sections and icons.

Primary CTA:

```text
Review teacher
```

Only when backend says eligible.

---

## P-20 — Review

Visual layout:

```text
Verified session summary
Rating input
Comment input
Review policy note
Submit button
```

Use a visible badge:

```text
Verified completed session
```

Do not show if not eligible.

---

## P-21 — Payment / Invoice History

Visual layout:

```text
Payment cards/list
Status badges
Refund summary badges
Receipt/invoice links
```

Refund state must link to P-22 timeline.

---

## P-22 — Refund Timeline

Visual layout:

```text
Refund timeline
Amount card
Reason card
Related dispute/payment links
```

Timeline states:

```text
Requested
Approved
Submitted to provider
Completed / Failed / Rejected / Cancelled
```

Use green only for completed/succeeded.

---

## P-23 — Dispute

Visual layout:

```text
Dispute form or status timeline
Category selector
Description
Evidence area
Linked booking/session/payment summary
```

Safety category receives priority visual treatment.

Dispute does not replace factual states.

---

## P-24 — Refund Rejected

Visual layout:

```text
Rejected state
Reason
Related dispute/payment
Contact support
```

Do not show refund completed visuals.

---

## P-25 — Refund Cancelled

Visual layout:

```text
Cancelled state
No refund issued
Reason
Payment link
```

Do not show provider success or refund receipt.

---

## P-26 — Refund Completed

Visual layout:

```text
Success state
Amount refunded
Completion date
Full/partial indicator
Payment history link
```

Only for refund `SUCCEEDED`.

---

## P-27 — Notifications

Visual layout:

```text
Unread/read list
Notification cards
Category icons
Target navigation
```

Canonical endpoints:

```text
GET /notifications
POST /notifications/:id/read
```

---

## P-28 — Account / Security

Visual layout:

```text
Profile settings
Language
Active sessions
Security events
Logout/revoke sessions
```

Canonical endpoints:

```text
GET /auth/sessions
GET /account/security-events
POST /auth/logout
POST /auth/revoke-sessions
```

---

# 8. Teacher Experience — High-Fidelity Screen Design

## T-29 — Teacher Onboarding

Visual layout:

```text
Teacher welcome
Setup checklist
Progress indicator
Next step CTA
```

Checklist:

```text
Profile
Subjects & Pricing
Verification
Availability
```

Do not imply teacher is listed until listing requirements are met.

---

## T-30 — Teacher Verification

Visual layout:

```text
Verification checklist
Upload panels
Status timeline
Privacy note
```

Document access/privacy note:

```text
Your documents are reviewed securely and are not public.
```

---

## T-31 — Teacher Dashboard

Visual layout:

```text
Profile/listing status
Upcoming sessions
Reports due
Earnings summary
Notifications
```

Canonical bookings endpoint:

```text
GET /bookings?scope=teacher
```

---

## T-32 — Subjects & Pricing

Visual layout:

```text
Offering cards
Subject / level / price / duration
Active/inactive toggle
Add/edit/deactivate controls
```

Duplicate offering error:

```text
You already offer this subject for this academic level.
```

---

## T-33 — Availability Management

Visual layout:

```text
Calendar
Recurring rule panel
Concrete slot list
Block/unblock controls
```

Canonical endpoints:

```text
POST /teachers/availability/rules
PATCH /teachers/availability/rules/:id
POST /teachers/availability/slots
POST /teachers/availability/slots/:id/block
POST /teachers/availability/slots/:id/unblock
```

Booked slots cannot be silently removed.

---

## T-34 — Booking Requests / Bookings

Visual layout:

```text
Booking list tabs
Upcoming / payment pending / confirmed / completed / cancelled
Booking cards
```

Teacher cannot confirm payment or directly complete booking.

---

## T-35 — Session Detail

Visual layout:

```text
Session state header
Student context card
Start/complete controls
Attendance/report status
```

CTA rules:

```text
Start only if SCHEDULED and assigned teacher
Complete only if STARTED and assigned teacher
Report only if COMPLETED
```

---

## T-36 — Attendance

Visual layout:

```text
Attendance decision card
Present / Student no-show
Grace period placeholder
```

Grace period:

```text
[POLICY DECISION REQUIRED]
```

---

## T-37 — Session Report

Visual layout:

```text
Fast report form
Sectioned input cards
Submit report CTA
```

Target completion:

```text
under 2 minutes
```

No AI assistance in MVP.

---

## T-38 — Reviews

Visual layout:

```text
Rating summary
Review count
Verified review list
```

Teacher cannot edit/delete reviews.

---

## T-39 — Earnings

Visual layout:

```text
Earnings summary cards
Gross payable
Refund exposure
Deductions
Net payable
Blocked reasons
```

Frontend displays backend-calculated values.

---

## T-40 — Payout Detail

Visual layout:

```text
Payout status timeline
Financial breakdown
Included sessions
Blocked reasons
```

Refund exposure includes:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

---

## T-41 — Refund Adjustment

Visual layout:

```text
Adjustment card
Refund status
Teacher adjustment amount
Effect on net payout
```

Use amber for approved/provider-pending exposure.

Use green only after succeeded.

---

## T-42 — Post-Payout Recovery

Visual layout:

```text
Original paid payout card
Separate recovery/adjustment card
Future offset status
Platform absorbed amount if applicable
```

Old payout remains visually locked/immutable.

---

## T-43 — Student Session Context / Permission Boundary

Visual layout:

```text
Limited student context
Permission status
Scope
Expiry
Linked session
```

Teacher sees only permitted data.

Sensitive access must audit where applicable.

---

## T-44 — Notifications

Visual layout:

```text
Notification list
Booking/session/report/payout/verification filters
```

Canonical endpoints:

```text
GET /notifications
POST /notifications/:id/read
```

---

## T-45 — Account / Security

Visual layout:

```text
Account settings
Active sessions
Security events
Logout/revoke sessions
```

Canonical endpoints:

```text
GET /auth/sessions
GET /account/security-events
POST /auth/logout
POST /auth/revoke-sessions
```

---

# 9. Admin / OPS Experience — High-Fidelity Screen Design

## A-46 — Admin Dashboard

Visual layout:

```text
Operational KPI cards
Queues
Critical alerts
Recent events
```

Admin UI is desktop-first with dense but readable tables.

---

## A-47 — Teacher Verification Queue

Visual layout:

```text
Table
Teacher
Verification type
Submitted at
Status
Review action
```

No document preview in queue.

---

## A-48 — Teacher Verification Detail

Visual layout:

```text
Teacher profile summary
Verification metadata
Sensitive document access panel
Approve/reject controls
```

Mandatory notice:

```text
This access will be logged.
```

---

## A-49 — Booking Monitoring

Visual layout:

```text
Filterable table
Booking/payment/session/dispute columns
Status badges
```

Ordinary list read does not need Event Ledger.

Sensitive drilldown must be audited.

---

## A-50 — Payment Monitoring

Visual layout:

```text
Payments table
Provider/status filters
Refund/reconciliation indicators
```

Raw provider payload hidden by default.

Sensitive provider payload access must audit.

---

## A-51 — Refund Queue

Visual layout:

```text
Refund lifecycle tabs
Requested / Approved / Provider pending / Failed / Rejected / Cancelled / Succeeded
```

Canonical endpoint:

```text
GET /admin/refunds
```

Sensitive refund/payment access must audit.

---

## A-52 — Refund Detail

Visual layout:

```text
Refund timeline
Amount/allocation card
Linked payment/booking/dispute
Provider/reconciliation summary
Actions
```

Do not show `PAYMENT_REFUNDED` before refund `SUCCEEDED`.

---

## A-53 — Refund Reconciliation

Visual layout:

```text
Warning banner: This access/action will be logged.
Reconciliation form
Source
Reference
Timestamp
Reason
Evidence
Mark succeeded/failed
```

Canonical endpoint:

```text
POST /admin/refunds/:id/reconcile
```

Idempotency required.

---

## A-54 — Dispute Queue

Visual layout:

```text
Priority queue
Safety flags
Category filters
Status tabs
```

Safety disputes visually prioritized.

---

## A-55 — Dispute Detail

Visual layout:

```text
Dispute timeline
Factual booking/session/payment states
Evidence
Resolution panel
Refund/payout impact
```

Factual state and dispute overlay must be visually separate.

---

## A-56 — Payout Eligible Queue

Visual layout:

```text
Eligible/blocked payout table
Teacher
Gross payable
Refund exposure
Deductions
Net payable
Blocked reason
```

Process disabled if eligibility blockers exist.

---

## A-57 — Payout Processing

Visual layout:

```text
Batch confirmation screen
Included sessions
Net payable
Provider processing state
```

Idempotency required.

---

## A-58 — Payout Failure

Visual layout:

```text
Failure summary
Provider/reference if safe
Retry/cancel options based on policy
Audit link
```

Do not create duplicate payout items.

---

## A-59 — Recovery / Adjustment

Visual layout:

```text
Read-only recovery view
Original paid payout
Refund reference
Teacher recoverable
Platform absorbed amount
Future payout offset
Ledger/audit links
```

No manual create adjustment CTA in MVP.

---

## A-60 — Event Ledger

Visual layout:

```text
Search/filter panel
Immutable event table
Event detail drawer
```

Sensitive event detail access must be audited.

---

## A-61 — Security Events

Visual layout:

```text
Security event table
Severity badges
User/entity filters
```

Security event viewing must be audited according to role/policy.

---

## A-62 — Sensitive Document / Provider Payload Access

Visual layout:

```text
Sensitive access modal
This access will be logged.
Reason required
Open secure view
```

No raw unrestricted payload/document access by default.

---

## A-63 — User Suspension

Visual layout:

```text
User summary
Reason field
Impact warning
Suspend/reactivate CTA
```

ADMIN only.

Action must audit.

---

## A-64 — Audit Trail

Visual layout:

```text
Entity timeline
Business events
Admin actions
Security events
Provider event summaries
```

Sensitive audit trail access must be audited.

---

# 10. Responsive Behavior

## 10.1 Parent mobile

- Bottom navigation.
- Cards over tables.
- Sticky CTA for booking/payment flows.
- Timelines collapse vertically.

## 10.2 Teacher mobile/tablet

- Dashboard card layout.
- Calendar scrolls horizontally by week.
- Report form is single-column.
- Earnings breakdown uses stacked cards.

## 10.3 Admin desktop

- Left sidebar navigation.
- Dense tables with filters.
- Detail drawer or split view.
- Sensitive access modal.
- Audit timeline panel.

---

# 11. Open Policy Placeholders

The following must remain placeholders in high-fidelity mockups unless separately decided:

| Policy | UI placeholder |
|---|---|
| Booking hold duration | `[POLICY DECISION REQUIRED]` |
| Payment checkout timeout | `[POLICY DECISION REQUIRED]` |
| Late-payment auto-refund vs OPS review | `[POLICY DECISION REQUIRED]` |
| No-show grace periods | `[POLICY DECISION REQUIRED]` |
| Parent dispute window | `[POLICY DECISION REQUIRED]` |
| Payout delay | `[POLICY DECISION REQUIRED]` |
| Refund allocation teacher/platform | `[POLICY DECISION REQUIRED]` |
| Review eligibility after partial refund | `[POLICY DECISION REQUIRED]` |
| Notification channels | `[POLICY DECISION REQUIRED]` |
| Arabic/French final terminology | `[POLICY DECISION REQUIRED]` |

---

# 12. High-Fidelity Review Checklist

## 12.1 Architecture safety

- [ ] No new business logic introduced.
- [ ] No arbitrary state transitions added.
- [ ] Every CTA maps to approved backend authority.
- [ ] No hidden financial assumptions.
- [ ] No frontend-only financial calculations.

## 12.2 Financial accuracy

- [ ] Refund states visually distinct.
- [ ] Approved/provider-pending refunds are not shown as completed.
- [ ] Late payment after expiry does not show confirmed booking/session.
- [ ] Payout shows gross, exposure, deductions, net.
- [ ] Paid payout remains immutable.
- [ ] Recovery/adjustment appears separately.

## 12.3 Privacy and audit

- [ ] Student data minimized.
- [ ] Parent permission controls visible.
- [ ] Teacher sees only permitted context.
- [ ] Sensitive admin access shows “This access will be logged.”
- [ ] Raw provider payloads/documents hidden by default.

## 12.4 MVP scope

- [ ] No AI tutor.
- [ ] No AI matching.
- [ ] No session recording.
- [ ] No gamification.
- [ ] No subscriptions.
- [ ] No group classes.
- [ ] No institutional accounts.
- [ ] No public leaderboard.
- [ ] No paid ranking.
- [ ] No microservices.

## 12.5 Accessibility

- [ ] Text contrast is sufficient.
- [ ] Status not color-only.
- [ ] Touch targets adequate.
- [ ] RTL layouts considered.
- [ ] Form errors clear and accessible.

---

# 13. Deliverables Expected After This Document

This document can guide creation of visual mockups in a design tool.

Next design deliverables may include:

```text
High-fidelity screen mockups
Clickable prototype
High-fidelity UI audit
Design handoff specification
```

But the following remain prohibited until separate gates:

```text
Frontend implementation
Backend implementation
Production UI code
Architecture changes
Database changes
State-machine changes
MVP expansion
```

---

# 14. Final Status

```text
High-Fidelity UI Design v1.0 Status: READY FOR REVIEW
```

Next gate:

```text
High-Fidelity UI Audit
```

Do not proceed to frontend/backend implementation until implementation gates are explicitly approved.
