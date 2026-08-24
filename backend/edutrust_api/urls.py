from django.urls import path
from . import views

urlpatterns = [
    path("auth/register", views.register),
    path("auth/login", views.login_view),
    path("auth/logout", views.logout_view),
    path("students", views.students_create),
    path("students/<uuid:student_id>", views.students_detail),
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
]
