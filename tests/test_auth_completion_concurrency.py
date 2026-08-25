"""DEV Vertical Slice #10 — R6 Auth completion concurrency (C01–C05).

Lock strategy (approved, authorization doc §10): the existing auth_sessions row lock —
rotation takes the session row FOR UPDATE inside one transaction; revocation uses
guarded UPDATEs after a SELECT ... FOR UPDATE over the caller's candidate rows.
auth_sessions is a leaf object (no cross-object lock order) — acyclic by construction.
All post-race assertions are made directly against the database.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edutrust.settings")

import django

django.setup()

from django.test import Client
from django.db import connection

from edutrust_api.auth import decode_access_token

PASSWORD = "StrongPassword123!"


def post_json(client: Client, path: str, data: dict, token: str | None = None):
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.post(path, data=json.dumps(data), content_type="application/json", **headers)


def register_and_login(client: Client, role: str, email_prefix: str) -> dict:
    email = f"{email_prefix}-{uuid.uuid4()}@example.com"
    res = post_json(client, "/api/v1/auth/register", {"role": role, "full_name": f"{role} User", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.content
    return api_login(client, email)


def api_login(client: Client, email: str) -> dict:
    login = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": PASSWORD})
    assert login.status_code == 200, login.content
    return login.json()["data"]


def same_user_sessions(client: Client, prefix: str, n: int) -> list[dict]:
    """One PARENT user with n live sessions (n logins)."""
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    res = post_json(client, "/api/v1/auth/register", {"role": "PARENT", "full_name": "P User", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.content
    return [api_login(client, email) for _ in range(n)]


def refresh(client: Client, refresh_token: str) -> object:
    return post_json(client, "/api/v1/auth/refresh", {"refresh_token": refresh_token})


def revoke(client: Client, token: str, scope: str) -> object:
    return post_json(client, "/api/v1/auth/revoke-sessions", {"scope": scope}, token)


def user_id_of(auth: dict) -> str:
    return decode_access_token(auth["access_token"])["sub"]


def sid_of(auth: dict) -> str:
    return decode_access_token(auth["access_token"])["sid"]


def user_sessions(user_id: str) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id::text, refresh_token_hash, revoked_at IS NOT NULL, expires_at "
            "FROM edutrust.auth_sessions WHERE user_id=%s ORDER BY created_at",
            [user_id],
        )
        return [{"id": r[0], "hash": r[1], "revoked": bool(r[2]), "expires_at": r[3]} for r in cur.fetchall()]


def token_revoked_events(user_id: str) -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='TOKEN_REVOKED' AND user_id=%s", [user_id])
        return cur.fetchone()[0]


def test_c01_two_simultaneous_refresh_same_token():
    """CR-1: exactly one valid rotation; the other caller gets the uniform 401.
    No double rotation, no corrupted row, one live credential."""
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-c01")
    user_id = user_id_of(auth)
    t0 = auth["refresh_token"]
    results: list[int] = []
    winners: list[str] = []
    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        res = refresh(client, t0)
        results.append(res.status_code)
        if res.status_code == 200:
            winners.append(res.json()["data"]["refresh_token"])

    t1 = threading.Thread(target=attempt)
    t2 = threading.Thread(target=attempt)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert sorted(results) == [200, 401], results  # exactly one rotation wins
    assert len(winners) == 1
    rows = user_sessions(user_id)
    assert len(rows) == 1  # same session, no row corruption
    assert rows[0]["revoked"] is False
    # the winner's new token is the session's current hash (rotation landed exactly once)
    assert rows[0]["hash"] == hashlib.sha256(winners[0].encode("utf-8")).hexdigest()
    # the original token is dead; the winner's token works
    assert refresh(client, t0).status_code == 401
    assert refresh(client, winners[0]).status_code == 200


def test_c02_refresh_vs_revoke_current():
    """CR-2: consistent terminal state in both interleavings; the session ends
    revoked either way; exactly one TOKEN_REVOKED event (no duplicates)."""
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-c02")
    user_id = user_id_of(auth)
    sid = sid_of(auth)
    t0 = auth["refresh_token"]
    base = token_revoked_events(user_id)
    results: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def do_refresh():
        barrier.wait()
        results["refresh"] = refresh(client, t0).status_code

    def do_revoke():
        barrier.wait()
        results["revoke"] = revoke(client, auth["access_token"], "CURRENT").status_code

    t1 = threading.Thread(target=do_refresh)
    t2 = threading.Thread(target=do_revoke)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert results["revoke"] == 200, results
    assert results["refresh"] in (200, 401), results  # rotation won → 200; revocation won → 401
    rows = user_sessions(user_id)
    assert len(rows) == 1
    assert rows[0]["id"] == sid
    assert rows[0]["revoked"] is True  # revoked in either interleaving
    assert token_revoked_events(user_id) - base == 1  # exactly one revocation event
    # no usable credential remains
    assert refresh(client, t0).status_code == 401


def test_c03_refresh_vs_revoke_all():
    """CR-3: one user, two live sessions; refresh(session A's token) races
    revoke-ALL(session B's token — B's ALL covers the whole user incl. A's session).
    Final state: every session of the user is revoked; the revoke call flips exactly
    the rows that were still live when it ran; events = rows flipped (once each)."""
    client = Client()
    sessions = same_user_sessions(client, "vs10-c03", 2)
    a, b = sessions
    user_id = user_id_of(a)
    t0 = a["refresh_token"]
    base = token_revoked_events(user_id)
    results: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def do_refresh():
        barrier.wait()
        results["refresh"] = refresh(client, t0).status_code

    def do_revoke():
        barrier.wait()
        res = revoke(client, b["access_token"], "ALL")
        results["revoke"] = res.status_code
        results["revoked"] = res.json()["data"]["revoked"]

    t1 = threading.Thread(target=do_refresh)
    t2 = threading.Thread(target=do_revoke)
    t1.start(); t2.start(); t1.join(); t2.join()

    assert results["revoke"] == 200, results
    assert results["refresh"] in (200, 401), results
    rows = user_sessions(user_id)
    assert len(rows) == 2
    assert all(r["revoked"] for r in rows)  # ALL revokes everything, whatever the rotation did
    assert results["revoked"] in (1, 2)  # the rows that were still live when the revoke ran
    assert token_revoked_events(user_id) - base == 2  # each row flips exactly once, once total
    # nothing usable remains
    assert refresh(client, t0).status_code == 401
    assert refresh(client, b["refresh_token"]).status_code == 401


def test_c04_concurrent_revoke_others_same_current():
    """CR-4: one user, three sessions; two concurrent revoke-OTHERS calls issued
    from the SAME current session (two tabs): both target exactly {S2, S3}; each
    target row flips once; counts partition the target set; no duplicate events;
    the current session survives."""
    client = Client()
    sessions = same_user_sessions(client, "vs10-c04", 3)
    a, b, c = sessions
    user_id = user_id_of(a)
    base = token_revoked_events(user_id)
    counts: list[int] = []
    barrier = threading.Barrier(2)

    def do_revoke():
        barrier.wait()
        res = revoke(client, a["access_token"], "OTHERS")
        assert res.status_code == 200, res.content
        counts.append(res.json()["data"]["revoked"])

    t1 = threading.Thread(target=do_revoke)
    t2 = threading.Thread(target=do_revoke)
    t1.start(); t2.start(); t1.join(); t2.join()

    rows = user_sessions(user_id)
    assert len(rows) == 3
    assert [r for r in rows if r["id"] == sid_of(a)][0]["revoked"] is False  # current survives
    assert sum(1 for r in rows if r["revoked"]) == 2  # b and c sessions revoked
    assert sum(counts) == 2  # partition of the 2 target rows
    assert token_revoked_events(user_id) - base == 2  # no duplicate events


def test_c05_repeated_concurrent_revoke_all():
    """CR-5: one user, three live sessions; three concurrent revoke-ALL calls (one
    per session token). The first committer flips all rows; late callers may
    authenticate (200, revoked: 0) or find their session already dead (401 at the
    per-request session check — a legitimate outcome). Invariants: each row flips
    exactly once; event count = session count; the 200-counts partition the rows;
    all credentials dead."""
    client = Client()
    sessions = same_user_sessions(client, "vs10-c05", 3)
    user_id = user_id_of(sessions[0])
    base = token_revoked_events(user_id)
    outcomes: list[tuple[int, int]] = []
    barrier = threading.Barrier(3)

    def do_revoke(auth: dict):
        barrier.wait()
        res = revoke(client, auth["access_token"], "ALL")
        if res.status_code == 200:
            outcomes.append((200, res.json()["data"]["revoked"]))
        else:
            outcomes.append((res.status_code, 0))

    threads = [threading.Thread(target=do_revoke, args=(s,)) for s in sessions]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = user_sessions(user_id)
    assert len(rows) == 3
    assert all(r["revoked"] for r in rows)
    ok = [n for status, n in outcomes if status == 200]
    assert len(ok) >= 1, outcomes
    assert sum(ok) == 3, outcomes  # partition of the 3 rows across the successful calls
    assert token_revoked_events(user_id) - base == 3  # one event per row, exactly once
    # all credentials dead
    for s in sessions:
        assert refresh(client, s["refresh_token"]).status_code == 401
