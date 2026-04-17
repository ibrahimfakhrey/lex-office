"""Client management routes: Full CRUD with documents and RBAC."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required, manager_only
from app.models.client import Client, ClientDocument
from app.utils.helpers import save_uploaded_file
from app.utils.validators import validate_national_id, validate_phone, validate_email

clients_bp = Blueprint('clients', __name__, template_folder='../../templates/clients')

EGYPTIAN_GOVERNORATES = [
    'القاهرة', 'الجيزة', 'الإسكندرية', 'الدقهلية', 'البحر الأحمر', 'البحيرة',
    'الفيوم', 'الغربية', 'الإسماعيلية', 'المنوفية', 'المنيا', 'القليوبية',
    'الوادي الجديد', 'السويس', 'أسوان', 'أسيوط', 'بني سويف', 'بورسعيد',
    'دمياط', 'الشرقية', 'جنوب سيناء', 'كفر الشيخ', 'مطروح', 'الأقصر',
    'قنا', 'شمال سيناء', 'سوهاج',
]


@clients_bp.route('/')
@permission_required('clients', 'view')
def index():
    """List all clients with search and filters."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    client_type = request.args.get('type', '')
    status = request.args.get('status', '')

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

    clients = query.order_by(Client.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('clients/index.html', clients=clients, search=search,
                           client_type=client_type, status=status)


@clients_bp.route('/create', methods=['GET', 'POST'])
@permission_required('clients', 'create')
def create():
    """Create a new client."""
    if request.method == 'POST':
        errors = []
        full_name = request.form.get('full_name', '').strip()
        if not full_name:
            errors.append('اسم الموكل مطلوب')

        national_id = request.form.get('national_id', '').strip()
        if national_id and not validate_national_id(national_id):
            errors.append('الرقم القومي يجب أن يكون 14 رقم')

        phone = request.form.get('phone_primary', '').strip()
        if phone and not validate_phone(phone):
            errors.append('رقم الهاتف غير صالح')

        email = request.form.get('email', '').strip()
        if email and not validate_email(email):
            errors.append('البريد الإلكتروني غير صالح')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('clients/create.html', form=request.form,
                                   governorates=EGYPTIAN_GOVERNORATES)

        client = Client(
            tenant_id=g.tenant_id,
            client_type=request.form.get('client_type', 'individual'),
            full_name=full_name,
            full_name_en=request.form.get('full_name_en', '').strip() or None,
            national_id=national_id or None,
            commercial_reg=request.form.get('commercial_reg', '').strip() or None,
            date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date() if request.form.get('date_of_birth') else None,
            nationality=request.form.get('nationality', '').strip() or None,
            profession=request.form.get('profession', '').strip() or None,
            governorate=request.form.get('governorate', '').strip() or None,
            city=request.form.get('city', '').strip() or None,
            district=request.form.get('district', '').strip() or None,
            street=request.form.get('street', '').strip() or None,
            building_no=request.form.get('building_no', '').strip() or None,
            phone_primary=phone or None,
            phone_secondary=request.form.get('phone_secondary', '').strip() or None,
            email=email or None,
            whatsapp=request.form.get('whatsapp', '').strip() or None,
            emergency_contact_name=request.form.get('emergency_contact_name', '').strip() or None,
            emergency_contact_phone=request.form.get('emergency_contact_phone', '').strip() or None,
            emergency_contact_relation=request.form.get('emergency_contact_relation', '').strip() or None,
            internal_notes=request.form.get('internal_notes', '').strip() or None,
            registered_by=g.current_user.id,
        )
        client.generate_client_number()
        db.session.add(client)
        db.session.commit()

        flash('تم إضافة الموكل بنجاح', 'success')
        return redirect(url_for('clients.show', id=client.id))

    return render_template('clients/create.html', form={}, governorates=EGYPTIAN_GOVERNORATES)


@clients_bp.route('/<int:id>')
@permission_required('clients', 'view')
def show(id):
    """Show client details with cases, payments, documents."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    cases = client.cases.order_by(db.text('created_at desc')).all()
    documents = client.documents.order_by(db.text('created_at desc')).all()
    return render_template('clients/show.html', client=client, cases=cases, documents=documents)


@clients_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('clients', 'edit')
def edit(id):
    """Edit client details."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    if request.method == 'POST':
        errors = []
        full_name = request.form.get('full_name', '').strip()
        if not full_name:
            errors.append('اسم الموكل مطلوب')

        national_id = request.form.get('national_id', '').strip()
        if national_id and not validate_national_id(national_id):
            errors.append('الرقم القومي يجب أن يكون 14 رقم')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('clients/edit.html', client=client,
                                   governorates=EGYPTIAN_GOVERNORATES)

        client.full_name = full_name
        client.full_name_en = request.form.get('full_name_en', '').strip() or None
        client.client_type = request.form.get('client_type', client.client_type)
        client.national_id = national_id or None
        client.commercial_reg = request.form.get('commercial_reg', '').strip() or None
        dob_str = request.form.get('date_of_birth', '').strip()
        client.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        client.nationality = request.form.get('nationality', '').strip() or None
        client.profession = request.form.get('profession', '').strip() or None
        client.governorate = request.form.get('governorate', '').strip() or None
        client.city = request.form.get('city', '').strip() or None
        client.district = request.form.get('district', '').strip() or None
        client.street = request.form.get('street', '').strip() or None
        client.building_no = request.form.get('building_no', '').strip() or None
        client.phone_primary = request.form.get('phone_primary', '').strip() or None
        client.phone_secondary = request.form.get('phone_secondary', '').strip() or None
        client.email = request.form.get('email', '').strip() or None
        client.whatsapp = request.form.get('whatsapp', '').strip() or None
        client.emergency_contact_name = request.form.get('emergency_contact_name', '').strip() or None
        client.emergency_contact_phone = request.form.get('emergency_contact_phone', '').strip() or None
        client.emergency_contact_relation = request.form.get('emergency_contact_relation', '').strip() or None
        client.internal_notes = request.form.get('internal_notes', '').strip() or None

        db.session.commit()
        flash('تم تحديث بيانات الموكل بنجاح', 'success')
        return redirect(url_for('clients.show', id=client.id))

    return render_template('clients/edit.html', client=client, governorates=EGYPTIAN_GOVERNORATES)


@clients_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('clients', 'delete')
def delete(id):
    """Soft-delete a client (manager only via RBAC)."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    client.is_active = False
    db.session.commit()
    flash('تم حذف الموكل', 'warning')
    return redirect(url_for('clients.index'))


@clients_bp.route('/<int:id>/print')
@permission_required('clients', 'view')
def print_profile(id):
    """Print-friendly client profile with all related data."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    cases = client.cases.order_by(db.text('created_at desc')).all()
    documents = client.documents.order_by(db.text('created_at desc')).all()
    poas = client.powers_of_attorney.order_by(db.text('created_at desc')).all()
    payments = client.payments.order_by(db.text('payment_date desc')).all()
    return render_template('clients/print.html', client=client, cases=cases,
                           documents=documents, poas=poas, payments=payments)


@clients_bp.route('/<int:id>/upload-document', methods=['POST'])
@permission_required('clients', 'edit')
def upload_document(id):
    """Upload a document for a client (ID copy, etc.)."""
    client = Client.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    file = request.files.get('file')
    if not file or not file.filename:
        flash('يرجى اختيار ملف', 'danger')
        return redirect(url_for('clients.show', id=client.id))

    doc_type = request.form.get('document_type', 'other')
    file_path = save_uploaded_file(file, f'clients/{client.id}')
    if not file_path:
        flash('فشل رفع الملف', 'danger')
        return redirect(url_for('clients.show', id=client.id))

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

    flash('تم رفع المستند بنجاح', 'success')
    return redirect(url_for('clients.show', id=client.id))
