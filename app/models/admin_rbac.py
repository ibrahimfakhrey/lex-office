"""Admin RBAC — Roles and per-role permissions.

Distinct from tenant-side `Role`/`Permission` models. These tables only gate
access to the super-admin panel.

Cardinality: one AdminUser → one AdminRole. Each AdminRole has many
AdminRolePermission rows (one per allowed (module, action) pair). Absence
of a row = denied.
"""
from datetime import datetime
from app.extensions import db


class AdminRole(db.Model):
    __tablename__ = 'admin_roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name_ar = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = db.relationship(
        'AdminRolePermission',
        backref='role',
        cascade='all, delete-orphan',
        lazy='joined',
    )

    @property
    def admin_count(self) -> int:
        # Use the backref defined on AdminUser
        return len(self.admins) if hasattr(self, 'admins') else 0

    def has_permission(self, module: str, action: str) -> bool:
        if self.is_system:
            return True
        return any(p.module == module and p.action == action for p in self.permissions)

    def permission_set(self) -> set:
        return {(p.module, p.action) for p in self.permissions}


class AdminRolePermission(db.Model):
    __tablename__ = 'admin_role_permissions'
    __table_args__ = (
        db.UniqueConstraint('role_id', 'module', 'action', name='uq_admin_role_perm'),
    )

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(
        db.Integer,
        db.ForeignKey('admin_roles.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    module = db.Column(db.String(60), nullable=False)
    action = db.Column(db.String(30), nullable=False)
