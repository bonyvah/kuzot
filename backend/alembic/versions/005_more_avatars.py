"""Competitor and user avatars

Revision ID: 005_more_avatars
Revises: 004_url_unique_per_competitor
Create Date: 2026-11-03 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '005_more_avatars'
down_revision: Union[str, None] = '004_url_unique_per_competitor'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('competitors', 'users')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('avatar_emoji', sa.String(length=32), nullable=True))
        op.add_column(table, sa.Column('avatar_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'avatar_key')
        op.drop_column(table, 'avatar_emoji')
