from datetime import datetime
from app.extensions import db


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=True)
    doc_type = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    doc_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    share_token = db.Column(db.String(100), nullable=True)
    share_expires_at = db.Column(db.DateTime, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploader = db.relationship('User')
    client = db.relationship('Client')

    @property
    def is_share_active(self):
        if self.share_token and self.share_expires_at:
            return datetime.utcnow() < self.share_expires_at
        return False

    @property
    def file_size_display(self):
        if not self.file_size:
            return '0 KB'
        if self.file_size < 1024:
            return f'{self.file_size} B'
        if self.file_size < 1024 * 1024:
            return f'{self.file_size / 1024:.1f} KB'
        return f'{self.file_size / (1024 * 1024):.1f} MB'

    def __repr__(self):
        return f'<Document {self.name}>'


class LegalTemplate(db.Model):
    __tablename__ = 'legal_templates'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    template_type = db.Column(db.String(30), nullable=False)
    output_format = db.Column(db.String(10), nullable=False)
    template_content = db.Column(db.Text, nullable=False)
    auto_fill_fields = db.Column(db.JSON, nullable=True)
    thumbnail_path = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<LegalTemplate {self.name}>'
