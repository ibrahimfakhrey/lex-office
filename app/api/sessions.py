"""API routes for court session management."""
from datetime import timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_time)
from app.extensions import db
from flask import g, request

from app.models.session import Session
from app.models.case import Case
from app.utils.helpers import egypt_today

SESSION_TYPES = [
    ('first', 'أولى'), ('evidence', 'إثبات'), ('pleading', 'مرافعة'),
    ('judgment', 'حكم'), ('emergency', 'طارئة'), ('postponement', 'تأجيل'),
]


@api_bp.route('/sessions', methods=['GET'])
@api_permission_required('sessions', 'view')
def api_sessions_list():
    """List sessions with filters and pagination."""
    filter_date = request.args.get('date', '').strip()
    status = request.args.get('status', '').strip()
    case_id = request.args.get('case_id', '').strip()

    query = Session.query.filter_by(tenant_id=g.tenant_id)

    if filter_date:
        parsed = parse_date(filter_date)
        if parsed:
            query = query.filter(Session.session_date == parsed)
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

    query = query.order_by(Session.session_date.desc())
    return paginated_response(query)


@api_bp.route('/sessions', methods=['POST'])
@api_permission_required('sessions', 'create')
def api_sessions_create():
    """Create a new court session."""
    data = get_json_or_form()
    errors = {}

    case_id = data.get('case_id')
    if case_id is not None:
        try:
            case_id = int(case_id)
        except (ValueError, TypeError):
            case_id = None
    if not case_id:
        errors['case_id'] = 'يجب اختيار القضية'

    session_date_str = (data.get('session_date') or '').strip()
    session_date = parse_date(session_date_str)
    if not session_date:
        errors['session_date'] = 'تاريخ الجلسة مطلوب'

    if errors:
        return validation_error(errors)

    session_time = parse_time((data.get('session_time') or '').strip())

    responsible_lawyer_id = data.get('responsible_lawyer_id')
    if responsible_lawyer_id:
        try:
            responsible_lawyer_id = int(responsible_lawyer_id)
        except (ValueError, TypeError):
            responsible_lawyer_id = g.current_user.id
    else:
        responsible_lawyer_id = g.current_user.id

    sess = Session(
        tenant_id=g.tenant_id,
        case_id=case_id,
        session_date=session_date,
        session_time=session_time,
        court_id=int(data['court_id']) if data.get('court_id') else None,
        circuit=(data.get('circuit') or '').strip() or None,
        session_type=(data.get('session_type') or '').strip() or None,
        preparation_notes=(data.get('preparation_notes') or '').strip() or None,
        responsible_lawyer_id=responsible_lawyer_id,
    )
    db.session.add(sess)
    db.session.commit()

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

    return success_response(data=sess.to_dict(), message='تم إضافة الجلسة بنجاح', status_code=201)


@api_bp.route('/sessions/<int:id>', methods=['GET'])
@api_permission_required('sessions', 'view')
def api_sessions_show(id):
    """Show session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not sess:
        return error_response('الجلسة غير موجودة', error_code='not_found', status_code=404)

    return success_response(data=sess.to_dict())


@api_bp.route('/sessions/<int:id>', methods=['PUT'])
@api_permission_required('sessions', 'edit')
def api_sessions_update(id):
    """Update session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not sess:
        return error_response('الجلسة غير موجودة', error_code='not_found', status_code=404)

    data = get_json_or_form()

    if 'session_date' in data:
        parsed = parse_date((data['session_date'] or '').strip())
        if parsed:
            sess.session_date = parsed
    if 'session_time' in data:
        sess.session_time = parse_time((data['session_time'] or '').strip())
    if 'court_id' in data:
        sess.court_id = int(data['court_id']) if data['court_id'] else None
    if 'circuit' in data:
        sess.circuit = (data['circuit'] or '').strip() or None
    if 'session_type' in data:
        sess.session_type = (data['session_type'] or '').strip() or None
    if 'preparation_notes' in data:
        sess.preparation_notes = (data['preparation_notes'] or '').strip() or None
    if 'responsible_lawyer_id' in data:
        try:
            sess.responsible_lawyer_id = int(data['responsible_lawyer_id']) if data['responsible_lawyer_id'] else sess.responsible_lawyer_id
        except (ValueError, TypeError):
            pass

    from app.services.tasks_service import sync_session_reminder_task
    sync_session_reminder_task(sess)
    db.session.commit()
    return success_response(data=sess.to_dict(), message='تم تحديث الجلسة بنجاح')


@api_bp.route('/sessions/<int:id>', methods=['DELETE'])
@api_permission_required('sessions', 'delete')
def api_sessions_delete(id):
    """Delete a session."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not sess:
        return error_response('الجلسة غير موجودة', error_code='not_found', status_code=404)

    case_id = sess.case_id
    db.session.delete(sess)
    db.session.commit()
    return success_response(data={'case_id': case_id}, message='تم حذف الجلسة')


@api_bp.route('/sessions/<int:id>/result', methods=['POST'])
@api_permission_required('sessions', 'edit')
def api_sessions_record_result(id):
    """Record session result and optionally schedule next session."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not sess:
        return error_response('الجلسة غير موجودة', error_code='not_found', status_code=404)

    data = get_json_or_form()

    sess.result = (data.get('result') or '').strip() or None
    sess.result_summary = (data.get('result_summary') or '').strip() or None

    next_session_date_str = (data.get('next_session_date') or '').strip()
    next_session_date = parse_date(next_session_date_str)
    if next_session_date:
        sess.next_session_date = next_session_date

        # Auto-create next session if requested
        create_next = data.get('create_next')
        if create_next in (True, 'true', 'yes', '1', 1):
            next_sess = Session(
                tenant_id=g.tenant_id,
                case_id=sess.case_id,
                session_date=next_session_date,
                court_id=sess.court_id,
                circuit=sess.circuit,
                responsible_lawyer_id=sess.responsible_lawyer_id,
            )
            db.session.add(next_sess)
            db.session.flush()
            from app.services.tasks_service import create_session_reminder_task
            create_session_reminder_task(next_sess, g.current_user.id)

    # When result is judgment, update case status
    redirect_to_judgment = False
    if sess.result == 'judgment':
        case = Case.query.get(sess.case_id)
        if case and case.status not in ('closed',):
            case.status = 'awaiting_judgment'
        redirect_to_judgment = True

    # Mark this session's reminder task as done.
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

    result = sess.to_dict()
    result['redirect_to_judgment'] = redirect_to_judgment
    return success_response(data=result, message='تم تسجيل نتيجة الجلسة بنجاح')


@api_bp.route('/sessions/calendar', methods=['GET'])
@api_permission_required('sessions', 'view')
def api_sessions_calendar():
    """Return calendar events for sessions."""
    sessions = Session.query.filter_by(tenant_id=g.tenant_id).filter(
        Session.session_date >= egypt_today() - timedelta(days=30)
    ).order_by(Session.session_date).all()

    type_map = dict(SESSION_TYPES)
    events = []
    for s in sessions:
        events.append({
            'id': s.id,
            'title': f'{s.case.case_number or "قضية"} - {type_map.get(s.session_type, "")}',
            'date': s.session_date.isoformat(),
            'time': s.session_time.strftime('%H:%M') if s.session_time else None,
            'status': 'completed' if s.result else 'pending',
            'case_id': s.case_id,
        })

    return success_response(data=events)
