from __future__ import annotations

from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from .audit import write_event, write_security_event
from .db import fetchone
from .errors import ApiError
from .permissions import require_roles
from .services import create_student, get_student, login, logout, register_user

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def health(request):
    return Response({"data": {"status": "ok"}, "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def ready(request):
    checks = {"database": False, "schema": False, "users_table": False}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            checks["database"] = cur.fetchone()[0] == 1
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name='edutrust')")
            checks["schema"] = bool(cur.fetchone()[0])
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='edutrust' AND table_name='users')")
            checks["users_table"] = bool(cur.fetchone()[0])
    except Exception:
        return Response({"data": {"status": "not_ready", "checks": checks}, "request_id": getattr(request, "request_id", None)}, status=503)
    status = "ready" if all(checks.values()) else "not_ready"
    return Response({"data": {"status": status, "checks": checks}, "request_id": getattr(request, "request_id", None)}, status=200 if status == "ready" else 503)

@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def register(request):
    data = register_user(request.data or {}, request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def login_view(request):
    identifier = request.data.get("identifier") or request.data.get("email") or request.data.get("phone_e164") or ""
    data = login(identifier, request.data.get("password") or "", request_id=getattr(request, "request_id", None), user_agent=request.headers.get("User-Agent"), ip_address=request.META.get("REMOTE_ADDR"))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
def logout_view(request):
    if not request.user or not request.user.is_authenticated:
        raise ApiError("AUTH_REQUIRED", "Authentication is required.", 401)
    logout(request.user.id, request.user.session_id, request_id=getattr(request, "request_id", None))
    return Response({"data": {"status": "logged_out"}, "request_id": getattr(request, "request_id", None)})

# ---- DEV Vertical Slice 10: R6 Auth completion views (VS10 R6 Authorization D1/D2) ----

@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def refresh_view(request):
    from .services import refresh_tokens
    # D1.1: single required field; the endpoint IS the re-authentication (no Bearer required).
    data = refresh_tokens(request.data.get("refresh_token") or "", request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
def revoke_sessions_view(request):
    from .services import revoke_sessions
    if not request.user or not request.user.is_authenticated:
        raise ApiError("AUTH_REQUIRED", "Authentication is required.", 401)
    # D2: self-service — the caller's own sessions only; the current session comes
    # from the verified JWT sid claim (server-derived), never from the request body.
    data = revoke_sessions(request.user.id, request.data.get("scope") or "", request.user.session_id, request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("PARENT")
def students_create(request):
    data = create_student(request.user.id, request.data or {}, request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["GET"])
@require_roles("PARENT")
def students_detail(request, student_id: str):
    data = get_student(request.user.id, student_id)
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@require_roles("ADMIN")
def admin_security_events(request):
    # Admin sensitive-ish operational read. Log audit/security event foundation.
    write_security_event("ADMIN_ACCESS", user_id=request.user.id, severity=2, metadata={"path": request.path, "request_id": getattr(request, "request_id", None)})
    write_event("ADMIN_ACTION", "security_events", None, actor_user_id=request.user.id, actor_role="ADMIN", request_id=getattr(request, "request_id", None), metadata={"action": "READ_SECURITY_EVENTS"})
    count = fetchone("SELECT count(*)::int AS count FROM edutrust.security_events")
    return Response({"data": {"count": count["count"]}, "request_id": getattr(request, "request_id", None)})

@api_view(["GET", "PATCH"])
@require_roles("TEACHER")
def teachers_me(request):
    from .services import current_teacher_profile, update_teacher_profile
    if request.method == "GET":
        return Response({"data": current_teacher_profile(request.user.id), "request_id": getattr(request, "request_id", None)})
    data = update_teacher_profile(request.user.id, request.data or {}, request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["POST", "GET"])
@require_roles("TEACHER")
def teacher_subjects(request):
    from .services import add_teacher_subject, list_teacher_subjects
    if request.method == "GET":
        return Response({"data": list_teacher_subjects(request.user.id), "request_id": getattr(request, "request_id", None)})
    return Response({"data": add_teacher_subject(request.user.id, request.data or {}, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["POST", "GET"])
@require_roles("TEACHER")
def teacher_availability_slots(request):
    from .services import create_availability_slot, list_teacher_availability
    if request.method == "GET":
        return Response({"data": list_teacher_availability(request.user.id), "request_id": getattr(request, "request_id", None)})
    return Response({"data": create_availability_slot(request.user.id, request.data or {}, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["POST"])
@require_roles("TEACHER")
def teacher_availability_block(request, slot_id: str):
    from .services import block_unblock_slot
    return Response({"data": block_unblock_slot(request.user.id, slot_id, True, (request.data or {}).get("reason"), request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("TEACHER")
def teacher_availability_unblock(request, slot_id: str):
    from .services import block_unblock_slot
    return Response({"data": block_unblock_slot(request.user.id, slot_id, False, (request.data or {}).get("reason"), request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def teachers_search(request):
    from .services import search_teachers
    return Response({"data": search_teachers(request.query_params), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
def teachers_match(request):
    from .services import search_teachers
    return Response({"data": search_teachers(request.data or {}), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def teacher_profile(request, teacher_id: str):
    from .services import teacher_public_profile
    return Response({"data": teacher_public_profile(teacher_id), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def teacher_trust_profile(request, teacher_id: str):
    from .services import teacher_public_profile
    p = teacher_public_profile(teacher_id)
    return Response({"data": {"teacher_id": teacher_id, "verification_status": p["verification_status"], "identity_verified": p["identity_verified"], "qualifications_verified": p["qualifications_verified"], "completed_sessions_count": p["completed_sessions_count"], "verified_rating": p.get("verified_rating"), "review_count": p.get("review_count"), "attendance_rate": p.get("attendance_rate"), "cancellation_rate": p.get("cancellation_rate")}, "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("PARENT")
def bookings_hold(request):
    from .services import hold_booking
    data = hold_booking(request.user.id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["POST"])
@require_roles("PARENT")
def bookings_confirm(request, booking_id: str):
    from .services import confirm_booking_dev_mock
    return Response({"data": confirm_booking_dev_mock(request.user.id, booking_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
def bookings_list(request):
    from .services import list_bookings_for_user
    return Response({"data": list_bookings_for_user(request.user.id, request.user.roles, request.query_params.get("scope")), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
def bookings_detail(request, booking_id: str):
    from .services import get_booking_for_user
    return Response({"data": get_booking_for_user(request.user.id, request.user.roles, booking_id), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("PARENT")
def payments_initiate(request):
    from .services import initiate_payment
    return Response({"data": initiate_payment(request.user.id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)}, status=201)

@api_view(["GET"])
def payments_detail(request, payment_id: str):
    from .services import get_payment_for_user
    return Response({"data": get_payment_for_user(request.user.id, request.user.roles, payment_id), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("PARENT", "ADMIN")
def payments_mock_succeed(request, payment_id: str):
    from .services import get_payment_for_user, process_mock_provider_event
    # parent/admin access check before DEV mock provider event
    get_payment_for_user(request.user.id, request.user.roles, payment_id)
    data = process_mock_provider_event(payment_id, "payment.confirmed", provider_event_id=(request.data or {}).get("provider_event_id"), force_session_failure=bool((request.data or {}).get("force_session_failure")), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("PARENT", "ADMIN")
def payments_mock_fail(request, payment_id: str):
    from .services import get_payment_for_user, process_mock_provider_event
    get_payment_for_user(request.user.id, request.user.roles, payment_id)
    data = process_mock_provider_event(payment_id, "payment.failed", provider_event_id=(request.data or {}).get("provider_event_id"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@require_roles("ADMIN")
def admin_payments(request):
    from .services import list_admin_payments
    return Response({"data": list_admin_payments(request.user.id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
@require_roles("ADMIN")
def admin_events(request):
    from .services import list_admin_events
    return Response({"data": list_admin_events(request.user.id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
def sessions_list(request):
    from .services import list_sessions_for_user
    return Response({"data": list_sessions_for_user(request.user.id, request.user.roles), "request_id": getattr(request, "request_id", None)})

@api_view(["GET"])
def sessions_detail(request, session_id: str):
    from .services import get_session_for_user
    return Response({"data": get_session_for_user(request.user.id, request.user.roles, session_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("TEACHER", "ADMIN")
def sessions_start(request, session_id: str):
    from .services import start_session
    return Response({"data": start_session(request.user.id, request.user.roles, session_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("TEACHER", "ADMIN")
def sessions_complete(request, session_id: str):
    from .services import complete_session
    return Response({"data": complete_session(request.user.id, request.user.roles, session_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["POST"])
@require_roles("TEACHER", "ADMIN")
def sessions_no_show(request, session_id: str):
    from .services import record_session_no_show
    return Response({"data": record_session_no_show(request.user.id, request.user.roles, session_id, (request.data or {}).get("no_show_type") or "STUDENT", request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

@api_view(["GET", "POST"])
def sessions_report(request, session_id: str):
    from .services import create_session_report, get_session_report_for_user
    if request.method == "GET":
        return Response({"data": get_session_report_for_user(request.user.id, request.user.roles, session_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})
    if "TEACHER" not in request.user.roles and "ADMIN" not in request.user.roles:
        from .errors import ApiError
        raise ApiError("FORBIDDEN", "Only the assigned teacher can create this report.", 403)
    return Response({"data": create_session_report(request.user.id, request.user.roles, session_id, request.data or {}, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)}, status=201)

# ---- Vertical Slice 4 views: verified review + basic dispute foundation ----

@api_view(["GET", "POST"])
@require_roles("PARENT", "TEACHER", "ADMIN", "OPS")
def sessions_review(request, session_id: str):
    from .services import create_review, get_review_for_session
    if request.method == "POST":
        if "PARENT" not in request.user.roles:
            from .errors import ApiError
            raise ApiError("FORBIDDEN", "Only the parent of this session can create a review.", 403)
        data = create_review(request.user.id, session_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
        return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)
    return Response({"data": get_review_for_session(request.user.id, request.user.roles, session_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("PARENT", "TEACHER", "ADMIN", "OPS")
def reviews_list(request):
    from .services import list_own_reviews
    return Response({"data": list_own_reviews(request.user.id, request.user.roles, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def teacher_reviews(request, teacher_id: str):
    from .services import list_teacher_public_reviews
    return Response({"data": list_teacher_public_reviews(teacher_id), "request_id": getattr(request, "request_id", None)})


@api_view(["GET", "POST"])
@require_roles("PARENT", "TEACHER", "ADMIN", "OPS")
def disputes(request):
    from .services import list_disputes_for_user, open_dispute
    if request.method == "POST":
        if "PARENT" not in request.user.roles and "TEACHER" not in request.user.roles:
            from .errors import ApiError
            raise ApiError("FORBIDDEN", "Only parents and teachers can open disputes.", 403)
        data = open_dispute(request.user.id, request.user.roles, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
        return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)
    if not ({"PARENT", "TEACHER", "ADMIN", "OPS"} & set(request.user.roles)):
        from .errors import ApiError
        raise ApiError("FORBIDDEN", "You do not have permission to view disputes.", 403)
    return Response({"data": list_disputes_for_user(request.user.id, request.user.roles, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("PARENT", "TEACHER", "ADMIN", "OPS")
def disputes_detail(request, dispute_id: str):
    from .services import get_dispute_for_user
    return Response({"data": get_dispute_for_user(request.user.id, request.user.roles, dispute_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

# ---- Vertical Slice 5 views: payout lifecycle (MANUAL_OPS / MOCK) ----

@api_view(["GET"])
@require_roles("TEACHER")
def teacher_payouts_list(request):
    from .services import list_payouts_for_teacher
    return Response({"data": list_payouts_for_teacher(request.user.id), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("TEACHER")
def teacher_payouts_detail(request, payout_id: str):
    from .services import get_payout_for_teacher
    return Response({"data": get_payout_for_teacher(request.user.id, payout_id), "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_payouts_process(request):
    from .services import create_and_process_payout
    data = create_and_process_payout(request.user.id, request.user.roles, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)


@api_view(["GET"])
@require_roles("OPS", "ADMIN")
def admin_payouts(request):
    from .services import list_admin_payouts
    return Response({"data": list_admin_payouts(request.user.id, request.user.roles, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})

# ---- Vertical Slice 6 views: review moderation ----

@api_view(["GET"])
@require_roles("SUPPORT", "OPS", "ADMIN")
def admin_reviews(request):
    from .services import list_admin_reviews
    return Response({"data": list_admin_reviews(request.user.id, request.user.roles, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_reviews_moderate(request, review_id: str):
    from .services import moderate_review
    data = moderate_review(request.user.id, request.user.roles, review_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

# ---- Vertical Slice 7 views: teacher verification ----

@api_view(["GET", "POST"])
@require_roles("TEACHER")
def teacher_verifications(request):
    from .services import list_verifications_for_teacher, submit_verification
    if request.method == "POST":
        data = submit_verification(request.user.id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
        return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)
    return Response({"data": list_verifications_for_teacher(request.user.id), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("OPS", "ADMIN")
def admin_teachers_pending_verification(request):
    from .services import list_pending_verifications
    return Response({"data": list_pending_verifications(request.user.id, request.user.roles, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("OPS", "ADMIN")
def admin_teacher_verifications(request, teacher_id: str):
    from .services import get_verifications_for_admin
    return Response({"data": get_verifications_for_admin(request.user.id, request.user.roles, teacher_id, request_id=getattr(request, "request_id", None)), "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_teacher_verify(request, teacher_id: str):
    from .services import review_verification
    data = review_verification(request.user.id, request.user.roles, teacher_id, (request.data or {}).get("verification_id"), "APPROVED", (request.data or {}).get("reviewer_note"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_teacher_reject(request, teacher_id: str):
    from .services import review_verification
    data = review_verification(request.user.id, request.user.roles, teacher_id, (request.data or {}).get("verification_id"), "REJECTED", (request.data or {}).get("rejection_reason"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

# ---- Vertical Slice 8 views: refund operations (DEV mock only) ----

@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def payments_refund(request, payment_id: str):
    from .services import create_refund
    data = create_refund(request.user.id, request.user.roles, payment_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)}, status=201)


@api_view(["GET"])
@require_roles("OPS", "ADMIN")
def admin_refunds(request):
    from .services import list_admin_refunds
    result = list_admin_refunds(request.user.id, request.user.roles, request.query_params, request_id=getattr(request, "request_id", None))
    return Response({"data": result["data"], "pagination": result["pagination"], "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("OPS", "ADMIN")
def admin_refund_detail(request, refund_id: str):
    from .services import get_admin_refund
    data = get_admin_refund(request.user.id, request.user.roles, refund_id, request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_approve(request, refund_id: str):
    from .services import approve_refund
    data = approve_refund(request.user.id, request.user.roles, refund_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_reject(request, refund_id: str):
    from .services import reject_refund
    data = reject_refund(request.user.id, request.user.roles, refund_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_cancel(request, refund_id: str):
    from .services import cancel_refund
    data = cancel_refund(request.user.id, request.user.roles, refund_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_mock_succeed(request, refund_id: str):
    from .services import process_mock_refund_result
    data = process_mock_refund_result(request.user.id, request.user.roles, refund_id, "succeeded", provider_event_id=(request.data or {}).get("provider_event_id"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_mock_fail(request, refund_id: str):
    from .services import process_mock_refund_result
    data = process_mock_refund_result(request.user.id, request.user.roles, refund_id, "failed", provider_event_id=(request.data or {}).get("provider_event_id"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_refund_reconcile(request, refund_id: str):
    from .services import reconcile_refund
    data = reconcile_refund(request.user.id, request.user.roles, refund_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})

# ---- Vertical Slice 9 views: dispute resolution (CORE) ----

@api_view(["POST"])
@require_roles("OPS", "ADMIN")
def admin_disputes_resolve(request, dispute_id: str):
    from .services import resolve_dispute
    data = resolve_dispute(request.user.id, request.user.roles, dispute_id, request.data or {}, request.headers.get("Idempotency-Key"), request_id=getattr(request, "request_id", None))
    return Response({"data": data, "request_id": getattr(request, "request_id", None)})


@api_view(["GET"])
@require_roles("SUPPORT", "OPS", "ADMIN")
def admin_disputes(request):
    from .services import list_admin_disputes
    result = list_admin_disputes(request.user.id, request.user.roles, request.query_params, request_id=getattr(request, "request_id", None))
    return Response({"data": result["data"], "pagination": result["pagination"], "request_id": getattr(request, "request_id", None)})
