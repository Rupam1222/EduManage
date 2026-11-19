"""Shared form helpers and public website forms."""

from django import forms


class TenantFormMixin:
    """Bind a model form to the signed-in user's institute.

    The owning institute is always taken from ``request.user``; an ``institute``
    value submitted by a client is never trusted.
    """

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        self._apply_request_institute()
        return cleaned_data

    def _apply_request_institute(self):
        request = getattr(self, "request", None)
        institute = getattr(getattr(request, "user", None), "institute", None)
        if request is not None and institute is not None:
            self.instance.institute = institute

    def save(self, commit=True):
        self._apply_request_institute()
        return super().save(commit=commit)


class ContactForm(forms.Form):
    """A simple contact request that is delivered by email."""

    name = forms.CharField(max_length=120, label="Your name")
    email = forms.EmailField(label="Email address")
    subject = forms.CharField(max_length=150, required=False, label="Subject")
    message = forms.CharField(
        max_length=4000,
        label="Message",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "How can we help?"}),
    )
