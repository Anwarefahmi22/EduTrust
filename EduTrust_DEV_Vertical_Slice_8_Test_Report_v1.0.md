# EduTrust — DEV Vertical Slice #8 Test Report v1.0

**Sprint:** DEV Vertical Slice #8 — Refund Operations
**Status:** PASS — 160/160 (118 baseline regression + 42 VS8)
**Runner:** `bash scripts/run_backend_tests.sh` (isolated temporary PostgreSQL 16.2 cluster per run — same pattern as VS1–VS7)
**Runtime environment (reconstructed after sandbox reset, identical to prior slices):** PostgreSQL 16.2 (pgserver wheel binary) with `pgcrypto`/`citext`/`btree_gist` compiled via PGXS from `REL_16_2` source (OpenSSL 3.0.16 + zlib 1.3.1); Python 3.11.2 venv with pinned `requirements.txt`.

---

# 1. Result

```text
160 passed in 328.27s (0:05:28)
```

| Suite | Tests | Result |
|---|---|---|
| Foundation + VS1 + VS2 + VS3 + VS4 + VS5 + VS6 + VS7 (baseline regression) | 118 | PASS (unchanged files, verified by diff) |
| `tests/test_refund_service.py` (new) | 38 | PASS |
| `tests/test_refund_concurrency.py` (new) | 4 | PASS |
| **Total** | **160** | **PASS** |

Baseline arithmetic: foundation 5 · VS2 payment 7 · VS3 session 9 · VS1 5 · VS4 review/dispute 28 · VS5 payout 29 · VS6 moderation 15 · VS7 verification 20 = 118.

# 2. VS8 coverage (test → approved rule)

## Creation (E1)
- `test_refund_creation_request_only_and_events` — `REQUESTED` only, payment untouched, v1.3 state-data cleanliness (no approval/allocation/provider data), events `REFUND_REQUESTED` + `ADMIN_ACTION`, no `PAYMENT_*`, no ledger tx.
- `test_refund_creation_partial_type_derivation` — PARTIAL vs FULL derivation from amount vs payment amount.
- `test_refund_creation_idempotency_replay_conflict_missing_key` — replay (same row), conflict 409 `IDEMPOTENCY_KEY_CONFLICT`, missing key 400 `IDEMPOTENCY_KEY_REQUIRED`.
- `test_refund_creation_authorization_matrix` — PARENT/TEACHER/SUPPORT 403; OPS/ADMIN 201.
- `test_refund_creation_invalid_payment_states` — PENDING/FAILED/unknown → 409 `REFUND_INVALID_STATE` / 404 (contract precondition §12.6).
- `test_refund_over_refund_bound_enforced_at_approval` — Addendum §15.4 bound checked under the payment lock at approval (both `REQUESTED` rows creatable; second approval 409 `OVER_REFUND`).
- `test_refund_approve_over_refund_reservation` — reservation under lock (1200+1200 blocked); creation while `REFUND_PENDING` contract-blocked (409) — plan O7.

## Approval + allocation (E2, D9)
- `test_refund_approve_happy_path_form_d` — `PROVIDER_PENDING` + payment `REFUND_PENDING` + Form D DRAFT ledger (exact accounts/amounts, balanced) + `provider_refund_id` `mock_ref_*` + provider event `refund.initiated` PROCESSED + events.
- `test_refund_approve_allocation_validation` — sum mismatch 400; negative component 400; approved > requested 400; FULL ≠ payment amount 400; PARTIAL ≥ payment amount 400; unknown refund 404.
- `test_refund_approve_idempotency_replay_and_conflict` — replay 200 (single submission), conflict 409.

## Reject / cancel (E3/E4)
- `test_refund_reject_from_requested` — `REJECTED`, payment unchanged, no ledger, terminal reopen 409, short reason 400.
- `test_refund_cancel_requested_no_payment_effect` — `CANCELLED`, payment unchanged.
- `test_refund_cancel_approved_restores_payment_and_voids_ledger` — documented crash-window recovery (raw DB simulation of TX1-without-TX2): cancel from `APPROVED` restores payment to prior state + `VOID`s the DRAFT ledger; subsequent refund proceeds.
- `test_refund_cancel_provider_pending_forbidden` — cancel after submission 409 (SM §14.3 "no provider refund completed").

## Mock results (E5/E6, D2)
- `test_mock_success_full_refund` — `SUCCEEDED` + payment `REFUNDED` + `refunded_at` + ledger `POSTED` balanced + events exact (`REFUND_SUCCEEDED`, `PAYMENT_REFUNDED` once, no `PARTIALLY`) + booking factually untouched (`BOOKED`).
- `test_mock_success_partial_then_remainder_full` — two refunds created while `CONFIRMED`, settled in sequence; cumulative rule → `PARTIALLY_REFUNDED` then `REFUNDED`; over-refund re-check at second approval.
- `test_mock_success_replay_duplicate_no_remutation` — same `provider_event_id` replay → 200 `duplicate:true`, single event row, single ledger tx, single `REFUND_SUCCEEDED`.
- `test_mock_result_dev_guard_forbidden` — 403 `FORBIDDEN` with `MOCK_PAYMENT_PROVIDER_ENABLED=false` (scoped override); operable again once the guard is restored.
- `test_mock_failure_restores_payment_and_voids_ledger` — `FAILED` + `PROVIDER_REFUND_FAILED` + payment restored + ledger `VOIDED` + no `PAYMENT_*` events + recovery via a new request.
- `test_mock_failure_from_disputed_payment_keeps_disputed` — restore target is the prior state (`DISPUTED`), via `metadata.payment_status_before_refund`.
- `test_mock_result_invalid_states` — success on `REQUESTED` 409; on terminal `SUCCEEDED` 409; unknown refund 404; parent 403.
- `test_mock_event_conflict_across_refunds` — same event identity on a different refund → 409 `PAYMENT_PROVIDER_CONFLICT` + committed `SUSPICIOUS_ACTIVITY` security event (survives the main-tx rollback).

## Reconciliation (E7, Addendum §7.3)
- `test_reconcile_success_manual_reconciliation` — `SUCCEEDED` with proof (source/reference/`reconciled_by_user_id` = actor), payment `REFUNDED`, ledger `POSTED`, event order `ADMIN_ACTION` + `REFUND_SUCCEEDED` + `PAYMENT_REFUNDED`.
- `test_reconcile_failure_result` — `FAILED` + `RECONCILIATION_FAILED` + payment restored + ledger `VOIDED` + no `PAYMENT_*`.
- `test_reconcile_proof_validation_errors` — missing/whitespace source/reference, missing `reconciled_at` → `REFUND_RECONCILIATION_PROOF_REQUIRED`; unparseable timestamp, invalid `result`, short reason → `VALIDATION_ERROR`; state untouched.
- `test_reconcile_admin_override_requires_admin` — OPS + `ADMIN_OVERRIDE` 403; ADMIN 200; OPS `MANUAL_RECONCILIATION` 200.
- `test_reconcile_invalid_states` — `REQUESTED` 409; terminal reopen 409.
- `test_reconcile_idempotency` — replay 200 original; conflict 409; missing key 400.

## Admin reads (E8/E9)
- `test_admin_refunds_list_filters_and_pagination` — field set (no raw payload), `status`/`payment_id` filters, `limit` + `next_cursor`/`has_more`.
- `test_admin_refund_detail_shape_and_audit` — timeline, `reconciliation` block, `provider_event_summary[]` (`refund.initiated` + `refund.succeeded`), audit increments (`ADMIN_ACTION` + `ADMIN_ACCESS`), 404, SUPPORT 403.

## Addendum §8 summaries
- `test_payment_booking_dispute_refund_summaries` — `refunds[]` on `GET /payments/:id`, `refund_summary` on `GET /bookings/:id`, `linked_refunds[]` on `GET /disputes/:id`; fields absent when no activity (existing responses unchanged).

## Late refunds + ledger forms
- `test_late_refund_progression_form_l_no_auto_approval` — VS2 branch unchanged (`REQUESTED` FULL, no auto-approval, `PAYMENT_RECONCILIATION_REQUIRED`); progression via approve (0/2000 allocation) + mock success; Form L ledger (`REFUND_PAYABLE`/`PAYMENT_PROVIDER_CLEARING`) DRAFT→`POSTED`; booking `EXPIRED`, zero sessions.
- `test_post_paid_refund_recovery_form_a_payout_untouched` — payout PAID 1700 first; later partial refund (300/100) → Form A ledger (`TEACHER_RECOVERABLE`/`PLATFORM_REFUND_EXPENSE`/clearing) DRAFT→`POSTED`; old PAID payout byte-identical (v1.4).
- `test_payout_blocked_while_refund_in_flight` — approved refund ⇒ payment `REFUND_PENDING` ⇒ payout 422 `NO_CONFIRMED_PAYMENT` (v1 DB guard semantics); still blocked after partial settles; no payout item.
- `test_full_refund_blocks_payout_eligibility` — FULL refund row ⇒ `FULL_REFUND_EXISTS` (VS5 strict rule preserved through the real refund flow).

## Event discipline + terminality
- `test_refund_issued_never_emitted` — zero `REFUND_ISSUED` rows globally after the full happy path; no ledger rows named `REFUND_PROVIDER_PENDING`/`REFUND_RECONCILIATION_REQUIRED` (the non-existent event names from the governance question — verified absent).
- `test_terminal_states_cannot_reopen` — all five re-entry commands 409 on `SUCCEEDED`; DB backstop: raw `UPDATE ... SET status='REQUESTED'` on a terminal row rejected by the v1.2 lifecycle guard.

## Concurrency (`tests/test_refund_concurrency.py`)
- `test_concurrent_approvals_over_refund_exactly_one_wins` — barrier-raced approvals (1200+1200 on 2000): exactly `[200, 409]`; reservation totals 1200.
- `test_concurrent_mock_success_and_reconcile_first_writer_wins` — barrier-raced result paths: `[200, 409]`; refund `SUCCEEDED`; single `POSTED` balanced ledger tx.
- `test_concurrent_same_provider_event_id_single_row` — barrier-raced same event identity: all responses ∈ {200, 409}; exactly one event row (UNIQUE holds); refund `SUCCEEDED`.
- `test_concurrent_creations_serialized_under_payment_lock` — barrier-raced creations serialize under the payment lock; both rows consistent.

# 3. Notes / limitations

- No new dependencies, no new fixtures requiring real providers. All provider interaction is the deterministic DEV mock.
- The Addendum §10.4 net-reduction vector is pinned by the VS5 suite (seeded `APPROVED` refund with payment still `CONFIRMED`); VS8 verifies the real-flow consequence (in-flight block via the v1 guard) — see Implementation Report §"Payout interaction".
- Test isolation: event-count assertions are scoped to the test's own payment/refund (global counters would couple suites).
- One environment note: after the sandbox reset, the PG 16.2 toolchain was reconstructed exactly as in prior slices (pgserver wheel + PGXS-built `pgcrypto`/`citext`/`btree_gist`); the runner and migration chain are unchanged.
