"""Notifications — manual single + broadcast + history."""
from datetime import datetime
from flask import (
    render_template, request, redirect, url_for, flash, g,
)
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action, admin_permission_required
from app.models.admin import BroadcastNotification
from app.models.tenant import Tenant
from app.models.user import User
from app.models.notification import Notification
from app.models.subscription import SubscriptionPlan
from app.services.email_service import send_email


# ───────────────────────────── send to one tenant ─────────────────────────────

@admin_bp.route('/notifications/send', methods=['GET', 'POST'])
@admin_permission_required('notifications', 'view', write_action='send')
def notifications_send():
    """Send a notification to a single tenant."""
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id', type=int)
        title = (request.form.get('title') or '').strip()
        body = (request.form.get('body') or '').strip()
        priority = request.form.get('priority', 'info')
        channels = request.form.getlist('channels') or ['in_app']

        if not tenant_id or not title or not body:
            flash('الحقول المطلوبة ناقصة', 'danger')
            return redirect(url_for('admin.notifications_send'))

        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            flash('المكتب غير موجود', 'danger')
            return redirect(url_for('admin.notifications_send'))

        sent = _deliver_to_tenant(tenant, title, body, priority, channels)

        log_action(
            'NOTIFICATION_SENT', entity_type='Tenant', entity_id=tenant_id,
            new_value={'title': title, 'channels': channels},
            description=f'Sent "{title}" to {tenant.name} via {",".join(channels)}',
        )
        db.session.commit()
        flash(f'تم إرسال الإشعار إلى {sent} مستخدم في {tenant.name}', 'success')
        return redirect(url_for('admin.notifications_send'))

    tenants = Tenant.query.order_by(Tenant.name).all()
    pre_tenant_id = request.args.get('tenant_id', type=int)
    return render_template(
        'admin/notifications/send.html',
        tenants=tenants, pre_tenant_id=pre_tenant_id,
    )


# ───────────────────────────── broadcast ─────────────────────────────

@admin_bp.route('/notifications/broadcast', methods=['GET', 'POST'])
@admin_permission_required('notifications', 'view', write_action='send')
def notifications_broadcast():
    """Broadcast to all tenants matching audience filter."""
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        body = (request.form.get('body') or '').strip()
        priority = request.form.get('priority', 'info')
        audience_type = request.form.get('audience_type', 'all')
        plan_id = request.form.get('plan_id', type=int)
        status = (request.form.get('status') or '').strip()
        channels = request.form.getlist('channels') or ['in_app']
        action = request.form.get('action', 'send')

        if not title or not body:
            flash('العنوان والمحتوى مطلوبان', 'danger')
            return redirect(url_for('admin.notifications_broadcast'))

        # Build audience
        query = Tenant.query
        audience_filter = {}
        if audience_type == 'plan' and plan_id:
            query = query.filter(Tenant.subscription_plan_id == plan_id)
            audience_filter = {'plan_id': plan_id}
        elif audience_type == 'status' and status:
            query = query.filter(Tenant.subscription_status == status)
            audience_filter = {'status': status}

        target_tenants = query.all()

        if action == 'preview':
            return render_template(
                'admin/notifications/broadcast.html',
                plans=SubscriptionPlan.query.all(),
                preview={
                    'title': title, 'body': body, 'priority': priority,
                    'audience_type': audience_type, 'channels': channels,
                    'count': len(target_tenants),
                    'tenants': target_tenants[:20],
                },
                form=request.form,
            )

        bc = BroadcastNotification(
            title=title, body=body,
            audience_type=audience_type,
            audience_filter=audience_filter,
            channels=channels,
            sent_at=datetime.utcnow(),
            created_by=g.current_admin.id,
        )
        db.session.add(bc)
        db.session.flush()

        total_users_sent = 0
        for tenant in target_tenants:
            total_users_sent += _deliver_to_tenant(tenant, title, body, priority, channels)

        bc.sent_count = total_users_sent
        log_action(
            'BROADCAST_SENT', entity_type='Broadcast', entity_id=bc.id,
            new_value={'title': title, 'audience': audience_type, 'recipients': total_users_sent},
            description=f'Broadcast "{title}" to {len(target_tenants)} tenants ({total_users_sent} users)',
        )
        db.session.commit()
        flash(f'تم إرسال الإشعار إلى {total_users_sent} مستخدم في {len(target_tenants)} مكتب', 'success')
        return redirect(url_for('admin.notifications_history'))

    plans = SubscriptionPlan.query.all()
    return render_template(
        'admin/notifications/broadcast.html',
        plans=plans, preview=None, form={},
    )


# ───────────────────────────── history ─────────────────────────────

@admin_bp.route('/notifications/history')
@admin_permission_required('notifications', 'view')
def notifications_history():
    """List of past broadcasts with sent counts."""
    page = request.args.get('page', 1, type=int)
    pagination = BroadcastNotification.query.order_by(
        BroadcastNotification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/notifications/history.html', pagination=pagination)


# ───────────────────────────── helper ─────────────────────────────

def _deliver_to_tenant(tenant, title, body, priority, channels):
    """Deliver a notification to all active users of a tenant via selected channels."""
    users = User.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    sent_count = 0

    for u in users:
        # In-app notification
        if 'in_app' in channels:
            n = Notification(
                tenant_id=tenant.id,
                user_id=u.id,
                notification_type='general',
                title=title,
                body=body,
                priority=priority,
                channel='in_app',
                is_read=False,
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow(),
            )
            db.session.add(n)

        # Email
        if 'email' in channels and u.email:
            html = f"""
            <div dir='rtl' style='font-family:Tajawal,Arial;padding:24px;max-width:600px;margin:auto'>
                <h2 style='color:#1849A9'>{title}</h2>
                <div style='font-size:14px;line-height:1.8;color:#333'>{body}</div>
                <hr style='border:none;border-top:1px solid #eee;margin:24px 0'>
                <p style='color:#888;font-size:12px'>LexOffice — Manasety</p>
            </div>
            """
            try:
                send_email(u.email, title, html)
            except Exception:
                pass

        sent_count += 1

    return sent_count
