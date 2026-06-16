"""tasks: reminder_offset_days + reminder_sent_at

Revision ID: a8b9c0d1e2f3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-16 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a8b9c0d1e2f3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reminder_offset_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('reminder_sent_at')
        batch_op.drop_column('reminder_offset_days')
