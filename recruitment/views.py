from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Avg, Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    ApplicationForm,
    ApplicationStatusForm,
    CandidateProfileForm,
    CandidateRegistrationForm,
    CompanyForm,
    CVUploadForm,
    JobPostForm,
    RecruiterRegistrationForm,
    VietnameseAuthenticationForm,
)
from .models import Application, Company, CVDocument, JobPost, Notification, SavedJob
from .services.ats import calculate_application_ats, ensure_cv_text
from .services.emailer import send_application_success_email, send_status_update_email
from .services.notifications import notify_recruiter_new_application, serialize_notification


SCORE_GROUPS = [
    ("lt50", "Dưới 50"),
    ("50_69", "50-69"),
    ("70_84", "70-84"),
    ("85_100", "85-100"),
]


JOB_SORT_CHOICES = [
    ("newest", "Mới nhất trước"),
    ("oldest", "Cũ nhất trước"),
]


class VietnameseLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    authentication_form = VietnameseAuthenticationForm


def is_candidate(user):
    return hasattr(user, "candidate_profile")


def is_recruiter(user):
    return hasattr(user, "recruiter_profile") and hasattr(user, "company")


def month_shift(year, month, offset):
    total = year * 12 + (month - 1) + offset
    return total // 12, total % 12 + 1


def build_recruiter_timeline(applications, period):
    today = timezone.localdate()
    if period == "year":
        labels = [str(today.year - offset) for offset in range(4, -1, -1)]
        keys = labels[:]
        start_date = date(today.year - 4, 1, 1)

        def key_for(value):
            return str(timezone.localtime(value).year)

    elif period == "month":
        months = [month_shift(today.year, today.month, offset) for offset in range(-11, 1)]
        keys = [f"{year}-{month:02d}" for year, month in months]
        labels = [f"{month:02d}/{year}" for year, month in months]
        first_year, first_month = months[0]
        start_date = date(first_year, first_month, 1)

        def key_for(value):
            local_value = timezone.localtime(value)
            return f"{local_value.year}-{local_value.month:02d}"

    else:
        dates = [today - timedelta(days=offset) for offset in range(29, -1, -1)]
        keys = [date.isoformat() for date in dates]
        labels = [date.strftime("%d/%m") for date in dates]
        start_date = dates[0]

        def key_for(value):
            return timezone.localtime(value).date().isoformat()

    totals = {key: 0 for key in keys}
    score_sums = {key: 0.0 for key in keys}
    recent_applications = applications.filter(created_at__date__gte=start_date).values("created_at", "ats_score")
    for application in recent_applications:
        key = key_for(application["created_at"])
        if key not in totals:
            continue
        totals[key] += 1
        score_sums[key] += application["ats_score"] or 0

    counts = [totals[key] for key in keys]
    average_scores = [
        round(score_sums[key] / totals[key], 1) if totals[key] else 0
        for key in keys
    ]
    return labels, counts, average_scores


def score_bucket_counts(applications):
    return [
        applications.filter(ats_score__lt=50).count(),
        applications.filter(ats_score__gte=50, ats_score__lt=70).count(),
        applications.filter(ats_score__gte=70, ats_score__lt=85).count(),
        applications.filter(ats_score__gte=85).count(),
    ]


def normalize_job_sort(sort_value):
    return sort_value if sort_value in dict(JOB_SORT_CHOICES) else "newest"


def apply_job_sort(jobs, sort_value):
    if sort_value == "oldest":
        return jobs.order_by("created_at", "id")
    return jobs.order_by("-created_at", "-id")


def candidate_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_candidate(request.user):
            return render(request, "recruitment/403.html", status=403)
        return view_func(request, *args, **kwargs)

    return wrapper


def recruiter_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_recruiter(request.user):
            return render(request, "recruitment/403.html", status=403)
        return view_func(request, *args, **kwargs)

    return wrapper


def job_list(request):
    jobs = JobPost.objects.select_related("company").filter(is_active=True)
    q = request.GET.get("q", "").strip()
    location = request.GET.get("location", "").strip()
    skill = request.GET.get("skill", "").strip()
    work_mode = request.GET.get("work_mode", "").strip()
    job_type = request.GET.get("job_type", "").strip()
    sort = normalize_job_sort(request.GET.get("sort", "newest").strip())

    if q:
        jobs = jobs.filter(
            Q(title__icontains=q)
            | Q(company__name__icontains=q)
            | Q(description__icontains=q)
            | Q(requirements__icontains=q)
            | Q(required_skills__icontains=q)
        )
    if location:
        jobs = jobs.filter(location__icontains=location)
    if skill:
        jobs = jobs.filter(required_skills__icontains=skill)
    if work_mode:
        jobs = jobs.filter(work_mode=work_mode)
    if job_type:
        jobs = jobs.filter(job_type=job_type)

    jobs = apply_job_sort(jobs, sort)
    job_count = jobs.count()
    return render(
        request,
        "recruitment/job_list.html",
        {
            "jobs": jobs,
            "job_count": job_count,
            "filters": {
                "q": q,
                "location": location,
                "skill": skill,
                "work_mode": work_mode,
                "job_type": job_type,
                "sort": sort,
            },
            "sort_choices": JOB_SORT_CHOICES,
            "work_modes": JobPost.WorkMode.choices,
            "job_types": JobPost.JobType.choices,
        },
    )


def job_detail(request, pk):
    job = get_object_or_404(JobPost.objects.select_related("company"), pk=pk, is_active=True)
    JobPost.objects.filter(pk=job.pk).update(view_count=job.view_count + 1)

    saved = False
    application = None
    if request.user.is_authenticated and is_candidate(request.user):
        candidate = request.user.candidate_profile
        saved = SavedJob.objects.filter(candidate=candidate, job=job).exists()
        application = Application.objects.filter(candidate=candidate, job=job).first()

    return render(
        request,
        "recruitment/job_detail.html",
        {"job": job, "saved": saved, "application": application},
    )


def register_candidate(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = CandidateRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Đăng ký ứng viên thành công.")
        return redirect("candidate_dashboard")
    return render(request, "registration/register_candidate.html", {"form": form})


def register_recruiter(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RecruiterRegistrationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Đăng ký nhà tuyển dụng và công ty thành công.")
        return redirect("recruiter_dashboard")
    return render(request, "registration/register_recruiter.html", {"form": form})


@login_required
def dashboard(request):
    if is_candidate(request.user):
        return redirect("candidate_dashboard")
    if is_recruiter(request.user):
        return redirect("recruiter_dashboard")
    if request.user.is_superuser:
        return redirect("admin:index")
    return render(request, "recruitment/403.html", status=403)


@login_required
def notifications_page(request):
    view_filter = request.GET.get("filter", "all")
    notifications = request.user.notifications.all()
    if view_filter == "unread":
        notifications = notifications.filter(is_read=False)
    else:
        view_filter = "all"
    return render(
        request,
        "recruitment/notifications.html",
        {
            "notifications": notifications,
            "view_filter": view_filter,
            "unread_count": request.user.notifications.filter(is_read=False).count(),
        },
    )


@login_required
def notifications_poll(request):
    notifications = request.user.notifications.all()[:8]
    return JsonResponse(
        {
            "unread_count": request.user.notifications.filter(is_read=False).count(),
            "notifications": [serialize_notification(notification) for notification in notifications],
        }
    )


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return JsonResponse(
        {
            "ok": True,
            "target_url": notification.target_url,
            "unread_count": request.user.notifications.filter(is_read=False).count(),
        }
    )


@login_required
@require_POST
def notifications_mark_all_read(request):
    updated = request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "updated": updated, "unread_count": 0})


@candidate_required
def candidate_dashboard(request):
    candidate = request.user.candidate_profile
    applications = candidate.applications.select_related("job", "job__company").all()
    saved_jobs = candidate.saved_jobs.select_related("job", "job__company").all()[:5]
    recommended_jobs = JobPost.objects.filter(is_active=True).select_related("company")[:6]
    active_cv_documents = candidate.cv_documents.filter(is_deleted=False)
    return render(
        request,
        "recruitment/candidate_dashboard.html",
        {
            "candidate": candidate,
            "applications": applications[:5],
            "application_count": applications.count(),
            "cv_count": active_cv_documents.count(),
            "saved_jobs": saved_jobs,
            "recommended_jobs": recommended_jobs,
        },
    )


@candidate_required
def candidate_profile(request):
    candidate = request.user.candidate_profile
    form = CandidateProfileForm(request.POST or None, instance=candidate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật hồ sơ.")
        return redirect("candidate_profile")
    return render(request, "recruitment/candidate_profile.html", {"form": form})


@candidate_required
def cv_list(request):
    candidate = request.user.candidate_profile
    form = CVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        cv_document = form.save(commit=False)
        cv_document.candidate = candidate
        cv_document.original_filename = cv_document.file.name
        cv_document.save()
        try:
            ensure_cv_text(cv_document)
            messages.success(request, "Đã upload và đọc nội dung CV PDF.")
        except Exception as exc:
            messages.error(request, f"Đã lưu file nhưng chưa đọc được CV: {exc}")
        return redirect("cv_list")
    return render(
        request,
        "recruitment/cv_list.html",
        {"form": form, "cv_documents": candidate.cv_documents.filter(is_deleted=False)},
    )


@candidate_required
def cv_delete(request, pk):
    candidate = request.user.candidate_profile
    cv_document = get_object_or_404(
        CVDocument,
        pk=pk,
        candidate=candidate,
        is_deleted=False,
    )
    if request.method == "POST":
        cv_document.soft_delete()
        messages.success(request, "Đã xóa CV khỏi danh sách sử dụng.")
        return redirect("cv_list")
    return render(request, "recruitment/cv_confirm_delete.html", {"cv_document": cv_document})


@candidate_required
def saved_jobs(request):
    candidate = request.user.candidate_profile
    return render(
        request,
        "recruitment/saved_jobs.html",
        {"saved_jobs": candidate.saved_jobs.select_related("job", "job__company").all()},
    )


@candidate_required
def toggle_saved_job(request, pk):
    job = get_object_or_404(JobPost, pk=pk, is_active=True)
    candidate = request.user.candidate_profile
    saved, created = SavedJob.objects.get_or_create(candidate=candidate, job=job)
    if created:
        messages.success(request, "Đã lưu việc làm.")
    else:
        saved.delete()
        messages.info(request, "Đã bỏ lưu việc làm.")
    next_url = request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("job_detail", pk=job.pk)


@candidate_required
def application_history(request):
    candidate = request.user.candidate_profile
    applications = candidate.applications.select_related("job", "job__company", "cv")
    return render(request, "recruitment/application_history.html", {"applications": applications})


@candidate_required
def apply_job(request, pk):
    job = get_object_or_404(JobPost.objects.select_related("company"), pk=pk, is_active=True)
    candidate = request.user.candidate_profile
    if Application.objects.filter(candidate=candidate, job=job).exists():
        messages.info(request, "Bạn đã ứng tuyển công việc này.")
        return redirect("job_detail", pk=job.pk)
    if not candidate.cv_documents.filter(is_deleted=False).exists():
        messages.warning(request, "Bạn cần upload CV PDF trước khi ứng tuyển.")
        return redirect("cv_list")

    form = ApplicationForm(request.POST or None, candidate=candidate)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.candidate = candidate
        application.job = job
        try:
            cv_text = ensure_cv_text(application.cv)
            if not cv_text:
                raise ValueError("CV PDF khong co text de tinh ATS.")
            result = calculate_application_ats(cv_text, job)
        except Exception as exc:
            messages.error(request, f"Chưa thể tính ATS score cho CV này: {exc}")
            return render(request, "recruitment/apply_job.html", {"form": form, "job": job})

        application.ats_score = result["score"]
        application.ats_semantic_score = result["semantic_score"]
        application.ats_skill_score = result["skill_score"]
        application.ats_breakdown = result["breakdown"]
        application.matched_skills = result["matched_skills"]
        application.missing_skills = result["missing_skills"]
        application.ai_summary = result["summary"]
        application.ats_notes = result["notes"]
        application.save()
        notify_recruiter_new_application(application)
        send_application_success_email(application)
        messages.success(request, "Ứng tuyển thành công. Email thông báo sẽ được gửi nếu SMTP đã cấu hình.")
        return redirect("application_history")

    return render(request, "recruitment/apply_job.html", {"form": form, "job": job})


def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    jobs = company.jobs.filter(is_active=True)
    return render(request, "recruitment/company_detail.html", {"company": company, "jobs": jobs})


@recruiter_required
def recruiter_dashboard(request):
    company = request.user.company
    jobs = company.jobs.all()
    applications = Application.objects.filter(job__company=company).select_related("candidate", "job")
    period = request.GET.get("period", "day")
    if period not in {"day", "month", "year"}:
        period = "day"

    status_counts_raw = applications.values("status").annotate(total=Count("id")).order_by("status")
    status_labels = dict(Application.Status.choices)
    status_total_map = {item["status"]: item["total"] for item in status_counts_raw}
    status_counts = [
        {
            "status": status,
            "label": label,
            "total": status_total_map.get(status, 0),
        }
        for status, label in Application.Status.choices
    ]
    top_applications = applications.order_by("-ats_score")[:8]
    needs_manual_review_count = applications.filter(
        ats_score__lt=70,
        review_status__in=[Application.ReviewStatus.NOT_REVIEWED, Application.ReviewStatus.CONSIDER],
    ).count()
    timeline_labels, timeline_counts, timeline_scores = build_recruiter_timeline(applications, period)
    top_jobs = (
        jobs.annotate(
            application_total=Count("applications"),
            average_score=Avg("applications__ats_score"),
            best_score=Max("applications__ats_score"),
        )
        .filter(application_total__gt=0)
        .order_by("-application_total", "-best_score")[:6]
    )
    chart_data = {
        "timeline": {
            "labels": timeline_labels,
            "counts": timeline_counts,
            "average_scores": timeline_scores,
        },
        "statuses": {
            "labels": [item["label"] for item in status_counts],
            "totals": [item["total"] for item in status_counts],
        },
        "score_buckets": {
            "labels": [label for _, label in SCORE_GROUPS],
            "totals": score_bucket_counts(applications),
        },
        "top_jobs": {
            "labels": [job.title for job in top_jobs],
            "totals": [job.application_total for job in top_jobs],
        },
    }
    return render(
        request,
        "recruitment/recruiter_dashboard.html",
        {
            "company": company,
            "job_count": jobs.count(),
            "active_job_count": jobs.filter(is_active=True).count(),
            "application_count": applications.count(),
            "average_ats_score": applications.aggregate(score=Avg("ats_score"))["score"] or 0,
            "needs_manual_review_count": needs_manual_review_count,
            "period": period,
            "status_counts": status_counts,
            "top_applications": top_applications,
            "top_jobs": top_jobs,
            "chart_data": chart_data,
        },
    )


@recruiter_required
def company_update(request):
    company = request.user.company
    form = CompanyForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật công ty.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "recruitment/company_form.html", {"form": form, "company": company})


@recruiter_required
def recruiter_jobs(request):
    jobs = request.user.company.jobs.annotate(application_total=Count("applications"))
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    sort = normalize_job_sort(request.GET.get("sort", "newest").strip())

    if q:
        jobs = jobs.filter(
            Q(title__icontains=q)
            | Q(location__icontains=q)
            | Q(required_skills__icontains=q)
            | Q(description__icontains=q)
            | Q(requirements__icontains=q)
        )
    if status == "active":
        jobs = jobs.filter(is_active=True)
    elif status == "inactive":
        jobs = jobs.filter(is_active=False)
    else:
        status = ""

    jobs = apply_job_sort(jobs, sort)
    return render(
        request,
        "recruitment/recruiter_jobs.html",
        {
            "jobs": jobs,
            "job_count": jobs.count(),
            "filters": {"q": q, "status": status, "sort": sort},
            "sort_choices": JOB_SORT_CHOICES,
        },
    )


@recruiter_required
def job_create(request):
    form = JobPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.company = request.user.company
        job.save()
        messages.success(request, "Đã tạo bài tuyển dụng.")
        return redirect("recruiter_jobs")
    return render(request, "recruitment/job_form.html", {"form": form, "title": "Tạo bài tuyển dụng"})


@recruiter_required
def job_update(request, pk):
    job = get_object_or_404(JobPost, pk=pk, company=request.user.company)
    form = JobPostForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật bài tuyển dụng.")
        return redirect("recruiter_jobs")
    return render(request, "recruitment/job_form.html", {"form": form, "title": "Sửa bài tuyển dụng"})


@recruiter_required
def job_delete(request, pk):
    job = get_object_or_404(JobPost, pk=pk, company=request.user.company)
    if request.method == "POST":
        job.delete()
        messages.success(request, "Đã xóa bài tuyển dụng.")
        return redirect("recruiter_jobs")
    return render(request, "recruitment/job_confirm_delete.html", {"job": job})


@recruiter_required
def recruiter_job_applications(request, pk):
    job = get_object_or_404(JobPost, pk=pk, company=request.user.company)
    applications = job.applications.select_related("candidate", "candidate__user", "cv").order_by("-ats_score")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    review_status = request.GET.get("review_status", "").strip()
    score_group = request.GET.get("score_group", "").strip()
    if q:
        applications = applications.filter(
            Q(candidate__full_name__icontains=q)
            | Q(candidate__user__email__icontains=q)
            | Q(candidate__skills__icontains=q)
            | Q(cv__extracted_text__icontains=q)
        )
    if status in dict(Application.Status.choices):
        applications = applications.filter(status=status)
    if review_status in dict(Application.ReviewStatus.choices):
        applications = applications.filter(review_status=review_status)
    if score_group == "lt50":
        applications = applications.filter(ats_score__lt=50)
    elif score_group == "50_69":
        applications = applications.filter(ats_score__gte=50, ats_score__lt=70)
    elif score_group == "70_84":
        applications = applications.filter(ats_score__gte=70, ats_score__lt=85)
    elif score_group == "85_100":
        applications = applications.filter(ats_score__gte=85)

    return render(
        request,
        "recruitment/recruiter_job_applications.html",
        {
            "job": job,
            "applications": applications,
            "q": q,
            "status": status,
            "review_status": review_status,
            "score_group": score_group,
            "status_choices": Application.Status.choices,
            "review_status_choices": Application.ReviewStatus.choices,
            "score_groups": SCORE_GROUPS,
        },
    )


@recruiter_required
def application_status_update(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("job", "candidate", "candidate__user"),
        pk=pk,
        job__company=request.user.company,
    )
    old_status = application.status
    old_review_status = application.review_status
    old_recruiter_note = application.recruiter_note
    old_manual_score = application.manual_score
    form = ApplicationStatusForm(request.POST or None, instance=application)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        review_changed = (
            updated.review_status != old_review_status
            or updated.recruiter_note != old_recruiter_note
            or updated.manual_score != old_manual_score
        )
        if review_changed:
            updated.reviewed_at = timezone.now()
        updated.save()
        if updated.status != old_status:
            send_status_update_email(updated)
        messages.success(request, "Đã cập nhật trạng thái ứng tuyển.")
        return redirect("recruiter_job_applications", pk=application.job.pk)
    return render(
        request,
        "recruitment/application_status_form.html",
        {"form": form, "application": application},
    )
