"""Phase 7 E2E Test: Documents, Tasks & Legal Templates."""
import sys, os, smtplib, io
smtplib.SMTP = type('MockSMTP', (), {'__init__': lambda *a, **k: None, 'ehlo': lambda s: None, 'starttls': lambda s: None, 'login': lambda s, u, p: None, 'send_message': lambda s, m: None, 'quit': lambda s: None})

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User, Role, Permission, RolePermission
from app.models.tenant import Tenant
from app.models.subscription import SubscriptionPlan
from app.models.case import Case, Court
from app.models.client import Client
from app.models.document import Document, LegalTemplate
from app.models.task import Task
from datetime import date, datetime
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

    for module in ['documents', 'tasks', 'templates', 'cases', 'clients']:
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
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    headers = {'Authorization': f'Bearer {token}'}

    with app.test_client() as c:

        # ===== DOCUMENTS =====
        print("\n=== DOCUMENTS ===")

        r = c.get('/documents/', headers=headers)
        check("Documents list loads", r.status_code == 200)

        r = c.get('/documents/upload', headers=headers)
        check("Upload form loads", r.status_code == 200)

        # Upload a file
        data = {
            'name': 'عقد إيجار',
            'doc_type': 'contract',
            'case_id': str(case.id),
            'client_id': str(client.id),
            'doc_date': '2026-04-01',
            'notes': 'عقد إيجار اختبار',
        }
        data['file'] = (io.BytesIO(b'%PDF-1.4 test content'), 'test_contract.pdf')
        r = c.post('/documents/upload', headers=headers, data=data,
                    content_type='multipart/form-data', follow_redirects=True)
        check("Upload document succeeds", r.status_code == 200)
        doc = Document.query.first()
        check("Document saved in DB", doc is not None)
        check("Document name correct", doc.name == 'عقد إيجار')
        check("Document type correct", doc.doc_type == 'contract')
        check("File type detected", doc.file_type == 'pdf')
        check("File size > 0", doc.file_size > 0)
        check("Uploaded by set", doc.uploaded_by == user.id)

        # Show document
        r = c.get(f'/documents/{doc.id}', headers=headers)
        check("Show document loads", r.status_code == 200)

        # Share document
        r = c.post(f'/documents/{doc.id}/share', headers=headers, data={
            'days': '7'
        }, follow_redirects=True)
        check("Share document succeeds", r.status_code == 200)
        db.session.refresh(doc)
        check("Share token generated", doc.share_token is not None)
        check("Share is active", doc.is_share_active)

        # Validation - no file
        r = c.post('/documents/upload', headers=headers, data={
            'doc_type': 'contract'
        }, content_type='multipart/form-data', follow_redirects=True)
        check("Upload validation (no file)", r.status_code == 200)
        check("No extra document created", Document.query.count() == 1)

        # ===== TASKS =====
        print("\n=== TASKS ===")

        r = c.get('/tasks/', headers=headers)
        check("Tasks list loads", r.status_code == 200)

        r = c.get('/tasks/create', headers=headers)
        check("Create task form loads", r.status_code == 200)

        r = c.post('/tasks/create', headers=headers, data={
            'title': 'مراجعة العقد',
            'description': 'مراجعة بنود عقد الإيجار',
            'assigned_to': str(user.id),
            'case_id': str(case.id),
            'priority': 'important',
            'deadline': '2026-04-10T14:00',
        }, follow_redirects=True)
        check("Create task succeeds", r.status_code == 200)
        task = Task.query.first()
        check("Task saved in DB", task is not None)
        check("Task title correct", task.title == 'مراجعة العقد')
        check("Task priority correct", task.priority == 'important')
        check("Task assigned correctly", task.assigned_to == user.id)
        check("Task assigned_by set", task.assigned_by == user.id)
        check("Task deadline set", task.deadline is not None)

        # Show task
        r = c.get(f'/tasks/{task.id}', headers=headers)
        check("Show task loads", r.status_code == 200)

        # Edit task
        r = c.get(f'/tasks/{task.id}/edit', headers=headers)
        check("Edit task form loads", r.status_code == 200)

        r = c.post(f'/tasks/{task.id}/edit', headers=headers, data={
            'title': 'مراجعة العقد - محدّث',
            'description': 'تم تحديث الوصف',
            'assigned_to': str(user.id),
            'priority': 'urgent',
            'deadline': '2026-04-08T10:00',
        }, follow_redirects=True)
        check("Edit task succeeds", r.status_code == 200)
        db.session.refresh(task)
        check("Task title updated", task.title == 'مراجعة العقد - محدّث')
        check("Task priority updated", task.priority == 'urgent')

        # Update status
        r = c.post(f'/tasks/{task.id}/update-status', headers=headers, data={
            'status': 'in_progress'
        }, follow_redirects=True)
        check("Status update works", r.status_code == 200)
        db.session.refresh(task)
        check("Status changed", task.status == 'in_progress')

        r = c.post(f'/tasks/{task.id}/update-status', headers=headers, data={
            'status': 'done'
        }, follow_redirects=True)
        check("Mark as done works", r.status_code == 200)
        db.session.refresh(task)
        check("Status is done", task.status == 'done')

        # Validation
        r = c.post('/tasks/create', headers=headers, data={
            'title': '', 'assigned_to': ''
        }, follow_redirects=True)
        check("Task validation works", r.status_code == 200)
        check("No extra task created", Task.query.count() == 1)

        # ===== LEGAL TEMPLATES =====
        print("\n=== LEGAL TEMPLATES ===")

        r = c.get('/templates/', headers=headers)
        check("Templates list loads", r.status_code == 200)

        r = c.get('/templates/create', headers=headers)
        check("Create template form loads", r.status_code == 200)

        r = c.post('/templates/create', headers=headers, data={
            'name': 'Power of Attorney',
            'name_ar': 'توكيل عام',
            'template_type': 'power_of_attorney',
            'output_format': 'html',
            'template_content': 'أنا الموقع أدناه {{client_name}} حامل بطاقة رقم {{client_national_id}} المقيم في {{client_address}} أوكل السيد {{lawyer_name}} في القضية رقم {{case_number}} بخصوص {{case_subject}} ضد {{opponent_name}} أمام {{court_name}} بتاريخ {{today_date}}.',
        }, follow_redirects=True)
        check("Create template succeeds", r.status_code == 200)
        tmpl = LegalTemplate.query.first()
        check("Template saved in DB", tmpl is not None)
        check("Template name correct", tmpl.name_ar == 'توكيل عام')
        check("Template type correct", tmpl.template_type == 'power_of_attorney')

        # Show template
        r = c.get(f'/templates/{tmpl.id}', headers=headers)
        check("Show template loads", r.status_code == 200)

        # Preview
        r = c.get(f'/templates/{tmpl.id}/preview', headers=headers)
        check("Preview template loads", r.status_code == 200)

        # Edit template
        r = c.get(f'/templates/{tmpl.id}/edit', headers=headers)
        check("Edit template form loads", r.status_code == 200)

        r = c.post(f'/templates/{tmpl.id}/edit', headers=headers, data={
            'name': 'General Power of Attorney',
            'name_ar': 'توكيل عام رسمي',
            'template_type': 'power_of_attorney',
            'output_format': 'html',
            'template_content': tmpl.template_content,
        }, follow_redirects=True)
        check("Edit template succeeds", r.status_code == 200)
        db.session.refresh(tmpl)
        check("Template name updated", tmpl.name_ar == 'توكيل عام رسمي')

        # Use template (generate document)
        r = c.get(f'/templates/{tmpl.id}/use', headers=headers)
        check("Use template form loads", r.status_code == 200)

        r = c.post(f'/templates/{tmpl.id}/use', headers=headers, data={
            'case_id': str(case.id),
            'client_id': str(client.id),
        })
        check("Generate document succeeds", r.status_code == 200)
        # Verify variable substitution happened
        html = r.data.decode('utf-8')
        check("Client name substituted", 'أحمد محمد' in html)
        check("Case number substituted", '200/2026' in html)
        check("Opponent name substituted", 'خالد أحمد' in html)
        check("Court name substituted", 'محكمة القاهرة' in html)
        check("Today date substituted", date.today().strftime('%Y-%m-%d') in html)

        # ===== DELETES =====
        print("\n=== DELETES ===")

        r = c.post(f'/documents/{doc.id}/delete', headers=headers, follow_redirects=True)
        check("Delete document succeeds", r.status_code == 200)
        check("Document deleted", Document.query.count() == 0)

        r = c.post(f'/tasks/{task.id}/delete', headers=headers, follow_redirects=True)
        check("Delete task succeeds", r.status_code == 200)
        check("Task deleted", Task.query.count() == 0)

        r = c.post(f'/templates/{tmpl.id}/delete', headers=headers, follow_redirects=True)
        check("Delete template succeeds", r.status_code == 200)
        check("Template deleted", LegalTemplate.query.count() == 0)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {passed+failed}")
    if failed:
        sys.exit(1)
    else:
        print("Phase 7 ALL PASSED!")
