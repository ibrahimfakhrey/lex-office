"""Super-admin view of T&C + Privacy acceptances.

A read-only listing across all tenants:
- One row per acceptance record.
- Status badge: ✅ Current (version matches SystemSetting.terms_version)
                ⚠️ Outdated (older version).
- Filter by tenant + status.
- Expandable IP + user_agent cells (rendered as `<details>`).

Notification of NEW acceptances is left to Phase M6 (admin notif stream).
"""
from flask import render_template, request

from app.admin import admin_bp
from app.admin.decorators import admin_permission_required
from app.models.admin import SystemSetting
from app.models.terms_acceptance import TermsAcceptance
from app.models.user import User
from app.models.tenant import Tenant


@admin_bp.route('/terms-acceptances')
@admin_permission_required('audit_log', 'view')
def terms_acceptances():
    """List all T&C acceptances with filters."""
    page = request.args.get('page', 1, type=int)
    tenant_id = request.args.get('tenant_id', type=int)
    status = (request.args.get('status') or '').strip()

    current_version = SystemSetting.get('terms_version', '1.0') or '1.0'

    q = (TermsAcceptance.query
         .join(User, TermsAcceptance.user_id == User.id)
         .join(Tenant, TermsAcceptance.tenant_id == Tenant.id))

    if tenant_id:
        q = q.filter(TermsAcceptance.tenant_id == tenant_id)
    if status == 'current':
        q = q.filter(TermsAcceptance.version == current_version)
    elif status == 'outdated':
        q = q.filter(TermsAcceptance.version != current_version)

    q = q.order_by(TermsAcceptance.accepted_at.desc())
    pagination = q.paginate(page=page, per_page=30)

    # Tenants list for the filter dropdown
    tenants = Tenant.query.order_by(Tenant.name).all()

    return render_template(
        'admin/terms/list.html',
        pagination=pagination,
        current_version=current_version,
        tenants=tenants,
        sel_tenant_id=tenant_id,
        sel_status=status,
    )
