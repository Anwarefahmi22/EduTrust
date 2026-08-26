"""R7 (VS10 candidate 2) — Student Management Completion, Executor A (A1–A3) — standalone E2E.

Contract: EduTrust_VS10_R7_Implementation_Authorization_v1.0.md (D1/D2/D6/D9; Executor A scope
list / patch / archive — NO passport, NO permissions, NO teacher context in this phase).
Established E2E pattern (VS2–VS10): isolated temporary PostgreSQL cluster + full migration
chain + Django dev server + scripted HTTP scenario checks + direct-SQL state assertions.
No financial mutations (S8 asserts the financial tables are untouched).
"""
from __future__ import annotations

import json
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
BASE = Path(f"/tmp/r7_mgmt_e2e_{os.getpid()}")
PORT = int(os.environ.get("R7_E2E_PGPORT", "55492"))
API_PORT = int(os.environ.get("R7_E2E_APIPORT", "8103"))
API = f"http://127.0.0.1:{API_PORT}"
DB = "edutrust_e2e"
PASSWORD = "StrongPassword123!"

_results: list[tuple[str, str, bool, str]] = []


def check(scenario: str, desc: str, ok: bool, detail: str = "") -> None:
    _results.append((scenario, desc, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}" + (f" — {detail}" if detail and not ok else ""), flush=True)


def psql(sql: str) -> str:
    out = subprocess.run(
        [f"{PG_BIN}/psql", "-h", str(BASE / "socket"), "-p", str(PORT), DB, "-tA", "-c", sql],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> requests.Response:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, API + path, json=body, headers=headers, timeout=10)


def register_and_login(role: str, prefix: str) -> dict:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    r = api("POST", "/api/v1/auth/register", body={"role": role, "full_name": f"{role} User", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def event_count(event_type: str, entity_id: str) -> int:
    return int(psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='{event_type}' AND entity_id='{entity_id}'"))


def s1_create_vs1_preserved() -> None:
    print("== S1_CREATE_VS1_PRESERVED ==", flush=True)
    auth = register_and_login("PARENT", "r7e2e-p1")
    token = auth["access_token"]
    r = api("POST", "/api/v1/students", token, {"display_name": "E2E Student"})
    check("S1", "VS1 create → 201 with exact legacy shape", r.status_code == 201 and set(r.json()["data"].keys()) == {"id", "display_name", "status"}, r.text)
    sid = r.json()["data"]["id"]
    check("S1", "STUDENT_PROFILE_CREATED event written", event_count("STUDENT_PROFILE_CREATED", sid) == 1)


def s2_list() -> tuple[str, str]:
    print("== S2_LIST ==", flush=True)
    auth = register_and_login("PARENT", "r7e2e-p2")
    token = auth["access_token"]
    r1 = api("POST", "/api/v1/students", token, {"display_name": "Listed A"})
    sid1 = r1.json()["data"]["id"]
    r2 = api("POST", "/api/v1/students", token, {"display_name": "Listed B"})
    sid2 = r2.json()["data"]["id"]
    r = api("GET", "/api/v1/students", token)
    data = r.json().get("data")
    check("S2", "list → 200 envelope with own students", r.status_code == 200 and isinstance(data, list) and {sid1, sid2} <= {i["id"] for i in data}, r.text)
    check("S2", "list item field set per D6", all(set(i.keys()) == {"id", "display_name", "status", "parent_id", "created_at"} for i in data))
    check("S2", "list ordering created_at DESC", [i["id"] for i in data][:2] == [sid2, sid1])
    return token, sid1


def s3_patch(token: str, sid: str) -> None:
    print("== S3_PATCH ==", flush=True)
    before = event_count("STUDENT_PROFILE_UPDATED", sid)
    r = api("PATCH", f"/api/v1/students/{sid}", token, {"display_name": "E2E Patched", "school_year": "2026/2027", "consent_status": "PENDING"})
    check("S3", "PATCH → 200 updated student object", r.status_code == 200 and r.json()["data"]["display_name"] == "E2E Patched", r.text)
    check("S3", "DB row updated", psql(f"SELECT display_name || '|' || school_year || '|' || consent_status FROM edutrust.student_profiles WHERE id='{sid}'") == "E2E Patched|2026/2027|PENDING")
    check("S3", "exactly one STUDENT_PROFILE_UPDATED for the update", event_count("STUDENT_PROFILE_UPDATED", sid) == before + 1)
    r400 = api("PATCH", f"/api/v1/students/{sid}", token, {"birth_year": 1950})
    check("S3", "invalid birth_year → 400 VALIDATION_ERROR", r400.status_code == 400 and r400.json()["error"]["code"] == "VALIDATION_ERROR", r400.text)


def s4_detail(token: str, sid: str) -> None:
    print("== S4_DETAIL_VS1_PRESERVED ==", flush=True)
    r = api("GET", f"/api/v1/students/{sid}", token)
    check("S4", "VS1 detail → 200 with exact legacy shape", r.status_code == 200 and set(r.json()["data"].keys()) == {"id", "display_name", "status", "parent_id"}, r.text)
    check("S4", "detail reflects the patch", r.json()["data"]["display_name"] == "E2E Patched")


def s5_archive(token: str, sid: str) -> None:
    print("== S5_ARCHIVE ==", flush=True)
    before = event_count("STUDENT_PROFILE_UPDATED", sid)
    r = api("DELETE", f"/api/v1/students/{sid}", token)
    check("S5", "DELETE → 200 archived", r.status_code == 200 and r.json()["data"]["status"] == "ARCHIVED", r.text)
    check("S5", "DB status ARCHIVED, row retained", psql(f"SELECT status FROM edutrust.student_profiles WHERE id='{sid}'") == "ARCHIVED")
    check("S5", "exactly one archive event (first transition only)", event_count("STUDENT_PROFILE_UPDATED", sid) == before + 1)


def s6_repeat_delete(token: str, sid: str) -> None:
    print("== S6_REPEAT_DELETE_NOOP ==", flush=True)
    before = event_count("STUDENT_PROFILE_UPDATED", sid)
    r = api("DELETE", f"/api/v1/students/{sid}", token)
    check("S6", "repeat DELETE → 200 no-op", r.status_code == 200 and r.json()["data"]["status"] == "ARCHIVED", r.text)
    check("S6", "no second archive event", event_count("STUDENT_PROFILE_UPDATED", sid) == before)
    check("S6", "row still present (never hard-deleted)", psql(f"SELECT count(*) FROM edutrust.student_profiles WHERE id='{sid}'") == "1")


def s7_no_oracle(sid: str, expected_events: int) -> None:
    print("== S7_NO_ORACLE ==", flush=True)
    other = register_and_login("PARENT", "r7e2e-p3")
    r_foreign = api("PATCH", f"/api/v1/students/{sid}", other["access_token"], {"display_name": "Hijack"})
    r_unknown = api("PATCH", f"/api/v1/students/{uuid.uuid4()}", other["access_token"], {"display_name": "Hijack"})
    check("S7", "foreign student PATCH → 403 STUDENT_ACCESS_DENIED", r_foreign.status_code == 403 and r_foreign.json()["error"]["code"] == "STUDENT_ACCESS_DENIED", r_foreign.text)
    check("S7", "unknown student PATCH → identical 403 (no oracle)", r_unknown.status_code == 403 and r_unknown.json()["error"]["code"] == r_foreign.json()["error"]["code"])
    r_del = api("DELETE", f"/api/v1/students/{sid}", other["access_token"])
    check("S7", "foreign student DELETE → 403 uniform", r_del.status_code == 403 and r_del.json()["error"]["code"] == "STUDENT_ACCESS_DENIED", r_del.text)
    check("S7", "victim row untouched", psql(f"SELECT display_name FROM edutrust.student_profiles WHERE id='{sid}'") == "E2E Patched")
    r_list = api("GET", "/api/v1/students", other["access_token"])
    check("S7", "cross-parent list isolation", sid not in {i["id"] for i in r_list.json()["data"]})
    denied_events = event_count("STUDENT_PROFILE_UPDATED", sid)
    check("S7", "denied attempts write no new events", denied_events == expected_events, f"expected {expected_events}, got {denied_events}")


def s8_no_financial_mutations() -> None:
    print("== S8_NO_FINANCIAL_MUTATIONS ==", flush=True)
    counts = {t: psql(f"SELECT count(*) FROM edutrust.{t}") for t in ("payments", "refunds", "payouts", "payout_items", "ledger_transactions", "ledger_entries")}
    ok = all(v == "0" for v in counts.values())
    check("S8", "financial tables all empty after the whole slice flow (no R7 financial surface)", ok, str(counts))


def main() -> int:
    print("R7 MANAGEMENT E2E — Student Management Completion, Executor A (DEV mock only)", flush=True)
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

        s1_create_vs1_preserved()
        token, sid = s2_list()
        s3_patch(token, sid)
        s4_detail(token, sid)
        s5_archive(token, sid)
        s6_repeat_delete(token, sid)
        s7_no_oracle(sid, expected_events=2)  # 1 update (S3) + 1 archive (S5)
        s8_no_financial_mutations()
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
    print(f"\nR7 MANAGEMENT E2E RESULT: {total - len(failed)}/{total} checks passed", flush=True)
    for sc, desc, ok, detail in failed:
        print(f"  FAILED in {sc}: {desc} — {detail}", flush=True)
    if not failed:
        print("R7_STUDENT_MANAGEMENT_E2E=PASS", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
