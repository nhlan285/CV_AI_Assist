from django.contrib import admin

from .models import (
    Application,
    CandidateProfile,
    Company,
    CVDocument,
    JobPost,
    Notification,
    RecruiterProfile,
    SavedJob,
    Skill,
    SkillAlias,
)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "work_area", "updated_at")
    search_fields = ("full_name", "user__username", "user__email", "skills", "work_area")


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "updated_at")
    search_fields = ("full_name", "user__username", "user__email")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "recruiter", "website", "company_size", "updated_at")
    search_fields = ("name", "address", "description", "recruiter__username")


@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "location", "work_mode", "job_type", "is_active", "deadline")
    list_filter = ("is_active", "work_mode", "job_type", "location")
    search_fields = ("title", "company__name", "required_skills", "description", "requirements")


@admin.register(CVDocument)
class CVDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "candidate",
        "original_filename",
        "parse_status",
        "is_deleted",
        "extracted_email",
        "uploaded_at",
    )
    list_filter = ("parse_status", "is_deleted", "uploaded_at", "deleted_at")
    search_fields = (
        "title",
        "candidate__full_name",
        "original_filename",
        "extracted_text",
        "extracted_email",
        "extracted_phone",
        "extracted_skills",
    )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "review_status", "ats_score", "manual_score", "created_at")
    list_filter = ("status", "review_status", "created_at")
    search_fields = ("candidate__full_name", "job__title", "job__company__name", "ai_summary", "recruiter_note")


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "created_at")
    search_fields = ("candidate__full_name", "job__title")


class SkillAliasInline(admin.TabularInline):
    model = SkillAlias
    extra = 1
    fields = ("alias", "is_active")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "aliases__alias")
    inlines = [SkillAliasInline]


@admin.register(SkillAlias)
class SkillAliasAdmin(admin.ModelAdmin):
    list_display = ("alias", "skill", "is_active", "created_at")
    list_filter = ("is_active", "skill__category")
    search_fields = ("alias", "skill__name")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "count", "is_read", "last_event_at")
    list_filter = ("notification_type", "is_read", "last_event_at", "created_at")
    search_fields = ("title", "message", "group_key", "user__username")
