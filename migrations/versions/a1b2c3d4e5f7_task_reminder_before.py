"""Add tasks.reminder_before_days + reminder_sent_at

Revision ID: a1b2c3d4e5f7
Revises: f0a1b2c3d4e5
Create Date: 2026-06-11 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f7'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('reminder_before_days', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('tasks', 'reminder_sent_at')
    op.drop_column('tasks', 'reminder_before_days')
