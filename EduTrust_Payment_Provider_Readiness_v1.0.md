# EduTrust Algeria — Payment Provider Readiness v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Payment provider readiness and decision support  
**Status:** READY FOR REVIEW — NOT LEGAL APPROVAL  
**Implementation status:** NOT STARTED

---

# 1. Purpose

This document evaluates candidate payment modes for EduTrust MVP against the approved payment architecture and Algerian market context.

It is **not** payment implementation.

It does **not** claim legal approval, provider certification, or regulatory clearance.

---

# 2. Evidence Classification

Every statement is classified as:

| Label | Meaning |
|---|---|
| FACT | Supported by current source or approved baseline |
| ASSUMPTION | Operationally plausible but not verified |
| REQUIRES LEGAL REVIEW | Must be reviewed by Algerian legal/accounting/payment advisor |
| REQUIRES PROVIDER CONFIRMATION | Must be confirmed with actual provider contract/docs |
| RECOMMENDATION | Proposed product/engineering path, not approval |

---

# 3. External Context Facts

- FACT: Chargily Pay documentation describes a payment gateway that supports online payments in Algeria with EDAHABIA and CIB cards [5](https://dev.chargily.com/pay-v2/introduction).
- FACT: Chargily JavaScript package documentation describes server-side webhook support for Chargily Pay and says it supports EDAHABIA/Algerie Poste and CIB/SATIM [3](https://github.com/Chargily/chargily-pay-javascript).
- FACT: Algérie Poste e-payment terms describe the EDAHABIA card as a debit card enabling internet payments and refer to an electronic payment receipt displayed after each internet card payment [5](https://edcarte.poste.dz/fr/terms.html).
- FACT: Algérie Poste terms describe refund/reclamation concepts for card payments, including merchant/web merchant authorization for refund where a debit transaction exists [5](https://edcarte.poste.dz/fr/terms.html).

These facts do not imply EduTrust is legally approved to process, hold, or settle funds.

---

# 4. EduTrust Payment Architecture Requirements

Payment mode must support or be operationally compatible with:

```text
payment initiation
payment confirmation
idempotency
provider event identity
provider transaction identity
amount/currency verification
refund lifecycle
manual reconciliation if needed
late payment after expiry branch
internal marketplace ledger
teacher payout eligibility
audit/event ledger
receipts/invoices
```

Critical architecture rules:

```text
No booking BOOKED without confirmed payment.
No session SCHEDULED unless booking is BOOKED and payment is CONFIRMED.
Late payment after expiry does not revive booking.
Refund success only after provider/reconciliation success.
No raw provider payload to Parent/Teacher.
```

---

# 5. Candidate Evaluation Matrix

## 5.1 CIB direct / SATIM route

| Criterion | Readiness assessment |
|---|---|
| Payment initiation | REQUIRES PROVIDER CONFIRMATION: API/merchant onboarding and checkout flow must be confirmed |
| Payment confirmation | REQUIRES PROVIDER CONFIRMATION: callback/webhook or status polling model required |
| Webhook support | REQUIRES PROVIDER CONFIRMATION |
| Webhook signature/security | REQUIRES PROVIDER CONFIRMATION |
| Transaction identity | REQUIRES PROVIDER CONFIRMATION: transaction ID fields must map to `provider_transaction_id` |
| Refund support | REQUIRES PROVIDER CONFIRMATION |
| Refund webhook | REQUIRES PROVIDER CONFIRMATION |
| Manual reconciliation | ASSUMPTION: likely possible operationally through merchant dashboard/bank records; must confirm |
| Settlement | REQUIRES LEGAL REVIEW + PROVIDER CONFIRMATION |
| Teacher payout | REQUIRES LEGAL/ACCOUNTING REVIEW; CIB payment receipt does not define marketplace payout legality |
| Platform commission | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Invoice/receipt | REQUIRES PROVIDER CONFIRMATION + accounting review |
| Failure handling | Requires provider error/status model |
| Late payment handling | Must support status check/reconciliation if confirmation delayed |
| Partial refund | REQUIRES PROVIDER CONFIRMATION |
| Auditability | Possible if provider references/export available; must confirm |
| API availability | REQUIRES PROVIDER CONFIRMATION |
| Sandbox/test | REQUIRES PROVIDER CONFIRMATION |
| Operational complexity | Medium/high due direct bank/payment integration and certification/onboarding |
| Legal/compliance questions | High |

## 5.2 Edahabia / Algérie Poste route

| Criterion | Readiness assessment |
|---|---|
| Payment initiation | REQUIRES PROVIDER CONFIRMATION |
| Payment confirmation | REQUIRES PROVIDER CONFIRMATION |
| Webhook support | REQUIRES PROVIDER CONFIRMATION |
| Webhook signature/security | REQUIRES PROVIDER CONFIRMATION |
| Transaction identity | REQUIRES PROVIDER CONFIRMATION |
| Refund support | FACT: Algérie Poste terms discuss refunds/reclamations for card payments, but EduTrust merchant refund API capability still REQUIRES PROVIDER CONFIRMATION [5](https://edcarte.poste.dz/fr/terms.html) |
| Refund webhook | REQUIRES PROVIDER CONFIRMATION |
| Manual reconciliation | ASSUMPTION: operational reconciliation possible through receipts/merchant records; must confirm |
| Settlement | REQUIRES LEGAL REVIEW + PROVIDER CONFIRMATION |
| Teacher payout | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Platform commission | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Invoice/receipt | FACT: e-payment receipt exists in Algérie Poste terms; merchant invoice requirements require accounting review [5](https://edcarte.poste.dz/fr/terms.html) |
| Failure handling | Requires provider status/error model |
| Late payment handling | Requires confirmation timing and reconciliation policy |
| Partial refund | REQUIRES PROVIDER CONFIRMATION |
| Auditability | Requires provider records/receipts/export |
| API availability | REQUIRES PROVIDER CONFIRMATION |
| Sandbox/test | REQUIRES PROVIDER CONFIRMATION |
| Operational complexity | Medium/high if direct integration; lower if via approved gateway |
| Legal/compliance questions | High |

## 5.3 Bank transfer

| Criterion | Readiness assessment |
|---|---|
| Payment initiation | Manual instructions generated by platform |
| Payment confirmation | Manual/OPS reconciliation required |
| Webhook support | Not applicable unless bank API exists |
| Webhook signature/security | Not applicable |
| Transaction identity | Bank reference entered/verified manually |
| Refund support | Manual bank transfer refund process |
| Refund webhook | Not applicable |
| Manual reconciliation | Required |
| Settlement | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Teacher payout | Manual payout process possible but must be legally/accounting reviewed |
| Platform commission | REQUIRES ACCOUNTING REVIEW |
| Invoice/receipt | Platform-generated receipt/invoice after manual confirmation |
| Failure handling | Manual pending/failed handling |
| Late payment handling | Easier to identify but operationally slow |
| Partial refund | Manual possible |
| Auditability | Strong if every manual action logged and evidence attached |
| API availability | Low/not required |
| Sandbox/test | Not applicable |
| Operational complexity | High manual ops; low engineering complexity |
| Legal/compliance questions | High |

## 5.4 Cash/manual pilot

| Criterion | Readiness assessment |
|---|---|
| Payment initiation | Platform creates manual payment intent |
| Payment confirmation | OPS confirms after evidence/collection |
| Webhook support | None |
| Webhook signature/security | None |
| Transaction identity | Internal manual reference |
| Refund support | Manual refund workflow |
| Refund webhook | None |
| Manual reconciliation | Required by design |
| Settlement | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Teacher payout | Manual settlement/payout rules required |
| Platform commission | REQUIRES ACCOUNTING REVIEW |
| Invoice/receipt | Requires accounting review and manual receipt generation |
| Failure handling | OPS-driven |
| Late payment handling | OPS-driven; no provider late webhook |
| Partial refund | Manual possible with refund allocation |
| Auditability | Strong if every manual action uses Event Ledger/Admin Action |
| API availability | Not needed initially |
| Sandbox/test | Can simulate internally |
| Operational complexity | High ops load, low integration risk |
| Legal/compliance questions | Very high if handling cash/funds |

## 5.5 Other provider / gateway aggregator

Example external context: Chargily Pay documentation says it supports EDAHABIA and CIB cards in Algeria [5](https://dev.chargily.com/pay-v2/introduction), and its JS package docs mention server-side webhooks [3](https://github.com/Chargily/chargily-pay-javascript).

| Criterion | Readiness assessment |
|---|---|
| Payment initiation | Potentially available through gateway API; REQUIRES PROVIDER CONFIRMATION |
| Payment confirmation | Potentially via webhook; REQUIRES PROVIDER CONFIRMATION |
| Webhook support | FACT for Chargily docs; exact event model still REQUIRES PROVIDER CONFIRMATION [3](https://github.com/Chargily/chargily-pay-javascript) |
| Webhook signature/security | REQUIRES PROVIDER CONFIRMATION |
| Transaction identity | REQUIRES PROVIDER FIELD MAPPING |
| Refund support | REQUIRES PROVIDER CONFIRMATION |
| Refund webhook | REQUIRES PROVIDER CONFIRMATION |
| Manual reconciliation | REQUIRES PROVIDER DASHBOARD/EXPORT CONFIRMATION |
| Settlement | REQUIRES LEGAL/PROVIDER/ACCOUNTING REVIEW |
| Teacher payout | Marketplace payout support likely separate; REQUIRES LEGAL/PROVIDER CONFIRMATION |
| Platform commission | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Invoice/receipt | Provider receipt + platform invoice model needs review |
| Failure handling | Depends provider status/event model |
| Late payment handling | Depends provider confirmation timing; architecture can handle if events/status exist |
| Partial refund | REQUIRES PROVIDER CONFIRMATION |
| Auditability | Good if provider exposes event IDs, transaction IDs, dashboard/export |
| API availability | Potentially yes; confirm contract |
| Sandbox/test | REQUIRES PROVIDER CONFIRMATION |
| Operational complexity | Potentially lower than direct CIB/Edahabia if provider handles complexity |
| Legal/compliance questions | Still high; provider terms and marketplace fund flow must be reviewed |

---

# 6. MVP Pilot Recommendation

## Recommendation

For the earliest controlled pilot, use one of these two paths:

### Preferred if provider contract is ready

```text
Gateway/provider integration supporting CIB/Edahabia with webhook + dashboard reconciliation
```

Reasons:

- closer to long-term digital transaction model,
- can test online payment behavior,
- supports webhook architecture if confirmed,
- may reduce manual ops.

### Fallback if provider/legal readiness is not ready

```text
Controlled manual payment pilot with strict OPS confirmation, ledger, event logging, and limited scale
```

Reasons:

- validates booking/session/report/review loop,
- avoids pretending provider integration is ready,
- allows operational learning.

But cash/manual pilot must be legally/accounting reviewed and must not be marketed as fully automated secure payment.

---

# 7. Production Recommendation

Production should use a compliant digital payment provider or direct payment infrastructure that confirms:

```text
payment initiation API
secure confirmation/webhook or reliable polling
signature/security model
unique provider_event_id or equivalent
provider_transaction_id
refund support
refund status/reconciliation
merchant settlement model
legal compatibility with marketplace commissions/payouts
sandbox/test environment
provider dashboard/export
```

Do not launch production payment flows until legal/payment/accounting review is complete.

---

# 8. Provider Selection Criteria

Minimum required:

1. Supports Algerian customer payment methods relevant to parents.
2. Provides secure payment confirmation.
3. Provides unique transaction identity.
4. Provides webhook/event identity or equivalent deduplication support.
5. Supports refunds or clear manual refund process.
6. Provides reconciliation dashboard/export.
7. Supports sandbox/test environment.
8. Supports legally acceptable merchant settlement.
9. Allows platform commission/payout model or compatible accounting workflow.
10. Provides documentation and support.

---

# 9. Unresolved Legal Questions

Requires legal review:

- Can EduTrust collect parent funds and later pay teachers?
- Is EduTrust acting as merchant of record, marketplace, agent, or facilitator?
- Are teacher payouts regulated as payment services?
- What KYC/contracting is required for teachers?
- What invoices/receipts are required for parents and teachers?
- How should commissions and taxes be handled?
- What refund/dispute rules are legally required?
- What data retention rules apply to payment and minor data?

---

# 10. Unresolved Accounting Questions

Requires accounting review:

- Revenue recognition for commission.
- Treatment of teacher payable.
- Treatment of refund liability.
- Partial refund allocation between teacher/platform.
- Invoice/receipt format.
- Payout reporting to teachers.
- Tax treatment of commissions/fees.
- Cash/manual pilot reconciliation.

---

# 11. Provider Questions to Ask

1. Do you support CIB and/or Edahabia?
2. Do you provide checkout/payment initiation API?
3. Do you provide webhooks?
4. How are webhooks signed?
5. What is the unique event ID?
6. What is the transaction ID?
7. Are duplicate webhooks possible?
8. Do you support refunds?
9. Do you support partial refunds?
10. Do you provide refund webhooks/status updates?
11. Do you offer sandbox/test mode?
12. What settlement timeline applies?
13. Can marketplace commissions/payouts be supported?
14. Are payouts to teachers supported or must EduTrust handle separately?
15. What merchant onboarding/legal documents are required?
16. What provider payload fields contain PII and must be redacted?

---

# 12. Integration Risks

| Risk | Severity | Mitigation |
|---|---:|---|
| Provider lacks webhook event ID | High | Use provider transaction + event timestamp/status polling with reconciliation table, but requires design review |
| Provider lacks refunds | High | Manual refund workflow; impacts UX and ops |
| Provider lacks partial refunds | Medium/High | Manual partial refund and ledger adjustment, or policy disallow partial automated refunds |
| Provider settlement incompatible with marketplace | Critical | Legal/accounting review before launch |
| Manual pilot creates operational burden | High | Limit pilot size and strict audit |
| Late payment confirmation delay | High | Keep late-payment branch and reconciliation queue |
| Raw provider payload contains PII | High | Redaction/encryption/access audit |

---

# 13. Readiness Status

```text
Payment Provider Readiness Status: NOT READY FOR PRODUCTION
```

Pilot readiness may be possible only after selecting a provider/mode and approving legal/accounting/ops controls.

---

# 14. Final Recommendation

Proceed with provider discovery and legal/accounting review in parallel with non-payment engineering planning.

Do not implement production payment workflows until:

```text
provider selected
contract/docs reviewed
webhook/refund capabilities confirmed
legal/accounting path approved
sandbox tested
```
