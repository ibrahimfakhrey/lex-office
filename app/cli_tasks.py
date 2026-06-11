"""Flask CLI commands for task reminders.

Wire to system cron (every 15 min is a safe cadence). Example crontab:

    */15 * * * *  cd /path/to/app && FLASK_APP=flask_app.py /path/to/venv/bin/flask send-task-reminders >> /var/log/almustshar/task-reminders.log 2>&1

The dispatcher walks tasks where:
- status != 'done'
- deadline is set
- reminder_before_days is set
- reminder_sent_at IS NULL  (haven't sent yet)
- deadline - reminder_before_days <= now  (we're inside the reminder window)
- deadline > now                          (deadline hasn't passed yet — overdue is a separate concern)

For each match: send an in-app + email notification to the assignee and
stamp reminder_sent_at so the next cron tick skips it.
"""
from datetime import datetime, timedelta

import click

from app.extensions import db
from app.models.task import Task


def register_tasks_cli(app):
    @app.cli.command('send-task-reminders')
    @click.option('--dry-run', is_flag=True, help='Print what would fire; do not send.')
    def send_task_reminders(dry_run):
        """Fire pending reminder notifications for tasks whose deadline is approaching."""
        now = datetime.utcnow()
        candidates = Task.query.filter(
            Task.status != 'done',
            Task.deadline.isnot(None),
            Task.reminder_before_days.isnot(None),
            Task.reminder_sent_at.is_(None),
            Task.deadline > now,
        ).all()

        sent = 0
        skipped = 0
        from app.services.notification_service import create_notification

        for task in candidates:
            window_start = task.deadline - timedelta(days=task.reminder_before_days)
            if now < window_start:
                skipped += 1
                continue

            label_map = {1: 'يوم', 2: 'يومين', 3: '3 أيام', 7: 'أسبوع'}
            window_label = label_map.get(task.reminder_before_days, f'{task.reminder_before_days} يوم')
            click.echo(
                f'[{"DRY" if dry_run else "SEND"}] task={task.id} '
                f'assignee={task.assigned_to} deadline={task.deadline.isoformat()} '
                f'window=قبل {window_label}'
            )
            if dry_run:
                continue

            try:
                create_notification(
                    tenant_id=task.tenant_id,
                    user_id=task.assigned_to,
                    notification_type='task_reminder',
                    title=f'تذكير: مهمة "{task.title}" مستحقة قريباً',
                    body=(
                        f'موعد التسليم: {task.deadline.strftime("%d/%m/%Y %H:%M")} — '
                        f'يتبقى {window_label}.'
                    ),
                    priority='important',
                    related_type='task',
                    related_id=task.id,
                )
                task.reminder_sent_at = datetime.utcnow()
                db.session.commit()
                sent += 1
            except Exception as e:
                db.session.rollback()
                click.echo(f'  ✗ failed to dispatch task={task.id}: {e}', err=True)

        click.echo(f'\nDone. sent={sent} skipped(not-yet-due)={skipped} candidates={len(candidates)}')
