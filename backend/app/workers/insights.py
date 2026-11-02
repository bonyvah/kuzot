from bson import ObjectId

from app.insights.headline import generate_headline
from app.models import Competitor
from app.workers.db import SyncSession, get_mongo_db


def write_headline(insight_id: str) -> str | None:
    """Write the AI headline for an insight; None if it's gone or already written."""
    mongo = get_mongo_db()
    oid = ObjectId(insight_id)
    insight = mongo.insights.find_one({"_id": oid})
    if insight is None or insight.get("headline_status") == "done":
        return None
    with SyncSession() as db:
        competitor = db.get(Competitor, insight["competitor_id"])
    if competitor is None:
        return None  # deleted meanwhile; its insights aren't shown
    headline = generate_headline(insight, competitor.name)
    mongo.insights.update_one(
        {"_id": oid}, {"$set": {"headline": headline, "headline_status": "done"}}
    )
    return headline


def mark_headline_failed(insight_id: str) -> None:
    get_mongo_db().insights.update_one(
        {"_id": ObjectId(insight_id)}, {"$set": {"headline_status": "failed"}}
    )
