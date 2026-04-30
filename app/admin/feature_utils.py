"""Feature entitlement resolution.

Order of precedence:
  1. Tenant-level override (if not expired) — wins always
  2. Plan-level feature flag
  3. Default (False / None)

Use `tenant_has_feature(tenant, key)` from anywhere in the app to check if a
tenant should be granted a particular feature.
"""
from datetime import datetime
from app.models.admin import TenantFeatureOverride


def tenant_has_feature(tenant, key, default=False):
    """Return True/False or numeric value for a feature on this tenant."""
    if tenant is None:
        return default

    # 1. Check override
    override = TenantFeatureOverride.query.filter_by(
        tenant_id=tenant.id, feature_key=key
    ).first()
    if override and (override.expires_at is None or override.expires_at > datetime.utcnow()):
        return override.enabled

    # 2. Check plan
    if tenant.subscription_plan and tenant.subscription_plan.features:
        val = tenant.subscription_plan.features.get(key)
        if val is not None:
            return val

    return default


def tenant_feature_limit(tenant, key, default=None):
    """Return the numeric limit for a quantity feature (e.g. max_cases)."""
    if tenant is None:
        return default

    override = TenantFeatureOverride.query.filter_by(
        tenant_id=tenant.id, feature_key=key
    ).first()
    if override and (override.expires_at is None or override.expires_at > datetime.utcnow()):
        # Overrides for limits are stored in `enabled` field as bool, but if the
        # admin sets a numeric limit it would go in plan flags. For now return
        # plan limit unchanged.
        pass

    if tenant.subscription_plan and tenant.subscription_plan.features:
        val = tenant.subscription_plan.features.get(key)
        if val is not None:
            return val
    return default
