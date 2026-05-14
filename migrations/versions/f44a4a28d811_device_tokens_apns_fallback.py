"""device_tokens_apns_fallback

Revision ID: f44a4a28d811
Revises: c1e458d051eb
Create Date: 2026-05-14 12:19:33.744875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f44a4a28d811'
down_revision = 'c1e458d051eb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('device_tokens', schema=None) as batch_op:
        batch_op.add_column(sa.Column('apns_token', sa.Text(), nullable=True))
        batch_op.alter_column('fcm_token',
               existing_type=sa.TEXT(),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_device_tokens_apns_token'), ['apns_token'], unique=False)


def downgrade():
    with op.batch_alter_table('device_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_device_tokens_apns_token'))
        batch_op.alter_column('fcm_token',
               existing_type=sa.TEXT(),
               nullable=False)
        batch_op.drop_column('apns_token')
