"""Forms for authentication, profile and account management."""

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from institutes.models import Institute

from .models import Invitation, Role

User = get_user_model()

# Brute-force protection: after this many failed attempts the email/IP pair is
# locked for LOGIN_LOCKOUT_SECONDS. Cache-backed so it works with the default
# locmem cache in development and a shared cache (Redis) in production.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _login_cache_key(email, request):
    ip = ""
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else request.META.get("REMOTE_ADDR", "")
        )
    return f"login_fail:{str(email).lower().strip()}:{ip}"


class BootstrapFormMixin:
    """Apply Bootstrap form-control classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            attrs = field.widget.attrs
            css = attrs.get("class", "")
            if "form-control" not in css:
                attrs["class"] = f"{css} form-control".strip()


class LoginForm(BootstrapFormMixin, forms.Form):
    """Email + password login form."""

    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={"placeholder": "you@example.com", "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            key = _login_cache_key(email, self.request)
            failures = cache.get(key, 0)
            if failures >= LOGIN_MAX_ATTEMPTS:
                raise ValidationError(
                    "Too many failed login attempts. Please try again in 15 minutes."
                )
            self.user_cache = authenticate(
                self.request, email=email, password=password
            )
            if self.user_cache is None:
                cache.set(key, failures + 1, LOGIN_LOCKOUT_SECONDS)
                raise ValidationError("Invalid email or password.")
            if not self.user_cache.is_active:
                raise ValidationError("This account has been deactivated.")
            cache.delete(key)
        return cleaned_data

    def get_user(self):
        return self.user_cache


def _validate_new_password(password1, password2, user=None):
    """Shared password confirmation + Django policy validation."""
    if password1 and password2 and password1 != password2:
        raise ValidationError("The two password fields did not match.")
    if password2:
        validate_password(password2, user=user)
    return password2


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Allow a user to edit their own contact details and profile image."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "profile_image")

    def clean_email(self):
        """Normalize to lowercase so case-variant duplicates cannot exist."""
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return email
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("An account with this email address already exists.")
        return email


class InstituteForm(BootstrapFormMixin, forms.ModelForm):
    """Create a tenant institute (Super Admin only)."""

    class Meta:
        model = Institute
        fields = (
            "institute_name",
            "owner_name",
            "email",
            "mobile",
            "address",
            "city",
            "state",
            "pincode",
            "website",
            "logo",
        )


class InstituteAdminCreateForm(BootstrapFormMixin, forms.ModelForm):
    """Create an Institute Admin tied to an existing institute."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "institute")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institute"].queryset = Institute.objects.filter(is_active=True)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        prospective_user = User(
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
        )
        return _validate_new_password(password1, password2, user=prospective_user)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Role.INSTITUTE_ADMIN
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class RoleUserCreateForm(BootstrapFormMixin, forms.ModelForm):
    """Create a Teacher or Student inside the current user's institute."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            (Role.TEACHER.value, Role.TEACHER.label),
            (Role.STUDENT.value, Role.STUDENT.label),
        ]

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role not in (Role.TEACHER, Role.STUDENT):
            raise ValidationError("Only teachers and students can be created here.")
        return role

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        prospective_user = User(
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
        )
        return _validate_new_password(password1, password2, user=prospective_user)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class InvitationForm(BootstrapFormMixin, forms.ModelForm):
    """Invite a teacher/student to self-register for one institute."""

    class Meta:
        model = Invitation
        fields = ("email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            (Role.TEACHER.value, Role.TEACHER.label),
            (Role.STUDENT.value, Role.STUDENT.label),
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        pending = Invitation.objects.filter(
            email__iexact=email,
            is_active=True,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        if pending.exists():
            raise ValidationError("A valid invitation is already pending for this email.")
        return email


class InvitationRegisterForm(BootstrapFormMixin, forms.Form):
    """Complete an approved invitation by choosing a password."""

    first_name = forms.CharField(label="First name", max_length=150)
    last_name = forms.CharField(label="Last name", max_length=150)
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_password2(self):
        # Build a transient user so the similarity validator rejects passwords
        # derived from the invited person's own name.
        first = self.cleaned_data.get("first_name", "")
        last = self.cleaned_data.get("last_name", "")
        email = getattr(self, "invitation_email", "") or ""
        prospective = User(
            email=email, first_name=first, last_name=last
        )
        return _validate_new_password(
            self.cleaned_data.get("password1"),
            self.cleaned_data.get("password2"),
            user=prospective,
        )
