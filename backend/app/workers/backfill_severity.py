"""Rate insights stored before severity existed.

Queues each unrated change insight for the headline task, which writes the
severity (and a fresh headline) the same way it does for new ones.

    python -m app.workers.backfill_severity            # all unrated
    python -m app.workers.backfill_severity --limit 50
"""

import argparse

from app.workers.db import get_mongo_db
from app.workers.tasks.embedding import write_insight_headline

UNRATED = {"kind": {"$ne": "monitoring_started"}, "severity": None}


def queue_unrated(limit: int = 0) -> int:
    cursor = get_mongo_db().insights.find(UNRATED, {"_id": 1}).sort("detected_at", -1)
    if limit:
        cursor = cursor.limit(limit)
    n = 0
    for doc in cursor:
        write_insight_headline.apply_async(args=[str(doc["_id"])], ignore_result=True)
        n += 1
    return n


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="at most this many, newest first")
    print(f"queued {queue_unrated(parser.parse_args().limit)} insights")
