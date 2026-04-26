from datetime import datetime
from app.extensions import db


class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    max_lawyers = db.Column(db.Integer, nullable=False)
    price_monthly = db.Column(db.Numeric(10, 2), nullable=False)
    price_yearly = db.Column(db.Numeric(10, 2), nullable=False)
    features = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'max_lawyers': self.max_lawyers,
            'price_monthly': float(self.price_monthly) if self.price_monthly is not None else None,
            'price_yearly': float(self.price_yearly) if self.price_yearly is not None else None,
            'features': self.features,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'


class SubscriptionPayment(db.Model):
    __tablename__ = 'subscription_payments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    payment_reference = db.Column(db.String(200), nullable=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')
    receipt_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship('Tenant')
    plan = db.relationship('SubscriptionPlan')
