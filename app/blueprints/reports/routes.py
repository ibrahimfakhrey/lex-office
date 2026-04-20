"""Reports and analytics routes."""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, g
from sqlalchemy import func, extract
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.utils.helpers import egypt_today
from app.models.case import Case
from app.models.session import Session
from app.models.judgment import Judgment
from app.models.financial import Payment, Invoice, Expense
from app.models.task import Task
from app.models.user import User

reports_bp = Blueprint('reports', __name__, template_folder='../../templates/reports')


@reports_bp.route('/')
@permission_required('reports', 'view')
def index():
    """Reports dashboard with quick stats."""
    today = egypt_today()

    total_cases = Case.query.filter_by(tenant_id=g.tenant_id).count()
    active_cases = Case.query.filter_by(tenant_id=g.tenant_id).filter(
        Case.status.in_(['new', 'active'])).count()
    total_clients = db.session.query(func.count(func.distinct(Case.client_id))).filter(
        Case.tenant_id == g.tenant_id).scalar()

    total_income = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.tenant_id == g.tenant_id).scalar())
    total_expenses = float(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.tenant_id == g.tenant_id).scalar())

    pending_tasks = Task.query.filter_by(tenant_id=g.tenant_id).filter(
        Task.status.notin_(['done', 'cancelled'])).count()

    upcoming_sessions = Session.query.filter_by(tenant_id=g.tenant_id).filter(
        Session.session_date >= today, Session.result.is_(None)).count()

    return render_template('reports/index.html',
                           total_cases=total_cases, active_cases=active_cases,
                           total_clients=total_clients, total_income=total_income,
                           total_expenses=total_expenses, pending_tasks=pending_tasks,
                           upcoming_sessions=upcoming_sessions)


@reports_bp.route('/financial')
@permission_required('reports', 'view')
def financial():
    """Financial report: income, expenses, profit by period."""
    date_from = request.args.get('date_from', (egypt_today().replace(day=1)).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', egypt_today().strftime('%Y-%m-%d'))

    start = datetime.strptime(date_from, '%Y-%m-%d').date()
    end = datetime.strptime(date_to, '%Y-%m-%d').date()

    payments = Payment.query.filter(
        Payment.tenant_id == g.tenant_id,
        Payment.payment_date >= start, Payment.payment_date <= end
    ).order_by(Payment.payment_date.desc()).all()

    expenses = Expense.query.filter(
        Expense.tenant_id == g.tenant_id,
        Expense.expense_date >= start, Expense.expense_date <= end
    ).order_by(Expense.expense_date.desc()).all()

    total_income = sum(float(p.amount) for p in payments)
    total_expenses = sum(float(e.amount) for e in expenses)
    net_profit = total_income - total_expenses

    # Payment method breakdown
    method_breakdown = db.session.query(
        Payment.payment_method, func.sum(Payment.amount)
    ).filter(
        Payment.tenant_id == g.tenant_id,
        Payment.payment_date >= start, Payment.payment_date <= end
    ).group_by(Payment.payment_method).all()

    # Expense type breakdown
    expense_breakdown = db.session.query(
        Expense.expense_type, func.sum(Expense.amount)
    ).filter(
        Expense.tenant_id == g.tenant_id,
        Expense.expense_date >= start, Expense.expense_date <= end
    ).group_by(Expense.expense_type).all()

    return render_template('reports/financial.html',
                           payments=payments, expenses=expenses,
                           total_income=total_income, total_expenses=total_expenses,
                           net_profit=net_profit,
                           method_breakdown=method_breakdown,
                           expense_breakdown=expense_breakdown,
                           date_from=date_from, date_to=date_to)


@reports_bp.route('/performance')
@permission_required('reports', 'view')
def performance():
    """Lawyer performance report."""
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    perf_data = []
    for lawyer in lawyers:
        cases_count = Case.query.filter_by(
            responsible_lawyer_id=lawyer.id, tenant_id=g.tenant_id).count()
        active_cases = Case.query.filter_by(
            responsible_lawyer_id=lawyer.id, tenant_id=g.tenant_id
        ).filter(Case.status.in_(['new', 'active'])).count()

        sessions_count = Session.query.filter_by(
            responsible_lawyer_id=lawyer.id, tenant_id=g.tenant_id).count()

        tasks_done = Task.query.filter_by(
            assigned_to=lawyer.id, tenant_id=g.tenant_id, status='done').count()
        tasks_total = Task.query.filter_by(
            assigned_to=lawyer.id, tenant_id=g.tenant_id).count()

        perf_data.append({
            'lawyer': lawyer,
            'cases_total': cases_count,
            'active_cases': active_cases,
            'sessions': sessions_count,
            'tasks_done': tasks_done,
            'tasks_total': tasks_total,
            'completion_rate': round(tasks_done / tasks_total * 100) if tasks_total > 0 else 0,
        })

    return render_template('reports/performance.html', perf_data=perf_data)


@reports_bp.route('/workload')
@permission_required('reports', 'view')
def workload():
    """Team workload distribution."""
    lawyers = User.query.filter_by(tenant_id=g.tenant_id, is_active=True).all()

    workload_data = []
    for lawyer in lawyers:
        active_cases = Case.query.filter_by(
            responsible_lawyer_id=lawyer.id, tenant_id=g.tenant_id
        ).filter(Case.status.in_(['new', 'active'])).count()

        pending_tasks = Task.query.filter_by(
            assigned_to=lawyer.id, tenant_id=g.tenant_id
        ).filter(Task.status.notin_(['done', 'cancelled'])).count()

        upcoming_sessions = Session.query.filter_by(
            responsible_lawyer_id=lawyer.id, tenant_id=g.tenant_id
        ).filter(Session.session_date >= egypt_today(), Session.result.is_(None)).count()

        workload_data.append({
            'lawyer': lawyer,
            'active_cases': active_cases,
            'pending_tasks': pending_tasks,
            'upcoming_sessions': upcoming_sessions,
            'total_load': active_cases + pending_tasks + upcoming_sessions,
        })

    workload_data.sort(key=lambda x: x['total_load'], reverse=True)
    return render_template('reports/workload.html', workload_data=workload_data)


@reports_bp.route('/sessions')
@permission_required('reports', 'view')
def sessions_report():
    """Sessions report with results breakdown."""
    date_from = request.args.get('date_from', (egypt_today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', egypt_today().strftime('%Y-%m-%d'))

    start = datetime.strptime(date_from, '%Y-%m-%d').date()
    end = datetime.strptime(date_to, '%Y-%m-%d').date()

    sessions = Session.query.filter(
        Session.tenant_id == g.tenant_id,
        Session.session_date >= start, Session.session_date <= end
    ).order_by(Session.session_date.desc()).all()

    total = len(sessions)
    completed = sum(1 for s in sessions if s.result)
    pending = total - completed

    # Result breakdown
    result_counts = db.session.query(
        Session.result, func.count(Session.id)
    ).filter(
        Session.tenant_id == g.tenant_id,
        Session.session_date >= start, Session.session_date <= end,
        Session.result.isnot(None)
    ).group_by(Session.result).all()

    return render_template('reports/sessions_report.html',
                           sessions=sessions, total=total,
                           completed=completed, pending=pending,
                           result_counts=result_counts,
                           date_from=date_from, date_to=date_to)
