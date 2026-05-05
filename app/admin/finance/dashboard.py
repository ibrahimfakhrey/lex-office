"""Internal Finance Dashboard.

Per PDF §3.10 and §4.4:
  net = total_income - (payroll_balance + loan_balance + monthly_expenses)
Year/month filter applies only to expenses (per PDF rule). Payroll & loans
show full lifetime totals always. Income is filtered by date too so the net
number is meaningful for the chosen period.
"""
from datetime import date
from flask import render_template, request
from sqlalchemy import func, extract
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, admin_permission_required
from app.models.op_finance import (
    OpEmployee, OpLender, OpMonthlyExpense, OpIncome,
)


ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]


@admin_bp.route('/finance/dashboard')
@admin_permission_required('finance_dashboard', 'view')
def finance_dashboard():
    year_filter = request.args.get('year', type=int)
    month_filter = request.args.get('month', type=int)

    # ─── Payroll (lifetime — not affected by filter, per PDF) ───
    employees = OpEmployee.query.all()
    payroll_due = sum(e.total_due for e in employees)
    payroll_paid = sum(e.total_paid for e in employees)
    payroll_balance = sum(e.balance for e in employees)

    # ─── Loans (lifetime) ───
    lenders = OpLender.query.all()
    loan_original = sum(float(l.original_amount or 0) for l in lenders)
    loan_paid = sum(l.total_paid for l in lenders)
    loan_balance = sum(l.balance for l in lenders)

    # ─── Expenses (filtered) ───
    exp_q = db.session.query(func.coalesce(func.sum(OpMonthlyExpense.amount), 0))
    if year_filter:
        exp_q = exp_q.filter(OpMonthlyExpense.year == year_filter)
    if month_filter:
        exp_q = exp_q.filter(OpMonthlyExpense.month == month_filter)
    expenses_total = float(exp_q.scalar() or 0)

    # ─── Income (filtered by income_date year/month) ───
    inc_q = db.session.query(func.coalesce(func.sum(OpIncome.amount), 0))
    if year_filter:
        inc_q = inc_q.filter(extract('year', OpIncome.income_date) == year_filter)
    if month_filter:
        inc_q = inc_q.filter(extract('month', OpIncome.income_date) == month_filter)
    income_total = float(inc_q.scalar() or 0)

    # ─── Net (PDF §4.4): income − (payroll_balance + loan_balance + expenses) ───
    net = income_total - (payroll_balance + loan_balance + expenses_total)

    # Build year picker source from any year that has data
    expense_years = [r[0] for r in db.session.query(OpMonthlyExpense.year.distinct()).all()]
    income_years = [r[0] for r in db.session.query(extract('year', OpIncome.income_date).distinct()).all()]
    available_years = sorted({int(y) for y in expense_years + income_years if y is not None}, reverse=True)
    if not available_years:
        available_years = [date.today().year]

    return render_template(
        'admin/finance/dashboard.html',
        year_filter=year_filter,
        month_filter=month_filter,
        available_years=available_years,
        arabic_months=ARABIC_MONTHS,
        payroll={'due': payroll_due, 'paid': payroll_paid, 'balance': payroll_balance, 'count': len(employees)},
        loans={'original': loan_original, 'paid': loan_paid, 'balance': loan_balance, 'count': len(lenders)},
        expenses_total=expenses_total,
        income_total=income_total,
        net=net,
    )
