from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename


def candidate_cv_upload_path(instance, filename):
    safe_name = get_valid_filename(Path(filename).name)
    user_id = instance.candidate.user_id if instance.candidate_id else "unknown"
    return f"cvs/{user_id}/{safe_name}"


def company_logo_upload_path(instance, filename):
    safe_name = get_valid_filename(Path(filename).name)
    company_id = instance.pk or "new"
    return f"company_logos/{company_id}/{safe_name}"


def validate_pdf_size(file_obj):
    max_size = getattr(settings, "CV_MAX_UPLOAD_SIZE", 5 * 1024 * 1024)
    if file_obj.size > max_size:
        mb = max_size / (1024 * 1024)
        raise ValidationError(f"File CV toi da {mb:.0f}MB.")


class CandidateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate_profile")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    work_area = models.CharField(max_length=120, blank=True)
    skills = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.get_username()


class RecruiterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="recruiter_profile")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.get_username()


class Company(models.Model):
    recruiter = models.OneToOneField(User, on_delete=models.CASCADE, related_name="company")
    name = models.CharField(max_length=180)
    logo = models.FileField(upload_to=company_logo_upload_path, blank=True)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    company_size = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class JobPost(models.Model):
    class WorkMode(models.TextChoices):
        ONSITE = "onsite", "Tại văn phòng"
        REMOTE = "remote", "Từ xa"
        HYBRID = "hybrid", "Linh hoạt"

    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Toàn thời gian"
        PART_TIME = "part_time", "Bán thời gian"
        INTERN = "intern", "Thực tập"
        CONTRACT = "contract", "Hợp đồng"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=180)
    location = models.CharField(max_length=120)
    work_mode = models.CharField(max_length=20, choices=WorkMode.choices, default=WorkMode.ONSITE)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULL_TIME)
    salary_min = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    salary_max = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    required_skills = models.TextField(help_text="Nhap cac ky nang cach nhau bang dau phay hoac xuong dong.")
    description = models.TextField()
    requirements = models.TextField()
    benefits = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.is_active and (not self.deadline or self.deadline >= timezone.localdate())

    def salary_display(self):
        if self.salary_min and self.salary_max:
            return f"{self.salary_min:,} - {self.salary_max:,} VND"
        if self.salary_min:
            return f"Tu {self.salary_min:,} VND"
        if self.salary_max:
            return f"Den {self.salary_max:,} VND"
        return "Thoa thuan"


class CVDocument(models.Model):
    class ParseStatus(models.TextChoices):
        PENDING = "pending", "Chờ xử lý"
        PARSED = "parsed", "Đã đọc CV"
        FAILED = "failed", "Lỗi đọc CV"

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="cv_documents")
    title = models.CharField(max_length=150, blank=True)
    file = models.FileField(
        upload_to=candidate_cv_upload_path,
        validators=[FileExtensionValidator(["pdf"]), validate_pdf_size],
    )
    original_filename = models.CharField(max_length=255, blank=True)
    extracted_text = models.TextField(blank=True)
    extracted_email = models.EmailField(blank=True)
    extracted_phone = models.CharField(max_length=40, blank=True)
    extracted_links = models.JSONField(default=list, blank=True)
    extracted_skills = models.TextField(blank=True)
    education_summary = models.TextField(blank=True)
    project_summary = models.TextField(blank=True)
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
    )
    parse_error = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.original_filename or f"CV #{self.pk}"

    def soft_delete(self):
        if self.is_deleted:
            return
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Đã ứng tuyển"
        SCREENING = "screening", "Đang xem xét"
        REVIEWED = "reviewed", "Đã xem"
        SHORTLISTED = "shortlisted", "Phù hợp"
        INTERVIEW = "interview", "Phỏng vấn"
        REJECTED = "rejected", "Từ chối"
        HIRED = "hired", "Đã tuyển"

    class ReviewStatus(models.TextChoices):
        NOT_REVIEWED = "not_reviewed", "Chưa xem"
        CONSIDER = "consider", "Cần cân nhắc"
        FIT = "fit", "Phù hợp"
        REJECTED = "rejected", "Từ chối"

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="applications")
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    cv = models.ForeignKey(CVDocument, on_delete=models.PROTECT, related_name="applications")
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)
    ats_score = models.FloatField(default=0)
    ats_semantic_score = models.FloatField(default=0)
    ats_skill_score = models.FloatField(default=0)
    ats_breakdown = models.JSONField(default=dict, blank=True)
    matched_skills = models.TextField(blank=True)
    missing_skills = models.TextField(blank=True)
    ats_notes = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NOT_REVIEWED,
    )
    recruiter_note = models.TextField(blank=True)
    manual_score = models.PositiveSmallIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["candidate", "job"], name="unique_candidate_job_application")
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job}"


class SavedJob(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="saved_jobs")
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["candidate", "job"], name="unique_saved_job")
        ]

    def __str__(self):
        return f"{self.candidate} saved {self.job}"


class Skill(models.Model):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reset_ats_skill_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        reset_ats_skill_cache()
        return result


class SkillAlias(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["alias"]
        constraints = [
            models.UniqueConstraint(fields=["skill", "alias"], name="unique_skill_alias")
        ]

    def __str__(self):
        return f"{self.alias} -> {self.skill.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reset_ats_skill_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        reset_ats_skill_cache()
        return result


def reset_ats_skill_cache():
    try:
        from recruitment.services.ats import reset_skill_alias_cache
    except Exception:
        return
    reset_skill_alias_cache()


class Notification(models.Model):
    class Type(models.TextChoices):
        APPLICATION_SUCCESS = "application_success", "Ứng tuyển thành công"
        APPLICATION_STATUS = "application_status", "Cập nhật ứng tuyển"
        NEW_APPLICATION = "new_application", "Đơn ứng tuyển mới"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField()
    notification_type = models.CharField(max_length=40, choices=Type.choices, blank=True)
    target_url = models.CharField(max_length=255, blank=True)
    group_key = models.CharField(max_length=120, blank=True, db_index=True)
    count = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_event_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_event_at", "-created_at"]

    def __str__(self):
        return self.title
