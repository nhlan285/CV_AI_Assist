from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from recruitment.models import CandidateProfile, Company, JobPost, RecruiterProfile


class Command(BaseCommand):
    help = "Tao du lieu mau cho he thong ATS recruitment."

    def handle(self, *args, **options):
        call_command("seed_skills")

        admin = ensure_user("admin", "admin@example.com", "admin12345", is_superuser=True, is_staff=True)
        recruiter = ensure_user("recruiter_demo", "recruiter@example.com", "demo12345")
        candidate = ensure_user("candidate_demo", "candidate@example.com", "demo12345")

        RecruiterProfile.objects.get_or_create(
            user=recruiter,
            defaults={"full_name": "Nguyen Minh Recruiter", "phone": "0900000001"},
        )
        CandidateProfile.objects.get_or_create(
            user=candidate,
            defaults={
                "full_name": "Tran An Candidate",
                "phone": "0900000002",
                "work_area": "TP. Ho Chi Minh / Remote",
                "skills": "Python, Django, REST API, SQL, Machine Learning",
                "summary": "Ung vien backend co kinh nghiem xay API va xu ly du lieu.",
            },
        )
        company, _ = Company.objects.get_or_create(
            recruiter=recruiter,
            defaults={
                "name": "Astra Talent Lab",
                "website": "https://example.com",
                "address": "Quan 1, TP. Ho Chi Minh",
                "company_size": "50-100",
                "description": "Cong ty cong nghe xay dung san pham HR Tech va AI automation.",
            },
        )

        deadline = timezone.localdate() + timedelta(days=30)
        jobs = [
            {
                "title": "Backend Developer Django",
                "location": "TP. Ho Chi Minh",
                "work_mode": JobPost.WorkMode.HYBRID,
                "job_type": JobPost.JobType.FULL_TIME,
                "salary_min": 18000000,
                "salary_max": 32000000,
                "required_skills": "Python, Django, REST API, PostgreSQL, Git",
                "description": "Xay dung API, xu ly business logic va toi uu hieu nang cho nen tang tuyen dung.",
                "requirements": "Nam vung Django, co kinh nghiem thiet ke database va lam viec voi REST API.",
                "benefits": "Bao hiem, review luong, thoi gian lam viec linh hoat.",
            },
            {
                "title": "AI/NLP Engineer",
                "location": "Remote",
                "work_mode": JobPost.WorkMode.REMOTE,
                "job_type": JobPost.JobType.FULL_TIME,
                "salary_min": 25000000,
                "salary_max": 45000000,
                "required_skills": "Python, NLP, sentence-transformers, spaCy, Machine Learning",
                "description": "Phat trien pipeline CV parsing, semantic matching va scoring cho he thong ATS.",
                "requirements": "Co kinh nghiem NLP, embedding model va xu ly text tieng Viet/tieng Anh.",
                "benefits": "Lam tu xa, ngan sach hoc tap, co hoi lam san pham AI that.",
            },
            {
                "title": "HR Tech Product Intern",
                "location": "Da Nang",
                "work_mode": JobPost.WorkMode.ONSITE,
                "job_type": JobPost.JobType.INTERN,
                "salary_min": 4000000,
                "salary_max": 7000000,
                "required_skills": "Research, Excel, Communication, English",
                "description": "Ho tro nghien cuu hanh vi nha tuyen dung va cai tien flow ung tuyen.",
                "requirements": "Chu dong, giao tiep tot, quan tam san pham HR Tech.",
                "benefits": "Mentor truc tiep, co phu cap, xac nhan thuc tap.",
            },
        ]
        for job_data in jobs:
            JobPost.objects.get_or_create(
                company=company,
                title=job_data["title"],
                defaults={**job_data, "deadline": deadline, "is_active": True},
            )

        self.stdout.write(self.style.SUCCESS("Da tao du lieu demo."))
        self.stdout.write("Admin: admin / admin12345")
        self.stdout.write("Recruiter: recruiter_demo / demo12345")
        self.stdout.write("Candidate: candidate_demo / demo12345")


def ensure_user(username, email, password, is_superuser=False, is_staff=False):
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    user.email = email
    user.is_superuser = is_superuser
    user.is_staff = is_staff or is_superuser
    if created or not user.has_usable_password():
        user.set_password(password)
    else:
        user.set_password(password)
    user.save()
    return user
