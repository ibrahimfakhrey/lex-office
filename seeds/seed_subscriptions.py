"""Seed subscription plans (Basic, Starter, Professional, Business)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.subscription import SubscriptionPlan

PLANS = [
    {
        'name': 'Basic',
        'name_ar': 'المحامي الفردي',
        'price_monthly': 297.00,
        'price_yearly': 1782.00,
        'max_lawyers': 1,
        'features': {
            'max_cases': 50, 'max_storage_gb': 3,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'enforcement': True, 'financial_basic': True, 'documents': True,
            'notifications_inapp': True, 'notifications_email': False,
            'whatsapp_notifications': False,
            'templates': True, 'max_templates': 1,
            'tasks_personal': True, 'tasks_distribute': False,
            'ai_summary': False,
            'dashboard_widgets': 3,
            'reports_basic': False, 'advanced_reports': False,
            'api_access': False,
        },
    },
    {
        'name': 'Starter',
        'name_ar': 'فريق النمو',
        'price_monthly': 497.00,
        'price_yearly': 2982.00,
        'max_lawyers': 3,
        'features': {
            'max_cases': -1, 'max_storage_gb': 5,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'enforcement': True, 'financial_basic': True, 'documents': True,
            'notifications_inapp': True, 'notifications_email': False,
            'whatsapp_notifications': False,
            'templates': True, 'max_templates': 3,
            'tasks_personal': True, 'tasks_distribute': True,
            'ai_summary': True,
            'dashboard_widgets': 5,
            'reports_basic': True, 'advanced_reports': False,
            'api_access': False,
        },
    },
    {
        'name': 'Professional',
        'name_ar': 'المكاتب الكبرى',
        'price_monthly': 697.00,
        'price_yearly': 4182.00,
        'max_lawyers': 6,
        'features': {
            'max_cases': -1, 'max_storage_gb': 10,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'enforcement': True, 'financial_basic': True, 'financial_advanced': True,
            'documents': True,
            'notifications_inapp': True, 'notifications_email': True,
            'whatsapp_notifications': False,
            'templates': True, 'max_templates': 5,
            'tasks_personal': True, 'tasks_distribute': True,
            'ai_summary': True, 'ai_documents': True,
            'dashboard_widgets': 7,
            'reports_basic': True, 'advanced_reports': True,
            'api_access': False,
        },
    },
    {
        'name': 'Business',
        'name_ar': 'المؤسسات',
        'price_monthly': 0,
        'price_yearly': 0,
        'max_lawyers': -1,
        'features': {
            'max_cases': -1, 'max_storage_gb': -1,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'enforcement': True, 'financial_basic': True, 'financial_advanced': True,
            'documents': True,
            'notifications_inapp': True, 'notifications_email': True,
            'whatsapp_notifications': True,
            'templates': True, 'max_templates': -1,
            'tasks_personal': True, 'tasks_distribute': True, 'tasks_departments': True,
            'ai_summary': True, 'ai_documents': True,
            'dashboard_widgets': -1,
            'reports_basic': True, 'advanced_reports': True,
            'api_access': True,
            'dedicated_server': True,
            'dedicated_support': True,
        },
    },
]


def seed():
    with app.app_context():
        # Deactivate old plans that are no longer in the new list
        new_names = [p['name'] for p in PLANS]
        old_plans = SubscriptionPlan.query.filter(SubscriptionPlan.name.notin_(new_names)).all()
        for old in old_plans:
            old.is_active = False

        # Upsert new plans
        count = 0
        for plan_data in PLANS:
            existing = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
            if existing:
                for key, value in plan_data.items():
                    setattr(existing, key, value)
                existing.is_active = True
            else:
                db.session.add(SubscriptionPlan(**plan_data))
                count += 1
        db.session.commit()
        print(f"Seeded/updated subscription plans. {count} new, {len(old_plans)} deactivated.")


if __name__ == '__main__':
    seed()
