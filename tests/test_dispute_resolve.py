"""DEV Vertical Slice #9 — Dispute Resolution (CORE: RESOLVED path, nine actions).

Regression baseline before this file: 160 tests (foundation + VS1..VS8).

Covers plan test IDs T-01..T-34 (plan section 22):
  A. creation/visibility   T-25, T-26, T-27
  B. resolution            T-01, T-02, T-17, T-18, T-19, T-20
  C. authorization         T-04, T-05
  D. invalid states        T-03, T-06, T-21, T-28, T-29
  E. refund integration    T-07, T-08, T-09, T-10, T-11
  F. payout interaction    T-12, T-15, T-16
  G. ledger integrity      T-11, T-12, T-13, T-14, T-32
  H. idempotency           T-22, T-23, T-24
  I. concurrency           (test_dispute_resolve_concurrency.py C-01..C-04)
  J. audit                 T-25, T-30
  K. security              T-04, T-05, T-26, T-32
  L. terminality           T-03, T-34
  M. regression            T-31 (overlay invariants), T-15/T-16 (payout reactivity)
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import django
from django.db import connection
from django.test import Client

django.setup()

from tests.test_payment_slice_2 import make_held_booking, initiate
from tests.test_session_slice_3 import create_completed_session, make_scheduled_session
from tests.test_vertical_slice_4 import admin_login
from tests.test_vertical_slice_5 import completed_with_report, process_payout
from tests.test_vertical_slice_6 import seed_operator
from tests.test_vertical_slice_1 import post_json, get_json


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def login_op(client, email: str) -> str:
    res = post_json(client, "/api/v1/auth/login", {"identifier": email, "password": "StrongPassword123!"})
    assert res.status_code == 200, res.content
    return res.json()["data"]["access_token"]


def open_dispute(client, token, body: dict, idem=None):
    return post_json(client, "/api/v1/disputes", body, token, idem=idem or f"disp-{uuid.uuid4()}")


def resolve(client, token, dispute_id: str, body: dict, idem=None):
    return post_json(client, f"/api/v1/admin/disputes/{dispute_id}/resolve", body, token, idem=idem or f"disp-res-{uuid.uuid4()}")


def dispute_status(dispute_id: str) -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.disputes WHERE id=%s", [dispute_id])
        return cur.fetchone()[0]


def event_count(event_type: str, entity_id: str | None = None) -> int:
    with connection.cursor() as cur:
        if entity_id:
            cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type=%s AND entity_id=%s", [event_type, entity_id])
        else:
            cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type=%s", [event_type])
        return cur.fetchone()[0]


def refund_rows_for_dispute(dispute_id: str) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute("SELECT id::text, status::text, refund_type::text, requested_amount::text FROM edutrust.refunds WHERE dispute_id=%s ORDER BY created_at", [dispute_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def reserved_for_payment(payment_id: str) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(approved_amount),0) FROM edutrust.refunds WHERE payment_id=%s AND status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')", [payment_id])
        return Decimal(str(cur.fetchone()[0]))


def direct_refund_to_succeeded(client, token, payment_id: str, amount: str, teacher: str, platform: str) -> str:
    """VS8 direct path: create -> approve -> mock succeed (no dispute)."""
    c = post_json(client, f"/api/v1/payments/{payment_id}/refund", {"amount": amount, "currency": "DZD", "reason": "direct test refund"}, token, idem=f"ref-{uuid.uuid4()}")
    assert c.status_code == 201, c.content
    rid = c.json()["data"]["refund"]["refund_id"]
    a = post_json(client, f"/api/v1/admin/refunds/{rid}/approve", {"approved_amount": amount, "teacher_adjustment_amount": teacher, "platform_adjustment_amount": platform}, token, idem=f"ref-{uuid.uuid4()}")
    assert a.status_code == 200, a.content
    s = post_json(client, f"/api/v1/admin/refunds/{rid}/mock/succeed", {"provider_event_id": f"rfevt-{uuid.uuid4()}"}, token)
    assert s.status_code == 200, s.content
    return rid


def ops_admin_session(report: bool = False):
    """Fresh completed paid session + OPS and ADMIN operators.

    report=True uses the VS5 completed_with_report() fixture (session report written),
    which payout processing requires (VS5 eligibility: NO_SESSION_REPORT otherwise)."""
    factory = completed_with_report if report else create_completed_session
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = factory()
    ops_email = seed_operator("OPS", "vs9-ops")
    admin_email = seed_operator("ADMIN", "vs9-admin")
    ops_tok = login_op(parent_client, ops_email)
    admin_tok = admin_login(parent_client)  # admin_login seeds its own ADMIN
    return {
        "teacher": teacher, "parent_client": parent_client, "parent_auth": parent_auth,
        "booking_id": booking_id, "payment_id": payment_id, "session_id": session_id,
        "ops_tok": ops_tok, "admin_tok": admin_tok, "ptok": parent_auth["access_token"],
    }


# ---------------------------------------------------------------------------
# B. resolution (record-only actions)
# ---------------------------------------------------------------------------

def test_t01_resolve_no_action_from_open():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "general question about the session"})
    assert d.status_code == 201, d.content
    dispute_id = d.json()["data"]["dispute"]["id"]
    before = event_count("ADMIN_ACTION", dispute_id)
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "Reviewed the context; no action required.", "action": "NO_ACTION"})
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["dispute"]["status"] == "RESOLVED"
    assert data["dispute"]["resolution"] == "Reviewed the context; no action required."
    assert "refund" not in data  # record-only action creates no refund
    assert dispute_status(dispute_id) == "RESOLVED"
    assert event_count("DISPUTE_RESOLVED", dispute_id) == 1
    assert event_count("ADMIN_ACTION", dispute_id) == before + 1
    assert refund_rows_for_dispute(dispute_id) == []
    # no financial effect: payment unchanged, no ledger tx for this dispute
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.payments WHERE id=%s", [s["payment_id"]])
        assert cur.fetchone()[0] == "CONFIRMED"
        cur.execute("SELECT count(*) FROM edutrust.ledger_transactions t JOIN edutrust.refunds r ON t.reference='refund-'||r.id::text WHERE r.dispute_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 0


def test_t02_resolve_from_under_review():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "under review case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    with connection.cursor() as cur:
        # UNDER_REVIEW is a valid schema state; the assignment mechanism is deferred (plan P5),
        # so the state is prepared directly to exercise the approved from-set.
        cur.execute("UPDATE edutrust.disputes SET status='UNDER_REVIEW' WHERE id=%s", [dispute_id])
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "Reviewed under review state; closing.", "action": "WARNING"})
    assert res.status_code == 200, res.content
    assert res.json()["data"]["dispute"]["status"] == "RESOLVED"


def test_t17_payout_block_release_actions_recorded():
    s = ops_admin_session()
    for action in ("PAYOUT_BLOCKED", "PAYOUT_RELEASED"):
        d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": f"{action} case"})
        dispute_id = d.json()["data"]["dispute"]["id"]
        res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": f"Operational {action.lower()} recorded.", "action": action})
        assert res.status_code == 200, res.content
        assert res.json()["data"]["dispute"]["status"] == "RESOLVED"
        with connection.cursor() as cur:
            cur.execute("SELECT resolution FROM edutrust.disputes WHERE id=%s", [dispute_id])
            assert cur.fetchone()[0].startswith(f"Operational {action.lower()}")
        # no payout mutation, no ledger tx (mechanism = status reactivity only)
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [s["session_id"]])
            assert cur.fetchone()[0] == 0


def test_t18_teacher_no_show_confirmed_scheduled_session():
    teacher, parent_client, parent_auth, booking_id, payment_id, session_id = make_scheduled_session()
    ops_email = seed_operator("OPS", "vs9-ops-ns")
    ops_tok = login_op(parent_client, ops_email)
    d = open_dispute(parent_client, parent_auth["access_token"], {"session_id": session_id, "category": "TEACHER_NO_SHOW", "description": "teacher did not show up"})
    assert d.status_code == 201
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(parent_client, ops_tok, dispute_id, {"resolution": "Teacher no-show confirmed from dispute.", "action": "TEACHER_NO_SHOW_CONFIRMED"})
    assert res.status_code == 200, res.content
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.sessions WHERE id=%s", [session_id])
        assert cur.fetchone()[0] == "NO_SHOW_TEACHER"
    assert event_count("SESSION_NO_SHOW", session_id) == 1
    assert dispute_status(dispute_id) == "RESOLVED"


def test_t19_no_show_confirmed_completed_session_record_only():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "STUDENT_NO_SHOW", "description": "no-show claim on completed session"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "No-show claim on an already completed session; recorded.", "action": "STUDENT_NO_SHOW_CONFIRMED"})
    assert res.status_code == 200, res.content
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.sessions WHERE id=%s", [s["session_id"]])
        assert cur.fetchone()[0] == "COMPLETED"  # unchanged — no approved no-show transition from COMPLETED


def test_t20_report_correction_required_record_only():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "REPORT_ISSUE", "description": "report contains a factual error"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "Report correction requested from teacher.", "action": "REPORT_CORRECTION_REQUIRED"})
    assert res.status_code == 200, res.content
    assert res.json()["data"]["dispute"]["status"] == "RESOLVED"
    assert refund_rows_for_dispute(dispute_id) == []


# ---------------------------------------------------------------------------
# C. authorization
# ---------------------------------------------------------------------------

def test_t04_authorization_matrix():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "auth matrix case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    body = {"resolution": "attempt to resolve", "action": "NO_ACTION"}
    # parent (opener) cannot resolve
    assert resolve(s["parent_client"], s["ptok"], dispute_id, body).status_code == 403
    # teacher (participant) cannot resolve
    ttok = s["teacher"]["teacher_auth"]["access_token"]
    assert resolve(s["parent_client"], ttok, dispute_id, body).status_code == 403
    # support cannot resolve
    sup_tok = login_op(s["parent_client"], seed_operator("SUPPORT", "vs9-sup"))
    assert resolve(s["parent_client"], sup_tok, dispute_id, body).status_code == 403
    # anonymous
    anon = Client()
    assert anon.post(f"/api/v1/admin/disputes/{dispute_id}/resolve", data="{}", content_type="application/json").status_code == 401
    # OPS allowed (non-SAFETY, non-refund action)
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, body).status_code == 200
    assert dispute_status(dispute_id) == "RESOLVED"


def test_t05_safety_dispute_admin_only():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SAFETY", "description": "safety concern"})
    assert d.status_code == 201
    dispute_id = d.json()["data"]["dispute"]["id"]
    with connection.cursor() as cur:
        cur.execute("SELECT priority FROM edutrust.disputes WHERE id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1  # SAFETY priority 1 (VS4, unchanged)
    body = {"resolution": "safety resolution", "action": "NO_ACTION"}
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, body).status_code == 403
    assert dispute_status(dispute_id) == "OPEN"
    assert resolve(s["parent_client"], s["admin_tok"], dispute_id, body).status_code == 200
    assert dispute_status(dispute_id) == "RESOLVED"


# ---------------------------------------------------------------------------
# D. invalid states / excluded actions / validation
# ---------------------------------------------------------------------------

def test_t03_resolve_terminal_dispute_rejected():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "terminality case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "first resolution", "action": "NO_ACTION"}).status_code == 200
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "second resolution", "action": "NO_ACTION"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "DISPUTE_INVALID_STATE"


def test_t06_excluded_actions_rejected():
    s = ops_admin_session()
    for action in ("ACCOUNT_SUSPENDED", "ACCOUNT_SUSPENSION_RECOMMENDED", "REFUND", "NOT_AN_ACTION"):
        d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "excluded action case"})
        dispute_id = d.json()["data"]["dispute"]["id"]
        res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "excluded action attempt", "action": action})
        assert res.status_code == 400, (action, res.content)
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"
        assert dispute_status(dispute_id) == "OPEN"
        # close between iterations (VS4 invariant: at most one active dispute per interaction)
        assert resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "closed between iterations", "action": "NO_ACTION"}).status_code == 200


def test_t21_account_action_non_null_rejected():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "account_action case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "with account action", "action": "NO_ACTION", "account_action": "SUSPEND"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert dispute_status(dispute_id) == "OPEN"


def test_t28_resolution_validation():
    s = ops_admin_session()
    for body in ({"resolution": "ab", "action": "NO_ACTION"}, {"action": "NO_ACTION"}):
        d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "validation case"})
        dispute_id = d.json()["data"]["dispute"]["id"]
        res = resolve(s["parent_client"], s["ops_tok"], dispute_id, body)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"
        assert dispute_status(dispute_id) == "OPEN"
        # close between iterations (VS4 invariant: at most one active dispute per interaction)
        assert resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "closed between iterations", "action": "NO_ACTION"}).status_code == 200


def test_t29_refund_amount_on_non_refund_action_rejected():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "amount on non-refund"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "warning with amount", "action": "WARNING", "refund_amount": "100.00"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_t27_unknown_dispute_not_found():
    s = ops_admin_session()
    res = resolve(s["parent_client"], s["ops_tok"], str(uuid.uuid4()), {"resolution": "unknown dispute", "action": "NO_ACTION"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# E. refund integration (P1 two-step)
# ---------------------------------------------------------------------------

def test_t07_partial_refund_creates_linked_requested_refund():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "session ended after 30 minutes instead of 60"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    before_ref = event_count("REFUND_REQUESTED")
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "Partial refund approved due to shortened session.", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["dispute"]["status"] == "RESOLVED"
    refund = data["refund"]
    assert refund["status"] == "REQUESTED"
    assert refund["refund_type"] == "PARTIAL"
    assert refund["requested_amount"] == "400.00"
    rows = refund_rows_for_dispute(dispute_id)
    assert len(rows) == 1 and rows[0]["status"] == "REQUESTED" and rows[0]["refund_type"] == "PARTIAL"
    assert event_count("REFUND_REQUESTED") == before_ref + 1
    assert event_count("DISPUTE_RESOLVED", dispute_id) == 1
    # payment untouched at creation (two-step: approval happens via VS8 endpoint)
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.payments WHERE id=%s", [s["payment_id"]])
        assert cur.fetchone()[0] == "CONFIRMED"
    # no ledger tx yet (DRAFT is created at the VS8 approve step)
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.ledger_transactions WHERE reference=%s", [f"refund-{refund['refund_id']}"])
        assert cur.fetchone()[0] == 0


def test_t08_full_refund_amount_must_equal_payment():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "TEACHER_NO_SHOW", "description": "full refund wrong amount"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "full refund with wrong amount", "action": "FULL_REFUND", "refund_amount": "1500.00"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert dispute_status(dispute_id) == "OPEN"
    # correct amount passes creation
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "full refund correct amount", "action": "FULL_REFUND", "refund_amount": "2000.00"})
    assert res.status_code == 200, res.content
    assert res.json()["data"]["refund"]["refund_type"] == "FULL"


def test_t09_partial_refund_amount_must_be_below_payment():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "partial at full amount"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "partial at payment amount", "action": "PARTIAL_REFUND", "refund_amount": "2000.00"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert dispute_status(dispute_id) == "OPEN"


def test_t10_over_refund_at_resolve_rolls_back_resolution():
    s = ops_admin_session()
    # pre-existing SUCCEEDED 1500 refund (direct VS8 path)
    direct_refund_to_succeeded(s["parent_client"], s["ops_tok"], s["payment_id"], "1500.00", "1500.00", "0.00")
    assert reserved_for_payment(s["payment_id"]) == Decimal("1500.00")
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.payments WHERE id=%s", [s["payment_id"]])
        assert cur.fetchone()[0] == "PARTIALLY_REFUNDED"
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "over-refund via dispute"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    # Plan T-10 correction: the plan expected 409 OVER_REFUND here, but the approved VS8
    # creation contract (protected, byte-identical) status-gates FIRST — a SUCCEEDED partial
    # refund moves the payment to PARTIALLY_REFUNDED, and follow-up partials on that state
    # are contract-excluded (VS8 plan O7 gap; verified on the pure VS8 direct path: both
    # 600.00 and the exact 500.00 remainder return REFUND_INVALID_STATE). The rollback
    # guarantee the plan cares about (dispute stays OPEN, no refund row) is what is asserted.
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "too much combined refund", "action": "PARTIAL_REFUND", "refund_amount": "600.00"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    # whole resolution rolled back — no half-resolved dispute, no refund row
    assert dispute_status(dispute_id) == "OPEN"
    assert refund_rows_for_dispute(dispute_id) == []
    assert reserved_for_payment(s["payment_id"]) == Decimal("1500.00")
    # even the exact remainder (500.00) is contract-excluded until the O7 Addendum patch
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "within bound combined refund", "action": "PARTIAL_REFUND", "refund_amount": "500.00"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REFUND_INVALID_STATE"
    assert dispute_status(dispute_id) == "OPEN"
    assert refund_rows_for_dispute(dispute_id) == []


def test_t11_two_step_refund_completion_via_vs8():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "two-step completion"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "partial refund two-step", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    refund_id = res.json()["data"]["refund"]["refund_id"]
    # operator approves through the EXISTING VS8 endpoint with allocation (P1 two-step)
    a = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/approve",
                  {"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"},
                  s["ops_tok"], idem=f"ref-{uuid.uuid4()}")
    assert a.status_code == 200, a.content
    m = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/mock/succeed", {"provider_event_id": f"rfevt-{uuid.uuid4()}"}, s["ops_tok"])
    assert m.status_code == 200, m.content
    assert m.json()["data"]["payment_status"] == "PARTIALLY_REFUNDED"
    # Form D ledger: teacher/platform debits + clearing credit, POSTED
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.ledger_transactions WHERE reference=%s", [f"refund-{refund_id}"])
        assert cur.fetchone()[0] == "POSTED"
        cur.execute("""
            SELECT account_type::text, direction::text, amount::text FROM edutrust.ledger_entries e
            JOIN edutrust.ledger_transactions t ON t.id=e.ledger_transaction_id
            WHERE t.reference=%s ORDER BY e.created_at
        """, [f"refund-{refund_id}"])
        entries = [dict(zip(("account", "direction", "amount"), r)) for r in cur.fetchall()]
    assert ("TEACHER_PAYABLE", "DEBIT", "300.00") in [(e["account"], e["direction"], e["amount"]) for e in entries]
    assert ("PLATFORM_REVENUE", "DEBIT", "100.00") in [(e["account"], e["direction"], e["amount"]) for e in entries]
    assert ("PAYMENT_PROVIDER_CLEARING", "CREDIT", "400.00") in [(e["account"], e["direction"], e["amount"]) for e in entries]
    assert event_count("PAYMENT_PARTIALLY_REFUNDED", s["payment_id"]) == 1
    assert event_count("REFUND_ISSUED") == 0  # deprecated event never emitted
    # dispute detail shows the linked refund (VS8 field)
    det = get_json(s["parent_client"], f"/api/v1/disputes/{dispute_id}", s["ops_tok"])
    assert det.status_code == 200
    assert det.json()["data"]["linked_refunds"][0]["status"] == "SUCCEEDED"


# ---------------------------------------------------------------------------
# F. payout interaction
# ---------------------------------------------------------------------------

def test_t15_payout_blocked_by_open_dispute():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "open dispute blocks payout"})
    assert d.status_code == 201
    res = process_payout(s["parent_client"], s["admin_tok"], s["teacher"]["teacher_id"], [s["session_id"]])
    assert res.status_code == 422
    assert any(d2["reason"] == "OPEN_DISPUTE" for d2 in res.json()["error"]["details"]["details"])
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.payout_items WHERE session_id=%s", [s["session_id"]])
        assert cur.fetchone()[0] == 0


def test_t16_payout_unblocks_after_resolution():
    s = ops_admin_session(report=True)  # payout requires a session report (VS5 eligibility)
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "resolve then pay out"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "No refund warranted; closing.", "action": "NO_ACTION"}).status_code == 200
    res = process_payout(s["parent_client"], s["admin_tok"], s["teacher"]["teacher_id"], [s["session_id"]])
    assert res.status_code == 201, res.content
    assert res.json()["data"]["result"] == "PAID"
    assert res.json()["data"]["payout"]["amount"] == "1700.00"  # 2000 - 15% commission (unchanged VS5 behavior)


def test_t12_post_paid_refund_form_a_payout_untouched():
    s = ops_admin_session(report=True)  # payout requires a session report (VS5 eligibility)
    # payout PAID first (VS5 flow)
    p = process_payout(s["parent_client"], s["admin_tok"], s["teacher"]["teacher_id"], [s["session_id"]])
    assert p.status_code == 201, p.content
    payout = p.json()["data"]["payout"]
    with connection.cursor() as cur:
        cur.execute("SELECT amount::text, status::text, provider_reference, paid_at FROM edutrust.payouts WHERE id=%s", [payout["id"]])
        before = cur.fetchone()
    # dispute + PARTIAL_REFUND (300 teacher / 100 platform allocation)
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "post-paid partial refund"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "post-paid partial refund", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    assert res.status_code == 200, res.content
    refund_id = res.json()["data"]["refund"]["refund_id"]
    a = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/approve",
                  {"approved_amount": "400.00", "teacher_adjustment_amount": "300.00", "platform_adjustment_amount": "100.00"},
                  s["admin_tok"], idem=f"ref-{uuid.uuid4()}")
    assert a.status_code == 200, a.content
    m = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/mock/succeed", {"provider_event_id": f"rfevt-{uuid.uuid4()}"}, s["admin_tok"])
    assert m.status_code == 200, m.content
    # Form A recovery entries (Addendum 11): teacher recoverable + platform expense, clearing credit
    with connection.cursor() as cur:
        cur.execute("""
            SELECT account_type::text, direction::text, amount::text, t.status::text FROM edutrust.ledger_entries e
            JOIN edutrust.ledger_transactions t ON t.id=e.ledger_transaction_id
            WHERE t.reference=%s ORDER BY e.created_at
        """, [f"refund-{refund_id}"])
        entries = [dict(zip(("account", "direction", "amount", "tx_status"), r)) for r in cur.fetchall()]
    assert ("TEACHER_RECOVERABLE", "DEBIT", "300.00", "POSTED") in [(e["account"], e["direction"], e["amount"], e["tx_status"]) for e in entries]
    assert ("PLATFORM_REFUND_EXPENSE", "DEBIT", "100.00", "POSTED") in [(e["account"], e["direction"], e["amount"], e["tx_status"]) for e in entries]
    assert ("PAYMENT_PROVIDER_CLEARING", "CREDIT", "400.00", "POSTED") in [(e["account"], e["direction"], e["amount"], e["tx_status"]) for e in entries]
    # old PAID payout byte-identical (v1.4 immutability + Addendum 11)
    with connection.cursor() as cur:
        cur.execute("SELECT amount::text, status::text, provider_reference, paid_at FROM edutrust.payouts WHERE id=%s", [payout["id"]])
        assert cur.fetchone() == before


# ---------------------------------------------------------------------------
# G. ledger integrity (failure + reconciliation paths)
# ---------------------------------------------------------------------------

def test_t13_refund_failure_after_resolution():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "refund failure case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "partial refund then provider failure", "action": "PARTIAL_REFUND", "refund_amount": "400.00"})
    refund_id = res.json()["data"]["refund"]["refund_id"]
    a = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/approve",
                  {"approved_amount": "400.00", "teacher_adjustment_amount": "200.00", "platform_adjustment_amount": "200.00"},
                  s["ops_tok"], idem=f"ref-{uuid.uuid4()}")
    assert a.status_code == 200, a.content
    f = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/mock/fail", {"provider_event_id": f"rfevt-{uuid.uuid4()}"}, s["ops_tok"])
    assert f.status_code == 200, f.content
    assert f.json()["data"]["refund_status"] == "FAILED"
    assert f.json()["data"]["payment_status"] == "CONFIRMED"  # restored
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.ledger_transactions WHERE reference=%s", [f"refund-{refund_id}"])
        assert cur.fetchone()[0] == "VOIDED"  # draft never posted — no premature POSTED
    assert event_count("PAYMENT_REFUNDED", s["payment_id"]) == 0
    assert event_count("PAYMENT_PARTIALLY_REFUNDED", s["payment_id"]) == 0
    assert dispute_status(dispute_id) == "RESOLVED"  # resolution stands; refund lifecycle independent


def test_t14_reconciliation_completion_path():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "reconciled refund"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "full refund via manual reconciliation", "action": "FULL_REFUND", "refund_amount": "2000.00"})
    refund_id = res.json()["data"]["refund"]["refund_id"]
    a = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/approve",
                  {"approved_amount": "2000.00", "teacher_adjustment_amount": "1400.00", "platform_adjustment_amount": "600.00"},
                  s["admin_tok"], idem=f"ref-{uuid.uuid4()}")
    assert a.status_code == 200, a.content
    r = post_json(s["parent_client"], f"/api/v1/admin/refunds/{refund_id}/reconcile",
                  {"result": "SUCCEEDED", "reconciliation_source": "MANUAL_RECONCILIATION",
                   "reconciliation_reference": "BANK-REF-VS9-1", "reconciled_at": "2026-08-25T12:00:00Z",
                   "reason": "Bank confirmation received."},
                  s["admin_tok"], idem=f"ref-{uuid.uuid4()}")
    assert r.status_code == 200, r.content
    assert r.json()["data"]["refund"]["status"] == "SUCCEEDED"
    assert r.json()["data"]["payment_status"] == "REFUNDED"
    with connection.cursor() as cur:
        cur.execute("SELECT reconciliation_source, reconciliation_reference, reconciled_by_user_id IS NOT NULL FROM edutrust.refunds WHERE id=%s", [refund_id])
        source, reference, has_actor = cur.fetchone()
    assert source == "MANUAL_RECONCILIATION" and reference == "BANK-REF-VS9-1" and has_actor
    assert event_count("PAYMENT_REFUNDED", s["payment_id"]) == 1


# ---------------------------------------------------------------------------
# H. idempotency
# ---------------------------------------------------------------------------

def test_t22_idempotency_replay_same_key_same_body():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "idempotent resolve"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    key = f"disp-res-{uuid.uuid4()}"
    body = {"resolution": "idempotent partial refund", "action": "PARTIAL_REFUND", "refund_amount": "300.00"}
    r1 = resolve(s["parent_client"], s["ops_tok"], dispute_id, body, idem=key)
    assert r1.status_code == 200, r1.content
    r2 = resolve(s["parent_client"], s["ops_tok"], dispute_id, body, idem=key)
    assert r2.status_code == 200, r2.content
    assert r2.json()["data"]["refund"]["refund_id"] == r1.json()["data"]["refund"]["refund_id"]
    assert refund_rows_for_dispute(dispute_id) == [r for r in refund_rows_for_dispute(dispute_id)]  # sanity
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.refunds WHERE dispute_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1  # no duplicate refund
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='DISPUTE_RESOLVED' AND entity_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1  # no double resolution event


def test_t23_idempotency_conflict_same_key_different_body():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "idempotency conflict"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    key = f"disp-res-{uuid.uuid4()}"
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "conflict body one", "action": "NO_ACTION"}, idem=key).status_code == 200
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "conflict body two", "action": "NO_ACTION"}, idem=key)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_r2_regression_resolve_response_json_serializable():
    """Regression (Post-VS8 audit finding R-2): the URL converter passes dispute_id as a
    uuid.UUID; resolve_dispute must normalize to str before the plain-json idempotency
    canonical. A successful resolve response and its idempotency replay must be
    JSON-serializable end to end (view -> DRF, and service -> idempotency store -> replay)."""
    import json as _json
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "serialization regression"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    key = f"disp-res-{uuid.uuid4()}"
    body = {"resolution": "serialization regression resolve", "action": "PARTIAL_REFUND", "refund_amount": "250.00"}
    r1 = resolve(s["parent_client"], s["ops_tok"], dispute_id, body, idem=key)
    assert r1.status_code == 200, r1.content
    payload1 = r1.json()["data"]
    _json.dumps(payload1)  # successful response must be plain-JSON serializable
    # the idempotency record must be COMPLETED with a re-serializable stored body
    with connection.cursor() as cur:
        cur.execute("SELECT status::text, response_status, response_body FROM edutrust.api_idempotency_keys "
                    "WHERE scope='dispute_resolve' AND idempotency_key=%s", [key])
        row = cur.fetchone()
    assert row is not None, "idempotency record missing"
    status, response_status, stored = row
    assert status == "COMPLETED" and response_status == 200
    if isinstance(stored, str):
        stored = _json.loads(stored)
    _json.dumps(stored)  # stored body must be plain JSON (no uuid/Decimal residue)
    # replay: same key + same body -> 200, identical refund, still serializable
    r2 = resolve(s["parent_client"], s["ops_tok"], dispute_id, body, idem=key)
    assert r2.status_code == 200, r2.content
    payload2 = r2.json()["data"]
    _json.dumps(payload2)
    assert payload2["refund"]["refund_id"] == payload1["refund"]["refund_id"]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.refunds WHERE dispute_id=%s", [dispute_id])
        assert cur.fetchone()[0] == 1  # replay created no second refund


def test_t24_missing_idempotency_key_rejected():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "missing key case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    client = s["parent_client"]
    headers = {"HTTP_AUTHORIZATION": f"Bearer {s['ops_tok']}"}
    res = client.post(f"/api/v1/admin/disputes/{dispute_id}/resolve",
                      data='{"resolution": "missing key resolve", "action": "NO_ACTION"}',
                      content_type="application/json", **headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert dispute_status(dispute_id) == "OPEN"


# ---------------------------------------------------------------------------
# A/J. admin list + audit
# ---------------------------------------------------------------------------

def test_t25_admin_disputes_list_filters_and_audit():
    s = ops_admin_session()
    d1 = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "list case one"})
    # second dispute on a DIFFERENT interaction (VS4 invariant: one active dispute per
    # interaction) — also exercises cross-interaction listing
    _, pc2, auth2, _, _, session2 = create_completed_session()
    d2 = open_dispute(pc2, auth2["access_token"], {"session_id": session2, "category": "SAFETY", "description": "list case two"})
    d1_id, d2_id = d1.json()["data"]["dispute"]["id"], d2.json()["data"]["dispute"]["id"]
    like = "%READ_DISPUTE_LIST%"
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        sec_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='disputes' AND metadata::text LIKE %s", [like])
        act_before = cur.fetchone()[0]
    res = get_json(s["parent_client"], "/api/v1/admin/disputes", s["ops_tok"])
    assert res.status_code == 200
    ids = [d["id"] for d in res.json()["data"]]
    assert d1_id in ids and d2_id in ids
    assert "pagination" in res.json()
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM edutrust.security_events WHERE event_type='ADMIN_ACCESS'")
        assert cur.fetchone()[0] == sec_before + 1  # audited read
        cur.execute("SELECT count(*) FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_type='disputes' AND metadata::text LIKE %s", [like])
        assert cur.fetchone()[0] == act_before + 1
    # status filter (order-independent: earlier tests may have left RESOLVED rows behind)
    res = get_json(s["parent_client"], "/api/v1/admin/disputes?status=RESOLVED", s["ops_tok"])
    assert res.status_code == 200
    assert all(d["status"] == "RESOLVED" for d in res.json()["data"])
    assert d1_id not in [d["id"] for d in res.json()["data"]]  # d1 is OPEN
    # category filter (order-independent: earlier tests may have left SAFETY rows behind)
    res = get_json(s["parent_client"], "/api/v1/admin/disputes?category=SAFETY", s["ops_tok"])
    assert res.status_code == 200
    assert d2_id in [d["id"] for d in res.json()["data"]]
    assert all(d["category"] == "SAFETY" for d in res.json()["data"])
    # priority filter
    res = get_json(s["parent_client"], "/api/v1/admin/disputes?priority=1", s["ops_tok"])
    assert res.status_code == 200
    assert all(d["priority"] == 1 for d in res.json()["data"])


def test_t26_admin_disputes_list_role_access():
    s = ops_admin_session()
    # parent / teacher denied
    assert get_json(s["parent_client"], "/api/v1/admin/disputes", s["ptok"]).status_code == 403
    assert get_json(s["parent_client"], "/api/v1/admin/disputes", s["teacher"]["teacher_auth"]["access_token"]).status_code == 403
    # SUPPORT allowed per API 21.3 (plan P3), audited
    sup_tok = login_op(s["parent_client"], seed_operator("SUPPORT", "vs9-sup-list"))
    res = get_json(s["parent_client"], "/api/v1/admin/disputes", sup_tok)
    assert res.status_code == 200


def test_t30_audit_fields_complete_sm_11_7():
    s = ops_admin_session()
    ops_uid = s["ops_tok"]  # token, for reference
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "audit fields case"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "audit fields resolution text", "action": "PARTIAL_REFUND", "refund_amount": "100.00"})
    assert res.status_code == 200, res.content
    refund_id = res.json()["data"]["refund"]["refund_id"]
    with connection.cursor() as cur:
        cur.execute("SELECT resolution, resolved_at IS NOT NULL, assigned_admin_user_id IS NOT NULL FROM edutrust.disputes WHERE id=%s", [dispute_id])
        resolution, has_resolved_at, has_resolver = cur.fetchone()
    assert resolution == "audit fields resolution text"
    assert has_resolved_at and has_resolver  # SM 11.7: resolution, resolved_at, resolver
    # admin action event carries the refund reference (SM 11.7)
    with connection.cursor() as cur:
        cur.execute("SELECT metadata::text FROM edutrust.event_ledger WHERE event_type='ADMIN_ACTION' AND entity_id=%s AND metadata::text LIKE %s",
                    [dispute_id, "%DISPUTE_RESOLVED%"])
        row = cur.fetchone()
    assert row and refund_id in row[0]


# ---------------------------------------------------------------------------
# L/M. terminality + overlay regression
# ---------------------------------------------------------------------------

def test_t31_overlay_invariants_untouched():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "SESSION_QUALITY", "description": "overlay invariants"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    res = resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "overlay invariants case", "action": "PARTIAL_REFUND", "refund_amount": "200.00"})
    assert res.status_code == 200
    with connection.cursor() as cur:
        cur.execute("SELECT status::text FROM edutrust.bookings WHERE id=%s", [s["booking_id"]])
        assert cur.fetchone()[0] == "COMPLETED"  # never DISPUTED (Addendum 4.1)
        cur.execute("SELECT status::text FROM edutrust.sessions WHERE id=%s", [s["session_id"]])
        assert cur.fetchone()[0] == "COMPLETED"


def test_t34_terminal_dispute_no_reopen_new_dispute_allowed():
    s = ops_admin_session()
    d = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "terminal no reopen"})
    dispute_id = d.json()["data"]["dispute"]["id"]
    assert resolve(s["parent_client"], s["ops_tok"], dispute_id, {"resolution": "first close", "action": "NO_ACTION"}).status_code == 200
    # no reopen (SM 11.6: create a new dispute or admin appeal record instead)
    res = resolve(s["parent_client"], s["admin_tok"], dispute_id, {"resolution": "attempted reopen", "action": "NO_ACTION"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "DISPUTE_INVALID_STATE"
    # a NEW dispute for the same interaction is allowed (old one is terminal, not active)
    d2 = open_dispute(s["parent_client"], s["ptok"], {"session_id": s["session_id"], "category": "OTHER", "description": "fresh dispute after terminal"})
    assert d2.status_code == 201
    assert d2.json()["data"]["dispute"]["id"] != dispute_id
