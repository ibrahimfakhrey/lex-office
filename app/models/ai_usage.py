"""Per-call AI usage log for governance, billing, and the admin dashboard.

Every successful Claude call writes one row. Failed calls also write rows
(with success=False) so the admin can see if a tenant is hammering the API
with bad requests, or if there's a service-level issue.

The cost is computed from the model + token counts at call time using
PRICING in app/services/ai_usage.py — pricing changes in code do not
retroactively rewrite history.
"""
from datetime import datetime
from app.extensions import db


class AIUsageEvent(db.Model):
    __tablename__ = 'ai_usage_events'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True, index=True,
    )
    # Logical feature key — judgment_extract, poa_extract, document_qa, etc.
    feature = db.Column(db.String(50), nullable=False, index=True)
    model = db.Column(db.String(50), nullable=False)

    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    cache_creation_input_tokens = db.Column(db.Integer, nullable=False, default=0)
    cache_read_input_tokens = db.Column(db.Integer, nullable=False, default=0)

    # USD with 6 decimals — Numeric is stable across drivers; Haiku at minimum
    # call (~50 in / 30 out) costs ~$0.00020, so 6 decimals is sufficient.
    cost_usd = db.Column(db.Numeric(10, 6), nullable=False, default=0)

    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True, nullable=False,
    )

    tenant = db.relationship('Tenant')
    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant.name if self.tenant else None,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'feature': self.feature,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cache_creation_input_tokens': self.cache_creation_input_tokens,
            'cache_read_input_tokens': self.cache_read_input_tokens,
            'cost_usd': float(self.cost_usd) if self.cost_usd is not None else 0.0,
            'success': self.success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        status = 'OK' if self.success else 'FAIL'
        return f'<AIUsageEvent t={self.tenant_id} {self.feature} {status}>'
