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


# ===================== DEVICE TOKEN REGISTRATION (FCM) =====================

@api_bp.route('/notifications/register-device', methods=['POST'])
@api_login_required
def api_register_device():
    """Register/refresh an FCM device token for the current user."""
    from app.models.device_token import DeviceToken

    data = get_json_or_form()
    fcm_token = (data.get('fcm_token') or '').strip()
    platform = (data.get('platform') or '').strip().lower()
    device_name = (data.get('device_name') or None)
    app_version = (data.get('app_version') or None)

    if not fcm_token:
        return validation_error({'fcm_token': 'fcm_token مطلوب'})
    if platform not in ('ios', 'android', 'web'):
        return validation_error({'platform': 'platform يجب أن يكون ios/android/web'})

    existing = DeviceToken.query.filter_by(fcm_token=fcm_token).first()
    if existing:
        # Reassign if it moved to a different user
        existing.user_id = g.current_user.id
        existing.tenant_id = g.tenant_id
        existing.platform = platform
        existing.device_name = device_name or existing.device_name
        existing.app_version = app_version or existing.app_version
        existing.last_seen_at = datetime.utcnow()
        db.session.commit()
        return success_response(data=existing.to_dict(), message='تم تحديث جهازك')

    dt = DeviceToken(
        tenant_id=g.tenant_id,
        user_id=g.current_user.id,
        fcm_token=fcm_token,
        platform=platform,
        device_name=device_name,
        app_version=app_version,
    )
    db.session.add(dt)
    db.session.commit()
    return success_response(data=dt.to_dict(), message='تم تسجيل الجهاز', status_code=201)


@api_bp.route('/notifications/unregister-device', methods=['DELETE'])
@api_login_required
def api_unregister_device():
    """Remove an FCM device token (call on logout)."""
    from app.models.device_token import DeviceToken

    data = get_json_or_form()
    fcm_token = (data.get('fcm_token') or '').strip()
    if not fcm_token:
        return validation_error({'fcm_token': 'fcm_token مطلوب'})

    DeviceToken.query.filter_by(
        fcm_token=fcm_token, user_id=g.current_user.id
    ).delete()
    db.session.commit()
    return success_response(message='تم إلغاء تسجيل الجهاز')


# ===================== FCM DEBUG (diagnostics) =====================

@api_bp.route('/notifications/fcm-debug', methods=['GET'])
@api_login_required
def api_fcm_debug():
    """Diagnostic route: reports FCM setup state + device tokens.

    Returns JSON like:
    {
      "firebase_admin_installed": true,
      "service_account_env_set": true,
      "service_account_file_exists": true,
      "service_account_path": "/etc/lexoffice/firebase-service-account.json",
      "firebase_initialized": true,
      "device_tokens_in_tenant": 3,
      "device_tokens_for_current_user": 1,
      "my_tokens": [{"id":1,"platform":"ios","device_name":"iOS device","last_seen_at":"..."}],
      "tenant_id": 12,
      "current_user_id": 6
    }
    """
    import os
    from app.models.device_token import DeviceToken
    from flask import current_app

    # Try import firebase-admin
    try:
        import firebase_admin
        from firebase_admin import credentials  # noqa: F401
        installed = True
    except Exception as e:
        installed = False
        firebase_admin = None

    cred_path = (
        current_app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH')
        or os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
    )
    file_exists = bool(cred_path) and os.path.exists(cred_path) if cred_path else False

    # Try lazy-init
    fb_inited = False
    init_error = None
    if installed:
        try:
            from app.services.fcm_service import _init_firebase
            fb_inited = _init_firebase()
        except Exception as e:
            init_error = str(e)

    tokens_tenant = DeviceToken.query.filter_by(tenant_id=g.tenant_id).all()
    tokens_user = DeviceToken.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.current_user.id
    ).all()

    return success_response(data={
        'firebase_admin_installed': installed,
        'service_account_env_set': bool(cred_path),
        'service_account_path': cred_path,
        'service_account_file_exists': file_exists,
        'firebase_initialized': fb_inited,
        'init_error': init_error,
        'device_tokens_in_tenant': len(tokens_tenant),
        'device_tokens_for_current_user': len(tokens_user),
        'tokens_by_user': {
            t.user_id: (t.platform, t.device_name) for t in tokens_tenant
        },
        'my_tokens': [t.to_dict() for t in tokens_user],
        'tenant_id': g.tenant_id,
        'current_user_id': g.current_user.id,
    })


@api_bp.route('/notifications/fcm-test', methods=['POST'])
@api_login_required
def api_fcm_test():
    """Send a test push to all FCM-registered users in the tenant.

    Optionally include `user_id` in body to target a single user; default
    is everyone (including the caller — actor is NOT excluded so single-user
    tests work).
    """
    from app.services.fcm_service import send_push
    from app.models.device_token import DeviceToken

    data = get_json_or_form() if request.is_json or request.form else {}
    target_user_id = data.get('user_id') if isinstance(data, dict) else None

    if target_user_id:
        user_ids = [int(target_user_id)]
    else:
        # All distinct user_ids that have device tokens in this tenant
        rows = DeviceToken.query.filter_by(tenant_id=g.tenant_id).all()
        user_ids = sorted({r.user_id for r in rows})

    sent_per_user = {}
    for uid in user_ids:
        n = send_push(
            user_id=uid,
            title='اختبار الإشعارات',
            body='إذا وصلك هذا، الـ FCM يعمل! 🚀',
            related_type='case',
            related_id=1,
            route='/notifications',
        )
        sent_per_user[uid] = n

    total = sum(sent_per_user.values())
    return success_response(data={
        'targeted_users': user_ids,
        'sent_per_user': sent_per_user,
        'total_sent': total,
        'tenant_id': g.tenant_id,
    }, message=f'تم إرسال {total} إشعار')
