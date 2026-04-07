"""Notification management routes."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from app.extensions import db
from app.utils.decorators import login_required, permission_required
from app.models.notification import Notification, NotificationSetting

notifications_bp = Blueprint('notifications', __name__, template_folder='../../templates/notifications')

NOTIFICATION_TYPES = [
    ('session_reminder', 'تذكير بجلسة'),
    ('task_assigned', 'مهمة جديدة'),
    ('deadline_alert', 'تنبيه موعد نهائي'),
    ('payment_received', 'دفعة جديدة'),
    ('appeal_deadline', 'موعد استئناف'),
    ('case_update', 'تحديث قضية'),
]

PRIORITY_COLORS = {
    'urgent': 'danger', 'warning': 'warning', 'info': 'info', 'success': 'success',
}


@notifications_bp.route('/')
@login_required
def index():
    """List all notifications for the current user."""
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('type', '')

    query = Notification.query.filter_by(tenant_id=g.tenant_id, user_id=g.current_user.id)
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)

    notifications = query.order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)

    unread_count = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id, is_read=False
    ).count()

    return render_template('notifications/index.html', notifications=notifications,
                           filter_type=filter_type, unread_count=unread_count,
                           priority_colors=PRIORITY_COLORS)


@notifications_bp.route('/<int:id>/mark-read', methods=['POST'])
@login_required
def mark_read(id):
    """Mark a notification as read."""
    notification = Notification.query.filter_by(
        id=id, tenant_id=g.tenant_id, user_id=g.current_user.id
    ).first_or_404()

    notification.mark_read()
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'ok'})
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    flash('تم تحديد جميع الإشعارات كمقروءة', 'success')
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Manage notification preferences."""
    if request.method == 'POST':
        for ntype, _ in NOTIFICATION_TYPES:
            setting = NotificationSetting.query.filter_by(
                user_id=g.current_user.id, notification_type=ntype
            ).first()

            if not setting:
                setting = NotificationSetting(user_id=g.current_user.id, notification_type=ntype)
                db.session.add(setting)

            setting.email_enabled = request.form.get(f'{ntype}_email') == 'on'
            setting.sms_enabled = request.form.get(f'{ntype}_sms') == 'on'
            setting.in_app_enabled = request.form.get(f'{ntype}_in_app') == 'on'

        db.session.commit()
        flash('تم حفظ إعدادات الإشعارات', 'success')
        return redirect(url_for('notifications.settings'))

    current_settings = {s.notification_type: s for s in
                        NotificationSetting.query.filter_by(user_id=g.current_user.id).all()}

    return render_template('notifications/settings.html', notification_types=NOTIFICATION_TYPES,
                           current_settings=current_settings)
