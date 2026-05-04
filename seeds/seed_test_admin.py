"""Seed a dedicated admin account used by Playwright e2e tests.

Idempotent: re-running re-applies the password (useful if it's been changed)
and ensures the admin is active and unlocked.

Run with:
  cd <project>
  FLASK_APP=flask_app.py python3 -m flask shell -c "exec(open('seeds/seed_test_admin.py').read())"

Or directly:
  python3 seeds/seed_test_admin.py
"""
from app import create_app
from app.extensions import db
from app.models.admin import AdminUser


TEST_ADMIN_EMAIL = 'test_admin@manasety.ai'
TEST_ADMIN_PASSWORD = 'TestAdmin@2026'
TEST_ADMIN_NAME = 'Playwright Test Admin'


def seed():
    admin = AdminUser.query.filter_by(email=TEST_ADMIN_EMAIL).first()
    if admin:
        admin.full_name = TEST_ADMIN_NAME
        admin.role = 'super_admin'
        admin.is_active = True
        admin.mfa_enabled = False
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.set_password(TEST_ADMIN_PASSWORD)
        db.session.commit()
        print(f'✓ Refreshed test admin: {TEST_ADMIN_EMAIL} (id={admin.id})')
        return admin

    admin = AdminUser(
        email=TEST_ADMIN_EMAIL,
        full_name=TEST_ADMIN_NAME,
        role='super_admin',
        is_active=True,
        mfa_enabled=False,
    )
    admin.set_password(TEST_ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    print(f'✓ Created test admin: {TEST_ADMIN_EMAIL} (id={admin.id})')
    print(f'  Password: {TEST_ADMIN_PASSWORD}')
    print(f'  Login at: http://127.0.0.1:5000/admin/login')
    return admin


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
