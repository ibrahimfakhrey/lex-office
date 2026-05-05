"""Admin authentication and audit decorators."""
from functools import wraps
from flask import session, redirect, url_for, flash, g, request
from app.extensions import db
from app.models.admin import AdminUser, AdminAuditLog


def super_admin_required(f):
    """Ensure the current request has a logged-in active super admin.

    Loads `g.current_admin` for use in views.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            flash('يرجى تسجيل الدخول كمدير', 'warning')
            return redirect(url_for('admin.login'))

        admin = AdminUser.query.get(admin_id)
        if not admin or not admin.is_active:
            session.pop('admin_id', None)
            session.pop('admin_mfa_verified', None)
            flash('الحساب غير نشط', 'danger')
            return redirect(url_for('admin.login'))

        # Enforce MFA — if MFA is enabled but session not verified, force MFA
        if admin.mfa_enabled and not session.get('admin_mfa_verified'):
            return redirect(url_for('admin.mfa'))

        g.current_admin = admin
        return f(*args, **kwargs)
    return decorated


def admin_permission_required(module, action='view', write_action=None):
    """Gate a route on (module, action) RBAC. Super Admin role short-circuits.

    For routes that handle both GET and POST, pass `write_action` separately
    (e.g. action='view', write_action='edit') so the POST path is checked
    against the correct permission. If `write_action` is omitted, the same
    `action` applies to both methods.
    """
    def decorator(f):
        @wraps(f)
        @super_admin_required
        def decorated(*args, **kwargs):
            admin = g.current_admin
            needed = write_action if (write_action and request.method == 'POST') else action
            if admin.has_admin_permission(module, needed):
                return f(*args, **kwargs)
            flash('ليس لديك صلاحية للوصول لهذه الصفحة', 'danger')
            return redirect(url_for('admin.index'))
        return decorated
    return decorator


def role_required(*allowed_roles):
    """Restrict route to specific admin roles."""
    def decorator(f):
        @wraps(f)
        @super_admin_required
        def decorated(*args, **kwargs):
            if g.current_admin.role not in allowed_roles:
                flash('ليس لديك صلاحية للوصول لهذه الصفحة', 'danger')
                return redirect(url_for('admin.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def log_action(action_type, entity_type=None, entity_id=None,
               old_value=None, new_value=None, description=None):
    """Write an audit log entry.

    Call from inside any admin view that mutates data.
    """
    admin = getattr(g, 'current_admin', None)
    log = AdminAuditLog(
        admin_id=admin.id if admin else None,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        description=description,
        ip_address=request.remote_addr,
        user_agent=(request.headers.get('User-Agent') or '')[:500],
    )
    db.session.add(log)
    # Caller is responsible for committing.
    return log
