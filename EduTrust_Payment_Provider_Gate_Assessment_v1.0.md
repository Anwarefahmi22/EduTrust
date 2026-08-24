# EduTrust Algeria — Payment Provider Gate Assessment v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Payment readiness gate assessment  
**Status:** PAYMENT READY FOR DEV/STAGING MOCK ONLY; REAL-MONEY PILOT/PRODUCTION NOT READY

---

# 1. Executive Decision

Payment gate decision:

```text
PAYMENT READY FOR PILOT ONLY: NO, not for real-money pilot yet.
PAYMENT READY FOR DEV/STAGING MOCK: YES.
PAYMENT READY FOR PRODUCTION: NO.
```

Short classification:

```text
Payment Gate Status: NOT READY for real-money pilot/production; READY for controlled DEV/STAGING with mock payment adapter only.
```

No legal approval is claimed.

No provider certification is claimed.

---

# 2. Evidence Basis

Reviewed:

```text
EduTrust_Payment_Provider_Readiness_v1.0.md
API Architecture v1.0
State Machines v1.1 Addendum
Schema patches v1.1–v1.4
Migration validation reports
UX/prototype financial flows
```

---

# 3. Assessment Matrix

| Area | Assessment | Classification |
|---|---|---|
| MVP pilot payment mode | Controlled mock adapter for DEV/STAGING is ready; real-money pilot requires provider/legal decisions | FACT + REQUIRES LEGAL REVIEW |
| Production payment mode | Not selected | REQUIRES LEGAL REVIEW / PROVIDER CONFIRMATION |
| Provider candidates | CIB, Edahabia, bank transfer, cash/manual, aggregator/gateway | FACT from baseline |
| Webhook capability | Architecturally supported, provider-specific capability unconfirmed | REQUIRES PROVIDER CONFIRMATION |
| Refund capability | Architecturally supported, provider-specific capability unconfirmed | REQUIRES PROVIDER CONFIRMATION |
| Reconciliation | Manual reconciliation supported by architecture | FACT |
| Payout implications | Architecture supports internal payout eligibility; real payouts need legal/accounting path | REQUIRES LEGAL/ACCOUNTING REVIEW |
| Transaction identity | Required by architecture; provider field mapping unconfirmed | REQUIRES PROVIDER CONFIRMATION |
| Provider event identity | Required by architecture; provider support unconfirmed | REQUIRES PROVIDER CONFIRMATION |
| Security | Webhook signature/provider payload protection required | FACT + REQUIRES PROVIDER CONFIRMATION |
| Sandbox/testing | Required; provider availability unconfirmed | REQUIRES PROVIDER CONFIRMATION |
| Operational support | Refund/dispute/reconciliation OPS flows exist | FACT |
| Algerian legal/compliance | Not approved | REQUIRES LEGAL REVIEW |
| Accounting/tax | Not approved | REQUIRES ACCOUNTING REVIEW |
| Data protection | Controls planned, provider payload details unconfirmed | REQUIRES PROVIDER CONFIRMATION |

---

# 4. Minimum Pilot-Safe Workflow

## DEV

Approved mode:

```text
MOCK_PAYMENT_PROVIDER
```

Allowed:

- simulate payment initiation,
- simulate provider webhook events through test-only fixtures,
- test late-payment branch,
- test refunds/reconciliation using mock provider events,
- test ledger/event ledger behavior.

Not allowed:

- real money,
- real customer payment credentials,
- real teacher payouts.

## STAGING

Allowed with:

```text
MOCK or provider SANDBOX only
```

Requirements:

- no real funds,
- no production payment credentials,
- webhook signing simulation or sandbox secrets,
- audit events enabled.

## REAL-MONEY PILOT

Not approved yet.

Minimum requirements before approval:

1. Select provider/mode.
2. Legal review of EduTrust role in funds flow.
3. Accounting review of commissions/refunds/payouts.
4. Provider confirms API, webhook, transaction ID, refund support, sandbox.
5. OPS runbook for reconciliation/refunds/disputes.
6. Security review of provider payloads and webhooks.

## PRODUCTION

Not approved.

Requires full provider/legal/accounting/security readiness.

---

# 5. Provider Candidate Notes

## CIB / Edahabia direct

Status:

```text
REQUIRES PROVIDER CONFIRMATION + LEGAL REVIEW
```

Key questions:

- checkout API?
- webhook/callback?
- signature?
- transaction ID?
- refund API?
- partial refund?
- sandbox?
- settlement?

## Bank transfer

Status:

```text
Operationally possible but manual; REQUIRES LEGAL/ACCOUNTING REVIEW
```

Risks:

- manual ops burden,
- delayed confirmation,
- reconciliation overhead.

## Cash/manual pilot

Status:

```text
Not approved for real-money pilot without legal/accounting review
```

Useful only if strictly controlled and audited.

## Other gateway/aggregator

Status:

```text
Potentially promising, REQUIRES PROVIDER CONFIRMATION
```

Must confirm webhook/refund/sandbox and legal settlement model.

---

# 6. Gate Decision by Environment

| Environment | Payment readiness |
|---|---|
| DEV | APPROVED with mock provider only |
| STAGING | APPROVED with mock/sandbox only |
| PILOT | NOT APPROVED for real money |
| PRODUCTION | NOT APPROVED |

---

# 7. Final Status

```text
Payment Gate Assessment: DEV/STAGING MOCK READY; REAL-MONEY PILOT/PRODUCTION NOT READY
```
