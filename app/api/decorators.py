"""API authentication and authorization decorators."""
from functools import wraps
from flask import g, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity


def api_login_required(f):
    """Ensure user is authenticated via Bearer token. Returns JSON errors."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({
                'success': False,
                'error': 'unauthorized',
                'message': 'مطلوب تسجيل الدخول',
            }), 401

        user_id = get_jwt_identity()
        from app.models.user import User
        user = User.query.get(int(user_id))

        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'error': 'account_inactive',
                'message': 'الحساب غير نشط',
            }), 401

        if not user.tenant or not user.tenant.is_active:
            return jsonify({
                'success': False,
                'error': 'tenant_inactive',
                'message': 'حساب المكتب غير نشط',
            }), 403

        g.current_user = user
        g.tenant_id = user.tenant_id
        return f(*args, **kwargs)
    return decorated


def api_permission_required(module, action):
    """Check RBAC permission, return JSON 403 on failure."""
    def decorator(f):
        @wraps(f)
        @api_login_required
        def decorated(*args, **kwargs):
            has_perm, constraint = g.current_user.has_permission(module, action)
            if not has_perm:
                return jsonify({
                    'success': False,
                    'error': 'forbidden',
                    'message': 'ليس لديك صلاحية لتنفيذ هذا الإجراء',
                }), 403
            g.permission_constraint = constraint
            return f(*args, **kwargs)
        return decorated
    return decorator


def api_role_required(*roles):
    """Restrict to specific roles, return JSON 403."""
    def decorator(f):
        @wraps(f)
        @api_login_required
        def decorated(*args, **kwargs):
            if g.current_user.role.name not in roles:
                return jsonify({
                    'success': False,
                    'error': 'forbidden',
                    'message': 'ليس لديك الدور المطلوب',
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
