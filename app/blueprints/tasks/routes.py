"""Task management routes."""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.utils.helpers import egypt_today
from app.models.task import Task
from app.models.case import Case
from app.models.user import User
from app.models.client import Client

tasks_bp = Blueprint('tasks', __name__, template_folder='../../templates/tasks')

PRIORITIES = [('urgent', 'عاجل'), ('important', 'مهم'), ('normal', 'عادي')]
STATUSES = [('new', 'جديدة'), ('in_progress', 'قيد التنفيذ'), ('done', 'مكتملة'), ('cancelled', 'ملغاة')]


@tasks_bp.route('/')
@permission_required('tasks', 'view')
def index():
    """List tasks with filters."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    assigned_to = request.args.get('assigned_to', '', type=str)
    view = request.args.get('view', 'all')  # all, mine, overdue

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

    tasks = query.order_by(Task.deadline.asc().nullslast()).paginate(page=page, per_page=20)

    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(User.full_name).all()

    return render_template('tasks/index.html', tasks=tasks, status=status, priority=priority,
                           assigned_to=assigned_to, view=view, priorities=PRIORITIES,
                           statuses=STATUSES, lawyers=lawyers, today=egypt_today())


@tasks_bp.route('/create', methods=['GET', 'POST'])
@permission_required('tasks', 'create')
def create():
    """Create a new task."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active'])
    ).order_by(Case.case_number).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(User.full_name).all()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        errors = []
        title = request.form.get('title', '').strip()
        assigned_to = request.form.get('assigned_to', type=int)

        if not title:
            errors.append('عنوان المهمة مطلوب')
        if not assigned_to:
            errors.append('يجب تعيين المهمة لشخص')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('tasks/create.html', cases=cases, lawyers=lawyers,
                                   clients=clients, form=request.form, priorities=PRIORITIES)

        deadline = None
        if request.form.get('deadline'):
            deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%dT%H:%M')

        task = Task(
            tenant_id=g.tenant_id,
            title=title,
            description=request.form.get('description', '').strip() or None,
            assigned_to=assigned_to,
            assigned_by=g.current_user.id,
            case_id=request.form.get('case_id', type=int) or None,
            priority=request.form.get('priority', 'normal'),
            deadline=deadline,
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

        flash('تم إنشاء المهمة بنجاح', 'success')
        return redirect(url_for('tasks.show', id=task.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('tasks/create.html', cases=cases, lawyers=lawyers,
                           clients=clients, form=request.args, priorities=PRIORITIES, pre_case_id=pre_case)


@tasks_bp.route('/<int:id>')
@permission_required('tasks', 'view')
def show(id):
    """Show task details."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    priority_map = dict(PRIORITIES)
    status_map = dict(STATUSES)
    return render_template('tasks/show.html', task=task, priority_map=priority_map,
                           status_map=status_map, statuses=STATUSES)


@tasks_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('tasks', 'edit')
def edit(id):
    """Edit a task."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active'])
    ).order_by(Case.case_number).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(User.full_name).all()

    if request.method == 'POST':
        task.title = request.form.get('title', task.title).strip()
        task.description = request.form.get('description', '').strip() or None
        task.assigned_to = request.form.get('assigned_to', type=int) or task.assigned_to
        task.case_id = request.form.get('case_id', type=int) or None
        task.priority = request.form.get('priority', task.priority)

        if request.form.get('deadline'):
            task.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%dT%H:%M')
        elif request.form.get('clear_deadline'):
            task.deadline = None

        db.session.commit()
        flash('تم تحديث المهمة بنجاح', 'success')
        return redirect(url_for('tasks.show', id=task.id))

    return render_template('tasks/edit.html', task=task, cases=cases, lawyers=lawyers,
                           priorities=PRIORITIES)


@tasks_bp.route('/<int:id>/update-status', methods=['POST'])
@permission_required('tasks', 'edit')
def update_status(id):
    """Quick status update."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    new_status = request.form.get('status', '')
    valid_statuses = dict(STATUSES)

    if new_status in valid_statuses:
        task.status = new_status
        db.session.commit()

        from app.services.notification_service import notify_tenant_users
        notify_tenant_users(
            tenant_id=g.tenant_id,
            notification_type='general',
            title=f'تم تحديث حالة المهمة: {task.title}',
            body=f'الحالة الجديدة: {valid_statuses[new_status]}',
            related_type='task',
            related_id=task.id,
            actor_name=g.current_user.full_name,
            exclude_user_id=g.current_user.id,
        )
        db.session.commit()

        flash('تم تحديث حالة المهمة', 'success')
    else:
        flash('حالة غير صالحة', 'danger')

    return redirect(request.referrer or url_for('tasks.show', id=task.id))


@tasks_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('tasks', 'delete')
def delete(id):
    """Delete a task."""
    task = Task.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash('تم حذف المهمة', 'warning')
    return redirect(url_for('tasks.index'))
