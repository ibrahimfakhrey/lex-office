"""Add tasks.session_id FK (CASCADE) for session-reminder tasks

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-06-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f0a1b2c3d4e5'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tasks_session_id', 'tasks', 'sessions',
        ['session_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_tasks_session_id', 'tasks', ['session_id'])


def downgrade():
    op.drop_index('ix_tasks_session_id', table_name='tasks')
    op.drop_constraint('fk_tasks_session_id', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'session_id')
