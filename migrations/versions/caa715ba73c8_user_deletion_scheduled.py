"""user_deletion_scheduled

Revision ID: caa715ba73c8
Revises: f44a4a28d811
Create Date: 2026-05-18 09:58:47.867554

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'caa715ba73c8'
down_revision = 'f44a4a28d811'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deletion_scheduled_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deletion_reason', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('deletion_reason')
        batch_op.drop_column('deletion_scheduled_at')
