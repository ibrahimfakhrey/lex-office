from datetime import datetime
from app.extensions import db
from app.models._encryption import EncryptedFieldsMixin, register_encrypt_on_flush


class Session(db.Model, EncryptedFieldsMixin):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    session_time = db.Column(db.Time, nullable=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=True)
    circuit = db.Column(db.String(100), nullable=True)
    session_type = db.Column(db.String(30), nullable=True)
    _preparation_notes = db.Column('preparation_notes', db.Text, nullable=True)
    result = db.Column(db.String(30), nullable=True)
    _result_summary = db.Column('result_summary', db.Text, nullable=True)
    next_session_date = db.Column(db.Date, nullable=True)
    minutes_file_path = db.Column(db.String(500), nullable=True)
    responsible_lawyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_48h_sent = db.Column(db.Boolean, default=False)
    notification_24h_sent = db.Column(db.Boolean, default=False)
    notification_3h_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    court = db.relationship('Court')
    responsible_lawyer = db.relationship('User', backref='assigned_sessions')
    session_documents = db.relationship('Document', backref='session', lazy='dynamic')

    @property
    def preparation_notes(self):
        return self._enc_get(self._preparation_notes)

    @preparation_notes.setter
    def preparation_notes(self, value):
        self._preparation_notes = self._enc_set(value)

    @property
    def result_summary(self):
        return self._enc_get(self._result_summary)

    @result_summary.setter
    def result_summary(self, value):
        self._result_summary = self._enc_set(value)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'case_subject': self.case.subject if self.case else None,
            'session_date': self.session_date.isoformat() if self.session_date else None,
            'session_time': self.session_time.strftime('%H:%M') if self.session_time else None,
            'court_id': self.court_id,
            'court_name': self.court.name if self.court else None,
            'circuit': self.circuit,
            'session_type': self.session_type,
            'preparation_notes': self.preparation_notes,
            'result': self.result,
            'result_summary': self.result_summary,
            'next_session_date': self.next_session_date.isoformat() if self.next_session_date else None,
            'minutes_file_path': self.minutes_file_path,
            'responsible_lawyer_id': self.responsible_lawyer_id,
            'responsible_lawyer_name': self.responsible_lawyer.full_name if self.responsible_lawyer else None,
            'notification_48h_sent': self.notification_48h_sent,
            'notification_24h_sent': self.notification_24h_sent,
            'notification_3h_sent': self.notification_3h_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Session {self.session_date} - Case {self.case_id}>'


register_encrypt_on_flush(Session, ['_preparation_notes', '_result_summary'])
