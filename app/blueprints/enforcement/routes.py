"""Enforcement management routes."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.enforcement import Enforcement, EnforcementCollection, EnforcementAction
from app.models.case import Case
from app.models.client import Client
from app.models.judgment import Judgment

enforcement_bp = Blueprint('enforcement', __name__, template_folder='../../templates/enforcement')

ENFORCEMENT_TYPES = [
    ('real_estate_seizure', 'حجز عقاري'), ('funds_seizure', 'حجز على أموال'),
    ('movables_seizure', 'حجز منقولات'), ('eviction', 'إخلاء'), ('delivery', 'تسليم'),
]
ENFORCEMENT_STATUSES = [
    ('active', 'نشط'), ('completed', 'مكتمل'), ('suspended', 'معلق'), ('cancelled', 'ملغي'),
]
COLLECTION_METHODS = [
    ('bank_transfer', 'تحويل بنكي'), ('cash', 'نقداً'), ('cheque', 'شيك'),
]


@enforcement_bp.route('/')
@permission_required('enforcement', 'view')
def index():
    """List all enforcement records."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')

    query = Enforcement.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)

    enforcements = query.order_by(Enforcement.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('enforcement/index.html', enforcements=enforcements, status=status,
                           enforcement_statuses=ENFORCEMENT_STATUSES)


@enforcement_bp.route('/create', methods=['GET', 'POST'])
@permission_required('enforcement', 'create')
def create():
    """Create a new enforcement record."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        errors = []
        case_id = request.form.get('case_id', type=int)
        client_id = request.form.get('client_id', type=int)
        enforcement_type = request.form.get('enforcement_type', '')
        total_amount = request.form.get('total_amount', type=float)

        if not case_id:
            errors.append('يجب اختيار القضية')
        if not client_id:
            errors.append('يجب اختيار الموكل')
        if not enforcement_type:
            errors.append('نوع التنفيذ مطلوب')
        if not total_amount:
            errors.append('المبلغ الإجمالي مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('enforcement/create.html', cases=cases, clients=clients,
                                   form=request.form, enforcement_types=ENFORCEMENT_TYPES)

        enforcement = Enforcement(
            tenant_id=g.tenant_id,
            case_id=case_id,
            client_id=client_id,
            judgment_id=request.form.get('judgment_id', type=int) or None,
            enforcement_number=request.form.get('enforcement_number', '').strip() or None,
            enforcement_court=request.form.get('enforcement_court', '').strip() or None,
            executor_name=request.form.get('executor_name', '').strip() or None,
            enforcement_type=enforcement_type,
            total_amount=total_amount,
            debtor_name=request.form.get('debtor_name', '').strip() or None,
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date() if request.form.get('start_date') else None,
            notes=request.form.get('notes', '').strip() or None,
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

        flash('تم إضافة ملف التنفيذ بنجاح', 'success')
        return redirect(url_for('enforcement.show', id=enforcement.id))

    return render_template('enforcement/create.html', cases=cases, clients=clients,
                           form=request.args, enforcement_types=ENFORCEMENT_TYPES)


@enforcement_bp.route('/<int:id>')
@permission_required('enforcement', 'view')
def show(id):
    """Show enforcement details with collections and actions."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    collections = enforcement.collections.all()
    actions = enforcement.actions.all()
    type_map = dict(ENFORCEMENT_TYPES)
    return render_template('enforcement/show.html', enforcement=enforcement,
                           collections=collections, actions=actions, type_map=type_map,
                           collection_methods=COLLECTION_METHODS,
                           method_map=dict(COLLECTION_METHODS))


@enforcement_bp.route('/<int:id>/add-collection', methods=['POST'])
@permission_required('enforcement', 'edit')
def add_collection(id):
    """Add a collection record."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    amount = request.form.get('amount', type=float)
    if not amount or amount <= 0:
        flash('يجب إدخال مبلغ صالح', 'danger')
        return redirect(url_for('enforcement.show', id=enforcement.id))

    method_in = (request.form.get('collection_method') or '').strip() or None
    if method_in and method_in not in dict(COLLECTION_METHODS):
        flash('طريقة التحصيل غير صالحة', 'danger')
        return redirect(url_for('enforcement.show', id=enforcement.id))

    collection = EnforcementCollection(
        enforcement_id=enforcement.id,
        amount=amount,
        collection_date=datetime.strptime(request.form['collection_date'], '%Y-%m-%d').date() if request.form.get('collection_date') else datetime.utcnow().date(),
        collection_method=method_in,
        notes=request.form.get('notes', '').strip() or None,
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

    flash('تم إضافة التحصيل بنجاح', 'success')
    return redirect(url_for('enforcement.show', id=enforcement.id))


@enforcement_bp.route('/<int:id>/add-action', methods=['POST'])
@permission_required('enforcement', 'edit')
def add_action(id):
    """Add an enforcement action."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    action = EnforcementAction(
        enforcement_id=enforcement.id,
        action_description=request.form.get('action_description', '').strip(),
        action_date=datetime.strptime(request.form['action_date'], '%Y-%m-%d').date() if request.form.get('action_date') else datetime.utcnow().date(),
    )
    db.session.add(action)
    db.session.commit()
    flash('تم إضافة الإجراء بنجاح', 'success')
    return redirect(url_for('enforcement.show', id=enforcement.id))


@enforcement_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('enforcement', 'delete')
def delete(id):
    """Delete an enforcement record."""
    enforcement = Enforcement.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    case_id = enforcement.case_id
    db.session.delete(enforcement)
    db.session.commit()
    flash('تم حذف ملف التنفيذ', 'warning')
    return redirect(url_for('cases.show', id=case_id))
