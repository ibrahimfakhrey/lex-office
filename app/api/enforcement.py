"""API routes for Enforcement management."""
from datetime import datetime
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request
from app.models.enforcement import Enforcement, EnforcementCollection, EnforcementAction


# ---------- LIST ----------

@api_bp.route('/enforcement', methods=['GET'])
@api_permission_required('enforcement', 'view')
def api_enforcement_list():
    """List enforcement records with optional status filter."""
    status = request.args.get('status', '')

    query = Enforcement.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)

    query = query.order_by(Enforcement.created_at.desc())
    return paginated_response(query)


# ---------- CREATE ----------

@api_bp.route('/enforcement', methods=['POST'])
@api_permission_required('enforcement', 'create')
def api_enforcement_create():
    """Create a new enforcement record."""
    data = get_json_or_form()
    errors = {}

    case_id = data.get('case_id')
    client_id = data.get('client_id')
    enforcement_type = data.get('enforcement_type', '')
    total_amount = data.get('total_amount')

    if not case_id:
        errors['case_id'] = 'يجب اختيار القضية'
    if not client_id:
        errors['client_id'] = 'يجب اختيار الموكل'
    if not enforcement_type:
        errors['enforcement_type'] = 'نوع التنفيذ مطلوب'
    if not total_amount:
        errors['total_amount'] = 'المبلغ الإجمالي مطلوب'

    if errors:
        return validation_error(errors)

    enforcement = Enforcement(
        tenant_id=g.tenant_id,
        case_id=int(case_id),
        client_id=int(client_id),
        judgment_id=int(data['judgment_id']) if data.get('judgment_id') else None,
        enforcement_number=(data.get('enforcement_number', '') or '').strip() or None,
        enforcement_court=(data.get('enforcement_court', '') or '').strip() or None,
        executor_name=(data.get('executor_name', '') or '').strip() or None,
        enforcement_type=enforcement_type,
        total_amount=float(total_amount),
        debtor_name=(data.get('debtor_name', '') or '').strip() or None,
        start_date=parse_date(data.get('start_date')),
        notes=(data.get('notes', '') or '').strip() or None,
    )
    db.session.add(enforcement)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم إضافة ملف تنفيذ جديد: {enforcement.enforcement_number or "-"}',
        body=f'المبلغ: {total_amount} ج.م',
        related_type='enforcement',
        related_id=enforcement.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=enforcement.to_dict(), message='تم إضافة ملف التنفيذ بنجاح', status_code=201)


# ---------- SHOW ----------

@api_bp.route('/enforcement/<int:id>', methods=['GET'])
@api_permission_required('enforcement', 'view')
def api_enforcement_show(id):
    """Return enforcement details with collections and actions."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not enforcement:
        return error_response('ملف التنفيذ غير موجود', error_code='not_found', status_code=404)

    return success_response(data=enforcement.to_dict(include_related=True))


# ---------- DELETE ----------

@api_bp.route('/enforcement/<int:id>', methods=['DELETE'])
@api_permission_required('enforcement', 'delete')
def api_enforcement_delete(id):
    """Delete an enforcement record."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not enforcement:
        return error_response('ملف التنفيذ غير موجود', error_code='not_found', status_code=404)

    case_id = enforcement.case_id
    db.session.delete(enforcement)
    db.session.commit()

    return success_response(data={'case_id': case_id}, message='تم حذف ملف التنفيذ')


# ---------- ADD COLLECTION ----------

@api_bp.route('/enforcement/<int:id>/collections', methods=['POST'])
@api_permission_required('enforcement', 'edit')
def api_enforcement_add_collection(id):
    """Add a collection payment to an enforcement record."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not enforcement:
        return error_response('ملف التنفيذ غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()
    errors = {}

    amount = data.get('amount')
    if not amount:
        errors['amount'] = 'يجب إدخال المبلغ'
    else:
        try:
            amount = float(amount)
            if amount <= 0:
                errors['amount'] = 'يجب أن يكون المبلغ أكبر من صفر'
        except (ValueError, TypeError):
            errors['amount'] = 'مبلغ غير صالح'

    if errors:
        return validation_error(errors)

    collection_date = parse_date(data.get('collection_date'))
    if not collection_date:
        collection_date = datetime.utcnow().date()

    collection = EnforcementCollection(
        enforcement_id=enforcement.id,
        amount=amount,
        collection_date=collection_date,
        collection_method=(data.get('collection_method', '') or '').strip() or None,
        notes=(data.get('notes', '') or '').strip() or None,
    )
    db.session.add(collection)
    enforcement.update_collected()

    # Auto-complete if fully collected
    if float(enforcement.collected_amount) >= float(enforcement.total_amount):
        enforcement.status = 'completed'

    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='payment_received',
        title=f'تم تحصيل مبلغ {amount} ج.م',
        body=f'ملف التنفيذ: {enforcement.enforcement_number or "-"}',
        priority='success',
        related_type='enforcement',
        related_id=enforcement.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(
        data=enforcement.to_dict(include_related=True),
        message='تم إضافة التحصيل بنجاح',
        status_code=201,
    )


# ---------- ADD ACTION ----------

@api_bp.route('/enforcement/<int:id>/actions', methods=['POST'])
@api_permission_required('enforcement', 'edit')
def api_enforcement_add_action(id):
    """Add an enforcement action."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not enforcement:
        return error_response('ملف التنفيذ غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()
    errors = {}

    action_description = (data.get('action_description', '') or '').strip()
    if not action_description:
        errors['action_description'] = 'وصف الإجراء مطلوب'

    if errors:
        return validation_error(errors)

    action_date = parse_date(data.get('action_date'))
    if not action_date:
        action_date = datetime.utcnow().date()

    action = EnforcementAction(
        enforcement_id=enforcement.id,
        action_description=action_description,
        action_date=action_date,
    )
    db.session.add(action)
    db.session.commit()

    return success_response(data=action.to_dict(), message='تم إضافة الإجراء بنجاح', status_code=201)
