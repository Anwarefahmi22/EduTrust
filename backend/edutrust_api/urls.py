from django.urls import path
from . import views

urlpatterns = [
    path("auth/register", views.register),
    path("auth/login", views.login_view),
    path("auth/logout", views.logout_view),
    # DEV Vertical Slice 10: R6 auth completion
    path("auth/refresh", views.refresh_view),
    path("auth/revoke-sessions", views.revoke_sessions_view),
    # R7 (VS10 candidate 2, Executor A): combined routes — POST/GET(VS1) behavior preserved via
    # the unchanged VS1 service functions; GET list / PATCH / DELETE additive (authorization D1/D2/D6).
    path("students", views.students_collection),
    path("students/<uuid:student_id>", views.students_item),
    # R7 (VS10 candidate 2, Executor B): Student Passport + Student Permissions (authorization
    # D3/D4/D5/D7/D9). Distinct URL block; Executor A routes and behavior untouched.
    path("students/<uuid:student_id>/passport", views.students_passport),
    path("students/<uuid:student_id>/permissions", views.students_permissions),
    path("students/<uuid:student_id>/permissions/<uuid:permission_id>", views.students_permission_item),
    path("teachers/me", views.teachers_me),
    path("teachers/subjects", views.teacher_subjects),
    path("teachers/availability/slots", views.teacher_availability_slots),
    path("teachers/availability/slots/<uuid:slot_id>/block", views.teacher_availability_block),
    path("teachers/availability/slots/<uuid:slot_id>/unblock", views.teacher_availability_unblock),
    path("teachers/search", views.teachers_search),
    path("teachers/match", views.teachers_match),
    path("teachers/<uuid:teacher_id>", views.teacher_profile),
    path("teachers/<uuid:teacher_id>/trust-profile", views.teacher_trust_profile),
    path("teachers/<uuid:teacher_id>/reviews", views.teacher_reviews),
    path("bookings/hold", views.bookings_hold),
    path("bookings/<uuid:booking_id>/confirm", views.bookings_confirm),
    path("bookings", views.bookings_list),
    path("bookings/<uuid:booking_id>", views.bookings_detail),

    path("payments/initiate", views.payments_initiate),
    path("payments/<uuid:payment_id>", views.payments_detail),
    path("payments/<uuid:payment_id>/mock/succeed", views.payments_mock_succeed),
    path("payments/<uuid:payment_id>/mock/fail", views.payments_mock_fail),

    path("sessions", views.sessions_list),
    path("sessions/<uuid:session_id>", views.sessions_detail),
    path("sessions/<uuid:session_id>/start", views.sessions_start),
    path("sessions/<uuid:session_id>/complete", views.sessions_complete),
    path("sessions/<uuid:session_id>/no-show", views.sessions_no_show),
    path("sessions/<uuid:session_id>/report", views.sessions_report),
    path("admin/payments", views.admin_payments),
    path("admin/events", views.admin_events),
    path("admin/security-events", views.admin_security_events),

    # Vertical Slice 4: verified review + basic dispute foundation
    path("sessions/<uuid:session_id>/review", views.sessions_review),
    path("reviews", views.reviews_list),
    path("disputes", views.disputes),
    path("disputes/<uuid:dispute_id>", views.disputes_detail),

    # Vertical Slice 5: payout lifecycle (MANUAL_OPS / MOCK)
    path("teacher/payouts", views.teacher_payouts_list),
    path("teacher/payouts/<uuid:payout_id>", views.teacher_payouts_detail),
    path("admin/payouts/process", views.admin_payouts_process),
    path("admin/payouts", views.admin_payouts),

    # Vertical Slice 6: review moderation
    path("admin/reviews/<uuid:review_id>/moderate", views.admin_reviews_moderate),
    path("admin/reviews", views.admin_reviews),

    # Vertical Slice 7: teacher verification
    path("teachers/verifications", views.teacher_verifications),
    path("admin/teachers/pending-verification", views.admin_teachers_pending_verification),
    path("admin/teachers/<uuid:teacher_id>/verifications", views.admin_teacher_verifications),
    path("admin/teachers/<uuid:teacher_id>/verify", views.admin_teacher_verify),
    path("admin/teachers/<uuid:teacher_id>/reject", views.admin_teacher_reject),

    # Vertical Slice 9: dispute resolution (CORE)
    path("admin/disputes", views.admin_disputes),
    path("admin/disputes/<uuid:dispute_id>/resolve", views.admin_disputes_resolve),

    # Vertical Slice 8: refund operations (DEV mock)
    path("payments/<uuid:payment_id>/refund", views.payments_refund),
    path("admin/refunds", views.admin_refunds),
    path("admin/refunds/<uuid:refund_id>", views.admin_refund_detail),
    path("admin/refunds/<uuid:refund_id>/approve", views.admin_refund_approve),
    path("admin/refunds/<uuid:refund_id>/reject", views.admin_refund_reject),
    path("admin/refunds/<uuid:refund_id>/cancel", views.admin_refund_cancel),
    path("admin/refunds/<uuid:refund_id>/mock/succeed", views.admin_refund_mock_succeed),
    path("admin/refunds/<uuid:refund_id>/mock/fail", views.admin_refund_mock_fail),
    path("admin/refunds/<uuid:refund_id>/reconcile", views.admin_refund_reconcile),
]
