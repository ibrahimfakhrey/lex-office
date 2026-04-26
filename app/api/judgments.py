"""API routes for Judgment management."""
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request
from app.models.judgment import Judgment
from app.models.case import Case

JUDGMENT_TYPES = [
    ('primary', 'ابتدائي'), ('appeal', 'استئنافي'),
    ('cassation', 'نقض'), ('constitutional', 'دستوري'),
]
JUDGMENT_RESULTS = [
    ('full_win', 'كسب كامل'), ('partial_win', 'كسب جزئي'), ('loss', 'خسارة'),
    ('postponement', 'تأجيل'), ('procedural', 'شكلي'), ('absence', 'غيابي'),
]
APPEAL_DAYS = {'primary': 40, 'appeal': 60, 'cassation': 60}


# ---------- LIST ----------

@api_bp.route('/judgments', methods=['GET'])
@api_permission_required('judgments', 'view')
def api_judgments_list():
    """List judgments with optional filters."""
    case_id = request.args.get('case_id', type=int)
    result = request.args.get('result', '')

    query = Judgment.query.filter_by(tenant_id=g.tenant_id)
    if case_id:
        query = query.filter_by(case_id=case_id)
    if result:
        query = query.filter_by(result=result)

    query = query.order_by(Judgment.judgment_date.desc())
    return paginated_response(query)


# ---------- CREATE ----------

@api_bp.route('/judgments', methods=['POST'])
@api_permission_required('judgments', 'create')
def api_judgments_create():
    """Record a new judgment."""
    data = get_json_or_form()
    errors = {}

    case_id = data.get('case_id')
    judgment_date_str = data.get('judgment_date', '')
    judgment_type = data.get('judgment_type', '')
    result = data.get('result', '')

    if not case_id:
        errors['case_id'] = 'يجب اختيار القضية'
    if not judgment_date_str:
        errors['judgment_date'] = 'تاريخ الحكم مطلوب'
    if not judgment_type:
        errors['judgment_type'] = 'نوع الحكم مطلوب'
    if not result:
        errors['result'] = 'نتيجة الحكم مطلوبة'

    if errors:
        return validation_error(errors)

    judgment_date = parse_date(judgment_date_str)
    if not judgment_date:
        return validation_error({'judgment_date': 'تنسيق التاريخ غير صالح'})

    # Auto-calculate appeal deadline
    appeal_deadline = None
    appeal_tracking = str(data.get('appeal_tracking_enabled', '')).lower() in ('true', '1', 'yes')
    if appeal_tracking:
        days = APPEAL_DAYS.get(judgment_type, 40)
        appeal_deadline = judgment_date + timedelta(days=days)
        # Allow manual override
        manual_deadline = data.get('appeal_deadline')
        if manual_deadline:
            parsed = parse_date(manual_deadline)
            if parsed:
                appeal_deadline = parsed

    judgment = Judgment(
        tenant_id=g.tenant_id,
        case_id=int(case_id),
        judgment_date=judgment_date,
        court_id=int(data['court_id']) if data.get('court_id') else None,
        judgment_type=judgment_type,
        result=result,
        judgment_text=(data.get('judgment_text', '') or '').strip() or None,
        judge_name=(data.get('judge_name', '') or '').strip() or None,
        awarded_amount=float(data['awarded_amount']) if data.get('awarded_amount') else None,
        notes=(data.get('notes', '') or '').strip() or None,
        appeal_tracking_enabled=appeal_tracking,
        appeal_type=judgment_type,
        appeal_deadline=appeal_deadline,
    )
    db.session.add(judgment)

    # Update case status based on result
    case = Case.query.get(int(case_id))
    if case:
        if result == 'postponement':
            case.status = 'awaiting_judgment'
        elif judgment_type == 'cassation':
            case.status = 'closed'

    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='appeal_deadline',
        title=f'تم تسجيل حكم للقضية: {case.case_number or "-"}' if case else 'تم تسجيل حكم جديد',
        body=f'النتيجة: {result} — موعد الاستئناف: {appeal_deadline.strftime("%Y-%m-%d") if appeal_deadline else "غير محدد"}',
        priority='important',
        related_type='judgment',
        related_id=judgment.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=judgment.to_dict(), message='تم تسجيل الحكم بنجاح', status_code=201)


# ---------- SHOW ----------

@api_bp.route('/judgments/<int:id>', methods=['GET'])
@api_permission_required('judgments', 'view')
def api_judgments_show(id):
    """Return judgment details with days_until_appeal."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not judgment:
        return error_response('الحكم غير موجود', error_code='not_found', status_code=404)

    result = judgment.to_dict()

    # Computed value: days until appeal deadline
    days_until_appeal = None
    if judgment.appeal_deadline:
        days_until_appeal = (judgment.appeal_deadline - datetime.utcnow().date()).days
    result['days_until_appeal'] = days_until_appeal

    return success_response(data=result)


# ---------- UPDATE ----------

@api_bp.route('/judgments/<int:id>', methods=['PUT'])
@api_permission_required('judgments', 'edit')
def api_judgments_update(id):
    """Update an existing judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not judgment:
        return error_response('الحكم غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()

    if data.get('judgment_date'):
        parsed = parse_date(data['judgment_date'])
        if parsed:
            judgment.judgment_date = parsed

    if 'court_id' in data:
        judgment.court_id = int(data['court_id']) if data['court_id'] else None
    if 'judgment_type' in data:
        judgment.judgment_type = data['judgment_type']
    if 'result' in data:
        judgment.result = data['result']
    if 'judgment_text' in data:
        judgment.judgment_text = (data['judgment_text'] or '').strip() or None
    if 'judge_name' in data:
        judgment.judge_name = (data['judge_name'] or '').strip() or None
    if 'awarded_amount' in data:
        judgment.awarded_amount = float(data['awarded_amount']) if data['awarded_amount'] else None
    if 'notes' in data:
        judgment.notes = (data['notes'] or '').strip() or None

    if data.get('appeal_deadline'):
        parsed = parse_date(data['appeal_deadline'])
        if parsed:
            judgment.appeal_deadline = parsed
            judgment.appeal_tracking_enabled = True

    db.session.commit()

    return success_response(data=judgment.to_dict(), message='تم تحديث الحكم بنجاح')


# ---------- DELETE ----------

@api_bp.route('/judgments/<int:id>', methods=['DELETE'])
@api_permission_required('judgments', 'delete')
def api_judgments_delete(id):
    """Delete a judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not judgment:
        return error_response('الحكم غير موجود', error_code='not_found', status_code=404)

    case_id = judgment.case_id
    db.session.delete(judgment)
    db.session.commit()

    return success_response(data={'case_id': case_id}, message='تم حذف الحكم')
