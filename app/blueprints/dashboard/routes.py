"""Dashboard routes: Main overview with statistics and alerts."""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, g
from app.extensions import db
from app.utils.decorators import login_required, role_required, permission_required, manager_only
from app.models.case import Case
from app.models.session import Session
from app.models.task import Task, Appointment
from app.models.notification import Notification
from app.models.client import Client
from app.models.financial import Payment, Invoice, Expense

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard with statistics and upcoming items."""
    today = date.today()
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

    # Urgent tasks (due within 48 hours)
    urgent_deadline = datetime.utcnow() + timedelta(hours=48)
    urgent_tasks = Task.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Task.status != 'done',
        Task.deadline <= urgent_deadline,
        Task.deadline >= datetime.utcnow()
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

    # Sessions without recorded results
    pending_results = Session.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(
        Session.session_date < today,
        Session.result.is_(None)
    ).count()

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
                           pending_results=pending_results)
