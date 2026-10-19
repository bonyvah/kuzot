from functools import cache

from openai import OpenAI

from app.core.config import settings

BATCH_SIZE = 100  # inputs per embeddings request (API allows up to 2048)


@cache
def get_openai() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        response = get_openai().embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts[start : start + BATCH_SIZE],
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        # the API may return items out of order; index says where each belongs
        vectors.extend(
            item.embedding for item in sorted(response.data, key=lambda d: d.index)
        )
    return vectors
