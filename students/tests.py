"""Automated tests for tenant-scoped student administration."""

import csv
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch

from PIL import Image

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from batches.models import Batch
from courses.models import Course
from institutes.models import Institute, RegistrationStatus
from licenses.services import sync_license
from subscriptions.models import Subscription, SubscriptionPlan

from .models import Student, StudentStatus
from .services import generate_enrollment_number

User = get_user_model()
PASSWORD = "StudentTest!123"
_image_buffer = BytesIO()
Image.new("RGB", (1, 1), color="red").save(_image_buffer, format="PNG")
PNG_1PX = _image_buffer.getvalue()


def make_institute(name, email, **kwargs):
    defaults = {
        "institute_name": name,
        "owner_name": f"{name} Owner",
        "email": email,
        "mobile": "9876543210",
        "address": "1 Student Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411001",
        "status": RegistrationStatus.ACTIVE,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Institute.objects.create(**defaults)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StudentManagementTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.institute = make_institute("Alpha Institute", "alpha@example.test")
        self.other_institute = make_institute("Beta Institute", "beta@example.test")

        self.admin = User.objects.create_user(
            "admin@example.test",
            PASSWORD,
            role=Role.INSTITUTE_ADMIN,
            institute=self.institute,
        )
        self.other_admin = User.objects.create_user(
            "other-admin@example.test",
            PASSWORD,
            role=Role.INSTITUTE_ADMIN,
            institute=self.other_institute,
        )
        self.teacher = User.objects.create_user(
            "teacher@example.test",
            PASSWORD,
            role=Role.TEACHER,
            institute=self.institute,
        )
        self.student_user = User.objects.create_user(
            "existing-student@example.test",
            PASSWORD,
            role=Role.STUDENT,
            institute=self.institute,
        )
        self.super_admin = User.objects.create_superuser("owner@example.test", PASSWORD)

        self.plan = SubscriptionPlan.objects.create(
            slug="student-management-plan",
            plan_name="Student Test Plan",
            price=Decimal("999.00"),
            duration_in_days=30,
            duration_in_months=1,
            max_students=2,
            max_teachers=5,
            max_batches=5,
        )
        self.subscription = Subscription.all_objects.create(
            institute=self.institute,
            plan=self.plan,
            status=RegistrationStatus.ACTIVE,
            activated_at=self.now - timedelta(days=1),
            expires_at=self.now + timedelta(days=29),
        )
        sync_license(self.subscription, self.super_admin)

        self.course = Course.objects.create(
            institute=self.institute, name="Mathematics", code="MATH"
        )
        self.other_course = Course.objects.create(
            institute=self.institute, name="Physics", code="PHY"
        )
        self.batch = Batch.objects.create(
            institute=self.institute,
            name="Morning Batch",
            code="MORN",
            course=self.course,
        )
        self.other_batch = Batch.objects.create(
            institute=self.institute,
            name="Evening Batch",
            code="EVE",
            course=self.other_course,
        )
        mail.outbox = []

    def login(self, user):
        self.assertTrue(self.client.login(email=user.email, password=PASSWORD))

    def payload(self, **overrides):
        data = {
            "full_name": "Aarav Sharma",
            "email": "aarav@example.test",
            "mobile": "9876543211",
            "date_of_birth": "2010-05-14",
            "gender": "male",
            "address": "12 Main Street",
            "parent_name": "Raj Sharma",
            "parent_mobile": "9876543212",
            "qualification": "Class IX",
            "course": self.course.pk,
            "batch": self.batch.pk,
            "admission_date": "2026-06-01",
            "status": StudentStatus.ACTIVE,
        }
        data.update(overrides)
        return data

    def create_student(self, email="created@example.test", **overrides):
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_create"),
            self.payload(email=email, **overrides),
        )
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        return Student.all_objects.get(institute=self.institute, email=email)

    def test_student_admin_pages_require_institute_admin(self):
        legacy = Student.all_objects.create(
            institute=self.institute,
            student_id="STU-LEGACY-000001",
            full_name="Legacy Student",
            email="legacy@example.test",
            mobile="9000000000",
        )
        urls = [
            reverse("students:student_list"),
            reverse("students:student_create"),
            reverse("students:student_export"),
            reverse("students:student_detail", args=[legacy.pk]),
            reverse("students:student_edit", args=[legacy.pk]),
            reverse("students:student_activate", args=[legacy.pk]),
            reverse("students:student_deactivate", args=[legacy.pk]),
            reverse("students:student_delete", args=[legacy.pk]),
        ]
        for url in urls:
            for user in (self.teacher, self.student_user):
                self.client.logout()
                self.login(user)
                self.assertEqual(
                    self.client.get(url).status_code,
                    403,
                    f"{user.email} must not access {url}",
                )
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_create_student_generates_enrollment_and_login_account(self):
        student = self.create_student()
        self.assertRegex(student.student_id, r"^STU-[A-Z0-9]{4}-\d{4}-\d{6}$")
        self.assertEqual(student.status, StudentStatus.ACTIVE)
        self.assertTrue(student.is_active)
        self.assertIsNotNone(student.account)

        account = student.account
        self.assertEqual(account.role, Role.STUDENT)
        self.assertEqual(account.institute, self.institute)
        self.assertEqual(account.email, "created@example.test")
        self.assertEqual(account.first_name, "Aarav")
        self.assertTrue(account.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password-reset/confirm", mail.outbox[0].body)

    def test_duplicate_email_is_rejected(self):
        self.create_student(email="duplicate@example.test")
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_create"),
            self.payload(email="duplicate@example.test", full_name="Another Name"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already belongs to a login account")
        self.assertEqual(
            Student.all_objects.filter(institute=self.institute).count(), 1
        )
        self.assertEqual(
            User.objects.filter(email="duplicate@example.test").count(), 1
        )

    def test_max_students_limit_blocks_creation_with_upgrade_message(self):
        self.create_student(email="one@example.test")
        self.create_student(email="two@example.test")

        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_create"), self.payload(email="three@example.test")
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Student.all_objects.filter(institute=self.institute).count(), 2
        )

        listing = self.client.get(reverse("students:student_list"))
        self.assertContains(listing, "Upgrade plan required")
        self.assertContains(listing, "all 2 seats are in use")

        form_page = self.client.get(reverse("students:student_create"))
        self.assertContains(form_page, "Upgrade plan required")
        self.assertContains(form_page, "disabled")

    def test_expired_subscription_blocks_creation(self):
        self.subscription.status = RegistrationStatus.EXPIRED
        self.subscription.save(update_fields=["status"])
        self.login(self.admin)
        # The license gate would normally redirect first; keep it out of the way
        # so the student module's own plan check is what we exercise here.
        with patch("licenses.services.validate_institute_license"):
            response = self.client.post(
                reverse("students:student_create"), self.payload()
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Student.all_objects.count(), 0)
            listing = self.client.get(reverse("students:student_list"))
        self.assertContains(listing, "active subscription is required")

    def test_edit_student_updates_profile_and_login(self):
        student = self.create_student()
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_edit", args=[student.pk]),
            self.payload(
                email="edited@example.test",
                full_name="Meera Iyer",
                mobile="9000000010",
                course=self.other_course.pk,
                batch=self.other_batch.pk,
            ),
        )
        self.assertEqual(response.status_code, 302)
        student.refresh_from_db()
        self.assertEqual(student.full_name, "Meera Iyer")
        self.assertEqual(student.mobile, "9000000010")
        self.assertEqual(student.course, self.other_course)
        self.assertEqual(student.batch, self.other_batch)

        account = student.account
        account.refresh_from_db()
        self.assertEqual(account.email, "edited@example.test")
        self.assertEqual(account.first_name, "Meera")
        self.assertEqual(account.last_name, "Iyer")
        self.assertEqual(account.phone, "9000000010")

    def test_deactivate_and_activate_student_also_toggle_login(self):
        student = self.create_student()
        self.login(self.admin)
        self.client.post(reverse("students:student_deactivate", args=[student.pk]))
        student.refresh_from_db()
        self.assertEqual(student.status, StudentStatus.INACTIVE)
        self.assertFalse(student.is_active)
        self.assertFalse(student.account.is_active)

        self.client.post(reverse("students:student_activate", args=[student.pk]))
        student.refresh_from_db()
        self.assertEqual(student.status, StudentStatus.ACTIVE)
        self.assertTrue(student.is_active)
        self.assertTrue(student.account.is_active)

    def test_delete_student_removes_its_login_account(self):
        student = self.create_student(email="delete-me@example.test")
        self.assertEqual(User.objects.filter(email="delete-me@example.test").count(), 1)
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_delete", args=[student.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Student.all_objects.filter(pk=student.pk).exists())
        self.assertFalse(User.objects.filter(email="delete-me@example.test").exists())

    def test_student_pages_are_tenant_scoped(self):
        own = self.create_student(email="own@example.test")
        other_subscription = Subscription.all_objects.create(
            institute=self.other_institute,
            plan=self.plan,
            status=RegistrationStatus.ACTIVE,
            expires_at=self.now + timedelta(days=10),
        )
        other_student = Student.all_objects.create(
            institute=self.other_institute,
            student_id="STU-BETA-000001",
            full_name="Hidden Student",
            email="hidden@example.test",
            mobile="9000000099",
        )
        self.assertTrue(other_subscription.pk)

        self.login(self.admin)
        self.assertEqual(
            self.client.get(reverse("students:student_detail", args=[other_student.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("students:student_edit", args=[other_student.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("students:student_delete", args=[other_student.pk])
            ).status_code,
            404,
        )
        listing = self.client.get(reverse("students:student_list"))
        self.assertContains(listing, own.get_full_name())
        self.assertNotContains(listing, "Hidden Student")
        self.assertNotContains(listing, "hidden@example.test")

    def test_search_and_filters_only_return_matching_own_students(self):
        self.create_student(email="math@example.test", full_name="Alpha One")
        self.plan.max_students = 5
        self.plan.save(update_fields=["max_students"])
        self.create_student(
            email="physics@example.test",
            full_name="Beta Two",
            course=self.other_course.pk,
            batch=self.other_batch.pk,
            status=StudentStatus.INACTIVE,
        )

        self.login(self.admin)
        listing = reverse("students:student_list")

        by_name = self.client.get(listing, {"q": "Alpha"})
        self.assertContains(by_name, "Alpha One")
        self.assertNotContains(by_name, "Beta Two")

        by_status = self.client.get(listing, {"status": StudentStatus.INACTIVE})
        self.assertContains(by_status, "Beta Two")
        self.assertNotContains(by_status, "Alpha One")

        by_course = self.client.get(listing, {"course": self.other_course.pk})
        self.assertContains(by_course, "Beta Two")
        self.assertNotContains(by_course, "Alpha One")

        by_batch = self.client.get(listing, {"batch": self.batch.pk})
        self.assertContains(by_batch, "Alpha One")
        self.assertNotContains(by_batch, "Beta Two")

    def test_export_csv_contains_only_the_requesting_institute(self):
        self.create_student(email="export@example.test", full_name="Export Student")
        Student.all_objects.create(
            institute=self.other_institute,
            student_id="STU-OTHER-000002",
            full_name="Other Institute Student",
            email="other-export@example.test",
        )

        self.login(self.admin)
        response = self.client.get(reverse("students:student_export"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("students-", response["Content-Disposition"])

        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[0][0], "Student ID")
        body = "\n".join(",".join(row) for row in rows)
        self.assertIn("Export Student", body)
        self.assertIn("export@example.test", body)
        self.assertNotIn("Other Institute Student", body)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="edumanage-students-"))
    def test_profile_picture_upload_is_partitioned_by_tenant(self):
        self.create_student()
        student = Student.all_objects.get(institute=self.institute)
        self.login(self.admin)
        upload = SimpleUploadedFile("avatar.png", PNG_1PX, content_type="image/png")
        response = self.client.post(
            reverse("students:student_edit", args=[student.pk]),
            self.payload(profile_picture=upload),
        )
        self.assertEqual(response.status_code, 302)
        student.refresh_from_db()
        self.assertTrue(
            student.profile_picture.name.startswith(
                f"tenants/{self.institute.pk}/students/"
            )
        )

        download_url = reverse(
            "core:secure_download",
            args=["students", "student", student.pk, "profile_picture"],
        )
        self.assertEqual(self.client.get(download_url).status_code, 200)
        self.client.logout()
        self.login(self.other_admin)
        self.assertEqual(self.client.get(download_url).status_code, 404)

    def test_enrollment_generator_retries_on_collision(self):
        with patch("students.services.secrets.randbelow", side_effect=[11111]):
            first = generate_enrollment_number(self.institute)
        Student.all_objects.create(
            institute=self.institute,
            student_id=first,
            full_name="Collision",
            email="collision@example.test",
        )
        with patch("students.services.secrets.randbelow", side_effect=[11111, 122222]):
            second = generate_enrollment_number(self.institute)
        self.assertTrue(second.endswith("-222222"))
        self.assertNotEqual(first, second)

    def _foreign_enrollment(self):
        course = Course.all_objects.create(
            institute=self.other_institute,
            name="Foreign Course",
            code="FOREIGN-C",
        )
        batch = Batch.all_objects.create(
            institute=self.other_institute,
            name="Foreign Batch",
            code="FOREIGN-B",
            course=course,
        )
        return course, batch

    def test_student_form_scopes_course_and_batch_to_request_institute(self):
        course, batch = self._foreign_enrollment()
        self.login(self.admin)
        create_url = reverse("students:student_create")

        form_page = self.client.get(create_url)
        self.assertEqual(form_page.status_code, 200)
        self.assertNotContains(form_page, "Foreign Course")
        self.assertNotContains(form_page, "Foreign Batch")
        self.assertContains(form_page, "Mathematics")

        response = self.client.post(
            create_url,
            self.payload(
                email="foreign-create@example.test",
                course=course.pk,
                batch=batch.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not belong to your institute")
        self.assertFalse(
            Student.all_objects.filter(email="foreign-create@example.test").exists()
        )

    def test_student_edit_rejects_foreign_course_and_batch(self):
        student = self.create_student(email="edit-tenant@example.test")
        course, batch = self._foreign_enrollment()
        self.login(self.admin)
        response = self.client.post(
            reverse("students:student_edit", args=[student.pk]),
            self.payload(
                email=student.email,
                course=course.pk,
                batch=batch.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not belong to your institute")
        student.refresh_from_db()
        self.assertNotEqual(student.course_id, course.pk)
        self.assertNotEqual(student.batch_id, batch.pk)
