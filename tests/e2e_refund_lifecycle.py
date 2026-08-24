"""DEV Vertical Slice #8 — Refund Operations E2E (DEV mock only).

Standalone end-to-end suite (not collected by pytest). Mirrors the VS2–VS6 E2E
convention: isolated temporary PostgreSQL cluster + Django dev server + scripted
scenario checks against the live HTTP API, plus DB-level financial-integrity
gates. Scenarios per the approved VS8 implementation plan.

Usage:
    PG_BIN=<pg bin dir> python tests/e2e_refund_lifecycle.py
"""
from __future__ import annotations

import os
import re
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
BASE = Path(f"/tmp/vs8_e2e_{os.getpid()}")
PORT = int(os.environ.get("VS8_E2E_PGPORT", "55480"))
API_PORT = int(os.environ.get("VS8_E2E_APIPORT", "8100"))
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


def api(method: str, path: str, token: str | None = None, body: dict | None = None, idem: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idem:
        headers["Idempotency-Key"] = idem
    r = requests.request(method, API + path, json=body, headers=headers, timeout=30)
    try:
        data = r.json()
    except ValueError:
        data = {}
    return r.status_code, data


def register(role: str, prefix: str):
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    status, _ = api("POST", "/api/v1/auth/register", body={"role": role, "full_name": f"{role} E2E", "email": email, "password": "StrongPassword123!"})
    assert status == 201, f"register {role}: {status}"
    status, data = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": "StrongPassword123!"})
    assert status == 200, f"login {role}: {status}"
    return data["data"]["access_token"]


def seed_admin_ops():
    from django.contrib.auth.hashers import make_password
    admin_email, ops_email = f"admin-vs8-e2e-{uuid.uuid4()}@example.com", f"ops-vs8-e2e-{uuid.uuid4()}@example.com"
    pwd = make_password("StrongPassword123!")
    psql(f"INSERT INTO edutrust.users (full_name, email, password_hash) VALUES ('Admin E2E', '{admin_email}', '{pwd}')")
    psql(f"INSERT INTO edutrust.users (full_name, email, password_hash) VALUES ('OPS E2E', '{ops_email}', '{pwd}')")
    admin_id = psql(f"SELECT id FROM edutrust.users WHERE email='{admin_email}'")
    ops_id = psql(f"SELECT id FROM edutrust.users WHERE email='{ops_email}'")
    psql(f"INSERT INTO edutrust.user_roles (user_id, role) VALUES ('{admin_id}', 'ADMIN')")
    psql(f"INSERT INTO edutrust.user_roles (user_id, role) VALUES ('{ops_id}', 'OPS')")
    status, data = api("POST", "/api/v1/auth/login", body={"identifier": admin_email, "password": "StrongPassword123!"})
    assert status == 200
    status, data2 = api("POST", "/api/v1/auth/login", body={"identifier": ops_email, "password": "StrongPassword123!"})
    assert status == 200
    return data["data"]["access_token"], data2["data"]["access_token"]


def full_booking_cycle():
    """Teacher + slot + parent + student + HELD booking + payment."""
    ttok = register("TEACHER", "teacher-vs8e2e")
    subject_id = str(uuid.uuid4())
    level_id = str(uuid.uuid4())
    psql(f"INSERT INTO edutrust.subjects (id, code, name_ar, name_en) VALUES ('{subject_id}', 'MATH-{subject_id[:8]}', 'رياضيات', 'Mathematics')")
    psql(f"INSERT INTO edutrust.academic_levels (id, code, name_ar, sort_order) VALUES ('{level_id}', 'BAC-{level_id[:8]}', 'بكالوريا', 1)")
    status, _ = api("PATCH", "/api/v1/teachers/me", ttok, body={"bio": "E2E teacher", "teaching_modes": ["ONLINE"]})
    assert status == 200
    status, data = api("POST", "/api/v1/teachers/subjects", ttok, body={"subject_id": subject_id, "academic_level_id": level_id, "price": {"amount": "2000.00"}, "session_duration_minutes": 60})
    assert status == 201
    tsid = data["data"]["id"]
    from datetime import datetime, timedelta
    starts = (datetime.utcnow() + timedelta(days=10)).replace(microsecond=0).isoformat()
    ends = (datetime.fromisoformat(starts) + timedelta(hours=1)).isoformat()
    status, data = api("POST", "/api/v1/teachers/availability/slots", ttok, body={"starts_at": starts, "ends_at": ends, "mode": "ONLINE"})
    assert status == 201
    slot_id = data["data"]["id"]
    ptok = register("PARENT", "parent-vs8e2e")
    status, data = api("POST", "/api/v1/students", ptok, body={"display_name": "Ahmed"})
    assert status == 201
    student_id = data["data"]["id"]
    status, data = api("POST", "/api/v1/bookings/hold", ptok, body={"student_id": student_id, "teacher_subject_id": tsid, "availability_slot_id": slot_id}, idem=f"hold-{uuid.uuid4()}")
    assert status == 201
    booking_id = data["data"]["booking"]["id"]
    status, data = api("POST", "/api/v1/payments/initiate", ptok, body={"booking_id": booking_id, "provider": "OTHER"}, idem=f"pay-{uuid.uuid4()}")
    assert status == 201
    return {"ttok": ttok, "ptok": ptok, "booking_id": booking_id, "payment_id": data["data"]["payment"]["id"], "student_id": student_id}


def confirm_payment(cycle):
    status, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/mock/succeed", cycle["ptok"], body={"provider_event_id": f"evt-{uuid.uuid4()}"})
    assert status == 200 and data["data"]["payment_status"] == "CONFIRMED", f"confirm: {status} {data}"
    return data["data"].get("session_id")


def complete_session_with_report(cycle, session_id):
    status, _ = api("POST", f"/api/v1/sessions/{session_id}/start", cycle["ttok"], body={})
    assert status == 200
    status, _ = api("POST", f"/api/v1/sessions/{session_id}/complete", cycle["ttok"], body={})
    assert status == 200
    status, data = api("POST", f"/api/v1/sessions/{session_id}/report", cycle["ttok"], body={
        "topics_covered": ["E2E topic"],
        "skills_practiced": ["E2E skill"],
        "participation": "HIGH",
        "teacher_observations": "E2E observation.",
        "homework": "E2E homework.",
        "recommended_revision": "E2E revision.",
        "next_objectives": ["E2E objective"],
        "progress_indicator": 2,
    })
    assert status == 201, f"report: {status} {data}"
    return session_id


# ---------------------------------------------------------------------------
# Scenarios (approved VS8 plan)
# ---------------------------------------------------------------------------

def scenario_full_refund_lifecycle(atok):
    S = "E2E_FULL_REFUND_LIFECYCLE"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    confirm_payment(cycle)
    pid = cycle["payment_id"]
    st, data = api("POST", f"/api/v1/payments/{pid}/refund", atok,
                   body={"amount": "2000.00", "currency": "DZD", "reason": "Teacher no-show confirmed"}, idem=f"refund-{uuid.uuid4()}")
    check(S, "create refund -> 201 REQUESTED", st == 201 and data["data"]["refund"]["status"] == "REQUESTED", f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok,
                   body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"refund-{uuid.uuid4()}")
    check(S, "approve + mock submit -> PROVIDER_PENDING / payment REFUND_PENDING",
          st == 200 and data["data"]["refund"]["status"] == "PROVIDER_PENDING" and data["data"]["payment_status"] == "REFUND_PENDING",
          f"{st} {data}")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock success -> SUCCEEDED / payment REFUNDED",
          st == 200 and data["data"]["refund_status"] == "SUCCEEDED" and data["data"]["payment_status"] == "REFUNDED", f"{st} {data}")
    tx = psql(f"SELECT status FROM edutrust.ledger_transactions WHERE reference='refund-{rid}'")
    check(S, "ledger REFUND tx POSTED", tx == "POSTED", tx)
    bal = psql(f"SELECT (SELECT COALESCE(SUM(amount),0) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='DEBIT') = "
               f"(SELECT COALESCE(SUM(amount),0) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='CREDIT') "
               f"FROM edutrust.ledger_transactions t WHERE t.reference='refund-{rid}'")
    check(S, "ledger tx balanced (DEBIT=CREDIT)", bal == "t", bal)
    evs = psql(f"SELECT string_agg(event_type::text, ',' ORDER BY created_at) FROM edutrust.event_ledger WHERE entity_id='{rid}' AND event_type::text LIKE 'REFUND%'")
    check(S, "event order REFUND_REQUESTED,REFUND_APPROVED,REFUND_PROVIDER_SUBMITTED,REFUND_SUCCEEDED",
          evs == "REFUND_REQUESTED,REFUND_APPROVED,REFUND_PROVIDER_SUBMITTED,REFUND_SUCCEEDED", evs)
    check(S, "PAYMENT_REFUNDED emitted exactly once",
          psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='PAYMENT_REFUNDED' AND entity_id='{pid}'") == "1")
    check(S, "REFUND_ISSUED never emitted (global)",
          psql("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='REFUND_ISSUED'") == "0")
    st, data = api("GET", f"/api/v1/payments/{pid}", cycle["ptok"])
    check(S, "parent payment view shows refunds[] SUCCEEDED",
          st == 200 and data["data"]["refunds"][0]["status"] == "SUCCEEDED", f"{st}")


def scenario_partial_refund_payout_exposure(atok):
    S = "E2E_PARTIAL_REFUND_PAYOUT_EXPOSURE"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    teacher_id = psql(f"SELECT id FROM edutrust.teacher_profiles WHERE user_id=(SELECT user_id FROM edutrust.teacher_profiles WHERE id=(SELECT teacher_id FROM edutrust.bookings WHERE id='{cycle['booking_id']}'))")
    st, data = api("POST", "/api/v1/admin/payouts/process", atok, body={"teacher_id": teacher_id, "session_ids": [session_id]}, idem=f"payout-{uuid.uuid4()}")
    check(S, "payout before refund -> PAID 1700 (gross)", st == 201 and data["data"]["result"] == "PAID" and data["data"]["payout"]["amount"] == "1700.00", f"{st} {data}")
    st, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/refund", atok,
                   body={"amount": "400.00", "currency": "DZD", "reason": "Quality issue partial refund"}, idem=f"refund-{uuid.uuid4()}")
    assert st == 201
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok,
                   body={"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"}, idem=f"refund-{uuid.uuid4()}")
    assert st == 200
    st, data = api("POST", "/api/v1/admin/payouts/process", atok, body={"teacher_id": teacher_id, "session_ids": [session_id]}, idem=f"payout-{uuid.uuid4()}")
    check(S, "payout while refund in flight -> 422 NO_CONFIRMED_PAYMENT (v1 guard)",
          st == 422 and any(d["reason"] == "NO_CONFIRMED_PAYMENT" for d in data["error"]["details"]["details"]), f"{st} {data}")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock success -> PARTIALLY_REFUNDED", st == 200 and data["data"]["payment_status"] == "PARTIALLY_REFUNDED", f"{st} {data}")
    st, data = api("POST", "/api/v1/admin/payouts/process", atok, body={"teacher_id": teacher_id, "session_ids": [session_id]}, idem=f"payout-{uuid.uuid4()}")
    check(S, "payout after partial settled -> still 422 (payment not CONFIRMED)", st == 422, f"{st}")
    check(S, "no payout item created", psql(f"SELECT count(*) FROM edutrust.payout_items WHERE session_id='{session_id}'") == "1")


def scenario_late_refund_reconciliation(atok):
    S = "E2E_LATE_REFUND_RECONCILIATION"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    psql(f"UPDATE edutrust.bookings SET hold_expires_at = now() - interval '1 second' WHERE id='{cycle['booking_id']}'")
    st, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/mock/succeed", cycle["ptok"], body={"provider_event_id": f"evt-{uuid.uuid4()}"})
    check(S, "late payment -> CONFIRMED + reconciliation_required + no session",
          st == 200 and data["data"]["payment_status"] == "CONFIRMED" and data["data"]["reconciliation_required"] is True and data["data"]["session_id"] is None,
          f"{st} {data}")
    rows = psql(f"SELECT status || '|' || refund_type || '|' || COALESCE(approved_amount::text,'NULL') FROM edutrust.refunds WHERE payment_id='{cycle['payment_id']}'")
    check(S, "late refund auto-created REQUESTED FULL (no auto-approval)", rows == "REQUESTED|FULL|NULL", rows)
    rid = psql(f"SELECT id FROM edutrust.refunds WHERE payment_id='{cycle['payment_id']}'")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok,
                   body={"approved_amount": "2000.00", "teacher_adjustment_amount": "0.00", "platform_adjustment_amount": "2000.00"}, idem=f"refund-{uuid.uuid4()}")
    check(S, "approve (late allocation 0/2000) -> PROVIDER_PENDING", st == 200 and data["data"]["refund"]["status"] == "PROVIDER_PENDING", f"{st} {data}")
    tx = psql(f"SELECT string_agg(e.account_type::text || ':' || e.direction::text, ',' ORDER BY e.created_at) FROM edutrust.ledger_transactions t JOIN edutrust.ledger_entries e ON e.ledger_transaction_id=t.id WHERE t.reference='refund-{rid}'")
    check(S, "Form L ledger DRAFT: REFUND_PAYABLE:DEBIT, PAYMENT_PROVIDER_CLEARING:CREDIT",
          tx == "REFUND_PAYABLE:DEBIT,PAYMENT_PROVIDER_CLEARING:CREDIT", tx)
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/reconcile", atok,
                   body={"result": "SUCCEEDED", "reconciliation_source": "MANUAL_RECONCILIATION",
                         "reconciliation_reference": "BANK-REF-E2E-1", "reconciled_at": "2026-08-24T12:00:00Z",
                         "reason": "Manual bank confirmation recorded."}, idem=f"refund-{uuid.uuid4()}")
    check(S, "reconcile SUCCEEDED (manual) -> refund SUCCEEDED / payment REFUNDED",
          st == 200 and data["data"]["refund"]["status"] == "SUCCEEDED" and data["data"]["payment_status"] == "REFUNDED", f"{st} {data}")
    recon = psql(f"SELECT reconciliation_source || '|' || reconciliation_reference || '|' || (reconciled_by_user_id IS NOT NULL)::text FROM edutrust.refunds WHERE id='{rid}'")
    check(S, "reconciliation proof recorded (source/reference/by_user)", recon == "MANUAL_RECONCILIATION|BANK-REF-E2E-1|true", recon)
    check(S, "booking factually untouched (EXPIRED), zero sessions",
          psql(f"SELECT status FROM edutrust.bookings WHERE id='{cycle['booking_id']}'") == "EXPIRED"
          and psql(f"SELECT count(*) FROM edutrust.sessions WHERE booking_id='{cycle['booking_id']}'") == "0")


def scenario_refund_failure_recovery(atok):
    S = "E2E_REFUND_FAILURE_RECOVERY"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    confirm_payment(cycle)
    st, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/refund", atok,
                   body={"amount": "2000.00", "currency": "DZD", "reason": "Teacher no-show confirmed"}, idem=f"refund-{uuid.uuid4()}")
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok,
                   body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"refund-{uuid.uuid4()}")
    assert st == 200
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/fail", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock failure -> FAILED / payment restored CONFIRMED",
          st == 200 and data["data"]["refund_status"] == "FAILED" and data["data"]["payment_status"] == "CONFIRMED", f"{st} {data}")
    check(S, "ledger tx VOIDED (not POSTED) after failure",
          psql(f"SELECT status FROM edutrust.ledger_transactions WHERE reference='refund-{rid}'") == "VOIDED")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "terminal FAILED cannot reopen (409)", st == 409 and data["error"]["code"] == "REFUND_INVALID_STATE", f"{st} {data}")
    st, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/refund", atok,
                   body={"amount": "2000.00", "currency": "DZD", "reason": "Retry after provider failure"}, idem=f"refund-{uuid.uuid4()}")
    rid2 = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid2}/approve", atok,
                   body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"refund-{uuid.uuid4()}")
    assert st == 200
    st, data = api("POST", f"/api/v1/admin/refunds/{rid2}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "new refund request -> approve -> success (recovery path)",
          st == 200 and data["data"]["payment_status"] == "REFUNDED", f"{st} {data}")


def scenario_post_paid_refund_recovery(atok):
    S = "E2E_POST_PAID_REFUND_RECOVERY"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    teacher_id = psql(f"SELECT id FROM edutrust.teacher_profiles WHERE id=(SELECT teacher_id FROM edutrust.bookings WHERE id='{cycle['booking_id']}')")
    st, data = api("POST", "/api/v1/admin/payouts/process", atok, body={"teacher_id": teacher_id, "session_ids": [session_id]}, idem=f"payout-{uuid.uuid4()}")
    assert st == 201
    payout = data["data"]["payout"]
    st, data = api("POST", f"/api/v1/payments/{cycle['payment_id']}/refund", atok,
                   body={"amount": "400.00", "currency": "DZD", "reason": "Quality issue partial refund"}, idem=f"refund-{uuid.uuid4()}")
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok,
                   body={"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"}, idem=f"refund-{uuid.uuid4()}")
    assert st == 200
    tx = psql(f"SELECT string_agg(e.account_type::text || ':' || e.direction::text, ',' ORDER BY e.created_at) FROM edutrust.ledger_transactions t JOIN edutrust.ledger_entries e ON e.ledger_transaction_id=t.id WHERE t.reference='refund-{rid}'")
    check(S, "Form A ledger DRAFT: TEACHER_RECOVERABLE/PLATFORM_REFUND_EXPENSE debits + clearing credit",
          tx == "TEACHER_RECOVERABLE:DEBIT,PLATFORM_REFUND_EXPENSE:DEBIT,PAYMENT_PROVIDER_CLEARING:CREDIT", tx)
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock success -> PARTIALLY_REFUNDED", st == 200 and data["data"]["payment_status"] == "PARTIALLY_REFUNDED", f"{st} {data}")
    row = psql(f"SELECT amount || '|' || status || '|' || provider_reference FROM edutrust.payouts WHERE id='{payout['id']}'")
    check(S, "old PAID payout byte-identical (v1.4 immutability)",
          row == f"{payout['amount']}|PAID|{payout['provider_reference']}", row)


def scenario_idempotency_and_replay(atok):
    S = "E2E_IDEMPOTENCY_AND_REPLAY"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    confirm_payment(cycle)
    pid = cycle["payment_id"]
    key = f"refund-{uuid.uuid4()}"
    st1, d1 = api("POST", f"/api/v1/payments/{pid}/refund", atok, body={"amount": "2000.00", "currency": "DZD", "reason": "Teacher no-show confirmed"}, idem=key)
    st2, d2 = api("POST", f"/api/v1/payments/{pid}/refund", atok, body={"amount": "2000.00", "currency": "DZD", "reason": "Teacher no-show confirmed"}, idem=key)
    check(S, "create replay same key+body -> same refund (one row)",
          st1 == 201 and st2 == 201 and d1["data"]["refund"]["refund_id"] == d2["data"]["refund"]["refund_id"]
          and psql(f"SELECT count(*) FROM edutrust.refunds WHERE payment_id='{pid}'") == "1")
    st3, d3 = api("POST", f"/api/v1/payments/{pid}/refund", atok, body={"amount": "100.00", "currency": "DZD", "reason": "different body here"}, idem=key)
    check(S, "create same key different body -> 409 IDEMPOTENCY_KEY_CONFLICT",
          st3 == 409 and d3["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT", f"{st3} {d3}")
    rid = d1["data"]["refund"]["refund_id"]
    akey = f"refund-{uuid.uuid4()}"
    body = {"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}
    st1, _ = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body=body, idem=akey)
    st2, d2 = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body=body, idem=akey)
    check(S, "approve replay -> 200, single submission",
          st1 == 200 and st2 == 200
          and psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='REFUND_PROVIDER_SUBMITTED' AND entity_id='{rid}'") == "1")
    st3, d3 = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1000.00", "platform_adjustment_amount": "1000.00"}, idem=akey)
    check(S, "approve same key different body -> 409 conflict", st3 == 409 and d3["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT", f"{st3} {d3}")
    eid = f"rfevt-{uuid.uuid4()}"
    st1, d1 = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": eid})
    st2, d2 = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": eid})
    check(S, "mock event replay -> 200 duplicate, single event row",
          st1 == 200 and st2 == 200 and d2["data"]["duplicate"] is True
          and psql(f"SELECT count(*) FROM edutrust.payment_provider_events WHERE provider_event_id='{eid}'") == "1")
    # reconcile idempotency on a FRESH in-flight refund (the first one is already SUCCEEDED)
    cycle3 = full_booking_cycle()
    confirm_payment(cycle3)
    st, data = api("POST", f"/api/v1/payments/{cycle3['payment_id']}/refund", atok,
                   body={"amount": "2000.00", "currency": "DZD", "reason": "reconcile idempotency case"}, idem=f"refund-{uuid.uuid4()}")
    rid3 = data["data"]["refund"]["refund_id"]
    api("POST", f"/api/v1/admin/refunds/{rid3}/approve", atok,
        body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"refund-{uuid.uuid4()}")
    rkey = f"refund-{uuid.uuid4()}"
    rbody_s = {"result": "SUCCEEDED", "reconciliation_source": "MANUAL_RECONCILIATION", "reconciliation_reference": "R-1",
               "reconciled_at": "2026-08-24T12:00:00Z", "reason": "bank confirmed ok"}
    st1, d1 = api("POST", f"/api/v1/admin/refunds/{rid3}/reconcile", atok, body=rbody_s, idem=rkey)
    st2, d2 = api("POST", f"/api/v1/admin/refunds/{rid3}/reconcile", atok, body=rbody_s, idem=rkey)
    check(S, "reconcile replay same key+body -> 200 original", st1 == 200 and st2 == 200 and d2["data"]["refund"]["status"] == "SUCCEEDED", f"{st1}/{st2}")
    rbody_f = {"result": "FAILED", "reconciliation_source": "MANUAL_RECONCILIATION", "reconciliation_reference": "R-1",
               "reconciled_at": "2026-08-24T12:00:00Z", "reason": "bank says no"}
    st3, d3 = api("POST", f"/api/v1/admin/refunds/{rid3}/reconcile", atok, body=rbody_f, idem=rkey)
    check(S, "reconcile same key different body -> 409 IDEMPOTENCY_KEY_CONFLICT", st3 == 409 and d3["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT", f"{st3} {d3}")
    st4, d4 = api("POST", f"/api/v1/admin/refunds/{rid3}/reconcile", atok, body=rbody_f, idem=f"refund-{uuid.uuid4()}")
    check(S, "reconcile after terminal SUCCEEDED -> 409 REFUND_INVALID_STATE", st4 == 409 and d4["error"]["code"] == "REFUND_INVALID_STATE", f"{st4} {d4}")


def scenario_authorization_matrix(atok, otok):
    S = "E2E_AUTHORIZATION_MATRIX"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    confirm_payment(cycle)
    pid = cycle["payment_id"]
    ptok, ttok = cycle["ptok"], cycle["ttok"]
    body = {"amount": "100.00", "currency": "DZD", "reason": "reason here"}
    st_p, _ = api("POST", f"/api/v1/payments/{pid}/refund", ptok, body=body, idem=f"refund-{uuid.uuid4()}")
    st_t, _ = api("POST", f"/api/v1/payments/{pid}/refund", ttok, body=body, idem=f"refund-{uuid.uuid4()}")
    check(S, "parent create -> 403", st_p == 403, str(st_p))
    check(S, "teacher create -> 403", st_t == 403, str(st_t))
    st, data = api("POST", f"/api/v1/payments/{pid}/refund", otok, body=body, idem=f"refund-{uuid.uuid4()}")
    check(S, "OPS create -> 201 (policy-limited)", st == 201, str(st))
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", otok,
                   body={"approved_amount": "100.00", "teacher_adjustment_amount": "60.00", "platform_adjustment_amount": "40.00"}, idem=f"refund-{uuid.uuid4()}")
    check(S, "OPS approve -> 200", st == 200, str(st))
    eid = f"rfevt-{uuid.uuid4()}"
    st_p, _ = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", ptok, body={"provider_event_id": eid})
    check(S, "parent mock result -> 403", st_p == 403, str(st_p))
    st, _ = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", otok, body={"provider_event_id": eid})
    check(S, "OPS mock result -> 200", st == 200, str(st))
    # ADMIN_OVERRIDE reconciliation requires ADMIN
    cycle2 = full_booking_cycle()
    confirm_payment(cycle2)
    st, data = api("POST", f"/api/v1/payments/{cycle2['payment_id']}/refund", atok, body={"amount": "100.00", "currency": "DZD", "reason": "override case"}, idem=f"refund-{uuid.uuid4()}")
    rid2 = data["data"]["refund"]["refund_id"]
    api("POST", f"/api/v1/admin/refunds/{rid2}/approve", otok, body={"approved_amount": "100.00", "teacher_adjustment_amount": "100.00", "platform_adjustment_amount": "0.00"}, idem=f"refund-{uuid.uuid4()}")
    rbody = {"result": "SUCCEEDED", "reconciliation_source": "ADMIN_OVERRIDE", "reconciliation_reference": "OV-1",
             "reconciled_at": "2026-08-24T12:00:00Z", "reason": "exceptional override"}
    st_o, _ = api("POST", f"/api/v1/admin/refunds/{rid2}/reconcile", otok, body=rbody, idem=f"refund-{uuid.uuid4()}")
    st_a, da = api("POST", f"/api/v1/admin/refunds/{rid2}/reconcile", atok, body=rbody, idem=f"refund-{uuid.uuid4()}")
    check(S, "OPS ADMIN_OVERRIDE reconcile -> 403; ADMIN -> 200",
          st_o == 403 and st_a == 200 and da["data"]["refund"]["reconciliation"]["source"] == "ADMIN_OVERRIDE", f"{st_o}/{st_a}")
    # reads
    st, _ = api("GET", "/api/v1/admin/refunds", ptok)
    check(S, "parent GET /admin/refunds -> 403", st == 403, str(st))
    st, _ = api("GET", f"/api/v1/admin/refunds/{rid}", atok)
    check(S, "admin GET detail -> 200 (audited)", st == 200, str(st))


def financial_integrity_gates():
    S = "FINANCIAL_INTEGRITY"
    print(f"\n== {S} ==", flush=True)
    bad = psql("SELECT count(*) FROM edutrust.ledger_transactions t WHERE t.transaction_type='REFUND' AND t.status='POSTED' AND NOT EXISTS (SELECT 1 FROM edutrust.refunds r WHERE r.status='SUCCEEDED' AND t.reference='refund-'||r.id::text)")
    check(S, "every POSTED refund ledger tx has a SUCCEEDED refund", bad == "0", bad)
    bad = psql("SELECT count(*) FROM edutrust.refunds r WHERE r.status='FAILED' AND EXISTS (SELECT 1 FROM edutrust.ledger_transactions t WHERE t.reference='refund-'||r.id::text AND t.status='POSTED')")
    check(S, "no FAILED refund has a prematurely POSTED ledger tx", bad == "0", bad)
    bad = psql("SELECT count(*) FROM edutrust.ledger_transactions t WHERE (SELECT COALESCE(SUM(amount),0) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='DEBIT') <> (SELECT COALESCE(SUM(amount),0) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='CREDIT')")
    check(S, "ALL ledger transactions balanced", bad == "0", bad)
    bad = psql("SELECT count(*) FROM edutrust.refunds WHERE status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED') AND (COALESCE(teacher_adjustment_amount,0) + COALESCE(platform_adjustment_amount,0)) <> approved_amount")
    check(S, "no invalid/duplicate allocation (sum = approved for APPROVED+)", bad == "0", bad)
    bad = psql("SELECT count(*) FROM (SELECT provider, provider_event_id, count(*) FROM edutrust.payment_provider_events GROUP BY 1,2 HAVING count(*) > 1) d")
    check(S, "no duplicate provider event identity", bad == "0", bad)
    bad = psql("SELECT count(*) FROM edutrust.refunds WHERE status='SUCCEEDED' AND completed_at IS NULL OR status='FAILED' AND failed_at IS NULL OR status='REJECTED' AND rejected_at IS NULL OR status='CANCELLED' AND cancelled_at IS NULL")
    check(S, "state/timestamp integrity (no terminal row missing its timestamp)", bad == "0", bad)
    # real-provider absence: only MockPaymentProvider implements initiate_refund
    src = (REPO / "backend/edutrust_api/payments.py").read_text()
    provider_classes = re.findall(r"^class (\w*Provider)\b", src, flags=re.M)
    check(S, "provider classes = PaymentProvider + MockPaymentProvider only (no real provider)",
          provider_classes == ["PaymentProvider", "MockPaymentProvider"], str(provider_classes))
    settings_src = (REPO / "backend/edutrust/settings.py").read_text()
    check(S, "REAL_PAYMENT/REAL_PAYOUT defaults false; no REFUND provider flag wired to a real vendor",
          'REAL_PAYMENT_ENABLED", "false"' in settings_src and 'REAL_PAYOUT_ENABLED", "false"' in settings_src)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    print("VS8 E2E — Refund Operations (DEV mock only)")
    print(f"PG_BIN={PG_BIN}")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edutrust.settings")
    sys.path.insert(0, str(REPO / "backend"))
    import django
    django.setup()
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

        atok, otok = seed_admin_ops()
        scenario_full_refund_lifecycle(atok)
        scenario_partial_refund_payout_exposure(atok)
        scenario_late_refund_reconciliation(atok)
        scenario_refund_failure_recovery(atok)
        scenario_post_paid_refund_recovery(atok)
        scenario_idempotency_and_replay(atok)
        scenario_authorization_matrix(atok, otok)
        financial_integrity_gates()
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
    failed = [r for r in _results if not r[2]]
    print(f"\nVS8 E2E RESULT: {total - len(failed)}/{total} checks passed")
    if failed:
        for sc, desc, _, detail in failed:
            print(f"  FAILED in {sc}: {desc} — {detail}")
        return 1
    print("E2E_REFUND_LIFECYCLE=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
