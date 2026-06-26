"""Add reminder_before_days to tasks (LexOffice Egypt port)

Revision ID: e1f2a3b4c5d6
Revises: b9c0d1e2f3a4
Create Date: 2026-06-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'b9c0d1e2f3a4'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('tasks', sa.Column('reminder_before_days', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('tasks', 'reminder_before_days')
