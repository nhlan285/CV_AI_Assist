from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/apply/", views.apply_job, name="apply_job"),
    path("jobs/<int:pk>/save/", views.toggle_saved_job, name="toggle_saved_job"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("login/", views.VietnameseLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("candidate/register/", views.register_candidate, name="register_candidate"),
    path("recruiter/register/", views.register_recruiter, name="register_recruiter"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications_page, name="notifications_page"),
    path("notifications/poll/", views.notifications_poll, name="notifications_poll"),
    path("notifications/<int:pk>/read/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/read-all/", views.notifications_mark_all_read, name="notifications_mark_all_read"),
    path("candidate/dashboard/", views.candidate_dashboard, name="candidate_dashboard"),
    path("candidate/profile/", views.candidate_profile, name="candidate_profile"),
    path("candidate/cvs/", views.cv_list, name="cv_list"),
    path("candidate/cvs/<int:pk>/delete/", views.cv_delete, name="cv_delete"),
    path("candidate/saved-jobs/", views.saved_jobs, name="saved_jobs"),
    path("candidate/applications/", views.application_history, name="application_history"),
    path("recruiter/dashboard/", views.recruiter_dashboard, name="recruiter_dashboard"),
    path("recruiter/company/", views.company_update, name="company_update"),
    path("recruiter/jobs/", views.recruiter_jobs, name="recruiter_jobs"),
    path("recruiter/jobs/new/", views.job_create, name="job_create"),
    path("recruiter/jobs/<int:pk>/edit/", views.job_update, name="job_update"),
    path("recruiter/jobs/<int:pk>/delete/", views.job_delete, name="job_delete"),
    path("recruiter/jobs/<int:pk>/applications/", views.recruiter_job_applications, name="recruiter_job_applications"),
    path("recruiter/applications/<int:pk>/status/", views.application_status_update, name="application_status_update"),
]
