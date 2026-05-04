"""Expense Categories + Monthly Log + Summary + Fixed Expenses.

PDF §3.6: each (category, item) pair recorded once in Categories.
PDF §3.7: each actual payment recorded as one row in Monthly Log; year+month required.
PDF §3.8: summary rolls up Monthly Log per item with year/month filter.
PDF §3.9: fixed expenses are reference-only (no math).
"""
from datetime import datetime, date
from collections import defaultdict
from flask import render_template, request, redirect, url_for, flash, g
from sqlalchemy import func
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required
from app.admin.finance.audit import log_finance_action
from app.models.op_finance import OpExpenseCategory, OpMonthlyExpense, OpFixedExpense


RECURRENCE_OPTIONS = [
    ('monthly', 'شهري'),
    ('yearly', 'سنوي'),
    ('lifetime', 'مدى الحياة'),
]
ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


# ─── Categories ───
@admin_bp.route('/finance/expenses/categories')
@super_admin_required
def finance_expense_categories():
    cats = OpExpenseCategory.query.order_by(
        OpExpenseCategory.category_name, OpExpenseCategory.item_name
    ).all()
    grouped = defaultdict(list)
    for c in cats:
        grouped[c.category_name].append(c)
    return render_template('admin/finance/expenses/categories.html', grouped=grouped)


@admin_bp.route('/finance/expenses/categories/new', methods=['POST'])
@super_admin_required
def finance_expense_categories_create():
    try:
        cat = OpExpenseCategory(
            category_name=request.form['category_name'].strip(),
            item_name=request.form['item_name'].strip(),
            notes=(request.form.get('notes') or '').strip() or None,
        )
        db.session.add(cat)
        db.session.flush()
        log_finance_action(
            action_type='CREATE', entity_type='OpExpenseCategory', entity_id=cat.id,
            new_value={'category': cat.category_name, 'item': cat.item_name},
            description=f'إضافة بند: {cat.display_label}',
        )
        db.session.commit()
        flash(f'تم إضافة "{cat.display_label}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الإضافة: {e}', 'danger')
    return redirect(url_for('admin.finance_expense_categories'))


@admin_bp.route('/finance/expenses/categories/<int:cat_id>/delete', methods=['POST'])
@super_admin_required
def finance_expense_categories_delete(cat_id):
    cat = OpExpenseCategory.query.get_or_404(cat_id)
    label = cat.display_label
    in_use = OpMonthlyExpense.query.filter_by(category_id=cat.id).count()
    if in_use:
        flash(f'لا يمكن الحذف — البند مستخدم في {in_use} مصروف(ات) شهرية. احذفها أولاً.', 'danger')
        return redirect(url_for('admin.finance_expense_categories'))
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpExpenseCategory', entity_id=cat.id,
            old_value={'category': cat.category_name, 'item': cat.item_name},
            description=f'حذف بند: {label}',
        )
        db.session.delete(cat)
        db.session.commit()
        flash(f'تم حذف "{label}"', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_expense_categories'))


# ─── Monthly Log ───
@admin_bp.route('/finance/expenses/monthly')
@super_admin_required
def finance_monthly_expenses():
    year_filter = request.args.get('year', type=int)
    month_filter = request.args.get('month', type=int)

    q = OpMonthlyExpense.query
    if year_filter:
        q = q.filter(OpMonthlyExpense.year == year_filter)
    if month_filter:
        q = q.filter(OpMonthlyExpense.month == month_filter)
    expenses = q.order_by(
        OpMonthlyExpense.year.desc(),
        OpMonthlyExpense.month.desc(),
        OpMonthlyExpense.id.desc(),
    ).all()

    categories = OpExpenseCategory.query.order_by(
        OpExpenseCategory.category_name, OpExpenseCategory.item_name
    ).all()

    available_years = [r[0] for r in db.session.query(
        OpMonthlyExpense.year.distinct()
    ).order_by(OpMonthlyExpense.year.desc()).all()]
    if not available_years:
        available_years = [date.today().year]

    return render_template(
        'admin/finance/expenses/monthly.html',
        expenses=expenses,
        categories=categories,
        available_years=available_years,
        arabic_months=ARABIC_MONTHS,
        year_filter=year_filter,
        month_filter=month_filter,
        current_year=date.today().year,
        current_month=date.today().month,
    )


@admin_bp.route('/finance/expenses/monthly/new', methods=['POST'])
@super_admin_required
def finance_monthly_expenses_create():
    try:
        cat = OpExpenseCategory.query.get_or_404(int(request.form['category_id']))
        exp = OpMonthlyExpense(
            year=int(request.form['year']),
            month=int(request.form['month']),
            category_id=cat.id,
            amount=request.form['amount'],
            payment_date=_parse_date(request.form.get('payment_date')),
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin_id=g.current_admin.id,
        )
        if not (1 <= exp.month <= 12):
            raise ValueError('الشهر يجب أن يكون بين 1 و 12')
        db.session.add(exp)
        db.session.flush()
        log_finance_action(
            action_type='CREATE', entity_type='OpMonthlyExpense', entity_id=exp.id,
            new_value={'category': cat.display_label, 'amount': float(exp.amount), 'year': exp.year, 'month': exp.month},
            description=f'مصروف {ARABIC_MONTHS[exp.month]} {exp.year}: {cat.display_label} — {exp.amount} ج.م',
        )
        db.session.commit()
        flash(f'تم تسجيل المصروف ({exp.amount} ج.م)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر التسجيل: {e}', 'danger')
    return redirect(url_for('admin.finance_monthly_expenses'))


@admin_bp.route('/finance/expenses/monthly/<int:exp_id>/delete', methods=['POST'])
@super_admin_required
def finance_monthly_expenses_delete(exp_id):
    exp = OpMonthlyExpense.query.get_or_404(exp_id)
    label = exp.category.display_label if exp.category else '—'
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpMonthlyExpense', entity_id=exp.id,
            old_value={'category': label, 'amount': float(exp.amount), 'year': exp.year, 'month': exp.month},
            description=f'حذف مصروف: {label} — {exp.amount} ج.م',
        )
        db.session.delete(exp)
        db.session.commit()
        flash('تم حذف المصروف', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_monthly_expenses'))


# ─── Expenses Summary ───
@admin_bp.route('/finance/expenses/summary')
@super_admin_required
def finance_expenses_summary():
    year_filter = request.args.get('year', type=int)
    month_filter = request.args.get('month', type=int)

    # Apply period filter inside the LEFT JOIN ON clause so categories with
    # no matching expenses still appear (count=0, total=0). PDF §3.8 requires
    # the count itself to reflect the period — a zero count is valid info.
    join_conds = [OpMonthlyExpense.category_id == OpExpenseCategory.id]
    if year_filter:
        join_conds.append(OpMonthlyExpense.year == year_filter)
    if month_filter:
        join_conds.append(OpMonthlyExpense.month == month_filter)

    q = db.session.query(
        OpExpenseCategory.id,
        OpExpenseCategory.category_name,
        OpExpenseCategory.item_name,
        func.count(OpMonthlyExpense.id).label('count'),
        func.coalesce(func.sum(OpMonthlyExpense.amount), 0).label('total'),
        func.max(OpMonthlyExpense.payment_date).label('last_date'),
    ).outerjoin(OpMonthlyExpense, db.and_(*join_conds))

    rows = q.group_by(
        OpExpenseCategory.id,
        OpExpenseCategory.category_name,
        OpExpenseCategory.item_name,
    ).order_by(
        OpExpenseCategory.category_name, OpExpenseCategory.item_name
    ).all()

    total_amount = sum(float(r.total or 0) for r in rows)

    available_years = [r[0] for r in db.session.query(
        OpMonthlyExpense.year.distinct()
    ).order_by(OpMonthlyExpense.year.desc()).all()]
    if not available_years:
        available_years = [date.today().year]

    return render_template(
        'admin/finance/expenses/summary.html',
        rows=rows,
        total_amount=total_amount,
        available_years=available_years,
        arabic_months=ARABIC_MONTHS,
        year_filter=year_filter,
        month_filter=month_filter,
    )


# ─── Fixed Expenses (reference only) ───
@admin_bp.route('/finance/expenses/fixed')
@super_admin_required
def finance_fixed_expenses():
    items = OpFixedExpense.query.order_by(OpFixedExpense.recurrence, OpFixedExpense.expense_name).all()
    return render_template(
        'admin/finance/expenses/fixed.html',
        items=items,
        recurrence_options=RECURRENCE_OPTIONS,
        arabic_months=ARABIC_MONTHS,
    )


@admin_bp.route('/finance/expenses/fixed/new', methods=['POST'])
@super_admin_required
def finance_fixed_expenses_create():
    try:
        item = OpFixedExpense(
            expense_name=request.form['expense_name'].strip(),
            estimated_amount=request.form.get('estimated_amount') or None,
            recurrence=request.form['recurrence'],
            month_if_yearly=int(request.form['month_if_yearly']) if request.form.get('month_if_yearly') else None,
            notes=(request.form.get('notes') or '').strip() or None,
        )
        db.session.add(item)
        db.session.flush()
        log_finance_action(
            action_type='CREATE', entity_type='OpFixedExpense', entity_id=item.id,
            new_value={'name': item.expense_name, 'recurrence': item.recurrence},
            description=f'إضافة مصروف ثابت: {item.expense_name}',
        )
        db.session.commit()
        flash(f'تم إضافة "{item.expense_name}" بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الإضافة: {e}', 'danger')
    return redirect(url_for('admin.finance_fixed_expenses'))


@admin_bp.route('/finance/expenses/fixed/<int:item_id>/delete', methods=['POST'])
@super_admin_required
def finance_fixed_expenses_delete(item_id):
    item = OpFixedExpense.query.get_or_404(item_id)
    name = item.expense_name
    try:
        log_finance_action(
            action_type='DELETE', entity_type='OpFixedExpense', entity_id=item.id,
            old_value={'name': name},
            description=f'حذف مصروف ثابت: {name}',
        )
        db.session.delete(item)
        db.session.commit()
        flash(f'تم حذف "{name}"', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'تعذر الحذف: {e}', 'danger')
    return redirect(url_for('admin.finance_fixed_expenses'))
