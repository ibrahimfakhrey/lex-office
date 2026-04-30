"""Feature flags matrix — cross-plan view."""
from flask import render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.admin import admin_bp
from app.admin.decorators import super_admin_required, log_action
from app.admin.feature_keys import ALL_FEATURES, BOOLEAN_FEATURES, LIMIT_FEATURES, features_by_group, GROUPS
from app.models.subscription import SubscriptionPlan


@admin_bp.route('/features')
@super_admin_required
def features_matrix():
    """Show all features × all plans in one matrix."""
    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.price_monthly.asc()).all()

    # Build grid: feature_key → {plan_id: value}
    grid = {}
    for f in ALL_FEATURES:
        row = {'feature': f, 'cells': {}}
        for p in plans:
            features = (p.features or {})
            row['cells'][p.id] = features.get(f['key'])
        grid[f['key']] = row

    return render_template(
        'admin/plans/matrix.html',
        plans=plans, grid=grid,
        features_by_group=features_by_group(), groups=GROUPS,
    )


@admin_bp.route('/features/plan/<int:plan_id>/toggle', methods=['POST'])
@super_admin_required
def feature_toggle(plan_id):
    """Toggle a single boolean feature on a plan, AJAX-friendly."""
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    key = (request.form.get('key') or '').strip()
    enabled = request.form.get('enabled') == '1'
    if not key:
        return jsonify({'success': False, 'error': 'Missing key'}), 400

    features = dict(plan.features or {})
    old_val = features.get(key)
    features[key] = enabled
    plan.features = features

    log_action(
        'FEATURE_TOGGLED', entity_type='Plan', entity_id=plan_id,
        old_value={key: old_val}, new_value={key: enabled},
        description=f'Toggled {key} = {enabled} on plan {plan.name}',
    )
    db.session.commit()
    return jsonify({'success': True, 'plan_id': plan_id, 'key': key, 'enabled': enabled})


@admin_bp.route('/features/plan/<int:plan_id>/limit', methods=['POST'])
@super_admin_required
def feature_limit(plan_id):
    """Set numeric quantity limit (e.g. max_cases=50) on a plan."""
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    key = (request.form.get('key') or '').strip()
    value = request.form.get('value', type=int)
    if not key:
        flash('مفتاح الميزة مطلوب', 'danger')
        return redirect(url_for('admin.features_matrix'))

    features = dict(plan.features or {})
    old_val = features.get(key)
    features[key] = value
    plan.features = features

    log_action(
        'FEATURE_LIMIT_SET', entity_type='Plan', entity_id=plan_id,
        old_value={key: old_val}, new_value={key: value},
        description=f'Set limit {key} = {value} on plan {plan.name}',
    )
    db.session.commit()
    flash(f'تم تحديث {key} للخطة {plan.name_ar}', 'success')
    return redirect(url_for('admin.features_matrix'))
