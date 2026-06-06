from datetime import datetime
from app.extensions import db
from app.models._encryption import EncryptedFieldsMixin, register_encrypt_on_flush


class Payment(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    invoice_id = db.Column(
        db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'),
        nullable=True, index=True,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    reference_number = db.Column(db.String(200), nullable=True)
    receipt_file_path = db.Column(db.String(500), nullable=True)
    _notes = db.Column('notes', db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recorder = db.relationship('User')
    invoice = db.relationship(
        'Invoice',
        backref=db.backref(
            'linked_payment',
            uselist=False,
            cascade='all, delete-orphan',
            passive_deletes=True,
        ),
    )

    @property
    def notes(self):
        return self._enc_get(self._notes)

    @notes.setter
    def notes(self, value):
        self._notes = self._enc_set(value)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'invoice_id': self.invoice_id,
            'amount': float(self.amount) if self.amount is not None else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'reference_number': self.reference_number,
            'receipt_file_path': self.receipt_file_path,
            'notes': self.notes,
            'recorded_by': self.recorded_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Payment {self.amount} - Client {self.client_id}>'


register_encrypt_on_flush(Payment, ['_notes'])


class Invoice(db.Model, EncryptedFieldsMixin):
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
    _notes = db.Column('notes', db.Text, nullable=True)
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

    @property
    def notes(self):
        return self._enc_get(self._notes)

    @notes.setter
    def notes(self, value):
        self._notes = self._enc_set(value)

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'invoice_number': self.invoice_number,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'status': self.status,
            'subtotal': float(self.subtotal) if self.subtotal is not None else None,
            'discount_type': self.discount_type,
            'discount_value': float(self.discount_value) if self.discount_value is not None else None,
            'tax_rate': float(self.tax_rate) if self.tax_rate is not None else None,
            'tax_amount': float(self.tax_amount) if self.tax_amount is not None else None,
            'total': float(self.total) if self.total is not None else None,
            'notes': self.notes,
            'sent_via': self.sent_via,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


register_encrypt_on_flush(Invoice, ['_notes'])


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'description': self.description,
            'item_type': self.item_type,
            'amount': float(self.amount) if self.amount is not None else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Expense(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    expense_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    _description = db.Column('description', db.Text, nullable=True)
    receipt_file_path = db.Column(db.String(500), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client')
    recorder = db.relationship('User')

    @property
    def description(self):
        return self._enc_get(self._description)

    @description.setter
    def description(self, value):
        self._description = self._enc_set(value)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'expense_type': self.expense_type,
            'amount': float(self.amount) if self.amount is not None else None,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'description': self.description,
            'receipt_file_path': self.receipt_file_path,
            'recorded_by': self.recorded_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


register_encrypt_on_flush(Expense, ['_description'])
