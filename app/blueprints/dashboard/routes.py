"""Dashboard routes: Main overview with statistics and alerts."""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, g
from app.extensions import db
from app.utils.decorators import login_required, role_required, permission_required, manager_only
from app.utils.helpers import egypt_today
from app.models.case import Case
from app.models.session import Session
from app.models.task import Task, Appointment
from app.models.notification import Notification
from app.models.client import Client
from app.models.financial import Payment, Invoice, Expense
from app.models.power_of_attorney import PowerOfAttorney

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard with statistics and upcoming items."""
    today = egypt_today()
    tomorrow = today + timedelta(days=1)
    week_ahead = today + timedelta(days=7)

    # Active cases count
    active_cases_count = Case.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(Case.status.in_(['new', 'active', 'in_progress'])).count()

    # Today's sessions
    today_sessions = Session.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(Session.session_date == today).order_by(Session.session_time).all()

    # Upcoming sessions (next 7 days)
    upcoming_sessions = Session.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Session.session_date > today,
        Session.session_date <= week_ahead
    ).order_by(Session.session_date, Session.session_time).all()

    # Overdue tasks
    overdue_tasks = Task.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Task.status != 'done',
        Task.deadline < datetime.utcnow()
    ).order_by(Task.deadline).all()

    # Urgent tasks. General tasks surface within 48h of deadline; session
    # reminders (Task.session_id IS NOT NULL) get a 14-day window so the
    # lawyer sees upcoming court sessions on the dashboard, not just the
    # day before. Both buckets exclude done tasks.
    now = datetime.utcnow()
    urgent_deadline = now + timedelta(hours=48)
    session_horizon = now + timedelta(days=14)
    urgent_tasks = Task.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Task.status != 'done',
        Task.deadline >= now,
        db.or_(
            Task.deadline <= urgent_deadline,
            db.and_(Task.session_id.isnot(None), Task.deadline <= session_horizon),
        ),
    ).order_by(Task.deadline).all()

    # Unread notifications
    unread_notifications = Notification.query.filter_by(
        tenant_id=g.tenant_id,
        user_id=g.current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()

    # Total clients
    total_clients = Client.query.filter_by(tenant_id=g.tenant_id).count()

    # Today's appointments
    today_appointments = Appointment.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(Appointment.appointment_date == today).order_by(Appointment.appointment_time).all()

    # Financial summary (current month)
    month_start = today.replace(day=1)
    monthly_payments = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(
        Payment.tenant_id == g.tenant_id,
        Payment.payment_date >= month_start
    ).scalar()

    monthly_expenses = db.session.query(
        db.func.coalesce(db.func.sum(Expense.amount), 0)
    ).filter(
        Expense.tenant_id == g.tenant_id,
        Expense.expense_date >= month_start
    ).scalar()

    # POAs expiring within 30 days or already expired (for alerts)
    expiring_poas = PowerOfAttorney.query.filter_by(tenant_id=g.tenant_id).filter(
        PowerOfAttorney.expiry_date.isnot(None),
        PowerOfAttorney.expiry_date <= today + timedelta(days=30),
    ).order_by(PowerOfAttorney.expiry_date).limit(5).all()

    # Sessions without recorded results
    pending_results = Session.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Session.session_date < today,
        Session.result.is_(None)
    ).count()

    # ── Premium dashboard extras ───────────────────────────────────────────

    # Cases by status — drives the donut chart
    status_rows = (
        db.session.query(Case.status, db.func.count(Case.id))
        .filter(Case.tenant_id == g.tenant_id)
        .group_by(Case.status)
        .all()
    )
    cases_by_status = {row[0]: row[1] for row in status_rows}
    total_cases = sum(cases_by_status.values())

    # Recent cases (last 5 by updated_at)
    recent_cases = (
        Case.query.filter_by(tenant_id=g.tenant_id)
        .order_by(Case.updated_at.desc())
        .limit(5).all()
    )

    # Team — active users in this tenant with case-counts
    from app.models.user import User
    team_rows = (
        db.session.query(
            User,
            db.func.count(Case.id).label('case_count'),
        )
        .outerjoin(Case, db.and_(
            Case.responsible_lawyer_id == User.id,
            Case.tenant_id == g.tenant_id,
        ))
        .filter(User.tenant_id == g.tenant_id, User.is_active.is_(True))
        .group_by(User.id)
        .order_by(db.desc('case_count'))
        .limit(6).all()
    )

    # Monthly outstanding dues (invoices issued, unpaid)
    monthly_dues = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total), 0)
    ).filter(
        Invoice.tenant_id == g.tenant_id,
        Invoice.issue_date >= month_start,
        Invoice.status.in_(['sent', 'overdue']),
    ).scalar()

    # Collection percentage (paid vs all issued this month)
    invoiced_total = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total), 0)
    ).filter(
        Invoice.tenant_id == g.tenant_id,
        Invoice.issue_date >= month_start,
        Invoice.status != 'cancelled',
    ).scalar() or 0
    collection_pct = round(
        100 * float(monthly_payments or 0) / float(invoiced_total),
        0,
    ) if invoiced_total else 0

    # Upcoming appeal-deadline alerts (judgments tracking appeals)
    from app.models.judgment import Judgment
    appeal_alerts = Judgment.query.filter_by(
        tenant_id=g.tenant_id,
    ).filter(
        Judgment.appeal_tracking_enabled.is_(True),
        Judgment.appeal_deadline.isnot(None),
        Judgment.appeal_deadline >= today,
        Judgment.appeal_deadline <= today + timedelta(days=14),
    ).order_by(Judgment.appeal_deadline).limit(5).all()

    return render_template('dashboard/index.html',
                           active_cases_count=active_cases_count,
                           today_sessions=today_sessions,
                           upcoming_sessions=upcoming_sessions,
                           overdue_tasks=overdue_tasks,
                           urgent_tasks=urgent_tasks,
                           unread_notifications=unread_notifications,
                           total_clients=total_clients,
                           today_appointments=today_appointments,
                           monthly_payments=monthly_payments,
                           monthly_expenses=monthly_expenses,
                           monthly_dues=monthly_dues,
                           collection_pct=collection_pct,
                           pending_results=pending_results,
                           expiring_poas=expiring_poas,
                           cases_by_status=cases_by_status,
                           total_cases=total_cases,
                           recent_cases=recent_cases,
                           team_rows=team_rows,
                           appeal_alerts=appeal_alerts,
                           today=today)
