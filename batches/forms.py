"""Tenant-aware batch and enrollment forms."""

from django import forms

from core.forms import TenantFormMixin
from courses.models import CourseStatus
from students.models import Student
from teachers.models import Teacher, TeacherStatus

from .models import Batch
from .services import batch_code_exists, sync_batch_assignments


def _institute_for(form):
    request = getattr(form, "request", None)
    if request is not None and getattr(request.user, "institute_id", None):
        return request.user.institute
    return getattr(form.instance, "institute", None)


def _style(form):
    for field in form.fields.values():
        current = field.widget.attrs.get("class", "")
        if "form-control" not in current and "form-select" not in current:
            field.widget.attrs["class"] = f"{current} form-control".strip()


class BatchForm(TenantFormMixin, forms.ModelForm):
    """Create/edit a batch and assign its teachers, subjects and capacity."""

    teachers = forms.ModelMultipleChoiceField(
        label="Assigned teachers",
        queryset=Teacher.objects.none(),
        required=False,
        help_text="Optional. These teachers will see the batch and its subjects in their workspace.",
    )

    class Meta:
        model = Batch
        fields = (
            "batch_name",
            "code",
            "course",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "assigned_teacher",
            "maximum_students",
            "status",
            "subjects",
            "teachers",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        institute = _institute_for(self)
        self.fields["code"].required = False
        self.fields["code"].help_text = "Optional; generated automatically when blank."

        if institute is not None:
            self.fields["course"].queryset = (
                self.fields["course"]
                .queryset.for_institute(institute)
                .filter(status=CourseStatus.ACTIVE)
            )
            self.fields["assigned_teacher"].queryset = Teacher.objects.for_institute(
                institute
            ).filter(status=TeacherStatus.ACTIVE)
            self.fields["teachers"].queryset = Teacher.objects.for_institute(
                institute
            ).filter(status=TeacherStatus.ACTIVE)
            self.fields["subjects"].queryset = self.fields[
                "subjects"
            ].queryset.for_institute(institute)

        if self.instance.pk:
            self.fields["teachers"].initial = Teacher.all_objects.filter(
                batches=self.instance
            )

        _style(self)

    def clean_batch_name(self):
        name = (self.cleaned_data.get("batch_name") or "").strip()
        if not name:
            raise forms.ValidationError("Batch name is required.")
        return name

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if code and batch_code_exists(
            _institute_for(self), code, exclude_pk=self.instance.pk
        ):
            raise forms.ValidationError("This batch code is already in use.")
        return code

    def clean_maximum_students(self):
        value = self.cleaned_data.get("maximum_students")
        if value is None or value <= 0:
            raise forms.ValidationError("Maximum students must be at least 1.")
        if self.instance.pk and value < self.instance.student_count:
            raise forms.ValidationError(
                "Capacity cannot be lower than the number of enrolled students."
            )
        return value

    def clean(self):
        cleaned = super().clean()
        institute = _institute_for(self)
        course = cleaned.get("course")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")

        if institute is not None:
            teacher = cleaned.get("assigned_teacher")
            if teacher is not None and teacher.institute_id != institute.pk:
                self.add_error(
                    "assigned_teacher", "This teacher does not belong to your institute."
                )
            for field_name in ("teachers", "subjects"):
                for related in cleaned.get(field_name) or []:
                    if related.institute_id != institute.pk:
                        self.add_error(
                            field_name,
                            f"{related} does not belong to your institute.",
                        )
        if course is not None and institute is not None:
            if course.institute_id != institute.pk:
                self.add_error("course", "This course does not belong to your institute.")
            for subject in cleaned.get("subjects") or []:
                if subject.course_id != course.pk:
                    self.add_error(
                        "subjects",
                        f"'{subject.display_name}' does not belong to the selected course.",
                    )

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date cannot be before the start date.")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be after the start time.")

        return cleaned

    def save(self, commit=True):
        batch = super().save(commit=commit)
        if commit:
            actor = None
            request = getattr(self, "request", None)
            if request is not None and request.user.is_authenticated:
                actor = request.user
            sync_batch_assignments(
                batch,
                self.cleaned_data.get("teachers") or [],
                self.cleaned_data.get("subjects") or [],
                actor=actor,
            )
        return batch


class StudentEnrollmentForm(forms.Form):
    """Enroll several students into one batch, with seat validation."""

    students = forms.ModelMultipleChoiceField(
        label="Students to enroll",
        queryset=Student.objects.none(),
        required=True,
        help_text="Hold Ctrl/Cmd to select more than one student.",
    )

    def __init__(self, batch, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch = batch
        already = set(batch.student_queryset().values_list("pk", flat=True))
        queryset = Student.objects.for_institute(batch.institute).exclude(pk__in=already)
        self.fields["students"].queryset = queryset
        available = batch.available_seats
        if available is not None:
            self.fields["students"].help_text += f" Available seats: {available}."
        _style(self)

    def clean_students(self):
        students = self.cleaned_data.get("students") or []
        available = self.batch.available_seats
        if available is not None and len(students) > available:
            raise forms.ValidationError(
                f"Only {available} seat(s) are available in this batch."
            )
        return students
