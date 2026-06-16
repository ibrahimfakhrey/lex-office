"""tasks.session_id link (auto-task from session)

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-16 15:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_tasks_session_id',
            'sessions',
            ['session_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_index('ix_tasks_session_id', ['session_id'])


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index('ix_tasks_session_id')
        batch_op.drop_constraint('fk_tasks_session_id', type_='foreignkey')
        batch_op.drop_column('session_id')
