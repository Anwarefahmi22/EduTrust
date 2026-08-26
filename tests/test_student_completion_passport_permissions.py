"""R7 (VS10 candidate 2) — Student Passport + Permissions, Executor B (B1–B3).

Contract: EduTrust_VS10_R7_Implementation_Authorization_v1.0.md
  B1 GET    /students/:id/passport                  (D3; API §7.4 exact shape; no event on read)
  B2 POST   /students/:id/permissions               (D4 + D7; §10 idempotency; §7.5 rules)
  B3 DELETE /students/:id/permissions/:permission_id (D5; guarded terminal transition)
Ownership: VS1 no-oracle convention — uniform 403 STUDENT_ACCESS_DENIED for foreign AND
unknown ids. No schema change; no financial surface (asserted directly).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import django
from django.db import connection
from django.utils import timezone

django.setup()

from tests.test_payment_slice_2 import initiate
from tests.test_session_slice_3 import report_payload
from tests.test_vertical_slice_1 import (
    auth_user,
    get_json,
    post_json,
    setup_teacher_with_slot,
)

STUDENT_PATH = "/api/v1/students"


# ---------------------------------------------------------------- helpers


def parent_with_student(prefix: str, name: str = "Passport Kid"):
    client, auth = auth_user("PARENT", prefix)
    token = auth["access_token"]
    res = post_json(client, STUDENT_PATH, {"display_name": name}, token)
    assert res.status_code == 201, res.content
    return client, token, res.json()["data"]["id"]


def extra_slot(setup: dict, offset_hours: int = 48):
    from tests.test_vertical_slice_1 import patch_json  # noqa: F401  (convention import)
    ttok = setup["teacher_auth"]["access_token"]
    starts = (timezone.now() + timedelta(hours=offset_hours)).replace(microsecond=0)
    ends = starts + timedelta(hours=1)
    res = post_json(
        setup["teacher_client"],
        "/api/v1/teachers/availability/slots",
        {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "mode": "ONLINE"},
        ttok,
    )
    assert res.status_code == 201, res.content
    return res.json()["data"]["id"]


def completed_session_for(client, token: str, student_id: str, setup: dict | None = None,
                          complete: bool = True, report: dict | None = None,
                          rename_subject: str | None = None, clear_name_en: bool = False):
    """Full VS3-compatible flow: hold → pay (DEV mock) → session start/complete → report."""
    setup = setup or setup_teacher_with_slot()
    if rename_subject or clear_name_en:
        with connection.cursor() as cur:
            if clear_name_en:
                cur.execute("UPDATE edutrust.subjects SET name_en = NULL WHERE id = %s", [setup["subject_id"]])
            if rename_subject:
                cur.execute("UPDATE edutrust.subjects SET name_en = %s WHERE id = %s", [rename_subject, setup["subject_id"]])
    hold = post_json(
        client,
        "/api/v1/bookings/hold",
        {"student_id": student_id, "teacher_subject_id": setup["teacher_subject_id"], "availability_slot_id": setup["slot_id"]},
        token,
        idem=f"hold-{uuid.uuid4()}",
    )
    assert hold.status_code == 201, hold.content
    booking_id = hold.json()["data"]["booking"]["id"]
    payment = initiate(client, token, booking_id).json()["data"]["payment"]
    ok = post_json(client, f"/api/v1/payments/{payment['id']}/mock/succeed", {"provider_event_id": f"evt-{uuid.uuid4()}"}, token)
    assert ok.status_code == 200, ok.content
    session_id = ok.json()["data"]["session_id"]
    ttok = setup["teacher_auth"]["access_token"]
    if complete:
        start = post_json(setup["teacher_client"], f"/api/v1/sessions/{session_id}/start", {}, ttok)
        assert start.status_code == 200, start.content
        done = post_json(setup["teacher_client"], f"/api/v1/sessions/{session_id}/complete", {}, ttok)
        assert done.status_code == 200, done.content
        if report is not False:
            rep = post_json(setup["teacher_client"], f"/api/v1/sessions/{session_id}/report", report or report_payload(), ttok)
            assert rep.status_code == 201, rep.content
    return {"session_id": session_id, "booking_id": booking_id, "teacher_id": setup["teacher_id"],
            "subject_id": setup["subject_id"], "setup": setup}


def insert_progress(student_id: str, subject_id: str, event_type: str, *, topic: str | None = None,
                    note: str | None = None, created_at=None, session_id: str | None = None):
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO edutrust.student_progress_events
                (student_id, session_id, subject_id, event_type, source_type, topic, note, created_at)
            VALUES (%s, %s, %s, %s::edutrust.progress_event_type, 'TEACHER_REPORT', %s, %s, %s)
            """,
            [student_id, session_id, subject_id, event_type, topic, note,
             created_at or timezone.now()],
        )


def passport(client, token: str, student_id: str):
    return get_json(client, f"{STUDENT_PATH}/{student_id}/passport", token)


def grant(client, token: str, student_id: str, body: dict, idem: str | None = None):
    return post_json(client, f"{STUDENT_PATH}/{student_id}/permissions", body, token, idem=idem)


def grant_body(teacher_id: str, **extra):
    return {"teacher_id": teacher_id, "scope": "SESSION_CONTEXT", **extra}


def revoke(client, token: str, student_id: str, permission_id: str):
    return client.delete(f"{STUDENT_PATH}/{student_id}/permissions/{permission_id}",
                         **{"HTTP_AUTHORIZATION": f"Bearer {token}"})


def permission_rows(student_id: str, teacher_id: str | None = None):
    sql = "SELECT id::text, teacher_id::text, scope, revoked_at, expires_at FROM edutrust.student_permissions WHERE student_id = %s"
    args = [student_id]
    if teacher_id:
        sql += " AND teacher_id = %s"
        args.append(teacher_id)
    with connection.cursor() as cur:
        cur.execute(sql + " ORDER BY created_at", args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def updated_events(student_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='STUDENT_PROFILE_UPDATED' AND entity_id=%s", [student_id])
        return cur.fetchone()[0]


def financial_counts() -> tuple:
    with connection.cursor() as cur:
        out = []
        for table in ("payments", "refunds", "payouts", "payout_items"):
            cur.execute(f"SELECT count(*) FROM edutrust.{table}")
            out.append(cur.fetchone()[0])
    return tuple(out)


def student_subject_entry(payload: dict, subject_id: str) -> dict:
    matches = [s for s in payload["subjects"] if s["subject_id"] == subject_id]
    assert len(matches) == 1, f"expected exactly one entry for {subject_id}: {payload['subjects']}"
    return matches[0]


# ================================================================ B1 PASSPORT


def test_passport_own_access_exact_shape():
    client, token, sid = parent_with_student("b1-shape")
    completed_session_for(client, token, sid)
    res = passport(client, token, sid)
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert set(data.keys()) == {"student_id", "subjects"}
    assert data["student_id"] == sid
    assert len(data["subjects"]) == 1
    entry = data["subjects"][0]
    assert set(entry.keys()) == {"subject_id", "subject_name", "completed_sessions",
                                 "recent_topics", "recurring_weaknesses", "recent_progress_notes"}
    assert entry["completed_sessions"] == 1
    assert entry["subject_name"] == "Mathematics"  # subjects.name_en (D3)


def test_passport_cross_parent_and_unknown_uniform_403():
    client, token, sid = parent_with_student("b1-oracle")
    other_client, other_auth = auth_user("PARENT", "b1-oracle-foreign")
    foreign = passport(other_client, other_auth["access_token"], sid)
    unknown = passport(client, token, str(uuid.uuid4()))
    assert foreign.status_code == 403 and unknown.status_code == 403
    # no-oracle: the error code and status are identical for foreign AND unknown ids
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"


def test_passport_empty_without_completed_data():
    client, token, sid = parent_with_student("b1-empty")
    res = passport(client, token, sid)
    assert res.status_code == 200, res.content
    assert res.json()["data"] == {"student_id": sid, "subjects": []}


def test_passport_scheduled_session_alone_is_excluded():
    client, token, sid = parent_with_student("b1-sched")
    completed_session_for(client, token, sid, complete=False, report=False)  # SCHEDULED, no report
    res = passport(client, token, sid)
    assert res.status_code == 200, res.content
    assert res.json()["data"]["subjects"] == []  # only COMPLETED sessions aggregate (D3)


def test_passport_multiple_subjects():
    client, token, sid = parent_with_student("b1-multi")
    first = completed_session_for(client, token, sid)
    second = completed_session_for(client, token, sid, rename_subject="Physics")
    res = passport(client, token, sid)
    assert res.status_code == 200, res.content
    subjects = res.json()["data"]["subjects"]
    assert {s["subject_name"] for s in subjects} == {"Mathematics", "Physics"}
    assert student_subject_entry(res.json()["data"], first["subject_id"])["completed_sessions"] == 1
    assert student_subject_entry(res.json()["data"], second["subject_id"])["completed_sessions"] == 1


def test_passport_completed_sessions_counts_per_subject():
    client, token, sid = parent_with_student("b1-count")
    setup = setup_teacher_with_slot()
    completed_session_for(client, token, sid, setup=setup)
    setup["slot_id"] = extra_slot(setup)  # second slot for the same teacher/subject
    completed_session_for(client, token, sid, setup=setup)
    res = passport(client, token, sid)
    entry = student_subject_entry(res.json()["data"], setup["subject_id"])
    assert entry["completed_sessions"] == 2


def test_passport_topics_distinct_latest_ten():
    client, token, sid = parent_with_student("b1-topics")
    flow = completed_session_for(client, token, sid)  # writes TOPIC_COVERED: "Linear equations", "Functions"
    subject_id = flow["subject_id"]
    base = timezone.now()
    for i in range(1, 12):  # 11 distinct topics, increasing recency
        insert_progress(sid, subject_id, "TOPIC_COVERED", topic=f"Topic-{i:02d}",
                        created_at=base + timedelta(minutes=i))
    # a duplicate occurrence of an existing topic, NEWER than everything else
    insert_progress(sid, subject_id, "TOPIC_COVERED", topic="Linear equations",
                    created_at=base + timedelta(minutes=12))
    entry = student_subject_entry(passport(client, token, sid).json()["data"], subject_id)
    topics = entry["recent_topics"]
    assert len(topics) == 10  # latest-10 limit (D3)
    assert topics[0] == "Linear equations"  # most recent occurrence wins the position
    assert topics.count("Linear equations") == 1  # distinct topic behavior
    assert "Topic-02" not in topics  # the oldest distinct topic fell out of the window


def test_passport_recurring_weaknesses_threshold():
    client, token, sid = parent_with_student("b1-weak")
    flow = completed_session_for(client, token, sid)
    subject_id = flow["subject_id"]
    base = timezone.now()
    for _ in range(2):
        insert_progress(sid, subject_id, "WEAKNESS_OBSERVED", topic="Geometry", created_at=base)
    insert_progress(sid, subject_id, "WEAKNESS_OBSERVED", topic="Fractions", created_at=base)
    for _ in range(3):
        insert_progress(sid, subject_id, "WEAKNESS_OBSERVED", topic="Word problems", created_at=base)
    entry = student_subject_entry(passport(client, token, sid).json()["data"], subject_id)
    assert entry["recurring_weaknesses"] == ["Geometry", "Word problems"]  # >= 2 threshold (D3)
    assert "Fractions" not in entry["recurring_weaknesses"]


def test_passport_progress_notes_types_limit_order():
    client, token, sid = parent_with_student("b1-notes")
    flow = completed_session_for(client, token, sid)  # VS3 writes >= 3 PROGRESS_NOTE events
    subject_id = flow["subject_id"]
    base = timezone.now()
    insert_progress(sid, subject_id, "PARTICIPATION_NOTE", note="Participated well", created_at=base + timedelta(minutes=1))
    for i in range(2, 7):  # five newer PROGRESS_NOTE notes
        insert_progress(sid, subject_id, "PROGRESS_NOTE", note=f"Note-{i}",
                        created_at=base + timedelta(minutes=i))
    entry = student_subject_entry(passport(client, token, sid).json()["data"], subject_id)
    notes = entry["recent_progress_notes"]
    assert len(notes) == 5  # latest-5 limit (D3)
    assert notes[0] == "Note-6" and notes[4] == "Note-2"  # recency order
    assert "Participated well" not in notes  # pushed out of the window by newer notes
    # PARTICIPATION_NOTE participates in the same bucket when recent enough
    insert_progress(sid, subject_id, "PARTICIPATION_NOTE", note="Newest participation",
                    created_at=base + timedelta(minutes=10))
    notes = student_subject_entry(passport(client, token, sid).json()["data"], subject_id)["recent_progress_notes"]
    assert notes[0] == "Newest participation"


def test_passport_subject_name_arabic_fallback():
    client, token, sid = parent_with_student("b1-arabic")
    flow = completed_session_for(client, token, sid, clear_name_en=True)
    entry = student_subject_entry(passport(client, token, sid).json()["data"], flow["subject_id"])
    assert entry["subject_name"] == "رياضيات"  # name_ar fallback when name_en absent (D3)


def test_passport_no_event_on_read():
    client, token, sid = parent_with_student("b1-noevt")
    completed_session_for(client, token, sid)
    before = updated_events(sid)
    assert passport(client, token, sid).status_code == 200
    assert passport(client, token, sid).status_code == 200
    assert updated_events(sid) == before  # reads never emit STUDENT_PROFILE_UPDATED (D9)


def test_passport_vs3_compatibility():
    client, token, sid = parent_with_student("b1-vs3")
    flow = completed_session_for(client, token, sid)  # pure VS3 API path, no SQL seeding
    payload = report_payload()
    entry = student_subject_entry(passport(client, token, sid).json()["data"], flow["subject_id"])
    assert set(payload["topics_covered"]) <= set(entry["recent_topics"])
    assert payload["teacher_observations"] in entry["recent_progress_notes"]
    assert payload["recommended_revision"] in entry["recent_progress_notes"]


# ================================================================ B2 GRANT


def test_grant_success_shape_and_event():
    client, token, sid = parent_with_student("b2-ok")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    res = grant(client, token, sid, grant_body(teacher_id), idem=f"grant-{uuid.uuid4()}")
    assert res.status_code == 201, res.content
    permission = res.json()["data"]["permission"]
    assert set(permission.keys()) == {"id", "student_id", "parent_id", "teacher_id",
                                      "granted_for_booking_id", "scope", "starts_at",
                                      "expires_at", "revoked_at", "created_at"}
    assert permission["scope"] == "SESSION_CONTEXT"
    assert permission["teacher_id"] == teacher_id
    assert permission["revoked_at"] is None and permission["granted_for_booking_id"] is None
    assert updated_events(sid) == 1  # exactly one STUDENT_PROFILE_UPDATED on creation (D9)


def test_grant_requires_idempotency_key():
    client, token, sid = parent_with_student("b2-idemreq")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    res = grant(client, token, sid, grant_body(teacher_id))  # no key
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert permission_rows(sid) == []


def test_grant_scope_validation():
    client, token, sid = parent_with_student("b2-scope")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    missing = grant(client, token, sid, {"teacher_id": teacher_id}, idem=f"g-{uuid.uuid4()}")
    bad = grant(client, token, sid, {"teacher_id": teacher_id, "scope": "FULL_PROFILE"}, idem=f"g-{uuid.uuid4()}")
    assert missing.status_code == 400 and bad.status_code == 400
    assert missing.json()["error"]["code"] == bad.json()["error"]["code"] == "VALIDATION_ERROR"
    assert permission_rows(sid) == []


def test_grant_teacher_validation():
    client, token, sid = parent_with_student("b2-teacher")
    unknown = grant(client, token, sid, grant_body(str(uuid.uuid4())), idem=f"g-{uuid.uuid4()}")
    malformed = grant(client, token, sid, grant_body("not-a-uuid"), idem=f"g-{uuid.uuid4()}")
    assert unknown.status_code == 400 and malformed.status_code == 400
    assert unknown.json()["error"]["code"] == malformed.json()["error"]["code"] == "VALIDATION_ERROR"
    assert permission_rows(sid) == []


def test_grant_ownership_no_oracle():
    client, token, sid = parent_with_student("b2-own")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    other_client, other_auth = auth_user("PARENT", "b2-own-foreign")
    foreign = grant(other_client, other_auth["access_token"], sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    unknown = grant(client, token, str(uuid.uuid4()), grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    assert foreign.status_code == unknown.status_code == 403
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"
    assert permission_rows(sid) == []


def test_grant_valid_booking_triple():
    client, token, sid = parent_with_student("b2-triple")
    flow = completed_session_for(client, token, sid)
    body = grant_body(flow["teacher_id"], granted_for_booking_id=flow["booking_id"])
    res = grant(client, token, sid, body, idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 201, res.content
    permission = res.json()["data"]["permission"]
    assert permission["granted_for_booking_id"] == flow["booking_id"]


def test_grant_foreign_parent_booking():
    client, token, sid = parent_with_student("b2-fpb")
    # A booking owned by a DIFFERENT parent (fresh VS1-VS3 flow)
    other_client, other_token, other_sid = parent_with_student("b2-fpb-other")
    other_flow = completed_session_for(other_client, other_token, other_sid)
    body = grant_body(other_flow["teacher_id"], granted_for_booking_id=other_flow["booking_id"])
    res = grant(client, token, sid, body, idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"  # uniform, no oracle (D4/D7)
    assert permission_rows(sid) == []


def test_grant_wrong_teacher_booking():
    client, token, sid = parent_with_student("b2-wtb")
    flow = completed_session_for(client, token, sid)  # booking taught by teacher X
    other_teacher = setup_teacher_with_slot()["teacher_id"]  # presented teacher Y
    body = grant_body(other_teacher, granted_for_booking_id=flow["booking_id"])
    res = grant(client, token, sid, body, idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert permission_rows(sid) == []


def test_grant_unknown_booking():
    client, token, sid = parent_with_student("b2-ub")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    body = grant_body(teacher_id, granted_for_booking_id=str(uuid.uuid4()))
    res = grant(client, token, sid, body, idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_grant_booking_wrong_student():
    client, auth = auth_user("PARENT", "b2-bws")
    token = auth["access_token"]
    sids = []
    for name in ("Kid One", "Kid Two"):
        res = post_json(client, STUDENT_PATH, {"display_name": name}, token)
        assert res.status_code == 201, res.content
        sids.append(res.json()["data"]["id"])
    sid_a, sid_b = sids
    flow = completed_session_for(client, token, sid_b)  # booking is for the parent's OTHER student
    body = grant_body(flow["teacher_id"], granted_for_booking_id=flow["booking_id"])
    res = grant(client, token, sid_a, body, idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"  # booking.student_id != path student (D7)
    assert permission_rows(sid_a) == []


def test_grant_canonical_replay_same_key():
    client, token, sid = parent_with_student("b2-replay")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    key = f"grant-{uuid.uuid4()}"
    first = grant(client, token, sid, grant_body(teacher_id), idem=key)
    assert first.status_code == 201, first.content
    second = grant(client, token, sid, grant_body(teacher_id), idem=key)
    assert second.status_code == 200  # §10 replay convention: 200 stored body
    assert second.json()["data"] == first.json()["data"]
    assert len(permission_rows(sid)) == 1
    assert updated_events(sid) == 1  # no second event on replay


def test_grant_same_key_different_body_conflict():
    client, token, sid = parent_with_student("b2-keyconf")
    t1 = setup_teacher_with_slot()["teacher_id"]
    t2 = setup_teacher_with_slot()["teacher_id"]
    key = f"grant-{uuid.uuid4()}"
    assert grant(client, token, sid, grant_body(t1), idem=key).status_code == 201
    res = grant(client, token, sid, grant_body(t2), idem=key)  # same key, different canonical
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert len(permission_rows(sid)) == 1


def test_grant_duplicate_active_different_key():
    client, token, sid = parent_with_student("b2-dup")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    assert grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").status_code == 201
    res = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 409  # D4: duplicate ACTIVE canonical permission
    assert res.json()["error"]["code"] == "DUPLICATE_PERMISSION"
    assert len(permission_rows(sid)) == 1
    assert updated_events(sid) == 1


def test_grant_after_revoke_creates_new_row():
    client, token, sid = parent_with_student("b2-regrant")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    first = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    assert revoke(client, token, sid, first["id"]).status_code == 200
    second = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    assert second.status_code == 201  # revocation is terminal per row → new row allowed (D5)
    assert second.json()["data"]["permission"]["id"] != first["id"]
    rows = permission_rows(sid)
    assert len(rows) == 2
    assert rows[0]["revoked_at"] is not None and rows[1]["revoked_at"] is None


def test_grant_expired_permission_not_active():
    client, token, sid = parent_with_student("b2-expired")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    with connection.cursor() as cur:  # an already-expired row is NOT active (D5 predicate)
        cur.execute("SELECT parent_id::text FROM edutrust.student_profiles WHERE id = %s", [sid])
        parent_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO edutrust.student_permissions
                (student_id, parent_id, teacher_id, scope, starts_at, expires_at)
            VALUES (%s, %s, %s, 'SESSION_CONTEXT', now() - interval '2 days', now() - interval '1 day')
            """,
            [sid, parent_id, teacher_id],
        )
    res = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 201, res.content
    active = [r for r in permission_rows(sid) if r["revoked_at"] is None and r["expires_at"] is not None]
    assert len(active) == 1  # the expired row is NOT active; exactly the new grant remains


def test_grant_expires_at_validation():
    client, token, sid = parent_with_student("b2-expval")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    past = grant(client, token, sid, grant_body(teacher_id, expires_at="2020-01-01T00:00:00Z"), idem=f"g-{uuid.uuid4()}")
    garbage = grant(client, token, sid, grant_body(teacher_id, expires_at="next tuesday"), idem=f"g-{uuid.uuid4()}")
    assert past.status_code == 400 and garbage.status_code == 400
    assert past.json()["error"]["code"] == garbage.json()["error"]["code"] == "VALIDATION_ERROR"
    assert permission_rows(sid) == []


def test_grant_no_financial_side_effects():
    client, token, sid = parent_with_student("b2-fin")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    before = financial_counts()
    permission = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    revoke(client, token, sid, permission["id"])
    assert financial_counts() == before  # grant/revoke touch no financial table


def test_grant_admin_role_forbidden():
    from tests.test_vertical_slice_4 import admin_login

    client, token, sid = parent_with_student("b2-admin")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    admin_token = admin_login(client, "b2-admin-op")
    res = grant(client, admin_token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")
    assert res.status_code == 403  # PARENT-only surface; no admin mutation path exists in R7
    assert res.json()["error"]["code"] == "FORBIDDEN"
    assert permission_rows(sid) == []


# ================================================================ B3 REVOKE


def test_revoke_success_terminal_and_event():
    client, token, sid = parent_with_student("b3-ok")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    permission = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    events_before = updated_events(sid)
    res = revoke(client, token, sid, permission["id"])
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["revoked_at"] is not None  # revoked_at set (D5)
    rows = permission_rows(sid)
    assert len(rows) == 1  # row retained — never hard-deleted
    assert rows[0]["revoked_at"] is not None
    assert updated_events(sid) == events_before + 1  # exactly one event on first transition (D9)


def test_revoke_idempotent_noop_no_second_event():
    client, token, sid = parent_with_student("b3-idem")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    permission = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    first = revoke(client, token, sid, permission["id"])
    revoked_at = first.json()["data"]["revoked_at"]
    second = revoke(client, token, sid, permission["id"])
    assert second.status_code == 200  # idempotent no-op (D5)
    assert second.json()["data"]["revoked_at"] == revoked_at  # unchanged — single transition
    assert updated_events(sid) == 2  # grant(1) + revoke(1); no event for the no-op


def test_revoke_ownership_no_oracle():
    client, token, sid = parent_with_student("b3-oracle")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    permission = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    other_client, other_auth = auth_user("PARENT", "b3-oracle-foreign")
    foreign = revoke(other_client, other_auth["access_token"], sid, permission["id"])
    unknown = revoke(client, token, sid, str(uuid.uuid4()))
    assert foreign.status_code == unknown.status_code == 403
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"
    assert permission_rows(sid)[0]["revoked_at"] is None  # untouched


def test_revoke_wrong_student_uniform_403():
    client, token, sid_a = parent_with_student("b3-ws-a")
    _, token_b, sid_b = parent_with_student("b3-ws-b")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    # permission granted on student B, addressed under student A's path
    permission = grant(client, token_b, sid_b, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    res = revoke(client, token, sid_a, permission["id"])
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "STUDENT_ACCESS_DENIED"  # uniform — no oracle
    assert permission_rows(sid_b)[0]["revoked_at"] is None


def test_revoke_parent_role_required():
    client, token, sid = parent_with_student("b3-role")
    teacher_setup = setup_teacher_with_slot()
    permission = grant(client, token, sid, grant_body(teacher_setup["teacher_id"]), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    ttok = teacher_setup["teacher_auth"]["access_token"]
    res = revoke(teacher_setup["teacher_client"], ttok, sid, permission["id"])
    assert res.status_code == 403  # role gate: PARENT only
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_revoke_terminal_row_not_reactivated():
    client, token, sid = parent_with_student("b3-terminal")
    teacher_id = setup_teacher_with_slot()["teacher_id"]
    first = grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}").json()["data"]["permission"]
    revoke(client, token, sid, first["id"])
    grant(client, token, sid, grant_body(teacher_id), idem=f"g-{uuid.uuid4()}")  # re-grant: NEW row
    rows = permission_rows(sid)
    assert len(rows) == 2
    assert rows[0]["id"] == first["id"] and rows[0]["revoked_at"] is not None  # old row stays dead
    assert rows[1]["revoked_at"] is None  # only the new row is active
