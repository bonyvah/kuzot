"""Monitored URLs unique per competitor, not globally

Revision ID: 004_url_unique_per_competitor
Revises: 003_page_labels
Create Date: 2026-11-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '004_url_unique_per_competitor'
down_revision: Union[str, None] = '003_page_labels'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('monitored_urls_url_key', 'monitored_urls', type_='unique')
    op.create_unique_constraint(
        'uq_monitored_urls_competitor_url', 'monitored_urls', ['competitor_id', 'url']
    )


def downgrade() -> None:
    # fails if two competitors now share a URL; remove the duplicates first
    op.drop_constraint('uq_monitored_urls_competitor_url', 'monitored_urls', type_='unique')
    op.create_unique_constraint('monitored_urls_url_key', 'monitored_urls', ['url'])
