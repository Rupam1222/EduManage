"""Tests for authentication, authorization and account management."""

import io
import re
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import FieldDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from attendance.models import AttendanceRecord, AttendanceStatus
from batches.models import Batch
from courses.models import Course
from examinations.models import Examination, Mark
from institutes.models import Institute, RegistrationStatus
from licenses.services import sync_license
from payments.models import Invoice, Payment, PaymentStatus
from students.models import Student, StudentStatus
from subscriptions.models import Subscription, SubscriptionPlan
from teachers.models import Teacher

from .models import Invitation, Role

User = get_user_model()
PASSWORD = "Str0ng!Pass123"
NEW_PASSWORD = "N3w!StrongPass456"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthTestBase(TestCase):
    """Shared fixture with one user per supported role."""

    def setUp(self):
        self.institute = Institute.objects.create(
            institute_name="Sunrise Coaching",
            owner_name="Sunil Owner",
            email="office@sunrise.test",
            mobile="9876543210",
            address="1 Main Road",
            city="Pune",
            state="Maharashtra",
            pincode="411001",
            status=RegistrationStatus.ACTIVE,
            is_active=True,
        )
        self.other_institute = Institute.objects.create(
            institute_name="Other Coaching",
            owner_name="Other Owner",
            email="office@other.test",
            mobile="9876543211",
            address="2 Main Road",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            status=RegistrationStatus.ACTIVE,
            is_active=True,
        )
        self.super_admin = User.objects.create_superuser(
            "super@example.com", PASSWORD
        )
        self.institute_admin = User.objects.create_user(
            "admin@example.com",
            PASSWORD,
            role=Role.INSTITUTE_ADMIN,
            institute=self.institute,
            first_name="Aditi",
            last_name="Admin",
        )
        self.teacher = User.objects.create_user(
            "teacher@example.com",
            PASSWORD,
            role=Role.TEACHER,
            institute=self.institute,
            first_name="Tara",
            last_name="Teacher",
        )
        self.student = User.objects.create_user(
            "student@example.com",
            PASSWORD,
            role=Role.STUDENT,
            institute=self.institute,
        )
        self.other_teacher = User.objects.create_user(
            "other@example.com",
            PASSWORD,
            role=Role.TEACHER,
            institute=self.other_institute,
        )

    def login_as(self, user):
        logged_in = self.client.login(email=user.email, password=PASSWORD)
        self.assertTrue(logged_in, f"Could not authenticate {user.email}")


class CustomUserModelTests(AuthTestBase):
    def test_email_is_the_login_identifier(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertTrue(User._meta.get_field("email").unique)
        with self.assertRaises(FieldDoesNotExist):
            User._meta.get_field("username")
        self.assertEqual(str(self.teacher), "teacher@example.com")

    def test_password_is_hashed(self):
        self.assertNotEqual(self.teacher.password, PASSWORD)
        self.assertTrue(self.teacher.check_password(PASSWORD))

    def test_superuser_has_super_admin_role(self):
        self.assertEqual(self.super_admin.role, Role.SUPER_ADMIN)
        self.assertTrue(self.super_admin.is_staff)
        self.assertTrue(self.super_admin.is_superuser)


class LoginLogoutTests(AuthTestBase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email address")

    def test_email_login_redirects_to_role_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "teacher@example.com", "password": PASSWORD},
        )
        self.assertRedirects(
            response, reverse("accounts:teacher_dashboard"), fetch_redirect_response=False
        )

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "teacher@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")

    def test_logout_requires_post_and_clears_session(self):
        self.login_as(self.teacher)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(
            response,
            reverse("accounts:logged_out"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        confirmation = self.client.get(reverse("accounts:logged_out"))
        self.assertContains(confirmation, "You have been signed out")


class DashboardAuthorizationTests(AuthTestBase):
    DASHBOARDS = (
        ("super_admin", "superadmin:dashboard"),
        ("institute_admin", "accounts:institute_admin_dashboard"),
        ("teacher", "accounts:teacher_dashboard"),
        ("student", "accounts:student_dashboard"),
    )

    def test_each_role_can_only_access_its_own_dashboard(self):
        users = {
            "super_admin": self.super_admin,
            "institute_admin": self.institute_admin,
            "teacher": self.teacher,
            "student": self.student,
        }
        for owner_key, url_name in self.DASHBOARDS:
            for viewer_key, viewer_url_name in self.DASHBOARDS:
                self.client.logout()
                self.login_as(users[viewer_key])
                response = self.client.get(reverse(url_name))
                expected = 200 if viewer_key == owner_key else 403
                self.assertEqual(
                    response.status_code,
                    expected,
                    f"{viewer_key} accessing {owner_key} dashboard",
                )

    def test_dashboard_redirect_uses_role(self):
        expected = {
            self.super_admin: "superadmin:dashboard",
            self.institute_admin: "accounts:institute_admin_dashboard",
            self.teacher: "accounts:teacher_dashboard",
            self.student: "accounts:student_dashboard",
        }
        for user, url_name in expected.items():
            self.client.logout()
            self.login_as(user)
            response = self.client.get(reverse("accounts:dashboard"))
            self.assertRedirects(
                response, reverse(url_name), fetch_redirect_response=False
            )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("accounts:teacher_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])


class AccountManagementTests(AuthTestBase):
    def test_super_admin_creates_institute_admin(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse("accounts:institute_admin_create"),
            {
                "email": "newadmin@example.com",
                "first_name": "Nina",
                "last_name": "Admin",
                "institute": self.institute.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="newadmin@example.com")
        self.assertEqual(created.role, Role.INSTITUTE_ADMIN)
        self.assertEqual(created.institute, self.institute)
        self.assertTrue(created.check_password(PASSWORD))

    def test_institute_admin_cannot_create_another_admin(self):
        self.login_as(self.institute_admin)
        response = self.client.post(
            reverse("accounts:institute_admin_create"),
            {
                "email": "forbidden@example.com",
                "first_name": "For",
                "last_name": "Bidden",
                "institute": self.institute.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="forbidden@example.com").exists())

    def test_institute_admin_creates_teacher_and_student_in_own_institute(self):
        self.login_as(self.institute_admin)
        for role in (Role.TEACHER, Role.STUDENT):
            email = f"new-{role}@example.com"
            response = self.client.post(
                reverse("accounts:role_user_create"),
                {
                    "email": email,
                    "first_name": "New",
                    "last_name": role.title(),
                    "role": role,
                    "phone": "9876543210",
                    "password1": PASSWORD,
                    "password2": PASSWORD,
                },
            )
            self.assertEqual(response.status_code, 302)
            created = User.objects.get(email=email)
            self.assertEqual(created.role, role)
            self.assertEqual(created.institute, self.institute)

    def test_role_user_create_rejects_super_admin_role(self):
        self.login_as(self.institute_admin)
        response = self.client.post(
            reverse("accounts:role_user_create"),
            {
                "email": "escalate@example.com",
                "first_name": "Bad",
                "last_name": "Actor",
                "role": Role.SUPER_ADMIN,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="escalate@example.com").exists())

    def test_super_admin_cannot_use_institute_admin_create_view(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse("accounts:role_user_create"))
        self.assertEqual(response.status_code, 403)

    def test_there_is_no_public_registration_endpoint(self):
        self.assertEqual(self.client.get("/accounts/register/").status_code, 404)

    def test_deactivation_blocks_login(self):
        self.login_as(self.institute_admin)
        response = self.client.post(
            reverse("accounts:user_deactivate", args=[self.teacher.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_active)

        self.client.logout()
        self.assertFalse(
            self.client.login(email=self.teacher.email, password=PASSWORD)
        )

        self.login_as(self.institute_admin)
        self.client.post(reverse("accounts:user_activate", args=[self.teacher.pk]))
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.is_active)

    def test_manager_cannot_modify_users_outside_scope(self):
        self.login_as(self.institute_admin)
        response = self.client.post(
            reverse("accounts:user_deactivate", args=[self.other_teacher.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.other_teacher.refresh_from_db()
        self.assertTrue(self.other_teacher.is_active)

    def test_manager_cannot_deactivate_self(self):
        self.login_as(self.institute_admin)
        self.client.post(
            reverse("accounts:user_deactivate", args=[self.institute_admin.pk])
        )
        self.institute_admin.refresh_from_db()
        self.assertTrue(self.institute_admin.is_active)

    def test_user_list_is_scoped_to_institute(self):
        self.login_as(self.institute_admin)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertContains(response, self.teacher.email)
        self.assertNotContains(response, self.other_teacher.email)


class InvitationTests(AuthTestBase):
    def test_full_invitation_registration_flow(self):
        self.login_as(self.institute_admin)
        response = self.client.post(
            reverse("accounts:invitation_create"),
            {"email": "invited@example.com", "role": Role.TEACHER},
        )
        self.assertEqual(response.status_code, 302)

        invitation = Invitation.objects.get(email="invited@example.com")
        self.assertEqual(invitation.institute, self.institute)
        self.assertEqual(invitation.created_by, self.institute_admin)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(invitation.token), mail.outbox[0].body)

        register_url = reverse(
            "accounts:invitation_register", args=[str(invitation.token)]
        )
        self.assertEqual(self.client.get(register_url).status_code, 200)
        response = self.client.post(
            register_url,
            {
                "first_name": "Invited",
                "last_name": "Teacher",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)

        created = User.objects.get(email="invited@example.com")
        self.assertEqual(created.role, Role.TEACHER)
        self.assertEqual(created.institute, self.institute)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        self.assertFalse(invitation.is_valid)

        self.assertEqual(self.client.get(register_url).status_code, 400)

    def test_expired_invitation_is_rejected(self):
        invitation = Invitation.objects.create(
            email="expired@example.com",
            role=Role.STUDENT,
            institute=self.institute,
            created_by=self.institute_admin,
            expires_at=timezone.now() - timedelta(days=1),
        )
        url = reverse("accounts:invitation_register", args=[str(invitation.token)])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())


class PasswordTests(AuthTestBase):
    def test_password_reset_flow(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": self.teacher.email}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        match = re.search(
            r"/accounts/password-reset/confirm/([^/\s]+)/([^/\s]+)/", body
        )
        self.assertIsNotNone(match, "Reset link missing from email")

        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": match.group(1), "token": match.group(2)},
        )
        # Django 6 redirects from the token URL to a token-free URL so the
        # token is not leaked through the Referer header.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        form_url = response["Location"]
        self.assertTrue(form_url.endswith("/set-password/"))
        self.assertEqual(self.client.get(form_url).status_code, 200)
        response = self.client.post(
            form_url,
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.client.login(email=self.teacher.email, password=NEW_PASSWORD)
        )

    def test_password_change_requires_login(self):
        url = reverse("accounts:password_change")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        self.login_as(self.student)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            url,
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(NEW_PASSWORD))


class ProfileTests(AuthTestBase):
    def test_profile_update_and_image_upload(self):
        self.login_as(self.teacher)
        image = Image.new("RGB", (8, 8), (30, 120, 200))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        upload = SimpleUploadedFile(
            "avatar.png", buffer.getvalue(), content_type="image/png"
        )

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse("accounts:profile"),
                    {
                        "first_name": "Tara Updated",
                        "last_name": "Teacher",
                        "email": self.teacher.email,
                        "phone": "9876543210",
                        "profile_image": upload,
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.teacher.refresh_from_db()
                self.assertEqual(self.teacher.first_name, "Tara Updated")
                self.assertEqual(self.teacher.phone, "9876543210")
                self.assertTrue(self.teacher.profile_image.name.startswith("profiles/"))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class InstituteAdminDashboardTests(TestCase):
    """Live, tenant-scoped Institute Admin dashboard data and actions."""

    PASSWORD = "DashTest!123"

    def setUp(self):
        self.institute = Institute.objects.create(
            institute_name="Dashboard Coaching",
            owner_name="Dash Owner",
            email="dash@example.test",
            mobile="9876543210",
            address="1 Dashboard Road",
            city="Pune",
            state="Maharashtra",
            pincode="411001",
            status=RegistrationStatus.ACTIVE,
            is_active=True,
        )
        self.other_institute = Institute.objects.create(
            institute_name="Other Coaching",
            owner_name="Other Owner",
            email="other-dash@example.test",
            mobile="9876543211",
            address="2 Other Road",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            status=RegistrationStatus.ACTIVE,
            is_active=True,
        )
        self.admin = User.objects.create_user(
            "dash-admin@example.test",
            self.PASSWORD,
            role=Role.INSTITUTE_ADMIN,
            institute=self.institute,
        )
        self.teacher_user = User.objects.create_user(
            "dash-teacher@example.test",
            self.PASSWORD,
            role=Role.TEACHER,
            institute=self.institute,
        )
        self.super_admin = User.objects.create_superuser(
            "dash-owner@example.test", self.PASSWORD
        )
        self.client.login(email=self.admin.email, password=self.PASSWORD)

        now = timezone.now()
        plan = SubscriptionPlan.objects.create(
            slug="dashboard-test-plan",
            plan_name="Dashboard Plan",
            price=Decimal("999.00"),
            duration_in_days=30,
            duration_in_months=1,
            max_students=20,
            max_teachers=5,
            max_batches=5,
        )
        self.subscription = Subscription.all_objects.create(
            institute=self.institute,
            plan=plan,
            status=RegistrationStatus.ACTIVE,
            activated_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=20, seconds=60),
        )
        self.license = sync_license(self.subscription, self.super_admin)

        self.course = Course.objects.create(
            institute=self.institute, course_name="Mathematics", code="MATH-DASH"
        )
        self.batch = Batch.objects.create(
            institute=self.institute,
            batch_name="Morning",
            code="MORN-DASH",
            course=self.course,
        )
        self.teacher = Teacher.all_objects.create(
            institute=self.institute,
            teacher_id="TCH-DASH-1",
            full_name="Dash Teacher",
            email=self.teacher_user.email,
            account=self.teacher_user,
        )
        self.student = Student.all_objects.create(
            institute=self.institute,
            student_id="STU-DASH-1",
            full_name="Dash Student",
            email="dash-student@example.test",
            mobile="9000000001",
            course=self.course,
            batch=self.batch,
            status=StudentStatus.ACTIVE,
        )
        AttendanceRecord.objects.create(
            institute=self.institute,
            student=self.student,
            batch=self.batch,
            teacher=self.teacher,
            date=timezone.localdate(),
            status=AttendanceStatus.PRESENT,
        )
        self.exam = Examination.objects.create(
            institute=self.institute,
            title="Dash Midterm",
            course=self.course,
            batch=self.batch,
            exam_date=timezone.localdate(),
            max_marks=50,
        )
        Mark.objects.create(
            institute=self.institute,
            examination=self.exam,
            student=self.student,
            marks=Decimal("40.00"),
        )

        self.payment = Payment.objects.create(
            institute=self.institute,
            subscription=self.subscription,
            amount=Decimal("999.00"),
            payment_status=PaymentStatus.PAID,
            receipt_number="RCP-DASH-1",
            payment_date=now,
        )
        self.invoice = Invoice.objects.create(
            institute=self.institute,
            subscription=self.subscription,
            payment=self.payment,
            billing_name=self.institute.institute_name,
            billing_email=self.institute.email,
            subtotal=Decimal("999.00"),
            total_amount=Decimal("999.00"),
        )

    def dashboard(self):
        return self.client.get(reverse("accounts:institute_admin_dashboard"))

    def test_dashboard_renders_real_stats_and_chart_data(self):
        response = self.dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Institute overview")
        self.assertContains(response, "Live analytics")
        self.assertContains(response, "Students by course")
        self.assertContains(response, "Attendance trend")
        self.assertContains(response, "Examination results")
        self.assertContains(response, "Mathematics")
        self.assertContains(response, "100.0")

        stats = response.context["stats"]
        self.assertEqual(stats["Students"], 1)
        self.assertEqual(stats["Teachers"], 1)
        self.assertEqual(stats["Courses"], 1)
        self.assertEqual(stats["Batches"], 1)
        self.assertEqual(stats["Examinations"], 1)
        self.assertEqual(stats["Attendance"], "100.0%")
        self.assertEqual(response.context["course_values"], [1])
        self.assertEqual(response.context["exam_values"], [1, 0])

    def test_subscription_widget_actions_and_seats(self):
        response = self.dashboard()
        widget = response.context["subscription"]
        self.assertEqual(widget["plan"], self.subscription.plan)
        self.assertEqual(widget["days_remaining"], 20)
        self.assertFalse(widget["is_expired"])
        self.assertFalse(widget["expiring_soon"])
        self.assertEqual(widget["seats"]["Students"], {"used": 1, "limit": 20})
        for label in ("Renew", "Upgrade", "View Invoice", "Download Receipt"):
            self.assertContains(response, label)
        self.assertContains(response, reverse("payments:invoice_pdf", args=[self.invoice.pk]))
        self.assertContains(
            response, reverse("payments:payment_receipt", args=[self.payment.pk])
        )

    def test_expiring_soon_shows_warning(self):
        self.subscription.expires_at = timezone.now() + timedelta(days=3, seconds=60)
        self.subscription.save(update_fields=["expires_at"])
        response = self.dashboard()
        self.assertTrue(response.context["subscription"]["expiring_soon"])
        self.assertContains(response, "expires in 3 day(s)")

    def test_expired_subscription_shows_danger_warning(self):
        # An expired licence is redirected to the licence page by middleware,
        # so assert the widget data directly instead of the rendered response.
        from .dashboard_data import subscription_widget

        self.subscription.expires_at = timezone.now() - timedelta(days=1)
        self.subscription.save(update_fields=["expires_at"])
        widget = subscription_widget(self.institute)
        self.assertTrue(widget["is_expired"])
        self.assertFalse(widget["expiring_soon"])
        self.assertIn("has expired", widget["warning"])

    def test_dashboard_is_scoped_to_own_institute(self):
        foreign_course = Course.objects.create(
            institute=self.other_institute, course_name="Foreign Course", code="F-DASH"
        )
        Student.all_objects.create(
            institute=self.other_institute,
            student_id="STU-OTHER-1",
            full_name="Foreign Student",
            email="foreign-dash@example.test",
            mobile="9000000099",
            course=foreign_course,
            status=StudentStatus.ACTIVE,
        )
        response = self.dashboard()
        self.assertEqual(response.context["stats"]["Students"], 1)
        self.assertNotContains(response, "Foreign Course")
        self.assertNotContains(response, "Foreign Student")

    def test_only_institute_admin_may_view_dashboard(self):
        url = reverse("accounts:institute_admin_dashboard")
        self.client.logout()
        self.client.login(email=self.teacher_user.email, password=self.PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 403)

