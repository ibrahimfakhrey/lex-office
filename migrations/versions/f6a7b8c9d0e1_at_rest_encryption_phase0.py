"""At-rest encryption Phase 0: tenants.encryption_key (DEK envelope).

Adds a per-tenant Data Encryption Key (DEK), itself encrypted by the master
Fernet key in ENCRYPTION_MASTER_KEY. The DEK is lazy-generated on first
encryption call for a tenant.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tenants') as batch:
        batch.add_column(sa.Column('encryption_key', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('tenants') as batch:
        batch.drop_column('encryption_key')
