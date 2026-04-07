"""Phase 8 E2E Test: Notifications, Reports & Settings."""
import sys, os, smtplib
smtplib.SMTP = type('MockSMTP', (), {'__init__': lambda *a, **k: None, 'ehlo': lambda s: None, 'starttls': lambda s: None, 'login': lambda s, u, p: None, 'send_message': lambda s, m: None, 'quit': lambda s: None})

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User, Role, Permission, RolePermission
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.models.case import Case, Court
from app.models.client import Client
from app.models.session import Session
from app.models.task import Task
from app.models.financial import Payment, Expense
from app.models.notification import Notification, NotificationSetting
from datetime import date, datetime, timedelta
from flask_jwt_extended import create_access_token

app = create_app('testing')
passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")

with app.app_context():
    db.drop_all()
    db.create_all()

    # Setup
    plan = SubscriptionPlan(name='Test', name_ar='تجريبي', max_lawyers=10, price_monthly=0, price_yearly=0)
    db.session.add(plan)
    db.session.flush()

    tenant = Tenant(name='مكتب الاختبار', subscription_plan_id=plan.id)
    db.session.add(tenant)
    db.session.flush()

    role = Role(name='admin', name_ar='مدير')
    db.session.add(role)
    db.session.flush()

    role2 = Role(name='lawyer', name_ar='محامي')
    db.session.add(role2)
    db.session.flush()

    for module in ['notifications', 'reports', 'settings', 'cases', 'clients', 'financial', 'tasks', 'sessions']:
        for action in ['view', 'create', 'edit', 'delete']:
            perm = Permission(module=module, action=action)
            db.session.add(perm)
            db.session.flush()
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = User(full_name='محامي اختبار', email='test@test.com', phone='01012345678',
                tenant_id=tenant.id, role_id=role.id, is_active=True)
    user.set_password('Test123!')
    db.session.add(user)
    db.session.flush()

    # Second user for team tests
    user2 = User(full_name='محامي ثاني', email='test2@test.com', phone='01098765432',
                 tenant_id=tenant.id, role_id=role2.id, is_active=True)
    user2.set_password('Test123!')
    db.session.add(user2)
    db.session.flush()

    court = Court(name='محكمة القاهرة', court_type='primary', governorate='القاهرة', is_active=True)
    db.session.add(court)
    db.session.flush()

    client = Client(tenant_id=tenant.id, full_name='أحمد محمد', client_type='individual',
                    phone_primary='01098765432', national_id='12345678901234',
                    governorate='القاهرة', city='مدينة نصر', street='شارع 10', is_active=True)
    db.session.add(client)
    db.session.flush()

    case = Case(tenant_id=tenant.id, client_id=client.id, case_number='200/2026',
                subject='قضية إيجارات', case_type='civil', status='active',
                responsible_lawyer_id=user.id, court_id=court.id, opponent_name='خالد أحمد')
    db.session.add(case)
    db.session.flush()

    # Create some data for reports
    session1 = Session(tenant_id=tenant.id, case_id=case.id, session_date=date.today(),
                       responsible_lawyer_id=user.id, court_id=court.id, session_type='first_hearing')
    db.session.add(session1)

    session2 = Session(tenant_id=tenant.id, case_id=case.id,
                       session_date=date.today() + timedelta(days=7),
                       responsible_lawyer_id=user.id, court_id=court.id, result='postponed')
    db.session.add(session2)

    task1 = Task(tenant_id=tenant.id, title='مهمة اختبار', assigned_to=user.id,
                 assigned_by=user.id, case_id=case.id, status='new', priority='high')
    db.session.add(task1)

    payment1 = Payment(tenant_id=tenant.id, client_id=client.id, case_id=case.id,
                       amount=5000, payment_date=date.today(), payment_method='cash')
    db.session.add(payment1)

    expense1 = Expense(tenant_id=tenant.id, expense_type='court_fees', amount=500,
                       expense_date=date.today(), description='رسوم محكمة')
    db.session.add(expense1)

    # Create notifications
    notif1 = Notification(tenant_id=tenant.id, user_id=user.id, notification_type='session_reminder',
                          priority='warning', title='تذكير بجلسة غداً', body='جلسة قضية إيجارات',
                          is_read=False)
    db.session.add(notif1)

    notif2 = Notification(tenant_id=tenant.id, user_id=user.id, notification_type='task_assigned',
                          priority='info', title='مهمة جديدة', body='تم تعيين مهمة لك',
                          is_read=True, read_at=datetime.utcnow())
    db.session.add(notif2)

    notif3 = Notification(tenant_id=tenant.id, user_id=user.id, notification_type='payment_received',
                          priority='success', title='دفعة جديدة', is_read=False)
    db.session.add(notif3)

    db.session.commit()

    token = create_access_token(identity=str(user.id))
    headers = {'Authorization': f'Bearer {token}'}

    with app.test_client() as c:

        # ===== NOTIFICATIONS =====
        print("\n=== NOTIFICATIONS ===")

        r = c.get('/notifications/', headers=headers)
        check("Notifications list loads", r.status_code == 200)
        check("Shows notifications", 'تذكير بجلسة' in r.data.decode())

        r = c.get('/notifications/?type=unread', headers=headers)
        check("Filter unread", r.status_code == 200)

        # Mark single as read
        r = c.post(f'/notifications/{notif1.id}/mark-read', headers=headers, follow_redirects=True)
        check("Mark single as read", r.status_code == 200)
        db.session.refresh(notif1)
        check("Notification marked read in DB", notif1.is_read == True)

        # Mark all as read
        r = c.post('/notifications/mark-all-read', headers=headers, follow_redirects=True)
        check("Mark all as read", r.status_code == 200)
        unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        check("All notifications read in DB", unread == 0)

        # Notification settings page
        r = c.get('/notifications/settings', headers=headers)
        check("Notification settings loads", r.status_code == 200)
        check("Shows notification types", 'تذكير بجلسة' in r.data.decode())

        # Save notification settings
        r = c.post('/notifications/settings', headers=headers, data={
            'session_reminder_in_app': 'on',
            'session_reminder_email': 'on',
            'task_assigned_in_app': 'on',
        }, follow_redirects=True)
        check("Save notification settings", r.status_code == 200)

        setting = NotificationSetting.query.filter_by(
            user_id=user.id, notification_type='session_reminder').first()
        check("Setting saved - email enabled", setting is not None and setting.email_enabled == True)
        check("Setting saved - sms disabled", setting is not None and setting.sms_enabled == False)

        task_setting = NotificationSetting.query.filter_by(
            user_id=user.id, notification_type='task_assigned').first()
        check("Task setting saved", task_setting is not None and task_setting.in_app_enabled == True)

        # ===== REPORTS =====
        print("\n=== REPORTS ===")

        r = c.get('/reports/', headers=headers)
        check("Reports dashboard loads", r.status_code == 200)

        r = c.get('/reports/financial', headers=headers)
        check("Financial report loads", r.status_code == 200)

        r = c.get(f'/reports/financial?date_from=2026-01-01&date_to=2026-12-31', headers=headers)
        check("Financial report with date filter", r.status_code == 200)

        r = c.get('/reports/performance', headers=headers)
        check("Performance report loads", r.status_code == 200)

        r = c.get('/reports/workload', headers=headers)
        check("Workload report loads", r.status_code == 200)

        r = c.get('/reports/sessions', headers=headers)
        check("Sessions report loads", r.status_code == 200)

        r = c.get('/reports/sessions?date_from=2026-01-01&date_to=2026-12-31', headers=headers)
        check("Sessions report with date filter", r.status_code == 200)

        # ===== SETTINGS =====
        print("\n=== SETTINGS ===")

        r = c.get('/settings/', headers=headers)
        check("Settings index loads", r.status_code == 200)
        check("Shows office name", 'مكتب الاختبار' in r.data.decode())

        # Update office settings
        r = c.post('/settings/update-office', headers=headers, data={
            'office_name': 'مكتب المحاماة المتحد',
            'address': 'شارع التحرير، القاهرة',
            'bar_registration_no': '12345',
            'primary_court': 'محكمة القاهرة',
            'phone': '0223456789',
            'fax': '0223456780',
            'email': 'office@test.com',
        }, follow_redirects=True)
        check("Update office settings", r.status_code == 200)
        db.session.refresh(tenant)
        check("Office name updated in DB", tenant.name == 'مكتب المحاماة المتحد')
        check("Address updated in DB", tenant.address == 'شارع التحرير، القاهرة')
        check("Bar registration updated", tenant.bar_registration_no == '12345')

        # Team management
        r = c.get('/settings/team', headers=headers)
        check("Team page loads", r.status_code == 200)
        check("Shows team members", 'محامي ثاني' in r.data.decode())

        # Toggle member (deactivate user2)
        r = c.post(f'/settings/team/{user2.id}/toggle', headers=headers, follow_redirects=True)
        check("Toggle member", r.status_code == 200)
        db.session.refresh(user2)
        check("User2 deactivated", user2.is_active == False)

        # Toggle back (activate)
        r = c.post(f'/settings/team/{user2.id}/toggle', headers=headers, follow_redirects=True)
        check("Toggle member back", r.status_code == 200)
        db.session.refresh(user2)
        check("User2 reactivated", user2.is_active == True)

        # Cannot deactivate self
        r = c.post(f'/settings/team/{user.id}/toggle', headers=headers, follow_redirects=True)
        check("Cannot deactivate self", r.status_code == 200)
        db.session.refresh(user)
        check("Self still active", user.is_active == True)

        # Change role
        r = c.post(f'/settings/team/{user2.id}/role', headers=headers, data={
            'role_id': str(role.id),
        }, follow_redirects=True)
        check("Change role", r.status_code == 200)
        db.session.refresh(user2)
        check("Role changed in DB", user2.role_id == role.id)

        # Profile page
        r = c.get('/settings/profile', headers=headers)
        check("Profile page loads", r.status_code == 200)
        check("Shows user name", 'محامي اختبار' in r.data.decode())

        # Update profile
        r = c.post('/settings/profile', headers=headers, data={
            'full_name': 'محامي اختبار معدّل',
            'full_name_en': 'Test Lawyer',
            'phone': '01111111111',
        }, follow_redirects=True)
        check("Update profile", r.status_code == 200)
        db.session.refresh(user)
        check("Name updated in DB", user.full_name == 'محامي اختبار معدّل')
        check("English name updated", user.full_name_en == 'Test Lawyer')
        check("Phone updated", user.phone == '01111111111')

        # Change password
        r = c.post('/settings/profile', headers=headers, data={
            'full_name': 'محامي اختبار معدّل',
            'current_password': 'Test123!',
            'new_password': 'NewPass123!',
        }, follow_redirects=True)
        check("Change password", r.status_code == 200)
        db.session.refresh(user)
        check("Password changed in DB", user.check_password('NewPass123!'))
        check("Password changed timestamp set", user.password_changed_at is not None)

        # Wrong current password
        r = c.post('/settings/profile', headers=headers, data={
            'full_name': 'محامي اختبار معدّل',
            'current_password': 'WrongPassword',
            'new_password': 'AnotherPass1!',
        }, follow_redirects=True)
        check("Wrong password rejected", r.status_code == 200)
        db.session.refresh(user)
        check("Password unchanged after wrong current", user.check_password('NewPass123!'))

        # Short new password
        r = c.post('/settings/profile', headers=headers, data={
            'full_name': 'محامي اختبار معدّل',
            'current_password': 'NewPass123!',
            'new_password': 'short',
        }, follow_redirects=True)
        check("Short password rejected", r.status_code == 200)
        db.session.refresh(user)
        check("Password unchanged after short attempt", user.check_password('NewPass123!'))

    print(f"\n{'='*40}")
    print(f"Phase 8 Results: {passed} passed, {failed} failed out of {passed+failed}")
    if failed == 0:
        print("✅ ALL PHASE 8 TESTS PASSED!")
    else:
        print("❌ Some tests failed")
