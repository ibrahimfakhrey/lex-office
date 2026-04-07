"""Settings management routes: Office, team, user profile."""
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.tenant import Tenant
from app.models.user import User, Role, Invitation
from app.utils.helpers import generate_token
from app.services.email_service import send_invitation_email

settings_bp = Blueprint('settings', __name__, template_folder='../../templates/settings')


@settings_bp.route('/')
@permission_required('settings', 'view')
def index():
    """Office settings page."""
    tenant = Tenant.query.get(g.tenant_id)
    return render_template('settings/index.html', tenant=tenant)


@settings_bp.route('/update-office', methods=['POST'])
@permission_required('settings', 'edit')
def update_office():
    """Update office settings."""
    tenant = Tenant.query.get(g.tenant_id)

    tenant.name = request.form.get('office_name', tenant.name).strip()
    tenant.address = request.form.get('address', '').strip() or None
    tenant.bar_registration_no = request.form.get('bar_registration_no', '').strip() or None
    tenant.primary_court = request.form.get('primary_court', '').strip() or None
    tenant.phone = request.form.get('phone', '').strip() or None
    tenant.fax = request.form.get('fax', '').strip() or None
    tenant.email = request.form.get('email', '').strip() or None

    logo = request.files.get('logo')
    if logo and logo.filename:
        filename = secure_filename(logo.filename)
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'logos')
        os.makedirs(upload_dir, exist_ok=True)
        logo_path = os.path.join(upload_dir, f'tenant_{g.tenant_id}_{filename}')
        logo.save(logo_path)
        tenant.logo_path = logo_path

    db.session.commit()
    flash('تم تحديث إعدادات المكتب بنجاح', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/team')
@permission_required('settings', 'manage_users')
def team():
    """Team members management."""
    members = User.query.filter_by(tenant_id=g.tenant_id).order_by(User.created_at).all()
    roles = Role.query.all()
    return render_template('settings/team.html', members=members, roles=roles)


@settings_bp.route('/team/invite', methods=['POST'])
@login_required
def invite_member():
    """Invite a new team member via email."""
    email = request.form.get('email', '').strip().lower()
    role_id = request.form.get('role_id', type=int)

    if not email or not role_id:
        flash('البريد الإلكتروني والدور مطلوبان', 'danger')
        return redirect(url_for('settings.team'))

    # Check if already exists
    if User.query.filter_by(email=email, tenant_id=g.tenant_id).first():
        flash('هذا البريد مسجل بالفعل', 'warning')
        return redirect(url_for('settings.team'))

    if Invitation.query.filter_by(email=email, tenant_id=g.tenant_id, accepted_at=None).first():
        flash('تم إرسال دعوة لهذا البريد بالفعل', 'warning')
        return redirect(url_for('settings.team'))

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

    flash(f'تم إرسال دعوة إلى {email}', 'success')
    return redirect(url_for('settings.team'))


@settings_bp.route('/team/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_member(user_id):
    """Activate/deactivate a team member."""
    member = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first_or_404()
    if member.id == g.current_user.id:
        flash('لا يمكنك تعطيل حسابك', 'danger')
        return redirect(url_for('settings.team'))

    member.is_active = not member.is_active
    db.session.commit()
    status = 'تفعيل' if member.is_active else 'تعطيل'
    flash(f'تم {status} حساب {member.full_name}', 'success')
    return redirect(url_for('settings.team'))


@settings_bp.route('/team/<int:user_id>/role', methods=['POST'])
@login_required
def change_role(user_id):
    """Change a team member's role."""
    member = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first_or_404()
    role_id = request.form.get('role_id', type=int)
    if role_id:
        member.role_id = role_id
        db.session.commit()
        flash(f'تم تحديث دور {member.full_name}', 'success')
    return redirect(url_for('settings.team'))


@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile settings."""
    user = g.current_user

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name).strip()
        user.full_name_en = request.form.get('full_name_en', '').strip() or None
        user.phone = request.form.get('phone', '').strip() or None

        # Change password
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        if current_password and new_password:
            if user.check_password(current_password):
                if len(new_password) >= 8:
                    user.set_password(new_password)
                    user.password_changed_at = datetime.utcnow()
                    flash('تم تغيير كلمة المرور بنجاح', 'success')
                else:
                    flash('كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل', 'danger')
            else:
                flash('كلمة المرور الحالية غير صحيحة', 'danger')
                return render_template('settings/profile.html', user=user)

        # Avatar
        avatar = request.files.get('avatar')
        if avatar and avatar.filename:
            filename = secure_filename(avatar.filename)
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
            os.makedirs(upload_dir, exist_ok=True)
            avatar_path = os.path.join(upload_dir, f'user_{user.id}_{filename}')
            avatar.save(avatar_path)
            user.avatar_path = avatar_path

        db.session.commit()
        flash('تم تحديث الملف الشخصي', 'success')
        return redirect(url_for('settings.profile'))

    return render_template('settings/profile.html', user=user)
