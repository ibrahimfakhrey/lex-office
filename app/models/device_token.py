"""DeviceToken model — stores FCM tokens per user device for push notifications."""
from datetime import datetime
from app.extensions import db


class DeviceToken(db.Model):
    __tablename__ = 'device_tokens'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # fcm_token is nullable now — iOS devices behind VPN may only have apns_token
    fcm_token = db.Column(db.Text, nullable=True, unique=True, index=True)
    # apns_token: raw APNs device token (hex), iOS only — used as fallback when FCM is blocked
    apns_token = db.Column(db.Text, nullable=True, index=True)
    platform = db.Column(db.String(16), nullable=False)  # 'ios' | 'android' | 'web'
    device_name = db.Column(db.String(120), nullable=True)
    app_version = db.Column(db.String(32), nullable=True)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='device_tokens')

    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'device_name': self.device_name,
            'app_version': self.app_version,
            'has_fcm': bool(self.fcm_token),
            'has_apns': bool(self.apns_token),
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
