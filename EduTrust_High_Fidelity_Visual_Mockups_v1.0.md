# EduTrust Algeria — High-Fidelity Visual Mockups v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Visual mockup specification and clickable prototype planning  
**Status:** Ready for visual review  
**Implementation status:** No frontend/backend implementation started  
**Derived from:**

```text
Approved Low-Fidelity Baseline
Low-Fidelity Final Audit PASS
High-Fidelity UI Design v1.0
High-Fidelity UI Audit v1.0
Locked Architecture Baseline
```

---

# 1. Purpose

This document specifies how approved EduTrust screens should be visually composed in high-fidelity mockups and clickable prototypes.

It is intended for designers preparing:

- Figma screens
- Visual mockups
- Clickable prototype
- Design handoff package

This document is **not** production code and does **not** start frontend or backend implementation.

---

# 2. Absolute Boundaries

Do **not**:

- implement frontend
- implement backend
- write production UI code
- modify database schema
- modify API architecture
- modify state machines
- modify UX business logic
- add MVP features
- reopen architecture baseline
- invent unresolved policy values

The visual mockups must reflect the approved architecture and UX only.

---

# 3. Figma / Design File Structure Recommendation

Recommended Figma pages:

```text
00 Cover / Notes
01 Design Tokens
02 Components
03 Parent Mobile Screens
04 Teacher Mobile Screens
05 Admin Desktop Screens
06 Financial Edge States
07 Privacy & Permissions
08 Empty / Error / Loading States
09 RTL Variants
10 Clickable Prototype Flow
11 Design Handoff Notes
```

Recommended frame sizes:

```text
Parent mobile: 390 × 844
Teacher mobile: 390 × 844
Tablet optional: 768 × 1024
Admin desktop: 1440 × 1024
Admin dense table variant: 1600 × 1024
```

---

# 4. Global Visual System

## 4.1 Brand feel

EduTrust should visually communicate:

```text
trust
clarity
parental safety
professional education
financial reliability
calm transparency
```

Avoid a playful/gamified look.

## 4.2 Core palette

Use the high-fidelity UI design tokens:

| Purpose | Suggested color role |
|---|---|
| Primary action | Trust blue |
| Main text | Deep navy |
| Background | Light slate/surface |
| Success only | Green |
| Pending/approved-not-final | Amber |
| Failed/rejected/cancelled | Red |
| Audit/recovery/admin-sensitive | Purple |
| Neutral/inactive | Slate |

Critical:

```text
APPROVED and PROVIDER_PENDING refunds must use warning/amber, not success green.
Only SUCCEEDED can use success green.
```

## 4.3 Typography

Mockups should support Arabic/French UI.

Recommended:

```text
Arabic: Noto Sans Arabic / IBM Plex Sans Arabic
French/Latin: Inter / system sans
```

Final Arabic/French terminology remains:

```text
[POLICY DECISION REQUIRED]
```

## 4.4 Layout principles

Parent and teacher:

```text
mobile-first
card-based
single primary CTA per screen
bottom navigation where appropriate
sticky action bar for booking/payment actions
```

Admin/OPS:

```text
desktop-first
left sidebar
filterable tables
detail drawers
audit timelines
sensitive access modals
```

## 4.5 Standard visual components

Create high-fidelity components for:

```text
Primary button
Secondary button
Danger button
Disabled button with reason
Status badge
Trust badge
Timeline
Financial breakdown card
Student permission card
Teacher card
Session card
Booking card
Refund timeline
Payout breakdown
Sensitive access modal
Admin table
Detail drawer
Empty state
Error state
Loading skeleton
Permission denied state
```

---

# 5. Critical Financial Visual Rules

## 5.1 Refund lifecycle

Refund states must remain visually distinct:

```text
REQUESTED
APPROVED
PROVIDER_PENDING
SUCCEEDED
FAILED
REJECTED
CANCELLED
```

| State | Label | Visual treatment |
|---|---|---|
| REQUESTED | Refund requested | Blue/info |
| APPROVED | Refund approved | Amber/warning |
| PROVIDER_PENDING | Refund processing | Amber/warning |
| SUCCEEDED | Refund completed | Green/success |
| FAILED | Refund failed | Red/danger |
| REJECTED | Refund rejected | Red/danger |
| CANCELLED | Refund cancelled | Neutral/red depending copy |

Only `SUCCEEDED` may use:

```text
Refund completed
Refunded
success-green treatment
```

## 5.2 Late Payment After Expiry

This edge-state must show:

```text
Payment received
Reservation expired
Refund/reconciliation started
No session scheduled
```

Never show:

```text
Booking confirmed
Session scheduled
Teacher payout pending
```

## 5.3 Payout presentation

Payout UI must show:

```text
Gross teacher payable
Refund exposure
Other deductions
Net teacher payable
```

Refund exposure includes:

```text
APPROVED
PROVIDER_PENDING
SUCCEEDED
```

Paid payouts must remain visually immutable.

Post-payout refunds appear as separate:

```text
Adjustment / Recovery
```

records.

---

# 6. Critical Privacy Visual Rules

## 6.1 Student data

Student information must be minimized.

Teacher sees only:

```text
permitted student/session context
```

Parent controls permissions.

## 6.2 Sensitive admin access

Every sensitive access mockup must display:

```text
This access will be logged.
```

Sensitive documents and raw provider payloads must remain protected and hidden by default.

---

# 7. Open Policy Rules

Do not invent values for:

1. Booking hold duration
2. Payment checkout timeout
3. Late-payment auto-refund vs OPS review
4. No-show grace periods
5. Parent dispute window
6. Payout delay
7. Refund allocation teacher/platform
8. Review eligibility after partial refund
9. Notification channels
10. Arabic/French final terminology

Use:

```text
[POLICY DECISION REQUIRED]
```

where needed.

---

# 8. Parent Experience Visual Mockups

---

## P-01 — Authentication / Login

| Field | Visual specification |
|---|---|
| Screen ID | P-01 |
| Layout hierarchy | Centered auth card on mobile; optional split layout on desktop with trust illustration |
| Header | EduTrust wordmark, language selector |
| Navigation | None; login/register tab switch |
| Main content regions | Login/Register form, security note, help links |
| Cards | Single elevated auth card |
| Tables | None |
| CTA hierarchy | Primary: Login/Create account; Secondary: Forgot password, switch role |
| Status badges | None |
| Timelines | None |
| Forms | Phone/email, password/OTP area |
| Modals | Optional forgot-password modal later; MVP can use route |
| Alerts | Generic failed-login alert; no account enumeration |
| Empty states | Not applicable |
| Error states | Invalid credentials, rate limited, suspended account |
| Loading states | Button spinner and disabled form |
| Permission states | Wrong role redirects to correct portal |
| Mobile composition | Full-width card with 16px margins |
| Desktop composition | Centered card max width 420px |
| RTL considerations | Form labels align right in Arabic; tab order mirrored |
| Accessibility | Inputs labelled; error announced; touch targets 44px |

---

## P-02 — Parent Dashboard

| Field | Visual specification |
|---|---|
| Screen ID | P-02 |
| Layout hierarchy | Header → children summary → upcoming session → pending actions → quick search |
| Header | Greeting, notification icon, account avatar |
| Navigation | Bottom nav: Home, Children, Find Teacher, Bookings, Account |
| Main content regions | Children cards, upcoming session card, pending actions card |
| Cards | Child card, session card, alert/action card |
| CTA hierarchy | Primary: Find teacher; Secondary: Add student, View report, Pay if eligible |
| Status badges | Payment pending, Report available, Dispute open |
| Alerts | Dispute/refund alerts visible above general content |
| Empty state | “Add your first student profile.” |
| Error state | Dashboard failed to load with retry |
| Loading state | Skeleton cards |
| Permission state | Parent role required |
| Mobile composition | Vertical card stack |
| Desktop composition | Two-column dashboard with action sidebar |
| RTL considerations | Card order mirrors; badges remain text-based |
| Accessibility | Headings clear; pending actions reachable by screen reader |

---

## P-03 — Student List

| Field | Visual specification |
|---|---|
| Screen ID | P-03 |
| Layout hierarchy | Title → Add CTA → student cards |
| Header | “Students / Children” title |
| Navigation | Parent bottom nav |
| Main content regions | Student list, summary chips |
| Cards | Student profile card with academic level and next action |
| CTA hierarchy | Primary: Add student; Secondary: View profile, Find teacher |
| Status badges | Active, Archived |
| Empty state | Illustration + “Add your first student profile.” |
| Error state | Cannot load students |
| Loading state | Student card skeletons |
| Permission state | Parent only |
| Mobile composition | One card per row |
| Desktop composition | Grid cards |
| RTL considerations | Student display names align per locale |
| Accessibility | Add Student button labelled clearly |

---

## P-04 — Create Student

| Field | Visual specification |
|---|---|
| Screen ID | P-04 |
| Layout hierarchy | Title → privacy note → grouped form → sticky save CTA |
| Header | Back button + title |
| Main content regions | Basic info, academic level, learning goal, preferences, consent |
| Cards | Privacy note card |
| CTA hierarchy | Primary: Save student; Secondary: Cancel |
| Forms | Display name, birth year optional, academic level, goal, mode, consent |
| Alerts | Consent/data minimization note |
| Error state | Field-level validation |
| Loading state | Save button spinner |
| Permission state | Parent role required |
| Mobile composition | Single-column form |
| Desktop composition | Form max width 720px |
| RTL considerations | Inputs/labels mirror |
| Accessibility | Consent checkbox labelled; required fields announced |

---

## P-05 — Student Profile

| Field | Visual specification |
|---|---|
| Screen ID | P-05 |
| Layout hierarchy | Student header → quick actions → recent sessions → reports/progress |
| Header | Student display name, academic level badge |
| Main content regions | Learning goal, upcoming sessions, recent reports, permissions summary |
| Cards | Student summary, recent session, recent report |
| CTA hierarchy | Primary: Find teacher; Secondary: View Passport, Manage permissions |
| Status badges | Active/Archived, Permission active |
| Empty state | No sessions yet |
| Error state | Student unavailable/access denied |
| Loading state | Profile skeleton |
| Permission state | Parent ownership required |
| Mobile composition | Vertical sections |
| Desktop composition | Main content + right action sidebar |
| RTL considerations | Progress lists mirror layout |
| Accessibility | Section landmarks for reports/passport/actions |

---

## P-06 — Student Passport v0

| Field | Visual specification |
|---|---|
| Screen ID | P-06 |
| Layout hierarchy | Passport header → subject cards → recent topics → observations/homework |
| Header | Student Passport + “Based on verified session reports” badge |
| Main content regions | Subjects, completed sessions, topics, homework, teacher observations |
| Cards | Subject progress card, report-derived note card |
| CTA hierarchy | Primary: Find next teacher/session; Secondary: Manage sharing permissions |
| Status badges | Verified session data, Report-based |
| Timelines | Optional recent progress timeline from structured reports |
| Empty state | “Progress appears after completed sessions and reports.” |
| Error state | Cannot load passport |
| Loading state | Passport skeleton |
| Permission state | Parent-only unless explicitly shared |
| Mobile composition | Subject accordion cards |
| Desktop composition | Subject cards + report timeline |
| RTL considerations | Timeline direction mirrors in RTL |
| Accessibility | No chart-only information; all metrics have text |

---

## P-07 — Student Data Sharing Permissions

| Field | Visual specification |
|---|---|
| Screen ID | P-07 |
| Layout hierarchy | Privacy explanation → active permissions → expired/revoked → grant action |
| Header | Data Sharing Permissions |
| Main content regions | Permission cards with teacher, scope, expiry, linked session |
| Cards | Permission card with privacy-shield icon |
| CTA hierarchy | Primary: Grant access; Secondary: Revoke |
| Status badges | Active, Expired, Revoked, Parent controlled |
| Modals | Revoke confirmation modal |
| Alerts | Explanation of exactly what teacher can see |
| Empty state | “No teachers currently have access.” |
| Error state | Permission update failed |
| Loading state | Updating access spinner |
| Permission state | Parent owns student |
| Mobile composition | Permission cards stacked |
| Desktop composition | Table/card hybrid |
| RTL considerations | Scope/expiry labels mirror |
| Accessibility | Revoke button labelled with teacher name |

---

## P-08 — Teacher Search

| Field | Visual specification |
|---|---|
| Screen ID | P-08 |
| Layout hierarchy | Student selector → filter form → CTAs |
| Header | Find Teacher |
| Main content regions | Subject, level, mode, budget, availability, language, location |
| Cards | Search form card |
| CTA hierarchy | Primary: Search; Secondary: Find best match |
| Forms | Filter inputs and chips |
| Empty state | Not applicable before search |
| Error state | Invalid filters |
| Loading state | Search button loading |
| Permission state | Student ownership required for matching |
| Mobile composition | Form with bottom-sheet filters |
| Desktop composition | Filter sidebar + results area |
| RTL considerations | Filter chips mirror |
| Accessibility | All filters labelled; budget input accessible |

---

## P-09 — Matching Results

| Field | Visual specification |
|---|---|
| Screen ID | P-09 |
| Layout hierarchy | Results header → filter chips → teacher cards |
| Header | Recommended Matches |
| Main content regions | Teacher cards, reasons, available slots |
| Cards | Teacher result card |
| CTA hierarchy | Primary: Select slot; Secondary: View profile |
| Status badges | Verified identity, Qualification verified, Best match |
| Alerts | No unexplained score |
| Empty state | No strong match found |
| Error state | Matching failed |
| Loading state | Teacher card skeleton |
| Permission state | Parent/student context required |
| Mobile composition | Single-column cards |
| Desktop composition | Results list + filter sidebar |
| RTL considerations | Reasons list mirrors |
| Accessibility | Recommendation reasons readable as text |

---

## P-10 — Teacher Trust Profile

| Field | Visual specification |
|---|---|
| Screen ID | P-10 |
| Layout hierarchy | Teacher hero → offerings → trust grid → reviews → availability preview |
| Header | Teacher name/photo/subjects |
| Main content regions | Trust cards, methods, languages, reviews |
| Cards | Trust metric card, review card, subject offering card |
| CTA hierarchy | Primary: Choose slot; Secondary: View reviews |
| Status badges | Verified identity, Qualifications reviewed, Listed/Unavailable |
| Empty state | No verified reviews yet |
| Error state | Teacher unavailable/suspended |
| Loading state | Profile skeleton |
| Permission state | Public reduced view; parent auth for booking |
| Mobile composition | Stacked hero and trust cards |
| Desktop composition | Profile main + booking sidebar |
| RTL considerations | Trust grid order mirrors |
| Accessibility | Rating includes review count text |

---

## P-11 — Teacher Availability

| Field | Visual specification |
|---|---|
| Screen ID | P-11 |
| Layout hierarchy | Date selector → slot list/calendar → selected slot summary |
| Header | Availability |
| Main content regions | Slot calendar/list, timezone label |
| Cards | Slot chip/card, selected slot summary |
| CTA hierarchy | Primary: Reserve this slot; Secondary: Change date |
| Status badges | Available, Held, Booked, Blocked |
| Empty state | No available slots |
| Error state | Cannot load availability |
| Loading state | Calendar skeleton |
| Permission state | Login required before reserve |
| Mobile composition | Horizontal date scroller + slot chips |
| Desktop composition | Weekly calendar grid |
| RTL considerations | Calendar direction follows locale |
| Accessibility | Slot buttons include date/time/mode labels |

---

## P-12 — Booking Hold

| Field | Visual specification |
|---|---|
| Screen ID | P-12 |
| Layout hierarchy | Reservation summary → countdown → payment CTA |
| Header | Reservation Summary |
| Main content regions | Teacher/student/subject/time/price |
| Cards | Summary card, countdown card |
| CTA hierarchy | Primary: Proceed to payment; Secondary: Cancel reservation |
| Status badges | Reserved temporarily, Expired |
| Alerts | “Reserved for [POLICY DECISION REQUIRED]” |
| Empty state | Not applicable |
| Error state | Slot unavailable/hold failed |
| Loading state | Reserving spinner |
| Permission state | Parent owns student |
| Mobile composition | Sticky payment CTA bottom |
| Desktop composition | Summary + payment sidebar |
| RTL considerations | Countdown and date format localized later |
| Accessibility | Countdown has text equivalent |

---

## P-13 — Checkout / Payment Initiation

| Field | Visual specification |
|---|---|
| Screen ID | P-13 |
| Layout hierarchy | Booking summary → amount card → payment method → pay CTA |
| Header | Checkout |
| Cards | Amount card, payment method card, security note |
| CTA hierarchy | Primary: Pay; Secondary: Back |
| Status badges | Held, Payment not started |
| Alerts | Provider unavailable / hold expired |
| Empty state | No payment methods available |
| Error state | Payment setup failed |
| Loading state | Starting payment spinner |
| Permission state | Parent owns booking |
| Mobile composition | Sticky Pay CTA |
| Desktop composition | Checkout form + summary sidebar |
| RTL considerations | Amount alignment supports Arabic/French |
| Accessibility | Payment method selection labelled |

---

## P-14 — Payment Pending

| Field | Visual specification |
|---|---|
| Screen ID | P-14 |
| Layout hierarchy | Pending status → booking summary → refresh/action area |
| Header | Payment Pending |
| Cards | Payment pending card, booking summary |
| CTA hierarchy | Primary: Refresh status; Secondary: Return to dashboard |
| Status badges | Payment pending, Booking waiting confirmation |
| Alerts | Confirmation may take time |
| Empty state | Not applicable |
| Error state | Cannot check status |
| Loading state | Checking latest status |
| Permission state | Own booking/payment only |
| Mobile composition | Centered status with summary below |
| Desktop composition | Status panel + timeline |
| RTL considerations | Timeline mirrors |
| Accessibility | Pending state announced; no auto-refresh trap |

---

## P-14A / P-22A — Late Payment After Expiry / Reconciliation

| Field | Visual specification |
|---|---|
| Screen ID | P-14A / P-22A |
| Layout hierarchy | Warning header → payment received card → reservation expired card → refund timeline → actions |
| Header | Payment received after reservation expired |
| Cards | Payment received, Reservation expired, Refund/reconciliation started |
| CTA hierarchy | Primary: View refund timeline; Secondary: Choose another slot, Contact support |
| Status badges | Payment received, Reservation expired, No session scheduled, Refund/reconciliation started |
| Timelines | Refund/reconciliation timeline |
| Alerts | Warning-style explanation, not success |
| Empty state | Not applicable |
| Error state | Cannot load reconciliation status |
| Loading state | Checking payment/refund status |
| Permission state | Own payment/booking/refund only |
| Mobile composition | Warning banner and cards stacked |
| Desktop composition | Timeline on right; explanatory cards left |
| RTL considerations | Timeline and action order mirror |
| Accessibility | Warning text explicit; color not only indicator |

---

## P-15 — Payment Success

| Field | Visual specification |
|---|---|
| Screen ID | P-15 |
| Layout hierarchy | Success header → confirmed booking card → session scheduled card → receipt link |
| Header | Payment Confirmed |
| Cards | Booking confirmed, Session scheduled, Receipt |
| CTA hierarchy | Primary: View session; Secondary: View receipt |
| Status badges | Paid, Confirmed, Scheduled |
| Alerts | Operational incident copy if backend detects missing session |
| Empty state | Not applicable |
| Error state | Automatic refresh + support escalation; no user retry mutation |
| Loading state | Loading session details |
| Permission state | Own booking/session only |
| Mobile composition | Success stack with sticky View Session |
| Desktop composition | Confirmation details + receipt sidebar |
| RTL considerations | Success timeline mirrors |
| Accessibility | Success not color-only; clear text labels |

---

## P-16 — Payment Failure / Retry

| Field | Visual specification |
|---|---|
| Screen ID | P-16 |
| Layout hierarchy | Error header → reason summary → booking status → recovery actions |
| Header | Payment Failed |
| Cards | Failure reason, booking/hold status |
| CTA hierarchy | Primary: Try again if backend allows; Secondary: Choose another slot |
| Status badges | Payment failed, Reservation expired if applicable |
| Alerts | Safe provider error summary |
| Empty state | Not applicable |
| Error state | Unknown provider status |
| Loading state | Checking retry eligibility |
| Permission state | Own payment only |
| Mobile composition | Error card with CTAs below |
| Desktop composition | Failure timeline + actions panel |
| RTL considerations | Button order mirrors but primary remains prominent |
| Accessibility | Failure reason text clear |

---

## P-17 — Booking Detail

| Field | Visual specification |
|---|---|
| Screen ID | P-17 |
| Layout hierarchy | Status header → summary → payment/session states → overlays → timeline → actions |
| Header | Booking Detail |
| Cards | Booking summary, payment card, session card |
| CTA hierarchy | Contextual: Pay/View session/View report; Secondary: Cancel, Report problem |
| Status badges | Held, Pending, Confirmed, Completed, Cancelled, Expired |
| Timelines | Booking/payment/session timeline |
| Alerts | Dispute/refund overlay banners |
| Empty state | Not applicable |
| Error state | Booking unavailable |
| Loading state | Booking skeleton |
| Permission state | Own booking only |
| Mobile composition | Stacked state cards |
| Desktop composition | Details + state timeline sidebar |
| RTL considerations | Timeline mirrors |
| Accessibility | Disabled actions explain reason |

---

## P-18 — Session Detail

| Field | Visual specification |
|---|---|
| Screen ID | P-18 |
| Layout hierarchy | Session status → teacher/student/subject/time → attendance → report/dispute actions |
| Header | Session Detail |
| Cards | Session summary, attendance, report status |
| CTA hierarchy | Primary: View report if available; Secondary: Report problem |
| Status badges | Scheduled, In progress, Completed, Student absent, Teacher absent |
| Alerts | Dispute overlay if open |
| Empty state | If no session, show booking state instead |
| Error state | Session unavailable |
| Loading state | Session skeleton |
| Permission state | Own child session only |
| Mobile composition | Stacked summary cards |
| Desktop composition | Detail view + report/dispute sidebar |
| RTL considerations | Date/time localized later |
| Accessibility | Parent cannot see start/complete controls |

---

## P-19 — Session Report

| Field | Visual specification |
|---|---|
| Screen ID | P-19 |
| Layout hierarchy | Report header → structured sections → actions |
| Header | Session Report |
| Cards | Topic card, skills card, observations, homework, next objectives |
| CTA hierarchy | Primary: Review teacher if eligible; Secondary: Report issue |
| Status badges | Report available, Verified session |
| Empty state | Report not available yet |
| Error state | Cannot load report |
| Loading state | Report skeleton |
| Permission state | Own child report only |
| Mobile composition | Section cards stacked |
| Desktop composition | Report document view + actions sidebar |
| RTL considerations | Report text direction supports Arabic/French |
| Accessibility | Sections have headings |

---

## P-20 — Review

| Field | Visual specification |
|---|---|
| Screen ID | P-20 |
| Layout hierarchy | Verified session summary → rating → comment → submit |
| Header | Review Teacher |
| Cards | Verified session summary, review policy |
| CTA hierarchy | Primary: Submit review; Secondary: Cancel |
| Status badges | Verified completed session |
| Forms | Rating and comment |
| Empty state | If not eligible, show reason |
| Error state | Duplicate/not eligible |
| Loading state | Submitting review |
| Permission state | Parent owner only; teacher self-review impossible |
| Mobile composition | Single-column form |
| Desktop composition | Form + session summary sidebar |
| RTL considerations | Rating interaction works in RTL |
| Accessibility | Star rating accessible with labels |

---

## P-21 to P-28 — Parent Supporting Screens

These screens follow the approved high-fidelity system:

| Screen | Visual composition summary |
|---|---|
| P-21 Payment / Invoice History | List/cards with payment status, refund badges, receipt links; no raw provider payload |
| P-22 Refund Timeline | Vertical timeline with all refund states; success green only for SUCCEEDED |
| P-23 Dispute | Category form/status timeline; safety prioritized; dispute overlay preserved |
| P-24 Refund Rejected | Red rejected card, reason, dispute/support links; no refund-completed visuals |
| P-25 Refund Cancelled | Cancelled card, “No refund was issued,” no provider success visuals |
| P-26 Refund Completed | Green success card only for SUCCEEDED; amount/date/full-partial indicator |
| P-27 Notifications | Notification cards/list, unread/read, target navigation |
| P-28 Account / Security | Account settings, active sessions, security events, revoke sessions |

---

# 9. Teacher Experience Visual Mockups

## T-29 to T-45 — Teacher Screens

| Screen | Visual composition summary |
|---|---|
| T-29 Teacher Onboarding | Checklist-based setup, progress indicator, profile/subjects/verification/availability steps |
| T-30 Teacher Verification | Secure upload/status timeline; documents not public |
| T-31 Teacher Dashboard | Profile status, upcoming sessions, reports due, earnings summary |
| T-32 Subjects & Pricing | Offering cards with subject, level, price, duration, active/inactive |
| T-33 Availability Management | Calendar + rules + block/unblock controls; booked slots protected |
| T-34 Bookings | Status-tabbed booking list using scoped teacher bookings |
| T-35 Session Detail | Session state header, limited student context, start/complete/report actions |
| T-36 Attendance | Present/student no-show controls with grace placeholder |
| T-37 Session Report | Fast structured form, no AI assistance |
| T-38 Reviews | Verified review list, rating summary, no teacher editing |
| T-39 Earnings | Gross/refund exposure/deductions/net payable breakdown |
| T-40 Payout Detail | Payout status timeline and included sessions |
| T-41 Refund Adjustment | Approved/provider-pending/succeeded adjustment visibility |
| T-42 Post-Payout Recovery | Separate recovery/adjustment card; old payout locked |
| T-43 Student Session Context | Permission-scoped context with expiry/scope badge |
| T-44 Notifications | Teacher notification list for bookings/reports/payouts/verification |
| T-45 Account / Security | Sessions/security events/logout/revoke sessions |

Teacher-specific visual rules:

- Use task-focused dashboard cards.
- Always explain payout blockers.
- Use warning colors for refund exposure before success.
- Never expose unrestricted Student Passport.
- Never expose parent raw payment details.

---

# 10. Admin / OPS Visual Mockups

## A-46 to A-64 — Admin Screens

| Screen | Visual composition summary |
|---|---|
| A-46 Admin Dashboard | Queue cards, critical alerts, operational KPIs |
| A-47 Verification Queue | Dense table of pending verifications; no document preview |
| A-48 Verification Detail | Teacher metadata + sensitive document access modal + approve/reject |
| A-49 Booking Monitoring | Filterable table with booking/payment/session/dispute states |
| A-50 Payment Monitoring | Payment table with provider/refund/reconciliation badges; payload hidden |
| A-51 Refund Queue | Lifecycle tabs: requested/approved/provider-pending/failed/rejected/cancelled/succeeded |
| A-52 Refund Detail | Timeline, amount/allocation, linked entities, provider/reconciliation summary |
| A-53 Refund Reconciliation | Logged-action form with source/reference/timestamp/reason/evidence |
| A-54 Dispute Queue | Priority/safety-focused dispute table |
| A-55 Dispute Detail | Factual states + dispute overlay + evidence + resolution actions |
| A-56 Payout Eligible Queue | Eligible/blocked table with gross/exposure/deductions/net |
| A-57 Payout Processing | Batch confirmation with idempotency-safe processing copy |
| A-58 Payout Failure | Failure reason, retry/cancel if allowed, audit link |
| A-59 Recovery / Adjustment | Read-only recovery view; no manual create adjustment CTA |
| A-60 Event Ledger | Immutable event table and detail drawer |
| A-61 Security Events | Severity-filtered security table |
| A-62 Sensitive Access | Modal with “This access will be logged.” and reason field |
| A-63 User Suspension | Admin-only account action with reason and impact warning |
| A-64 Audit Trail | Unified entity timeline with business/admin/security/provider events |

Admin-specific visual rules:

- Desktop-first dense tables.
- Role-sensitive disabled actions.
- Sensitive access warning must be visible before opening protected data.
- Raw payloads/documents hidden by default.
- No direct mutation of ledger, paid payout, or factual booking/session state.

---

# 11. Clickable Prototype Plan

## 11.1 Parent prototype path

```text
P-01 Login
→ P-02 Dashboard
→ P-04 Create Student
→ P-08 Teacher Search
→ P-09 Matching Results
→ P-10 Teacher Trust Profile
→ P-11 Availability
→ P-12 Booking Hold
→ P-13 Checkout
→ P-14 Payment Pending
→ P-15 Payment Success
→ P-18 Session Detail
→ P-19 Report
→ P-20 Review
```

Edge branch:

```text
P-14 Payment Pending
→ P-14A/P-22A Late Payment After Expiry
→ P-22 Refund Timeline
→ P-26 Refund Completed
```

Dispute branch:

```text
P-18 Session Detail
→ P-23 Dispute
→ P-22 Refund Timeline
→ P-24/P-25/P-26 outcome
```

## 11.2 Teacher prototype path

```text
T-29 Onboarding
→ T-32 Subjects & Pricing
→ T-30 Verification
→ T-33 Availability
→ T-31 Dashboard
→ T-35 Session Detail
→ T-36 Attendance
→ T-37 Report
→ T-39 Earnings
→ T-40 Payout Detail
```

Recovery branch:

```text
T-40 Payout Detail
→ T-42 Post-Payout Recovery
```

## 11.3 Admin prototype path

```text
A-46 Dashboard
→ A-51 Refund Queue
→ A-52 Refund Detail
→ A-53 Refund Reconciliation
→ A-56 Payout Eligible Queue
→ A-57 Payout Processing
→ A-60 Event Ledger
```

Sensitive access branch:

```text
A-48 Verification Detail
→ A-62 Sensitive Access Modal
→ A-64 Audit Trail
```

---

# 12. Responsive Behavior

## 12.1 Mobile

Parent and teacher screens:

- bottom navigation,
- card stacks,
- sticky CTA bars,
- compact timelines,
- bottom sheets for filters.

## 12.2 Tablet

Teacher dashboard and parent search can use two-column layout.

## 12.3 Desktop

Admin:

- sidebar navigation,
- tables,
- detail drawers,
- split-view timelines,
- sticky filters.

---

# 13. RTL Behavior

Mockups must include at least representative RTL variants for:

- Parent dashboard
- Teacher search/matching results
- Teacher Trust Profile
- Booking/payment flow
- Refund timeline
- Teacher earnings/payout
- Admin refund queue/detail

RTL rules:

- Layout direction mirrors.
- Icons that imply direction must mirror.
- Numeric amounts remain readable with DZD labels.
- Timelines can mirror direction but state order must remain semantically clear.
- Mixed Arabic/French content must remain legible.

Final terminology:

```text
[POLICY DECISION REQUIRED]
```

---

# 14. Accessibility Behavior

High-fidelity mockups must demonstrate:

- visible focus states,
- text labels for status badges,
- non-color-only status communication,
- sufficient contrast,
- touch targets of at least 44px,
- accessible form errors,
- accessible rating input,
- clear disabled-action reasons,
- keyboard-operable admin tables and modals,
- screen-reader-friendly timeline labels.

---

# 15. Error / Loading / Empty States Visual Direction

## 15.1 Loading

Use skeleton loaders for:

- dashboards,
- lists,
- teacher cards,
- reports,
- refunds,
- admin tables.

Use button-level spinners for:

- reserve slot,
- payment initiation,
- submit report,
- submit review,
- process refund,
- process payout.

## 15.2 Empty states

Empty states should be calm and action-oriented:

```text
No students → Add student
No teachers found → Adjust filters
No reports → Reports appear after completed sessions
No payouts → Completed reported sessions will appear here
```

## 15.3 Errors

Errors must not leak private data.

Use clear labels:

```text
The selected slot is no longer available.
This action is not available for the current state.
You do not have access to this resource.
Payment confirmation is still pending.
```

---

# 16. MVP Restrictions Confirmation

Do not introduce:

- AI Tutor
- AI Matching
- Session Recording
- Gamification
- Subscriptions
- Group Classes
- Institutional Accounts
- Predictive Analytics
- Advanced Referral Engine
- Public Teacher Leaderboard
- Paid Ranking
- Microservices

Do not turn:

```text
Find best match
```

into an AI-branded experience.

---

# 17. Open Policy Dependency Map

| Policy | Visual treatment |
|---|---|
| Booking hold duration | `[POLICY DECISION REQUIRED]` in countdown copy |
| Payment checkout timeout | `[POLICY DECISION REQUIRED]` in pending/expiry copy |
| Late-payment auto-refund vs OPS review | `[POLICY DECISION REQUIRED]` in reconciliation timeline |
| No-show grace periods | `[POLICY DECISION REQUIRED]` in attendance screens |
| Parent dispute window | `[POLICY DECISION REQUIRED]` in dispute/report screens |
| Payout delay | `[POLICY DECISION REQUIRED]` in earnings/payout screens |
| Refund allocation teacher/platform | `[POLICY DECISION REQUIRED]` in admin refund/payout detail |
| Review eligibility after partial refund | `[POLICY DECISION REQUIRED]` in review eligibility UI |
| Notification channels | `[POLICY DECISION REQUIRED]` in notification settings |
| Arabic/French final terminology | `[POLICY DECISION REQUIRED]` across final copy |

---

# 18. Visual Review Checklist

Before approval, check:

- [ ] Refund states visually distinct.
- [ ] `APPROVED` and `PROVIDER_PENDING` are amber/warning, not green.
- [ ] Only `SUCCEEDED` says refund completed/refunded.
- [ ] Late payment after expiry does not look like booking success.
- [ ] Payout breakdown shows gross, exposure, deductions, net.
- [ ] Paid payout remains visually immutable.
- [ ] Recovery appears as separate adjustment.
- [ ] Student permissions are parent-controlled and visible.
- [ ] Teacher context is permission-scoped.
- [ ] Sensitive admin access says “This access will be logged.”
- [ ] Raw provider payload/document access is protected.
- [ ] Reschedule does not appear.
- [ ] No excluded MVP features appear.
- [ ] `[POLICY DECISION REQUIRED]` placeholders remain unresolved.
- [ ] RTL variants are considered.
- [ ] Accessibility states are visible.

---

# 19. Handoff Notes for Designers

Designers should create visual mockups using the approved structure, not reinterpret business rules.

If a screen seems to require a new action, new state, or new backend behavior, mark it as:

```text
CHANGE REQUEST REQUIRED
```

Do not silently add it to the UI.

---

# 20. Final Status

```text
High-Fidelity Visual Mockups v1.0 Status: READY FOR VISUAL REVIEW
```

Do not proceed to frontend/backend implementation.

Do not write production UI code.

Do not modify architecture, database, API, or state machines.
