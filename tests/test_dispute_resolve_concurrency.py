"""DEV Vertical Slice #9 — Dispute Resolution concurrency (plan section 23 C-01..C-04).

Lock order under test: dispute -> session (no-show) -> payment -> booking,
acyclic with the VS5 payout order (session -> payment) and the VS8 refund order
(payment -> refund -> booking). Exactly one authoritative transition per race;
no double refund, no double ledger posting, no double payout.
"""
from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import django
from django.db import connection

django.setup()

from tests.test_session_slice_3 import create_completed_session
from tests.test_vertical_slice_1 import post_json
from tests.test_vertical_slice_4 import admin_login
from tests.test_vertical_slice_5 import completed_with_report, process_payout
from tests.test_vertical_slice_6 import seed_operator


def login_op(client, email: str) -> str:
    res = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    assert res.status_code == 200, res.content
    return res.json()["data"]["access_token"]


def open_dispute(client, token, body: dict, idem=None):
    return post_json(client, "/api/v1/disputes", body, token, idem=idem or f"disp-{uuid.uuid4()}")


def resolve(client, token, dispute_id: str, body: dict, idem=None):
    return post_json(client, f"/api/v1/admin/disputes/{dispute_id}/resolve", body, token, idem=idem or f"disp-res-{uuid.uuid4()}")


def test_c01_two_operators_resolve_same_dispute():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ops1 = login_op(parent_client, seed_operator("OPS", "vs9c-ops1"))
    ops2 = login_op(parent_client, seed_operator("OPS", "vs9c-ops2"))
    d = open_dispute(parent_client, ptok, {"session_id": session_id, "category": "OTHER", "description": "concurrent resolution"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt(tok, res_text):
        barrier.wait()
        res = resolve(parent_client, tok, dispute_id, {"resolution": res_text, "action": "NO_ACTION"})
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt, args=(ops1, "operator one resolution"))
    t2 = threading.Thread(target=attempt, args=(ops2, "operator two resolution"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [200, 409], results
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.disputes WHERE id=%s", [dispute_id])
        status = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edutrust.disputes WHERE id=%s", [dispute_id])
        count = cur.fetchone()[0]
    assert status == "RESOLVED" and count == 1
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1  # exactly one authoritative transition


def test_c02_concurrent_approves_over_refund_race():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ops = login_op(parent_client, seed_operator("OPS", "vs9c-ops3"))
    # two REQUESTED 1500 refunds: one via dispute resolve, one direct VS8 create
    d = open_dispute(parent_client, ptok, {"session_id": session_id, "category": "SESSION_QUALITY", "description": "over-refund race"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    r_resolve = resolve(parent_client, ops, dispute_id, {"resolution": "race refund one", "action": "PARTIAL_REFUND", "refund_amount": "1500.00"})
    assert r_resolve.status_code == 200, r_resolve.content
    rid_a = r_resolve.json()["data"]["refund"]["refund_id"]
    c = post_json(parent_client, f"/api/v1/payments/{payment_id}/refund", {"amount": "1500.00", "currency": "DZD", "reason": "race refund two"}, ops, idem=f"ref-{uuid.uuid4()}")
    assert c.status_code == 201, c.content
    rid_b = c.json()["data"]["refund"]["refund_id"]
    assert reserved(payment_id) == Decimal("0.00")  # REQUESTED rows do not reserve
    results: list[int] = []
    barrier = threading.Barrier(2)

    def approve(rid):
        barrier.wait()
        res = post_json(parent_client, f"/api/v1/admin/refunds/{rid}/approve",
                        {"approved_amount": "1500.00", "teacher_adjustment_amount": "1500.00", "platform_adjustment_amount": "0.00"},
                        ops, idem=f"ref-{uuid.uuid4()}")
        results.append(res.status_code)

    t1 = threading.Thread(target=approve, args=(rid_a,))
    t2 = threading.Thread(target=approve, args=(rid_b,))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [200, 409], results  # exactly one approve survives (Addendum 15.4 under lock)
    assert reserved(payment_id) <= Decimal(payment_amount(payment_id))  # no over-refund at rest
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.ledger_transactions WHERE reference IN (%s, %s) AND status='POSTED'", [f"refund-{rid_a}", f"refund-{rid_b}"])
        assert cur.fetchone()[0] == 0  # neither approved refund is SUCCEEDED yet — no double posting


def reserved(payment_id: str) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(approved_amount),0) FROM edutrust.refunds WHERE payment_id=%s AND status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')", [payment_id])
        return Decimal(str(cur.fetchone()[0]))


def payment_amount(payment_id: str) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("SELECT amount::text FROM edutrust.payments WHERE id=%s", [payment_id])
        return Decimal(cur.fetchone()[0])


def test_c03_resolve_no_action_vs_payout_processing_race():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    ptok = parent_auth["access_token"]
    atok = admin_login(parent_client)
    d = open_dispute(parent_client, ptok, {"session_id": session_id, "category": "SESSION_QUALITY", "description": "resolve vs payout race"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    results: dict = {}
    barrier = threading.Barrier(2)

    def do_payout():
        barrier.wait()
        res = process_payout(parent_client, atok, teacher["teacher_id"], [session_id])
        results["payout"] = res.status_code

    def do_resolve():
        barrier.wait()
        res = resolve(parent_client, atok, dispute_id, {"resolution": "race resolution", "action": "NO_ACTION"})
        results["resolve"] = res.status_code

    t1 = threading.Thread(target=do_payout)
    t2 = threading.Thread(target=do_resolve)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results["resolve"] == 200, results  # resolve always succeeds (dispute was OPEN at its check)
    # payout is either blocked (dispute OPEN at its check) or paid (resolve committed first) —
    # never paid-while-open, never double
    assert results["payout"] in (422, 201), results
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [session_id])
        items = cur.fetchone()[0]
    if results["payout"] == 422:
        assert items == 0
    else:
        assert items == 1  # exactly one payout item — no double payout


def test_c04_same_idempotency_key_concurrent():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ops = login_op(parent_client, seed_operator("OPS", "vs9c-ops4"))
    d = open_dispute(parent_client, ptok, {"session_id": session_id, "category": "OTHER", "description": "same key concurrent"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    key = f"disp-res-{uuid.uuid4()}"
    body = {"resolution": "same key concurrent resolve", "action": "NO_ACTION"}
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        res = resolve(parent_client, ops, dispute_id, body, idem=key)
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    # one 200 + (200 replay of the stored response | 409 in-flight) — never two resolutions
    assert sorted(results) in ([200, 200], [200, 409]), results
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.disputes WHERE id=%s", [dispute_id])
        status = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edutrust.disputes WHERE id=%s", [dispute_id])
        count = cur.fetchone()[0]
    assert status == "RESOLVED" and count == 1
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1
