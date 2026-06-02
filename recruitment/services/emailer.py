from django.conf import settings
from django.core.mail import send_mail

from recruitment.services.notifications import (
    notify_candidate_application_success,
    notify_candidate_status_update,
)


def send_application_success_email(application):
    candidate_user = application.candidate.user
    subject = f"Da ung tuyen: {application.job.title}"
    message = (
        f"Chao {application.candidate.full_name},\n\n"
        f"Ban da ung tuyen thanh cong vao vi tri {application.job.title} "
        f"tai {application.job.company.name}.\n"
        f"ATS score hien tai: {application.ats_score:.2f}/100.\n\n"
        "He thong se thong bao khi nha tuyen dung cap nhat trang thai."
    )
    notify_candidate_application_success(application)
    send_if_configured(subject, message, [candidate_user.email])


def send_status_update_email(application):
    candidate_user = application.candidate.user
    subject = f"Cap nhat trang thai: {application.job.title}"
    message = (
        f"Chao {application.candidate.full_name},\n\n"
        f"Trang thai ung tuyen cua ban cho vi tri {application.job.title} "
        f"da duoc cap nhat thanh: {application.get_status_display()}.\n"
    )
    notify_candidate_status_update(application)
    send_if_configured(subject, message, [candidate_user.email])


def send_if_configured(subject, message, recipients):
    recipients = [email for email in recipients if email]
    if not recipients or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        return
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )
