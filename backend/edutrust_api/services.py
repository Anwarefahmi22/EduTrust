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
