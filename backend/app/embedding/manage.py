"""Vector index maintenance.

    python -m app.embedding.manage init-index   # create the prod serverless index
    python -m app.embedding.manage reindex      # rebuild Pinecone from page_chunks

Pinecone Local keeps vectors in memory only, so run `reindex` after its
container restarts. Embeddings come from Mongo, so no OpenAI calls are made.
"""

import argparse
from collections import defaultdict

from app.core.config import settings
from app.embedding import vector_store
from app.workers.db import get_mongo_db
from app.workers.embedding_pipeline import pinecone_record


def reindex() -> None:
    by_org: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for doc in get_mongo_db().page_chunks.find():
        if doc.get("embedding_model") != settings.OPENAI_EMBEDDING_MODEL:
            skipped += 1  # vectors from another model don't fit this index
            continue
        by_org[doc["org_id"]].append(pinecone_record(doc))
    for org_id, records in by_org.items():
        vector_store.upsert(records, namespace=org_id)
    total = sum(len(r) for r in by_org.values())
    print(f"upserted {total} vectors across {len(by_org)} orgs; skipped {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.embedding.manage")
    parser.add_argument("command", choices=["init-index", "reindex"])
    args = parser.parse_args()
    if args.command == "init-index":
        created = vector_store.ensure_index()
        print("index created" if created else "index exists (or Pinecone Local)")
    else:
        reindex()


if __name__ == "__main__":
    main()
