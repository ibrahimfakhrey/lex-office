"""Hard-block enforcement for T&C + Privacy acceptance.

A `before_request` hook that intercepts any logged-in tenant user whose
last acceptance is behind the current `terms_version` and redirects them
to `/account/accept-terms?next=<path>`. Whitelisted endpoints (login,
public terms/privacy pages, static assets, admin panel, API) bypass the
check so we don't redirect-loop or break unauthenticated access.

Idempotent — safe to install once per app at startup.
"""
from flask import request, redirect, url_for, g

from app.models.terms_acceptance import TermsAcceptance
from app.models.admin import SystemSetting


# Endpoint prefixes that should NEVER be blocked. Anything else that
# successfully loads a tenant user is subject to the check.
_BYPASS_ENDPOINT_PREFIXES = (
    'static',           # asset files
    'auth.',            # login, logout, OTP, password reset
    'public.',          # /terms, /privacy, /security, /account/delete,
                        # /account/accept-terms — the destination itself
    'admin.',           # super-admin panel — admins don't accept tenant terms
    'admin_billing.',
    'admin_settings.',
    'admin_notifications.',
    'admin_auth.',
    'admin_faq.',
    'admin_rbac.',
    'onboarding.',      # plan-picker / setup — block on enforcement would
                        # collide with the existing onboarding redirect
)


def _is_bypassed():
    ep = request.endpoint or ''
    if ep.startswith(_BYPASS_ENDPOINT_PREFIXES):
        return True
    # API has its own JWT/auth flow; never block JSON callers
    if request.path.startswith('/api/'):
        return True
    if request.path.startswith('/static/'):
        return True
    return False


def _logged_in_tenant_user():
    """Return the logged-in tenant User or None, without enforcing login.

    Mirrors public.routes._current_user_or_none but local so we don't
    pull a hook dependency on a blueprint module.
    """
    try:
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from app.models.user import User
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if not uid:
            return None
        user = User.query.get(int(uid))
        if not user or not user.is_active:
            return None
        if not user.tenant or not user.tenant.is_active:
            return None
        return user
    except Exception:
        return None


def install_terms_enforcement(app):
    """Register the before_request hook on the Flask app."""

    @app.before_request
    def _enforce_terms_acceptance():
        if _is_bypassed():
            return None

        user = _logged_in_tenant_user()
        if user is None:
            # Not logged in — let the route's own decorator handle redirect.
            return None

        current_version = SystemSetting.get('terms_version', '1.0') or '1.0'
        accepted = (TermsAcceptance.query
                    .filter_by(user_id=user.id, version=current_version)
                    .first())
        if accepted is not None:
            return None

        # Redirect to the acceptance page, preserving the original path
        # so the user lands back where they intended once they accept.
        return redirect(url_for('public.accept_terms', next=request.full_path))
