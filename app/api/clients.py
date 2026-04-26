"""API routes for client management."""
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_time)
from app.extensions import db
from flask import g, request

from app.models.client import Client, ClientDocument
from app.utils.validators import validate_national_id, validate_phone, validate_email
from app.utils.helpers import save_uploaded_file


@api_bp.route('/clients', methods=['GET'])
@api_permission_required('clients', 'view')
def api_clients_list():
    """List clients with search, filters, and pagination."""
    search = request.args.get('search', '').strip()
    client_type = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()

    query = Client.query.filter_by(tenant_id=g.tenant_id)

    if search:
        query = query.filter(
            db.or_(
                Client.full_name.ilike(f'%{search}%'),
                Client.client_number.ilike(f'%{search}%'),
                Client.national_id.ilike(f'%{search}%'),
                Client.phone_primary.ilike(f'%{search}%'),
            )
        )
    if client_type:
        query = query.filter_by(client_type=client_type)
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    query = query.order_by(Client.created_at.desc())
    return paginated_response(query)


@api_bp.route('/clients', methods=['POST'])
@api_permission_required('clients', 'create')
def api_clients_create():
    """Create a new client."""
    data = get_json_or_form()
    errors = {}

    full_name = (data.get('full_name') or '').strip()
    if not full_name:
        errors['full_name'] = 'اسم الموكل مطلوب'

    national_id = (data.get('national_id') or '').strip()
    if national_id and not validate_national_id(national_id):
        errors['national_id'] = 'الرقم القومي يجب أن يكون 14 رقم'

    phone = (data.get('phone_primary') or '').strip()
    if phone and not validate_phone(phone):
        errors['phone_primary'] = 'رقم الهاتف غير صالح'

    email = (data.get('email') or '').strip()
    if email and not validate_email(email):
        errors['email'] = 'البريد الإلكتروني غير صالح'

    if errors:
        return validation_error(errors)

    dob_str = (data.get('date_of_birth') or '').strip()
    client = Client(
        tenant_id=g.tenant_id,
        client_type=data.get('client_type', 'individual'),
        full_name=full_name,
        full_name_en=(data.get('full_name_en') or '').strip() or None,
        national_id=national_id or None,
        commercial_reg=(data.get('commercial_reg') or '').strip() or None,
        date_of_birth=parse_date(dob_str),
        nationality=(data.get('nationality') or '').strip() or None,
        profession=(data.get('profession') or '').strip() or None,
        governorate=(data.get('governorate') or '').strip() or None,
        city=(data.get('city') or '').strip() or None,
        district=(data.get('district') or '').strip() or None,
        street=(data.get('street') or '').strip() or None,
        building_no=(data.get('building_no') or '').strip() or None,
        phone_primary=phone or None,
        phone_secondary=(data.get('phone_secondary') or '').strip() or None,
        email=email or None,
        whatsapp=(data.get('whatsapp') or '').strip() or None,
        emergency_contact_name=(data.get('emergency_contact_name') or '').strip() or None,
        emergency_contact_phone=(data.get('emergency_contact_phone') or '').strip() or None,
        emergency_contact_relation=(data.get('emergency_contact_relation') or '').strip() or None,
        internal_notes=(data.get('internal_notes') or '').strip() or None,
        registered_by=g.current_user.id,
    )
    client.generate_client_number()
    db.session.add(client)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم إضافة موكل جديد: {client.full_name}',
        body=f'رقم الملف: {client.client_number}',
        related_type='client',
        related_id=client.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=client.to_dict(), message='تم إضافة الموكل بنجاح', status_code=201)


@api_bp.route('/clients/<int:id>', methods=['GET'])
@api_permission_required('clients', 'view')
def api_clients_show(id):
    """Show client details with related data."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not client:
        return error_response('الموكل غير موجود', error_code='not_found', status_code=404)

    result = client.to_dict(include_related=True)
    result['cases'] = [c.to_dict() for c in client.cases.order_by(db.text('created_at desc')).all()]
    result['documents'] = [d.to_dict() for d in client.documents.order_by(db.text('created_at desc')).all()]
    return success_response(data=result)


@api_bp.route('/clients/<int:id>', methods=['PUT'])
@api_permission_required('clients', 'edit')
def api_clients_update(id):
    """Update client details."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not client:
        return error_response('الموكل غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()
    errors = {}

    full_name = (data.get('full_name') or '').strip()
    if 'full_name' in data and not full_name:
        errors['full_name'] = 'اسم الموكل مطلوب'

    national_id = (data.get('national_id') or '').strip()
    if national_id and not validate_national_id(national_id):
        errors['national_id'] = 'الرقم القومي يجب أن يكون 14 رقم'

    phone = (data.get('phone_primary') or '').strip()
    if phone and not validate_phone(phone):
        errors['phone_primary'] = 'رقم الهاتف غير صالح'

    email = (data.get('email') or '').strip()
    if email and not validate_email(email):
        errors['email'] = 'البريد الإلكتروني غير صالح'

    if errors:
        return validation_error(errors)

    # Update fields if provided
    if full_name:
        client.full_name = full_name
    if 'full_name_en' in data:
        client.full_name_en = (data['full_name_en'] or '').strip() or None
    if 'client_type' in data:
        client.client_type = data['client_type']
    if 'national_id' in data:
        client.national_id = national_id or None
    if 'commercial_reg' in data:
        client.commercial_reg = (data['commercial_reg'] or '').strip() or None
    if 'date_of_birth' in data:
        client.date_of_birth = parse_date((data['date_of_birth'] or '').strip())
    if 'nationality' in data:
        client.nationality = (data['nationality'] or '').strip() or None
    if 'profession' in data:
        client.profession = (data['profession'] or '').strip() or None
    if 'governorate' in data:
        client.governorate = (data['governorate'] or '').strip() or None
    if 'city' in data:
        client.city = (data['city'] or '').strip() or None
    if 'district' in data:
        client.district = (data['district'] or '').strip() or None
    if 'street' in data:
        client.street = (data['street'] or '').strip() or None
    if 'building_no' in data:
        client.building_no = (data['building_no'] or '').strip() or None
    if 'phone_primary' in data:
        client.phone_primary = phone or None
    if 'phone_secondary' in data:
        client.phone_secondary = (data['phone_secondary'] or '').strip() or None
    if 'email' in data:
        client.email = email or None
    if 'whatsapp' in data:
        client.whatsapp = (data['whatsapp'] or '').strip() or None
    if 'emergency_contact_name' in data:
        client.emergency_contact_name = (data['emergency_contact_name'] or '').strip() or None
    if 'emergency_contact_phone' in data:
        client.emergency_contact_phone = (data['emergency_contact_phone'] or '').strip() or None
    if 'emergency_contact_relation' in data:
        client.emergency_contact_relation = (data['emergency_contact_relation'] or '').strip() or None
    if 'internal_notes' in data:
        client.internal_notes = (data['internal_notes'] or '').strip() or None

    db.session.commit()
    return success_response(data=client.to_dict(), message='تم تحديث بيانات الموكل بنجاح')


@api_bp.route('/clients/<int:id>', methods=['DELETE'])
@api_permission_required('clients', 'delete')
def api_clients_delete(id):
    """Soft-delete a client."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not client:
        return error_response('الموكل غير موجود', error_code='not_found', status_code=404)

    client_name = client.full_name
    client.is_active = False
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم حذف موكل: {client_name}',
        related_type='client',
        related_id=id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(message='تم حذف الموكل')


@api_bp.route('/clients/<int:id>/documents', methods=['POST'])
@api_permission_required('clients', 'edit')
def api_clients_upload_document(id):
    """Upload a document for a client."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not client:
        return error_response('الموكل غير موجود', error_code='not_found', status_code=404)

    file = request.files.get('file')
    if not file or not file.filename:
        return error_response('يرجى اختيار ملف', error_code='missing_file', status_code=400)

    doc_type = request.form.get('document_type', 'other')
    file_path = save_uploaded_file(file, f'clients/{client.id}')
    if not file_path:
        return error_response('فشل رفع الملف', error_code='upload_failed', status_code=500)

    doc = ClientDocument(
        client_id=client.id,
        document_type=doc_type,
        file_path=file_path,
        file_name=file.filename,
        file_type=file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else '',
        uploaded_by=g.current_user.id,
    )
    db.session.add(doc)
    db.session.commit()

    return success_response(data=doc.to_dict(), message='تم رفع المستند بنجاح', status_code=201)


@api_bp.route('/clients/<int:id>/documents', methods=['GET'])
@api_permission_required('clients', 'view')
def api_clients_documents(id):
    """List documents for a client."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first()
    if not client:
        return error_response('الموكل غير موجود', error_code='not_found', status_code=404)

    documents = client.documents.order_by(db.text('created_at desc')).all()
    return success_response(data=[d.to_dict() for d in documents])
