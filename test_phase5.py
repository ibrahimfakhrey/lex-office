"""Phase 5 E2E Test: Sessions, Judgments & Enforcement."""
import sys, os, smtplib
# Disable SMTP
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
from app.models.judgment import Judgment
from app.models.enforcement import Enforcement, EnforcementCollection, EnforcementAction
from datetime import date, time, timedelta
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

    # Setup: plan, tenant, role, user, court, client, case
    plan = SubscriptionPlan(name='Test', name_ar='تجريبي', max_lawyers=10, price_monthly=0, price_yearly=0)
    db.session.add(plan)
    db.session.flush()

    tenant = Tenant(name='Test Office', subscription_plan_id=plan.id)
    db.session.add(tenant)
    db.session.flush()

    role = Role(name='admin', name_ar='مدير')
    db.session.add(role)
    db.session.flush()

    # Add permissions for sessions, judgments, enforcement
    for module in ['sessions', 'judgments', 'enforcement', 'cases', 'clients']:
        for action in ['view', 'create', 'edit', 'delete']:
            perm = Permission(module=module, action=action)
            db.session.add(perm)
            db.session.flush()
            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            db.session.add(rp)

    user = User(full_name='Test Lawyer', email='test@test.com', phone='01012345678',
                tenant_id=tenant.id, role_id=role.id, is_active=True)
    user.set_password('Test123!')
    db.session.add(user)
    db.session.flush()

    court = Court(name='محكمة القاهرة', court_type='primary', governorate='القاهرة', is_active=True)
    db.session.add(court)
    db.session.flush()

    client = Client(tenant_id=tenant.id, full_name='أحمد محمد', client_type='individual',
                    phone_primary='01098765432', is_active=True)
    db.session.add(client)
    db.session.flush()

    case = Case(tenant_id=tenant.id, client_id=client.id, case_number='100/2026',
                subject='قضية مدنية', case_type='civil', status='active',
                responsible_lawyer_id=user.id)
    db.session.add(case)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    headers = {'Authorization': f'Bearer {token}'}

    with app.test_client() as c:
        # ===== SESSIONS =====
        print("\n=== SESSIONS ===")

        # List sessions
        r = c.get('/sessions/', headers=headers)
        check("List sessions page loads", r.status_code == 200)

        # Create session GET
        r = c.get('/sessions/create', headers=headers)
        check("Create session form loads", r.status_code == 200)

        # Create session POST
        r = c.post('/sessions/create', headers=headers, data={
            'case_id': case.id, 'session_date': '2026-04-10', 'session_time': '09:00',
            'court_id': court.id, 'circuit': 'دائرة 5', 'session_type': 'first',
            'responsible_lawyer_id': user.id, 'preparation_notes': 'ملاحظات تحضير'
        }, follow_redirects=True)
        check("Create session succeeds", r.status_code == 200)
        session_obj = Session.query.first()
        check("Session saved in DB", session_obj is not None)
        check("Session date correct", session_obj.session_date == date(2026, 4, 10))

        # Show session
        r = c.get(f'/sessions/{session_obj.id}', headers=headers)
        check("Show session page loads", r.status_code == 200)

        # Edit session GET
        r = c.get(f'/sessions/{session_obj.id}/edit', headers=headers)
        check("Edit session form loads", r.status_code == 200)

        # Edit session POST
        r = c.post(f'/sessions/{session_obj.id}/edit', headers=headers, data={
            'session_date': '2026-04-12', 'session_time': '10:00',
            'court_id': court.id, 'circuit': 'دائرة 7', 'session_type': 'pleading',
            'responsible_lawyer_id': user.id, 'preparation_notes': 'تم التعديل'
        }, follow_redirects=True)
        check("Edit session succeeds", r.status_code == 200)
        db.session.refresh(session_obj)
        check("Session date updated", session_obj.session_date == date(2026, 4, 12))

        # Record result
        r = c.get(f'/sessions/{session_obj.id}/record-result', headers=headers)
        check("Record result form loads", r.status_code == 200)

        r = c.post(f'/sessions/{session_obj.id}/record-result', headers=headers, data={
            'result': 'postponed', 'result_summary': 'تأجيل لتقديم مستندات',
            'next_session_date': '2026-05-01', 'create_next': 'yes'
        }, follow_redirects=True)
        check("Record result succeeds", r.status_code == 200)
        db.session.refresh(session_obj)
        check("Result saved", session_obj.result == 'postponed')
        next_session = Session.query.filter(Session.id != session_obj.id).first()
        check("Next session auto-created", next_session is not None)
        if next_session:
            check("Next session date correct", next_session.session_date == date(2026, 5, 1))

        # Calendar view
        r = c.get('/sessions/calendar', headers=headers)
        check("Calendar view loads", r.status_code == 200)

        # ===== JUDGMENTS =====
        print("\n=== JUDGMENTS ===")

        r = c.get('/judgments/', headers=headers)
        check("List judgments page loads", r.status_code == 200)

        r = c.get('/judgments/create', headers=headers)
        check("Create judgment form loads", r.status_code == 200)

        r = c.post('/judgments/create', headers=headers, data={
            'case_id': case.id, 'judgment_date': '2026-04-06', 'court_id': court.id,
            'judgment_type': 'primary', 'result': 'full_win',
            'judge_name': 'المستشار أحمد', 'awarded_amount': '50000',
            'judgment_text': 'حكم لصالح المدعي', 'notes': 'حكم نهائي',
            'appeal_tracking_enabled': 'yes'
        }, follow_redirects=True)
        check("Create judgment succeeds", r.status_code == 200)
        judgment = Judgment.query.first()
        check("Judgment saved in DB", judgment is not None)
        check("Judgment type correct", judgment.judgment_type == 'primary')
        check("Appeal deadline auto-calculated", judgment.appeal_deadline == date(2026, 4, 6) + timedelta(days=40))
        check("Awarded amount saved", float(judgment.awarded_amount) == 50000.0)

        # Show judgment
        r = c.get(f'/judgments/{judgment.id}', headers=headers)
        check("Show judgment page loads", r.status_code == 200)

        # Edit judgment
        r = c.get(f'/judgments/{judgment.id}/edit', headers=headers)
        check("Edit judgment form loads", r.status_code == 200)

        r = c.post(f'/judgments/{judgment.id}/edit', headers=headers, data={
            'judgment_date': '2026-04-06', 'court_id': court.id,
            'judgment_type': 'primary', 'result': 'partial_win',
            'judge_name': 'المستشار أحمد', 'awarded_amount': '35000',
            'judgment_text': 'حكم جزئي', 'notes': '',
            'appeal_deadline': '2026-05-20'
        }, follow_redirects=True)
        check("Edit judgment succeeds", r.status_code == 200)
        db.session.refresh(judgment)
        check("Judgment result updated", judgment.result == 'partial_win')
        check("Appeal deadline manually set", judgment.appeal_deadline == date(2026, 5, 20))

        # ===== ENFORCEMENT =====
        print("\n=== ENFORCEMENT ===")

        r = c.get('/enforcement/', headers=headers)
        check("List enforcement page loads", r.status_code == 200)

        r = c.get('/enforcement/create', headers=headers)
        check("Create enforcement form loads", r.status_code == 200)

        r = c.post('/enforcement/create', headers=headers, data={
            'case_id': case.id, 'client_id': client.id, 'judgment_id': judgment.id,
            'enforcement_number': '500/2026', 'enforcement_court': 'محكمة تنفيذ القاهرة',
            'executor_name': 'محضر', 'enforcement_type': 'funds_seizure',
            'total_amount': '35000', 'debtor_name': 'المدعى عليه',
            'start_date': '2026-04-06', 'notes': 'ملف تنفيذ'
        }, follow_redirects=True)
        check("Create enforcement succeeds", r.status_code == 200)
        enf = Enforcement.query.first()
        check("Enforcement saved in DB", enf is not None)
        check("Total amount correct", float(enf.total_amount) == 35000.0)

        # Show enforcement
        r = c.get(f'/enforcement/{enf.id}', headers=headers)
        check("Show enforcement page loads", r.status_code == 200)

        # Add collection
        r = c.post(f'/enforcement/{enf.id}/add-collection', headers=headers, data={
            'amount': '20000', 'collection_date': '2026-04-10', 'collection_method': 'تحويل بنكي',
            'notes': 'دفعة أولى'
        }, follow_redirects=True)
        check("Add collection succeeds", r.status_code == 200)
        db.session.refresh(enf)
        check("Collected amount updated", float(enf.collected_amount) == 20000.0)
        check("Status still active", enf.status == 'active')

        # Add second collection to complete
        r = c.post(f'/enforcement/{enf.id}/add-collection', headers=headers, data={
            'amount': '15000', 'collection_date': '2026-04-15', 'collection_method': 'نقدي'
        }, follow_redirects=True)
        check("Second collection succeeds", r.status_code == 200)
        db.session.refresh(enf)
        check("Fully collected", float(enf.collected_amount) == 35000.0)
        check("Auto-completed", enf.status == 'completed')

        # Add action
        enf.status = 'active'  # reset for testing action
        db.session.commit()
        r = c.post(f'/enforcement/{enf.id}/add-action', headers=headers, data={
            'action_description': 'إنذار رسمي', 'action_date': '2026-04-08'
        }, follow_redirects=True)
        check("Add action succeeds", r.status_code == 200)
        check("Action saved", EnforcementAction.query.count() == 1)

        # Delete session
        r = c.post(f'/sessions/{session_obj.id}/delete', headers=headers, follow_redirects=True)
        check("Delete session succeeds", r.status_code == 200)

        # Delete judgment
        r = c.post(f'/judgments/{judgment.id}/delete', headers=headers, follow_redirects=True)
        check("Delete judgment succeeds", r.status_code == 200)

        # Delete enforcement
        r = c.post(f'/enforcement/{enf.id}/delete', headers=headers, follow_redirects=True)
        check("Delete enforcement succeeds", r.status_code == 200)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {passed+failed}")
    if failed:
        sys.exit(1)
    else:
        print("Phase 5 ALL PASSED!")
