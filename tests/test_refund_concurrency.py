"""DEV Vertical Slice #8 — Refund concurrency & idempotency under race.

Plan section 10 (concurrency): global lock order payment -> refund;
over-refund bound recomputed under the payment lock; provider event
identity locked before state mutation; first-writer-wins for concurrent
result paths.
"""
from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import django
from django.db import connection

django.setup()

from tests.test_session_slice_3 import make_scheduled_session
from tests.test_vertical_slice_1 import post_json, get_json
from tests.test_vertical_slice_4 import admin_login
from tests.test_refund_service import (
    create_via_api,
    approve_via_api,
    mock_result,
    reconcile_via_api,
    refund_ledger_tx,
    assert_balanced,
)


def _confirmed() -> tuple:
    # make_scheduled_session already confirms the payment (booking BOOKED, session SCHEDULED)
    return make_scheduled_session()


def test_concurrent_approvals_over_refund_exactly_one_wins():
    _, parent_client, _, _, payment_id, _ = _confirmed()
    atok = admin_login(parent_client)
    r1 = create_via_api(parent_client, atok, payment_id, amount="1200.00").json()["data"]["refund"]["refund_id"]
    r2 = create_via_api(parent_client, atok, payment_id, amount="1200.00").json()["data"]["refund"]["refund_id"]
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt(refund_id):
        barrier.wait()
        res = approve_via_api(parent_client, atok, refund_id, approved="1200.00", teacher="1200.00", platform="0.00")
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt, args=(r1,))
    t2 = threading.Thread(target=attempt, args=(r2,))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [200, 409], results
    # the loser is OVER_REFUND; the winner reserved 1200 of 2000
    with connection.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(approved_amount),0) FROM edutrust.refunds WHERE payment_id=%s AND status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')",
            [payment_id],
        )
        assert Decimal(str(cur.fetchone()[0])) == Decimal("1200.00")


def test_concurrent_mock_success_and_reconcile_first_writer_wins():
    _, parent_client, _, _, payment_id, _ = _confirmed()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    results: list[int] = []
    barrier = threading.Barrier(2)

    def succeed():
        barrier.wait()
        results.append(mock_result(parent_client, atok, refund_id, "succeed").status_code)

    def reconcile():
        barrier.wait()
        results.append(reconcile_via_api(parent_client, atok, refund_id).status_code)

    t1 = threading.Thread(target=succeed)
    t2 = threading.Thread(target=reconcile)
    t1.start(); t2.start(); t1.join(); t2.join()
    # one 200, the other 409 REFUND_INVALID_STATE (lost the race after commit)
    assert sorted(results) == [200, 409], results
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.refunds WHERE id=%s", [refund_id])
        assert cur.fetchone()[0] == "SUCCEEDED"
    tx = refund_ledger_tx(refund_id)
    assert tx["status"] == "POSTED"
    assert_balanced(tx)


def test_concurrent_same_provider_event_id_single_row():
    _, parent_client, _, _, payment_id, _ = _confirmed()
    atok = admin_login(parent_client)
    refund_id = create_via_api(parent_client, atok, payment_id).json()["data"]["refund"]["refund_id"]
    assert approve_via_api(parent_client, atok, refund_id).status_code == 200
    event_id = f"rfevt-{uuid.uuid4()}"
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        results.append(mock_result(parent_client, atok, refund_id, "succeed", event_id=event_id).status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    # exactly one can process; the other replays (200) or is in-flight (409)
    assert all(code in (200, 409) for code in results), results
    assert results.count(200) >= 1
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payment_provider_events WHERE provider_event_id=%s", [event_id])
        assert cur.fetchone()[0] == 1  # UNIQUE(provider, provider_event_id)
        cur.execute("SELECT status::text FROM edutrust.refunds WHERE id=%s", [refund_id])
        assert cur.fetchone()[0] == "SUCCEEDED"


def test_concurrent_creations_serialized_under_payment_lock():
    _, parent_client, _, _, payment_id, _ = _confirmed()
    atok = admin_login(parent_client)
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt(amount):
        barrier.wait()
        res = create_via_api(parent_client, atok, payment_id, amount=amount)
        results.append(res.status_code)

    # 1500 + 1500 > 2000: both fit individually as REQUESTED? No — the
    # creation bound uses reserved (approved+) only, so both can be created;
    # serialization must not corrupt state. Both 201.
    t1 = threading.Thread(target=attempt, args=("1500.00",))
    t2 = threading.Thread(target=attempt, args=("1500.00",))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 201], results
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.refunds WHERE payment_id=%s AND status='REQUESTED'", [payment_id])
        assert cur.fetchone()[0] == 2
