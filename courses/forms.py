"""Tenant-aware course and subject forms."""

from django import forms

from core.forms import TenantFormMixin

from .models import Course, CourseStatus, Subject
from .services import course_code_exists, subject_code_exists


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


class CourseForm(TenantFormMixin, forms.ModelForm):
    """Create/edit a course; the owning institute comes from the request."""

    class Meta:
        model = Course
        fields = (
            "course_name",
            "code",
            "description",
            "duration",
            "course_fee",
            "status",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "duration": forms.TextInput(attrs={"placeholder": "e.g. 6 months"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["code"].help_text = "Optional; generated automatically when blank."
        self.fields["course_fee"].required = False
        _style(self)

    def clean_course_name(self):
        name = (self.cleaned_data.get("course_name") or "").strip()
        if not name:
            raise forms.ValidationError("Course name is required.")
        return name

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if code and course_code_exists(
            _institute_for(self), code, exclude_pk=self.instance.pk
        ):
            raise forms.ValidationError("This course code is already in use.")
        return code

    def clean_course_fee(self):
        fee = self.cleaned_data.get("course_fee")
        return fee if fee is not None else 0


class SubjectForm(TenantFormMixin, forms.ModelForm):
    """Create/edit a subject inside one of the institute's courses."""

    subject_code = forms.CharField(
        label="Subject code",
        max_length=40,
        required=True,
        help_text="Must be unique within your institute.",
    )

    class Meta:
        model = Subject
        fields = ("subject_name", "subject_code", "course", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        institute = _institute_for(self)
        if institute is not None:
            self.fields["course"].queryset = (
                self.fields["course"]
                .queryset.for_institute(institute)
                .filter(status=CourseStatus.ACTIVE)
            )
        _style(self)

    def clean_subject_name(self):
        name = (self.cleaned_data.get("subject_name") or "").strip()
        if not name:
            raise forms.ValidationError("Subject name is required.")
        return name

    def clean_subject_code(self):
        code = (self.cleaned_data.get("subject_code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Subject code is required.")
        if subject_code_exists(
            _institute_for(self), code, exclude_pk=self.instance.pk
        ):
            raise forms.ValidationError("This subject code is already in use.")
        return code

    def clean(self):
        cleaned = super().clean()
        institute = _institute_for(self)
        course = cleaned.get("course")
        if institute is not None and course is not None:
            if course.institute_id != institute.pk:
                self.add_error("course", "This course does not belong to your institute.")
        return cleaned
