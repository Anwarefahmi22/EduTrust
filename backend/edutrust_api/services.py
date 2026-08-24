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
