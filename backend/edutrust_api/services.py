from __future__ import annotations

from datetime import timedelta
import uuid
from django.conf import settings
from django.utils import timezone

from .audit import write_event, write_security_event
from .auth import make_access_token
from .db import execute, fetchall, fetchone, tx
from .errors import ApiError
from .security import generate_token, hash_password, hash_token, verify_password

PUBLIC_REGISTRATION_ROLES = {"PARENT", "TEACHER"}


def get_roles(user_id: str) -> list[str]:
    return [r["role"] for r in fetchall("SELECT role::text AS role FROM edutrust.user_roles WHERE user_id = %s ORDER BY role", [user_id])]


def register_user(data: dict, request_id: str | None = None) -> dict:
    role = str(data.get("role") or "").upper()
    if role not in PUBLIC_REGISTRATION_ROLES:
        raise ApiError("VALIDATION_ERROR", "Public registration supports PARENT or TEACHER only.", 400, {"field": "role"})
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower() or None
    phone = (data.get("phone_e164") or "").strip() or None
    password = data.get("password") or ""
    if not full_name or (not email and not phone) or len(password) < 8:
        raise ApiError("VALIDATION_ERROR", "full_name, phone/email, and password are required.", 400)
    with tx():
        user = fetchone(
            """
            INSERT INTO edutrust.users (full_name, phone_e164, email, password_hash, preferred_locale)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text, full_name, email::text, phone_e164::text
            """,
            [full_name, phone, email, hash_password(password), data.get("preferred_locale") or "ar-DZ"],
        )
        execute("INSERT INTO edutrust.user_roles (user_id, role) VALUES (%s, %s)", [user["id"], role])
        if role == "PARENT":
            profile = fetchone("INSERT INTO edutrust.parent_profiles (user_id) VALUES (%s) RETURNING id::text", [user["id"]])
        else:
            profile = fetchone(
                "INSERT INTO edutrust.teacher_profiles (user_id, public_name) VALUES (%s, %s) RETURNING id::text",
                [user["id"], full_name],
            )
        write_event("USER_REGISTERED", "user", user["id"], actor_user_id=user["id"], actor_role=role, request_id=request_id, metadata={"role": role})
    return {"user_id": user["id"], "role": role, "profile_id": profile["id"]}


def login(identifier: str, password: str, request_id: str | None = None, user_agent: str | None = None, ip_address: str | None = None) -> dict:
    user = fetchone(
        """
        SELECT id::text, password_hash, status::text AS status
        FROM edutrust.users
        WHERE lower(email::text) = lower(%s) OR phone_e164::text = %s
        """,
        [identifier, identifier],
    )
    if not user or user["status"] != "ACTIVE" or not verify_password(password, user["password_hash"]):
        if user:
            write_security_event("LOGIN_FAILED", user_id=user["id"], severity=2, metadata={"request_id": request_id})
        raise ApiError("AUTH_INVALID_CREDENTIALS", "Invalid credentials.", 401)
    refresh_token = generate_token()
    expires_at = timezone.now() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    with tx():
        session = fetchone(
            """
            INSERT INTO edutrust.auth_sessions (user_id, refresh_token_hash, device_label, ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            [user["id"], hash_token(refresh_token), "DEV client", ip_address, user_agent, expires_at],
        )
        roles = get_roles(user["id"])
        execute("UPDATE edutrust.users SET last_login_at = now() WHERE id = %s", [user["id"]])
        write_event("USER_LOGIN", "auth_session", session["id"], actor_user_id=user["id"], actor_role=roles[0] if roles else None, request_id=request_id)
    return {"user_id": user["id"], "roles": roles, "access_token": make_access_token(user["id"], roles, session["id"]), "refresh_token": refresh_token, "expires_in": settings.JWT_ACCESS_TTL_SECONDS}


def logout(user_id: str, session_id: str, request_id: str | None = None):
    with tx():
        execute("UPDATE edutrust.auth_sessions SET revoked_at = now() WHERE id = %s AND user_id = %s AND revoked_at IS NULL", [session_id, user_id])
        write_security_event("TOKEN_REVOKED", user_id=user_id, severity=1, metadata={"request_id": request_id, "session_id": session_id})
        write_event("SECURITY_EVENT", "auth_session", session_id, actor_user_id=user_id, actor_role=None, request_id=request_id, metadata={"event": "TOKEN_REVOKED"})


def create_student(parent_user_id: str, data: dict, request_id: str | None = None) -> dict:
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id = %s", [parent_user_id])
    if not parent:
        raise ApiError("FORBIDDEN", "Parent profile is required.", 403)
    display_name = (data.get("display_name") or "").strip()
    if not display_name:
        raise ApiError("VALIDATION_ERROR", "display_name is required.", 400)
    with tx():
        student = fetchone(
            """
            INSERT INTO edutrust.student_profiles (parent_id, display_name, birth_year, academic_level_id, school_year, primary_goal, preferred_mode, consent_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 'GRANTED')::edutrust.consent_status)
            RETURNING id::text, display_name, status::text
            """,
            [parent["id"], display_name, data.get("birth_year"), data.get("academic_level_id"), data.get("school_year"), data.get("primary_goal"), data.get("preferred_mode"), data.get("consent_status")],
        )
        write_event("STUDENT_PROFILE_CREATED", "student", student["id"], actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id)
    return student


def get_student(parent_user_id: str, student_id: str) -> dict:
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id = %s", [parent_user_id])
    if not parent:
        raise ApiError("FORBIDDEN", "Parent profile is required.", 403)
    student = fetchone(
        """
        SELECT id::text, display_name, status::text, parent_id::text
        FROM edutrust.student_profiles
        WHERE id = %s AND parent_id = %s
        """,
        [student_id, parent["id"]],
    )
    if not student:
        raise ApiError("STUDENT_ACCESS_DENIED", "You do not have access to this student profile.", 403)
    return student

# ---- Vertical Slice 1 services ----
import hashlib
from datetime import datetime, timedelta, timezone as py_timezone
from decimal import Decimal


def current_teacher_profile(user_id: str) -> dict:
    teacher = fetchone(
        """
        SELECT id::text, user_id::text, public_name, bio, methodology, experience_years,
               languages, teaching_modes::text[] AS teaching_modes, base_wilaya_code, base_commune,
               service_area, verification_status::text AS verification_status, listing_status::text AS listing_status
        FROM edutrust.teacher_profiles WHERE user_id = %s
        """,
        [user_id],
    )
    if not teacher:
        raise ApiError("TEACHER_PROFILE_NOT_FOUND", "Teacher profile not found.", 404)
    return teacher


def update_teacher_profile(user_id: str, data: dict, request_id: str | None = None) -> dict:
    teacher = current_teacher_profile(user_id)
    allowed = {
        "public_name", "bio", "methodology", "experience_years", "languages", "teaching_modes",
        "base_wilaya_code", "base_commune", "service_area",
    }
    updates = {k: v for k, v in (data or {}).items() if k in allowed}
    if not updates:
        return teacher
    set_parts = []
    params = []
    for key, value in updates.items():
        if key == "teaching_modes":
            set_parts.append(f"{key} = %s::edutrust.teaching_mode[]")
        else:
            set_parts.append(f"{key} = %s")
        params.append(value)
    params.append(teacher["id"])
    with tx():
        updated = fetchone(
            f"""
            UPDATE edutrust.teacher_profiles
            SET {', '.join(set_parts)}
            WHERE id = %s
            RETURNING id::text, public_name, bio, methodology, experience_years,
                      languages, teaching_modes::text[] AS teaching_modes, base_wilaya_code, base_commune,
                      service_area, verification_status::text AS verification_status, listing_status::text AS listing_status
            """,
            params,
        )
        write_event("TEACHER_PROFILE_UPDATED", "teacher", updated["id"], actor_user_id=user_id, actor_role="TEACHER", request_id=request_id)
    return updated


def add_teacher_subject(user_id: str, data: dict, request_id: str | None = None) -> dict:
    teacher = current_teacher_profile(user_id)
    subject_id = data.get("subject_id")
    academic_level_id = data.get("academic_level_id")
    amount = data.get("price_amount") or (data.get("price") or {}).get("amount")
    duration = data.get("session_duration_minutes") or 60
    if not subject_id or not academic_level_id or not amount:
        raise ApiError("VALIDATION_ERROR", "subject_id, academic_level_id, and price amount are required.", 400)
    with tx():
        row = fetchone(
            """
            INSERT INTO edutrust.teacher_subjects (teacher_id, subject_id, academic_level_id, price_amount, session_duration_minutes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text, teacher_id::text, subject_id::text, academic_level_id::text, price_amount::text, currency, session_duration_minutes, is_active
            """,
            [teacher["id"], subject_id, academic_level_id, amount, duration],
        )
        write_event("TEACHER_PROFILE_UPDATED", "teacher_subject", row["id"], actor_user_id=user_id, actor_role="TEACHER", request_id=request_id)
    return row


def list_teacher_subjects(user_id: str) -> list[dict]:
    teacher = current_teacher_profile(user_id)
    return fetchall(
        """
        SELECT ts.id::text, ts.teacher_id::text, ts.subject_id::text, s.code AS subject_code, COALESCE(s.name_en, s.name_ar) AS subject_name,
               ts.academic_level_id::text, al.code AS academic_level_code, COALESCE(al.name_fr, al.name_ar) AS academic_level_name,
               ts.price_amount::text, ts.currency, ts.session_duration_minutes, ts.is_active
        FROM edutrust.teacher_subjects ts
        JOIN edutrust.subjects s ON s.id = ts.subject_id
        JOIN edutrust.academic_levels al ON al.id = ts.academic_level_id
        WHERE ts.teacher_id = %s
        ORDER BY s.code, al.sort_order
        """,
        [teacher["id"]],
    )


def create_availability_slot(user_id: str, data: dict, request_id: str | None = None) -> dict:
    teacher = current_teacher_profile(user_id)
    starts_at = data.get("starts_at") or data.get("starts_at_utc")
    ends_at = data.get("ends_at") or data.get("ends_at_utc")
    mode = data.get("mode") or "ONLINE"
    if not starts_at or not ends_at:
        raise ApiError("VALIDATION_ERROR", "starts_at and ends_at are required.", 400)
    with tx():
        row = fetchone(
            """
            INSERT INTO edutrust.availability_slots (teacher_id, starts_at, ends_at, mode, status)
            VALUES (%s, %s, %s, %s::edutrust.teaching_mode, 'AVAILABLE')
            RETURNING id::text, teacher_id::text, starts_at, ends_at, mode::text, status::text
            """,
            [teacher["id"], starts_at, ends_at, mode],
        )
        write_event("SLOT_CREATED", "availability_slot", row["id"], actor_user_id=user_id, actor_role="TEACHER", request_id=request_id)
    return row


def list_teacher_availability(user_id: str) -> list[dict]:
    teacher = current_teacher_profile(user_id)
    return fetchall(
        """
        SELECT id::text, teacher_id::text, starts_at, ends_at, mode::text, status::text, held_until
        FROM edutrust.availability_slots
        WHERE teacher_id = %s
        ORDER BY starts_at
        """,
        [teacher["id"]],
    )


def block_unblock_slot(user_id: str, slot_id: str, block: bool, reason: str | None, request_id: str | None = None) -> dict:
    teacher = current_teacher_profile(user_id)
    target_status = "BLOCKED" if block else "AVAILABLE"
    allowed_current = "AVAILABLE" if block else "BLOCKED"
    with tx():
        slot = fetchone("SELECT id::text, status::text FROM edutrust.availability_slots WHERE id=%s AND teacher_id=%s FOR UPDATE", [slot_id, teacher["id"]])
        if not slot:
            raise ApiError("RESOURCE_NOT_FOUND", "Availability slot not found.", 404)
        if slot["status"] != allowed_current:
            raise ApiError("INVALID_STATE_TRANSITION", "Slot cannot be updated from its current state.", 422, {"current_status": slot["status"]})
        row = fetchone(
            """
            UPDATE edutrust.availability_slots
            SET status=%s::edutrust.availability_slot_status, blocked_reason=%s, updated_at=now()
            WHERE id=%s
            RETURNING id::text, teacher_id::text, starts_at, ends_at, mode::text, status::text
            """,
            [target_status, reason, slot_id],
        )
        write_event("SLOT_BLOCKED" if block else "SLOT_UPDATED", "availability_slot", row["id"], actor_user_id=user_id, actor_role="TEACHER", request_id=request_id)
    return row


def teacher_public_profile(teacher_id: str) -> dict:
    teacher = fetchone(
        """
        SELECT tp.id::text, tp.public_name, tp.bio, tp.methodology, tp.experience_years,
               tp.languages, tp.teaching_modes::text[] AS teaching_modes, tp.service_area,
               tp.verification_status::text AS verification_status, tp.listing_status::text AS listing_status,
               COALESCE(tm.completed_sessions_count,0) AS completed_sessions_count,
               tm.attendance_rate::text, tm.cancellation_rate::text, tm.verified_rating::text, COALESCE(tm.review_count,0) AS review_count
        FROM edutrust.teacher_profiles tp
        LEFT JOIN edutrust.teacher_trust_metrics tm ON tm.teacher_id = tp.id
        WHERE tp.id = %s
        """,
        [teacher_id],
    )
    if not teacher:
        raise ApiError("RESOURCE_NOT_FOUND", "Teacher not found.", 404)
    teacher["subjects"] = fetchall(
        """
        SELECT ts.id::text AS teacher_subject_id, ts.subject_id::text, s.code AS subject_code, COALESCE(s.name_en, s.name_ar) AS subject_name,
               ts.academic_level_id::text, al.code AS academic_level_code, COALESCE(al.name_fr, al.name_ar) AS academic_level_name,
               ts.price_amount::text, ts.currency, ts.session_duration_minutes
        FROM edutrust.teacher_subjects ts
        JOIN edutrust.subjects s ON s.id = ts.subject_id
        JOIN edutrust.academic_levels al ON al.id = ts.academic_level_id
        WHERE ts.teacher_id=%s AND ts.is_active
        ORDER BY s.code, al.sort_order
        """,
        [teacher_id],
    )
    teacher["available_slots"] = fetchall(
        """
        SELECT id::text, starts_at, ends_at, mode::text, status::text
        FROM edutrust.availability_slots
        WHERE teacher_id=%s AND status='AVAILABLE' AND starts_at > now()
        ORDER BY starts_at LIMIT 10
        """,
        [teacher_id],
    )
    # VS7 (V4): additive per-type verified booleans (approved API 8.5 / PRD 8.4
    # shape). Existing fields preserved for backward compatibility.
    approved_types = {
        r["t"]
        for r in fetchall(
            "SELECT verification_type::text AS t FROM edutrust.teacher_verifications WHERE teacher_id=%s AND status='APPROVED'",
            [teacher_id],
        )
    }
    teacher["identity_verified"] = "IDENTITY" in approved_types
    teacher["qualifications_verified"] = "QUALIFICATION" in approved_types
    return teacher


def search_teachers(params: dict) -> list[dict]:
    subject_id = params.get("subject_id")
    academic_level_id = params.get("academic_level_id")
    mode = params.get("mode")
    where = ["ts.is_active", "avs.status='AVAILABLE'", "avs.starts_at > now()"]
    sql_params = []
    if subject_id:
        where.append("ts.subject_id=%s"); sql_params.append(subject_id)
    if academic_level_id:
        where.append("ts.academic_level_id=%s"); sql_params.append(academic_level_id)
    if mode:
        where.append("avs.mode=%s::edutrust.teaching_mode"); sql_params.append(mode)
    rows = fetchall(
        f"""
        SELECT DISTINCT ON (tp.id)
          tp.id::text AS teacher_id, tp.public_name, tp.verification_status::text AS verification_status, tp.listing_status::text AS listing_status,
          ts.id::text AS teacher_subject_id, ts.price_amount::text, ts.currency, ts.session_duration_minutes,
          s.code AS subject_code, al.code AS academic_level_code,
          avs.id::text AS slot_id, avs.starts_at, avs.ends_at, avs.mode::text,
          COALESCE(tm.completed_sessions_count,0) AS completed_sessions_count,
          tm.verified_rating::text AS verified_rating,
          COALESCE(tm.review_count,0) AS review_count,
          tm.attendance_rate::text AS attendance_rate
        FROM edutrust.teacher_profiles tp
        JOIN edutrust.teacher_subjects ts ON ts.teacher_id=tp.id
        JOIN edutrust.subjects s ON s.id=ts.subject_id
        JOIN edutrust.academic_levels al ON al.id=ts.academic_level_id
        JOIN edutrust.availability_slots avs ON avs.teacher_id=tp.id
        LEFT JOIN edutrust.teacher_trust_metrics tm ON tm.teacher_id=tp.id
        WHERE {' AND '.join(where)}
        ORDER BY tp.id, COALESCE(tm.completed_sessions_count,0) DESC, avs.starts_at ASC
        LIMIT 50
        """,
        sql_params,
    )
    for row in rows:
        reasons = []
        if subject_id: reasons.append(f"Matches requested subject {row['subject_code']}")
        if academic_level_id: reasons.append(f"Matches academic level {row['academic_level_code']}")
        if mode: reasons.append(f"Has available {mode} slot")
        if row.get("completed_sessions_count"): reasons.append(f"{row['completed_sessions_count']} verified sessions")
        row["recommendation_reasons"] = reasons or ["Has available tutoring slot"]
    return rows


def _idempotency_begin(scope: str, actor_user_id: str, key: str | None, request_hash: str, path: str) -> dict | None:
    if not key:
        raise ApiError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required.", 400)
    actor_key = f"user:{actor_user_id}"
    existing = fetchone(
        "SELECT id::text, request_hash, status::text, response_status, response_body, resource_id::text FROM edutrust.api_idempotency_keys WHERE scope=%s AND actor_key=%s AND idempotency_key=%s FOR UPDATE",
        [scope, actor_key, key],
    )
    if existing:
        if existing["request_hash"] != request_hash:
            raise ApiError("IDEMPOTENCY_KEY_CONFLICT", "Idempotency key was used with a different request.", 409)
        if existing["status"] == "COMPLETED":
            if isinstance(existing.get("response_body"), str):
                existing["response_body"] = __import__('json').loads(existing["response_body"])
            return existing
        raise ApiError("IDEMPOTENCY_REQUEST_PROCESSING", "This request is already processing.", 409)
    fetchone(
        """
        INSERT INTO edutrust.api_idempotency_keys (scope, idempotency_key, actor_user_id, actor_key, request_method, request_path, request_hash)
        VALUES (%s, %s, %s, %s, 'POST', %s, %s)
        RETURNING id::text
        """,
        [scope, key, actor_user_id, actor_key, path, request_hash],
    )
    return None


def _idempotency_complete(scope: str, actor_user_id: str, key: str, response_status: int, response_body: dict, resource_type: str, resource_id: str):
    from django.core.serializers.json import DjangoJSONEncoder
    execute(
        """
        UPDATE edutrust.api_idempotency_keys
        SET status='COMPLETED', response_status=%s, response_body=%s::jsonb, resource_type=%s, resource_id=%s
        WHERE scope=%s AND actor_key=%s AND idempotency_key=%s
        """,
        [response_status, __import__('json').dumps(response_body, cls=DjangoJSONEncoder), resource_type, resource_id, scope, f"user:{actor_user_id}", key],
    )


def hold_booking(parent_user_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    request_hash = hashlib.sha256(json.dumps(data or {}, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("booking_hold", parent_user_id, idempotency_key, request_hash, "/api/v1/bookings/hold")
        if replay:
            return replay["response_body"]
        parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [parent_user_id])
        if not parent:
            raise ApiError("FORBIDDEN", "Parent profile is required.", 403)
        student_id = data.get("student_id")
        slot_id = data.get("availability_slot_id")
        teacher_subject_id = data.get("teacher_subject_id")
        if not student_id or not slot_id or not teacher_subject_id:
            raise ApiError("VALIDATION_ERROR", "student_id, teacher_subject_id, and availability_slot_id are required.", 400)
        student = fetchone("SELECT id::text FROM edutrust.student_profiles WHERE id=%s AND parent_id=%s", [student_id, parent["id"]])
        if not student:
            raise ApiError("STUDENT_ACCESS_DENIED", "You do not have access to this student profile.", 403)
        offer = fetchone(
            """
            SELECT ts.id::text, ts.teacher_id::text, ts.subject_id::text, ts.academic_level_id::text, ts.price_amount, ts.currency, ts.session_duration_minutes,
                   avs.starts_at, avs.ends_at, avs.mode::text, avs.status::text
            FROM edutrust.teacher_subjects ts
            JOIN edutrust.availability_slots avs ON avs.teacher_id=ts.teacher_id
            WHERE ts.id=%s AND avs.id=%s AND ts.is_active
            """,
            [teacher_subject_id, slot_id],
        )
        if not offer:
            raise ApiError("BOOKING_SLOT_UNAVAILABLE", "The selected slot is no longer available.", 409)
        if offer["status"] != "AVAILABLE":
            raise ApiError("BOOKING_SLOT_UNAVAILABLE", "The selected slot is no longer available.", 409)
        booking = fetchone(
            """
            INSERT INTO edutrust.bookings (booking_number, parent_id, student_id, teacher_id, teacher_subject_id, subject_id, academic_level_id, availability_slot_id, scheduled_start, scheduled_end, mode, price_amount, currency, status, hold_expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::edutrust.teaching_mode, %s, %s, 'HELD', now() + (%s * interval '1 second'))
            RETURNING id::text, status::text, parent_id::text, student_id::text, teacher_id::text, availability_slot_id::text, scheduled_start, scheduled_end, price_amount::text, currency, hold_expires_at
            """,
            [f"B-{uuid.uuid4().hex[:10]}", parent["id"], student_id, offer["teacher_id"], teacher_subject_id, offer["subject_id"], offer["academic_level_id"], slot_id, offer["starts_at"], offer["ends_at"], offer["mode"], offer["price_amount"], offer["currency"], settings.BOOKING_HOLD_DURATION_SECONDS],
        )
        write_event("BOOKING_CREATED", "booking", booking["id"], actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id)
        write_event("BOOKING_HELD", "booking", booking["id"], actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id)
        response = {"booking": booking}
        _idempotency_complete("booking_hold", parent_user_id, idempotency_key, 201, response, "booking", booking["id"])
        return response



def confirm_booking_dev_mock(parent_user_id: str, booking_id: str, request_id: str | None = None) -> dict:
    """Deprecated DEV compatibility endpoint.

    Routes through the new payment initiation + mock provider event pathway so there
    is not a second booking/payment/session business logic path.
    """
    idem = f"dev-confirm-payment-{booking_id}"
    payment_response = initiate_payment(parent_user_id, {"booking_id": booking_id, "provider": "OTHER"}, idem, request_id=request_id)
    payment_id = payment_response["payment"]["id"]
    return process_mock_provider_event(payment_id, "payment.confirmed", provider_event_id=f"dev-confirm-event-{booking_id}", request_id=request_id)


def list_bookings_for_user(user_id: str, roles: list[str], scope: str | None = None) -> list[dict]:
    if scope == "teacher" or "TEACHER" in roles and scope != "parent":
        teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [user_id])
        if not teacher:
            return []
        return fetchall(
            """
            SELECT b.id::text, b.status::text, b.scheduled_start, b.scheduled_end, b.price_amount::text, b.currency,
                   sp.display_name AS student_display_name, b.teacher_id::text, b.parent_id::text
            FROM edutrust.bookings b JOIN edutrust.student_profiles sp ON sp.id=b.student_id
            WHERE b.teacher_id=%s ORDER BY b.scheduled_start DESC
            """,
            [teacher["id"]],
        )
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [user_id])
    if not parent:
        return []
    return fetchall(
        """
        SELECT b.id::text, b.status::text, b.scheduled_start, b.scheduled_end, b.price_amount::text, b.currency,
               tp.public_name AS teacher_name, b.teacher_id::text, b.student_id::text
        FROM edutrust.bookings b JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
        WHERE b.parent_id=%s ORDER BY b.scheduled_start DESC
        """,
        [parent["id"]],
    )


def get_booking_for_user(user_id: str, roles: list[str], booking_id: str) -> dict:
    row = fetchone(
        """
        SELECT b.id::text, b.status::text, b.parent_id::text, b.teacher_id::text, b.student_id::text, b.scheduled_start, b.scheduled_end,
               b.price_amount::text, b.currency, pp.user_id::text AS parent_user_id, tp.user_id::text AS teacher_user_id
        FROM edutrust.bookings b
        JOIN edutrust.parent_profiles pp ON pp.id=b.parent_id
        JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
        WHERE b.id=%s
        """,
        [booking_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Booking not found.", 404)
    if row["parent_user_id"] != user_id and row["teacher_user_id"] != user_id and "ADMIN" not in roles:
        raise ApiError("FORBIDDEN", "You do not have access to this booking.", 403)
    # VS8 (Addendum v1.1 section 8.2): refund_summary when applicable.
    refund_rows = fetchall(
        "SELECT status::text, approved_amount, currency FROM edutrust.refunds WHERE booking_id=%s ORDER BY created_at",
        [booking_id],
    )
    if refund_rows:
        total = sum((r["approved_amount"] for r in refund_rows if r["approved_amount"] is not None), Decimal("0"))
        active = next((r["status"] for r in reversed(refund_rows) if r["status"] in REFUND_ACTIVE_STATUSES), None)
        row["refund_summary"] = {
            "has_refund_activity": True,
            "active_refund_status": active,
            "total_approved_refund_amount": str(total.quantize(Decimal("0.01"))),
            "currency": "DZD",
        }
    return row


def expire_held_bookings() -> int:
    """Internal DEV/job helper for hold expiry. Safe to retry."""
    with tx():
        rows = fetchall(
            """
            SELECT id::text, availability_slot_id::text
            FROM edutrust.bookings
            WHERE status='HELD' AND hold_expires_at IS NOT NULL AND hold_expires_at < now()
            FOR UPDATE
            """
        )
        for row in rows:
            execute("UPDATE edutrust.bookings SET status='EXPIRED', updated_at=now() WHERE id=%s", [row["id"]])
            execute("UPDATE edutrust.availability_slots SET status='AVAILABLE', held_until=NULL, held_by_parent_id=NULL, updated_at=now() WHERE id=%s", [row["availability_slot_id"]])
        return len(rows)

# ---- Vertical Slice 2 payment lifecycle services (DEV mock only) ----

def _serialize_row(row: dict) -> dict:
    from django.core.serializers.json import DjangoJSONEncoder
    import json
    return json.loads(json.dumps(row, cls=DjangoJSONEncoder))


def _payment_response(payment: dict) -> dict:
    return {"payment": _serialize_row(payment)}


def initiate_payment(parent_user_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    booking_id = str(data.get("booking_id")) if data.get("booking_id") is not None else None
    provider = data.get("provider") or "OTHER"
    if provider != "OTHER":
        raise ApiError("PAYMENT_PROVIDER_NOT_AVAILABLE", "Only DEV mock payment provider is enabled.", 400)
    if not booking_id:
        raise ApiError("VALIDATION_ERROR", "booking_id is required.", 400)
    request_hash = hashlib.sha256(json.dumps({"booking_id": booking_id, "provider": provider}, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("payment_initiate", parent_user_id, idempotency_key, request_hash, "/api/v1/payments/initiate")
        if replay:
            return replay["response_body"]
        booking = fetchone(
            """
            SELECT b.*, b.id::text AS id_text, pp.user_id::text AS parent_user_id
            FROM edutrust.bookings b JOIN edutrust.parent_profiles pp ON pp.id=b.parent_id
            WHERE b.id=%s FOR UPDATE
            """,
            [booking_id],
        )
        if not booking or booking["parent_user_id"] != parent_user_id:
            raise ApiError("RESOURCE_NOT_FOUND", "Booking not found.", 404)
        if str(booking["status"]) not in ("HELD", "PAYMENT_PENDING"):
            raise ApiError("INVALID_STATE_TRANSITION", "Payment cannot be initiated for this booking state.", 422, {"booking_status": str(booking["status"])})
        if booking["hold_expires_at"] is not None and booking["hold_expires_at"] <= timezone.now():
            execute("UPDATE edutrust.bookings SET status='EXPIRED', updated_at=now() WHERE id=%s", [booking_id])
            raise ApiError("BOOKING_HOLD_EXPIRED", "The booking hold has expired.", 409)
        existing = fetchone(
            """
            SELECT id::text, booking_id::text, parent_id::text, provider::text, provider_transaction_id, amount::text, currency, status::text, initiated_at, confirmed_at, failed_at
            FROM edutrust.payments
            WHERE booking_id=%s AND status IN ('INITIATED','PENDING')
            ORDER BY created_at DESC LIMIT 1
            """,
            [booking_id],
        )
        if existing:
            response = _payment_response(existing)
            _idempotency_complete("payment_initiate", parent_user_id, idempotency_key, 200, response, "payment", existing["id"])
            return response
        payment = fetchone(
            """
            INSERT INTO edutrust.payments (booking_id, parent_id, provider, idempotency_key, amount, currency, status, raw_provider_payload)
            VALUES (%s, %s, 'OTHER', %s, %s, %s, 'PENDING', %s::jsonb)
            RETURNING id::text, booking_id::text, parent_id::text, provider::text, provider_transaction_id, amount::text, currency, status::text, initiated_at, confirmed_at, failed_at
            """,
            [booking_id, booking["parent_id"], idempotency_key, booking["price_amount"], booking["currency"], '{"provider":"MockPaymentProvider","phase":"initiate"}'],
        )
        execute("UPDATE edutrust.bookings SET status='PAYMENT_PENDING', updated_at=now() WHERE id=%s", [booking_id])
        write_event("PAYMENT_INITIATED", "payment", payment["id"], actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id, metadata={"dev_mock": True})
        response = _payment_response(payment)
        _idempotency_complete("payment_initiate", parent_user_id, idempotency_key, 201, response, "payment", payment["id"])
        return response


def get_payment_for_user(user_id: str, roles: list[str], payment_id: str) -> dict:
    payment = fetchone(
        """
        SELECT p.id::text, p.booking_id::text, p.parent_id::text, p.provider::text, p.provider_transaction_id, p.amount::text, p.currency, p.status::text,
               p.initiated_at, p.confirmed_at, p.failed_at, b.status::text AS booking_status, pp.user_id::text AS parent_user_id
        FROM edutrust.payments p
        JOIN edutrust.bookings b ON b.id=p.booking_id
        JOIN edutrust.parent_profiles pp ON pp.id=p.parent_id
        WHERE p.id=%s
        """,
        [payment_id],
    )
    if not payment:
        raise ApiError("RESOURCE_NOT_FOUND", "Payment not found.", 404)
    if payment["parent_user_id"] != user_id and "ADMIN" not in roles:
        raise ApiError("FORBIDDEN", "You do not have access to this payment.", 403)
    payment["provider_events"] = fetchall(
        """
        SELECT id::text, provider::text, provider_event_id, provider_transaction_id, event_type, status::text, received_at, processed_at
        FROM edutrust.payment_provider_events WHERE payment_id=%s ORDER BY received_at
        """,
        [payment_id],
    ) if "ADMIN" in roles else []
    # VS8 (Addendum v1.1 section 8.1): refunds[] summary when refund activity exists.
    refunds = fetchall(
        """
        SELECT id::text AS refund_id, status::text, refund_type::text, requested_amount::text, approved_amount::text,
               currency, reason, created_at, approved_at, provider_submitted_at, completed_at
        FROM edutrust.refunds WHERE payment_id=%s ORDER BY created_at
        """,
        [payment_id],
    )
    if refunds:
        payment["refunds"] = _serialize_row_rows(refunds)
    return payment


def _create_parent_payment_ledger(payment: dict, booking: dict, *, late_payment: bool = False):
    amount = Decimal(str(payment["amount"]))
    if late_payment:
        tx = fetchone(
            """
            INSERT INTO edutrust.ledger_transactions (transaction_type, status, booking_id, payment_id, reference)
            VALUES ('PARENT_PAYMENT','POSTED',%s,%s,'late-payment-refund-liability') RETURNING id::text
            """,
            [booking["id"], payment["id"]],
        )
        execute("INSERT INTO edutrust.ledger_entries (ledger_transaction_id, account_type, direction, amount, memo) VALUES (%s,'PAYMENT_PROVIDER_CLEARING','DEBIT',%s,'late payment received'),(%s,'REFUND_PAYABLE','CREDIT',%s,'late payment refund liability')", [tx["id"], amount, tx["id"], amount])
        return tx
    commission = (amount * Decimal(str(booking["platform_commission_bps"])) / Decimal("10000")).quantize(Decimal("0.01"))
    teacher_payable = amount - commission
    tx = fetchone(
        """
        INSERT INTO edutrust.ledger_transactions (transaction_type, status, booking_id, payment_id, reference)
        VALUES ('PARENT_PAYMENT','POSTED',%s,%s,'mock-payment-confirmed') RETURNING id::text
        """,
        [booking["id"], payment["id"]],
    )
    execute(
        """
        INSERT INTO edutrust.ledger_entries (ledger_transaction_id, account_type, direction, amount, memo)
        VALUES (%s,'PAYMENT_PROVIDER_CLEARING','DEBIT',%s,'mock payment received'),
               (%s,'TEACHER_PAYABLE','CREDIT',%s,'teacher payable'),
               (%s,'PLATFORM_REVENUE','CREDIT',%s,'platform commission')
        """,
        [tx["id"], amount, tx["id"], teacher_payable, tx["id"], commission],
    )
    return tx


def process_mock_provider_event(payment_id: str, event_type: str, provider_event_id: str | None = None, force_session_failure: bool = False, request_id: str | None = None) -> dict:
    if not settings.MOCK_PAYMENT_PROVIDER_ENABLED or settings.REAL_PAYMENT_ENABLED:
        raise ApiError("FORBIDDEN", "Mock provider controls are DEV-only.", 403)
    if event_type not in ("payment.confirmed", "payment.failed"):
        raise ApiError("VALIDATION_ERROR", "Unsupported mock event type.", 400)
    provider_event_id = provider_event_id or f"mock_evt_{uuid.uuid4()}"
    with tx():
        existing_event = fetchone(
            "SELECT id::text, status::text, payment_id::text FROM edutrust.payment_provider_events WHERE provider='OTHER' AND provider_event_id=%s FOR UPDATE",
            [provider_event_id],
        )
        if existing_event and existing_event["status"] == "PROCESSED":
            payment = fetchone("SELECT id::text, booking_id::text, status::text FROM edutrust.payments WHERE id=%s", [existing_event["payment_id"]])
            sessions = fetchall("SELECT id::text, status::text FROM edutrust.sessions WHERE booking_id=(SELECT booking_id FROM edutrust.payments WHERE id=%s)", [existing_event["payment_id"]])
            return {"duplicate": True, "provider_event_id": provider_event_id, "payment": payment, "sessions": sessions}
        payment = fetchone(
            """
            SELECT p.*, p.id::text AS id_text, b.id::text AS booking_id_text, b.status::text AS booking_status, b.hold_expires_at,
                   b.parent_id, b.student_id, b.teacher_id, b.subject_id, b.academic_level_id, b.scheduled_start, b.scheduled_end, b.platform_commission_bps, b.availability_slot_id::text
            FROM edutrust.payments p JOIN edutrust.bookings b ON b.id=p.booking_id
            WHERE p.id=%s FOR UPDATE
            """,
            [payment_id],
        )
        if not payment:
            raise ApiError("RESOURCE_NOT_FOUND", "Payment not found.", 404)
        if existing_event and existing_event["status"] == "FAILED":
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSING', processing_attempts=processing_attempts+1, updated_at=now() WHERE id=%s", [existing_event["id"]])
            event_id = existing_event["id"]
        elif not existing_event:
            ev = fetchone(
                """
                INSERT INTO edutrust.payment_provider_events (provider, provider_event_id, provider_transaction_id, event_type, status, payment_id, amount, currency, normalized_payload)
                VALUES ('OTHER', %s, %s, %s, 'RECEIVED', %s, %s, %s, %s::jsonb)
                RETURNING id::text
                """,
                [provider_event_id, f"mock_tx_{payment_id}", event_type, payment_id, payment["amount"], payment["currency"], '{"provider":"MockPaymentProvider"}'],
            )
            event_id = ev["id"]
            write_event("PAYMENT_PROVIDER_EVENT_RECEIVED" if False else "PAYMENT_INITIATED", "payment_provider_event", event_id, request_id=request_id, metadata={"event_type": event_type, "dev_mock": True})
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSING', processing_attempts=processing_attempts+1, updated_at=now() WHERE id=%s", [event_id])
        else:
            raise ApiError("PAYMENT_PROVIDER_EVENT_IN_PROGRESS", "Provider event is already being processed or rejected.", 409)

        if event_type == "payment.failed":
            execute("UPDATE edutrust.payments SET status='FAILED', failed_at=now(), provider_transaction_id=%s, updated_at=now() WHERE id=%s", [f"mock_tx_{payment_id}", payment_id])
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSED', processed_at=now(), updated_at=now() WHERE id=%s", [event_id])
            write_event("PAYMENT_FAILED", "payment", payment_id, request_id=request_id, metadata={"provider_event_id": provider_event_id, "dev_mock": True})
            return {"duplicate": False, "provider_event_id": provider_event_id, "payment_status": "FAILED", "booking_status": payment["booking_status"], "session_id": None}

        # payment.confirmed
        unfulfillable = payment["booking_status"] in ("EXPIRED", "CANCELLED") or (payment["hold_expires_at"] is not None and payment["hold_expires_at"] <= timezone.now())
        execute("UPDATE edutrust.payments SET status='CONFIRMED', confirmed_at=now(), provider_transaction_id=%s, updated_at=now() WHERE id=%s", [f"mock_tx_{payment_id}", payment_id])
        confirmed_payment = {"id": payment_id, "amount": payment["amount"]}
        booking_for_ledger = {"id": payment["booking_id_text"], "platform_commission_bps": payment["platform_commission_bps"]}
        if unfulfillable:
            if payment["booking_status"] not in ("EXPIRED", "CANCELLED"):
                execute("UPDATE edutrust.bookings SET status='EXPIRED', updated_at=now() WHERE id=%s", [payment["booking_id"]])
            _create_parent_payment_ledger(confirmed_payment, booking_for_ledger, late_payment=True)
            refund = fetchone(
                """
                INSERT INTO edutrust.refunds (payment_id, booking_id, provider, refund_type, status, requested_amount, currency, reason, reason_code, idempotency_key, requested_by_user_id)
                VALUES (%s,%s,'OTHER','FULL','REQUESTED',%s,%s,'Late payment after booking expiry','LATE_PAYMENT_AFTER_EXPIRY',%s,NULL)
                RETURNING id::text, status::text
                """,
                [payment_id, payment["booking_id"], payment["amount"], payment["currency"], f"late-refund-{payment_id}"],
            )
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSED', processed_at=now(), updated_at=now() WHERE id=%s", [event_id])
            write_event("PAYMENT_CONFIRMED", "payment", payment_id, request_id=request_id, metadata={"late_payment": True, "dev_mock": True})
            write_event("PAYMENT_RECONCILIATION_REQUIRED", "payment", payment_id, request_id=request_id, metadata={"refund_id": refund["id"], "dev_mock": True})
            write_event("REFUND_REQUESTED", "refund", refund["id"], request_id=request_id, metadata={"late_payment": True})
            return {"duplicate": False, "provider_event_id": provider_event_id, "payment_status": "CONFIRMED", "booking_status": "EXPIRED", "session_id": None, "refund_id": refund["id"], "reconciliation_required": True}

        if payment["booking_status"] != "PAYMENT_PENDING":
            raise ApiError("INVALID_STATE_TRANSITION", "Payment cannot confirm booking from current state.", 422, {"booking_status": payment["booking_status"]})
        execute("UPDATE edutrust.bookings SET status='BOOKED', updated_at=now() WHERE id=%s", [payment["booking_id"]])
        if force_session_failure:
            raise ApiError("FORCED_SESSION_FAILURE", "Forced session creation failure for atomicity test.", 500)
        session = fetchone(
            """
            INSERT INTO edutrust.sessions (booking_id, parent_id, student_id, teacher_id, subject_id, academic_level_id, scheduled_start, scheduled_end, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'SCHEDULED')
            RETURNING id::text, status::text
            """,
            [payment["booking_id"], payment["parent_id"], payment["student_id"], payment["teacher_id"], payment["subject_id"], payment["academic_level_id"], payment["scheduled_start"], payment["scheduled_end"]],
        )
        _create_parent_payment_ledger(confirmed_payment, booking_for_ledger, late_payment=False)
        execute("UPDATE edutrust.payment_provider_events SET status='PROCESSED', processed_at=now(), updated_at=now() WHERE id=%s", [event_id])
        write_event("PAYMENT_CONFIRMED", "payment", payment_id, request_id=request_id, metadata={"provider_event_id": provider_event_id, "dev_mock": True})
        write_event("BOOKING_CONFIRMED", "booking", payment["booking_id"], request_id=request_id, metadata={"session_id": session["id"], "dev_mock": True})
        return {"duplicate": False, "provider_event_id": provider_event_id, "payment_status": "CONFIRMED", "booking_status": "BOOKED", "session_id": session["id"], "session_status": session["status"]}



def list_admin_payments(admin_user_id: str, request_id: str | None = None) -> list[dict]:
    write_event("ADMIN_ACTION", "payments", None, actor_user_id=admin_user_id, actor_role="ADMIN", request_id=request_id, metadata={"action": "READ_ADMIN_PAYMENTS"})
    return fetchall(
        """
        SELECT p.id::text, p.booking_id::text, p.provider::text, p.provider_transaction_id, p.amount::text, p.currency, p.status::text,
               p.initiated_at, p.confirmed_at, p.failed_at, b.status::text AS booking_status,
               COUNT(ppe.id)::int AS provider_event_count
        FROM edutrust.payments p
        JOIN edutrust.bookings b ON b.id=p.booking_id
        LEFT JOIN edutrust.payment_provider_events ppe ON ppe.payment_id=p.id
        GROUP BY p.id, b.status
        ORDER BY p.created_at DESC
        LIMIT 100
        """
    )


def list_admin_events(admin_user_id: str, request_id: str | None = None) -> list[dict]:
    write_event("ADMIN_ACTION", "event_ledger", None, actor_user_id=admin_user_id, actor_role="ADMIN", request_id=request_id, metadata={"action": "READ_EVENT_LEDGER"})
    return fetchall(
        """
        SELECT id::text, event_type::text, entity_type, entity_id::text, actor_user_id::text, created_at, metadata
        FROM edutrust.event_ledger
        ORDER BY created_at DESC
        LIMIT 100
        """
    )

# ---- Vertical Slice 3 session execution / report services ----

def _session_access_row(session_id: str) -> dict:
    row = fetchone(
        """
        SELECT s.id::text, s.booking_id::text, s.parent_id::text, s.student_id::text, s.teacher_id::text,
               s.subject_id::text, s.academic_level_id::text, s.scheduled_start, s.scheduled_end,
               s.actual_start, s.actual_end, s.status::text, s.attendance_status::text,
               pp.user_id::text AS parent_user_id, tp.user_id::text AS teacher_user_id,
               b.status::text AS booking_status
        FROM edutrust.sessions s
        JOIN edutrust.parent_profiles pp ON pp.id=s.parent_id
        JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
        JOIN edutrust.bookings b ON b.id=s.booking_id
        WHERE s.id=%s
        """,
        [session_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
    return row


def _can_access_session(user_id: str, roles: list[str], row: dict) -> bool:
    return row["parent_user_id"] == user_id or row["teacher_user_id"] == user_id or "ADMIN" in roles or "OPS" in roles


def get_session_for_user(user_id: str, roles: list[str], session_id: str, request_id: str | None = None) -> dict:
    row = _session_access_row(session_id)
    if not _can_access_session(user_id, roles, row):
        raise ApiError("FORBIDDEN", "You do not have access to this session.", 403)
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "session", session_id, actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_SESSION"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "session", "entity_id": session_id, "request_id": request_id})
    return row


def list_sessions_for_user(user_id: str, roles: list[str]) -> list[dict]:
    if "ADMIN" in roles or "OPS" in roles:
        return fetchall("SELECT id::text, booking_id::text, student_id::text, teacher_id::text, scheduled_start, scheduled_end, actual_start, actual_end, status::text, attendance_status::text FROM edutrust.sessions ORDER BY scheduled_start DESC LIMIT 100")
    if "TEACHER" in roles:
        teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [user_id])
        if not teacher:
            return []
        return fetchall("SELECT id::text, booking_id::text, student_id::text, teacher_id::text, scheduled_start, scheduled_end, actual_start, actual_end, status::text, attendance_status::text FROM edutrust.sessions WHERE teacher_id=%s ORDER BY scheduled_start DESC", [teacher["id"]])
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [user_id])
    if not parent:
        return []
    return fetchall("SELECT id::text, booking_id::text, student_id::text, teacher_id::text, scheduled_start, scheduled_end, actual_start, actual_end, status::text, attendance_status::text FROM edutrust.sessions WHERE parent_id=%s ORDER BY scheduled_start DESC", [parent["id"]])


def start_session(user_id: str, roles: list[str], session_id: str, request_id: str | None = None) -> dict:
    with tx():
        row = fetchone(
            """
            SELECT s.id::text, s.teacher_id::text, s.status::text, s.actual_start, tp.user_id::text AS teacher_user_id
            FROM edutrust.sessions s JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
            WHERE s.id=%s FOR UPDATE
            """,
            [session_id],
        )
        if not row:
            raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
        is_admin = "ADMIN" in roles or "OPS" in roles
        if row["teacher_user_id"] != user_id and not is_admin:
            raise ApiError("FORBIDDEN", "Only the assigned teacher can start this session.", 403)
        if row["status"] == "STARTED":
            return get_session_for_user(user_id, roles, session_id, request_id=request_id)
        if row["status"] != "SCHEDULED":
            raise ApiError("INVALID_STATE_TRANSITION", "Only scheduled sessions can be started.", 422, {"session_status": row["status"]})
        updated = fetchone("UPDATE edutrust.sessions SET status='STARTED', actual_start=COALESCE(actual_start, now()), updated_at=now() WHERE id=%s RETURNING id::text, status::text, actual_start, attendance_status::text", [session_id])
        write_event("SESSION_STARTED", "session", session_id, actor_user_id=user_id, actor_role="ADMIN" if is_admin else "TEACHER", request_id=request_id)
        return updated


def complete_session(user_id: str, roles: list[str], session_id: str, request_id: str | None = None) -> dict:
    with tx():
        row = fetchone(
            """
            SELECT s.id::text, s.teacher_id::text, s.status::text, s.actual_start, tp.user_id::text AS teacher_user_id
            FROM edutrust.sessions s JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
            WHERE s.id=%s FOR UPDATE
            """,
            [session_id],
        )
        if not row:
            raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
        is_admin = "ADMIN" in roles or "OPS" in roles
        if row["teacher_user_id"] != user_id and not is_admin:
            raise ApiError("FORBIDDEN", "Only the assigned teacher can complete this session.", 403)
        if row["status"] == "COMPLETED":
            return get_session_for_user(user_id, roles, session_id, request_id=request_id)
        if row["status"] != "STARTED":
            raise ApiError("INVALID_STATE_TRANSITION", "Only started sessions can be completed.", 422, {"session_status": row["status"]})
        updated = fetchone(
            """
            UPDATE edutrust.sessions
            SET status='COMPLETED', actual_end=now(), attendance_status='PRESENT', updated_at=now()
            WHERE id=%s
            RETURNING id::text, status::text, actual_start, actual_end, attendance_status::text, booking_id::text
            """,
            [session_id],
        )
        write_event("SESSION_COMPLETED", "session", session_id, actor_user_id=user_id, actor_role="ADMIN" if is_admin else "TEACHER", request_id=request_id, metadata={"attendance_status": "PRESENT"})
        return updated


def record_session_no_show(user_id: str, roles: list[str], session_id: str, no_show_type: str, request_id: str | None = None) -> dict:
    no_show_type = (no_show_type or "STUDENT").upper()
    if no_show_type not in ("STUDENT", "TEACHER"):
        raise ApiError("VALIDATION_ERROR", "no_show_type must be STUDENT or TEACHER.", 400)
    with tx():
        row = fetchone(
            """
            SELECT s.id::text, s.teacher_id::text, s.status::text, tp.user_id::text AS teacher_user_id
            FROM edutrust.sessions s JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
            WHERE s.id=%s FOR UPDATE
            """,
            [session_id],
        )
        if not row:
            raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
        is_admin = "ADMIN" in roles or "OPS" in roles
        if no_show_type == "STUDENT":
            if row["teacher_user_id"] != user_id and not is_admin:
                raise ApiError("FORBIDDEN", "Only the assigned teacher or admin can record student no-show.", 403)
            status = "NO_SHOW_STUDENT"; attendance = "STUDENT_ABSENT"
        else:
            if not is_admin:
                raise ApiError("FORBIDDEN", "Teacher no-show requires admin/ops authority.", 403)
            status = "NO_SHOW_TEACHER"; attendance = "TEACHER_ABSENT"
        if row["status"] in ("COMPLETED", "NO_SHOW_STUDENT", "NO_SHOW_TEACHER", "CANCELLED"):
            raise ApiError("INVALID_STATE_TRANSITION", "No-show cannot be recorded for the current session state.", 422, {"session_status": row["status"]})
        updated = fetchone("UPDATE edutrust.sessions SET status=%s::edutrust.session_status, attendance_status=%s::edutrust.attendance_status, updated_at=now() WHERE id=%s RETURNING id::text, status::text, attendance_status::text", [status, attendance, session_id])
        write_event("SESSION_NO_SHOW", "session", session_id, actor_user_id=user_id, actor_role="ADMIN" if is_admin else "TEACHER", request_id=request_id, metadata={"no_show_type": no_show_type, "attendance_status": attendance})
        return updated


def create_session_report(user_id: str, roles: list[str], session_id: str, data: dict, request_id: str | None = None) -> dict:
    topics = data.get("topics_covered") or []
    skills = data.get("skills_practiced") or []
    next_objectives = data.get("next_objectives") or []
    participation = data.get("participation")
    with tx():
        session = fetchone(
            """
            SELECT s.id::text, s.status::text, s.teacher_id::text, s.student_id::text, s.subject_id::text, tp.user_id::text AS teacher_user_id
            FROM edutrust.sessions s JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
            WHERE s.id=%s FOR UPDATE
            """,
            [session_id],
        )
        if not session:
            raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
        is_admin = "ADMIN" in roles or "OPS" in roles
        if session["teacher_user_id"] != user_id and not is_admin:
            raise ApiError("FORBIDDEN", "Only the assigned teacher can create this report.", 403)
        if session["status"] != "COMPLETED":
            raise ApiError("INVALID_STATE_TRANSITION", "Report can only be created for a completed session.", 422, {"session_status": session["status"]})
        existing = fetchone("SELECT id::text FROM edutrust.session_reports WHERE session_id=%s", [session_id])
        if existing:
            raise ApiError("DUPLICATE_REPORT", "A report already exists for this session.", 409)
        report = fetchone(
            """
            INSERT INTO edutrust.session_reports (session_id, teacher_id, student_id, subject_id, topics_covered, skills_practiced, participation, teacher_observations, homework, recommended_revision, next_objectives, progress_indicator)
            VALUES (%s,%s,%s,%s,%s,%s,%s::edutrust.participation_level,%s,%s,%s,%s,%s)
            RETURNING id::text, session_id::text, teacher_id::text, student_id::text, subject_id::text, topics_covered, skills_practiced, participation::text, teacher_observations, homework, recommended_revision, next_objectives, progress_indicator, created_at
            """,
            [session_id, session["teacher_id"], session["student_id"], session["subject_id"], topics, skills, participation, data.get("teacher_observations"), data.get("homework"), data.get("recommended_revision"), next_objectives, data.get("progress_indicator")],
        )
        progress_count = 0
        for topic in topics:
            execute("INSERT INTO edutrust.student_progress_events (student_id, session_id, report_id, subject_id, event_type, source_type, topic, created_by_user_id) VALUES (%s,%s,%s,%s,'TOPIC_COVERED','TEACHER_REPORT',%s,%s)", [session["student_id"], session_id, report["id"], session["subject_id"], topic, user_id]); progress_count += 1
        for skill in skills:
            execute("INSERT INTO edutrust.student_progress_events (student_id, session_id, report_id, subject_id, event_type, source_type, topic, created_by_user_id) VALUES (%s,%s,%s,%s,'SKILL_PRACTICED','TEACHER_REPORT',%s,%s)", [session["student_id"], session_id, report["id"], session["subject_id"], skill, user_id]); progress_count += 1
        if data.get("homework"):
            execute("INSERT INTO edutrust.student_progress_events (student_id, session_id, report_id, subject_id, event_type, source_type, note, created_by_user_id) VALUES (%s,%s,%s,%s,'HOMEWORK_ASSIGNED','TEACHER_REPORT',%s,%s)", [session["student_id"], session_id, report["id"], session["subject_id"], data.get("homework"), user_id]); progress_count += 1
        for note in [data.get("teacher_observations"), data.get("recommended_revision")] + list(next_objectives):
            if note:
                execute("INSERT INTO edutrust.student_progress_events (student_id, session_id, report_id, subject_id, event_type, source_type, note, created_by_user_id) VALUES (%s,%s,%s,%s,'PROGRESS_NOTE','TEACHER_REPORT',%s,%s)", [session["student_id"], session_id, report["id"], session["subject_id"], note, user_id]); progress_count += 1
        write_event("REPORT_CREATED", "session_report", report["id"], actor_user_id=user_id, actor_role="ADMIN" if is_admin else "TEACHER", request_id=request_id, metadata={"session_id": session_id, "progress_events_created": progress_count})
        report["progress_events_created"] = progress_count
        return report


def get_session_report_for_user(user_id: str, roles: list[str], session_id: str, request_id: str | None = None) -> dict:
    session = _session_access_row(session_id)
    if not _can_access_session(user_id, roles, session):
        raise ApiError("FORBIDDEN", "You do not have access to this session report.", 403)
    report = fetchone(
        """
        SELECT id::text, session_id::text, teacher_id::text, student_id::text, subject_id::text, topics_covered, skills_practiced, participation::text, teacher_observations, homework, recommended_revision, next_objectives, progress_indicator, created_at
        FROM edutrust.session_reports WHERE session_id=%s
        """,
        [session_id],
    )
    if not report:
        raise ApiError("RESOURCE_NOT_FOUND", "Session report not found.", 404)
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "session_report", report["id"], actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_SESSION_REPORT"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "session_report", "entity_id": report["id"], "request_id": request_id})
    report["progress_events"] = fetchall("SELECT id::text, event_type::text, topic, note, session_id::text, report_id::text, created_at FROM edutrust.student_progress_events WHERE report_id=%s ORDER BY created_at, id", [report["id"]])
    return report


# ---- Vertical Slice 4 verified review + basic dispute foundation services ----
#
# Baselines implemented here (no new business rules):
# - State Machines v1.0 section 10 (Review State Machine): eligibility =
#   session COMPLETED + booking COMPLETED + payment CONFIRMED + one review per
#   session + reviewer is the parent of the student + not the teacher.
#   Duplicate -> 409 DUPLICATE_REVIEW. Eligibility failure -> 422
#   REVIEW_NOT_ELIGIBLE.
# - State Machines v1.1 Addendum section 4 (Dispute Overlay Model): a dispute
#   is a procedural overlay. Opening a dispute MUST NOT set bookings.status or
#   sessions.status to DISPUTED. Payout blocking is already enforced at the
#   database level by validate_payout_item_eligibility().
# - API Architecture v1.0 section 19 (Dispute APIs): POST /disputes,
#   GET /disputes, GET /disputes/:id, SAFETY -> priority 1, actor must
#   participate in the referenced booking/session/payment.
# - Schema v1: reviews.session_id UNIQUE, is_verified CHECK (is_verified = TRUE)
#   (verification is derived server-side; clients cannot set it), and the
#   trg_reviews_validate_eligibility DB trigger as final consistency guard.

DISPUTE_CATEGORIES = {
    "TEACHER_NO_SHOW", "STUDENT_NO_SHOW", "SESSION_QUALITY",
    "PAYMENT_REFUND", "SAFETY", "REPORT_ISSUE", "OTHER",
}


def create_review(parent_user_id: str, session_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    from django.db import IntegrityError
    comment = data.get("comment")
    if comment is not None:
        comment = str(comment).strip() or None
    try:
        rating_value = int(data.get("rating"))
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_ERROR", "rating must be an integer between 1 and 5.", 400)
    if rating_value < 1 or rating_value > 5:
        raise ApiError("VALIDATION_ERROR", "rating must be an integer between 1 and 5.", 400)
    # Verification is derived from the qualifying completed session. Any
    # client-provided "verified" flag is intentionally ignored.
    canonical = {"session_id": str(session_id), "rating": rating_value, "comment": comment}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = None
        if idempotency_key:
            replay = _idempotency_begin("review_create", parent_user_id, idempotency_key, request_hash, f"/api/v1/sessions/{session_id}/review")
        if replay:
            return replay["response_body"]
        parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [parent_user_id])
        if not parent:
            raise ApiError("FORBIDDEN", "Parent profile is required.", 403)
        # Lock the session row so concurrent creation attempts serialize here.
        row = fetchone(
            """
            SELECT s.id::text, s.booking_id::text, s.status::text,
                   s.parent_id::text, s.student_id::text, s.teacher_id::text,
                   pp.user_id::text AS parent_user_id,
                   b.status::text AS booking_status
            FROM edutrust.sessions s
            JOIN edutrust.parent_profiles pp ON pp.id=s.parent_id
            JOIN edutrust.bookings b ON b.id=s.booking_id
            WHERE s.id=%s FOR UPDATE
            """,
            [session_id],
        )
        if not row:
            raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404)
        if row["parent_user_id"] != parent_user_id:
            raise ApiError("FORBIDDEN", "Only the parent of this session can create a review.", 403)
        existing = fetchone("SELECT id::text FROM edutrust.reviews WHERE session_id=%s", [session_id])
        if existing:
            raise ApiError("DUPLICATE_REVIEW", "A review already exists for this session.", 409)
        if row["status"] != "COMPLETED" or row["booking_status"] != "COMPLETED":
            raise ApiError(
                "REVIEW_NOT_ELIGIBLE",
                "A review can only be created for a completed session with a completed booking.",
                422,
                {"session_status": row["status"], "booking_status": row["booking_status"]},
            )
        payment = fetchone(
            "SELECT 1 AS one FROM edutrust.payments WHERE booking_id=%s AND status='CONFIRMED' LIMIT 1",
            [row["booking_id"]],
        )
        if not payment:
            raise ApiError(
                "REVIEW_NOT_ELIGIBLE",
                "A review can only be created for a completed session with a completed booking and a confirmed payment.",
                422,
                {"session_status": row["status"], "booking_status": row["booking_status"]},
            )
        try:
            review = fetchone(
                """
                INSERT INTO edutrust.reviews (session_id, booking_id, parent_id, student_id, teacher_id, rating, comment)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text, session_id::text, booking_id::text, parent_id::text, student_id::text, teacher_id::text,
                          rating, comment, status::text, is_verified, created_at
                """,
                [session_id, row["booking_id"], row["parent_id"], row["student_id"], row["teacher_id"], rating_value, comment],
            )
        except IntegrityError:
            # reviews.session_id UNIQUE is the final consistency guard.
            raise ApiError("DUPLICATE_REVIEW", "A review already exists for this session.", 409)
        write_event(
            "REVIEW_CREATED", "review", review["id"],
            actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id,
            metadata={"session_id": session_id, "booking_id": row["booking_id"], "is_verified": True},
        )
        response = {"review": _serialize_row(review)}
        if idempotency_key:
            _idempotency_complete("review_create", parent_user_id, idempotency_key, 201, response, "review", review["id"])
        return response


def get_review_for_session(user_id: str, roles: list[str], session_id: str, request_id: str | None = None) -> dict:
    row = _session_access_row(session_id)
    if not _can_access_session(user_id, roles, row):
        raise ApiError("FORBIDDEN", "You do not have access to this review.", 403)
    review = fetchone(
        """
        SELECT r.id::text, r.session_id::text, r.booking_id::text, r.parent_id::text, r.student_id::text, r.teacher_id::text,
               r.rating, r.comment, r.status::text, r.is_verified, r.created_at,
               tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
        FROM edutrust.reviews r
        JOIN edutrust.teacher_profiles tp ON tp.id=r.teacher_id
        JOIN edutrust.student_profiles sp ON sp.id=r.student_id
        WHERE r.session_id=%s
        """,
        [session_id],
    )
    if not review:
        raise ApiError("REVIEW_NOT_FOUND", "No review exists for this session yet.", 404)
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "review", review["id"], actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_REVIEW"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "review", "entity_id": review["id"], "request_id": request_id})
    return _serialize_row(review)


def list_own_reviews(user_id: str, roles: list[str], request_id: str | None = None) -> list[dict]:
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "reviews", None, actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_REVIEW_LIST"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "reviews", "request_id": request_id})
        return fetchall(
            """
            SELECT r.id::text, r.session_id::text, r.booking_id::text, r.rating, r.comment, r.status::text, r.is_verified, r.created_at,
                   tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
            FROM edutrust.reviews r
            JOIN edutrust.teacher_profiles tp ON tp.id=r.teacher_id
            JOIN edutrust.student_profiles sp ON sp.id=r.student_id
            ORDER BY r.created_at DESC LIMIT 100
            """,
        )
    if "TEACHER" in roles:
        teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [user_id])
        if not teacher:
            return []
        return fetchall(
            """
            SELECT r.id::text, r.session_id::text, r.booking_id::text, r.rating, r.comment, r.status::text, r.is_verified, r.created_at,
                   sp.display_name AS student_display_name
            FROM edutrust.reviews r
            JOIN edutrust.student_profiles sp ON sp.id=r.student_id
            WHERE r.teacher_id=%s
            ORDER BY r.created_at DESC LIMIT 100
            """,
            [teacher["id"]],
        )
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [user_id])
    if not parent:
        return []
    return fetchall(
        """
        SELECT r.id::text, r.session_id::text, r.booking_id::text, r.rating, r.comment, r.status::text, r.is_verified, r.created_at,
               tp.public_name AS teacher_public_name
        FROM edutrust.reviews r
        JOIN edutrust.teacher_profiles tp ON tp.id=r.teacher_id
        WHERE r.parent_id=%s
        ORDER BY r.created_at DESC LIMIT 100
        """,
        [parent["id"]],
    )


def list_teacher_public_reviews(teacher_id: str) -> list[dict]:
    teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE id=%s", [teacher_id])
    if not teacher:
        raise ApiError("RESOURCE_NOT_FOUND", "Teacher not found.", 404)
    # Public read: only visible verified reviews, no student-identifying data.
    return fetchall(
        """
        SELECT id::text, rating, comment, is_verified, created_at
        FROM edutrust.reviews
        WHERE teacher_id=%s AND status='VISIBLE' AND is_verified
        ORDER BY created_at DESC
        LIMIT 100
        """,
        [teacher_id],
    )


def _dispute_participation(user_id: str, booking_id: str | None, session_id: str | None, payment_id: str | None) -> dict:
    """Verify actor participation in every provided target (API Architecture section 19.3)."""
    refs = {"booking_id": None, "session_id": None, "payment_id": None}
    if session_id:
        srow = fetchone(
            """
            SELECT s.id::text, s.booking_id::text, pp.user_id::text AS parent_user_id, tp.user_id::text AS teacher_user_id
            FROM edutrust.sessions s
            JOIN edutrust.parent_profiles pp ON pp.id=s.parent_id
            JOIN edutrust.teacher_profiles tp ON tp.id=s.teacher_id
            WHERE s.id=%s
            """,
            [session_id],
        )
        if not srow:
            raise ApiError("RESOURCE_NOT_FOUND", "Referenced session not found.", 404)
        if srow["parent_user_id"] != user_id and srow["teacher_user_id"] != user_id:
            raise ApiError("FORBIDDEN", "You are not a participant in the referenced session.", 403)
        refs["session_id"] = session_id
        refs["booking_id"] = srow["booking_id"]
    if booking_id:
        brow = fetchone(
            """
            SELECT b.id::text, pp.user_id::text AS parent_user_id, tp.user_id::text AS teacher_user_id
            FROM edutrust.bookings b
            JOIN edutrust.parent_profiles pp ON pp.id=b.parent_id
            JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
            WHERE b.id=%s
            """,
            [booking_id],
        )
        if not brow:
            raise ApiError("RESOURCE_NOT_FOUND", "Referenced booking not found.", 404)
        if brow["parent_user_id"] != user_id and brow["teacher_user_id"] != user_id:
            raise ApiError("FORBIDDEN", "You are not a participant in the referenced booking.", 403)
        refs["booking_id"] = booking_id
    if payment_id:
        prow = fetchone(
            """
            SELECT p.id::text, p.booking_id::text, pp.user_id::text AS parent_user_id
            FROM edutrust.payments p
            JOIN edutrust.parent_profiles pp ON pp.id=p.parent_id
            WHERE p.id=%s
            """,
            [payment_id],
        )
        if not prow:
            raise ApiError("RESOURCE_NOT_FOUND", "Referenced payment not found.", 404)
        if prow["parent_user_id"] != user_id:
            raise ApiError("FORBIDDEN", "You are not a participant in the referenced payment.", 403)
        refs["booking_id"] = refs["booking_id"] or prow["booking_id"]
    if not any(refs.values()):
        raise ApiError("VALIDATION_ERROR", "At least one of booking_id, session_id, or payment_id is required.", 400)
    return refs


def open_dispute(user_id: str, roles: list[str], data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    if "PARENT" not in roles and "TEACHER" not in roles:
        raise ApiError("FORBIDDEN", "Only parents and teachers can open disputes.", 403)
    category = str(data.get("category") or "").upper()
    if category not in DISPUTE_CATEGORIES:
        raise ApiError("VALIDATION_ERROR", f"category must be one of {sorted(DISPUTE_CATEGORIES)}.", 400)
    description = (data.get("description") or "").strip() or None
    priority = data.get("priority")
    if category == "SAFETY":
        priority_value = 1  # Safety disputes always receive highest priority (State Machines section 11.2)
    else:
        if priority is None:
            priority_value = 3
        else:
            try:
                priority_value = int(priority)
            except (TypeError, ValueError):
                raise ApiError("VALIDATION_ERROR", "priority must be an integer between 1 and 5.", 400)
            if priority_value < 1 or priority_value > 5:
                raise ApiError("VALIDATION_ERROR", "priority must be an integer between 1 and 5.", 400)
    booking_id = str(data.get("booking_id")) if data.get("booking_id") is not None else None
    session_id = str(data.get("session_id")) if data.get("session_id") is not None else None
    payment_id = str(data.get("payment_id")) if data.get("payment_id") is not None else None
    canonical = {"booking_id": booking_id, "session_id": session_id, "payment_id": payment_id, "category": category, "priority": priority_value, "description": description}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = None
        if idempotency_key:
            replay = _idempotency_begin("dispute_open", user_id, idempotency_key, request_hash, "/api/v1/disputes")
        if replay:
            return replay["response_body"]
        refs = _dispute_participation(user_id, booking_id, session_id, payment_id)
        # Lock the derived booking row so concurrent openings for the same
        # interaction serialize here (State Machines section 11.3: lock target rows).
        fetchone("SELECT id::text FROM edutrust.bookings WHERE id=%s FOR UPDATE", [refs["booking_id"]])
        # Service-level duplicate invariant: at most one active dispute per
        # (actor, interaction). Every dispute row created through this service
        # carries the interaction's booking_id, so the interaction is keyed on it.
        duplicate = fetchone(
            "SELECT id::text, status::text FROM edutrust.disputes WHERE opened_by_user_id=%s AND status IN ('OPEN','UNDER_REVIEW') AND booking_id=%s LIMIT 1",
            [user_id, refs["booking_id"]],
        )
        if duplicate:
            raise ApiError("DUPLICATE_DISPUTE", "An open dispute already exists for this interaction.", 409, {"dispute_id": duplicate["id"]})
        dispute = fetchone(
            """
            INSERT INTO edutrust.disputes (booking_id, session_id, payment_id, opened_by_user_id, category, status, priority, description)
            VALUES (%s, %s, %s, %s, %s::edutrust.dispute_category, 'OPEN', %s, %s)
            RETURNING id::text, booking_id::text, session_id::text, payment_id::text, opened_by_user_id::text,
                      category::text, status::text, priority, description, assigned_admin_user_id::text,
                      resolution, resolved_at, created_at, updated_at
            """,
            [refs["booking_id"], session_id, payment_id, user_id, category, priority_value, description],
        )
        write_event(
            "DISPUTE_OPENED", "dispute", dispute["id"],
            actor_user_id=user_id, actor_role="PARENT" if "PARENT" in roles else "TEACHER", request_id=request_id,
            metadata={"category": category, "priority": priority_value, "booking_id": refs["booking_id"], "session_id": session_id, "payment_id": payment_id, "overlay_only": True},
        )
        response = {"dispute": _serialize_row(dispute)}
        if idempotency_key:
            _idempotency_complete("dispute_open", user_id, idempotency_key, 201, response, "dispute", dispute["id"])
        return response


def _dispute_access_row(dispute_id: str) -> dict:
    row = fetchone(
        """
        SELECT d.id::text, d.booking_id::text, d.session_id::text, d.payment_id::text, d.opened_by_user_id::text,
               d.category::text, d.status::text, d.priority, d.description, d.assigned_admin_user_id::text,
               d.resolution, d.resolved_at, d.created_at, d.updated_at,
               pp.user_id::text AS parent_user_id, tp.user_id::text AS teacher_user_id
        FROM edutrust.disputes d
        JOIN edutrust.bookings b ON b.id=d.booking_id
        JOIN edutrust.parent_profiles pp ON pp.id=b.parent_id
        JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
        WHERE d.id=%s
        """,
        [dispute_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Dispute not found.", 404)
    return row


def _can_access_dispute(user_id: str, roles: list[str], row: dict) -> bool:
    if "ADMIN" in roles or "OPS" in roles:
        return True
    if row["opened_by_user_id"] == user_id:
        return True
    # Opposing participants of the referenced interaction may read the dispute.
    return row["parent_user_id"] == user_id or row["teacher_user_id"] == user_id


def get_dispute_for_user(user_id: str, roles: list[str], dispute_id: str, request_id: str | None = None) -> dict:
    row = _dispute_access_row(dispute_id)
    if not _can_access_dispute(user_id, roles, row):
        raise ApiError("FORBIDDEN", "You do not have access to this dispute.", 403)
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "dispute", dispute_id, actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_DISPUTE"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "dispute", "entity_id": dispute_id, "request_id": request_id})
    teacher = fetchone("SELECT public_name FROM edutrust.teacher_profiles WHERE id=(SELECT teacher_id FROM edutrust.bookings WHERE id=%s)", [row["booking_id"]])
    student = fetchone("SELECT display_name FROM edutrust.student_profiles WHERE id=(SELECT student_id FROM edutrust.bookings WHERE id=%s)", [row["booking_id"]])
    row["teacher_public_name"] = teacher["public_name"] if teacher else None
    row["student_display_name"] = student["display_name"] if student else None
    # VS8 (Addendum v1.1 section 8.3): linked_refunds when applicable.
    linked = fetchall(
        "SELECT id::text AS refund_id, status::text, approved_amount::text, currency FROM edutrust.refunds WHERE dispute_id=%s ORDER BY created_at",
        [dispute_id],
    )
    if linked:
        row["linked_refunds"] = _serialize_row_rows(linked)
    return _serialize_row(row)


def list_disputes_for_user(user_id: str, roles: list[str], request_id: str | None = None) -> list[dict]:
    base = """
        SELECT d.id::text, d.booking_id::text, d.session_id::text, d.payment_id::text, d.opened_by_user_id::text,
               d.category::text, d.status::text, d.priority, d.description, d.created_at,
               tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
        FROM edutrust.disputes d
        JOIN edutrust.bookings b ON b.id=d.booking_id
        JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
        JOIN edutrust.student_profiles sp ON sp.id=b.student_id
    """
    if "ADMIN" in roles or "OPS" in roles:
        write_event("ADMIN_ACTION", "disputes", None, actor_user_id=user_id, actor_role="ADMIN" if "ADMIN" in roles else "OPS", request_id=request_id, metadata={"action": "READ_DISPUTE_LIST"})
        write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "disputes", "request_id": request_id})
        return fetchall(base + " ORDER BY d.created_at DESC LIMIT 100")
    conds: list[str] = []
    sql_params: list = []
    if "TEACHER" in roles:
        teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [user_id])
        if teacher:
            conds.append("tp.id=%s")
            sql_params.append(teacher["id"])
    if "PARENT" in roles:
        parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id=%s", [user_id])
        if parent:
            conds.append("pp.id=%s")
            sql_params.append(parent["id"])
    conds.append("d.opened_by_user_id=%s")
    sql_params.append(user_id)
    return fetchall(
        base + " JOIN edutrust.parent_profiles pp ON pp.id=b.parent_id WHERE (" + " OR ".join(conds) + ") ORDER BY d.created_at DESC LIMIT 100",
        sql_params,
    )

# ---- Vertical Slice 5 payout lifecycle services (MANUAL_OPS / MOCK execution) ----
#
# Baselines implemented here (no new business rules, no schema/state changes):
# - State Machines v1.0 section 12 (Payout State Machine): PENDING -> ELIGIBLE ->
#   PROCESSING -> PAID/FAILED, allowed/forbidden transitions, ledger behavior,
#   failure/compensation. PAID rows are DB-immutable via v1.4
#   trg_00_payouts_paid_immutable_v1_4 (recovery = separate adjustment/recovery
#   ledger transaction, never mutation).
# - State Machines v1.1 Addendum section 10 (authoritative net-payable
#   calculation: gross - approved/provider-pending/succeeded partial-refund
#   teacher adjustments - other approved deductions; net = 0 -> no item) and
#   section 11 (post-paid correction is adjustment/reversal only).
# - API Architecture section 15 (Payout APIs): GET /teacher/payouts,
#   GET /teacher/payouts/:id, POST /admin/payouts/process (OPS/ADMIN,
#   Idempotency-Key payout-<uuid>, two-transaction boundary), GET /admin/payouts.
# - U1 (approved): DEV execution is MANUAL_OPS/MOCK only - no real payout
#   provider, no money movement, no provider-specific behavior.
# - U2 (approved): PENDING batches are created through the authorized Admin/Ops
#   workflow; no scheduled jobs or automation.

PAYOUT_MOCK_PROVIDER_REFERENCE_PREFIX = "mock_payout_"


def _payout_session_row_for_update(session_id: str) -> dict:
    row = fetchone(
        """
        SELECT s.id::text AS session_id, s.booking_id::text, s.status::text, s.teacher_id::text,
               b.status::text AS booking_status, b.platform_commission_bps
        FROM edutrust.sessions s
        JOIN edutrust.bookings b ON b.id=s.booking_id
        WHERE s.id=%s FOR UPDATE
        """,
        [session_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Session not found.", 404, {"session_id": session_id})
    return row


def _payout_ineligibility_reasons(row: dict) -> tuple[list[dict], Decimal | None]:
    """Service-level eligibility per SM v1.0 section 12.2 + Addendum section 10.5.
    The DB trigger validate_payout_item_eligibility remains the final guard."""
    reasons: list[dict] = []
    sid = row["session_id"]
    if row["status"] != "COMPLETED":
        reasons.append({"session_id": sid, "reason": "SESSION_NOT_COMPLETED"})
    report = fetchone("SELECT 1 AS one FROM edutrust.session_reports WHERE session_id=%s", [sid])
    if not report:
        reasons.append({"session_id": sid, "reason": "NO_SESSION_REPORT"})
    payment = fetchone(
        "SELECT amount FROM edutrust.payments WHERE booking_id=%s AND status='CONFIRMED' ORDER BY created_at DESC LIMIT 1",
        [row["booking_id"]],
    )
    if not payment:
        reasons.append({"session_id": sid, "reason": "NO_CONFIRMED_PAYMENT"})
    dispute = fetchone(
        "SELECT 1 AS one FROM edutrust.disputes WHERE status IN ('OPEN','UNDER_REVIEW') AND (session_id=%s OR booking_id=%s) LIMIT 1",
        [sid, row["booking_id"]],
    )
    if dispute:
        reasons.append({"session_id": sid, "reason": "OPEN_DISPUTE"})
    # Strict reading of "no full refund exists" (Addendum 10.5): any FULL refund
    # row for the booking blocks the session (documented plan decision).
    full_refund = fetchone(
        "SELECT 1 AS one FROM edutrust.refunds WHERE booking_id=%s AND refund_type='FULL' LIMIT 1",
        [row["booking_id"]],
    )
    if full_refund:
        reasons.append({"session_id": sid, "reason": "FULL_REFUND_EXISTS"})
    return reasons, payment


def _calculate_session_net(row: dict, payment_amount: Decimal) -> Decimal:
    """Addendum section 10.1: gross - refund exposure - other approved deductions."""
    amount = Decimal(str(payment_amount))
    commission = (amount * Decimal(str(row["platform_commission_bps"])) / Decimal("10000")).quantize(Decimal("0.01"))
    gross = amount - commission
    exposure = fetchone(
        """
        SELECT COALESCE(SUM(teacher_adjustment_amount), 0) AS s
        FROM edutrust.refunds
        WHERE booking_id=%s AND refund_type='PARTIAL' AND status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')
        """,
        [row["booking_id"]],
    )
    net = gross - Decimal(str(exposure["s"]))
    return net.quantize(Decimal("0.01"))


def create_and_process_payout(user_id: str, roles: list[str], data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    if "OPS" not in roles and "ADMIN" not in roles:
        raise ApiError("FORBIDDEN", "Only OPS/ADMIN can process payouts.", 403)
    teacher_id = str(data.get("teacher_id")) if data.get("teacher_id") is not None else None
    session_ids = data.get("session_ids") or []
    force_mock_failure = bool(data.get("force_mock_failure"))
    if not teacher_id or not isinstance(session_ids, list) or not session_ids:
        raise ApiError("VALIDATION_ERROR", "teacher_id and a non-empty session_ids list are required.", 400)
    if len(session_ids) != len(set(session_ids)):
        raise ApiError("VALIDATION_ERROR", "session_ids must be unique.", 400)
    session_ids = sorted(str(s) for s in session_ids)  # deterministic lock order
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    canonical = {"teacher_id": teacher_id, "session_ids": session_ids, "force_mock_failure": force_mock_failure}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

    # TX1 — creation + eligibility (API Architecture 15.3 first transaction boundary).
    with tx():
        replay = _idempotency_begin("payout_process", user_id, idempotency_key, request_hash, "/api/v1/admin/payouts/process")
        if replay:
            return replay["response_body"]
        teacher = fetchone("SELECT id::text, public_name FROM edutrust.teacher_profiles WHERE id=%s FOR UPDATE", [teacher_id])
        if not teacher:
            raise ApiError("RESOURCE_NOT_FOUND", "Teacher not found.", 404)
        nets: list[tuple[str, Decimal]] = []
        ineligible: list[dict] = []
        for sid in session_ids:
            row = _payout_session_row_for_update(sid)
            if row["teacher_id"] != teacher_id:
                raise ApiError("PAYOUT_SESSION_NOT_OWNED", "Session does not belong to this teacher.", 422, {"session_id": sid})
            reasons, payment = _payout_ineligibility_reasons(row)
            if reasons:
                ineligible.extend(reasons)
                continue
            net = _calculate_session_net(row, payment["amount"])
            if net <= 0:
                ineligible.append({"session_id": sid, "reason": "NET_PAYABLE_ZERO"})
                continue
            existing_item = fetchone("SELECT 1 AS one FROM edutrust.payout_items WHERE session_id=%s", [sid])
            if existing_item:
                raise ApiError("PAYOUT_SESSION_ALREADY_PAYOUT", "Session already included in a payout item.", 409, {"session_id": sid})
            nets.append((sid, net))
        if ineligible:
            raise ApiError("PAYOUT_INELIGIBLE", "One or more sessions are not payout-eligible.", 422, {"details": ineligible})
        total = sum(net for _, net in nets)
        payout = fetchone(
            """
            INSERT INTO edutrust.payouts (teacher_id, amount, currency, status)
            VALUES (%s, %s, 'DZD', 'PENDING')
            RETURNING id::text, teacher_id::text, amount::text, currency, status::text, eligible_at, paid_at, provider_reference, created_at
            """,
            [teacher_id, total],
        )
        for sid, net in nets:
            execute(
                "INSERT INTO edutrust.payout_items (payout_id, teacher_id, session_id, amount, currency) VALUES (%s, %s, %s, %s, 'DZD')",
                [payout["id"], teacher_id, sid, net],
            )
        # PENDING -> ELIGIBLE (SM 12.3: authority PayoutService/OPS admin process).
        execute("UPDATE edutrust.payouts SET status='ELIGIBLE', eligible_at=now(), updated_at=now() WHERE id=%s", [payout["id"]])
        ledger_tx = fetchone(
            """
            INSERT INTO edutrust.ledger_transactions (transaction_type, status, payout_id, reference)
            VALUES ('TEACHER_PAYOUT', 'DRAFT', %s, %s)
            RETURNING id::text
            """,
            [payout["id"], f"payout:{payout['id']}"],
        )
        execute(
            """
            INSERT INTO edutrust.ledger_entries (ledger_transaction_id, account_type, direction, amount, memo)
            VALUES (%s, 'TEACHER_PAYABLE', 'DEBIT', %s, %s),
                   (%s, 'TEACHER_CASH', 'CREDIT', %s, %s)
            """,
            [ledger_tx["id"], total, f"payout {payout['id']}", ledger_tx["id"], total, f"payout {payout['id']}"],
        )
        write_event(
            "PAYOUT_ELIGIBLE", "payout", payout["id"],
            actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
            metadata={"session_ids": session_ids, "item_count": len(nets), "total": str(total), "dev_mock": True},
        )
        # ELIGIBLE -> PROCESSING (SM 12.3: OPS/Admin).
        execute("UPDATE edutrust.payouts SET status='PROCESSING', updated_at=now() WHERE id=%s", [payout["id"]])

    # MOCK EXECUTION — outside the DB transaction, per API Architecture 15.3.
    # U1: MANUAL_OPS/MOCK only. Deterministic DEV result; no provider call,
    # no credentials, no money movement, no provider-specific behavior.
    result = "FAILED" if force_mock_failure else "PAID"

    # TX2 — outcome (API Architecture 15.3 second transaction boundary).
    with tx():
        fetchone("SELECT id::text FROM edutrust.payouts WHERE id=%s FOR UPDATE", [payout["id"]])
        if result == "PAID":
            provider_reference = f"{PAYOUT_MOCK_PROVIDER_REFERENCE_PREFIX}{payout['id']}"
            execute(
                "UPDATE edutrust.payouts SET status='PAID', paid_at=now(), provider_reference=%s, updated_at=now() WHERE id=%s",
                [provider_reference, payout["id"]],
            )
            # Final TEACHER_PAYOUT ledger is posted only on success (SM 12.5.3).
            execute("UPDATE edutrust.ledger_transactions SET status='POSTED' WHERE id=%s", [ledger_tx["id"]])
            write_event(
                "PAYOUT_PROCESSED", "payout", payout["id"],
                actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
                metadata={"provider_reference": provider_reference, "dev_mock": True},
            )
        else:
            execute("UPDATE edutrust.payouts SET status='FAILED', updated_at=now() WHERE id=%s", [payout["id"]])
            # DRAFT ledger was never posted -> no funds moved -> VOID, no reversal needed (SM 12.6).
            execute("UPDATE edutrust.ledger_transactions SET status='VOIDED' WHERE id=%s", [ledger_tx["id"]])
            write_event(
                "ADMIN_ACTION", "payout", payout["id"],
                actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
                metadata={"action": "PAYOUT_PROCESS_FAILED", "dev_mock": True, "reason": "mock_failure_forced"},
            )
        response = {
            "payout": _serialize_row(payout),
            "items": _serialize_row_rows(
                fetchall(
                    "SELECT session_id::text, amount::text, currency FROM edutrust.payout_items WHERE payout_id=%s ORDER BY created_at, id",
                    [payout["id"]],
                )
            ),
            "ledger": {"transaction_id": ledger_tx["id"], "status": "POSTED" if result == "PAID" else "VOIDED"},
            "result": result,
        }
        # Refresh payout row for the response (final status/dates).
        response["payout"] = _serialize_row(
            fetchone(
                "SELECT id::text, teacher_id::text, amount::text, currency, status::text, eligible_at, paid_at, provider_reference, created_at FROM edutrust.payouts WHERE id=%s",
                [payout["id"]],
            )
        )
        _idempotency_complete("payout_process", user_id, idempotency_key, 201, response, "payout", payout["id"])
    return response


def _serialize_row_rows(rows: list[dict]) -> list[dict]:
    return [_serialize_row(r) for r in rows]


def _teacher_profile_id(user_id: str) -> str:
    teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [user_id])
    if not teacher:
        raise ApiError("FORBIDDEN", "Teacher profile is required.", 403)
    return teacher["id"]


def get_payout_for_teacher(user_id: str, payout_id: str) -> dict:
    teacher_id = _teacher_profile_id(user_id)
    row = fetchone(
        """
        SELECT p.id::text, p.teacher_id::text, p.amount::text, p.currency, p.status::text,
               p.eligible_at, p.paid_at, p.created_at,
               (SELECT count(*)::int FROM edutrust.payout_items pi WHERE pi.payout_id=p.id) AS item_count
        FROM edutrust.payouts p
        WHERE p.id=%s AND p.teacher_id=%s
        """,
        [payout_id, teacher_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Payout not found.", 404)
    row["items"] = fetchall(
        "SELECT id::text, session_id::text, amount::text, currency, created_at FROM edutrust.payout_items WHERE payout_id=%s ORDER BY created_at, id",
        [payout_id],
    )
    # provider_reference intentionally omitted from teacher views (internal mock identity).
    return _serialize_row(row)


def list_payouts_for_teacher(user_id: str) -> list[dict]:
    teacher_id = _teacher_profile_id(user_id)
    return fetchall(
        """
        SELECT p.id::text, p.teacher_id::text, p.amount::text, p.currency, p.status::text,
               p.eligible_at, p.paid_at, p.created_at,
               (SELECT count(*)::int FROM edutrust.payout_items pi WHERE pi.payout_id=p.id) AS item_count
        FROM edutrust.payouts p
        WHERE p.teacher_id=%s
        ORDER BY p.created_at DESC LIMIT 100
        """,
        [teacher_id],
    )


def list_admin_payouts(user_id: str, roles: list[str], request_id: str | None = None) -> list[dict]:
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    write_event("ADMIN_ACTION", "payouts", None, actor_user_id=user_id, actor_role=actor_role, request_id=request_id, metadata={"action": "READ_PAYOUT_LIST"})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "payouts", "request_id": request_id})
    return fetchall(
        """
        SELECT p.id::text, p.teacher_id::text, p.amount::text, p.currency, p.status::text,
               p.eligible_at, p.paid_at, p.provider_reference, p.created_at,
               tp.public_name AS teacher_public_name,
               (SELECT count(*)::int FROM edutrust.payout_items pi WHERE pi.payout_id=p.id) AS item_count
        FROM edutrust.payouts p
        JOIN edutrust.teacher_profiles tp ON tp.id=p.teacher_id
        ORDER BY p.created_at DESC LIMIT 100
        """,
    )

# ---- Vertical Slice 6 review moderation services ----
#
# Baselines implemented here (no new business rules, no schema/state changes):
# - State Machines v1.0 section 10.3: manual OPS/Admin moderation transitions
#   VISIBLE->FLAGGED (FLAG), FLAGGED->HIDDEN (HIDE), FLAGGED|HIDDEN->VISIBLE
#   (RESTORE), any-of-VISIBLE/FLAGGED/HIDDEN->REMOVED (REMOVE, Admin only);
#   "Lock review"; event ADMIN_ACTION; review record preserved.
# - State Machines v1.0 section 10.4: no physical deletion — status-based only.
# - API Architecture 18.1/18.4/21.4: POST /admin/reviews/:id/moderate (OPS/ADMIN,
#   "Moderation must be audited"), GET /admin/reviews (SUPPORT/OPS/ADMIN);
#   verified rating not silently deleted.
# - VS4 verified-review model preserved: is_verified stays server-derived
#   (DB CHECK is_verified = TRUE); moderation updates status only.
# - System/automatic flagging is OUT OF SCOPE (no approved detection spec).

MODERATION_TRANSITIONS = {
    "FLAG": {"from": {"VISIBLE"}, "to": "FLAGGED", "admin_only": False},
    "HIDE": {"from": {"FLAGGED"}, "to": "HIDDEN", "admin_only": False},
    "RESTORE": {"from": {"FLAGGED", "HIDDEN"}, "to": "VISIBLE", "admin_only": False},
    "REMOVE": {"from": {"VISIBLE", "FLAGGED", "HIDDEN"}, "to": "REMOVED", "admin_only": True},
}


def _moderation_review_row(review_id: str) -> dict:
    return fetchone(
        """
        SELECT r.id::text, r.session_id::text, r.booking_id::text, r.teacher_id::text, r.rating, r.comment,
               r.status::text, r.is_verified, r.created_at,
               tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
        FROM edutrust.reviews r
        JOIN edutrust.teacher_profiles tp ON tp.id=r.teacher_id
        JOIN edutrust.student_profiles sp ON sp.id=r.student_id
        WHERE r.id=%s FOR UPDATE
        """,
        [review_id],
    )


def moderate_review(user_id: str, roles: list[str], review_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    action = str(data.get("action") or "").upper()
    reason = (data.get("reason") or "").strip()
    if action not in MODERATION_TRANSITIONS:
        raise ApiError("VALIDATION_ERROR", "action must be one of FLAG, HIDE, RESTORE, REMOVE.", 400)
    if not reason:
        raise ApiError("VALIDATION_ERROR", "reason is required.", 400)
    transition = MODERATION_TRANSITIONS[action]
    if transition["admin_only"] and "ADMIN" not in roles:
        raise ApiError("FORBIDDEN", "REMOVE requires ADMIN authority.", 403)
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    canonical = {"review_id": str(review_id), "action": action, "reason": reason}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("review_moderate", user_id, idempotency_key, request_hash, f"/api/v1/admin/reviews/{review_id}/moderate")
        if replay:
            return replay["response_body"]
        review = _moderation_review_row(review_id)
        if not review:
            raise ApiError("RESOURCE_NOT_FOUND", "Review not found.", 404)
        if review["status"] not in transition["from"]:
            raise ApiError(
                "INVALID_STATE_TRANSITION",
                f"Action {action} is not allowed from status {review['status']}.",
                422,
                {"current_status": review["status"]},
            )
        # Status-only update: rating/comment/is_verified/session linkage untouched.
        execute(
            "UPDATE edutrust.reviews SET status=%s::edutrust.review_status, updated_at=now() WHERE id=%s",
            [transition["to"], review_id],
        )
        write_event(
            "ADMIN_ACTION", "review", review_id,
            actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
            metadata={"action": f"MODERATE_{action}", "reason": reason, "from_status": review["status"], "to_status": transition["to"]},
        )
        response = {"review": _serialize_row(_moderation_review_row(review_id))}
        _idempotency_complete("review_moderate", user_id, idempotency_key, 200, response, "review", review_id)
    return response


def list_admin_reviews(user_id: str, roles: list[str], request_id: str | None = None) -> list[dict]:
    actor_role = "ADMIN" if "ADMIN" in roles else ("OPS" if "OPS" in roles else "SUPPORT")
    write_event("ADMIN_ACTION", "reviews", None, actor_user_id=user_id, actor_role=actor_role, request_id=request_id, metadata={"action": "READ_REVIEW_LIST"})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "reviews", "request_id": request_id})
    return fetchall(
        """
        SELECT r.id::text, r.session_id::text, r.booking_id::text, r.teacher_id::text, r.rating, r.comment,
               r.status::text, r.is_verified, r.created_at,
               tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
        FROM edutrust.reviews r
        JOIN edutrust.teacher_profiles tp ON tp.id=r.teacher_id
        JOIN edutrust.student_profiles sp ON sp.id=r.student_id
        ORDER BY r.created_at DESC LIMIT 100
        """,
    )

# ---- Vertical Slice 7 teacher verification services ----
#
# Baselines implemented here (no new business rules, no schema changes):
# - PRD 9.2 (P0/P1): levels 0-2 (Level 3 future — out of scope); submit, admin
#   review, status on profile, events logged; acceptance criteria: auditable
#   approval/rejection, parents distinguish verified vs unverified, document
#   access restricted.
# - API Architecture 8.4: submission contract (type + documents + metadata;
#   "API stores metadata and storage key only"; "Teacher cannot self-approve
#   verification"); 8.1 (verification_status/listing_status not freely
#   editable); 8.5 (per-type verified booleans); 21.1 admin endpoints.
# - Security/Privacy Plan 6: document access only through audited admin/OPS
#   flow; metadata-only in DEV (approved decision V6).
# - Approved plan decisions: V1 profile mapping, V2 no-demotion, V3
#   EXPERIENCE/BACKGROUND_CHECK rows without profile mapping, V4 additive
#   trust-profile booleans, V5 mandatory Idempotency-Key, V6 metadata-only
#   audited document access.
# - Out of scope (no approved mechanic): EXPIRED, SUSPENDED, real document
#   storage/upload, KYC/provider/AI/automatic verification, search filtering.

VERIFICATION_TYPES = {"IDENTITY", "QUALIFICATION", "EXPERIENCE", "BACKGROUND_CHECK"}
# V1/V2 profile-level mapping. Only IDENTITY/QUALIFICATION approvals carry an
# approved profile level; EXPERIENCE/BACKGROUND_CHECK rows never change the
# profile status (V3 — no approved level exists for them). SUSPENDED is never
# touched by this slice (owned by the user-suspension workstream).
_APPROVED_PROFILE_LEVELS = {"IDENTITY_VERIFIED", "QUALIFICATION_REVIEWED"}
_LEVEL_RANK = {
    "UNVERIFIED": 0,
    "REJECTED": 0,
    "SUBMITTED": 0,
    "IDENTITY_VERIFIED": 1,
    "QUALIFICATION_REVIEWED": 2,
    "SUSPENDED": 9,
}


def _verification_approved_levels(teacher_profile_id: str) -> set:
    """Types currently at APPROVED for the teacher (per-type results)."""
    rows = fetchall(
        "SELECT verification_type::text FROM edutrust.teacher_verifications WHERE teacher_id=%s AND status='APPROVED'",
        [teacher_profile_id],
    )
    return {r["verification_type"] for r in rows}


def _highest_profile_level(approved_types: set) -> str | None:
    if "QUALIFICATION" in approved_types:
        return "QUALIFICATION_REVIEWED"
    if "IDENTITY" in approved_types:
        return "IDENTITY_VERIFIED"
    return None


def _apply_profile_status_after_change(teacher_profile_id: str, changed_type: str, decision: str | None):
    """Approved profile-status mapping (V1) with the no-demotion rule (V2).

    - submission: UNVERIFIED/REJECTED -> SUBMITTED; never demotes SUBMITTED or
      an approved level.
    - APPROVED: profile rises to the highest approved level; an already
      approved level is never demoted by approving a lower type.
    - REJECTED: profile -> REJECTED only when no approved level remains (V1);
      an approved level is never demoted by rejecting a lower type (V2).
    """
    current = fetchone("SELECT verification_status::text FROM edutrust.teacher_profiles WHERE id=%s", [teacher_profile_id])
    current_status = current["verification_status"]
    if current_status == "SUSPENDED":
        return

    def set_status(status: str):
        execute(
            "UPDATE edutrust.teacher_profiles SET verification_status=%s::edutrust.teacher_verification_status, updated_at=now() WHERE id=%s",
            [status, teacher_profile_id],
        )

    if decision is None:  # submission (any type)
        if current_status in ("UNVERIFIED", "REJECTED"):
            set_status("SUBMITTED")
        return

    approved = _verification_approved_levels(teacher_profile_id)
    if decision == "APPROVED":
        approved.add(changed_type)
    # (REJECTED rows were SUBMITTED, so the approved set is unchanged.)
    target = _highest_profile_level(approved)
    if decision == "APPROVED":
        if target is None:  # EXPERIENCE/BACKGROUND_CHECK: no profile level (V3)
            return
        if current_status in _APPROVED_PROFILE_LEVELS and _LEVEL_RANK[current_status] > _LEVEL_RANK[target]:
            return  # V2: never demote an approved higher level
        set_status(target)
    else:  # REJECTED
        if target is not None:
            return  # an approved level remains; profile already reflects it (V2)
        if current_status in _APPROVED_PROFILE_LEVELS:
            return  # defensive: never demote an approved level
        set_status("REJECTED")


def submit_verification(teacher_user_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    vtype = str(data.get("verification_type") or "").upper()
    if vtype not in VERIFICATION_TYPES:
        raise ApiError("VALIDATION_ERROR", f"verification_type must be one of {sorted(VERIFICATION_TYPES)}.", 400)
    documents = data.get("documents")
    doc_rows = []
    if documents is not None:
        if not isinstance(documents, list):
            raise ApiError("VALIDATION_ERROR", "documents must be a list.", 400)
        for d in documents:
            if not isinstance(d, dict):
                raise ApiError("VALIDATION_ERROR", "each document must be an object.", 400)
            dtype = str(d.get("document_type") or "").strip()
            token = str(d.get("upload_token") or "").strip()
            if not dtype or not token:
                raise ApiError("VALIDATION_ERROR", "document_type and upload_token are required for each document.", 400)
            doc_rows.append((dtype, token))
    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ApiError("VALIDATION_ERROR", "metadata must be an object.", 400)
    teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE user_id=%s", [teacher_user_id])
    if not teacher:
        raise ApiError("FORBIDDEN", "Teacher profile is required.", 403)
    canonical = {"verification_type": vtype,
                 "documents": [{"document_type": d[0], "upload_token": d[1]} for d in doc_rows],
                 "metadata": metadata}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("verification_submit", teacher_user_id, idempotency_key, request_hash, "/api/v1/teachers/verifications")
        if replay:
            return replay["response_body"]
        verification = fetchone(
            """
            INSERT INTO edutrust.teacher_verifications (teacher_id, verification_type, status, metadata)
            VALUES (%s, %s::edutrust.verification_type, 'SUBMITTED', %s::jsonb)
            RETURNING id::text, teacher_id::text, verification_type::text, status::text, submitted_at,
                      reviewed_by_user_id::text, reviewed_at, reviewer_note, rejection_reason, metadata
            """,
            [teacher["id"], vtype, json.dumps(metadata or {}, default=str)],
        )
        for dtype, token in doc_rows:
            # DEV: metadata + synthetic storage key only (API 8.4; V6). No real storage.
            fetchone(
                """
                INSERT INTO edutrust.verification_documents (verification_id, teacher_id, uploaded_by_user_id, document_type, storage_key, file_mime_type, status)
                VALUES (%s, %s, %s, %s, %s, 'application/octet-stream', 'UPLOADED')
                RETURNING id::text, verification_id::text, teacher_id::text, document_type, storage_key, status::text
                """,
                [verification["id"], teacher["id"], teacher_user_id, dtype, f"dev-synthetic-{uuid.uuid4().hex}"],
            )
        _apply_profile_status_after_change(teacher["id"], vtype, None)
        write_event(
            "TEACHER_VERIFICATION_SUBMITTED", "teacher_verification", verification["id"],
            actor_user_id=teacher_user_id, actor_role="TEACHER", request_id=request_id,
            metadata={"verification_type": vtype, "document_count": len(doc_rows)},
        )
        verification["documents"] = _serialize_row_rows(verification_documents(verification["id"]))
        response = {"verification": _serialize_row(_decode_metadata(verification)),
                    "profile_verification_status": fetchone("SELECT verification_status::text FROM edutrust.teacher_profiles WHERE id=%s", [teacher["id"]])["verification_status"]}
        _idempotency_complete("verification_submit", teacher_user_id, idempotency_key, 201, response, "teacher_verification", verification["id"])
    return response


def verification_documents(verification_id: str) -> list[dict]:
    return fetchall(
        """
        SELECT id::text, verification_id::text, teacher_id::text, document_type, storage_key, sha256_hash,
               file_mime_type, file_size_bytes, encrypted, status::text, created_at
        FROM edutrust.verification_documents WHERE verification_id=%s ORDER BY created_at, id
        """,
        [verification_id],
    )


def _decode_metadata(row: dict) -> dict:
    import json
    m = row.get("metadata")
    if isinstance(m, str):
        try:
            row["metadata"] = json.loads(m)
        except (TypeError, ValueError):
            pass
    return row


def _verification_with_documents(verification_id: str) -> dict:
    row = fetchone(
        """
        SELECT id::text, teacher_id::text, verification_type::text, status::text, submitted_at,
               reviewed_by_user_id::text, reviewed_at, reviewer_note, rejection_reason, metadata
        FROM edutrust.teacher_verifications WHERE id=%s
        """,
        [verification_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Verification not found.", 404)
    row["documents"] = verification_documents(verification_id)
    return _serialize_row(_decode_metadata(row))


def list_verifications_for_teacher(teacher_user_id: str) -> dict:
    teacher = fetchone("SELECT id::text, verification_status::text FROM edutrust.teacher_profiles WHERE user_id=%s", [teacher_user_id])
    if not teacher:
        raise ApiError("FORBIDDEN", "Teacher profile is required.", 403)
    rows = fetchall(
        """
        SELECT id::text, verification_type::text, status::text, submitted_at, reviewed_at, reviewer_note, rejection_reason, metadata
        FROM edutrust.teacher_verifications WHERE teacher_id=%s ORDER BY submitted_at DESC, id DESC LIMIT 100
        """,
        [teacher["id"]],
    )
    return {"profile_verification_status": teacher["verification_status"],
            "verifications": [_serialize_row(_decode_metadata(r)) for r in rows]}


def list_pending_verifications(user_id: str, roles: list[str], request_id: str | None = None) -> dict:
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    write_event("ADMIN_ACTION", "teacher_verifications", None, actor_user_id=user_id, actor_role=actor_role, request_id=request_id, metadata={"action": "READ_PENDING_VERIFICATIONS"})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "teacher_verifications", "request_id": request_id})
    teachers = fetchall(
        """
        SELECT tp.id::text, tp.public_name, tp.verification_status::text,
               (SELECT count(*)::int FROM edutrust.teacher_verifications tv WHERE tv.teacher_id=tp.id AND tv.status='SUBMITTED') AS pending_count
        FROM edutrust.teacher_profiles tp
        WHERE EXISTS (SELECT 1 FROM edutrust.teacher_verifications tv WHERE tv.teacher_id=tp.id AND tv.status='SUBMITTED')
        ORDER BY tp.created_at DESC LIMIT 100
        """,
    )
    for t in teachers:
        t["pending"] = fetchall(
            "SELECT id::text, verification_type::text, submitted_at FROM edutrust.teacher_verifications WHERE teacher_id=%s AND status='SUBMITTED' ORDER BY submitted_at",
            [t["id"]],
        )
        t["pending"] = _serialize_row_rows(t["pending"])
    return {"teachers": _serialize_row_rows(teachers)}


def get_verifications_for_admin(user_id: str, roles: list[str], teacher_id: str, request_id: str | None = None) -> dict:
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    write_event("ADMIN_ACTION", "teacher_verification", None, actor_user_id=user_id, actor_role=actor_role, request_id=request_id, metadata={"action": "READ_VERIFICATION_DETAIL", "teacher_id": teacher_id})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "teacher_verification", "teacher_id": teacher_id, "request_id": request_id})
    teacher = fetchone(
        "SELECT id::text, public_name, verification_status::text, listing_status::text, experience_years, languages, base_wilaya_code FROM edutrust.teacher_profiles WHERE id=%s",
        [teacher_id],
    )
    if not teacher:
        raise ApiError("RESOURCE_NOT_FOUND", "Teacher not found.", 404)
    rows = fetchall(
        """
        SELECT id::text, verification_type::text, status::text, submitted_at, reviewed_at, reviewer_note, rejection_reason, metadata
        FROM edutrust.teacher_verifications WHERE teacher_id=%s ORDER BY submitted_at DESC, id DESC LIMIT 100
        """,
        [teacher_id],
    )
    verifications = []
    for r in rows:
        rr = _serialize_row(_decode_metadata(r))
        rr["documents"] = _serialize_row_rows(verification_documents(r["id"]))
        verifications.append(rr)
    return {"teacher": _serialize_row(teacher), "verifications": verifications}


def review_verification(user_id: str, roles: list[str], teacher_id: str, verification_id: str, decision: str, reason: str | None, request_id: str | None = None) -> dict:
    """Shared core for E5 verify (APPROVED) and E6 reject (REJECTED).
    decision: 'APPROVED' | 'REJECTED'. reason: reviewer_note (APPROVED) or
    rejection_reason (REJECTED, required non-empty)."""
    if decision not in ("APPROVED", "REJECTED"):
        raise ApiError("VALIDATION_ERROR", "decision must be APPROVED or REJECTED.", 400)
    if decision == "REJECTED" and not (reason and reason.strip()):
        raise ApiError("VALIDATION_ERROR", "rejection_reason is required.", 400)
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    with tx():
        teacher = fetchone("SELECT id::text FROM edutrust.teacher_profiles WHERE id=%s FOR UPDATE", [teacher_id])
        if not teacher:
            raise ApiError("RESOURCE_NOT_FOUND", "Teacher not found.", 404)
        row = fetchone(
            "SELECT id::text, teacher_id::text, verification_type::text, status::text FROM edutrust.teacher_verifications WHERE id=%s AND teacher_id=%s FOR UPDATE",
            [verification_id, teacher_id],
        )
        if not row:
            raise ApiError("RESOURCE_NOT_FOUND", "Verification not found for this teacher.", 404)
        if row["status"] != "SUBMITTED":
            raise ApiError("INVALID_STATE_TRANSITION", f"Verification cannot be reviewed from status {row['status']}.", 422, {"current_status": row["status"]})
        note = reason.strip() if reason and reason.strip() else None
        if decision == "APPROVED":
            execute(
                "UPDATE edutrust.teacher_verifications SET status='APPROVED'::edutrust.verification_review_status, reviewed_by_user_id=%s, reviewed_at=now(), reviewer_note=%s WHERE id=%s",
                [user_id, note, verification_id],
            )
        else:
            execute(
                "UPDATE edutrust.teacher_verifications SET status='REJECTED'::edutrust.verification_review_status, reviewed_by_user_id=%s, reviewed_at=now(), rejection_reason=%s WHERE id=%s",
                [user_id, reason.strip(), verification_id],
            )
        _apply_profile_status_after_change(teacher_id, row["verification_type"], decision)
        event = "TEACHER_VERIFIED" if decision == "APPROVED" else "TEACHER_REJECTED"
        write_event(event, "teacher_verification", verification_id, actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
                    metadata={"verification_type": row["verification_type"], "reviewer_note": note, "rejection_reason": reason.strip() if decision == "REJECTED" else None})
        write_event("ADMIN_ACTION", "teacher_verification", verification_id, actor_user_id=user_id, actor_role=actor_role, request_id=request_id,
                    metadata={"action": "VERIFICATION_APPROVED" if decision == "APPROVED" else "VERIFICATION_REJECTED", "verification_type": row["verification_type"]})
    result = _verification_with_documents(verification_id)
    status = fetchone("SELECT verification_status::text FROM edutrust.teacher_profiles WHERE id=%s", [teacher_id])["verification_status"]
    return {"verification": result, "profile_verification_status": status}

# ---- Vertical Slice 8 refund operations services (DEV mock only) ----
#
# Baselines implemented here (no new business rules, no schema/state changes):
# - API Architecture section 12.6 (POST /payments/:id/refund, OPS under
#   policy / ADMIN elevated, two-transaction boundary, provider call
#   outside the DB transaction) and section 24 (idempotency required).
# - API Contract Addendum v1.1 sections 7.1/7.2 (admin refund reads) and
#   7.3 (POST /admin/refunds/:id/reconcile, verbatim contract) and section 8
#   (refund summaries in payment/booking/dispute reads).
# - State Machines v1.0 section 14 (refund lifecycle: 7 states, transition
#   matrix, partial/full behavior) and v1.1 Addendum sections 7 (states,
#   event semantics, forbidden semantics), 8.4 (provider_refund_id linked to
#   refunds.id), 13.1/13.2/13.3 (event list, REFUND_ISSUED deprecation,
#   event timing), 15.4 (over-refund prevention).
# - Schema v1.1 (refunds table, allocation + integrity trigger,
#   api_idempotency_keys, payment_provider_events with refund linkage),
#   v1.2 (lifecycle guard, reconciliation proof), v1.3 (hardening).
# - D1 (approved): DEV mock initiation via the existing
#   MockPaymentProvider.initiate_refund() primitive. D2 (approved):
#   deterministic mock SUCCESS/FAILURE only. D3 (approved): reuse
#   payment_provider_events; no new table; no new event enum values;
#   REFUND_ISSUED is never emitted. D9 (approved): allocation explicitly
#   supplied by the authorized Admin/OPS actor at approval; no formula.
# - REAL REFUND / REAL PAYMENT / REAL PAYOUT remain FORBIDDEN; DEV mock only.

REFUND_TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "REJECTED", "CANCELLED")
REFUND_ACTIVE_STATUSES = ("REQUESTED", "APPROVED", "PROVIDER_PENDING")


def _refund_amount(value, field: str) -> "Decimal":
    try:
        amount = Decimal(str(value).strip())
    except Exception:
        raise ApiError("VALIDATION_ERROR", f"{field} must be a decimal string amount.", 400)
    if not amount.is_finite() or amount <= 0:
        raise ApiError("VALIDATION_ERROR", f"{field} must be a positive decimal amount.", 400)
    return amount.quantize(Decimal("0.01"))


def _refund_nonnegative_amount(value, field: str) -> "Decimal":
    try:
        amount = Decimal(str(value).strip())
    except Exception:
        raise ApiError("VALIDATION_ERROR", f"{field} must be a decimal string amount.", 400)
    if not amount.is_finite() or amount < 0:
        raise ApiError("VALIDATION_ERROR", f"{field} must be a non-negative decimal amount.", 400)
    return amount.quantize(Decimal("0.01"))


def _refund_require_key(idempotency_key: str | None) -> None:
    if idempotency_key is not None and len(str(idempotency_key)) < 16:
        raise ApiError("VALIDATION_ERROR", "Idempotency-Key must be at least 16 characters.", 400)


def _refund_payment_for_update(payment_id: str) -> dict:
    payment = fetchone(
        """
        SELECT id::text, booking_id::text, amount::text, currency, status::text, provider::text
        FROM edutrust.payments WHERE id=%s FOR UPDATE
        """,
        [payment_id],
    )
    if not payment:
        raise ApiError("RESOURCE_NOT_FOUND", "Payment not found.", 404)
    return payment


def _refund_row_for_update(refund_id: str) -> dict:
    refund = fetchone(
        """
        SELECT r.id::text, r.payment_id::text, r.booking_id::text, r.dispute_id::text,
               r.provider::text, r.refund_type::text, r.status::text, r.requested_amount::text,
               r.approved_amount::text, r.currency, r.teacher_adjustment_amount::text,
               r.platform_adjustment_amount::text, r.reason, r.reason_code, r.provider_refund_id,
               r.metadata, r.reconciliation_source, r.reconciliation_reference, r.reconciled_at,
               r.reconciled_by_user_id::text, r.created_at
        FROM edutrust.refunds r WHERE r.id=%s FOR UPDATE
        """,
        [refund_id],
    )
    if not refund:
        raise ApiError("RESOURCE_NOT_FOUND", "Refund not found.", 404)
    return refund


def _refund_reserved_amount(payment_id: str, exclude_refund_id: str | None = None) -> "Decimal":
    params: list = [payment_id]
    sql = "SELECT COALESCE(SUM(approved_amount),0) AS s FROM edutrust.refunds WHERE payment_id=%s AND status IN ('APPROVED','PROVIDER_PENDING','SUCCEEDED')"
    if exclude_refund_id:
        sql += " AND id<>%s"
        params.append(exclude_refund_id)
    return Decimal(str(fetchone(sql, params)["s"]))


def _refund_ledger_form(booking_id: str) -> str:
    """PLAN-LOCK (D10): L = late/unfulfillable (zero sessions), D = direct
    reversal (fulfilled, no PAID payout), A = post-paid recovery (PAID payout
    covering the booking exists). Determined at approval, recorded on the tx."""
    paid = fetchone(
        """
        SELECT 1 AS one FROM edutrust.payouts p
        JOIN edutrust.payout_items pi ON pi.payout_id=p.id
        JOIN edutrust.sessions s ON s.id=pi.session_id
        WHERE p.status='PAID' AND s.booking_id=%s LIMIT 1
        """,
        [booking_id],
    )
    if paid:
        return "A"
    session = fetchone("SELECT 1 AS one FROM edutrust.sessions WHERE booking_id=%s LIMIT 1", [booking_id])
    if not session:
        return "L"
    return "D"


def _create_refund_ledger_draft(refund_id: str, payment_id: str, booking_id: str, form: str,
                                approved: "Decimal", teacher_adj: "Decimal", platform_adj: "Decimal") -> str:
    tx_row = fetchone(
        "INSERT INTO edutrust.ledger_transactions (transaction_type, status, booking_id, payment_id, reference) "
        "VALUES ('REFUND','DRAFT',%s,%s,%s) RETURNING id::text",
        [booking_id, payment_id, f"refund-{refund_id}"],
    )
    entries: list[tuple[str, str, "Decimal"]] = []
    if form == "L":
        entries.append(("REFUND_PAYABLE", "DEBIT", approved))
    else:
        if teacher_adj > 0:
            entries.append(("TEACHER_PAYABLE" if form == "D" else "TEACHER_RECOVERABLE", "DEBIT", teacher_adj))
        if platform_adj > 0:
            entries.append(("PLATFORM_REVENUE" if form == "D" else "PLATFORM_REFUND_EXPENSE", "DEBIT", platform_adj))
    entries.append(("PAYMENT_PROVIDER_CLEARING", "CREDIT", approved))
    for account, direction, amount in entries:
        execute(
            "INSERT INTO edutrust.ledger_entries (ledger_transaction_id, account_type, direction, amount, memo) "
            "VALUES (%s,%s::edutrust.ledger_account_type,%s::edutrust.ledger_direction,%s,%s)",
            [tx_row["id"], account, direction, str(amount), f"refund {refund_id} form {form}"],
        )
    return tx_row["id"]


def _set_refund_ledger_status(refund_id: str, status: str) -> None:
    execute("UPDATE edutrust.ledger_transactions SET status=%s WHERE reference=%s",
            [status, f"refund-{refund_id}"])


def _refund_cumulative_succeeded(payment_id: str) -> "Decimal":
    return Decimal(str(fetchone(
        "SELECT COALESCE(SUM(approved_amount),0) AS s FROM edutrust.refunds WHERE payment_id=%s AND status='SUCCEEDED'",
        [payment_id],
    )["s"]))


def _refund_payment_status_after_success(payment_id: str) -> str:
    payment_amount = Decimal(str(fetchone("SELECT amount::text FROM edutrust.payments WHERE id=%s", [payment_id])["amount"]))
    return "REFUNDED" if _refund_cumulative_succeeded(payment_id) >= payment_amount else "PARTIALLY_REFUNDED"


def _refund_prior_payment_status(refund: dict) -> str:
    import json
    meta = refund.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except (TypeError, ValueError):
            meta = {}
    prior = (meta or {}).get("payment_status_before_refund")
    return prior if prior in ("CONFIRMED", "DISPUTED") else "CONFIRMED"


def _refund_detail(refund_id: str) -> dict:
    row = fetchone(
        """
        SELECT r.id::text AS refund_id, r.status::text, r.refund_type::text, r.payment_id::text,
               r.booking_id::text, r.dispute_id::text, r.provider::text, r.requested_amount::text,
               r.approved_amount::text, r.currency, r.teacher_adjustment_amount::text,
               r.platform_adjustment_amount::text, r.reason, r.reason_code, r.provider_refund_id,
               r.requested_by_user_id::text, r.requested_by_role::text, r.approved_by_user_id::text,
               r.approved_by_role::text, r.reconciliation_source, r.reconciliation_reference,
               r.reconciled_at, r.reconciled_by_user_id::text, r.failure_code, r.failure_message,
               r.created_at, r.approved_at, r.provider_submitted_at, r.completed_at, r.failed_at,
               r.rejected_at, r.cancelled_at, p.status::text AS payment_status, p.amount::text AS payment_amount
        FROM edutrust.refunds r JOIN edutrust.payments p ON p.id=r.payment_id
        WHERE r.id=%s
        """,
        [refund_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Refund not found.", 404)
    row["timeline"] = {
        "created_at": row.pop("created_at"),
        "approved_at": row.pop("approved_at"),
        "provider_submitted_at": row.pop("provider_submitted_at"),
        "completed_at": row.pop("completed_at"),
        "failed_at": row.pop("failed_at"),
        "rejected_at": row.pop("rejected_at"),
        "cancelled_at": row.pop("cancelled_at"),
    }
    row["reconciliation"] = (
        {
            "source": row["reconciliation_source"],
            "reference": row["reconciliation_reference"],
            "reconciled_at": row["reconciled_at"],
            "reconciled_by_user_id": row["reconciled_by_user_id"],
        }
        if row["reconciliation_source"] is not None
        else None
    )
    return _serialize_row(row)


def _refund_list_item(row: dict) -> dict:
    return {
        "refund_id": row["id"],
        "payment_id": row["payment_id"],
        "booking_id": row["booking_id"],
        "dispute_id": row["dispute_id"],
        "provider": row["provider"],
        "refund_type": row["refund_type"],
        "status": row["status"],
        "requested_amount": row["requested_amount"],
        "approved_amount": row["approved_amount"],
        "currency": row["currency"],
        "reason_code": row["reason_code"],
        "created_at": row["created_at"],
    }


def create_refund(user_id: str, roles: list[str], payment_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    amount = _refund_amount(data.get("amount"), "amount")
    currency = str(data.get("currency") or "DZD")
    reason = str(data.get("reason") or "").strip()
    dispute_id = data.get("dispute_id") or None
    if currency != "DZD":
        raise ApiError("VALIDATION_ERROR", "currency must be DZD.", 400)
    if len(reason) < 3:
        raise ApiError("VALIDATION_ERROR", "reason must be at least 3 characters.", 400)
    _refund_require_key(idempotency_key)
    canonical = {"payment_id": str(payment_id), "amount": str(amount), "currency": currency, "reason": reason, "dispute_id": dispute_id}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("refund_create", user_id, idempotency_key, request_hash, f"/api/v1/payments/{payment_id}/refund")
        if replay:
            return replay["response_body"]
        payment = _refund_payment_for_update(payment_id)
        fetchone("SELECT id::text FROM edutrust.bookings WHERE id=%s FOR UPDATE", [payment["booking_id"]])
        if payment["status"] not in ("CONFIRMED", "DISPUTED"):
            raise ApiError("REFUND_INVALID_STATE", f"Payment status {payment['status']} is not refundable.", 409, {"payment_status": payment["status"]})
        if dispute_id is not None:
            dispute = fetchone("SELECT booking_id::text FROM edutrust.disputes WHERE id=%s", [dispute_id])
            if not dispute or dispute["booking_id"] != payment["booking_id"]:
                raise ApiError("VALIDATION_ERROR", "dispute_id must belong to this payment's booking.", 400)
        if _refund_reserved_amount(payment_id) + amount > Decimal(payment["amount"]):
            raise ApiError("OVER_REFUND", "Refund request would exceed the payment amount.", 409, {"payment_amount": payment["amount"]})
        refund_type = "FULL" if amount == Decimal(payment["amount"]) else "PARTIAL"
        refund = fetchone(
            """
            INSERT INTO edutrust.refunds (payment_id, booking_id, dispute_id, provider, refund_type, status,
                                          requested_amount, currency, reason, idempotency_key,
                                          requested_by_user_id, requested_by_role)
            VALUES (%s,%s,%s,%s::edutrust.payment_provider,%s::edutrust.refund_type,'REQUESTED',%s,%s,%s,%s,%s,%s)
            RETURNING id::text
            """,
            [payment_id, payment["booking_id"], dispute_id, payment["provider"], refund_type,
             str(amount), currency, reason, idempotency_key, user_id, actor_role],
        )
        write_event("REFUND_REQUESTED", "refund", refund["id"], actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"requested_amount": str(amount), "dev_mock": payment["provider"] == "OTHER"})
        write_event("ADMIN_ACTION", "refund", refund["id"], actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"action": "REFUND_CREATED", "payment_id": payment_id})
        response = {"refund": _refund_detail(refund["id"]), "payment_status": payment["status"]}
        _idempotency_complete("refund_create", user_id, idempotency_key, 201, response, "refund", refund["id"])
    return response


def approve_refund(user_id: str, roles: list[str], refund_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    from .payments import MockPaymentProvider
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    approved = _refund_amount(data.get("approved_amount"), "approved_amount")
    teacher_adj = _refund_nonnegative_amount(data.get("teacher_adjustment_amount"), "teacher_adjustment_amount")
    platform_adj = _refund_nonnegative_amount(data.get("platform_adjustment_amount"), "platform_adjustment_amount")
    reason_code = str(data.get("reason_code") or "").strip() or None
    # D9: allocation is actor-supplied; the only validation is the approved
    # accounting constraint (sum must equal approved_amount). No formula.
    if teacher_adj + platform_adj != approved:
        raise ApiError("VALIDATION_ERROR",
                       "teacher_adjustment_amount + platform_adjustment_amount must equal approved_amount.",
                       400, {"teacher": str(teacher_adj), "platform": str(platform_adj), "approved": str(approved)})
    _refund_require_key(idempotency_key)
    canonical = {"refund_id": str(refund_id), "approved_amount": str(approved),
                 "teacher_adjustment_amount": str(teacher_adj), "platform_adjustment_amount": str(platform_adj),
                 "reason_code": reason_code}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    # TX1: approve + DRAFT ledger (balanced), payment -> REFUND_PENDING.
    with tx():
        replay = _idempotency_begin("refund_approve", user_id, idempotency_key, request_hash, f"/api/v1/admin/refunds/{refund_id}/approve")
        if replay:
            return replay["response_body"]
        refund_payment_row = fetchone("SELECT payment_id::text FROM edutrust.refunds WHERE id=%s", [refund_id])
        if not refund_payment_row:
            raise ApiError("RESOURCE_NOT_FOUND", "Refund not found.", 404)
        payment_id = refund_payment_row["payment_id"]
        payment = _refund_payment_for_update(payment_id)
        refund = _refund_row_for_update(refund_id)
        if refund["status"] != "REQUESTED":
            raise ApiError("REFUND_INVALID_STATE", f"Refund must be REQUESTED to approve (current: {refund['status']}).", 409, {"refund_status": refund["status"]})
        if approved > Decimal(refund["requested_amount"]):
            raise ApiError("VALIDATION_ERROR", "approved_amount cannot exceed requested_amount.", 400)
        if refund["refund_type"] == "FULL" and approved != Decimal(payment["amount"]):
            raise ApiError("VALIDATION_ERROR", "FULL refund must approve the full payment amount.", 400)
        if refund["refund_type"] == "PARTIAL" and approved >= Decimal(payment["amount"]):
            raise ApiError("VALIDATION_ERROR", "PARTIAL refund must approve less than the payment amount.", 400)
        if _refund_reserved_amount(payment_id, refund_id) + approved > Decimal(payment["amount"]):
            raise ApiError("OVER_REFUND", "Refund approval would exceed the payment amount.", 409, {"payment_amount": payment["amount"]})
        prior_status = payment["status"]
        form = _refund_ledger_form(payment["booking_id"])
        execute(
            """
            UPDATE edutrust.refunds
            SET status='APPROVED', approved_amount=%s, approved_at=now(), approved_by_user_id=%s,
                approved_by_role=%s, teacher_adjustment_amount=%s, platform_adjustment_amount=%s,
                reason_code=COALESCE(%s, reason_code),
                metadata = metadata || jsonb_build_object('payment_status_before_refund', %s::text)
            WHERE id=%s
            """,
            [str(approved), user_id, actor_role, str(teacher_adj), str(platform_adj), reason_code, prior_status, refund_id],
        )
        execute("UPDATE edutrust.payments SET status='REFUND_PENDING', updated_at=now() WHERE id=%s", [payment_id])
        _create_refund_ledger_draft(refund_id, payment_id, payment["booking_id"], form, approved, teacher_adj, platform_adj)
        write_event("REFUND_APPROVED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id,
                    metadata={"approved_amount": str(approved), "teacher_adjustment_amount": str(teacher_adj),
                              "platform_adjustment_amount": str(platform_adj), "ledger_form": form})
        write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"action": "REFUND_APPROVED", "ledger_form": form})
    # Outside the DB transaction (API 12.6): DEV mock provider call (D1).
    submission = MockPaymentProvider().initiate_refund(payment_id=payment_id, amount=str(approved), currency=payment["currency"])
    # TX2: record provider event + PROVIDER_PENDING + REFUND_PROVIDER_SUBMITTED.
    with tx():
        refund = _refund_row_for_update(refund_id)
        if refund["status"] != "APPROVED":
            raise ApiError("REFUND_INVALID_STATE",
                           "Refund is no longer APPROVED; submission aborted. Operator may cancel and create a new refund.",
                           409, {"refund_status": refund["status"]})
        event = fetchone(
            """
            INSERT INTO edutrust.payment_provider_events (provider, provider_event_id, provider_refund_id,
                                                          event_type, status, refund_id, amount, currency, normalized_payload)
            VALUES (%s::edutrust.payment_provider, %s, %s, 'refund.initiated', 'RECEIVED', %s, %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            [payment["provider"], f"mock_evt_{uuid.uuid4()}", submission["provider_refund_id"],
             refund_id, str(approved), payment["currency"], '{"provider":"MockPaymentProvider"}'],
        )
        execute("UPDATE edutrust.payment_provider_events SET status='PROCESSING', processing_attempts=processing_attempts+1, updated_at=now() WHERE id=%s", [event["id"]])
        execute("UPDATE edutrust.refunds SET status='PROVIDER_PENDING', provider_refund_id=%s, provider_submitted_at=now(), updated_at=now() WHERE id=%s",
                [submission["provider_refund_id"], refund_id])
        execute("UPDATE edutrust.payment_provider_events SET status='PROCESSED', processed_at=now(), updated_at=now() WHERE id=%s", [event["id"]])
        write_event("REFUND_PROVIDER_SUBMITTED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"provider_refund_id": submission["provider_refund_id"], "dev_mock": True})
        response = {"refund": _refund_detail(refund_id), "payment_status": "REFUND_PENDING"}
        _idempotency_complete("refund_approve", user_id, idempotency_key, 200, response, "refund", refund_id)
    return response


def _refund_close_simple(user_id: str, roles: list[str], refund_id: str, data: dict, idempotency_key: str | None,
                         scope: str, transition: str, to_status: str, from_status: tuple[str, ...],
                         reason_field: str, event_type: str, action: str, metadata_key: str,
                         request_id: str | None = None) -> dict:
    import json
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    reason = str(data.get(reason_field) or "").strip()
    if len(reason) < 3:
        raise ApiError("VALIDATION_ERROR", f"{reason_field} must be at least 3 characters.", 400)
    _refund_require_key(idempotency_key)
    canonical = {"refund_id": str(refund_id), reason_field: reason}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin(scope, user_id, idempotency_key, request_hash, f"/api/v1/admin/refunds/{refund_id}/{transition}")
        if replay:
            return replay["response_body"]
        refund_payment_row = fetchone("SELECT payment_id::text FROM edutrust.refunds WHERE id=%s", [refund_id])
        if not refund_payment_row:
            raise ApiError("RESOURCE_NOT_FOUND", "Refund not found.", 404)
        payment_id = refund_payment_row["payment_id"]
        payment = _refund_payment_for_update(payment_id)
        refund = _refund_row_for_update(refund_id)
        if refund["status"] not in from_status:
            raise ApiError("REFUND_INVALID_STATE",
                           f"Refund must be one of {', '.join(from_status)} for {transition} (current: {refund['status']}).",
                           409, {"refund_status": refund["status"]})
        timestamp = "rejected_at" if transition == "reject" else "cancelled_at"
        execute(
            f"""
            UPDATE edutrust.refunds
            SET status=%s, {timestamp}=now(),
                metadata = metadata || jsonb_build_object(%s, %s::text)
            WHERE id=%s
            """,
            [to_status, metadata_key, reason, refund_id],
        )
        payment_status = payment["status"]
        if transition == "cancel" and refund["status"] == "APPROVED":
            # Payment was moved to REFUND_PENDING at approval; restore it
            # (SM 7.6 refund-failure handling) and void the draft ledger.
            prior = _refund_prior_payment_status(refund)
            execute("UPDATE edutrust.payments SET status=%s, updated_at=now() WHERE id=%s", [prior, payment_id])
            payment_status = prior
            _set_refund_ledger_status(refund_id, "VOIDED")
        write_event(event_type, "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={metadata_key: reason})
        write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"action": action, "refund_status": to_status})
        response = {"refund": _refund_detail(refund_id), "payment_status": payment_status}
        _idempotency_complete(scope, user_id, idempotency_key, 200, response, "refund", refund_id)
    return response


def reject_refund(user_id: str, roles: list[str], refund_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    return _refund_close_simple(user_id, roles, refund_id, data, idempotency_key,
                                 "refund_reject", "reject", "REJECTED", ("REQUESTED",), "reason",
                                 "REFUND_REJECTED", "REFUND_REJECTED", "rejection_reason", request_id)


def cancel_refund(user_id: str, roles: list[str], refund_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    return _refund_close_simple(user_id, roles, refund_id, data, idempotency_key,
                                 "refund_cancel", "cancel", "CANCELLED", ("REQUESTED", "APPROVED"), "reason",
                                 "REFUND_CANCELLED", "REFUND_CANCELLED", "cancellation_reason", request_id)


def process_mock_refund_result(user_id: str, roles: list[str], refund_id: str, outcome: str,
                               provider_event_id: str | None = None, request_id: str | None = None) -> dict:
    if not settings.MOCK_PAYMENT_PROVIDER_ENABLED or settings.REAL_PAYMENT_ENABLED:
        raise ApiError("FORBIDDEN", "Mock provider controls are DEV-only.", 403)
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    if outcome not in ("succeeded", "failed"):
        raise ApiError("VALIDATION_ERROR", "outcome must be succeeded or failed.", 400)
    provider_event_id = str(provider_event_id or f"mock_evt_{uuid.uuid4()}")
    event_kind = "refund.succeeded" if outcome == "succeeded" else "refund.failed"
    conflict_ctx: dict | None = None
    try:
      with tx():
        # Event identity first (Addendum 15.1), VS2 pattern: provider fixed
        # to 'OTHER' (the mock provider identity in this DEV deployment).
        existing_event = fetchone(
            "SELECT id::text, status::text, refund_id::text, provider_refund_id FROM edutrust.payment_provider_events "
            "WHERE provider='OTHER' AND provider_event_id=%s FOR UPDATE",
            [provider_event_id],
        )
        refund = _refund_row_for_update(refund_id)
        # Identity conflict first (SM 7.8): the provider event identity is
        # already linked to a different refund (or is a non-refund event).
        if existing_event and str(existing_event["refund_id"]) != str(refund_id):
            # REJECTED is only settable from non-terminal states (v1.2 lifecycle
            # guard); terminal rows are already the audit trail.
            if existing_event["status"] in ("RECEIVED", "PROCESSING"):
                execute("UPDATE edutrust.payment_provider_events SET status='REJECTED', last_error_code='PAYMENT_PROVIDER_CONFLICT', updated_at=now() WHERE id=%s", [existing_event["id"]])
            conflict_ctx = {"refund_id": refund_id, "provider_event_id": provider_event_id}
            raise ApiError("PAYMENT_PROVIDER_CONFLICT", "Provider event identity is already linked to a different refund.", 409)
        # SM 7.8: an already-PROCESSED provider event replays as 200 with the
        # recorded outcome, no state re-mutation — checked before any
        # refund-state precondition.
        if existing_event and existing_event["status"] == "PROCESSED":
            payment_now = fetchone("SELECT status::text FROM edutrust.payments WHERE id=%s", [refund["payment_id"]])
            return {
                "duplicate": True,
                "provider_event_id": provider_event_id,
                "refund_id": refund_id,
                "refund_status": refund["status"],
                "payment_status": payment_now["status"],
            }
        payment = _refund_payment_for_update(refund["payment_id"])
        if refund["status"] != "PROVIDER_PENDING":
            raise ApiError("REFUND_INVALID_STATE", f"Refund must be PROVIDER_PENDING for a provider result (current: {refund['status']}).", 409, {"refund_status": refund["status"]})
        if existing_event:
            if existing_event["status"] in ("RECEIVED", "PROCESSING"):
                raise ApiError("PAYMENT_PROVIDER_EVENT_IN_PROGRESS", "Provider event is already being processed or rejected.", 409)
            event_id = existing_event["id"]
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSING', processing_attempts=processing_attempts+1, updated_at=now() WHERE id=%s", [event_id])
        else:
            event = fetchone(
                """
                INSERT INTO edutrust.payment_provider_events (provider, provider_event_id, provider_refund_id,
                                                              event_type, status, refund_id, amount, currency, normalized_payload)
                VALUES ('OTHER', %s, %s, %s, 'RECEIVED', %s, %s, %s, %s::jsonb)
                RETURNING id::text
                """,
                [provider_event_id, refund["provider_refund_id"], event_kind, refund_id,
                 refund["approved_amount"], refund["currency"], '{"provider":"MockPaymentProvider"}'],
            )
            event_id = event["id"]
            execute("UPDATE edutrust.payment_provider_events SET status='PROCESSING', processing_attempts=processing_attempts+1, updated_at=now() WHERE id=%s", [event_id])
        if outcome == "succeeded":
            execute("UPDATE edutrust.refunds SET status='SUCCEEDED', completed_at=now(), updated_at=now() WHERE id=%s", [refund_id])
            new_payment_status = _refund_payment_status_after_success(payment["id"])
            execute("UPDATE edutrust.payments SET status=%s, refunded_at=now(), updated_at=now() WHERE id=%s", [new_payment_status, payment["id"]])
            _set_refund_ledger_status(refund_id, "POSTED")
            write_event("REFUND_SUCCEEDED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"provider_event_id": provider_event_id, "dev_mock": True})
            payment_event = "PAYMENT_REFUNDED" if new_payment_status == "REFUNDED" else "PAYMENT_PARTIALLY_REFUNDED"
            write_event(payment_event, "payment", payment["id"], actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"refund_id": refund_id, "dev_mock": True})
            write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"action": "REFUND_MOCK_SUCCEEDED", "provider_event_id": provider_event_id})
            refund_status, payment_status = "SUCCEEDED", new_payment_status
        else:
            prior = _refund_prior_payment_status(refund)
            execute(
                "UPDATE edutrust.refunds SET status='FAILED', failed_at=now(), failure_code='PROVIDER_REFUND_FAILED', "
                "failure_message='Mock provider refund failure (DEV).', updated_at=now() WHERE id=%s",
                [refund_id],
            )
            execute("UPDATE edutrust.payments SET status=%s, updated_at=now() WHERE id=%s", [prior, payment["id"]])
            _set_refund_ledger_status(refund_id, "VOIDED")
            write_event("REFUND_FAILED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"failure_code": "PROVIDER_REFUND_FAILED", "provider_event_id": provider_event_id})
            write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"action": "REFUND_MOCK_FAILED", "provider_event_id": provider_event_id})
            refund_status, payment_status = "FAILED", prior
        execute("UPDATE edutrust.payment_provider_events SET status='PROCESSED', processed_at=now(), updated_at=now() WHERE id=%s", [event_id])
      return {
        "duplicate": False,
        "provider_event_id": provider_event_id,
        "refund_id": refund_id,
        "refund_status": refund_status,
        "payment_status": payment_status,
    }
    except ApiError as exc:
        if conflict_ctx is not None:
            # Audit the conflict in its own committed transaction (the main
            # transaction rolled back).
            try:
                with tx():
                    write_security_event("SUSPICIOUS_ACTIVITY", user_id=user_id, severity=2,
                                         metadata={"entity": "refund", "entity_id": conflict_ctx["refund_id"],
                                                   "provider_event_id": conflict_ctx["provider_event_id"],
                                                   "request_id": request_id})
            except Exception:
                pass
        raise


def reconcile_refund(user_id: str, roles: list[str], refund_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    from django.utils import dateparse
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    result = str(data.get("result") or "").upper()
    source = str(data.get("reconciliation_source") or "").strip()
    reference = str(data.get("reconciliation_reference") or "").strip()
    reconciled_at_raw = data.get("reconciled_at")
    reason = str(data.get("reason") or "").strip()
    evidence = data.get("supporting_evidence") or []
    if result not in ("SUCCEEDED", "FAILED"):
        raise ApiError("VALIDATION_ERROR", "result must be SUCCEEDED or FAILED.", 400)
    if not source:
        raise ApiError("REFUND_RECONCILIATION_PROOF_REQUIRED", "reconciliation_source is required.", 400)
    if not reference:
        raise ApiError("REFUND_RECONCILIATION_PROOF_REQUIRED", "reconciliation_reference must be non-empty.", 400)
    if not reconciled_at_raw:
        raise ApiError("REFUND_RECONCILIATION_PROOF_REQUIRED", "reconciled_at is required.", 400)
    reconciled_at = dateparse.parse_datetime(str(reconciled_at_raw))
    if reconciled_at is None:
        raise ApiError("VALIDATION_ERROR", "reconciled_at must be an ISO-8601 timestamp.", 400)
    if len(reason) < 3:
        raise ApiError("VALIDATION_ERROR", "reason must be at least 3 characters.", 400)
    if not isinstance(evidence, list):
        raise ApiError("VALIDATION_ERROR", "supporting_evidence must be a list of references.", 400)
    if source == "ADMIN_OVERRIDE" and "ADMIN" not in roles:
        raise ApiError("FORBIDDEN", "ADMIN_OVERRIDE reconciliation requires ADMIN authority.", 403)
    _refund_require_key(idempotency_key)
    canonical = {"refund_id": str(refund_id), "result": result, "reconciliation_source": source,
                 "reconciliation_reference": reference, "reconciled_at": str(reconciled_at), "reason": reason,
                 "supporting_evidence": evidence}
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    # PLAN-LOCK: reconcile is allowed from PROVIDER_PENDING only (the only
    # state that legally reaches a terminal state via reconciliation).
    with tx():
        replay = _idempotency_begin("refund_reconcile", user_id, idempotency_key, request_hash, f"/api/v1/admin/refunds/{refund_id}/reconcile")
        if replay:
            return replay["response_body"]
        refund_payment_row = fetchone("SELECT payment_id::text FROM edutrust.refunds WHERE id=%s", [refund_id])
        if not refund_payment_row:
            raise ApiError("RESOURCE_NOT_FOUND", "Refund not found.", 404)
        payment_id = refund_payment_row["payment_id"]
        payment = _refund_payment_for_update(payment_id)
        refund = _refund_row_for_update(refund_id)
        if refund["status"] != "PROVIDER_PENDING":
            raise ApiError("REFUND_INVALID_STATE", f"Refund must be PROVIDER_PENDING to reconcile (current: {refund['status']}).", 409, {"refund_status": refund["status"]})
        if result == "SUCCEEDED":
            execute(
                "UPDATE edutrust.refunds SET status='SUCCEEDED', completed_at=now(), reconciliation_source=%s, "
                "reconciliation_reference=%s, reconciled_at=%s, reconciled_by_user_id=%s, updated_at=now() WHERE id=%s",
                [source, reference, reconciled_at, user_id, refund_id],
            )
            new_payment_status = _refund_payment_status_after_success(payment["id"])
            execute("UPDATE edutrust.payments SET status=%s, refunded_at=now(), updated_at=now() WHERE id=%s", [new_payment_status, payment["id"]])
            _set_refund_ledger_status(refund_id, "POSTED")
            write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"action": "REFUND_RECONCILED", "reconciliation_source": source,
                                                         "reconciliation_reference": reference})
            write_event("REFUND_SUCCEEDED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"reconciliation_source": source})
            payment_event = "PAYMENT_REFUNDED" if new_payment_status == "REFUNDED" else "PAYMENT_PARTIALLY_REFUNDED"
            write_event(payment_event, "payment", payment["id"], actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"refund_id": refund_id})
            payment_status = new_payment_status
        else:
            prior = _refund_prior_payment_status(refund)
            execute(
                "UPDATE edutrust.refunds SET status='FAILED', failed_at=now(), failure_code='RECONCILIATION_FAILED', "
                "failure_message=%s, reconciliation_source=%s, reconciliation_reference=%s, reconciled_at=%s, "
                "reconciled_by_user_id=%s, updated_at=now() WHERE id=%s",
                [reason, source, reference, reconciled_at, user_id, refund_id],
            )
            execute("UPDATE edutrust.payments SET status=%s, updated_at=now() WHERE id=%s", [prior, payment["id"]])
            _set_refund_ledger_status(refund_id, "VOIDED")
            write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"action": "REFUND_RECONCILED", "reconciliation_source": source,
                                                         "reconciliation_reference": reference})
            write_event("REFUND_FAILED", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                        request_id=request_id, metadata={"reconciliation_source": source})
            payment_status = prior
        response = {"refund": _refund_detail(refund_id), "payment_status": payment_status}
        _idempotency_complete("refund_reconcile", user_id, idempotency_key, 200, response, "refund", refund_id)
    return response


def list_admin_refunds(user_id: str, roles: list[str], params: dict, request_id: str | None = None) -> dict:
    # Addendum 7.1: ordinary list read generates no event; sensitive
    # drilldown is audited in the detail endpoint.
    conds: list[str] = []
    sql_params: list = []
    for field, column in (("status", "r.status::text"), ("provider", "r.provider::text"),
                          ("dispute_id", "r.dispute_id::text"), ("payment_id", "r.payment_id::text")):
        value = str(params.get(field) or "").strip()
        if value:
            conds.append(f"{column}=%s")
            sql_params.append(value)
    frm = str(params.get("from") or "").strip()
    to = str(params.get("to") or "").strip()
    if frm:
        conds.append("r.created_at >= %s")
        sql_params.append(frm)
    if to:
        conds.append("r.created_at <= %s")
        sql_params.append(to)
    try:
        limit = max(1, min(int(params.get("limit") or 20), 100))
    except (TypeError, ValueError):
        limit = 20
    cursor = str(params.get("cursor") or "").strip()
    if cursor:
        conds.append("r.created_at < (SELECT created_at FROM edutrust.refunds WHERE id=%s)")
        sql_params.append(cursor)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    rows = fetchall(
        f"""
        SELECT r.id::text, r.payment_id::text, r.booking_id::text, r.dispute_id::text, r.provider::text,
               r.refund_type::text, r.status::text, r.requested_amount::text, r.approved_amount::text,
               r.currency, r.reason_code, r.created_at
        FROM edutrust.refunds r{where}
        ORDER BY r.created_at DESC, r.id
        LIMIT {limit + 1}
        """,
        sql_params,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_serialize_row(_refund_list_item(r)) for r in rows]
    return {
        "data": items,
        "pagination": {"limit": limit, "next_cursor": items[-1]["refund_id"] if has_more else None, "has_more": has_more},
    }


def get_admin_refund(user_id: str, roles: list[str], refund_id: str, request_id: str | None = None) -> dict:
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    write_event("ADMIN_ACTION", "refund", refund_id, actor_user_id=user_id, actor_role=actor_role,
                request_id=request_id, metadata={"action": "READ_REFUND_DETAIL"})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2,
                         metadata={"entity": "refund", "entity_id": refund_id, "request_id": request_id})
    detail = _refund_detail(refund_id)
    events = fetchall(
        """
        SELECT provider_event_id, provider_refund_id, event_type, status::text, received_at, processed_at
        FROM edutrust.payment_provider_events WHERE refund_id=%s ORDER BY received_at
        """,
        [refund_id],
    )
    detail["provider_event_summary"] = _serialize_row_rows(events)
    return detail


# ---- Vertical Slice 9: dispute resolution (CORE — RESOLVED path, nine actions) ----
#
# Baselines: State Machines v1.0 section 11 (transitions/actions/effects/forbidden/audit),
# API Architecture section 19.4 (resolve contract) and section 21.3 (admin list),
# State Machines v1.1 Addendum section 4.1 (overlay — booking/session never DISPUTED),
# PRD section 17 (dispute flow v0), VS9 Implementation Plan v1.0 decisions:
#   P1: two-step refund — resolve creates the REQUESTED refund (dispute-linked); the
#       operator completes it through the existing VS8 approve endpoint with allocation.
#       No allocation field is accepted on the resolve request (contract-pure).
#   P2: REPORT_CORRECTION_REQUIRED is record-only (correction workflow = R14, out of scope).
#   P3: GET /admin/disputes is a dedicated route (SUPPORT/OPS/ADMIN per API 21.3); reads audited.
#   P4: OPS may resolve non-SAFETY refund actions; ADMIN required for SAFETY disputes and
#       for FULL_REFUND after a COMPLETED session (SM section 18.2 ADMIN-override class).
#   P5: REJECTED / CANCELLED outcomes and the UNDER_REVIEW assignment mechanism are DEFERRED
#       (contract gaps — not implemented in VS9).
# Excluded: account actions (R10 — spec UNKNOWN), suspension effects, real provider, production UI.
# Lock order (acyclic, refined per plan section 19 — session locked before payment so the
# no-show path never inverts VS5 payout's session-first order):
#   dispute -> session (no-show actions) -> payment -> booking (inside VS8 create_refund)

DISPUTE_RESOLVE_ACTIONS = {
    "NO_ACTION", "WARNING", "FULL_REFUND", "PARTIAL_REFUND",
    "PAYOUT_BLOCKED", "PAYOUT_RELEASED",
    "TEACHER_NO_SHOW_CONFIRMED", "STUDENT_NO_SHOW_CONFIRMED",
    "REPORT_CORRECTION_REQUIRED",
}
DISPUTE_REFUND_ACTIONS = {"FULL_REFUND", "PARTIAL_REFUND"}
DISPUTE_NOSHOW_ACTIONS = {
    "TEACHER_NO_SHOW_CONFIRMED": "TEACHER",
    "STUDENT_NO_SHOW_CONFIRMED": "STUDENT",
}
DISPUTE_RESOLVABLE_STATUSES = ("OPEN", "UNDER_REVIEW")


def _dispute_resolve_row_for_update(dispute_id: str) -> dict:
    row = fetchone(
        """
        SELECT d.id::text, d.booking_id::text, d.session_id::text, d.payment_id::text,
               d.opened_by_user_id::text, d.category::text, d.status::text, d.priority,
               d.description, d.assigned_admin_user_id::text, d.resolution, d.resolved_at,
               d.created_at, d.updated_at
        FROM edutrust.disputes d WHERE d.id=%s FOR UPDATE
        """,
        [dispute_id],
    )
    if not row:
        raise ApiError("RESOURCE_NOT_FOUND", "Dispute not found.", 404)
    return row


def _linked_payment_for_dispute(dispute: dict) -> dict:
    """Identify the payment a dispute refund must target. The dispute always carries a
    derived booking_id (VS4 open_dispute). The refundable-payment state check itself is
    left to the VS8 create_refund service (do not bypass VS8 validation)."""
    if dispute["payment_id"]:
        payment = fetchone(
            "SELECT id::text, booking_id::text, amount::text, status::text FROM edutrust.payments WHERE id=%s",
            [dispute["payment_id"]],
        )
    else:
        payment = fetchone(
            "SELECT id::text, booking_id::text, amount::text, status::text FROM edutrust.payments "
            "WHERE booking_id=%s ORDER BY created_at DESC LIMIT 1",
            [dispute["booking_id"]],
        )
    if not payment:
        raise ApiError("REFUND_INVALID_STATE", "No payment found for this dispute.", 409, {"detail": "no payment on dispute or booking"})
    return payment


def _dispute_detail_payload(dispute_id: str) -> dict:
    """Response payload for a resolved dispute (VS4/VS8 read shape: access row + party
    names + linked_refunds). No read-audit event here — the resolving operation is
    itself audited (DISPUTE_RESOLVED + ADMIN_ACTION)."""
    row = _dispute_access_row(dispute_id)
    teacher = fetchone("SELECT public_name FROM edutrust.teacher_profiles WHERE id=(SELECT teacher_id FROM edutrust.bookings WHERE id=%s)", [row["booking_id"]])
    student = fetchone("SELECT display_name FROM edutrust.student_profiles WHERE id=(SELECT student_id FROM edutrust.bookings WHERE id=%s)", [row["booking_id"]])
    row["teacher_public_name"] = teacher["public_name"] if teacher else None
    row["student_display_name"] = student["display_name"] if student else None
    linked = fetchall(
        "SELECT id::text AS refund_id, status::text, approved_amount::text, currency FROM edutrust.refunds WHERE dispute_id=%s ORDER BY created_at",
        [dispute_id],
    )
    if linked:
        row["linked_refunds"] = _serialize_row_rows(linked)
    return _serialize_row(row)


def resolve_dispute(user_id: str, roles: list[str], dispute_id: str, data: dict, idempotency_key: str | None, request_id: str | None = None) -> dict:
    import json
    # The URL converter passes dispute_id as a uuid.UUID; the service normalizes to str
    # once, before the plain-json idempotency canonical (VS8 convention: create_refund /
    # approve_refund stringify their id in the canonical). Every downstream use (row lock,
    # nested create_refund data, path f-string, idempotency resource_id) then sees a str.
    dispute_id = str(dispute_id)
    actor_role = "ADMIN" if "ADMIN" in roles else "OPS"
    resolution = str(data.get("resolution") or "").strip()
    action = str(data.get("action") or "").upper()
    refund_amount_raw = data.get("refund_amount")
    account_action = data.get("account_action")
    if action not in DISPUTE_RESOLVE_ACTIONS:
        raise ApiError("VALIDATION_ERROR", f"action must be one of {sorted(DISPUTE_RESOLVE_ACTIONS)}.", 400, {"actions": sorted(DISPUTE_RESOLVE_ACTIONS)})
    if len(resolution) < 3:
        raise ApiError("VALIDATION_ERROR", "resolution must be at least 3 characters.", 400)
    # Account actions are excluded from VS9 (R10 spec UNKNOWN) — never interpreted.
    if account_action is not None:
        raise ApiError("VALIDATION_ERROR", "account_action is not supported in this slice (account actions are deferred).", 400)
    refund_amount = None
    if action in DISPUTE_REFUND_ACTIONS:
        refund_amount = _refund_amount(refund_amount_raw, "refund_amount")
    elif refund_amount_raw is not None:
        raise ApiError("VALIDATION_ERROR", "refund_amount is only valid for FULL_REFUND and PARTIAL_REFUND actions.", 400)
    _refund_require_key(idempotency_key)
    canonical = {
        "dispute_id": str(dispute_id),
        "resolution": resolution,
        "action": action,
        "refund_amount": str(refund_amount) if refund_amount is not None else None,
        "account_action": None,
    }
    request_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    with tx():
        replay = _idempotency_begin("dispute_resolve", user_id, idempotency_key, request_hash, f"/api/v1/admin/disputes/{dispute_id}/resolve")
        if replay:
            return replay["response_body"]
        dispute = _dispute_resolve_row_for_update(dispute_id)
        if dispute["status"] not in DISPUTE_RESOLVABLE_STATUSES:
            raise ApiError("DISPUTE_INVALID_STATE", f"Dispute must be OPEN or UNDER_REVIEW to resolve (current: {dispute['status']}).", 409, {"dispute_status": dispute["status"]})
        # P4: SAFETY disputes require ADMIN (API 19.4).
        if dispute["category"] == "SAFETY" and "ADMIN" not in roles:
            raise ApiError("FORBIDDEN", "SAFETY disputes require ADMIN authority to resolve.", 403)
        # Session lock BEFORE payment (lock-order refinement, plan section 19).
        session_row = None
        if dispute["session_id"]:
            if action in DISPUTE_NOSHOW_ACTIONS:
                session_row = fetchone("SELECT id::text, status::text FROM edutrust.sessions WHERE id=%s FOR UPDATE", [dispute["session_id"]])
            else:
                session_row = fetchone("SELECT id::text, status::text FROM edutrust.sessions WHERE id=%s", [dispute["session_id"]])
            if not session_row:
                raise ApiError("RESOURCE_NOT_FOUND", "Dispute session not found.", 404)
        # P4 (SM 18.2): FULL_REFUND after a COMPLETED session is ADMIN-override class.
        if action == "FULL_REFUND" and session_row is not None and session_row["status"] == "COMPLETED" and "ADMIN" not in roles:
            raise ApiError("FORBIDDEN", "Full refund after a completed session requires ADMIN authority.", 403)
        # No-show confirmations: reuse the existing VS3 no-show path only when the
        # session is SCHEDULED (plan section 9); otherwise record-only.
        if action in DISPUTE_NOSHOW_ACTIONS and session_row is not None and session_row["status"] == "SCHEDULED":
            record_session_no_show(user_id, roles, dispute["session_id"], DISPUTE_NOSHOW_ACTIONS[action], request_id=request_id)
        refund_id = None
        refund_detail = None
        if action in DISPUTE_REFUND_ACTIONS:
            payment = _linked_payment_for_dispute(dispute)
            if action == "FULL_REFUND" and refund_amount != Decimal(payment["amount"]):
                raise ApiError("VALIDATION_ERROR", "FULL_REFUND refund_amount must equal the payment amount.", 400, {"payment_amount": payment["amount"], "refund_amount": str(refund_amount)})
            if action == "PARTIAL_REFUND" and refund_amount >= Decimal(payment["amount"]):
                raise ApiError("VALIDATION_ERROR", "PARTIAL_REFUND refund_amount must be less than the payment amount.", 400, {"payment_amount": payment["amount"], "refund_amount": str(refund_amount)})
            # P1 two-step: the VS8 create is nested (savepoint). Any VS8 error
            # (state/over-refund/booking mismatch) rolls back the whole resolution —
            # no half-resolved dispute, no duplicate refund. The deterministic derived
            # key is defense-in-depth against a second refund row for this dispute.
            refund_resp = create_refund(
                user_id, roles, payment["id"],
                {"amount": str(refund_amount), "currency": "DZD", "reason": resolution, "dispute_id": dispute_id},
                idempotency_key=f"dispute-resolve-{dispute_id}",
                request_id=request_id,
            )
            refund_id = refund_resp["refund"]["refund_id"]
            refund_detail = refund_resp["refund"]
        execute(
            "UPDATE edutrust.disputes SET status='RESOLVED', resolution=%s, resolved_at=now(), assigned_admin_user_id=%s, updated_at=now() WHERE id=%s",
            [resolution, user_id, dispute_id],
        )
        write_event("DISPUTE_RESOLVED", "dispute", dispute_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"action": action, "refund_id": refund_id, "account_action": None})
        write_event("ADMIN_ACTION", "dispute", dispute_id, actor_user_id=user_id, actor_role=actor_role,
                    request_id=request_id, metadata={"action": f"DISPUTE_RESOLVED:{action}", "dispute_id": dispute_id, "refund_id": refund_id, "request_id": request_id})
        response = {"dispute": _dispute_detail_payload(dispute_id)}
        if refund_detail is not None:
            response["refund"] = refund_detail
        _idempotency_complete("dispute_resolve", user_id, idempotency_key, 200, response, "dispute", dispute_id)
    return response


def list_admin_disputes(user_id: str, roles: list[str], params: dict, request_id: str | None = None) -> dict:
    """Admin/OPS/SUPPORT dispute monitoring list (API 21.3; plan P3 — reads audited,
    matching the VS4 dispute-list audit precedent and the API section 21 admin-operation
    audit rule). The UX-patch resolution_action filter is NOT supported (no action
    column in the approved schema — plan P3)."""
    actor_role = "ADMIN" if "ADMIN" in roles else ("OPS" if "OPS" in roles else "SUPPORT")
    write_event("ADMIN_ACTION", "disputes", None, actor_user_id=user_id, actor_role=actor_role,
                request_id=request_id, metadata={"action": "READ_DISPUTE_LIST", "admin_list": True})
    write_security_event("ADMIN_ACCESS", user_id=user_id, severity=2, metadata={"entity": "disputes", "request_id": request_id})
    conds: list[str] = []
    sql_params: list = []
    for field, column, is_int in (("status", "d.status::text", False), ("category", "d.category::text", False), ("priority", "d.priority", True)):
        value = str(params.get(field) or "").strip()
        if value:
            if is_int:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    raise ApiError("VALIDATION_ERROR", "priority filter must be an integer between 1 and 5.", 400)
            conds.append(f"{column}=%s")
            sql_params.append(value)
    frm = str(params.get("from") or "").strip()
    to = str(params.get("to") or "").strip()
    if frm:
        conds.append("d.created_at >= %s")
        sql_params.append(frm)
    if to:
        conds.append("d.created_at <= %s")
        sql_params.append(to)
    try:
        limit = max(1, min(int(params.get("limit") or 20), 100))
    except (TypeError, ValueError):
        limit = 20
    cursor = str(params.get("cursor") or "").strip()
    if cursor:
        conds.append("d.created_at < (SELECT created_at FROM edutrust.disputes WHERE id=%s)")
        sql_params.append(cursor)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    rows = fetchall(
        f"""
        SELECT d.id::text, d.booking_id::text, d.session_id::text, d.payment_id::text, d.opened_by_user_id::text,
               d.category::text, d.status::text, d.priority, d.description, d.assigned_admin_user_id::text,
               d.resolution, d.resolved_at, d.created_at,
               tp.public_name AS teacher_public_name, sp.display_name AS student_display_name
        FROM edutrust.disputes d
        JOIN edutrust.bookings b ON b.id=d.booking_id
        JOIN edutrust.teacher_profiles tp ON tp.id=b.teacher_id
        JOIN edutrust.student_profiles sp ON sp.id=b.student_id
        {where}
        ORDER BY d.created_at DESC
        LIMIT {limit + 1}
        """,
        sql_params,
    )
    has_more = len(rows) > limit
    items = _serialize_row_rows(rows[:limit])
    return {
        "data": items,
        "pagination": {"limit": limit, "next_cursor": items[-1]["id"] if has_more else None, "has_more": has_more},
    }


# ---- DEV Vertical Slice 10: R6 Auth completion (approved: VS10 R6 Implementation
# Authorization v1.0 — D1/D2 locks + D3a baseline) ----
#
# POST /auth/refresh (D1) and POST /auth/revoke-sessions (D2).
# D3a baseline: strict one-use rotation over the EXISTING auth_sessions schema
# (one current hash per session; no previous-hash column, no token history, no
# session family, no schema change). A rotated-out token is unrecoverable as
# "this session's old token" — it fails verification exactly like any unknown
# token (uniform 401). That is the schema-supported extent of API §3.5 bullet 5
# under its own "where supported" clause; the limitation is documented in the
# slice report (compliance note). No security downgrade: the old token is dead
# by hash replacement in the same transaction.

REVOKE_SCOPES = ("CURRENT", "OTHERS", "ALL")


def refresh_tokens(refresh_token: str, request_id: str | None = None) -> dict:
    """POST /api/v1/auth/refresh (D1). Atomically rotate the refresh token of an
    active session; re-issue the access token for the SAME session (sid preserved,
    roles re-read server-side, existing TTL conventions)."""
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise ApiError("AUTH_INVALID_REFRESH_TOKEN", "Invalid or expired refresh token.", 401)
    token_hash = hash_token(refresh_token.strip())
    with tx():
        session = fetchone(
            "SELECT id::text, user_id::text, revoked_at, expires_at "
            "FROM edutrust.auth_sessions WHERE refresh_token_hash = %s FOR UPDATE",
            [token_hash],
        )
        # Uniform 401 for every token-validation outcome (D1.5/D3.3): unknown hash,
        # revoked session, expired session, rotated-out (old) token — indistinguishable,
        # no existence oracle (D3.4).
        if not session or session["revoked_at"] is not None or session["expires_at"] <= timezone.now():
            raise ApiError("AUTH_INVALID_REFRESH_TOKEN", "Invalid or expired refresh token.", 401)
        session_id = session["id"]
        user_id = session["user_id"]
        # D1.3: rotation PRESERVES the session's existing expires_at (no extension).
        # §3.5 bullets 2-4: rotate + store new hash + revoke the old token in the SAME
        # transaction (the hash replacement is the old token's invalidation).
        new_token = generate_token()
        execute(
            "UPDATE edutrust.auth_sessions SET refresh_token_hash = %s WHERE id = %s",
            [hash_token(new_token), session_id],
        )
    # No event on successful rotation (D1.6). Access token: existing structure,
    # same sid claim, existing TTL (make_access_token unchanged). Roles re-read
    # server-side (never taken from the prior token).
    roles = get_roles(user_id)
    return {
        "access_token": make_access_token(user_id, roles, session_id),
        "refresh_token": new_token,
        "expires_in": settings.JWT_ACCESS_TTL_SECONDS,
    }


def revoke_sessions(user_id: str, scope: str, current_session_id: str | None, request_id: str | None = None) -> dict:
    """POST /api/v1/auth/revoke-sessions (D2). Self-service only: acts exclusively on
    the CALLER's sessions (ownership enforced server-side; the contract carries no
    user/session-id parameters, so cross-user targeting is structurally impossible).
    Only sessions that actually transition to revoked emit events (D2.3)."""
    if scope not in REVOKE_SCOPES:
        raise ApiError(
            "VALIDATION_ERROR",
            'scope must be one of "CURRENT", "OTHERS", "ALL".',
            400,
            {"scopes": list(REVOKE_SCOPES)},
        )
    with tx():
        if scope == "CURRENT":
            candidates = fetchall(
                "SELECT id::text FROM edutrust.auth_sessions "
                "WHERE id = %s AND user_id = %s AND revoked_at IS NULL FOR UPDATE",
                [current_session_id, user_id],
            )
        elif scope == "OTHERS":
            candidates = fetchall(
                "SELECT id::text FROM edutrust.auth_sessions "
                "WHERE user_id = %s AND id <> %s AND revoked_at IS NULL FOR UPDATE",
                [user_id, current_session_id],
            )
        else:  # ALL
            candidates = fetchall(
                "SELECT id::text FROM edutrust.auth_sessions "
                "WHERE user_id = %s AND revoked_at IS NULL FOR UPDATE",
                [user_id],
            )
        revoked = 0
        for cand in candidates:
            sid = cand["id"]
            # Guarded flip (logout convention); idempotent — a session already revoked
            # by a concurrent call is not re-flipped and emits no duplicate event (D2.4).
            flipped = execute(
                "UPDATE edutrust.auth_sessions SET revoked_at = now() "
                "WHERE id = %s AND user_id = %s AND revoked_at IS NULL",
                [sid, user_id],
            )
            if flipped:
                revoked += 1
                write_security_event(
                    "TOKEN_REVOKED", user_id=user_id, severity=1,
                    metadata={"request_id": request_id, "session_id": sid},
                )
                write_event(
                    "SECURITY_EVENT", "auth_session", sid,
                    actor_user_id=user_id, actor_role=None,
                    request_id=request_id, metadata={"event": "TOKEN_REVOKED"},
                )
    # D2.2: self-count only — no session identifiers, no token values, no details.
    return {"revoked": revoked}


# ---- R7 (VS10 candidate 2) Student Management Completion — Executor A (A1–A3) ----
# Authorization: EduTrust_VS10_R7_Implementation_Authorization_v1.0.md
# (locks D1/D1e, D2, D6, D7, D9; Executor A scope: list / patch / archive only).
#
# Conventions reused (not duplicated):
#  - VS1 ownership no-oracle: uniform 403 STUDENT_ACCESS_DENIED for foreign AND unknown ids.
#  - student-row FOR UPDATE locking — leaf object, acyclic (R7 doc §11).
#  - STUDENT_PROFILE_UPDATED (pre-existing enum value) only on actual transitions
#    (R6 guarded-transition convention, D9); no events for the list read (D9).
# No schema change; no new event values; zero financial surface.

STUDENT_UPDATABLE_FIELDS = (
    "display_name",
    "birth_year",
    "academic_level_id",
    "school_year",
    "primary_goal",
    "preferred_mode",
    "consent_status",
)
TEACHING_MODE_VALUES = ("ONLINE", "IN_PERSON", "HYBRID")
CONSENT_STATUS_VALUES = ("PENDING", "GRANTED", "REVOKED")
BIRTH_YEAR_MIN, BIRTH_YEAR_MAX = 1990, 2035  # §7.3 parity; schema CHECK is the backstop

STUDENT_OBJECT_COLUMNS = """id::text, display_name, birth_year::int, academic_level_id::text,
       school_year, primary_goal, preferred_mode::text, consent_status::text,
       status::text, parent_id::text, created_at, updated_at"""


def _student_parent_profile_id(user_id: str) -> str:
    """Acting parent's profile id (VS1 convention: 403 FORBIDDEN if the JWT user has no parent profile)."""
    parent = fetchone("SELECT id::text FROM edutrust.parent_profiles WHERE user_id = %s", [user_id])
    if not parent:
        raise ApiError("FORBIDDEN", "Parent profile is required.", 403)
    return parent["id"]


def _student_object_row(student_id: str) -> dict:
    """Full student object (the PATCH/DELETE response shape per D1 'updated student object')."""
    row = fetchone(
        f"SELECT {STUDENT_OBJECT_COLUMNS} FROM edutrust.student_profiles WHERE id = %s",
        [student_id],
    )
    if row is None:
        raise ApiError("STUDENT_ACCESS_DENIED", "You do not have access to this student profile.", 403)
    return row


def list_students(parent_user_id: str, request_id: str | None = None) -> list[dict]:
    """A1 — GET /students (D6): own students only; item = get_student field set + created_at;
    ordered created_at DESC; no pagination; no event (read)."""
    parent_id = _student_parent_profile_id(parent_user_id)
    return fetchall(
        """
        SELECT id::text, display_name, status::text, parent_id::text, created_at
        FROM edutrust.student_profiles
        WHERE parent_id = %s
        ORDER BY created_at DESC
        """,
        [parent_id],
    )


def _validate_student_patch_fields(data: dict) -> dict:
    """D1/D1e — §7.3 validation parity. Returns {field: value} for provided updatable fields
    only; server-owned fields (id, parent_id, status, timestamps) and unknown fields are
    ignored (D1). Explicit null clears a nullable column; NOT NULL fields must be valid."""
    updates: dict = {}
    for key, value in (data or {}).items():
        if key not in STUDENT_UPDATABLE_FIELDS:
            continue
        if key == "display_name":
            text = str(value or "").strip()
            if not text:
                raise ApiError("VALIDATION_ERROR", "display_name must be a non-empty string.", 400, {"field": "display_name"})
            updates["display_name"] = text
        elif key == "birth_year":
            if value is None:
                updates["birth_year"] = None
            elif isinstance(value, bool) or not isinstance(value, int) or not (BIRTH_YEAR_MIN <= value <= BIRTH_YEAR_MAX):
                raise ApiError("VALIDATION_ERROR", f"birth_year must be an integer between {BIRTH_YEAR_MIN} and {BIRTH_YEAR_MAX}.", 400, {"field": "birth_year"})
            else:
                updates["birth_year"] = value
        elif key == "academic_level_id":
            if value is None:
                updates["academic_level_id"] = None
            else:
                try:
                    level_uuid = str(uuid.UUID(str(value)))
                except (ValueError, AttributeError, TypeError):
                    raise ApiError("VALIDATION_ERROR", "academic_level_id must be a UUID.", 400, {"field": "academic_level_id"})
                level = fetchone("SELECT 1 AS ok FROM edutrust.academic_levels WHERE id = %s AND is_active", [level_uuid])
                if not level:
                    raise ApiError("VALIDATION_ERROR", "academic_level_id must reference an active academic level.", 400, {"field": "academic_level_id"})
                updates["academic_level_id"] = level_uuid
        elif key in ("school_year", "primary_goal"):
            if value is None:
                updates[key] = None
            elif not isinstance(value, str) or not value.strip():
                raise ApiError("VALIDATION_ERROR", f"{key} must be a non-empty string.", 400, {"field": key})
            else:
                updates[key] = value
        elif key == "preferred_mode":
            if value is None:
                updates["preferred_mode"] = None
            else:
                mode = str(value).upper()
                if mode not in TEACHING_MODE_VALUES:
                    raise ApiError("VALIDATION_ERROR", "preferred_mode must be ONLINE, IN_PERSON, or HYBRID.", 400, {"field": "preferred_mode"})
                updates["preferred_mode"] = mode
        elif key == "consent_status":
            if value is None:
                raise ApiError("VALIDATION_ERROR", "consent_status must be PENDING, GRANTED, or REVOKED.", 400, {"field": "consent_status"})
            status = str(value).upper()
            if status not in CONSENT_STATUS_VALUES:
                raise ApiError("VALIDATION_ERROR", "consent_status must be PENDING, GRANTED, or REVOKED.", 400, {"field": "consent_status"})
            updates["consent_status"] = status
    return updates


def update_student(parent_user_id: str, student_id: str, data: dict, request_id: str | None = None) -> dict:
    """A2 — PATCH /students/:id (D1): updatable field set per lock D1; server-owned fields are
    ignored if sent; §7.3 validation parity (D1e); last-writer-wins under the student-row lock
    (D1d); STUDENT_PROFILE_UPDATED per actual update (D9). No updatable field provided →
    no-op 200 returning the current row, no event (D1 'ignored if sent' + R6 guarded-transition
    silence)."""
    parent_id = _student_parent_profile_id(parent_user_id)
    updates = _validate_student_patch_fields(data or {})
    with tx():
        student = fetchone(
            """
            SELECT id::text, display_name, status::text, parent_id::text
            FROM edutrust.student_profiles
            WHERE id = %s AND parent_id = %s
            FOR UPDATE
            """,
            [student_id, parent_id],
        )
        if not student:
            raise ApiError("STUDENT_ACCESS_DENIED", "You do not have access to this student profile.", 403)
        if updates:
            set_parts, params = [], []
            for key, value in updates.items():
                # column → enum-type mapping (preferred_mode column is of type teaching_mode)
                if key == "preferred_mode":
                    set_parts.append("preferred_mode = %s::edutrust.teaching_mode")
                elif key == "consent_status":
                    set_parts.append("consent_status = %s::edutrust.consent_status")
                else:
                    set_parts.append(f"{key} = %s")
                params.append(value)
            set_parts.append("updated_at = now()")
            params.append(student["id"])
            execute(
                f"""
                UPDATE edutrust.student_profiles
                SET {', '.join(set_parts)}
                WHERE id = %s
                """,
                params,
            )
            write_event("STUDENT_PROFILE_UPDATED", "student", student["id"], actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id)
    return _student_object_row(student["id"])


def archive_student(parent_user_id: str, student_id: str, request_id: str | None = None) -> dict:
    """A3 — DELETE /students/:id (D2): soft-archive ACTIVE → ARCHIVED; repeated DELETE is an
    idempotent no-op (200, no second event — R6 guarded-transition convention); the row is
    always retained (no hard delete — bookings RESTRICT FK + minimized-data retention);
    STUDENT_PROFILE_UPDATED on the first transition only (D9)."""
    parent_id = _student_parent_profile_id(parent_user_id)
    with tx():
        student = fetchone(
            """
            SELECT id::text, status::text
            FROM edutrust.student_profiles
            WHERE id = %s AND parent_id = %s
            FOR UPDATE
            """,
            [student_id, parent_id],
        )
        if not student:
            raise ApiError("STUDENT_ACCESS_DENIED", "You do not have access to this student profile.", 403)
        if student["status"] != "ARCHIVED":
            execute(
                "UPDATE edutrust.student_profiles SET status = 'ARCHIVED'::edutrust.student_status, updated_at = now() WHERE id = %s",
                [student_id],
            )
            write_event("STUDENT_PROFILE_UPDATED", "student", student_id, actor_user_id=parent_user_id, actor_role="PARENT", request_id=request_id)
    return _student_object_row(student_id)
