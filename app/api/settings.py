"""API routes for settings management: office, team, profile."""
import os
from datetime import datetime, timedelta
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request, current_app
from werkzeug.utils import secure_filename

from app.models.tenant import Tenant
from app.models.user import User, Role, Invitation
from app.utils.helpers import generate_token
from app.services.email_service import send_invitation_email


# ── Office Settings ──────────────────────────────────────────────────

@api_bp.route('/settings/office', methods=['GET'])
@api_permission_required('settings', 'view')
def api_settings_office_get():
    """Return current tenant/office settings."""
    tenant = Tenant.query.get(g.tenant_id)
    return success_response(data=tenant.to_dict())


@api_bp.route('/settings/office', methods=['PUT'])
@api_permission_required('settings', 'edit')
def api_settings_office_update():
    """Update office settings (JSON or multipart for logo)."""
    tenant = Tenant.query.get(g.tenant_id)
    data = get_json_or_form()

    if 'office_name' in data or 'name' in data:
        tenant.name = (data.get('office_name') or data.get('name') or tenant.name).strip()
    if 'address' in data:
        tenant.address = (data['address'] or '').strip() or None
    if 'bar_registration_no' in data:
        tenant.bar_registration_no = (data['bar_registration_no'] or '').strip() or None
    if 'primary_court' in data:
        tenant.primary_court = (data['primary_court'] or '').strip() or None
    if 'phone' in data:
        tenant.phone = (data['phone'] or '').strip() or None
    if 'fax' in data:
        tenant.fax = (data['fax'] or '').strip() or None
    if 'email' in data:
        tenant.email = (data['email'] or '').strip() or None

    # Handle logo upload (multipart)
    logo = request.files.get('logo')
    if logo and logo.filename:
        filename = secure_filename(logo.filename)
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
        os.makedirs(upload_dir, exist_ok=True)
        logo_filename = f'tenant_{g.tenant_id}_{filename}'
        logo.save(os.path.join(upload_dir, logo_filename))
        tenant.logo_path = f'uploads/logos/{logo_filename}'

    db.session.commit()
    return success_response(data=tenant.to_dict(), message='تم تحديث إعدادات المكتب بنجاح')


# ── Team Management ──────────────────────────────────────────────────

@api_bp.route('/settings/team', methods=['GET'])
@api_permission_required('settings', 'manage_users')
def api_settings_team_list():
    """Return list of team members and available roles."""
    members = User.query.filter_by(tenant_id=g.tenant_id).order_by(User.created_at).all()
    roles = Role.query.all()

    return success_response(data={
        'members': [m.to_dict() for m in members],
        'roles': [r.to_dict() for r in roles],
    })


@api_bp.route('/settings/team/invite', methods=['POST'])
@api_login_required
def api_settings_team_invite():
    """Invite a new team member via email."""
    data = get_json_or_form()
    errors = {}

    email = (data.get('email') or '').strip().lower()
    if not email:
        errors['email'] = 'البريد الإلكتروني مطلوب'

    role_id = data.get('role_id')
    try:
        role_id = int(role_id) if role_id else None
    except (TypeError, ValueError):
        role_id = None
    if not role_id:
        errors['role_id'] = 'الدور مطلوب'

    if errors:
        return validation_error(errors)

    # Check duplicates
    if User.query.filter_by(email=email, tenant_id=g.tenant_id).first():
        return error_response('هذا البريد مسجل بالفعل', error_code='duplicate', status_code=409)

    if Invitation.query.filter_by(email=email, tenant_id=g.tenant_id, accepted_at=None).first():
        return error_response('تم إرسال دعوة لهذا البريد بالفعل', error_code='duplicate', status_code=409)

    token = generate_token()
    invitation = Invitation(
        tenant_id=g.tenant_id,
        email=email,
        role_id=role_id,
        token=token,
        invited_by=g.current_user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.session.add(invitation)
    db.session.commit()

    tenant = Tenant.query.get(g.tenant_id)
    role = Role.query.get(role_id)
    send_invitation_email(email, token, tenant.name, role.name_ar if role else '')

    return success_response(message=f'تم إرسال دعوة إلى {email}', status_code=201)


@api_bp.route('/settings/team/<int:user_id>/toggle', methods=['POST'])
@api_login_required
def api_settings_team_toggle(user_id):
    """Activate/deactivate a team member."""
    member = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first()
    if not member:
        return error_response('العضو غير موجود', error_code='not_found', status_code=404)

    if member.id == g.current_user.id:
        return error_response('لا يمكنك تعطيل حسابك', error_code='forbidden', status_code=403)

    member.is_active = not member.is_active
    db.session.commit()

    status = 'تفعيل' if member.is_active else 'تعطيل'
    return success_response(data=member.to_dict(), message=f'تم {status} حساب {member.full_name}')


@api_bp.route('/settings/team/<int:user_id>/role', methods=['POST'])
@api_login_required
def api_settings_team_change_role(user_id):
    """Change a team member's role."""
    member = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first()
    if not member:
        return error_response('العضو غير موجود', error_code='not_found', status_code=404)

    data = get_json_or_form()
    role_id = data.get('role_id')
    try:
        role_id = int(role_id) if role_id else None
    except (TypeError, ValueError):
        role_id = None

    if not role_id:
        return validation_error({'role_id': 'الدور مطلوب'})

    member.role_id = role_id
    db.session.commit()
    return success_response(data=member.to_dict(), message=f'تم تحديث دور {member.full_name}')


# ── Profile ──────────────────────────────────────────────────────────

@api_bp.route('/settings/profile', methods=['GET'])
@api_login_required
def api_settings_profile_get():
    """Return current user profile."""
    return success_response(data=g.current_user.to_dict())


@api_bp.route('/settings/profile', methods=['PUT'])
@api_login_required
def api_settings_profile_update():
    """Update current user profile (name, phone, password)."""
    user = g.current_user
    data = get_json_or_form()

    if 'full_name' in data:
        user.full_name = (data['full_name'] or user.full_name).strip()
    if 'full_name_en' in data:
        user.full_name_en = (data['full_name_en'] or '').strip() or None
    if 'phone' in data:
        user.phone = (data['phone'] or '').strip() or None

    # Password change
    current_password = (data.get('current_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    if current_password and new_password:
        if not user.check_password(current_password):
            return error_response('كلمة المرور الحالية غير صحيحة', error_code='invalid_password', status_code=400)
        if len(new_password) < 8:
            return validation_error({'new_password': 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل'})
        user.set_password(new_password)
        user.password_changed_at = datetime.utcnow()

    db.session.commit()
    return success_response(data=user.to_dict(), message='تم تحديث الملف الشخصي')


@api_bp.route('/settings/profile/avatar', methods=['POST'])
@api_login_required
def api_settings_profile_avatar():
    """Upload user avatar."""
    avatar = request.files.get('avatar')
    if not avatar or not avatar.filename:
        return error_response('يرجى اختيار صورة', error_code='missing_file', status_code=400)

    user = g.current_user
    filename = secure_filename(avatar.filename)
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)
    avatar_filename = f'user_{user.id}_{filename}'
    avatar.save(os.path.join(upload_dir, avatar_filename))
    user.avatar_path = f'uploads/avatars/{avatar_filename}'

    db.session.commit()
    return success_response(data=user.to_dict(), message='تم تحديث الصورة الشخصية')
