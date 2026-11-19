"""Automated tests for tenant-scoped teacher administration and workspace."""

import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from assignments.models import Assignment
from attendance.models import AttendanceRecord
from batches.models import Batch
from courses.models import Course, Subject
from examinations.models import Examination, Mark
from institutes.models import Institute, RegistrationStatus
from licenses.services import sync_license
from notifications.models import BatchAnnouncement
from students.models import Student, StudentStatus
from study_material.models import StudyMaterial
from subscriptions.models import Subscription, SubscriptionPlan

from .models import Teacher, TeacherActivity, TeacherStatus
from .services import generate_teacher_id

User = get_user_model()
PASSWORD = "TeacherTest!123"


def make_institute(name, email, **kwargs):
    defaults = {
        "institute_name": name,
        "owner_name": f"{name} Owner",
        "email": email,
        "mobile": "9876543210",
        "address": "1 Teacher Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411001",
        "status": RegistrationStatus.ACTIVE,
        "is_active": True,
    }
    defaults.update(kwargs)
    return Institute.objects.create(**defaults)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TeacherManagementTests(TestCase):
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
        self.student_user = User.objects.create_user(
            "student@example.test",
            PASSWORD,
            role=Role.STUDENT,
            institute=self.institute,
        )
        self.super_admin = User.objects.create_superuser("owner@example.test", PASSWORD)

        self.plan = SubscriptionPlan.objects.create(
            slug="teacher-management-plan",
            plan_name="Teacher Test Plan",
            price=Decimal("999.00"),
            duration_in_days=30,
            duration_in_months=1,
            max_students=10,
            max_teachers=2,
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
        self.subject = Subject.objects.create(
            institute=self.institute, name="Algebra", code="ALG", course=self.course
        )
        self.batch = Batch.objects.create(
            institute=self.institute,
            name="Morning Batch",
            code="MORN",
            course=self.course,
        )

        self.unassigned_course = Course.objects.create(
            institute=self.institute, name="Physics", code="PHY"
        )
        self.unassigned_subject = Subject.objects.create(
            institute=self.institute,
            name="Mechanics",
            code="MECH",
            course=self.unassigned_course,
        )
        self.unassigned_batch = Batch.objects.create(
            institute=self.institute,
            name="Evening Batch",
            code="EVE",
            course=self.unassigned_course,
        )

        self.other_course = Course.objects.create(
            institute=self.other_institute, name="History", code="HIST"
        )
        self.other_subject = Subject.objects.create(
            institute=self.other_institute,
            name="Ancient History",
            code="AHIST",
            course=self.other_course,
        )
        self.other_batch = Batch.objects.create(
            institute=self.other_institute,
            name="Beta Batch",
            code="BETA",
            course=self.other_course,
        )
        mail.outbox = []

    def login(self, user):
        self.assertTrue(self.client.login(email=user.email, password=PASSWORD))

    def payload(self, **overrides):
        data = {
            "full_name": "Ananya Rao",
            "email": "ananya@example.test",
            "mobile": "9876543211",
            "qualification": "M.Sc. Mathematics",
            "experience": "5",
            "specialization": "Algebra",
            "joining_date": "2026-01-01",
            "status": TeacherStatus.ACTIVE,
            "subjects": [self.subject.pk],
            "batches": [self.batch.pk],
        }
        data.update(overrides)
        return data

    def create_teacher(self, email="created@example.test", **overrides):
        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_create"), self.payload(email=email, **overrides)
        )
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        return Teacher.all_objects.get(institute=self.institute, email=email)

    def make_workspace_teacher(self, **overrides):
        teacher = self.create_teacher("workspace@example.test", **overrides)
        account = teacher.account
        account.set_password(PASSWORD)
        account.save(update_fields=["password"])
        return teacher

    def make_student(self, email, full_name, batch):
        return Student.all_objects.create(
            institute=self.institute,
            student_id=f"STU-{email.split('@')[0].upper()[:6]}",
            full_name=full_name,
            email=email,
            mobile="9000000001",
            batch=batch,
            status=StudentStatus.ACTIVE,
        )

    def test_teacher_admin_pages_require_institute_admin(self):
        teacher = self.make_workspace_teacher()
        urls = [
            reverse("teachers:teacher_list"),
            reverse("teachers:teacher_create"),
            reverse("teachers:teacher_activity"),
            reverse("teachers:teacher_detail", args=[teacher.pk]),
            reverse("teachers:teacher_edit", args=[teacher.pk]),
            reverse("teachers:teacher_activate", args=[teacher.pk]),
            reverse("teachers:teacher_deactivate", args=[teacher.pk]),
            reverse("teachers:teacher_delete", args=[teacher.pk]),
        ]
        for url in urls:
            for user in (teacher.account, self.student_user):
                self.client.logout()
                self.login(user)
                self.assertEqual(
                    self.client.get(url).status_code,
                    403,
                    f"{user.email} must not access {url}",
                )
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_create_teacher_generates_id_and_login_account(self):
        teacher = self.create_teacher()
        self.assertRegex(teacher.teacher_id, r"^TCH-[A-Z0-9]{4}-\d{4}-\d{6}$")
        self.assertEqual(teacher.status, TeacherStatus.ACTIVE)
        self.assertTrue(teacher.is_active)
        self.assertEqual(teacher.qualification, "M.Sc. Mathematics")
        self.assertEqual(teacher.experience, 5)
        self.assertEqual(list(teacher.subjects.all()), [self.subject])
        self.assertEqual(list(teacher.batches.all()), [self.batch])

        account = teacher.account
        self.assertIsNotNone(account)
        self.assertEqual(account.role, Role.TEACHER)
        self.assertEqual(account.institute, self.institute)
        self.assertEqual(account.email, "created@example.test")
        self.assertEqual(account.first_name, "Ananya")
        self.assertEqual(account.last_name, "Rao")
        self.assertEqual(account.phone, "9876543211")
        self.assertTrue(account.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password-reset/confirm", mail.outbox[0].body)
        self.assertTrue(
            TeacherActivity.objects.filter(
                teacher=teacher, action="created", actor=self.admin
            ).exists()
        )

    def test_duplicate_email_is_rejected(self):
        self.create_teacher(email="duplicate@example.test")
        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_create"),
            self.payload(email="duplicate@example.test", full_name="Another Teacher"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already belongs to a login account")
        self.assertEqual(
            Teacher.all_objects.filter(institute=self.institute).count(), 1
        )
        self.assertEqual(
            User.objects.filter(email="duplicate@example.test").count(), 1
        )

    def test_max_teachers_limit_blocks_creation_with_upgrade_message(self):
        self.create_teacher(email="one@example.test")
        self.create_teacher(email="two@example.test")

        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_create"),
            self.payload(email="three@example.test"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Teacher.all_objects.filter(institute=self.institute).count(), 2)

        listing = self.client.get(reverse("teachers:teacher_list"))
        self.assertContains(listing, "Upgrade plan required")
        self.assertContains(listing, "all 2 seats are in use")

        form_page = self.client.get(reverse("teachers:teacher_create"))
        self.assertContains(form_page, "Upgrade plan required")
        self.assertContains(form_page, "disabled")

    def test_expired_subscription_blocks_creation(self):
        self.subscription.status = RegistrationStatus.EXPIRED
        self.subscription.save(update_fields=["status"])
        self.login(self.admin)
        with patch("licenses.services.validate_institute_license"):
            response = self.client.post(
                reverse("teachers:teacher_create"), self.payload()
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Teacher.all_objects.count(), 0)
            listing = self.client.get(reverse("teachers:teacher_list"))
        self.assertContains(listing, "active subscription is required")

    def test_edit_teacher_updates_profile_assignments_and_login(self):
        teacher = self.create_teacher()
        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_edit", args=[teacher.pk]),
            self.payload(
                email="edited@example.test",
                full_name="Meera Iyer",
                mobile="9000000010",
                specialization="Number Theory",
                subjects=[self.unassigned_subject.pk],
                batches=[self.unassigned_batch.pk],
            ),
        )
        self.assertEqual(response.status_code, 302)
        teacher.refresh_from_db()
        self.assertEqual(teacher.full_name, "Meera Iyer")
        self.assertEqual(teacher.mobile, "9000000010")
        self.assertEqual(teacher.specialization, "Number Theory")
        self.assertEqual(list(teacher.subjects.all()), [self.unassigned_subject])
        self.assertEqual(list(teacher.batches.all()), [self.unassigned_batch])

        account = teacher.account
        account.refresh_from_db()
        self.assertEqual(account.email, "edited@example.test")
        self.assertEqual(account.first_name, "Meera")
        self.assertEqual(account.last_name, "Iyer")
        self.assertEqual(account.phone, "9000000010")
        self.assertTrue(
            TeacherActivity.objects.filter(teacher=teacher, action="updated").exists()
        )

    def test_deactivate_and_activate_teacher_also_toggle_login(self):
        teacher = self.create_teacher()
        self.login(self.admin)
        self.client.post(
            reverse("teachers:teacher_deactivate", args=[teacher.pk])
        )
        teacher.refresh_from_db()
        self.assertEqual(teacher.status, TeacherStatus.INACTIVE)
        self.assertFalse(teacher.is_active)
        teacher.account.refresh_from_db()
        self.assertFalse(teacher.account.is_active)

        self.client.post(reverse("teachers:teacher_activate", args=[teacher.pk]))
        teacher.refresh_from_db()
        self.assertEqual(teacher.status, TeacherStatus.ACTIVE)
        self.assertTrue(teacher.is_active)
        teacher.account.refresh_from_db()
        self.assertTrue(teacher.account.is_active)
        self.assertTrue(
            TeacherActivity.objects.filter(
                teacher=teacher, action="deactivated"
            ).exists()
        )
        self.assertTrue(
            TeacherActivity.objects.filter(teacher=teacher, action="activated").exists()
        )

    def test_delete_teacher_removes_its_login_account(self):
        teacher = self.create_teacher(email="delete-me@example.test")
        self.login(self.admin)
        response = self.client.post(
            reverse("teachers:teacher_delete", args=[teacher.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Teacher.all_objects.filter(pk=teacher.pk).exists())
        self.assertFalse(User.objects.filter(email="delete-me@example.test").exists())

    def test_teacher_pages_are_tenant_scoped(self):
        own = self.create_teacher(email="own@example.test")
        other = Teacher.all_objects.create(
            institute=self.other_institute,
            teacher_id="TCH-OTHER-000001",
            employee_id="TCH-OTHER-000001",
            full_name="Hidden Teacher",
            email="hidden@example.test",
            mobile="9000000099",
        )
        self.login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("teachers:teacher_detail", args=[other.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("teachers:teacher_edit", args=[other.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("teachers:teacher_delete", args=[other.pk])
            ).status_code,
            404,
        )
        listing = self.client.get(reverse("teachers:teacher_list"))
        self.assertContains(listing, own.get_full_name())
        self.assertNotContains(listing, "Hidden Teacher")
        self.assertNotContains(listing, "hidden@example.test")

        response = self.client.post(
            reverse("teachers:teacher_create"),
            self.payload(
                email="forged@example.test",
                subjects=[self.other_subject.pk],
                batches=[self.other_batch.pk],
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Teacher.all_objects.filter(email="forged@example.test").exists()
        )

    def test_search_status_subject_and_batch_filters(self):
        self.plan.max_teachers = 5
        self.plan.save(update_fields=["max_teachers"])
        self.create_teacher(
            email="algebra@example.test",
            full_name="Alpha Teacher",
            specialization="Geometry",
        )
        self.create_teacher(
            email="mechanics@example.test",
            full_name="Beta Teacher",
            specialization="Statistics",
            status=TeacherStatus.INACTIVE,
            subjects=[self.unassigned_subject.pk],
            batches=[self.unassigned_batch.pk],
        )
        self.login(self.admin)
        listing = reverse("teachers:teacher_list")

        by_name = self.client.get(listing, {"q": "Alpha"})
        self.assertContains(by_name, "Alpha Teacher")
        self.assertNotContains(by_name, "Beta Teacher")

        by_status = self.client.get(listing, {"status": TeacherStatus.INACTIVE})
        self.assertContains(by_status, "Beta Teacher")
        self.assertNotContains(by_status, "Alpha Teacher")

        by_subject = self.client.get(listing, {"subject": self.unassigned_subject.pk})
        self.assertContains(by_subject, "Beta Teacher")
        self.assertNotContains(by_subject, "Alpha Teacher")

        by_batch = self.client.get(listing, {"batch": self.batch.pk})
        self.assertContains(by_batch, "Alpha Teacher")
        self.assertNotContains(by_batch, "Beta Teacher")

    def test_activity_log_is_tenant_scoped_and_filterable(self):
        teacher = self.create_teacher()
        other = Teacher.all_objects.create(
            institute=self.other_institute,
            teacher_id="TCH-OTHER-000002",
            employee_id="TCH-OTHER-000002",
            full_name="Other Activity Teacher",
            email="other-activity@example.test",
        )
        TeacherActivity.objects.create(
            institute=self.other_institute,
            teacher=other,
            action="created",
            notes="Hidden activity",
        )
        self.login(self.admin)
        response = self.client.get(
            reverse("teachers:teacher_activity"), {"teacher": teacher.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created by")
        self.assertNotContains(response, "Hidden activity")
        self.assertNotContains(response, "Other Activity Teacher")

    def test_teacher_sees_only_assigned_batches_and_students(self):
        teacher = self.make_workspace_teacher()
        assigned_student = self.make_student(
            "assigned-student@example.test", "Assigned Student", self.batch
        )
        hidden_student = self.make_student(
            "hidden-student@example.test", "Hidden Student", self.unassigned_batch
        )
        self.login(teacher.account)

        batches_page = self.client.get(reverse("teachers:my_batches"))
        self.assertContains(batches_page, self.batch.name)
        self.assertContains(batches_page, self.subject.name)
        self.assertNotContains(batches_page, self.unassigned_batch.name)
        self.assertNotContains(batches_page, self.unassigned_subject.name)

        students_page = self.client.get(reverse("teachers:my_students"))
        self.assertContains(students_page, assigned_student.get_full_name())
        self.assertNotContains(students_page, hidden_student.get_full_name())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="edumanage-teacher-materials-"))
    def test_teacher_uploads_material_only_to_assigned_courses(self):
        teacher = self.make_workspace_teacher()
        self.login(teacher.account)
        upload = SimpleUploadedFile("notes.txt", b"chapter one", content_type="text/plain")

        response = self.client.post(
            reverse("study_material:upload_material"),
            {
                "title": "Algebra Notes",
                "course": self.course.pk,
                "file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        material = StudyMaterial.objects.get(title="Algebra Notes")
        self.assertEqual(material.institute, self.institute)
        self.assertTrue(
            TeacherActivity.objects.filter(
                teacher=teacher, action="material_uploaded"
            ).exists()
        )

        response = self.client.post(
            reverse("study_material:upload_material"),
            {
                "title": "Physics Notes",
                "course": self.unassigned_course.pk,
                "file": SimpleUploadedFile("physics.txt", b"nope", content_type="text/plain"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StudyMaterial.objects.filter(title="Physics Notes").exists())
        self.assertContains(
            self.client.get(reverse("study_material:material_list")), "Algebra Notes"
        )

    def test_teacher_creates_assignments_only_for_assigned_batches_and_subjects(self):
        teacher = self.make_workspace_teacher()
        self.login(teacher.account)

        response = self.client.post(
            reverse("assignments:assignment_create"),
            {
                "title": "Algebra homework",
                "description": "Solve equations",
                "batch": self.batch.pk,
                "subject": self.subject.pk,
                "due_date": "2026-07-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        assignment = Assignment.objects.get(title="Algebra homework")
        self.assertEqual(assignment.teacher, teacher)
        self.assertEqual(assignment.course, self.course)
        self.assertEqual(assignment.institute, self.institute)

        response = self.client.post(
            reverse("assignments:assignment_create"),
            {
                "title": "Unauthorized homework",
                "batch": self.unassigned_batch.pk,
                "subject": self.unassigned_subject.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Assignment.objects.count(), 1)
        self.assertContains(
            self.client.get(reverse("assignments:assignment_list")), "Algebra homework"
        )

    def test_teacher_marks_attendance_only_in_assigned_batches(self):
        teacher = self.make_workspace_teacher()
        student = self.make_student(
            "attendance-student@example.test", "Attendance Student", self.batch
        )
        hidden_student = self.make_student(
            "hidden-attendance@example.test", "Hidden Attendance Student", self.unassigned_batch
        )
        self.login(teacher.account)

        response = self.client.get(
            reverse("attendance:mark_attendance"),
            {"batch": self.batch.pk, "date": "2026-06-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.get_full_name())

        response = self.client.post(
            reverse("attendance:mark_attendance"),
            {
                "batch": self.batch.pk,
                "date": "2026-06-01",
                f"status_{student.pk}": "present",
                f"status_{hidden_student.pk}": "present",
            },
        )
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(student=student)
        self.assertEqual(record.marked_by, teacher)
        self.assertEqual(record.status, "present")
        self.assertFalse(
            AttendanceRecord.objects.filter(student=hidden_student).exists()
        )

        response = self.client.post(
            reverse("attendance:mark_attendance"),
            {
                "batch": self.unassigned_batch.pk,
                "date": "2026-06-01",
                f"status_{hidden_student.pk}": "present",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AttendanceRecord.objects.filter(student=hidden_student).exists()
        )

    def test_teacher_creates_examination_and_enters_marks_in_assigned_scope(self):
        teacher = self.make_workspace_teacher()
        other_teacher = Teacher.all_objects.create(
            institute=self.institute,
            teacher_id="TCH-LOCAL-000009",
            employee_id="TCH-LOCAL-000009",
            full_name="Another Teacher",
            email="another-teacher@example.test",
        )
        student = self.make_student(
            "exam-student@example.test", "Exam Student", self.batch
        )
        hidden_student = self.make_student(
            "hidden-exam@example.test", "Hidden Exam Student", self.unassigned_batch
        )
        foreign_exam = Examination.objects.create(
            institute=self.institute,
            title="Foreign Exam",
            course=self.unassigned_course,
            batch=self.unassigned_batch,
            exam_date="2026-06-01",
            created_by=other_teacher,
        )

        self.login(teacher.account)
        response = self.client.post(
            reverse("examinations:examination_create"),
            {
                "title": "Algebra Test",
                "batch": self.batch.pk,
                "subject": self.subject.pk,
                "exam_date": "2026-06-01",
                "max_marks": "50",
            },
        )
        self.assertEqual(response.status_code, 302)
        exam = Examination.objects.get(title="Algebra Test")
        self.assertEqual(exam.created_by, teacher)

        response = self.client.post(
            reverse("examinations:enter_marks", args=[exam.pk]),
            {
                f"marks_{student.pk}": "42",
                f"marks_{hidden_student.pk}": "50",
            },
        )
        self.assertEqual(response.status_code, 302)
        mark = Mark.objects.get(examination=exam, student=student)
        self.assertEqual(mark.marks, Decimal("42"))
        self.assertEqual(mark.entered_by, teacher)
        self.assertFalse(Mark.objects.filter(student=hidden_student).exists())

        self.assertEqual(
            self.client.get(
                reverse("examinations:enter_marks", args=[foreign_exam.pk])
            ).status_code,
            404,
        )
        self.assertTrue(
            TeacherActivity.objects.filter(teacher=teacher, action="marks_entered").exists()
        )

    def test_teacher_sends_announcements_only_to_assigned_batches(self):
        teacher = self.make_workspace_teacher()
        self.login(teacher.account)

        response = self.client.post(
            reverse("notifications:announcement_create"),
            {
                "title": "Class shifted",
                "message": "Tomorrow's class starts at 10 AM.",
                "batch": self.batch.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        announcement = BatchAnnouncement.objects.get(title="Class shifted")
        self.assertEqual(announcement.batch, self.batch)
        self.assertEqual(announcement.created_by, teacher.account)
        self.assertEqual(announcement.institute, self.institute)

        response = self.client.post(
            reverse("notifications:announcement_create"),
            {
                "title": "Unauthorized notice",
                "message": "This batch is not mine.",
                "batch": self.unassigned_batch.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BatchAnnouncement.objects.count(), 1)
        self.assertContains(
            self.client.get(reverse("notifications:announcement_list")), "Class shifted"
        )
        self.assertTrue(
            TeacherActivity.objects.filter(
                teacher=teacher, action="announcement_sent"
            ).exists()
        )

    def test_teacher_id_generator_retries_on_collision(self):
        with patch("teachers.services.secrets.randbelow", side_effect=[111111]):
            first = generate_teacher_id(self.institute)
        Teacher.all_objects.create(
            institute=self.institute,
            teacher_id=first,
            employee_id=first,
            full_name="Collision Teacher",
            email="collision@example.test",
        )
        with patch("teachers.services.secrets.randbelow", side_effect=[111111, 222222]):
            second = generate_teacher_id(self.institute)
        self.assertTrue(second.endswith("-322222"))
        self.assertNotEqual(first, second)
