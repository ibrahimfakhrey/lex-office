from datetime import datetime
from app.extensions import db


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    logo_path = db.Column(db.String(500), nullable=True)
    address = db.Column(db.Text, nullable=True)
    bar_registration_no = db.Column(db.String(100), nullable=True)
    primary_court = db.Column(db.String(200), nullable=True)
    courts = db.Column(db.Text, nullable=True)  # JSON list
    phone = db.Column(db.String(20), nullable=True)
    fax = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    subscription_plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=True)
    subscription_status = db.Column(db.String(20), default='trial')
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    subscription_ends_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    suspension_reason = db.Column(db.Text, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    country = db.Column(db.String(80), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    # 'eg' | 'sa' — frozen at registration from g.market. Drives plan list,
    # phone validation, currency display, courts dropdown, bar body label.
    market = db.Column(db.String(2), nullable=False, default='eg', index=True)
    # organic / referral / paid_ad / direct
    acquisition_source = db.Column(db.String(40), nullable=True)
    # Which admin onboarded this tenant (NULL for public-signup tenants).
    # Used by RBAC scope filtering to restrict which admins can see/edit.
    created_by_admin_id = db.Column(
        db.Integer, db.ForeignKey('admin_users.id'), nullable=True, index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription_plan = db.relationship('SubscriptionPlan', backref='tenants')
    users = db.relationship('User', backref='tenant', lazy='dynamic')
    clients = db.relationship('Client', backref='tenant', lazy='dynamic')
    cases = db.relationship('Case', backref='tenant', lazy='dynamic')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'name': self.name,
            'logo_path': self.logo_path,
            'address': self.address,
            'bar_registration_no': self.bar_registration_no,
            'primary_court': self.primary_court,
            'courts': json.loads(self.courts) if self.courts else None,
            'phone': self.phone,
            'fax': self.fax,
            'email': self.email,
            'subscription_plan_id': self.subscription_plan_id,
            'subscription_status': self.subscription_status,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'subscription_ends_at': self.subscription_ends_at.isoformat() if self.subscription_ends_at else None,
            'is_active': self.is_active,
            'suspension_reason': self.suspension_reason,
            'suspended_at': self.suspended_at.isoformat() if self.suspended_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'country': self.country,
            'city': self.city,
            'market': self.market,
            'acquisition_source': self.acquisition_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Tenant {self.name}>'
