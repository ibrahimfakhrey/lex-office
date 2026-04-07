from datetime import datetime
from app.extensions import db


class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    session_time = db.Column(db.Time, nullable=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=True)
    circuit = db.Column(db.String(100), nullable=True)
    session_type = db.Column(db.String(30), nullable=True)
    preparation_notes = db.Column(db.Text, nullable=True)
    result = db.Column(db.String(30), nullable=True)
    result_summary = db.Column(db.Text, nullable=True)
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

    def __repr__(self):
        return f'<Session {self.session_date} - Case {self.case_id}>'
