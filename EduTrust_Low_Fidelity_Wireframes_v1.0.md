# EduTrust Algeria — Low-Fidelity Wireframes v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Low-fidelity product/interaction wireframes  
**Status:** Ready for review — no implementation started  
**Derived from:** Approved UX Flows v1.0 + UX Flows v1.1 Patch  
**Architecture baseline:** LOCKED

---

# 1. Purpose

This document describes screen-level low-fidelity wireframes for the EduTrust MVP.

It does **not** define visual styling, colors, typography, component libraries, pixel-perfect layouts, frontend code, backend code, database changes, or new product features.

The wireframes reflect the approved architecture and UX flows. They do not redefine business logic.

---

# 2. Non-Negotiable Wireframe Rules

## 2.1 Every CTA must map to approved authority

A button or action may appear only if the backend state machine and user role allow it.

Examples:

```text
Review Teacher → only if review eligibility is true.
Pay → only if booking is HELD and not expired.
Start Session → only assigned teacher, session SCHEDULED.
Process Payout → only OPS/Admin, payout eligible, no open dispute, refund exposure included.
```

## 2.2 Financial UX must be precise

Refund states remain distinct:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

Never display “Refunded” before `SUCCEEDED`.

Payout UI must show:

```text
gross_teacher_payable
refund exposure
other deductions
net_teacher_payable
```

Refund exposure includes:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

Paid payouts remain immutable. Later refunds appear as separate adjustment/recovery entries.

## 2.3 Privacy UX must be strict

- Student information is minimized.
- Parent controls student data-sharing permissions.
- Teacher sees only permitted student/session context.
- Sensitive admin access displays: **“This access will be logged.”**
- Raw payment provider payloads, unrestricted verification documents, and unnecessary minor data are not exposed.

## 2.4 Open policy values are not invented

Where a screen depends on unresolved operational policy, use:

```text
[POLICY DECISION REQUIRED]
```

---

# 3. Wireframe Index

## Parent Experience

| ID | Screen |
|---|---|
| P-01 | Authentication / Login |
| P-02 | Parent Dashboard |
| P-03 | Student List |
| P-04 | Create Student |
| P-05 | Student Profile |
| P-06 | Student Passport v0 |
| P-07 | Student Data Sharing Permissions |
| P-08 | Teacher Search |
| P-09 | Matching Results |
| P-10 | Teacher Trust Profile |
| P-11 | Teacher Availability |
| P-12 | Booking Hold |
| P-13 | Checkout / Payment Initiation |
| P-14 | Payment Pending |
| P-15 | Payment Success |
| P-16 | Payment Failure / Retry |
| P-17 | Booking Detail |
| P-18 | Session Detail |
| P-19 | Session Report |
| P-20 | Review |
| P-21 | Payment / Invoice History |
| P-22 | Refund Timeline |
| P-23 | Dispute |
| P-24 | Refund Rejected |
| P-25 | Refund Cancelled |
| P-26 | Refund Completed |
| P-27 | Notifications |
| P-28 | Account / Security |

## Teacher Experience

| ID | Screen |
|---|---|
| T-29 | Teacher Onboarding |
| T-30 | Teacher Verification |
| T-31 | Teacher Dashboard |
| T-32 | Subjects & Pricing |
| T-33 | Availability Management |
| T-34 | Booking Requests / Bookings |
| T-35 | Session Detail |
| T-36 | Attendance |
| T-37 | Session Report |
| T-38 | Reviews |
| T-39 | Earnings |
| T-40 | Payout Detail |
| T-41 | Refund Adjustment |
| T-42 | Post-Payout Recovery |
| T-43 | Student Session Context / Permission Boundary |
| T-44 | Notifications |
| T-45 | Account / Security |

## Admin / OPS Experience

| ID | Screen |
|---|---|
| A-46 | Admin Dashboard |
| A-47 | Teacher Verification Queue |
| A-48 | Teacher Verification Detail |
| A-49 | Booking Monitoring |
| A-50 | Payment Monitoring |
| A-51 | Refund Queue |
| A-52 | Refund Detail |
| A-53 | Refund Reconciliation |
| A-54 | Dispute Queue |
| A-55 | Dispute Detail |
| A-56 | Payout Eligible Queue |
| A-57 | Payout Processing |
| A-58 | Payout Failure |
| A-59 | Recovery / Adjustment |
| A-60 | Event Ledger |
| A-61 | Security Events |
| A-62 | Sensitive Document / Provider Payload Access |
| A-63 | User Suspension |
| A-64 | Audit Trail |

---

# 4. Parent Wireframes

---

## P-01 — Authentication / Login

```text
[EduTrust]
[Login/Register tabs]
Phone or Email
Password / OTP area
[Login]
[Create parent account]
[Forgot password]
```

| Field | Specification |
|---|---|
| Screen ID | P-01 |
| Actor | Parent |
| Purpose | Authenticate or create parent account |
| Entry point | Landing page, protected-route redirect, session expired |
| Primary content | Login/register form; phone/email; password or approved auth method |
| Secondary content | Security note; language selector; help link |
| Primary CTA | Login / Create account |
| Secondary CTA | Forgot password; switch to teacher registration |
| Disabled actions | Submit disabled until required fields valid |
| State badges | None |
| Loading state | “Signing you in…” |
| Empty state | Not applicable |
| Error state | Invalid credentials, rate limited, account suspended |
| Permission-denied state | If authenticated with wrong role, show role-specific redirect |
| Relevant API endpoint(s) | `POST /auth/login`, `POST /auth/register`, `POST /auth/refresh` |
| Backend state represented | User authentication/session state |
| Event generated by action | `USER_REGISTERED`, `USER_LOGIN`, `SECURITY_EVENT` on failure/anomaly |
| Idempotency requirement | Not required; duplicate submit frontend-disabled |
| Navigation destination | Parent Dashboard or Create Student |
| Sensitive-data visibility rules | Never expose token details; failed login message must not reveal account existence |

---

## P-02 — Parent Dashboard

```text
[Header: Hello, Parent]
[Children summary]
[Upcoming session card]
[Pending actions]
  - Complete payment
  - View report
  - Review teacher
[Find Teacher]
[Notifications]
```

| Field | Specification |
|---|---|
| Screen ID | P-02 |
| Actor | Parent |
| Purpose | Central hub for children, bookings, reports, payments, disputes |
| Entry point | After login, app home |
| Primary content | Upcoming sessions; children; pending payments/reports/reviews/disputes |
| Secondary content | Recent notifications; progress snapshot; quick actions |
| Primary CTA | Find teacher |
| Secondary CTA | Add student; view bookings; view reports |
| Disabled actions | Review disabled unless backend says eligible; pay disabled unless booking payable |
| State badges | Upcoming, Payment pending, Report available, Dispute open |
| Loading state | Dashboard skeleton cards |
| Empty state | “Add your first student profile to start finding teachers.” |
| Error state | Unable to load dashboard; retry |
| Permission-denied state | Parent role required |
| Relevant API endpoint(s) | `GET /students`, `GET /bookings`, `GET /notifications` or aggregated dashboard endpoint if implemented |
| Backend state represented | Student, booking, payment, session, report, review eligibility summaries |
| Event generated by action | None for read; actions generate their own events |
| Idempotency requirement | Not applicable |
| Navigation destination | Student List, Teacher Search, Booking Detail, Session Report |
| Sensitive-data visibility rules | Show only own children and own transactions |

---

## P-03 — Student List

```text
[Children]
[+ Add student]

Student card:
  Name/nickname
  Academic level
  Active bookings
  Recent progress
  [View profile]
  [Find teacher]
```

| Field | Specification |
|---|---|
| Screen ID | P-03 |
| Actor | Parent |
| Purpose | View and manage own student profiles |
| Entry point | Dashboard → Children |
| Primary content | List of own students with academic level and summary |
| Secondary content | Progress/report count; upcoming sessions |
| Primary CTA | Add student |
| Secondary CTA | View profile; Find teacher |
| Disabled actions | Find teacher disabled if student inactive/deleted |
| State badges | Active, Archived |
| Loading state | Student card skeleton |
| Empty state | “Add your first student profile.” |
| Error state | Could not load students |
| Permission-denied state | Parent role required |
| Relevant API endpoint(s) | `GET /students`, `POST /students` for add action |
| Backend state represented | `student_profiles.status`, parent ownership |
| Event generated by action | None for list; create generates `STUDENT_PROFILE_CREATED` |
| Idempotency requirement | Not applicable for list |
| Navigation destination | Create Student, Student Profile |
| Sensitive-data visibility rules | Only display minimized student data; never expose other parents’ students |

---

## P-04 — Create Student

```text
[Create Student]
Display name / nickname
Birth year optional
Academic level
Primary goal
Preferred mode
Consent checkbox
[Save student]
```

| Field | Specification |
|---|---|
| Screen ID | P-04 |
| Actor | Parent |
| Purpose | Create minimized student profile |
| Entry point | Student List → Add; onboarding prompt |
| Primary content | Student display name, academic level, goal, preferred mode, consent |
| Secondary content | Privacy explanation: “Only necessary learning information is collected.” |
| Primary CTA | Save student |
| Secondary CTA | Cancel |
| Disabled actions | Save disabled until required fields valid and consent granted |
| State badges | None |
| Loading state | “Saving student profile…” |
| Empty state | Not applicable |
| Error state | Validation error; inactive academic level |
| Permission-denied state | Parent role required |
| Relevant API endpoint(s) | `POST /students` |
| Backend state represented | New `student_profiles` row |
| Event generated by action | `STUDENT_PROFILE_CREATED` |
| Idempotency requirement | Recommended for duplicate submit, not financial-critical |
| Navigation destination | Student Profile or Teacher Search |
| Sensitive-data visibility rules | Do not request unnecessary minor data |

---

## P-05 — Student Profile

```text
[Student: Ahmed]
Academic level
Learning goal
Preferred mode
[Find teacher]
[View Passport]
[Data sharing permissions]
Recent sessions
Reports
```

| Field | Specification |
|---|---|
| Screen ID | P-05 |
| Actor | Parent |
| Purpose | Manage one student profile and access related learning/session history |
| Entry point | Student List, Dashboard |
| Primary content | Student summary, learning goal, academic level, recent sessions/reports |
| Secondary content | Data-sharing permissions, progress preview |
| Primary CTA | Find teacher |
| Secondary CTA | View Passport; Manage permissions; Edit profile |
| Disabled actions | Find teacher disabled if student archived |
| State badges | Active, Archived |
| Loading state | Profile skeleton |
| Empty state | “No sessions yet.” |
| Error state | Could not load student profile |
| Permission-denied state | Generic “You do not have access to this student profile.” |
| Relevant API endpoint(s) | `GET /students/:id`, `PATCH /students/:id`, `GET /students/:id/passport` |
| Backend state represented | Student ownership and status |
| Event generated by action | `STUDENT_PROFILE_UPDATED` on edit |
| Idempotency requirement | Not required for read; recommended for update |
| Navigation destination | Passport, Permissions, Search |
| Sensitive-data visibility rules | Parent-only; no unnecessary minor data shown |

---

## P-06 — Student Passport v0

```text
[Student Passport]
Subject: Mathematics
Completed sessions: 12
Recent topics
Teacher observations
Homework history
Progress notes
[Share limited context]
```

| Field | Specification |
|---|---|
| Screen ID | P-06 |
| Actor | Parent |
| Purpose | View structured learning history from verified sessions/reports |
| Entry point | Student Profile → Passport |
| Primary content | Subjects, recent topics, reports, progress events, homework notes |
| Secondary content | Teacher observations and session history links |
| Primary CTA | Find next teacher/session |
| Secondary CTA | Manage sharing permissions |
| Disabled actions | Share disabled if no teacher/session context selected |
| State badges | Data from verified sessions; Report-based |
| Loading state | Passport skeleton |
| Empty state | “Progress appears after completed sessions and teacher reports.” |
| Error state | Could not load passport |
| Permission-denied state | Parent-only unless explicitly shared |
| Relevant API endpoint(s) | `GET /students/:id/passport` |
| Backend state represented | `student_progress_events`, session reports, parent ownership |
| Event generated by action | None for parent read; sensitive teacher/admin access may audit |
| Idempotency requirement | Not applicable |
| Navigation destination | Student Permissions, Reports, Booking repeat |
| Sensitive-data visibility rules | No AI-derived claims; structured data only; teacher access requires permission |

---

## P-07 — Student Data Sharing Permissions

```text
[Data Sharing]
Teacher access list:
  Teacher name
  Scope: SESSION_CONTEXT
  Linked booking/session
  Expires at
  [Revoke]
[Grant access]
```

| Field | Specification |
|---|---|
| Screen ID | P-07 |
| Actor | Parent |
| Purpose | Grant, view, and revoke teacher access to limited student context |
| Entry point | Student Passport, Student Profile, Booking confirmation |
| Primary content | Active/expired/revoked permissions, scope, teacher, expiry |
| Secondary content | Explanation of what teacher can see |
| Primary CTA | Grant access |
| Secondary CTA | Revoke access; View teacher profile |
| Disabled actions | Grant disabled without valid teacher/context; revoke disabled if already revoked/expired |
| State badges | Active, Expired, Revoked |
| Loading state | “Updating access…” |
| Empty state | “No teachers currently have access to this student profile.” |
| Error state | Invalid teacher, booking mismatch, permission expired |
| Permission-denied state | Parent must own student |
| Relevant API endpoint(s) | `POST /students/:id/permissions`, `DELETE /students/:id/permissions/:permission_id`, read via student/passport response or `GET /students/:id/permissions` if implemented |
| Backend state represented | `student_permissions`, parent ownership, scope, expiry |
| Event generated by action | `STUDENT_PROFILE_UPDATED` or equivalent permission audit event; sensitive access logs where applicable |
| Idempotency requirement | Recommended for grant/revoke |
| Navigation destination | Passport, Teacher Profile, Session Detail |
| Sensitive-data visibility rules | Teacher sees only granted scope; parent controls revocation |

---

## P-08 — Teacher Search

```text
[Find Teacher]
Student selector
Subject
Academic level
Mode
Budget
Availability
Language
Location if in-person
[Search]
[Find best match]
```

| Field | Specification |
|---|---|
| Screen ID | P-08 |
| Actor | Parent |
| Purpose | Search teachers using filters |
| Entry point | Dashboard, Student Profile |
| Primary content | Search filters |
| Secondary content | Saved/recent searches if later implemented; MVP can omit |
| Primary CTA | Search |
| Secondary CTA | Find best match |
| Disabled actions | Search disabled until subject/level/student selected |
| State badges | None |
| Loading state | “Searching teachers…” |
| Empty state | “No teachers match these filters.” |
| Error state | Invalid filters or network error |
| Permission-denied state | Booking requires login; parent-owned student required for match |
| Relevant API endpoint(s) | `GET /teachers/search`, `POST /teachers/match` |
| Backend state represented | Read-only teacher listing/availability/search state |
| Event generated by action | Optional analytics, not critical Event Ledger |
| Idempotency requirement | Not required |
| Navigation destination | Matching Results, Teacher Trust Profile |
| Sensitive-data visibility rules | Public search may show reduced trust/profile data; no student data exposed |

---

## P-09 — Matching Results

```text
[Best matches]
Teacher card:
  Name
  Price
  Next available slots
  Trust summary
  Why recommended
  [View profile]
  [Select slot]
```

| Field | Specification |
|---|---|
| Screen ID | P-09 |
| Actor | Parent |
| Purpose | Display rule-based teacher matches with explainable reasons |
| Entry point | Teacher Search → Find best match |
| Primary content | Matched teacher cards, trust summaries, available slots |
| Secondary content | Filters summary; adjust search |
| Primary CTA | Select slot |
| Secondary CTA | View profile; adjust filters |
| Disabled actions | Select slot disabled if slot no longer available |
| State badges | Best match, Verified identity, Qualification verified |
| Loading state | Match skeleton cards |
| Empty state | “No strong match found. Try widening availability or budget.” |
| Error state | Matching failed; retry |
| Permission-denied state | Student ownership required for student-based matching |
| Relevant API endpoint(s) | `POST /teachers/match` |
| Backend state represented | Rule-based matching output; no state transition |
| Event generated by action | None critical |
| Idempotency requirement | Not applicable |
| Navigation destination | Teacher Trust Profile, Teacher Availability |
| Sensitive-data visibility rules | Do not reveal hidden ranking score; show explainable reasons only |

---

## P-10 — Teacher Trust Profile

```text
[Teacher profile]
Name/photo
Subjects & levels
Price
Teaching mode
Trust Profile:
  Identity verified
  Qualification verified
  Completed sessions
  Rating + review count
  Attendance
  Cancellation
[Available slots]
[Book]
```

| Field | Specification |
|---|---|
| Screen ID | P-10 |
| Actor | Parent |
| Purpose | Evaluate teacher trust and suitability |
| Entry point | Search/match results |
| Primary content | Teacher profile, subject offerings, trust profile, verified reviews |
| Secondary content | Teaching methodology, languages, service area |
| Primary CTA | Choose slot |
| Secondary CTA | View reviews; back to results |
| Disabled actions | Book disabled if no available slots or teacher unlisted |
| State badges | Identity verified, Qualifications reviewed, Listed/Unavailable |
| Loading state | Profile skeleton |
| Empty state | “No verified reviews yet.” |
| Error state | Teacher unavailable/suspended/not found |
| Permission-denied state | Public view hides sensitive/internal data |
| Relevant API endpoint(s) | `GET /teachers/:id`, `GET /teachers/:id/trust-profile`, `GET /teachers/:id/reviews` |
| Backend state represented | Teacher listing, trust metrics derived data |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Teacher Availability, Booking Hold |
| Sensitive-data visibility rules | Trust metrics are read-only derived data; no private verification documents exposed |

---

## P-11 — Teacher Availability

```text
[Teacher Availability]
Calendar week view
Available slot chips
Selected slot summary
[Reserve this slot]
```

| Field | Specification |
|---|---|
| Screen ID | P-11 |
| Actor | Parent |
| Purpose | Select available teacher slot |
| Entry point | Teacher Trust Profile |
| Primary content | Calendar/list of available slots in local time |
| Secondary content | Timezone display, mode, duration, price |
| Primary CTA | Reserve this slot |
| Secondary CTA | Change date; back to profile |
| Disabled actions | Reserve disabled if slot not available |
| State badges | Available, Held, Booked, Blocked |
| Loading state | Loading slots |
| Empty state | “No available slots for this teacher.” |
| Error state | Could not load availability |
| Permission-denied state | Login required before hold |
| Relevant API endpoint(s) | `GET /availability/search`, `POST /bookings/hold` |
| Backend state represented | `availability_slots.status` |
| Event generated by action | Hold action generates `BOOKING_CREATED`, `BOOKING_HELD` |
| Idempotency requirement | Required for hold |
| Navigation destination | Booking Hold |
| Sensitive-data visibility rules | Show slot times only; no other parent/booking details |

---

## P-12 — Booking Hold

```text
[Reservation Summary]
Teacher
Student
Subject
Date/time
Price
Countdown: [POLICY DECISION REQUIRED]
[Proceed to payment]
[Cancel reservation]
```

| Field | Specification |
|---|---|
| Screen ID | P-12 |
| Actor | Parent |
| Purpose | Show temporary booking hold and countdown |
| Entry point | Slot reservation success |
| Primary content | Booking summary, price, hold expiry countdown |
| Secondary content | Cancellation/refund policy note if payment starts |
| Primary CTA | Proceed to payment |
| Secondary CTA | Cancel reservation; choose another slot |
| Disabled actions | Pay disabled after hold expiry |
| State badges | Reserved temporarily, Expired |
| Loading state | “Reserving your session…” |
| Empty state | Not applicable |
| Error state | Slot unavailable, hold failed |
| Permission-denied state | Parent must own student |
| Relevant API endpoint(s) | `POST /bookings/hold`, `GET /bookings/:id` |
| Backend state represented | Booking `HELD`, slot `HELD`, `hold_expires_at` |
| Event generated by action | `BOOKING_CREATED`, `BOOKING_HELD` |
| Idempotency requirement | Required for hold |
| Navigation destination | Checkout / Payment Initiation |
| Sensitive-data visibility rules | Parent sees own booking/student only |

---

## P-13 — Checkout / Payment Initiation

```text
[Checkout]
Booking summary
Amount: DZD
Payment method
[Pay]
[Back]
```

| Field | Specification |
|---|---|
| Screen ID | P-13 |
| Actor | Parent |
| Purpose | Initiate payment for held booking |
| Entry point | Booking Hold → Proceed to payment |
| Primary content | Amount, provider options, booking summary |
| Secondary content | Payment security note; hold countdown |
| Primary CTA | Pay |
| Secondary CTA | Back to booking summary |
| Disabled actions | Pay disabled if hold expired or provider unavailable |
| State badges | Payment not started, Held |
| Loading state | “Starting payment…” |
| Empty state | “No payment methods available.” |
| Error state | Provider unavailable; payment setup failed; hold expired |
| Permission-denied state | Parent must own booking |
| Relevant API endpoint(s) | `POST /payments/initiate`, `POST /bookings/:id/payment` |
| Backend state represented | Booking `HELD` → `PAYMENT_PENDING`; payment `INITIATED/PENDING` |
| Event generated by action | `PAYMENT_INITIATED` |
| Idempotency requirement | Required |
| Navigation destination | Provider checkout or Payment Pending |
| Sensitive-data visibility rules | Do not display raw provider payload; show only amount/status/reference |

---

## P-14 — Payment Pending

```text
[Payment pending]
We are waiting for confirmation.
Booking summary
[Refresh status]
[Return to dashboard]
```

| Field | Specification |
|---|---|
| Screen ID | P-14 |
| Actor | Parent |
| Purpose | Represent provider/webhook delay safely |
| Entry point | Return from provider, booking detail, payment status |
| Primary content | Payment pending message, booking summary |
| Secondary content | Explanation that confirmation may take time |
| Primary CTA | Refresh status |
| Secondary CTA | Return to dashboard |
| Disabled actions | Review/session actions disabled until booking confirmed/session exists |
| State badges | Payment pending, Booking waiting for confirmation |
| Loading state | “Checking latest status…” |
| Empty state | Not applicable |
| Error state | Could not check status; retry |
| Permission-denied state | Parent must own payment/booking |
| Relevant API endpoint(s) | `GET /payments/:id`, `GET /bookings/:id` |
| Backend state represented | Payment `INITIATED/PENDING`, booking `PAYMENT_PENDING` |
| Event generated by action | None for polling |
| Idempotency requirement | Not applicable |
| Navigation destination | Payment Success, Payment Failure, Late Payment/Reconciliation if applicable |
| Sensitive-data visibility rules | No raw provider payload exposed |

---

## P-15 — Payment Success

```text
[Payment confirmed]
[Booking confirmed]
Session scheduled
Teacher
Student
Date/time
[View session]
```

| Field | Specification |
|---|---|
| Screen ID | P-15 |
| Actor | Parent |
| Purpose | Confirm successful fulfillable payment and scheduled session |
| Entry point | Payment status polling, notification, booking detail |
| Primary content | Payment confirmed, booking confirmed, session scheduled details |
| Secondary content | Receipt/invoice link, reminders |
| Primary CTA | View session |
| Secondary CTA | View payment receipt; add calendar reminder |
| Disabled actions | Review disabled until completed session |
| State badges | Paid, Confirmed, Scheduled |
| Loading state | Loading session details |
| Empty state | Not applicable |
| Error state | Payment confirmed but session missing should not occur; show support/retry status if detected |
| Permission-denied state | Parent must own booking/session |
| Relevant API endpoint(s) | `GET /payments/:id`, `GET /bookings/:id`, `GET /sessions/:id` |
| Backend state represented | Payment `CONFIRMED`, booking `BOOKED`, session `SCHEDULED` |
| Event generated by action | Backend already emitted `PAYMENT_CONFIRMED`, `BOOKING_CONFIRMED` |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Session Detail |
| Sensitive-data visibility rules | Receipt shows own payment only |

---

## P-16 — Payment Failure / Retry

```text
[Payment failed]
Reason summary
Booking status
[Try again]
[Choose another slot]
[Contact support]
```

| Field | Specification |
|---|---|
| Screen ID | P-16 |
| Actor | Parent |
| Purpose | Recover from failed payment or checkout setup failure |
| Entry point | Provider return, payment status page |
| Primary content | Failure state, retry eligibility, booking status |
| Secondary content | Hold expiry information, support link |
| Primary CTA | Try again, if booking still payable/fulfillable |
| Secondary CTA | Choose another slot; contact support |
| Disabled actions | Retry disabled if booking expired/cancelled |
| State badges | Payment failed, Reservation expired if applicable |
| Loading state | “Checking whether retry is available…” |
| Empty state | Not applicable |
| Error state | Provider unavailable; unknown status |
| Permission-denied state | Parent must own payment |
| Relevant API endpoint(s) | `GET /payments/:id`, `GET /bookings/:id`, `POST /payments/initiate` for retry if allowed |
| Backend state represented | Payment `FAILED`; booking `HELD/PAYMENT_PENDING/EXPIRED/CANCELLED` |
| Event generated by action | Retry generates `PAYMENT_INITIATED`; failure generated `PAYMENT_FAILED` |
| Idempotency requirement | Retry initiation requires new or replay-safe idempotency key as backend defines |
| Navigation destination | Payment Pending, Teacher Availability |
| Sensitive-data visibility rules | Show safe error summary, not raw provider details |

---

## P-17 — Booking Detail

```text
[Booking]
Status badge
Teacher
Student
Subject
Time
Payment status
Session status
Dispute banner if open
[View session]
[Cancel booking]
[Report problem]
```

| Field | Specification |
|---|---|
| Screen ID | P-17 |
| Actor | Parent |
| Purpose | View booking state and allowed actions |
| Entry point | Dashboard, bookings list, notification |
| Primary content | Booking summary with booking/payment/session states |
| Secondary content | Timeline; refund/dispute overlays |
| Primary CTA | Context-dependent: Pay, View session, View report |
| Secondary CTA | Cancel booking, Report problem, Choose new slot |
| Disabled actions | Reschedule hidden; review hidden until eligible; cancel disabled if not allowed |
| State badges | Held, Payment pending, Confirmed, Completed, Cancelled, Expired, Refund pending |
| Loading state | Booking skeleton |
| Empty state | Not applicable |
| Error state | Booking unavailable |
| Permission-denied state | Parent can view only own booking |
| Relevant API endpoint(s) | `GET /bookings/:id`, `POST /bookings/:id/cancel`, `POST /disputes` |
| Backend state represented | Booking/payment/session/dispute/refund overlay states |
| Event generated by action | Cancel → `BOOKING_CANCELLED`; dispute → `DISPUTE_OPENED` |
| Idempotency requirement | Cancel/dispute recommended idempotent |
| Navigation destination | Session Detail, Refund Timeline, Dispute, Teacher Availability |
| Sensitive-data visibility rules | Own booking only; teacher private data hidden |

---

## P-18 — Session Detail

```text
[Session]
Status: Scheduled/In progress/Completed
Teacher
Student
Subject
Date/time
Attendance status
[View report]
[Report problem]
```

| Field | Specification |
|---|---|
| Screen ID | P-18 |
| Actor | Parent |
| Purpose | View session status and related report/dispute actions |
| Entry point | Booking Detail, Dashboard, notification |
| Primary content | Session state, attendance, teacher/student/subject/time |
| Secondary content | Report status, dispute banner, payment/refund summary |
| Primary CTA | View report if available |
| Secondary CTA | Report problem; view booking |
| Disabled actions | Parent cannot start/complete session; review disabled until eligible |
| State badges | Scheduled, In progress, Completed, Student absent, Teacher absent, Dispute open overlay |
| Loading state | Session skeleton |
| Empty state | No session if booking not confirmed; show booking status instead |
| Error state | Session unavailable |
| Permission-denied state | Parent can view only own child session |
| Relevant API endpoint(s) | `GET /sessions/:id`, `GET /sessions/:id/report`, `POST /disputes` |
| Backend state represented | Session factual state + dispute overlay |
| Event generated by action | Dispute action → `DISPUTE_OPENED` |
| Idempotency requirement | Dispute recommended idempotent |
| Navigation destination | Report, Dispute, Review if eligible |
| Sensitive-data visibility rules | Own child session only |

---

## P-19 — Session Report

```text
[Session Report]
Topics covered
Skills practiced
Participation
Teacher observations
Homework
Recommended revision
Next objectives
[Review teacher]
[Report issue]
```

| Field | Specification |
|---|---|
| Screen ID | P-19 |
| Actor | Parent |
| Purpose | View structured teacher report |
| Entry point | Report notification, Session Detail |
| Primary content | Structured report fields |
| Secondary content | Link to Student Passport and homework/history |
| Primary CTA | Review teacher if eligible |
| Secondary CTA | Report issue; view Passport |
| Disabled actions | Review disabled if not eligible or already reviewed |
| State badges | Report available, Verified session |
| Loading state | Report skeleton |
| Empty state | “Report not available yet.” |
| Error state | Could not load report |
| Permission-denied state | Parent can view own child report only |
| Relevant API endpoint(s) | `GET /sessions/:id/report`, `POST /sessions/:id/review`, `POST /disputes` |
| Backend state represented | `session_reports`, review eligibility, session completed |
| Event generated by action | Review → `REVIEW_CREATED`; dispute → `DISPUTE_OPENED` |
| Idempotency requirement | Review recommended idempotent |
| Navigation destination | Review, Passport, Dispute |
| Sensitive-data visibility rules | Report belongs to own child/session |

---

## P-20 — Review

```text
[Review Teacher]
Rating stars
Comment
Verified session summary
[Submit review]
```

| Field | Specification |
|---|---|
| Screen ID | P-20 |
| Actor | Parent |
| Purpose | Submit verified review after eligible completed paid session |
| Entry point | Session Report, review request notification |
| Primary content | Rating, comment, verified session context |
| Secondary content | Review policy note |
| Primary CTA | Submit review |
| Secondary CTA | Cancel |
| Disabled actions | Submit disabled if not eligible or duplicate review exists |
| State badges | Verified completed session |
| Loading state | “Submitting review…” |
| Empty state | If not eligible, show reason rather than empty form |
| Error state | Duplicate review, not eligible, validation error |
| Permission-denied state | Parent must own student/session; teacher cannot review self |
| Relevant API endpoint(s) | `POST /sessions/:id/review` |
| Backend state represented | Review eligibility; review `VISIBLE` after creation |
| Event generated by action | `REVIEW_CREATED` |
| Idempotency requirement | Recommended; DB unique also protects |
| Navigation destination | Teacher Profile, Booking Detail |
| Sensitive-data visibility rules | Review linked to verified session; no arbitrary reviews |

---

## P-21 — Payment / Invoice History

```text
[Payments]
Payment cards:
  Date
  Teacher/session
  Amount
  Status
  Refund status if any
  [View receipt]
  [View refund]
```

| Field | Specification |
|---|---|
| Screen ID | P-21 |
| Actor | Parent |
| Purpose | View own payment, invoice, and refund history |
| Entry point | Dashboard → Payments |
| Primary content | Payment list with status and amount |
| Secondary content | Refund summaries, invoice/receipt links |
| Primary CTA | View payment detail |
| Secondary CTA | View refund timeline; download invoice if implemented |
| Disabled actions | Refund request disabled unless policy/eligibility allows |
| State badges | Paid, Payment pending, Failed, Refund processing, Partially refunded, Refunded |
| Loading state | Payment list skeleton |
| Empty state | “No payments yet.” |
| Error state | Could not load payments |
| Permission-denied state | Parent can view only own payments |
| Relevant API endpoint(s) | `GET /payments`, `GET /payments/:id` |
| Backend state represented | Payments, refunds, invoices/records |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Refund Timeline, Booking Detail |
| Sensitive-data visibility rules | No raw provider payload; own payments only |

---

## P-22 — Refund Timeline

```text
[Refund Timeline]
Requested
Approved
Submitted to provider
Completed / Failed / Rejected / Cancelled
Amount
Reason
[Contact support]
```

| Field | Specification |
|---|---|
| Screen ID | P-22 |
| Actor | Parent |
| Purpose | Show exact refund lifecycle without collapsing states |
| Entry point | Payment detail, dispute detail, notification |
| Primary content | Timeline states: REQUESTED, APPROVED, PROVIDER_PENDING, SUCCEEDED, FAILED, REJECTED, CANCELLED |
| Secondary content | Amount, reason, dispute link, expected timing if policy defined |
| Primary CTA | Contact support if failed/rejected |
| Secondary CTA | View payment; view dispute |
| Disabled actions | No “refunded” label before SUCCEEDED |
| State badges | Refund requested, approved, processing, completed, failed, rejected, cancelled |
| Loading state | Refund timeline skeleton |
| Empty state | “No refund activity for this payment.” |
| Error state | Could not load refund status |
| Permission-denied state | Parent can view only own refund/payment |
| Relevant API endpoint(s) | `GET /payments/:id` including refunds, `GET /bookings/:id`, `GET /disputes/:id` where refund linked; explicit refund read endpoint if implemented |
| Backend state represented | `refunds.status`, payment refund status |
| Event generated by action | None for read; refund actions generate refund events |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Payment History, Dispute |
| Sensitive-data visibility rules | No provider payload or admin reconciliation internals exposed to parent |

---

## P-23 — Dispute

```text
[Report a problem]
Category
Description
Evidence optional
Related booking/session/payment
[Submit]

[Dispute detail]
Status timeline
Resolution
Refund link if any
```

| Field | Specification |
|---|---|
| Screen ID | P-23 |
| Actor | Parent |
| Purpose | Open and track dispute as overlay |
| Entry point | Booking Detail, Session Detail, Report, Payment |
| Primary content | Dispute category form or dispute status timeline |
| Secondary content | Related booking/session/payment; refund link if any |
| Primary CTA | Submit dispute |
| Secondary CTA | Add evidence; contact support |
| Disabled actions | Submit disabled without category/description; duplicate active dispute policy-dependent |
| State badges | Open, Under review, Resolved, Rejected, Cancelled; Safety priority |
| Loading state | “Opening dispute…” / dispute skeleton |
| Empty state | “No disputes.” |
| Error state | Not participant, invalid target |
| Permission-denied state | Actor must participate in booking/session/payment |
| Relevant API endpoint(s) | `POST /disputes`, `GET /disputes`, `GET /disputes/:id` if implemented/read via dashboard |
| Backend state represented | `disputes.status`; booking/session factual state unchanged |
| Event generated by action | `DISPUTE_OPENED`, later `DISPUTE_RESOLVED` |
| Idempotency requirement | Recommended; required if refund action involved by admin |
| Navigation destination | Refund Timeline, Booking Detail, Session Detail |
| Sensitive-data visibility rules | Parent sees own dispute only; safety reports handled carefully |

---

## P-24 — Refund Rejected

```text
[Refund rejected]
Reason
Related dispute/payment
[View dispute]
[Contact support]
```

| Field | Specification |
|---|---|
| Screen ID | P-24 |
| Actor | Parent |
| Purpose | Explain rejected refund without implying money moved |
| Entry point | Refund notification, Refund Timeline |
| Primary content | Rejection label, reason, timestamp |
| Secondary content | Related dispute/payment; support guidance |
| Primary CTA | View dispute |
| Secondary CTA | Contact support |
| Disabled actions | No “refund completed” or payout-related actions |
| State badges | Refund rejected |
| Loading state | Loading refund decision |
| Empty state | Not applicable |
| Error state | Could not load refund rejection details |
| Permission-denied state | Parent can view only own refund |
| Relevant API endpoint(s) | Refund read through `GET /payments/:id` or linked dispute/payment response |
| Backend state represented | Refund `REJECTED` |
| Event generated by action | Backend emitted `REFUND_REJECTED` |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Dispute, Payment History |
| Sensitive-data visibility rules | No internal admin notes beyond approved user-facing reason |

---

## P-25 — Refund Cancelled

```text
[Refund cancelled]
No refund was issued.
Reason
[View payment]
```

| Field | Specification |
|---|---|
| Screen ID | P-25 |
| Actor | Parent |
| Purpose | Show refund workflow cancelled before completion |
| Entry point | Refund notification, Refund Timeline |
| Primary content | Cancelled label, reason, timestamp |
| Secondary content | Payment/dispute reference |
| Primary CTA | View payment |
| Secondary CTA | Contact support |
| Disabled actions | Do not show refunded receipt |
| State badges | Refund cancelled |
| Loading state | Loading cancellation details |
| Empty state | Not applicable |
| Error state | Could not load refund cancellation |
| Permission-denied state | Parent can view only own refund/payment |
| Relevant API endpoint(s) | Refund read through payment/dispute response |
| Backend state represented | Refund `CANCELLED` |
| Event generated by action | Backend emitted `REFUND_CANCELLED` |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Payment History, Dispute |
| Sensitive-data visibility rules | No provider evidence shown; internal details remain admin-only |

---

## P-26 — Refund Completed

```text
[Refund completed]
Amount refunded
Date completed
Payment status: Refunded / Partially refunded
[View receipt/history]
```

| Field | Specification |
|---|---|
| Screen ID | P-26 |
| Actor | Parent |
| Purpose | Confirm refund success only after provider/reconciliation success |
| Entry point | Refund notification, Refund Timeline |
| Primary content | Amount, completion date, full/partial indicator |
| Secondary content | Related dispute/payment; remaining amount if partial |
| Primary CTA | View payment history |
| Secondary CTA | View dispute |
| Disabled actions | None unless additional refund not allowed |
| State badges | Refund completed, Partially refunded or Refunded |
| Loading state | Loading refund completion |
| Empty state | Not applicable |
| Error state | Could not load refund completion details |
| Permission-denied state | Parent can view only own refund |
| Relevant API endpoint(s) | `GET /payments/:id`, refund timeline response |
| Backend state represented | Refund `SUCCEEDED`; payment `REFUNDED` or `PARTIALLY_REFUNDED` |
| Event generated by action | Backend emitted `REFUND_SUCCEEDED`, `PAYMENT_REFUNDED` or `PAYMENT_PARTIALLY_REFUNDED` |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Payment History, Dispute |
| Sensitive-data visibility rules | No provider raw payload |

---

## P-27 — Notifications

```text
[Notifications]
Unread/read list
Booking confirmed
Payment failed
Report available
Refund completed
Dispute update
[Mark read]
```

| Field | Specification |
|---|---|
| Screen ID | P-27 |
| Actor | Parent |
| Purpose | View important platform notifications |
| Entry point | Notification icon/tab |
| Primary content | Notifications list with status and timestamps |
| Secondary content | Filters: all/unread/payment/session/dispute |
| Primary CTA | Open notification target |
| Secondary CTA | Mark as read |
| Disabled actions | Open disabled if target no longer accessible; show safe message |
| State badges | Unread, Read, Failed delivery not normally parent-facing |
| Loading state | Notification skeleton |
| Empty state | “No notifications.” |
| Error state | Could not load notifications |
| Permission-denied state | User sees own notifications only |
| Relevant API endpoint(s) | `GET /notifications`, `POST /notifications/:id/read` if implemented |
| Backend state represented | `notifications.status` |
| Event generated by action | Mark-read may not require Event Ledger; notification created by source events |
| Idempotency requirement | Recommended for mark-read |
| Navigation destination | Booking, Payment, Report, Dispute, Refund |
| Sensitive-data visibility rules | Notification text avoids exposing sensitive details on lock screen if push/SMS policy requires |

---

## P-28 — Account / Security

```text
[Account]
Profile
Preferred language
Login sessions
[Logout]
[Revoke other sessions]
Security events
```

| Field | Specification |
|---|---|
| Screen ID | P-28 |
| Actor | Parent |
| Purpose | Manage account and security sessions |
| Entry point | Account tab |
| Primary content | Profile, preferred language, active sessions |
| Secondary content | Security tips, recent security events |
| Primary CTA | Save changes |
| Secondary CTA | Logout; revoke sessions |
| Disabled actions | Revoke disabled if no other sessions |
| State badges | Active session, Current device |
| Loading state | Account skeleton |
| Empty state | No other sessions |
| Error state | Could not update account |
| Permission-denied state | Auth required |
| Relevant API endpoint(s) | `GET /parents/me`, `PATCH /parents/me`, `POST /auth/logout`, `POST /auth/revoke-sessions` |
| Backend state represented | User/auth sessions/security events |
| Event generated by action | `SECURITY_EVENT` for session revocation/password/security changes |
| Idempotency requirement | Recommended for revoke-sessions |
| Navigation destination | Login after logout; dashboard after save |
| Sensitive-data visibility rules | Never show raw tokens; session details limited to device/time/IP approximation |

---

# 5. Teacher Wireframes

---

## T-29 — Teacher Onboarding

```text
[Become a teacher]
Account basics
Professional profile progress
Steps:
1 Profile
2 Subjects & pricing
3 Verification
4 Availability
[Continue]
```

| Field | Specification |
|---|---|
| Screen ID | T-29 |
| Actor | Teacher |
| Purpose | Guide teacher through setup to become listable |
| Entry point | Teacher registration/login |
| Primary content | Onboarding checklist |
| Secondary content | Benefits: verified reputation, bookings, reports, payouts |
| Primary CTA | Continue setup |
| Secondary CTA | Save and exit |
| Disabled actions | Become listed disabled until required steps complete |
| State badges | Draft, Pending verification, Ready to list |
| Loading state | Loading setup progress |
| Empty state | New teacher starts with empty checklist |
| Error state | Could not load onboarding progress |
| Permission-denied state | Teacher role required |
| Relevant API endpoint(s) | `POST /auth/register`, `POST /teachers/me`, `GET /teachers/me` |
| Backend state represented | Teacher profile/listing/verification status |
| Event generated by action | `USER_REGISTERED`, `TEACHER_PROFILE_CREATED`, `TEACHER_PROFILE_UPDATED` |
| Idempotency requirement | Duplicate submits frontend-disabled/recommended |
| Navigation destination | Verification, Subjects & Pricing, Availability |
| Sensitive-data visibility rules | Teacher sees own profile only |

---

## T-30 — Teacher Verification

```text
[Verification]
Identity verification
Qualification review
Upload document metadata
[Submit]
Status: Submitted / Approved / Rejected
```

| Field | Specification |
|---|---|
| Screen ID | T-30 |
| Actor | Teacher |
| Purpose | Submit identity/qualification verification |
| Entry point | Onboarding checklist, Verification tab |
| Primary content | Verification types, upload controls, status timeline |
| Secondary content | Privacy/security note about document handling |
| Primary CTA | Submit verification |
| Secondary CTA | Replace document if rejected; view rejection reason |
| Disabled actions | Submit disabled until required docs/metadata present |
| State badges | Not submitted, Submitted, Approved, Rejected |
| Loading state | “Uploading securely…” |
| Empty state | “No verification submitted yet.” |
| Error state | Upload failed; invalid file; rejected |
| Permission-denied state | Teacher can submit only own verification |
| Relevant API endpoint(s) | `POST /teachers/verifications`, `GET /teachers/verifications` |
| Backend state represented | `teacher_verifications`, document metadata, teacher verification status |
| Event generated by action | `TEACHER_VERIFICATION_SUBMITTED` |
| Idempotency requirement | Recommended |
| Navigation destination | Teacher Dashboard, Admin review later |
| Sensitive-data visibility rules | Documents not public; secure upload; teacher sees own submissions only |

---

## T-31 — Teacher Dashboard

```text
[Teacher Dashboard]
Profile completion
Upcoming sessions
Report tasks
Earnings summary
Verification status
[Add availability]
[View bookings]
```

| Field | Specification |
|---|---|
| Screen ID | T-31 |
| Actor | Teacher |
| Purpose | Central teacher operating dashboard |
| Entry point | Teacher login |
| Primary content | Upcoming bookings/sessions, reports due, payout summary |
| Secondary content | Verification/listing status, reviews, profile completion |
| Primary CTA | View next session / Complete report |
| Secondary CTA | Add availability; manage subjects |
| Disabled actions | Start session disabled outside allowed state/window; payout processing not teacher action |
| State badges | Listed, Draft, Verification pending, Report due, Payout blocked |
| Loading state | Dashboard skeleton |
| Empty state | “Add availability so parents can book you.” |
| Error state | Could not load dashboard |
| Permission-denied state | Teacher role required |
| Relevant API endpoint(s) | `GET /teacher/bookings` or `GET /bookings` scoped, `GET /sessions`, `GET /teacher/payouts` |
| Backend state represented | Teacher profile, bookings, sessions, reports, payouts |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Sessions, Reports, Availability, Earnings |
| Sensitive-data visibility rules | Only own bookings/sessions/students with permitted context |

---

## T-32 — Subjects & Pricing

```text
[Subjects & Pricing]
Offer cards:
  Subject
  Academic level
  Price
  Duration
  Active/Inactive
[Add offering]
```

| Field | Specification |
|---|---|
| Screen ID | T-32 |
| Actor | Teacher |
| Purpose | Manage teacher subject offerings and prices |
| Entry point | Teacher Dashboard, Onboarding |
| Primary content | List of subject/level/price/duration offerings |
| Secondary content | Validation guidance and historical price note |
| Primary CTA | Add offering |
| Secondary CTA | Edit; Deactivate |
| Disabled actions | Duplicate subject/level creation blocked; delete historical offering uses deactivate |
| State badges | Active, Inactive |
| Loading state | Offering list skeleton |
| Empty state | “Add at least one subject and level so parents can find you.” |
| Error state | Duplicate offering, invalid price, inactive subject/level |
| Permission-denied state | Teacher can manage only own offerings |
| Relevant API endpoint(s) | `POST /teachers/subjects`, `PATCH /teachers/subjects/:id`, `DELETE /teachers/subjects/:id` or deactivate equivalent |
| Backend state represented | `teacher_subjects` |
| Event generated by action | `TEACHER_PROFILE_UPDATED` |
| Idempotency requirement | Recommended for create/update/deactivate |
| Navigation destination | Availability Management, Teacher Profile preview |
| Sensitive-data visibility rules | Public sees active offerings only; historical booking prices preserved |

---

## T-33 — Availability Management

```text
[Availability]
Calendar
Recurring rules
Concrete slots
Blocked periods
[Add rule]
[Add slot]
[Block slot]
```

| Field | Specification |
|---|---|
| Screen ID | T-33 |
| Actor | Teacher |
| Purpose | Create/manage available slots |
| Entry point | Teacher Dashboard, Onboarding |
| Primary content | Calendar with available/booked/held/blocked slots |
| Secondary content | Recurring rules and timezone |
| Primary CTA | Add availability |
| Secondary CTA | Block/unblock slot |
| Disabled actions | Cannot remove booked slot silently; overlapping slots blocked |
| State badges | Available, Held, Booked, Blocked |
| Loading state | Calendar skeleton |
| Empty state | “Add availability so parents can book you.” |
| Error state | Overlap, invalid time, timezone error |
| Permission-denied state | Teacher can manage only own availability |
| Relevant API endpoint(s) | `POST /teachers/availability/rules`, `PATCH /teachers/availability/rules/:id`, `POST /teachers/availability/slots`, block/unblock endpoints |
| Backend state represented | `availability_rules`, `availability_slots.status` |
| Event generated by action | `SLOT_CREATED`, `SLOT_UPDATED`, `SLOT_BLOCKED` |
| Idempotency requirement | Recommended for slot/rule creation |
| Navigation destination | Booking list, Dashboard |
| Sensitive-data visibility rules | Teacher sees own schedule; no parent details for held slot unless booking authorized |

---

## T-34 — Booking Requests / Bookings

```text
[Bookings]
Upcoming
Payment pending
Confirmed
Completed
Cancelled
Booking card:
  Student display name
  Subject
  Time
  Status
  [View]
```

| Field | Specification |
|---|---|
| Screen ID | T-34 |
| Actor | Teacher |
| Purpose | View teacher’s bookings and allowed actions |
| Entry point | Teacher Dashboard → Bookings |
| Primary content | Scoped booking list |
| Secondary content | Filters by status/date/subject |
| Primary CTA | View booking/session |
| Secondary CTA | Cancel under policy |
| Disabled actions | Cannot confirm payment; cannot complete booking directly |
| State badges | Payment pending, Confirmed, Completed, Cancelled, Report due |
| Loading state | Booking skeleton |
| Empty state | “No bookings yet.” |
| Error state | Could not load bookings |
| Permission-denied state | Teacher can view only own bookings |
| Relevant API endpoint(s) | `GET /bookings`, `GET /bookings/:id`, `POST /bookings/:id/cancel` |
| Backend state represented | Booking/payment/session summary |
| Event generated by action | Cancellation → `BOOKING_CANCELLED` |
| Idempotency requirement | Cancellation recommended |
| Navigation destination | Session Detail, Attendance, Report |
| Sensitive-data visibility rules | Student context minimized and permission-scoped |

---

## T-35 — Session Detail

```text
[Session]
Student display name
Subject
Academic level
Time
Status
[Start session]
[Complete session]
[Mark no-show]
[Create report]
```

| Field | Specification |
|---|---|
| Screen ID | T-35 |
| Actor | Teacher |
| Purpose | Manage assigned session lifecycle |
| Entry point | Booking list, Dashboard upcoming session |
| Primary content | Session details and current state |
| Secondary content | Limited student context, report status, dispute overlay |
| Primary CTA | Start / Complete based on state |
| Secondary CTA | Mark no-show; create report after completion |
| Disabled actions | Complete disabled unless session STARTED; report disabled unless COMPLETED |
| State badges | Scheduled, Started, Completed, No-show, Dispute open overlay |
| Loading state | Session skeleton |
| Empty state | Not applicable |
| Error state | Session unavailable |
| Permission-denied state | Only assigned teacher can manage session |
| Relevant API endpoint(s) | `GET /sessions/:id`, `POST /sessions/:id/start`, `POST /sessions/:id/complete`, `POST /sessions/:id/no-show` |
| Backend state represented | Session state machine |
| Event generated by action | `SESSION_STARTED`, `SESSION_COMPLETED`, `SESSION_NO_SHOW` |
| Idempotency requirement | Recommended for state actions |
| Navigation destination | Attendance, Report, Booking Detail |
| Sensitive-data visibility rules | Only permitted student/session context shown |

---

## T-36 — Attendance

```text
[Attendance]
Student: Ahmed
Status options:
[Present]
[Student no-show]
Grace period: [POLICY DECISION REQUIRED]
[Submit]
```

| Field | Specification |
|---|---|
| Screen ID | T-36 |
| Actor | Teacher |
| Purpose | Record attendance/no-show for assigned session |
| Entry point | Session Detail |
| Primary content | Attendance options and timing policy |
| Secondary content | No-show policy explanation |
| Primary CTA | Submit attendance/no-show |
| Secondary CTA | Back to session |
| Disabled actions | No-show disabled before grace period [POLICY DECISION REQUIRED] |
| State badges | Present, Student absent, Teacher absent claim if dispute overlay |
| Loading state | “Recording attendance…” |
| Empty state | Not applicable |
| Error state | Too early, already completed, unauthorized |
| Permission-denied state | Only assigned teacher/OPS can record student no-show |
| Relevant API endpoint(s) | `POST /sessions/:id/no-show`, `POST /sessions/:id/complete` for present completion flow |
| Backend state represented | `attendance_status`, session state |
| Event generated by action | `SESSION_NO_SHOW` or `SESSION_COMPLETED` |
| Idempotency requirement | Recommended |
| Navigation destination | Session Detail, Report |
| Sensitive-data visibility rules | Minimal student info |

---

## T-37 — Session Report

```text
[Create Report]
Topics covered
Skills practiced
Participation
Observations
Homework
Recommended revision
Next objectives
Progress indicator
[Submit report]
```

| Field | Specification |
|---|---|
| Screen ID | T-37 |
| Actor | Teacher |
| Purpose | Submit structured report under 2 minutes |
| Entry point | Completed Session Detail, Dashboard report task |
| Primary content | Structured report fields |
| Secondary content | Reminder that parent will see report |
| Primary CTA | Submit report |
| Secondary CTA | Save draft if implemented later; MVP may omit |
| Disabled actions | Submit disabled until required fields complete; disabled if report already exists |
| State badges | Report due, Report submitted |
| Loading state | “Saving report…” |
| Empty state | “No reports due.” |
| Error state | Session not completed, duplicate report, validation error |
| Permission-denied state | Only assigned teacher can create report |
| Relevant API endpoint(s) | `POST /sessions/:id/report`, `PATCH /sessions/:id/report` if edit policy implemented |
| Backend state represented | `session_reports`, `student_progress_events` creation |
| Event generated by action | `REPORT_CREATED` |
| Idempotency requirement | Recommended |
| Navigation destination | Session Detail, Earnings |
| Sensitive-data visibility rules | Report visible to parent of student; no AI-generated claims |

---

## T-38 — Reviews

```text
[Reviews]
Average rating
Review count
Verified review list
Status filters
```

| Field | Specification |
|---|---|
| Screen ID | T-38 |
| Actor | Teacher |
| Purpose | View verified reviews received |
| Entry point | Teacher Dashboard → Reviews |
| Primary content | Verified reviews and rating summary |
| Secondary content | Trust metrics summary; moderation status if hidden/flagged |
| Primary CTA | View review detail |
| Secondary CTA | Report inappropriate content if policy allows |
| Disabled actions | Teacher cannot edit/delete reviews or review self |
| State badges | Verified, Flagged/Hidden if relevant |
| Loading state | Reviews skeleton |
| Empty state | “No verified reviews yet.” |
| Error state | Could not load reviews |
| Permission-denied state | Teacher sees own reviews; public sees visible reviews only |
| Relevant API endpoint(s) | `GET /teachers/:id/reviews` |
| Backend state represented | `reviews.status`, verified reviews |
| Event generated by action | None for read; moderation admin only |
| Idempotency requirement | Not applicable |
| Navigation destination | Teacher Dashboard, Trust Profile preview |
| Sensitive-data visibility rules | Reviews are verified but should avoid unnecessary student data |

---

## T-39 — Earnings

```text
[Earnings]
Completed sessions
Gross payable
Refund exposure
Other deductions
Net payable
Payout status
Blocked reasons
```

| Field | Specification |
|---|---|
| Screen ID | T-39 |
| Actor | Teacher |
| Purpose | View earnings and payout eligibility transparently |
| Entry point | Teacher Dashboard → Earnings |
| Primary content | Earnings summary, net payable, payout statuses |
| Secondary content | Blocked reasons: report missing, dispute open, refund exposure, waiting period |
| Primary CTA | View payout detail |
| Secondary CTA | Complete report if blocking payout |
| Disabled actions | Teacher cannot process payout |
| State badges | Eligible, Processing, Paid, Blocked, Adjusted |
| Loading state | Earnings skeleton |
| Empty state | “No payable sessions yet.” |
| Error state | Could not load earnings |
| Permission-denied state | Teacher can view only own earnings |
| Relevant API endpoint(s) | `GET /teacher/payouts`, `GET /teacher/payouts/:id` |
| Backend state represented | Payout status, refund exposure, report/dispute blockers |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Payout Detail, Session Report |
| Sensitive-data visibility rules | Shows teacher economic impact, not parent raw payment/provider data |

---

## T-40 — Payout Detail

```text
[Payout Detail]
Gross teacher payable
Refund exposure:
  Approved
  Provider-pending
  Succeeded
Other deductions
Net teacher payable
Status
[View sessions]
```

| Field | Specification |
|---|---|
| Screen ID | T-40 |
| Actor | Teacher |
| Purpose | Show payout calculation and status |
| Entry point | Earnings → Payout card |
| Primary content | Gross, refund exposure, deductions, net, status |
| Secondary content | Included sessions, blocked reasons, payout timeline |
| Primary CTA | View included sessions |
| Secondary CTA | Contact support if failed/blocked |
| Disabled actions | No edit/process CTA for teacher |
| State badges | Eligible, Processing, Paid, Failed, Blocked |
| Loading state | Payout detail skeleton |
| Empty state | “No sessions included in this payout.” |
| Error state | Could not load payout |
| Permission-denied state | Teacher can view only own payout |
| Relevant API endpoint(s) | `GET /teacher/payouts/:id` |
| Backend state represented | Payout state machine; net payable calculation from backend |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Session Detail, Refund Adjustment, Recovery if any |
| Sensitive-data visibility rules | No raw parent payment/provider details |

---

## T-41 — Refund Adjustment

```text
[Refund Adjustment]
Related session
Refund status
Teacher adjustment amount
Platform adjustment amount if visible
Effect on net payout
```

| Field | Specification |
|---|---|
| Screen ID | T-41 |
| Actor | Teacher |
| Purpose | Explain refund impact on unpaid payout |
| Entry point | Earnings/Payout Detail when refund exposure exists |
| Primary content | Refund status and teacher adjustment amount |
| Secondary content | Dispute/reference summary; payout impact |
| Primary CTA | View related session |
| Secondary CTA | Contact support |
| Disabled actions | Teacher cannot alter adjustment |
| State badges | Approved adjustment, Processing adjustment, Applied adjustment |
| Loading state | Adjustment skeleton |
| Empty state | “No refund adjustments.” |
| Error state | Could not load adjustment |
| Permission-denied state | Teacher can view only adjustments affecting own earnings |
| Relevant API endpoint(s) | `GET /teacher/payouts/:id`, refund adjustment fields in payout response |
| Backend state represented | Refund `APPROVED/PROVIDER_PENDING/SUCCEEDED`; teacher adjustment amount |
| Event generated by action | None for read |
| Idempotency requirement | Not applicable |
| Navigation destination | Payout Detail, Session Detail |
| Sensitive-data visibility rules | Show economic impact only; hide parent-private dispute/payment details unless needed |

---

## T-42 — Post-Payout Recovery

```text
[Recovery / Adjustment]
Original payout: PAID
Later refund
Recovery balance
Future payout offset
Platform absorbed amount
Reference
```

| Field | Specification |
|---|---|
| Screen ID | T-42 |
| Actor | Teacher |
| Purpose | Explain recovery after refund on already-paid payout |
| Entry point | Earnings, notification, Payout Detail |
| Primary content | Recovery balance, adjustment entry, original payout reference |
| Secondary content | Refund/dispute reference; future payout offset |
| Primary CTA | View adjustment detail |
| Secondary CTA | Contact support |
| Disabled actions | Old payout cannot be edited |
| State badges | Recovery pending, Recovered, Platform absorbed |
| Loading state | Recovery skeleton |
| Empty state | “No recovery adjustments.” |
| Error state | Could not load recovery details |
| Permission-denied state | Teacher sees only own recovery entries |
| Relevant API endpoint(s) | `GET /teacher/payouts`, `GET /teacher/payouts/:id` with adjustments/recovery fields |
| Backend state represented | Ledger adjustment/recovery; old payout remains `PAID` |
| Event generated by action | None for read; admin adjustment generated audit/ledger events |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Payout Detail, Refund Adjustment |
| Sensitive-data visibility rules | Show financial impact, not raw ledger internals unless user-facing summary |

---

## T-43 — Student Session Context / Permission Boundary

```text
[Student Context]
Display name
Academic level
Subject
Learning goal
Shared notes allowed by parent
Permission status
Expires at
```

| Field | Specification |
|---|---|
| Screen ID | T-43 |
| Actor | Teacher |
| Purpose | Show limited student context for session preparation |
| Entry point | Session Detail, Booking Detail |
| Primary content | Minimal permitted student/session context |
| Secondary content | Permission scope and expiry |
| Primary CTA | Prepare session / Start session when allowed |
| Secondary CTA | None or request parent share more context if policy allows later; MVP omit |
| Disabled actions | Full Student Passport disabled without permission |
| State badges | Access active, Access expired, Limited context |
| Loading state | Loading context |
| Empty state | “No additional student context shared.” |
| Error state | Permission expired or unavailable |
| Permission-denied state | “You do not have access to this student context.” |
| Relevant API endpoint(s) | `GET /sessions/:id`, student context embedded by permission; permissions managed by parent |
| Backend state represented | `student_permissions`, session ownership |
| Event generated by action | Sensitive access may generate audit/security event where policy requires |
| Idempotency requirement | Not applicable |
| Navigation destination | Session Detail, Attendance |
| Sensitive-data visibility rules | Teacher sees only granted scope; no unnecessary minor data |

---

## T-44 — Notifications

```text
[Notifications]
New booking
Session approaching
Report due
Payout processed
Verification update
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | T-44 |
| Actor | Teacher |
| Purpose | View teacher notifications |
| Entry point | Notification icon/tab |
| Primary content | Notification list |
| Secondary content | Filters by booking/session/payout/verification |
| Primary CTA | Open notification target |
| Secondary CTA | Mark as read |
| Disabled actions | Open disabled if target inaccessible |
| State badges | Unread, Read |
| Loading state | Notification skeleton |
| Empty state | “No notifications.” |
| Error state | Could not load notifications |
| Permission-denied state | Teacher sees own notifications only |
| Relevant API endpoint(s) | `GET /notifications`, `POST /notifications/:id/read` if implemented |
| Backend state represented | Notifications for teacher-owned events |
| Event generated by action | Source business event creates notification |
| Idempotency requirement | Recommended for mark-read |
| Navigation destination | Booking, Session, Report, Earnings, Verification |
| Sensitive-data visibility rules | Avoid sensitive student/payment details in notification text |

---

## T-45 — Account / Security

```text
[Teacher Account]
Profile basics
Preferred language
Sessions/devices
[Logout]
[Revoke sessions]
```

| Field | Specification |
|---|---|
| Screen ID | T-45 |
| Actor | Teacher |
| Purpose | Manage teacher account security and settings |
| Entry point | Teacher Settings |
| Primary content | Account profile, active sessions, language |
| Secondary content | Security events, password/session controls |
| Primary CTA | Save settings |
| Secondary CTA | Logout; revoke sessions |
| Disabled actions | Revoke disabled if no other sessions |
| State badges | Current device, Active session |
| Loading state | Account skeleton |
| Empty state | No other sessions |
| Error state | Could not update settings |
| Permission-denied state | Auth required |
| Relevant API endpoint(s) | `POST /auth/logout`, `POST /auth/revoke-sessions`, teacher profile endpoints |
| Backend state represented | Auth sessions, teacher user profile |
| Event generated by action | `SECURITY_EVENT` for session/security actions |
| Idempotency requirement | Recommended for revoke sessions |
| Navigation destination | Login, Dashboard |
| Sensitive-data visibility rules | Never expose raw tokens |

---

# 6. Admin / OPS Wireframes

---

## A-46 — Admin Dashboard

```text
[Admin Dashboard]
Cards:
Pending verifications
Open disputes
Payment issues
Refunds pending
Payouts eligible
Security alerts
[Queues]
```

| Field | Specification |
|---|---|
| Screen ID | A-46 |
| Actor | Admin/OPS/SUPPORT scoped |
| Purpose | Operational overview of marketplace health |
| Entry point | Admin login |
| Primary content | Queue counts and alerts |
| Secondary content | Recent critical events; filters by role scope |
| Primary CTA | Open highest-priority queue |
| Secondary CTA | View events/security |
| Disabled actions | Actions disabled if role lacks authority |
| State badges | High priority, Safety, Payment issue, Payout blocked |
| Loading state | Dashboard skeleton |
| Empty state | “No active operational issues.” |
| Error state | Could not load admin dashboard |
| Permission-denied state | Admin/OPS/SUPPORT role required |
| Relevant API endpoint(s) | Admin list endpoints: bookings, payments, disputes, refunds, payouts, events |
| Backend state represented | Operational queue states |
| Event generated by action | Reads none; sensitive access must audit |
| Idempotency requirement | Not applicable |
| Navigation destination | Verification Queue, Dispute Queue, Refund Queue, Payout Queue |
| Sensitive-data visibility rules | Role-scoped; sensitive access warning where applicable |

---

## A-47 — Teacher Verification Queue

```text
[Verification Queue]
Teacher
Type
Submitted at
Priority/status
[Review]
```

| Field | Specification |
|---|---|
| Screen ID | A-47 |
| Actor | OPS/Admin |
| Purpose | List pending teacher verifications |
| Entry point | Admin Dashboard → Teacher Verification |
| Primary content | Pending verification records |
| Secondary content | Filters by type/status/date |
| Primary CTA | Review |
| Secondary CTA | Assign/filter |
| Disabled actions | Approve/reject disabled from list unless detail reviewed |
| State badges | Submitted, Approved, Rejected, Expired |
| Loading state | Queue skeleton |
| Empty state | “No pending verifications.” |
| Error state | Could not load queue |
| Permission-denied state | SUPPORT cannot approve unless authorized |
| Relevant API endpoint(s) | `GET /admin/teachers/pending-verification` |
| Backend state represented | `teacher_verifications.status` |
| Event generated by action | None for list; sensitive document access later audits |
| Idempotency requirement | Not applicable |
| Navigation destination | Teacher Verification Detail |
| Sensitive-data visibility rules | No document preview in list; detail access audited |

---

## A-48 — Teacher Verification Detail

```text
[Verification Detail]
Teacher profile
Verification type
Submitted metadata
[Access document] This access will be logged.
[Approve]
[Reject]
Reason/note
```

| Field | Specification |
|---|---|
| Screen ID | A-48 |
| Actor | Admin/authorized OPS |
| Purpose | Review teacher verification and documents |
| Entry point | Verification Queue → Review |
| Primary content | Teacher details, verification metadata, document access action |
| Secondary content | Review notes, rejection reason field |
| Primary CTA | Approve |
| Secondary CTA | Reject; request more info if policy allows later |
| Disabled actions | Approve/reject disabled without required reason/document review policy |
| State badges | Submitted, Approved, Rejected |
| Loading state | Loading verification detail |
| Empty state | Not applicable |
| Error state | Document unavailable; verification already resolved |
| Permission-denied state | ADMIN/authorized OPS required |
| Relevant API endpoint(s) | `GET /admin/teachers/:id/verifications`, `POST /admin/teachers/:id/verify`, `POST /admin/teachers/:id/reject` |
| Backend state represented | Verification status and teacher verification status |
| Event generated by action | `TEACHER_VERIFIED`, `TEACHER_REJECTED`, `ADMIN_ACTION`, document access `SECURITY_EVENT` |
| Idempotency requirement | Recommended for approve/reject |
| Navigation destination | Verification Queue, Teacher Profile admin view |
| Sensitive-data visibility rules | Must show “This access will be logged”; secure document access only |

---

## A-49 — Booking Monitoring

```text
[Bookings]
Filters: status, date, teacher, parent
Booking row:
  Status
  Payment
  Session
  Dispute overlay
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-49 |
| Actor | SUPPORT/OPS/Admin scoped |
| Purpose | Monitor bookings and operational issues |
| Entry point | Admin Dashboard → Bookings |
| Primary content | Booking list with linked payment/session/dispute state |
| Secondary content | Filters/search; timeline summary |
| Primary CTA | Open booking |
| Secondary CTA | Export/reconcile if policy later; MVP omit |
| Disabled actions | Direct status mutation disabled |
| State badges | Held, Payment pending, Booked, Completed, Cancelled, Expired, Dispute overlay |
| Loading state | Booking table skeleton |
| Empty state | “No bookings match filters.” |
| Error state | Query too broad or failed |
| Permission-denied state | Role-scoped access |
| Relevant API endpoint(s) | `GET /admin/bookings`, `GET /bookings/:id` admin scoped |
| Backend state represented | Booking/payment/session/dispute overlay |
| Event generated by action | Read none; sensitive drilldown may audit based on scope |
| Idempotency requirement | Not applicable |
| Navigation destination | Payment Monitoring, Dispute Detail, Booking detail |
| Sensitive-data visibility rules | Minimize minor data; show only operationally necessary student context |

---

## A-50 — Payment Monitoring

```text
[Payments]
Filters: status/provider/date
Payment row:
  Amount
  Provider
  Status
  Booking
  Refund status
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-50 |
| Actor | OPS/Admin; SUPPORT limited/redacted |
| Purpose | Monitor payments, failures, late payments, refund state |
| Entry point | Admin Dashboard → Payments |
| Primary content | Payment table with status and booking link |
| Secondary content | Provider transaction reference, redacted by default |
| Primary CTA | Open payment detail |
| Secondary CTA | View refund timeline; reconcile issue |
| Disabled actions | Direct payment status mutation disabled |
| State badges | Pending, Confirmed, Failed, Refund pending, Partially refunded, Refunded, Reconciliation required |
| Loading state | Payment table skeleton |
| Empty state | “No payments match filters.” |
| Error state | Could not load payments |
| Permission-denied state | OPS/Admin for full details; SUPPORT redacted |
| Relevant API endpoint(s) | `GET /admin/payments`, `GET /admin/payments/:id`, `GET /payments/:id` scoped |
| Backend state represented | Payment/refund/provider event summaries |
| Event generated by action | Sensitive payload access must generate audit/security event |
| Idempotency requirement | Not applicable for read |
| Navigation destination | Refund Detail, Event Ledger, Booking Monitoring |
| Sensitive-data visibility rules | Raw provider payload hidden; access logged if opened |

---

## A-51 — Refund Queue

```text
[Refund Queue]
Tabs: Requested / Approved / Provider pending / Failed / Rejected / Cancelled / Succeeded
Refund row:
  Payment
  Amount
  Status
  Reason
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-51 |
| Actor | OPS/Admin |
| Purpose | Monitor refund lifecycle states |
| Entry point | Admin Dashboard → Refunds |
| Primary content | Refunds grouped by lifecycle state |
| Secondary content | Filters by provider/status/date/dispute |
| Primary CTA | Open refund |
| Secondary CTA | Bulk filters only; no bulk approval in MVP unless policy approved |
| Disabled actions | Financial actions disabled for SUPPORT |
| State badges | Requested, Approved, Provider pending, Succeeded, Failed, Rejected, Cancelled |
| Loading state | Refund queue skeleton |
| Empty state | “No refunds pending.” |
| Error state | Could not load refunds |
| Permission-denied state | OPS/Admin required |
| Relevant API endpoint(s) | `GET /admin/refunds` or refund summaries via admin payments/disputes per API patch |
| Backend state represented | `refunds.status` |
| Event generated by action | None for queue read; sensitive access may audit |
| Idempotency requirement | Not applicable |
| Navigation destination | Refund Detail, Refund Reconciliation |
| Sensitive-data visibility rules | Provider payload hidden by default |

---

## A-52 — Refund Detail

```text
[Refund Detail]
Status timeline
Payment/booking/dispute links
Requested amount
Approved amount
Teacher/platform allocation
Provider/reconciliation proof status
[Approve]
[Reject]
[Submit to provider]
[Reconcile]
[Cancel]
```

| Field | Specification |
|---|---|
| Screen ID | A-52 |
| Actor | OPS/Admin |
| Purpose | Review and operate refund lifecycle |
| Entry point | Refund Queue, Dispute Detail, Payment Monitoring |
| Primary content | Refund lifecycle, amount, allocation, reason, linked entities |
| Secondary content | Provider event summary, reconciliation summary, audit trail link |
| Primary CTA | Context-dependent: Approve, Submit to provider, Reconcile |
| Secondary CTA | Reject, Cancel, View dispute/payment |
| Disabled actions | PAYMENT_REFUNDED label disabled until SUCCEEDED; approve disabled if allocation invalid |
| State badges | Requested, Approved, Provider pending, Succeeded, Failed, Rejected, Cancelled |
| Loading state | Refund detail skeleton |
| Empty state | Not applicable |
| Error state | Invalid state, over-refund risk, allocation mismatch |
| Permission-denied state | OPS/Admin required; ADMIN for overrides |
| Relevant API endpoint(s) | `POST /payments/:id/refund`, `POST /admin/refunds/:id/reconcile`, refund read endpoint/response |
| Backend state represented | Refund state machine, payment refund summary, allocation |
| Event generated by action | `REFUND_APPROVED`, `REFUND_REJECTED`, `REFUND_CANCELLED`, `REFUND_PROVIDER_SUBMITTED`, `REFUND_SUCCEEDED/FAILED`, `ADMIN_ACTION` |
| Idempotency requirement | Required for refund commands |
| Navigation destination | Refund Reconciliation, Payment Monitoring, Dispute Detail |
| Sensitive-data visibility rules | Provider proof access is audited; raw payload hidden by default |

---

## A-53 — Refund Reconciliation

```text
[Refund Reconciliation]
This access/action will be logged.
Refund summary
Reconciliation source
Reference
Reconciled at
Reason
Supporting evidence
[Mark succeeded]
[Mark failed]
```

| Field | Specification |
|---|---|
| Screen ID | A-53 |
| Actor | OPS/Admin |
| Purpose | Record manual/provider reconciliation result |
| Entry point | Refund Detail → Reconcile |
| Primary content | Reconciliation form fields |
| Secondary content | Provider event history, payment/refund IDs |
| Primary CTA | Mark succeeded / Mark failed |
| Secondary CTA | Cancel; back to refund detail |
| Disabled actions | Submit disabled without source, reference, timestamp; manual/admin source requires authenticated admin/OPS user |
| State badges | Reconciliation required, Manual reconciliation, Admin override |
| Loading state | “Saving reconciliation…” |
| Empty state | Not applicable |
| Error state | Missing proof, invalid state, insufficient permission |
| Permission-denied state | SUPPORT cannot reconcile; ADMIN required for admin override |
| Relevant API endpoint(s) | `POST /admin/refunds/:id/reconcile` or equivalent RefundService command |
| Backend state represented | Refund `SUCCEEDED` or `FAILED` through reconciliation proof |
| Event generated by action | `ADMIN_ACTION`, `REFUND_SUCCEEDED`/`REFUND_FAILED`, `PAYMENT_REFUNDED`/`PAYMENT_PARTIALLY_REFUNDED` only on success |
| Idempotency requirement | Required |
| Navigation destination | Refund Detail, Dispute Detail, Payment Monitoring |
| Sensitive-data visibility rules | Must show “This access/action will be logged.” Supporting evidence access audited |

---

## A-54 — Dispute Queue

```text
[Disputes]
Tabs: Open / Under review / Resolved / Rejected / Cancelled
Priority
Category
Safety flag
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-54 |
| Actor | SUPPORT/OPS/Admin scoped |
| Purpose | Triage disputes and safety issues |
| Entry point | Admin Dashboard → Disputes |
| Primary content | Dispute rows with priority/category/status |
| Secondary content | Filters by safety, payment, no-show, report issue |
| Primary CTA | Open dispute |
| Secondary CTA | Assign/filter |
| Disabled actions | Resolve disabled from list without detail review |
| State badges | Open, Under review, Safety, Resolved, Rejected, Cancelled |
| Loading state | Dispute queue skeleton |
| Empty state | “No open disputes.” |
| Error state | Could not load disputes |
| Permission-denied state | Role-scoped access; SUPPORT limited |
| Relevant API endpoint(s) | `GET /admin/disputes`, `GET /disputes/:id` admin scoped |
| Backend state represented | `disputes.status`, priority/category |
| Event generated by action | None for list |
| Idempotency requirement | Not applicable |
| Navigation destination | Dispute Detail |
| Sensitive-data visibility rules | Safety/minor data minimized; sensitive views audited |

---

## A-55 — Dispute Detail

```text
[Dispute Detail]
Status overlay
Booking/session/payment factual states
Evidence
Event timeline
Resolution actions
[Resolve]
[Approve refund]
[Reject]
[Escalate safety]
```

| Field | Specification |
|---|---|
| Screen ID | A-55 |
| Actor | OPS/Admin; SUPPORT limited |
| Purpose | Resolve dispute without overwriting factual states |
| Entry point | Dispute Queue |
| Primary content | Dispute details, linked booking/session/payment/report, evidence |
| Secondary content | Event ledger timeline, refund/payout impact |
| Primary CTA | Resolve dispute |
| Secondary CTA | Approve refund, reject, escalate, request info |
| Disabled actions | High-risk financial/safety actions disabled for SUPPORT |
| State badges | Dispute open overlay; booking/session factual states remain visible |
| Loading state | Dispute detail skeleton |
| Empty state | Not applicable |
| Error state | Dispute already resolved; invalid action |
| Permission-denied state | Role/authority required |
| Relevant API endpoint(s) | `POST /admin/disputes/:id/resolve`, `POST /payments/:id/refund` if refund resolution |
| Backend state represented | Dispute overlay, refund/payout side effects |
| Event generated by action | `DISPUTE_RESOLVED`, `ADMIN_ACTION`, refund events if applicable |
| Idempotency requirement | Required if refund action; recommended otherwise |
| Navigation destination | Refund Detail, Payout Queue, Event Ledger |
| Sensitive-data visibility rules | Sensitive evidence access must audit; minor data minimized |

---

## A-56 — Payout Eligible Queue

```text
[Payout Eligible Queue]
Teacher
Sessions
Gross payable
Refund exposure
Deductions
Net payable
Blocked reason
[Process payout]
```

| Field | Specification |
|---|---|
| Screen ID | A-56 |
| Actor | OPS/Admin |
| Purpose | Review payout eligibility before processing |
| Entry point | Admin Dashboard → Payouts |
| Primary content | Eligible/blocked payout candidates with net calculation |
| Secondary content | Refund exposure by status, report/dispute blockers |
| Primary CTA | Process payout |
| Secondary CTA | View teacher/session/refund details |
| Disabled actions | Process disabled if open dispute, full refund, net <= 0, missing report, waiting period not passed |
| State badges | Eligible, Blocked, Refund exposure, Dispute open, Report missing |
| Loading state | Payout queue skeleton |
| Empty state | “No eligible payouts.” |
| Error state | Could not load payout queue |
| Permission-denied state | OPS/Admin only; SUPPORT no processing |
| Relevant API endpoint(s) | `GET /admin/payouts`, `POST /admin/payouts/process` |
| Backend state represented | Payout eligibility, refund exposure, net teacher payable |
| Event generated by action | `PAYOUT_ELIGIBLE`, later `PAYOUT_PROCESSED`, `ADMIN_ACTION` |
| Idempotency requirement | Required for processing |
| Navigation destination | Payout Processing, Payout Failure, Recovery/Adjustment |
| Sensitive-data visibility rules | Show operational financial data; raw parent payment/provider payload hidden |

---

## A-57 — Payout Processing

```text
[Process Payout]
Batch summary
Teacher
Net payable
Included sessions
Idempotency-safe command
[Confirm process]
```

| Field | Specification |
|---|---|
| Screen ID | A-57 |
| Actor | OPS/Admin |
| Purpose | Process payout safely with idempotency |
| Entry point | Payout Eligible Queue → Process |
| Primary content | Batch/session breakdown and net payable |
| Secondary content | Warning that eligibility will be rechecked |
| Primary CTA | Confirm process |
| Secondary CTA | Cancel |
| Disabled actions | Confirm disabled if eligibility stale/changed |
| State badges | Eligible, Processing, Paid, Failed |
| Loading state | “Processing payout…” |
| Empty state | Not applicable |
| Error state | Provider failure, eligibility changed, duplicate payout item |
| Permission-denied state | OPS/Admin only |
| Relevant API endpoint(s) | `POST /admin/payouts/process` |
| Backend state represented | Payout `ELIGIBLE → PROCESSING → PAID/FAILED` |
| Event generated by action | `ADMIN_ACTION`, `PAYOUT_PROCESSED` on success |
| Idempotency requirement | Required |
| Navigation destination | Payout detail, Payout Failure, Teacher payout view |
| Sensitive-data visibility rules | No unnecessary parent/student details |

---

## A-58 — Payout Failure

```text
[Payout Failed]
Provider/reference
Failure reason
Affected teacher/sessions
[Retry safely]
[Cancel payout]
[View audit]
```

| Field | Specification |
|---|---|
| Screen ID | A-58 |
| Actor | OPS/Admin |
| Purpose | Handle provider payout failure without duplicating payout |
| Entry point | Payout Processing failure, admin notification |
| Primary content | Failure reason, payout batch, provider reference if safe |
| Secondary content | Retry/cancel policy, ledger status |
| Primary CTA | Retry safely |
| Secondary CTA | Cancel payout; view audit |
| Disabled actions | Retry disabled if payout not in retryable failed state |
| State badges | Failed, Retryable, Not retryable |
| Loading state | Loading failure details |
| Empty state | Not applicable |
| Error state | Could not load failure details |
| Permission-denied state | OPS/Admin only |
| Relevant API endpoint(s) | Payout admin endpoints; `POST /admin/payouts/process` for retry if architecture permits same payout retry |
| Backend state represented | Payout `FAILED`, retry/cancel authority |
| Event generated by action | `ADMIN_ACTION`; payout failure metadata |
| Idempotency requirement | Required for retry/process |
| Navigation destination | Payout Queue, Event Ledger |
| Sensitive-data visibility rules | Provider details redacted unless authorized; access audited if sensitive |

---

## A-59 — Recovery / Adjustment

```text
[Recovery / Adjustment]
Original paid payout
Refund reference
Teacher recoverable
Platform absorbed amount
Future payout offset
[Create adjustment]
[View ledger]
```

| Field | Specification |
|---|---|
| Screen ID | A-59 |
| Actor | OPS/Admin |
| Purpose | Create/view post-payout recovery after later refund |
| Entry point | Refund Detail, Payout Detail, Dispute resolution |
| Primary content | Original payout, refund, teacher/platform allocation, recovery balance |
| Secondary content | Ledger adjustment summary; future offset plan |
| Primary CTA | Create adjustment/recovery |
| Secondary CTA | View ledger/audit |
| Disabled actions | Editing old paid payout disabled |
| State badges | Paid payout immutable, Recovery pending, Platform absorbed |
| Loading state | Adjustment skeleton |
| Empty state | “No recovery adjustments.” |
| Error state | Invalid allocation, old payout not paid, duplicate adjustment |
| Permission-denied state | OPS/Admin only; ADMIN for exceptional overrides |
| Relevant API endpoint(s) | Admin payout/refund/ledger adjustment endpoints as implementation-level commands; no old payout update |
| Backend state represented | Ledger adjustment/recovery, not payout mutation |
| Event generated by action | `ADMIN_ACTION`; ledger adjustment event metadata |
| Idempotency requirement | Required for adjustment creation |
| Navigation destination | Event Ledger, Payout Detail, Refund Detail |
| Sensitive-data visibility rules | Financial/admin-only; access logged where sensitive |

---

## A-60 — Event Ledger

```text
[Event Ledger]
Filters: entity type/id, event type, actor, request ID
Event row:
  timestamp
  actor
  event
  entity
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-60 |
| Actor | OPS/Admin |
| Purpose | Audit critical business events |
| Entry point | Admin Dashboard, entity details |
| Primary content | Event table with filters |
| Secondary content | Request ID, idempotency key, metadata summary |
| Primary CTA | Open event detail |
| Secondary CTA | Copy request ID; filter by entity |
| Disabled actions | Edit/delete disabled; event ledger immutable |
| State badges | Admin action, Security event, Payment, Booking, Refund |
| Loading state | Event table skeleton |
| Empty state | “No events match filters.” |
| Error state | Query too broad or failed |
| Permission-denied state | OPS/Admin only; SUPPORT limited if allowed |
| Relevant API endpoint(s) | `GET /admin/events` |
| Backend state represented | Append-only `event_ledger` |
| Event generated by action | Sensitive access to event detail may itself audit depending policy |
| Idempotency requirement | Not applicable |
| Navigation destination | Related booking/payment/refund/dispute |
| Sensitive-data visibility rules | Redact sensitive metadata; raw payload not shown |

---

## A-61 — Security Events

```text
[Security Events]
Login failures
Suspicious activity
Admin access
Document access
Sensitive payload access
[Open]
```

| Field | Specification |
|---|---|
| Screen ID | A-61 |
| Actor | ADMIN primarily; OPS limited if policy allows |
| Purpose | Review security-sensitive events |
| Entry point | Admin Dashboard → Security Events |
| Primary content | Security event list with severity |
| Secondary content | IP/user agent, user, entity, timestamp |
| Primary CTA | Open security event |
| Secondary CTA | Filter by user/severity |
| Disabled actions | Edit/delete disabled |
| State badges | Severity 1–5, Admin access, Document access, Suspicious |
| Loading state | Security event skeleton |
| Empty state | “No security events match filters.” |
| Error state | Could not load security events |
| Permission-denied state | ADMIN required for full access |
| Relevant API endpoint(s) | `GET /admin/security-events` |
| Backend state represented | `security_events` |
| Event generated by action | Sensitive viewing may audit depending policy |
| Idempotency requirement | Not applicable |
| Navigation destination | User detail, Audit Trail |
| Sensitive-data visibility rules | Access is sensitive and role-limited |

---

## A-62 — Sensitive Document / Provider Payload Access

```text
[Access Sensitive Data]
This access will be logged.
Reason required
Entity summary
[Open secure view]
[Cancel]
```

| Field | Specification |
|---|---|
| Screen ID | A-62 |
| Actor | ADMIN/authorized OPS |
| Purpose | Controlled audited access to sensitive documents or provider payload summaries |
| Entry point | Verification Detail, Payment Monitoring, Refund Detail |
| Primary content | Warning, reason field, entity summary |
| Secondary content | Access policy and audit notice |
| Primary CTA | Open secure view |
| Secondary CTA | Cancel |
| Disabled actions | Open disabled without reason/permission |
| State badges | Sensitive, Logged access |
| Loading state | “Preparing secure access…” |
| Empty state | No document/payload available |
| Error state | Access denied, secure link expired, payload unavailable |
| Permission-denied state | ADMIN/authorized OPS only |
| Relevant API endpoint(s) | Secure document/payload access endpoint as admin implementation detail |
| Backend state represented | Verification document metadata, redacted provider payload references |
| Event generated by action | `SECURITY_EVENT`, `ADMIN_ACTION` as appropriate |
| Idempotency requirement | Not applicable for read access |
| Navigation destination | Secure view, Verification Detail, Payment/Refund Detail |
| Sensitive-data visibility rules | Must show “This access will be logged.” Never expose unrestricted/raw payload by default |

---

## A-63 — User Suspension

```text
[User Action]
User summary
Reason
Impact warning
[ Suspend user ]
[ Reactivate user ]
```

| Field | Specification |
|---|---|
| Screen ID | A-63 |
| Actor | ADMIN |
| Purpose | Suspend/reactivate user with audit trail |
| Entry point | Admin user detail, safety dispute resolution |
| Primary content | User summary, role, reason, impact warning |
| Secondary content | Related disputes/security events |
| Primary CTA | Suspend / Reactivate |
| Secondary CTA | Cancel |
| Disabled actions | Action disabled without reason; SUPPORT/OPS disabled unless policy allows special case |
| State badges | Active, Suspended, Deleted |
| Loading state | “Applying account action…” |
| Empty state | Not applicable |
| Error state | Invalid state, insufficient permission |
| Permission-denied state | ADMIN only |
| Relevant API endpoint(s) | `POST /admin/users/:id/suspend`, `POST /admin/users/:id/reactivate` |
| Backend state represented | `users.status` |
| Event generated by action | `ADMIN_ACTION`, possibly `SECURITY_EVENT` |
| Idempotency requirement | Recommended |
| Navigation destination | User detail, Dispute Detail, Security Events |
| Sensitive-data visibility rules | Reason and account action are admin-only; audit required |

---

## A-64 — Audit Trail

```text
[Audit Trail]
Entity timeline
Business events
Admin actions
Security events
Provider events summary
[Filter]
```

| Field | Specification |
|---|---|
| Screen ID | A-64 |
| Actor | OPS/Admin |
| Purpose | Unified timeline for an entity investigation |
| Entry point | Booking/payment/refund/dispute/payout detail |
| Primary content | Chronological event timeline |
| Secondary content | Request IDs, actors, entity links |
| Primary CTA | Filter timeline |
| Secondary CTA | Open related event/entity |
| Disabled actions | Edit/delete disabled |
| State badges | Payment, Refund, Dispute, Admin action, Security |
| Loading state | Audit timeline skeleton |
| Empty state | “No audit events found for this entity.” |
| Error state | Could not load audit trail |
| Permission-denied state | OPS/Admin scoped; sensitive entries redacted based on role |
| Relevant API endpoint(s) | `GET /admin/events`, `GET /admin/security-events` |
| Backend state represented | `event_ledger`, `security_events`, provider event summaries if exposed |
| Event generated by action | Sensitive audit access may audit depending policy |
| Idempotency requirement | Not applicable |
| Navigation destination | Event Ledger, Security Events, related entity detail |
| Sensitive-data visibility rules | Redact sensitive metadata; raw payload not exposed by default |

---

# 7. Cross-Flow Navigation Map

## Parent happy path

```text
P-01 Login/Register
  ↓
P-02 Dashboard
  ↓
P-04 Create Student
  ↓
P-08 Teacher Search
  ↓
P-09 Matching Results
  ↓
P-10 Teacher Trust Profile
  ↓
P-11 Teacher Availability
  ↓
P-12 Booking Hold
  ↓
P-13 Checkout
  ↓
P-14 Payment Pending
  ↓
P-15 Payment Success
  ↓
P-18 Session Detail
  ↓
P-19 Session Report
  ↓
P-20 Review
  ↓
Repeat booking
```

## Parent refund/dispute path

```text
P-17 Booking Detail / P-18 Session Detail
  ↓
P-23 Dispute
  ↓
P-22 Refund Timeline
  ↓
P-24 Refund Rejected
or P-25 Refund Cancelled
or P-26 Refund Completed
```

## Teacher happy path

```text
T-29 Onboarding
  ↓
T-32 Subjects & Pricing
  ↓
T-30 Verification
  ↓
T-33 Availability
  ↓
T-34 Bookings
  ↓
T-35 Session Detail
  ↓
T-36 Attendance
  ↓
T-37 Session Report
  ↓
T-39 Earnings
  ↓
T-40 Payout Detail
```

## Admin financial operations path

```text
A-46 Dashboard
  ↓
A-50 Payment Monitoring
  ↓
A-51 Refund Queue
  ↓
A-52 Refund Detail
  ↓
A-53 Refund Reconciliation
  ↓
A-56 Payout Eligible Queue
  ↓
A-57 Payout Processing
  ↓
A-59 Recovery / Adjustment, if needed
  ↓
A-60 Event Ledger / A-64 Audit Trail
```

---

# 8. State-to-Screen Mapping

| Backend state/domain | User-facing screen(s) |
|---|---|
| Booking `HELD` | P-12 Booking Hold, P-17 Booking Detail |
| Booking `PAYMENT_PENDING` | P-14 Payment Pending, P-17 Booking Detail |
| Booking `BOOKED` | P-15 Payment Success, P-17 Booking Detail, P-18 Session Detail |
| Booking `COMPLETED` | P-17, P-18, P-19, P-20 |
| Booking `CANCELLED` | P-17, P-21 if refund/payment involved |
| Booking `EXPIRED` | P-12, P-16, P-22 if late payment/refund |
| Payment `INITIATED/PENDING` | P-14 |
| Payment `CONFIRMED` | P-15, P-21 |
| Payment `FAILED` | P-16 |
| Payment `REFUND_PENDING` | P-22 |
| Payment `PARTIALLY_REFUNDED` | P-21, P-22, P-26, T-41 |
| Payment `REFUNDED` | P-21, P-22, P-26 |
| Refund `REQUESTED` | P-22, A-51, A-52 |
| Refund `APPROVED` | P-22, A-52, T-41 if payout exposure |
| Refund `PROVIDER_PENDING` | P-22, A-52, T-41 |
| Refund `SUCCEEDED` | P-26, A-52, T-41/T-42 |
| Refund `FAILED` | P-22, A-52 |
| Refund `REJECTED` | P-24 |
| Refund `CANCELLED` | P-25 |
| Session `SCHEDULED` | P-18, T-35 |
| Session `STARTED` | P-18, T-35 |
| Session `COMPLETED` | P-18, P-19, T-37 |
| Session `NO_SHOW_STUDENT` | P-18, T-35, T-36, A-55 |
| Session `NO_SHOW_TEACHER` | P-18, A-55 |
| Dispute `OPEN` | P-23, A-54, A-55 |
| Dispute `UNDER_REVIEW` | P-23, A-55 |
| Dispute `RESOLVED/REJECTED/CANCELLED` | P-23, A-55 |
| Payout `ELIGIBLE` | T-39, T-40, A-56 |
| Payout `PROCESSING` | T-40, A-57 |
| Payout `PAID` | T-40, T-42 if later recovery |
| Payout `FAILED` | T-40, A-58 |
| Event Ledger | A-60, A-64 |
| Security Events | A-61 |

---

# 9. Permission Visibility Matrix

| Data/action | Parent | Teacher | Support | OPS | Admin |
|---|---|---|---|---|---|
| Own student profile | Full own | No, except permitted context | Limited | Limited | Audited access |
| Student Passport | Own only | Permission-scoped only | Limited | Limited | Audited access |
| Teacher Trust Profile | View public | Own/public | View | View | View |
| Teacher trust metrics edit | No | No | No | Metrics worker/admin path only | Controlled path only |
| Booking | Own | Assigned | Limited | Operational | Full scoped |
| Payment | Own redacted | Economic impact only | Limited redacted | Operational | Full audited |
| Raw provider payload | No | No | No | Limited audited if allowed | Audited |
| Verification documents | No | Own metadata only | No | Audited limited | Audited |
| Session report | Own child | Own session report | Limited | Operational | Audited |
| Review creation | Own eligible session | No | No | No | Not normal path |
| Dispute creation | Own participant | Own participant | Assist only | Yes | Yes |
| Refund approval | No | No | No | Policy-limited | Yes |
| Refund reconciliation | No | No | No | Policy-limited | Yes |
| Payout processing | No | No | No | Yes | Yes |
| User suspension | No | No | No | No | Yes |
| Event Ledger | No | No | No | Scoped | Full scoped |
| Security Events | Own account events if exposed | Own account events if exposed | No | Limited | Full |

---

# 10. Financial UX Rules

1. Never show “Refunded” before refund `SUCCEEDED`.
2. `APPROVED` means platform approved internally, not money returned.
3. `PROVIDER_PENDING` means refund submitted/processing, not money returned.
4. `FAILED`, `REJECTED`, and `CANCELLED` need distinct labels.
5. Late payment after expiry shows payment received but booking not confirmed.
6. Late payment after expiry does not show scheduled session.
7. Refund exposure affects payout from `APPROVED`, `PROVIDER_PENDING`, and `SUCCEEDED`.
8. Payout UI must show gross, refund exposure, deductions, and net payable.
9. Paid payout records are immutable in UX.
10. Later refunds after paid payout appear as separate adjustment/recovery entries.
11. Teachers see economic impact, not raw parent payment/provider details.
12. Admin sensitive financial access must show “This access will be logged.”

---

# 11. Error / Loading / Empty-State Rules

## Loading states

- Use skeletons for dashboards/lists.
- Use action-specific labels for state changes:
  - “Reserving your session…”
  - “Starting payment…”
  - “Waiting for payment confirmation…”
  - “Saving report…”
  - “Processing refund…”
  - “Processing payout…”

## Empty states

Empty states must suggest the next safe action:

```text
No students → Add student
No teachers found → Adjust filters
No slots → Try another date/teacher
No reports → Reports appear after completed sessions
No payouts → Completed reported sessions will appear here
```

## Error states

Error messages must be safe and non-leaky:

```text
You do not have access to this resource.
The selected slot is no longer available.
Payment confirmation is still pending.
This action is not available for the current state.
```

Do not reveal other users’ data.

## Permission denied states

Show generic messages:

```text
You do not have access to this student profile.
You do not have access to this booking.
This action requires admin permission.
Only the assigned teacher can start this session.
```

---

# 12. Open-Policy Dependency Map

| Policy decision | Affected screens | Placeholder |
|---|---|---|
| Booking hold duration | P-12, P-13 | `[POLICY DECISION REQUIRED]` |
| Payment checkout timeout | P-14, P-16 | `[POLICY DECISION REQUIRED]` |
| Late-payment auto-refund vs OPS review | P-22, A-52, A-53 | `[POLICY DECISION REQUIRED]` |
| No-show grace periods | T-36, P-18, A-55 | `[POLICY DECISION REQUIRED]` |
| Parent dispute window | P-23, A-55, T-39 | `[POLICY DECISION REQUIRED]` |
| Payout delay | T-39, A-56 | `[POLICY DECISION REQUIRED]` |
| Refund allocation teacher/platform | A-52, A-56, T-41 | `[POLICY DECISION REQUIRED]` |
| Review eligibility after partial refund | P-20 | `[POLICY DECISION REQUIRED]` |
| Notification channels | P-27, T-44 | `[POLICY DECISION REQUIRED]` |
| Arabic/French terminology | All user-facing screens | `[POLICY DECISION REQUIRED]` |

---

# 13. UX Consistency Checklist

## Architecture consistency

- [ ] No screen creates arbitrary status updates.
- [ ] Every CTA maps to approved backend authority.
- [ ] Booking/payment/session states remain separate.
- [ ] Dispute appears as overlay, not factual state replacement.
- [ ] Late payment after expiry does not schedule session.
- [ ] Review appears only when backend eligibility is true.
- [ ] Payout processing appears only for OPS/Admin and eligible payouts.

## Financial consistency

- [ ] Refund states are distinct.
- [ ] “Refunded” appears only after `SUCCEEDED`.
- [ ] Refund `APPROVED` and `PROVIDER_PENDING` affect payout exposure.
- [ ] Net teacher payable comes from backend, not frontend-only calculation.
- [ ] Paid payout is immutable.
- [ ] Recovery/adjustment appears separately after later refund.

## Privacy consistency

- [ ] Student data minimized.
- [ ] Parent controls sharing permissions.
- [ ] Teacher sees only permitted context.
- [ ] Admin sensitive access says “This access will be logged.”
- [ ] Raw provider payload not exposed by default.
- [ ] Verification documents not public.

## Scope consistency

- [ ] No AI Tutor.
- [ ] No AI Matching.
- [ ] No session recording.
- [ ] No gamification.
- [ ] No subscriptions.
- [ ] No group classes.
- [ ] No institutional accounts.
- [ ] No predictive analytics.
- [ ] No public leaderboard.
- [ ] No paid ranking.
- [ ] No microservices.

---

# 14. Final Status

```text
Low-Fidelity Wireframes v1.0 Status: READY FOR REVIEW
```

Do not proceed to high-fidelity UI.

Do not proceed to frontend implementation.

Do not proceed to backend implementation.
