"""API routes for Financial management: Payments, Invoices, Expenses."""
from datetime import datetime, date
from sqlalchemy import func, extract
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date, parse_datetime)
from app.extensions import db
from flask import g, request
from app.utils.helpers import egypt_today
from app.models.financial import Payment, Invoice, InvoiceItem, Expense
from app.models.case import Case
from app.models.client import Client
from app.blueprints.financial.routes import sync_invoice_payment

_AR_MONTH_LABELS = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]


def _shift_month(d: date, delta: int) -> date:
    """Return the first day of (d's month + delta)."""
    m = d.month - 1 + delta
    year = d.year + m // 12
    month = m % 12 + 1
    return date(year, month, 1)


_CASE_TYPE_LABELS = {
    'criminal': 'جنائية', 'civil': 'مدنية', 'commercial': 'تجارية',
    'administrative': 'إدارية', 'labor': 'عمالية', 'family': 'أسرة',
    'constitutional': 'دستورية', 'enforcement': 'تنفيذ',
}

PAYMENT_METHODS = ['cash', 'bank_transfer', 'check', 'credit_card', 'online']
EXPENSE_TYPES = ['court_fees', 'registration', 'transportation', 'copies',
                 'expert_fees', 'office', 'other']
INVOICE_STATUSES = ['draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled']
ITEM_TYPES = ['fees', 'consultation', 'court_fees', 'expenses', 'other']


# ===================== FINANCIAL OVERVIEW =====================

@api_bp.route('/financial', methods=['GET'])
@api_permission_required('financial', 'view')
def api_financial_overview():
    """Financial overview dashboard."""
    today = egypt_today()
    current_month = today.month
    current_year = today.year

    # Monthly totals
    monthly_payments = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.tenant_id == g.tenant_id,
        extract('month', Payment.payment_date) == current_month,
        extract('year', Payment.payment_date) == current_year
    ).scalar()

    monthly_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.tenant_id == g.tenant_id,
        extract('month', Expense.expense_date) == current_month,
        extract('year', Expense.expense_date) == current_year
    ).scalar()

    # Pending invoices
    pending_invoices = Invoice.query.filter(
        Invoice.tenant_id == g.tenant_id,
        Invoice.status.in_(['sent', 'partially_paid', 'overdue'])
    ).count()

    pending_invoice_total = db.session.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.tenant_id == g.tenant_id,
        Invoice.status.in_(['sent', 'partially_paid', 'overdue'])
    ).scalar()

    # Recent items
    recent_payments = Payment.query.filter_by(tenant_id=g.tenant_id).order_by(
        Payment.payment_date.desc()).limit(10).all()
    recent_invoices = Invoice.query.filter_by(tenant_id=g.tenant_id).order_by(
        Invoice.created_at.desc()).limit(10).all()
    recent_expenses = Expense.query.filter_by(tenant_id=g.tenant_id).order_by(
        Expense.expense_date.desc()).limit(10).all()

    # Previous month payments → MoM delta
    prev_month_date = _shift_month(today.replace(day=1), -1)
    prev_payments = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.tenant_id == g.tenant_id,
        extract('month', Payment.payment_date) == prev_month_date.month,
        extract('year', Payment.payment_date) == prev_month_date.year,
    ).scalar()
    monthly_net = float(monthly_payments) - float(monthly_expenses)
    delta_payments = None
    if float(prev_payments) > 0:
        delta_payments = round(
            ((float(monthly_payments) - float(prev_payments)) / float(prev_payments)) * 100
        )

    # Overdue count (invoices with overdue status)
    overdue_count = Invoice.query.filter(
        Invoice.tenant_id == g.tenant_id,
        Invoice.status == 'overdue',
    ).count()

    # 6-month series of invoiced vs collected
    monthly_series = []
    for i in range(5, -1, -1):
        m_date = _shift_month(today.replace(day=1), -i)
        invoiced = db.session.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
            Invoice.tenant_id == g.tenant_id,
            extract('month', Invoice.issue_date) == m_date.month,
            extract('year', Invoice.issue_date) == m_date.year,
        ).scalar()
        collected = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.tenant_id == g.tenant_id,
            extract('month', Payment.payment_date) == m_date.month,
            extract('year', Payment.payment_date) == m_date.year,
        ).scalar()
        monthly_series.append({
            'month': m_date.month,
            'year': m_date.year,
            'label': _AR_MONTH_LABELS[m_date.month - 1],
            'invoiced': float(invoiced),
            'collected': float(collected),
            'is_current': m_date.month == current_month and m_date.year == current_year,
        })

    # Revenue by case type (current year, top 4)
    rev_by_type_rows = db.session.query(
        Case.case_type, func.coalesce(func.sum(Payment.amount), 0)
    ).join(Payment, Payment.case_id == Case.id).filter(
        Payment.tenant_id == g.tenant_id,
        extract('year', Payment.payment_date) == current_year,
    ).group_by(Case.case_type).order_by(func.sum(Payment.amount).desc()).limit(4).all()
    revenue_by_case_type = [
        {'case_type': r[0], 'label': _CASE_TYPE_LABELS.get(r[0], r[0]), 'amount': float(r[1])}
        for r in rev_by_type_rows
    ]

    # Collection rate (YTD): collected / invoiced
    ytd_invoiced = db.session.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.tenant_id == g.tenant_id,
        extract('year', Invoice.issue_date) == current_year,
    ).scalar()
    ytd_collected = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.tenant_id == g.tenant_id,
        extract('year', Payment.payment_date) == current_year,
    ).scalar()
    collection_rate = (
        round((float(ytd_collected) / float(ytd_invoiced)) * 100)
        if float(ytd_invoiced) > 0 else 0
    )

    return success_response(data={
        'current_month_label': _AR_MONTH_LABELS[current_month - 1],
        'current_year': current_year,
        'monthly_payments': float(monthly_payments),
        'monthly_expenses': float(monthly_expenses),
        'monthly_net': monthly_net,
        'delta_payments': delta_payments,
        'pending_invoices': pending_invoices,
        'pending_invoice_total': float(pending_invoice_total),
        'overdue_count': overdue_count,
        'collection_rate': collection_rate,
        'monthly_series': monthly_series,
        'revenue_by_case_type': revenue_by_case_type,
        'recent_payments': [p.to_dict() for p in recent_payments],
        'recent_invoices': [i.to_dict() for i in recent_invoices],
        'recent_expenses': [e.to_dict() for e in recent_expenses],
    })


# ===================== PAYMENTS =====================

@api_bp.route('/financial/payments', methods=['GET'])
@api_permission_required('financial', 'view')
def api_list_payments():
    """List all payments with filters."""
    client_id = request.args.get('client_id', '', type=str)
    case_id = request.args.get('case_id', '', type=str)
    method = request.args.get('method', '')

    query = Payment.query.filter_by(tenant_id=g.tenant_id)
    if client_id:
        query = query.filter_by(client_id=int(client_id))
    if case_id:
        query = query.filter_by(case_id=int(case_id))
    if method:
        query = query.filter_by(payment_method=method)

    query = query.order_by(Payment.payment_date.desc())

    total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter_by(
        tenant_id=g.tenant_id).scalar()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response(
        data=[p.to_dict() for p in pagination.items],
        meta={
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
            'total_sum': float(total),
        },
    )


@api_bp.route('/financial/payments', methods=['POST'])
@api_permission_required('financial', 'create')
def api_create_payment():
    """Record a new payment."""
    data = get_json_or_form()
    errors = {}

    client_id = data.get('client_id')
    amount = data.get('amount')
    payment_date_str = data.get('payment_date', '')
    payment_method = data.get('payment_method', '')

    if not client_id:
        errors['client_id'] = 'يجب اختيار الموكل'
    try:
        amount = float(amount) if amount else None
    except (ValueError, TypeError):
        amount = None
    if not amount or amount <= 0:
        errors['amount'] = 'يجب إدخال مبلغ صالح'
    if not payment_date_str:
        errors['payment_date'] = 'تاريخ الدفع مطلوب'
    if not payment_method:
        errors['payment_method'] = 'طريقة الدفع مطلوبة'

    if errors:
        return validation_error(errors)

    payment_date = parse_date(payment_date_str)
    if not payment_date:
        return validation_error({'payment_date': 'تنسيق التاريخ غير صالح (YYYY-MM-DD)'})

    payment = Payment(
        tenant_id=g.tenant_id,
        client_id=int(client_id),
        case_id=int(data['case_id']) if data.get('case_id') else None,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        reference_number=(data.get('reference_number') or '').strip() or None,
        notes=(data.get('notes') or '').strip() or None,
        recorded_by=g.current_user.id,
    )
    db.session.add(payment)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='payment_received',
        title=f'تم تسجيل دفعة: {amount} ج.م',
        body=f'الموكل: {payment.client.full_name if payment.client else "-"}',
        priority='success',
        related_type='payment',
        related_id=payment.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=payment.to_dict(), message='تم تسجيل الدفعة بنجاح', status_code=201)


@api_bp.route('/financial/payments/<int:id>', methods=['GET'])
@api_permission_required('financial', 'view')
def api_show_payment(id):
    """Show payment details."""
    payment = Payment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return success_response(data=payment.to_dict())


@api_bp.route('/financial/payments/<int:id>', methods=['DELETE'])
@api_permission_required('financial', 'delete')
def api_delete_payment(id):
    """Delete a payment."""
    payment = Payment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(payment)
    db.session.commit()
    return success_response(message='تم حذف الدفعة')


# ===================== INVOICES =====================

@api_bp.route('/financial/invoices', methods=['GET'])
@api_permission_required('financial', 'view')
def api_list_invoices():
    """List all invoices with filters."""
    status = request.args.get('status', '')
    client_id = request.args.get('client_id', '', type=str)

    query = Invoice.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    if client_id:
        query = query.filter_by(client_id=int(client_id))

    query = query.order_by(Invoice.created_at.desc())
    return paginated_response(query)


@api_bp.route('/financial/invoices', methods=['POST'])
@api_permission_required('financial', 'create')
def api_create_invoice():
    """Create a new invoice with line items."""
    data = get_json_or_form()
    errors = {}

    client_id = data.get('client_id')
    issue_date_str = data.get('issue_date', '')
    items = data.get('items', [])

    if not client_id:
        errors['client_id'] = 'يجب اختيار الموكل'
    if not issue_date_str:
        errors['issue_date'] = 'تاريخ الإصدار مطلوب'
    if not items or not isinstance(items, list) or len(items) == 0:
        errors['items'] = 'يجب إضافة بند واحد على الأقل'

    if errors:
        return validation_error(errors)

    issue_date = parse_date(issue_date_str)
    if not issue_date:
        return validation_error({'issue_date': 'تنسيق التاريخ غير صالح (YYYY-MM-DD)'})

    tax_rate = data.get('tax_rate')
    try:
        tax_rate = float(tax_rate) if tax_rate is not None else 14.00
    except (ValueError, TypeError):
        tax_rate = 14.00

    invoice = Invoice(
        tenant_id=g.tenant_id,
        client_id=int(client_id),
        case_id=int(data['case_id']) if data.get('case_id') else None,
        issue_date=issue_date,
        discount_type=data.get('discount_type') or None,
        discount_value=float(data['discount_value']) if data.get('discount_value') else None,
        tax_rate=tax_rate,
        notes=(data.get('notes') or '').strip() or None,
    )
    invoice.generate_invoice_number(g.tenant_id)
    db.session.add(invoice)
    db.session.flush()

    # Add items
    for item_data in items:
        desc = (item_data.get('description') or '').strip()
        amt = item_data.get('amount')
        if desc and amt:
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=desc,
                item_type=item_data.get('item_type', 'fees'),
                amount=float(amt),
            )
            db.session.add(item)

    db.session.flush()
    invoice.calculate_totals()
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم إنشاء فاتورة جديدة: {invoice.invoice_number}',
        body=f'الإجمالي: {float(invoice.total):.0f} ج.م — الموكل: {invoice.client.full_name if invoice.client else "-"}',
        related_type='invoice',
        related_id=invoice.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=invoice.to_dict(include_items=True),
                            message='تم إنشاء الفاتورة بنجاح', status_code=201)


@api_bp.route('/financial/invoices/<int:id>', methods=['GET'])
@api_permission_required('financial', 'view')
def api_show_invoice(id):
    """Show invoice details with items and paid amount."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()

    paid_amount = 0
    if invoice.case_id:
        paid_amount = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.tenant_id == g.tenant_id,
            Payment.case_id == invoice.case_id,
            Payment.client_id == invoice.client_id
        ).scalar())

    data = invoice.to_dict(include_items=True)
    data['paid_amount'] = paid_amount
    return success_response(data=data)


@api_bp.route('/financial/invoices/<int:id>', methods=['PUT'])
@api_permission_required('financial', 'edit')
def api_update_invoice(id):
    """Update invoice fields and replace items."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    data = get_json_or_form()

    if data.get('client_id'):
        invoice.client_id = int(data['client_id'])
    if data.get('case_id') is not None:
        invoice.case_id = int(data['case_id']) if data['case_id'] else None
    if data.get('issue_date'):
        issue_date = parse_date(data['issue_date'])
        if issue_date:
            invoice.issue_date = issue_date
    if data.get('status'):
        invoice.status = data['status']
    if 'discount_type' in data:
        invoice.discount_type = data.get('discount_type') or None
    if 'discount_value' in data:
        invoice.discount_value = float(data['discount_value']) if data.get('discount_value') else None
    if data.get('tax_rate') is not None:
        try:
            invoice.tax_rate = float(data['tax_rate'])
        except (ValueError, TypeError):
            pass
    if 'notes' in data:
        invoice.notes = (data.get('notes') or '').strip() or None

    # Replace items if provided
    items = data.get('items')
    if items is not None and isinstance(items, list):
        for old_item in invoice.items.all():
            db.session.delete(old_item)

        for item_data in items:
            desc = (item_data.get('description') or '').strip()
            amt = item_data.get('amount')
            if desc and amt:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=desc,
                    item_type=item_data.get('item_type', 'fees'),
                    amount=float(amt),
                )
                db.session.add(item)

    db.session.flush()
    invoice.calculate_totals()
    sync_invoice_payment(invoice)
    db.session.commit()

    return success_response(data=invoice.to_dict(include_items=True), message='تم تحديث الفاتورة بنجاح')


@api_bp.route('/financial/invoices/<int:id>/status', methods=['PATCH'])
@api_permission_required('financial', 'edit')
def api_update_invoice_status(id):
    """Quick status update for invoice."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    data = get_json_or_form()
    new_status = data.get('status', '')

    if new_status not in INVOICE_STATUSES:
        return error_response('حالة غير صالحة', error_code='invalid_status')

    invoice.status = new_status
    if new_status == 'sent' and not invoice.sent_at:
        invoice.sent_at = datetime.utcnow()
    sync_invoice_payment(invoice)
    db.session.commit()

    return success_response(data=invoice.to_dict(), message='تم تحديث حالة الفاتورة')


@api_bp.route('/financial/invoices/<int:id>', methods=['DELETE'])
@api_permission_required('financial', 'delete')
def api_delete_invoice(id):
    """Delete an invoice."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(invoice)
    db.session.commit()
    return success_response(message='تم حذف الفاتورة')


# ===================== EXPENSES =====================

@api_bp.route('/financial/expenses', methods=['GET'])
@api_permission_required('financial', 'view')
def api_list_expenses():
    """List all expenses with filters."""
    expense_type = request.args.get('type', '')
    case_id = request.args.get('case_id', '', type=str)

    query = Expense.query.filter_by(tenant_id=g.tenant_id)
    if expense_type:
        query = query.filter_by(expense_type=expense_type)
    if case_id:
        query = query.filter_by(case_id=int(case_id))

    query = query.order_by(Expense.expense_date.desc())

    total = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter_by(
        tenant_id=g.tenant_id).scalar()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response(
        data=[e.to_dict() for e in pagination.items],
        meta={
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
            'total_sum': float(total),
        },
    )


@api_bp.route('/financial/expenses', methods=['POST'])
@api_permission_required('financial', 'create')
def api_create_expense():
    """Record a new expense."""
    data = get_json_or_form()
    errors = {}

    amount = data.get('amount')
    expense_type = data.get('expense_type', '')
    expense_date_str = data.get('expense_date', '')

    try:
        amount = float(amount) if amount else None
    except (ValueError, TypeError):
        amount = None
    if not amount or amount <= 0:
        errors['amount'] = 'يجب إدخال مبلغ صالح'
    if not expense_type:
        errors['expense_type'] = 'نوع المصروف مطلوب'
    if not expense_date_str:
        errors['expense_date'] = 'تاريخ المصروف مطلوب'

    if errors:
        return validation_error(errors)

    expense_date = parse_date(expense_date_str)
    if not expense_date:
        return validation_error({'expense_date': 'تنسيق التاريخ غير صالح (YYYY-MM-DD)'})

    expense = Expense(
        tenant_id=g.tenant_id,
        case_id=int(data['case_id']) if data.get('case_id') else None,
        client_id=int(data['client_id']) if data.get('client_id') else None,
        expense_type=expense_type,
        amount=amount,
        expense_date=expense_date,
        description=(data.get('description') or '').strip() or None,
        recorded_by=g.current_user.id,
    )
    db.session.add(expense)
    db.session.commit()

    from app.services.notification_service import notify_tenant_users
    notify_tenant_users(
        tenant_id=g.tenant_id,
        notification_type='general',
        title=f'تم تسجيل مصروف: {amount} ج.م',
        body=f'النوع: {expense_type}',
        related_type='expense',
        related_id=expense.id,
        actor_name=g.current_user.full_name,
        exclude_user_id=g.current_user.id,
    )
    db.session.commit()

    return success_response(data=expense.to_dict(), message='تم تسجيل المصروف بنجاح', status_code=201)


@api_bp.route('/financial/expenses/<int:id>', methods=['GET'])
@api_permission_required('financial', 'view')
def api_show_expense(id):
    """Show expense details."""
    expense = Expense.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    return success_response(data=expense.to_dict())


@api_bp.route('/financial/expenses/<int:id>', methods=['DELETE'])
@api_permission_required('financial', 'delete')
def api_delete_expense(id):
    """Delete an expense."""
    expense = Expense.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return success_response(message='تم حذف المصروف')


# ===================== CLIENT STATEMENT =====================

@api_bp.route('/financial/client-statement/<int:client_id>', methods=['GET'])
@api_permission_required('financial', 'view')
def api_client_statement(client_id):
    """Financial statement for a specific client."""
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()
    cases = Case.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).all()

    payments = Payment.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).order_by(
        Payment.payment_date.desc()).all()
    invoices = Invoice.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).order_by(
        Invoice.issue_date.desc()).all()
    expenses = Expense.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).order_by(
        Expense.expense_date.desc()).all()

    total_fees = sum(float(c.fee_amount or 0) for c in cases)
    total_paid = sum(float(p.amount) for p in payments)
    total_invoiced = sum(float(inv.total) for inv in invoices)
    total_expenses = sum(float(e.amount) for e in expenses)

    return success_response(data={
        'client': client.to_dict(),
        'cases': [c.to_dict() for c in cases],
        'payments': [p.to_dict() for p in payments],
        'invoices': [i.to_dict() for i in invoices],
        'expenses': [e.to_dict() for e in expenses],
        'totals': {
            'total_fees': total_fees,
            'total_paid': total_paid,
            'total_invoiced': total_invoiced,
            'total_expenses': total_expenses,
        },
    })
