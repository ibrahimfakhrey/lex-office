"""Public-facing legal pages (no auth required).

Required by App Store / Play Store policies:
- /terms       Terms of Service
- /privacy     Privacy Policy
- /account/delete  Public account deletion page (Google Play requirement)
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.models.admin import SystemSetting
from app.models.terms_acceptance import TermsAcceptance

public_bp = Blueprint('public', __name__)


def _current_user_or_none():
    """Resolve the logged-in tenant user without enforcing login.

    Returns the User if a valid JWT cookie is present and the user is
    active; otherwise None. Used by /terms and /privacy to optionally
    surface the acceptance widget for logged-in viewers.
    """
    try:
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


def _terms_context():
    """Shared template context for /terms and /privacy."""
    user = _current_user_or_none()
    current_version = SystemSetting.get('terms_version', '1.0') or '1.0'
    acceptance = None
    if user is not None:
        acceptance = (TermsAcceptance.query
                      .filter_by(user_id=user.id, version=current_version)
                      .first())
    return {
        'current_user': user,
        'terms_version': current_version,
        'terms_acceptance': acceptance,
    }


@public_bp.route('/terms')
def terms():
    return render_template('public/terms.html', **_terms_context())


@public_bp.route("/security")
def security():
    return render_template("public/security.html")

@public_bp.route("/privacy")
def privacy():
    return render_template('public/privacy.html', **_terms_context())


def _client_ip():
    """Pick the user-facing IP — honor a forward header if the app is
    behind nginx/a CDN, fall back to remote_addr."""
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        # First entry in the chain is the originator
        return fwd.split(',')[0].strip()[:45]
    return (request.remote_addr or '')[:45]


@public_bp.route('/account/accept-terms', methods=['GET', 'POST'])
def accept_terms():
    """Record the logged-in user's acceptance of the current T&C +
    Privacy version. GET renders a standalone full-page version used
    by the enforcement hook when the user's last accepted version is
    behind the current one. POST records and redirects.
    """
    user = _current_user_or_none()
    if user is None:
        # Not logged in — bounce to login, then back here.
        return redirect(url_for('auth.login', next=request.path))

    current_version = SystemSetting.get('terms_version', '1.0') or '1.0'

    if request.method == 'POST':
        if not request.form.get('agree'):
            flash('يجب الموافقة على الشروط للمتابعة', 'danger')
            return redirect(url_for('public.accept_terms'))

        # Idempotent: the UNIQUE(user_id, version) constraint is the source
        # of truth. A pre-check + insert is racy if the user double-clicks;
        # the IntegrityError that arrives milliseconds apart should be
        # treated as success, not as a 500.
        existing = (TermsAcceptance.query
                    .filter_by(user_id=user.id, version=current_version)
                    .first())
        if existing is None:
            acc = TermsAcceptance(
                user_id=user.id,
                tenant_id=user.tenant_id,
                version=current_version,
                ip_address=_client_ip(),
                user_agent=(request.headers.get('User-Agent') or '')[:4096],
            )
            db.session.add(acc)
            try:
                db.session.commit()
            except IntegrityError:
                # Concurrent insert from the same user won the race — the
                # row is now there, the user effectively got their wish.
                db.session.rollback()

        flash('تم تسجيل موافقتك بنجاح', 'success')
        next_path = (request.form.get('next') or '').strip()
        if next_path and next_path.startswith('/') and not next_path.startswith('//'):
            return redirect(next_path)
        return redirect(url_for('dashboard.home'))

    # GET — render the standalone full-page acceptance screen.
    acceptance = (TermsAcceptance.query
                  .filter_by(user_id=user.id, version=current_version)
                  .first())
    return render_template(
        'public/accept_terms.html',
        current_user=user,
        terms_version=current_version,
        terms_acceptance=acceptance,
    )


@public_bp.route('/account/delete', methods=['GET', 'POST'])
def account_delete():
    """Public web flow for account deletion (no auth needed before action).

    User enters email + password. If valid, mark account for deletion (90-day
    grace period). They can cancel by logging back in to the app within 90 days.
    """
    if request.method == 'GET':
        return render_template('public/account_delete.html')

    email = (request.form.get('email') or '').strip().lower()
    password = (request.form.get('password') or '').strip()
    reason = (request.form.get('reason') or '').strip() or None

    if not email or not password:
        flash('البريد الإلكتروني وكلمة المرور مطلوبان', 'error')
        return render_template('public/account_delete.html')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash('بيانات الدخول غير صحيحة', 'error')
        return render_template('public/account_delete.html')

    if user.deletion_scheduled_at:
        final_at = user.deletion_scheduled_at + timedelta(days=90)
        return render_template(
            'public/account_delete_success.html',
            final_at=final_at,
            scheduled_at=user.deletion_scheduled_at,
            already=True,
        )

    user.deletion_scheduled_at = datetime.utcnow()
    user.deletion_reason = reason
    db.session.commit()

    final_at = user.deletion_scheduled_at + timedelta(days=90)
    return render_template(
        'public/account_delete_success.html',
        final_at=final_at,
        scheduled_at=user.deletion_scheduled_at,
        already=False,
    )
