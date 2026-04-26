"""API routes for Power of Attorney management."""
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request, current_app
from app.models.power_of_attorney import PowerOfAttorney


# ---------- LIST ----------

@api_bp.route('/poa', methods=['GET'])
@api_login_required
def api_poa_list():
    """List all powers of attorney."""
    query = PowerOfAttorney.query.filter_by(tenant_id=g.tenant_id).order_by(
        PowerOfAttorney.created_at.desc()
    )
    return paginated_response(query)


# ---------- CREATE ----------

@api_bp.route('/poa', methods=['POST'])
@api_login_required
def api_poa_create():
    """Create a new power of attorney (supports multipart/form-data or JSON)."""
    data = get_json_or_form()
    errors = {}

    client_id = data.get('client_id')
    poa_type = data.get('poa_type', '')

    if not client_id:
        errors['client_id'] = 'يجب اختيار الموكل'
    if not poa_type:
        errors['poa_type'] = 'نوع التوكيل مطلوب'

    if errors:
        return validation_error(errors)

    poa = PowerOfAttorney(
        tenant_id=g.tenant_id,
        client_id=int(client_id),
        poa_type=poa_type,
        notarization_number=(data.get('poa_number', '') or '').strip() or None,
        issue_date=parse_date(data.get('issue_date')),
        expiry_date=parse_date(data.get('expiry_date')),
        notary_office=(data.get('notary_office', '') or '').strip() or None,
    )
    db.session.add(poa)
    db.session.flush()  # get poa.id before saving file

    # Handle POA file upload (multipart/form-data)
    file = request.files.get('poa_file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'poa', str(g.tenant_id))
        os.makedirs(upload_dir, exist_ok=True)
        saved_name = f'poa_{poa.id}_{filename}'
        file.save(os.path.join(upload_dir, saved_name))
        poa.file_path = f'uploads/poa/{g.tenant_id}/{saved_name}'

    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم إضافة توكيل جديد للموكل: {poa.client.full_name if poa.client else "-"}',
        body=f'النوع: {poa.poa_type} — تاريخ الانتهاء: {poa.expiry_date.strftime("%Y-%m-%d") if poa.expiry_date else "غير محدد"}',
        related_type='poa',
        related_id=poa.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=poa.to_dict(), message='تم إضافة التوكيل بنجاح', status_code=201)


# ---------- SHOW ----------

@api_bp.route('/poa/<int:id>', methods=['GET'])
@api_login_required
def api_poa_show(id):
    """Return power of attorney details."""
    poa = PowerOfAttorney.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not poa:
        return error_response('التوكيل غير موجود', error_code='not_found', status_code=404)

    return success_response(data=poa.to_dict())


# ---------- UPLOAD FILE ----------

@api_bp.route('/poa/<int:id>/upload', methods=['POST'])
@api_login_required
def api_poa_upload(id):
    """Upload or replace the POA document file."""
    poa = PowerOfAttorney.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not poa:
        return error_response('التوكيل غير موجود', error_code='not_found', status_code=404)

    file = request.files.get('poa_file')
    if not file or not file.filename:
        return validation_error({'poa_file': 'يرجى اختيار ملف'})

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'poa', str(g.tenant_id))
    os.makedirs(upload_dir, exist_ok=True)
    saved_name = f'poa_{poa.id}_{filename}'
    file.save(os.path.join(upload_dir, saved_name))
    poa.file_path = f'uploads/poa/{g.tenant_id}/{saved_name}'
    db.session.commit()

    return success_response(data=poa.to_dict(), message='تم رفع ملف التوكيل بنجاح')
