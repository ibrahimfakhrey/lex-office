"""Public-facing legal pages (no auth required).

Required by App Store / Play Store policies:
- /terms       Terms of Service
- /privacy     Privacy Policy
- /account/delete  Public account deletion page (Google Play requirement)
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for

from app.extensions import db
from app.models.user import User

public_bp = Blueprint('public', __name__)


@public_bp.route('/terms')
def terms():
    return render_template('public/terms.html')


@public_bp.route("/security")
def security():
    return render_template("public/security.html")

@public_bp.route("/privacy")
def privacy():
    return render_template('public/privacy.html')


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
