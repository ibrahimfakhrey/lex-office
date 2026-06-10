"""Task helpers — currently: auto-issue a reminder Task for every new Session.

ALMUSTSHAR-22: every time a court session is created we want a reminder task
sitting next to it in /tasks and on the dashboard, scoped to the same case
and assigned to the responsible lawyer. The task's deadline is the session
moment itself (date + time), so the dashboard's "overdue / urgent" filter
picks it up on the day of the session.
"""
from datetime import datetime, time as dtime

from app.extensions import db
from app.models.task import Task


def create_session_reminder_task(session, created_by_user_id):
    """Create and add a reminder Task for `session`. Caller commits.

    Returns the Task instance (added but not yet flushed). Safe to call
    repeatedly only if the caller wants duplicates — there's no de-dup
    on session_id since Task has no FK back to Session.
    """
    case = session.case
    case_label = (case.case_number if case and case.case_number else 'قضية')
    title = f'تذكير: جلسة {case_label} — {session.session_date.strftime("%Y-%m-%d")}'

    # Deadline = session date + session time (default 09:00 if no time given).
    sess_time = session.session_time or dtime(9, 0)
    deadline = datetime.combine(session.session_date, sess_time)

    assignee_id = session.responsible_lawyer_id or created_by_user_id

    task = Task(
        tenant_id=session.tenant_id,
        title=title,
        description='تم إنشاء هذه المهمة تلقائياً عند إنشاء الجلسة.',
        assigned_to=assignee_id,
        assigned_by=created_by_user_id,
        case_id=session.case_id,
        priority='important',
        deadline=deadline,
        status='new',
    )
    db.session.add(task)
    return task
