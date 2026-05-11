"""Phase 3 (option a): Encrypt Client.national_id with blind index.

- Widens clients.national_id from VARCHAR(20) to TEXT (Fernet ciphertexts
  are ~120+ bytes, can't fit in VARCHAR(20)).
- Adds clients.national_id_idx VARCHAR(64) with an index for blind-index
  exact-match lookups.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients') as batch:
        batch.alter_column(
            'national_id',
            existing_type=sa.String(length=20),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch.add_column(sa.Column('national_id_idx', sa.String(length=64), nullable=True))
    op.create_index(
        'ix_clients_national_id_idx', 'clients', ['national_id_idx'],
    )


def downgrade():
    op.drop_index('ix_clients_national_id_idx', table_name='clients')
    with op.batch_alter_table('clients') as batch:
        batch.drop_column('national_id_idx')
        batch.alter_column(
            'national_id',
            existing_type=sa.Text(),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
