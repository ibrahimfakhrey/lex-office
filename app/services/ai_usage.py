"""AI usage governance: per-tenant entitlement, quota enforcement, recording.

Every AI call goes through this module:

    from app.services import ai_usage
    ai_usage.check_can_use(tenant)            # raises QuotaError on block
    response = call_claude(...)               # actual API call
    ai_usage.record(tenant, user, feature='judgment_extract',
                    model='claude-haiku-4-5', response=response, success=True)

The check happens BEFORE the API call so we never spend tokens for a
blocked tenant. The record happens AFTER so we have real token counts
from the response — never hand-estimated.
"""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func

from app.extensions import db
from app.admin.feature_utils import tenant_has_feature, tenant_feature_limit
from app.models.ai_usage import AIUsageEvent
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────
# Source: shared/models.md in the claude-api skill (cached 2026-04-15).
# Updates here apply only to NEW events; historical rows keep their cost.

PRICING = {
    'claude-haiku-4-5':   (Decimal('1.00'),  Decimal('5.00')),
    'claude-sonnet-4-6':  (Decimal('3.00'),  Decimal('15.00')),
    'claude-opus-4-7':    (Decimal('5.00'),  Decimal('25.00')),
    'claude-opus-4-6':    (Decimal('5.00'),  Decimal('25.00')),
}
# Fallback if model unknown — prefer the most expensive so we don't under-bill.
_FALLBACK_PRICE = (Decimal('5.00'), Decimal('25.00'))

# Cache write costs 1.25× input rate; cache read costs 0.10× input rate.
_CACHE_WRITE_MULTIPLIER = Decimal('1.25')
_CACHE_READ_MULTIPLIER = Decimal('0.10')


# ── Feature registry ──────────────────────────────────────────────────────────
# Single source of truth for every AI feature in the app. New features add
# themselves here; the admin's plan-edit form auto-includes them. Absence of
# a feature in plan.features.ai_features defaults to "enabled, no per-feature
# cap" — backwards compatible with plans seeded before this registry existed.

KNOWN_AI_FEATURES = [
    {
        'key': 'judgment_extract',
        'label_ar': 'تحليل الأحكام (PDF/DOCX)',
        'description_ar': 'استخراج بيانات الحكم تلقائياً من ملف PDF أو DOCX',
    },
    # Add new features here as they ship. The admin form re-renders automatically.
    # {'key': 'poa_extract', 'label_ar': 'استخراج التوكيلات', 'description_ar': '...'},
    # {'key': 'document_qa', 'label_ar': 'الإجابة على المستندات', 'description_ar': '...'},
    # {'key': 'session_minutes', 'label_ar': 'تنظيم محاضر الجلسات', 'description_ar': '...'},
]

_KNOWN_FEATURE_KEYS = {f['key'] for f in KNOWN_AI_FEATURES}


def feature_label(key: str) -> str:
    """Human-readable Arabic label for a feature key."""
    for f in KNOWN_AI_FEATURES:
        if f['key'] == key:
            return f['label_ar']
    return key


# ── Errors ────────────────────────────────────────────────────────────────────

class QuotaError(Exception):
    """Base class — message is Arabic, safe to surface to the user."""


class AIDisabledError(QuotaError):
    """AI is disabled for this tenant (plan-level or admin override)."""


class FeatureDisabledError(QuotaError):
    """Master AI is on, but THIS specific feature is disabled in the plan."""


class QuotaExceededError(QuotaError):
    """Umbrella monthly cap reached (across all features)."""


class FeatureQuotaExceededError(QuotaError):
    """Per-feature monthly cap reached, even though umbrella has room."""


# ── Quota helpers ─────────────────────────────────────────────────────────────

def is_ai_enabled(tenant: Tenant) -> bool:
    """True if the tenant's plan grants AI AND no admin override disables it.

    This is the **master kill switch** — checked before any per-feature flag.
    """
    if tenant is None:
        return False
    return bool(tenant_has_feature(tenant, 'ai_enabled', default=False))


def _plan_features(tenant: Tenant) -> dict:
    """Plan features dict, defaulting to {} if no plan or no features set."""
    plan = getattr(tenant, 'subscription_plan', None) if tenant else None
    return (plan.features or {}) if plan else {}


def get_feature_config(tenant: Tenant, feature_key: str) -> dict:
    """Return {'enabled': bool, 'monthly_cap': int|None} for a specific feature.

    Resolution order:
      1. plan.features.ai_features.<key> if present
      2. otherwise default: enabled=True, monthly_cap=None (uses umbrella cap)

    A feature absent from the map is implicitly enabled — we don't want to
    silently disable existing features when adding new ones to the registry.
    """
    ai_features_map = _plan_features(tenant).get('ai_features') or {}
    cfg = ai_features_map.get(feature_key) or {}
    enabled = cfg.get('enabled', True)
    cap_raw = cfg.get('monthly_cap')
    if cap_raw is None:
        cap = None
    else:
        try:
            cap_int = int(cap_raw)
            cap = None if cap_int < 0 else cap_int
        except (TypeError, ValueError):
            cap = None
    return {'enabled': bool(enabled), 'monthly_cap': cap}


def is_feature_enabled(tenant: Tenant, feature_key: str) -> bool:
    """Combined check: master AI on AND this feature not explicitly disabled."""
    if not is_ai_enabled(tenant):
        return False
    return get_feature_config(tenant, feature_key)['enabled']


def get_quota(tenant: Tenant, feature_key: Optional[str] = None) -> Tuple[int, int]:
    """Return (used, limit) for the umbrella cap, or for a specific feature.

    When `feature_key` is None → umbrella numbers from `ai_calls_per_month`.
    When `feature_key` is given → per-feature numbers from `ai_features.<key>.monthly_cap`,
    falling back to umbrella if no per-feature cap is set.

    Limit -1 (or None / unset) means unlimited — caller treats it as "no cap".
    Successful events only — failed calls don't burn the quota, otherwise an
    upstream Anthropic outage would exhaust the tenant's cap.
    """
    used = _count_used_this_month(tenant, feature=feature_key)

    if feature_key is None:
        limit_raw = tenant_feature_limit(tenant, 'ai_calls_per_month', default=0) or 0
    else:
        cfg = get_feature_config(tenant, feature_key)
        if cfg['monthly_cap'] is None:
            # No per-feature cap set; reuse umbrella as the effective cap so
            # callers see consistent (used, limit) pairs.
            limit_raw = tenant_feature_limit(tenant, 'ai_calls_per_month', default=0) or 0
        else:
            limit_raw = cfg['monthly_cap']

    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 0
    return used, limit


def _count_used_this_month(tenant: Tenant, feature: Optional[str] = None) -> int:
    if tenant is None:
        return 0
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    q = (
        db.session.query(func.count(AIUsageEvent.id))
        .filter(
            AIUsageEvent.tenant_id == tenant.id,
            AIUsageEvent.created_at >= month_start,
            AIUsageEvent.success.is_(True),
        )
    )
    if feature:
        q = q.filter(AIUsageEvent.feature == feature)
    return q.scalar() or 0


def check_can_use(tenant: Tenant, feature_key: str) -> None:
    """Raise QuotaError if the tenant cannot make this specific AI call.

    Resolution order, each raising a distinct exception:
      1. Master AI off (plan flag or admin override) → AIDisabledError
      2. This feature explicitly disabled in plan      → FeatureDisabledError
      3. Per-feature cap exhausted (if cap set)        → FeatureQuotaExceededError
      4. Umbrella monthly cap exhausted                → QuotaExceededError

    All errors carry Arabic, user-safe messages.
    """
    # 1. Master kill switch
    if not is_ai_enabled(tenant):
        from app.models.admin import TenantFeatureOverride
        override = TenantFeatureOverride.query.filter_by(
            tenant_id=tenant.id, feature_key='ai_enabled',
        ).first()
        if override is not None and not override.enabled:
            raise AIDisabledError(
                'خاصية الذكاء الاصطناعي معطّلة لمكتبك حالياً — '
                'يرجى التواصل مع الإدارة'
            )
        raise AIDisabledError(
            'خطتك الحالية لا تشمل الذكاء الاصطناعي — '
            'ترقّ إلى خطة أعلى للاستفادة من هذه الميزة'
        )

    # 2. Per-feature on/off
    feature_cfg = get_feature_config(tenant, feature_key)
    if not feature_cfg['enabled']:
        label = feature_label(feature_key)
        raise FeatureDisabledError(
            f'ميزة "{label}" غير مفعّلة في خطتك الحالية — '
            f'ترقّ إلى خطة أعلى أو تواصل مع الإدارة'
        )

    # 3. Per-feature cap (if set)
    if feature_cfg['monthly_cap'] is not None:
        used_feature = _count_used_this_month(tenant, feature=feature_key)
        cap = feature_cfg['monthly_cap']
        if used_feature >= cap:
            label = feature_label(feature_key)
            raise FeatureQuotaExceededError(
                f'وصلت إلى الحد الأقصى لاستخدام "{label}" هذا الشهر '
                f'({used_feature} من {cap}) — يتجدد أول الشهر القادم'
            )

    # 4. Umbrella cap
    used, limit = get_quota(tenant)
    if limit < 0 or limit == 0:
        return  # unlimited
    if used >= limit:
        raise QuotaExceededError(
            f'وصلت إلى الحد الأقصى لاستخدام الذكاء الاصطناعي هذا الشهر '
            f'({used} من {limit}) — يتجدد أول الشهر القادم، أو رقّ خطتك للحصول '
            f'على حد أكبر'
        )


# ── Cost computation ──────────────────────────────────────────────────────────

def compute_cost_usd(model: str, usage) -> Decimal:
    """Compute the USD cost of a single Claude response.

    `usage` is the SDK's response.usage object (has input_tokens,
    output_tokens, cache_creation_input_tokens, cache_read_input_tokens).
    """
    input_rate, output_rate = PRICING.get(model, _FALLBACK_PRICE)
    per_million = Decimal('1000000')

    input_tokens = Decimal(getattr(usage, 'input_tokens', 0) or 0)
    output_tokens = Decimal(getattr(usage, 'output_tokens', 0) or 0)
    cache_create = Decimal(getattr(usage, 'cache_creation_input_tokens', 0) or 0)
    cache_read = Decimal(getattr(usage, 'cache_read_input_tokens', 0) or 0)

    cost = (input_tokens * input_rate / per_million)
    cost += (output_tokens * output_rate / per_million)
    cost += (cache_create * input_rate * _CACHE_WRITE_MULTIPLIER / per_million)
    cost += (cache_read * input_rate * _CACHE_READ_MULTIPLIER / per_million)
    # Round to 6 decimals (matches DB column scale)
    return cost.quantize(Decimal('0.000001'))


# ── Recording ─────────────────────────────────────────────────────────────────

def record(tenant: Tenant, user, feature: str, model: str, response=None,
           success: bool = True, error: Optional[str] = None) -> AIUsageEvent:
    """Persist a usage event row. Always returns the persisted event.

    For failed calls (success=False) `response` may be None and the row is
    written with zero token counts so the admin can still see the failure
    without billing the tenant for it.
    """
    if response is not None and getattr(response, 'usage', None) is not None:
        usage = response.usage
        input_tokens = getattr(usage, 'input_tokens', 0) or 0
        output_tokens = getattr(usage, 'output_tokens', 0) or 0
        cache_create = getattr(usage, 'cache_creation_input_tokens', 0) or 0
        cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
        cost = compute_cost_usd(model, usage) if success else Decimal('0')
    else:
        input_tokens = output_tokens = cache_create = cache_read = 0
        cost = Decimal('0')

    event = AIUsageEvent(
        tenant_id=tenant.id,
        user_id=user.id if user is not None else None,
        feature=feature,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_create,
        cache_read_input_tokens=cache_read,
        cost_usd=cost,
        success=success,
        error_message=(error[:500] if error else None),
    )
    db.session.add(event)
    db.session.flush()

    # Soft-warning email at 80% — fire-and-forget; never let email failures
    # break the AI call path.
    if success:
        try:
            _maybe_send_warning_email(tenant)
        except Exception:
            logger.exception('AI quota warning email failed for tenant %s', tenant.id)

    return event


# ── 80% warning email ─────────────────────────────────────────────────────────

def _maybe_send_warning_email(tenant: Tenant) -> None:
    """Send the office manager a heads-up when the tenant first crosses 80%
    in the current calendar month. Idempotent — uses
    `tenant.ai_warning_sent_month` to dedupe.
    """
    used, limit = get_quota(tenant)
    if limit <= 0:
        return  # unlimited or disabled — never warn
    pct = used / limit
    if pct < 0.80:
        return

    current_month = datetime.utcnow().strftime('%Y-%m')
    if tenant.ai_warning_sent_month == current_month:
        return  # already warned this month

    # Find the office manager (first user with role.name='manager').
    from app.models.user import User, Role
    manager = (
        User.query
        .join(Role)
        .filter(User.tenant_id == tenant.id, Role.name == 'manager',
                User.is_active.is_(True))
        .first()
    )
    if manager is None or not manager.email:
        # No manager email known — mark as sent so we don't try every call.
        tenant.ai_warning_sent_month = current_month
        return

    from app.services.email_service import send_email
    subject = f'تنبيه: تجاوزت 80% من حصة الذكاء الاصطناعي ({used}/{limit})'
    body_html = (
        f'<div style="font-family: Tahoma, sans-serif; direction: rtl; text-align: right;">'
        f'<p>السلام عليكم {manager.full_name},</p>'
        f'<p>وصل استخدام مكتبكم <strong>{tenant.name}</strong> لميزة الذكاء '
        f'الاصطناعي إلى <strong>{used} من {limit}</strong> طلباً '
        f'({int(pct * 100)}%) لهذا الشهر.</p>'
        f'<p>سيتم إيقاف استخدام الميزة تلقائياً عند الوصول إلى الحد الأقصى. '
        f'يمكنكم ترقية الخطة في أي وقت من إعدادات الاشتراك.</p>'
        f'<p>تتجدد الحصة تلقائياً في أول كل شهر ميلادي.</p>'
        f'<hr><small>LexOffice — منظومة إدارة مكاتب المحاماة</small></div>'
    )
    try:
        send_email(to=manager.email, subject=subject, html_body=body_html)
        logger.info('Sent AI quota 80%% warning to tenant %s manager %s',
                    tenant.id, manager.email)
    except Exception:
        logger.exception('Failed to send AI quota warning email')
    finally:
        # Mark as sent regardless of email outcome — better to skip a retry
        # than to spam the manager with one warning per call.
        tenant.ai_warning_sent_month = current_month


# ── Aggregation helpers (used by admin dashboard) ─────────────────────────────

def usage_summary_for_tenant(tenant: Tenant) -> dict:
    """Aggregate stats for the admin per-tenant detail page."""
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    used, limit = get_quota(tenant)

    # Cost this month
    month_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageEvent.cost_usd), 0))
        .filter(AIUsageEvent.tenant_id == tenant.id,
                AIUsageEvent.created_at >= month_start,
                AIUsageEvent.success.is_(True))
        .scalar() or 0
    )

    # Lifetime totals
    lifetime_count = (
        db.session.query(func.count(AIUsageEvent.id))
        .filter(AIUsageEvent.tenant_id == tenant.id,
                AIUsageEvent.success.is_(True))
        .scalar() or 0
    )
    lifetime_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageEvent.cost_usd), 0))
        .filter(AIUsageEvent.tenant_id == tenant.id,
                AIUsageEvent.success.is_(True))
        .scalar() or 0
    )

    # Per-feature breakdown this month
    by_feature = (
        db.session.query(
            AIUsageEvent.feature,
            func.count(AIUsageEvent.id).label('count'),
            func.coalesce(func.sum(AIUsageEvent.cost_usd), 0).label('cost'),
        )
        .filter(AIUsageEvent.tenant_id == tenant.id,
                AIUsageEvent.created_at >= month_start,
                AIUsageEvent.success.is_(True))
        .group_by(AIUsageEvent.feature)
        .all()
    )

    # Per-feature config (enabled + cap + used) — lets admin see the full
    # picture: does the plan allow this feature? what's the per-feature cap?
    feature_status = []
    for f in KNOWN_AI_FEATURES:
        cfg = get_feature_config(tenant, f['key'])
        used_for_feature = _count_used_this_month(tenant, feature=f['key'])
        feature_status.append({
            'key': f['key'],
            'label_ar': f['label_ar'],
            'enabled': cfg['enabled'],
            'monthly_cap': cfg['monthly_cap'],
            'used_this_month': used_for_feature,
        })

    return {
        'enabled': is_ai_enabled(tenant),
        'used_this_month': used,
        'limit': limit,
        'unlimited': limit < 0,
        'percent': (round(100 * used / limit, 1) if limit > 0 else 0.0),
        'month_cost_usd': float(month_cost),
        'lifetime_count': lifetime_count,
        'lifetime_cost_usd': float(lifetime_cost),
        'by_feature': [
            {'feature': r.feature, 'count': r.count, 'cost_usd': float(r.cost)}
            for r in by_feature
        ],
        'feature_status': feature_status,
    }
