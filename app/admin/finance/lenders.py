"""Lenders + Loan Payments + Loan Summary.

Per PDF §3.4: each loan recorded once in Lenders. Per PDF §3.5: each payment
references a lender via dropdown. Summary is computed from both.
"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import (
    super_admin_required, admin_permission_required,
    apply_admin_scope, get_or_404_with_scope,
)
from app.admin.finance.audit import log_finance_action
from app.models.op_finance import OpLender, OpLoanPayment


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


# ─── Lenders CRUD ───
@admin_bp.route('/finance/lenders')
@admin_permission_required('finance_lenders', 'view')
def finance_lenders_list():
    lenders = apply_admin_scope(OpLender.query, OpLender).order_by(OpLender.created_at.desc()).all()
    return render_template('admin/finance/loans/lenders.html', lenders=lenders)


@admin_bp.route('/finance/lenders/new', methods=['POST'])
@admin_permission_required('finance_lenders', 'add')
def finance_lenders_create():
    try:
        lender = OpLender(
            lender_name=request.form['lender_name'].strip(),
            original_amount=request.form['original_amount'],
            loan_date=_parse_date(request.form['loan_date']),
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin_id=g.current_admin.id,
        )
        db.session.add(lender)
        db.session.flush()
        log_finance_action(
            action_type='CREATE',
            entity_type='OpLender',
            entity_id=lender.id,
            new_value={'lender_name': lender.lender_name, 'amount': float(lender.original_amount)},
            description=f'إضافة قرض من: {lender.lender_name}',
        )
        db.session.commit()
        flash(f'تم إضافة القرض من "{lender.lender_name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الإضافة: {e}', 'danger')
    return redirect(url_for('admin.finance_lenders_list'))


@admin_bp.route('/finance/lenders/<int:lender_id>/edit', methods=['POST'])
@admin_permission_required('finance_lenders', 'edit')
def finance_lenders_edit(lender_id):
    lender = get_or_404_with_scope(OpLender, lender_id)
    try:
        old = {'lender_name': lender.lender_name, 'amount': float(lender.original_amount)}
        lender.lender_name = request.form['lender_name'].strip()
        lender.original_amount = request.form['original_amount']
        lender.loan_date = _parse_date(request.form['loan_date'])
        lender.notes = (request.form.get('notes') or '').strip() or None
        log_finance_action(
            action_type='UPDATE', entity_type='OpLender', entity_id=lender.id,
            old_value=old,
            new_value={'lender_name': lender.lender_name, 'amount': float(lender.original_amount)},
            description=f'تعديل قرض: {lender.lender_name}',
        )
        db.session.commit()
        flash('تم حفظ التعديلات', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر التعديل: {e}', 'danger')
    return redirect(url_for('admin.finance_lenders_list'))


@admin_bp.route('/finance/lenders/<int:lender_id>/delete', methods=['POST'])
@admin_permission_required('finance_lenders', 'delete')
def finance_lenders_delete(lender_id):
    lender = get_or_404_with_scope(OpLender, lender_id)
    name = lender.lender_name
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpLender', entity_id=lender.id,
            old_value={'lender_name': name},
            description=f'حذف قرض: {name}',
        )
        db.session.delete(lender)
        db.session.commit()
        flash(f'تم حذف القرض من "{name}" وكل دفعاته', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_lenders_list'))


# ─── Loan Payments ───
@admin_bp.route('/finance/loans/payments')
@admin_permission_required('finance_lenders', 'view')
def finance_loan_payments():
    # Scope payments by their parent lender's ownership
    visible_lender_ids = [l.id for l in apply_admin_scope(OpLender.query, OpLender).all()]
    payments = (
        OpLoanPayment.query
        .filter(OpLoanPayment.lender_id.in_(visible_lender_ids))
        .order_by(OpLoanPayment.payment_date.desc(), OpLoanPayment.id.desc())
        .all()
    )
    lenders = apply_admin_scope(OpLender.query, OpLender).order_by(OpLender.lender_name).all()
    return render_template(
        'admin/finance/loans/payments.html',
        payments=payments, lenders=lenders,
    )


@admin_bp.route('/finance/loans/payments/new', methods=['POST'])
@admin_permission_required('finance_lenders', 'add')
def finance_loan_payments_create():
    try:
        lender_id = int(request.form['lender_id'])
        lender = get_or_404_with_scope(OpLender, lender_id)
        payment = OpLoanPayment(
            lender_id=lender.id,
            payment_date=_parse_date(request.form['payment_date']),
            amount=request.form['amount'],
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin_id=g.current_admin.id,
        )
        db.session.add(payment)
        db.session.flush()
        log_finance_action(
            action_type='CREATE', entity_type='OpLoanPayment', entity_id=payment.id,
            new_value={'lender': lender.lender_name, 'amount': float(payment.amount), 'date': str(payment.payment_date)},
            description=f'دفعة قرض: {lender.lender_name} — {payment.amount} ج.م',
        )
        db.session.commit()
        flash(f'تم تسجيل دفعة {payment.amount} ج.م لـ {lender.lender_name}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر تسجيل الدفعة: {e}', 'danger')
    return redirect(url_for('admin.finance_loan_payments'))


@admin_bp.route('/finance/loans/payments/<int:payment_id>/delete', methods=['POST'])
@admin_permission_required('finance_lenders', 'delete')
def finance_loan_payments_delete(payment_id):
    payment = OpLoanPayment.query.get_or_404(payment_id)
    # Enforce scope via the parent lender — if you can't see the lender, you can't delete its payments
    if g.get('current_scope') == 'own' and payment.lender and payment.lender.created_by_admin_id != g.current_admin.id:
        from flask import abort
        abort(404)
    lender_name = payment.lender.lender_name if payment.lender else '—'
    amount = payment.amount
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpLoanPayment', entity_id=payment.id,
            old_value={'lender': lender_name, 'amount': float(amount), 'date': str(payment.payment_date)},
            description=f'حذف دفعة قرض: {lender_name} — {amount} ج.م',
        )
        db.session.delete(payment)
        db.session.commit()
        flash('تم حذف الدفعة', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_loan_payments'))


# ─── Loan Summary (read-only computed) ───
@admin_bp.route('/finance/loans/summary')
@admin_permission_required('finance_lenders', 'view')
def finance_loans_summary():
    lenders = apply_admin_scope(OpLender.query, OpLender).order_by(OpLender.lender_name).all()
    rows = []
    totals = {'original': 0.0, 'paid': 0.0, 'balance': 0.0}
    for lender in lenders:
        original = float(lender.original_amount or 0)
        paid = lender.total_paid
        balance = lender.balance
        totals['original'] += original
        totals['paid'] += paid
        totals['balance'] += balance
        rows.append({
            'lender': lender,
            'original': original,
            'paid': paid,
            'balance': balance,
            'count': lender.payment_count,
            'last_date': lender.last_payment_date,
        })
    return render_template('admin/finance/loans/summary.html', rows=rows, totals=totals)
