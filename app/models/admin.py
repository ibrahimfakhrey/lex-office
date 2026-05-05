"""Super Admin Panel models — separate from tenant users."""
from datetime import datetime
import bcrypt
from app.extensions import db


class AdminUser(db.Model):
    """Super admin / staff with access to admin panel only.

    Completely separate from the tenant `User` table. These accounts can
    manage all tenants, plans, billing, and system settings.
    """
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    # super_admin / support_agent / finance_admin (P3 — for now everyone is super_admin)
    role = db.Column(db.String(30), default='super_admin', nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    mfa_enabled = db.Column(db.Boolean, default=False)
    mfa_secret = db.Column(db.String(100), nullable=True)

    # OTP for password reset
    otp_code = db.Column(db.String(10), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)

    # Login tracking
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    # New RBAC link (one admin → one AdminRole)
    role_id = db.Column(
        db.Integer,
        db.ForeignKey('admin_roles.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    admin_role = db.relationship('AdminRole', backref='admins', lazy='joined')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8'),
        )

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and datetime.utcnow() < self.locked_until

    def has_admin_permission(self, module: str, action: str = 'view') -> bool:
        """Check whether this admin's role grants the given (module, action).

        System role (Super Admin) always returns True; admins with no role
        return False.
        """
        if not self.admin_role:
            return False
        return self.admin_role.has_permission(module, action)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'mfa_enabled': self.mfa_enabled,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<AdminUser {self.email}>'


class AdminAuditLog(db.Model):
    """Immutable log of every admin action."""
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    # e.g. TENANT_SUSPENDED, PLAN_CREATED, FEATURE_TOGGLED, INVOICE_REFUNDED
    action_type = db.Column(db.String(80), nullable=False)
    # Tenant / Plan / Feature / Invoice / Setting / AdminUser
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    admin = db.relationship('AdminUser')

    def to_dict(self):
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'admin_name': self.admin.full_name if self.admin else None,
            'action_type': self.action_type,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'description': self.description,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TenantFeatureOverride(db.Model):
    """Tenant-level feature override — overrides plan-level flag."""
    __tablename__ = 'tenant_feature_overrides'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    feature_key = db.Column(db.String(80), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # null = permanent
    reason = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship('Tenant')
    creator = db.relationship('AdminUser')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'feature_key', name='uq_tenant_feature'),
    )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.utcnow() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_expired

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'feature_key': self.feature_key,
            'enabled': self.enabled,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'reason': self.reason,
            'is_expired': self.is_expired,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TenantSupportNote(db.Model):
    """Internal admin notes about a tenant (not visible to tenant)."""
    __tablename__ = 'tenant_support_notes'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(500), nullable=True)  # optional attachment
    created_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship('Tenant')
    creator = db.relationship('AdminUser')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'note': self.note,
            'file_path': self.file_path,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SystemSetting(db.Model):
    """Singleton key-value store for system-wide settings.

    Examples of keys:
      - product_name, product_logo, support_email, default_currency
      - terms_url, privacy_url, help_center_url
      - smtp_host, smtp_port, smtp_username, smtp_password, smtp_from
      - maintenance_mode, maintenance_message, maintenance_until
    """
    __tablename__ = 'system_settings'

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.JSON, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = db.relationship('AdminUser')

    @classmethod
    def get(cls, key, default=None):
        s = cls.query.get(key)
        return s.value if s else default

    @classmethod
    def set(cls, key, value, admin_id=None):
        s = cls.query.get(key)
        if s:
            s.value = value
            s.updated_by = admin_id
            s.updated_at = datetime.utcnow()
        else:
            s = cls(key=key, value=value, updated_by=admin_id)
            db.session.add(s)
        return s

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class BroadcastNotification(db.Model):
    """Manual broadcast notifications sent by admins."""
    __tablename__ = 'broadcast_notifications'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    # all / plan / status / single
    audience_type = db.Column(db.String(30), nullable=False, default='all')
    # e.g. {"plan_id": 2} or {"status": "trial"} or {"tenant_id": 5}
    audience_filter = db.Column(db.JSON, nullable=True)
    # list of channels: ['email', 'in_app', 'sms']
    channels = db.Column(db.JSON, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    sent_count = db.Column(db.Integer, default=0)
    read_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('AdminUser')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body,
            'audience_type': self.audience_type,
            'audience_filter': self.audience_filter,
            'channels': self.channels,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'sent_count': self.sent_count,
            'read_count': self.read_count,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
