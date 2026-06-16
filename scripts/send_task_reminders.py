"""Dispatch task reminders.

Finds open tasks whose deadline minus `reminder_offset_days` is today (or in
the past, for tasks that slipped through earlier runs) and that have not had
a reminder sent yet, then fires an in-app + email + push notification to the
assignee.

Run daily from cron:
    0 9 * * *  cd /srv/app && /srv/app/venv/bin/python scripts/send_task_reminders.py

The script is idempotent — once `reminder_sent_at` is set on a task, it is
never re-notified unless the deadline or offset changes (the route handlers
clear `reminder_sent_at` in those cases).
"""
from datetime import datetime, timedelta, date
from typing import Optional

from app import create_app
from app.extensions import db
from app.models.task import Task
from app.services.notification_service import create_notification


def _trigger_date(task: Task) -> Optional[date]:
    if not task.deadline or not task.reminder_offset_days:
        return None
    return (task.deadline - timedelta(days=task.reminder_offset_days)).date()


def dispatch_reminders(now=None):
    now = now or datetime.utcnow()
    today = now.date()
    sent = 0
    candidates = Task.query.filter(
        Task.deadline.isnot(None),
        Task.reminder_offset_days.isnot(None),
        Task.reminder_sent_at.is_(None),
        Task.status.notin_(['done', 'cancelled']),
    ).all()
    for task in candidates:
        trigger = _trigger_date(task)
        if trigger is None or trigger > today:
            continue
        body = (
            f'الموعد: {task.deadline.strftime("%Y-%m-%d %H:%M")} — '
            f'تبقّى {task.reminder_offset_days} يوم'
        )
        create_notification(
            tenant_id=task.tenant_id,
            user_id=task.assigned_to,
            notification_type='task_reminder',
            title=f'تذكير: {task.title}',
            body=body,
            priority='important' if task.priority == 'urgent' else 'info',
            related_type='task',
            related_id=task.id,
        )
        task.reminder_sent_at = now
        sent += 1

    if sent:
        db.session.commit()
    return sent


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        n = dispatch_reminders()
        print(f'task reminders dispatched: {n}')
