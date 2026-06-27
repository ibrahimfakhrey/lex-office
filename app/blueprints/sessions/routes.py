"""Court session management routes."""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.utils.helpers import egypt_today
from app.models.session import Session
from app.models.case import Case, Court
from app.models.user import User

# Session-reminder Task lifecycle lives in app.services.tasks_service —
# create_session_reminder_task / sync_session_reminder_task /
# complete_session_reminder_task. The local _sync_session_task helper
# that used to be here was removed because it ran alongside the service
# in `create()`, producing two reminder tasks per session.

sessions_bp = Blueprint('sessions', __name__, template_folder='../../templates/sessions')

SESSION_TYPES = [
    ('first', 'أولى'), ('evidence', 'إثبات'), ('pleading', 'مرافعة'),
    ('judgment', 'حكم'), ('emergency', 'طارئة'), ('postponement', 'تأجيل'),
]
SESSION_RESULTS = [
    ('postponed', 'تأجيل'), ('judgment', 'حكم'), ('decision', 'قرار'),
    ('evidence', 'إثبات'), ('attendance', 'حضور'), ('absence', 'غياب'),
]


@sessions_bp.route('/')
@permission_required('sessions', 'view')
def index():
    """List all sessions with filters."""
    page = request.args.get('page', 1, type=int)
    filter_date = request.args.get('date', '')
    status = request.args.get('status', '')
    case_id = request.args.get('case_id', '', type=str)

    query = Session.query.filter_by(tenant_id=g.tenant_id)
    if filter_date:
        query = query.filter(Session.session_date == filter_date)
    if status == 'pending':
        query = query.filter(Session.result.is_(None))
    elif status == 'completed':
        query = query.filter(Session.result.isnot(None))
    elif status == 'today':
        query = query.filter(Session.session_date == egypt_today())
    elif status == 'upcoming':
        query = query.filter(Session.session_date > egypt_today())
    if case_id:
        query = query.filter_by(case_id=int(case_id))

    sessions = query.order_by(Session.session_date.desc()).paginate(page=page, per_page=20)
    return render_template('sessions/index.html', sessions=sessions, filter_date=filter_date,
                           status=status, case_id=case_id, session_results=SESSION_RESULTS,
                           today=egypt_today())


@sessions_bp.route('/create', methods=['GET', 'POST'])
@permission_required('sessions', 'create')
def create():
    """Create a new court session."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active', 'awaiting_judgment'])
    ).order_by(Case.case_number).all()
    from app.utils.market import current_market
    courts = Court.query.filter_by(is_active=True, market=current_market()).order_by(Court.name).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    if request.method == 'POST':
        errors = []
        case_id = request.form.get('case_id', type=int)
        session_date = request.form.get('session_date', '')

        if not case_id:
            errors.append('يجب اختيار القضية')
        if not session_date:
            errors.append('تاريخ الجلسة مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('sessions/create.html', cases=cases, courts=courts,
                                   lawyers=lawyers, form=request.form,
                                   session_types=SESSION_TYPES)

        session_time = None
        if request.form.get('session_time'):
            session_time = datetime.strptime(request.form['session_time'], '%H:%M').time()

        sess = Session(
            tenant_id=g.tenant_id,
            case_id=case_id,
            session_date=datetime.strptime(session_date, '%Y-%m-%d').date(),
            session_time=session_time,
            court_id=request.form.get('court_id', type=int) or None,
            circuit=request.form.get('circuit', '').strip() or None,
            session_type=request.form.get('session_type', '') or None,
            preparation_notes=request.form.get('preparation_notes', '').strip() or None,
            responsible_lawyer_id=request.form.get('responsible_lawyer_id', type=int) or g.current_user.id,
        )
        db.session.add(sess)
        db.session.flush()

        from app.services.tasks_service import create_session_reminder_task
        create_session_reminder_task(sess, g.current_user.id)
        db.session.commit()

        from app.services.notification_service import notify_tenant_users
        notify_tenant_users(
            tenant_id=g.tenant_id,
            notification_type='session_reminder',
            title=f'تم إضافة جلسة جديدة بتاريخ {sess.session_date.strftime("%Y-%m-%d")}',
            body=f'القضية: {sess.case.case_number if sess.case else "-"}',
            priority='important',
            related_type='session',
            related_id=sess.id,
            actor_name=g.current_user.full_name,
            exclude_user_id=g.current_user.id,
        )
        db.session.commit()

        flash('تم إضافة الجلسة بنجاح وتم إنشاء مهمة تذكيرية تلقائياً', 'success')
        return redirect(url_for('sessions.show', id=sess.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('sessions/create.html', cases=cases, courts=courts,
                           lawyers=lawyers, form=request.args, session_types=SESSION_TYPES,
                           pre_case_id=pre_case)


@sessions_bp.route('/<int:id>')
@permission_required('sessions', 'view')
def show(id):
    """Show session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    result_map = dict(SESSION_RESULTS)
    type_map = dict(SESSION_TYPES)
    return render_template('sessions/show.html', session=sess, result_map=result_map, type_map=type_map)


@sessions_bp.route('/<int:id>/record-result', methods=['GET', 'POST'])
@permission_required('sessions', 'edit')
def record_result(id):
    """Record session result and optionally schedule next session."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    if request.method == 'POST':
        sess.result = request.form.get('result', '')
        sess.result_summary = request.form.get('result_summary', '').strip() or None

        next_date = request.form.get('next_session_date', '')
        if next_date:
            sess.next_session_date = datetime.strptime(next_date, '%Y-%m-%d').date()

            # Auto-create next session
            if request.form.get('create_next') == 'yes':
                next_sess = Session(
                    tenant_id=g.tenant_id,
                    case_id=sess.case_id,
                    session_date=sess.next_session_date,
                    court_id=sess.court_id,
                    circuit=sess.circuit,
                    responsible_lawyer_id=sess.responsible_lawyer_id,
                )
                db.session.add(next_sess)
                db.session.flush()
                from app.services.tasks_service import create_session_reminder_task
                create_session_reminder_task(next_sess, g.current_user.id)

        # When result is judgment, update case status and redirect to record the judgment
        if sess.result == 'judgment':
            case = Case.query.get(sess.case_id)
            if case and case.status not in ('closed',):
                case.status = 'awaiting_judgment'

        # Mark this session's reminder task as done — the session has now
        # been held, so the reminder is no longer outstanding.
        if sess.result:
            from app.services.tasks_service import complete_session_reminder_task
            complete_session_reminder_task(sess)

        db.session.commit()

        from app.services.notification_service import notify_tenant_users
        notify_tenant_users(
            tenant_id=g.tenant_id,
            notification_type='case_update',
            title=f'تم تسجيل نتيجة جلسة: {sess.result or "-"}',
            body=f'القضية: {sess.case.case_number if sess.case else "-"} - التاريخ: {sess.session_date.strftime("%Y-%m-%d")}',
            related_type='session',
            related_id=sess.id,
            actor_name=g.current_user.full_name,
            exclude_user_id=g.current_user.id,
        )
        db.session.commit()

        flash('تم تسجيل نتيجة الجلسة بنجاح', 'success')

        if sess.result == 'judgment':
            flash('يرجى تسجيل بيانات الحكم', 'info')
            return redirect(url_for('judgments.create', case_id=sess.case_id))

        return redirect(url_for('sessions.show', id=sess.id))

    return render_template('sessions/record_result.html', session=sess, session_results=SESSION_RESULTS)


@sessions_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('sessions', 'edit')
def edit(id):
    """Edit session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    from app.utils.market import current_market
    courts = Court.query.filter_by(is_active=True, market=current_market()).order_by(Court.name).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    if request.method == 'POST':
        sess.session_date = datetime.strptime(request.form['session_date'], '%Y-%m-%d').date()
        if request.form.get('session_time'):
            sess.session_time = datetime.strptime(request.form['session_time'], '%H:%M').time()
        sess.court_id = request.form.get('court_id', type=int) or None
        sess.circuit = request.form.get('circuit', '').strip() or None
        sess.session_type = request.form.get('session_type', '') or None
        sess.preparation_notes = request.form.get('preparation_notes', '').strip() or None
        sess.responsible_lawyer_id = request.form.get('responsible_lawyer_id', type=int) or sess.responsible_lawyer_id

        from app.services.tasks_service import sync_session_reminder_task
        sync_session_reminder_task(sess)
        db.session.commit()
        flash('تم تحديث الجلسة بنجاح', 'success')
        return redirect(url_for('sessions.show', id=sess.id))

    return render_template('sessions/edit.html', session=sess, courts=courts,
                           lawyers=lawyers, session_types=SESSION_TYPES)


@sessions_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('sessions', 'delete')
def delete(id):
    """Delete a session. Notifies the tenant team."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    case_id = sess.case_id
    case_number = sess.case.case_number if sess.case else None
    session_date = sess.session_date.strftime('%Y-%m-%d') if sess.session_date else ''
    db.session.delete(sess)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم حذف جلسة بتاريخ {session_date}'.strip(),
        body=f'القضية: {case_number}' if case_number else None,
        priority='important',
        related_type='case',
        related_id=case_id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    flash('تم حذف الجلسة', 'warning')
    return redirect(url_for('cases.show', id=case_id))


@sessions_bp.route('/calendar')
@permission_required('sessions', 'view')
def calendar():
    """Calendar view of sessions."""
    sessions = Session.query.filter_by(tenant_id=g.tenant_id).filter(
        Session.session_date >= egypt_today() - timedelta(days=30)
    ).order_by(Session.session_date).all()

    events = []
    for s in sessions:
        events.append({
            'id': s.id,
            'title': f'{s.case.case_number or "قضية"} - {dict(SESSION_TYPES).get(s.session_type, "")}',
            'date': s.session_date.isoformat(),
            'time': s.session_time.strftime('%H:%M') if s.session_time else None,
            'status': 'completed' if s.result else 'pending',
            'case_id': s.case_id,
        })
    return render_template('sessions/calendar.html', events=events, sessions=sessions)
