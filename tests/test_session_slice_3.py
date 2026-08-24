from __future__ import annotations

import threading
import uuid

import django
from django.db import connection

django.setup()

from tests.test_foundation import create_admin
from tests.test_payment_slice_2 import make_held_booking, initiate
from tests.test_vertical_slice_1 import create_parent_student, post_json, get_json


def make_scheduled_session():
    teacher, parent_client, parent_auth, booking_id = make_held_booking()
    ptok = parent_auth["access_token"]
    payment = initiate(parent_client, ptok, booking_id).json()["data"]["payment"]
    success = post_json(parent_client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}"}, ptok)
    assert success.status_code == 200, success.content
    session_id = success.json()["data"]["session_id"]
    return teacher, parent_client, parent_auth, booking_id, payment["id"], session_id


def create_completed_session():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    start = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
    assert start.status_code == 200, start.content
    complete = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
    assert complete.status_code == 200, complete.content
    return teacher, parent_client, parent_auth, booking_id, payment_id, session_id


def report_payload():
    return {
        "topics_covered": ["Linear equations", "Functions"],
        "skills_practiced": ["Solving equations", "Graph reading"],
        "participation": "HIGH",
        "teacher_observations": "Good participation; needs practice with word problems.",
        "homework": "Exercises 4, 5, 6.",
        "recommended_revision": "Revise function graphs.",
        "next_objectives": ["Applied problems"],
        "progress_indicator": 2,
    }


def test_session_start_complete_report_parent_read_progress_events():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ttok = teacher["teacher_auth"]["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert report.status_code == 201, report.content
    data = report.json()["data"]
    assert data["progress_events_created"] >= 5
    parent_read = get_json(parent_client, f"/api/v1/sessions/{session_id}/report", ptok)
    assert parent_read.status_code == 200, parent_read.content
    assert len(parent_read.json()["data"]["progress_events"]) == data["progress_events_created"]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='SESSION_STARTED'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='SESSION_COMPLETED'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='REPORT_CREATED'")
        assert cur.fetchone()[0] >= 1


def test_parent_cannot_start_complete_or_create_report_and_foreign_parent_cannot_read_report():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    start_parent = post_json(parent_client, f"/api/v1/sessions/{session_id}/start", {}, ptok)
    assert start_parent.status_code == 403
    complete_parent = post_json(parent_client, f"/api/v1/sessions/{session_id}/complete", {}, ptok)
    assert complete_parent.status_code == 403
    report_parent = post_json(parent_client, f"/api/v1/sessions/{session_id}/report", report_payload(), ptok)
    assert report_parent.status_code == 403
    ttok = teacher["teacher_auth"]["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert report.status_code == 201
    other_parent_client, other_auth, _ = create_parent_student()
    foreign = get_json(other_parent_client, f"/api/v1/sessions/{session_id}/report", other_auth["access_token"])
    assert foreign.status_code == 403


def test_teacher_cannot_modify_another_teacher_session():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    other_teacher_client, other_auth = teacher["teacher_client"].__class__(), None
    # create separate teacher through helper-like direct auth
    from tests.test_vertical_slice_1 import auth_user
    other_teacher_client, other_auth = auth_user("TEACHER", "other-session-teacher")
    denied = post_json(other_teacher_client, f"/api/v1/sessions/{session_id}/start", {}, other_auth["access_token"])
    assert denied.status_code == 403


def test_duplicate_start_complete_are_safe():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    first_start = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
    second_start = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
    assert first_start.status_code == 200 and second_start.status_code == 200
    first_complete = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
    second_complete = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
    assert first_complete.status_code == 200 and second_complete.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT status FROM edutrust.sessions WHERE id=%s", [session_id])
        assert cur.fetchone()[0] == "COMPLETED"


def test_cannot_complete_before_start():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    res = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
    assert res.status_code == 422


def test_student_no_show_by_teacher_and_teacher_no_show_by_admin():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    no_show = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/no-show", {"no_show_type": "STUDENT"}, ttok)
    assert no_show.status_code == 200, no_show.content
    assert no_show.json()["data"]["status"] == "NO_SHOW_STUDENT"

    teacher2, parent_client2, parent_auth2, booking_id2, payment_id2, session_id2 = make_scheduled_session()
    admin_email = f"admin-noshow-{uuid.uuid4()}@example.com"
    create_admin(admin_email)
    admin_login = post_json(parent_client2, "/api/v1/auth/login", {"identifier": admin_email, "password": "StrongPassword123!"})
    atok = admin_login.json()["data"]["access_token"]
    teacher_no_show = post_json(parent_client2, f"/api/v1/sessions/{session_id2}/no-show", {"no_show_type": "TEACHER"}, atok)
    assert teacher_no_show.status_code == 200, teacher_no_show.content
    assert teacher_no_show.json()["data"]["status"] == "NO_SHOW_TEACHER"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='SESSION_NO_SHOW'")
        assert cur.fetchone()[0] >= 2


def test_duplicate_report_and_concurrent_report_creation():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ttok = teacher["teacher_auth"]["access_token"]
    first = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert first.status_code == 201
    dup = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert dup.status_code == 409

    teacher2, parent_client2, parent_auth2, booking_id2, payment_id2, session_id2 = create_completed_session()
    ttok2 = teacher2["teacher_auth"]["access_token"]
    results = []
    def attempt():
        res = post_json(teacher2["teacher_client"], f"/api/v1/sessions/{session_id2}/report", report_payload(), ttok2)
        results.append(res.status_code)
    t1 = threading.Thread(target=attempt); t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 409], results
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.session_reports WHERE session_id=%s", [session_id2])
        assert cur.fetchone()[0] == 1


def test_concurrent_completion_attempts_safe():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    start = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
    assert start.status_code == 200
    results = []
    def attempt():
        res = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
        results.append(res.status_code)
    t1 = threading.Thread(target=attempt); t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results.count(200) == 2, results
    with connection.cursor() as cur:
        cur.execute("SELECT status, attendance_status FROM edutrust.sessions WHERE id=%s", [session_id])
        assert cur.fetchone() == ("COMPLETED", "PRESENT")


def test_admin_report_read_is_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ttok = teacher["teacher_auth"]["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert report.status_code == 201
    admin_email = f"admin-report-{uuid.uuid4()}@example.com"
    create_admin(admin_email)
    admin_login = post_json(parent_client, "/api/v1/auth/login", {"identifier": admin_email, "password": "StrongPassword123!"})
    atok = admin_login.json()["data"]["access_token"]
    admin_read = get_json(parent_client, f"/api/v1/sessions/{session_id}/report", atok)
    assert admin_read.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='session_report'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 1
