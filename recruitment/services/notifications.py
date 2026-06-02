from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.utils import timezone

from recruitment.models import Application, Notification


def notification_group_name(user_id):
    return f"user_notifications_{user_id}"


def serialize_notification(notification):
    return {
        "id": notification.pk,
        "title": notification.title,
        "message": notification.message,
        "notification_type": notification.notification_type,
        "target_url": notification.target_url,
        "count": notification.count,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else "",
        "last_event_at": notification.last_event_at.isoformat() if notification.last_event_at else "",
        "last_event_label": timezone.localtime(notification.last_event_at).strftime("%d/%m/%Y %H:%M"),
        "metadata": notification.metadata,
    }


def push_notification(notification):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    unread_count = Notification.objects.filter(user_id=notification.user_id, is_read=False).count()
    async_to_sync(channel_layer.group_send)(
        notification_group_name(notification.user_id),
        {
            "type": "notification.event",
            "payload": {
                "kind": "notification",
                "unread_count": unread_count,
                "notification": serialize_notification(notification),
            },
        },
    )


def _status_title(application):
    status_title_map = {
        Application.Status.REVIEWED: "CV của bạn đã được xem",
        Application.Status.SHORTLISTED: "CV của bạn đã được duyệt",
        Application.Status.INTERVIEW: "Bạn được mời phỏng vấn",
        Application.Status.REJECTED: "Ứng tuyển của bạn chưa phù hợp",
        Application.Status.HIRED: "Bạn đã được tuyển",
    }
    return status_title_map.get(
        application.status,
        "Trạng thái ứng tuyển đã được cập nhật",
    )


def notify_candidate_application_success(application):
    notification = Notification.objects.create(
        user=application.candidate.user,
        title="Ứng tuyển đã được gửi",
        message=(
            f"Bạn đã ứng tuyển vào vị trí {application.job.title}. "
            f"ATS hiện tại: {application.ats_score:.1f}/100."
        ),
        notification_type=Notification.Type.APPLICATION_SUCCESS,
        target_url=reverse("application_history"),
        metadata={
            "application_id": application.pk,
            "job_id": application.job_id,
            "ats_score": round(application.ats_score or 0, 1),
        },
    )
    push_notification(notification)
    return notification


def notify_candidate_status_update(application):
    notification = Notification.objects.create(
        user=application.candidate.user,
        title=_status_title(application),
        message=(
            f"Ứng tuyển {application.job.title} đã chuyển sang trạng thái "
            f"{application.get_status_display()}."
        ),
        notification_type=Notification.Type.APPLICATION_STATUS,
        target_url=reverse("application_history"),
        metadata={
            "application_id": application.pk,
            "job_id": application.job_id,
            "status": application.status,
            "status_label": application.get_status_display(),
        },
    )
    push_notification(notification)
    return notification


def notify_recruiter_new_application(application):
    recruiter_user = application.job.company.recruiter
    group_key = f"job_new_application:{application.job_id}"
    now = timezone.now()
    notification = Notification.objects.filter(user=recruiter_user, group_key=group_key).first()

    if notification:
        notification.count = 1 if notification.is_read else notification.count + 1
        notification.is_read = False
        notification.last_event_at = now
    else:
        notification = Notification(
            user=recruiter_user,
            notification_type=Notification.Type.NEW_APPLICATION,
            group_key=group_key,
            target_url=reverse("recruiter_job_applications", args=[application.job_id]),
            last_event_at=now,
        )

    notification.title = "Đơn ứng tuyển mới"
    notification.message = (
        f'Bài tuyển dụng "{application.job.title}" có '
        f"{notification.count} đơn ứng tuyển mới."
    )
    notification.notification_type = Notification.Type.NEW_APPLICATION
    notification.target_url = reverse("recruiter_job_applications", args=[application.job_id])
    notification.metadata = {
        "job_id": application.job_id,
        "job_title": application.job.title,
        "latest_application_id": application.pk,
    }
    notification.save()
    push_notification(notification)
    return notification
