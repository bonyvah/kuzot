from bson import ObjectId

from app.insights.headline import assess_change, is_trivial
from app.models import Competitor
from app.workers.db import SyncSession, get_mongo_db


def write_headline(insight_id: str) -> str | None:
    """Write the AI headline and severity for an insight; None if it's gone or already written."""
    mongo = get_mongo_db()
    oid = ObjectId(insight_id)
    insight = mongo.insights.find_one({"_id": oid})
    # done and rated: nothing to do. Done but unrated (stored before severity existed) is redone.
    if insight is None or (insight.get("headline_status") == "done" and insight.get("severity")):
        return None
    if is_trivial(insight):
        # lines only moved or were re-spaced: not worth a model call, and never shown
        mongo.insights.update_one(
            {"_id": oid},
            {"$set": {
                "headline_status": "done",
                "severity": "none",
                "severity_reason": "Only reordered or reformatted lines",
            }},
        )
        return insight["headline"]
    with SyncSession() as db:
        competitor = db.get(Competitor, insight["competitor_id"])
    if competitor is None:
        return None  # deleted meanwhile; its insights aren't shown
    result = assess_change(insight, competitor.name)
    mongo.insights.update_one(
        {"_id": oid},
        {"$set": {
            "headline": result.headline,
            "headline_status": "done",
            "severity": result.severity,
            "severity_reason": result.reason,
        }},
    )
    return result.headline


def mark_headline_failed(insight_id: str) -> None:
    # severity stays unset: the insight is shown, unrated
    get_mongo_db().insights.update_one(
        {"_id": ObjectId(insight_id)}, {"$set": {"headline_status": "failed"}}
    )
