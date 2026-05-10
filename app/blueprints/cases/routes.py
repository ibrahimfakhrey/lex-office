"""Case management routes: Full CRUD with RBAC, filters, and case lifecycle."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.case import Case, Court
from app.models.client import Client
from app.models.user import User

cases_bp = Blueprint('cases', __name__, template_folder='../../templates/cases')

CASE_TYPES = [
    ('criminal', 'جنائية'), ('civil', 'مدنية'), ('commercial', 'تجارية'),
    ('administrative', 'إدارية'), ('labor', 'عمالية'), ('family', 'أسرة'),
    ('constitutional', 'دستورية'), ('enforcement', 'تنفيذ'),
]
CASE_STATUSES = [
    ('new', 'جديدة'), ('active', 'نشطة'), ('awaiting_judgment', 'منتظرة حكم'),
    ('suspended', 'موقوفة'), ('closed', 'مغلقة'),
]
PRIORITIES = [('normal', 'عادية'), ('important', 'مهمة'), ('critical', 'حرجة')]
CAPACITIES = [
    ('plaintiff', 'مدعي'), ('defendant', 'مدعى عليه'),
    ('appellant', 'مستأنف'), ('respondent', 'مطعون ضده'), ('other', 'أخرى'),
]
FEE_TYPES = [('fixed', 'مبلغ ثابت'), ('percentage', 'نسبة'), ('hourly', 'بالساعة'), ('mixed', 'مختلط')]
PAYMENT_SCHEDULES = [('upfront', 'مقدم'), ('installments', 'أقساط'), ('after_judgment', 'بعد الحكم')]


def _get_form_context():
    """Common data needed by create/edit forms."""
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()
    return dict(
        clients=clients, courts=courts, lawyers=lawyers,
        case_types=CASE_TYPES, statuses=CASE_STATUSES, priorities=PRIORITIES,
        capacities=CAPACITIES, fee_types=FEE_TYPES, payment_schedules=PAYMENT_SCHEDULES,
    )


@cases_bp.route('/api/by-client/<int:client_id>')
@permission_required('cases', 'view')
def api_by_client(client_id):
    """Return JSON list of cases for a given client (used by cascading dropdowns)."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).order_by(Case.case_number).all()
    return jsonify([{
        'id': c.id,
        'label': f"{c.case_number or '-'} — {(c.subject or '')[:40]}",
        'client_id': c.client_id,
    } for c in cases])


@cases_bp.route('/')
@permission_required('cases', 'view')
def index():
    """List all cases with search and filters."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    case_type = request.args.get('type', '')
    priority = request.args.get('priority', '')
    lawyer_id = request.args.get('lawyer_id', '', type=str)

    query = Case.query.filter_by(tenant_id=g.tenant_id)

    if search:
        query = query.filter(db.or_(
            Case.case_number.ilike(f'%{search}%'),
            Case.subject.ilike(f'%{search}%'),
            Case.opponent_name.ilike(f'%{search}%'),
        ))
    if status:
        query = query.filter_by(status=status)
    if case_type:
        query = query.filter_by(case_type=case_type)
    if priority:
        query = query.filter_by(priority=priority)
    if lawyer_id:
        query = query.filter_by(responsible_lawyer_id=int(lawyer_id))

    cases = query.order_by(Case.created_at.desc()).paginate(page=page, per_page=20)
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    # Status counts for the filter chip strip — independent of current filters
    # so the counts show what's available globally, not within the filtered set.
    status_count_rows = (
        db.session.query(Case.status, db.func.count(Case.id))
        .filter(Case.tenant_id == g.tenant_id)
        .group_by(Case.status)
        .all()
    )
    status_counts = {row[0]: row[1] for row in status_count_rows}
    total_count = sum(status_counts.values())

    return render_template('cases/index.html', cases=cases, search=search,
                           status=status, case_type=case_type, priority=priority,
                           lawyer_id=lawyer_id, lawyers=lawyers,
                           case_types=CASE_TYPES, statuses=CASE_STATUSES, priorities=PRIORITIES,
                           status_counts=status_counts, total_count=total_count)


@cases_bp.route('/create', methods=['GET', 'POST'])
@permission_required('cases', 'create')
def create():
    """Create a new case."""
    if request.method == 'POST':
        errors = []
        client_id = request.form.get('client_id', type=int)
        case_type = request.form.get('case_type', '')
        responsible_lawyer_id = request.form.get('responsible_lawyer_id', type=int)

        if not client_id:
            errors.append('يجب اختيار الموكل')
        if not case_type:
            errors.append('يجب اختيار نوع القضية')
        if not responsible_lawyer_id:
            errors.append('يجب اختيار المحامي المسؤول')

        if errors:
            for err in errors:
                flash(err, 'danger')
            ctx = _get_form_context()
            return render_template('cases/create.html', form=request.form, **ctx)

        retainer_amount = request.form.get('retainer_paid', type=float) or 0

        case = Case(
            tenant_id=g.tenant_id,
            client_id=client_id,
            case_number=request.form.get('case_number', '').strip() or None,
            judicial_year=request.form.get('judicial_year', '').strip() or None,
            court_id=request.form.get('court_id', type=int) or None,
            circuit=request.form.get('circuit', '').strip() or None,
            case_type=case_type,
            subject=request.form.get('subject', '').strip() or None,
            opponent_name=request.form.get('opponent_name', '').strip() or None,
            opponent_capacity=request.form.get('opponent_capacity', '').strip() or None,
            opponent_lawyer=request.form.get('opponent_lawyer', '').strip() or None,
            responsible_lawyer_id=responsible_lawyer_id,
            assistant_lawyer_id=request.form.get('assistant_lawyer_id', type=int) or None,
            our_client_capacity=request.form.get('our_client_capacity', '') or None,
            fee_type=request.form.get('fee_type', '') or None,
            fee_amount=request.form.get('fee_amount', type=float) or None,
            retainer_paid=retainer_amount,
            payment_schedule=request.form.get('payment_schedule', '') or None,
            priority=request.form.get('priority', 'normal'),
            internal_notes=request.form.get('internal_notes', '').strip() or None,
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
        assistant_id = request.form.get('assistant_lawyer_id', type=int)
        if assistant_id and assistant_id != g.current_user.id:
            create_notification(
                tenant_id=g.tenant_id,
                user_id=assistant_id,
                notification_type='case_update',
                title=f'تم تعيينك محامي مساعد لقضية: {case.case_number or "قضية جديدة"}',
                related_type='case',
                related_id=case.id,
                actor_name=g.current_user.full_name,
            )
        db.session.commit()

        flash('تم إضافة القضية بنجاح', 'success')
        return redirect(url_for('cases.show', id=case.id))

    ctx = _get_form_context()
    pre_client = request.args.get('client_id', type=int)
    return render_template('cases/create.html', form=request.args, pre_client_id=pre_client, **ctx)


@cases_bp.route('/<int:id>')
@permission_required('cases', 'view')
def show(id):
    """Show case details with all related data."""
    from app.utils.helpers import egypt_today
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    sessions = case.sessions.all()
    judgments = case.judgments.all()
    payments = case.case_payments.all()
    expenses = case.expenses.all()
    documents = case.case_documents.all()
    tasks = case.tasks.all()

    # Next upcoming session — drives the highlighted side card
    today = egypt_today()
    next_session = None
    upcoming = [s for s in sessions if s.session_date and s.session_date >= today]
    if upcoming:
        from datetime import time as _t
        next_session = sorted(
            upcoming,
            key=lambda s: (s.session_date, s.session_time or _t(0, 0)),
        )[0]

    return render_template('cases/show.html', case=case, sessions=sessions,
                           judgments=judgments, payments=payments, expenses=expenses,
                           documents=documents, tasks=tasks, statuses=CASE_STATUSES,
                           next_session=next_session, today=today)


@cases_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('cases', 'edit')
def edit(id):
    """Edit case details."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    if request.method == 'POST':
        case.case_number = request.form.get('case_number', '').strip() or None
        case.judicial_year = request.form.get('judicial_year', '').strip() or None
        case.court_id = request.form.get('court_id', type=int) or None
        case.circuit = request.form.get('circuit', '').strip() or None
        case.case_type = request.form.get('case_type', case.case_type)
        case.subject = request.form.get('subject', '').strip() or None
        case.opponent_name = request.form.get('opponent_name', '').strip() or None
        case.opponent_capacity = request.form.get('opponent_capacity', '').strip() or None
        case.opponent_lawyer = request.form.get('opponent_lawyer', '').strip() or None
        case.responsible_lawyer_id = request.form.get('responsible_lawyer_id', type=int) or case.responsible_lawyer_id
        case.assistant_lawyer_id = request.form.get('assistant_lawyer_id', type=int) or None
        case.our_client_capacity = request.form.get('our_client_capacity', '') or None
        case.fee_type = request.form.get('fee_type', '') or None
        case.fee_amount = request.form.get('fee_amount', type=float) or None
        case.retainer_paid = request.form.get('retainer_paid', type=float) or 0
        case.payment_schedule = request.form.get('payment_schedule', '') or None
        case.priority = request.form.get('priority', 'normal')
        case.status = request.form.get('status', case.status)
        case.internal_notes = request.form.get('internal_notes', '').strip() or None

        if case.status == 'closed' and not case.closed_at:
            case.closed_at = datetime.utcnow()

        db.session.commit()
        flash('تم تحديث القضية بنجاح', 'success')
        return redirect(url_for('cases.show', id=case.id))

    ctx = _get_form_context()
    return render_template('cases/edit.html', case=case, **ctx)


@cases_bp.route('/<int:id>/close', methods=['POST'])
@permission_required('cases', 'edit')
def close(id):
    """Close a case."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
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

    flash('تم إغلاق القضية', 'warning')
    return redirect(url_for('cases.show', id=case.id))


@cases_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('cases', 'delete')
def delete(id):
    """Delete a case (manager only via RBAC)."""
    case = Case.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(case)
    db.session.commit()
    flash('تم حذف القضية', 'warning')
    return redirect(url_for('cases.index'))
