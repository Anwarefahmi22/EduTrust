"""R7 (VS10 candidate 2) — Student Management Completion, Executor A (A1–A3).

Contract: EduTrust_VS10_R7_Implementation_Authorization_v1.0.md (locks D1/D1e, D2, D6, D9).
  A1 GET /students          — own students only, created_at DESC, no pagination, no event (D6)
  A2 PATCH /students/:id    — updatable field set, server-owned fields ignored, §7.3 parity
                              incl. is_active check (D1/D1e), last-writer-wins under row lock (D1d)
  A3 DELETE /students/:id   — soft archive ACTIVE→ARCHIVED, idempotent no-op, event on first
                              transition only (D2), no hard delete ever
Ownership: VS1 no-oracle convention — uniform 403 STUDENT_ACCESS_DENIED for foreign AND
unknown ids (no existence oracle). No schema change; no new event values; no financial surface.
"""
from __future__ import annotations

import uuid

from django.db import connection

from tests.test_vertical_slice_1 import (
    auth_user,
    create_parent_student,
    get_json,
    patch_json,
    post_json,
    seed_taxonomy,
    setup_teacher_with_slot,
)

STUDENT_PATH = "/api/v1/students"


def student_row(student_id: str) -> dict:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, display_name, birth_year, academic_level_id::text, school_year,
                   primary_goal, preferred_mode::text, consent_status::text, status::text,
                   parent_id::text, created_at, updated_at
            FROM edutrust.student_profiles WHERE id = %s
            """,
            [student_id],
        )
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None


def updated_events(student_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM edutrust.event_ledger WHERE event_type='STUDENT_PROFILE_UPDATED' AND entity_id=%s",
            [student_id],
        )
        return cur.fetchone()[0]


def created_events(student_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM edutrust.event_ledger WHERE event_type='STUDENT_PROFILE_CREATED' AND entity_id=%s",
            [student_id],
        )
        return cur.fetchone()[0]


def create_student_api(client, token: str, display_name: str = "Lina", **extra):
    body = {"display_name": display_name, **extra}
    res = post_json(client, f"{STUDENT_PATH}", body, token)
    assert res.status_code == 201, res.content
    return res.json()["data"]["id"]


def test_a1_list_own_students():
    """Req 1+4: parent lists own students; standard envelope; item field set per D6."""
    client, auth = auth_user("PARENT", "r7-a1")
    token = auth["access_token"]
    s1 = create_student_api(client, token, "Sara")
    s2 = create_student_api(client, token, "Yacine", birth_year=2013)
    res = get_json(client, STUDENT_PATH, token)
    assert res.status_code == 200, res.content
    payload = res.json()
    assert set(payload.keys()) == {"data", "request_id"}  # standard envelope
    assert isinstance(payload["data"], list) and len(payload["data"]) == 2
    ids = [item["id"] for item in payload["data"]]
    assert set(ids) == {s1, s2}
    for item in payload["data"]:
        assert set(item.keys()) == {"id", "display_name", "status", "parent_id", "created_at"}  # D6 item shape


def test_a1_list_cross_parent_isolation():
    """Req 2: a parent can never see another parent's students (list or detail)."""
    client_a, auth_a = auth_user("PARENT", "r7-a1b")
    client_b, auth_b = auth_user("PARENT", "r7-a1c")
    tok_a, tok_b = auth_a["access_token"], auth_b["access_token"]
    s_a = create_student_api(client_a, tok_a, "Omar")
    create_student_api(client_b, tok_b, "Leila")
    list_b = get_json(client_b, STUDENT_PATH, tok_b)
    assert list_b.status_code == 200
    assert s_a not in [item["id"] for item in list_b.json()["data"]]
    detail = get_json(client_b, f"{STUDENT_PATH}/{s_a}", tok_b)
    assert detail.status_code == 403 and detail.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"


def test_a1_list_ordering_created_at_desc():
    """Req 3: list ordered created_at DESC."""
    client, auth = auth_user("PARENT", "r7-a1d")
    token = auth["access_token"]
    s1 = create_student_api(client, token, "Order1")
    s2 = create_student_api(client, token, "Order2")
    s3 = create_student_api(client, token, "Order3")
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.student_profiles SET created_at = now() - interval '3 minutes' WHERE id=%s", [s1])
        cur.execute("UPDATE edutrust.student_profiles SET created_at = now() - interval '2 minutes' WHERE id=%s", [s2])
        cur.execute("UPDATE edutrust.student_profiles SET created_at = now() - interval '1 minute' WHERE id=%s", [s3])
    ids = [item["id"] for item in get_json(client, STUDENT_PATH, token).json()["data"]]
    assert ids == [s3, s2, s1]


def test_a1_list_empty():
    """Req 5: a parent with no students gets an empty list (envelope preserved)."""
    client, auth = auth_user("PARENT", "r7-a1e")
    res = get_json(client, STUDENT_PATH, auth["access_token"])
    assert res.status_code == 200 and res.json()["data"] == []


def test_a2_patch_allowed_fields():
    """Req 6: each D1-updatable field is writable; response is the updated student object;
    updated_at advances; explicit null clears a nullable column (documented decision note)."""
    client, auth = auth_user("PARENT", "r7-a2a")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Patchable")
    subject_id, level_id = seed_taxonomy()
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.student_profiles SET updated_at = now() - interval '1 hour' WHERE id=%s", [sid])
    res = patch_json(
        client,
        f"{STUDENT_PATH}/{sid}",
        {
            "display_name": "Patched",
            "birth_year": 2014,
            "academic_level_id": level_id,
            "school_year": "2026/2027",
            "primary_goal": "BAC exam",
            "preferred_mode": "IN_PERSON",
            "consent_status": "PENDING",
        },
        token,
    )
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["display_name"] == "Patched"
    assert data["birth_year"] == 2014
    assert data["academic_level_id"] == level_id
    assert data["school_year"] == "2026/2027"
    assert data["primary_goal"] == "BAC exam"
    assert data["preferred_mode"] == "IN_PERSON"
    assert data["consent_status"] == "PENDING"
    row = student_row(sid)
    assert row["display_name"] == "Patched" and row["birth_year"] == 2014
    assert row["status"] == "ACTIVE"  # server-owned status untouched by PATCH
    assert row["updated_at"] > row["created_at"]  # updated_at advanced past the backdated value (DB-level compare)
    assert data["updated_at"] is not None  # response carries the updated timestamp (JSON string)
    # explicit null clears a nullable column
    res2 = patch_json(client, f"{STUDENT_PATH}/{sid}", {"birth_year": None}, token)
    assert res2.status_code == 200 and res2.json()["data"]["birth_year"] is None
    assert student_row(sid)["birth_year"] is None


def test_a2_patch_server_owned_fields_ignored():
    """Req 7: server-owned fields (id, parent_id, status, timestamps) and unknown fields are
    ignored (D1 'ignored if sent'); no-op body → 200, row unchanged, no event."""
    client, auth = auth_user("PARENT", "r7-a2b")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Owned")
    before = student_row(sid)
    assert updated_events(sid) == 0
    res = patch_json(
        client,
        f"{STUDENT_PATH}/{sid}",
        {
            "id": str(uuid.uuid4()),
            "parent_id": str(uuid.uuid4()),
            "status": "ARCHIVED",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "not_a_field": "x",
        },
        token,
    )
    assert res.status_code == 200, res.content
    after = student_row(sid)
    assert after["status"] == "ACTIVE" and after["parent_id"] == before["parent_id"]
    assert after["id"] == sid
    assert updated_events(sid) == 0  # no-op: no event (R6 guarded-transition silence)
    res_empty = patch_json(client, f"{STUDENT_PATH}/{sid}", {}, token)
    assert res_empty.status_code == 200 and updated_events(sid) == 0


def test_a2_patch_validation():
    """Req 8: invalid values → 400 VALIDATION_ERROR with field detail; row untouched, no event."""
    client, auth = auth_user("PARENT", "r7-a2c")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Validated")
    cases = [
        {"birth_year": 1950},
        {"birth_year": 2100},
        {"birth_year": "not-a-year"},
        {"display_name": "   "},
        {"consent_status": "NOPE"},
        {"preferred_mode": "HYBRID2"},
        {"school_year": 2026},
    ]
    for body in cases:
        res = patch_json(client, f"{STUDENT_PATH}/{sid}", body, token)
        assert res.status_code == 400, (body, res.content)
        err = res.json()["error"]
        assert err["code"] == "VALIDATION_ERROR" and err["details"].get("field")
    assert updated_events(sid) == 0
    assert student_row(sid)["display_name"] == "Validated"


def test_a2_patch_academic_level_must_exist():
    """Req 9: academic_level_id must reference an existing level (§7.3 parity)."""
    client, auth = auth_user("PARENT", "r7-a2d")
    token = auth["access_token"]
    sid = create_student_api(client, token, "LevelRef")
    for bad in (str(uuid.uuid4()), "not-a-uuid"):
        res = patch_json(client, f"{STUDENT_PATH}/{sid}", {"academic_level_id": bad}, token)
        assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"
        assert res.json()["error"]["details"].get("field") == "academic_level_id"
    assert updated_events(sid) == 0


def test_a2_patch_academic_level_must_be_active():
    """Req 10: is_active validation per D1e — inactive level → 400; active level → 200."""
    client, auth = auth_user("PARENT", "r7-a2e")
    token = auth["access_token"]
    sid = create_student_api(client, token, "LevelActive")
    level_id = str(uuid.uuid4())
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO edutrust.academic_levels (id, code, name_ar, sort_order, is_active) VALUES (%s, %s, %s, 9, FALSE)",
            [level_id, f"INACT-{level_id[:6]}", "معطل"],
        )
    res = patch_json(client, f"{STUDENT_PATH}/{sid}", {"academic_level_id": level_id}, token)
    assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert student_row(sid)["academic_level_id"] is None
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.academic_levels SET is_active = TRUE WHERE id=%s", [level_id])
    res = patch_json(client, f"{STUDENT_PATH}/{sid}", {"academic_level_id": level_id}, token)
    assert res.status_code == 200 and res.json()["data"]["academic_level_id"] == level_id
    assert updated_events(sid) == 1


def test_a2_patch_ownership_no_oracle():
    """Req 11: foreign student and unknown (non-existent) student are indistinguishable —
    uniform 403 STUDENT_ACCESS_DENIED, no existence oracle (§7.2)."""
    client_a, auth_a = auth_user("PARENT", "r7-a2f")
    client_b, auth_b = auth_user("PARENT", "r7-a2g")
    tok_a, tok_b = auth_a["access_token"], auth_b["access_token"]
    sid_a = create_student_api(client_a, tok_a, "Locked")
    foreign = patch_json(client_b, f"{STUDENT_PATH}/{sid_a}", {"display_name": "Hijack"}, tok_b)
    unknown = patch_json(client_b, f"{STUDENT_PATH}/{uuid.uuid4()}", {"display_name": "Hijack"}, tok_b)
    assert foreign.status_code == 403 and unknown.status_code == 403
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"
    assert student_row(sid_a)["display_name"] == "Locked"


def test_a2_patch_writes_event():
    """Req 12: an actual update writes exactly one STUDENT_PROFILE_UPDATED (entity student,
    actor PARENT) — D9."""
    client, auth = auth_user("PARENT", "r7-a2h")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Evented")
    assert updated_events(sid) == 0
    res = patch_json(client, f"{STUDENT_PATH}/{sid}", {"display_name": "Evented2"}, token)
    assert res.status_code == 200
    assert updated_events(sid) == 1
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT actor_user_id::text, actor_role::text, entity_type, entity_id::text, request_id IS NOT NULL
            FROM edutrust.event_ledger
            WHERE event_type='STUDENT_PROFILE_UPDATED' AND entity_id=%s
            """,
            [sid],
        )
        actor_user_id, actor_role, entity_type, entity_id, has_request_id = cur.fetchone()
    assert (actor_role, entity_type, entity_id) == ("PARENT", "student", sid)
    assert has_request_id is True


def test_a2_patch_archived_student_still_updatable():
    """§7 state table: ARCHIVED + PATCH is allowed (archive is orthogonal to field edits)."""
    client, auth = auth_user("PARENT", "r7-a2i")
    token = auth["access_token"]
    sid = create_student_api(client, token, "ArchThenEdit")
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.student_profiles SET status='ARCHIVED'::edutrust.student_status WHERE id=%s", [sid])
    res = patch_json(client, f"{STUDENT_PATH}/{sid}", {"primary_goal": "After archive"}, token)
    assert res.status_code == 200, res.content
    assert student_row(sid)["status"] == "ARCHIVED"  # status untouched by PATCH (D1)
    assert student_row(sid)["primary_goal"] == "After archive"
    assert updated_events(sid) == 1


def test_a3_delete_active_to_archived():
    """Req 14: DELETE archives ACTIVE → ARCHIVED (soft); response is the updated student object."""
    client, auth = auth_user("PARENT", "r7-a3a")
    token = auth["access_token"]
    sid = create_student_api(client, token, "ArchiveMe")
    res = client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["status"] == "ARCHIVED" and data["id"] == sid
    assert student_row(sid)["status"] == "ARCHIVED"
    assert updated_events(sid) == 1  # first (and only) transition emits the event (D9)


def test_a3_delete_ownership_no_oracle():
    """Req 15: DELETE honors ownership with the uniform no-oracle 403."""
    client_a, auth_a = auth_user("PARENT", "r7-a3b")
    client_b, auth_b = auth_user("PARENT", "r7-a3c")
    tok_a, tok_b = auth_a["access_token"], auth_b["access_token"]
    sid_a = create_student_api(client_a, tok_a, "Protected")
    foreign = client_b.delete(f"{STUDENT_PATH}/{sid_a}", **{"HTTP_AUTHORIZATION": f"Bearer {tok_b}"})
    unknown = client_b.delete(f"{STUDENT_PATH}/{uuid.uuid4()}", **{"HTTP_AUTHORIZATION": f"Bearer {tok_b}"})
    assert foreign.status_code == 403 and unknown.status_code == 403
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"
    assert student_row(sid_a)["status"] == "ACTIVE"


def test_a3_delete_idempotent_noop():
    """Req 16+17: repeated DELETE → 200 no-op; exactly ONE archive event total (D2)."""
    client, auth = auth_user("PARENT", "r7-a3d")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Twice")
    r1 = client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
    r2 = client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
    r3 = client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
    assert [r.status_code for r in (r1, r2, r3)] == [200, 200, 200]
    assert student_row(sid)["status"] == "ARCHIVED"
    assert updated_events(sid) == 1  # no second/third archive event (guarded transition)
    assert r2.json()["data"]["status"] == "ARCHIVED"  # no-op still confirms current state


def test_a3_delete_never_hard_deletes():
    """Req 18: the row always survives — including for a student with booking history
    (RESTRICT FK makes hard delete impossible by design; D2 soft archive only)."""
    client, auth = auth_user("PARENT", "r7-a3e")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Kept")
    client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
    assert student_row(sid) is not None  # row retained

    teacher = setup_teacher_with_slot()
    _, auth2, sid2 = create_parent_student()
    hold = post_json(
        client,
        "/api/v1/bookings/hold",
        {
            "student_id": sid2,
            "teacher_subject_id": teacher["teacher_subject_id"],
            "availability_slot_id": teacher["slot_id"],
        },
        auth2["access_token"],
        idem=f"r7-hold-{uuid.uuid4()}",
    )
    assert hold.status_code == 201, hold.content
    booking_id = hold.json()["data"]["booking"]["id"]
    res = client.delete(f"{STUDENT_PATH}/{sid2}", **{"HTTP_AUTHORIZATION": f"Bearer {auth2['access_token']}"})
    assert res.status_code == 200, res.content
    assert student_row(sid2)["status"] == "ARCHIVED"  # archived, NOT deleted
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.bookings WHERE id=%s", [booking_id])
        assert cur.fetchone()[0] == 1  # booking history intact (RESTRICT preserved)


def test_a4_vs1_create_get_behavior_preserved():
    """Req 19 (regression gate): VS1 create/get behavior is byte/behavior-preserved (T-30)."""
    client, auth = auth_user("PARENT", "r7-a4")
    token = auth["access_token"]
    res = post_json(client, STUDENT_PATH, {"display_name": "Classic"}, token)
    assert res.status_code == 201, res.content
    data = res.json()["data"]
    assert set(data.keys()) == {"id", "display_name", "status"}  # exact VS1 create shape
    assert data["status"] == "ACTIVE"
    assert created_events(data["id"]) == 1  # STUDENT_PROFILE_CREATED unchanged
    detail = get_json(client, f"{STUDENT_PATH}/{data['id']}", token)
    assert detail.status_code == 200
    assert set(detail.json()["data"].keys()) == {"id", "display_name", "status", "parent_id"}  # exact VS1 detail shape
    missing = get_json(client, f"{STUDENT_PATH}/{uuid.uuid4()}", token)
    assert missing.status_code == 403 and missing.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"


def test_a5_authz_matrix_and_anonymous():
    """§8 matrix (Executor A endpoints): anonymous → 401; non-PARENT roles → 403 FORBIDDEN;
    no events from denied attempts."""
    client, auth = auth_user("PARENT", "r7-a5")
    token = auth["access_token"]
    sid = create_student_api(client, token, "Matrixed")
    anon_list = get_json(client, STUDENT_PATH)
    anon_patch = patch_json(client, f"{STUDENT_PATH}/{sid}", {"display_name": "x"})
    anon_delete = client.delete(f"{STUDENT_PATH}/{sid}")
    assert anon_list.status_code == 401 and anon_patch.status_code == 401 and anon_delete.status_code == 401
    for code in (anon_list.json(), anon_patch.json(), anon_delete.json()):
        assert code["error"]["code"] == "AUTH_REQUIRED"
    teacher_client, teacher_auth = auth_user("TEACHER", "r7-a5t")
    ttok = teacher_auth["access_token"]
    t_list = get_json(teacher_client, STUDENT_PATH, ttok)
    t_patch = patch_json(teacher_client, f"{STUDENT_PATH}/{sid}", {"display_name": "x"}, ttok)
    t_delete = teacher_client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {ttok}"})
    assert t_list.status_code == 403 and t_patch.status_code == 403 and t_delete.status_code == 403
    assert updated_events(sid) == 0  # denied attempts write nothing
