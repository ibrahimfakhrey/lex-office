"""Add paid_amount + invoice attachment columns to subscription_payments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-03 10:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscription_payments', sa.Column('paid_amount', sa.Numeric(10, 2), nullable=True))
    op.add_column('subscription_payments', sa.Column('attached_invoice_path', sa.String(length=500), nullable=True))
    op.add_column('subscription_payments', sa.Column('attached_invoice_filename', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('subscription_payments', 'attached_invoice_filename')
    op.drop_column('subscription_payments', 'attached_invoice_path')
    op.drop_column('subscription_payments', 'paid_amount')
