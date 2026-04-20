"""Power of Attorney management routes."""
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, send_file, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.utils.decorators import login_required, role_required, permission_required, manager_only
from app.models.power_of_attorney import PowerOfAttorney
from app.models.client import Client

poa_bp = Blueprint('poa', __name__, template_folder='../../templates/poa')


@poa_bp.route('/')
@login_required
def index():
    """List all powers of attorney."""
    page = request.args.get('page', 1, type=int)
    poas = PowerOfAttorney.query.filter_by(tenant_id=g.tenant_id).order_by(
        PowerOfAttorney.created_at.desc()
    ).paginate(page=page, per_page=20)
    return render_template('poa/index.html', poas=poas)


@poa_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new power of attorney."""
    clients = Client.query.filter_by(tenant_id=g.tenant_id).order_by(Client.full_name).all()

    if request.method == 'POST':
        poa = PowerOfAttorney(
            tenant_id=g.tenant_id,
            client_id=request.form.get('client_id', type=int),
            notarization_number=request.form.get("poa_number", "").strip(),
            poa_type=request.form.get('poa_type', ''),
            issue_date=datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d').date() if request.form.get('issue_date') else None,
            expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
            notary_office=request.form.get('notary_office', '').strip(),
        )
        db.session.add(poa)
        db.session.flush()  # get poa.id before saving file

        # Handle POA file upload
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

        flash('تم إضافة التوكيل بنجاح', 'success')
        return redirect(url_for('poa.show', id=poa.id))

    pre_client = request.args.get('client_id', type=int)
    return render_template('poa/create.html', clients=clients, pre_client_id=pre_client)


@poa_bp.route('/<int:id>/upload-file', methods=['POST'])
@login_required
def upload_file(id):
    """Upload or replace the POA document file."""
    poa = PowerOfAttorney.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    file = request.files.get('poa_file')
    if not file or not file.filename:
        flash('يرجى اختيار ملف', 'danger')
        return redirect(url_for('poa.show', id=poa.id))

    filename = secure_filename(file.filename)
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'poa', str(g.tenant_id))
    os.makedirs(upload_dir, exist_ok=True)
    saved_name = f'poa_{poa.id}_{filename}'
    file.save(os.path.join(upload_dir, saved_name))
    poa.file_path = f'uploads/poa/{g.tenant_id}/{saved_name}'
    db.session.commit()
    flash('تم رفع ملف التوكيل بنجاح', 'success')
    return redirect(url_for('poa.show', id=poa.id))


@poa_bp.route('/<int:id>')
@login_required
def show(id):
    """Show power of attorney details."""
    poa = PowerOfAttorney.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return render_template('poa/show.html', poa=poa)
