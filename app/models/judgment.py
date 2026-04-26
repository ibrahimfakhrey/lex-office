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

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'case_id': self.case_id,
            'case_number': self.case.case_number if self.case else None,
            'judgment_date': self.judgment_date.isoformat() if self.judgment_date else None,
            'court_id': self.court_id,
            'court_name': self.court.name if self.court else None,
            'judgment_type': self.judgment_type,
            'result': self.result,
            'judgment_text': self.judgment_text,
            'judgment_file_path': self.judgment_file_path,
            'judge_name': self.judge_name,
            'awarded_amount': float(self.awarded_amount) if self.awarded_amount is not None else None,
            'notes': self.notes,
            'appeal_tracking_enabled': self.appeal_tracking_enabled,
            'appeal_type': self.appeal_type,
            'appeal_deadline': self.appeal_deadline.isoformat() if self.appeal_deadline else None,
            'appeal_notification_30d': self.appeal_notification_30d,
            'appeal_notification_14d': self.appeal_notification_14d,
            'appeal_notification_7d': self.appeal_notification_7d,
            'appeal_notification_3d': self.appeal_notification_3d,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Judgment {self.judgment_date} - {self.result}>'
