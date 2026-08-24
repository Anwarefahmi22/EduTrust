# EduTrust Algeria — Engineering Governance v1.0

**Product:** EduTrust Algeria  
**MVP:** v0.1  
**Document type:** Engineering governance model  
**Status:** READY FOR REVIEW

---

# 1. Role-Based Ownership

Actual people are unknown; roles are used.

| Role | Ownership |
|---|---|
| Architecture Owner | Preserves locked architecture, approves change requests |
| Backend Owner | Backend modules, service layer, API implementation |
| Frontend Owner | Parent/Teacher/Admin UI implementation |
| Database Owner | Migrations, constraints, SQL review, dry-runs |
| Security Owner | RBAC, privacy, audit, secrets, incident response |
| Payment Owner | Payment/refund/payout workflows, provider integration |
| QA Owner | Test strategy, traceability, release gates |
| Product Lead | UX scope, policy, marketplace behavior |
| Ops Lead | Support workflows, disputes, verification operations |
| Legal/Compliance Advisor | Payment/privacy/legal review |

---

# 2. Module Ownership Model

| Module | Primary owner | Secondary reviewer |
|---|---|---|
| Auth/RBAC | Backend Owner | Security Owner |
| Parent/Student | Backend Owner | Security Owner |
| Teacher/Profile | Backend Owner | Product Lead |
| Verification/Documents | Backend Owner | Security Owner/Ops Lead |
| Availability/Booking | Backend Owner | Database Owner |
| Payment/Webhook | Payment Owner | Database Owner/Security Owner |
| Refunds | Payment Owner | Ops Lead/Database Owner |
| Ledger/Payout | Payment Owner | Database Owner |
| Sessions/Reports/Reviews | Backend Owner | Product Lead |
| Disputes | Ops Lead | Payment Owner/Security Owner |
| Notifications | Backend Owner | Product/Ops |
| Event Ledger/Audit | Security Owner | Database Owner |
| Frontend Parent/Teacher | Frontend Owner | Product Lead |
| Admin UI | Frontend Owner | Ops Lead/Security Owner |
| Testing | QA Owner | Module owners |

---

# 3. Change Request Process

A change request is required for any change to:

- architecture,
- schema,
- state machines,
- payment/refund/payout behavior,
- student privacy model,
- admin override/audit behavior,
- MVP scope,
- UX business logic.

Change request template:

```text
Title
Requester role
Affected artifacts
Current baseline behavior
Requested change
Reason
Risk assessment
Security/privacy impact
Payment/financial impact
Migration impact
Testing impact
Rollback plan
Approval roles required
```

---

# 4. Emergency Change Process

Allowed only for production incidents.

Steps:

1. Incident declared by authorized role.
2. Minimal safe mitigation approved by Architecture Owner + relevant owner.
3. Change logged.
4. Audit/security event recorded where applicable.
5. Post-incident review within agreed SLA.
6. Formal change request created retroactively if baseline changed.

---

# 5. Financial Workflow Change Approval

Changes to payment/refund/payout/ledger require:

```text
Payment Owner
Database Owner
Security Owner
Architecture Owner
Ops Lead
Legal/Compliance Advisor where applicable
```

No single engineer may alter financial state-machine behavior alone.

---

# 6. Security/Privacy Change Approval

Changes to student data, permissions, verification documents, provider payloads, audit logging, or admin sensitive access require:

```text
Security Owner
Architecture Owner
Product Lead or Ops Lead
Legal/Compliance Advisor where applicable
```

---

# 7. Release Gate Ownership

| Gate | Approver roles |
|---|---|
| Implementation Gate | Architecture Owner, Backend Owner, Frontend Owner, QA Owner |
| Payment Gate | Payment Owner, Database Owner, Security Owner |
| Security/Privacy Gate | Security Owner, Legal/Compliance Advisor, Architecture Owner |
| Pilot Launch Gate | Product Lead, Ops Lead, Payment Owner, Security Owner |
| Production Launch Gate | Executive/Product, Legal/Compliance, Engineering, Ops |

---

# 8. Final Status

```text
EduTrust Engineering Governance v1.0 Status: READY FOR REVIEW
```
