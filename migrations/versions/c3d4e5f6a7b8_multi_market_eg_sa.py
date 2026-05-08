"""Multi-market support (EG / SA): add market columns + plan currency/comparison.

Revision ID: c3d4e5f6a7b8
Revises: bfb15b0f1fa4
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'bfb15b0f1fa4'
branch_labels = None
depends_on = None


def upgrade():
    # ── tenants ─────────────────────────────────────────────────────────────
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('market', sa.String(length=2), nullable=False,
                      server_default='eg')
        )
        batch_op.create_index('ix_tenants_market', ['market'])

    # ── courts ──────────────────────────────────────────────────────────────
    with op.batch_alter_table('courts', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('market', sa.String(length=2), nullable=False,
                      server_default='eg')
        )
        batch_op.create_index('ix_courts_market', ['market'])

    # ── subscription_plans ──────────────────────────────────────────────────
    with op.batch_alter_table('subscription_plans', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('market', sa.String(length=2), nullable=False,
                      server_default='eg')
        )
        batch_op.add_column(
            sa.Column('currency_code', sa.String(length=3), nullable=False,
                      server_default='EGP')
        )
        batch_op.add_column(
            sa.Column('comparison', sa.JSON(), nullable=True)
        )
        batch_op.create_index('ix_subscription_plans_market', ['market'])

    # The server_default ensured existing rows got 'eg' / 'EGP' on add. Drop the
    # defaults now so application-layer defaults take over (cleaner DDL going
    # forward; rows are already populated).
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.alter_column('market', server_default=None)
    with op.batch_alter_table('courts', schema=None) as batch_op:
        batch_op.alter_column('market', server_default=None)
    with op.batch_alter_table('subscription_plans', schema=None) as batch_op:
        batch_op.alter_column('market', server_default=None)
        batch_op.alter_column('currency_code', server_default=None)


def downgrade():
    with op.batch_alter_table('subscription_plans', schema=None) as batch_op:
        batch_op.drop_index('ix_subscription_plans_market')
        batch_op.drop_column('comparison')
        batch_op.drop_column('currency_code')
        batch_op.drop_column('market')

    with op.batch_alter_table('courts', schema=None) as batch_op:
        batch_op.drop_index('ix_courts_market')
        batch_op.drop_column('market')

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_index('ix_tenants_market')
        batch_op.drop_column('market')
