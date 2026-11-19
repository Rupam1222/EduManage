"""Institute-admin teacher management and teacher workspace views."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import institute_admin_required, teacher_required
from batches.models import Batch
from courses.models import Subject
from students.models import Student

from .forms import TeacherForm
from .models import Teacher, TeacherActivity, TeacherActivityAction, TeacherStatus
from .services import (
    TeacherManagementError,
    assigned_batches,
    assigned_subjects,
    create_teacher_from_form,
    delete_teacher,
    filtered_teachers,
    log_teacher_activity,
    set_teacher_active,
    sync_teacher_account,
    teacher_for_user,
    teacher_limit_context,
)


def _institute(request):
    institute = getattr(request.user, "institute", None)
    if institute is None:
        messages.error(request, "Your account is not linked to an institute.")
    return institute


def _teacher_queryset(request, institute):
    return Teacher.objects.for_institute(institute).prefetch_related("subjects", "batches")


def _filters(request):
    return {
        "query": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", ""),
        "subject_id": request.GET.get("subject", ""),
        "batch_id": request.GET.get("batch", ""),
    }


@institute_admin_required
def teacher_list(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    filters = _filters(request)
    return render(
        request,
        "teachers/teacher_list.html",
        {
            "teachers": filtered_teachers(institute, **filters),
            "filters": filters,
            "statuses": TeacherStatus.choices,
            "subjects": Subject.objects.for_institute(institute),
            "batches": Batch.objects.for_institute(institute),
            "limit": teacher_limit_context(institute),
        },
    )


@institute_admin_required
def teacher_create(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")

    limit = teacher_limit_context(institute)
    if not limit["can_create"]:
        messages.error(request, limit["message"])

    if request.method == "POST":
        if not limit["can_create"]:
            return redirect("teachers:teacher_list")
        form = TeacherForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            try:
                teacher = create_teacher_from_form(form, request)
            except TeacherManagementError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Teacher {teacher.get_full_name()} was added with ID "
                    f"{teacher.teacher_id}. A login account was created.",
                )
                return redirect("teachers:teacher_detail", pk=teacher.pk)
    else:
        form = TeacherForm(request=request)

    return render(
        request,
        "teachers/teacher_form.html",
        {
            "form": form,
            "form_title": "Add teacher",
            "limit": limit,
            "cancel_url": reverse("teachers:teacher_list"),
        },
    )


@institute_admin_required
def teacher_detail(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    teacher = get_object_or_404(_teacher_queryset(request, institute), pk=pk)
    return render(
        request,
        "teachers/teacher_detail.html",
        {
            "teacher": teacher,
            "activity": teacher.activity.select_related("actor").order_by("-created_at")[:30],
            "limit": teacher_limit_context(institute),
        },
    )


@institute_admin_required
def teacher_edit(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    teacher = get_object_or_404(_teacher_queryset(request, institute), pk=pk)

    if request.method == "POST":
        form = TeacherForm(request.POST, request.FILES, instance=teacher, request=request)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated = form.save()
                    sync_teacher_account(updated)
                    log_teacher_activity(
                        updated,
                        TeacherActivityAction.UPDATED,
                        actor=request.user,
                        notes="Profile updated by an Institute Admin.",
                    )
            except TeacherManagementError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Teacher details and login were updated.")
                return redirect("teachers:teacher_detail", pk=pk)
    else:
        form = TeacherForm(instance=teacher, request=request)

    return render(
        request,
        "teachers/teacher_form.html",
        {
            "form": form,
            "teacher": teacher,
            "form_title": f"Edit {teacher.get_full_name()}",
            "limit": teacher_limit_context(institute),
            "cancel_url": reverse("teachers:teacher_detail", args=[pk]),
        },
    )


@institute_admin_required
def teacher_activity_list(request):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    rows = TeacherActivity.objects.for_institute(institute).select_related(
        "teacher", "actor"
    )
    teacher_id = request.GET.get("teacher", "").strip()
    if teacher_id.isdigit():
        rows = rows.filter(teacher_id=int(teacher_id))
    return render(
        request,
        "teachers/teacher_activity.html",
        {
            "rows": rows,
            "teachers": Teacher.objects.for_institute(institute),
            "teacher_filter": teacher_id,
        },
    )


@institute_admin_required
@require_POST
def teacher_activate(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    teacher = get_object_or_404(_teacher_queryset(request, institute), pk=pk)
    set_teacher_active(teacher, True, actor=request.user)
    messages.success(request, f"{teacher.get_full_name()} was activated.")
    return redirect("teachers:teacher_detail", pk=pk)


@institute_admin_required
@require_POST
def teacher_deactivate(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    teacher = get_object_or_404(_teacher_queryset(request, institute), pk=pk)
    set_teacher_active(teacher, False, actor=request.user)
    messages.warning(request, f"{teacher.get_full_name()} was deactivated.")
    return redirect("teachers:teacher_detail", pk=pk)


@institute_admin_required
@require_POST
def teacher_delete(request, pk):
    institute = _institute(request)
    if institute is None:
        return redirect("accounts:dashboard")
    teacher = get_object_or_404(_teacher_queryset(request, institute), pk=pk)
    name = teacher.get_full_name()
    delete_teacher(teacher)
    messages.warning(request, f"{name} and their login account were deleted.")
    return redirect("teachers:teacher_list")


def _workspace_teacher(request):
    teacher = teacher_for_user(request.user)
    if teacher is None:
        raise PermissionDenied("No teacher profile is linked to this account.")
    return teacher


@teacher_required
def my_batches(request):
    teacher = _workspace_teacher(request)
    return render(
        request,
        "teachers/my_batches.html",
        {
            "teacher": teacher,
            "batches": assigned_batches(teacher),
            "subjects": assigned_subjects(teacher),
        },
    )


@teacher_required
def my_students(request):
    teacher = _workspace_teacher(request)
    students = Student.objects.for_institute(teacher.institute).filter(
        batch__in=assigned_batches(teacher)
    )
    return render(
        request,
        "teachers/my_students.html",
        {"teacher": teacher, "students": students},
    )
