"""System settings — general, SMTP, etc."""
import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, g, current_app
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action, admin_permission_required
from app.models.admin import SystemSetting
from app.services.email_service import send_email
from app.utils.helpers import save_uploaded_file


# Default keys we expose in the UI. `help_center_url` removed per
# requirements doc — replaced by the existing contact page.
GENERAL_KEYS = [
    ('product_name',     'اسم المنتج',                'LexOffice'),
    ('product_logo_url', 'رابط شعار المنتج',          ''),
    ('support_email',    'بريد الدعم الفني',          'support@manasety.ai'),
    ('default_currency', 'العملة الافتراضية',         'EGP'),
    ('terms_url',        'رابط شروط الخدمة',          ''),
    ('privacy_url',      'رابط سياسة الخصوصية',       ''),
]

SMTP_KEYS = [
    ('smtp_host',     'SMTP Host',         'smtp.gmail.com'),
    ('smtp_port',     'SMTP Port',         '587'),
    ('smtp_username', 'SMTP Username',     ''),
    ('smtp_password', 'SMTP Password',     ''),
    ('smtp_from',     'From Email',        ''),
    ('smtp_use_tls',  'Use TLS',           'true'),
]


def _get(key, default=''):
    return SystemSetting.get(key, default)


# ──────────────────────────── general ────────────────────────────

@admin_bp.route('/settings/general', methods=['GET', 'POST'])
@admin_permission_required('settings', 'view', write_action='edit')
def settings_general():
    """General system settings — product name, support email, links, etc."""
    if request.method == 'POST':
        old_values = {}
        new_values = {}
        for key, label, default in GENERAL_KEYS:
            old_values[key] = _get(key, default)
            val = (request.form.get(key) or '').strip()
            SystemSetting.set(key, val, admin_id=g.current_admin.id)
            new_values[key] = val

        # Optional logo upload: if a file is provided, save it and overwrite
        # `product_logo_url` with the served path (wins over the URL field).
        logo_file = request.files.get('product_logo_file')
        if logo_file and logo_file.filename:
            saved_path = save_uploaded_file(logo_file, subfolder='branding')
            served_url = url_for('static', filename=f'uploads/{saved_path}')
            SystemSetting.set('product_logo_url', served_url, admin_id=g.current_admin.id)
            new_values['product_logo_url'] = served_url

        log_action(
            'SETTINGS_GENERAL_UPDATED', entity_type='Setting',
            old_value=old_values, new_value=new_values,
            description='Updated general settings',
        )
        db.session.commit()
        flash('تم حفظ الإعدادات', 'success')
        return redirect(url_for('admin.settings_general'))

    values = {key: _get(key, default) for key, _, default in GENERAL_KEYS}
    return render_template(
        'admin/settings/general.html',
        keys=GENERAL_KEYS, values=values,
    )


# ──────────────────────────── SMTP ────────────────────────────

@admin_bp.route('/settings/smtp', methods=['GET', 'POST'])
@admin_permission_required('settings', 'view', write_action='edit')
def settings_smtp():
    """SMTP email configuration."""
    if request.method == 'POST':
        old_values = {}
        for key, _, default in SMTP_KEYS:
            old_values[key] = _get(key, default)
            val = (request.form.get(key) or '').strip()
            # Don't overwrite password if blank (keep existing)
            if key == 'smtp_password' and not val:
                continue
            SystemSetting.set(key, val, admin_id=g.current_admin.id)

        log_action(
            'SETTINGS_SMTP_UPDATED', entity_type='Setting',
            description='Updated SMTP configuration',
        )
        db.session.commit()
        flash('تم حفظ إعدادات SMTP', 'success')
        return redirect(url_for('admin.settings_smtp'))

    values = {key: (_get(key, default) if key != 'smtp_password' else '') for key, _, default in SMTP_KEYS}
    return render_template(
        'admin/settings/smtp.html',
        keys=SMTP_KEYS, values=values,
    )


@admin_bp.route('/settings/smtp/test', methods=['POST'])
@admin_permission_required('settings', 'edit')
def settings_smtp_test():
    """Send a test email to verify SMTP works."""
    test_email = (request.form.get('test_email') or g.current_admin.email).strip()
    subject = 'المُحامي — Test Email'
    html = f"""
    <div dir='rtl' style='font-family:Tajawal,Arial;padding:20px'>
        <h2 style='color:#1849A9'>✓ تم إرسال البريد بنجاح</h2>
        <p>هذه رسالة اختبار من Super Admin Panel للتأكد من إعدادات SMTP.</p>
        <p style='color:#666;font-size:12px'>أُرسلت في {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>
    """
    sent = send_email(test_email, subject, html)
    log_action(
        'SMTP_TEST_SENT', entity_type='Setting',
        description=f'SMTP test email to {test_email}: {"OK" if sent else "FAILED"}',
    )
    db.session.commit()
    flash(f'{"تم إرسال" if sent else "فشل إرسال"} رسالة الاختبار إلى {test_email}',
          'success' if sent else 'danger')
    return redirect(url_for('admin.settings_smtp'))


# ──────────────────────────── admins management ────────────────────────────

@admin_bp.route('/settings/admins')
@admin_permission_required('admin_users', 'view')
def settings_admins():
    """List + manage admin users (CRUD + role assignment)."""
    from app.models.admin import AdminUser
    from app.models.admin_rbac import AdminRole
    admins = AdminUser.query.order_by(AdminUser.created_at).all()
    roles = AdminRole.query.order_by(AdminRole.is_system.desc(), AdminRole.created_at).all()
    return render_template('admin/settings/admins.html', admins=admins, roles=roles)


@admin_bp.route('/settings/admins/new', methods=['POST'])
@admin_permission_required('admin_users', 'add')
def settings_admins_create():
    from app.models.admin import AdminUser
    from app.models.admin_rbac import AdminRole
    from app.utils.validators import validate_email, validate_password

    email = (request.form.get('email') or '').strip().lower()
    full_name = (request.form.get('full_name') or '').strip()
    password = request.form.get('password') or ''
    role_id = request.form.get('role_id', type=int)

    if not validate_email(email):
        flash('بريد غير صالح', 'danger')
        return redirect(url_for('admin.settings_admins'))
    if not full_name:
        flash('الاسم الكامل مطلوب', 'danger')
        return redirect(url_for('admin.settings_admins'))
    valid, msg = validate_password(password)
    if not valid:
        flash(msg, 'danger')
        return redirect(url_for('admin.settings_admins'))
    if AdminUser.query.filter_by(email=email).first():
        flash(f'يوجد أدمن بالبريد {email} بالفعل', 'danger')
        return redirect(url_for('admin.settings_admins'))

    role = AdminRole.query.get_or_404(role_id) if role_id else None
    if not role:
        flash('يجب اختيار دور للأدمن الجديد', 'danger')
        return redirect(url_for('admin.settings_admins'))

    admin = AdminUser(
        email=email,
        full_name=full_name,
        role=role.name,            # legacy string column kept in sync
        role_id=role.id,
        is_active=True,
        mfa_enabled=False,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.flush()
    log_action(
        'ADMIN_USER_CREATED', entity_type='AdminUser', entity_id=admin.id,
        new_value={'email': email, 'role': role.name_ar},
        description=f'إنشاء أدمن: {email}',
    )
    db.session.commit()
    flash(f'تم إنشاء الأدمن "{full_name}" بدور "{role.name_ar}"', 'success')
    return redirect(url_for('admin.settings_admins'))


@admin_bp.route('/settings/admins/<int:admin_id>/edit', methods=['POST'])
@admin_permission_required('admin_users', 'edit')
def settings_admins_edit(admin_id):
    from app.models.admin import AdminUser
    from app.models.admin_rbac import AdminRole

    admin = AdminUser.query.get_or_404(admin_id)
    full_name = (request.form.get('full_name') or '').strip()
    role_id = request.form.get('role_id', type=int)
    is_active = request.form.get('is_active') == 'on'
    new_password = request.form.get('password') or ''

    if not full_name:
        flash('الاسم مطلوب', 'danger')
        return redirect(url_for('admin.settings_admins'))

    role = AdminRole.query.get_or_404(role_id) if role_id else None
    if not role:
        flash('يجب اختيار دور', 'danger')
        return redirect(url_for('admin.settings_admins'))

    # Safety: don't deactivate or demote the last active super admin
    if admin.role_id and admin.admin_role and admin.admin_role.is_system:
        if (not is_active or role.id != admin.role_id):
            other_active_supers = AdminUser.query.filter(
                AdminUser.id != admin.id,
                AdminUser.role_id == admin.role_id,
                AdminUser.is_active.is_(True),
            ).count()
            if other_active_supers == 0:
                flash('لا يمكن تعطيل أو نقل آخر Super Admin نشط', 'danger')
                return redirect(url_for('admin.settings_admins'))

    old = {'full_name': admin.full_name, 'role': admin.admin_role.name_ar if admin.admin_role else None,
           'is_active': admin.is_active}
    admin.full_name = full_name
    admin.role = role.name
    admin.role_id = role.id
    admin.is_active = is_active
    if new_password:
        from app.utils.validators import validate_password
        valid, msg = validate_password(new_password)
        if not valid:
            flash(msg, 'danger')
            return redirect(url_for('admin.settings_admins'))
        admin.set_password(new_password)

    log_action(
        'ADMIN_USER_UPDATED', entity_type='AdminUser', entity_id=admin.id,
        old_value=old,
        new_value={'full_name': full_name, 'role': role.name_ar, 'is_active': is_active},
        description=f'تعديل أدمن: {admin.email}',
    )
    db.session.commit()
    flash(f'تم حفظ تعديلات "{admin.full_name}"', 'success')
    return redirect(url_for('admin.settings_admins'))


@admin_bp.route('/settings/admins/<int:admin_id>/delete', methods=['POST'])
@admin_permission_required('admin_users', 'delete')
def settings_admins_delete(admin_id):
    from app.models.admin import AdminUser

    admin = AdminUser.query.get_or_404(admin_id)
    if admin.id == g.current_admin.id:
        flash('لا يمكن حذف حسابك أنت', 'danger')
        return redirect(url_for('admin.settings_admins'))

    # Safety: can't delete last active super admin
    if admin.admin_role and admin.admin_role.is_system:
        other_active_supers = AdminUser.query.filter(
            AdminUser.id != admin.id,
            AdminUser.role_id == admin.role_id,
            AdminUser.is_active.is_(True),
        ).count()
        if other_active_supers == 0:
            flash('لا يمكن حذف آخر Super Admin نشط', 'danger')
            return redirect(url_for('admin.settings_admins'))

    email = admin.email
    log_action(
        'ADMIN_USER_DELETED', entity_type='AdminUser', entity_id=admin.id,
        old_value={'email': email, 'full_name': admin.full_name},
        description=f'حذف أدمن: {email}',
    )
    db.session.delete(admin)
    db.session.commit()
    flash(f'تم حذف الأدمن "{email}"', 'warning')
    return redirect(url_for('admin.settings_admins'))
