from datetime import datetime, date
from app.extensions import db


class PowerOfAttorney(db.Model):
    __tablename__ = 'powers_of_attorney'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    poa_type = db.Column(db.String(30), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    notary_office = db.Column(db.String(300), nullable=True)
    real_estate_registry = db.Column(db.String(200), nullable=True)
    notarization_number = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='active')
    notification_30d_sent = db.Column(db.Boolean, default=False)
    notification_7d_sent = db.Column(db.Boolean, default=False)
    notification_1d_sent = db.Column(db.Boolean, default=False)
    file_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    case = db.relationship('Case', backref='powers_of_attorney')

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def color_status(self):
        """Return color based on expiry proximity."""
        days = self.days_until_expiry
        if days is None:
            return 'green'
        if days <= 0:
            return 'red'
        if days <= 7:
            return 'orange'
        if days <= 30:
            return 'yellow'
        return 'green'

    @property
    def computed_status(self):
        days = self.days_until_expiry
        if days is None:
            return 'active'
        if days <= 0:
            return 'expired'
        if days <= 30:
            return 'expiring_soon'
        return 'active'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'case_id': self.case_id,
            'poa_type': self.poa_type,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'notary_office': self.notary_office,
            'real_estate_registry': self.real_estate_registry,
            'notarization_number': self.notarization_number,
            'status': self.status,
            'notification_30d_sent': self.notification_30d_sent,
            'notification_7d_sent': self.notification_7d_sent,
            'notification_1d_sent': self.notification_1d_sent,
            'file_path': self.file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'days_until_expiry': self.days_until_expiry,
            'color_status': self.color_status,
            'computed_status': self.computed_status,
        }

    def __repr__(self):
        return f'<POA {self.poa_type} - Client {self.client_id}>'
