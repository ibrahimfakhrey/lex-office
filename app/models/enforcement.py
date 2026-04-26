from datetime import datetime
from app.extensions import db


class Enforcement(db.Model):
    __tablename__ = 'enforcements'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    judgment_id = db.Column(db.Integer, db.ForeignKey('judgments.id'), nullable=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    enforcement_number = db.Column(db.String(100), nullable=True)
    enforcement_court = db.Column(db.String(300), nullable=True)
    executor_name = db.Column(db.String(200), nullable=True)
    enforcement_type = db.Column(db.String(30), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    collected_amount = db.Column(db.Numeric(12, 2), default=0)
    debtor_name = db.Column(db.String(300), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = db.relationship('Client')
    collections = db.relationship('EnforcementCollection', backref='enforcement', lazy='dynamic',
                                  order_by='EnforcementCollection.collection_date.desc()',
                                  cascade='all, delete-orphan')
    actions = db.relationship('EnforcementAction', backref='enforcement', lazy='dynamic',
                              order_by='EnforcementAction.action_date.desc()',
                              cascade='all, delete-orphan')

    @property
    def remaining_amount(self):
        return float(self.total_amount) - float(self.collected_amount)

    @property
    def collection_percentage(self):
        if self.total_amount and float(self.total_amount) > 0:
            return round(float(self.collected_amount) / float(self.total_amount) * 100, 1)
        return 0

    def update_collected(self):
        """Recalculate collected amount from collections."""
        total = sum(float(c.amount) for c in self.collections)
        self.collected_amount = total

    def to_dict(self, include_related=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'judgment_id': self.judgment_id,
            'case_id': self.case_id,
            'client_id': self.client_id,
            'enforcement_number': self.enforcement_number,
            'enforcement_court': self.enforcement_court,
            'executor_name': self.executor_name,
            'enforcement_type': self.enforcement_type,
            'total_amount': float(self.total_amount) if self.total_amount is not None else None,
            'collected_amount': float(self.collected_amount) if self.collected_amount is not None else None,
            'debtor_name': self.debtor_name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'remaining_amount': float(self.remaining_amount),
            'collection_percentage': float(self.collection_percentage),
        }
        if include_related:
            data['collections'] = [c.to_dict() for c in self.collections]
            data['actions'] = [a.to_dict() for a in self.actions]
        return data

    def __repr__(self):
        return f'<Enforcement {self.enforcement_number}>'


class EnforcementCollection(db.Model):
    __tablename__ = 'enforcement_collections'

    id = db.Column(db.Integer, primary_key=True)
    enforcement_id = db.Column(db.Integer, db.ForeignKey('enforcements.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    collection_date = db.Column(db.Date, nullable=False)
    collection_method = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'enforcement_id': self.enforcement_id,
            'amount': float(self.amount) if self.amount is not None else None,
            'collection_date': self.collection_date.isoformat() if self.collection_date else None,
            'collection_method': self.collection_method,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EnforcementAction(db.Model):
    __tablename__ = 'enforcement_actions'

    id = db.Column(db.Integer, primary_key=True)
    enforcement_id = db.Column(db.Integer, db.ForeignKey('enforcements.id'), nullable=False)
    action_description = db.Column(db.Text, nullable=False)
    action_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'enforcement_id': self.enforcement_id,
            'action_description': self.action_description,
            'action_date': self.action_date.isoformat() if self.action_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
