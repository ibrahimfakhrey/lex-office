"""Power of Attorney management routes."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
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
        db.session.commit()
        flash('تم إضافة التوكيل بنجاح', 'success')
        return redirect(url_for('poa.show', id=poa.id))

    return render_template('poa/create.html', clients=clients)


@poa_bp.route('/<int:id>')
@login_required
def show(id):
    """Show power of attorney details."""
    poa = PowerOfAttorney.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return render_template('poa/show.html', poa=poa)
