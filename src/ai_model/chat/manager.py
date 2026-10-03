from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_model.topic.detector import detect_topic
from src.ai_model.topic.relevance import check_relevance
from src.ai_model.topic.subject import get_subject

from src.ai_model.rag.embedding import embed
from src.ai_model.rag.retrieval import retrieve
from src.ai_model.rag.context import build_context
from src.ai_model.rag.generation import generate_answer


TOP_K = 5
CANDIDATES = 50


def filter_by_subject(
    docs: list[dict],
    subject: str,
) -> list[dict]:

    if not subject:
        return []

    subject = subject.strip().lower()

    filtered = []

    for doc in docs:

        metadata = doc.get(
            "metadata",
            {}
        )

        doc_subject = get_subject(
            metadata
        )

        if not doc_subject:
            continue

        if doc_subject.strip().lower() == subject:
            filtered.append(doc)

    return filtered[:TOP_K]


async def ai_chat(
    question: str,
    db: AsyncSession,
    current_subject: str | None = None,
) -> tuple[str, str | None, dict | None]:

    # --------------------------------------------------
    # 1. Embed question
    # --------------------------------------------------

    q_embedding = embed(
        question
    )

    # --------------------------------------------------
    # 2. Retrieve candidate documents
    # --------------------------------------------------

    candidates = await retrieve(
        db,
        q_embedding,
        candidate_count=CANDIDATES,
    )

    # --------------------------------------------------
    # 3. No relevant documents found
    # --------------------------------------------------

    if not candidates:

        if current_subject is None:
            return (
                "I couldn't find this topic "
                "in the study materials.",
                None,
                None,
            )

        return (
            f"This question does not appear to be "
            f"related to {current_subject}. "
            "Please start a new chat.",
            current_subject,
            None,
        )

    # --------------------------------------------------
    # 4. Determine subject
    # --------------------------------------------------

    # New chat
    if current_subject is None:

        detected = detect_topic(
            candidates
        )

        if detected is None:
            return (
                "I couldn't determine the study subject "
                "from the available study materials.",
                None,
                None,
            )

        subject = detected["subject"]

    # Existing chat
    else:

        subject = current_subject

        if not check_relevance(
            subject,
            candidates,
        ):
            return (
                f"This chat is about "
                f"{subject}. "
                "Please start a new chat.",
                subject,
                None,
            )

    # --------------------------------------------------
    # 5. Keep only documents from this subject
    # --------------------------------------------------

    docs = filter_by_subject(
        candidates,
        subject,
    )

    if not docs:
        return (
            f"This question does not appear to be "
            f"related to {subject}. "
            "Please start a new chat.",
            subject,
            None,
        )

    # --------------------------------------------------
    # 6. Get hierarchy for this turn
    # --------------------------------------------------

    metadata = docs[0].get(
        "metadata",
        {}
    )

    hierarchy = {
        "chapter": metadata.get("chapter"),
        "topic": metadata.get("topic"),
        "subtopic": metadata.get("subtopic"),
    }

    # --------------------------------------------------
    # 7. Build RAG context
    # --------------------------------------------------

    context = build_context(
        docs
    )

    # --------------------------------------------------
    # 8. Generate answer
    # --------------------------------------------------

    answer = generate_answer(
        question,
        context,
    )

    # --------------------------------------------------
    # 9. Return everything needed by the chat service
    # --------------------------------------------------

    return (
        answer,
        subject,
        hierarchy,
    )