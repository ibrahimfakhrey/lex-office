"""API routes for case management."""
from datetime import datetime
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_time)
from app.extensions import db
from flask import g, request

from app.models.case import Case, Court
from app.models.client import Client
from app.models.user import User


@api_bp.route('/cases', methods=['GET'])
@api_permission_required('cases', 'view')
def api_cases_list():
    """List cases with search, filters, and pagination."""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    case_type = request.args.get('type', '').strip()
    priority = request.args.get('priority', '').strip()
    lawyer_id = request.args.get('lawyer_id', '').strip()
    client_id = request.args.get('client_id', '').strip()

    query = Case.query.filter_by(tenant_id=g.tenant_id)

    if search:
        query = query.filter(
            db.or_(
                Case.case_number.ilike(f'%{search}%'),
                Case.subject.ilike(f'%{search}%'),
                Case.opponent_name.ilike(f'%{search}%'),
            )
        )
    if status:
        query = query.filter_by(status=status)
    if case_type:
        query = query.filter_by(case_type=case_type)
    if priority:
        query = query.filter_by(priority=priority)
    if lawyer_id:
        query = query.filter_by(responsible_lawyer_id=int(lawyer_id))
    if client_id:
        try:
            query = query.filter_by(client_id=int(client_id))
        except (ValueError, TypeError):
            pass

    query = query.order_by(Case.created_at.desc())
    return paginated_response(query)


@api_bp.route('/cases', methods=['POST'])
@api_permission_required('cases', 'create')
def api_cases_create():
    """Create a new case."""
    data = get_json_or_form()
    errors = {}

    client_id = data.get('client_id')
    if client_id is not None:
        try:
            client_id = int(client_id)
        except (ValueError, TypeError):
            client_id = None
    if not client_id:
        errors['client_id'] = 'يجب اختيار الموكل'

    case_type = (data.get('case_type') or '').strip()
    if not case_type:
        errors['case_type'] = 'يجب اختيار نوع القضية'

    responsible_lawyer_id = data.get('responsible_lawyer_id')
    if responsible_lawyer_id is not None:
        try:
            responsible_lawyer_id = int(responsible_lawyer_id)
        except (ValueError, TypeError):
            responsible_lawyer_id = None
    if not responsible_lawyer_id:
        errors['responsible_lawyer_id'] = 'يجب اختيار المحامي المسؤول'

    if errors:
        return validation_error(errors)

    retainer_amount = 0
    try:
        retainer_amount = float(data.get('retainer_paid') or 0)
    except (ValueError, TypeError):
        retainer_amount = 0

    assistant_lawyer_id = data.get('assistant_lawyer_id')
    if assistant_lawyer_id:
        try:
            assistant_lawyer_id = int(assistant_lawyer_id)
        except (ValueError, TypeError):
            assistant_lawyer_id = None

    case = Case(
        tenant_id=g.tenant_id,
        client_id=client_id,
        case_number=(data.get('case_number') or '').strip() or None,
        judicial_year=(data.get('judicial_year') or '').strip() or None,
        court_id=int(data['court_id']) if data.get('court_id') else None,
        circuit=(data.get('circuit') or '').strip() or None,
        case_type=case_type,
        subject=(data.get('subject') or '').strip() or None,
        opponent_name=(data.get('opponent_name') or '').strip() or None,
        opponent_capacity=(data.get('opponent_capacity') or '').strip() or None,
        opponent_lawyer=(data.get('opponent_lawyer') or '').strip() or None,
        responsible_lawyer_id=responsible_lawyer_id,
        assistant_lawyer_id=assistant_lawyer_id,
        our_client_capacity=(data.get('our_client_capacity') or '').strip() or None,
        fee_type=(data.get('fee_type') or '').strip() or None,
        fee_amount=float(data['fee_amount']) if data.get('fee_amount') else None,
        retainer_paid=retainer_amount,
        payment_schedule=(data.get('payment_schedule') or '').strip() or None,
        priority=data.get('priority', 'normal'),
        internal_notes=(data.get('internal_notes') or '').strip() or None,
    )
    db.session.add(case)
    db.session.flush()

    # Create Payment record for retainer if paid upfront
    if retainer_amount > 0:
        from app.models.financial import Payment
        from app.utils.helpers import egypt_today
        initial_payment = Payment(
            tenant_id=g.tenant_id,
            client_id=client_id,
            case_id=case.id,
            amount=retainer_amount,
            payment_date=egypt_today(),
            payment_method='cash',
            notes='مقدم أتعاب عند فتح القضية',
            recorded_by=g.current_user.id,
        )
        db.session.add(initial_payment)

    db.session.commit()

    from app.services.notification_service import notify_tenant_users, create_notification
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='case_update',
        title=f'تم إضافة قضية جديدة: {case.case_number or case.subject or "قضية جديدة"}',
        body=f'الموكل: {case.client.full_name if case.client else "-"}',
        priority='important',
        related_type='case',
        related_id=case.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    # Notify assistant lawyer specifically if different
    if assistant_lawyer_id and assistant_lawyer_id != g.current_user.id:
        create_notification(
            tenant_id=g.tenant_id,
            user_id=assistant_lawyer_id,
            notification_type='case_update',
            title=f'تم تعيينك محامي مساعد لقضية: {case.case_number or "قضية جديدة"}',
            related_type='case',
            related_id=case.id,
            actor_name=g.current_user.full_name,
        )
    db.session.commit()

    return success_response(data=case.to_dict(), message='تم إضافة القضية بنجاح', status_code=201)


@api_bp.route('/cases/<int:id>', methods=['GET'])
@api_permission_required('cases', 'view')
def api_cases_show(id):
    """Show case details with all related data."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not case:
        return error_response('القضية غير موجودة', error_code='not_found', status_code=404)

    result = case.to_dict(include_related=True)
    result['sessions'] = [s.to_dict() for s in case.sessions.all()]
    result['judgments'] = [j.to_dict() for j in case.judgments.all()]
    result['payments'] = [p.to_dict() for p in case.case_payments.all()]
    result['expenses'] = [e.to_dict() for e in case.expenses.all()]
    result['documents'] = [d.to_dict() for d in case.case_documents.all()]
    result['tasks'] = [t.to_dict() for t in case.tasks.all()]
    return success_response(data=result)


@api_bp.route('/cases/<int:id>', methods=['PUT'])
@api_permission_required('cases', 'edit')
def api_cases_update(id):
    """Update case details."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not case:
        return error_response('القضية غير موجودة', error_code='not_found', status_code=404)

    data = get_json_or_form()

    if 'case_number' in data:
        case.case_number = (data['case_number'] or '').strip() or None
    if 'judicial_year' in data:
        case.judicial_year = (data['judicial_year'] or '').strip() or None
    if 'court_id' in data:
        case.court_id = int(data['court_id']) if data['court_id'] else None
    if 'circuit' in data:
        case.circuit = (data['circuit'] or '').strip() or None
    if 'case_type' in data:
        case.case_type = data['case_type'] or case.case_type
    if 'subject' in data:
        case.subject = (data['subject'] or '').strip() or None
    if 'opponent_name' in data:
        case.opponent_name = (data['opponent_name'] or '').strip() or None
    if 'opponent_capacity' in data:
        case.opponent_capacity = (data['opponent_capacity'] or '').strip() or None
    if 'opponent_lawyer' in data:
        case.opponent_lawyer = (data['opponent_lawyer'] or '').strip() or None
    if 'responsible_lawyer_id' in data:
        case.responsible_lawyer_id = int(data['responsible_lawyer_id']) if data['responsible_lawyer_id'] else case.responsible_lawyer_id
    if 'assistant_lawyer_id' in data:
        case.assistant_lawyer_id = int(data['assistant_lawyer_id']) if data['assistant_lawyer_id'] else None
    if 'our_client_capacity' in data:
        case.our_client_capacity = (data['our_client_capacity'] or '').strip() or None
    if 'fee_type' in data:
        case.fee_type = (data['fee_type'] or '').strip() or None
    if 'fee_amount' in data:
        case.fee_amount = float(data['fee_amount']) if data['fee_amount'] else None
    if 'retainer_paid' in data:
        try:
            case.retainer_paid = float(data['retainer_paid']) if data['retainer_paid'] else 0
        except (ValueError, TypeError):
            case.retainer_paid = 0
    if 'payment_schedule' in data:
        case.payment_schedule = (data['payment_schedule'] or '').strip() or None
    if 'priority' in data:
        case.priority = data['priority'] or 'normal'
    if 'status' in data:
        case.status = data['status'] or case.status
    if 'internal_notes' in data:
        case.internal_notes = (data['internal_notes'] or '').strip() or None

    # If status changed to closed, set closed_at
    if case.status == 'closed' and not case.closed_at:
        case.closed_at = datetime.utcnow()

    db.session.commit()
    return success_response(data=case.to_dict(), message='تم تحديث القضية بنجاح')


@api_bp.route('/cases/<int:id>', methods=['DELETE'])
@api_permission_required('cases', 'delete')
def api_cases_delete(id):
    """Delete a case (hard delete)."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not case:
        return error_response('القضية غير موجودة', error_code='not_found', status_code=404)

    db.session.delete(case)
    db.session.commit()
    return success_response(message='تم حذف القضية')


@api_bp.route('/cases/<int:id>/close', methods=['POST'])
@api_permission_required('cases', 'edit')
def api_cases_close(id):
    """Close a case."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not case:
        return error_response('القضية غير موجودة', error_code='not_found', status_code=404)

    case.status = 'closed'
    case.closed_at = datetime.utcnow()
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='case_update',
        title=f'تم إغلاق القضية: {case.case_number or "قضية"}',
        related_type='case',
        related_id=case.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=case.to_dict(), message='تم إغلاق القضية')


@api_bp.route('/cases/by-client/<int:client_id>', methods=['GET'])
@api_permission_required('cases', 'view')
def api_cases_by_client(client_id):
    """Return list of cases for a given client (for dropdown use)."""
    cases = Case.query.filter_by(
        tenant_id=g.tenant_id, client_id=client_id
    ).order_by(Case.case_number).all()

    result = [{
        'id': c.id,
        'label': f"{c.case_number or '-'} — {(c.subject or '')[:40]}",
        'client_id': c.client_id,
    } for c in cases]

    return success_response(data=result)
