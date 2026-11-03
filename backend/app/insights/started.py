"""Insights for pages that just started being monitored.

They have no diff: they mark in the feed when Kuzot began watching a page,
so the first real change has something before it.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

from app.db.mongo import get_mongo_db
from app.models.monitored_url import MonitoredURL

log = logging.getLogger(__name__)

_NAMES = {
    "homepage": "homepage",
    "pricing": "pricing page",
    "blog": "blog",
    "docs": "docs",
    "changelog": "changelog",
    "instagram": "Instagram",
    "telegram": "Telegram channel",
    "facebook": "Facebook page",
    "x": "X account",
}


def started_headline(url_type: str, label: str | None) -> str:
    name = (label or "page") if url_type == "other" else _NAMES.get(url_type, "page")
    return f"Now monitoring their {name}"


def started_insight(url: MonitoredURL, org_id: str, workspace_id: str, at: datetime) -> dict:
    url_type = str(url.url_type)
    return {
        "kind": "monitoring_started",
        "org_id": org_id,
        "workspace_id": workspace_id,
        "competitor_id": str(url.competitor_id),
        "monitored_url_id": str(url.id),
        "url": url.url,
        "url_type": url_type,
        "label": url.label,
        "detected_at": at,
        "headline": started_headline(url_type, url.label),
        "headline_status": "done",
        "diff": [],
        "added": [],
        "removed": [],
        "added_count": 0,
        "removed_count": 0,
    }


async def record_monitoring_started(urls: Iterable[MonitoredURL], *, org_id, workspace_id) -> None:
    """Best effort: the page is monitored either way, so a Mongo error is only logged."""
    now = datetime.now(UTC).replace(tzinfo=None)  # naive UTC, like change insights
    docs = [started_insight(u, str(org_id), str(workspace_id), now) for u in urls]
    if not docs:
        return
    try:
        await get_mongo_db().insights.insert_many(docs, ordered=False)
    except Exception:
        log.exception("Couldn't record monitoring-started insights")
