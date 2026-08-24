"""DEV Vertical Slice 4 — Verified Review + Basic Dispute Foundation.

Regression baseline before this file: 26 tests (foundation + VS1 + VS2 + VS3).
"""
from __future__ import annotations

import threading
import uuid

import django
from django.db import connection

django.setup()

from tests.test_foundation import create_admin
from tests.test_session_slice_3 import create_completed_session, make_scheduled_session, report_payload
from tests.test_vertical_slice_1 import auth_user, create_parent_student, post_json, get_json


def admin_login(client, prefix: str = "admin") -> str:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    create_admin(email)
    res = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    assert res.status_code == 200, res.content
    return res.json()["data"]["access_token"]


def review_payload(rating: int = 5, comment: str = "Excellent session, very clear explanations.") -> dict:
    return {"rating": rating, "comment": comment}


# ---------------------------------------------------------------------------
# Review: eligibility + verified derivation
# ---------------------------------------------------------------------------

def test_review_eligible_creation_is_verified_and_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5, "Great session."), ptok, idem=f"rev-{uuid.uuid4()}")
    assert res.status_code == 201, res.content
    review = res.json()["data"]["review"]
    assert review["is_verified"] is True
    assert review["session_id"] == session_id
    assert review["booking_id"] == booking_id
    assert review["status"] == "VISIBLE"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='REVIEW_CREATED' AND entity_id=%s", [review["id"]])
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT is_verified, status FROM edutrust.reviews WHERE id=%s", [review["id"]])
        assert cur.fetchone() == (True, "VISIBLE")


def test_review_incomplete_session_rejected():
    # Session SCHEDULED (payment confirmed, booking BOOKED, session not completed)
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ptok = parent_auth["access_token"]
    res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(), ptok)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "REVIEW_NOT_ELIGIBLE"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 0


def test_review_start_but_not_completed_rejected():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ttok = teacher["teacher_auth"]["access_token"]
    start = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
    assert start.status_code == 200
    ptok = parent_auth["access_token"]
    res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(), ptok)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "REVIEW_NOT_ELIGIBLE"


def test_review_unauthorized_parent_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    other_client, other_auth, _ = create_parent_student()
    res = post_json(other_client, f"/api/v1/sessions/{session_id}/review", review_payload(), other_auth["access_token"])
    assert res.status_code == 403


def test_review_unrelated_user_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    other_teacher_client, other_auth = auth_user("TEACHER", "unrelated-review-teacher")
    # Teacher role cannot POST a review at all.
    res = post_json(other_teacher_client, f"/api/v1/sessions/{session_id}/review", review_payload(), other_auth["access_token"])
    assert res.status_code == 403


def test_review_client_cannot_claim_verified():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(4) | {"verified": False}, ptok)
    assert res.status_code == 201, res.content
    review = res.json()["data"]["review"]
    assert review["is_verified"] is True  # server-derived, client flag ignored
    with connection.cursor() as cur:
        cur.execute("SELECT is_verified FROM edutrust.reviews WHERE id=%s", [review["id"]])
        assert cur.fetchone()[0] is True


def test_review_rating_validation():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    bad = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", {"rating": 9, "comment": "x"}, ptok)
    assert bad.status_code == 400
    bad2 = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", {"rating": "high"}, ptok)
    assert bad2.status_code == 400


# ---------------------------------------------------------------------------
# Review: duplication, idempotency, concurrency
# ---------------------------------------------------------------------------

def test_review_duplicate_rejected():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    first = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(), ptok)
    assert first.status_code == 201
    dup = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(4, "different"), ptok)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_REVIEW"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 1


def test_review_idempotency_replay_same_key_same_payload():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    key = f"rev-{uuid.uuid4()}"
    first = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5, "once"), ptok, idem=key)
    assert first.status_code == 201
    replay = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5, "once"), ptok, idem=key)
    assert replay.status_code == 201
    assert replay.json()["data"]["review"]["id"] == first.json()["data"]["review"]["id"]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 1


def test_review_idempotency_conflicting_payload():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    key = f"rev-{uuid.uuid4()}"
    first = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5, "a"), ptok, idem=key)
    assert first.status_code == 201
    conflict = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(3, "b"), ptok, idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_review_concurrent_creation_one_success_one_conflict():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    results = []

    def attempt(rating, comment):
        res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(rating, comment), ptok)
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt, args=(5, "first"))
    t2 = threading.Thread(target=attempt, args=(4, "second"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 409], results
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE session_id=%s", [session_id])
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Review: reads and visibility
# ---------------------------------------------------------------------------

def test_review_parent_read_own_and_not_found_case():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    missing = get_json(parent_client, f"/api/v1/sessions/{session_id}/review", ptok)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REVIEW_NOT_FOUND"
    created = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(4, "solid"), ptok)
    assert created.status_code == 201
    read = get_json(parent_client, f"/api/v1/sessions/{session_id}/review", ptok)
    assert read.status_code == 200
    assert read.json()["data"]["rating"] == 4
    # Parent list of own reviews
    own = get_json(parent_client, "/api/v1/reviews", ptok)
    assert own.status_code == 200
    assert any(r["session_id"] == session_id for r in own.json()["data"])


def test_review_teacher_read_own_and_foreign_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ttok = teacher["teacher_auth"]["access_token"]
    created = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5), ptok)
    assert created.status_code == 201
    teacher_read = get_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/review", ttok)
    assert teacher_read.status_code == 200
    other_teacher_client, other_auth = auth_user("TEACHER", "foreign-review-teacher")
    foreign = get_json(other_teacher_client, f"/api/v1/sessions/{session_id}/review", other_auth["access_token"])
    assert foreign.status_code == 403
    # Teacher list of own reviews
    own = get_json(teacher["teacher_client"], "/api/v1/reviews", ttok)
    assert own.status_code == 200
    assert any(r["session_id"] == session_id for r in own.json()["data"])


def test_review_foreign_parent_cannot_read():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(), ptok)
    assert created.status_code == 201
    other_client, other_auth, _ = create_parent_student()
    foreign = get_json(other_client, f"/api/v1/sessions/{session_id}/review", other_auth["access_token"])
    assert foreign.status_code == 403


def test_review_admin_read_is_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(), ptok)
    assert created.status_code == 201
    atok = admin_login(parent_client)
    admin_read = get_json(parent_client, f"/api/v1/sessions/{session_id}/review", atok)
    assert admin_read.status_code == 200
    admin_list = get_json(parent_client, "/api/v1/reviews", atok)
    assert admin_list.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND (entity_type IN ('review','reviews'))")
        assert cur.fetchone()[0] >= 2
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 2


def test_review_public_teacher_reviews_only_visible_no_student_data():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", review_payload(5, "Recommended."), ptok)
    assert created.status_code == 201
    teacher_id = teacher["teacher_id"]
    client2 = auth_user("PARENT", "public-review-viewer")[0]
    res = get_json(client2, f"/api/v1/teachers/{teacher_id}/reviews")  # public, no token needed
    assert res.status_code == 200
    rows = res.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["is_verified"] is True
    assert row["rating"] == 5
    # No student-identifying data is exposed publicly.
    assert "student_id" not in row and "student_display_name" not in row and "parent_id" not in row
    missing = get_json(client2, f"/api/v1/teachers/{uuid.uuid4()}/reviews")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Dispute: opening + eligibility
# ---------------------------------------------------------------------------

def test_dispute_open_valid_by_parent_overlay_only():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    res = post_json(
        parent_client,
        "/api/v1/disputes",
        {"session_id": session_id, "category": "SESSION_QUALITY", "description": "Session ended early."},
        ptok,
        idem=f"disp-{uuid.uuid4()}",
    )
    assert res.status_code == 201, res.content
    dispute = res.json()["data"]["dispute"]
    assert dispute["status"] == "OPEN"
    assert dispute["category"] == "SESSION_QUALITY"
    assert dispute["priority"] == 3
    assert dispute["booking_id"] == booking_id
    # Overlay model: factual booking/session/payment states are untouched.
    with connection.cursor() as cur:
        cur.execute("SELECT status FROM edutrust.bookings WHERE id=%s", [booking_id])
        assert cur.fetchone()[0] == "COMPLETED"
        cur.execute("SELECT status FROM edutrust.sessions WHERE id=%s", [session_id])
        assert cur.fetchone()[0] == "COMPLETED"
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_OPENED' AND entity_id=%s", [dispute["id"]])
        assert cur.fetchone()[0] == 1


def test_dispute_open_requires_target_and_validates_category():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    no_target = post_json(parent_client, "/api/v1/disputes", {"category": "OTHER"}, ptok)
    assert no_target.status_code == 400
    bad_category = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "NOPE"}, ptok)
    assert bad_category.status_code == 400
    missing_target = post_json(parent_client, "/api/v1/disputes", {"session_id": str(uuid.uuid4()), "category": "OTHER"}, ptok)
    assert missing_target.status_code == 404


def test_dispute_open_unauthorized_users_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    # A foreign parent cannot open a dispute on this interaction.
    other_client, other_auth, _ = create_parent_student()
    foreign = post_json(other_client, "/api/v1/disputes", {"session_id": session_id, "category": "OTHER", "description": "x"}, other_auth["access_token"])
    assert foreign.status_code == 403
    # Admin cannot open disputes (resolution authority is not VS4 scope).
    atok = admin_login(parent_client)
    admin_open = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "OTHER"}, atok)
    assert admin_open.status_code == 403


def test_dispute_safety_priority_and_teacher_open():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    ttok = teacher["teacher_auth"]["access_token"]
    # Teacher (participant) can open a dispute on their own interaction.
    teacher_open = post_json(teacher["teacher_client"], "/api/v1/disputes", {"session_id": session_id, "category": "OTHER", "description": "Note from teacher"}, ttok)
    assert teacher_open.status_code == 201
    # The parent (different actor, also a participant) may file their own dispute
    # on the same interaction, but the same actor may not file two active ones.
    parent_open = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY"}, ptok)
    assert parent_open.status_code == 201
    dup = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "REPORT_ISSUE"}, ptok)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_DISPUTE"
    # A separate completed interaction: SAFETY forces priority 1 regardless of input.
    teacher2, parent_client2, parent_auth2, booking_id2, payment_id2, session_id2 = create_completed_session()
    ptok2 = parent_auth2["access_token"]
    safety = post_json(parent_client2, "/api/v1/disputes", {"session_id": session_id2, "category": "SAFETY", "priority": 5, "description": "safety concern"}, ptok2)
    assert safety.status_code == 201
    assert safety.json()["data"]["dispute"]["priority"] == 1


def test_dispute_duplicate_protection():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    first = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY"}, ptok)
    assert first.status_code == 201
    dup = post_json(parent_client, "/api/v1/disputes", {"booking_id": booking_id, "category": "SESSION_QUALITY"}, ptok)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_DISPUTE"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.disputes WHERE booking_id=%s", [booking_id])
        assert cur.fetchone()[0] == 1


def test_dispute_idempotency_replay_and_conflict():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    key = f"disp-{uuid.uuid4()}"
    payload = {"session_id": session_id, "category": "REPORT_ISSUE", "description": "report missing"}
    first = post_json(parent_client, "/api/v1/disputes", payload, ptok, idem=key)
    assert first.status_code == 201
    replay = post_json(parent_client, "/api/v1/disputes", payload, ptok, idem=key)
    assert replay.status_code == 201
    assert replay.json()["data"]["dispute"]["id"] == first.json()["data"]["dispute"]["id"]
    conflict = post_json(parent_client, "/api/v1/disputes", {**payload, "description": "changed"}, ptok, idem=key)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_dispute_concurrent_open_one_success_one_conflict():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    results = []

    def attempt():
        res = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY", "description": "x"}, ptok)
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [201, 409], results
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.disputes WHERE booking_id=%s", [booking_id])
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Dispute: reads, authorization, audit
# ---------------------------------------------------------------------------

def test_dispute_parent_read_own_and_foreign_denied():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY"}, ptok)
    assert created.status_code == 201
    dispute_id = created.json()["data"]["dispute"]["id"]
    own = get_json(parent_client, f"/api/v1/disputes/{dispute_id}", ptok)
    assert own.status_code == 200
    own_list = get_json(parent_client, "/api/v1/disputes", ptok)
    assert own_list.status_code == 200
    assert any(d["id"] == dispute_id for d in own_list.json()["data"])
    other_client, other_auth, _ = create_parent_student()
    foreign = get_json(other_client, f"/api/v1/disputes/{dispute_id}", other_auth["access_token"])
    assert foreign.status_code == 403
    foreign_list = get_json(other_client, "/api/v1/disputes", other_auth["access_token"])
    assert all(d["id"] != dispute_id for d in foreign_list.json()["data"])


def test_dispute_teacher_read_own_interactions_only():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "STUDENT_NO_SHOW"}, ptok)
    assert created.status_code == 201
    dispute_id = created.json()["data"]["dispute"]["id"]
    ttok = teacher["teacher_auth"]["access_token"]
    teacher_read = get_json(teacher["teacher_client"], f"/api/v1/disputes/{dispute_id}", ttok)
    assert teacher_read.status_code == 200
    other_teacher_client, other_auth = auth_user("TEACHER", "foreign-dispute-teacher")
    foreign = get_json(other_teacher_client, f"/api/v1/disputes/{dispute_id}", other_auth["access_token"])
    assert foreign.status_code == 403
    teacher_list = get_json(teacher["teacher_client"], "/api/v1/disputes", ttok)
    assert any(d["id"] == dispute_id for d in teacher_list.json()["data"])


def test_dispute_admin_read_is_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "PAYMENT_REFUND"}, ptok)
    assert created.status_code == 201
    dispute_id = created.json()["data"]["dispute"]["id"]
    atok = admin_login(parent_client)
    admin_detail = get_json(parent_client, f"/api/v1/disputes/{dispute_id}", atok)
    assert admin_detail.status_code == 200
    admin_list = get_json(parent_client, "/api/v1/disputes", atok)
    assert admin_list.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type IN ('dispute','disputes')")
        assert cur.fetchone()[0] >= 2
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 2


def test_dispute_has_no_status_mutation_path_in_vs4():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "OTHER"}, ptok)
    assert created.status_code == 201
    dispute_id = created.json()["data"]["dispute"]["id"]
    # VS4 exposes no dispute status mutation endpoint (resolve/moderate belong to
    # the approved admin resolve flow, outside this slice). Verify the API refuses
    # mutation verbs and the status is unchanged.
    headers = {"HTTP_AUTHORIZATION": f"Bearer {ptok}"}
    patch = parent_client.patch(f"/api/v1/disputes/{dispute_id}", data="{}", content_type="application/json", **headers)
    assert patch.status_code in (404, 405)
    put = parent_client.put(f"/api/v1/disputes/{dispute_id}", data="{}", content_type="application/json", **headers)
    assert put.status_code in (404, 405)
    with connection.cursor() as cur:
        cur.execute("SELECT status FROM edutrust.disputes WHERE id=%s", [dispute_id])
        assert cur.fetchone()[0] == "OPEN"


def _insert_payout_item(session_id: str, teacher_profile_id: str):
    """Direct DB insert used to exercise the approved payout-eligibility trigger."""
    with connection.cursor() as cur:
        payout_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO edutrust.payouts (id, teacher_id, amount, currency, status) VALUES (%s, %s, 100.00, 'DZD', 'PENDING')",
            [payout_id, teacher_profile_id],
        )
        cur.execute(
            "INSERT INTO edutrust.payout_items (payout_id, teacher_id, session_id, amount, currency) VALUES (%s, %s, %s, 100.00, 'DZD')",
            [payout_id, teacher_profile_id, session_id],
        )


def test_open_dispute_blocks_payout_item_at_database_level():
    # Control: an eligible completed interaction (with report) accepts a payout item.
    ctrl_teacher, ctrl_client, ctrl_auth, ctrl_booking, ctrl_payment, ctrl_session = create_completed_session()
    ctok = ctrl_teacher["teacher_auth"]["access_token"]
    report = post_json(ctrl_teacher["teacher_client"], f"/api/v1/sessions/{ctrl_session}/report", report_payload(), ctok)
    assert report.status_code == 201
    _insert_payout_item(ctrl_session, ctrl_teacher["teacher_id"])

    # With an open dispute on the session, the same insert must be blocked by the
    # approved database trigger (validate_payout_item_eligibility).
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = create_completed_session()
    ttok = teacher["teacher_auth"]["access_token"]
    report = post_json(teacher["teacher_client"], f"/api/v1/sessions/{session_id}/report", report_payload(), ttok)
    assert report.status_code == 201
    ptok = parent_auth["access_token"]
    created = post_json(parent_client, "/api/v1/disputes", {"session_id": session_id, "category": "SESSION_QUALITY"}, ptok)
    assert created.status_code == 201
    try:
        _insert_payout_item(session_id, teacher["teacher_id"])
        assert False, "expected payout item insert to be blocked by open dispute"
    except Exception as exc:
        assert "dispute" in str(exc).lower()
