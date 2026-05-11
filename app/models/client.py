from datetime import datetime
from app.extensions import db
from app.models._encryption import EncryptedFieldsMixin, register_encrypt_on_flush


class Client(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_number = db.Column(db.String(50), nullable=True)
    client_type = db.Column(db.String(20), default='individual')
    full_name = db.Column(db.String(300), nullable=False)
    full_name_en = db.Column(db.String(300), nullable=True)
    # Encrypted at rest. Stored as Fernet ciphertext (Text). Search uses
    # `_national_id_idx` — a per-tenant HMAC of the normalized digits.
    _national_id = db.Column('national_id', db.Text, nullable=True)
    _national_id_idx = db.Column('national_id_idx', db.String(64), nullable=True, index=True)
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
    # Encrypted at rest. Access via the `internal_notes` hybrid_property below —
    # it transparently encrypts on assign and decrypts on read.
    _internal_notes = db.Column('internal_notes', db.Text, nullable=True)
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

    @property
    def internal_notes(self):
        return self._enc_get(self._internal_notes)

    @internal_notes.setter
    def internal_notes(self, value):
        self._internal_notes = self._enc_set(value)

    @property
    def national_id(self):
        return self._enc_get(self._national_id)

    @national_id.setter
    def national_id(self, value):
        # Normalize: strip + drop common formatting chars. Egyptian IDs are
        # 14 digits, Saudi IDs are 10 — both are digits-only when "real".
        if value is None or value == '':
            self._national_id = None
            self._national_id_idx = None
            return
        normalized = ''.join(c for c in str(value) if c.isdigit())
        if not normalized:
            normalized = str(value).strip()
        self._national_id = self._enc_set(value)
        if self.tenant_id:
            from app.services.encryption import blind_index
            self._national_id_idx = blind_index(normalized, self.tenant_id)
        # If tenant_id not set yet, flush hook will compute the index.

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


register_encrypt_on_flush(Client, ['_internal_notes', '_national_id'])


# Compute / refresh national_id blind index at flush time if it's missing
# (e.g. setter ran before tenant_id was assigned).
from sqlalchemy import event as _sa_event  # noqa: E402

@_sa_event.listens_for(Client, 'before_insert')
@_sa_event.listens_for(Client, 'before_update')
def _refresh_client_national_id_idx(mapper, connection, target):
    from app.services.encryption import blind_index, decrypt, is_encrypted
    if not target.tenant_id:
        return
    raw = target._national_id
    if not raw:
        target._national_id_idx = None
        return
    if target._national_id_idx:
        return  # already set
    # Recover plaintext for indexing (raw may be ciphertext after the
    # register_encrypt_on_flush hook above ran for the same target).
    try:
        plain = decrypt(raw, target.tenant_id) if is_encrypted(raw) else raw
    except Exception:
        return
    if plain:
        normalized = ''.join(c for c in str(plain) if c.isdigit()) or str(plain).strip()
        target._national_id_idx = blind_index(normalized, target.tenant_id)


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
