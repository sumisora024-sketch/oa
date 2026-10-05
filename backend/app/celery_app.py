from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "nit_oa",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    timezone="Asia/Tokyo",
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "poll-mailbox-every-minute": {
            "task": "app.tasks.poll_mailbox",
            "schedule": 60.0,
        },
        "contract-due-reminders-at-nine": {
            "task": "app.tasks.send_contract_due_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
        "process-due-offboardings-hourly": {
            "task": "app.tasks.process_due_offboardings",
            "schedule": crontab(minute=5),
        },
        "ensure-current-month-salaries-nightly": {
            "task": "app.tasks.ensure_current_month_salary_records",
            "schedule": crontab(hour=1, minute=20),
        },
        "dispatch-notifications-every-minute": {
            "task": "app.tasks.dispatch_notifications",
            "schedule": 60.0,
        },
    },
)
