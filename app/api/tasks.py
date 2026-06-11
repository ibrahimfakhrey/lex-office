"""API routes for Task management."""
from datetime import datetime
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_datetime)
from app.extensions import db
from flask import g, request
from app.models.task import Task
from app.models.case import Case
from app.models.user import User

VALID_STATUSES = {'new', 'in_progress', 'done', 'cancelled'}
STATUS_LABELS = {'new': 'جديدة', 'in_progress': 'قيد التنفيذ', 'done': 'مكتملة', 'cancelled': 'ملغاة'}


# ===================== TASKS LIST =====================

@api_bp.route('/tasks', methods=['GET'])
@api_permission_required('tasks', 'view')
def api_list_tasks():
    """List tasks with filters."""
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    assigned_to = request.args.get('assigned_to', '', type=str)
    view = request.args.get('view', 'all')

    query = Task.query.filter_by(tenant_id=g.tenant_id)

    # Non-managers only see tasks assigned to or created by them
    if not (g.current_user.is_manager or g.current_user.is_partner):
        query = query.filter(
            db.or_(
                Task.assigned_to == g.current_user.id,
                Task.assigned_by == g.current_user.id,
            )
        )

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if assigned_to:
        query = query.filter_by(assigned_to=int(assigned_to))
    if view == 'mine':
        query = query.filter_by(assigned_to=g.current_user.id)
    elif view == 'overdue':
        query = query.filter(Task.deadline < datetime.utcnow(), Task.status.notin_(['done', 'cancelled']))

    query = query.order_by(Task.deadline.asc().nullslast())
    return paginated_response(query)


# ===================== CREATE TASK =====================

@api_bp.route('/tasks', methods=['POST'])
@api_permission_required('tasks', 'create')
def api_create_task():
    """Create a new task."""
    data = get_json_or_form()
    errors = {}

    title = (data.get('title') or '').strip()
    assigned_to = data.get('assigned_to')

    if not title:
        errors['title'] = 'عنوان المهمة مطلوب'
    if not assigned_to:
        errors['assigned_to'] = 'يجب تعيين المهمة لشخص'

    if errors:
        return validation_error(errors)

    deadline = None
    if data.get('deadline'):
        deadline = parse_datetime(data['deadline'])

    # ALMUSTSHAR-19: optional reminder-before-deadline window.
    # Accept only the 4 documented values; ignore anything else.
    reminder_before_days = None
    try:
        rb = int(data.get('reminder_before_days')) if data.get('reminder_before_days') else None
        if rb in (1, 2, 3, 7):
            reminder_before_days = rb
    except (ValueError, TypeError):
        pass

    task = Task(
        tenant_id=g.tenant_id,
        title=title,
        description=(data.get('description') or '').strip() or None,
        assigned_to=int(assigned_to),
        assigned_by=g.current_user.id,
        case_id=int(data['case_id']) if data.get('case_id') else None,
        priority=data.get('priority', 'normal'),
        deadline=deadline,
        reminder_before_days=reminder_before_days,
    )
    db.session.add(task)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='task_assigned',
        title=f'تم إنشاء مهمة جديدة: {task.title}',
        body=f'الأولوية: {task.priority} — الموعد: {task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else "غير محدد"}',
        priority='important' if task.priority == 'urgent' else 'info',
        related_type='task',
        related_id=task.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=task.to_dict(), message='تم إنشاء المهمة بنجاح', status_code=201)


# ===================== SHOW TASK =====================

@api_bp.route('/tasks/<int:id>', methods=['GET'])
@api_permission_required('tasks', 'view')
def api_show_task(id):
    """Show task details."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return success_response(data=task.to_dict())


# ===================== UPDATE TASK =====================

@api_bp.route('/tasks/<int:id>', methods=['PUT'])
@api_permission_required('tasks', 'edit')
def api_update_task(id):
    """Update a task."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    data = get_json_or_form()

    if data.get('title'):
        task.title = data['title'].strip()
    if 'description' in data:
        task.description = (data.get('description') or '').strip() or None
    if data.get('assigned_to'):
        task.assigned_to = int(data['assigned_to'])
    if 'case_id' in data:
        task.case_id = int(data['case_id']) if data['case_id'] else None
    if data.get('priority'):
        task.priority = data['priority']

    prev_deadline = task.deadline
    if data.get('deadline'):
        task.deadline = parse_datetime(data['deadline'])
    elif data.get('clear_deadline'):
        task.deadline = None

    # ALMUSTSHAR-19: keep the reminder window editable via API.
    prev_reminder = task.reminder_before_days
    if 'reminder_before_days' in data:
        raw = data.get('reminder_before_days')
        new_reminder = None
        if raw not in (None, '', 'none', '0', 0):
            try:
                rb = int(raw)
                if rb in (1, 2, 3, 7):
                    new_reminder = rb
            except (ValueError, TypeError):
                pass
        task.reminder_before_days = new_reminder

    # If deadline shifted OR the window changed, clear reminder_sent_at
    # so the dispatcher fires once for the new schedule.
    if task.deadline != prev_deadline or task.reminder_before_days != prev_reminder:
        task.reminder_sent_at = None

    db.session.commit()

    return success_response(data=task.to_dict(), message='تم تحديث المهمة بنجاح')


# ===================== UPDATE TASK STATUS =====================

@api_bp.route('/tasks/<int:id>/status', methods=['PATCH'])
@api_permission_required('tasks', 'edit')
def api_update_task_status(id):
    """Quick status update for a task."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    data = get_json_or_form()
    new_status = data.get('status', '')

    if new_status not in VALID_STATUSES:
        return error_response('حالة غير صالحة', error_code='invalid_status')

    task.status = new_status
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم تحديث حالة المهمة: {task.title}',
        body=f'الحالة الجديدة: {STATUS_LABELS.get(new_status, new_status)}',
        related_type='task',
        related_id=task.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=task.to_dict(), message='تم تحديث حالة المهمة')


# ===================== DELETE TASK =====================

@api_bp.route('/tasks/<int:id>', methods=['DELETE'])
@api_permission_required('tasks', 'delete')
def api_delete_task(id):
    """Delete a task."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return success_response(message='تم حذف المهمة')
