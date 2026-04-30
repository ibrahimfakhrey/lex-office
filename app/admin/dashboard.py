"""Admin dashboard — KPIs and analytics."""
from datetime import datetime, timedelta
from flask import render_template, g
from sqlalchemy import func
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPayment


@admin_bp.route('/')
@super_admin_required
def index():
    """Admin home — KPI cards."""
    today = datetime.utcnow().date()
    week_ahead = today + timedelta(days=7)
    month_start = today.replace(day=1)

    total_active = Tenant.query.filter_by(subscription_status='active', is_active=True).count()
    total_trial = Tenant.query.filter_by(subscription_status='trial').count()
    total_suspended = Tenant.query.filter_by(subscription_status='suspended').count()
    total_cancelled = Tenant.query.filter_by(subscription_status='cancelled').count()
    total_tenants = Tenant.query.count()

    # New this month
    new_this_month = Tenant.query.filter(Tenant.created_at >= month_start).count()

    # Expiring soon (next 7 days) — trial or paid
    expiring_soon = Tenant.query.filter(
        db.or_(
            db.and_(Tenant.trial_ends_at.isnot(None), Tenant.trial_ends_at <= week_ahead, Tenant.trial_ends_at >= datetime.utcnow()),
            db.and_(Tenant.subscription_ends_at.isnot(None), Tenant.subscription_ends_at <= week_ahead, Tenant.subscription_ends_at >= datetime.utcnow()),
        )
    ).count()

    # Overdue invoices
    overdue_invoices = SubscriptionPayment.query.filter(
        SubscriptionPayment.status == 'overdue'
    ).count()

    # Churn rate (cancelled this month / total at start of month)
    cancelled_this_month = Tenant.query.filter(
        Tenant.cancelled_at.isnot(None),
        Tenant.cancelled_at >= month_start,
    ).count()
    total_at_month_start = Tenant.query.filter(Tenant.created_at < month_start).count()
    churn_rate = round(100.0 * cancelled_this_month / total_at_month_start, 2) if total_at_month_start else 0.0

    # Revenue this month
    monthly_revenue = db.session.query(
        func.coalesce(func.sum(SubscriptionPayment.amount), 0)
    ).filter(
        SubscriptionPayment.status == 'paid',
        SubscriptionPayment.paid_at >= month_start,
    ).scalar()

    return render_template(
        'admin/dashboard/index.html',
        kpis={
            'total_tenants': total_tenants,
            'total_active': total_active,
            'total_trial': total_trial,
            'total_suspended': total_suspended,
            'total_cancelled': total_cancelled,
            'new_this_month': new_this_month,
            'expiring_soon': expiring_soon,
            'overdue_invoices': overdue_invoices,
            'churn_rate': churn_rate,
            'monthly_revenue': float(monthly_revenue or 0),
        },
    )
