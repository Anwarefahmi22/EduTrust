"""R7 (VS10 candidate 2) — Student Management Completion, Executor A — concurrency.

Lock strategy (authorization doc §11): the student_profiles row lock (FOR UPDATE) serializes
all management mutations; student_profiles/student_permissions are leaf objects — acyclic by
construction. All post-race assertions are made directly against the database.

  C-4 two concurrent PATCHes on the same student → both 200, last-writer-wins (D1d INFERRED),
      one event per successful update.
  C-5 PATCH vs DELETE on the same student → both 200 in either interleaving; the student ends
      ARCHIVED; events per actual transitions (1 update + 1 archive).
  C-6 two concurrent DELETEs → both 200; exactly one archive transition event (D2, R6
      guarded-transition convention).
"""
from __future__ import annotations

import threading
import uuid

from django.db import connection

from tests.test_vertical_slice_1 import auth_user, post_json

STUDENT_PATH = "/api/v1/students"


def student_row(student_id: str):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id::text, display_name, status::text, updated_at FROM edutrust.student_profiles WHERE id = %s",
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


def make_student(prefix: str):
    client, auth = auth_user("PARENT", f"r7c-{prefix}")
    token = auth["access_token"]
    res = post_json(client, STUDENT_PATH, {"display_name": f"Race-{prefix}"}, token)
    assert res.status_code == 201, res.content
    return client, auth, res.json()["data"]["id"]


def patch(client, token: str, sid: str, body: dict):
    from tests.test_vertical_slice_1 import patch_json

    return patch_json(client, f"{STUDENT_PATH}/{sid}", body, token)


def delete(client, token: str, sid: str):
    return client.delete(f"{STUDENT_PATH}/{sid}", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})


def test_c04_two_concurrent_patches_same_student():
    """C-4: last-writer-wins under the row lock; both callers succeed; one event per update."""
    client, auth, sid = make_student("c04")
    token = auth["access_token"]
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt(name: str):
        barrier.wait()
        res = patch(client, token, sid, {"display_name": name})
        results.append(res.status_code)

    t1 = threading.Thread(target=attempt, args=("WinnerA",))
    t2 = threading.Thread(target=attempt, args=("WinnerB",))
    t1.start(); t2.start(); t1.join(); t2.join()

    assert sorted(results) == [200, 200], results  # both succeed (D1d: last-writer-wins, no versioning)
    row = student_row(sid)
    assert row["display_name"] in {"WinnerA", "WinnerB"}  # exactly one writer's value survives
    assert updated_events(sid) == 2  # one event per successful update (D9)
    assert row["status"] == "ACTIVE"


def test_c05_patch_vs_delete_race():
    """C-5: consistent terminal state in both interleavings — the student ends ARCHIVED, no
    credential/state corruption, events = one per actual transition."""
    client, auth, sid = make_student("c05")
    token = auth["access_token"]
    results: list[int] = []
    barrier = threading.Barrier(2)

    def do_patch():
        barrier.wait()
        results.append(patch(client, token, sid, {"display_name": "PatchedInRace"}).status_code)

    def do_delete():
        barrier.wait()
        results.append(delete(client, token, sid).status_code)

    t1 = threading.Thread(target=do_patch)
    t2 = threading.Thread(target=do_delete)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert sorted(results) == [200, 200], results  # both succeed in either order (§7: PATCH allowed on ARCHIVED)
    row = student_row(sid)
    assert row["status"] == "ARCHIVED"  # terminal state: archived
    assert row["display_name"] in {"PatchedInRace", "Race-c05"}  # patch applied or not, per ordering
    assert updated_events(sid) == 2  # exactly 1 update event + exactly 1 archive event


def test_c06_two_concurrent_deletes():
    """C-6: both 200 (idempotent no-op for the loser); exactly ONE archive event; row retained."""
    client, auth, sid = make_student("c06")
    token = auth["access_token"]
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        results.append(delete(client, token, sid).status_code)

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert sorted(results) == [200, 200], results
    row = student_row(sid)
    assert row is not None and row["status"] == "ARCHIVED"  # row retained, archived once
    assert updated_events(sid) == 1  # no duplicate archive events (D2 guarded transition)
