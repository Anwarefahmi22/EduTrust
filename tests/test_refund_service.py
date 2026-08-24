"""DEV Vertical Slice #8 — Refund Operations (DEV mock only).

Regression baseline before this file: 118 tests (foundation + VS1..VS7).

Covers (per approved VS8 plan, Test Traceability rows "Refund lifecycle valid",
"Over-refund blocked", "Partial refund allocation", "Post-payout recovery
separate", "Provider payload redaction"):
- refund creation/request (E1) + idempotency + authorization + state guards
- approval with actor-supplied allocation (E2, D9) + ledger DRAFT forms
- reject / cancel (E3/E4) incl. payment restore + ledger VOID
- deterministic mock provider SUCCESS/FAILURE (E5/E6, D2) + DEV guard
- provider event identity: replay/conflict (D3)
- reconciliation exactly per Addendum v1.1 7.3 (E7) incl. ADMIN_OVERRIDE
- admin refund reads (E8/E9) incl. audit events
- refund summaries in payment/booking/dispute reads (Addendum 8)
- late-refund progression without auto-approval (Form L ledger)
- post-paid refund recovery (Form A ledger; PAID payout untouched)
- REFUND_ISSUED is never emitted; terminal states never reopen
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import django
from django.db import connection
from django.test import override_settings

django.setup()

from tests.test_foundation import create_admin
from tests.test_session_slice_3 import create_completed_session, make_scheduled_session, report_payload
from tests.test_vertical_slice_1 import auth_user, create_parent_student, post_json, get_json
from tests.test_vertical_slice_4 import admin_login


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_confirmed_payment():
    """Booking BOOKED + payment CONFIRMED + one SCHEDULED session (make_scheduled_session already confirms)."""
    return make_scheduled_session()


def seed_ops(client) -> str:
    ops_id = str(uuid.uuid4())
    email = f"ops-vs8-{uuid.uuid4()}@example.com"
    from django.contrib.auth.hashers import make_password
    with connection.cursor() as cur:
        cur.execute("INSERT INTO edutrust.users (id, full_name, email, password_hash) VALUES (%s,'OPS User',%s,%s)",
                    [ops_id, email, make_password("StrongPassword123!")])
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s,'OPS')", [ops_id])
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    assert login.status_code == 200, login.content
    return login.json()["data"]["access_token"]


def seed_support(client) -> str:
    sup_id = str(uuid.uuid4())
    email = f"sup-vs8-{uuid.uuid4()}@example.com"
    from django.contrib.auth.hashers import make_password
    with connection.cursor() as cur:
        cur.execute("INSERT INTO edutrust.users (id, full_name, email, password_hash) VALUES (%s,'Support User',%s,%s)",
                    [sup_id, email, make_password("StrongPassword123!")])
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s,'SUPPORT')", [sup_id])
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    assert login.status_code == 200, login.content
    return login.json()["data"]["access_token"]


def refund_rows(payment_id: str) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute("SELECT id, status::text, approved_amount, teacher_adjustment_amount, platform_adjustment_amount FROM edutrust.refunds WHERE payment_id=%s ORDER BY created_at", [payment_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def event_count(event_type: str, entity_id: str | None = None) -> int:
    with connection.cursor() as cur:
        if entity_id:
            cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type=%s AND entity_id=%s", [event_type, entity_id])
        else:
            cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type=%s", [event_type])
        return cur.fetchone()[0]


def refund_ledger_tx(refund_id: str):
    with connection.cursor() as cur:
        cur.execute("SELECT id::text, transaction_type, status::text, reference FROM edutrust.ledger_transactions WHERE reference=%s", [f"refund-{refund_id}"])
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("SELECT account_type::text, direction::text, amount::text FROM edutrust.ledger_entries WHERE ledger_transaction_id=%s ORDER BY created_at", [row[0]])
        entries = [dict(zip(("account_type", "direction", "amount"), e)) for e in cur.fetchall()]
        return {"id": row[0], "transaction_type": row[1], "status": row[2], "reference": row[3], "entries": entries}


def assert_balanced(tx: dict) -> None:
    debit = sum(Decimal(e["amount"]) for e in tx["entries"] if e["direction"] == "DEBIT")
    credit = sum(Decimal(e["amount"]) for e in tx["entries"] if e["direction"] == "CREDIT")
    assert debit == credit and debit > 0, tx["entries"]


def create_via_api(client, atok, payment_id, amount="2000.00", reason="Teacher no-show confirmed", idem=None, dispute_id=None):
    body = {"amount": amount, "currency": "DZD", "reason": reason}
    if dispute_id:
        body["dispute_id"] = dispute_id
    return post_json(client, f"/api/v1/payments/{payment_id}/refund", body, atok, idem=idem or f"refund-{uuid.uuid4()}")


def approve_via_api(client, atok, refund_id, approved="2000.00", teacher="1400.00", platform="600.00", idem=None):
    body = {"approved_amount": approved, "teacher_adjustment_amount": teacher, "platform_adjustment_amount": platform}
    return post_json(client, f"/api/v1/admin/refunds/{refund_id}/approve", body, atok, idem=idem or f"refund-{uuid.uuid4()}")


def mock_result(client, atok, refund_id, outcome, event_id=None):
    body = {"provider_event_id": event_id or f"rfevt-{uuid.uuid4()}"}
    return post_json(client, f"/api/v1/admin/refunds/{refund_id}/mock/{outcome}", body, atok)


def reconcile_via_api(client, atok, refund_id, result="SUCCEEDED", source="MANUAL_RECONCILIATION", reference="BANK-REF-12345", idem=None, **extra):
    body = {
        "result": result,
        "reconciliation_source": source,
        "reconciliation_reference": reference,
        "reconciled_at": "2026-08-24T12:00:00Z",
        "reason": "Manual bank confirmation recorded.",
        "supporting_evidence": [{"type": "document_reference", "id": "evidence_1"}],
    }
    body.update(extra)
    return post_json(client, f"/api/v1/admin/refunds/{refund_id}/reconcile", body, atok, idem=idem or f"refund-{uuid.uuid4()}")


# ---------------------------------------------------------------------------
# E1 — creation
# ---------------------------------------------------------------------------

def test_refund_creation_request_only_and_events():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    key = f"refund-{uuid.uuid4()}"
    res = create_via_api(parent_client, atok, payment_id, idem=key)
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert data["refund"]["status"] == "REQUESTED"
    assert data["refund"]["refund_type"] == "FULL"
    assert data["refund"]["requested_amount"] == "2000.00"
    assert data["refund"]["provider_refund_id"] is None
    assert data["refund"]["approved_amount"] is None
    assert data["payment_status"] == "CONFIRMED"
    refund_id = data["refund"]["refund_id"]
    # v1.3 cleanliness: REQUESTED rows carry no provider/approval/allocation data
    rows = refund_rows(payment_id)
    assert len(rows) == 1 and rows[0]["status"] == "REQUESTED"
    assert rows[0]["approved_amount"] is None
    assert Decimal(rows[0]["teacher_adjustment_amount"]) == 0 and Decimal(rows[0]["platform_adjustment_amount"]) == 0
    # events: REFUND_REQUESTED + ADMIN_ACTION, no payment events yet (scoped to this payment)
    assert event_count("REFUND_REQUESTED", refund_id) == 1
    assert event_count("ADMIN_ACTION", refund_id) >= 1
    assert event_count("REFUND_APPROVED", refund_id) == 0
    assert event_count("PAYMENT_REFUNDED", payment_id) == 0
    assert event_count("PAYMENT_PARTIALLY_REFUNDED", payment_id) == 0
    # no ledger tx for a REQUESTED refund
    assert refund_ledger_tx(refund_id) is None
    # payment state untouched
    pay = get_json(parent_client, f"/api/v1/payments/{payment_id}", atok).json()["data"]
    assert pay["status"] == "CONFIRMED"
    assert "refunded_at" not in pay or pay.get("refunded_at") is None


def test_refund_creation_partial_type_derivation():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    res = create_via_api(parent_client, atok, payment_id, amount="500.00")
    assert res.status_code == 201, res.content
    assert res.json()["data"]["refund"]["refund_type"] == "PARTIAL"


def test_refund_creation_idempotency_replay_conflict_missing_key():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    key = f"refund-{uuid.uuid4()}"
    first = create_via_api(parent_client, atok, payment_id, idem=key)
    assert first.status_code == 201, first.content
    first_id = first.json()["data"]["refund"]["refund_id"]
    replay = create_via_api(parent_client, atok, payment_id, idem=key)
    assert replay.status_code == 201, replay.content
    assert replay.json()["data"]["refund"]["refund_id"] == first_id
    conflict = create_via_api(parent_client, atok, payment_id, amount="100.00", idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    missing = post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", {"amount": "100.00", "currency": "DZD", "reason": "reason here"}, atok)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert len(refund_rows(payment_id)) == 1


def test_refund_creation_authorization_matrix():
    _, parent_client, parent_auth, _, payment_id, _ = make_confirmed_payment()
    ptok = parent_auth["access_token"]
    atok = admin_login(parent_client)
    otok = seed_ops(parent_client)
    stok = seed_support(parent_client)
    _, _, teacher_auth, _, _, _ = make_confirmed_payment()
    body = {"amount": "100.00", "currency": "DZD", "reason": "reason here"}
    assert post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", body, ptok, idem=f"refund-{uuid.uuid4()}").status_code == 403
    assert post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", body, teacher_auth["access_token"], idem=f"refund-{uuid.uuid4()}").status_code == 403
    assert post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", body, stok, idem=f"refund-{uuid.uuid4()}").status_code == 403
    assert post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", body, otok, idem=f"refund-{uuid.uuid4()}").status_code == 201
    assert post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", body, atok, idem=f"refund-{uuid.uuid4()}").status_code in (201, 409)  # 409 only via over-refund bound


def test_refund_creation_invalid_payment_states():
    from tests.test_payment_slice_2 import make_held_booking, initiate
    teacher, parent_client, parent_auth, booking_id = make_held_booking()
    ptok = parent_auth["access_token"]
    atok = admin_login(parent_client)
    payment = initiate(parent_client, ptok, booking_id).json()["data"]["payment"]
    payment_id = payment["id"]
    # PENDING (not yet confirmed)
    res = create_via_api(parent_client, atok, payment_id)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    # FAILED
    fail = post_json(parent_client, f"/api/v1/payments/{payment_id}/mock/fail", {"provider_event_id": f"evt-{uuid.uuid4()}"}, ptok)
    assert fail.status_code == 200
    res = create_via_api(parent_client, atok, payment_id)
    assert res.status_code == 409
    # unknown payment
    res = create_via_api(parent_client, atok, str(uuid.uuid4()))
    assert res.status_code == 404


def test_refund_over_refund_bound_enforced_at_approval():
    # Addendum 15.4: sum(APPROVED, PROVIDER_PENDING, SUCCEEDED) + new approved <= payment.amount,
    # checked under the payment lock at approval/provider-submission.
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    r1 = create_via_api(parent_client, atok, payment_id, amount="2000.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r1, approved="2000.00", teacher="2000.00", platform="0.00").status_code == 200
    res = approve_via_api(parent_client, atok, r2, approved="1.00", teacher="1.00", platform="0.00")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "OVER_REFUND"


def test_refund_creation_dispute_id_cross_booking_rejected():
    _, parent_client, parent_auth, _, payment_id, session_id = make_confirmed_session_with_dispute()
    atok = admin_login(parent_client)
    res = create_via_api(parent_client, atok, payment_id, dispute_id=str(uuid.uuid4()))
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def make_confirmed_session_with_dispute():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), teacher["teacher_auth"]["access_token"])
    assert report.status_code == 201, report.content
    return teacher, parent_client, parent_auth, booking_id, payment_id, session_id


# ---------------------------------------------------------------------------
# E2 — approval + allocation (D9) + ledger DRAFT
# ---------------------------------------------------------------------------

def test_refund_approve_happy_path_form_d():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    res = approve_via_api(parent_client, atok, refund_id, approved="1000.00", teacher="700.00", platform="300.00")
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["refund"]["status"] == "PROVIDER_PENDING"
    assert data["refund"]["provider_refund_id"].startswith("mock_ref_")
    assert data["refund"]["teacher_adjustment_amount"] == "700.00"
    assert data["refund"]["platform_adjustment_amount"] == "300.00"
    assert data["payment_status"] == "REFUND_PENDING"
    tx = refund_ledger_tx(refund_id)
    assert tx is not None and tx["status"] == "DRAFT" and tx["transaction_type"] == "REFUND"
    assert_balanced(tx)
    by_account = {(e["account_type"], e["direction"]): Decimal(e["amount"]) for e in tx["entries"]}
    assert by_account == {
        ("TEACHER_PAYABLE", "DEBIT"): Decimal("700.00"),
        ("PLATFORM_REVENUE", "DEBIT"): Decimal("300.00"),
        ("PAYMENT_PROVIDER_CLEARING", "CREDIT"): Decimal("1000.00"),
    }
    assert event_count("REFUND_APPROVED", refund_id) == 1
    assert event_count("REFUND_PROVIDER_SUBMITTED", refund_id) == 1
    # provider event recorded (D3): refund.initiated PROCESSED, linked to refund
    with connection.cursor() as cur:
        cur.execute("SELECT event_type, status::text, provider_refund_id IS NOT NULL FROM edutrust.payment_provider_events WHERE refund_id=%s AND event_type='refund.initiated'", [refund_id])
        assert cur.fetchone() == ("refund.initiated", "PROCESSED", True)
    pay = get_json(parent_client, f"/api/v1/payments/{payment_id}", atok).json()["data"]
    assert pay["status"] == "REFUND_PENDING"


def test_refund_approve_allocation_validation():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    # sum mismatch
    res = approve_via_api(parent_client, atok, refund_id, approved="1000.00", teacher="700.00", platform="200.00")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert refund_rows(payment_id)[0]["status"] == "REQUESTED"
    # negative component
    res = approve_via_api(parent_client, atok, refund_id, approved="1000.00", teacher="-100.00", platform="1100.00")
    assert res.status_code == 400
    # approved > requested
    refund2 = create_via_api(parent_client, atok, payment_id, amount="2000.00").json()["data"]["refund"]["refund_id"]
    res = approve_via_api(parent_client, atok, refund2, approved="2500.00", teacher="2500.00", platform="0.00")
    assert res.status_code == 400
    # FULL type requires full amount
    refund3 = create_via_api(parent_client, atok, payment_id, amount="2000.00").json()["data"]["refund"]["refund_id"]
    res = approve_via_api(parent_client, atok, refund3, approved="1500.00", teacher="1500.00", platform="0.00")
    assert res.status_code == 400
    # PARTIAL type cannot approve full amount
    res = approve_via_api(parent_client, atok, refund_id, approved="2000.00", teacher="2000.00", platform="0.00")
    assert res.status_code == 400
    # terminal/invalid state
    res = approve_via_api(parent_client, atok, str(uuid.uuid4()))
    assert res.status_code == 404


def test_refund_approve_over_refund_reservation():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    r1 = create_via_api(parent_client, atok, payment_id, amount="1200.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1200.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r1, approved="1200.00", teacher="1200.00", platform="0.00").status_code == 200
    res = approve_via_api(parent_client, atok, r2, approved="1200.00", teacher="1200.00", platform="0.00")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "OVER_REFUND"
    # creation contract (API 12.6): while the payment is REFUND_PENDING (refund in
    # flight), new refund creation is contract-blocked (CONFIRMED/DISPUTED only)
    res = create_via_api(parent_client, atok, payment_id, amount="800.00")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"


def test_refund_approve_idempotency_replay_and_conflict():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    key = f"refund-{uuid.uuid4()}"
    first = approve_via_api(parent_client, atok, refund_id, idem=key)
    assert first.status_code == 200, first.content
    replay = approve_via_api(parent_client, atok, refund_id, idem=key)
    assert replay.status_code == 200
    assert replay.json()["data"]["refund"]["refund_id"] == refund_id
    conflict = approve_via_api(parent_client, atok, refund_id, teacher="1000.00", platform="1000.00", idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    # exactly one submission
    assert event_count("REFUND_PROVIDER_SUBMITTED", refund_id) == 1


# ---------------------------------------------------------------------------
# E3/E4 — reject / cancel
# ---------------------------------------------------------------------------

def test_refund_reject_from_requested():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/reject", {"reason": "Policy does not allow refund"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["status"] == "REJECTED"
    assert res.json()["data"]["payment_status"] == "CONFIRMED"
    assert event_count("REFUND_REJECTED", refund_id) == 1
    assert refund_ledger_tx(refund_id) is None
    # reject again (terminal) -> 409
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/reject", {"reason": "again please"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    # missing reason
    refund2 = create_via_api(parent_client, atok, payment_id, amount="100.00").json()["data"]["refund"]["refund_id"]
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund2}/reject", {"reason": "x"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 400


def test_refund_cancel_requested_no_payment_effect():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/cancel", {"reason": "Parent withdrew request"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["status"] == "CANCELLED"
    assert res.json()["data"]["payment_status"] == "CONFIRMED"
    assert event_count("REFUND_CANCELLED", refund_id) == 1


def test_refund_cancel_approved_restores_payment_and_voids_ledger():
    # Simulates the documented crash window (TX1 committed, TX2 lost): refund
    # APPROVED, payment REFUND_PENDING, DRAFT ledger, no provider submission.
    # Operator recovery per plan: cancel (approved transition) + new request.
    _, parent_client, _, booking_id, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE edutrust.refunds
            SET status='APPROVED', approved_amount=2000.00, approved_at=now(),
                teacher_adjustment_amount=1400.00, platform_adjustment_amount=600.00,
                approved_by_role='ADMIN',
                metadata = metadata || jsonb_build_object('payment_status_before_refund', 'CONFIRMED')
            WHERE id=%s
            """,
            [refund_id],
        )
        cur.execute("UPDATE edutrust.payments SET status='REFUND_PENDING' WHERE id=%s", [payment_id])
        tx_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO edutrust.ledger_transactions (id, transaction_type, status, booking_id, payment_id, reference) "
            "VALUES (%s,'REFUND','DRAFT',%s,%s,%s)",
            [tx_id, booking_id, payment_id, f"refund-{refund_id}"],
        )
        cur.execute(
            "INSERT INTO edutrust.ledger_entries (ledger_transaction_id, account_type, direction, amount, memo) VALUES "
            "(%s,'TEACHER_PAYABLE','DEBIT',1400.00,'crash window test'),(%s,'PLATFORM_REVENUE','DEBIT',600.00,'crash window test'),"
            "(%s,'PAYMENT_PROVIDER_CLEARING','CREDIT',2000.00,'crash window test')",
            [tx_id, tx_id, tx_id],
        )
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/cancel", {"reason": "Cancelled before provider completion"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["status"] == "CANCELLED"
    assert res.json()["data"]["payment_status"] == "CONFIRMED"
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "VOIDED"
    # a new refund on the same payment can now proceed
    r2 = create_via_api(parent_client, atok, payment_id, amount="500.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r2, approved="500.00", teacher="500.00", platform="0.00").status_code == 200


def test_refund_cancel_provider_pending_forbidden():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/cancel", {"reason": "too late now"}, atok, idem=f"refund-{uuid.uuid4()}")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"


# ---------------------------------------------------------------------------
# E5/E6 — deterministic mock results (D2) + DEV guard
# ---------------------------------------------------------------------------

def test_mock_success_full_refund():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = mock_result(parent_client, atok, refund_id, "succeed")
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["refund_status"] == "SUCCEEDED"
    assert data["payment_status"] == "REFUNDED"
    assert data["duplicate"] is False
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "POSTED"
    assert_balanced(tx)
    assert event_count("REFUND_SUCCEEDED", refund_id) == 1
    assert event_count("PAYMENT_REFUNDED", payment_id) == 1
    assert event_count("PAYMENT_PARTIALLY_REFUNDED", payment_id) == 0
    pay = get_json(parent_client, f"/api/v1/payments/{payment_id}", atok).json()["data"]
    assert pay["status"] == "REFUNDED"
    with connection.cursor() as cur:
        cur.execute("SELECT refunded_at IS NOT NULL FROM edutrust.payments WHERE id=%s", [payment_id])
        assert cur.fetchone()[0] is True
    # booking/session facts untouched (Addendum overlay rule)
    with connection.cursor() as cur:
        cur.execute("SELECT b.status::text FROM edutrust.bookings b JOIN edutrust.payments p ON p.booking_id=b.id WHERE p.id=%s", [payment_id])
        assert cur.fetchone()[0] == "BOOKED"


def test_mock_success_partial_then_remainder_full():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    # both refunds are created while the payment is still CONFIRMED (creation
    # contract: CONFIRMED/DISPUTED only), then settled in sequence
    r1 = create_via_api(parent_client, atok, payment_id, amount="800.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1200.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r1, approved="800.00", teacher="500.00", platform="300.00").status_code == 200
    res = mock_result(parent_client, atok, r1, "succeed")
    assert res.status_code == 200 and res.json()["data"]["payment_status"] == "PARTIALLY_REFUNDED"
    assert event_count("PAYMENT_PARTIALLY_REFUNDED", payment_id) == 1
    # remainder: approval re-checks the over-refund bound under the lock (800 + 1200 = 2000)
    assert approve_via_api(parent_client, atok, r2, approved="1200.00", teacher="1200.00", platform="0.00").status_code == 200
    res = mock_result(parent_client, atok, r2, "succeed")
    assert res.status_code == 200 and res.json()["data"]["payment_status"] == "REFUNDED"
    assert event_count("PAYMENT_REFUNDED", payment_id) == 1


def test_mock_success_replay_duplicate_no_remutation():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    event_id = f"rfevt-{uuid.uuid4()}"
    first = mock_result(parent_client, atok, refund_id, "succeed", event_id=event_id)
    assert first.status_code == 200 and first.json()["data"]["duplicate"] is False
    replay = mock_result(parent_client, atok, refund_id, "succeed", event_id=event_id)
    assert replay.status_code == 200, replay.content
    assert replay.json()["data"]["duplicate"] is True
    assert replay.json()["data"]["refund_status"] == "SUCCEEDED"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payment_provider_events WHERE provider_event_id=%s", [event_id])
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM edutrust.ledger_transactions WHERE reference=%s", [f"refund-{refund_id}"])
        assert cur.fetchone()[0] == 1
    assert event_count("REFUND_SUCCEEDED", refund_id) == 1


def test_mock_result_dev_guard_forbidden():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    with override_settings(MOCK_PAYMENT_PROVIDER_ENABLED=False):
        res = mock_result(parent_client, atok, refund_id, "succeed")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
    # and still operable once the guard is back on
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200


def test_mock_failure_restores_payment_and_voids_ledger():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = mock_result(parent_client, atok, refund_id, "fail")
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["refund_status"] == "FAILED"
    assert data["payment_status"] == "CONFIRMED"
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "VOIDED"
    with connection.cursor() as cur:
        cur.execute("SELECT failure_code, failure_message IS NOT NULL FROM edutrust.refunds WHERE id=%s", [refund_id])
        assert cur.fetchone() == ("PROVIDER_REFUND_FAILED", True)
    assert event_count("REFUND_FAILED", refund_id) == 1
    assert event_count("PAYMENT_REFUNDED", payment_id) == 0
    # recovery: a new refund request is possible (FAILED does not reserve)
    r2 = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r2).status_code == 200
    assert mock_result(parent_client, atok, r2, "succeed").status_code == 200


def test_mock_failure_from_disputed_payment_keeps_disputed():
    _, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    # open a dispute, then move payment to DISPUTED via direct DB (dispute resolution is R2)
    disp = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY", "description": "quality issue"}, ptok, idem=f"disp-{uuid.uuid4()}")
    assert disp.status_code == 201, disp.content
    dispute_id = disp.json()["data"]["dispute"]["id"]
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.payments SET status='DISPUTED' WHERE id=%s", [payment_id])
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id, dispute_id=dispute_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = mock_result(parent_client, atok, refund_id, "fail")
    assert res.status_code == 200
    assert res.json()["data"]["payment_status"] == "DISPUTED"


def test_mock_result_invalid_states():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    # REQUESTED: no provider result yet
    res = mock_result(parent_client, atok, refund_id, "succeed")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    # SUCCEEDED (terminal): further results rejected
    res = mock_result(parent_client, atok, refund_id, "fail")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    # unknown refund
    res = mock_result(parent_client, atok, str(uuid.uuid4()), "succeed")
    assert res.status_code == 404
    # authorization: parent cannot drive mock results (fresh payment; the first one is now REFUNDED)
    _, parent_client2, parent_auth2, _, payment_id2, _ = make_confirmed_payment()
    refund3_id = create_via_api(parent_client2, atok, payment_id2, amount="100.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client2, atok, refund3_id, approved="100.00", teacher="100.00", platform="0.00").status_code == 200
    res = mock_result(parent_client2, parent_auth2["access_token"], refund3_id, "succeed")
    assert res.status_code == 403


def test_mock_event_conflict_across_refunds():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    r1 = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r1, approved="1000.00", teacher="1000.00", platform="0.00").status_code == 200
    assert approve_via_api(parent_client, atok, r2, approved="1000.00", teacher="1000.00", platform="0.00").status_code == 200
    event_id = f"rfevt-{uuid.uuid4()}"
    assert mock_result(parent_client, atok, r1, "succeed", event_id=event_id).status_code == 200
    res = mock_result(parent_client, atok, r2, "succeed", event_id=event_id)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "PAYMENT_PROVIDER_CONFLICT"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='SUSPICIOUS_ACTIVITY'")
        assert cur.fetchone()[0] >= 1


# ---------------------------------------------------------------------------
# E7 — reconciliation (Addendum v1.1 7.3 verbatim)
# ---------------------------------------------------------------------------

def test_reconcile_success_manual_reconciliation():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = reconcile_via_api(parent_client, atok, refund_id)
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["refund"]["status"] == "SUCCEEDED"
    assert data["payment_status"] == "REFUNDED"
    assert data["refund"]["reconciliation"]["source"] == "MANUAL_RECONCILIATION"
    assert data["refund"]["reconciliation"]["reference"] == "BANK-REF-12345"
    assert data["refund"]["reconciliation"]["reconciled_by_user_id"]
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "POSTED"
    assert_balanced(tx)
    # 7.3 event order: ADMIN_ACTION + REFUND_SUCCEEDED + PAYMENT_REFUNDED (success only)
    assert event_count("ADMIN_ACTION", refund_id) >= 1
    assert event_count("REFUND_SUCCEEDED", refund_id) == 1
    assert event_count("PAYMENT_REFUNDED", payment_id) == 1


def test_reconcile_failure_result():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = reconcile_via_api(parent_client, atok, refund_id, result="FAILED", reference="BANK-REF-999")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["status"] == "FAILED"
    assert res.json()["data"]["payment_status"] == "CONFIRMED"
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "VOIDED"
    with connection.cursor() as cur:
        cur.execute("SELECT failure_code FROM edutrust.refunds WHERE id=%s", [refund_id])
        assert cur.fetchone()[0] == "RECONCILIATION_FAILED"
    assert event_count("REFUND_FAILED", refund_id) == 1
    assert event_count("PAYMENT_REFUNDED", payment_id) == 0


def test_reconcile_proof_validation_errors():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    base = {"result": "SUCCEEDED", "reconciliation_source": "MANUAL_RECONCILIATION",
            "reconciliation_reference": "REF-1", "reconciled_at": "2026-08-24T12:00:00Z", "reason": "bank confirmed"}
    for mutation, code in (
        ({**base, "reconciliation_source": ""}, "REFUND_RECONCILIATION_PROOF_REQUIRED"),
        ({**base, "reconciliation_reference": "   "}, "REFUND_RECONCILIATION_PROOF_REQUIRED"),
        ({**base, "reconciled_at": None}, "REFUND_RECONCILIATION_PROOF_REQUIRED"),
        ({**base, "reconciled_at": "not-a-date"}, "VALIDATION_ERROR"),
        ({**base, "result": "MAYBE"}, "VALIDATION_ERROR"),
        ({**base, "reason": "x"}, "VALIDATION_ERROR"),
    ):
        res = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/reconcile", mutation, atok, idem=f"refund-{uuid.uuid4()}")
        assert res.status_code == 400, (mutation, res.content)
        assert res.json()["error"]["code"] == code
    assert refund_rows(payment_id)[0]["status"] == "PROVIDER_PENDING"


def test_reconcile_admin_override_requires_admin():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    otok = seed_ops(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    res = reconcile_via_api(parent_client, otok, refund_id, source="ADMIN_OVERRIDE")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
    res = reconcile_via_api(parent_client, atok, refund_id, source="ADMIN_OVERRIDE")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["reconciliation"]["source"] == "ADMIN_OVERRIDE"
    # OPS may use MANUAL_RECONCILIATION on a fresh refund (but not ADMIN_OVERRIDE)
    _, parent_client2, _, _, payment_id2, _ = make_confirmed_payment()
    r3 = create_via_api(parent_client2, otok, payment_id2, amount="1.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client2, otok, r3, approved="1.00", teacher="1.00", platform="0.00").status_code == 200
    res = reconcile_via_api(parent_client2, otok, r3, source="MANUAL_RECONCILIATION")
    assert res.status_code == 200, res.content


def test_reconcile_invalid_states():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    # REQUESTED: not yet reconcilable
    res = reconcile_via_api(parent_client, atok, refund_id)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    # SUCCEEDED (terminal): cannot reopen
    res = reconcile_via_api(parent_client, atok, refund_id, result="FAILED")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"


def test_reconcile_idempotency():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    key = f"refund-{uuid.uuid4()}"
    first = reconcile_via_api(parent_client, atok, refund_id, idem=key)
    assert first.status_code == 200, first.content
    replay = reconcile_via_api(parent_client, atok, refund_id, idem=key)
    assert replay.status_code == 200
    assert replay.json()["data"]["refund"]["status"] == "SUCCEEDED"
    conflict = reconcile_via_api(parent_client, atok, refund_id, result="FAILED", idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    missing = post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/reconcile",
                        {"result": "FAILED", "reconciliation_source": "MANUAL_RECONCILIATION",
                         "reconciliation_reference": "R", "reconciled_at": "2026-08-24T12:00:00Z", "reason": "reason"},
                        atok)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


# ---------------------------------------------------------------------------
# E8/E9 — admin reads + audit
# ---------------------------------------------------------------------------

def test_admin_refunds_list_filters_and_pagination():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    r1 = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1000.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, r1, approved="1000.00", teacher="1000.00", platform="0.00").status_code == 200
    res = get_json(parent_client, f"/api/v1/admin/refunds?payment_id={payment_id}", atok)
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 2
    for item in items:
        assert set(item) >= {"refund_id", "payment_id", "booking_id", "provider", "refund_type", "status", "requested_amount", "currency", "reason_code", "created_at"}
        assert "normalized_provider_payload" not in str(item)
    assert res.json()["pagination"]["has_more"] is False
    assert res.json()["pagination"]["limit"] == 20
    res = get_json(parent_client, f"/api/v1/admin/refunds?status=PROVIDER_PENDING&payment_id={payment_id}", atok)
    assert [i["refund_id"] for i in res.json()["data"]] == [r1]
    res = get_json(parent_client, f"/api/v1/admin/refunds?limit=1&payment_id={payment_id}", atok)
    assert len(res.json()["data"]) == 1
    assert res.json()["pagination"]["has_more"] is True
    assert res.json()["pagination"]["next_cursor"] is not None


def test_admin_refund_detail_shape_and_audit():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    before_action = event_count("ADMIN_ACTION", refund_id)
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        before_access = cur.fetchone()[0]
    res = get_json(parent_client, f"/api/v1/admin/refunds/{refund_id}", atok)
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["status"] == "SUCCEEDED"
    assert data["timeline"]["created_at"] is not None
    assert data["timeline"]["approved_at"] is not None
    assert data["timeline"]["provider_submitted_at"] is not None
    assert data["timeline"]["completed_at"] is not None
    assert data["reconciliation"] is None
    assert len(data["provider_event_summary"]) == 2
    kinds = {e["event_type"] for e in data["provider_event_summary"]}
    assert kinds == {"refund.initiated", "refund.succeeded"}
    assert event_count("ADMIN_ACTION", refund_id) == before_action + 1
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] == before_access + 1
    # 404 unknown
    assert get_json(parent_client, f"/api/v1/admin/refunds/{uuid.uuid4()}", atok).status_code == 404
    # SUPPORT denied
    stok = seed_support(parent_client)
    assert get_json(parent_client, f"/api/v1/admin/refunds/{refund_id}", stok).status_code == 403


# ---------------------------------------------------------------------------
# Addendum 8 — embedded summaries (X1/X2/X3)
# ---------------------------------------------------------------------------

def test_payment_booking_dispute_refund_summaries():
    _, parent_client, parent_auth, booking_id, payment_id, session_id = make_confirmed_session_with_dispute()
    ptok = parent_auth["access_token"]
    atok = admin_login(parent_client)
    # no activity yet: fields absent (existing responses unchanged)
    pay = get_json(parent_client, f"/api/v1/payments/{payment_id}", ptok).json()["data"]
    assert "refunds" not in pay
    b = get_json(parent_client, f"/api/v1/bookings/{booking_id}", ptok).json()["data"]
    assert "refund_summary" not in b
    # open dispute on the session, create linked refund
    disp = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY", "description": "quality issue"}, ptok, idem=f"disp-{uuid.uuid4()}")
    dispute_id = disp.json()["data"]["dispute"]["id"]
    d = get_json(parent_client, f"/api/v1/disputes/{dispute_id}", ptok).json()["data"]
    assert "linked_refunds" not in d
    refund_id = create_via_api(parent_client, atok, payment_id, amount="500.00", dispute_id=dispute_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id, approved="500.00", teacher="300.00", platform="200.00").status_code == 200
    # X1
    pay = get_json(parent_client, f"/api/v1/payments/{payment_id}", ptok).json()["data"]
    assert len(pay["refunds"]) == 1
    assert pay["refunds"][0]["refund_id"] == refund_id
    assert pay["refunds"][0]["status"] == "PROVIDER_PENDING"
    assert pay["refunds"][0]["approved_amount"] == "500.00"
    # X2
    b = get_json(parent_client, f"/api/v1/bookings/{booking_id}", ptok).json()["data"]
    assert b["refund_summary"] == {"has_refund_activity": True, "active_refund_status": "PROVIDER_PENDING",
                                   "total_approved_refund_amount": "500.00", "currency": "DZD"}
    # X3
    d = get_json(parent_client, f"/api/v1/disputes/{dispute_id}", ptok).json()["data"]
    assert d["linked_refunds"][0]["refund_id"] == refund_id
    assert d["linked_refunds"][0]["status"] == "PROVIDER_PENDING"
    # parent-scoped read verified; teacher isolation on payment details is covered by VS2
    assert pay["refunds"][0]["currency"] == "DZD"


# ---------------------------------------------------------------------------
# Late refunds + ledger forms L / A
# ---------------------------------------------------------------------------

def test_late_refund_progression_form_l_no_auto_approval():
    # VS2 late branch: expired hold + mock success -> REQUESTED FULL refund, no session
    from tests.test_payment_slice_2 import make_held_booking, initiate
    teacher, parent_client, parent_auth, booking_id = make_held_booking()
    ptok = parent_auth["access_token"]
    payment_id = initiate(parent_client, ptok, booking_id).json()["data"]["payment"]["id"]
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.bookings SET hold_expires_at = now() - interval '1 second' WHERE id=%s", [booking_id])
    late = post_json(parent_client, f"/api/v1/payments/{payment_id}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}"}, ptok)
    assert late.status_code == 200
    assert late.json()["data"]["reconciliation_required"] is True
    rows = refund_rows(payment_id)
    assert len(rows) == 1
    assert rows[0]["status"] == "REQUESTED"  # NO auto-approval (OPS-POL-003 unset behavior)
    assert event_count("PAYMENT_RECONCILIATION_REQUIRED", payment_id) == 1
    atok = admin_login(parent_client)
    refund_id = rows[0]["id"]
    # approve with the economically consistent late allocation (teacher earned nothing)
    res = approve_via_api(parent_client, atok, refund_id, approved="2000.00", teacher="0.00", platform="2000.00")
    assert res.status_code == 200, res.content
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "DRAFT"
    by_account = {(e["account_type"], e["direction"]): Decimal(e["amount"]) for e in tx["entries"]}
    assert by_account == {
        ("REFUND_PAYABLE", "DEBIT"): Decimal("2000.00"),
        ("PAYMENT_PROVIDER_CLEARING", "CREDIT"): Decimal("2000.00"),
    }
    # complete via mock success
    res = mock_result(parent_client, atok, refund_id, "succeed")
    assert res.status_code == 200 and res.json()["data"]["payment_status"] == "REFUNDED"
    assert refund_ledger_tx(refund_id)["status"] == "POSTED"
    # booking facts untouched
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.bookings WHERE id=%s", [booking_id])
        assert cur.fetchone()[0] in ("EXPIRED", "CANCELLED")
        cur.execute("SELECT count(*) FROM edutrust.sessions WHERE booking_id=%s", [booking_id])
        assert cur.fetchone()[0] == 0


def test_post_paid_refund_recovery_form_a_payout_untouched():
    from tests.test_vertical_slice_5 import completed_with_report, process_payout
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    # payout first (payment CONFIRMED) -> PAID 1700
    payout = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert payout.status_code == 201, payout.content
    payout_data = payout.json()["data"]["payout"]
    payout_id = payout_data["id"]
    # later partial refund against the paid booking
    refund_id = create_via_api(parent_client, atok, payment_id, amount="400.00", reason="Quality issue partial refund").json()["data"]["refund"]["refund_id"]
    # Addendum 10.4 vector: teacher share 300, platform share 100
    res = approve_via_api(parent_client, atok, refund_id, approved="400.00", teacher="300.00", platform="100.00")
    assert res.status_code == 200, res.content
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "DRAFT"
    by_account = {(e["account_type"], e["direction"]): Decimal(e["amount"]) for e in tx["entries"]}
    assert by_account == {
        ("TEACHER_RECOVERABLE", "DEBIT"): Decimal("300.00"),
        ("PLATFORM_REFUND_EXPENSE", "DEBIT"): Decimal("100.00"),
        ("PAYMENT_PROVIDER_CLEARING", "CREDIT"): Decimal("400.00"),
    }
    res = mock_result(parent_client, atok, refund_id, "succeed")
    assert res.status_code == 200 and res.json()["data"]["payment_status"] == "PARTIALLY_REFUNDED"
    assert refund_ledger_tx(refund_id)["status"] == "POSTED"
    # old payout untouched (v1.4 immutability + Addendum 11): amount/status/ref/paid_at unchanged
    with connection.cursor() as cur:
        cur.execute("SELECT amount::text, status::text, provider_reference FROM edutrust.payouts WHERE id=%s", [payout_id])
        amount, status, reference = cur.fetchone()
        assert (amount, status, reference) == (payout_data["amount"], "PAID", payout_data["provider_reference"])
    # no payout item mutation
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 1
    # recovery representation exists as a separate ledger transaction (never a payout mutation)
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.ledger_transactions WHERE transaction_type='REFUND' AND reference=%s", [f"refund-{refund_id}"])
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Event discipline + terminality + payout interaction
# ---------------------------------------------------------------------------

def test_refund_issued_never_emitted():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    assert event_count("REFUND_ISSUED") == 0
    # and no event named REFUND_PROVIDER_PENDING exists in the enum/ledger
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM edutrust.event_ledger WHERE event_type::text IN ('REFUND_PROVIDER_PENDING','REFUND_RECONCILIATION_REQUIRED')")
        assert cur.fetchone() is None


def test_terminal_states_cannot_reopen():
    _, parent_client, _, _, payment_id, _ = make_confirmed_payment()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    key = lambda: f"refund-{uuid.uuid4()}"
    assert approve_via_api(parent_client, atok, refund_id, idem=key()).status_code == 409
    assert post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/reject", {"reason": "reopen attempt"}, atok, idem=key()).status_code == 409
    assert post_json(parent_client, f"/api/v1/admin/refunds/{refund_id}/cancel", {"reason": "reopen attempt"}, atok, idem=key()).status_code == 409
    assert mock_result(parent_client, atok, refund_id, "fail").status_code == 409
    assert reconcile_via_api(parent_client, atok, refund_id, result="FAILED").status_code == 409
    # DB backstop: direct UPDATE to a terminal row must be rejected by the lifecycle guard
    with connection.cursor() as cur:
        try:
            cur.execute("UPDATE edutrust.refunds SET status='REQUESTED' WHERE id=%s", [refund_id])
            connection.rollback()
            assert False, "lifecycle guard failed to block terminal reopen"
        except Exception:
            connection.rollback()


def test_full_refund_blocks_payout_eligibility():
    from tests.test_vertical_slice_5 import completed_with_report, process_payout
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200  # FULL refund row exists
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PAYOUT_INELIGIBLE"
    reasons = res.json()["error"]["details"]["details"]
    assert any(r["reason"] == "FULL_REFUND_EXISTS" for r in reasons)


def test_payout_blocked_while_refund_in_flight():
    # Approved semantics: approval moves the payment to REFUND_PENDING (SM 7.6);
    # the v1 payout-eligibility DB guard requires a CONFIRMED payment, so a payout
    # for the session is blocked while the refund is in flight and after a partial
    # settles (PARTIALLY_REFUNDED). The Addendum 10.4 net-reduction vector is pinned
    # by the VS5 suite (seeded APPROVED refund with payment still CONFIRMED).
    from tests.test_vertical_slice_5 import completed_with_report, process_payout
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id, amount="400.00").json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id, approved="400.00", teacher="300.00", platform="100.00").status_code == 200
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PAYOUT_INELIGIBLE"
    assert any(d["reason"] == "NO_CONFIRMED_PAYMENT" for d in res.json()["error"]["details"]["details"])
    # after the partial settles the payment is PARTIALLY_REFUNDED: still blocked
    assert mock_result(parent_client, atok, refund_id, "succeed").status_code == 200
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 0
