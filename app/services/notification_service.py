"""Notification service: in-app + email notifications."""
from flask import current_app
from app.extensions import db
from app.models.notification import Notification, NotificationSetting
from app.models.user import User
from app.services.email_service import send_email


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
                    subject=f'LexOffice: {title}',
                    html_body=email_html,
                )
        except Exception as e:
            current_app.logger.error(f'Notification email failed: {e}')

    return notification


def notify_tenant_users(tenant_id, notification_type, title, body=None,
                        priority='info', related_type=None, related_id=None,
                        actor_name=None, exclude_user_id=None):
    """Send notification to all active users in a tenant.

    The actor gets in-app only (no self-email). Others get in-app + email.
    """
    users = User.query.filter_by(tenant_id=tenant_id, is_active=True).all()
    notifications = []
    for user in users:
        is_actor = exclude_user_id and user.id == exclude_user_id
        if is_actor:
            # Actor: in-app only, no email to self
            n = _create_in_app_only(
                tenant_id=tenant_id,
                user_id=user.id,
                notification_type=notification_type,
                title=title,
                body=body,
                priority=priority,
                related_type=related_type,
                related_id=related_id,
            )
        else:
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


def _create_in_app_only(tenant_id, user_id, notification_type, title,
                        body=None, priority='info', related_type=None, related_id=None):
    """Create in-app notification only (no email). Used for the actor's own record."""
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
        return notification
    except Exception as e:
        current_app.logger.error(f'In-app notification failed: {e}')
        return None


def _build_notification_email(title, body, actor_name=None):
    """Build Arabic HTML email for notification."""
    actor_line = f'<p style="margin: 8px 0 0; color: #64748b; font-size: 13px;">بواسطة: <strong>{actor_name}</strong></p>' if actor_name else ''
    body_line = f'<p style="margin: 8px 0 0; color: #475569;">{body}</p>' if body else ''
    return f"""
    <div dir="rtl" style="font-family: Tajawal, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1849A9; margin-bottom: 16px;">LexOffice</h2>
        <div style="background: #f1f5f9; padding: 16px; border-radius: 8px; margin: 16px 0; border-right: 4px solid #1849A9;">
            <h3 style="margin: 0; color: #1e293b; font-size: 16px;">{title}</h3>
            {body_line}
        </div>
        {actor_line}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="color: #94a3b8; font-size: 12px;">هذا إشعار تلقائي من نظام LexOffice لإدارة مكتب المحاماة.</p>
    </div>
    """
