"""Tenant-aware student forms."""

from django import forms
from django.contrib.auth import get_user_model

from core.forms import TenantFormMixin

from .models import Student

User = get_user_model()


class StudentForm(TenantFormMixin, forms.ModelForm):
    """Create/edit a student; ownership and enrollment ID come from the server."""

    full_name = forms.CharField(label="Full name", max_length=200)
    email = forms.EmailField(label="Login email")
    mobile = forms.CharField(label="Mobile number", max_length=20)

    class Meta:
        model = Student
        fields = (
            "full_name",
            "email",
            "mobile",
            "date_of_birth",
            "gender",
            "address",
            "parent_name",
            "parent_mobile",
            "qualification",
            "course",
            "batch",
            "admission_date",
            "profile_picture",
            "status",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "admission_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def _institute(self):
        request = getattr(self, "request", None)
        if request is not None and getattr(request.user, "institute_id", None):
            return request.user.institute
        return getattr(self.instance, "institute", None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ModelChoiceField builds its default queryset when the form class is
        # imported, before any request has set the tenant ContextVar. Rebuild
        # both choices explicitly for the requesting institute so foreign PKs
        # cannot even be selected, let alone saved.
        institute = self._institute()
        if institute is not None:
            from batches.models import Batch
            from courses.models import Course

            self.fields["course"].queryset = Course.objects.for_institute(institute)
            self.fields["batch"].queryset = Batch.objects.for_institute(institute)
        else:
            # Fail closed when neither a request nor an owned instance is
            # available; the default import-time queryset is unscoped.
            self.fields["course"].queryset = self.fields["course"].queryset.none()
            self.fields["batch"].queryset = self.fields["batch"].queryset.none()

        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            if "form-control" not in current:
                field.widget.attrs["class"] = f"{current} form-control".strip()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exclude(
            pk=self.instance.account_id
        ).exists():
            raise forms.ValidationError(
                "This email already belongs to a login account."
            )
        institute = None
        if self.request is not None and getattr(
            self.request.user, "institute_id", None
        ):
            institute = self.request.user.institute
        elif self.instance.institute_id:
            institute = self.instance.institute
        if institute is not None and Student.all_objects.filter(
            institute=institute, email__iexact=email
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Another student in your institute already uses this email."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        institute = self._institute()
        course = cleaned.get("course")
        batch = cleaned.get("batch")

        if institute is not None:
            for field_name in ("course", "batch"):
                item = cleaned.get(field_name)
                if item is not None and item.institute_id != institute.pk:
                    # No foreign names in the error message: a forged PK must
                    # not become a disclosure channel.
                    self.add_error(
                        field_name, "This choice does not belong to your institute."
                    )
                    continue
                # A forged PK is normally rejected by the scoped
                # ModelChoiceField. Resolve it without tenant scoping only to
                # report the same explicit error instead of a generic one.
                raw_id = self.data.get(self.add_prefix(field_name), "")
                if not item and str(raw_id).isdigit():
                    from batches.models import Batch
                    from courses.models import Course

                    model = Course if field_name == "course" else Batch
                    foreign = model.all_objects.filter(pk=int(raw_id)).first()
                    if foreign is not None and foreign.institute_id != institute.pk:
                        self.add_error(
                            field_name,
                            "This choice does not belong to your institute.",
                        )

        if course and batch and batch.course_id != course.pk:
            self.add_error(
                "batch", "This batch does not belong to the selected course."
            )
        return cleaned
