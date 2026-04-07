from datetime import datetime
from app.extensions import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    reference_number = db.Column(db.String(200), nullable=True)
    receipt_file_path = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recorder = db.relationship('User')

    def __repr__(self):
        return f'<Payment {self.amount} - Client {self.client_id}>'


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    issue_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='draft')
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    discount_type = db.Column(db.String(20), nullable=True)
    discount_value = db.Column(db.Numeric(12, 2), nullable=True)
    tax_rate = db.Column(db.Numeric(5, 2), default=14.00)
    tax_amount = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text, nullable=True)
    sent_via = db.Column(db.String(20), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')

    def generate_invoice_number(self, tenant_id):
        last = Invoice.query.filter_by(tenant_id=tenant_id).order_by(Invoice.id.desc()).first()
        if last and last.invoice_number:
            try:
                num = int(last.invoice_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        self.invoice_number = f'INV-{num:05d}'

    def calculate_totals(self):
        self.subtotal = sum(float(item.amount) for item in self.items)
        discount = 0
        if self.discount_type == 'percentage' and self.discount_value:
            discount = float(self.subtotal) * float(self.discount_value) / 100
        elif self.discount_type == 'fixed' and self.discount_value:
            discount = float(self.discount_value)
        after_discount = float(self.subtotal) - discount
        self.tax_amount = after_discount * float(self.tax_rate or 0) / 100
        self.total = after_discount + float(self.tax_amount)

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    expense_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    receipt_file_path = db.Column(db.String(500), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client')
    recorder = db.relationship('User')
