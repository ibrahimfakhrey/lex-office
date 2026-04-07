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
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscription_plan = db.relationship('SubscriptionPlan', backref='tenants')
    users = db.relationship('User', backref='tenant', lazy='dynamic')
    clients = db.relationship('Client', backref='tenant', lazy='dynamic')
    cases = db.relationship('Case', backref='tenant', lazy='dynamic')

    def __repr__(self):
        return f'<Tenant {self.name}>'
