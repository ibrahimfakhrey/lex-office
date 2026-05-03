from datetime import datetime
from app.extensions import db
import bcrypt


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    permissions = db.relationship('RolePermission', backref='role', lazy='dynamic')
    users = db.relationship('User', backref='role', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
        }

    def __repr__(self):
        return f'<Role {self.name}>'


class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    scope = db.Column(db.String(50), default='all')

    __table_args__ = (db.UniqueConstraint('module', 'action', 'scope'),)

    def __repr__(self):
        return f'<Permission {self.module}.{self.action}.{self.scope}>'


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
    constraint_value = db.Column(db.String(100), nullable=True)

    permission = db.relationship('Permission')

    __table_args__ = (db.UniqueConstraint('role_id', 'permission_id'),)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    full_name_en = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    mfa_enabled = db.Column(db.Boolean, default=False)
    mfa_secret = db.Column(db.String(100), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    avatar_path = db.Column(db.String(500), nullable=True)
    notification_preferences = db.Column(db.JSON, nullable=True)
    quiet_hours_start = db.Column(db.Time, nullable=True)
    quiet_hours_end = db.Column(db.Time, nullable=True)
    daily_summary_enabled = db.Column(db.Boolean, default=False)

    # OTP fields
    otp_code = db.Column(db.String(10), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_attempts = db.Column(db.Integer, default=0)

    # Login tracking
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index(
            'uq_users_phone_not_null',
            'phone',
            unique=True,
            postgresql_where=db.text('phone IS NOT NULL'),
        ),
    )

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        self.password_changed_at = datetime.utcnow()

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def has_permission(self, module, action):
        """Check if user's role has a specific permission."""
        role_perms = RolePermission.query.filter_by(role_id=self.role_id).all()
        for rp in role_perms:
            perm = rp.permission
            if perm.module == module and perm.action == action:
                return True, rp.constraint_value
        return False, None

    @property
    def is_manager(self):
        return self.role and self.role.name == 'manager'

    @property
    def is_partner(self):
        return self.role and self.role.name == 'partner'

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'email': self.email,
            'full_name': self.full_name,
            'full_name_en': self.full_name_en,
            'phone': self.phone,
            'role_id': self.role_id,
            'role_name': self.role.name if self.role else None,
            'role_name_ar': self.role.name_ar if self.role else None,
            'is_active': self.is_active,
            'mfa_enabled': self.mfa_enabled,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'avatar_path': self.avatar_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.email}>'


class Invitation(db.Model):
    __tablename__ = 'invitations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship('Tenant')
    role = db.relationship('Role')
    inviter = db.relationship('User')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'email': self.email,
            'role_id': self.role_id,
            'invited_by': self.invited_by,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired,
            'is_accepted': self.is_accepted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
