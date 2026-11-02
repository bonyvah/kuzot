"""Organization and workspace avatars

Revision ID: 002_avatars
Revises: 001_initial_schema
Create Date: 2026-11-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_avatars'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('organizations', 'workspaces')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('avatar_emoji', sa.String(length=32), nullable=True))
        op.add_column(table, sa.Column('avatar_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'avatar_key')
        op.drop_column(table, 'avatar_emoji')
