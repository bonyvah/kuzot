"""Insights: what changed on a monitored page, built from one change event.

A change event becomes an insight once its passages are diffed (in the
embedding step). The insight's id is the change event's id, so building it
twice for the same event is harmless.
"""

from datetime import datetime

# enough to read the change; a full page rewrite would otherwise be enormous
MAX_PASSAGES = 20

_FALLBACK = {
    "homepage": "Homepage changed",
    "pricing": "Pricing page changed",
    "blog": "New blog content",
    "docs": "Docs changed",
    "changelog": "Changelog updated",
    "instagram": "New Instagram activity",
    "telegram": "New Telegram posts",
    "facebook": "New Facebook activity",
    "x": "New posts on X",
}


def fallback_headline(url_type: str, label: str | None) -> str:
    """Shown until (or if) the AI headline is written."""
    if url_type == "other":
        return f"{label or 'Page'} changed"
    return _FALLBACK.get(url_type, "Page changed")


def build_insight(
    tenant: dict, added: list[str], removed: list[str], detected_at: datetime
) -> dict:
    """The insight document for a diff; the caller stores it under the event's id."""
    return {
        "org_id": tenant["org_id"],
        "workspace_id": tenant["workspace_id"],
        "competitor_id": tenant["competitor_id"],
        "monitored_url_id": tenant["monitored_url_id"],
        "url": tenant["url"],
        "url_type": tenant["url_type"],
        "label": tenant.get("label"),
        "detected_at": detected_at,
        "added": added[:MAX_PASSAGES],
        "removed": removed[:MAX_PASSAGES],
        "added_count": len(added),
        "removed_count": len(removed),
        "headline": fallback_headline(tenant["url_type"], tenant.get("label")),
        "headline_status": "pending",
    }
