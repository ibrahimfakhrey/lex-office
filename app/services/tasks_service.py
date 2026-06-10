"""Session-reminder Task lifecycle helpers.

ALMUSTSHAR-22 — every court session gets a reminder Task pinned to it via
`Task.session_id` (CASCADE FK). The session is the source of truth: when
it's edited the linked reminder is re-synced; when it's deleted the FK
cascade drops the reminder; when its result is recorded the reminder is
marked done.

All four helpers are no-op safe: if no linked reminder exists they just
return None / do nothing.
"""
from datetime import datetime, time as dtime

from app.extensions import db
from app.models.task import Task


def _reminder_title(session):
    case = session.case
    case_label = case.case_number if (case and case.case_number) else 'قضية'
    return f'تذكير: جلسة {case_label} — {session.session_date.strftime("%Y-%m-%d")}'


def _reminder_deadline(session):
    """Session moment as a naive datetime. 09:00 fallback when no time."""
    return datetime.combine(session.session_date, session.session_time or dtime(9, 0))


def create_session_reminder_task(session, created_by_user_id):
    """Create and add a reminder Task for `session`. Caller commits."""
    task = Task(
        tenant_id=session.tenant_id,
        title=_reminder_title(session),
        description='تم إنشاء هذه المهمة تلقائياً عند إنشاء الجلسة.',
        assigned_to=session.responsible_lawyer_id or created_by_user_id,
        assigned_by=created_by_user_id,
        case_id=session.case_id,
        session_id=session.id,
        priority='important',
        deadline=_reminder_deadline(session),
        status='new',
    )
    db.session.add(task)
    return task


def sync_session_reminder_task(session):
    """Re-derive title/deadline/assignee on the linked reminder after a
    session edit. No-op if the reminder was already marked done (user
    finished it) or never existed. Caller commits."""
    task = Task.query.filter_by(session_id=session.id).first()
    if task is None or task.status == 'done':
        return None
    task.title = _reminder_title(session)
    task.deadline = _reminder_deadline(session)
    new_assignee = session.responsible_lawyer_id
    if new_assignee and task.assigned_to != new_assignee:
        task.assigned_to = new_assignee
    return task


def complete_session_reminder_task(session):
    """Mark the linked reminder as done when the session result is
    recorded. Skips reminders the user already moved out of `new`
    (e.g. cancelled) or completed by hand."""
    task = Task.query.filter_by(session_id=session.id).first()
    if task is None or task.status == 'done':
        return None
    task.status = 'done'
    return task
