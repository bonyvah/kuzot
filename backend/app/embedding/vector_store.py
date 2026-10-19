from functools import cache

from pinecone import Pinecone, ServerlessSpec
from pinecone.errors import ResponseParsingError

from app.core.config import settings

UPSERT_BATCH = 100


def vector_id(monitored_url_id: str, chunk_hash: str) -> str:
    return f"{monitored_url_id}#{chunk_hash}"


@cache
def get_client() -> Pinecone:
    return Pinecone(api_key=settings.PINECONE_API_KEY)


@cache
def get_index():
    # Pinecone Local serves one index at a fixed host; in prod resolve it by name
    if settings.PINECONE_HOST:
        return get_client().Index(host=settings.PINECONE_HOST)
    return get_client().Index(name=settings.PINECONE_INDEX_NAME)


def ensure_index() -> bool:
    """Create the serverless index if missing (prod only). True when created."""
    if settings.PINECONE_HOST:
        return False  # Pinecone Local creates its index from container env
    client = get_client()
    if client.has_index(settings.PINECONE_INDEX_NAME):
        return False
    client.create_index(
        name=settings.PINECONE_INDEX_NAME,
        dimension=settings.EMBEDDING_DIMENSIONS,
        metric="cosine",
        spec=ServerlessSpec(
            cloud=settings.PINECONE_CLOUD, region=settings.PINECONE_REGION
        ),
    )
    return True


def upsert(vectors: list[dict], namespace: str) -> None:
    index = get_index()
    for start in range(0, len(vectors), UPSERT_BATCH):
        index.upsert(vectors=vectors[start : start + UPSERT_BATCH], namespace=namespace)


def set_metadata(ids: list[str], metadata: dict, namespace: str) -> None:
    index = get_index()
    for id_ in ids:
        try:
            index.update(id=id_, set_metadata=metadata, namespace=namespace)
        except ResponseParsingError:
            # Pinecone Local applies the update but answers with a non-JSON body
            pass
