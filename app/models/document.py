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

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_name': self.client.full_name if self.client else None,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'session_id': self.session_id,
            'doc_type': self.doc_type,
            'name': self.name,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'doc_date': self.doc_date.isoformat() if self.doc_date else None,
            'notes': self.notes,
            'ai_summary': self.ai_summary,
            'share_token': self.share_token,
            'share_expires_at': self.share_expires_at.isoformat() if self.share_expires_at else None,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.full_name if self.uploader else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_share_active': self.is_share_active,
            'file_size_display': self.file_size_display,
        }

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

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'name_ar': self.name_ar,
            'template_type': self.template_type,
            'output_format': self.output_format,
            'template_content': self.template_content,
            'auto_fill_fields': self.auto_fill_fields,
            'thumbnail_path': self.thumbnail_path,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<LegalTemplate {self.name}>'
