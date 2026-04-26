"""API routes for reports and analytics."""
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request
from sqlalchemy import func

from app.models.case import Case
from app.models.session import Session
from app.models.financial import Payment, Expense
from app.models.task import Task
from app.models.user import User
from app.utils.helpers import egypt_today


@api_bp.route('/reports', methods=['GET'])
@api_permission_required('reports', 'view')
def api_reports_overview():
    """Quick stats overview: cases, clients, financials, tasks, sessions."""
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

    return success_response(data={
        'total_cases': total_cases,
        'active_cases': active_cases,
        'total_clients': total_clients,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'pending_tasks': pending_tasks,
        'upcoming_sessions': upcoming_sessions,
    })


@api_bp.route('/reports/financial', methods=['GET'])
@api_permission_required('reports', 'view')
def api_reports_financial():
    """Financial report: income, expenses, profit by period."""
    today = egypt_today()
    date_from = request.args.get('date_from', today.replace(day=1).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', today.strftime('%Y-%m-%d'))

    start = parse_date(date_from) or today.replace(day=1)
    end = parse_date(date_to) or today

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
    method_breakdown_raw = db.session.query(
        Payment.payment_method, func.sum(Payment.amount)
    ).filter(
        Payment.tenant_id == g.tenant_id,
        Payment.payment_date >= start, Payment.payment_date <= end
    ).group_by(Payment.payment_method).all()
    method_breakdown = {m: float(a) for m, a in method_breakdown_raw}

    # Expense type breakdown
    expense_breakdown_raw = db.session.query(
        Expense.expense_type, func.sum(Expense.amount)
    ).filter(
        Expense.tenant_id == g.tenant_id,
        Expense.expense_date >= start, Expense.expense_date <= end
    ).group_by(Expense.expense_type).all()
    expense_breakdown = {t: float(a) for t, a in expense_breakdown_raw}

    return success_response(data={
        'date_from': start.isoformat(),
        'date_to': end.isoformat(),
        'payments': [p.to_dict() for p in payments],
        'expenses': [e.to_dict() for e in expenses],
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'method_breakdown': method_breakdown,
        'expense_breakdown': expense_breakdown,
    })


@api_bp.route('/reports/performance', methods=['GET'])
@api_permission_required('reports', 'view')
def api_reports_performance():
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
            'lawyer': lawyer.to_dict(),
            'cases_total': cases_count,
            'active_cases': active_cases,
            'sessions': sessions_count,
            'tasks_done': tasks_done,
            'tasks_total': tasks_total,
            'completion_rate': round(tasks_done / tasks_total * 100) if tasks_total > 0 else 0,
        })

    return success_response(data=perf_data)


@api_bp.route('/reports/workload', methods=['GET'])
@api_permission_required('reports', 'view')
def api_reports_workload():
    """Team workload distribution."""
    today = egypt_today()
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
        ).filter(Session.session_date >= today, Session.result.is_(None)).count()

        workload_data.append({
            'lawyer': lawyer.to_dict(),
            'active_cases': active_cases,
            'pending_tasks': pending_tasks,
            'upcoming_sessions': upcoming_sessions,
            'total_load': active_cases + pending_tasks + upcoming_sessions,
        })

    workload_data.sort(key=lambda x: x['total_load'], reverse=True)
    return success_response(data=workload_data)


@api_bp.route('/reports/sessions', methods=['GET'])
@api_permission_required('reports', 'view')
def api_reports_sessions():
    """Sessions report with results breakdown."""
    today = egypt_today()
    date_from = request.args.get('date_from', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', today.strftime('%Y-%m-%d'))

    start = parse_date(date_from) or (today - timedelta(days=30))
    end = parse_date(date_to) or today

    sessions = Session.query.filter(
        Session.tenant_id == g.tenant_id,
        Session.session_date >= start, Session.session_date <= end
    ).order_by(Session.session_date.desc()).all()

    total = len(sessions)
    completed = sum(1 for s in sessions if s.result)
    pending = total - completed

    # Result breakdown
    result_counts_raw = db.session.query(
        Session.result, func.count(Session.id)
    ).filter(
        Session.tenant_id == g.tenant_id,
        Session.session_date >= start, Session.session_date <= end,
        Session.result.isnot(None)
    ).group_by(Session.result).all()
    result_counts = {r: c for r, c in result_counts_raw}

    return success_response(data={
        'date_from': start.isoformat(),
        'date_to': end.isoformat(),
        'sessions': [s.to_dict() for s in sessions],
        'total': total,
        'completed': completed,
        'pending': pending,
        'result_counts': result_counts,
    })
