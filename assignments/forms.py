"""Teacher-scoped assignment forms and student submission forms."""

from django import forms
from django.utils import timezone

from teachers.services import assigned_batches, assigned_subjects

from .models import Assignment, AssignmentSubmission
from .services import validate_document


class AssignmentForm(forms.ModelForm):
    # Optional so older teacher integrations that only send ``due_date`` keep
    # working; the view falls back to today's date.
    issue_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Assignment
        fields = ("title", "description", "issue_date", "file", "batch", "subject", "due_date")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        self.teacher = teacher
        super().__init__(*args, **kwargs)
        if not self.fields["issue_date"].initial:
            self.fields["issue_date"].initial = timezone.localdate()
        self.fields["file"].required = False
        if teacher is not None:
            self.fields["batch"].queryset = assigned_batches(teacher)
            self.fields["subject"].queryset = assigned_subjects(teacher)
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            if "form-control" not in current:
                field.widget.attrs["class"] = f"{current} form-control".strip()

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        return validate_document(upload, required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("issue_date"):
            cleaned["issue_date"] = timezone.localdate()
        batch = cleaned.get("batch")
        subject = cleaned.get("subject")
        if batch and subject and subject.course_id != batch.course_id:
            self.add_error(
                "subject", "The subject must belong to the selected batch's course."
            )
        return cleaned


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("file",)
        widgets = {"file": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.txt"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].required = True
        self.fields["file"].widget.attrs["class"] = "form-control"

    def clean_file(self):
        return validate_document(self.cleaned_data.get("file"), required=True)


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("marks", "feedback")
        widgets = {"feedback": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marks"].required = True
        self.fields["marks"].min_value = 0
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            css = "form-control"
            field.widget.attrs["class"] = f"{current} {css}".strip()

    def clean_marks(self):
        marks = self.cleaned_data.get("marks")
        if marks is None or marks < 0:
            raise forms.ValidationError("Marks must be zero or greater.")
        return marks
