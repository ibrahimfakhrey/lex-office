"""Notification service: in-app + email + FCM push notifications."""
from flask import current_app
from app.extensions import db
from app.models.notification import Notification, NotificationSetting
from app.models.user import User
from app.services.email_service import send_email
from app.services.fcm_service import send_push
from app.utils.helpers import product_name


# Maps related_type → mobile deep-link route. The mobile FcmService reads
# data.route and calls GoRouter.go() when the user taps the notification.
def _route_for(related_type, related_id, notification_type=None):
    if related_type == 'case' and related_id:
        return f'/cases/{related_id}'
    if related_type == 'session' and related_id:
        return f'/sessions/{related_id}'
    if related_type == 'judgment' and related_id:
        return f'/judgments/{related_id}'
    if related_type == 'enforcement' and related_id:
        return f'/enforcement/{related_id}'
    if related_type == 'poa' and related_id:
        return f'/poa/{related_id}'
    if related_type == 'task' and related_id:
        return f'/tasks/{related_id}'
    if related_type == 'document' and related_id:
        return f'/documents/{related_id}'
    if related_type == 'invoice' and related_id:
        return f'/financial/invoices/{related_id}'
    if related_type == 'payment':
        return '/financial/payments'
    if related_type == 'client' and related_id:
        return f'/clients/{related_id}'
    # Fallback for non-entity notifications
    if notification_type == 'payment_received':
        return '/financial/payments'
    return '/notifications'


def create_notification(
    tenant_id,
    user_id,
    notification_type,
    title,
    body=None,
    priority='info',
    related_type=None,
    related_id=None,
    actor_name=None,
):
    """Create in-app notification and optionally send email.

    Always creates in-app notification first. Email failure won't
    prevent the in-app notification from being saved.
    """
    notification = None

    # Check user's notification settings
    try:
        setting = NotificationSetting.query.filter_by(
            user_id=user_id,
            notification_type=notification_type,
        ).first()
    except Exception:
        setting = None

    in_app_enabled = setting.in_app_enabled if setting else True
    email_enabled = setting.email_enabled if setting else True

    # Step 1: Create in-app notification (must succeed)
    if in_app_enabled:
        try:
            notification = Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                notification_type=notification_type,
                priority=priority,
                title=title,
                body=body,
                channel='in_app',
                related_type=related_type,
                related_id=related_id,
                delivery_status='delivered',
            )
            db.session.add(notification)
            db.session.flush()
        except Exception as e:
            current_app.logger.error(f'In-app notification failed: {e}')
            return None

    # Step 2: Send email (failure is non-fatal)
    if email_enabled:
        try:
            user = User.query.get(user_id)
            if user and user.email:
                email_html = _build_notification_email(title, body, actor_name)
                send_email(
                    to=user.email,
                    subject=f'{product_name()}: {title}',
                    html_body=email_html,
                )
        except Exception as e:
            current_app.logger.error(f'Notification email failed: {e}')

    # Step 3: Push to FCM-registered devices (failure is non-fatal)
    try:
        send_push(
            user_id=user_id,
            title=title,
            body=body,
            related_type=related_type,
            related_id=related_id,
            route=_route_for(related_type, related_id, notification_type),
            extra_data={'notification_type': notification_type, 'priority': priority},
        )
    except Exception as e:
        current_app.logger.error(f'FCM push failed: {e}')

    return notification


def notify_tenant_users(tenant_id, notification_type, title, body=None,
                        priority='info', related_type=None, related_id=None,
                        actor_name=None, exclude_user_id=None):
    """Send in-app + email + push to every active user in the tenant.

    `exclude_user_id` is accepted for back-compat but no longer suppresses
    the actor — single-user tenants and multi-device owners want to be
    notified of their own actions too.
    """
    users = User.query.filter_by(tenant_id=tenant_id, is_active=True).all()
    notifications = []
    for user in users:
        n = create_notification(
            tenant_id=tenant_id,
            user_id=user.id,
            notification_type=notification_type,
            title=title,
            body=body,
            priority=priority,
            related_type=related_type,
            related_id=related_id,
            actor_name=actor_name,
        )
        if n:
            notifications.append(n)
    return notifications


def _create_in_app_and_push(tenant_id, user_id, notification_type, title,
                            body=None, priority='info', related_type=None, related_id=None):
    """In-app DB record + push only (no email). Kept for any direct callers."""
    try:
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            priority=priority,
            title=title,
            body=body,
            channel='in_app',
            related_type=related_type,
            related_id=related_id,
            delivery_status='delivered',
        )
        db.session.add(notification)
        db.session.flush()
    except Exception as e:
        current_app.logger.error(f'In-app notification failed: {e}')
        notification = None

    try:
        send_push(
            user_id=user_id,
            title=title,
            body=body,
            related_type=related_type,
            related_id=related_id,
            route=_route_for(related_type, related_id, notification_type),
            extra_data={'notification_type': notification_type, 'priority': priority},
        )
    except Exception as e:
        current_app.logger.error(f'FCM push failed: {e}')

    return notification


# Back-compat alias for any older imports.
_create_in_app_only = _create_in_app_and_push


def _build_notification_email(title, body, actor_name=None):
    """Build Arabic HTML email for notification."""
    brand = product_name()
    actor_line = f'<p style="margin: 8px 0 0; color: #64748b; font-size: 13px;">بواسطة: <strong>{actor_name}</strong></p>' if actor_name else ''
    body_line = f'<p style="margin: 8px 0 0; color: #475569;">{body}</p>' if body else ''
    return f"""
    <div dir="rtl" style="font-family: Tajawal, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1849A9; margin-bottom: 16px;">{brand}</h2>
        <div style="background: #f1f5f9; padding: 16px; border-radius: 8px; margin: 16px 0; border-right: 4px solid #1849A9;">
            <h3 style="margin: 0; color: #1e293b; font-size: 16px;">{title}</h3>
            {body_line}
        </div>
        {actor_line}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="color: #94a3b8; font-size: 12px;">هذا إشعار تلقائي من نظام {brand} لإدارة مكتب المحاماة.</p>
    </div>
    """
