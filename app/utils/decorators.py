"""Authentication and authorization decorators."""
from functools import wraps
from flask import redirect, url_for, flash, abort, g, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity


def login_required(f):
    """Ensure user is logged in and load current user + tenant."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return redirect(url_for('auth.login'))

        user_id = get_jwt_identity()
        from app.models.user import User
        user = User.query.get(int(user_id))
        if not user or not user.is_active:
            return redirect(url_for('auth.login'))

        if not user.tenant or not user.tenant.is_active:
            flash('حساب المكتب غير نشط', 'danger')
            return redirect(url_for('auth.login'))

        g.current_user = user
        g.tenant_id = user.tenant_id

        # Onboarding check: redirect to setup if tenant has no plan yet
        if not request.path.startswith('/onboarding'):
            if not user.tenant.subscription_plan_id:
                return redirect(url_for('onboarding.setup_office'))

        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Restrict access to specific roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if g.current_user.role.name not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(module, action):
    """Check if user has permission for module.action."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            has_perm, constraint = g.current_user.has_permission(module, action)
            if not has_perm:
                abort(403)
            g.permission_constraint = constraint
            return f(*args, **kwargs)
        return decorated
    return decorator


def manager_only(f):
    """Shortcut: only office manager."""
    return role_required('manager')(f)


def manager_or_partner(f):
    """Shortcut: manager or partner."""
    return role_required('manager', 'partner')(f)


def tenant_filter(query, model):
    """Apply tenant isolation to a query."""
    return query.filter(model.tenant_id == g.tenant_id)
