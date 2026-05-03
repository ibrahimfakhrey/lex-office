"""Users: global unique email + partial unique phone

Revision ID: a1b2c3d4e5f6
Revises: 85c5aa2a6892
Create Date: 2026-05-03 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '85c5aa2a6892'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('users_tenant_id_email_key', 'users', type_='unique')
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
    op.execute(
        "CREATE UNIQUE INDEX uq_users_phone_not_null ON users (phone) "
        "WHERE phone IS NOT NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_users_phone_not_null")
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.create_unique_constraint('users_tenant_id_email_key', 'users', ['tenant_id', 'email'])
