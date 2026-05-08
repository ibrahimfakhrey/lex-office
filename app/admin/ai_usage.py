"""Admin dashboard for AI usage governance.

Routes:
  GET  /admin/ai-usage              — list all tenants with usage bars
  GET  /admin/ai-usage/<tenant_id>  — drill-down: events log + per-feature

Permissions reuse the existing 'tenants' RBAC module — anyone who can view
tenants can view AI usage. Same for edit (admins who can edit a tenant can
toggle their AI feature override at /admin/tenants/<id>/features).
"""
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, abort
from sqlalchemy import func, or_

from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import admin_permission_required
from app.admin.feature_utils import tenant_has_feature, tenant_feature_limit
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.models.ai_usage import AIUsageEvent
from app.services import ai_usage as ai_usage_svc


@admin_bp.route('/ai-usage')
@admin_permission_required('tenants', 'view')
def ai_usage_list():
    """List tenants with AI usage stats this month. Filter + sort options."""
    market = (request.args.get('market') or '').strip().lower()
    filter_kind = (request.args.get('filter') or '').strip()  # high | disabled | empty
    sort = (request.args.get('sort') or 'usage_desc').strip()

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    # Base query — all tenants
    query = Tenant.query
    if market in ('eg', 'sa'):
        query = query.filter_by(market=market)
    tenants = query.order_by(Tenant.name).all()

    # Bulk-load this month's usage per tenant in one round-trip
    rows = (
        db.session.query(
            AIUsageEvent.tenant_id,
            func.count(AIUsageEvent.id).label('count'),
            func.coalesce(func.sum(AIUsageEvent.cost_usd), 0).label('cost'),
        )
        .filter(AIUsageEvent.created_at >= month_start,
                AIUsageEvent.success.is_(True))
        .group_by(AIUsageEvent.tenant_id)
        .all()
    )
    usage_map = {r.tenant_id: (r.count, float(r.cost)) for r in rows}

    enriched = []
    for t in tenants:
        used, cost = usage_map.get(t.id, (0, 0.0))
        limit = tenant_feature_limit(t, 'ai_calls_per_month', default=0) or 0
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 0
        enabled = bool(tenant_has_feature(t, 'ai_enabled', default=False))
        if limit < 0:
            pct = 0.0
            unlimited = True
        elif limit == 0:
            pct = 100.0 if used > 0 else 0.0
            unlimited = False
        else:
            pct = round(100.0 * used / limit, 1)
            unlimited = False

        enriched.append({
            'tenant': t,
            'enabled': enabled,
            'used': used,
            'limit': limit,
            'unlimited': unlimited,
            'percent': pct,
            'cost_usd': cost,
        })

    # Filter
    if filter_kind == 'high':
        enriched = [e for e in enriched if not e['unlimited'] and e['percent'] >= 80]
    elif filter_kind == 'disabled':
        enriched = [e for e in enriched if not e['enabled']]
    elif filter_kind == 'active':
        enriched = [e for e in enriched if e['used'] > 0]

    # Sort
    if sort == 'usage_desc':
        enriched.sort(key=lambda e: e['used'], reverse=True)
    elif sort == 'percent_desc':
        enriched.sort(key=lambda e: e['percent'], reverse=True)
    elif sort == 'cost_desc':
        enriched.sort(key=lambda e: e['cost_usd'], reverse=True)
    elif sort == 'name':
        enriched.sort(key=lambda e: e['tenant'].name or '')

    # Aggregates for the header strip
    totals = {
        'tenant_count': len(enriched),
        'active_tenants': sum(1 for e in enriched if e['used'] > 0),
        'total_calls': sum(e['used'] for e in enriched),
        'total_cost_usd': sum(e['cost_usd'] for e in enriched),
        'over_80pct': sum(1 for e in enriched if not e['unlimited'] and e['percent'] >= 80),
        'disabled': sum(1 for e in enriched if not e['enabled']),
    }

    return render_template(
        'admin/ai_usage/list.html',
        rows=enriched,
        totals=totals,
        filter_market=market,
        filter_kind=filter_kind,
        sort=sort,
        month_label=now.strftime('%Y-%m'),
    )


@admin_bp.route('/ai-usage/<int:tenant_id>')
@admin_permission_required('tenants', 'view')
def ai_usage_detail(tenant_id):
    """Per-tenant usage detail: summary, per-feature breakdown, event log."""
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        abort(404)

    summary = ai_usage_svc.usage_summary_for_tenant(tenant)

    # Last 100 events, newest first
    events = (
        AIUsageEvent.query
        .filter_by(tenant_id=tenant_id)
        .order_by(AIUsageEvent.created_at.desc())
        .limit(100)
        .all()
    )

    return render_template(
        'admin/ai_usage/detail.html',
        tenant=tenant,
        summary=summary,
        events=events,
    )
