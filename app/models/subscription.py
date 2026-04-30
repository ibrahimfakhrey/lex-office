from datetime import datetime
from app.extensions import db


class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_lawyers = db.Column(db.Integer, nullable=False)
    max_storage_gb = db.Column(db.Integer, nullable=True)
    price_monthly = db.Column(db.Numeric(10, 2), nullable=False)
    price_yearly = db.Column(db.Numeric(10, 2), nullable=False)
    features = db.Column(db.JSON, nullable=True)
    # active / archived / draft
    status = db.Column(db.String(20), default='active', nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    # Public means visible on signup. Private/Custom plans are admin-assigned only.
    is_public = db.Column(db.Boolean, default=True)
    # Self-service: tenants can subscribe directly. Otherwise needs admin intervention.
    self_service = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'max_lawyers': self.max_lawyers,
            'max_storage_gb': self.max_storage_gb,
            'price_monthly': float(self.price_monthly) if self.price_monthly is not None else None,
            'price_yearly': float(self.price_yearly) if self.price_yearly is not None else None,
            'features': self.features,
            'status': self.status,
            'is_active': self.is_active,
            'is_public': self.is_public,
            'self_service': self.self_service,
        }

    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'


class SubscriptionPayment(db.Model):
    """Subscription invoice / payment record (used by admin billing)."""
    __tablename__ = 'subscription_payments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True, unique=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    # cash / bank_transfer / card / paymob / vodafone_cash / etisalat_cash / manual
    payment_method = db.Column(db.String(30), nullable=False, default='manual')
    payment_reference = db.Column(db.String(200), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    # monthly / yearly / upgrade / refund / custom
    payment_type = db.Column(db.String(20), nullable=False, default='monthly')
    # pending / paid / unpaid / overdue / refunded / cancelled
    status = db.Column(db.String(20), default='pending')
    paid_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=True)
    refund_reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    receipt_sent = db.Column(db.Boolean, default=False)
    created_by_admin = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')
    plan = db.relationship('SubscriptionPlan')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant.name if self.tenant else None,
            'plan_id': self.plan_id,
            'plan_name': self.plan.name_ar if self.plan else None,
            'invoice_number': self.invoice_number,
            'amount': float(self.amount) if self.amount is not None else None,
            'payment_method': self.payment_method,
            'payment_reference': self.payment_reference,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'payment_type': self.payment_type,
            'status': self.status,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
            'refund_amount': float(self.refund_amount) if self.refund_amount else None,
            'refund_reason': self.refund_reason,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
