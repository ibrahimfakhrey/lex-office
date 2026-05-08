"""AI usage governance: ai_usage_events + tenants.ai_warning_sent_month.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_usage_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('feature', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=50), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_creation_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_read_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        'ix_ai_usage_events_tenant_id', 'ai_usage_events', ['tenant_id'],
    )
    op.create_index(
        'ix_ai_usage_events_user_id', 'ai_usage_events', ['user_id'],
    )
    op.create_index(
        'ix_ai_usage_events_feature', 'ai_usage_events', ['feature'],
    )
    op.create_index(
        'ix_ai_usage_events_created_at', 'ai_usage_events', ['created_at'],
    )

    # Composite index used by the monthly-quota query (tenant + month).
    op.create_index(
        'ix_ai_usage_tenant_created',
        'ai_usage_events',
        ['tenant_id', 'created_at'],
    )

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('ai_warning_sent_month', sa.String(length=7), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('ai_warning_sent_month')

    op.drop_index('ix_ai_usage_tenant_created', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_created_at', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_feature', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_user_id', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_tenant_id', table_name='ai_usage_events')
    op.drop_table('ai_usage_events')
