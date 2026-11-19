"""Tenant-aware teacher forms."""

from django import forms
from django.contrib.auth import get_user_model

from core.forms import TenantFormMixin

from .models import Teacher

User = get_user_model()


class TeacherForm(TenantFormMixin, forms.ModelForm):
    full_name = forms.CharField(label="Full name", max_length=200)
    email = forms.EmailField(label="Login email")
    mobile = forms.CharField(label="Mobile number", max_length=20)

    class Meta:
        model = Teacher
        fields = (
            "full_name",
            "email",
            "mobile",
            "qualification",
            "experience",
            "specialization",
            "joining_date",
            "profile_picture",
            "status",
            "subjects",
            "batches",
        )
        widgets = {
            "joining_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        institute = None
        if self.request is not None and getattr(
            self.request.user, "institute_id", None
        ):
            institute = self.request.user.institute
        elif self.instance.institute_id:
            institute = self.instance.institute

        if institute is not None:
            from batches.models import Batch
            from courses.models import Subject

            self.fields["subjects"].queryset = Subject.objects.for_institute(institute)
            self.fields["batches"].queryset = Batch.objects.for_institute(institute)

        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            if "form-control" not in current:
                field.widget.attrs["class"] = f"{current} form-control".strip()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exclude(
            pk=self.instance.account_id
        ).exists():
            raise forms.ValidationError("This email already belongs to a login account.")
        institute = None
        if self.request is not None and getattr(
            self.request.user, "institute_id", None
        ):
            institute = self.request.user.institute
        elif self.instance.institute_id:
            institute = self.instance.institute
        if institute is not None and Teacher.all_objects.filter(
            institute=institute, email__iexact=email
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Another teacher in your institute already uses this email."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        institute = None
        if self.request is not None and getattr(
            self.request.user, "institute_id", None
        ):
            institute = self.request.user.institute
        elif self.instance.institute_id:
            institute = self.instance.institute
        if institute is not None:
            for field_name in ("subjects", "batches"):
                for item in cleaned.get(field_name) or []:
                    if item.institute_id != institute.pk:
                        self.add_error(
                            field_name,
                            f"{item} does not belong to your institute.",
                        )
        return cleaned
