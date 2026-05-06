"""Admin authentication — login, logout, MFA, password reset."""
from datetime import datetime, timedelta
from flask import (
    render_template, request, redirect, url_for, flash, session, g
)
from app.extensions import db, limiter
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action
from app.models.admin import AdminUser
from app.utils.helpers import generate_otp
from app.utils.validators import validate_email, validate_password
from app.services.email_service import send_email

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 30


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def login():
    """Admin login (step 1 — email + password)."""
    if session.get('admin_id') and session.get('admin_mfa_verified'):
        return redirect(url_for('admin.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        if not validate_email(email):
            flash('البريد الإلكتروني غير صالح', 'danger')
            return render_template('admin/auth/login.html', email=email)

        admin = AdminUser.query.filter_by(email=email).first()
        if not admin:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
            return render_template('admin/auth/login.html', email=email)

        # Lockout check
        if admin.is_locked:
            remaining = (admin.locked_until - datetime.utcnow()).seconds // 60
            flash(f'الحساب مقفل لمدة {remaining} دقيقة بسبب محاولات فاشلة', 'danger')
            return render_template('admin/auth/login.html', email=email)

        if not admin.check_password(password):
            admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
            if admin.failed_login_attempts >= LOGIN_MAX_ATTEMPTS:
                admin.locked_until = datetime.utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
                admin.failed_login_attempts = 0
                flash(f'تم قفل الحساب لمدة {LOGIN_LOCKOUT_MINUTES} دقيقة بسبب المحاوالت الفاشلة', 'danger')
            else:
                flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
            db.session.commit()
            return render_template('admin/auth/login.html', email=email)

        if not admin.is_active:
            flash('الحساب غير نشط', 'danger')
            return render_template('admin/auth/login.html', email=email)

        # Success — reset counters, set session
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.last_login_at = datetime.utcnow()
        admin.last_login_ip = request.remote_addr
        db.session.commit()

        session.permanent = True
        session['admin_id'] = admin.id
        session['admin_mfa_verified'] = not admin.mfa_enabled  # if no MFA, mark verified

        if admin.mfa_enabled:
            return redirect(url_for('admin.mfa'))
        return redirect(url_for('admin.index'))

    return render_template('admin/auth/login.html', email='')


@admin_bp.route('/mfa', methods=['GET', 'POST'])
def mfa():
    """MFA challenge — TOTP code from Google Authenticator etc."""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin.login'))

    admin = AdminUser.query.get(admin_id)
    if not admin or not admin.mfa_enabled:
        session['admin_mfa_verified'] = True
        return redirect(url_for('admin.index'))

    if request.method == 'POST':
        import pyotp
        otp = (request.form.get('otp') or '').strip()
        if admin.mfa_secret and pyotp.TOTP(admin.mfa_secret).verify(otp):
            session['admin_mfa_verified'] = True
            return redirect(url_for('admin.index'))
        flash('رمز التحقق غير صحيح', 'danger')

    return render_template('admin/auth/mfa.html')


@admin_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout admin."""
    session.pop('admin_id', None)
    session.pop('admin_mfa_verified', None)
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    """Request password reset OTP via email."""
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        admin = AdminUser.query.filter_by(email=email).first()
        if admin:
            otp = generate_otp()
            admin.otp_code = otp
            admin.otp_expires_at = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
            from app.models.admin import SystemSetting
            product_name = SystemSetting.get('product_name', 'LexOffice') or 'LexOffice'
            html = f"""
            <div dir='rtl' style='font-family: Tajawal, Arial; padding: 20px;'>
                <h2>إعادة تعيين كلمة المرور — {product_name} Admin</h2>
                <p>رمز التحقق الخاص بك:</p>
                <div style='font-size:28px; font-weight:bold; letter-spacing:6px; padding:16px; background:#f0f4f8; border-radius:8px; text-align:center'>{otp}</div>
                <p>صالح لمدة 15 دقيقة.</p>
            </div>
            """
            send_email(email, f'إعادة تعيين كلمة المرور — {product_name} Admin', html)

        # Always show same message (don't reveal if email exists)
        flash('إذا كان البريد مسجلاً، فستصلك رسالة برمز التحقق', 'info')
        return redirect(url_for('admin.reset_password', email=email))

    return render_template('admin/auth/forgot_password.html')


@admin_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def reset_password():
    """Reset password using OTP."""
    email = (request.args.get('email') or request.form.get('email') or '').strip().lower()

    if request.method == 'POST':
        otp = (request.form.get('otp') or '').strip()
        new_password = request.form.get('new_password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        admin = AdminUser.query.filter_by(email=email).first()
        if not admin or admin.otp_code != otp or not admin.otp_expires_at or datetime.utcnow() > admin.otp_expires_at:
            flash('رمز التحقق غير صحيح أو منتهي الصلاحية', 'danger')
            return render_template('admin/auth/reset_password.html', email=email)

        if new_password != confirm_password:
            flash('كلمتا المرور غير متطابقتين', 'danger')
            return render_template('admin/auth/reset_password.html', email=email)

        valid, msg = validate_password(new_password)
        if not valid:
            flash(msg, 'danger')
            return render_template('admin/auth/reset_password.html', email=email)

        admin.set_password(new_password)
        admin.otp_code = None
        admin.otp_expires_at = None
        db.session.commit()

        flash('تم تغيير كلمة المرور بنجاح. سجل دخولك الآن', 'success')
        return redirect(url_for('admin.login'))

    return render_template('admin/auth/reset_password.html', email=email)
