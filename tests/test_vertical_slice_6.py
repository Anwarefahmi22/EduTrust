"""DEV Vertical Slice #6 — Review Moderation.

Regression baseline before this file: 83 tests (foundation + VS1–VS5).
Approved decisions: U1 {action, reason} contract · U2 mandatory Idempotency-Key ·
U3 strict 422 INVALID_STATE_TRANSITION for invalid transitions.
"""
from __future__ import annotations

import threading
import uuid

import django
from django.db import connection

django.setup()

from tests.test_foundation import create_admin
from tests.test_session_slice_3 import report_payload
from tests.test_vertical_slice_1 import auth_user, post_json, get_json
from tests.test_vertical_slice_4 import admin_login
from tests.test_vertical_slice_5 import completed_with_report


def make_review():
    """Full cycle to a VISIBLE verified review; returns (teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id)."""
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = completed_with_report()
    ptok = parent_auth["access_token"]
    res = post_json(parent_client, f"/api/v1/sessions/{session_id}/review",
                    {"rating": 5, "comment": "great session"}, ptok, idem=f"rev6-{uuid.uuid4()}")
    assert res.status_code == 201, res.content
    review_id = res.json()["data"]["review"]["id"]
    return teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id


def seed_operator(role: str, prefix: str):
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    user_id = str(uuid.uuid4())
    with connection.cursor() as cur:
        from django.contrib.auth.hashers import make_password
        cur.execute("INSERT INTO edutrust.users (id, full_name, email, password_hash) VALUES (%s,%s,%s,%s)",
                    [user_id, f"{role} Op", email, make_password("StrongPassword123!")])
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s,%s)", [user_id, role])
    return email


def moderate(client, token, review_id, action, reason="policy review", idem=None):
    return post_json(client, f"/api/v1/admin/reviews/{review_id}/moderate",
                     {"action": action, "reason": reason}, token, idem=idem or f"mod-{uuid.uuid4()}")


def review_status(review_id: str) -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.reviews WHERE id=%s", [review_id])
        row = cur.fetchone()
        return row[0] if row else None


def public_review_visible(client, teacher_id: str, review_id: str) -> bool:
    res = get_json(client, f"/api/v1/teachers/{teacher_id}/reviews")
    assert res.status_code == 200
    return any(r["id"] == review_id for r in res.json()["data"])


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def test_moderate_flag_visible_to_flagged():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    res = moderate(parent_client, atok, review_id, "FLAG", reason="abusive language")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["review"]["status"] == "FLAGGED"
    assert review_status(review_id) == "FLAGGED"
    import json as _json
    with connection.cursor() as cur:
        cur.execute("SELECT metadata FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_id=%s AND metadata->>'action'='MODERATE_FLAG'", [review_id])
        row = cur.fetchone()
        meta = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert row and meta.get("reason") == "abusive language" and meta.get("from_status") == "VISIBLE" and meta.get("to_status") == "FLAGGED"


def test_moderate_hide_flagged_to_hidden():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    assert moderate(parent_client, atok, review_id, "FLAG").status_code == 200
    res = moderate(parent_client, atok, review_id, "HIDE", reason="policy violation in comment")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["review"]["status"] == "HIDDEN"
    assert review_status(review_id) == "HIDDEN"


def test_moderate_restore_flagged_to_visible():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    assert moderate(parent_client, atok, review_id, "FLAG").status_code == 200
    res = moderate(parent_client, atok, review_id, "RESTORE", reason="review cleared after appeal")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["review"]["status"] == "VISIBLE"


def test_moderate_restore_hidden_to_visible():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    assert moderate(parent_client, atok, review_id, "FLAG").status_code == 200
    assert moderate(parent_client, atok, review_id, "HIDE").status_code == 200
    res = moderate(parent_client, atok, review_id, "RESTORE")
    assert res.status_code == 200
    assert review_status(review_id) == "VISIBLE"


def test_moderate_remove_admin_only_success_row_preserved():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    res = moderate(parent_client, atok, review_id, "REMOVE", reason="fraudulent review")
    assert res.status_code == 200, res.content
    assert review_status(review_id) == "REMOVED"
    # No physical deletion: row + rating + comment preserved.
    with connection.cursor() as cur:
        cur.execute("SELECT rating, comment, is_verified FROM edutrust.reviews WHERE id=%s", [review_id])
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 5 and row[1] == "great session" and row[2] is True


def test_moderate_remove_from_flagged_and_hidden():
    t1, pc, pa, b1, p1, s1, r1 = make_review()
    atok = admin_login(pc)
    assert moderate(pc, atok, r1, "FLAG").status_code == 200
    assert moderate(pc, atok, r1, "REMOVE").status_code == 200
    assert review_status(r1) == "REMOVED"
    t2, pc2, pa2, b2, p2, s2, r2 = make_review()
    assert moderate(pc2, atok, r2, "FLAG").status_code == 200
    assert moderate(pc2, atok, r2, "HIDE").status_code == 200
    assert moderate(pc2, atok, r2, "REMOVE").status_code == 200
    assert review_status(r2) == "REMOVED"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_ops_cannot_remove():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    ops_email = seed_operator("OPS", "ops-mod")
    ops_login = post_json(parent_client, "/api/v1/auth/login", {"identifier": ops_email, "password": "StrongPassword123!"})
    otok = ops_login.json()["data"]["access_token"]
    # OPS can flag/hide/restore
    assert moderate(parent_client, otok, review_id, "FLAG", idem=f"mod-{uuid.uuid4()}").status_code == 200
    # OPS cannot remove
    res = moderate(parent_client, otok, review_id, "REMOVE")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
    assert review_status(review_id) == "FLAGGED"


def test_moderation_denied_for_parent_teacher_anonymous():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    ptok = parent_auth["access_token"]
    ttok = teacher["teacher_auth"]["access_token"]
    assert moderate(parent_client, ptok, review_id, "FLAG").status_code == 403  # parent owner denied
    assert moderate(teacher["teacher_client"], ttok, review_id, "FLAG").status_code == 403  # reviewed teacher denied
    anon = post_json(parent_client, f"/api/v1/admin/reviews/{review_id}/moderate", {"action": "FLAG", "reason": "x"})
    assert anon.status_code == 401
    # List access
    assert get_json(parent_client, "/api/v1/admin/reviews", ptok).status_code == 403
    assert get_json(teacher["teacher_client"], "/api/v1/admin/reviews", ttok).status_code == 403
    assert get_json(parent_client, "/api/v1/admin/reviews").status_code == 401


def test_support_list_access_audited():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    support_email = seed_operator("SUPPORT", "support-mod")
    support_login = post_json(parent_client, "/api/v1/auth/login", {"identifier": support_email, "password": "StrongPassword123!"})
    stok = support_login.json()["data"]["access_token"]
    res = get_json(parent_client, "/api/v1/admin/reviews", stok)
    assert res.status_code == 200, res.content
    assert any(r["id"] == review_id for r in res.json()["data"])
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='reviews' AND metadata->>'action'='READ_REVIEW_LIST'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 1
    # SUPPORT cannot moderate
    assert moderate(parent_client, stok, review_id, "FLAG").status_code == 403


# ---------------------------------------------------------------------------
# Invalid transitions + validation
# ---------------------------------------------------------------------------

def test_invalid_transitions_rejected_422():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    # HIDE from VISIBLE (must FLAG first)
    r = moderate(parent_client, atok, review_id, "HIDE")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert r.json()["error"]["details"]["current_status"] == "VISIBLE"
    # RESTORE from VISIBLE (U3 strict)
    r = moderate(parent_client, atok, review_id, "RESTORE")
    assert r.status_code == 422 and r.json()["error"]["details"]["current_status"] == "VISIBLE"
    # proceed to REMOVED, then invalid-from-REMOVED cases
    assert moderate(parent_client, atok, review_id, "REMOVE").status_code == 200
    for action in ("FLAG", "HIDE", "RESTORE", "REMOVE"):
        r = moderate(parent_client, atok, review_id, action)
        assert r.status_code == 422, (action, r.content)
        assert r.json()["error"]["details"]["current_status"] == "REMOVED"
    assert review_status(review_id) == "REMOVED"


def test_validation_errors():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    bad_action = post_json(parent_client, f"/api/v1/admin/reviews/{review_id}/moderate", {"action": "NUKE", "reason": "x"}, atok, idem=f"mod-{uuid.uuid4()}")
    assert bad_action.status_code == 400 and bad_action.json()["error"]["code"] == "VALIDATION_ERROR"
    no_reason = post_json(parent_client, f"/api/v1/admin/reviews/{review_id}/moderate", {"action": "FLAG", "reason": "   "}, atok, idem=f"mod-{uuid.uuid4()}")
    assert no_reason.status_code == 400 and no_reason.json()["error"]["code"] == "VALIDATION_ERROR"
    unknown = post_json(parent_client, f"/api/v1/admin/reviews/{uuid.uuid4()}/moderate", {"action": "FLAG", "reason": "x"}, atok, idem=f"mod-{uuid.uuid4()}")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Public visibility + verified invariants
# ---------------------------------------------------------------------------

def test_public_visibility_reflects_moderation():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    teacher_id = teacher["teacher_id"]
    assert public_review_visible(parent_client, teacher_id, review_id) is True
    assert moderate(parent_client, atok, review_id, "FLAG").status_code == 200
    assert public_review_visible(parent_client, teacher_id, review_id) is False
    assert moderate(parent_client, atok, review_id, "RESTORE").status_code == 200
    assert public_review_visible(parent_client, teacher_id, review_id) is True
    # HIDE requires the FLAGGED state: re-flag, then hide (matrix-compliant path)
    assert moderate(parent_client, atok, review_id, "FLAG").status_code == 200
    assert moderate(parent_client, atok, review_id, "HIDE").status_code == 200
    assert public_review_visible(parent_client, teacher_id, review_id) is False
    assert moderate(parent_client, atok, review_id, "RESTORE").status_code == 200
    assert moderate(parent_client, atok, review_id, "REMOVE").status_code == 200
    assert public_review_visible(parent_client, teacher_id, review_id) is False


def test_verified_review_invariants_preserved():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    ptok = parent_auth["access_token"]
    for action in ("FLAG", "HIDE"):
        assert moderate(parent_client, atok, review_id, action).status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT is_verified, rating, comment, session_id::text FROM edutrust.reviews WHERE id=%s", [review_id])
        verified, rating, comment, sid = cur.fetchone()
        assert verified is True and rating == 5 and comment == "great session" and sid == session_id
    # one-review-per-session invariant intact: second creation still 409
    dup = post_json(parent_client, f"/api/v1/sessions/{session_id}/review", {"rating": 4, "comment": "again"}, ptok)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DUPLICATE_REVIEW"


# ---------------------------------------------------------------------------
# Idempotency + concurrency
# ---------------------------------------------------------------------------

def test_moderation_idempotency_replay_conflict_and_missing_key():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    key = f"mod-{uuid.uuid4()}"
    first = moderate(parent_client, atok, review_id, "FLAG", reason="abuse", idem=key)
    assert first.status_code == 200
    replay = moderate(parent_client, atok, review_id, "FLAG", reason="abuse", idem=key)
    assert replay.status_code == 200
    assert replay.json()["data"]["review"]["status"] == "FLAGGED"
    assert review_status(review_id) == "FLAGGED"
    conflict = moderate(parent_client, atok, review_id, "HIDE", reason="different", idem=key)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    missing = post_json(parent_client, f"/api/v1/admin/reviews/{review_id}/moderate", {"action": "RESTORE", "reason": "x"}, atok)
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_concurrent_moderation_serialized_one_winner():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id, review_id = make_review()
    atok = admin_login(parent_client)
    results = []

    def attempt():
        res = moderate(parent_client, atok, review_id, "REMOVE", reason=f"concurrent-{len(results)}")
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()
    # Two parallel REMOVEs: first 200 (VISIBLE->REMOVED), second 422 (REMOVED->REMOVED invalid).
    assert sorted(results) == [200, 422], results
    assert review_status(review_id) == "REMOVED"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE id=%s", [review_id])
        assert cur.fetchone()[0] == 1
    # Chained parallel actions (FLAG + HIDE) must also end in a consistent state, no 5xx.
    teacher2, pc2, pa2, b2, p2, s2, r2 = make_review()
    results2 = []

    def attempt2(action):
        res = moderate(pc2, atok, r2, action, reason=f"chain-{action}")
        results2.append(res.status_code)

    t3 = threading.Thread(target=attempt2, args=("FLAG",))
    t4 = threading.Thread(target=attempt2, args=("HIDE",))
    t3.start(); t4.start(); t3.join(); t4.join()
    assert all(code in (200, 422) for code in results2), results2
    assert review_status(r2) in ("FLAGGED", "HIDDEN")
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.reviews WHERE id=%s", [r2])
        assert cur.fetchone()[0] == 1
