"""Phase 6 E2E Test: Financial Management."""
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
from app.models.financial import Payment, Invoice, InvoiceItem, Expense
from datetime import date
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

    tenant = Tenant(name='Test Office', subscription_plan_id=plan.id)
    db.session.add(tenant)
    db.session.flush()

    role = Role(name='admin', name_ar='مدير')
    db.session.add(role)
    db.session.flush()

    for module in ['financial', 'cases', 'clients']:
        for action in ['view', 'create', 'edit', 'delete']:
            perm = Permission(module=module, action=action)
            db.session.add(perm)
            db.session.flush()
            db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))

    user = User(full_name='Test Lawyer', email='test@test.com', phone='01012345678',
                tenant_id=tenant.id, role_id=role.id, is_active=True)
    user.set_password('Test123!')
    db.session.add(user)
    db.session.flush()

    client = Client(tenant_id=tenant.id, full_name='أحمد محمد', client_type='individual', is_active=True)
    db.session.add(client)
    db.session.flush()

    case = Case(tenant_id=tenant.id, client_id=client.id, case_number='100/2026',
                subject='قضية مدنية', case_type='civil', status='active',
                responsible_lawyer_id=user.id, fee_amount=50000)
    db.session.add(case)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    headers = {'Authorization': f'Bearer {token}'}

    with app.test_client() as c:

        # ===== FINANCIAL OVERVIEW =====
        print("\n=== FINANCIAL OVERVIEW ===")
        r = c.get('/financial/', headers=headers)
        check("Financial overview loads", r.status_code == 200)

        # ===== PAYMENTS =====
        print("\n=== PAYMENTS ===")

        r = c.get('/financial/payments', headers=headers)
        check("Payments list loads", r.status_code == 200)

        r = c.get('/financial/payments/create', headers=headers)
        check("Create payment form loads", r.status_code == 200)

        r = c.post('/financial/payments/create', headers=headers, data={
            'client_id': client.id, 'case_id': case.id, 'amount': '10000',
            'payment_date': '2026-04-06', 'payment_method': 'cash',
            'reference_number': 'REC-001', 'notes': 'دفعة أولى'
        }, follow_redirects=True)
        check("Create payment succeeds", r.status_code == 200)
        payment = Payment.query.first()
        check("Payment saved in DB", payment is not None)
        check("Payment amount correct", float(payment.amount) == 10000.0)
        check("Payment method correct", payment.payment_method == 'cash')
        check("Recorded by set", payment.recorded_by == user.id)

        r = c.get(f'/financial/payments/{payment.id}', headers=headers)
        check("Show payment loads", r.status_code == 200)

        # Validation test
        r = c.post('/financial/payments/create', headers=headers, data={
            'amount': '', 'payment_date': '', 'payment_method': ''
        }, follow_redirects=True)
        check("Payment validation works", r.status_code == 200)
        check("No extra payment created", Payment.query.count() == 1)

        # ===== INVOICES =====
        print("\n=== INVOICES ===")

        r = c.get('/financial/invoices', headers=headers)
        check("Invoices list loads", r.status_code == 200)

        r = c.get('/financial/invoices/create', headers=headers)
        check("Create invoice form loads", r.status_code == 200)

        r = c.post('/financial/invoices/create', headers=headers, data={
            'client_id': client.id, 'case_id': case.id,
            'issue_date': '2026-04-06', 'tax_rate': '14',
            'discount_type': 'percentage', 'discount_value': '10',
            'item_description[]': ['أتعاب قضية', 'رسوم محكمة'],
            'item_type[]': ['fees', 'court_fees'],
            'item_amount[]': ['30000', '5000'],
            'notes': 'فاتورة اختبار'
        }, follow_redirects=True)
        check("Create invoice succeeds", r.status_code == 200)
        invoice = Invoice.query.first()
        check("Invoice saved in DB", invoice is not None)
        check("Invoice number generated", invoice.invoice_number is not None and invoice.invoice_number.startswith('INV-'))
        check("Invoice has 2 items", invoice.items.count() == 2)
        # subtotal=35000, discount 10%=3500, after=31500, tax 14%=4410, total=35910
        check("Subtotal correct", float(invoice.subtotal) == 35000.0)
        check("Total calculated with discount+tax", abs(float(invoice.total) - 35910.0) < 1)

        r = c.get(f'/financial/invoices/{invoice.id}', headers=headers)
        check("Show invoice loads", r.status_code == 200)

        r = c.get(f'/financial/invoices/{invoice.id}/edit', headers=headers)
        check("Edit invoice form loads", r.status_code == 200)

        r = c.post(f'/financial/invoices/{invoice.id}/edit', headers=headers, data={
            'client_id': client.id, 'case_id': case.id,
            'issue_date': '2026-04-06', 'status': 'sent',
            'tax_rate': '14', 'discount_type': '', 'discount_value': '',
            'item_description[]': ['أتعاب قضية'],
            'item_type[]': ['fees'],
            'item_amount[]': ['40000'],
            'notes': ''
        }, follow_redirects=True)
        check("Edit invoice succeeds", r.status_code == 200)
        db.session.refresh(invoice)
        check("Invoice status updated", invoice.status == 'sent')
        check("Items replaced (now 1)", invoice.items.count() == 1)
        # subtotal=40000, no discount, tax 14%=5600, total=45600
        check("Total recalculated", abs(float(invoice.total) - 45600.0) < 1)

        # Status update
        r = c.post(f'/financial/invoices/{invoice.id}/update-status', headers=headers, data={
            'status': 'paid'
        }, follow_redirects=True)
        check("Quick status update works", r.status_code == 200)
        db.session.refresh(invoice)
        check("Status changed to paid", invoice.status == 'paid')

        # ===== EXPENSES =====
        print("\n=== EXPENSES ===")

        r = c.get('/financial/expenses', headers=headers)
        check("Expenses list loads", r.status_code == 200)

        r = c.get('/financial/expenses/create', headers=headers)
        check("Create expense form loads", r.status_code == 200)

        r = c.post('/financial/expenses/create', headers=headers, data={
            'case_id': case.id, 'client_id': client.id,
            'expense_type': 'court_fees', 'amount': '2000',
            'expense_date': '2026-04-05', 'description': 'رسوم قيد الدعوى'
        }, follow_redirects=True)
        check("Create expense succeeds", r.status_code == 200)
        expense = Expense.query.first()
        check("Expense saved in DB", expense is not None)
        check("Expense amount correct", float(expense.amount) == 2000.0)
        check("Expense type correct", expense.expense_type == 'court_fees')

        r = c.get(f'/financial/expenses/{expense.id}', headers=headers)
        check("Show expense loads", r.status_code == 200)

        # ===== CLIENT STATEMENT =====
        print("\n=== CLIENT STATEMENT ===")

        r = c.get(f'/financial/client-statement/{client.id}', headers=headers)
        check("Client statement loads", r.status_code == 200)

        # ===== DELETES =====
        print("\n=== DELETES ===")

        r = c.post(f'/financial/payments/{payment.id}/delete', headers=headers, follow_redirects=True)
        check("Delete payment succeeds", r.status_code == 200)
        check("Payment deleted", Payment.query.count() == 0)

        r = c.post(f'/financial/invoices/{invoice.id}/delete', headers=headers, follow_redirects=True)
        check("Delete invoice succeeds", r.status_code == 200)
        check("Invoice deleted (cascade items)", Invoice.query.count() == 0)
        check("Invoice items cascaded", InvoiceItem.query.count() == 0)

        r = c.post(f'/financial/expenses/{expense.id}/delete', headers=headers, follow_redirects=True)
        check("Delete expense succeeds", r.status_code == 200)
        check("Expense deleted", Expense.query.count() == 0)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {passed+failed}")
    if failed:
        sys.exit(1)
    else:
        print("Phase 6 ALL PASSED!")
