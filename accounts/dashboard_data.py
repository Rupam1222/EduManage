"""Real database metrics for the Institute Admin dashboard.

Every query is explicitly scoped to the requesting user's institute so the
dashboard cannot leak another tenant's numbers, even for Super Admin sessions.
"""

from collections import defaultdict

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from assignments.models import Assignment
from attendance.models import AttendanceRecord, AttendanceStatus
from batches.models import Batch
from courses.models import Course
from examinations.models import Examination, Mark
from payments.models import Invoice, Payment, PaymentStatus
from students.models import Student, StudentStatus
from study_material.models import StudyMaterial
from subscriptions.models import Subscription
from teachers.models import Teacher


def _pct(part, total):
    return round(part * 100 / total, 1) if total else 0


def dashboard_stats(institute):
    """Headline counters rendered as stat cards."""
    students = Student.objects.for_institute(institute)
    student_total = students.count()
    attendance = AttendanceRecord.objects.for_institute(institute)
    attendance_total = attendance.count()
    present = attendance.filter(status=AttendanceStatus.PRESENT).count()

    return {
        "Students": student_total,
        "Active students": students.filter(status=StudentStatus.ACTIVE).count(),
        "Teachers": Teacher.objects.for_institute(institute).count(),
        "Courses": Course.objects.for_institute(institute).count(),
        "Batches": Batch.objects.for_institute(institute).count(),
        "Assignments": Assignment.objects.for_institute(institute).count(),
        "Examinations": Examination.objects.for_institute(institute).count(),
        "Study materials": StudyMaterial.objects.for_institute(institute).count(),
        "Attendance": f"{_pct(present, attendance_total)}%",
    }


def subscription_widget(institute):
    """Current subscription plus the renewal, upgrade and document actions."""
    subscription = (
        Subscription.objects.for_institute(institute)
        .select_related("plan")
        .order_by("-requested_at")
        .first()
    )
    invoice = (
        Invoice.objects.for_institute(institute).order_by("-invoice_date").first()
    )
    receipt_payment = (
        Payment.objects.for_institute(institute)
        .filter(payment_status=PaymentStatus.PAID)
        .order_by("-created_at")
        .first()
    )

    now = timezone.now()
    expires_at = subscription.expires_at if subscription else None
    days_remaining = (expires_at - now).days if expires_at else None
    expired = bool(subscription and subscription.is_expired)
    expiring_soon = bool(
        not expired and days_remaining is not None and days_remaining <= 7
    )

    if expired:
        warning = "Your subscription has expired. Renew it to restore full access."
    elif expiring_soon:
        warning = (
            f"Your subscription expires in {max(days_remaining, 0)} day(s). "
            "Renew now to avoid interruption."
        )
    else:
        warning = ""

    plan = subscription.plan if subscription else None
    seats = {}
    if plan:
        seats = {
            "Students": {
                "used": Student.objects.for_institute(institute).count(),
                "limit": plan.max_students,
            },
            "Teachers": {
                "used": Teacher.objects.for_institute(institute).count(),
                "limit": plan.max_teachers,
            },
            "Batches": {
                "used": Batch.objects.for_institute(institute).count(),
                "limit": plan.max_batches,
            },
        }

    return {
        "subscription": subscription,
        "plan": plan,
        "status": subscription.get_status_display() if subscription else "No plan",
        "expires_at": expires_at,
        "days_remaining": days_remaining,
        "is_expired": expired,
        "expiring_soon": expiring_soon,
        "warning": warning,
        "seats": seats,
        "renew_url": reverse("subscriptions:renew"),
        "upgrade_url": reverse("subscriptions:renew"),
        "invoice_url": (
            reverse("payments:invoice_pdf", args=[invoice.pk])
            if invoice
            else reverse("payments:invoice_list")
        ),
        "receipt_url": (
            reverse("payments:payment_receipt", args=[receipt_payment.pk])
            if receipt_payment
            else reverse("payments:payment_history")
        ),
    }


def dashboard_charts(institute):
    """Chart series built only from the tenant's own records."""
    students_by_course = (
        Course.objects.for_institute(institute)
        .annotate(student_count=Count("students"))
        .order_by("course_name")
    )
    course_labels = [course.course_name for course in students_by_course]
    course_values = [course.student_count for course in students_by_course]

    monthly = defaultdict(lambda: [0, 0])  # month key -> [records, present]
    for day, status in AttendanceRecord.objects.for_institute(institute).values_list(
        "date", "status"
    ):
        key = day.strftime("%Y-%m")
        monthly[key][0] += 1
        if status == AttendanceStatus.PRESENT:
            monthly[key][1] += 1
    attendance_labels = []
    attendance_values = []
    for key in sorted(monthly)[-6:]:
        year, month = key.split("-")
        attendance_labels.append(f"{year}-{month}")
        attendance_values.append(_pct(monthly[key][1], monthly[key][0]))

    marks = list(
        Mark.objects.for_institute(institute).select_related("examination")
    )
    passed = sum(1 for mark in marks if mark.is_pass)

    return {
        "course_labels": course_labels,
        "course_values": course_values,
        "attendance_labels": attendance_labels,
        "attendance_values": attendance_values,
        "exam_labels": ["Pass", "Fail"],
        "exam_values": [passed, len(marks) - passed],
    }


def institute_dashboard_context(institute):
    """Assemble the full context consumed by the dashboard template."""
    context = {
        "institute": institute,
        "stats": dashboard_stats(institute),
        "subscription": subscription_widget(institute),
    }
    context.update(dashboard_charts(institute))
    context["links"] = [
        {
            "label": "Create user",
            "url": reverse("accounts:role_user_create"),
            "description": "Add a teacher or student to your institute.",
        },
        {
            "label": "Invite by email",
            "url": reverse("accounts:invitation_create"),
            "description": "Send an approval-based registration invitation.",
        },
        {
            "label": "Manage users",
            "url": reverse("accounts:user_list"),
            "description": "Review and deactivate institute accounts.",
        },
        {
            "label": "Students",
            "url": reverse("students:student_list"),
            "description": "Admissions, batches and profiles.",
        },
        {
            "label": "Teachers",
            "url": reverse("teachers:teacher_list"),
            "description": "Staff directory and assigned subjects.",
        },
        {
            "label": "Batches",
            "url": reverse("batches:batch_list"),
            "description": "Course batches, seats and timetable.",
        },
        {
            "label": "Attendance report",
            "url": reverse("attendance:admin_attendance_report"),
            "description": "Daily, monthly and exported attendance views.",
        },
        {
            "label": "Examination results",
            "url": reverse("examinations:admin_results"),
            "description": "Marks, report cards and result exports.",
        },
    ]
    return context
