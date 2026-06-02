from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationForm, ApplicationStatusForm
from .models import (
    Application,
    CandidateProfile,
    Company,
    CVDocument,
    JobPost,
    Notification,
    RecruiterProfile,
    Skill,
    SkillAlias,
)
from .services.ats import (
    calculate_application_ats,
    canonicalize_skill,
    match_skills,
    match_skills_with_evidence,
    parse_cv_profile,
    reset_skill_alias_cache,
    split_skills,
)
from .services.notifications import notify_candidate_status_update, notify_recruiter_new_application


class AtsUtilityTests(TestCase):
    def setUp(self):
        reset_skill_alias_cache()

    def tearDown(self):
        reset_skill_alias_cache()

    def test_split_skills_accepts_commas_and_newlines(self):
        self.assertEqual(split_skills("Python, Django\nSQL"), ["Python", "Django", "SQL"])

    def test_match_skills_is_case_insensitive(self):
        matched, missing = match_skills("Kinh nghiem Python va Django", ["python", "SQL"])
        self.assertEqual(matched, ["Python"])
        self.assertEqual(missing, ["SQL"])

    def test_split_skills_canonicalizes_common_aliases(self):
        raw = "ReactJS, RESTful API\nNode.js; C/C++"
        self.assertEqual(split_skills(raw), ["React", "REST API", "Node.js", "C/C++"])

    def test_split_skills_preserves_c_cpp_combo(self):
        self.assertEqual(split_skills("C/C++, Node.js, React.js"), ["C/C++", "Node.js", "React"])

    def test_match_skills_uses_aliases_and_missing_skills(self):
        cv_text = "Built ReactJS UI, RESTful APIs, Node.js services, C++ modules, and ML models."
        required = split_skills("React, REST API, Node.js, C/C++, Machine Learning, Docker")
        matched, missing = match_skills(cv_text, required)
        self.assertEqual(matched, ["React", "REST API", "Node.js", "C/C++", "Machine Learning"])
        self.assertEqual(missing, ["Docker"])

    def test_match_skills_does_not_match_java_inside_javascript(self):
        matched, missing = match_skills("Strong JavaScript and React experience.", ["Java"])
        self.assertEqual(matched, [])
        self.assertEqual(missing, ["Java"])

    def test_canonicalize_skill_handles_vietnamese_alias(self):
        self.assertEqual(canonicalize_skill("tiếng anh"), "English")

    def test_database_skill_alias_extends_ats_dictionary(self):
        skill = Skill.objects.create(name="Next.js", category="Frontend")
        SkillAlias.objects.create(skill=skill, alias="nextjs")
        SkillAlias.objects.create(skill=skill, alias="next js")

        reset_skill_alias_cache()

        self.assertEqual(canonicalize_skill("nextjs"), "Next.js")
        matched, missing = match_skills("Built production nextjs applications.", ["Next.js"])
        self.assertEqual(matched, ["Next.js"])
        self.assertEqual(missing, [])
        self.assertIn("Next.js", parse_cv_profile("Skills: nextjs, React")["skills"])

    def test_inactive_database_skill_alias_is_ignored(self):
        skill = Skill.objects.create(name="SvelteKit", is_active=False)
        SkillAlias.objects.create(skill=skill, alias="sveltekit")

        reset_skill_alias_cache()

        self.assertEqual(canonicalize_skill("sveltekit"), "sveltekit")

    def test_seed_skills_command_creates_default_dictionary(self):
        output = StringIO()
        call_command("seed_skills", stdout=output)

        self.assertTrue(Skill.objects.filter(name="Python").exists())
        self.assertTrue(SkillAlias.objects.filter(skill__name="React", alias="reactjs").exists())

    def test_parse_cv_profile_extracts_contact_links_and_skills(self):
        parsed = parse_cv_profile(
            """
            Nguyen Van A
            Email: a@example.com
            Phone: 0901234567
            GitHub: github.com/example/dev
            Skills: ReactJS, RESTful APIs, Node.js, Docker
            Education
            University of Technology
            Projects
            ATS dashboard with Django
            """
        )
        self.assertEqual(parsed["email"], "a@example.com")
        self.assertEqual(parsed["phone"], "0901234567")
        self.assertIn("https://github.com/example/dev", parsed["links"])
        self.assertIn("React", parsed["skills"])
        self.assertIn("REST API", parsed["skills"])
        self.assertTrue(parsed["education_summary"])
        self.assertTrue(parsed["project_summary"])

    def test_spacy_parser_extracts_sections_and_skill_evidence(self):
        parsed = parse_cv_profile(
            """
            Nguyen Van A
            Experience
            Built Django RESTful APIs for recruitment workflow.
            Projects
            Developed React dashboard with Chart.js.
            Education
            University of Technology
            Certifications
            AWS Cloud Practitioner
            """
        )

        evidence_by_skill = {item["skill"]: item["section"] for item in parsed["skill_evidence"]}
        self.assertEqual(evidence_by_skill["Django"], "experience")
        self.assertEqual(evidence_by_skill["REST API"], "experience")
        self.assertEqual(evidence_by_skill["React"], "projects")
        self.assertIn("Built Django RESTful APIs", parsed["experience_summary"])
        self.assertIn("Developed React dashboard", parsed["project_summary"])
        self.assertIn("AWS Cloud Practitioner", parsed["certification_summary"])

    def test_match_skills_with_evidence_returns_context_sections(self):
        matched, missing, evidence = match_skills_with_evidence(
            """
            Experience
            Built production Django APIs.
            Projects
            React reporting dashboard.
            """,
            ["Django", "React", "Docker"],
        )

        self.assertEqual(matched, ["Django", "React"])
        self.assertEqual(missing, ["Docker"])
        self.assertEqual({item["skill"]: item["section"] for item in evidence}, {"Django": "experience", "React": "projects"})

    @patch("recruitment.services.ats.semantic_similarity_score", return_value=(80, "semantic ok"))
    def test_calculate_application_ats_returns_breakdown_and_summary(self, _mock_semantic):
        recruiter = User.objects.create_user("ats_recruiter")
        company = Company.objects.create(recruiter=recruiter, name="Demo Co")
        job = JobPost.objects.create(
            company=company,
            title="Backend Developer",
            location="Remote",
            required_skills="Python, Django, REST API, Docker",
            description="Build APIs",
            requirements="Python Django RESTful API",
        )
        result = calculate_application_ats(
            """
            Experience
            Python Django developer with RESTful APIs and 2 years experience.
            Education
            Bachelor degree.
            """,
            job,
        )
        self.assertIn("breakdown", result)
        self.assertEqual(result["semantic_score"], 80)
        self.assertGreater(result["skill_score"], 70)
        self.assertIn("Docker", result["missing_skills"])
        self.assertTrue(result["summary"])

    def test_application_status_form_validates_manual_score_range(self):
        form = ApplicationStatusForm(
            data={
                "status": "applied",
                "review_status": "consider",
                "manual_score": 6,
                "recruiter_note": "Xem thêm portfolio.",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("manual_score", form.errors)


class JobPostModelTests(TestCase):
    def test_salary_display_for_range(self):
        recruiter = User.objects.create_user("recruiter")
        company = Company.objects.create(recruiter=recruiter, name="Demo Co")
        job = JobPost.objects.create(
            company=company,
            title="Backend Developer",
            location="Remote",
            salary_min=10000000,
            salary_max=20000000,
            required_skills="Python",
            description="Build APIs",
            requirements="Django",
        )
        self.assertIn("10,000,000", job.salary_display())


class JobSearchSortTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user("job_recruiter", password="pass12345")
        RecruiterProfile.objects.create(user=self.recruiter, full_name="Recruiter")
        self.company = Company.objects.create(recruiter=self.recruiter, name="Demo Co")

    def create_job(self, title, days_ago=0, **extra):
        job = JobPost.objects.create(
            company=self.company,
            title=title,
            location=extra.get("location", "Remote"),
            required_skills=extra.get("required_skills", "Python, Django"),
            description=extra.get("description", "Build APIs"),
            requirements=extra.get("requirements", "Python Django"),
            is_active=extra.get("is_active", True),
        )
        JobPost.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        job.refresh_from_db()
        return job

    def test_public_job_list_defaults_to_newest_first(self):
        old_job = self.create_job("Backend Old", days_ago=5)
        new_job = self.create_job("Backend New", days_ago=1)

        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["jobs"])[:2], [new_job, old_job])
        self.assertEqual(response.context["filters"]["sort"], "newest")

    def test_public_job_list_keeps_search_when_sorting_oldest_first(self):
        old_job = self.create_job("Backend Old", days_ago=5)
        new_job = self.create_job("Backend New", days_ago=1)
        self.create_job("Data Engineer", days_ago=10, required_skills="SQL")

        response = self.client.get(reverse("job_list"), {"q": "Backend", "sort": "oldest"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["jobs"]), [old_job, new_job])

    def test_recruiter_job_list_search_status_and_sort(self):
        old_active = self.create_job("Remote Backend Old", days_ago=6)
        new_active = self.create_job("Remote Backend New", days_ago=2)
        self.create_job("Remote Backend Hidden", days_ago=1, is_active=False)

        self.client.login(username="job_recruiter", password="pass12345")
        response = self.client.get(
            reverse("recruiter_jobs"),
            {"q": "Remote Backend", "status": "active", "sort": "oldest"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["jobs"]), [old_active, new_active])


class CandidateProfileTests(TestCase):
    def test_candidate_profile_string_uses_full_name(self):
        user = User.objects.create_user("candidate")
        profile = CandidateProfile.objects.create(user=user, full_name="Nguyen Van A")
        self.assertEqual(str(profile), "Nguyen Van A")


class CVDocumentSoftDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cv_candidate", password="pass12345")
        self.candidate = CandidateProfile.objects.create(user=self.user, full_name="CV Candidate")
        self.cv = CVDocument.objects.create(
            candidate=self.candidate,
            title="Primary CV",
            file="cvs/primary.pdf",
            original_filename="primary.pdf",
        )

    def test_soft_delete_marks_cv_without_removing_record(self):
        self.cv.soft_delete()
        self.cv.refresh_from_db()

        self.assertTrue(self.cv.is_deleted)
        self.assertIsNotNone(self.cv.deleted_at)
        self.assertTrue(CVDocument.objects.filter(pk=self.cv.pk).exists())

    def test_deleted_cv_is_not_selectable_when_applying(self):
        deleted_cv = CVDocument.objects.create(
            candidate=self.candidate,
            title="Old CV",
            file="cvs/old.pdf",
            original_filename="old.pdf",
            is_deleted=True,
            deleted_at=timezone.now(),
        )

        form = ApplicationForm(candidate=self.candidate)

        self.assertIn(self.cv, form.fields["cv"].queryset)
        self.assertNotIn(deleted_cv, form.fields["cv"].queryset)

    def test_cv_delete_view_hides_cv_from_candidate_pages(self):
        self.client.login(username="cv_candidate", password="pass12345")
        delete_response = self.client.post(reverse("cv_delete", args=[self.cv.pk]))
        self.assertRedirects(delete_response, reverse("cv_list"))

        self.cv.refresh_from_db()
        self.assertTrue(self.cv.is_deleted)

        list_response = self.client.get(reverse("cv_list"))
        self.assertEqual(list(list_response.context["cv_documents"]), [])

        dashboard_response = self.client.get(reverse("candidate_dashboard"))
        self.assertEqual(dashboard_response.context["cv_count"], 0)


class NotificationTests(TestCase):
    def setUp(self):
        self.recruiter_user = User.objects.create_user("recruiter", password="pass12345")
        self.candidate_user = User.objects.create_user(
            "candidate",
            email="candidate@example.com",
            password="pass12345",
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            full_name="Nguyen Van A",
        )
        self.company = Company.objects.create(recruiter=self.recruiter_user, name="Demo Co")
        self.job = JobPost.objects.create(
            company=self.company,
            title="Backend Developer",
            location="Remote",
            required_skills="Python, Django",
            description="Build APIs",
            requirements="Python Django",
        )
        self.cv = CVDocument.objects.create(
            candidate=self.candidate,
            title="Main CV",
            file="cvs/test.pdf",
            original_filename="test.pdf",
        )
        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
            cv=self.cv,
            ats_score=82,
        )

    @patch("recruitment.services.notifications.push_notification")
    def test_candidate_status_notification_uses_application_status_metadata(self, _mock_push):
        self.application.status = Application.Status.SHORTLISTED
        notification = notify_candidate_status_update(self.application)
        self.assertEqual(notification.user, self.candidate_user)
        self.assertEqual(notification.notification_type, Notification.Type.APPLICATION_STATUS)
        self.assertEqual(notification.metadata["status"], Application.Status.SHORTLISTED)
        self.assertEqual(notification.target_url, reverse("application_history"))

    @patch("recruitment.services.notifications.push_notification")
    def test_recruiter_new_application_notification_groups_by_job(self, _mock_push):
        notification = notify_recruiter_new_application(self.application)
        notify_recruiter_new_application(self.application)

        notification.refresh_from_db()
        self.assertEqual(notification.count, 2)
        self.assertFalse(notification.is_read)

        notification.is_read = True
        notification.save(update_fields=["is_read"])
        notify_recruiter_new_application(self.application)

        notification.refresh_from_db()
        self.assertEqual(notification.count, 1)
        self.assertFalse(notification.is_read)

    def test_notification_poll_and_mark_read_endpoints(self):
        notification = Notification.objects.create(
            user=self.candidate_user,
            title="Test notification",
            message="Notification body",
            notification_type=Notification.Type.APPLICATION_SUCCESS,
            target_url=reverse("application_history"),
        )
        self.client.login(username="candidate", password="pass12345")

        poll_response = self.client.get(reverse("notifications_poll"))
        self.assertEqual(poll_response.status_code, 200)
        self.assertEqual(poll_response.json()["unread_count"], 1)

        read_response = self.client.post(reverse("notification_mark_read", args=[notification.pk]))
        self.assertEqual(read_response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(read_response.json()["unread_count"], 0)
