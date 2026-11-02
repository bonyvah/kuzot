"""Label for "other" monitored pages; daily default interval

Revision ID: 003_page_labels
Revises: 002_avatars
Create Date: 2026-11-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003_page_labels'
down_revision: Union[str, None] = '002_avatars'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New page types (instagram, telegram, facebook, x, other) fit the
    # existing url_type VARCHAR(50); only "other" needs a label.
    op.add_column('monitored_urls', sa.Column('label', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('monitored_urls', 'label')
