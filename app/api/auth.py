"""API Authentication routes: Register, Login, OTP, Password Reset, MFA."""
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import success_response, error_response, validation_error, paginated_response, get_json_or_form, parse_date
from app.extensions import db, limiter
from flask import g, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from app.models.user import User, Role, Invitation
from app.models.tenant import Tenant
from app.utils.helpers import generate_otp, generate_token
from app.utils.validators import validate_email, validate_password, validate_phone
from app.services.email_service import send_otp_email


# ---------- POST /auth/register ----------
@api_bp.route('/auth/register', methods=['POST'])
@limiter.limit("10 per hour")
def api_register():
    """Register a new subscription (tenant + manager user)."""
    data = get_json_or_form()
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    password = data.get('password', '')
    office_size = data.get('office_size', '1-5')

    # Validations
    errors = {}
    if not full_name:
        errors['full_name'] = 'الاسم الكامل مطلوب'
    if not validate_email(email):
        errors['email'] = 'البريد الإلكتروني غير صالح'
    if not validate_phone(phone):
        errors['phone'] = 'رقم الهاتف غير صالح'

    valid_pw, pw_msg = validate_password(password)
    if not valid_pw:
        errors['password'] = pw_msg

    # Check email uniqueness
    existing = User.query.filter_by(email=email).first()
    if existing:
        errors['email'] = 'البريد الإلكتروني مسجل بالفعل'

    if errors:
        return validation_error(errors)

    # Create tenant
    tenant = Tenant(
        name=f'مكتب {full_name}',
        subscription_status='trial',
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
    )
    db.session.add(tenant)
    db.session.flush()

    # Get manager role
    manager_role = Role.query.filter_by(name='manager').first()
    if not manager_role:
        db.session.rollback()
        return error_response('خطأ في النظام: الأدوار غير موجودة', error_code='system_error', status_code=500)

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        phone=phone,
        role_id=manager_role.id,
        is_active=False,
    )
    user.set_password(password)

    # Generate OTP
    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    user.otp_attempts = 0

    db.session.add(user)
    db.session.commit()

    # Send OTP email
    send_otp_email(email, otp, full_name)

    return success_response(
        data={'user_id': user.id},
        message='تم إنشاء الحساب. تحقق من بريدك الإلكتروني لرمز التحقق',
        status_code=201,
    )


# ---------- POST /auth/verify-otp ----------
@api_bp.route('/auth/verify-otp', methods=['POST'])
@limiter.limit("20 per hour")
def api_verify_otp():
    """Verify OTP code and activate user account."""
    data = get_json_or_form()
    user_id = data.get('user_id')
    otp_code = (data.get('otp') or '').strip()

    if not user_id or not otp_code:
        return error_response('معرّف المستخدم ورمز التحقق مطلوبان', error_code='missing_fields')

    user = User.query.get(user_id)
    if not user:
        return error_response('المستخدم غير موجود', error_code='not_found', status_code=404)

    # Check max attempts
    if user.otp_attempts and user.otp_attempts >= 3:
        return error_response('تم تجاوز عدد المحاولات المسموح به', error_code='max_attempts')

    # Check expiry
    if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
        return error_response('انتهت صلاحية رمز التحقق', error_code='otp_expired')

    # Check code match
    if otp_code != user.otp_code:
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.session.commit()
        return error_response('رمز التحقق غير صحيح', error_code='invalid_otp')

    # Success: activate and clear OTP
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    user.is_active = True
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return success_response(data={
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    })


# ---------- POST /auth/resend-otp ----------
@api_bp.route('/auth/resend-otp', methods=['POST'])
@limiter.limit("3 per hour")
def api_resend_otp():
    """Resend a new OTP to the user's email."""
    data = get_json_or_form()
    user_id = data.get('user_id')

    if not user_id:
        return error_response('معرّف المستخدم مطلوب', error_code='missing_fields')

    user = User.query.get(user_id)
    if not user:
        return error_response('المستخدم غير موجود', error_code='not_found', status_code=404)

    # Anti-spam: check if last OTP was sent less than 60 seconds ago
    if user.otp_expires_at:
        remaining = (user.otp_expires_at - datetime.utcnow()).total_seconds()
        if remaining > 540:  # 10 min - 60s = 9 min = 540s
            return error_response('يرجى الانتظار قبل إعادة الإرسال', error_code='too_soon')

    # Generate new OTP
    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    user.otp_attempts = 0
    db.session.commit()

    send_otp_email(user.email, otp, user.full_name)

    return success_response(message='تم إرسال رمز تحقق جديد إلى بريدك الإلكتروني')


# ---------- POST /auth/login ----------
@api_bp.route('/auth/login', methods=['POST'])
@limiter.limit("30 per hour")
def api_login():
    """Authenticate user and return JWT tokens."""
    data = get_json_or_form()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    remember = data.get('remember', False)
    device_name = data.get('device_name')

    if not email or not password:
        return error_response('البريد الإلكتروني وكلمة المرور مطلوبان', error_code='missing_fields')

    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('البريد الإلكتروني أو كلمة المرور غير صحيحة', error_code='invalid_credentials', status_code=401)

    # Check lockout
    if user.locked_until and datetime.utcnow() < user.locked_until:
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        return error_response(
            f'الحساب مقفل. حاول مرة أخرى بعد {remaining} دقيقة',
            error_code='account_locked',
            status_code=403,
        )

    # Check password
    if not user.check_password(password):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            user.login_attempts = 0
            db.session.commit()
            return error_response(
                'تم قفل الحساب لمدة 15 دقيقة بسبب محاولات تسجيل دخول كثيرة',
                error_code='account_locked',
                status_code=403,
            )
        db.session.commit()
        return error_response('البريد الإلكتروني أو كلمة المرور غير صحيحة', error_code='invalid_credentials', status_code=401)

    # Check active
    if not user.is_active:
        return error_response('الحساب غير نشط. تواصل مع مدير المكتب', error_code='account_inactive', status_code=403)

    # Check tenant active
    if not user.tenant or not user.tenant.is_active:
        return error_response('حساب المكتب غير نشط', error_code='tenant_inactive', status_code=403)

    # MFA check
    if user.mfa_enabled:
        return success_response(data={
            'requires_mfa': True,
            'user_id': user.id,
        })

    # Successful login
    user.login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    token_expires = timedelta(days=30) if remember else timedelta(days=7)
    access_token = create_access_token(identity=str(user.id), expires_delta=token_expires)
    refresh_token = create_refresh_token(identity=str(user.id))

    return success_response(data={
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    })


# ---------- POST /auth/verify-mfa ----------
@api_bp.route('/auth/verify-mfa', methods=['POST'])
def api_verify_mfa():
    """Verify MFA (TOTP) code and return JWT tokens."""
    import pyotp

    data = get_json_or_form()
    user_id = data.get('user_id')
    otp_code = (data.get('otp') or '').strip()

    if not user_id or not otp_code:
        return error_response('معرّف المستخدم ورمز التحقق مطلوبان', error_code='missing_fields')

    user = User.query.get(user_id)
    if not user:
        return error_response('المستخدم غير موجود', error_code='not_found', status_code=404)

    if not user.mfa_secret:
        return error_response('المصادقة الثنائية غير مفعّلة لهذا المستخدم', error_code='mfa_not_enabled')

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(otp_code):
        return error_response('رمز التحقق غير صحيح', error_code='invalid_otp', status_code=401)

    user.last_login_at = datetime.utcnow()
    user.login_attempts = 0
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return success_response(data={
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    })


# ---------- POST /auth/refresh ----------
@api_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def api_refresh():
    """Refresh the access token using a valid refresh token."""
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return success_response(data={'access_token': access_token})


# ---------- POST /auth/logout ----------
@api_bp.route('/auth/logout', methods=['POST'])
@api_login_required
def api_logout():
    """Logout (client should discard tokens)."""
    return success_response(message='تم تسجيل الخروج بنجاح')


# ---------- POST /auth/forgot-password ----------
@api_bp.route('/auth/forgot-password', methods=['POST'])
@limiter.limit("5 per hour")
def api_forgot_password():
    """Request password reset OTP."""
    data = get_json_or_form()
    email = (data.get('email') or '').strip().lower()

    if not email:
        return error_response('البريد الإلكتروني مطلوب', error_code='missing_fields')

    # Always return success to avoid revealing whether an email exists
    response_data = {}
    user = User.query.filter_by(email=email).first()
    if user:
        otp = generate_otp()
        user.otp_code = otp
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        user.otp_attempts = 0
        db.session.commit()
        send_otp_email(email, otp, user.full_name)
        response_data['user_id'] = user.id

    return success_response(
        data=response_data if response_data else None,
        message='تم إرسال رمز التحقق إذا كان البريد مسجلاً',
    )


# ---------- POST /auth/reset-password ----------
@api_bp.route('/auth/reset-password', methods=['POST'])
def api_reset_password():
    """Reset password using OTP code."""
    data = get_json_or_form()
    user_id = data.get('user_id')
    otp_code = (data.get('otp') or '').strip()
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not user_id or not otp_code:
        return error_response('معرّف المستخدم ورمز التحقق مطلوبان', error_code='missing_fields')

    user = User.query.get(user_id)
    if not user:
        return error_response('المستخدم غير موجود', error_code='not_found', status_code=404)

    # Verify OTP
    if otp_code != user.otp_code:
        return error_response('رمز التحقق غير صحيح', error_code='invalid_otp')

    if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
        return error_response('انتهت صلاحية رمز التحقق', error_code='otp_expired')

    # Password match
    if new_password != confirm_password:
        return validation_error({'confirm_password': 'كلمتا المرور غير متطابقتين'})

    # Password policy
    valid_pw, pw_msg = validate_password(new_password)
    if not valid_pw:
        return validation_error({'new_password': pw_msg})

    # Set new password and clear OTP
    user.set_password(new_password)
    user.otp_code = None
    user.otp_expires_at = None
    db.session.commit()

    return success_response(message='تم تغيير كلمة المرور بنجاح')


# ---------- POST /auth/accept-invite ----------
@api_bp.route('/auth/accept-invite', methods=['POST'])
def api_accept_invite():
    """Accept a team invitation and create a user account."""
    data = get_json_or_form()
    token = (data.get('token') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    password = data.get('password', '')

    if not token or not full_name or not password:
        return error_response('جميع الحقول مطلوبة', error_code='missing_fields')

    invitation = Invitation.query.filter_by(token=token).first()
    if not invitation:
        return error_response('رابط الدعوة غير صالح', error_code='invalid_token', status_code=404)

    if invitation.is_expired:
        return error_response('رابط الدعوة منتهي الصلاحية', error_code='invitation_expired')

    if invitation.is_accepted:
        return error_response('تم قبول الدعوة بالفعل', error_code='invitation_accepted')

    # Validate password
    valid_pw, pw_msg = validate_password(password)
    if not valid_pw:
        return validation_error({'password': pw_msg})

    # Create user
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

    return success_response(message='تم إنشاء حسابك بنجاح', status_code=201)


# ---------- GET /auth/dev-otp (DEV ONLY) ----------
@api_bp.route('/auth/dev-otp/<int:user_id>', methods=['GET'])
def api_dev_otp(user_id):
    """Return OTP for testing — only works in development mode."""
    import os
    if os.getenv('FLASK_ENV', 'development') != 'development':
        return error_response('Not available', status_code=404)
    user = User.query.get(user_id)
    if not user or not user.otp_code:
        return error_response('No OTP found', status_code=404)
    return success_response(data={'otp': user.otp_code, 'user_id': user_id})


# ---------- GET /auth/me ----------
@api_bp.route('/auth/me', methods=['GET'])
@api_login_required
def api_me():
    """Return current authenticated user with tenant info and role."""
    user = g.current_user
    user_data = user.to_dict()
    user_data['tenant'] = user.tenant.to_dict() if user.tenant else None
    user_data['role'] = user.role.to_dict() if user.role else None

    return success_response(data=user_data)
