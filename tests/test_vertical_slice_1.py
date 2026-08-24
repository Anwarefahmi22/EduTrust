from __future__ import annotations

import json
import threading
import uuid
from datetime import timedelta

import django
from django.db import connection
from django.utils import timezone
from django.test import Client

django.setup()


def post_json(client: Client, path: str, data: dict, token: str | None = None, idem: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if idem:
        headers["HTTP_IDEMPOTENCY_KEY"] = idem
    return client.post(path, data=json.dumps(data), content_type="application/json", **headers)


def get_json(client: Client, path: str, token: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.get(path, **headers)


def patch_json(client: Client, path: str, data: dict, token: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.patch(path, data=json.dumps(data), content_type="application/json", **headers)


def auth_user(role: str, prefix: str):
    client = Client()
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    password = "StrongPassword123!"
    res = post_json(client, "/api/v1/auth/register", {"role": role, "full_name": f"{role} User", "email": email, "password": password})
    assert res.status_code == 201, res.content
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": password})
    assert login.status_code == 200, login.content
    return client, login.json()["data"]


def seed_taxonomy():
    sid = str(uuid.uuid4())
    lid = str(uuid.uuid4())
    with connection.cursor() as cur:
        cur.execute("INSERT INTO edutrust.subjects (id, code, name_ar, name_en) VALUES (%s, %s, %s, %s)", [sid, f"MATH-{sid[:6]}", "رياضيات", "Mathematics"])
        cur.execute("INSERT INTO edutrust.academic_levels (id, code, name_ar, sort_order) VALUES (%s, %s, %s, %s)", [lid, f"BAC-{lid[:6]}", "بكالوريا", 1])
    return sid, lid


def setup_teacher_with_slot():
    subject_id, level_id = seed_taxonomy()
    teacher_client, teacher_auth = auth_user("TEACHER", "teacher-vs")
    token = teacher_auth["access_token"]
    profile = get_json(teacher_client, "/api/v1/teachers/me", token)
    assert profile.status_code == 200
    teacher_id = profile.json()["data"]["id"]
    update = patch_json(teacher_client, "/api/v1/teachers/me", {"bio": "Math teacher", "teaching_modes": ["ONLINE"]}, token)
    assert update.status_code == 200, update.content
    subj = post_json(teacher_client, "/api/v1/teachers/subjects", {"subject_id": subject_id, "academic_level_id": level_id, "price": {"amount": "2000.00"}, "session_duration_minutes": 60}, token)
    assert subj.status_code == 201, subj.content
    starts = (timezone.now() + timedelta(days=10)).replace(microsecond=0)
    ends = starts + timedelta(hours=1)
    slot = post_json(teacher_client, "/api/v1/teachers/availability/slots", {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "mode": "ONLINE"}, token)
    assert slot.status_code == 201, slot.content
    return {
        "teacher_client": teacher_client,
        "teacher_auth": teacher_auth,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "level_id": level_id,
        "teacher_subject_id": subj.json()["data"]["id"],
        "slot_id": slot.json()["data"]["id"],
        "starts": starts,
        "ends": ends,
    }


def create_parent_student():
    parent_client, parent_auth = auth_user("PARENT", "parent-vs")
    token = parent_auth["access_token"]
    student = post_json(parent_client, "/api/v1/students", {"display_name": "Ahmed"}, token)
    assert student.status_code == 201, student.content
    return parent_client, parent_auth, student.json()["data"]["id"]


def test_teacher_profile_subject_pricing_availability_search_booking_flow():
    teacher = setup_teacher_with_slot()
    parent_client, parent_auth, student_id = create_parent_student()
    ptok = parent_auth["access_token"]

    search = get_json(parent_client, f"/api/v1/teachers/search?subject_id={teacher['subject_id']}&academic_level_id={teacher['level_id']}&mode=ONLINE", ptok)
    assert search.status_code == 200, search.content
    assert any(r["teacher_id"] == teacher["teacher_id"] for r in search.json()["data"])

    profile = get_json(parent_client, f"/api/v1/teachers/{teacher['teacher_id']}", ptok)
    assert profile.status_code == 200
    trust = get_json(parent_client, f"/api/v1/teachers/{teacher['teacher_id']}/trust-profile", ptok)
    assert trust.status_code == 200

    hold = post_json(parent_client, "/api/v1/bookings/hold", {"student_id": student_id, "teacher_subject_id": teacher["teacher_subject_id"], "availability_slot_id": teacher["slot_id"]}, ptok, idem=f"hold-{uuid.uuid4()}")
    assert hold.status_code == 201, hold.content
    booking_id = hold.json()["data"]["booking"]["id"]

    confirm = post_json(parent_client, f"/api/v1/bookings/{booking_id}/confirm", {}, ptok)
    assert confirm.status_code == 200, confirm.content
    assert confirm.json()["data"]["booking_status"] == "BOOKED"

    parent_bookings = get_json(parent_client, "/api/v1/bookings", ptok)
    assert parent_bookings.status_code == 200
    assert any(b["id"] == booking_id for b in parent_bookings.json()["data"])

    teacher_bookings = get_json(teacher["teacher_client"], "/api/v1/bookings?scope=teacher", teacher["teacher_auth"]["access_token"])
    assert teacher_bookings.status_code == 200
    assert any(b["id"] == booking_id for b in teacher_bookings.json()["data"])


def test_availability_overlap_block_unblock_and_unauthorized_mutation():
    teacher = setup_teacher_with_slot()
    token = teacher["teacher_auth"]["access_token"]
    # overlap blocked by DB exclusion constraint
    overlap = post_json(teacher["teacher_client"], "/api/v1/teachers/availability/slots", {"starts_at": teacher["starts"].isoformat(), "ends_at": teacher["ends"].isoformat(), "mode": "ONLINE"}, token)
    assert overlap.status_code == 409

    # create non-overlap then block/unblock
    starts = teacher["ends"] + timedelta(hours=1)
    ends = starts + timedelta(hours=1)
    slot = post_json(teacher["teacher_client"], "/api/v1/teachers/availability/slots", {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "mode": "ONLINE"}, token)
    assert slot.status_code == 201, slot.content
    sid = slot.json()["data"]["id"]
    block = post_json(teacher["teacher_client"], f"/api/v1/teachers/availability/slots/{sid}/block", {"reason": "busy"}, token)
    assert block.status_code == 200, block.content
    unblock = post_json(teacher["teacher_client"], f"/api/v1/teachers/availability/slots/{sid}/unblock", {"reason": "free"}, token)
    assert unblock.status_code == 200, unblock.content

    other_teacher_client, other_auth = auth_user("TEACHER", "other-teacher")
    denied = post_json(other_teacher_client, f"/api/v1/teachers/availability/slots/{sid}/block", {"reason": "hack"}, other_auth["access_token"])
    assert denied.status_code == 404


def test_booking_hold_expiration_and_blocked_slot():
    teacher = setup_teacher_with_slot()
    parent_client, parent_auth, student_id = create_parent_student()
    ptok = parent_auth["access_token"]
    hold = post_json(parent_client, "/api/v1/bookings/hold", {"student_id": student_id, "teacher_subject_id": teacher["teacher_subject_id"], "availability_slot_id": teacher["slot_id"]}, ptok, idem=f"hold-{uuid.uuid4()}")
    assert hold.status_code == 201
    booking_id = hold.json()["data"]["booking"]["id"]
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.bookings SET hold_expires_at = now() - interval '1 second' WHERE id=%s", [booking_id])
    confirm = post_json(parent_client, f"/api/v1/bookings/{booking_id}/confirm", {}, ptok)
    assert confirm.status_code == 409


def test_booking_same_slot_concurrency_one_success_one_conflict():
    teacher = setup_teacher_with_slot()
    parent_a, auth_a, student_a = create_parent_student()
    parent_b, auth_b, student_b = create_parent_student()
    results = []

    def attempt(client, token, student):
        res = post_json(client, "/api/v1/bookings/hold", {"student_id": student, "teacher_subject_id": teacher["teacher_subject_id"], "availability_slot_id": teacher["slot_id"]}, token, idem=f"hold-{uuid.uuid4()}")
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt, args=(parent_a, auth_a["access_token"], student_a))
    t2 = threading.Thread(target=attempt, args=(parent_b, auth_b["access_token"], student_b))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 409], results


def test_database_regression_smoke_for_payout_refund_idempotency():
    # Database migration has v1.4 trigger and critical functions/triggers available.
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_trigger tr JOIN pg_class c ON c.oid=tr.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='edutrust' AND c.relname='payouts' AND tr.tgname='trg_00_payouts_paid_immutable_v1_4'")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='edutrust' AND p.proname IN ('validate_refund_hardening_v1_3','validate_api_idempotency_lifecycle_v1_3','validate_provider_event_lifecycle_v1_2')")
        assert cur.fetchone()[0] == 3
