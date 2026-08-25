"""DEV Vertical Slice #10 — R6 Auth Completion E2E (DEV mock only).

Standalone end-to-end suite (not collected by pytest). Mirrors the VS2–VS9 E2E
convention: isolated temporary PostgreSQL cluster + migrations + Django dev server +
scripted scenario checks against the live HTTP API, plus direct-SQL state assertions.
Scenarios per the approved VS10 R6 Implementation Authorization (E2E matrix S1–S8;
S3 in its D3a form — strict one-use rotation, uniform 401 on rotated-token reuse,
no detection event, no forced revocation).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
PG_BIN = os.environ.get("PG_BIN", "/home/user/.venv-edutrust/lib/python3.11/site-packages/pgserver/pginstall/bin")
PY = sys.executable or "python3"
BASE = Path(f"/tmp/vs10_e2e_{os.getpid()}")
PORT = int(os.environ.get("VS10_E2E_PGPORT", "55482"))
API_PORT = int(os.environ.get("VS10_E2E_APIPORT", "8102"))
API = f"http://127.0.0.1:{API_PORT}"
DB = "edutrust_e2e"

_results: list[tuple[str, str, bool, str]] = []


def check(scenario: str, desc: str, ok: bool, detail: str = "") -> None:
    _results.append((scenario, desc, ok, detail))
    suffix = "" if ok else f"  [FAIL detail: {detail}]"
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}{suffix}", flush=True)


def psql(sql: str) -> str:
    r = subprocess.run(
        [f"{PG_BIN}/psql", "-h", str(BASE / "socket"), "-p", str(PORT), "-d", DB, "-tAc", sql],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql failed: {r.stderr}")
    return r.stdout.strip()


def api(method: str, path: str, token: str | None = None, body: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, API + path, json=body, headers=headers, timeout=30)
    try:
        data = r.json()
    except ValueError:
        data = {}
    return r.status_code, data


def register(role: str, prefix: str) -> str:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    status, _ = api("POST", "/api/v1/auth/register", body={"role": role, "full_name": f"{role} E2E", "email": email, "password": "StrongPassword123!"})
    assert status == 201, f"register {role}: {status}"
    return email


def login(email: str) -> dict:
    status, data = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": "StrongPassword123!"})
    assert status == 200, f"login: {status}"
    return data["data"]


def session_id_of(access_token: str) -> str:
    import jwt as pyjwt
    return pyjwt.decode(access_token, options={"verify_signature": False})["sid"]


def refresh_status(rt: str) -> tuple[int, dict]:
    return api("POST", "/api/v1/auth/refresh", body={"refresh_token": rt})


def revoke_status(token: str, scope: str) -> tuple[int, dict]:
    return api("POST", "/api/v1/auth/revoke-sessions", token=token, body={"scope": scope})


# ---------------------------------------------------------------------------
# Scenarios (approved VS10 R6 E2E matrix)
# ---------------------------------------------------------------------------

def s1_refresh_success() -> None:
    S = "S1_REFRESH_SUCCESS"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s1")
    auth = login(email)
    assert set(auth.keys()) == {"user_id", "roles", "access_token", "refresh_token", "expires_in"}
    t0 = auth["refresh_token"]
    st, data = refresh_status(t0)
    check(S, "refresh -> 200 with exact approved shape", st == 200 and set(data["data"].keys()) == {"access_token", "refresh_token", "expires_in"}, f"{st} {data}")
    t1 = data["data"]["refresh_token"]
    check(S, "old refresh token dead after rotation", refresh_status(t0)[0] == 401, str(refresh_status(t0)))
    check(S, "new refresh token live", refresh_status(t1)[0] == 200, str(refresh_status(t1)))
    n = psql("SELECT count(*) FROM edutrust.auth_sessions WHERE user_id=(SELECT id FROM edutrust.users WHERE email=%s)" % f"'{email}'")
    check(S, "refresh mints no session row (still exactly 1)", n == "1", n)


def s2_rotation_chain() -> None:
    S = "S2_ROTATION_CHAIN"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s2")
    auth = login(email)
    st, d = refresh_status(auth["refresh_token"])
    assert st == 200
    t1 = d["data"]["refresh_token"]
    sid0 = session_id_of(auth["access_token"])
    st2, d2 = refresh_status(t1)
    assert st2 == 200
    t2 = d2["data"]["refresh_token"]
    sid2 = session_id_of(d2["data"]["access_token"])
    check(S, "sid preserved across rotations (same session)", sid0 == sid2, f"{sid0} vs {sid2}")
    check(S, "every predecessor dead (T0, T1)", refresh_status(auth["refresh_token"])[0] == 401 and refresh_status(t1)[0] == 401, "")
    check(S, "current token (T2) live", refresh_status(t2)[0] == 200, "")
    n = psql("SELECT count(*) FROM edutrust.auth_sessions WHERE user_id=(SELECT id FROM edutrust.users WHERE email=%s)" % f"'{email}'")
    check(S, "single session row after two rotations", n == "1", n)


def s3_d3a_replay_semantics() -> None:
    S = "S3_D3A_REPLAY"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s3")
    auth = login(email)
    sid = session_id_of(auth["access_token"])
    t0 = auth["refresh_token"]
    st, d = refresh_status(t0)
    assert st == 200
    t1 = d["data"]["refresh_token"]
    susp_before = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='SUSPICIOUS_ACTIVITY'")
    st, data = refresh_status(t0)  # reuse the rotated-out token
    check(S, "rotated-out token -> uniform 401 (no oracle)", st == 401 and data["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN", f"{st} {data}")
    revoked = psql("SELECT count(*) FROM edutrust.auth_sessions WHERE id=%s AND revoked_at IS NOT NULL" % f"'{sid}'")
    check(S, "D3a: no forced revocation (schema cannot identify this session's old token)", revoked == "0", revoked)
    susp_after = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='SUSPICIOUS_ACTIVITY'")
    check(S, "D3a: no invented detection event", susp_after == susp_before, f"{susp_before} -> {susp_after}")
    check(S, "legitimate current token (T1) unaffected", refresh_status(t1)[0] == 200, "")


def s4_revoke_current() -> None:
    S = "S4_REVOKE_CURRENT"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s4")
    a = login(email)
    b = login(email)
    sid_a, sid_b = session_id_of(a["access_token"]), session_id_of(b["access_token"])
    st, data = revoke_status(a["access_token"], "CURRENT")
    check(S, "revoke CURRENT -> 200 revoked:1", st == 200 and data["data"] == {"revoked": 1}, f"{st} {data}")
    check(S, "current session revoked in DB", psql("SELECT count(*) FROM edutrust.auth_sessions WHERE id=%s AND revoked_at IS NOT NULL" % f"'{sid_a}'") == "1", "")
    check(S, "other session untouched", psql("SELECT count(*) FROM edutrust.auth_sessions WHERE id=%s AND revoked_at IS NULL" % f"'{sid_b}'") == "1", "")
    check(S, "current refresh token dead", refresh_status(a["refresh_token"])[0] == 401, "")
    check(S, "other refresh token live", refresh_status(b["refresh_token"])[0] == 200, "")
    ev = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='TOKEN_REVOKED' AND metadata::text LIKE %s" % f"'%{sid_a}%'")
    check(S, "exactly one TOKEN_REVOKED security event for the revoked session", ev == "1", ev)


def s5_revoke_others() -> None:
    S = "S5_REVOKE_OTHERS"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s5")
    a = login(email)
    b = login(email)
    c = login(email)
    sid_a = session_id_of(a["access_token"])
    st, data = revoke_status(a["access_token"], "OTHERS")
    check(S, "revoke OTHERS (2 targets) -> 200 revoked:2", st == 200 and data["data"]["revoked"] == 2, f"{st} {data}")
    check(S, "current session survives", psql("SELECT count(*) FROM edutrust.auth_sessions WHERE id=%s AND revoked_at IS NULL" % f"'{sid_a}'") == "1", "")
    ev = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='TOKEN_REVOKED' AND user_id=(SELECT id FROM edutrust.users WHERE email=%s)" % f"'{email}'")
    check(S, "two TOKEN_REVOKED events (one per revoked session)", ev == "2", ev)
    ledger = psql("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='SECURITY_EVENT' AND entity_type='auth_session' AND metadata->>'event'='TOKEN_REVOKED' AND entity_id IN (SELECT id FROM edutrust.auth_sessions WHERE user_id=(SELECT id FROM edutrust.users WHERE email=%s))" % f"'{email}'")
    check(S, "two audit ledger rows for the user's revocations", ledger == "2", ledger)


def s6_revoke_all() -> None:
    S = "S6_REVOKE_ALL"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s6")
    sessions = [login(email) for _ in range(3)]
    st, data = revoke_status(sessions[0]["access_token"], "ALL")
    check(S, "revoke ALL (3 sessions) -> 200 revoked:3", st == 200 and data["data"]["revoked"] == 3, f"{st} {data}")
    left = psql("SELECT count(*) FROM edutrust.auth_sessions WHERE user_id=(SELECT id FROM edutrust.users WHERE email=%s) AND revoked_at IS NULL" % f"'{email}'")
    check(S, "no live session remains", left == "0", left)
    dead = all(refresh_status(s["refresh_token"])[0] == 401 for s in sessions)
    check(S, "all three refresh tokens dead", dead, "")


def s7_expired_session_refresh() -> None:
    S = "S7_EXPIRED_SESSION"
    print(f"\n== {S} ==", flush=True)
    email = register("PARENT", "vs10e2e-s7")
    auth = login(email)
    sid = session_id_of(auth["access_token"])
    psql("UPDATE edutrust.auth_sessions SET created_at = now() - interval '40 days', expires_at = now() - interval '10 days' WHERE id=%s" % f"'{sid}'")
    st, data = refresh_status(auth["refresh_token"])
    check(S, "expired session refresh -> uniform 401", st == 401 and data["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN", f"{st} {data}")
    revoked = psql("SELECT count(*) FROM edutrust.auth_sessions WHERE id=%s AND revoked_at IS NOT NULL" % f"'{sid}'")
    check(S, "expiry is not auto-revocation", revoked == "0", revoked)


def s8_authorization_security() -> None:
    S = "S8_AUTHZ_SECURITY"
    print(f"\n== {S} ==", flush=True)
    pa = register("PARENT", "vs10e2e-s8a")
    tb = register("TEACHER", "vs10e2e-s8b")
    a = login(pa)
    b = login(tb)
    st, _ = api("POST", "/api/v1/auth/revoke-sessions", body={"scope": "ALL"})
    check(S, "anonymous revoke -> 401 AUTH_REQUIRED", st == 401, str(st))
    # cross-user: the contract carries no user parameter — a foreign token is simply an
    # unknown credential to this endpoint; outcomes must be indistinguishable (no oracle)
    st_unknown, data_unknown = refresh_status(f"unknown-{uuid.uuid4()}")
    st_foreign, data_foreign = refresh_status(b["refresh_token"])
    check(S, "unknown token -> 401 uniform code", st_unknown == 401 and data_unknown["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN", f"{st_unknown} {data_unknown}")
    check(S, "foreign-user token: 200 (validates against its own session) or 401 uniform — never 403/404", st_foreign in (200, 401), f"{st_foreign} {data_foreign}")
    # a is unaffected by b's credential being presented
    check(S, "owner session unaffected by foreign-token presentation", refresh_status(a["refresh_token"])[0] == 200, "")
    # no session identifiers or tokens in the revoke response
    st, data = revoke_status(b["access_token"], "OTHERS")
    check(S, "revoke response is the self-count only (no ids/tokens)", st == 200 and data["data"] == {"revoked": 0}, f"{st} {data}")
    # raw tokens never persisted in audit storage
    leak = psql("SELECT count(*) FROM (SELECT 1 FROM edutrust.event_ledger WHERE metadata::text LIKE %s UNION ALL SELECT 1 FROM edutrust.security_events WHERE metadata::text LIKE %s) d" % (f"'%{b['refresh_token']}%'", f"'%{b['refresh_token']}%'"))
    check(S, "no raw refresh token in audit storage", leak == "0", leak)


def main() -> int:
    print("VS10 E2E — R6 Auth Completion (DEV mock only)", flush=True)
    print(f"PG_BIN={PG_BIN}", flush=True)
    BASE.mkdir(parents=True, exist_ok=True)
    data_dir, sock_dir = BASE / "data", BASE / "socket"
    data_dir.mkdir(exist_ok=True)
    sock_dir.mkdir(exist_ok=True)
    server = None
    try:
        subprocess.run([f"{PG_BIN}/initdb", "-D", str(data_dir), "--auth-local=trust", "--auth-host=trust", "--no-instructions", "--encoding=UTF8"], check=True, capture_output=True)
        subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(data_dir), "-l", str(BASE / "pg.log"), "-o", f"-k {sock_dir} -p {PORT} -F", "start"], check=True, capture_output=True)
        subprocess.run([f"{PG_BIN}/createdb", "-h", str(sock_dir), "-p", str(PORT), DB], check=True, capture_output=True)
        env = dict(os.environ,
                   PATH=f"{PG_BIN}:{os.environ.get('PATH', '')}",
                   DATABASE_URL=f"postgresql://{os.environ.get('USER', 'user')}@localhost:{PORT}/{DB}",
                   APP_ENV="development", DEBUG="true", SECRET_KEY="e2e-secret",
                   JWT_SECRET="e2e-jwt-secret-with-at-least-32-bytes",
                   MOCK_PAYMENT_PROVIDER_ENABLED="true", REAL_PAYMENT_ENABLED="false", REAL_PAYOUT_ENABLED="false",
                   PYTHONPATH=str(REPO / "backend"), DJANGO_SETTINGS_MODULE="edutrust.settings")
        subprocess.run([PY, str(REPO / "scripts/run_migrations.py")], check=True, env=env, cwd=REPO, capture_output=True)
        server = subprocess.Popen([PY, str(REPO / "backend/manage.py"), "runserver", f"127.0.0.1:{API_PORT}", "--noreload"],
                                  env=env, cwd=REPO / "backend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                if requests.get(API + "/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            raise RuntimeError("Django dev server did not start")

        s1_refresh_success()
        s2_rotation_chain()
        s3_d3a_replay_semantics()
        s4_revoke_current()
        s5_revoke_others()
        s6_revoke_all()
        s7_expired_session_refresh()
        s8_authorization_security()
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(data_dir), "stop", "-m", "fast"], capture_output=True)
        shutil.rmtree(BASE, ignore_errors=True)

    total = len(_results)
    failed = [c for c in _results if not c[2]]
    print(f"\nVS10 E2E RESULT: {total - len(failed)}/{total} checks passed", flush=True)
    for sc, desc, ok, detail in failed:
        print(f"  FAILED in {sc}: {desc} — {detail}", flush=True)
    if not failed:
        print("E2E_AUTH_COMPLETION=PASS", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
