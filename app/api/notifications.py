"""API routes for notification management."""
from datetime import datetime
from app.api import api_bp
from app.api.decorators import api_login_required, api_permission_required
from app.api.helpers import (success_response, error_response, validation_error,
                             paginated_response, get_json_or_form, parse_date)
from app.extensions import db
from flask import g, request

from app.models.notification import Notification, NotificationSetting

NOTIFICATION_TYPES = [
    ('session_reminder', 'تذكير بجلسة'),
    ('task_assigned', 'مهمة جديدة'),
    ('deadline_alert', 'تنبيه موعد نهائي'),
    ('payment_received', 'دفعة جديدة'),
    ('appeal_deadline', 'موعد استئناف'),
    ('case_update', 'تحديث قضية'),
]


@api_bp.route('/notifications', methods=['GET'])
@api_login_required
def api_notifications_list():
    """List notifications for the current user."""
    filter_type = request.args.get('type', '').strip()

    query = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id
    )
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)

    query = query.order_by(Notification.created_at.desc())
    return paginated_response(query)


@api_bp.route('/notifications/unread-count', methods=['GET'])
@api_login_required
def api_notifications_unread_count():
    """Return the count of unread notifications."""
    count = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id, is_read=False
    ).count()
    return success_response(data={'count': count})


@api_bp.route('/notifications/<int:id>/read', methods=['POST'])
@api_login_required
def api_notifications_mark_read(id):
    """Mark a single notification as read."""
    notification = Notification.query.filter_by(
        id=id, tenant_id=g.tenant_id, user_id=g.current_user.id
    ).first()
    if not notification:
        return error_response('الإشعار غير موجود', error_code='not_found', status_code=404)

    notification.mark_read()
    db.session.commit()
    return success_response(message='تم تحديد الإشعار كمقروء')


@api_bp.route('/notifications/read-all', methods=['POST'])
@api_login_required
def api_notifications_mark_all_read():
    """Mark all unread notifications as read."""
    count = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return success_response(data={'count': count}, message='تم تحديد جميع الإشعارات كمقروءة')


@api_bp.route('/notifications/settings', methods=['GET'])
@api_login_required
def api_notifications_settings_get():
    """Return notification settings for the current user."""
    current_settings = {
        s.notification_type: s for s in
        NotificationSetting.query.filter_by(user_id=g.current_user.id).all()
    }

    settings_list = []
    for ntype, label_ar in NOTIFICATION_TYPES:
        setting = current_settings.get(ntype)
        settings_list.append({
            'notification_type': ntype,
            'label_ar': label_ar,
            'email_enabled': setting.email_enabled if setting else True,
            'sms_enabled': setting.sms_enabled if setting else True,
            'in_app_enabled': setting.in_app_enabled if setting else True,
        })

    return success_response(data=settings_list)


@api_bp.route('/notifications/settings', methods=['PUT'])
@api_login_required
def api_notifications_settings_update():
    """Update notification settings for the current user."""
    data = get_json_or_form()

    # Expect a list of settings objects
    settings_data = data if isinstance(data, list) else data.get('settings', [])
    if not settings_data:
        return validation_error({'settings': 'قائمة الإعدادات مطلوبة'})

    valid_types = {nt for nt, _ in NOTIFICATION_TYPES}

    for item in settings_data:
        ntype = item.get('notification_type', '')
        if ntype not in valid_types:
            continue

        setting = NotificationSetting.query.filter_by(
            user_id=g.current_user.id, notification_type=ntype
        ).first()

        if not setting:
            setting = NotificationSetting(
                user_id=g.current_user.id, notification_type=ntype
            )
            db.session.add(setting)

        if 'email_enabled' in item:
            setting.email_enabled = bool(item['email_enabled'])
        if 'sms_enabled' in item:
            setting.sms_enabled = bool(item['sms_enabled'])
        if 'in_app_enabled' in item:
            setting.in_app_enabled = bool(item['in_app_enabled'])

    db.session.commit()
    return success_response(message='تم حفظ إعدادات الإشعارات')
