"""Per-user read state for insights.

Two collections, so "mark all read" is a single write:

- insight_cursors: {user_id, org_id, seen_until}. Every insight detected at or
  before seen_until counts as seen. With no cursor yet, the user's join date
  stands in, so a new member doesn't start with the org's whole history unread.
- insight_states: one doc per (user, insight) the user did something with:
  seen_at, opened_at, saved_at, dismissed_at. It copies the insight's tenant ids
  and detected_at so unread queries need no join.
"""

from datetime import UTC, datetime
from typing import Literal

from pymongo import UpdateOne

Action = Literal["seen", "open", "save", "unsave", "dismiss", "restore"]
FeedState = Literal["all", "unread", "saved"]
MinSeverity = Literal["medium", "high"]


def severity_filter(min_severity: MinSeverity | None = None) -> dict:
    """Insights worth showing: never those rated none; unrated ones are shown too."""
    if min_severity == "high":
        return {"severity": "high"}
    if min_severity == "medium":
        return {"severity": {"$in": ["medium", "high"]}}
    return {"severity": {"$ne": "none"}}


def utcnow() -> datetime:
    """Naive UTC, like the timestamps pymongo hands back."""
    return datetime.now(UTC).replace(tzinfo=None)


async def seen_until(mongo, user_id: str, org_id: str, default: datetime) -> datetime:
    doc = await mongo.insight_cursors.find_one({"user_id": user_id, "org_id": org_id})
    return doc["seen_until"] if doc else default


async def set_seen_until(mongo, user_id: str, org_id: str, at: datetime) -> None:
    await mongo.insight_cursors.update_one(
        {"user_id": user_id, "org_id": org_id}, {"$set": {"seen_until": at}}, upsert=True
    )


async def _ids(mongo, query: dict) -> list:
    return [d["insight_id"] async for d in mongo.insight_states.find(query, {"insight_id": 1})]


async def _read_ids(mongo, user_id: str, org_id: str, watermark: datetime) -> list:
    """Insights after the watermark that the user has seen or dismissed one by one."""
    return await _ids(mongo, {
        "user_id": user_id,
        "org_id": org_id,
        "detected_at": {"$gt": watermark},
        "$or": [{"seen_at": {"$ne": None}}, {"dismissed_at": {"$ne": None}}],
    })


async def feed_filter(mongo, user_id: str, org_id: str, watermark: datetime, state: FeedState) -> dict:
    """The extra insight query terms for a feed tab."""
    if state == "saved":
        return {"_id": {"$in": await _ids(mongo, {"user_id": user_id, "org_id": org_id, "saved_at": {"$ne": None}})}}
    if state == "unread":
        return {"detected_at": {"$gt": watermark}, "_id": {"$nin": await _read_ids(mongo, user_id, org_id, watermark)}}
    # all: everything but what the user dismissed
    dismissed = await _ids(mongo, {"user_id": user_id, "org_id": org_id, "dismissed_at": {"$ne": None}})
    return {"_id": {"$nin": dismissed}} if dismissed else {}


async def states_for(mongo, user_id: str, docs: list[dict], watermark: datetime) -> dict[str, dict]:
    """{insight id: {seen, opened, saved, dismissed}} for insight documents."""
    found = {
        s["insight_id"]: s
        async for s in mongo.insight_states.find(
            {"user_id": user_id, "insight_id": {"$in": [d["_id"] for d in docs]}}
        )
    }
    out = {}
    for d in docs:
        s = found.get(d["_id"], {})
        out[str(d["_id"])] = {
            "seen": d["detected_at"] <= watermark or s.get("seen_at") is not None,
            "opened": s.get("opened_at") is not None,
            "saved": s.get("saved_at") is not None,
            "dismissed": s.get("dismissed_at") is not None,
        }
    return out


# Each action as a Mongo update. $min keeps the first time something was seen.
def _update(action: Action, at: datetime) -> dict:
    match action:
        case "seen":
            return {"$min": {"seen_at": at}}
        case "open":
            return {"$min": {"seen_at": at, "opened_at": at}}
        case "save":
            return {"$set": {"saved_at": at}, "$unset": {"dismissed_at": ""}}
        case "unsave":
            return {"$unset": {"saved_at": ""}}
        case "dismiss":
            # dismissing reads it and takes it off the saved list
            return {"$min": {"seen_at": at}, "$set": {"dismissed_at": at}, "$unset": {"saved_at": ""}}
        case "restore":
            return {"$unset": {"dismissed_at": ""}}


async def apply(mongo, user_id: str, docs: list[dict], action: Action, at: datetime) -> None:
    if not docs:
        return
    ops = []
    for d in docs:
        update = _update(action, at)
        update["$setOnInsert"] = {
            "org_id": d["org_id"],
            "workspace_id": d["workspace_id"],
            "competitor_id": d["competitor_id"],
            "detected_at": d["detected_at"],
        }
        ops.append(UpdateOne({"user_id": user_id, "insight_id": d["_id"]}, update, upsert=True))
    await mongo.insight_states.bulk_write(ops, ordered=False)


async def unread_counts(
    mongo, user_id: str, org_id: str, watermark: datetime, min_severity: MinSeverity | None = None
) -> dict[tuple[str, str], int]:
    """Unread insights per (workspace_id, competitor_id)."""
    read = await _read_ids(mongo, user_id, org_id, watermark)
    match = {"org_id": org_id, "detected_at": {"$gt": watermark}, "_id": {"$nin": read}}
    pipeline = [
        {"$match": match | severity_filter(min_severity)},
        {"$group": {"_id": {"w": "$workspace_id", "c": "$competitor_id"}, "n": {"$sum": 1}}},
    ]
    return {
        (row["_id"]["w"], row["_id"]["c"]): row["n"]
        async for row in mongo.insights.aggregate(pipeline)
    }
