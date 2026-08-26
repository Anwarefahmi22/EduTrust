"""R7 (VS10 candidate 2) — Student Passport + Permissions, Executor B — concurrency.

Lock strategy (authorization §11): E5/E6 lock the owning student_profiles row FOR UPDATE
inside the transaction FIRST, then operate on student_permissions rows (leaves). The
duplicate-active check therefore serializes WITHOUT any schema change or unique index
(there is none on the canonical tuple — proved by the races below hitting real database
state, not mocks).

  C-1 two concurrent grants, SAME idempotency key + body  → 201 + 200 replay, 1 row, 1 event
  C-2 two concurrent grants, DIFFERENT keys, same canonical → 201 + 409, exactly 1 active row
  C-2b N=4 concurrent grants, different keys               → one 201, three 409, 1 active row
  C-3 grant (duplicate canonical) vs revoke of the existing row → serialized on the student
      row; final state always consistent: the revoked row stays revoked, at most one active
  C-3b two concurrent revokes → both 200, exactly ONE transition + ONE event (D5)
"""
from __future__ import annotations

import threading
import uuid

import django
from django.db import connection

django.setup()

from tests.test_vertical_slice_1 import auth_user, post_json

STUDENT_PATH = "/api/v1/students"


def make_fixture(prefix: str):
    """Parent + student via the public API only."""
    client, auth = auth_user("PARENT", f"b2c-{prefix}")
    token = auth["access_token"]
    res = post_json(client, STUDENT_PATH, {"display_name": f"Race-{prefix}"}, token)
    assert res.status_code == 201, res.content
    sid = res.json()["data"]["id"]
    return client, token, sid


def teacher_id() -> str:
    from tests.test_vertical_slice_1 import get_json, setup_teacher_with_slot

    setup = setup_teacher_with_slot()
    tid = setup["teacher_id"]
    # keep a reference so the profile clearly exists
    assert get_json(setup["teacher_client"], f"/api/v1/teachers/{tid}", setup["teacher_auth"]["access_token"]).status_code == 200
    return tid


def grant(client, token: str, sid: str, tid: str, idem: str):
    return post_json(client, f"{STUDENT_PATH}/{sid}/permissions",
                     {"teacher_id": tid, "scope": "SESSION_CONTEXT"}, token, idem=idem)


def revoke(client, token: str, sid: str, pid: str):
    return client.delete(f"{STUDENT_PATH}/{sid}/permissions/{pid}",
                         **{"HTTP_AUTHORIZATION": f"Bearer {token}"})


def rows_for(sid: str, tid: str):
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, revoked_at, (expires_at IS NULL OR expires_at > now()) AS unexpired
            FROM edutrust.student_permissions WHERE student_id = %s AND teacher_id = %s
            ORDER BY created_at
            """,
            [sid, tid],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def updated_events(sid: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='STUDENT_PROFILE_UPDATED' AND entity_id=%s", [sid])
        return cur.fetchone()[0]


def run_threads(n: int, fn) -> list:
    results: list = []
    barrier = threading.Barrier(n)

    def attempt(i: int):
        barrier.wait()
        results.append(fn(i))

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_c1_concurrent_grants_same_key_replay():
    client, token, sid = make_fixture("c1")
    tid = teacher_id()
    key = f"grant-{uuid.uuid4()}"
    results = run_threads(2, lambda i: grant(client, token, sid, tid, key))
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 201], statuses  # creation + idempotent replay (§10)
    assert results[0].json()["data"] == results[1].json()["data"]  # identical stored body
    assert len(rows_for(sid, tid)) == 1  # exactly one permission row
    assert updated_events(sid) == 1  # one event, not two


def test_c2_concurrent_grants_different_keys_one_active():
    client, token, sid = make_fixture("c2")
    tid = teacher_id()
    results = run_threads(2, lambda i: grant(client, token, sid, tid, f"grant-{uuid.uuid4()}"))
    statuses = sorted(r.status_code for r in results)
    assert statuses == [201, 409], statuses  # one creation, one duplicate-active (D4)
    assert all(r.status_code != 500 for r in results)  # no race-induced 500
    rows = rows_for(sid, tid)
    assert len(rows) == 1  # exactly one row — the loser rolled back
    active = [r for r in rows if r["revoked_at"] is None and r["unexpired"]]
    assert len(active) == 1
    assert updated_events(sid) == 1  # exactly one grant event


def test_c2b_four_concurrent_grants_exactly_one_active():
    client, token, sid = make_fixture("c2b")
    tid = teacher_id()
    results = run_threads(4, lambda i: grant(client, token, sid, tid, f"grant-{uuid.uuid4()}"))
    statuses = sorted(r.status_code for r in results)
    assert statuses == [201, 409, 409, 409], statuses
    rows = rows_for(sid, tid)
    assert len(rows) == 1
    assert len([r for r in rows if r["revoked_at"] is None]) == 1  # at most ONE active grant
    assert updated_events(sid) == 1


def test_c3_grant_vs_revoke_race_consistent_final_state():
    client, token, sid = make_fixture("c3")
    tid = teacher_id()
    existing = grant(client, token, sid, tid, f"grant-{uuid.uuid4()}")
    assert existing.status_code == 201, existing.content
    pid = existing.json()["data"]["permission"]["id"]

    results = run_threads(2, lambda i: (
        grant(client, token, sid, tid, f"grant-{uuid.uuid4()}") if i == 0 else revoke(client, token, sid, pid)
    ))
    statuses = sorted(r.status_code for r in results)
    # Serialized on the student row. Either order is contract-consistent:
    #   revoke first → grant re-creates (201); grant first → duplicate 409, then revoke.
    assert statuses in ([200, 201], [200, 409]), statuses
    assert all(r.status_code != 500 for r in results)
    rows = rows_for(sid, tid)
    original = [r for r in rows if r["id"] == pid][0]
    assert original["revoked_at"] is not None  # the revocation always wins on its own row
    active = [r for r in rows if r["revoked_at"] is None and r["unexpired"]]
    assert len(active) <= 1  # never two active canonical grants
    if statuses == [200, 409]:
        assert len(rows) == 1  # grant was the duplicate → no new row
    else:
        assert len(rows) == 2  # revoke committed first → re-grant created a fresh row


def test_c3b_concurrent_revokes_single_transition():
    client, token, sid = make_fixture("c3b")
    tid = teacher_id()
    permission = grant(client, token, sid, tid, f"grant-{uuid.uuid4()}").json()["data"]["permission"]
    pid = permission["id"]
    results = run_threads(2, lambda i: revoke(client, token, sid, pid))
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 200], statuses  # both succeed (idempotent no-op for the loser)
    rows = rows_for(sid, tid)
    assert len(rows) == 1 and rows[0]["revoked_at"] is not None  # row retained, revoked once
    # grant(1) + exactly one revoke transition (D5: no second event on the no-op)
    assert updated_events(sid) == 2
