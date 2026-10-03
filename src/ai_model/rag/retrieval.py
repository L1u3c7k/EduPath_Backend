from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_model.rag.vector_store import EmbeddedDocument


MIN_WORDS = 100
DEFAULT_CANDIDATES = 50
MIN_SCORE = 0.55

# Retrieve more rows than ultimately needed because
# some documents will be removed by content filters.
RAW_CANDIDATES = 150


async def retrieve(
    db: AsyncSession,
    query_embedding,
    candidate_count: int = DEFAULT_CANDIDATES,
    min_score: float = MIN_SCORE,
):
    distance = EmbeddedDocument.embedding.cosine_distance(
        query_embedding.tolist()
    ).label("distance")

    rows = await db.execute(
        select(
            EmbeddedDocument.text,
            EmbeddedDocument.document_metadata,
            distance,
        )
        .order_by(distance)
        .limit(
            max(candidate_count * 3, RAW_CANDIDATES)
        )
    )

    results = []

    for row in rows:

        text = row.text
        metadata = row.document_metadata or {}

        content_type = metadata.get("content_type")

        # Ignore empty chunks
        if not text or not text.strip():
            continue

        # Ignore short chunks
        if len(text.split()) < MIN_WORDS:
            continue

        # Ignore tables
        if content_type == "table":
            continue

        # Convert cosine distance to similarity
        score = 1.0 - float(row.distance)

        # Similarity threshold
        if score < min_score:
            break

        results.append({
            "score": score,
            "text": text,
            "metadata": metadata,
        })

        # Return the requested number of usable candidates
        if len(results) >= candidate_count:
            break

    return results