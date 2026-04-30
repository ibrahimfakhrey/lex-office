"""System settings — general, SMTP, etc."""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action
from app.models.admin import SystemSetting
from app.services.email_service import send_email


# Default keys we expose in the UI
GENERAL_KEYS = [
    ('product_name',     'اسم المنتج',                'LexOffice'),
    ('product_logo_url', 'رابط شعار المنتج',          ''),
    ('support_email',    'بريد الدعم الفني',          'support@manasety.ai'),
    ('default_currency', 'العملة الافتراضية',         'EGP'),
    ('terms_url',        'رابط شروط الخدمة',          ''),
    ('privacy_url',      'رابط سياسة الخصوصية',       ''),
    ('help_center_url',  'رابط مركز المساعدة',        ''),
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
@super_admin_required
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
@super_admin_required
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
@super_admin_required
def settings_smtp_test():
    """Send a test email to verify SMTP works."""
    test_email = (request.form.get('test_email') or g.current_admin.email).strip()
    subject = 'LexOffice — Test Email'
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
@super_admin_required
def settings_admins():
    """List of admin users (P3 — read-only for now)."""
    from app.models.admin import AdminUser
    admins = AdminUser.query.order_by(AdminUser.created_at).all()
    return render_template('admin/settings/admins.html', admins=admins)
