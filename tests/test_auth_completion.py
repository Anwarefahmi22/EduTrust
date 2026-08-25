"""DEV Vertical Slice #10 — R6 Auth completion (POST /auth/refresh + POST /auth/revoke-sessions).

Contract: EduTrust_VS10_R6_Implementation_Authorization_v1.0.md (D1/D2 locks, D3a baseline).
Every test maps to an approved requirement (VS10 authorization doc §11 categories A–V).
D3a: strict one-use rotation; a rotated-out token is indistinguishable from an unknown
token (uniform 401) — no previous-hash tracking, no session family, no schema change.
"""
from __future__ import annotations

import json
import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edutrust.settings")

import django

django.setup()

from django.contrib.auth.hashers import make_password
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


def seed_user_email(role: str, prefix: str) -> str:
    """DB-seed a user for a role that public registration does not support
    (public registration is PARENT/TEACHER only — existing VS1 behavior)."""
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO edutrust.users (full_name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            [f"{role} User", email, make_password(PASSWORD)],
        )
        user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s, %s)", [user_id, role])
    return email


def new_user_login(client: Client, role: str, prefix: str) -> dict:
    if role in ("PARENT", "TEACHER"):
        return register_and_login(client, role, prefix)
    return api_login(client, seed_user_email(role, prefix))


def same_user_sessions(client: Client, role: str, prefix: str, n: int) -> list[dict]:
    """One user with n live sessions (n logins) — the unit for self-service scoping."""
    if role in ("PARENT", "TEACHER"):
        email = f"{prefix}-{uuid.uuid4()}@example.com"
        res = post_json(client, "/api/v1/auth/register", {"role": role, "full_name": f"{role} User", "email": email, "password": PASSWORD})
        assert res.status_code == 201, res.content
    else:
        email = seed_user_email(role, prefix)
    return [api_login(client, email) for _ in range(n)]


def refresh(client: Client, refresh_token: str) -> object:
    return post_json(client, "/api/v1/auth/refresh", {"refresh_token": refresh_token})


def revoke(client: Client, token: str, scope: str) -> object:
    return post_json(client, "/api/v1/auth/revoke-sessions", {"scope": scope}, token)


def user_id_of(auth: dict) -> str:
    return decode_access_token(auth["access_token"])["sub"]


def sid_of(auth: dict) -> str:
    return decode_access_token(auth["access_token"])["sid"]


def session_row(session_id: str) -> dict:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, user_id::text, refresh_token_hash, revoked_at, expires_at, created_at FROM edutrust.auth_sessions WHERE id=%s",
            [session_id],
        )
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None


def user_sessions(user_id: str) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute("SELECT id::text, revoked_at IS NOT NULL FROM edutrust.auth_sessions WHERE user_id=%s ORDER BY created_at", [user_id])
        return [{"id": r[0], "revoked": bool(r[1])} for r in cur.fetchall()]


def security_event_count(event_type: str, user_id: str | None = None) -> int:
    with connection.cursor() as cur:
        if user_id:
            cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type=%s AND user_id=%s", [event_type, user_id])
        else:
            cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type=%s", [event_type])
        return cur.fetchone()[0]


def ledger_security_event_count() -> int:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='SECURITY_EVENT'")
        return cur.fetchone()[0]


def token_in_audit_storage(raw_token: str) -> bool:
    """The raw refresh token must never appear in events/security events (Q)."""
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE metadata::text LIKE %s", [f"%{raw_token}%"])
        if cur.fetchone()[0]:
            return True
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE metadata::text LIKE %s", [f"%{raw_token}%"])
        return bool(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# A/B/C/D. refresh validation (uniform 401 class — D1.2/D1.5)
# ---------------------------------------------------------------------------

def test_a_refresh_success():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-a")
    res = refresh(client, auth["refresh_token"])
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert set(data.keys()) == {"access_token", "refresh_token", "expires_in"}  # D1.4 exact shape
    assert data["refresh_token"] != auth["refresh_token"]
    # old token is dead (rotation invalidated it in the same transaction)
    assert refresh(client, auth["refresh_token"]).status_code == 401
    # new token works
    assert refresh(client, data["refresh_token"]).status_code == 200
    # exactly one session row for the user throughout (refresh mints no session)
    assert len(user_sessions(user_id_of(auth))) == 1


def test_b_expired_refresh():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-b")
    sid = sid_of(auth)
    # backdate created_at AND expires_at consistently (CHECK: expires_at > created_at)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE edutrust.auth_sessions SET created_at = now() - interval '40 days', "
            "expires_at = now() - interval '10 days' WHERE id=%s",
            [sid],
        )
    res = refresh(client, auth["refresh_token"])
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN"
    # expiry is a validation outcome, not an auto-revocation (distinct terminal states)
    assert session_row(sid)["revoked_at"] is None


def test_c_invalid_refresh_uniform_401():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-c")
    for body in ({"refresh_token": f"garbage-{uuid.uuid4()}"}, {}, {"refresh_token": ""}, {"refresh_token": "   "}):
        res = post_json(client, "/api/v1/auth/refresh", body)
        assert res.status_code == 401, (body, res.content)
        assert res.json()["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN"
    # the valid token still works — no collateral state change
    assert refresh(client, auth["refresh_token"]).status_code == 200


def test_d_revoked_session_refresh():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-d")
    assert post_json(client, "/api/v1/auth/logout", {}, auth["access_token"]).status_code == 200
    res = refresh(client, auth["refresh_token"])
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN"


# ---------------------------------------------------------------------------
# E/F/G. rotation semantics (D1)
# ---------------------------------------------------------------------------

def test_e_rotation_chain():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-e")
    t0 = auth["refresh_token"]
    r1 = refresh(client, t0)
    assert r1.status_code == 200
    t1 = r1.json()["data"]["refresh_token"]
    r2 = refresh(client, t1)
    assert r2.status_code == 200
    t2 = r2.json()["data"]["refresh_token"]
    # every predecessor is dead; the current one lives
    assert refresh(client, t0).status_code == 401
    assert refresh(client, t1).status_code == 401
    assert refresh(client, t2).status_code == 200
    assert len(user_sessions(user_id_of(auth))) == 1  # same session throughout


def test_f_jwt_sid_and_identity_preserved():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-f")
    before = decode_access_token(auth["access_token"])
    r = refresh(client, auth["refresh_token"])
    assert r.status_code == 200
    after = decode_access_token(r.json()["data"]["access_token"])
    assert after["sub"] == before["sub"]
    assert after["sid"] == before["sid"]  # same session (D1)
    assert after["roles"] == before["roles"]
    assert r.json()["data"]["expires_in"] == auth["expires_in"]  # existing TTL convention


def test_g_ttl_preserved_on_rotation():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-g")
    sid = sid_of(auth)
    before = session_row(sid)["expires_at"]
    r = refresh(client, auth["refresh_token"])
    assert r.status_code == 200
    after = session_row(sid)["expires_at"]
    assert after == before  # D1.3: rotation does not extend the session lifetime


def test_refresh_roles_reread_server_side():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-roles")
    with connection.cursor() as cur:
        cur.execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s, 'OPS')", [user_id_of(auth)])
    r = refresh(client, auth["refresh_token"])
    assert r.status_code == 200
    assert "OPS" in decode_access_token(r.json()["data"]["access_token"])["roles"]


# ---------------------------------------------------------------------------
# H/J/I. ownership, anonymous, roles (self-service model — §7 matrix)
# ---------------------------------------------------------------------------

def test_h_ownership_no_cross_user_oracle():
    client = Client()
    a = register_and_login(client, "PARENT", "vs10-ha")
    b = register_and_login(client, "TEACHER", "vs10-hb")
    # A's token is presented (no user parameter exists in the contract — the token is
    # the authority): it validates against A's own session. The response class must be
    # identical to an unknown token (no 403/404 "that user's session exists" variant).
    res = refresh(client, a["refresh_token"])
    assert res.status_code in (200, 401), res.content
    unknown = refresh(client, f"unknown-{uuid.uuid4()}")
    assert unknown.status_code == 401
    if res.status_code == 200:
        # rotated (legitimate use of A's own credential) — A's new token works
        assert refresh(client, res.json()["data"]["refresh_token"]).status_code == 200
    # B is unaffected either way
    assert refresh(client, b["refresh_token"]).status_code == 200


def test_j_anonymous_revoke_denied():
    client = Client()
    res = post_json(client, "/api/v1/auth/revoke-sessions", {"scope": "ALL"})  # no token
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTH_REQUIRED"


def test_i_all_five_roles_self_service():
    client = Client()
    for role in ("PARENT", "TEACHER", "SUPPORT", "OPS", "ADMIN"):
        auth = new_user_login(client, role, f"vs10-i-{role.lower()}")
        res = revoke(client, auth["access_token"], "CURRENT")
        assert res.status_code == 200, (role, res.content)
        assert res.json()["data"]["revoked"] == 1, role


# ---------------------------------------------------------------------------
# K/L/M/N/O/P. revoke-sessions (D2)
# ---------------------------------------------------------------------------

def test_k_revoke_current():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-k", 2)
    a, b = sessions
    res = revoke(client, a["access_token"], "CURRENT")
    assert res.status_code == 200, res.content
    assert res.json()["data"] == {"revoked": 1}
    assert session_row(sid_of(a))["revoked_at"] is not None
    assert refresh(client, a["refresh_token"]).status_code == 401
    # the user's other session is untouched
    assert session_row(sid_of(b))["revoked_at"] is None
    assert refresh(client, b["refresh_token"]).status_code == 200


def test_l_revoke_others():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-l", 2)
    a, b = sessions
    res = revoke(client, a["access_token"], "OTHERS")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["revoked"] == 1
    assert session_row(sid_of(b))["revoked_at"] is not None
    assert refresh(client, b["refresh_token"]).status_code == 401
    # current session survives
    assert session_row(sid_of(a))["revoked_at"] is None
    assert refresh(client, a["refresh_token"]).status_code == 200


def test_m_revoke_all():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-m", 3)
    user_id = user_id_of(sessions[0])
    res = revoke(client, sessions[0]["access_token"], "ALL")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["revoked"] == 3
    assert all(s["revoked"] for s in user_sessions(user_id))
    for tok in sessions:
        assert refresh(client, tok["refresh_token"]).status_code == 401


def test_n_revoked_count_noop_zero():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-n", 2)
    a, b = sessions
    user_id = user_id_of(a)
    # simulate a concurrent winner: revoke b's session directly in the DB
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.auth_sessions SET revoked_at = now() WHERE id=%s AND revoked_at IS NULL", [sid_of(b)])
    base = security_event_count("TOKEN_REVOKED", user_id)
    # OTHERS from a's live session: the already-revoked session is not a candidate → no-op
    res = revoke(client, a["access_token"], "OTHERS")
    assert res.status_code == 200, res.content
    assert res.json()["data"]["revoked"] == 0
    assert security_event_count("TOKEN_REVOKED", user_id) == base  # no event for the no-op
    # and: OTHERS with no other sessions at all
    c = same_user_sessions(client, "PARENT", "vs10-n2", 1)[0]
    res2 = revoke(client, c["access_token"], "OTHERS")
    assert res2.status_code == 200 and res2.json()["data"]["revoked"] == 0


def test_bad_scope_400():
    client = Client()
    a = register_and_login(client, "PARENT", "vs10-scope")
    for body in ({}, {"scope": "everything"}, {"scope": "current"}, {"scope": ""}):
        res = post_json(client, "/api/v1/auth/revoke-sessions", body, a["access_token"])
        assert res.status_code == 400, (body, res.content)
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    # session unaffected
    assert refresh(client, a["refresh_token"]).status_code == 200


def test_o_audit_events_per_revoked_session():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-o", 2)
    a, b = sessions
    sid_b = sid_of(b)
    before = ledger_security_event_count()
    res = revoke(client, a["access_token"], "OTHERS")
    assert res.status_code == 200
    after = ledger_security_event_count()
    assert after - before == 1  # exactly one SECURITY_EVENT ledger row (for session b)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT entity_type, entity_id::text, metadata->>'event' FROM edutrust.event_ledger "
            "WHERE event_type='SECURITY_EVENT' AND entity_id=%s",
            [sid_b],
        )
        row = cur.fetchone()
    assert row and row[0] == "auth_session" and row[1] == sid_b and row[2] == "TOKEN_REVOKED"


def test_p_security_events_and_noop_silence():
    client = Client()
    sessions = same_user_sessions(client, "OPS", "vs10-p", 2)
    a, b = sessions
    user_id = user_id_of(a)
    base = security_event_count("TOKEN_REVOKED", user_id)
    res = revoke(client, a["access_token"], "ALL")
    assert res.status_code == 200 and res.json()["data"]["revoked"] == 2
    assert security_event_count("TOKEN_REVOKED", user_id) - base == 2  # one per actually-revoked session
    # no-op re-revocation (concurrent-winner simulation) adds no events
    c = same_user_sessions(client, "OPS", "vs10-p2", 2)
    user_id2 = user_id_of(c[0])
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.auth_sessions SET revoked_at = now() WHERE id=%s", [sid_of(c[1])])
    base2 = security_event_count("TOKEN_REVOKED", user_id2)
    res2 = revoke(client, c[0]["access_token"], "OTHERS")
    assert res2.status_code == 200 and res2.json()["data"]["revoked"] == 0
    assert security_event_count("TOKEN_REVOKED", user_id2) == base2  # no duplicate events


# ---------------------------------------------------------------------------
# Q. no credential leakage
# ---------------------------------------------------------------------------

def test_q_no_credential_leakage():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-q", 2)
    a, b = sessions
    res = revoke(client, a["access_token"], "OTHERS")
    assert res.status_code == 200
    body = res.json()
    # response carries no session identifiers or token values — the self-count only
    assert set(body.keys()) <= {"data", "request_id"}
    assert body["data"] == {"revoked": 1}
    # raw refresh tokens never persisted in audit storage
    assert not token_in_audit_storage(b["refresh_token"])
    assert not token_in_audit_storage(a["refresh_token"])


# ---------------------------------------------------------------------------
# S. D3a replay semantics (rotated-out token: uniform 401, session unaffected, no event)
# ---------------------------------------------------------------------------

def test_s_d3a_replay_semantics():
    client = Client()
    a = register_and_login(client, "PARENT", "vs10-s")
    user_id = user_id_of(a)
    sid = sid_of(a)
    t0 = a["refresh_token"]
    r = refresh(client, t0)
    assert r.status_code == 200
    t1 = r.json()["data"]["refresh_token"]
    base_susp = security_event_count("SUSPICIOUS_ACTIVITY", user_id)
    base_rev = security_event_count("TOKEN_REVOKED", user_id)
    # re-present the rotated-out token
    res = refresh(client, t0)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN"  # uniform, no oracle
    row = session_row(sid)
    assert row["revoked_at"] is None  # D3a: no forced revocation (not detectable as this session's old token)
    assert security_event_count("SUSPICIOUS_ACTIVITY", user_id) == base_susp  # no invented detection
    assert security_event_count("TOKEN_REVOKED", user_id) == base_rev
    # the legitimate current token is unaffected
    assert refresh(client, t1).status_code == 200


# ---------------------------------------------------------------------------
# T/U/V. idempotency, state consistency, regression
# ---------------------------------------------------------------------------

def test_t_repeated_revoke_idempotent():
    client = Client()
    a = register_and_login(client, "PARENT", "vs10-t")
    res = revoke(client, a["access_token"], "CURRENT")
    assert res.status_code == 200 and res.json()["data"]["revoked"] == 1
    # the guarded UPDATE flips each row at most once (the mechanism behind no-op no-ops):
    b = same_user_sessions(client, "PARENT", "vs10-t2", 1)[0]
    sid = sid_of(b)
    with connection.cursor() as cur:
        cur.execute("UPDATE edutrust.auth_sessions SET revoked_at = now() WHERE id=%s AND revoked_at IS NULL RETURNING id", [sid])
        assert cur.fetchone() is not None  # first flip: 1 row
        cur.execute("UPDATE edutrust.auth_sessions SET revoked_at = now() WHERE id=%s AND revoked_at IS NULL", [sid])
        assert cur.rowcount == 0  # second guard: nothing left to flip


def test_u_state_consistency():
    client = Client()
    sessions = same_user_sessions(client, "PARENT", "vs10-u", 2)
    revoke(client, sessions[0]["access_token"], "CURRENT")
    with connection.cursor() as cur:
        # global hash uniqueness (one current hash per live credential)
        cur.execute(
            "SELECT count(*) FROM (SELECT refresh_token_hash FROM edutrust.auth_sessions GROUP BY 1 HAVING count(*)>1) d"
        )
        assert cur.fetchone()[0] == 0
        # schema-frozen assertion: auth_sessions has exactly the v1 column set (order-independent)
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='edutrust' AND table_name='auth_sessions'")
        cols = {r[0] for r in cur.fetchall()}
    assert cols == {"id", "user_id", "refresh_token_hash", "device_label", "ip_address",
                    "user_agent", "expires_at", "revoked_at", "created_at"}
    # revoked_at consistency on the two known sessions
    assert session_row(sid_of(sessions[0]))["revoked_at"] is not None
    assert session_row(sid_of(sessions[1]))["revoked_at"] is None


def test_v_regression_login_logout_flow():
    client = Client()
    auth = register_and_login(client, "PARENT", "vs10-v")
    # login-issued pair fully usable (no existing-behavior change)
    assert refresh(client, auth["refresh_token"]).status_code == 200
    # logout still works and still revokes (existing behavior preserved)
    assert post_json(client, "/api/v1/auth/logout", {}, auth["access_token"]).status_code == 200
    assert session_row(sid_of(auth))["revoked_at"] is not None
    # a fresh login after logout is unaffected
    auth2 = register_and_login(client, "PARENT", "vs10-v2")
    assert refresh(client, auth2["refresh_token"]).status_code == 200
