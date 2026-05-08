"""Tenants management — list, detail, suspend/cancel/extend/change-plan."""
from datetime import datetime, timedelta
import csv
import io

from flask import (
    render_template, request, redirect, url_for, flash, g,
    abort, Response, jsonify,
)
from sqlalchemy import or_, func
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action, admin_permission_required
from app.models.tenant import Tenant
from app.models.user import User
from app.models.subscription import SubscriptionPlan, SubscriptionPayment
from app.models.client import Client
from app.models.case import Case
from app.models.session import Session as CaseSession
from app.models.admin import (
    AdminAuditLog, TenantFeatureOverride, TenantSupportNote,
)


# ───────────────────────────── helpers ─────────────────────────────

def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None


def _tenant_or_404(tenant_id):
    t = Tenant.query.get(tenant_id)
    if not t:
        abort(404)
    return t


# ───────────────────────────── list ─────────────────────────────

@admin_bp.route('/tenants')
@admin_permission_required('tenants', 'view')
def tenants_list():
    """Tenants list with filters, search, sort, pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    search = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    plan_id = request.args.get('plan_id', type=int)
    expiring_soon = request.args.get('expiring_soon') == '1'
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))
    sort = request.args.get('sort', 'created_desc')

    query = Tenant.query

    # Filters
    if search:
        query = query.filter(or_(
            Tenant.name.ilike(f'%{search}%'),
            Tenant.email.ilike(f'%{search}%'),
            Tenant.phone.ilike(f'%{search}%'),
        ))
    if status:
        query = query.filter(Tenant.subscription_status == status)
    if plan_id:
        query = query.filter(Tenant.subscription_plan_id == plan_id)
    if date_from:
        query = query.filter(Tenant.created_at >= date_from)
    if date_to:
        query = query.filter(Tenant.created_at < date_to + timedelta(days=1))
    if expiring_soon:
        in_seven = datetime.utcnow() + timedelta(days=7)
        query = query.filter(or_(
            db.and_(Tenant.trial_ends_at.isnot(None),
                    Tenant.trial_ends_at <= in_seven,
                    Tenant.trial_ends_at >= datetime.utcnow()),
            db.and_(Tenant.subscription_ends_at.isnot(None),
                    Tenant.subscription_ends_at <= in_seven,
                    Tenant.subscription_ends_at >= datetime.utcnow()),
        ))

    # Sort
    if sort == 'created_asc':
        query = query.order_by(Tenant.created_at.asc())
    elif sort == 'expiry_asc':
        query = query.order_by(Tenant.subscription_ends_at.asc().nullslast())
    elif sort == 'expiry_desc':
        query = query.order_by(Tenant.subscription_ends_at.desc().nullslast())
    elif sort == 'plan':
        query = query.order_by(Tenant.subscription_plan_id.asc())
    elif sort == 'name':
        query = query.order_by(Tenant.name.asc())
    else:  # created_desc default
        query = query.order_by(Tenant.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Active seats per tenant (compute in-page only)
    page_ids = [t.id for t in pagination.items]
    seats_map = {}
    if page_ids:
        rows = db.session.query(User.tenant_id, func.count(User.id)).filter(
            User.tenant_id.in_(page_ids), User.is_active == True
        ).group_by(User.tenant_id).all()
        seats_map = {tid: cnt for tid, cnt in rows}

    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.id).all()

    return render_template(
        'admin/tenants/list.html',
        pagination=pagination,
        seats_map=seats_map,
        plans=plans,
        filters={
            'q': search, 'status': status, 'plan_id': plan_id,
            'expiring_soon': expiring_soon,
            'date_from': request.args.get('date_from', ''),
            'date_to': request.args.get('date_to', ''),
            'sort': sort,
        },
    )


# ───────────────────────────── export ─────────────────────────────

@admin_bp.route('/tenants/export')
@admin_permission_required('tenants', 'view')
def tenants_export():
    """Export current filtered tenants list to CSV."""
    # Reuse the same filter logic as the list (simplified — no pagination)
    search = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()
    plan_id = request.args.get('plan_id', type=int)

    query = Tenant.query
    if search:
        query = query.filter(or_(
            Tenant.name.ilike(f'%{search}%'),
            Tenant.email.ilike(f'%{search}%'),
        ))
    if status:
        query = query.filter(Tenant.subscription_status == status)
    if plan_id:
        query = query.filter(Tenant.subscription_plan_id == plan_id)

    rows = query.order_by(Tenant.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'ID', 'Name', 'Email', 'Phone', 'Plan', 'Status',
        'Created', 'Trial Ends', 'Subscription Ends', 'Active', 'Country', 'City'
    ])
    for t in rows:
        writer.writerow([
            t.id, t.name, t.email or '', t.phone or '',
            t.subscription_plan.name if t.subscription_plan else '',
            t.subscription_status,
            t.created_at.strftime('%Y-%m-%d') if t.created_at else '',
            t.trial_ends_at.strftime('%Y-%m-%d') if t.trial_ends_at else '',
            t.subscription_ends_at.strftime('%Y-%m-%d') if t.subscription_ends_at else '',
            'Yes' if t.is_active else 'No',
            t.country or '', t.city or '',
        ])
    csv_data = buf.getvalue()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=tenants_{datetime.utcnow().strftime("%Y%m%d")}.csv'},
    )


# ───────────────────────────── detail ─────────────────────────────

@admin_bp.route('/tenants/<int:tenant_id>')
@admin_permission_required('tenants', 'view')
def tenant_detail(tenant_id):
    """Tenant detail — overview tab (default). Other tabs are GET endpoints."""
    tenant = _tenant_or_404(tenant_id)

    active_users = User.query.filter_by(tenant_id=tenant_id, is_active=True).count()
    total_users = User.query.filter_by(tenant_id=tenant_id).count()

    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.price_monthly).all()

    # AI status drives the one-click toggle button rendered in the header.
    from app.services.ai_usage import is_ai_enabled
    plan_grants_ai = bool(
        (tenant.subscription_plan.features or {}).get('ai_enabled')
        if tenant.subscription_plan else False
    )
    ai_override = TenantFeatureOverride.query.filter_by(
        tenant_id=tenant_id, feature_key='ai_enabled',
    ).first()
    ai_status = {
        'plan_grants': plan_grants_ai,
        'override_disabled': (ai_override is not None and not ai_override.enabled),
        'currently_enabled': is_ai_enabled(tenant),
    }

    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='overview',
        active_users=active_users,
        total_users=total_users,
        plans=plans,
        ai_status=ai_status,
    )


@admin_bp.route('/tenants/<int:tenant_id>/usage')
@admin_permission_required('tenants', 'view')
def tenant_usage(tenant_id):
    """Usage stats tab — case/client/session counts, storage, last logins."""
    tenant = _tenant_or_404(tenant_id)

    cases_count = Case.query.filter_by(tenant_id=tenant_id).count()
    clients_count = Client.query.filter_by(tenant_id=tenant_id).count()
    sessions_count = CaseSession.query.filter_by(tenant_id=tenant_id).count()
    users_count = User.query.filter_by(tenant_id=tenant_id).count()
    active_users_count = User.query.filter_by(tenant_id=tenant_id, is_active=True).count()

    # Last 10 user logins (across all tenant users)
    recent_logins = (
        User.query.filter(User.tenant_id == tenant_id, User.last_login_at.isnot(None))
        .order_by(User.last_login_at.desc())
        .limit(10).all()
    )

    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='usage',
        plans=SubscriptionPlan.query.all(),
        active_users=active_users_count,
        total_users=users_count,
        usage={
            'cases': cases_count,
            'clients': clients_count,
            'sessions': sessions_count,
            'users': users_count,
            'active_users': active_users_count,
        },
        recent_logins=recent_logins,
    )


@admin_bp.route('/tenants/<int:tenant_id>/billing')
@admin_permission_required('tenants', 'view')
def tenant_billing(tenant_id):
    """Billing tab — invoices and notes/files."""
    tenant = _tenant_or_404(tenant_id)
    payments = (
        SubscriptionPayment.query.filter_by(tenant_id=tenant_id)
        .order_by(SubscriptionPayment.created_at.desc()).all()
    )
    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='billing',
        plans=SubscriptionPlan.query.all(),
        active_users=User.query.filter_by(tenant_id=tenant_id, is_active=True).count(),
        total_users=User.query.filter_by(tenant_id=tenant_id).count(),
        payments=payments,
    )


@admin_bp.route('/tenants/<int:tenant_id>/features')
@admin_permission_required('tenants', 'view')
def tenant_features(tenant_id):
    """Features tab — show plan flags + per-tenant overrides."""
    tenant = _tenant_or_404(tenant_id)
    plan_features = (tenant.subscription_plan.features if tenant.subscription_plan else {}) or {}
    overrides = TenantFeatureOverride.query.filter_by(tenant_id=tenant_id).all()

    # Build a unified view of features: plan flag value + override info
    feature_keys = set(plan_features.keys())
    for o in overrides:
        feature_keys.add(o.feature_key)
    overrides_map = {o.feature_key: o for o in overrides}

    from app.admin.feature_keys import label_for

    feature_view = []
    for key in sorted(feature_keys):
        plan_val = plan_features.get(key)
        ov = overrides_map.get(key)
        if ov and not ov.is_expired:
            effective = ov.enabled
            source = 'override'
        else:
            effective = bool(plan_val) if not isinstance(plan_val, bool) else plan_val
            source = 'plan'
        feature_view.append({
            'key': key,
            'label': label_for(key),
            'plan_value': plan_val,
            'override': ov,
            'effective': effective,
            'source': source,
        })

    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='features',
        plans=SubscriptionPlan.query.all(),
        active_users=User.query.filter_by(tenant_id=tenant_id, is_active=True).count(),
        total_users=User.query.filter_by(tenant_id=tenant_id).count(),
        feature_view=feature_view,
    )


@admin_bp.route('/tenants/<int:tenant_id>/audit')
@admin_permission_required('tenants', 'view')
def tenant_audit(tenant_id):
    """Audit log tab — admin actions on this tenant."""
    tenant = _tenant_or_404(tenant_id)
    logs = (
        AdminAuditLog.query.filter_by(entity_type='Tenant', entity_id=tenant_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(200).all()
    )
    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='audit',
        plans=SubscriptionPlan.query.all(),
        active_users=User.query.filter_by(tenant_id=tenant_id, is_active=True).count(),
        total_users=User.query.filter_by(tenant_id=tenant_id).count(),
        audit_logs=logs,
    )


@admin_bp.route('/tenants/<int:tenant_id>/notes')
@admin_permission_required('tenants', 'view')
def tenant_notes(tenant_id):
    """Internal admin notes tab."""
    tenant = _tenant_or_404(tenant_id)
    notes = (
        TenantSupportNote.query.filter_by(tenant_id=tenant_id)
        .order_by(TenantSupportNote.created_at.desc()).all()
    )
    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant,
        active_tab='notes',
        plans=SubscriptionPlan.query.all(),
        active_users=User.query.filter_by(tenant_id=tenant_id, is_active=True).count(),
        total_users=User.query.filter_by(tenant_id=tenant_id).count(),
        notes=notes,
    )


# ───────────────────────────── actions ─────────────────────────────

@admin_bp.route('/tenants/<int:tenant_id>/edit', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_edit(tenant_id):
    """Edit basic tenant info."""
    tenant = _tenant_or_404(tenant_id)
    old = tenant.to_dict()

    tenant.name = (request.form.get('name') or tenant.name).strip()
    tenant.email = (request.form.get('email') or '').strip() or None
    tenant.phone = (request.form.get('phone') or '').strip() or None
    tenant.country = (request.form.get('country') or '').strip() or None
    tenant.city = (request.form.get('city') or '').strip() or None
    tenant.bar_registration_no = (request.form.get('bar_registration_no') or '').strip() or None
    tenant.address = (request.form.get('address') or '').strip() or None

    log_action(
        'TENANT_EDITED', entity_type='Tenant', entity_id=tenant_id,
        old_value=old, new_value=tenant.to_dict(),
        description=f'Edited basic info for {tenant.name}',
    )
    db.session.commit()
    flash('تم تحديث بيانات المكتب بنجاح', 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/suspend', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_suspend(tenant_id):
    """Suspend a tenant — locks all their users out."""
    tenant = _tenant_or_404(tenant_id)
    reason = (request.form.get('reason') or '').strip() or 'Suspended by admin'

    old = {'subscription_status': tenant.subscription_status, 'is_active': tenant.is_active}
    tenant.subscription_status = 'suspended'
    tenant.is_active = False
    tenant.suspension_reason = reason
    tenant.suspended_at = datetime.utcnow()

    log_action(
        'TENANT_SUSPENDED', entity_type='Tenant', entity_id=tenant_id,
        old_value=old,
        new_value={'subscription_status': 'suspended', 'is_active': False, 'reason': reason},
        description=f'Suspended {tenant.name}: {reason}',
    )
    db.session.commit()
    flash(f'تم تعليق المكتب: {tenant.name}', 'warning')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/unsuspend', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_unsuspend(tenant_id):
    """Reactivate a suspended tenant."""
    tenant = _tenant_or_404(tenant_id)
    old = {'subscription_status': tenant.subscription_status, 'is_active': tenant.is_active}

    # If they had a paid subscription, restore to active. Otherwise trial.
    if tenant.subscription_plan_id and tenant.subscription_ends_at and tenant.subscription_ends_at > datetime.utcnow():
        tenant.subscription_status = 'active'
    elif tenant.trial_ends_at and tenant.trial_ends_at > datetime.utcnow():
        tenant.subscription_status = 'trial'
    else:
        tenant.subscription_status = 'active'  # fallback
    tenant.is_active = True
    tenant.suspension_reason = None
    tenant.suspended_at = None

    log_action(
        'TENANT_UNSUSPENDED', entity_type='Tenant', entity_id=tenant_id,
        old_value=old,
        new_value={'subscription_status': tenant.subscription_status, 'is_active': True},
        description=f'Reactivated {tenant.name}',
    )
    db.session.commit()
    flash(f'تم إعادة تفعيل المكتب: {tenant.name}', 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/cancel', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_cancel(tenant_id):
    """Cancel a tenant subscription."""
    tenant = _tenant_or_404(tenant_id)
    reason = (request.form.get('reason') or '').strip() or 'Cancelled by admin'
    old = {'subscription_status': tenant.subscription_status, 'is_active': tenant.is_active}

    tenant.subscription_status = 'cancelled'
    tenant.is_active = False
    tenant.cancelled_at = datetime.utcnow()
    tenant.suspension_reason = reason

    log_action(
        'TENANT_CANCELLED', entity_type='Tenant', entity_id=tenant_id,
        old_value=old, new_value={'subscription_status': 'cancelled', 'reason': reason},
        description=f'Cancelled {tenant.name}: {reason}',
    )
    db.session.commit()
    flash(f'تم إلغاء اشتراك المكتب: {tenant.name}', 'danger')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/extend', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_extend(tenant_id):
    """Extend trial or subscription by N days."""
    tenant = _tenant_or_404(tenant_id)
    days = request.form.get('days', type=int) or 7
    target = (request.form.get('target') or 'subscription').strip()  # trial or subscription
    old = {
        'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        'subscription_ends_at': tenant.subscription_ends_at.isoformat() if tenant.subscription_ends_at else None,
    }

    if target == 'trial':
        base = tenant.trial_ends_at or datetime.utcnow()
        tenant.trial_ends_at = max(base, datetime.utcnow()) + timedelta(days=days)
    else:
        base = tenant.subscription_ends_at or datetime.utcnow()
        tenant.subscription_ends_at = max(base, datetime.utcnow()) + timedelta(days=days)

    new = {
        'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        'subscription_ends_at': tenant.subscription_ends_at.isoformat() if tenant.subscription_ends_at else None,
    }
    log_action(
        'TENANT_EXTENDED', entity_type='Tenant', entity_id=tenant_id,
        old_value=old, new_value=new,
        description=f'Extended {target} by {days} days',
    )
    db.session.commit()
    flash(f'تم تمديد {target} بعدد {days} أيام', 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/change-plan', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_change_plan(tenant_id):
    """Move tenant to a different plan."""
    tenant = _tenant_or_404(tenant_id)
    new_plan_id = request.form.get('plan_id', type=int)
    if not new_plan_id:
        flash('يرجى اختيار خطة', 'danger')
        return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))

    new_plan = SubscriptionPlan.query.get(new_plan_id)
    if not new_plan:
        flash('الخطة غير موجودة', 'danger')
        return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))

    old_plan_id = tenant.subscription_plan_id
    old_plan_name = tenant.subscription_plan.name if tenant.subscription_plan else None
    tenant.subscription_plan_id = new_plan_id

    from app.services.billing_service import create_subscription_invoice
    billing_cycle = (request.form.get('billing_cycle') or 'monthly').lower()
    payment_type = 'upgrade' if old_plan_id else billing_cycle
    invoice = create_subscription_invoice(
        tenant, new_plan, billing_cycle=billing_cycle,
        payment_type=payment_type,
        created_by_admin=g.current_admin.id,
        commit=False,
    )

    log_action(
        'TENANT_PLAN_CHANGED', entity_type='Tenant', entity_id=tenant_id,
        old_value={'plan_id': old_plan_id, 'plan_name': old_plan_name},
        new_value={'plan_id': new_plan_id, 'plan_name': new_plan.name,
                   'invoice_id': invoice.id if invoice else None,
                   'invoice_number': invoice.invoice_number if invoice else None},
        description=f'Plan changed from {old_plan_name} to {new_plan.name}',
    )
    db.session.commit()
    msg = f'تم تغيير الخطة إلى: {new_plan.name_ar}'
    if invoice:
        msg += f' وأنشأنا فاتورة جديدة: {invoice.invoice_number}'
    flash(msg, 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/notes', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_add_note(tenant_id):
    """Add an internal admin support note about this tenant."""
    tenant = _tenant_or_404(tenant_id)
    note_text = (request.form.get('note') or '').strip()
    if not note_text:
        flash('الملاحظة مطلوبة', 'danger')
        return redirect(url_for('admin.tenant_notes', tenant_id=tenant_id))

    note = TenantSupportNote(
        tenant_id=tenant_id, note=note_text, created_by=g.current_admin.id,
    )
    db.session.add(note)
    log_action(
        'NOTE_ADDED', entity_type='Tenant', entity_id=tenant_id,
        new_value={'note': note_text[:200]},
        description=f'Added support note to {tenant.name}',
    )
    db.session.commit()
    flash('تم إضافة الملاحظة', 'success')
    return redirect(url_for('admin.tenant_notes', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/notes/<int:note_id>/delete', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_delete_note(tenant_id, note_id):
    """Delete a support note."""
    note = TenantSupportNote.query.filter_by(id=note_id, tenant_id=tenant_id).first_or_404()
    db.session.delete(note)
    log_action(
        'NOTE_DELETED', entity_type='Tenant', entity_id=tenant_id,
        old_value={'note_id': note_id},
        description=f'Deleted support note {note_id}',
    )
    db.session.commit()
    flash('تم حذف الملاحظة', 'warning')
    return redirect(url_for('admin.tenant_notes', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/features/toggle', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_feature_toggle(tenant_id):
    """Set or update a per-tenant feature override."""
    tenant = _tenant_or_404(tenant_id)
    feature_key = (request.form.get('feature_key') or '').strip()
    enabled = request.form.get('enabled') == '1'
    expires_at = _parse_date(request.form.get('expires_at'))
    reason = (request.form.get('reason') or '').strip() or None

    if not feature_key:
        flash('مفتاح الميزة مطلوب', 'danger')
        return redirect(url_for('admin.tenant_features', tenant_id=tenant_id))

    override = TenantFeatureOverride.query.filter_by(
        tenant_id=tenant_id, feature_key=feature_key
    ).first()

    old = override.to_dict() if override else None

    if override:
        override.enabled = enabled
        override.expires_at = expires_at
        override.reason = reason
    else:
        override = TenantFeatureOverride(
            tenant_id=tenant_id, feature_key=feature_key,
            enabled=enabled, expires_at=expires_at, reason=reason,
            created_by=g.current_admin.id,
        )
        db.session.add(override)

    db.session.flush()  # to get override.id
    log_action(
        'FEATURE_OVERRIDE_SET', entity_type='Tenant', entity_id=tenant_id,
        old_value=old, new_value=override.to_dict(),
        description=f'Override {feature_key} = {enabled} for {tenant.name}',
    )
    db.session.commit()
    flash(f'تم تحديث الميزة: {feature_key}', 'success')
    return redirect(url_for('admin.tenant_features', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/features/<int:override_id>/remove', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_feature_remove(tenant_id, override_id):
    """Remove an override (revert to plan-level flag)."""
    override = TenantFeatureOverride.query.filter_by(
        id=override_id, tenant_id=tenant_id
    ).first_or_404()
    feature_key = override.feature_key
    db.session.delete(override)
    log_action(
        'FEATURE_OVERRIDE_REMOVED', entity_type='Tenant', entity_id=tenant_id,
        old_value={'feature_key': feature_key},
        description=f'Removed override for {feature_key}',
    )
    db.session.commit()
    flash(f'تم إزالة الـ Override: {feature_key}', 'warning')
    return redirect(url_for('admin.tenant_features', tenant_id=tenant_id))


# ────────────── one-click AI master kill switch ──────────────

@admin_bp.route('/tenants/<int:tenant_id>/ai/toggle', methods=['POST'])
@admin_permission_required('tenants', 'edit')
def tenant_ai_toggle(tenant_id):
    """One-click toggle: master AI on/off for this tenant.

    Three states the button cycles between:
      - Plan grants AI, no override        → click writes override(enabled=False)
      - Override(enabled=False) exists     → click DELETES the override
                                              (reverts to plan default)
      - Plan does not grant AI             → click is a no-op
                                              (button hidden in template anyway)

    Per-feature overrides are unaffected — admins still go to the Features
    tab for granular per-feature toggling. This is the master kill switch.
    """
    tenant = _tenant_or_404(tenant_id)
    intent = (request.form.get('intent') or '').strip()  # 'disable' | 'enable'

    override = TenantFeatureOverride.query.filter_by(
        tenant_id=tenant_id, feature_key='ai_enabled',
    ).first()

    if intent == 'disable':
        if override is None:
            override = TenantFeatureOverride(
                tenant_id=tenant_id,
                feature_key='ai_enabled',
                enabled=False,
                reason=(request.form.get('reason') or '').strip()
                       or 'Disabled via one-click admin action',
                created_by=g.current_admin.id,
            )
            db.session.add(override)
        else:
            override.enabled = False
            override.expires_at = None  # any prior auto-expiry is cancelled
            override.reason = ((request.form.get('reason') or '').strip()
                              or override.reason or 'Disabled via one-click admin action')
        log_action(
            'TENANT_AI_DISABLED', entity_type='Tenant', entity_id=tenant_id,
            new_value={'reason': override.reason},
            description=f'AI disabled for {tenant.name} via one-click toggle',
        )
        db.session.commit()
        flash(f'تم تعطيل الذكاء الاصطناعي لمكتب: {tenant.name}', 'warning')

    elif intent == 'enable':
        if override is not None and not override.enabled:
            db.session.delete(override)
            log_action(
                'TENANT_AI_REENABLED', entity_type='Tenant', entity_id=tenant_id,
                description=f'AI re-enabled for {tenant.name} (override removed)',
            )
            db.session.commit()
            flash(f'تم إعادة تفعيل الذكاء الاصطناعي لمكتب: {tenant.name}', 'success')
        else:
            flash('الذكاء الاصطناعي مفعّل بالفعل لهذا المكتب', 'info')

    else:
        flash('قيمة intent غير صحيحة', 'danger')

    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))
