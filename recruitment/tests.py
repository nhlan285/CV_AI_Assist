from django.contrib.auth.models import User
from django.test import TestCase

from .models import CandidateProfile, Company, JobPost
from .services.ats import match_skills, split_skills


class AtsUtilityTests(TestCase):
    def test_split_skills_accepts_commas_and_newlines(self):
        self.assertEqual(split_skills("Python, Django\nSQL"), ["Python", "Django", "SQL"])

    def test_match_skills_is_case_insensitive(self):
        matched, missing = match_skills("Kinh nghiem Python va Django", ["python", "SQL"])
        self.assertEqual(matched, ["python"])
        self.assertEqual(missing, ["SQL"])


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
