"""Court session management routes."""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.session import Session
from app.models.case import Case, Court
from app.models.user import User

sessions_bp = Blueprint('sessions', __name__, template_folder='../../templates/sessions')

SESSION_TYPES = [
    ('first', 'أولى'), ('evidence', 'إثبات'), ('pleading', 'مرافعة'),
    ('judgment', 'حكم'), ('emergency', 'طارئة'), ('postponement', 'تأجيل'),
]
SESSION_RESULTS = [
    ('postponed', 'تأجيل'), ('judgment', 'حكم'), ('decision', 'قرار'),
    ('evidence', 'إثبات'), ('attendance', 'حضور'), ('absence', 'غياب'),
]


@sessions_bp.route('/')
@permission_required('sessions', 'view')
def index():
    """List all sessions with filters."""
    page = request.args.get('page', 1, type=int)
    filter_date = request.args.get('date', '')
    status = request.args.get('status', '')
    case_id = request.args.get('case_id', '', type=str)

    query = Session.query.filter_by(tenant_id=g.tenant_id)
    if filter_date:
        query = query.filter(Session.session_date == filter_date)
    if status == 'pending':
        query = query.filter(Session.result.is_(None))
    elif status == 'completed':
        query = query.filter(Session.result.isnot(None))
    elif status == 'today':
        query = query.filter(Session.session_date == date.today())
    elif status == 'upcoming':
        query = query.filter(Session.session_date > date.today())
    if case_id:
        query = query.filter_by(case_id=int(case_id))

    sessions = query.order_by(Session.session_date.desc()).paginate(page=page, per_page=20)
    return render_template('sessions/index.html', sessions=sessions, filter_date=filter_date,
                           status=status, case_id=case_id, session_results=SESSION_RESULTS,
                           today=date.today())


@sessions_bp.route('/create', methods=['GET', 'POST'])
@permission_required('sessions', 'create')
def create():
    """Create a new court session."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active', 'awaiting_judgment'])
    ).order_by(Case.case_number).all()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    if request.method == 'POST':
        errors = []
        case_id = request.form.get('case_id', type=int)
        session_date = request.form.get('session_date', '')

        if not case_id:
            errors.append('يجب اختيار القضية')
        if not session_date:
            errors.append('تاريخ الجلسة مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('sessions/create.html', cases=cases, courts=courts,
                                   lawyers=lawyers, form=request.form,
                                   session_types=SESSION_TYPES)

        session_time = None
        if request.form.get('session_time'):
            session_time = datetime.strptime(request.form['session_time'], '%H:%M').time()

        sess = Session(
            tenant_id=g.tenant_id,
            case_id=case_id,
            session_date=datetime.strptime(session_date, '%Y-%m-%d').date(),
            session_time=session_time,
            court_id=request.form.get('court_id', type=int) or None,
            circuit=request.form.get('circuit', '').strip() or None,
            session_type=request.form.get('session_type', '') or None,
            preparation_notes=request.form.get('preparation_notes', '').strip() or None,
            responsible_lawyer_id=request.form.get('responsible_lawyer_id', type=int) or g.current_user.id,
        )
        db.session.add(sess)
        db.session.commit()

        flash('تم إضافة الجلسة بنجاح', 'success')
        return redirect(url_for('sessions.show', id=sess.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('sessions/create.html', cases=cases, courts=courts,
                           lawyers=lawyers, form=request.args, session_types=SESSION_TYPES,
                           pre_case_id=pre_case)


@sessions_bp.route('/<int:id>')
@permission_required('sessions', 'view')
def show(id):
    """Show session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    result_map = dict(SESSION_RESULTS)
    type_map = dict(SESSION_TYPES)
    return render_template('sessions/show.html', session=sess, result_map=result_map, type_map=type_map)


@sessions_bp.route('/<int:id>/record-result', methods=['GET', 'POST'])
@permission_required('sessions', 'edit')
def record_result(id):
    """Record session result and optionally schedule next session."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    if request.method == 'POST':
        sess.result = request.form.get('result', '')
        sess.result_summary = request.form.get('result_summary', '').strip() or None

        next_date = request.form.get('next_session_date', '')
        if next_date:
            sess.next_session_date = datetime.strptime(next_date, '%Y-%m-%d').date()

            # Auto-create next session
            if request.form.get('create_next') == 'yes':
                next_sess = Session(
                    tenant_id=g.tenant_id,
                    case_id=sess.case_id,
                    session_date=sess.next_session_date,
                    court_id=sess.court_id,
                    circuit=sess.circuit,
                    responsible_lawyer_id=sess.responsible_lawyer_id,
                )
                db.session.add(next_sess)

        db.session.commit()
        flash('تم تسجيل نتيجة الجلسة بنجاح', 'success')
        return redirect(url_for('sessions.show', id=sess.id))

    return render_template('sessions/record_result.html', session=sess, session_results=SESSION_RESULTS)


@sessions_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('sessions', 'edit')
def edit(id):
    """Edit session details."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    courts = Court.query.filter_by(is_active=True).order_by(Court.name).all()
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    if request.method == 'POST':
        sess.session_date = datetime.strptime(request.form['session_date'], '%Y-%m-%d').date()
        if request.form.get('session_time'):
            sess.session_time = datetime.strptime(request.form['session_time'], '%H:%M').time()
        sess.court_id = request.form.get('court_id', type=int) or None
        sess.circuit = request.form.get('circuit', '').strip() or None
        sess.session_type = request.form.get('session_type', '') or None
        sess.preparation_notes = request.form.get('preparation_notes', '').strip() or None
        sess.responsible_lawyer_id = request.form.get('responsible_lawyer_id', type=int) or sess.responsible_lawyer_id

        db.session.commit()
        flash('تم تحديث الجلسة بنجاح', 'success')
        return redirect(url_for('sessions.show', id=sess.id))

    return render_template('sessions/edit.html', session=sess, courts=courts,
                           lawyers=lawyers, session_types=SESSION_TYPES)


@sessions_bp.route('/<int:id>/delete', methods=['POST'])
@permission_required('sessions', 'delete')
def delete(id):
    """Delete a session."""
    sess = Session.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    case_id = sess.case_id
    db.session.delete(sess)
    db.session.commit()
    flash('تم حذف الجلسة', 'warning')
    return redirect(url_for('cases.show', id=case_id))


@sessions_bp.route('/calendar')
@permission_required('sessions', 'view')
def calendar():
    """Calendar view of sessions."""
    sessions = Session.query.filter_by(tenant_id=g.tenant_id).filter(
        Session.session_date >= date.today() - timedelta(days=30)
    ).order_by(Session.session_date).all()

    events = []
    for s in sessions:
        events.append({
            'id': s.id,
            'title': f'{s.case.case_number or "قضية"} - {dict(SESSION_TYPES).get(s.session_type, "")}',
            'date': s.session_date.isoformat(),
            'time': s.session_time.strftime('%H:%M') if s.session_time else None,
            'status': 'completed' if s.result else 'pending',
            'case_id': s.case_id,
        })
    return render_template('sessions/calendar.html', events=events, sessions=sessions)
