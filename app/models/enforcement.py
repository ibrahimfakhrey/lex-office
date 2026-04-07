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


class EnforcementAction(db.Model):
    __tablename__ = 'enforcement_actions'

    id = db.Column(db.Integer, primary_key=True)
    enforcement_id = db.Column(db.Integer, db.ForeignKey('enforcements.id'), nullable=False)
    action_description = db.Column(db.Text, nullable=False)
    action_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
