"""Tests for the institute and platform audit trails."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from institutes.models import Institute, RegistrationStatus
from licenses.services import sync_license
from subscriptions.models import Subscription, SubscriptionPlan

from .models import (
    ActivityAction,
    ActivityLog,
    log_activity,
    log_fee_payment,
    redact_sensitive,
)

User = get_user_model()
PASSWORD = "ActivityLogTest!123"


def make_institute(name, email):
    return Institute.objects.create(
        institute_name=name,
        owner_name=f"{name} Owner",
        email=email,
        mobile="9876543210",
        address="1 Audit Road",
        city="Pune",
        state="Maharashtra",
        pincode="411001",
        status=RegistrationStatus.ACTIVE,
        is_active=True,
    )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ActivityLogTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.institute = make_institute("Alpha Institute", "alpha-log@example.test")
        self.other_institute = make_institute("Beta Institute", "beta-log@example.test")
        self.super_admin = User.objects.create_superuser(
            "owner-log@example.test", PASSWORD
        )
        self.admin = User.objects.create_user(
            "admin-log@example.test",
            PASSWORD,
            role=Role.INSTITUTE_ADMIN,
            institute=self.institute,
        )
        self.teacher_user = User.objects.create_user(
            "teacher-log@example.test",
            PASSWORD,
            role=Role.TEACHER,
            institute=self.institute,
        )
        self.student_user = User.objects.create_user(
            "student-log@example.test",
            PASSWORD,
            role=Role.STUDENT,
            institute=self.institute,
        )

        plan = SubscriptionPlan.objects.create(
            slug="audit-plan",
            plan_name="Audit Test Plan",
            price=Decimal("999.00"),
            duration_in_days=30,
            duration_in_months=1,
            max_students=20,
            max_teachers=20,
            max_batches=20,
        )
        for institute in (self.institute, self.other_institute):
            subscription = Subscription.all_objects.create(
                institute=institute,
                plan=plan,
                status=RegistrationStatus.ACTIVE,
                activated_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=29),
            )
            sync_license(subscription, self.super_admin)

    def login(self, user):
        self.assertTrue(self.client.login(email=user.email, password=PASSWORD))

    def test_sensitive_values_are_redacted(self):
        description = redact_sensitive(
            "password=hunter2 token=abc123 secret=top api_key=key999 "
            "card_number=4111111111111111 cvv=123"
        )
        for secret in ("hunter2", "abc123", "top", "key999", "4111111111111111", "123"):
            self.assertNotIn(secret, description)
        self.assertEqual(description.count("[REDACTED]"), 6)

    def test_log_activity_sanitizes_descriptions(self):
        entry = log_fee_payment(
            None,
            "Recorded fee with password=letmein",
            institute=self.institute,
            user=self.admin,
        )
        self.assertEqual(entry.action, ActivityAction.FEE_PAYMENT)
        self.assertNotIn("letmein", entry.description)
        self.assertIn("[REDACTED]", entry.description)
        self.assertEqual(entry.user, self.admin)
        self.assertEqual(entry.institute, self.institute)

    def test_login_and_logout_are_logged(self):
        self.login(self.admin)
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityAction.USER_LOGIN, user=self.admin
            ).exists()
        )
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityAction.USER_LOGOUT, user=self.admin
            ).exists()
        )

    def test_ip_address_is_recorded_from_request(self):
        self.client.login(email=self.admin.email, password=PASSWORD)
        entry = ActivityLog.objects.filter(user=self.admin).first()
        self.assertIsNotNone(entry)
        self.assertIn(entry.ip_address, ("127.0.0.1", None))

    def test_student_creation_is_logged(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_create"),
            {
                "full_name": "Aarav Sharma",
                "email": "created-audit@example.test",
                "mobile": "9876543211",
                "date_of_birth": "2010-05-14",
                "gender": "male",
                "address": "12 Main Street",
                "parent_name": "Raj Sharma",
                "parent_mobile": "9876543212",
                "qualification": "Class IX",
                "admission_date": "2026-06-01",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityAction.STUDENT_CREATED).exists()
        )

    def test_teacher_creation_is_logged(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_create"),
            {
                "full_name": "Ananya Rao",
                "email": "created-teacher-audit@example.test",
                "mobile": "9876543211",
                "qualification": "M.Sc. Mathematics",
                "experience": "5",
                "specialization": "Algebra",
                "joining_date": "2026-01-01",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityAction.TEACHER_CREATED).exists()
        )

    def test_institute_admin_sees_only_own_institute_logs(self):
        log_activity(None, "Alpha action", "Internal", institute=self.institute)
        log_activity(None, "Beta action", "Internal", institute=self.other_institute)
        self.login(self.admin)
        response = self.client.get(reverse("activity_logs:institute_activity_logs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha action")
        self.assertNotContains(response, "Beta action")

    def test_teachers_and_students_cannot_access_admin_logs(self):
        for user in (self.teacher_user, self.student_user):
            self.client.logout()
            self.login(user)
            response = self.client.get(reverse("activity_logs:institute_activity_logs"))
            self.assertEqual(response.status_code, 403)

    def test_super_admin_sees_platform_wide_logs(self):
        log_activity(None, "Alpha action", "Internal", institute=self.institute)
        log_activity(None, "Beta action", "Internal", institute=self.other_institute)
        self.login(self.super_admin)
        response = self.client.get(reverse("superadmin:activity_logs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha action")
        self.assertContains(response, "Beta action")

    def test_activity_log_page_supports_search_and_action_filter(self):
        log_activity(None, "Notes uploaded", "Shared chapter 1", institute=self.institute)
        log_activity(None, "Notes deleted", "Removed chapter 2", institute=self.institute)
        self.login(self.admin)
        response = self.client.get(
            reverse("activity_logs:institute_activity_logs"),
            {"q": "chapter 1"},
        )
        self.assertContains(response, "Shared chapter 1")
        self.assertNotContains(response, "Removed chapter 2")
        response = self.client.get(
            reverse("activity_logs:institute_activity_logs"),
            {"action": "Notes deleted"},
        )
        self.assertContains(response, "Removed chapter 2")
        self.assertNotContains(response, "Shared chapter 1")
