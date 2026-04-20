"""Financial management routes: Payments, Invoices, Expenses."""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from sqlalchemy import func, extract
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.utils.helpers import egypt_today
from app.models.financial import Payment, Invoice, InvoiceItem, Expense
from app.models.case import Case
from app.models.client import Client
from app.models.user import User

financial_bp = Blueprint('financial', __name__, template_folder='../../templates/financial')

PAYMENT_METHODS = [
    ('cash', 'نقدي'), ('bank_transfer', 'تحويل بنكي'), ('check', 'شيك'),
    ('credit_card', 'بطاقة ائتمان'), ('online', 'دفع إلكتروني'),
]
EXPENSE_TYPES = [
    ('court_fees', 'رسوم محكمة'), ('registration', 'رسوم تسجيل'),
    ('transportation', 'مواصلات'), ('copies', 'تصوير مستندات'),
    ('expert_fees', 'أتعاب خبير'), ('office', 'مصاريف مكتبية'),
    ('other', 'أخرى'),
]
INVOICE_STATUSES = [
    ('draft', 'مسودة'), ('sent', 'مرسلة'), ('paid', 'مدفوعة'),
    ('partially_paid', 'مدفوعة جزئياً'), ('overdue', 'متأخرة'), ('cancelled', 'ملغاة'),
]
ITEM_TYPES = [
    ('fees', 'أتعاب'), ('consultation', 'استشارة'), ('court_fees', 'رسوم محكمة'),
    ('expenses', 'مصاريف'), ('other', 'أخرى'),
]


# ============= FINANCIAL OVERVIEW =============

@financial_bp.route('/')
@permission_required('financial', 'view')
def index():
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

    return render_template('financial/index.html',
                           monthly_payments=float(monthly_payments),
                           monthly_expenses=float(monthly_expenses),
                           pending_invoices=pending_invoices,
                           pending_invoice_total=float(pending_invoice_total),
                           recent_payments=recent_payments,
                           recent_invoices=recent_invoices,
                           recent_expenses=recent_expenses,
                           payment_methods=PAYMENT_METHODS,
                           invoice_statuses=INVOICE_STATUSES)


# ============= PAYMENTS =============

@financial_bp.route('/payments')
@permission_required('financial', 'view')
def payments():
    """List all payments with filters."""
    page = request.args.get('page', 1, type=int)
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

    payments = query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=20)

    total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter_by(
        tenant_id=g.tenant_id).scalar()

    return render_template('financial/payments.html', payments=payments,
                           client_id=client_id, case_id=case_id, method=method,
                           payment_methods=PAYMENT_METHODS, total=float(total))


@financial_bp.route('/payments/create', methods=['GET', 'POST'])
@permission_required('financial', 'create')
def create_payment():
    """Record a new payment."""
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()

    if request.method == 'POST':
        errors = []
        client_id = request.form.get('client_id', type=int)
        amount = request.form.get('amount', type=float)
        payment_date_str = request.form.get('payment_date', '')
        payment_method = request.form.get('payment_method', '')

        if not client_id:
            errors.append('يجب اختيار الموكل')
        if not amount or amount <= 0:
            errors.append('يجب إدخال مبلغ صالح')
        if not payment_date_str:
            errors.append('تاريخ الدفع مطلوب')
        if not payment_method:
            errors.append('طريقة الدفع مطلوبة')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('financial/create_payment.html', clients=clients, cases=cases,
                                   form=request.form, payment_methods=PAYMENT_METHODS)

        payment = Payment(
            tenant_id=g.tenant_id,
            client_id=client_id,
            case_id=request.form.get('case_id', type=int) or None,
            amount=amount,
            payment_date=datetime.strptime(payment_date_str, '%Y-%m-%d').date(),
            payment_method=payment_method,
            reference_number=request.form.get('reference_number', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None,
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

        flash('تم تسجيل الدفعة بنجاح', 'success')
        return redirect(url_for('financial.show_payment', id=payment.id))

    pre_client = request.args.get('client_id', type=int)
    pre_case = request.args.get('case_id', type=int)
    return render_template('financial/create_payment.html', clients=clients, cases=cases,
                           form=request.args, payment_methods=PAYMENT_METHODS,
                           pre_client_id=pre_client, pre_case_id=pre_case)


@financial_bp.route('/payments/<int:id>')
@permission_required('financial', 'view')
def show_payment(id):
    """Show payment details."""
    payment = Payment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    method_map = dict(PAYMENT_METHODS)
    return render_template('financial/show_payment.html', payment=payment, method_map=method_map)


@financial_bp.route('/payments/<int:id>/delete', methods=['POST'])
@permission_required('financial', 'delete')
def delete_payment(id):
    """Delete a payment."""
    payment = Payment.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(payment)
    db.session.commit()
    flash('تم حذف الدفعة', 'warning')
    return redirect(url_for('financial.payments'))


# ============= INVOICES =============

@financial_bp.route('/invoices')
@permission_required('financial', 'view')
def invoices():
    """List all invoices with filters."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    client_id = request.args.get('client_id', '', type=str)

    query = Invoice.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    if client_id:
        query = query.filter_by(client_id=int(client_id))

    invoices = query.order_by(Invoice.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('financial/invoices.html', invoices=invoices, status=status,
                           client_id=client_id, invoice_statuses=INVOICE_STATUSES)


@financial_bp.route('/invoices/create', methods=['GET', 'POST'])
@permission_required('financial', 'create')
def create_invoice():
    """Create a new invoice with line items."""
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()

    if request.method == 'POST':
        errors = []
        client_id = request.form.get('client_id', type=int)
        issue_date_str = request.form.get('issue_date', '')

        if not client_id:
            errors.append('يجب اختيار الموكل')
        if not issue_date_str:
            errors.append('تاريخ الإصدار مطلوب')

        # Parse items
        descriptions = request.form.getlist('item_description[]')
        item_types = request.form.getlist('item_type[]')
        amounts = request.form.getlist('item_amount[]')

        if not descriptions or not any(d.strip() for d in descriptions):
            errors.append('يجب إضافة بند واحد على الأقل')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('financial/create_invoice.html', clients=clients, cases=cases,
                                   form=request.form, item_types=ITEM_TYPES,
                                   invoice_statuses=INVOICE_STATUSES)

        invoice = Invoice(
            tenant_id=g.tenant_id,
            client_id=client_id,
            case_id=request.form.get('case_id', type=int) or None,
            issue_date=datetime.strptime(issue_date_str, '%Y-%m-%d').date(),
            discount_type=request.form.get('discount_type') or None,
            discount_value=request.form.get('discount_value', type=float) or None,
            tax_rate=request.form.get('tax_rate', type=float) if request.form.get('tax_rate') else 14.00,
            notes=request.form.get('notes', '').strip() or None,
        )
        invoice.generate_invoice_number(g.tenant_id)
        db.session.add(invoice)
        db.session.flush()

        # Add items
        for i in range(len(descriptions)):
            if descriptions[i].strip() and amounts[i]:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=descriptions[i].strip(),
                    item_type=item_types[i] if i < len(item_types) else 'fees',
                    amount=float(amounts[i]),
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

        flash('تم إنشاء الفاتورة بنجاح', 'success')
        return redirect(url_for('financial.show_invoice', id=invoice.id))

    pre_client = request.args.get('client_id', type=int)
    pre_case = request.args.get('case_id', type=int)
    return render_template('financial/create_invoice.html', clients=clients, cases=cases,
                           form=request.args, item_types=ITEM_TYPES,
                           invoice_statuses=INVOICE_STATUSES,
                           pre_client_id=pre_client, pre_case_id=pre_case)


@financial_bp.route('/invoices/<int:id>')
@permission_required('financial', 'view')
def show_invoice(id):
    """Show invoice details with items."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    items = invoice.items.all()
    status_map = dict(INVOICE_STATUSES)
    item_type_map = dict(ITEM_TYPES)

    # Calculate payments against this invoice's case/client
    paid_amount = 0
    if invoice.case_id:
        paid_amount = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.tenant_id == g.tenant_id,
            Payment.case_id == invoice.case_id,
            Payment.client_id == invoice.client_id
        ).scalar())

    return render_template('financial/show_invoice.html', invoice=invoice, items=items,
                           status_map=status_map, item_type_map=item_type_map,
                           paid_amount=paid_amount)


@financial_bp.route('/invoices/<int:id>/edit', methods=['GET', 'POST'])
@permission_required('financial', 'edit')
def edit_invoice(id):
    """Edit invoice."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()

    if request.method == 'POST':
        invoice.client_id = request.form.get('client_id', type=int)
        invoice.case_id = request.form.get('case_id', type=int) or None
        invoice.issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d').date()
        invoice.status = request.form.get('status', invoice.status)
        invoice.discount_type = request.form.get('discount_type') or None
        invoice.discount_value = request.form.get('discount_value', type=float) or None
        invoice.tax_rate = request.form.get('tax_rate', type=float) if request.form.get('tax_rate') else 14.00
        invoice.notes = request.form.get('notes', '').strip() or None

        # Replace items
        for old_item in invoice.items.all():
            db.session.delete(old_item)

        descriptions = request.form.getlist('item_description[]')
        item_types = request.form.getlist('item_type[]')
        amounts = request.form.getlist('item_amount[]')

        for i in range(len(descriptions)):
            if descriptions[i].strip() and amounts[i]:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=descriptions[i].strip(),
                    item_type=item_types[i] if i < len(item_types) else 'fees',
                    amount=float(amounts[i]),
                )
                db.session.add(item)

        db.session.flush()
        invoice.calculate_totals()
        db.session.commit()

        flash('تم تحديث الفاتورة بنجاح', 'success')
        return redirect(url_for('financial.show_invoice', id=invoice.id))

    items = invoice.items.all()
    return render_template('financial/edit_invoice.html', invoice=invoice, items=items,
                           clients=clients, cases=cases, item_types=ITEM_TYPES,
                           invoice_statuses=INVOICE_STATUSES)


@financial_bp.route('/invoices/<int:id>/update-status', methods=['POST'])
@permission_required('financial', 'edit')
def update_invoice_status(id):
    """Quick status update for invoice."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    new_status = request.form.get('status', '')
    if new_status in dict(INVOICE_STATUSES):
        invoice.status = new_status
        if new_status == 'sent' and not invoice.sent_at:
            invoice.sent_at = datetime.utcnow()
        db.session.commit()
        flash('تم تحديث حالة الفاتورة', 'success')
    return redirect(url_for('financial.show_invoice', id=invoice.id))


@financial_bp.route('/invoices/<int:id>/delete', methods=['POST'])
@permission_required('financial', 'delete')
def delete_invoice(id):
    """Delete an invoice."""
    invoice = Invoice.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(invoice)
    db.session.commit()
    flash('تم حذف الفاتورة', 'warning')
    return redirect(url_for('financial.invoices'))


# ============= EXPENSES =============

@financial_bp.route('/expenses')
@permission_required('financial', 'view')
def expenses():
    """List all expenses with filters."""
    page = request.args.get('page', 1, type=int)
    expense_type = request.args.get('type', '')
    case_id = request.args.get('case_id', '', type=str)

    query = Expense.query.filter_by(tenant_id=g.tenant_id)
    if expense_type:
        query = query.filter_by(expense_type=expense_type)
    if case_id:
        query = query.filter_by(case_id=int(case_id))

    expenses = query.order_by(Expense.expense_date.desc()).paginate(page=page, per_page=20)

    total = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter_by(
        tenant_id=g.tenant_id).scalar()

    return render_template('financial/expenses.html', expenses=expenses,
                           expense_type=expense_type, case_id=case_id,
                           expense_types=EXPENSE_TYPES, total=float(total))


@financial_bp.route('/expenses/create', methods=['GET', 'POST'])
@permission_required('financial', 'create')
def create_expense():
    """Record a new expense."""
    cases = Case.query.filter_by(tenant_id=g.tenant_id).order_by(Case.case_number).all()
    clients = Client.query.filter_by(tenant_id=g.tenant_id, is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        errors = []
        amount = request.form.get('amount', type=float)
        expense_type = request.form.get('expense_type', '')
        expense_date_str = request.form.get('expense_date', '')

        if not amount or amount <= 0:
            errors.append('يجب إدخال مبلغ صالح')
        if not expense_type:
            errors.append('نوع المصروف مطلوب')
        if not expense_date_str:
            errors.append('تاريخ المصروف مطلوب')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('financial/create_expense.html', cases=cases, clients=clients,
                                   form=request.form, expense_types=EXPENSE_TYPES)

        expense = Expense(
            tenant_id=g.tenant_id,
            case_id=request.form.get('case_id', type=int) or None,
            client_id=request.form.get('client_id', type=int) or None,
            expense_type=expense_type,
            amount=amount,
            expense_date=datetime.strptime(expense_date_str, '%Y-%m-%d').date(),
            description=request.form.get('description', '').strip() or None,
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

        flash('تم تسجيل المصروف بنجاح', 'success')
        return redirect(url_for('financial.show_expense', id=expense.id))

    pre_case = request.args.get('case_id', type=int)
    return render_template('financial/create_expense.html', cases=cases, clients=clients,
                           form=request.args, expense_types=EXPENSE_TYPES, pre_case_id=pre_case)


@financial_bp.route('/expenses/<int:id>')
@permission_required('financial', 'view')
def show_expense(id):
    """Show expense details."""
    expense = Expense.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    type_map = dict(EXPENSE_TYPES)
    return render_template('financial/show_expense.html', expense=expense, type_map=type_map)


@financial_bp.route('/expenses/<int:id>/delete', methods=['POST'])
@permission_required('financial', 'delete')
def delete_expense(id):
    """Delete an expense."""
    expense = Expense.query.filter_by(id=id, tenant_id=g.tenant_id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash('تم حذف المصروف', 'warning')
    return redirect(url_for('financial.expenses'))


# ============= CLIENT STATEMENT =============

@financial_bp.route('/client-statement/<int:client_id>')
@permission_required('financial', 'view')
def client_statement(client_id):
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

    method_map = dict(PAYMENT_METHODS)
    type_map = dict(EXPENSE_TYPES)
    status_map = dict(INVOICE_STATUSES)

    return render_template('financial/client_statement.html',
                           client=client, cases=cases,
                           payments=payments, invoices=invoices, expenses=expenses,
                           total_fees=total_fees, total_paid=total_paid,
                           total_invoiced=total_invoiced, total_expenses=total_expenses,
                           method_map=method_map, type_map=type_map, status_map=status_map)
