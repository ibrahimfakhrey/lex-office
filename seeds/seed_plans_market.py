"""Seed subscription plans for both markets (EG + SA).

Idempotent: upserts by (name, market). The choose_plan.html comparison table
is fully data-driven from the `comparison` JSON populated here — no more
hardcoded HTML.

Run after the c3d4e5f6a7b8 migration.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.subscription import SubscriptionPlan


# Comparison-row content shared shape for both markets — only currency-bound
# strings (price labels) differ. Keys must match PLAN_COMPARISON_ROWS in
# app/utils/market_config.py.
def _eg_plans():
    return [
        {
            'name': 'Basic', 'name_ar': 'المحامي الفردي',
            'price_monthly': 297.00, 'price_yearly': 1782.00,
            'max_lawyers': 1, 'currency_code': 'EGP', 'market': 'eg',
            'features': {
                'max_cases': 50, 'max_storage_gb': 3,
                'clients': True, 'cases': True, 'sessions': True,
                'judgments': True, 'enforcement': True,
                'financial_basic': True, 'documents': True,
                'notifications_inapp': True, 'notifications_email': False,
                'whatsapp_notifications': False,
                'templates': True, 'max_templates': 1,
                'tasks_personal': True, 'tasks_distribute': False,
                'ai_enabled': True, 'ai_calls_per_month': 50,
                'ai_summary': False, 'dashboard_widgets': 3,
                'reports_basic': False, 'advanced_reports': False,
                'api_access': False,
            },
            'comparison': {
                'users': 'محامي واحد',
                'cases': 'حتى 50 قضية',
                'storage': '3 جيجابايت',
                'clients_poa': True,
                'calendar': True,
                'tasks': 'مهام شخصية فقط',
                'judgments': True,
                'enforcement': True,
                'finance': True,
                'expenses': True,
                'templates': 'نموذج واحد',
                'notifications': 'إشعارات داخل النظام (In-app)',
                'ai': False,
                'dashboard': '3 عناصر (Widgets)',
                'reports': False,
                'support': 'تذاكر دعم',
                'hosting': 'سحابة مشتركة',
                'api': False,
            },
        },
        {
            'name': 'Starter', 'name_ar': 'فريق النمو',
            'price_monthly': 497.00, 'price_yearly': 2982.00,
            'max_lawyers': 3, 'currency_code': 'EGP', 'market': 'eg',
            'features': {
                'max_cases': -1, 'max_storage_gb': 5,
                'clients': True, 'cases': True, 'sessions': True,
                'judgments': True, 'enforcement': True,
                'financial_basic': True, 'documents': True,
                'notifications_inapp': True, 'notifications_email': False,
                'whatsapp_notifications': False,
                'templates': True, 'max_templates': 3,
                'tasks_personal': True, 'tasks_distribute': True,
                'ai_enabled': True, 'ai_calls_per_month': 200,
                'ai_summary': True, 'dashboard_widgets': 5,
                'reports_basic': True, 'advanced_reports': False,
                'api_access': False,
            },
            'comparison': {
                'users': 'حتى 3 محامين',
                'cases': 'حتى 200 قضية',
                'storage': '5 جيجابايت',
                'clients_poa': True,
                'calendar': True,
                'tasks': 'توزيع مهام + متابعة تنفيذ',
                'judgments': True,
                'enforcement': True,
                'finance': True,
                'expenses': True,
                'templates': '3 نماذج',
                'notifications': 'إشعارات داخل النظام (In-app)',
                'ai': 'مساعد ذكي أساسي',
                'dashboard': '5 عناصر (Widgets)',
                'reports': 'تقارير أساسية',
                'support': 'تذاكر دعم',
                'hosting': 'سحابة مشتركة',
                'api': False,
            },
        },
        {
            'name': 'Professional', 'name_ar': 'المكاتب الكبرى',
            'price_monthly': 697.00, 'price_yearly': 4182.00,
            'max_lawyers': 6, 'currency_code': 'EGP', 'market': 'eg',
            'features': {
                'max_cases': -1, 'max_storage_gb': 10,
                'clients': True, 'cases': True, 'sessions': True,
                'judgments': True, 'enforcement': True,
                'financial_basic': True, 'financial_advanced': True,
                'documents': True,
                'notifications_inapp': True, 'notifications_email': True,
                'whatsapp_notifications': False,
                'templates': True, 'max_templates': 5,
                'tasks_personal': True, 'tasks_distribute': True,
                'ai_enabled': True, 'ai_calls_per_month': 1000,
                'ai_summary': True, 'ai_documents': True,
                'dashboard_widgets': 7,
                'reports_basic': True, 'advanced_reports': True,
                'api_access': False,
            },
            'comparison': {
                'users': 'حتى 6 محامين',
                'cases': 'غير محدود',
                'storage': '10 جيجابايت',
                'clients_poa': True,
                'calendar': True,
                'tasks': 'توزيع مهام + متابعة تنفيذ',
                'judgments': True,
                'enforcement': True,
                'finance': True,
                'expenses': True,
                'templates': '5 نماذج',
                'notifications': 'البريد الإلكتروني + إشعارات داخل النظام (In-app)',
                'ai': 'تلخيص مستندات + تذكارات ذكية',
                'dashboard': '7 عناصر كاملة (Widgets)',
                'reports': 'متقدمة BI — 6 تقارير',
                'support': 'أولوية رد',
                'hosting': 'سحابة مشتركة',
                'api': False,
            },
        },
        {
            'name': 'Business', 'name_ar': 'المؤسسات',
            'price_monthly': 0, 'price_yearly': 0,
            'max_lawyers': -1, 'currency_code': 'EGP', 'market': 'eg',
            'features': {
                'max_cases': -1, 'max_storage_gb': -1,
                'clients': True, 'cases': True, 'sessions': True,
                'judgments': True, 'enforcement': True,
                'financial_basic': True, 'financial_advanced': True,
                'documents': True,
                'notifications_inapp': True, 'notifications_email': True,
                'whatsapp_notifications': True,
                'templates': True, 'max_templates': -1,
                'tasks_personal': True, 'tasks_distribute': True,
                'tasks_departments': True,
                'ai_enabled': True, 'ai_calls_per_month': -1,
                'ai_summary': True, 'ai_documents': True,
                'dashboard_widgets': -1,
                'reports_basic': True, 'advanced_reports': True,
                'api_access': True, 'dedicated_server': True,
                'dedicated_support': True,
            },
            'comparison': {
                'users': 'غير محدود',
                'cases': 'غير محدود',
                'storage': 'غير محدود',
                'clients_poa': True,
                'calendar': True,
                'tasks': 'إدارة أقسام وصلاحيات متعددة',
                'judgments': True,
                'enforcement': True,
                'finance': 'تخصيص حسب الاتفاق',
                'expenses': 'تخصيص حسب الاتفاق',
                'templates': 'تخصيص حسب الاتفاق',
                'notifications': 'واتساب + الكل',
                'ai': 'تخصيص متقدم حسب الاتفاق',
                'dashboard': 'تخصيص حسب الاتفاق',
                'reports': 'تخصيص حسب الاتفاق',
                'support': 'مدير حساب مخصص 24/7',
                'hosting': 'سيرفر خاص (Dedicated)',
                'api': 'ربط API كامل مع أنظمة أخرى',
            },
        },
    ]


# SA prices: 400 / 600 / 800 / custom (placeholder — admin can edit).
def _sa_plans():
    eg = {p['name']: p for p in _eg_plans()}

    def _clone_with_overrides(name, **kwargs):
        # Start from the EG plan's structure and override what differs.
        base = dict(eg[name])
        base.update(kwargs)
        base['market'] = 'sa'
        base['currency_code'] = 'SAR'
        # Yearly = monthly * 12 with the same 50% discount banner the EG plans
        # use. Admin can adjust later from /admin/plans.
        if base.get('price_monthly'):
            base['price_yearly'] = round(float(base['price_monthly']) * 12 * 0.5, 2)
        return base

    return [
        _clone_with_overrides('Basic',        price_monthly=400.00),
        _clone_with_overrides('Starter',      price_monthly=600.00),
        _clone_with_overrides('Professional', price_monthly=800.00),
        _clone_with_overrides('Business',     price_monthly=0,
                              price_yearly=0),
    ]


def seed():
    with app.app_context():
        all_plans = _eg_plans() + _sa_plans()
        new_keys = {(p['name'], p['market']) for p in all_plans}

        # Deactivate any plan whose (name, market) is no longer in our list
        # (e.g. a stale market='eg' plan removed in a future re-seed).
        existing_managed = SubscriptionPlan.query.all()
        deactivated = 0
        for p in existing_managed:
            if (p.name, p.market) not in new_keys:
                if p.is_active:
                    p.is_active = False
                    deactivated += 1

        added, updated = 0, 0
        for data in all_plans:
            existing = SubscriptionPlan.query.filter_by(
                name=data['name'], market=data['market']
            ).first()
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.is_active = True
                existing.status = 'active'
                updated += 1
            else:
                plan = SubscriptionPlan(**data)
                plan.status = 'active'
                plan.is_active = True
                db.session.add(plan)
                added += 1

        db.session.commit()
        print(f"Plans: {added} added, {updated} updated, {deactivated} deactivated.")
        print(f"Total: {SubscriptionPlan.query.filter_by(is_active=True).count()} active "
              f"({SubscriptionPlan.query.filter_by(is_active=True, market='eg').count()} EG, "
              f"{SubscriptionPlan.query.filter_by(is_active=True, market='sa').count()} SA).")


if __name__ == '__main__':
    seed()
