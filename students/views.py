"""Institute-admin-only student management views (fully tenant scoped)."""

import csv
from io import StringIO

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import institute_admin_required
from batches.models import Batch
from courses.models import Course

from .forms import StudentForm
from .models import Student, StudentStatus
from .services import (
    StudentManagementError,
    create_student_from_form,
    delete_student,
    filtered_students,
    set_student_active,
    student_limit_context,
    sync_student_account,
)


def _institute(request):
    """Return the scoped institute or None after queuing an error message."""
    institute = getattr(request.user, "institute", None)
    if institute is None:
        messages.error(request, "Your account is not linked to an institute.")
    return institute


def _student_queryset(request, institute):
    return Student.objects.for_institute(institute).select_related(
        "course", "batch", "account"
    )


def _filters(request):
    return {
        "query": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", ""),
        "course_id": request.GET.get("course", ""),
        "batch_id": request.GET.get("batch", ""),
    }


@institute_admin_required
def student_list(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")

    filters = _filters(request)
    students = filtered_students(institute, **filters)
    return render(
        request,
        "students/student_list.html",
        {
            "students": students,
            "filters": filters,
            "statuses": StudentStatus.choices,
            "courses": Course.objects.for_institute(institute),
            "batches": Batch.objects.for_institute(institute),
            "limit": student_limit_context(institute),
        },
    )


@institute_admin_required
def student_create(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")

    limit = student_limit_context(institute)
    if not limit["can_create"]:
        messages.error(request, limit["message"])

    if request.method == "POST":
        if not limit["can_create"]:
            return redirect("students:student_list")
        form = StudentForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            try:
                student = create_student_from_form(form, request)
            except StudentManagementError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Student {student.get_full_name()} was added with enrollment "
                    f"number {student.student_id}. A login account was created.",
                )
                return redirect("students:student_detail", pk=student.pk)
    else:
        form = StudentForm(request=request)

    return render(
        request,
        "students/student_form.html",
        {
            "form": form,
            "form_title": "Add student",
            "limit": limit,
            "cancel_url": reverse("students:student_list"),
        },
    )


@institute_admin_required
def student_detail(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    student = get_object_or_404(_student_queryset(request, institute), pk=pk)
    return render(
        request,
        "students/student_detail.html",
        {"student": student, "limit": student_limit_context(institute)},
    )


@institute_admin_required
def student_edit(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    student = get_object_or_404(_student_queryset(request, institute), pk=pk)

    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES, instance=student, request=request)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated = form.save()
                    sync_student_account(updated)
            except StudentManagementError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Student details and login were updated.")
                return redirect("students:student_detail", pk=student.pk)
    else:
        form = StudentForm(instance=student, request=request)

    return render(
        request,
        "students/student_form.html",
        {
            "form": form,
            "student": student,
            "form_title": f"Edit {student.get_full_name()}",
            "limit": student_limit_context(institute),
            "cancel_url": reverse("students:student_list"),
        },
    )


@institute_admin_required
@require_POST
def student_deactivate(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    student = get_object_or_404(_student_queryset(request, institute), pk=pk)
    set_student_active(student, False)
    messages.warning(request, f"{student.get_full_name()} was deactivated.")
    return redirect("students:student_detail", pk=pk)


@institute_admin_required
@require_POST
def student_activate(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    student = get_object_or_404(_student_queryset(request, institute), pk=pk)
    set_student_active(student, True)
    messages.success(request, f"{student.get_full_name()} was activated.")
    return redirect("students:student_detail", pk=pk)


@institute_admin_required
@require_POST
def student_delete(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    student = get_object_or_404(_student_queryset(request, institute), pk=pk)
    name = student.get_full_name()
    delete_student(student)
    messages.warning(request, f"{name} and their login account were deleted.")
    return redirect("students:student_list")


@institute_admin_required
def student_export(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")

    students = filtered_students(institute, **_filters(request))
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Student ID",
            "Full name",
            "Email",
            "Mobile",
            "Date of birth",
            "Gender",
            "Address",
            "Parent name",
            "Parent mobile",
            "Qualification",
            "Course",
            "Batch",
            "Admission date",
            "Status",
        ]
    )
    for student in students:
        writer.writerow(
            [
                student.student_id,
                student.get_full_name(),
                student.email,
                student.mobile,
                student.date_of_birth.isoformat() if student.date_of_birth else "",
                student.get_gender_display() if student.gender else "",
                student.address,
                student.parent_name,
                student.parent_mobile,
                student.qualification,
                student.course.name if student.course_id else "",
                student.batch.name if student.batch_id else "",
                student.admission_date.isoformat() if student.admission_date else "",
                student.get_status_display(),
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="students-{institute.institute_id}.csv"'
    )
    return response
