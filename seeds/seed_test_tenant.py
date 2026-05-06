"""Seed a test tenant + manager user used by Playwright e2e tests.

Idempotent: re-running re-applies the password and ensures the user is
active. The tenant is attached to a low-cap "Test Plan" with
max_legal_templates=2 so the templates-quota test can hit the cap quickly.

Run with:
    PYTHONPATH=. python3 seeds/seed_test_tenant.py
"""
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import User, Role
from app.models.subscription import SubscriptionPlan


TEST_PLAN_NAME = 'TEST_Plan'
TEST_PLAN_NAME_AR = 'خطة تجريبية'
TEST_TENANT_NAME = 'Test Office'
TEST_USER_EMAIL = 'test_office@manasety.ai'
TEST_USER_PASSWORD = 'TestOffice@2026'
TEST_USER_FULL_NAME = 'مدير المكتب التجريبي'
TEST_USER_PHONE = '01099999999'
TEMPLATE_LIMIT = 2  # default cap for the test plan


def seed():
    # 1. Find/refresh the test plan with our chosen template cap
    plan = SubscriptionPlan.query.filter_by(name=TEST_PLAN_NAME).first()
    if not plan:
        plan = SubscriptionPlan(
            name=TEST_PLAN_NAME,
            name_ar=TEST_PLAN_NAME_AR,
            description='Plan used only by Playwright e2e tests',
            max_lawyers=5,
            max_storage_gb=2,
            price_monthly=0,
            price_yearly=0,
            features={},
            status='active',
            is_active=True,
            is_public=False,
            self_service=False,
        )
        db.session.add(plan)
        db.session.flush()
    # Always reset features so prior runs of the test (which mutate the cap)
    # don't leave the seed in a weird state.
    plan.features = dict(plan.features or {}, max_legal_templates=TEMPLATE_LIMIT)

    # 2. Find/create the tenant
    tenant = Tenant.query.filter_by(name=TEST_TENANT_NAME).first()
    if not tenant:
        tenant = Tenant(
            name=TEST_TENANT_NAME,
            subscription_plan_id=plan.id,
            subscription_status='active',
            is_active=True,
            country='Egypt',
            city='Cairo',
            primary_court='Cairo Civil Court',
        )
        db.session.add(tenant)
        db.session.flush()
    else:
        # Make sure the tenant is on our test plan and active
        tenant.subscription_plan_id = plan.id
        tenant.subscription_status = 'active'
        tenant.is_active = True

    # 3. Find the manager role (already seeded by seed_roles.py)
    manager_role = Role.query.filter_by(name='manager').first()
    if not manager_role:
        raise RuntimeError(
            'Role "manager" not found. Run seed_roles.py first '
            '(or seed_all.py).'
        )

    # 4. Find/create the test user
    user = User.query.filter_by(email=TEST_USER_EMAIL).first()
    if not user:
        user = User(
            tenant_id=tenant.id,
            email=TEST_USER_EMAIL,
            full_name=TEST_USER_FULL_NAME,
            phone=TEST_USER_PHONE,
            role_id=manager_role.id,
            is_active=True,
            mfa_enabled=False,
        )
        user.set_password(TEST_USER_PASSWORD)
        db.session.add(user)
    else:
        user.tenant_id = tenant.id
        user.role_id = manager_role.id
        user.is_active = True
        user.mfa_enabled = False
        user.login_attempts = 0
        user.locked_until = None
        user.set_password(TEST_USER_PASSWORD)

    db.session.commit()
    print('✓ Test tenant + user seeded')
    print(f'  Tenant:       {tenant.name} (id={tenant.id})')
    print(f'  Plan:         {plan.name} (max_legal_templates={plan.features.get("max_legal_templates")})')
    print(f'  User email:   {TEST_USER_EMAIL}')
    print(f'  User pass:    {TEST_USER_PASSWORD}')
    print(f'  Login URL:    http://127.0.0.1:5050/auth/login')
    return user


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
