"""Manual income entries for the internal books.

Per user direction: subscription income is tracked separately in the existing
billing module. This is a manual ledger feeding the finance dashboard's
صافي (net) calculation.
"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required
from app.admin.finance.audit import log_finance_action
from app.models.op_finance import OpIncome


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


@admin_bp.route('/finance/income')
@super_admin_required
def finance_income_list():
    incomes = OpIncome.query.order_by(OpIncome.income_date.desc(), OpIncome.id.desc()).all()
    total = sum(float(i.amount or 0) for i in incomes)
    return render_template('admin/finance/income/list.html', incomes=incomes, total=total)


@admin_bp.route('/finance/income/new', methods=['POST'])
@super_admin_required
def finance_income_create():
    try:
        income = OpIncome(
            income_date=_parse_date(request.form['income_date']),
            source_label=request.form['source_label'].strip(),
            amount=request.form['amount'],
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin_id=g.current_admin.id,
        )
        db.session.add(income)
        db.session.flush()
        log_finance_action(
            action_type='CREATE', entity_type='OpIncome', entity_id=income.id,
            new_value={'source': income.source_label, 'amount': float(income.amount), 'date': str(income.income_date)},
            description=f'إيراد: {income.source_label} — {income.amount} ج.م',
        )
        db.session.commit()
        flash(f'تم تسجيل إيراد {income.amount} ج.م من {income.source_label}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر التسجيل: {e}', 'danger')
    return redirect(url_for('admin.finance_income_list'))


@admin_bp.route('/finance/income/<int:income_id>/delete', methods=['POST'])
@super_admin_required
def finance_income_delete(income_id):
    income = OpIncome.query.get_or_404(income_id)
    label = income.source_label
    amount = income.amount
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpIncome', entity_id=income.id,
            old_value={'source': label, 'amount': float(amount), 'date': str(income.income_date)},
            description=f'حذف إيراد: {label} — {amount} ج.م',
        )
        db.session.delete(income)
        db.session.commit()
        flash('تم حذف الإيراد', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_income_list'))
