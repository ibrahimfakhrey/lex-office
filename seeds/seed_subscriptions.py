"""Seed subscription plans (Starter, Professional, Enterprise)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask_app import app
from app.extensions import db
from app.models.subscription import SubscriptionPlan

PLANS = [
    {
        'name': 'Starter',
        'name_ar': 'أساسي',
        'price_monthly': 299.00,
        'price_yearly': 2990.00,
        'max_lawyers': 3,
        'features': {
            'max_cases': 50, 'max_storage_gb': 5,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'financial_basic': True, 'documents': True, 'notifications_email': True,
            'reports_basic': True,
            'ai_summary': False, 'enforcement': False, 'templates': False,
            'sms_notifications': False, 'whatsapp_notifications': False,
            'advanced_reports': False, 'api_access': False,
        },
    },
    {
        'name': 'Professional',
        'name_ar': 'احترافي',
        'price_monthly': 599.00,
        'price_yearly': 5990.00,
        'max_lawyers': 10,
        'features': {
            'max_cases': 200, 'max_storage_gb': 25,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'financial_basic': True, 'financial_advanced': True, 'documents': True,
            'enforcement': True, 'templates': True, 'notifications_email': True,
            'sms_notifications': True, 'reports_basic': True, 'advanced_reports': True,
            'ai_summary': True,
            'whatsapp_notifications': False, 'api_access': False,
        },
    },
    {
        'name': 'Enterprise',
        'name_ar': 'مؤسسي',
        'price_monthly': 999.00,
        'price_yearly': 9990.00,
        'max_lawyers': -1,
        'features': {
            'max_cases': -1, 'max_storage_gb': 100,
            'clients': True, 'cases': True, 'sessions': True, 'judgments': True,
            'financial_basic': True, 'financial_advanced': True, 'documents': True,
            'enforcement': True, 'templates': True, 'notifications_email': True,
            'sms_notifications': True, 'whatsapp_notifications': True,
            'reports_basic': True, 'advanced_reports': True, 'ai_summary': True,
            'api_access': True,
        },
    },
]


def seed():
    with app.app_context():
        count = 0
        for plan_data in PLANS:
            existing = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
            if not existing:
                db.session.add(SubscriptionPlan(**plan_data))
                count += 1
        db.session.commit()
        print(f"Seeded {count} subscription plans.")


if __name__ == '__main__':
    seed()
