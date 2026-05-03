"""Billing service: helpers for auto-generating subscription invoices."""
from datetime import datetime, timedelta, date
from app.extensions import db
from app.models.subscription import SubscriptionPayment


def _next_invoice_number():
    """INV-YYYYMM-#### sequential per month. Mirrors admin/billing.py logic."""
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


def create_subscription_invoice(tenant, plan, billing_cycle='monthly',
                                payment_type=None, created_by_admin=None,
                                commit=True):
    """Create an unpaid invoice tied to the tenant's current subscription.

    Returns the SubscriptionPayment instance (added to the session, optionally committed).
    Does nothing and returns None if tenant or plan is missing.
    """
    if not tenant or not plan:
        return None

    today = date.today()
    period_start = today
    if billing_cycle == 'yearly':
        amount = plan.price_yearly
        period_end = today + timedelta(days=365)
    else:
        billing_cycle = 'monthly'
        amount = plan.price_monthly
        period_end = today + timedelta(days=30)

    invoice = SubscriptionPayment(
        tenant_id=tenant.id,
        plan_id=plan.id,
        invoice_number=_next_invoice_number(),
        amount=amount or 0,
        payment_method='manual',
        issue_date=today,
        due_date=today + timedelta(days=30),
        period_start=period_start,
        period_end=period_end,
        payment_type=payment_type or billing_cycle,
        status='unpaid',
        created_by_admin=created_by_admin,
    )
    db.session.add(invoice)
    if commit:
        db.session.commit()
    return invoice
