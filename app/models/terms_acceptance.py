"""Combined Terms & Conditions + Privacy Policy acceptance log.

One row per (user, terms version). Re-accepting the same version is a
no-op (unique constraint). Bumping `SystemSetting['terms_version']`
implicitly invalidates every prior acceptance — the enforcement
middleware will redirect such users to the accept page on their next
request.

Only tenant users are tracked here — super-admin acceptance is not in
scope.
"""
from datetime import datetime

from app.extensions import db


class TermsAcceptance(db.Model):
    __tablename__ = 'terms_acceptances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    version = db.Column(db.String(32), nullable=False)
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)   # IPv6 fits
    user_agent = db.Column(db.Text, nullable=True)

    user = db.relationship('User')
    tenant = db.relationship('Tenant')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'version', name='uq_terms_acceptances_user_version'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'version': self.version,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
        }

    def __repr__(self):
        return f'<TermsAcceptance user={self.user_id} v={self.version}>'
