"""Billing — invoices, manual creation, refunds, grace period."""
from datetime import datetime, timedelta, date
import csv
import io

from flask import (
    render_template, request, redirect, url_for, flash, abort, Response, g,
)
from sqlalchemy import or_, func
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action
from app.models.subscription import SubscriptionPayment, SubscriptionPlan
from app.models.tenant import Tenant
from app.services.email_service import send_email


# ──────────────────────────── helpers ────────────────────────────

def _generate_invoice_number():
    """INV-YYYYMM-#### sequential per month."""
    now = datetime.utcnow()
    prefix = f"INV-{now.strftime('%Y%m')}-"
    last = SubscriptionPayment.query.filter(
        SubscriptionPayment.invoice_number.like(f'{prefix}%')
    ).order_by(SubscriptionPayment.id.desc()).first()
    if last and last.invoice_number:
        try:
            n = int(last.invoice_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f'{prefix}{n:04d}'


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


# ──────────────────────────── list ────────────────────────────

@admin_bp.route('/billing/invoices')
@super_admin_required
def billing_invoices():
    """All invoices across all tenants."""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    search = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    payment_type = (request.args.get('type') or '').strip()
    tenant_id = request.args.get('tenant_id', type=int)
    plan_id = request.args.get('plan_id', type=int)
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))

    query = SubscriptionPayment.query.join(Tenant, SubscriptionPayment.tenant_id == Tenant.id)

    if search:
        query = query.filter(or_(
            SubscriptionPayment.invoice_number.ilike(f'%{search}%'),
            Tenant.name.ilike(f'%{search}%'),
            Tenant.email.ilike(f'%{search}%'),
        ))
    if status:
        query = query.filter(SubscriptionPayment.status == status)
    if payment_type:
        query = query.filter(SubscriptionPayment.payment_type == payment_type)
    if tenant_id:
        query = query.filter(SubscriptionPayment.tenant_id == tenant_id)
    if plan_id:
        query = query.filter(SubscriptionPayment.plan_id == plan_id)
    if date_from:
        query = query.filter(SubscriptionPayment.created_at >= date_from)
    if date_to:
        query = query.filter(SubscriptionPayment.created_at < date_to + timedelta(days=1))

    pagination = query.order_by(SubscriptionPayment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Aggregates
    paid_total = float(db.session.query(
        func.coalesce(func.sum(SubscriptionPayment.amount), 0)
    ).filter(SubscriptionPayment.status == 'paid').scalar() or 0)
    unpaid_total = float(db.session.query(
        func.coalesce(func.sum(SubscriptionPayment.amount), 0)
    ).filter(SubscriptionPayment.status.in_(['pending', 'unpaid', 'overdue'])).scalar() or 0)
    overdue_count = SubscriptionPayment.query.filter_by(status='overdue').count()

    plans = SubscriptionPlan.query.all()

    return render_template(
        'admin/billing/invoices.html',
        pagination=pagination,
        plans=plans,
        filters={
            'q': search, 'status': status, 'type': payment_type,
            'tenant_id': tenant_id, 'plan_id': plan_id,
            'date_from': request.args.get('date_from', ''),
            'date_to': request.args.get('date_to', ''),
        },
        totals={'paid': paid_total, 'unpaid': unpaid_total, 'overdue_count': overdue_count},
    )


# ──────────────────────────── detail ────────────────────────────

@admin_bp.route('/billing/invoices/<int:invoice_id>')
@super_admin_required
def billing_invoice_detail(invoice_id):
    """View a single invoice."""
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    return render_template('admin/billing/detail.html', invoice=inv)


# ──────────────────────────── PDF ────────────────────────────

@admin_bp.route('/billing/invoices/<int:invoice_id>/pdf')
@super_admin_required
def billing_invoice_pdf(invoice_id):
    """Render an invoice as a printable PDF (uses WeasyPrint if installed,
    otherwise renders an HTML page that the browser can print)."""
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    html = render_template('admin/billing/pdf.html', invoice=inv)
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=request.url_root).write_pdf()
        return Response(
            pdf_bytes, mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={inv.invoice_number or inv.id}.pdf'
            },
        )
    except Exception:
        # Fallback — return printable HTML
        return html


# ──────────────────────────── create ────────────────────────────

@admin_bp.route('/billing/invoices/create', methods=['GET', 'POST'])
@super_admin_required
def billing_invoice_create():
    """Create a manual custom invoice for any tenant."""
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id', type=int)
        if not tenant_id:
            flash('يجب اختيار المكتب', 'danger')
            return redirect(url_for('admin.billing_invoice_create'))

        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            flash('المكتب غير موجود', 'danger')
            return redirect(url_for('admin.billing_invoice_create'))

        plan_id = request.form.get('plan_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        period_start = _parse_date(request.form.get('period_start')) or date.today()
        period_end = _parse_date(request.form.get('period_end')) or (period_start + timedelta(days=30))
        due_date = _parse_date(request.form.get('due_date')) or period_start

        inv = SubscriptionPayment(
            tenant_id=tenant_id,
            plan_id=plan_id or tenant.subscription_plan_id,
            invoice_number=_generate_invoice_number(),
            amount=amount,
            payment_method=request.form.get('payment_method', 'manual'),
            payment_reference=(request.form.get('payment_reference') or '').strip() or None,
            issue_date=date.today(),
            due_date=due_date,
            period_start=period_start,
            period_end=period_end,
            payment_type=request.form.get('payment_type', 'custom'),
            status=request.form.get('status', 'pending'),
            notes=(request.form.get('notes') or '').strip() or None,
            created_by_admin=g.current_admin.id,
        )
        db.session.add(inv)
        db.session.flush()

        log_action(
            'INVOICE_CREATED', entity_type='Invoice', entity_id=inv.id,
            new_value=inv.to_dict(),
            description=f'Created invoice {inv.invoice_number} for {tenant.name}',
        )
        db.session.commit()
        flash(f'تم إنشاء الفاتورة: {inv.invoice_number}', 'success')
        return redirect(url_for('admin.billing_invoice_detail', invoice_id=inv.id))

    # Pre-select tenant / plan from query string
    pre_tenant_id = request.args.get('tenant_id', type=int)
    tenants = Tenant.query.order_by(Tenant.name).all()
    plans = SubscriptionPlan.query.filter(
        SubscriptionPlan.status.in_(['active', 'draft'])
    ).order_by(SubscriptionPlan.price_monthly).all()
    return render_template(
        'admin/billing/create.html',
        tenants=tenants, plans=plans, pre_tenant_id=pre_tenant_id,
    )


# ──────────────────────────── status / refund / remind ────────────────────────────

@admin_bp.route('/billing/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@super_admin_required
def billing_invoice_mark_paid(invoice_id):
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    old_status = inv.status
    inv.status = 'paid'
    inv.paid_at = datetime.utcnow()
    log_action(
        'INVOICE_PAID', entity_type='Invoice', entity_id=invoice_id,
        old_value={'status': old_status}, new_value={'status': 'paid'},
        description=f'Marked invoice {inv.invoice_number} as paid',
    )
    db.session.commit()
    flash('تم وضع علامة "مدفوعة" على الفاتورة', 'success')
    return redirect(url_for('admin.billing_invoice_detail', invoice_id=invoice_id))


@admin_bp.route('/billing/invoices/<int:invoice_id>/refund', methods=['POST'])
@super_admin_required
def billing_invoice_refund(invoice_id):
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    refund_amount = request.form.get('refund_amount', type=float) or float(inv.amount)
    reason = (request.form.get('reason') or '').strip() or 'Refunded by admin'

    old_status = inv.status
    inv.status = 'refunded'
    inv.refunded_at = datetime.utcnow()
    inv.refund_amount = refund_amount
    inv.refund_reason = reason

    log_action(
        'INVOICE_REFUNDED', entity_type='Invoice', entity_id=invoice_id,
        old_value={'status': old_status},
        new_value={'status': 'refunded', 'refund_amount': refund_amount, 'reason': reason},
        description=f'Refunded {refund_amount} from invoice {inv.invoice_number}',
    )
    db.session.commit()
    flash(f'تم استرداد المبلغ: {refund_amount} ج.م', 'warning')
    return redirect(url_for('admin.billing_invoice_detail', invoice_id=invoice_id))


@admin_bp.route('/billing/invoices/<int:invoice_id>/cancel', methods=['POST'])
@super_admin_required
def billing_invoice_cancel(invoice_id):
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    old_status = inv.status
    inv.status = 'cancelled'
    log_action(
        'INVOICE_CANCELLED', entity_type='Invoice', entity_id=invoice_id,
        old_value={'status': old_status}, new_value={'status': 'cancelled'},
        description=f'Cancelled invoice {inv.invoice_number}',
    )
    db.session.commit()
    flash('تم إلغاء الفاتورة', 'warning')
    return redirect(url_for('admin.billing_invoice_detail', invoice_id=invoice_id))


@admin_bp.route('/billing/invoices/<int:invoice_id>/remind', methods=['POST'])
@super_admin_required
def billing_invoice_remind(invoice_id):
    """Send a payment reminder email to the tenant."""
    inv = SubscriptionPayment.query.get_or_404(invoice_id)
    tenant = inv.tenant
    if not tenant or not tenant.email:
        flash('لا يوجد بريد إلكتروني للمكتب', 'danger')
        return redirect(url_for('admin.billing_invoice_detail', invoice_id=invoice_id))

    subject = f'تذكير بفاتورة معلقة — {inv.invoice_number}'
    html = f"""
    <div dir='rtl' style='font-family: Tajawal, Arial; padding:24px'>
      <h2 style='color:#1849A9'>تذكير بدفع فاتورة</h2>
      <p>عزيزي {tenant.name},</p>
      <p>هذه رسالة تذكير بشأن الفاتورة رقم <strong>{inv.invoice_number}</strong>:</p>
      <ul>
        <li>المبلغ: <strong>{inv.amount} ج.م</strong></li>
        <li>تاريخ الإصدار: {inv.issue_date or inv.created_at.date()}</li>
        <li>تاريخ الاستحقاق: {inv.due_date or '—'}</li>
        <li>الحالة: {inv.status}</li>
      </ul>
      <p>يرجى الدفع في أقرب فرصة لتجنب تعليق الحساب.</p>
      <p style='color:#666;font-size:12px;margin-top:30px'>LexOffice — Manasety</p>
    </div>
    """
    sent = send_email(tenant.email, subject, html)
    log_action(
        'INVOICE_REMINDER_SENT', entity_type='Invoice', entity_id=invoice_id,
        description=f'Reminder email sent to {tenant.email} for {inv.invoice_number}',
    )
    db.session.commit()
    flash('تم إرسال التذكير بالبريد الإلكتروني' if sent else 'فشل إرسال البريد', 'success' if sent else 'warning')
    return redirect(url_for('admin.billing_invoice_detail', invoice_id=invoice_id))


# ──────────────────────────── grace period ────────────────────────────

@admin_bp.route('/billing/tenants/<int:tenant_id>/grace-period', methods=['POST'])
@super_admin_required
def billing_grace_period(tenant_id):
    """Add N days grace to a tenant's subscription."""
    tenant = Tenant.query.get_or_404(tenant_id)
    days = request.form.get('days', type=int) or 7

    base = tenant.subscription_ends_at or datetime.utcnow()
    if base < datetime.utcnow():
        base = datetime.utcnow()
    tenant.subscription_ends_at = base + timedelta(days=days)

    log_action(
        'GRACE_PERIOD_GRANTED', entity_type='Tenant', entity_id=tenant_id,
        new_value={'days': days, 'new_end': tenant.subscription_ends_at.isoformat()},
        description=f'Granted {days}-day grace period to {tenant.name}',
    )
    db.session.commit()
    flash(f'تم منح {days} يوم Grace Period', 'success')
    return redirect(url_for('admin.tenant_billing', tenant_id=tenant_id))


# ──────────────────────────── export ────────────────────────────

@admin_bp.route('/billing/export')
@super_admin_required
def billing_export():
    """Export filtered invoices to CSV."""
    search = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()

    query = SubscriptionPayment.query.join(Tenant)
    if search:
        query = query.filter(or_(
            SubscriptionPayment.invoice_number.ilike(f'%{search}%'),
            Tenant.name.ilike(f'%{search}%'),
        ))
    if status:
        query = query.filter(SubscriptionPayment.status == status)

    rows = query.order_by(SubscriptionPayment.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Invoice', 'Tenant', 'Plan', 'Amount', 'Type',
        'Status', 'Issued', 'Due', 'Paid At', 'Period Start', 'Period End',
    ])
    for p in rows:
        writer.writerow([
            p.invoice_number or f'#{p.id}',
            p.tenant.name if p.tenant else '',
            p.plan.name if p.plan else '',
            float(p.amount or 0),
            p.payment_type,
            p.status,
            p.issue_date or '',
            p.due_date or '',
            p.paid_at.strftime('%Y-%m-%d %H:%M') if p.paid_at else '',
            p.period_start or '',
            p.period_end or '',
        ])
    return Response(
        buf.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=invoices_{datetime.utcnow().strftime("%Y%m%d")}.csv'},
    )
