"""terms_acceptances table

Revision ID: c2d3e4f5a6b7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a6b7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'terms_acceptances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'version', name='uq_terms_acceptances_user_version'),
    )
    op.create_index('ix_terms_acceptances_user_id', 'terms_acceptances', ['user_id'])
    op.create_index('ix_terms_acceptances_tenant_id', 'terms_acceptances', ['tenant_id'])


def downgrade():
    op.drop_index('ix_terms_acceptances_tenant_id', table_name='terms_acceptances')
    op.drop_index('ix_terms_acceptances_user_id', table_name='terms_acceptances')
    op.drop_table('terms_acceptances')
