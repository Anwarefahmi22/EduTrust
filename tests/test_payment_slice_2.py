from __future__ import annotations

import uuid
from datetime import timedelta

import django
from django.db import connection
from django.utils import timezone

django.setup()

from tests.test_vertical_slice_1 import setup_teacher_with_slot, create_parent_student, post_json, get_json


def make_held_booking():
    teacher = setup_teacher_with_slot()
    parent_client, parent_auth, student_id = create_parent_student()
    token = parent_auth["access_token"]
    hold = post_json(parent_client, "/api/v1/bookings/hold", {"student_id": student_id, "teacher_subject_id": teacher["teacher_subject_id"], "availability_slot_id": teacher["slot_id"]}, token, idem=f"hold-{uuid.uuid4()}")
    assert hold.status_code == 201, hold.content
    return teacher, parent_client, parent_auth, hold.json()["data"]["booking"]["id"]


def initiate(parent_client, token, booking_id, idem=None):
    return post_json(parent_client, "/api/v1/payments/initiate", {"booking_id": booking_id, "provider": "OTHER"}, token, idem=idem or f"pay-{uuid.uuid4()}")


def session_count(booking_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.sessions WHERE booking_id=%s", [booking_id])
        return cur.fetchone()[0]


def event_count(event_type: str, entity_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type=%s AND entity_id=%s", [event_type, entity_id])
        return cur.fetchone()[0]


def test_payment_initiation_pending_and_idempotency():
    _, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    key = f"pay-{uuid.uuid4()}"
    first = initiate(parent_client, token, booking_id, key)
    assert first.status_code == 201, first.content
    payment = first.json()["data"]["payment"]
    assert payment["status"] == "PENDING"
    second = initiate(parent_client, token, booking_id, key)
    assert second.status_code == 201, second.content
    assert second.json()["data"]["payment"]["id"] == payment["id"]
    conflict = post_json(parent_client, "/api/v1/payments/initiate", {"booking_id": str(uuid.uuid4()), "provider": "OTHER"}, token, idem=key)
    assert conflict.status_code == 409


def test_mock_success_confirms_payment_books_booking_and_creates_one_session():
    _, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    event_id = f"evt-{uuid.uuid4()}"
    success = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": event_id}, token)
    assert success.status_code == 200, success.content
    data = success.json()["data"]
    assert data["payment_status"] == "CONFIRMED"
    assert data["booking_status"] == "BOOKED"
    assert data["session_status"] == "SCHEDULED"
    assert session_count(booking_id) == 1
    replay = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": event_id}, token)
    assert replay.status_code == 200
    assert replay.json()["data"]["duplicate"] is True
    assert session_count(booking_id) == 1
    assert event_count("PAYMENT_CONFIRMED", payment["id"]) == 1


def test_mock_failure_does_not_book_or_create_session():
    _, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    fail = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/fail", {"provider_event_id": f"evt-{uuid.uuid4()}"}, token)
    assert fail.status_code == 200, fail.content
    assert fail.json()["data"]["payment_status"] == "FAILED"
    booking = get_json(parent_client, f"/api/v1/bookings/{booking_id}", token).json()["data"]
    assert booking["status"] != "BOOKED"
    assert session_count(booking_id) == 0


def test_late_payment_after_expiry_creates_refund_and_no_session():
    teacher, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.bookings SET hold_expires_at = now() - interval '1 second' WHERE id=%s", [booking_id])
    late = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}"}, token)
    assert late.status_code == 200, late.content
    data = late.json()["data"]
    assert data["payment_status"] == "CONFIRMED"
    assert data["booking_status"] == "EXPIRED"
    assert data["session_id"] is None
    assert data["reconciliation_required"] is True
    assert session_count(booking_id) == 0
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.refunds WHERE payment_id=%s AND status='REQUESTED'", [payment["id"]])
        assert cur.fetchone()[0] == 1


def test_atomicity_rolls_back_payment_booking_session_on_forced_session_failure():
    _, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    res = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}", "force_session_failure": True}, token)
    assert res.status_code == 500
    pay = get_json(parent_client, f"/api/v1/payments/{payment['id']}", token).json()["data"]
    booking = get_json(parent_client, f"/api/v1/bookings/{booking_id}", token).json()["data"]
    assert pay["status"] == "PENDING"
    assert booking["status"] == "PAYMENT_PENDING"
    assert session_count(booking_id) == 0


def test_payment_authorization_parent_isolation_and_teacher_cannot_mutate():
    teacher, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    other_parent_client, other_auth, _ = create_parent_student()
    denied = get_json(other_parent_client, f"/api/v1/payments/{payment['id']}", other_auth["access_token"])
    assert denied.status_code == 403
    teacher_try = post_json(teacher["teacher_client"], f"/api/v1/payments/{payment['id']}/mock/fail", {"provider_event_id": f"evt-{uuid.uuid4()}"}, teacher["teacher_auth"]["access_token"])
    assert teacher_try.status_code == 403


def test_admin_payment_and_event_operational_reads_audited():
    _, parent_client, parent_auth, booking_id = make_held_booking()
    token = parent_auth["access_token"]
    payment = initiate(parent_client, token, booking_id).json()["data"]["payment"]
    post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/fail", {"provider_event_id": f"evt-{uuid.uuid4()}"}, token)
    from tests.test_foundation import create_admin
    admin_email = f"admin-pay-{uuid.uuid4()}@example.com"
    create_admin(admin_email)
    admin_login = post_json(parent_client, "/api/v1/auth/login", {"identifier": admin_email, "password": "StrongPassword123!"})
    admin_token = admin_login.json()["data"]["access_token"]
    payments = get_json(parent_client, "/api/v1/admin/payments", admin_token)
    assert payments.status_code == 200
    events = get_json(parent_client, "/api/v1/admin/events", admin_token)
    assert events.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION'")
        assert cur.fetchone()[0] >= 2
