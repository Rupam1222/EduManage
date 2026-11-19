"""Teacher-scoped attendance forms."""

from django import forms
from django.utils import timezone

from batches.models import Batch
from teachers.services import assigned_batches

from .models import AttendanceRecord


class AttendanceSelectionForm(forms.Form):
    batch = forms.ModelChoiceField(queryset=Batch.objects.none(), label="Assigned batch")
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, teacher=None, **kwargs):
        self.teacher = teacher
        super().__init__(*args, **kwargs)
        if teacher is not None:
            self.fields["batch"].queryset = assigned_batches(teacher)
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            if "form-control" not in current:
                field.widget.attrs["class"] = f"{current} form-control".strip()


class AttendanceEditForm(forms.ModelForm):
    """Edit the status and remarks of an existing attendance row."""

    class Meta:
        model = AttendanceRecord
        fields = ("status", "remarks")
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            current = field.widget.attrs.get("class", "")
            css = "form-select" if name == "status" else "form-control"
            field.widget.attrs["class"] = f"{current} {css}".strip()
