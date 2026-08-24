"""DEV Vertical Slice #7 — Teacher Verification.

Regression baseline before this file: 98 tests (foundation + VS1–VS6).
Approved decisions: V1 profile mapping · V2 no-demotion · V3 EXPERIENCE/
BACKGROUND_CHECK rows without profile mapping · V4 additive trust-profile
booleans · V5 mandatory Idempotency-Key · V6 metadata-only audited docs.
"""
from __future__ import annotations

import threading
import uuid

import django
from django.db import connection

django.setup()

from tests.test_foundation import create_admin, register_and_login, post_json as _foundation_post_json
from tests.test_vertical_slice_1 import auth_user, post_json, get_json, setup_teacher_with_slot
from tests.test_vertical_slice_4 import admin_login
from tests.test_vertical_slice_6 import seed_operator


def teacher_with_token():
    client, auth = auth_user("TEACHER", "vs7-teacher")
    token = auth["access_token"]
    profile_id = get_json(client, "/api/v1/teachers/me", token).json()["data"]["id"]
    return client, token, profile_id


def submit(client, token, vtype="IDENTITY", metadata=None, documents=None, idem=None):
    body = {"verification_type": vtype}
    if metadata is not None:
        body["metadata"] = metadata
    if documents is not None:
        body["documents"] = documents
    return post_json(client, "/api/v1/teachers/verifications", body, token, idem=idem or f"verif-{uuid.uuid4()}")


def profile_status(teacher_profile_id: str) -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT verification_status::text FROM edutrust.teacher_profiles WHERE id=%s", [teacher_profile_id])
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

def test_verification_submission_identity():
    client, token, tid = teacher_with_token()
    docs = [{"document_type": "national_id", "upload_token": "dev-upload-1"}]
    res = submit(client, token, "IDENTITY", metadata={"issuer": "test"}, documents=docs)
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert data["verification"]["status"] == "SUBMITTED"
    assert data["verification"]["verification_type"] == "IDENTITY"
    assert data["profile_verification_status"] == "SUBMITTED"
    assert profile_status(tid) == "SUBMITTED"
    docs = data["verification"]["documents"]
    assert len(docs) == 1
    assert docs[0]["document_type"] == "national_id"
    assert docs[0]["storage_key"].startswith("dev-synthetic-")
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='TEACHER_VERIFICATION_SUBMITTED' AND entity_id=%s", [data["verification"]["id"]])
        assert cur.fetchone()[0] == 1


def test_verification_submission_qualification_metadata():
    client, token, tid = teacher_with_token()
    res = submit(client, token, "QUALIFICATION", metadata={"institution": "University of Algiers", "graduation_year": 2018},
                 documents=[{"document_type": "degree_certificate", "upload_token": "dev-upload-2"}])
    assert res.status_code == 201, res.content
    v = res.json()["data"]["verification"]
    assert v["metadata"]["institution"] == "University of Algiers"
    assert v["metadata"]["graduation_year"] == 2018
    # No content fields exist on documents (metadata-only, V6)
    assert "content" not in v["documents"][0] and "url" not in v["documents"][0]
    assert profile_status(tid) == "SUBMITTED"


def test_verification_submission_validation():
    client, token, _ = teacher_with_token()
    assert submit(client, token, "NOT_A_TYPE").status_code == 400
    assert submit(client, token, "IDENTITY", documents="nope").status_code == 400
    assert submit(client, token, "IDENTITY", documents=[{"document_type": "x"}]).status_code == 400  # missing upload_token
    assert submit(client, token, "IDENTITY", metadata="nope").status_code == 400


def test_verification_list_own():
    client, token, tid = teacher_with_token()
    v1 = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    v2 = submit(client, token, "QUALIFICATION").json()["data"]["verification"]["id"]
    res = get_json(client, "/api/v1/teachers/verifications", token)
    assert res.status_code == 200
    rows = res.json()["data"]["verifications"]
    assert [r["id"] for r in rows[:2]] == [v2, v1]  # newest first
    assert res.json()["data"]["profile_verification_status"] == "SUBMITTED"
    # Other teacher cannot see these
    other_client, other_token, _ = teacher_with_token()
    other = get_json(other_client, "/api/v1/teachers/verifications", other_token)
    assert other.json()["data"]["verifications"] == []


def test_submission_denied_for_non_teacher():
    client, token, _ = teacher_with_token()
    parent_client, parent_auth = auth_user("PARENT", "vs7-parent")
    ptok = parent_auth["access_token"]
    assert post_json(parent_client, "/api/v1/teachers/verifications", {"verification_type": "IDENTITY"}, ptok).status_code == 403
    assert post_json(client, "/api/v1/teachers/verifications", {"verification_type": "IDENTITY"}).status_code == 401  # anonymous
    assert get_json(parent_client, "/api/v1/teachers/verifications", ptok).status_code == 403


# ---------------------------------------------------------------------------
# Approval / rejection / mapping
# ---------------------------------------------------------------------------

def _ops_token(client):
    email = seed_operator("OPS", "vs7-ops")
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    return login.json()["data"]["access_token"]


def test_verify_approves_identity():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    otok = _ops_token(client)
    res = post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid, "reviewer_note": "identity confirmed"}, otok)
    assert res.status_code == 200, res.content
    v = res.json()["data"]["verification"]
    assert v["status"] == "APPROVED" and v["reviewer_note"] == "identity confirmed" and v["reviewed_at"]
    assert res.json()["data"]["profile_verification_status"] == "IDENTITY_VERIFIED"
    assert profile_status(tid) == "IDENTITY_VERIFIED"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='TEACHER_VERIFIED' AND entity_id=%s", [vid])
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_id=%s", [vid])
        assert cur.fetchone()[0] >= 1


def test_verify_approves_qualification():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "QUALIFICATION").json()["data"]["verification"]["id"]
    otok = _ops_token(client)
    res = post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok)
    assert res.status_code == 200, res.content
    assert profile_status(tid) == "QUALIFICATION_REVIEWED"


def test_reject_sets_rejection():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    otok = _ops_token(client)
    res = post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": vid, "rejection_reason": "document illegible"}, otok)
    assert res.status_code == 200, res.content
    v = res.json()["data"]["verification"]
    assert v["status"] == "REJECTED" and v["rejection_reason"] == "document illegible"
    assert res.json()["data"]["profile_verification_status"] == "REJECTED"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='TEACHER_REJECTED' AND entity_id=%s", [vid])
        assert cur.fetchone()[0] == 1
    # reject without reason is a validation error
    vid2 = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": vid2, "rejection_reason": "  "}, otok).status_code == 400


def test_reject_does_not_demote_approved_higher_level():
    client, token, tid = teacher_with_token()
    otok = _ops_token(client)
    vid_id = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid_id}, otok).status_code == 200
    assert profile_status(tid) == "IDENTITY_VERIFIED"
    vid_q = submit(client, token, "QUALIFICATION").json()["data"]["verification"]["id"]
    res = post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": vid_q, "rejection_reason": "unverified institution"}, otok)
    assert res.status_code == 200, res.content
    assert profile_status(tid) == "IDENTITY_VERIFIED"  # V2: no demotion


def test_experience_row_without_profile_mapping():
    # V3: EXPERIENCE rows exist and can be approved, but have no profile level.
    client, token, tid = teacher_with_token()
    otok = _ops_token(client)
    vid = submit(client, token, "EXPERIENCE", metadata={"years": 10}).json()["data"]["verification"]["id"]
    res = post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok)
    assert res.status_code == 200
    v = res.json()["data"]["verification"]
    assert v["status"] == "APPROVED"
    assert profile_status(tid) == "SUBMITTED"  # profile level unchanged (no approved level)


def test_invalid_transitions():
    client, token, tid = teacher_with_token()
    otok = _ops_token(client)
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok).status_code == 200
    again = post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok)
    assert again.status_code == 422 and again.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert again.json()["error"]["details"]["current_status"] == "APPROVED"
    rej_again = post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": vid, "rejection_reason": "x"}, otok)
    assert rej_again.status_code == 422
    unknown = post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": str(uuid.uuid4())}, otok)
    assert unknown.status_code == 404
    unknown_teacher = post_json(client, f"/api/v1/admin/teachers/{uuid.uuid4()}/verify", {"verification_id": vid}, otok)
    assert unknown_teacher.status_code == 404


def test_resubmission_after_rejection_allowed():
    client, token, tid = teacher_with_token()
    otok = _ops_token(client)
    v1 = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": v1, "rejection_reason": "blurry"}, otok).status_code == 200
    assert profile_status(tid) == "REJECTED"
    v2 = submit(client, token, "IDENTITY", documents=[{"document_type": "national_id", "upload_token": "dev-again"}])
    assert v2.status_code == 201
    assert profile_status(tid) == "SUBMITTED"
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": v2.json()["data"]["verification"]["id"]}, otok).status_code == 200
    assert profile_status(tid) == "IDENTITY_VERIFIED"


# ---------------------------------------------------------------------------
# Authorization / audit
# ---------------------------------------------------------------------------

def test_admin_authorization_matrix():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    otok = _ops_token(client)
    atok = admin_login(client)
    # OPS + ADMIN allowed
    assert get_json(client, "/api/v1/admin/teachers/pending-verification", otok).status_code == 200
    assert get_json(client, "/api/v1/admin/teachers/pending-verification", atok).status_code == 200
    assert get_json(client, f"/api/v1/admin/teachers/{tid}/verifications", otok).status_code == 200
    assert get_json(client, f"/api/v1/admin/teachers/{tid}/verifications", atok).status_code == 200
    # Teacher cannot self-approve
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, token).status_code == 403
    # Parent denied
    parent_client, parent_auth = auth_user("PARENT", "vs7-matrix-parent")
    ptok = parent_auth["access_token"]
    assert get_json(parent_client, "/api/v1/admin/teachers/pending-verification", ptok).status_code == 403
    assert post_json(parent_client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, ptok).status_code == 403
    # Support denied (Security Plan matrix: support = No)
    support_email = seed_operator("SUPPORT", "vs7-support")
    stok = post_json(client, "/api/v1/auth/login", {"identifier": support_email, "password": "StrongPassword123!"}).json()["data"]["access_token"]
    assert get_json(client, "/api/v1/admin/teachers/pending-verification", stok).status_code == 403
    assert get_json(client, f"/api/v1/admin/teachers/{tid}/verifications", stok).status_code == 403
    # Anonymous
    assert get_json(client, "/api/v1/admin/teachers/pending-verification").status_code == 401


def test_admin_views_audited_metadata_only():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "IDENTITY", documents=[{"document_type": "national_id", "upload_token": "dev-audit"}]).json()["data"]["verification"]["id"]
    atok = admin_login(client)
    detail = get_json(client, f"/api/v1/admin/teachers/{tid}/verifications", atok)
    assert detail.status_code == 200
    v = [x for x in detail.json()["data"]["verifications"] if x["id"] == vid][0]
    assert v["documents"][0]["storage_key"].startswith("dev-synthetic-")
    assert "url" not in v["documents"][0] and "content" not in v["documents"][0]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='teacher_verification' AND metadata->>'action' IN ('READ_VERIFICATION_DETAIL','READ_PENDING_VERIFICATIONS')")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] >= 1


def test_pending_list_shows_only_submitted():
    client, token, tid = teacher_with_token()
    otok = _ops_token(client)
    assert submit(client, token, "IDENTITY").status_code == 201
    listing = get_json(client, "/api/v1/admin/teachers/pending-verification", otok)
    assert listing.status_code == 200
    teachers = listing.json()["data"]["teachers"]
    mine = [t for t in teachers if t["id"] == tid]
    assert mine and mine[0]["pending_count"] >= 1 and mine[0]["pending"][0]["verification_type"] == "IDENTITY"


# ---------------------------------------------------------------------------
# Trust profile / search (V4 + no-filter boundary)
# ---------------------------------------------------------------------------

def test_trust_profile_per_type_booleans():
    client, token, tid = teacher_with_token()
    before = get_json(client, f"/api/v1/teachers/{tid}/trust-profile")
    assert before.status_code == 200
    assert before.json()["data"]["identity_verified"] is False
    assert before.json()["data"]["qualifications_verified"] is False
    otok = _ops_token(client)
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok).status_code == 200
    mid = get_json(client, f"/api/v1/teachers/{tid}/trust-profile").json()["data"]
    assert mid["identity_verified"] is True and mid["qualifications_verified"] is False
    vid2 = submit(client, token, "QUALIFICATION").json()["data"]["verification"]["id"]
    assert post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid2}, otok).status_code == 200
    after = get_json(client, f"/api/v1/teachers/{tid}/trust-profile").json()["data"]
    assert after["identity_verified"] is True and after["qualifications_verified"] is True
    assert after["verification_status"] == "QUALIFICATION_REVIEWED"


def test_trust_profile_backward_compatible():
    client, token, tid = teacher_with_token()
    data = get_json(client, f"/api/v1/teachers/{tid}").json()["data"]
    for field in ("id", "public_name", "verification_status", "listing_status", "subjects", "available_slots",
                  "completed_sessions_count", "verified_rating", "review_count", "identity_verified", "qualifications_verified"):
        assert field in data, field
    assert data["verification_status"] == "UNVERIFIED"


def test_search_exposes_status_no_filter_change():
    # Search exposes verification_status on every returned row and never
    # filters by verification (approved boundary, plan §9). The baseline search
    # is LIMIT 50, so presence of our teacher in the window is asserted
    # conditionally; the public profile provides the deterministic check.
    teacher = setup_teacher_with_slot()
    ttok = teacher["teacher_auth"]["access_token"]
    tid = teacher["teacher_id"]
    results = get_json(teacher["teacher_client"], "/api/v1/teachers/search?mode=ONLINE")
    assert results.status_code == 200
    data = results.json()["data"]
    assert data  # search returns rows
    assert all("verification_status" in r for r in data)  # status exposed on every row
    rows = [r for r in data if r["teacher_id"] == tid]
    if rows:
        assert rows[0]["verification_status"] == "UNVERIFIED"
    profile = get_json(teacher["teacher_client"], f"/api/v1/teachers/{tid}")
    assert profile.json()["data"]["verification_status"] == "UNVERIFIED"
    # After identity verification, the exposed status reflects it (no filtering).
    vid = submit(teacher["teacher_client"], ttok, "IDENTITY").json()["data"]["verification"]["id"]
    otok = _ops_token(teacher["teacher_client"])
    assert post_json(teacher["teacher_client"], f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok).status_code == 200
    profile = get_json(teacher["teacher_client"], f"/api/v1/teachers/{tid}")
    assert profile.json()["data"]["verification_status"] == "IDENTITY_VERIFIED"
    rows = [r for r in get_json(teacher["teacher_client"], "/api/v1/teachers/search?mode=ONLINE").json()["data"] if r["teacher_id"] == tid]
    if rows:
        assert rows[0]["verification_status"] == "IDENTITY_VERIFIED"


# ---------------------------------------------------------------------------
# Idempotency / concurrency
# ---------------------------------------------------------------------------

def test_idempotency_replay_conflict_missing_key():
    client, token, tid = teacher_with_token()
    key = f"verif-{uuid.uuid4()}"
    first = submit(client, token, "IDENTITY", metadata={"n": 1}, idem=key)
    assert first.status_code == 201
    replay = submit(client, token, "IDENTITY", metadata={"n": 1}, idem=key)
    assert replay.status_code == 201
    assert replay.json()["data"]["verification"]["id"] == first.json()["data"]["verification"]["id"]
    conflict = submit(client, token, "IDENTITY", metadata={"n": 2}, idem=key)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    missing = post_json(client, "/api/v1/teachers/verifications", {"verification_type": "IDENTITY"}, token)
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.teacher_verifications WHERE teacher_id=%s", [tid])
        assert cur.fetchone()[0] == 1  # replay/conflict created no extra rows


def test_concurrent_verify_reject_one_wins():
    client, token, tid = teacher_with_token()
    vid = submit(client, token, "IDENTITY").json()["data"]["verification"]["id"]
    otok = _ops_token(client)
    results = []

    def verify():
        results.append(post_json(client, f"/api/v1/admin/teachers/{tid}/verify", {"verification_id": vid}, otok).status_code)

    def reject():
        results.append(post_json(client, f"/api/v1/admin/teachers/{tid}/reject", {"verification_id": vid, "rejection_reason": "parallel"}, otok).status_code)

    t1 = threading.Thread(target=verify)
    t2 = threading.Thread(target=reject)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [200, 422], results
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.teacher_verifications WHERE id=%s", [vid])
        assert cur.fetchone()[0] in ("APPROVED", "REJECTED")
        cur.execute("SELECT count(*) FROM edutrust.teacher_verifications WHERE id=%s", [vid])
        assert cur.fetchone()[0] == 1
