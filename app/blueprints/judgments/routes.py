"""Judgment management routes."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.judgment import Judgment
from app.models.case import Case, Court

judgments_bp = Blueprint('judgments', __name__, template_folder='../../templates/judgments')

JUDGMENT_TYPES = [
    ('primary', 'ابتدائي'), ('appeal', 'استئنافي'),
    ('cassation', 'نقض'), ('constitutional', 'دستوري'),
]
JUDGMENT_RESULTS = [
    ('full_win', 'كسب كامل'), ('partial_win', 'كسب جزئي'), ('loss', 'خسارة'),
    ('postponement', 'تأجيل'), ('procedural', 'شكلي'), ('absence', 'غيابي'),
]
APPEAL_DAYS = {'primary': 40, 'appeal': 60, 'cassation': 60}


@judgments_bp.route('/')
@permission_required('judgments', 'view')
def index():
    """List all judgments with filters."""
    page = request.args.get('page', 1, type=int)
    case_id = request.args.get('case_id', '', type=str)
    result = request.args.get('result', '')

    query = Judgment.query.filter_by(tenant_id=g.tenant_id)
    if case_id:
        query = query.filter_by(case_id=int(case_id))
    if result:
        query = query.filter_by(result=result)

    judgments = query.order_by(Judgment.judgment_date.desc()).paginate(page=page, per_page=20)
    return render_template('judgments/index.html', judgments=judgments, case_id=case_id,
                           result=result, judgment_results=JUDGMENT_RESULTS)


@judgments_bp.route('/create', methods=['GET', 'POST'])
@permission_required('judgments', 'create')
def create():
    """Record a new judgment."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['active', 'awaiting_judgment'])
    ).order_by(Case.case_number).all()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()

    if request.method == 'POST':
        errors = []
        case_id = request.form.get('case_id', type=int)
        judgment_date_str = request.form.get('judgment_date', '')
        judgment_type = request.form.get('judgment_type', '')
        result = request.form.get('result', '')

        if not case_id:
            errors.append('يجب اختيار القضية')
        if not judgment_date_str:
            errors.append('تاريخ الحكم مطلوب')
        if not judgment_type:
            errors.append('نوع الحكم مطلوب')
        if not result:
            errors.append('نتيجة الحكم مطلوبة')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('judgments/create.html', cases=cases, courts=courts,
                                   form=request.form, judgment_types=JUDGMENT_TYPES,
                                   judgment_results=JUDGMENT_RESULTS)

        judgment_date = datetime.strptime(judgment_date_str, '%Y-%m-%d').date()

        # Auto-calculate appeal deadline
        appeal_deadline = None
        appeal_tracking = request.form.get('appeal_tracking_enabled') == 'yes'
        if appeal_tracking:
            days = APPEAL_DAYS.get(judgment_type, 40)
            appeal_deadline = judgment_date + timedelta(days=days)
            # Allow manual override
            if request.form.get('appeal_deadline'):
                appeal_deadline = datetime.strptime(request.form['appeal_deadline'], '%Y-%m-%d').date()

        judgment = Judgment(
            tenant_id=g.tenant_id,
            case_id=case_id,
            judgment_date=judgment_date,
            court_id=request.form.get('court_id', type=int) or None,
            judgment_type=judgment_type,
            result=result,
            judgment_text=request.form.get('judgment_text', '').strip() or None,
            judge_name=request.form.get('judge_name', '').strip() or None,
            awarded_amount=request.form.get('awarded_amount', type=float) or None,
            notes=request.form.get('notes', '').strip() or None,
            appeal_tracking_enabled=appeal_tracking,
            appeal_type=judgment_type,
            appeal_deadline=appeal_deadline,
        )
        db.session.add(judgment)

        # Update case status
        case = Case.query.get(case_id)
        if case:
            case.status = 'awaiting_judgment' if result in ('postponement',) else 'closed' if judgment_type == 'cassation' else case.status

        db.session.commit()
        flash('تم تسجيل الحكم بنجاح', 'success')
        return redirect(url_for('judgments.show', id=judgment.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('judgments/create.html', cases=cases, courts=courts,
                           form=request.args, judgment_types=JUDGMENT_TYPES,
                           judgment_results=JUDGMENT_RESULTS, pre_case_id=pre_case)


@judgments_bp.route('/<int:id>')
@permission_required('judgments', 'view')
def show(id):
    """Show judgment details with appeal tracking."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    type_map = dict(JUDGMENT_TYPES)
    result_map = dict(JUDGMENT_RESULTS)

    # Calculate days until appeal deadline
    days_until_appeal = None
    if judgment.appeal_deadline:
        days_until_appeal = (judgment.appeal_deadline - datetime.utcnow().date()).days

    return render_template('judgments/show.html', judgment=judgment, type_map=type_map,
                           result_map=result_map, days_until_appeal=days_until_appeal)


@judgments_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('judgments', 'edit')
def edit(id):
    """Edit judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()

    if request.method == 'POST':
        judgment.judgment_date = datetime.strptime(request.form['judgment_date'], '%Y-%m-%d').date()
        judgment.court_id = request.form.get('court_id', type=int) or None
        judgment.judgment_type = request.form.get('judgment_type', judgment.judgment_type)
        judgment.result = request.form.get('result', judgment.result)
        judgment.judgment_text = request.form.get('judgment_text', '').strip() or None
        judgment.judge_name = request.form.get('judge_name', '').strip() or None
        judgment.awarded_amount = request.form.get('awarded_amount', type=float) or None
        judgment.notes = request.form.get('notes', '').strip() or None

        if request.form.get('appeal_deadline'):
            judgment.appeal_deadline = datetime.strptime(request.form['appeal_deadline'], '%Y-%m-%d').date()
            judgment.appeal_tracking_enabled = True

        db.session.commit()
        flash('تم تحديث الحكم بنجاح', 'success')
        return redirect(url_for('judgments.show', id=judgment.id))

    return render_template('judgments/edit.html', judgment=judgment, courts=courts,
                           judgment_types=JUDGMENT_TYPES, judgment_results=JUDGMENT_RESULTS)


@judgments_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('judgments', 'delete')
def delete(id):
    """Delete a judgment."""
    judgment = Judgment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    case_id = judgment.case_id
    db.session.delete(judgment)
    db.session.commit()
    flash('تم حذف الحكم', 'warning')
    return redirect(url_for('cases.show', id=case_id))
