"""Authentication routes: Register, Login, OTP, Password Reset, MFA."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies, get_jwt_identity, verify_jwt_in_request
)
from app.extensions import db, limiter, csrf
from app.models.user import User, Role, Invitation
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.utils.helpers import generate_otp, generate_token
from app.utils.validators import validate_email, validate_password, validate_phone
from app.services.email_service import send_otp_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    """Step 1: New subscription registration."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        office_size = request.form.get('office_size', '1-5')

        # Validations
        errors = []
        if not full_name:
            errors.append('الاسم الكامل مطلوب')
        if not validate_email(email):
            errors.append('البريد الإلكتروني غير صالح')
        if not validate_phone(phone):
            errors.append('رقم الهاتف غير صالح')

        valid_pw, pw_msg = validate_password(password)
        if not valid_pw:
            errors.append(pw_msg)

        # Check if email already exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            errors.append('البريد الإلكتروني مسجل بالفعل')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html',
                                   full_name=full_name, email=email, phone=phone)

        # Create tenant placeholder
        tenant = Tenant(name=f'مكتب {full_name}', subscription_status='trial',
                        trial_ends_at=datetime.utcnow() + timedelta(days=14))
        db.session.add(tenant)
        db.session.flush()

        # Get manager role
        manager_role = Role.query.filter_by(name='manager').first()
        if not manager_role:
            flash('خطأ في النظام: الأدوار غير موجودة', 'danger')
            db.session.rollback()
            return render_template('auth/register.html')

        # Create user
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            phone=phone,
            role_id=manager_role.id,
        )
        user.set_password(password)

        # Generate OTP
        otp = generate_otp()
        user.otp_code = otp
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        user.otp_attempts = 0

        db.session.add(user)
        db.session.commit()

        # Send OTP via email (show in dev mode as fallback)
        sent = send_otp_email(email, otp, full_name)
        if not sent:
            flash(f'تم إرسال رمز التحقق (للتطوير: {otp})', 'info')
        else:
            flash('تم إرسال رمز التحقق إلى بريدك الإلكتروني', 'info')

        return redirect(url_for('auth.verify_otp', user_id=user.id))

    return render_template('auth/register.html')


@auth_bp.route('/verify-otp/<int:user_id>', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def verify_otp(user_id):
    """Step 2: OTP verification."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        otp_code = request.form.get('otp', '').strip()

        if user.otp_attempts >= 3:
            flash('تم تجاوز عدد المحاولات المسموح به', 'danger')
            return render_template('auth/verify_otp.html', user_id=user_id)

        if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
            flash('انتهت صلاحية رمز التحقق', 'danger')
            return render_template('auth/verify_otp.html', user_id=user_id)

        if otp_code == user.otp_code:
            user.otp_code = None
            user.otp_expires_at = None
            user.otp_attempts = 0
            user.is_active = True
            db.session.commit()

            # Auto login
            access_token = create_access_token(identity=str(user.id))
            refresh_token = create_refresh_token(identity=str(user.id))
            resp = redirect(url_for('onboarding.setup_office'))
            set_access_cookies(resp, access_token)
            set_refresh_cookies(resp, refresh_token)
            flash('تم التحقق بنجاح!', 'success')
            return resp
        else:
            user.otp_attempts += 1
            db.session.commit()
            flash('رمز التحقق غير صحيح', 'danger')

    return render_template('auth/verify_otp.html', user_id=user_id)


@auth_bp.route('/resend-otp/<int:user_id>', methods=['POST'])
@limiter.limit("3 per hour")
def resend_otp(user_id):
    """Resend OTP code to user's email."""
    user = User.query.get_or_404(user_id)

    # Prevent spamming: don't resend if last OTP was sent less than 60 seconds ago
    if user.otp_expires_at:
        remaining = (user.otp_expires_at - datetime.utcnow()).total_seconds()
        if remaining > 540:  # 9 minutes = was sent less than 1 min ago
            flash('يرجى الانتظار قبل إعادة الإرسال', 'warning')
            return redirect(url_for('auth.verify_otp', user_id=user_id))

    # Revoke old OTP and generate new one
    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    user.otp_attempts = 0
    db.session.commit()

    sent = send_otp_email(user.email, otp, user.full_name)
    if sent:
        flash('تم إرسال رمز تحقق جديد إلى بريدك الإلكتروني', 'success')
    else:
        flash(f'تم إنشاء رمز تحقق جديد (للتطوير: {otp})', 'info')

    return redirect(url_for('auth.verify_otp', user_id=user_id))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per hour")
def login():
    """Daily login."""
    # If already logged in, redirect to dashboard
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            return redirect(url_for('dashboard.index'))
    except Exception:
        pass

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(email=email).first()

        if not user:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
            return render_template('auth/login.html', email=email)

        # Check lockout
        if user.locked_until and datetime.utcnow() < user.locked_until:
            remaining = (user.locked_until - datetime.utcnow()).seconds // 60
            flash(f'الحساب مقفل. حاول مرة أخرى بعد {remaining} دقيقة', 'danger')
            return render_template('auth/login.html', email=email)

        if not user.check_password(password):
            user.login_attempts = (user.login_attempts or 0) + 1
            if user.login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                user.login_attempts = 0
                flash('تم قفل الحساب لمدة 15 دقيقة بسبب محاولات تسجيل دخول كثيرة', 'danger')
            else:
                flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
            db.session.commit()
            return render_template('auth/login.html', email=email)

        if not user.is_active:
            flash('الحساب غير نشط. تواصل مع مدير المكتب', 'danger')
            return render_template('auth/login.html', email=email)

        if not user.tenant or not user.tenant.is_active:
            flash('حساب المكتب غير نشط', 'danger')
            return render_template('auth/login.html', email=email)

        # Check if MFA is required
        if user.mfa_enabled:
            # Store user_id in session temporarily for MFA verification
            return redirect(url_for('auth.verify_mfa', user_id=user.id))

        # Successful login
        user.login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        token_expires = timedelta(days=30) if remember else timedelta(minutes=15)
        access_token = create_access_token(identity=str(user.id), expires_delta=token_expires)
        refresh_token = create_refresh_token(identity=str(user.id))

        resp = redirect(url_for('dashboard.index'))
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        return resp

    return render_template('auth/login.html')


@auth_bp.route('/verify-mfa/<int:user_id>', methods=['GET', 'POST'])
def verify_mfa(user_id):
    """MFA verification step."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        import pyotp
        otp_code = request.form.get('otp', '').strip()

        if user.mfa_secret:
            totp = pyotp.TOTP(user.mfa_secret)
            if totp.verify(otp_code):
                user.last_login_at = datetime.utcnow()
                user.login_attempts = 0
                db.session.commit()

                access_token = create_access_token(identity=str(user.id))
                refresh_token = create_refresh_token(identity=str(user.id))
                resp = redirect(url_for('dashboard.index'))
                set_access_cookies(resp, access_token)
                set_refresh_cookies(resp, refresh_token)
                return resp

        flash('رمز التحقق غير صحيح', 'danger')

    return render_template('auth/verify_mfa.html', user_id=user_id)


@auth_bp.route('/logout')
def logout():
    """Logout and clear cookies."""
    resp = redirect(url_for('auth.login'))
    unset_jwt_cookies(resp)
    flash('تم تسجيل الخروج بنجاح', 'success')
    return resp


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    """Request password reset."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            otp = generate_otp()
            user.otp_code = otp
            user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
            user.otp_attempts = 0
            db.session.commit()
            sent = send_otp_email(email, otp, user.full_name)
            if not sent:
                flash(f'تم إرسال رمز التحقق (للتطوير: {otp})', 'info')
            else:
                flash('تم إرسال رمز التحقق إلى بريدك الإلكتروني', 'info')
            return redirect(url_for('auth.reset_password', user_id=user.id))

        flash('تم إرسال رمز التحقق إذا كان البريد مسجلاً', 'info')

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    """Reset password with OTP."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        otp_code = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if otp_code != user.otp_code:
            flash('رمز التحقق غير صحيح', 'danger')
            return render_template('auth/reset_password.html', user_id=user_id)

        if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
            flash('انتهت صلاحية رمز التحقق', 'danger')
            return render_template('auth/reset_password.html', user_id=user_id)

        if new_password != confirm_password:
            flash('كلمتا المرور غير متطابقتين', 'danger')
            return render_template('auth/reset_password.html', user_id=user_id)

        valid_pw, pw_msg = validate_password(new_password)
        if not valid_pw:
            flash(pw_msg, 'danger')
            return render_template('auth/reset_password.html', user_id=user_id)

        user.set_password(new_password)
        user.otp_code = None
        user.otp_expires_at = None
        db.session.commit()

        flash('تم تغيير كلمة المرور بنجاح', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', user_id=user_id)


@auth_bp.route('/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    """Accept team invitation."""
    invitation = Invitation.query.filter_by(token=token).first_or_404()

    if invitation.is_expired:
        flash('رابط الدعوة منتهي الصلاحية', 'danger')
        return redirect(url_for('auth.login'))

    if invitation.is_accepted:
        flash('تم قبول الدعوة بالفعل', 'info')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')

        valid_pw, pw_msg = validate_password(password)
        if not valid_pw:
            flash(pw_msg, 'danger')
            return render_template('auth/accept_invite.html', invitation=invitation)

        user = User(
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            full_name=full_name,
            role_id=invitation.role_id,
            is_active=True,
        )
        user.set_password(password)

        invitation.accepted_at = datetime.utcnow()

        db.session.add(user)
        db.session.commit()

        flash('تم إنشاء حسابك بنجاح! سجل دخولك الآن', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/accept_invite.html', invitation=invitation)
