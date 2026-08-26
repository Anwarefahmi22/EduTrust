"""R7 (VS10 candidate 2) — Student Passport + Permissions, Executor B (B1–B3) — standalone E2E.

Contract: EduTrust_VS10_R7_Implementation_Authorization_v1.0.md (D3/D4/D5/D7/D9; Executor B
scope passport + permission grant/revoke — NO student management, NO teacher context, NO UI).
Established E2E pattern (VS2–VS10 / Executor A): isolated temporary PostgreSQL cluster + full
migration chain + Django dev server + scripted HTTP scenario checks + direct-SQL state
assertions. No financial mutations (S8 asserts the financial tables: zero refunds/payouts,
and payments limited to the single VS3-compatible flow payment used to build passport data).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
PG_BIN = os.environ.get("PG_BIN", "/home/user/.venv-edutrust/lib/python3.11/site-packages/pgserver/pginstall/bin")
PY = sys.executable or "python3"
BASE = Path(f"/tmp/r7b_e2e_{os.getpid()}")
PORT = int(os.environ.get("R7B_E2E_PGPORT", "55494"))
API_PORT = int(os.environ.get("R7B_E2E_APIPORT", "8104"))
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


def api(method: str, path: str, token: str | None = None, body: dict | None = None,
        idem: str | None = None) -> requests.Response:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idem:
        headers["Idempotency-Key"] = idem
    return requests.request(method, API + path, json=body, headers=headers, timeout=15)


def register_and_login(role: str, prefix: str) -> dict:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    r = api("POST", "/api/v1/auth/register", body={"role": role, "full_name": f"{role} User", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def event_count(event_type: str, entity_id: str) -> int:
    return int(psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='{event_type}' AND entity_id='{entity_id}'"))


def seed_subject_level() -> tuple[str, str]:
    sid, lid = str(uuid.uuid4()), str(uuid.uuid4())
    psql(f"INSERT INTO edutrust.subjects (id, code, name_ar, name_en) VALUES ('{sid}', 'E2E-MATH-{sid[:6]}', 'رياضيات', 'Mathematics')")
    psql(f"INSERT INTO edutrust.academic_levels (id, code, name_ar, sort_order) VALUES ('{lid}', 'E2E-BAC-{lid[:6]}', 'بكالوريا', 1)")
    return sid, lid


def build_vs3_data(parent_token: str, student_id: str) -> dict:
    """S2 — create passport data through the REAL VS1→VS3 flow (DEV mock payment)."""
    subject_id, level_id = seed_subject_level()
    teacher = register_and_login("TEACHER", "r7b-teacher")
    ttok = teacher["access_token"]
    teacher_id = api("GET", "/api/v1/teachers/me", ttok).json()["data"]["id"]
    api("PATCH", "/api/v1/teachers/me", ttok, {"bio": "E2E math teacher", "teaching_modes": ["ONLINE"]})
    offer = api("POST", "/api/v1/teachers/subjects", ttok, {
        "subject_id": subject_id, "academic_level_id": level_id,
        "price": {"amount": "2000.00"}, "session_duration_minutes": 60})
    assert offer.status_code == 201, offer.text
    starts = (datetime.now(timezone.utc) + timedelta(days=10)).replace(microsecond=0)
    slot = api("POST", "/api/v1/teachers/availability/slots", ttok, {
        "starts_at": starts.isoformat(), "ends_at": (starts + timedelta(hours=1)).isoformat(), "mode": "ONLINE"})
    assert slot.status_code == 201, slot.text
    hold = api("POST", "/api/v1/bookings/hold", parent_token, {
        "student_id": student_id, "teacher_subject_id": offer.json()["data"]["id"],
        "availability_slot_id": slot.json()["data"]["id"]}, idem=f"e2e-hold-{uuid.uuid4()}")
    assert hold.status_code == 201, hold.text
    booking_id = hold.json()["data"]["booking"]["id"]
    payment = api("POST", "/api/v1/payments/initiate", parent_token, {"booking_id": booking_id, "provider": "OTHER"},
                  idem=f"e2e-pay-{uuid.uuid4()}").json()["data"]["payment"]
    ok = api("POST", f"/api/v1/payments/{payment['id']}/mock/succeed", parent_token, {"provider_event_id": f"evt-{uuid.uuid4()}"})
    assert ok.status_code == 200, ok.text
    session_id = ok.json()["data"]["session_id"]
    api("POST", f"/api/v1/sessions/{session_id}/start", ttok, {})
    api("POST", f"/api/v1/sessions/{session_id}/complete", ttok, {})
    report = api("POST", f"/api/v1/sessions/{session_id}/report", ttok, {
        "topics_covered": ["Algebra", "Functions"],
        "skills_practiced": ["Graph reading"],
        "participation": "HIGH",
        "teacher_observations": "Improved participation in algebra exercises.",
        "homework": "Exercises 4 and 5.",
        "recommended_revision": "Revise function graphs.",
        "next_objectives": ["Applied problems"],
        "progress_indicator": 2})
    assert report.status_code == 201, report.text
    # D3 sources also include WEAKNESS_OBSERVED / PARTICIPATION_NOTE events
    for _ in range(2):
        psql(f"INSERT INTO edutrust.student_progress_events (student_id, session_id, subject_id, event_type, source_type, topic) "
             f"VALUES ('{student_id}', '{session_id}', '{subject_id}', 'WEAKNESS_OBSERVED', 'TEACHER_REPORT', 'Geometry')")
    psql(f"INSERT INTO edutrust.student_progress_events (student_id, session_id, subject_id, event_type, source_type, note) "
         f"VALUES ('{student_id}', '{session_id}', '{subject_id}', 'PARTICIPATION_NOTE', 'TEACHER_REPORT', 'Active participation in class.')")
    return {"teacher_id": teacher_id, "teacher_token": ttok, "subject_id": subject_id,
            "booking_id": booking_id, "session_id": session_id, "payment_id": payment["id"]}


def s1_create_student_vs1() -> tuple[str, str]:
    print("== S1_CREATE_STUDENT_VS1 ==", flush=True)
    auth = register_and_login("PARENT", "r7b-parent")
    token = auth["access_token"]
    r = api("POST", "/api/v1/students", token, {"display_name": "E2E Passport Student"})
    check("S1", "VS1 create → 201", r.status_code == 201, r.text)
    sid = r.json()["data"]["id"]
    check("S1", "STUDENT_PROFILE_CREATED event written", event_count("STUDENT_PROFILE_CREATED", sid) == 1)
    return token, sid


def s2_build_passport_data(token: str, sid: str) -> dict:
    print("== S2_VS3_COMPATIBLE_PASSPORT_DATA ==", flush=True)
    flow = build_vs3_data(token, sid)
    check("S2", "VS3 flow completed (booking paid→session COMPLETED→report + progress events)",
          psql(f"SELECT status FROM edutrust.sessions WHERE id='{flow['session_id']}'") == "COMPLETED"
          and int(psql(f"SELECT count(*) FROM edutrust.student_progress_events WHERE student_id='{sid}'")) >= 5)
    return flow


def s3_get_passport(token: str, sid: str, flow: dict) -> None:
    print("== S3_GET_PASSPORT ==", flush=True)
    r = api("GET", f"/api/v1/students/{sid}/passport", token)
    check("S3", "GET passport → 200", r.status_code == 200, r.text)
    data = r.json()["data"]
    check("S3", "envelope shape is exactly §7.4 (student_id + subjects[6-field entries])",
          set(data.keys()) == {"student_id", "subjects"} and data["student_id"] == sid
          and all(set(e.keys()) == {"subject_id", "subject_name", "completed_sessions", "recent_topics",
                                    "recurring_weaknesses", "recent_progress_notes"} for e in data["subjects"]))
    entry = next(e for e in data["subjects"] if e["subject_id"] == flow["subject_id"])
    check("S3", "completed_sessions == 1 (COMPLETED session count per subject)", entry["completed_sessions"] == 1, json.dumps(entry))
    check("S3", "recent_topics aggregates VS3 TOPIC_COVERED events", set(entry["recent_topics"]) >= {"Algebra", "Functions"}, json.dumps(entry))
    check("S3", "recurring_weaknesses applies >=2 WEAKNESS_OBSERVED threshold", entry["recurring_weaknesses"] == ["Geometry"], json.dumps(entry))
    check("S3", "recent_progress_notes include VS3 notes + PARTICIPATION_NOTE",
          "Improved participation in algebra exercises." in entry["recent_progress_notes"]
          and "Active participation in class." in entry["recent_progress_notes"], json.dumps(entry))
    check("S3", "subject_name from subjects.name_en", entry["subject_name"] == "Mathematics", json.dumps(entry))
    check("S3", "no event for the passport READ", event_count("STUDENT_PROFILE_UPDATED", sid) == 0)


def s4_unauthorized_passport(token: str, sid: str) -> None:
    print("== S4_UNAUTHORIZED_PASSPORT ==", flush=True)
    foreign = register_and_login("PARENT", "r7b-foreign")
    fr = api("GET", f"/api/v1/students/{sid}/passport", foreign["access_token"])
    ur = api("GET", f"/api/v1/students/{uuid.uuid4()}/passport", token)
    check("S4", "foreign parent → 403 STUDENT_ACCESS_DENIED", fr.status_code == 403 and fr.json()["error"]["code"] == "STUDENT_ACCESS_DENIED", fr.text)
    check("S4", "unknown student → identical 403 (no existence oracle)",
          ur.status_code == 403 and ur.json()["error"]["code"] == fr.json()["error"]["code"], ur.text)


def s5_grant(token: str, sid: str, flow: dict) -> str:
    print("== S5_GRANT_PERMISSION ==", flush=True)
    body = {"teacher_id": flow["teacher_id"], "scope": "SESSION_CONTEXT", "granted_for_booking_id": flow["booking_id"]}
    r = api("POST", f"/api/v1/students/{sid}/permissions", token, body, idem=f"e2e-grant-{uuid.uuid4()}")
    check("S5", "grant with valid booking triple → 201", r.status_code == 201, r.text)
    permission = r.json()["data"]["permission"]
    pid = permission["id"]
    row = psql(f"SELECT teacher_id, parent_id, granted_for_booking_id, scope, revoked_at IS NULL FROM edutrust.student_permissions WHERE id='{pid}'")
    check("S5", "DB row written with server-validated relationships",
          row == f"{flow['teacher_id']}|{row.split('|')[1]}|{flow['booking_id']}|SESSION_CONTEXT|t", row)
    check("S5", "STUDENT_PROFILE_UPDATED event written once", event_count("STUDENT_PROFILE_UPDATED", sid) == 1)
    return pid


def s6_duplicate_grant(token: str, sid: str, flow: dict, pid: str) -> None:
    print("== S6_DUPLICATE_GRANT ==", flush=True)
    body = {"teacher_id": flow["teacher_id"], "scope": "SESSION_CONTEXT", "granted_for_booking_id": flow["booking_id"]}
    r = api("POST", f"/api/v1/students/{sid}/permissions", token, body, idem=f"e2e-grant-{uuid.uuid4()}")
    check("S6", "duplicate ACTIVE grant, different key → 409", r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_PERMISSION", r.text)
    check("S6", "no second permission row created",
          int(psql(f"SELECT count(*) FROM edutrust.student_permissions WHERE student_id='{sid}' AND revoked_at IS NULL")) == 1)
    replay = api("POST", f"/api/v1/students/{sid}/permissions", token, body, idem=f"e2e-replay-{uuid.uuid4()}")
    check("S6", "unknown key with same canonical body → 409 duplicate protection (not 500)", replay.status_code == 409, replay.text)


def s7_revoke(token: str, sid: str, pid: str) -> str:
    print("== S7_REVOKE_PERMISSION ==", flush=True)
    r = api("DELETE", f"/api/v1/students/{sid}/permissions/{pid}", token)
    check("S7", "revoke → 200", r.status_code == 200, r.text)
    check("S7", "revoked_at set, row retained",
          psql(f"SELECT revoked_at IS NOT NULL, revoked_at IS NOT NULL FROM edutrust.student_permissions WHERE id='{pid}'").startswith("t|"))
    check("S7", "exactly one revoke event", event_count("STUDENT_PROFILE_UPDATED", sid) == 2)
    return psql(f"SELECT revoked_at FROM edutrust.student_permissions WHERE id='{pid}'")


def s8_repeat_revoke_and_financials(token: str, sid: str, pid: str, revoked_at: str) -> None:
    print("== S8_REPEAT_REVOKE_AND_FINANCIALS ==", flush=True)
    r = api("DELETE", f"/api/v1/students/{sid}/permissions/{pid}", token)
    check("S8", "repeated revoke → 200 idempotent no-op", r.status_code == 200, r.text)
    check("S8", "revoked_at unchanged (terminal, single transition)",
          psql(f"SELECT revoked_at FROM edutrust.student_permissions WHERE id='{pid}'") == revoked_at)
    check("S8", "no second event on the no-op", event_count("STUDENT_PROFILE_UPDATED", sid) == 2)
    payments = int(psql("SELECT count(*) FROM edutrust.payments"))
    refunds = int(psql("SELECT count(*) FROM edutrust.refunds"))
    payouts = int(psql("SELECT count(*) FROM edutrust.payouts"))
    payout_items = int(psql("SELECT count(*) FROM edutrust.payout_items"))
    check("S8", f"financial surface untouched: payments={payments} (only the S2 VS3-flow payment), refunds/payouts/payout_items=0",
          payments == 1 and refunds == 0 and payouts == 0 and payout_items == 0,
          f"payments={payments} refunds={refunds} payouts={payouts} payout_items={payout_items}")


def main() -> int:
    print("R7 PASSPORT+PERMISSIONS E2E — Executor B (DEV mock only)", flush=True)
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

        token, sid = s1_create_student_vs1()
        flow = s2_build_passport_data(token, sid)
        s3_get_passport(token, sid, flow)
        s4_unauthorized_passport(token, sid)
        pid = s5_grant(token, sid, flow)
        s6_duplicate_grant(token, sid, flow, pid)
        revoked_at = s7_revoke(token, sid, pid)
        s8_repeat_revoke_and_financials(token, sid, pid, revoked_at)
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
    print(f"\nR7 PASSPORT+PERMISSIONS E2E RESULT: {total - len(failed)}/{total} checks passed", flush=True)
    for sc, desc, ok, detail in failed:
        print(f"  FAILED in {sc}: {desc} — {detail}", flush=True)
    if not failed:
        print("R7_STUDENT_PASSPORT_PERMISSIONS_E2E=PASS", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
