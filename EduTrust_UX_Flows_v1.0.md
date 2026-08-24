# EduTrust Algeria — UX Flows v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document:** UX Flows v1.0  
**Status:** UX specification only — no backend implementation  
**Architecture foundation:** LOCKED after DDL Audit FINAL PASS

Authoritative baseline:

1. EduTrust PRD v1.0
2. Database Schema v1.0
3. API Architecture v1.0
4. State Machines v1.0
5. Schema Patch v1.1
6. State Machines v1.1 Addendum
7. Schema Patch v1.2
8. DDL Hardening v1.3
9. `edutrust_schema_patch_v1_3.sql`

---

# 1. Executive Summary

This document translates the locked EduTrust architecture into user-facing UX flows for the MVP.

The UX must express the platform’s business logic without redefining it.

Core MVP loop:

```text
Parent
   ↓
Student Profile
   ↓
Search / Match
   ↓
Teacher Trust Profile
   ↓
Available Slot
   ↓
Booking Hold
   ↓
Payment Initiation
   ↓
Payment Confirmation
   ↓
Session Scheduled
   ↓
Session Started / Completed
   ↓
Session Report
   ↓
Student Passport v0
   ↓
Verified Review
   ↓
Repeat Booking
```

UX must keep the product simple for parents and teachers while respecting the underlying state machines.

---

# 2. UX Non-Negotiable Rules

## 2.1 UX does not define business logic

UX screens must never create or imply state transitions that do not exist in the architecture.

Forbidden examples:

```text
Parent directly marks booking as BOOKED
Parent directly marks session as COMPLETED
Teacher directly marks payment as CONFIRMED
Admin directly edits ledger entries
Review button appears before verified eligibility
Payout button appears before payout eligibility
Expired booking is revived after late payment
```

## 2.2 Server state is the source of truth

Frontend displays current state returned by the API.

The UI may show optimistic loading states, but final state always comes from backend responses.

## 2.3 State-based actions only

Every action button must be derived from:

```text
role
ownership
current booking status
current payment status
current session status
current dispute status
current refund status
current payout status
eligibility rules
```

## 2.4 Dispute is overlay

UX must show dispute as a banner/status overlay, not as a replacement for booking/session truth.

Correct:

```text
Session completed
Dispute open
Payout blocked
```

Incorrect:

```text
Session disputed instead of completed
```

## 2.5 Payment and fulfillment are separate

UX must distinguish:

```text
Payment received
```

from:

```text
Booking confirmed
```

especially for late payment after expiry.

## 2.6 No raw infrastructure language for users

Parents and teachers should not see terms like:

```text
webhook
ledger
idempotency key
provider event ID
row lock
```

Admin/OPS screens may expose technical details where needed.

---

# 3. MVP UX Scope

## 3.1 Included

- Parent onboarding
- Student profile creation
- Teacher search and matching
- Teacher Trust Profile
- Slot selection
- Booking hold
- Payment initiation and status handling
- Session lifecycle
- Structured session report
- Student Passport v0
- Verified review
- Cancellation
- No-show flows
- Disputes
- Refunds and partial refunds
- Late payment after expiry handling
- Teacher onboarding and verification
- Teacher availability
- Teacher booking/session/reporting
- Teacher earnings/payout visibility
- Admin verification, dispute, refund, audit views

## 3.2 Excluded

Do not include UX for:

- AI tutor
- AI matching
- AI report generation
- Session recording
- Gamification
- Subscriptions
- Group classes
- Advanced analytics
- Microservices
- Additional marketplace features
- Public teacher leaderboard
- Paid ranking

---

# 4. Global UX Components

## 4.1 Parent navigation

```text
Home
Children
Find Teacher
Bookings
Sessions
Reports
Progress
Payments
Reviews
Disputes & Safety
Notifications
Account
```

## 4.2 Teacher navigation

```text
Home
Profile
Verification
Subjects & Pricing
Availability
Bookings
Sessions
Reports
Reviews
Earnings
Payouts
Notifications
Settings
```

## 4.3 Admin navigation

```text
Dashboard
Users
Teacher Verification
Bookings
Payments
Refunds
Disputes
Reviews
Payouts
Event Ledger
Security Events
Settings
```

## 4.4 State badges

User-friendly labels:

| Backend state | Parent/teacher label |
|---|---|
| Booking `HELD` | Reserved temporarily |
| Booking `PAYMENT_PENDING` | Waiting for payment |
| Booking `BOOKED` | Confirmed |
| Booking `COMPLETED` | Completed |
| Booking `CANCELLED` | Cancelled |
| Booking `EXPIRED` | Reservation expired |
| Payment `INITIATED/PENDING` | Payment in progress |
| Payment `CONFIRMED` | Paid |
| Payment `FAILED` | Payment failed |
| Payment `REFUND_PENDING` | Refund in progress |
| Payment `PARTIALLY_REFUNDED` | Partially refunded |
| Payment `REFUNDED` | Refunded |
| Session `SCHEDULED` | Scheduled |
| Session `STARTED` | In progress |
| Session `COMPLETED` | Completed |
| Session `NO_SHOW_STUDENT` | Student absent |
| Session `NO_SHOW_TEACHER` | Teacher absent |
| Dispute `OPEN` | Dispute opened |
| Dispute `UNDER_REVIEW` | Under review |
| Dispute `RESOLVED` | Resolved |
| Refund `REQUESTED` | Refund requested |
| Refund `APPROVED` | Refund approved |
| Refund `PROVIDER_PENDING` | Refund processing |
| Refund `SUCCEEDED` | Refund completed |
| Refund `FAILED` | Refund failed |
| Payout `ELIGIBLE` | Eligible for payout |
| Payout `PROCESSING` | Payout processing |
| Payout `PAID` | Paid out |
| Payout `FAILED` | Payout failed |

---

# 5. Global Edge-Case UX Rules

## 5.1 Duplicate taps

For idempotent actions:

```text
Hold booking
Initiate payment
Request refund
Process payout
Create review, recommended
```

UX behavior:

- Disable button after first tap.
- Show loading state.
- If user taps again, do not create a second client request unless retry is explicit.
- If network retry occurs, send same idempotency key.
- If backend returns existing response, show same result.

## 5.2 Network timeout

UX behavior:

- Do not assume failure.
- Show: “We are checking the latest status.”
- Re-fetch resource status.
- For payment or booking hold, use idempotency replay or status polling.

## 5.3 Payment callback delay

UX behavior:

- Show payment pending screen.
- Explain: “Payment confirmation may take a few moments.”
- Poll `GET /payments/:id` or `GET /bookings/:id` with backoff.
- Do not show booking confirmed until backend says `BOOKED` and session exists.

## 5.4 Webhook delay

UX behavior:

- Payment provider callback page may say: “Payment submitted. Waiting for confirmation.”
- Backend webhook is authoritative.
- Do not mark session scheduled until webhook transaction succeeds.

## 5.5 Expired booking hold

UX behavior:

- If hold expires before payment initiation: show “Reservation expired.”
- Next action: choose another slot.
- Do not allow payment initiation for expired booking.

## 5.6 Late payment after expiry

UX behavior:

- Show payment received but booking not confirmed.
- Explain clearly that the slot expired before payment confirmation.
- Show refund/reconciliation status.
- Do not show session scheduled.
- Do not show teacher payable.

## 5.7 Dispute open

UX behavior:

- Show dispute banner on booking/session/payment.
- Keep factual state visible.
- Disable payout processing for affected session.
- Allow participant to view dispute status.

## 5.8 Refund pending

UX behavior:

- Show refund lifecycle state.
- Do not say “refunded” until refund succeeds.

## 5.9 Partial refund

UX behavior:

- Parent sees amount refunded and remaining paid amount.
- Teacher sees adjusted earning if payout not yet paid.
- If payout already paid, teacher/admin sees recovery/adjustment entry, not edited old payout.

---

# 6. Flow Template

Each flow below uses this structure:

```text
Actor
Entry point
Preconditions
UI state
User action
API call
Backend state transition
Success state
Failure state
Loading state
Empty state
Permission failure
Idempotency behavior
Notification
Audit/event generated
Next allowed action
```

---

# 7. Parent UX Flows

---

## Flow 1 — Parent Onboarding

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Landing page, mobile web app, invitation link |
| Preconditions | User is not authenticated |
| UI state | Registration form with full name, phone/email, password or passwordless method, preferred language |
| User action | Parent submits registration |
| API call | `POST /auth/register` with role `PARENT` |
| Backend state transition | User created; role `PARENT`; parent profile created |
| Success state | Parent is logged in and directed to create first student profile |
| Failure state | Duplicate phone/email, invalid input, weak password, rate limit |
| Loading state | Disable submit; show “Creating your account…” |
| Empty state | Not applicable |
| Permission failure | Public endpoint; if already logged in, redirect dashboard |
| Idempotency behavior | Not required, but duplicate submit should be frontend-disabled |
| Notification | Optional welcome notification |
| Audit/event generated | `USER_REGISTERED` |
| Next allowed action | Create student profile |

UX copy:

```text
Welcome to EduTrust. Create a parent account to find verified teachers and track your child’s sessions.
```

---

## Flow 2 — Student Creation

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Post-registration prompt, Children tab, booking prerequisite |
| Preconditions | Authenticated parent |
| UI state | Student profile form with minimized data |
| User action | Parent enters display name, academic level, birth year optional, goal, preferred mode |
| API call | `POST /students` |
| Backend state transition | `student_profiles` row created |
| Success state | Student appears in Children list and can be used for matching |
| Failure state | Validation error, inactive academic level, missing consent |
| Loading state | “Saving student profile…” |
| Empty state | Children tab shows “Add your first child/student profile.” |
| Permission failure | Teacher/admin cannot create normal parent student profile unless admin override |
| Idempotency behavior | Recommended for duplicate form submissions, but not critical |
| Notification | None by default |
| Audit/event generated | `STUDENT_PROFILE_CREATED` |
| Next allowed action | Search/match teachers |

Privacy UX rule:

```text
Ask only for information needed to match and track sessions. Avoid full legal identity unless required later.
```

---

## Flow 3 — Parent Search

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Find Teacher tab, student profile action “Find teacher” |
| Preconditions | Parent has at least one active student profile |
| UI state | Search form with subject, level, mode, budget, availability, language, location if in-person |
| User action | Parent submits search filters |
| API call | `GET /teachers/search` or `POST /teachers/match` for recommendation-style results |
| Backend state transition | None; read-only |
| Success state | Teacher list displayed with trust summaries and available slots |
| Failure state | Invalid filters, network error |
| Loading state | Skeleton teacher cards |
| Empty state | “No teachers match these filters. Try widening budget, time, or mode.” |
| Permission failure | If unauthenticated public search is allowed, hide sensitive data; booking requires login |
| Idempotency behavior | Not required |
| Notification | None |
| Audit/event generated | Optional analytics event, not critical Event Ledger |
| Next allowed action | View teacher profile or run match |

UX rule:

```text
Search should not show teachers as bookable if no active slot exists.
```

---

## Flow 4 — Rule-Based Teacher Matching

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | “Find best match” from student profile or search page |
| Preconditions | Parent owns student profile; subject and level selected |
| UI state | Guided matching form |
| User action | Parent submits matching request |
| API call | `POST /teachers/match` |
| Backend state transition | None; read-only rule-based ranking |
| Success state | Matched teachers shown with recommendation reasons |
| Failure state | Invalid student ownership, invalid filters, no results |
| Loading state | “Finding suitable teachers…” |
| Empty state | “No strong match found. Try different availability or budget.” |
| Permission failure | `STUDENT_ACCESS_DENIED` if student not owned |
| Idempotency behavior | Not required |
| Notification | None |
| Audit/event generated | Optional analytics event only |
| Next allowed action | Open Trust Profile or choose slot |

Hard filters displayed in UX:

```text
Subject
Academic level
Mode
Availability
Budget fit
Verification/listing status
```

Soft ranking displayed as reasons:

```text
✓ Teaches 2AS Mathematics
✓ Available Saturday afternoon
✓ Within your budget
✓ 97% attendance
✓ 238 verified sessions
```

No AI. No unexplained primary ranking score.

---

## Flow 5 — Teacher Trust Profile

| Field | Specification |
|---|---|
| Actor | Parent, public visitor with reduced view |
| Entry point | Teacher search card, match result, booking flow |
| Preconditions | Teacher profile is listed or visible by permission |
| UI state | Profile with subjects, levels, price, availability, Trust Profile, reviews |
| User action | Parent reviews trust signals and selects a slot |
| API call | `GET /teachers/:id`, `GET /teachers/:id/trust-profile`, `GET /teachers/:id/reviews` |
| Backend state transition | None; read-only |
| Success state | Parent understands why teacher is trustworthy and can book |
| Failure state | Teacher unavailable, profile suspended, not found |
| Loading state | Profile skeleton |
| Empty state | If no reviews: “No verified reviews yet.” Show completed sessions if available |
| Permission failure | Sensitive teacher/admin data hidden |
| Idempotency behavior | Not required |
| Notification | None |
| Audit/event generated | None critical |
| Next allowed action | Select available slot |

Trust display:

```text
Identity: Verified
Qualifications: Verified
Verified sessions: 238
Parent rating: 4.8 from 91 verified reviews
Attendance: 97%
Cancellation: 2%
Average response: < 10 min
```

UX rule:

```text
Do not expose an unexplained internal trust score as the main signal.
```

---

## Flow 6 — Availability / Slot Selection

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Teacher profile or match result |
| Preconditions | Teacher has active available slots |
| UI state | Calendar/slot picker in local time |
| User action | Parent selects slot |
| API call | `GET /availability/search`, then `POST /bookings/hold` |
| Backend state transition | Slot `AVAILABLE` → booking `HELD`; slot becomes `HELD` |
| Success state | Temporary reservation with countdown |
| Failure state | Slot no longer available, overlap conflict, teacher paused |
| Loading state | Disable selected slot; show “Reserving…” |
| Empty state | “No available slots. Try another teacher or date.” |
| Permission failure | Unauthenticated user asked to log in before hold |
| Idempotency behavior | `POST /bookings/hold` requires idempotency key |
| Notification | Optional hold confirmation in-app |
| Audit/event generated | `BOOKING_CREATED`, `BOOKING_HELD` |
| Next allowed action | Initiate payment before hold expires |

UX rule:

```text
Show countdown clearly: “Reserved for 10 minutes.” Final value depends on product policy.
```

---

## Flow 7 — Booking Hold

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Slot selection confirmation |
| Preconditions | Parent owns student; slot available; teacher offering valid |
| UI state | Booking summary: student, teacher, subject, time, price, hold countdown |
| User action | Parent confirms temporary hold or proceeds directly to payment |
| API call | `POST /bookings/hold` |
| Backend state transition | Booking created as `HELD`; slot set `HELD` |
| Success state | Booking summary with “Proceed to payment” |
| Failure state | `BOOKING_SLOT_UNAVAILABLE`, validation error, expired slot |
| Loading state | “Reserving your session…” |
| Empty state | Not applicable |
| Permission failure | Parent does not own student → access denied |
| Idempotency behavior | Required; duplicate taps replay same hold if same request |
| Notification | None or in-app reservation confirmation |
| Audit/event generated | `BOOKING_CREATED`, `BOOKING_HELD` |
| Next allowed action | Payment initiation, cancel hold, or wait until expiry |

Duplicate tap behavior:

```text
Second tap must not create second booking. Show existing held booking.
```

---

## Flow 8 — Payment Initiation

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Held booking payment screen |
| Preconditions | Booking `HELD`; hold not expired; parent owns booking |
| UI state | Payment method selection and total amount |
| User action | Parent taps “Pay securely” |
| API call | `POST /payments/initiate` or `POST /bookings/:id/payment` |
| Backend state transition | Booking `HELD` → `PAYMENT_PENDING`; payment `INITIATED/PENDING` |
| Success state | Redirect to provider checkout or show payment instructions |
| Failure state | Hold expired, provider unavailable, invalid state |
| Loading state | “Starting payment…” |
| Empty state | No payment methods available → show support message |
| Permission failure | Parent does not own booking |
| Idempotency behavior | Required; duplicate tap returns same payment attempt/checkout state |
| Notification | Optional payment pending notification |
| Audit/event generated | `PAYMENT_INITIATED` |
| Next allowed action | Complete payment with provider or return to booking status page |

UX rule:

```text
Never open multiple checkout sessions for repeated taps with same idempotency key.
```

---

## Flow 9 — Payment Pending / Success / Failure

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Return from payment provider, payment status page, booking details |
| Preconditions | Payment exists |
| UI state | Payment status card |
| User action | Wait, refresh, retry failed payment, or choose new slot if expired |
| API call | `GET /payments/:id`, `GET /bookings/:id` |
| Backend state transition | Read-only from UI; provider webhook changes payment/booking/session |
| Success state | Payment confirmed; booking confirmed; session scheduled |
| Failure state | Payment failed; booking may remain pending until timeout or expire |
| Loading state | “Waiting for payment confirmation…” |
| Empty state | No payment found for booking |
| Permission failure | Parent can view only own payments |
| Idempotency behavior | Not applicable for polling; retry initiation uses idempotency |
| Notification | Payment confirmed/failed notification |
| Audit/event generated | Webhook generates payment events, not UI polling |
| Next allowed action | View session if booked; retry payment if allowed; choose new slot if expired |

UX labels:

```text
Payment submitted. Confirmation may take a few moments.
Do not close? You may safely return later; we will update your booking automatically.
```

---

## Flow 10 — Payment Webhook Confirmation UX

This is a backend-driven transition, but UX must represent it correctly.

| Field | Specification |
|---|---|
| Actor | System/payment provider; parent observes result |
| Entry point | Provider webhook received; parent status page polling |
| Preconditions | Payment exists; booking `PAYMENT_PENDING`; provider event valid |
| UI state | Parent sees pending until backend confirms |
| User action | None; parent may refresh status |
| API call | Backend: `POST /payments/webhooks/:provider`; UI: `GET /bookings/:id` |
| Backend state transition | Fulfillable: payment `CONFIRMED`, booking `BOOKED`, session `SCHEDULED`, ledger/event created |
| Success state | Booking confirmed screen with session details |
| Failure state | Payment failed or reconciliation required |
| Loading state | “Confirming payment…” |
| Empty state | Not applicable |
| Permission failure | Webhook endpoint provider-only; parent cannot call it |
| Idempotency behavior | Provider event identity prevents duplicate processing |
| Notification | Payment confirmed, booking confirmed |
| Audit/event generated | `PAYMENT_CONFIRMED`, `BOOKING_CONFIRMED` |
| Next allowed action | View session, add reminder, contact support if issue |

UX rule:

```text
Do not show confirmed booking until session row exists and booking is BOOKED.
```

---

## Flow 11 — Session Lifecycle

| Field | Specification |
|---|---|
| Actor | Parent observes; teacher acts |
| Entry point | Upcoming sessions tab, booking details |
| Preconditions | Booking `BOOKED`; session `SCHEDULED` |
| UI state | Session card with date/time, teacher, student, status |
| User action | Parent views details; teacher starts/completes session |
| API call | Parent: `GET /sessions/:id`; teacher: `POST /sessions/:id/start`, `POST /sessions/:id/complete` |
| Backend state transition | `SCHEDULED` → `STARTED` → `COMPLETED`; booking `BOOKED` → `COMPLETED` after session completion |
| Success state | Session completed; report pending/available |
| Failure state | No-show, cancellation, dispute |
| Loading state | Status refresh spinner |
| Empty state | “No upcoming sessions.” |
| Permission failure | Parent can view own child sessions only |
| Idempotency behavior | Start/complete recommended idempotent behavior |
| Notification | Session started, session completed |
| Audit/event generated | `SESSION_STARTED`, `SESSION_COMPLETED` |
| Next allowed action | Teacher creates report; parent views report/review when eligible |

---

## Flow 12 — Session Attendance

| Field | Specification |
|---|---|
| Actor | Teacher primarily; parent may report teacher no-show |
| Entry point | Session details near scheduled time |
| Preconditions | Session `SCHEDULED` or `STARTED` |
| UI state | Attendance controls for teacher; report issue/no-show for parent |
| User action | Teacher marks student present/no-show; parent reports teacher absent |
| API call | `POST /sessions/:id/no-show` or dispute flow for teacher no-show |
| Backend state transition | `SCHEDULED` → `NO_SHOW_STUDENT` by teacher under rules; teacher no-show usually opens dispute/OPS review before factual marking |
| Success state | Attendance status recorded or dispute opened |
| Failure state | Too early, unauthorized actor, already completed/cancelled |
| Loading state | “Recording attendance…” |
| Empty state | Not applicable |
| Permission failure | Parent cannot directly mark final teacher no-show without review |
| Idempotency behavior | Recommended |
| Notification | No-show notification to affected party |
| Audit/event generated | `SESSION_NO_SHOW`, possibly `DISPUTE_OPENED` |
| Next allowed action | Dispute, refund review, payout blocked depending case |

UX rule:

```text
Teacher no-show reported by parent is a claim requiring review, not immediate final teacher metric.
```

---

## Flow 13 — Session Report

| Field | Specification |
|---|---|
| Actor | Teacher creates; parent reads |
| Entry point | Teacher completed session screen; parent report notification |
| Preconditions | Session `COMPLETED`; assigned teacher |
| UI state | Structured report form under 2 minutes |
| User action | Teacher fills topics, skills, participation, observations, homework, revision, next objectives, progress indicator |
| API call | `POST /sessions/:id/report`, `GET /sessions/:id/report` |
| Backend state transition | Report created; student progress events created |
| Success state | Parent can view report; Student Passport updated |
| Failure state | Session not completed, teacher not assigned, duplicate report |
| Loading state | “Saving report…” |
| Empty state | Parent sees “Report not available yet.” |
| Permission failure | Only assigned teacher can create report; parent can read own child report |
| Idempotency behavior | Recommended for duplicate submit |
| Notification | Report available notification to parent |
| Audit/event generated | `REPORT_CREATED` |
| Next allowed action | Parent reviews report; parent may review teacher if eligible |

No AI in MVP.

---

## Flow 14 — Student Passport v0

| Field | Specification |
|---|---|
| Actor | Parent; teacher only with permission/session context |
| Entry point | Student profile → Progress / Passport |
| Preconditions | Parent owns student; progress events may or may not exist |
| UI state | Structured progress summary by subject |
| User action | Parent views sessions, topics, homework, observations, progress notes |
| API call | `GET /students/:id/passport` |
| Backend state transition | None; read aggregation from structured data |
| Success state | Parent sees learning continuity view |
| Failure state | Data unavailable, permission denied |
| Loading state | Passport skeleton |
| Empty state | “No completed sessions yet. Progress will appear after session reports.” |
| Permission failure | Teacher requires parent permission/relevant session context |
| Idempotency behavior | Not applicable |
| Notification | None |
| Audit/event generated | None critical; sensitive access may be logged for teacher/admin |
| Next allowed action | Book follow-up, share limited context, view reports |

UX rule:

```text
Do not present AI-generated mastery estimates in MVP. Use structured report data only.
```

---

## Flow 15 — Verified Review

| Field | Specification |
|---|---|
| Actor | Parent |
| Entry point | Completed session page, report page, review request notification |
| Preconditions | Booking `COMPLETED`; payment `CONFIRMED`; session `COMPLETED`; no existing review; parent owns student; reviewer is not teacher |
| UI state | Rating + comment form |
| User action | Parent submits review |
| API call | `POST /sessions/:id/review` |
| Backend state transition | Review row created as `VISIBLE` |
| Success state | Review visible on teacher profile after moderation rules |
| Failure state | Duplicate review, not eligible, dispute/refund policy restriction |
| Loading state | “Submitting review…” |
| Empty state | If not eligible: show reason, not empty form |
| Permission failure | `STUDENT_ACCESS_DENIED` or `REVIEW_NOT_ELIGIBLE` |
| Idempotency behavior | Recommended; DB unique prevents duplicate review |
| Notification | Teacher may be notified of new verified review |
| Audit/event generated | `REVIEW_CREATED` |
| Next allowed action | Repeat booking |

UX rule:

```text
Do not display review form until backend says eligible.
```

---

## Flow 16 — Cancellation

| Field | Specification |
|---|---|
| Actor | Parent or teacher under policy; OPS/Admin override |
| Entry point | Booking details → Cancel action |
| Preconditions | Booking not completed; cancellation policy allows actor/timing |
| UI state | Cancellation confirmation with refund/policy explanation |
| User action | Actor submits cancellation reason |
| API call | `POST /bookings/:id/cancel` |
| Backend state transition | Eligible booking → `CANCELLED`; if paid, refund/dispute workflow may start |
| Success state | Booking cancelled; slot released if applicable; refund status shown if paid |
| Failure state | Too late, already completed, open dispute, permission denied |
| Loading state | “Cancelling booking…” |
| Empty state | Not applicable |
| Permission failure | Actor not booking owner/assigned teacher/admin |
| Idempotency behavior | Recommended |
| Notification | Booking cancelled to parent/teacher |
| Audit/event generated | `BOOKING_CANCELLED`; admin override emits `ADMIN_ACTION` |
| Next allowed action | Choose new slot, request refund if eligible, open dispute |

UX rule:

```text
Cancellation screen must show payment/refund impact before final confirmation.
```

---

## Flow 17 — No-Show

| Field | Specification |
|---|---|
| Actor | Teacher for student no-show; parent reports teacher no-show; OPS/Admin confirms contested cases |
| Entry point | Session details after grace period |
| Preconditions | Session scheduled and not completed/cancelled |
| UI state | No-show action with explanation and evidence prompt if needed |
| User action | Teacher marks student absent or parent reports teacher absent |
| API call | `POST /sessions/:id/no-show`, `POST /disputes` for teacher no-show claim |
| Backend state transition | Student no-show may set `NO_SHOW_STUDENT`; teacher no-show usually dispute overlay first, then OPS confirms `NO_SHOW_TEACHER` |
| Success state | No-show recorded or dispute opened |
| Failure state | Too early, unauthorized, already completed |
| Loading state | “Submitting no-show report…” |
| Empty state | Not applicable |
| Permission failure | Parent cannot directly finalize teacher no-show metric |
| Idempotency behavior | Recommended |
| Notification | No-show/dispute notification |
| Audit/event generated | `SESSION_NO_SHOW` and/or `DISPUTE_OPENED` |
| Next allowed action | Refund/dispute resolution; payout blocked if dispute open |

---

## Flow 18 — Dispute Creation

| Field | Specification |
|---|---|
| Actor | Parent or teacher participant |
| Entry point | Booking/session/payment/report page → “Report a problem” |
| Preconditions | Actor participates in related booking/session/payment |
| UI state | Dispute category form with description and optional evidence |
| User action | Actor selects category and submits |
| API call | `POST /disputes` |
| Backend state transition | Dispute `OPEN`; booking/session factual state unchanged; payout blocked |
| Success state | Dispute status page created |
| Failure state | Unauthorized, missing target, duplicate active dispute depending policy |
| Loading state | “Opening dispute…” |
| Empty state | Disputes tab: “No disputes.” |
| Permission failure | Actor not participant |
| Idempotency behavior | Recommended |
| Notification | Dispute opened to relevant parties/admin |
| Audit/event generated | `DISPUTE_OPENED` |
| Next allowed action | Track dispute, provide evidence, wait for admin review |

Safety UX:

```text
Safety category should be visually prioritized and reassure parent that it is reviewed urgently.
```

---

## Flow 19 — Dispute Resolution

| Field | Specification |
|---|---|
| Actor | OPS/Admin resolves; parent/teacher observes |
| Entry point | Admin dispute queue; user dispute status page |
| Preconditions | Dispute `OPEN` or `UNDER_REVIEW` |
| UI state | Admin resolution panel; user read-only status timeline |
| User action | Admin selects resolution: no action, warning, refund, partial refund, account action, report correction |
| API call | `POST /admin/disputes/:id/resolve` |
| Backend state transition | Dispute → `RESOLVED`/`REJECTED`; refund flow may start; payout may release/block |
| Success state | User sees resolution and next financial/session status |
| Failure state | Insufficient permission, invalid refund amount, already resolved |
| Loading state | “Resolving dispute…” |
| Empty state | Admin queue empty |
| Permission failure | SUPPORT cannot resolve high-risk financial/safety disputes |
| Idempotency behavior | Required if refund action involved; recommended otherwise |
| Notification | Dispute resolution notification |
| Audit/event generated | `DISPUTE_RESOLVED`, `ADMIN_ACTION`, possibly refund events |
| Next allowed action | Refund tracking, payout recalculation, account action, close dispute |

UX rule:

```text
Resolution does not overwrite factual booking/session state.
```

---

## Flow 20 — Refund Request

| Field | Specification |
|---|---|
| Actor | Parent/teacher via dispute; OPS/Admin directly under policy |
| Entry point | Dispute flow, payment page, admin refund panel |
| Preconditions | Payment confirmed/refundable; actor authorized; reason exists |
| UI state | Refund request summary with amount, reason, status timeline |
| User action | Submit refund request or admin creates refund workflow |
| API call | `POST /disputes` or `POST /payments/:id/refund` depending authority |
| Backend state transition | Refund `REQUESTED` or `APPROVED` depending role/policy |
| Success state | Refund timeline visible |
| Failure state | Payment not refundable, amount invalid, already fully refunded |
| Loading state | “Submitting refund request…” |
| Empty state | “No refund requests.” |
| Permission failure | Parent cannot approve own refund; admin/OPS required |
| Idempotency behavior | Required for refund command |
| Notification | Refund requested/approved depending state |
| Audit/event generated | `REFUND_REQUESTED` or `REFUND_APPROVED` |
| Next allowed action | Admin review or provider submission |

UX copy rule:

```text
Do not say “refunded” until refund status is SUCCEEDED.
```

---

## Flow 21 — Partial Refund

| Field | Specification |
|---|---|
| Actor | OPS/Admin approves; parent/teacher observe |
| Entry point | Dispute resolution/refund admin panel |
| Preconditions | Payment confirmed; partial amount < payment amount; allocation defined |
| UI state | Admin partial refund form with teacher/platform adjustment allocation |
| User action | Admin approves partial refund and submits provider refund |
| API call | `POST /payments/:id/refund` and provider refund processing |
| Backend state transition | Refund `APPROVED` → `PROVIDER_PENDING` → `SUCCEEDED`; payment → `PARTIALLY_REFUNDED` after success |
| Success state | Parent sees partial refund completed; teacher payout adjusted if not paid |
| Failure state | Over-refund, allocation mismatch, provider failure |
| Loading state | “Processing partial refund…” |
| Empty state | Not applicable |
| Permission failure | SUPPORT cannot approve financial refund unless policy allows |
| Idempotency behavior | Required |
| Notification | Refund approved, refund processing, refund completed/failed |
| Audit/event generated | `REFUND_APPROVED`, `REFUND_PROVIDER_SUBMITTED`, `REFUND_SUCCEEDED`, `PAYMENT_PARTIALLY_REFUNDED` |
| Next allowed action | Recalculate payout, close dispute, show refund receipt/history |

UX rule:

```text
Teacher earnings screen must show adjusted net amount before payout if payout not yet paid.
```

---

## Flow 22 — Late Payment After Booking Expiry

| Field | Specification |
|---|---|
| Actor | Parent observes; provider/system triggers; OPS may reconcile |
| Entry point | Payment status page after delayed provider success |
| Preconditions | Booking `EXPIRED` or `CANCELLED`; provider later confirms payment |
| UI state | Reconciliation/refund status screen |
| User action | Parent views status or contacts support |
| API call | Backend webhook; UI polls `GET /payments/:id`, `GET /bookings/:id`, refund status |
| Backend state transition | Payment `CONFIRMED`; booking remains `EXPIRED/CANCELLED`; no session; refund/reconciliation created |
| Success state | Parent sees payment received but booking not confirmed; refund processing |
| Failure state | Provider confirmation conflict, refund provider failure |
| Loading state | “Checking payment and refund status…” |
| Empty state | Not applicable |
| Permission failure | Parent can view only own payment/refund |
| Idempotency behavior | Provider event idempotency; refund idempotency |
| Notification | Payment reconciliation required; refund started/completed |
| Audit/event generated | `PAYMENT_CONFIRMED`, `PAYMENT_RECONCILIATION_REQUIRED`, refund events |
| Next allowed action | Choose new slot, track refund |

User-facing copy:

```text
Your payment was received after the reservation expired, so the session was not confirmed. We have started a refund/reconciliation process.
```

Forbidden UX:

```text
Do not show “Session scheduled.”
Do not show “Teacher paid.”
Do not reassign the old slot.
```

---

## Flow 23 — Payout Visibility

| Field | Specification |
|---|---|
| Actor | Teacher; Admin/OPS for monitoring |
| Entry point | Teacher Earnings/Payouts tab |
| Preconditions | Teacher authenticated; sessions may exist |
| UI state | Earnings summary with pending, eligible, processing, paid, adjusted amounts |
| User action | Teacher views payout breakdown |
| API call | `GET /teacher/payouts`, `GET /teacher/payouts/:id` |
| Backend state transition | Read-only for teacher |
| Success state | Teacher sees payout status and blocked/adjusted reasons |
| Failure state | Payout not found, permission denied |
| Loading state | Earnings skeleton |
| Empty state | “No completed payable sessions yet.” |
| Permission failure | Teacher can view only own payouts |
| Idempotency behavior | Not applicable |
| Notification | Payout eligible/processing/paid/failed notifications |
| Audit/event generated | None for read; admin payout processing generates events |
| Next allowed action | Teacher waits, views session/report requirements, resolves disputes if needed |

If payout blocked:

```text
Reason: report missing / dispute open / refund pending / waiting period not passed.
```

If payout paid:

```text
Show immutable payout record. Later refunds appear as separate adjustments, not edited payout.
```

---

# 8. Teacher UX Flows

---

## Flow 24 — Teacher Onboarding

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Teacher registration page |
| Preconditions | User not authenticated or has teacher role |
| UI state | Account creation and profile setup wizard |
| User action | Teacher registers and starts profile creation |
| API call | `POST /auth/register`, `POST /teachers/me` |
| Backend state transition | User + teacher role created; teacher profile `DRAFT` |
| Success state | Teacher dashboard prompts verification and subject setup |
| Failure state | Duplicate account, invalid data |
| Loading state | “Creating teacher account…” |
| Empty state | Not applicable |
| Permission failure | Parent role cannot create teacher profile unless also assigned teacher role |
| Idempotency behavior | Duplicate submits frontend-disabled |
| Notification | Welcome/onboarding prompt |
| Audit/event generated | `USER_REGISTERED`, `TEACHER_PROFILE_CREATED` |
| Next allowed action | Submit verification, add subjects/pricing, add availability |

---

## Flow 25 — Teacher Verification

| Field | Specification |
|---|---|
| Actor | Teacher submits; Admin/OPS reviews |
| Entry point | Teacher Verification tab |
| Preconditions | Teacher profile exists |
| UI state | Verification checklist: identity, qualifications |
| User action | Teacher uploads documents/metadata and submits |
| API call | `POST /teachers/verifications`, secure upload endpoint if implemented |
| Backend state transition | Verification row `SUBMITTED`; document metadata stored |
| Success state | Verification status “Under review” |
| Failure state | Upload failed, invalid document type, file too large |
| Loading state | “Uploading securely…” |
| Empty state | “No verification submitted yet.” |
| Permission failure | Teacher can submit only own verification |
| Idempotency behavior | Recommended for submit; upload flow must prevent duplicates |
| Notification | Submission received; later approved/rejected |
| Audit/event generated | `TEACHER_VERIFICATION_SUBMITTED`; admin later `TEACHER_VERIFIED`/`TEACHER_REJECTED` |
| Next allowed action | Wait for review; complete profile |

UX rule:

```text
Verification documents are not publicly visible.
```

---

## Flow 26 — Teacher Availability Management

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Teacher Availability tab |
| Preconditions | Teacher profile exists; subject offering preferred before listing |
| UI state | Calendar with recurring rules and concrete slots |
| User action | Teacher creates/updates rules, blocks/unblocks slots |
| API call | `POST/PATCH /teachers/availability/rules`, `POST /teachers/availability/slots`, block/unblock endpoints |
| Backend state transition | Availability slots created/updated/blocked; no overlap allowed |
| Success state | Slots appear as available/booked/blocked |
| Failure state | Overlap, invalid time, booked slot cannot be removed silently |
| Loading state | “Saving availability…” |
| Empty state | “Add availability so parents can book you.” |
| Permission failure | Teacher can manage only own availability |
| Idempotency behavior | Recommended for slot creation |
| Notification | None by default |
| Audit/event generated | `SLOT_CREATED`, `SLOT_UPDATED`, `SLOT_BLOCKED` |
| Next allowed action | Receive bookings |

Timezone UX:

```text
Display local time. Persist UTC. Show timezone on settings/calendar.
```

Changing rules with future bookings:

```text
Booked sessions remain unchanged. Only available future slots can be changed.
```

---

## Flow 27 — Teacher Booking Management

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Teacher Bookings tab |
| Preconditions | Teacher has bookings or availability |
| UI state | Booking list grouped by upcoming, pending, completed, cancelled |
| User action | Teacher views booking, cancels under policy, prepares session |
| API call | `GET /bookings`, `GET /bookings/:id`, `POST /bookings/:id/cancel` |
| Backend state transition | Read-only except cancellation under policy |
| Success state | Teacher sees student/session context allowed by permission |
| Failure state | Booking not found, cancellation not allowed |
| Loading state | Booking list skeleton |
| Empty state | “No bookings yet.” |
| Permission failure | Teacher can view only own bookings |
| Idempotency behavior | Cancellation recommended idempotent |
| Notification | New booking, cancellation notification |
| Audit/event generated | Cancellation emits `BOOKING_CANCELLED`; admin override emits `ADMIN_ACTION` |
| Next allowed action | Start scheduled session, create report after completion |

---

## Flow 28 — Teacher Session Reporting

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Completed session page; teacher dashboard task list |
| Preconditions | Session `COMPLETED`; report not yet created |
| UI state | Fast structured report form |
| User action | Teacher submits report |
| API call | `POST /sessions/:id/report` |
| Backend state transition | Report created; student progress events created |
| Success state | Report available to parent; payout eligibility can later be evaluated |
| Failure state | Session not completed, duplicate report, permission denied |
| Loading state | “Saving report…” |
| Empty state | Task list: “No reports due.” |
| Permission failure | Teacher not assigned to session |
| Idempotency behavior | Recommended |
| Notification | Parent: report available |
| Audit/event generated | `REPORT_CREATED` |
| Next allowed action | Teacher views earnings eligibility; parent reviews report |

---

## Flow 29 — Teacher Earnings/Payout View

| Field | Specification |
|---|---|
| Actor | Teacher |
| Entry point | Earnings tab |
| Preconditions | Teacher authenticated |
| UI state | Earnings dashboard with completed sessions, pending reports, blocked payouts, paid payouts |
| User action | Teacher views payout details |
| API call | `GET /teacher/payouts`, `GET /teacher/payouts/:id` |
| Backend state transition | None for teacher |
| Success state | Teacher sees clear explanation of payable amount |
| Failure state | Permission denied, data unavailable |
| Loading state | Earnings skeleton |
| Empty state | “No earnings yet. Completed reported sessions will appear here.” |
| Permission failure | Teacher cannot access another teacher’s payouts |
| Idempotency behavior | Not applicable |
| Notification | Payout eligible/processed/failed |
| Audit/event generated | None for read |
| Next allowed action | Complete reports, monitor disputes/refunds, wait for payout |

Display rules:

```text
Gross session amount
Platform commission
Refund adjustment, if any
Net teacher payable
Payout status
Blocked reason, if any
```

Do not edit paid payout after later refund; show separate adjustment/recovery.

---

# 9. Admin UX Flows

---

## Flow 30 — Admin Verification

| Field | Specification |
|---|---|
| Actor | Admin/authorized OPS |
| Entry point | Admin → Teacher Verification queue |
| Preconditions | Verification records submitted |
| UI state | Review queue with teacher profile, submitted metadata, secure document access |
| User action | Admin approves/rejects verification with reason |
| API call | `POST /admin/teachers/:id/verify`, `POST /admin/teachers/:id/reject` |
| Backend state transition | Verification status updated; teacher verification status/listing may update |
| Success state | Teacher sees verified/rejected status |
| Failure state | Missing reason, insufficient permission, document unavailable |
| Loading state | “Saving verification decision…” |
| Empty state | “No pending verifications.” |
| Permission failure | SUPPORT cannot approve unless explicitly allowed |
| Idempotency behavior | Recommended |
| Notification | Teacher verification approved/rejected |
| Audit/event generated | `TEACHER_VERIFIED`/`TEACHER_REJECTED`, `ADMIN_ACTION`, document access security event |
| Next allowed action | Teacher can be listed if all listing requirements met |

---

## Flow 31 — Admin Dispute Handling

| Field | Specification |
|---|---|
| Actor | OPS/Admin |
| Entry point | Admin → Disputes queue |
| Preconditions | Dispute exists |
| UI state | Dispute detail with booking/session/payment/report/event context |
| User action | Assign, review evidence, request more info, resolve |
| API call | `GET /admin/disputes`, `POST /admin/disputes/:id/resolve` |
| Backend state transition | Dispute `OPEN` → `UNDER_REVIEW` → `RESOLVED/REJECTED/CANCELLED` |
| Success state | Dispute resolved; related refund/payout/account actions created if needed |
| Failure state | Invalid resolution, refund amount invalid, insufficient authority |
| Loading state | “Loading dispute context…” / “Resolving…” |
| Empty state | “No open disputes.” |
| Permission failure | SUPPORT limited; ADMIN required for safety/high-risk financial actions |
| Idempotency behavior | Required for resolution that triggers refund; recommended otherwise |
| Notification | Parties notified of updates/resolution |
| Audit/event generated | `DISPUTE_RESOLVED`, `ADMIN_ACTION`, possible refund events |
| Next allowed action | Refund handling, payout release/block, account action |

UX rule:

```text
Show factual state and dispute overlay separately.
```

---

## Flow 32 — Admin Refund Handling

| Field | Specification |
|---|---|
| Actor | OPS/Admin |
| Entry point | Admin → Refunds, dispute resolution, payment detail |
| Preconditions | Refund request or admin refund decision exists |
| UI state | Refund form/timeline with requested, approved, provider pending, succeeded, failed |
| User action | Approve/reject refund, submit to provider, reconcile provider result |
| API call | `POST /payments/:id/refund`, refund reconciliation endpoint if implemented |
| Backend state transition | Refund lifecycle: `REQUESTED` → `APPROVED` → `PROVIDER_PENDING` → `SUCCEEDED/FAILED`; payment updates after success |
| Success state | Parent sees refund completed; teacher payout adjusted/recovery created if needed |
| Failure state | Over-refund, invalid allocation, provider failure, insufficient permission |
| Loading state | “Processing refund…” |
| Empty state | “No refunds pending.” |
| Permission failure | SUPPORT cannot approve financial refund unless policy allows |
| Idempotency behavior | Required |
| Notification | Refund approved/submitted/succeeded/failed |
| Audit/event generated | `REFUND_APPROVED`, `REFUND_PROVIDER_SUBMITTED`, `REFUND_SUCCEEDED/FAILED`, `PAYMENT_REFUNDED/PAYMENT_PARTIALLY_REFUNDED`, `ADMIN_ACTION` |
| Next allowed action | Resolve dispute, update payout eligibility, reconcile ledger |

Admin must see allocation:

```text
Approved amount
Teacher adjustment amount
Platform adjustment amount
Total allocation equals approved amount
```

---

## Flow 33 — Admin Audit/Event Views

| Field | Specification |
|---|---|
| Actor | OPS/Admin; SUPPORT limited |
| Entry point | Admin → Event Ledger / Security Events |
| Preconditions | Admin authenticated with permission |
| UI state | Searchable event timeline by user/entity/request ID |
| User action | Admin filters by booking, payment, session, dispute, refund, provider event |
| API call | `GET /admin/events`, `GET /admin/security-events` |
| Backend state transition | None; read-only |
| Success state | Admin sees audit trail for investigation |
| Failure state | Permission denied, too broad query, rate limit |
| Loading state | Event list skeleton |
| Empty state | “No events match these filters.” |
| Permission failure | SUPPORT sees limited operational events; ADMIN sees full allowed scope |
| Idempotency behavior | Not applicable |
| Notification | None |
| Audit/event generated | Sensitive access may generate `ADMIN_ACTION`/`SECURITY_EVENT` |
| Next allowed action | Investigate dispute, verify payment/refund, review admin action trail |

UX rule:

```text
Raw payment provider payload is not exposed by default. Sensitive access must be audited.
```

---

# 10. State-Based Button Rules

## 10.1 Parent buttons

| Button | Show only when |
|---|---|
| Add student | Parent authenticated |
| Find teacher | Parent has active student or can create one first |
| Hold slot | Slot `AVAILABLE`; parent owns selected student |
| Pay | Booking `HELD`; hold not expired |
| Retry payment | Payment failed and booking still payable/fulfillable |
| View session | Booking `BOOKED` and session exists |
| Open dispute | Parent participates in booking/session/payment and policy allows |
| Request refund | Through dispute/refund policy, not arbitrary if not refundable |
| Review teacher | Review eligibility confirmed by backend |
| Repeat booking | Teacher still listed and has slots |

## 10.2 Teacher buttons

| Button | Show only when |
|---|---|
| Submit verification | Teacher profile exists and verification incomplete/rejected |
| Add availability | Teacher owns profile |
| Cancel booking | Booking cancellable under policy |
| Start session | Assigned session `SCHEDULED` and within allowed window |
| Complete session | Assigned session `STARTED` |
| Mark student no-show | Grace period elapsed and session eligible |
| Submit report | Session `COMPLETED` and report not created |
| View payout | Teacher owns payout/session |

## 10.3 Admin buttons

| Button | Show only when |
|---|---|
| Approve verification | Admin/authorized OPS; verification submitted |
| Resolve dispute | OPS/Admin and dispute open/under review |
| Approve refund | OPS/Admin; payment refundable; amount valid |
| Submit refund to provider | Refund approved |
| Process payout | Payout eligible; no open dispute; net payable > 0 |
| Suspend user | ADMIN only |
| Access sensitive document/payload | ADMIN/authorized OPS with audit |

---

# 11. Screen-Level Empty States

| Screen | Empty state |
|---|---|
| Parent children | “Add your first student profile to find a teacher.” |
| Teacher search | “No teachers match these filters. Try changing time, budget, or mode.” |
| Teacher availability | “No available slots for this teacher.” |
| Parent bookings | “No bookings yet.” |
| Upcoming sessions | “No upcoming sessions.” |
| Reports | “Reports will appear after completed sessions.” |
| Student Passport | “Progress appears after teachers submit session reports.” |
| Reviews | “No verified reviews yet.” |
| Disputes | “No disputes.” |
| Teacher earnings | “No payable sessions yet.” |
| Admin verification | “No pending verifications.” |
| Admin disputes | “No open disputes.” |
| Admin refunds | “No refunds pending.” |
| Admin events | “No events match these filters.” |

---

# 12. Permission Failure UX

Use clear but non-leaky messages.

Examples:

```text
You do not have access to this student profile.
You do not have access to this booking.
Only the assigned teacher can start this session.
This action requires admin permission.
This review is not eligible yet.
```

Do not reveal whether another user’s resource exists.

For student data:

```text
Return generic access denied, not “This student belongs to another parent.”
```

---

# 13. Notifications Matrix

| Event | Recipient | UX message |
|---|---|---|
| `BOOKING_CONFIRMED` | Parent + teacher | Session confirmed |
| `BOOKING_CANCELLED` | Parent + teacher | Booking cancelled |
| `PAYMENT_CONFIRMED` | Parent | Payment confirmed |
| `PAYMENT_FAILED` | Parent | Payment failed |
| `PAYMENT_RECONCILIATION_REQUIRED` | Parent + OPS | Payment received after booking issue; refund/reconciliation started |
| `SESSION_STARTED` | Parent | Session started |
| `SESSION_COMPLETED` | Parent | Session completed |
| `REPORT_CREATED` | Parent | Session report available |
| `REVIEW_CREATED` | Teacher optional | New verified review received |
| `DISPUTE_OPENED` | Participants + admin | Dispute opened |
| `DISPUTE_RESOLVED` | Participants | Dispute resolved |
| `REFUND_APPROVED` | Parent | Refund approved |
| `REFUND_PROVIDER_SUBMITTED` | Parent | Refund processing |
| `REFUND_SUCCEEDED` | Parent | Refund completed |
| `REFUND_FAILED` | Parent + OPS | Refund failed; support reviewing |
| `PAYMENT_PARTIALLY_REFUNDED` | Parent + teacher if affected | Partial refund completed |
| `PAYOUT_ELIGIBLE` | Teacher optional | Payout eligible |
| `PAYOUT_PROCESSED` | Teacher | Payout processed |

External delivery failures do not roll back business state.

---

# 14. UX Testing Checklist

Before implementation, test UX against these scenarios:

## Booking/payment

- [ ] Parent double taps hold slot.
- [ ] Two parents try same slot.
- [ ] Hold expires while parent is on payment screen.
- [ ] Payment initiation times out on frontend.
- [ ] Provider callback returns before webhook processed.
- [ ] Webhook delayed.
- [ ] Late payment after expiry.
- [ ] Payment failed.

## Session/report/review

- [ ] Teacher starts session.
- [ ] Teacher completes session.
- [ ] Parent cannot complete session.
- [ ] Report cannot be created before completion.
- [ ] Review button hidden before eligibility.
- [ ] Duplicate review submit.

## Dispute/refund/payout

- [ ] Parent opens dispute after completed session.
- [ ] Booking/session factual state remains completed.
- [ ] Payout blocked while dispute open.
- [ ] Partial refund before payout adjusts teacher net payable.
- [ ] Refund after payout creates adjustment/recovery, not edited payout.
- [ ] Refund pending does not display as refunded.
- [ ] Refund failure shown clearly.

## Authorization

- [ ] Parent cannot see another parent’s student.
- [ ] Teacher cannot see unrelated student passport.
- [ ] Teacher cannot edit trust metrics.
- [ ] SUPPORT cannot perform admin-only refund/safety actions.
- [ ] Admin sensitive access is audited.

---

# 15. Implementation Notes for Designers and Engineers

## 15.1 UX should hide complexity but not lie

Parents do not need to understand webhooks, but they do need accurate status:

```text
Payment pending
Booking confirmed
Reservation expired
Refund processing
Dispute under review
```

## 15.2 Use progressive disclosure

Show simple state first, details second.

Example:

```text
Refund processing
Details: Approved on date, submitted to provider, awaiting confirmation.
```

## 15.3 Avoid destructive language

Instead of:

```text
Your booking failed.
```

Use:

```text
Your reservation expired before payment confirmation. We have started refund/reconciliation.
```

## 15.4 State timelines are useful

For booking/payment/refund/dispute, use timelines:

```text
Reserved → Payment started → Payment confirmed → Booking confirmed → Session completed → Report available
```

For late payment:

```text
Reserved → Reservation expired → Payment received late → Refund started → Refund completed
```

---

# 16. Open UX Policy Decisions Before High-Fidelity Design

These are not architecture blockers but should be decided before final UI copy and prototypes:

1. Exact booking hold duration.
2. Payment checkout timeout.
3. Whether late payment auto-refund is automatic or reviewed by OPS first.
4. Teacher/student no-show grace periods.
5. Parent dispute window after session completion.
6. Payout delay after report completion.
7. Refund allocation policy copy shown to teacher.
8. Whether partial refund before review blocks review eligibility.
9. Notification channels for MVP: SMS, email, in-app.
10. Exact Arabic/French terminology for trust, reports, disputes, refunds.

---

# 17. Final UX Decision

EduTrust UX Flows v1.0 is valid only if implementation preserves these principles:

```text
UX reflects architecture.
UX does not create business rules.
No arbitrary state transitions.
No review before verified eligibility.
No session scheduled after expired late payment.
No payout while dispute or refund exposure blocks eligibility.
No “refunded” label before refund success.
No mutation of paid payout after later refund.
No AI in MVP flows.
No scope expansion.
```

Recommended next step after review:

```text
UX Gate Review
   ↓
Low-fidelity wireframes
   ↓
Implementation planning
```

Do not start backend implementation until UX Flows v1.0 is reviewed and accepted.
