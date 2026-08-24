# EduTrust Algeria — MVP PRD v1.0

**Product:** EduTrust Algeria  
**Version:** MVP v0.1 / PRD v1.0  
**Market:** Algeria  
**Initial Wedge:** Algiers + Mathematics/Physics + Secondary/BAC + Verified Teachers  
**Product Type:** Education Marketplace + Trust & Transaction Infrastructure  
**Document Purpose:** Define the exact MVP product scope before moving to Database Schema, API Architecture, and implementation.

---

## 1. Strategic Definition

EduTrust is **not** merely a tutoring booking app.

EduTrust v0.1 is a narrow marketplace designed to validate whether Algerian parents are willing to:

> Discover a verified teacher → book a session → pay through/with the platform → complete a session → receive a report → submit a verified review → repeat booking.

The long-term strategic asset is the **Verified Session Graph**:

```text
Parent → Student → Teacher → Subject → Slot → Booking → Payment → Session → Report → Verified Review → Repeat Booking
```

After enough verified sessions, EduTrust becomes a trust, transaction, and educational data infrastructure for private education.

---

## 2. Core MVP Hypothesis

### Primary hypothesis

Parents in the Algerian private tutoring market will repeatedly use a digital platform if it gives them:

- Verified teachers
- Transparent trust signals
- Easy booking
- Reliable availability
- Payment records/protection
- Session tracking
- Structured educational reports
- Verified reviews
- Repeat-booking convenience

### The MVP does not prove

The MVP does **not** need to prove advanced AI, national expansion, subscriptions, group classes, or predictive analytics.

It only needs to prove the transaction loop:

```text
Search → Trust → Booking → Payment → Session → Report → Review → Repeat
```

---

## 3. MVP Scope Decision

### Initial niche

```text
Geography: Algiers / selected dense urban zones
Subjects: Mathematics and Physics
Levels: Secondary school / BAC-focused tutoring
Teacher type: Verified private teachers
Session type: 1-to-1 tutoring
Modes: Online first or hybrid, with in-person support where operationally viable
Business model: Transaction commission
```

### Why niche-first

The MVP must create liquidity inside a small market.

Bad wedge:

```text
All Algeria + all subjects + all levels + all teacher types
```

Better wedge:

```text
Algiers + Math/Physics + Secondary/BAC + 30–50 verified teachers
```

The parent search experience must feel trustworthy and populated.

---

## 4. MVP Success Definition

EduTrust MVP succeeds if:

> Parents repeatedly book and complete paid tutoring sessions through the platform with verified teachers.

### Primary success metrics

| Metric | Target for Pilot | Why It Matters |
|---|---:|---|
| Verified teachers onboarded | 30–50 | Supply density |
| Parent pilot users | 100–300 | Demand test |
| Booking conversion | 20%+ of active searching parents | Marketplace trust |
| Completed sessions | 50–100+ | Real transaction validation |
| Repeat bookings | 30%+ of parents who completed one session | Retention/value |
| Session report completion | 80%+ | Anti-bypass value |
| Verified review rate | 40–60%+ | Trust graph creation |
| Cancellation rate | <10% | Reliability |
| Dispute rate | <3–5% | Operational trust |
| Off-platform leakage signal | Track manually first | Business model risk |

### Vanity metrics to ignore

- App downloads
- Registrations without bookings
- Social media followers
- Website visits without transaction intent
- Teacher profiles without availability

---

## 5. Core User Loop

The product must support this full loop reliably:

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
Booking
   ↓
Payment
   ↓
Session
   ↓
Session Report
   ↓
Verified Review
   ↓
Repeat Booking
```

If this loop works, EduTrust has a real marketplace foundation.

---

## 6. User Roles

### 6.1 Parent

Primary customer and payer.

Parent needs:

- Find qualified teachers
- Compare trust signals
- Book easily
- Pay securely or through a compliant payment workflow
- Track sessions
- Receive reports
- Review only after completed sessions
- Repeat book easily
- Access payment/session history
- Raise disputes if needed

### 6.2 Student

Educational beneficiary.

Student needs:

- Be connected to suitable teachers
- Attend sessions
- Build structured learning history
- Receive homework and progress notes
- Be protected by parental control and privacy rules

### 6.3 Teacher

Service provider.

Teacher needs:

- Create professional profile
- Get verified
- Show subjects, levels, price, and availability
- Receive bookings
- Manage sessions
- Submit reports
- Receive payouts
- Build verified reputation
- Track income and students

### 6.4 Admin / Operations

Trust, safety, verification, payment, and dispute operator.

Admin needs:

- Verify teachers
- Monitor bookings
- Monitor payments
- Manage disputes
- Moderate reviews
- Review audit/event logs
- Detect fraud patterns
- Support parents and teachers

---

## 7. MVP Functional Requirements

Priorities:

- **P0:** Must-have for MVP transaction loop
- **P1:** Important but can be simplified or manual
- **P2:** Later version, explicitly excluded from MVP build

---

# 8. Parent Product Requirements

## 8.1 Parent Account — P0

### Description

A parent can register, log in, and manage basic account information.

### Requirements

- Parent can create account using phone/email.
- Parent can log in securely.
- Parent can update name, phone/email, and preferred language.
- Parent account status can be active, suspended, or deleted.

### Acceptance criteria

- Parent can register and log in.
- Parent cannot access another parent’s children, bookings, reports, or payments.
- Sensitive actions are logged in Event Ledger.

---

## 8.2 Student Profile — P0

### Description

Parent creates a student profile used for matching, booking, reports, and future Student Passport.

### MVP fields

- First name or nickname
- Age or birth year
- Academic level
- School year
- Target subject
- Learning goal
- Preferred teaching mode
- Parent consent status

### Requirements

- Parent can create multiple student profiles.
- Student profile belongs to parent account.
- Student data must be minimized.
- Student profile must not expose unnecessary personal information to teachers.

### Acceptance criteria

- Parent can create and edit student profile.
- Teacher only sees student information needed for the session.
- All access to student profile is permission-controlled.

---

## 8.3 Teacher Search / Match — P0

### Description

Parent searches for teachers using filters and receives ranked recommendations.

### MVP approach

Use a **rule-based Matching Engine v0**, not complex AI.

### Parent inputs

- Subject
- Academic level
- Goal
- Budget
- Mode: online / in-person / hybrid
- Availability
- Location if in-person
- Preferred language

### Hard filters

Teacher must:

- Teach selected subject
- Teach selected academic level
- Have available slots
- Support selected teaching mode
- Be verified or accepted in MVP teacher pool
- Match budget range or be close enough to show as alternative

### Ranking factors

- Verified identity
- Verified qualifications
- Completed sessions
- Verified rating
- Attendance rate
- Cancellation rate
- Response time
- Price fit
- Availability fit
- Location fit
- Repeat booking rate, when enough data exists

### UI requirement

Do not show unexplained algorithmic numbers as the primary trust indicator.

Instead of:

```text
Teacher A — 94% Match
```

Show:

```text
Best Match
Why recommended:
✓ Teaches 2AS Mathematics
✓ Available Saturday afternoon
✓ Online sessions supported
✓ 238 verified sessions
✓ 97% attendance
✓ Within budget
```

### Acceptance criteria

- Parent can filter teachers.
- Parent sees explainable recommended results.
- Teachers without availability should not appear as immediately bookable.
- Ranking must not rely only on average star rating.

---

## 8.4 Teacher Trust Profile — P0

### Description

Teacher profile displays transparent trust signals based on verified data.

### Principle

Trust Profile is a **data product**, not a decorative profile section.

### MVP Trust Profile fields

```text
Teacher
├── verified_identity
├── verified_qualification
├── completed_sessions
├── attendance_rate
├── cancellation_rate
├── response_time
├── verified_rating
├── review_count
├── dispute_rate
└── repeat_booking_rate
```

### User-facing display

```text
Trust Profile

Identity
✓ Verified

Qualifications
✓ Verified

Verified sessions
238

Parent rating
4.8 / 5 from verified sessions

Attendance
97%

Cancellation
2%

Average response time
< 10 min
```

### Product rule

```text
Internal ranking score ≠ User-facing trust profile
```

EduTrust may use internal ranking logic, but parents should see understandable trust evidence.

### Acceptance criteria

- Only verified completed sessions contribute to ratings and reviews.
- Review count is displayed with rating.
- Trust data cannot be manually inflated by teacher.
- Admin can correct data only through auditable processes.

---

## 8.5 Booking Flow — P0

### Description

Parent selects an available teacher slot and creates a booking.

### Requirements

- Parent selects teacher, subject, student, date/time, mode.
- System checks slot availability.
- System holds slot temporarily during payment initiation.
- Booking expires if payment is not completed in time.
- Parent receives booking confirmation.

### Acceptance criteria

- Double booking must be prevented.
- Booking state and payment state must be separated.
- Parent can see upcoming bookings.
- Teacher can see upcoming bookings.
- Admin can monitor booking status.

---

## 8.6 Payment Flow — P0/P1 depending on provider readiness

### Description

Payment confirms the booking and creates auditable transaction records.

### Strategic note

Payment must be treated as a regulated financial workflow. EduTrust should use compliant payment infrastructure and obtain Algerian legal/accounting advice before production launch.

### MVP requirements

- Parent initiates payment.
- Platform records payment attempt.
- Payment provider confirms or rejects payment.
- Booking becomes confirmed only after payment confirmation or approved operational rule.
- Payment record is linked to booking.
- Ledger entries are created.
- Refund/dispute status can be tracked.

### Acceptance criteria

- Payment webhook or confirmation is idempotent.
- Payment cannot confirm wrong booking amount.
- Failed payment does not create confirmed booking.
- All payment status changes are logged.
- Manual payment handling, if used in pilot, must still be recorded in ledger.

---

## 8.7 Session Report Access — P0

### Description

After a completed session, parent receives a structured teacher report.

### Requirements

- Parent can view session report.
- Parent receives notification when report is available.
- Report is attached to session.
- Report contributes to Student Passport v0.

### Acceptance criteria

- Parent cannot review before session is completed.
- Parent can view reports for their own children only.
- Report creation event is logged.

---

## 8.8 Verified Review — P0

### Description

Parent can review teacher only after a verified completed session.

### Requirements

- Review requires completed session.
- One review per session.
- Review is linked to parent, teacher, student, and session.
- Review rating contributes to verified rating.
- Review text may be moderated.

### Acceptance criteria

- Arbitrary users cannot review teachers.
- Duplicate review for same session is blocked.
- Review sample size is shown.
- Suspicious review behavior can be flagged.

---

## 8.9 Repeat Booking — P0

### Description

Parent can quickly rebook a teacher after a successful session.

### Requirements

- Parent can rebook same teacher.
- System suggests available future slots.
- Repeat booking is tracked as a marketplace retention metric.

### Acceptance criteria

- Parent can complete repeat booking with fewer steps.
- Repeat booking rate is tracked per teacher and globally.

---

# 9. Teacher Product Requirements

## 9.1 Teacher Account & Profile — P0

### Description

Teacher creates a professional profile visible to parents after approval/verification.

### MVP fields

- Full name
- Profile photo
- Bio
- Subjects
- Academic levels
- Experience years
- Qualifications
- Teaching methodology
- Languages
- Teaching mode
- Location/service area
- Price per session
- Session duration

### Acceptance criteria

- Teacher profile cannot be publicly listed until minimum required fields are complete.
- Verification status is visible.
- Teacher cannot edit trust metrics directly.

---

## 9.2 Teacher Verification — P0/P1

### Description

EduTrust verifies teacher identity and optionally qualifications.

### Verification levels

```text
Level 0: Profile submitted
Level 1: Identity verified
Level 2: Qualifications reviewed
Level 3: Advanced verification, future
```

### MVP requirements

- Teacher submits verification information/documents.
- Admin reviews verification.
- Verification status appears on profile.
- Verification events are logged.

### Acceptance criteria

- Admin approval/rejection is auditable.
- Parents can distinguish verified vs unverified claims.
- Document access is restricted.

---

## 9.3 Availability Management — P0

### Description

Teacher defines available slots.

### Requirements

- Teacher can create slots.
- Teacher can block/unblock time.
- Teacher can define recurring availability.
- System prevents slot conflicts.
- Slot status is visible to search and booking engine.

### Acceptance criteria

- Parent cannot book unavailable slot.
- Teacher cannot create overlapping slots.
- Slot changes are logged.

---

## 9.4 Booking Management — P0

### Description

Teacher can view and manage bookings.

### Requirements

- Teacher sees booking requests/confirmed bookings.
- Depending on business rule, teacher may auto-accept or manually confirm.
- Teacher can cancel according to cancellation rules.
- Teacher receives notification for new bookings.

### Acceptance criteria

- Teacher cannot cancel without status change being logged.
- Cancellation affects cancellation rate if applicable.
- Parent is notified of booking changes.

---

## 9.5 Session Management — P0

### Description

Teacher manages session execution and completion.

### Requirements

- Teacher can mark session started.
- Teacher can mark session completed.
- Teacher can mark attendance/no-show.
- Session status feeds attendance/cancellation metrics.

### Acceptance criteria

- Session cannot be completed before scheduled time unless admin override exists.
- Attendance events are logged.
- Parent can see session completion status.

---

## 9.6 Structured Session Report — P0

### Description

Teacher submits a short structured report after session completion.

### MVP report fields

- Subject
- Date
- Duration
- Topics covered
- Skills practiced
- Student participation
- Teacher observations
- Homework
- Recommended revision
- Next learning objective
- Optional progress indicator

### UX requirement

Report completion should take under 2 minutes.

### Acceptance criteria

- Report is required before teacher payout eligibility, if operationally/legal feasible.
- Report is visible to parent.
- Report contributes to Student Passport v0.
- Report creation is logged.

---

## 9.7 Teacher Income View — P1

### Description

Teacher sees completed sessions, expected payouts, paid payouts, and pending amounts.

### Requirements

- Show session revenue.
- Show platform commission if applicable.
- Show payout status.
- Show transaction history.

### Acceptance criteria

- Teacher sees income records linked to completed sessions.
- Financial records match ledger entries.

---

# 10. Admin Product Requirements

## 10.1 Teacher Verification Dashboard — P0

Admin can:

- View pending teachers
- Review submitted data/documents
- Approve/reject verification
- Add reason for decision
- Update verification status

All actions must be logged.

---

## 10.2 Booking Monitoring — P0

Admin can:

- View all bookings
- Filter by status
- View payment status
- View session status
- Handle operational issues

---

## 10.3 Payment Monitoring — P0

Admin can:

- View payment attempts
- View confirmed payments
- View failed payments
- View refund status
- Reconcile provider transaction IDs

---

## 10.4 Dispute Management — P1

Admin can:

- Open dispute
- Assign dispute category
- Review booking/payment/session/report context
- Add resolution
- Trigger refund/adjustment process if applicable

---

## 10.5 Review Moderation — P1

Admin can:

- View reviews
- Flag abusive content
- Hide content if it violates policy
- Preserve rating if review is verified and not fraudulent

---

## 10.6 Event Ledger Viewer — P0/P1

Admin or technical operator can view important system events.

This is essential for:

- Auditability
- Debugging
- Fraud detection
- Trust metric computation
- Dispute resolution

---

# 11. Event Ledger

## 11.1 Principle

EduTrust must record important events from day one.

This is not only for payments. It is the foundation for:

- Auditability
- Fraud detection
- Analytics
- Trust Engine
- Debugging
- AI context later
- Regulatory and dispute evidence

## 11.2 MVP Event Types

```text
USER_REGISTERED
USER_LOGIN
STUDENT_PROFILE_CREATED
STUDENT_PROFILE_UPDATED
TEACHER_PROFILE_CREATED
TEACHER_PROFILE_UPDATED
TEACHER_VERIFICATION_SUBMITTED
TEACHER_VERIFIED
TEACHER_REJECTED
SLOT_CREATED
SLOT_UPDATED
SLOT_BLOCKED
BOOKING_CREATED
BOOKING_HELD
BOOKING_CONFIRMED
BOOKING_CANCELLED
PAYMENT_INITIATED
PAYMENT_CONFIRMED
PAYMENT_FAILED
PAYMENT_REFUNDED
SESSION_STARTED
SESSION_COMPLETED
SESSION_NO_SHOW
REPORT_CREATED
REVIEW_CREATED
DISPUTE_OPENED
DISPUTE_RESOLVED
REFUND_ISSUED
PAYOUT_ELIGIBLE
PAYOUT_PROCESSED
ADMIN_ACTION
SECURITY_EVENT
```

## 11.3 Event Ledger minimum fields

```text
event_id
actor_user_id
actor_role
event_type
entity_type
entity_id
metadata_json
ip_address_optional
user_agent_optional
created_at
```

## 11.4 Requirements

- Event logs should be append-only where possible.
- Sensitive metadata must be minimized.
- Admin actions must always be logged.
- Payment-related events must include idempotency references.

---

# 12. Student Passport v0

## 12.1 Principle

Student Passport must be built from structured data, not AI-generated assumptions.

Correct architecture:

```text
Session
   ↓
Topics
   ↓
Observation
   ↓
Homework
   ↓
Progress Event
   ↓
Student Passport
   ↓
AI Insights later
```

Not:

```text
AI chatbot text → student profile
```

## 12.2 MVP Student Passport fields

```text
Student
├── subjects studied
├── completed sessions
├── recent topics
├── teacher observations
├── homework assigned
├── homework completion status, if available
├── participation trend
├── recurring weaknesses
└── recent progress notes
```

## 12.3 MVP behavior

- Passport is viewable by parent.
- Passport is updated from session reports.
- Teacher access requires parent permission and only for relevant student/session context.
- Passport should be simple and structured.

## 12.4 Future behavior

AI may later summarize:

- Weakness patterns
- Topic mastery
- Progress trends
- Revision recommendations

But AI must sit on top of structured session data.

---

# 13. Booking State Machine

## 13.1 Booking states

```text
AVAILABLE
HELD
PAYMENT_PENDING
BOOKED
CANCELLED
COMPLETED
DISPUTED
REFUNDED
EXPIRED
```

## 13.2 Flow

```text
AVAILABLE
   ↓ parent selects slot
HELD
   ↓ payment initiated
PAYMENT_PENDING
   ↓ payment confirmed
BOOKED
   ↓ session completed
COMPLETED
```

Side flows:

```text
HELD → EXPIRED
PAYMENT_PENDING → EXPIRED / CANCELLED
BOOKED → CANCELLED
COMPLETED → DISPUTED
DISPUTED → REFUNDED / RESOLVED
```

## 13.3 Rules

- Held slots expire after a defined time window.
- Slot cannot be booked by two parents at the same time.
- Booking status must be independent from payment status.
- Booking cancellation must record actor and reason.

---

# 14. Payment State Machine

## 14.1 Payment states

```text
NOT_STARTED
INITIATED
PENDING
CONFIRMED
FAILED
REFUND_PENDING
REFUNDED
PARTIALLY_REFUNDED
DISPUTED
```

## 14.2 Rules

- Payment confirmation must be idempotent.
- Payment amount must match booking amount.
- Provider transaction ID must be unique when available.
- Refunds must create ledger entries.
- Manual adjustments require admin reason and event log.

---

# 15. Session State Machine

## 15.1 Session states

```text
SCHEDULED
STARTED
COMPLETED
NO_SHOW_STUDENT
NO_SHOW_TEACHER
CANCELLED
DISPUTED
```

## 15.2 Rules

- Session is created from confirmed booking.
- Teacher can mark start and completion.
- Parent may confirm completion or raise issue depending on dispute rules.
- Report should be created after completion.
- No-show affects trust metrics.

---

# 16. Review Eligibility State Machine

## 16.1 Eligibility rules

Parent may review only if:

```text
Booking status = COMPLETED
Payment status = CONFIRMED or settled according to policy
Session status = COMPLETED
Review for this session does not already exist
Reviewer is parent/guardian of the student
```

## 16.2 Review restrictions

- No arbitrary reviews.
- No duplicate reviews.
- No teacher self-reviews.
- No reviews for cancelled sessions, unless separate cancellation feedback is implemented later.

---

# 17. Dispute Flow v0

## 17.1 MVP dispute categories

- Teacher no-show
- Student no-show
- Session quality issue
- Payment/refund issue
- Safety concern
- Report issue
- Other

## 17.2 MVP flow

```text
Parent/Teacher opens dispute
   ↓
Admin reviews booking + payment + session + event ledger
   ↓
Admin contacts parties if needed
   ↓
Resolution selected
   ↓
Refund / no refund / partial refund / warning / account action
   ↓
Dispute resolved
```

## 17.3 Requirements

- Disputes must be linked to booking/session/payment.
- Safety disputes must be prioritized.
- Admin actions must be logged.

---

# 18. Notifications

## 18.1 MVP channels

- SMS or WhatsApp-like operational notifications may be considered, but official platform notifications should be tracked.
- Email optional.
- Push notifications later if mobile app is native.

## 18.2 MVP events

```text
Booking confirmed
Booking cancelled
Session approaching
Session completed
Report available
Payment confirmed
Payment failed
Review requested
Dispute update
```

## 18.3 Requirements

- Notification delivery status should be tracked where possible.
- Critical parent-facing events should not rely only on in-app visibility.

---

# 19. Business Model v0

## 19.1 Primary model

Transaction commission.

## 19.2 Example assumptions

```text
Average session price: 1,500–2,500 DA
Initial platform commission: 10–20%
Average sessions per active student/month: 4
Example session price: 2,000 DA
Example commission: 15%
Revenue per session: 300 DA
```

If 1,000 completed sessions/month:

```text
GMV = 2,000,000 DA
Platform revenue = 300,000 DA
```

## 19.3 Business questions to validate

- Will parents pay through the platform?
- Will teachers accept commission?
- Does commission increase off-platform leakage?
- Does the platform provide enough value after discovery?
- What is the minimum take rate that sustains operations?

---

# 20. Anti-Bypass Strategy

## 20.1 Principle

Do not fight disintermediation only with rules.

Fight it with value.

```text
Don't make bypass forbidden only.
Make staying on-platform better.
```

## 20.2 Parent value

- Payment record/protection
- Booking reliability
- Session history
- Reports
- Progress tracking
- Verified reviews
- Dispute support
- Invoices/receipts
- Notifications
- Child safety controls

## 20.3 Teacher value

- New students
- Calendar
- Reminders
- Structured reports
- Verified reputation
- Trust Profile
- Income tracking
- Repeat booking tools
- Future AI report assistant

---

# 21. Security, Privacy, and Child Safety

## 21.1 MVP principles

- Privacy by design
- Data minimization
- Parental control
- Role-based access control
- Auditability
- Restricted access to minors’ data
- Secure document storage
- Secure payment processing
- Strict admin logging

## 21.2 Must-have controls

- Parent owns/controls student profile.
- Teacher sees only necessary student/session data.
- Verification documents are restricted.
- Admin access is auditable.
- Sensitive events are logged.
- Abuse/dispute reporting exists.
- Data retention and deletion policy must be defined before launch.

## 21.3 Excluded from MVP

- Session recording
- Automated video analysis
- Open teacher-student messaging without controls
- AI-based child safety decision-making

---

# 22. Explicit Non-Goals for MVP

Do **not** build now:

- AI Tutor
- Advanced AI analysis
- Session recording
- Full Student Learning Graph
- Complex Trust Score algorithm
- Subscriptions
- Microservices
- Group classes
- Institutional accounts
- Gamification
- Complex referral incentives
- Predictive analytics
- Paid ranking
- Public teacher leaderboard

These may be considered only after transaction behavior is validated.

---

# 23. Technical Architecture Direction

## 23.1 Recommended MVP architecture

Use a **modular monolith**, not microservices.

### Suggested stack direction

- Frontend: mobile-first web app initially
- Backend: API-first modular backend
- Database: PostgreSQL
- Cache/jobs: Redis/background workers when needed
- Storage: encrypted object storage for documents
- Admin: web dashboard
- Analytics: event-ledger-first, then warehouse later

## 23.2 Why modular monolith

- Faster MVP development
- Lower operational complexity
- Easier debugging
- Strong transactional consistency for bookings/payments/sessions
- Can later split modules if scale requires

---

# 24. Core Modules for Implementation

```text
Auth Module
User Module
Parent/Student Module
Teacher Module
Verification Module
Search/Matching Module
Availability Module
Booking Module
Payment/Ledger Module
Session Module
Report Module
Review Module
Notification Module
Dispute Module
Admin Module
Event Ledger Module
```

---

# 25. High-Level Data Entities

Detailed schema will be created in the next document.

Initial entities:

```text
users
parent_profiles
student_profiles
teacher_profiles
teacher_verifications
subjects
academic_levels
teacher_subjects
availability_slots
bookings
payments
ledger_entries
sessions
session_reports
reviews
disputes
notifications
event_ledger
payouts
```

---

# 26. High-Level API Areas

Detailed API specification will be created after database schema.

Initial API groups:

```text
/auth
/parents
/students
/teachers
/teachers/search
/teachers/match
/availability
/bookings
/payments
/sessions
/reports
/reviews
/disputes
/notifications
/admin
/events
```

---

# 27. Pilot Operations

## 27.1 Teacher onboarding

- Manually recruit 30–50 teachers.
- Prioritize Math/Physics Secondary/BAC teachers.
- Verify identity and qualifications where feasible.
- Train teachers to use availability and reports.

## 27.2 Parent acquisition

- Target parents of secondary/BAC students.
- Use specific message: reliable verified Math/Physics teachers with session reports.
- Avoid broad education marketplace messaging at launch.

## 27.3 Support

- Manual support is acceptable during pilot.
- Disputes can be handled manually but must be logged.
- Payment exceptions must be reconciled.

---

# 28. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Off-platform bypass | Critical | Reports, payment protection, progress history, trust reputation, repeat booking convenience |
| Low teacher adoption | High | Provide operational value: students, calendar, reputation, income tracking |
| Parents avoid platform payment | Critical | Test payment workflow early; provide records/protection; use compliant providers |
| Fake reviews | High | Only verified completed sessions can review |
| Weak liquidity | High | Niche-first launch with dense teacher supply |
| Teacher report fatigue | Medium/High | Structured 2-minute reports; later AI assistance |
| Safety incident | Critical | Verification, reporting, audit logs, restricted data, dispute escalation |
| Regulatory/payment complexity | Critical | Legal/accounting review before production payment launch |
| Overbuilding | High | Strict MVP scope and non-goals |

---

# 29. MVP Acceptance Criteria Summary

EduTrust MVP v0.1 is acceptable only if the platform can reliably support:

1. Parent registration
2. Student profile creation
3. Teacher onboarding and verification
4. Teacher search/matching
5. Transparent Trust Profile
6. Availability slot selection
7. Booking creation
8. Payment initiation/confirmation or compliant pilot payment workflow
9. Session lifecycle tracking
10. Structured session report
11. Verified review after completed session
12. Repeat booking
13. Admin monitoring
14. Event Ledger for all critical actions
15. Basic dispute workflow
16. Role-based access control and auditability

---

# 30. Next Documents

After this PRD is approved, the next documents should be produced in this order:

## 1. PostgreSQL Database Schema v1.0

Includes:

- Tables
- Relationships
- Constraints
- Indexes
- Enums
- Audit/event design
- Money/ledger design
- Privacy-sensitive fields

## 2. API Architecture v1.0

Includes:

- Endpoints
- Request/response bodies
- Validation
- Authorization rules
- Error handling
- Idempotency rules
- Webhook handling

## 3. State Machines v1.0

Includes:

- Booking
- Payment
- Session
- Review
- Dispute
- Payout

## 4. MVP Wireframes / UX Flows

Includes:

- Parent flow
- Teacher flow
- Admin flow
- Booking flow
- Report flow
- Trust Profile screens

---

# 31. Final Product Decision

EduTrust v0.1 should not expand scope further.

The next step is not adding features.

The next step is turning this PRD into engineering specifications:

```text
PRD → Database Schema → API Architecture → State Machines → UX Flows → MVP Build
```

The MVP must prove one thing:

> A trusted, verified, paid tutoring transaction loop can work repeatedly in a narrow Algerian market niche.

If that is proven, EduTrust can later evolve into:

```text
Trust Infrastructure → Student Passport → AI Learning Intelligence → Education Ecosystem
```
