"""Payroll Payments + Payroll Summary.

Per PDF §3.2: each row is one payment. Employee selected from dropdown
sourced by Employees — never typed manually.

Per PDF §3.3: summary is read-only and entirely computed from Employees +
PayrollPayments via @property helpers on OpEmployee.
"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required
from app.admin.finance.audit import log_finance_action
from app.models.op_finance import OpEmployee, OpPayrollPayment


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


@admin_bp.route('/finance/payroll')
@super_admin_required
def finance_payroll_payments():
    """List all payroll payments + add-payment form."""
    payments = (
        OpPayrollPayment.query
        .order_by(OpPayrollPayment.payment_date.desc(), OpPayrollPayment.id.desc())
        .all()
    )
    # Only show active/paused employees in dropdown — terminated stay hidden by default
    employees = (
        OpEmployee.query
        .filter(OpEmployee.status != 'terminated')
        .order_by(OpEmployee.full_name)
        .all()
    )
    return render_template(
        'admin/finance/payroll/payments.html',
        payments=payments,
        employees=employees,
    )


@admin_bp.route('/finance/payroll/new', methods=['POST'])
@super_admin_required
def finance_payroll_create():
    try:
        emp_id = int(request.form['employee_id'])
        # Ensure the employee exists (defensive — stops form-tampering attempts)
        emp = OpEmployee.query.get_or_404(emp_id)
        payment = OpPayrollPayment(
            employee_id=emp.id,
            payment_date=_parse_date(request.form['payment_date']),
            amount=request.form['amount'],
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin_id=g.current_admin.id,
        )
        db.session.add(payment)
        db.session.flush()
        log_finance_action(
            action_type='CREATE',
            entity_type='OpPayrollPayment',
            entity_id=payment.id,
            new_value={'employee': emp.full_name, 'amount': float(payment.amount), 'date': str(payment.payment_date)},
            description=f'دفعة راتب: {emp.full_name} — {payment.amount} ج.م',
        )
        db.session.commit()
        flash(f'تم تسجيل دفعة {payment.amount} ج.م لـ {emp.full_name}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر تسجيل الدفعة: {e}', 'danger')
    return redirect(url_for('admin.finance_payroll_payments'))


@admin_bp.route('/finance/payroll/<int:payment_id>/delete', methods=['POST'])
@super_admin_required
def finance_payroll_delete(payment_id):
    payment = OpPayrollPayment.query.get_or_404(payment_id)
    emp_name = payment.employee.full_name if payment.employee else '—'
    amount = payment.amount
    try:
        log_finance_action(
            action_type='DELETE',
            entity_type='OpPayrollPayment',
            entity_id=payment.id,
            old_value={'employee': emp_name, 'amount': float(amount), 'date': str(payment.payment_date)},
            description=f'حذف دفعة راتب: {emp_name} — {amount} ج.م',
        )
        db.session.delete(payment)
        db.session.commit()
        flash('تم حذف الدفعة', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_payroll_payments'))


@admin_bp.route('/finance/payroll/summary')
@super_admin_required
def finance_payroll_summary():
    """Read-only computed table — one row per employee."""
    employees = OpEmployee.query.order_by(OpEmployee.full_name).all()
    rows = []
    totals = {'due': 0.0, 'paid': 0.0, 'balance': 0.0}
    for emp in employees:
        due = emp.total_due
        paid = emp.total_paid
        balance = emp.balance
        totals['due'] += due
        totals['paid'] += paid
        totals['balance'] += balance
        rows.append({
            'employee': emp,
            'due': due,
            'paid': paid,
            'balance': balance,
            'count': emp.payment_count,
            'last_date': emp.last_payment_date,
        })
    return render_template(
        'admin/finance/payroll/summary.html',
        rows=rows,
        totals=totals,
    )
