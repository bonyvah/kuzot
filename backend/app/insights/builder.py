"""Insights: what changed on a monitored page, built from one change event.

A change event becomes an insight once its passages are diffed (in the
embedding step). The insight's id is the change event's id, so building it
twice for the same event is harmless.
"""

import difflib
from datetime import datetime

# enough to read the change; a full page rewrite would otherwise be enormous
MAX_PASSAGES = 20
MAX_DIFF_LINES = 80
# unchanged lines kept around each change, so a new price says which product
CONTEXT_LINES = 2

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


def line_diff(removed: list[str], added: list[str]) -> list[list[dict]]:
    """Changed lines between the old and new passages, grouped into hunks.

    Passages are whole chunks of a page; one edited price would otherwise show
    as two near-identical blocks. Each line is {"op": context|removed|added, "text"}.
    """
    old = [line for text in removed for line in text.splitlines() if line.strip()]
    new = [line for text in added for line in text.splitlines() if line.strip()]
    hunks: list[list[dict]] = []
    budget = MAX_DIFF_LINES
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for group in matcher.get_grouped_opcodes(CONTEXT_LINES):
        hunk = []
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                hunk += [{"op": "context", "text": t} for t in old[i1:i2]]
                continue
            hunk += [{"op": "removed", "text": t} for t in old[i1:i2]]
            hunk += [{"op": "added", "text": t} for t in new[j1:j2]]
        hunks.append(hunk[:budget])
        budget -= len(hunk)
        if budget <= 0:
            break
    return hunks


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
        "diff": line_diff(removed, added),
        "added": added[:MAX_PASSAGES],
        "removed": removed[:MAX_PASSAGES],
        "added_count": len(added),
        "removed_count": len(removed),
        "headline": fallback_headline(tenant["url_type"], tenant.get("label")),
        "headline_status": "pending",
    }
