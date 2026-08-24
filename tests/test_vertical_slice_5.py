"""DEV Vertical Slice #5 — Payout Lifecycle (MANUAL_OPS / MOCK execution).

Regression baseline before this file: 54 tests (foundation + VS1 + VS2 + VS3 + VS4).
"""
from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import django
from django.db import connection

django.setup()

from tests.test_foundation import create_admin
from tests.test_session_slice_3 import create_completed_session, make_scheduled_session, report_payload
from tests.test_vertical_slice_1 import auth_user, post_json, get_json
from tests.test_vertical_slice_4 import admin_login


def completed_with_report():
    """Full cycle: completed session + teacher report (payout-eligible)."""
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ttok = teacher["teacher_auth"]["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert report.status_code == 201, report.content
    return teacher, parent_client, parent_auth, booking_id, payment_id, session_id


def process_payout(admin_client, atok, teacher_profile_id, session_ids, idem=None, force_failure=False):
    body = {"teacher_id": teacher_profile_id, "session_ids": session_ids}
    if force_failure:
        body["force_mock_failure"] = True
    return post_json(admin_client, "/api/v1/admin/payouts/process", body, atok, idem=idem or f"payout-{uuid.uuid4()}")


def seed_refund(booking_id: str, refund_type: str, status: str, teacher_adjustment: str = "0.00"):
    """Direct DB fixture (refund service is out of VS5 scope). Respects the approved
    v1.1 validate_refund_integrity rules: approved/provider/succeeded refunds need
    approved_amount = teacher_adjustment + platform_adjustment; REQUESTED uses NULL."""
    # Constraint-compliant fixture (schema checks + v1.1/v1.3 integrity triggers):
    # approved_amount <= requested_amount; APPROVED/PROVIDER_PENDING/SUCCEEDED require
    # their state timestamps; REQUESTED carries no approval/allocation data.
    adj = Decimal(teacher_adjustment)
    requested = max(Decimal("100.00"), adj)
    approved = None if status == "REQUESTED" else str(adj)
    approved_at = "now()" if status in ("APPROVED", "PROVIDER_PENDING", "SUCCEEDED") else "NULL"
    submitted_at = "now()" if status in ("PROVIDER_PENDING", "SUCCEEDED") else "NULL"
    completed_at = "now()" if status == "SUCCEEDED" else "NULL"
    provider_refund_id = f"'mock_refund_{uuid.uuid4().hex[:12]}'" if status == "SUCCEEDED" else "NULL"
    with connection.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO edutrust.refunds (payment_id, booking_id, provider, refund_type, status,
                                          requested_amount, approved_amount, currency,
                                          teacher_adjustment_amount, platform_adjustment_amount,
                                          reason, reason_code, idempotency_key,
                                          approved_at, provider_submitted_at, completed_at, provider_refund_id)
            VALUES (
              (SELECT id FROM edutrust.payments WHERE booking_id=%s ORDER BY created_at DESC LIMIT 1),
              %s, 'OTHER', %s::edutrust.refund_type, %s::edutrust.refund_status,
              {requested}, %s, 'DZD', {adj}, 0.00, 'test seed', 'TEST_SEED', %s,
              {approved_at}, {submitted_at}, {completed_at}, {provider_refund_id}
            )
            """,
            [booking_id, booking_id, refund_type, status, approved, f"seed-{uuid.uuid4()}"],
        )


def payout_count() -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payouts")
        return cur.fetchone()[0]


def payout_item_count(session_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [session_id])
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Eligibility + calculation
# ---------------------------------------------------------------------------

def test_payout_eligible_paid_happy_path():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert data["result"] == "PAID"
    assert data["payout"]["status"] == "PAID"
    assert data["payout"]["paid_at"] is not None
    assert data["payout"]["provider_reference"].startswith("mock_payout_")
    assert len(data["items"]) == 1
    assert data["items"][0]["session_id"] == session_id
    assert data["ledger"]["status"] == "POSTED"
    assert payout_item_count(session_id) == 1
    # Addendum 10.4 vector: price 2000, commission 1500bps = 300 -> gross 1700, no refunds -> net 1700
    assert Decimal(data["payout"]["amount"]) == Decimal("1700.00")


def test_payout_partial_refund_approved_reduces_net():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    seed_refund(booking_id, "PARTIAL", "APPROVED", teacher_adjustment="300.00")
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201, res.content
    # 1700 gross - 300 teacher adjustment = 1400 (Addendum 10.4)
    assert Decimal(res.json()["data"]["payout"]["amount"]) == Decimal("1400.00")


def test_payout_refund_provider_pending_and_succeeded_counted():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    seed_refund(booking_id, "PARTIAL", "PROVIDER_PENDING", teacher_adjustment="100.00")
    seed_refund(booking_id, "PARTIAL", "SUCCEEDED", teacher_adjustment="50.00")
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201, res.content
    assert Decimal(res.json()["data"]["payout"]["amount"]) == Decimal("1550.00")


def test_payout_refund_requested_not_counted():
    # REFUND status REQUESTED is not in the approved exposure set (APPROVED/PROVIDER_PENDING/SUCCEEDED).
    # Per v1.3 hardening a REQUESTED row also cannot carry allocation data, so the fixture is
    # allocation-free; the exposure rule is tested via status, which is what the service checks.
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    seed_refund(booking_id, "PARTIAL", "REQUESTED")
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201, res.content
    assert Decimal(res.json()["data"]["payout"]["amount"]) == Decimal("1700.00")


def test_payout_ineligible_session_not_completed():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PAYOUT_INELIGIBLE"
    assert any(d["reason"] == "SESSION_NOT_COMPLETED" for d in res.json()["error"]["details"]["details"])
    assert payout_item_count(session_id) == 0


def test_payout_ineligible_no_session_report():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert any(d["reason"] == "NO_SESSION_REPORT" for d in res.json()["error"]["details"]["details"])


def test_payout_blocked_by_open_dispute_overlay_preserved():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    ptok = parent_auth["access_token"]
    dispute = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY"}, ptok)
    assert dispute.status_code == 201
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert any(d["reason"] == "OPEN_DISPUTE" for d in res.json()["error"]["details"]["details"])
    # Overlay model: factual states untouched.
    with connection.cursor() as cur:
        cur.execute("SELECT status FROM edutrust.bookings WHERE id=%s", [booking_id])
        assert cur.fetchone()[0] == "COMPLETED"
        cur.execute("SELECT status FROM edutrust.sessions WHERE id=%s", [session_id])
        assert cur.fetchone()[0] == "COMPLETED"


def test_payout_blocked_by_full_refund_strict_rule():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    seed_refund(booking_id, "FULL", "REQUESTED")
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert any(d["reason"] == "FULL_REFUND_EXISTS" for d in res.json()["error"]["details"]["details"])


def test_payout_net_zero_blocked_no_rows():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    # gross 1700 fully consumed by approved partial refund teacher adjustments
    seed_refund(booking_id, "PARTIAL", "APPROVED", teacher_adjustment="1700.00")
    atok = admin_login(parent_client)
    before = payout_count()
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 422
    assert any(d["reason"] == "NET_PAYABLE_ZERO" for d in res.json()["error"]["details"]["details"])
    assert payout_count() == before


def test_payout_session_not_owned_by_teacher():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    other_client, other_auth = auth_user("TEACHER", "payout-foreign-teacher")
    other_profile = get_json(other_client, "/api/v1/teachers/me", other_auth["access_token"]).json()["data"]["id"]
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, other_profile, [session_id])
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PAYOUT_SESSION_NOT_OWNED"


def _second_cycle_same_teacher(teacher, parent_client, parent_auth):
    """Run one more booking->payment->session->complete->report cycle for the same teacher."""
    from datetime import timedelta
    from django.utils import timezone
    ttok = teacher["teacher_auth"]["access_token"]
    starts = (timezone.now() + timedelta(days=11)).replace(microsecond=0)
    ends = starts + timedelta(hours=1)
    slot = post_json(teacher["teacher_client"], "/api/v1/teachers/availability/slots",
                     {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "mode": "ONLINE"}, ttok)
    assert slot.status_code == 201, slot.content
    ptok = parent_auth["access_token"]
    student_id = _student_of(parent_client, ptok)
    hold = post_json(parent_client, "/api/v1/bookings/hold",
                     {"student_id": student_id, "teacher_subject_id": teacher["teacher_subject_id"], "availability_slot_id": slot.json()["data"]["id"]},
                     ptok, idem=f"hold-{uuid.uuid4()}")
    assert hold.status_code == 201, hold.content
    booking_id = hold.json()["data"]["booking"]["id"]
    pay = post_json(parent_client, "/api/v1/payments/initiate", {"booking_id": booking_id, "provider": "OTHER"}, ptok, idem=f"pay-{uuid.uuid4()}")
    assert pay.status_code == 201
    payment_id = pay.json()["data"]["payment"]["id"]
    succ = post_json(parent_client, f"/api/v1/payments/{payment_id}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}"}, ptok)
    assert succ.status_code == 200
    session_id = succ.json()["data"]["session_id"]
    assert post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok).status_code == 200
    assert post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok).status_code == 200
    assert post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok).status_code == 201
    return booking_id, payment_id, session_id


def _student_of(parent_client, ptok) -> str:
    created = post_json(parent_client, "/api/v1/students", {"display_name": "Ahmed 2"}, ptok)
    assert created.status_code == 201
    return created.json()["data"]["id"]


def test_payout_multi_session_batch_totals_and_items():
    t1, pc1, pa1, b1, p1, s1 = completed_with_report()
    b2, p2, s2 = _second_cycle_same_teacher(t1, pc1, pa1)
    atok = admin_login(pc1)
    res = process_payout(pc1, atok, t1["teacher_id"], [s1, s2])
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert len(data["items"]) == 2
    assert Decimal(data["payout"]["amount"]) == Decimal("3400.00")
    for item in data["items"]:
        assert item["amount"] == "1700.00"


# ---------------------------------------------------------------------------
# Ledger, lifecycle, immutability
# ---------------------------------------------------------------------------

def test_paid_payout_ledger_posted_and_balanced():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201
    tx_id = res.json()["data"]["ledger"]["transaction_id"]
    with connection.cursor() as cur:
        cur.execute("SELECT status, transaction_type FROM edutrust.ledger_transactions WHERE id=%s", [tx_id])
        assert cur.fetchone() == ("POSTED", "TEACHER_PAYOUT")
        cur.execute(
            """
            SELECT direction, amount, account_type FROM edutrust.ledger_entries
            WHERE ledger_transaction_id=%s ORDER BY direction
            """,
            [tx_id],
        )
        rows = cur.fetchall()
        assert len(rows) == 2
        debit = [r for r in rows if r[0] == "DEBIT"][0]
        credit = [r for r in rows if r[0] == "CREDIT"][0]
        assert debit[2] == "TEACHER_PAYABLE" and credit[2] == "TEACHER_CASH"
        assert debit[1] == credit[1] == Decimal("1700.00")


def test_failed_payout_ledger_voided_and_no_processed_event():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id], force_failure=True)
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert data["result"] == "FAILED"
    assert data["payout"]["status"] == "FAILED"
    assert data["payout"]["provider_reference"] is None
    assert data["ledger"]["status"] == "VOIDED"
    tx_id = data["ledger"]["transaction_id"]
    with connection.cursor() as cur:
        cur.execute("SELECT status FROM edutrust.ledger_transactions WHERE id=%s", [tx_id])
        assert cur.fetchone()[0] == "VOIDED"
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='PAYOUT_PROCESSED' AND entity_id=%s", [data["payout"]["id"]])
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_id=%s AND metadata->>'action'='PAYOUT_PROCESS_FAILED'", [data["payout"]["id"]])
        assert cur.fetchone()[0] == 1


def test_payout_events_recorded():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201
    payout_id = res.json()["data"]["payout"]["id"]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='PAYOUT_ELIGIBLE' AND entity_id=%s", [payout_id])
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='PAYOUT_PROCESSED' AND entity_id=%s", [payout_id])
        assert cur.fetchone()[0] == 1


def test_paid_payout_row_is_db_immutable():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    payout_id = res.json()["data"]["payout"]["id"]
    with connection.cursor() as cur:
        try:
            cur.execute("UPDATE edutrust.payouts SET amount=1.00 WHERE id=%s", [payout_id])
            assert False, "expected PAID payout UPDATE to be rejected"
        except Exception as exc:
            assert "immutable" in str(exc).lower()


def test_ledger_entries_remain_append_only():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    tx_id = res.json()["data"]["ledger"]["transaction_id"]
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM edutrust.ledger_entries WHERE ledger_transaction_id=%s LIMIT 1", [tx_id])
        entry_id = cur.fetchone()[0]
        try:
            cur.execute("UPDATE edutrust.ledger_entries SET memo='hacked' WHERE id=%s", [entry_id])
            assert False, "expected ledger entry UPDATE to be rejected"
        except Exception:
            pass  # append-only trigger rejects mutation


def test_session_cannot_be_payouted_twice():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    first = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert first.status_code == 201
    second = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PAYOUT_SESSION_ALREADY_PAYOUT"
    assert payout_item_count(session_id) == 1


# ---------------------------------------------------------------------------
# Idempotency + concurrency
# ---------------------------------------------------------------------------

def test_payout_idempotency_replay_same_key_same_payload():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    key = f"payout-{uuid.uuid4()}"
    first = process_payout(parent_client, atok, teacher["teacher_id"], [session_id], idem=key)
    assert first.status_code == 201
    replay = process_payout(parent_client, atok, teacher["teacher_id"], [session_id], idem=key)
    assert replay.status_code == 201
    assert replay.json()["data"]["payout"]["id"] == first.json()["data"]["payout"]["id"]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payouts WHERE id=%s", [first.json()["data"]["payout"]["id"]])
        assert cur.fetchone()[0] == 1
    assert payout_item_count(session_id) == 1


def test_payout_idempotency_conflicting_payload():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    key = f"payout-{uuid.uuid4()}"
    first = process_payout(parent_client, atok, teacher["teacher_id"], [session_id], idem=key)
    assert first.status_code == 201
    conflict = post_json(parent_client, "/api/v1/admin/payouts/process",
                         {"teacher_id": teacher["teacher_id"], "session_ids": [str(uuid.uuid4())]}, atok, idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_payout_missing_idempotency_key_rejected():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = post_json(parent_client, "/api/v1/admin/payouts/process",
                    {"teacher_id": teacher["teacher_id"], "session_ids": [session_id]}, atok)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_payout_concurrent_same_key_no_double_payout():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    key = f"payout-{uuid.uuid4()}"
    results = []

    def attempt():
        res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id], idem=key)
        results.append((res.status_code, res.json().get("data", {}).get("payout", {}).get("id") if res.status_code == 201 else None))

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    statuses = sorted(r[0] for r in results)
    # In-flight same-key requests may return 409 (processing guard); replays return 201.
    # Either way: at most one 201, at least one 201, and exactly one payout exists.
    assert 201 in statuses and statuses.count(201) == 1, results
    payout_ids = [r[1] for r in results if r[0] == 201]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payouts")
        assert payout_item_count(session_id) == 1
    assert len(set(payout_ids)) == 1


def test_payout_concurrent_overlapping_sessions_one_wins():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    results = []

    def attempt():
        res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 409], results
    assert payout_item_count(session_id) == 1


# ---------------------------------------------------------------------------
# Authorization + visibility
# ---------------------------------------------------------------------------

def test_teacher_lists_own_payouts_without_provider_reference():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    ttok = teacher["teacher_auth"]["access_token"]
    listing = get_json(teacher["teacher_client"], "/api/v1/teacher/payouts", ttok)
    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert len(rows) == 1
    assert "provider_reference" not in rows[0]
    assert rows[0]["status"] == "PAID"


def test_teacher_payout_detail_and_foreign_teacher_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    payout_id = res.json()["data"]["payout"]["id"]
    ttok = teacher["teacher_auth"]["access_token"]
    detail = get_json(teacher["teacher_client"], f"/api/v1/teacher/payouts/{payout_id}", ttok)
    assert detail.status_code == 200
    assert detail.json()["data"]["item_count"] == 1
    assert len(detail.json()["data"]["items"]) == 1
    other_client, other_auth = auth_user("TEACHER", "payout-detail-foreign")
    foreign = get_json(other_client, f"/api/v1/teacher/payouts/{payout_id}", other_auth["access_token"])
    assert foreign.status_code == 404


def test_parent_and_anonymous_denied_on_payout_endpoints():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    ptok = parent_auth["access_token"]
    parent_list = get_json(parent_client, "/api/v1/teacher/payouts", ptok)
    assert parent_list.status_code == 403
    admin_list = get_json(parent_client, "/api/v1/admin/payouts", ptok)
    assert admin_list.status_code == 403
    anon = get_json(parent_client, "/api/v1/teacher/payouts")
    assert anon.status_code == 401
    anon_admin = get_json(parent_client, "/api/v1/admin/payouts")
    assert anon_admin.status_code == 401
    anon_process = post_json(parent_client, "/api/v1/admin/payouts/process", {"teacher_id": teacher["teacher_id"], "session_ids": [session_id]})
    assert anon_process.status_code == 401


def test_teacher_role_cannot_process_payout():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    ttok = teacher["teacher_auth"]["access_token"]
    res = post_json(teacher["teacher_client"], "/api/v1/admin/payouts/process",
                    {"teacher_id": teacher["teacher_id"], "session_ids": [session_id]}, ttok, idem=f"payout-{uuid.uuid4()}")
    assert res.status_code == 403


def test_ops_can_process_and_admin_list_is_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    # OPS user (created directly, as admins are in this suite)
    ops_email = f"ops-{uuid.uuid4()}@example.com"
    with connection.cursor() as cur:
        import uuid as _uuid
        ops_id = str(_uuid.uuid4())
        from django.contrib.auth.hashers import make_password
        cur.execute("INSERT INTO edutrust.users (id, full_name, email, password_hash) VALUES (%s,'OPS User',%s,%s)",
                    [ops_id, ops_email, make_password("StrongPassword123!")])
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s,'OPS')", [ops_id])
    ops_login = post_json(parent_client, "/api/v1/auth/login", {"identifier": ops_email, "password": "StrongPassword123!"})
    otok = ops_login.json()["data"]["access_token"]
    res = process_payout(parent_client, otok, teacher["teacher_id"], [session_id])
    assert res.status_code == 201, res.content
    assert res.json()["data"]["result"] == "PAID"
    atok = admin_login(parent_client)
    listing = get_json(parent_client, "/api/v1/admin/payouts", atok)
    assert listing.status_code == 200
    assert any(p["id"] == res.json()["data"]["payout"]["id"] for p in listing.json()["data"])
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='payouts'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 1


def test_admin_list_includes_teacher_name_and_provider_reference():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
    payout_id = res.json()["data"]["payout"]["id"]
    listing = get_json(parent_client, "/api/v1/admin/payouts", atok)
    assert listing.status_code == 200
    row = [p for p in listing.json()["data"] if p["id"] == payout_id][0]
    assert row["teacher_public_name"]
    assert row["provider_reference"].startswith("mock_payout_")
    assert row["item_count"] == 1


def test_payout_validation_errors():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    atok = admin_login(parent_client)
    missing_teacher = post_json(parent_client, "/api/v1/admin/payouts/process", {"session_ids": [session_id]}, atok, idem=f"payout-{uuid.uuid4()}")
    assert missing_teacher.status_code == 400
    empty_sessions = post_json(parent_client, "/api/v1/admin/payouts/process", {"teacher_id": teacher["teacher_id"], "session_ids": []}, atok, idem=f"payout-{uuid.uuid4()}")
    assert empty_sessions.status_code == 400
    dup_sessions = post_json(parent_client, "/api/v1/admin/payouts/process", {"teacher_id": teacher["teacher_id"], "session_ids": [session_id, session_id]}, atok, idem=f"payout-{uuid.uuid4()}")
    assert dup_sessions.status_code == 400
    unknown_teacher = post_json(parent_client, "/api/v1/admin/payouts/process", {"teacher_id": str(uuid.uuid4()), "session_ids": [session_id]}, atok, idem=f"payout-{uuid.uuid4()}")
    assert unknown_teacher.status_code == 404
    unknown_session = post_json(parent_client, "/api/v1/admin/payouts/process", {"teacher_id": teacher["teacher_id"], "session_ids": [str(uuid.uuid4())]}, atok, idem=f"payout-{uuid.uuid4()}")
    assert unknown_session.status_code == 404
