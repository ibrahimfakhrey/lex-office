from datetime import datetime
from app.extensions import db


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_number = db.Column(db.String(50), nullable=True)
    client_type = db.Column(db.String(20), default='individual')
    full_name = db.Column(db.String(300), nullable=False)
    full_name_en = db.Column(db.String(300), nullable=True)
    national_id = db.Column(db.String(20), nullable=True)
    commercial_reg = db.Column(db.String(50), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    nationality = db.Column(db.String(100), nullable=True)
    profession = db.Column(db.String(200), nullable=True)
    governorate = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    street = db.Column(db.String(200), nullable=True)
    building_no = db.Column(db.String(50), nullable=True)
    phone_primary = db.Column(db.String(20), nullable=True)
    phone_secondary = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    whatsapp = db.Column(db.String(20), nullable=True)
    emergency_contact_name = db.Column(db.String(200), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    emergency_contact_relation = db.Column(db.String(100), nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    registrar = db.relationship('User', foreign_keys=[registered_by])
    documents = db.relationship('ClientDocument', backref='client', lazy='dynamic')
    cases = db.relationship('Case', backref='client', lazy='dynamic')
    payments = db.relationship('Payment', backref='client', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='client', lazy='dynamic')
    powers_of_attorney = db.relationship('PowerOfAttorney', backref='client', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='client', lazy='dynamic')

    def generate_client_number(self):
        """Generate sequential client number per tenant."""
        last = Client.query.filter_by(tenant_id=self.tenant_id).order_by(Client.id.desc()).first()
        if last and last.client_number:
            try:
                num = int(last.client_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        self.client_number = f'CLT-{num:05d}'

    @property
    def full_address(self):
        parts = [self.building_no, self.street, self.district, self.city, self.governorate]
        return '، '.join(p for p in parts if p)

    @property
    def total_fees(self):
        return sum(float(c.fee_amount or 0) for c in self.cases)

    @property
    def total_paid(self):
        return sum(float(p.amount) for p in self.payments)

    @property
    def balance(self):
        return self.total_fees - self.total_paid

    def to_dict(self, include_related=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_number': self.client_number,
            'client_type': self.client_type,
            'full_name': self.full_name,
            'full_name_en': self.full_name_en,
            'national_id': self.national_id,
            'commercial_reg': self.commercial_reg,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'nationality': self.nationality,
            'profession': self.profession,
            'governorate': self.governorate,
            'city': self.city,
            'district': self.district,
            'street': self.street,
            'building_no': self.building_no,
            'phone_primary': self.phone_primary,
            'phone_secondary': self.phone_secondary,
            'email': self.email,
            'whatsapp': self.whatsapp,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'emergency_contact_relation': self.emergency_contact_relation,
            'internal_notes': self.internal_notes,
            'registered_by': self.registered_by,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'full_address': self.full_address,
            'total_fees': float(self.total_fees),
            'total_paid': float(self.total_paid),
            'balance': float(self.balance),
        }
        if include_related:
            data['cases_count'] = self.cases.count()
            data['documents_count'] = self.documents.count()
        return data

    def __repr__(self):
        return f'<Client {self.full_name}>'


class ClientDocument(db.Model):
    __tablename__ = 'client_documents'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'document_type': self.document_type,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'uploaded_by': self.uploaded_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
