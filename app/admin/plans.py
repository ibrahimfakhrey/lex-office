"""Plans management — CRUD + archive."""
from flask import (
    render_template, request, redirect, url_for, flash, abort,
)
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action, admin_permission_required
from app.admin.feature_keys import ALL_FEATURES, BOOLEAN_FEATURES, LIMIT_FEATURES, features_by_group, GROUPS
from app.models.subscription import SubscriptionPlan
from app.models.tenant import Tenant


def _plan_or_404(plan_id):
    p = SubscriptionPlan.query.get(plan_id)
    if not p:
        abort(404)
    return p


def _tenant_count(plan_id):
    return Tenant.query.filter_by(subscription_plan_id=plan_id).count()


# ───────────────────────────── list ─────────────────────────────

@admin_bp.route('/plans')
@admin_permission_required('plans', 'view')
def plans_list():
    """List all plans with tenant counts. Filter by market via ?market=eg|sa."""
    market = (request.args.get('market') or '').strip().lower()
    query = SubscriptionPlan.query
    if market in ('eg', 'sa'):
        query = query.filter_by(market=market)
    plans = query.order_by(
        SubscriptionPlan.market.asc(),
        SubscriptionPlan.price_monthly.asc(),
    ).all()
    counts = {p.id: _tenant_count(p.id) for p in plans}
    return render_template('admin/plans/list.html', plans=plans, counts=counts,
                           filter_market=market)


# ───────────────────────────── create ─────────────────────────────

@admin_bp.route('/plans/create', methods=['GET', 'POST'])
@admin_permission_required('plans', 'add')
def plans_create():
    """Create a new plan."""
    from app.utils.market_config import (
        normalize_market, get_config, PLAN_COMPARISON_ROWS, SUPPORTED_MARKETS,
    )
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        name_ar = (request.form.get('name_ar') or '').strip()
        market = normalize_market(request.form.get('market'))
        if not name or not name_ar:
            flash('الاسم مطلوب', 'danger')
            return render_template('admin/plans/form.html', plan=None,
                                   features_by_group=features_by_group(), groups=GROUPS,
                                   comparison_rows=PLAN_COMPARISON_ROWS,
                                   markets=SUPPORTED_MARKETS, form=request.form)

        # (name, market) is the natural key — same name allowed across markets.
        existing = SubscriptionPlan.query.filter_by(name=name, market=market).first()
        if existing:
            flash(f'اسم الخطة "{name}" مستخدم بالفعل في سوق {market.upper()}', 'danger')
            return render_template('admin/plans/form.html', plan=None,
                                   features_by_group=features_by_group(), groups=GROUPS,
                                   comparison_rows=PLAN_COMPARISON_ROWS,
                                   markets=SUPPORTED_MARKETS, form=request.form)

        currency = (request.form.get('currency_code') or get_config(market)['currency_code']).upper()
        plan = SubscriptionPlan(
            name=name,
            name_ar=name_ar,
            description=(request.form.get('description') or '').strip() or None,
            max_lawyers=request.form.get('max_lawyers', type=int) or 1,
            max_storage_gb=request.form.get('max_storage_gb', type=int),
            price_monthly=request.form.get('price_monthly', type=float) or 0,
            price_yearly=request.form.get('price_yearly', type=float) or 0,
            status=request.form.get('status', 'active'),
            is_public=request.form.get('is_public') == 'on',
            self_service=request.form.get('self_service') == 'on',
            market=market,
            currency_code=currency,
            comparison=_build_comparison_from_form(request.form),
            is_active=True,
            created_by_admin_id=g.current_admin.id,
        )
        plan.features = _build_features_from_form(request.form)
        db.session.add(plan)
        db.session.flush()

        log_action(
            'PLAN_CREATED', entity_type='Plan', entity_id=plan.id,
            new_value=plan.to_dict(),
            description=f'Created plan {plan.name}',
        )
        db.session.commit()
        flash(f'تم إنشاء الخطة: {plan.name_ar}', 'success')
        return redirect(url_for('admin.plans_list'))

    return render_template('admin/plans/form.html', plan=None,
                           features_by_group=features_by_group(), groups=GROUPS,
                           comparison_rows=PLAN_COMPARISON_ROWS,
                           markets=SUPPORTED_MARKETS, form={})


# ───────────────────────────── edit ─────────────────────────────

@admin_bp.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@admin_permission_required('plans', 'edit')
def plans_edit(plan_id):
    """Edit an existing plan."""
    from app.utils.market_config import (
        normalize_market, PLAN_COMPARISON_ROWS, SUPPORTED_MARKETS,
    )
    plan = _plan_or_404(plan_id)
    tenant_count = _tenant_count(plan_id)

    if request.method == 'POST':
        old = plan.to_dict()
        plan.name = (request.form.get('name') or plan.name).strip()
        plan.name_ar = (request.form.get('name_ar') or plan.name_ar).strip()
        plan.description = (request.form.get('description') or '').strip() or None
        plan.max_lawyers = request.form.get('max_lawyers', type=int) or 1
        plan.max_storage_gb = request.form.get('max_storage_gb', type=int)
        plan.price_monthly = request.form.get('price_monthly', type=float) or 0
        plan.price_yearly = request.form.get('price_yearly', type=float) or 0
        plan.status = request.form.get('status', plan.status)
        plan.is_public = request.form.get('is_public') == 'on'
        plan.self_service = request.form.get('self_service') == 'on'
        # Market and currency are editable but warn if any tenants are attached.
        new_market = normalize_market(request.form.get('market') or plan.market)
        new_currency = (request.form.get('currency_code') or plan.currency_code or 'EGP').upper()
        if (new_market != plan.market or new_currency != plan.currency_code) and tenant_count > 0:
            flash(f'تنبيه: تم تغيير السوق/العملة على خطة عليها {tenant_count} مكتب — تأكد من التأثير', 'warning')
        plan.market = new_market
        plan.currency_code = new_currency
        plan.features = _build_features_from_form(request.form)
        plan.comparison = _build_comparison_from_form(request.form)

        log_action(
            'PLAN_UPDATED', entity_type='Plan', entity_id=plan.id,
            old_value=old, new_value=plan.to_dict(),
            description=f'Updated plan {plan.name}',
        )
        db.session.commit()
        flash(f'تم تحديث الخطة: {plan.name_ar}', 'success')
        return redirect(url_for('admin.plans_list'))

    # Build form values from existing plan
    form = {
        'name': plan.name, 'name_ar': plan.name_ar,
        'description': plan.description or '',
        'max_lawyers': plan.max_lawyers, 'max_storage_gb': plan.max_storage_gb or '',
        'price_monthly': plan.price_monthly, 'price_yearly': plan.price_yearly,
        'status': plan.status, 'is_public': plan.is_public, 'self_service': plan.self_service,
        'market': plan.market, 'currency_code': plan.currency_code,
    }
    return render_template('admin/plans/form.html', plan=plan, tenant_count=tenant_count,
                           features_by_group=features_by_group(), groups=GROUPS,
                           comparison_rows=PLAN_COMPARISON_ROWS,
                           markets=SUPPORTED_MARKETS, form=form)


# ───────────────────────────── archive / delete ─────────────────────────────

@admin_bp.route('/plans/<int:plan_id>/archive', methods=['POST'])
@admin_permission_required('plans', 'delete')
def plans_archive(plan_id):
    """Archive a plan (existing tenants keep it, no new signups)."""
    plan = _plan_or_404(plan_id)
    old = plan.to_dict()
    plan.status = 'archived'
    plan.is_public = False
    plan.self_service = False

    log_action(
        'PLAN_ARCHIVED', entity_type='Plan', entity_id=plan.id,
        old_value=old, new_value=plan.to_dict(),
        description=f'Archived plan {plan.name}',
    )
    db.session.commit()
    flash(f'تم أرشفة الخطة: {plan.name_ar}', 'warning')
    return redirect(url_for('admin.plans_list'))


@admin_bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@admin_permission_required('plans', 'delete')
def plans_delete(plan_id):
    """Delete plan — only allowed if Draft AND zero tenants."""
    plan = _plan_or_404(plan_id)
    if _tenant_count(plan_id) > 0:
        flash('لا يمكن حذف خطة عليها مكاتب نشطة. قم بأرشفتها بدلاً من ذلك', 'danger')
        return redirect(url_for('admin.plans_list'))
    if plan.status != 'draft':
        flash('الحذف الكامل متاح فقط للخطط في وضع المسودة (Draft)', 'danger')
        return redirect(url_for('admin.plans_list'))

    log_action(
        'PLAN_DELETED', entity_type='Plan', entity_id=plan.id,
        old_value=plan.to_dict(),
        description=f'Deleted draft plan {plan.name}',
    )
    db.session.delete(plan)
    db.session.commit()
    flash(f'تم حذف الخطة: {plan.name_ar}', 'danger')
    return redirect(url_for('admin.plans_list'))


# ───────────────────────────── helpers ─────────────────────────────

def _build_features_from_form(form):
    """Read feature flags from POSTed form into a JSON dict."""
    features = {}

    # Boolean features
    for f in BOOLEAN_FEATURES:
        key = f['key']
        # checkbox: present = True, absent = False
        features[key] = form.get(f'feature_{key}') == 'on'

    # Numeric limits — store as int (-1 = unlimited)
    for f in LIMIT_FEATURES:
        key = f['key']
        val = form.get(f'feature_{key}', type=int)
        if val is not None:
            features[key] = val

    return features


def _build_comparison_from_form(form):
    """Read the per-cell comparison-row content from the form into a JSON dict.

    Each row in app/utils/market_config.PLAN_COMPARISON_ROWS produces one
    `comparison_<key>_value` text input plus a `comparison_<key>_kind` selector
    (auto / yes / no / text). 'auto'+empty text means leave the key unset.
    """
    from app.utils.market_config import PLAN_COMPARISON_ROWS
    out = {}
    for row in PLAN_COMPARISON_ROWS:
        key = row['key']
        kind = (form.get(f'comparison_{key}_kind') or 'text').strip()
        text = (form.get(f'comparison_{key}_value') or '').strip()
        if kind == 'yes':
            out[key] = True
        elif kind == 'no':
            out[key] = False
        elif kind == 'text':
            if text:
                out[key] = text
            # else: leave unset → renders as ✗
        # 'auto' / unknown → skip
    return out


# ───────────────────────────── duplicate to other market ─────────────────────

@admin_bp.route('/plans/<int:plan_id>/duplicate', methods=['POST'])
@admin_permission_required('plans', 'add')
def plans_duplicate(plan_id):
    """Clone a plan into the other market (eg ↔ sa).

    Convenience action: SA prices default to the source plan's monthly price
    (admin edits afterwards). Skips if a plan with the same (name, target market)
    already exists.
    """
    from app.utils.market_config import get_config, SUPPORTED_MARKETS
    src = _plan_or_404(plan_id)
    target = (request.form.get('target_market') or '').strip().lower()
    if target not in SUPPORTED_MARKETS or target == src.market:
        flash('سوق الهدف غير صالح', 'danger')
        return redirect(url_for('admin.plans_list'))

    if SubscriptionPlan.query.filter_by(name=src.name, market=target).first():
        flash(f'الخطة "{src.name}" موجودة بالفعل في سوق {target.upper()}', 'warning')
        return redirect(url_for('admin.plans_list', market=target))

    clone = SubscriptionPlan(
        name=src.name, name_ar=src.name_ar, description=src.description,
        max_lawyers=src.max_lawyers, max_storage_gb=src.max_storage_gb,
        price_monthly=src.price_monthly, price_yearly=src.price_yearly,
        status='draft', is_public=False, self_service=False, is_active=True,
        market=target, currency_code=get_config(target)['currency_code'],
        features=dict(src.features) if src.features else None,
        comparison=dict(src.comparison) if src.comparison else None,
        created_by_admin_id=g.current_admin.id,
    )
    db.session.add(clone)
    db.session.flush()
    log_action(
        'PLAN_DUPLICATED', entity_type='Plan', entity_id=clone.id,
        old_value={'source_plan_id': src.id, 'source_market': src.market},
        new_value=clone.to_dict(),
        description=f'Duplicated plan {src.name} from {src.market} to {target}',
    )
    db.session.commit()
    flash(f'تم نسخ الخطة إلى سوق {target.upper()} كمسودة — راجع الأسعار قبل التفعيل', 'success')
    return redirect(url_for('admin.plans_edit', plan_id=clone.id))
