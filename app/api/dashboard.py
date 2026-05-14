"""API Dashboard routes: Overview statistics and alerts."""
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import success_response, error_response, validation_error, paginated_response, get_json_or_form, parse_date
from app.extensions import db, limiter
from flask import g, request
from app.utils.helpers import egypt_today
from app.models.case import Case
from app.models.session import Session
from app.models.task import Task, Appointment
from app.models.notification import Notification
from app.models.client import Client
from app.models.financial import Payment, Expense
from app.models.power_of_attorney import PowerOfAttorney


# ---------- GET /dashboard ----------
@api_bp.route('/dashboard', methods=['GET'])
@api_permission_required('dashboard', 'view')
def api_dashboard():
    """Return all dashboard statistics as JSON."""
    today = egypt_today()
    tomorrow = today + timedelta(days=1)
    week_ahead = today + timedelta(days=7)

    # Active cases count
    active_cases_count = Case.query.filter_by(
        tenant_id=g.tenant_id
    ).filter(Case.status.in_(['new', 'active', 'in_progress'])).count()

    # Cases by status (for donut chart)
    status_rows = db.session.query(
        Case.status, db.func.count(Case.id)
    ).filter(Case.tenant_id == g.tenant_id).group_by(Case.status).all()
    _status_labels = {
        'new': 'جديدة', 'active': 'نشطة', 'in_progress': 'قيد النظر',
        'awaiting_judgment': 'منتظرة حكم', 'suspended': 'موقوفة',
        'closed': 'مغلقة',
    }
    cases_by_status = [
        {'status': r[0], 'label': _status_labels.get(r[0], r[0]), 'count': int(r[1])}
        for r in status_rows
    ]

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

    # POAs expiring within 30 days or already expired
    expiring_poas = PowerOfAttorney.query.filter_by(tenant_id=g.tenant_id).filter(
        PowerOfAttorney.expiry_date.isnot(None),
        PowerOfAttorney.expiry_date <= today + timedelta(days=30),
    ).order_by(PowerOfAttorney.expiry_date).limit(5).all()

    return success_response(data={
        'active_cases_count': active_cases_count,
        'cases_by_status': cases_by_status,
        'today_sessions': [s.to_dict() for s in today_sessions],
        'upcoming_sessions': [s.to_dict() for s in upcoming_sessions],
        'overdue_tasks': [t.to_dict() for t in overdue_tasks],
        'urgent_tasks': [t.to_dict() for t in urgent_tasks],
        'unread_notifications': [n.to_dict() for n in unread_notifications],
        'total_clients': total_clients,
        'today_appointments': [a.to_dict() for a in today_appointments],
        'monthly_payments': float(monthly_payments),
        'monthly_expenses': float(monthly_expenses),
        'pending_results': pending_results,
        'expiring_poas': [p.to_dict() for p in expiring_poas],
    })
