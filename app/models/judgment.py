from datetime import datetime
from app.extensions import db


class Judgment(db.Model):
    __tablename__ = 'judgments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    judgment_date = db.Column(db.Date, nullable=False)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=True)
    judgment_type = db.Column(db.String(30), nullable=False)
    result = db.Column(db.String(30), nullable=False)
    judgment_text = db.Column(db.Text, nullable=True)
    judgment_file_path = db.Column(db.String(500), nullable=True)
    judge_name = db.Column(db.String(200), nullable=True)
    awarded_amount = db.Column(db.Numeric(12, 2), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Appeal tracking
    appeal_tracking_enabled = db.Column(db.Boolean, default=False)
    appeal_type = db.Column(db.String(20), nullable=True)
    appeal_deadline = db.Column(db.Date, nullable=True)
    appeal_notification_30d = db.Column(db.Boolean, default=False)
    appeal_notification_14d = db.Column(db.Boolean, default=False)
    appeal_notification_7d = db.Column(db.Boolean, default=False)
    appeal_notification_3d = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    court = db.relationship('Court')
    enforcement = db.relationship('Enforcement', backref='judgment', uselist=False)

    def __repr__(self):
        return f'<Judgment {self.judgment_date} - {self.result}>'
