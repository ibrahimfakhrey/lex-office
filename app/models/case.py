from datetime import datetime
from app.extensions import db


class Court(db.Model):
    __tablename__ = 'courts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    name_en = db.Column(db.String(300), nullable=True)
    court_type = db.Column(db.String(30), nullable=False)
    governorate = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_en': self.name_en,
            'court_type': self.court_type,
            'governorate': self.governorate,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Court {self.name}>'


class Case(db.Model):
    __tablename__ = 'cases'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    case_number = db.Column(db.String(100), nullable=True)
    judicial_year = db.Column(db.String(10), nullable=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=True)
    circuit = db.Column(db.String(100), nullable=True)
    case_type = db.Column(db.String(30), nullable=False)
    subject = db.Column(db.Text, nullable=True)
    opponent_name = db.Column(db.String(300), nullable=True)
    opponent_capacity = db.Column(db.String(200), nullable=True)
    opponent_lawyer = db.Column(db.String(300), nullable=True)
    responsible_lawyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assistant_lawyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    our_client_capacity = db.Column(db.String(30), nullable=True)
    fee_type = db.Column(db.String(20), nullable=True)
    fee_amount = db.Column(db.Numeric(12, 2), nullable=True)
    retainer_paid = db.Column(db.Numeric(12, 2), default=0)
    payment_schedule = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(30), default='new')
    priority = db.Column(db.String(20), default='normal')
    internal_notes = db.Column(db.Text, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    court = db.relationship('Court', backref='cases')
    responsible_lawyer = db.relationship('User', foreign_keys=[responsible_lawyer_id], backref='responsible_cases')
    assistant_lawyer = db.relationship('User', foreign_keys=[assistant_lawyer_id], backref='assisted_cases')
    sessions = db.relationship('Session', backref='case', lazy='dynamic', order_by='Session.session_date.desc()')
    judgments = db.relationship('Judgment', backref='case', lazy='dynamic')
    enforcements = db.relationship('Enforcement', backref='case', lazy='dynamic')
    tasks = db.relationship('Task', backref='case', lazy='dynamic')
    case_payments = db.relationship('Payment', backref='case', lazy='dynamic')
    case_invoices = db.relationship('Invoice', backref='case', lazy='dynamic')
    expenses = db.relationship('Expense', backref='case', lazy='dynamic')
    case_documents = db.relationship('Document', backref='case', lazy='dynamic')

    @property
    def total_paid(self):
        return sum(float(p.amount) for p in self.case_payments)

    @property
    def total_expenses(self):
        return sum(float(e.amount) for e in self.expenses)

    @property
    def remaining_balance(self):
        return float(self.fee_amount or 0) - self.total_paid

    def to_dict(self, include_related=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'case_number': self.case_number,
            'judicial_year': self.judicial_year,
            'court_id': self.court_id,
            'court_name': self.court.name if self.court else None,
            'circuit': self.circuit,
            'case_type': self.case_type,
            'subject': self.subject,
            'opponent_name': self.opponent_name,
            'opponent_capacity': self.opponent_capacity,
            'opponent_lawyer': self.opponent_lawyer,
            'responsible_lawyer_id': self.responsible_lawyer_id,
            'responsible_lawyer_name': self.responsible_lawyer.full_name if self.responsible_lawyer else None,
            'assistant_lawyer_id': self.assistant_lawyer_id,
            'our_client_capacity': self.our_client_capacity,
            'fee_type': self.fee_type,
            'fee_amount': float(self.fee_amount) if self.fee_amount is not None else None,
            'retainer_paid': float(self.retainer_paid) if self.retainer_paid is not None else None,
            'payment_schedule': self.payment_schedule,
            'status': self.status,
            'priority': self.priority,
            'internal_notes': self.internal_notes,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'total_paid': float(self.total_paid),
            'total_expenses': float(self.total_expenses),
            'remaining_balance': float(self.remaining_balance),
        }
        if include_related:
            data['sessions_count'] = self.sessions.count()
            data['judgments_count'] = self.judgments.count()
            data['payments_count'] = self.case_payments.count()
            data['documents_count'] = self.case_documents.count()
        return data

    def __repr__(self):
        return f'<Case {self.case_number} - {self.subject}>'
