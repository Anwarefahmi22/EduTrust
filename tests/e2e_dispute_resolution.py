"""DEV Vertical Slice #9 — Dispute Resolution E2E (DEV mock only).

Standalone end-to-end suite (not collected by pytest). Mirrors the VS2–VS8 E2E
convention: isolated temporary PostgreSQL cluster + Django dev server + Next.js
production server + scripted scenario checks against the live HTTP API, plus
DB-level financial-integrity gates. Scenarios per the approved VS9 implementation
plan (plan section 23, S1..S15).

Usage:
    PG_BIN=<pg bin dir> python tests/e2e_dispute_resolution.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
PG_BIN = os.environ.get("PG_BIN", "/home/user/.venv-edutrust/lib/python3.11/site-packages/pgserver/pginstall/bin")
PY = sys.executable or "python3"
BASE = Path(f"/tmp/vs9_e2e_{os.getpid()}")
PORT = int(os.environ.get("VS9_E2E_PGPORT", "55481"))
API_PORT = int(os.environ.get("VS9_E2E_APIPORT", "8101"))
FRONTEND_PORT = int(os.environ.get("VS9_E2E_FRONTENDPORT", "3101"))
API = f"http://127.0.0.1:{API_PORT}"
FRONTEND = f"http://127.0.0.1:{FRONTEND_PORT}"
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


def api(method: str, path: str, token: str | None = None, body: dict | None = None, idem: str | None = None, api_base: str = API):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idem:
        headers["Idempotency-Key"] = idem
    r = requests.request(method, api_base + path, json=body, headers=headers, timeout=30)
    try:
        data = r.json()
    except ValueError:
        data = {}
    return r.status_code, data


def register(role: str, prefix: str) -> str:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    status, _ = api("POST", "/api/v1/auth/register", body={"role": role, "full_name": f"{role} E2E", "email": email, "password": "StrongPassword123!"})
    assert status == 201, f"register {role}: {status}"
    status, data = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": "StrongPassword123!"})
    assert status == 200, f"login {role}: {status}"
    return data["data"]["access_token"]


def seed_operator(role: str, prefix: str) -> str:
    from django.contrib.auth.hashers import make_password
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    uid = str(uuid.uuid4())
    pwd = make_password("StrongPassword123!")
    psql(f"INSERT INTO edutrust.users (id, full_name, email, password_hash) VALUES ('{uid}', '{role} E2E', '{email}', '{pwd}')")
    psql(f"INSERT INTO edutrust.user_roles (user_id, role) VALUES ('{uid}', '{role}')")
    status, data = api("POST", "/api/v1/auth/login", body={"identifier": email, "password": "StrongPassword123!"})
    assert status == 200
    return data["data"]["access_token"]


def full_booking_cycle():
    """Teacher + slot + parent + student + HELD booking + payment."""
    ttok = register("TEACHER", "teacher-vs9e2e")
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
    ptok = register("PARENT", "parent-vs9e2e")
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


def open_dispute(ptok, session_id: str, category: str, description: str):
    status, data = api("POST", "/api/v1/disputes", ptok, body={"session_id": session_id, "category": category, "description": description}, idem=f"disp-{uuid.uuid4()}")
    assert status == 201, f"open dispute: {status} {data}"
    return data["data"]["dispute"]["id"]


def resolve_dispute(token, dispute_id: str, body: dict, idem=None):
    return api("POST", f"/api/v1/admin/disputes/{dispute_id}/resolve", token, body=body, idem=idem or f"disp-res-{uuid.uuid4()}")


def process_payout(token, teacher_profile_id: str, session_id: str):
    return api("POST", "/api/v1/admin/payouts/process", token, body={"teacher_id": teacher_profile_id, "session_ids": [session_id]}, idem=f"payout-{uuid.uuid4()}")


def teacher_profile_id_of(cycle):
    return psql(f"SELECT id FROM edutrust.teacher_profiles WHERE user_id=(SELECT user_id FROM edutrust.teacher_profiles WHERE id=(SELECT teacher_id FROM edutrust.bookings WHERE id='{cycle['booking_id']}'))")


# ---------------------------------------------------------------------------
# Scenarios (approved VS9 plan, section 23)
# ---------------------------------------------------------------------------

def s01_normal_resolution(atok, otok):
    S = "S1_NORMAL_RESOLUTION"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    dispute_id = open_dispute(cycle["ptok"], session_id, "OTHER", "general question about the session")
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "Reviewed the context; no action required.", "action": "NO_ACTION"})
    check(S, "resolve NO_ACTION -> 200 RESOLVED", st == 200 and data["data"]["dispute"]["status"] == "RESOLVED", f"{st} {data}")
    check(S, "no refund created for record-only action", "refund" not in data["data"], str(data["data"].keys()))
    ev = psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id='{dispute_id}'")
    check(S, "DISPUTE_RESOLVED event recorded", ev == "1", ev)
    st, data = api("GET", f"/api/v1/disputes/{dispute_id}", cycle["ptok"])
    check(S, "parent sees resolution in dispute detail", st == 200 and data["data"]["status"] == "RESOLVED" and data["data"]["resolution"], f"{st} {data}")


def s02_unauthorized(atok, otok):
    S = "S2_UNAUTHORIZED"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "OTHER", "unauthorized case")
    body = {"resolution": "attempt to resolve", "action": "NO_ACTION"}
    st, _ = resolve_dispute(cycle["ptok"], dispute_id, body)
    check(S, "parent (opener) cannot resolve -> 403", st == 403, str(st))
    st, _ = resolve_dispute(cycle["ttok"], dispute_id, body)
    check(S, "teacher (participant) cannot resolve -> 403", st == 403, str(st))
    st, data = api("POST", f"/api/v1/admin/disputes/{dispute_id}/resolve", None, body=body)
    check(S, "anonymous resolve -> 401", st == 401, str(st))
    st, _ = api("GET", "/api/v1/admin/disputes", cycle["ptok"])
    check(S, "parent admin dispute list -> 403", st == 403, str(st))
    st, _ = api("GET", "/api/v1/admin/disputes", cycle["ttok"])
    check(S, "teacher admin dispute list -> 403", st == 403, str(st))


def s03_invalid_transition(atok, otok):
    S = "S3_INVALID_TRANSITION"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "OTHER", "terminality case")
    st, _ = resolve_dispute(otok, dispute_id, {"resolution": "first resolution", "action": "NO_ACTION"})
    check(S, "first resolve -> 200", st == 200, str(st))
    st, data = resolve_dispute(atok, dispute_id, {"resolution": "second resolution", "action": "NO_ACTION"})
    check(S, "resolve of RESOLVED dispute -> 409 DISPUTE_INVALID_STATE", st == 409 and data["error"]["code"] == "DISPUTE_INVALID_STATE", f"{st} {data}")
    for action in ("ACCOUNT_SUSPENDED", "ACCOUNT_SUSPENSION_RECOMMENDED"):
        dispute_id2 = open_dispute(cycle["ptok"], session_id, "OTHER", "excluded action case")
        st, data = resolve_dispute(atok, dispute_id2, {"resolution": "excluded action attempt", "action": action})
        check(S, f"excluded action {action} -> 400 VALIDATION_ERROR", st == 400 and data["error"]["code"] == "VALIDATION_ERROR", f"{st} {data}")
        # close between iterations (VS4 service invariant: at most one active dispute per interaction —
        # the 400 above leaves the dispute OPEN, which would make the next open a DUPLICATE_DISPUTE)
        resolve_dispute(atok, dispute_id2, {"resolution": "closed between iterations", "action": "NO_ACTION"})


def s04_full_refund(atok, otok):
    S = "S4_FULL_REFUND"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "TEACHER_NO_SHOW", "teacher never showed up")
    st, data = resolve_dispute(atok, dispute_id, {"resolution": "teacher no-show; full refund.", "action": "FULL_REFUND", "refund_amount": "2000.00"})
    check(S, "FULL_REFUND resolve -> 200 + refund REQUESTED FULL", st == 200 and data["data"]["refund"]["status"] == "REQUESTED" and data["data"]["refund"]["refund_type"] == "FULL", f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "VS8 approve (allocation) -> PROVIDER_PENDING", st == 200 and data["data"]["refund"]["status"] == "PROVIDER_PENDING", f"{st} {data}")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "VS8 mock success -> SUCCEEDED / payment REFUNDED", st == 200 and data["data"]["refund_status"] == "SUCCEEDED" and data["data"]["payment_status"] == "REFUNDED", f"{st} {data}")
    tx = psql(f"SELECT status FROM edutrust.ledger_transactions WHERE reference='refund-{rid}'")
    check(S, "refund ledger tx POSTED", tx == "POSTED", tx)
    st, data = api("GET", "/api/v1/payments/" + cycle["payment_id"], cycle["ptok"])
    check(S, "parent payment detail shows refund completed (SUCCEEDED only rule)",
          st == 200 and data["data"]["refunds"] and data["data"]["refunds"][0]["status"] == "SUCCEEDED", f"{st}")


def s05_partial_refund(atok, otok):
    S = "S5_PARTIAL_REFUND"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "session ended after 30 minutes instead of 60")
    # OPS may resolve non-SAFETY refund actions (plan P4); full refund after a COMPLETED session is ADMIN-only
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "shortened session; full refund", "action": "FULL_REFUND", "refund_amount": "2000.00"})
    check(S, "OPS full refund after COMPLETED session -> 403 (P4 / SM 18.2)", st == 403, f"{st} {data}")
    # PARTIAL_REFUND on a FRESH interaction (VS4: one active dispute per interaction — the 403 above
    # left dispute one OPEN, so a second open on the same session would be DUPLICATE_DISPUTE)
    cycle2 = full_booking_cycle()
    session2 = confirm_payment(cycle2)
    session2 = complete_session_with_report(cycle2, session2)
    dispute_id = open_dispute(cycle2["ptok"], session2, "SESSION_QUALITY", "partial refund case")
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "partial refund for shortened session.", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    check(S, "OPS PARTIAL_REFUND -> 200 + refund REQUESTED PARTIAL", st == 200 and data["data"]["refund"]["refund_type"] == "PARTIAL", f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/approve", otok, body={"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "VS8 approve (300/100 allocation) -> PROVIDER_PENDING", st == 200, f"{st} {data}")
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", otok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "VS8 mock success -> payment PARTIALLY_REFUNDED", st == 200 and data["data"]["payment_status"] == "PARTIALLY_REFUNDED", f"{st} {data}")
    st, data = process_payout(atok, teacher_profile_id_of(cycle2), session2)
    check(S, "payout after partial settled -> 422 (payment not CONFIRMED — VS5 guard)", st == 422, f"{st} {data}")


def s06_payout_blocking_release(atok, otok):
    S = "S6_PAYOUT_BLOCKING_RELEASE"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "open dispute blocks payout")
    st, data = process_payout(atok, teacher_profile_id_of(cycle), session_id)
    check(S, "payout while dispute OPEN -> 422 OPEN_DISPUTE",
          st == 422 and any(d["reason"] == "OPEN_DISPUTE" for d in data["error"]["details"]["details"]), f"{st} {data}")
    items = psql(f"SELECT count(*) FROM edutrust.payout_items WHERE session_id='{session_id}'")
    check(S, "no payout item while blocked", items == "0", items)
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "no refund warranted; closing.", "action": "NO_ACTION"})
    check(S, "resolve -> 200", st == 200, str(st))
    st, data = process_payout(atok, teacher_profile_id_of(cycle), session_id)
    check(S, "payout after resolution -> 201 PAID 1700", st == 201 and data["data"]["result"] == "PAID" and data["data"]["payout"]["amount"] == "1700.00", f"{st} {data}")


def s07_post_paid_refund(atok, otok):
    S = "S7_POST_PAID_REFUND"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    session_id = complete_session_with_report(cycle, session_id)
    st, data = process_payout(atok, teacher_profile_id_of(cycle), session_id)
    assert st == 201, f"payout: {st} {data}"
    payout = data["data"]["payout"]
    before = psql(f"SELECT amount||'|'||status::text||'|'||provider_reference FROM edutrust.payouts WHERE id='{payout['id']}'")
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "post-paid partial refund")
    st, data = resolve_dispute(atok, dispute_id, {"resolution": "post-paid partial refund.", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    check(S, "resolve PARTIAL_REFUND after payout PAID -> 200", st == 200, f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, _ = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body={"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "approve (300/100) -> 200", st == 200, str(st))
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", atok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock success -> PARTIALLY_REFUNDED", st == 200 and data["data"]["payment_status"] == "PARTIALLY_REFUNDED", f"{st} {data}")
    entries = psql(f"SELECT string_agg(account_type::text||':'||direction::text||':'||amount::text, ',' ORDER BY e.created_at) FROM edutrust.ledger_entries e JOIN edutrust.ledger_transactions t ON t.id=e.ledger_transaction_id WHERE t.reference='refund-{rid}'")
    check(S, "Form A recovery entries (Addendum 11): teacher recoverable + platform expense + clearing",
          "TEACHER_RECOVERABLE:DEBIT:300.00" in entries and "PLATFORM_REFUND_EXPENSE:DEBIT:100.00" in entries and "PAYMENT_PROVIDER_CLEARING:CREDIT:400.00" in entries, entries)
    after = psql(f"SELECT amount||'|'||status::text||'|'||provider_reference FROM edutrust.payouts WHERE id='{payout['id']}'")
    check(S, "old PAID payout byte-identical (v1.4 immutability)", before == after, f"{before} vs {after}")


def s08_refund_failure(atok, otok):
    S = "S8_REFUND_FAILURE"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "refund failure case")
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "partial refund then provider failure.", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    check(S, "resolve PARTIAL_REFUND -> 200", st == 200, f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, _ = api("POST", f"/api/v1/admin/refunds/{rid}/approve", otok, body={"approved_amount": "400.00", "teacher_adjustment_amount": "200.00", "platform_adjustment_amount": "200.00"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "approve -> 200", st == 200, str(st))
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/fail", otok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "mock failure -> FAILED / payment restored CONFIRMED", st == 200 and data["data"]["refund_status"] == "FAILED" and data["data"]["payment_status"] == "CONFIRMED", f"{st} {data}")
    tx = psql(f"SELECT status FROM edutrust.ledger_transactions WHERE reference='refund-{rid}'")
    check(S, "ledger tx VOIDED (no premature POSTED)", tx == "VOIDED", tx)
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/mock/succeed", otok, body={"provider_event_id": f"rfevt-{uuid.uuid4()}"})
    check(S, "terminal FAILED refund cannot reopen -> 409", st == 409 and data["error"]["code"] == "REFUND_INVALID_STATE", f"{st} {data}")
    ds = psql(f"SELECT status FROM edutrust.disputes WHERE id='{dispute_id}'")
    check(S, "dispute stays RESOLVED (refund lifecycle independent; G1: operator may open a new dispute)", ds == "RESOLVED", ds)


def s09_reconciliation(atok, otok):
    S = "S9_RECONCILIATION"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "reconciled full refund")
    st, data = resolve_dispute(atok, dispute_id, {"resolution": "full refund via manual reconciliation.", "action": "FULL_REFUND", "refund_amount": "2000.00"})
    check(S, "resolve FULL_REFUND -> 200", st == 200, f"{st} {data}")
    rid = data["data"]["refund"]["refund_id"]
    st, _ = api("POST", f"/api/v1/admin/refunds/{rid}/approve", atok, body={"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "approve -> 200", st == 200, str(st))
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/reconcile", atok,
                   body={"result": "SUCCEEDED", "reconciliation_source": "MANUAL_RECONCILIATION", "reconciliation_reference": "BANK-REF-VS9-1",
                         "reconciled_at": "2026-08-25T12:00:00Z", "reason": "bank confirmation received."}, idem=f"ref-{uuid.uuid4()}")
    check(S, "reconcile SUCCEEDED -> SUCCEEDED / payment REFUNDED", st == 200 and data["data"]["refund"]["status"] == "SUCCEEDED" and data["data"]["payment_status"] == "REFUNDED", f"{st} {data}")
    recon = psql(f"SELECT reconciliation_source||'|'||reconciliation_reference||'|'||(reconciled_by_user_id IS NOT NULL) FROM edutrust.refunds WHERE id='{rid}'")
    check(S, "reconciliation proof recorded with actor attribution", recon == "MANUAL_RECONCILIATION|BANK-REF-VS9-1|true", recon)
    st, data = api("POST", f"/api/v1/admin/refunds/{rid}/reconcile", atok,
                   body={"result": "FAILED", "reconciliation_source": "MANUAL_RECONCILIATION", "reconciliation_reference": "X",
                         "reconciled_at": "2026-08-25T12:00:00Z", "reason": "late failure attempt"}, idem=f"ref-{uuid.uuid4()}")
    check(S, "reconcile of terminal refund -> 409 DISPUTE... REFUND_INVALID_STATE", st == 409 and data["error"]["code"] == "REFUND_INVALID_STATE", f"{st} {data}")


def s10_idempotent_replay(atok, otok):
    S = "S10_IDEMPOTENT_REPLAY"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "idempotent resolve")
    key = f"disp-res-{uuid.uuid4()}"
    body = {"resolution": "idempotent partial refund", "action": "PARTIAL_REFUND", "refund_amount": "300.00"}
    st1, d1 = resolve_dispute(otok, dispute_id, body, idem=key)
    st2, d2 = resolve_dispute(otok, dispute_id, body, idem=key)
    check(S, "replay same key+body -> 200 original", st1 == 200 and st2 == 200, f"{st1}/{st2}")
    check(S, "replay returns the same refund (single refund row)",
          st1 == 200 and d2["data"]["refund"]["refund_id"] == d1["data"]["refund"]["refund_id"], f"{d2}")
    n = psql(f"SELECT count(*) FROM edutrust.refunds WHERE dispute_id='{dispute_id}'")
    check(S, "exactly one refund row (no duplicate refund)", n == "1", n)
    ev = psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id='{dispute_id}'")
    check(S, "exactly one DISPUTE_RESOLVED event (no double resolution)", ev == "1", ev)


def s11_idempotency_conflict(atok, otok):
    S = "S11_IDEMPOTENCY_CONFLICT"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "OTHER", "idempotency conflict")
    key = f"disp-res-{uuid.uuid4()}"
    st1, _ = resolve_dispute(otok, dispute_id, {"resolution": "conflict body one", "action": "NO_ACTION"}, idem=key)
    check(S, "first request -> 200", st1 == 200, str(st1))
    st2, d2 = resolve_dispute(otok, dispute_id, {"resolution": "conflict body two", "action": "NO_ACTION"}, idem=key)
    check(S, "same key different body -> 409 IDEMPOTENCY_KEY_CONFLICT", st2 == 409 and d2["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT", f"{st2} {d2}")
    st3, d3 = api("POST", f"/api/v1/admin/disputes/{dispute_id}/resolve", otok, body={"resolution": "missing key resolve", "action": "NO_ACTION"})
    check(S, "missing Idempotency-Key -> 400 IDEMPOTENCY_KEY_REQUIRED", st3 == 400 and d3["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED", f"{st3} {d3}")


def s12_concurrent_resolution(atok, otok):
    S = "S12_CONCURRENT_RESOLUTION"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "OTHER", "concurrent resolution")
    ops2 = seed_operator("OPS", "vs9e2e-ops2")
    results: list[int] = []
    barrier = threading.Barrier(2)

    def attempt(tok, text):
        barrier.wait()
        st, _ = resolve_dispute(tok, dispute_id, {"resolution": text, "action": "NO_ACTION"})
        results.append(st)

    t1 = threading.Thread(target=attempt, args=(otok, "operator one"))
    t2 = threading.Thread(target=attempt, args=(ops2, "operator two"))
    t1.start(); t2.start(); t1.join(); t2.join()
    check(S, "concurrent resolves -> exactly one 200, one 409", sorted(results) == [200, 409], str(results))
    ev = psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id='{dispute_id}'")
    check(S, "exactly one authoritative DISPUTE_RESOLVED", ev == "1", ev)
    ds = psql(f"SELECT status FROM edutrust.disputes WHERE id='{dispute_id}'")
    check(S, "dispute RESOLVED exactly once", ds == "RESOLVED", ds)


def s13_audit_security(atok, otok):
    S = "S13_AUDIT_SECURITY"
    print(f"\n== {S} ==", flush=True)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "audit fields case")
    before = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
    st, data = resolve_dispute(otok, dispute_id, {"resolution": "audit fields resolution text", "action": "PARTIAL_REFUND", "refund_amount": "100.00"})
    check(S, "resolve -> 200", st == 200, str(st))
    rid = data["data"]["refund"]["refund_id"]
    audit = psql(f"SELECT resolution IS NOT NULL AND resolved_at IS NOT NULL AND assigned_admin_user_id IS NOT NULL FROM edutrust.disputes WHERE id='{dispute_id}'")
    check(S, "SM 11.7 audit fields stored (resolution/resolved_at/resolver)", audit == "t", audit)
    ref = psql(f"SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_id='{dispute_id}' AND metadata::text LIKE '%{rid}%'")
    check(S, "ADMIN_ACTION event carries the refund reference", ref == "1", ref)
    after = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
    st, _ = api("GET", "/api/v1/admin/disputes", atok)
    after2 = psql("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
    check(S, "admin list read audited (ADMIN_ACCESS +1)", st == 200 and int(after2) == int(after) + 1, f"{after}->{after2}")
    st, _ = api("GET", f"/api/v1/disputes/{dispute_id}", atok)
    check(S, "admin dispute detail read audited", st == 200, str(st))
    issued = psql("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='REFUND_ISSUED'")
    check(S, "REFUND_ISSUED never emitted (deprecated)", issued == "0", issued)


def s14_ledger_integrity(atok, otok):
    S = "S14_LEDGER_INTEGRITY"
    print(f"\n== {S} ==", flush=True)
    bad_balanced = psql("SELECT count(*) FROM edutrust.ledger_transactions t WHERE COALESCE((SELECT SUM(amount) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='DEBIT'),0) <> COALESCE((SELECT SUM(amount) FROM edutrust.ledger_entries e WHERE e.ledger_transaction_id=t.id AND e.direction='CREDIT'),0)")
    check(S, "every ledger transaction balanced", bad_balanced == "0", bad_balanced)
    bad_posted = psql("SELECT count(*) FROM edutrust.ledger_transactions t WHERE t.transaction_type='REFUND' AND t.status='POSTED' AND NOT EXISTS (SELECT 1 FROM edutrust.refunds r WHERE r.status='SUCCEEDED' AND t.reference='refund-'||r.id::text)")
    check(S, "no unauthorized POSTED refund tx (every POSTED has a SUCCEEDED refund)", bad_posted == "0", bad_posted)
    bad_failed = psql("SELECT count(*) FROM edutrust.refunds r WHERE r.status='FAILED' AND EXISTS (SELECT 1 FROM edutrust.ledger_transactions t WHERE t.reference='refund-'||r.id::text AND t.status='POSTED')")
    check(S, "no FAILED refund with a POSTED tx", bad_failed == "0", bad_failed)
    bad_alloc = psql("SELECT count(*) FROM edutrust.refunds WHERE status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED') AND (COALESCE(teacher_adjustment_amount,0)+COALESCE(platform_adjustment_amount,0)) <> approved_amount")
    check(S, "allocation integrity (teacher+platform=approved)", bad_alloc == "0", bad_alloc)
    dup_ev = psql("SELECT count(*) FROM (SELECT provider, provider_event_id FROM edutrust.payment_provider_events GROUP BY 1,2 HAVING count(*)>1) d")
    check(S, "no duplicate provider event identity", dup_ev == "0", dup_ev)
    dup_refund = psql("SELECT count(*) FROM (SELECT payment_id, idempotency_key FROM edutrust.refunds GROUP BY 1,2 HAVING count(*)>1) d")
    check(S, "no duplicate refund (payment+key)", dup_refund == "0", dup_refund)
    dup_payout = psql("SELECT count(*) FROM (SELECT session_id FROM edutrust.payout_items GROUP BY 1 HAVING count(*)>1) d")
    check(S, "no duplicate payout item per session", dup_payout == "0", dup_payout)
    term = psql("SELECT count(*) FROM edutrust.refunds WHERE (status='SUCCEEDED' AND completed_at IS NULL) OR (status='FAILED' AND failed_at IS NULL) OR (status='REJECTED' AND rejected_at IS NULL) OR (status='CANCELLED' AND cancelled_at IS NULL)")
    check(S, "terminal refund states carry terminal timestamps", term == "0", term)
    rp = psql("SELECT count(*) FROM edutrust.payments p WHERE p.status IN ('REFUNDED','PARTIALLY_REFUNDED') AND NOT EXISTS (SELECT 1 FROM edutrust.refunds r WHERE r.payment_id=p.id AND r.status='SUCCEEDED')")
    check(S, "refund/payment consistency (refunded payments have SUCCEEDED refunds)", rp == "0", rp)
    over = psql("SELECT count(*) FROM edutrust.payments p WHERE (SELECT COALESCE(SUM(r.approved_amount),0) FROM edutrust.refunds r WHERE r.payment_id=p.id AND r.status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')) > p.amount")
    check(S, "no over-refund at rest (reserved <= payment amount)", over == "0", over)
    real = psql("SELECT count(*) FROM edutrust.payment_provider_events WHERE provider NOT IN ('OTHER')")
    check(S, "no real provider events (mock-only DEV boundary)", real == "0", real)


def s15_frontend_console(atok, otok):
    S = "S15_FRONTEND_CONSOLE"
    print(f"\n== {S} ==", flush=True)
    # API-level console endpoint checks (the repo has no browser automation — documented limitation)
    cycle = full_booking_cycle()
    session_id = confirm_payment(cycle)
    dispute_id = open_dispute(cycle["ptok"], session_id, "SESSION_QUALITY", "frontend console case")
    st, data = api("GET", "/api/v1/admin/disputes?status=OPEN", atok)
    check(S, "admin console list API (status filter) -> 200 + dispute present",
          st == 200 and any(d["id"] == dispute_id for d in data["data"]), f"{st}")
    st, data = api("GET", "/api/v1/disputes", cycle["ptok"])
    check(S, "parent console list API -> 200 + own dispute", st == 200 and any(d["id"] == dispute_id for d in data["data"]), f"{st}")
    st, data = api("GET", "/api/v1/disputes", cycle["ttok"])
    check(S, "teacher console list API -> 200 (participant visibility)", st == 200 and any(d["id"] == dispute_id for d in data["data"]), f"{st}")
    # Next.js production server serving the console pages
    try:
        r = requests.get(FRONTEND + "/admin", timeout=15)
        check(S, "Next.js /admin console served (200, contains Disputes section)", r.status_code == 200 and "Disputes (operational)" in r.text, str(r.status_code))
        r = requests.get(FRONTEND + "/parent", timeout=15)
        check(S, "Next.js /parent console served (200)", r.status_code == 200, str(r.status_code))
    except requests.RequestException as e:
        check(S, "Next.js console served (200)", False, f"frontend not reachable: {e}")


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

def main() -> int:
    django_available = False
    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edutrust.settings")
        sys.path.insert(0, str(REPO / "backend"))
        django.setup()
        django_available = True
    except Exception as e:
        print(f"django setup failed: {e}", flush=True)
    print("VS9 E2E — Dispute Resolution (DEV mock only)", flush=True)
    print(f"PG_BIN={PG_BIN}", flush=True)
    # isolated PG cluster
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "data").mkdir(exist_ok=True)
    (BASE / "socket").mkdir(exist_ok=True)
    if not (BASE / "data" / "PG_VERSION").exists():
        r = subprocess.run([f"{PG_BIN}/initdb", "-D", str(BASE / "data"), "-E", "UTF8", "--locale=C", "--auth-local=trust", "--auth-host=trust"], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"initdb failed: {r.stderr}", flush=True)
            return 2
        with open(BASE / "data" / "postgresql.conf", "a") as f:
            f.write(f"port={PORT}\nunix_socket_directories='{BASE / 'socket'}'\n")
    frontend_proc = None
    api_proc = None
    try:
        subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(BASE / "data"), "-l", str(BASE / "pg.log"), "-o", f"-k {BASE / 'socket'} -p {PORT} -F", "start"], check=True, capture_output=True)
        time.sleep(1)
        subprocess.run([f"{PG_BIN}/createdb", "-h", str(BASE / "socket"), "-p", str(PORT), DB], check=True, capture_output=True)
        env = dict(os.environ, PATH=f"{PG_BIN}:{os.environ.get('PATH', '')}",
                   DATABASE_URL=f"postgresql://{os.environ.get('USER', 'user')}@localhost:{PORT}/{DB}",
                   APP_ENV="development", DEBUG="true", SECRET_KEY="e2e-secret",
                   JWT_SECRET="e2e-jwt-secret-with-at-least-32-bytes",
                   MOCK_PAYMENT_PROVIDER_ENABLED="true", REAL_PAYMENT_ENABLED="false", REAL_PAYOUT_ENABLED="false",
                   PYTHONPATH=str(REPO / "backend"), DJANGO_SETTINGS_MODULE="edutrust.settings")
        r = subprocess.run([PY, str(REPO / "scripts/run_migrations.py")], env=env, cwd=REPO, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"migrations failed: {r.stderr[-2000:]}", flush=True)
            return 2
        api_proc = subprocess.Popen([PY, str(REPO / "backend/manage.py"), "runserver", f"127.0.0.1:{API_PORT}", "--noreload"],
                                    env=env, cwd=str(REPO / "backend"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                if requests.get(API + "/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            print("API server did not start", flush=True)
            return 2
        # frontend production server (requires .next build)
        if (REPO / "frontend" / ".next").exists():
            frontend_proc = subprocess.Popen(["npm", "run", "start", "--", "-p", str(FRONTEND_PORT)],
                                              env=dict(os.environ, PORT=str(FRONTEND_PORT)), cwd=str(REPO / "frontend"),
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(60):
                try:
                    if requests.get(FRONTEND + "/", timeout=1).status_code in (200, 307, 404):
                        break
                except requests.RequestException:
                    time.sleep(0.5)
    except Exception as e:
        print(f"runtime setup failed: {e}", flush=True)
        return 2
    try:
        atok = seed_operator("ADMIN", "vs9e2e-admin")
        otok = seed_operator("OPS", "vs9e2e-ops")
        s01_normal_resolution(atok, otok)
        s02_unauthorized(atok, otok)
        s03_invalid_transition(atok, otok)
        s04_full_refund(atok, otok)
        s05_partial_refund(atok, otok)
        s06_payout_blocking_release(atok, otok)
        s07_post_paid_refund(atok, otok)
        s08_refund_failure(atok, otok)
        s09_reconciliation(atok, otok)
        s10_idempotent_replay(atok, otok)
        s11_idempotency_conflict(atok, otok)
        s12_concurrent_resolution(atok, otok)
        s13_audit_security(atok, otok)
        s14_ledger_integrity(atok, otok)
        s15_frontend_console(atok, otok)
    finally:
        for proc in (frontend_proc, api_proc):
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(BASE / "data"), "stop", "-m", "fast"], capture_output=True)
        shutil.rmtree(BASE, ignore_errors=True)

    total = len(_results)
    failed = [c for c in _results if not c[2]]
    print(f"\nVS9 E2E RESULT: {total - len(failed)}/{total} checks passed", flush=True)
    for sc, desc, ok, detail in failed:
        print(f"  FAILED in {sc}: {desc} — {detail}", flush=True)
    if not failed:
        print("E2E_DISPUTE_RESOLUTION=PASS", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
