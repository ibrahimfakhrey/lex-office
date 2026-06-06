"""payments.invoice_id link + backfill from paid invoices

Revision ID: d7e8f9a0b1c2
Revises: caa715ba73c8
Create Date: 2026-06-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd7e8f9a0b1c2'
down_revision = 'caa715ba73c8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('invoice_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_payments_invoice_id',
            'invoices',
            ['invoice_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_index('ix_payments_invoice_id', ['invoice_id'])

    # Backfill: for every paid invoice with no linked Payment, create one
    # using invoice.total as the amount and invoice.issue_date as the date.
    op.execute("""
        INSERT INTO payments (
            tenant_id, client_id, case_id, invoice_id,
            amount, payment_date, payment_method,
            reference_number, created_at, updated_at
        )
        SELECT
            i.tenant_id, i.client_id, i.case_id, i.id,
            i.total, i.issue_date, 'invoice',
            i.invoice_number, NOW(), NOW()
        FROM invoices i
        WHERE i.status = 'paid'
          AND NOT EXISTS (
              SELECT 1 FROM payments p WHERE p.invoice_id = i.id
          );
    """)


def downgrade():
    # Remove auto-created invoice-linked payments first
    op.execute("DELETE FROM payments WHERE invoice_id IS NOT NULL")
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_index('ix_payments_invoice_id')
        batch_op.drop_constraint('fk_payments_invoice_id', type_='foreignkey')
        batch_op.drop_column('invoice_id')
