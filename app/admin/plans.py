"""Plans management — CRUD + archive."""
from flask import (
    render_template, request, redirect, url_for, flash, abort,
)
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action
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
@super_admin_required
def plans_list():
    """List all plans with tenant counts."""
    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.price_monthly.asc()).all()
    counts = {p.id: _tenant_count(p.id) for p in plans}
    return render_template('admin/plans/list.html', plans=plans, counts=counts)


# ───────────────────────────── create ─────────────────────────────

@admin_bp.route('/plans/create', methods=['GET', 'POST'])
@super_admin_required
def plans_create():
    """Create a new plan."""
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        name_ar = (request.form.get('name_ar') or '').strip()
        if not name or not name_ar:
            flash('الاسم مطلوب', 'danger')
            return render_template('admin/plans/form.html', plan=None,
                                   features_by_group=features_by_group(), groups=GROUPS, form=request.form)

        existing = SubscriptionPlan.query.filter_by(name=name).first()
        if existing:
            flash('اسم الخطة مستخدم بالفعل', 'danger')
            return render_template('admin/plans/form.html', plan=None,
                                   features_by_group=features_by_group(), groups=GROUPS, form=request.form)

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
            is_active=True,
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
                           features_by_group=features_by_group(), groups=GROUPS, form={})


# ───────────────────────────── edit ─────────────────────────────

@admin_bp.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def plans_edit(plan_id):
    """Edit an existing plan."""
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
        plan.features = _build_features_from_form(request.form)

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
    }
    return render_template('admin/plans/form.html', plan=plan, tenant_count=tenant_count,
                           features_by_group=features_by_group(), groups=GROUPS, form=form)


# ───────────────────────────── archive / delete ─────────────────────────────

@admin_bp.route('/plans/<int:plan_id>/archive', methods=['POST'])
@super_admin_required
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
@super_admin_required
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
