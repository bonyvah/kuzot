from bson import ObjectId

from app.workers.celery_app import celery_app
from app.workers.db import get_mongo_db


@celery_app.task(name="app.workers.tasks.embedding.process_change_event")
def process_change_event(event_id: str) -> dict:
    # Week 6: chunk -> OpenAI embeddings -> Pinecone. Stub for now.
    mongo_db = get_mongo_db()
    event = mongo_db.change_events.find_one({"_id": ObjectId(event_id)})
    if event is None:
        raise ValueError(f"Change event not found for id: {event_id}")

    return {
        "event_id": event_id,
        "monitored_url_id": event["monitored_url_id"],
        "new_hash": event["new_hash"],
    }