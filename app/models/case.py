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

    def __repr__(self):
        return f'<Case {self.case_number} - {self.subject}>'
