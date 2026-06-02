from django.contrib.auth.models import User
from django.test import TestCase
from unittest.mock import patch

from .forms import ApplicationStatusForm
from .models import CandidateProfile, Company, JobPost
from .services.ats import calculate_application_ats, canonicalize_skill, match_skills, parse_cv_profile, split_skills


class AtsUtilityTests(TestCase):
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
            "Python Django developer with RESTful APIs and 2 years experience. Bachelor degree.",
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


class CandidateProfileTests(TestCase):
    def test_candidate_profile_string_uses_full_name(self):
        user = User.objects.create_user("candidate")
        profile = CandidateProfile.objects.create(user=user, full_name="Nguyen Van A")
        self.assertEqual(str(profile), "Nguyen Van A")
