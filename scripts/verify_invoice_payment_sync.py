"""Smoke test for the invoice-paid -> Payment sync fix.

Creates an isolated tenant, client, case, and invoice; flips the invoice
to 'paid' and back; and asserts the linked Payment is created/removed
and that the client KPIs (total_paid / total_due) move correctly.

Run:  python scripts/verify_invoice_payment_sync.py
"""
from datetime import date
from flask import g

from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client
from app.models.case import Case
from app.models.financial import Invoice, InvoiceItem, Payment
from app.blueprints.financial.routes import sync_invoice_payment


def main():
    app = create_app()
    with app.app_context():
        with app.test_request_context():
            user = User.query.join(Tenant, Tenant.id == User.tenant_id).first()
            tenant = Tenant.query.get(user.tenant_id)
            g.tenant_id = tenant.id
            g.current_user = user

            tag = f'sync-test-{date.today().isoformat()}'
            client = Client(
                tenant_id=tenant.id,
                full_name=f'موكل {tag}',
                phone_primary='0500000000',
                is_active=True,
            )
            db.session.add(client)
            db.session.flush()

            case = Case(
                tenant_id=tenant.id,
                client_id=client.id,
                case_number=f'CASE-{tag}',
                case_type='criminal',
                status='new',
                fee_amount=3000,
                responsible_lawyer_id=user.id,
            )
            db.session.add(case)
            db.session.flush()

            invoice = Invoice(
                tenant_id=tenant.id,
                client_id=client.id,
                case_id=case.id,
                issue_date=date.today(),
                status='draft',
                tax_rate=0,
            )
            invoice.generate_invoice_number(tenant.id)
            db.session.add(invoice)
            db.session.flush()
            db.session.add(InvoiceItem(
                invoice_id=invoice.id,
                description='Test fees',
                item_type='fees',
                amount=2280,
            ))
            db.session.flush()
            invoice.calculate_totals()
            db.session.commit()

            print(f'[setup] invoice {invoice.invoice_number}, total={float(invoice.total)}')

            def kpis():
                payments = Payment.query.filter_by(client_id=client.id).all()
                paid = sum(float(p.amount or 0) for p in payments)
                fees = float(case.fee_amount or 0)
                return paid, max(fees - paid, 0), len(payments)

            paid, due, n = kpis()
            print(f'[draft]  total_paid={paid}, total_due={due}, payments={n}')
            assert paid == 0 and due == 3000 and n == 0, 'draft baseline wrong'

            invoice.status = 'paid'
            sync_invoice_payment(invoice)
            db.session.commit()
            paid, due, n = kpis()
            print(f'[paid]   total_paid={paid}, total_due={due}, payments={n}')
            assert paid == 2280 and due == 720 and n == 1, 'paid flip did not sync'

            linked = Payment.query.filter_by(invoice_id=invoice.id).first()
            assert linked and linked.payment_method == 'invoice', 'linked payment missing/wrong method'

            invoice.status = 'sent'
            sync_invoice_payment(invoice)
            db.session.commit()
            paid, due, n = kpis()
            print(f'[unpaid] total_paid={paid}, total_due={due}, payments={n}')
            assert paid == 0 and due == 3000 and n == 0, 'revert did not delete payment'

            invoice.status = 'paid'
            sync_invoice_payment(invoice)
            db.session.commit()
            db.session.delete(invoice)
            db.session.commit()
            paid, due, n = kpis()
            print(f'[del]    total_paid={paid}, total_due={due}, payments={n}')
            assert n == 0, 'cascade delete did not remove linked payment'

            Case.query.filter_by(id=case.id).delete()
            Client.query.filter_by(id=client.id).delete()
            db.session.commit()
            print('OK — sync_invoice_payment behaves correctly in all 4 transitions')


if __name__ == '__main__':
    main()
